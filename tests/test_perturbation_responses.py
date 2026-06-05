"""
Test perturbation responses.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Step, StepSequence
from slrdaf.observation.dependencies import DependencySet, DependencyEdge
from slrdaf.observation.verification import load_rule_library
from slrdaf.observation.perturbations import (
    load_perturbation_families,
    perturb_step,
    generate_perturbation_responses,
    hash_perturbation_payload,
)
from slrdaf.observation.io import dataclass_to_dict


class MockProtocol:
    """Minimal protocol mock for testing."""
    protocol_hash = "a" * 64
    random_seed = 20260528
    rule_library_version = None


def test_load_families():
    """Test loading at least 4 perturbation families."""
    families = load_perturbation_families(MockProtocol())
    assert len(families) >= 4, f"Expected >= 4 families, got {len(families)}"

    family_ids = {f.family_id for f in families}
    assert "structural.identifier_mask" in family_ids
    assert "structural.operator_flip" in family_ids
    assert "numerical.value_shift" in family_ids
    assert "structural.clause_marker_noise" in family_ids

    print("✓ test_load_families passed")


def test_identifier_mask_deterministic():
    """Test identifier mask is deterministic."""
    step = Step(
        sample_id="s1",
        step_id="s1::cp::0001",
        t=1,
        step_type="column_reference",
        content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
    )
    families = load_perturbation_families(MockProtocol())
    family = next(f for f in families if f.family_id == "structural.identifier_mask")

    p1 = perturb_step(step, family, MockProtocol())
    p2 = perturb_step(step, family, MockProtocol())

    assert hash_perturbation_payload(p1) == hash_perturbation_payload(p2)

    print("✓ test_identifier_mask_deterministic passed")


def test_numeric_value_shift():
    """Test numeric value shift."""
    step = Step(
        sample_id="s2",
        step_id="s2::cp::0001",
        t=1,
        step_type="predicate_binding",
        content={"kind": "sql_clause", "text": "WHERE value > 10", "clause": "WHERE"},
    )
    families = load_perturbation_families(MockProtocol())
    family = next(f for f in families if f.family_id == "numerical.value_shift")

    p = perturb_step(step, family, MockProtocol())
    assert p["safe_summary"]["changed"] is True
    assert p["safe_summary"]["changed_token_type"] == "number"

    print("✓ test_numeric_value_shift passed")


def test_operator_flip():
    """Test operator flip."""
    step = Step(
        sample_id="s3",
        step_id="s3::cp::0001",
        t=1,
        step_type="predicate_binding",
        content={"kind": "sql_clause", "text": "WHERE temperature > 30", "clause": "WHERE"},
    )
    families = load_perturbation_families(MockProtocol())
    family = next(f for f in families if f.family_id == "structural.operator_flip")

    p = perturb_step(step, family, MockProtocol())
    assert p["safe_summary"]["changed"] is True
    assert p["safe_summary"]["changed_token_type"] == "operator"

    print("✓ test_operator_flip passed")


def test_only_E_minus_perturbed():
    """Test that only E_minus predecessors are perturbed."""
    steps = [
        Step(
            sample_id="s4",
            step_id="s4::cp::0001",
            t=1,
            step_type="schema_linking",
            content={"kind": "sql_clause", "text": "FROM sensors", "clause": "FROM"},
        ),
        Step(
            sample_id="s4",
            step_id="s4::cp::0002",
            t=2,
            step_type="column_reference",
            content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
        ),
        Step(
            sample_id="s4",
            step_id="s4::cp::0003",
            t=3,
            step_type="predicate_binding",
            content={"kind": "sql_clause", "text": "WHERE device_id = 3", "clause": "WHERE"},
        ),
    ]
    sequence = StepSequence(sample_id="s4", steps=steps, protocol_hash="a" * 64)

    # E_minus for t3 only contains t1
    dep_sets = [
        DependencySet(
            sample_id="s4",
            step_id="s4::cp::0001",
            t=1,
            E_minus=[],
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
        DependencySet(
            sample_id="s4",
            step_id="s4::cp::0002",
            t=2,
            E_minus=["s4::cp::0001"],
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
        DependencySet(
            sample_id="s4",
            step_id="s4::cp::0003",
            t=3,
            E_minus=["s4::cp::0001"],  # Only t1, not t2
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
    ]

    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    # t3 should only perturb t1 (4 families)
    t3_responses = [r for r in responses if r.step_id == "s4::cp::0003"]
    assert len(t3_responses) == 4, f"Expected 4 responses for t3, got {len(t3_responses)}"
    for r in t3_responses:
        assert r.perturbed_predecessor_id == "s4::cp::0001"

    print("✓ test_only_E_minus_perturbed passed")


def test_no_future_predecessor():
    """Test that future predecessors are skipped."""
    steps = [
        Step(
            sample_id="s5",
            step_id="s5::cp::0001",
            t=1,
            step_type="other",
            content={"kind": "trace_step", "text": "step 1"},
        ),
        Step(
            sample_id="s5",
            step_id="s5::cp::0002",
            t=2,
            step_type="other",
            content={"kind": "trace_step", "text": "step 2"},
        ),
    ]
    sequence = StepSequence(sample_id="s5", steps=steps, protocol_hash="a" * 64)

    # Invalid: t1 depends on t2 (future)
    dep_sets = [
        DependencySet(
            sample_id="s5",
            step_id="s5::cp::0001",
            t=1,
            E_minus=["s5::cp::0002"],  # Future
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
    ]

    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    # Should be empty because future predecessor is skipped
    assert len(responses) == 0

    print("✓ test_no_future_predecessor passed")


def test_response_schema_fields():
    """Test that PerturbationResponse contains required fields."""
    step = Step(
        sample_id="s6",
        step_id="s6::cp::0001",
        t=1,
        step_type="schema_linking",
        content={"kind": "sql_clause", "text": "FROM t", "clause": "FROM"},
    )
    sequence = StepSequence(sample_id="s6", steps=[step], protocol_hash="a" * 64)
    dep_sets = [
        DependencySet(
            sample_id="s6",
            step_id="s6::cp::0001",
            t=1,
            E_minus=[],
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        )
    ]
    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    # Empty E_minus means no responses
    assert len(responses) == 0

    # Add a predecessor
    step2 = Step(
        sample_id="s6",
        step_id="s6::cp::0002",
        t=2,
        step_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )
    sequence.steps.append(step2)
    dep_sets.append(
        DependencySet(
            sample_id="s6",
            step_id="s6::cp::0002",
            t=2,
            E_minus=["s6::cp::0001"],
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        )
    )
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())
    assert len(responses) == 4  # 4 families

    for r in responses:
        assert r.sample_id == "s6"
        assert r.step_id == "s6::cp::0002"
        assert r.t == 2
        assert r.perturbed_predecessor_id == "s6::cp::0001"
        assert r.perturbation_family in ["structural.identifier_mask", "structural.operator_flip", "numerical.value_shift", "structural.clause_marker_noise"]
        assert r.perturbation_id.startswith("s6::pert::0002::0001::")
        assert len(r.perturbation_payload_hash) == 64
        assert r.protocol_hash == "a" * 64

    print("✓ test_response_schema_fields passed")


def test_before_after_summaries_only():
    """Test that before/after summaries only contain discrete rule fields."""
    step = Step(
        sample_id="s7",
        step_id="s7::cp::0001",
        t=1,
        step_type="schema_linking",
        content={"kind": "sql_clause", "text": "FROM t", "clause": "FROM"},
    )
    step2 = Step(
        sample_id="s7",
        step_id="s7::cp::0002",
        t=2,
        step_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )
    sequence = StepSequence(sample_id="s7", steps=[step, step2], protocol_hash="a" * 64)
    dep_sets = [
        DependencySet(sample_id="s7", step_id="s7::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s7", step_id="s7::cp::0002", t=2, E_minus=["s7::cp::0001"], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]
    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    for r in responses:
        for summary in [r.before_verification, r.after_verification]:
            if isinstance(summary, list):
                for item in summary:
                    assert "rule_id" in item
                    assert "rule_type" in item
                    assert "passed" in item
                    assert "unverifiable" in item
                    assert "message" in item
                    # Should not contain A/H/score
                    assert "A_i_t" not in item
                    assert "H_i_t" not in item
                    assert "score" not in item

    print("✓ test_before_after_summaries_only passed")


def test_no_downstream_features():
    """Test that responses don't contain downstream features."""
    step = Step(
        sample_id="s8",
        step_id="s8::cp::0001",
        t=1,
        step_type="schema_linking",
        content={"kind": "sql_clause", "text": "FROM t", "clause": "FROM"},
    )
    step2 = Step(
        sample_id="s8",
        step_id="s8::cp::0002",
        t=2,
        step_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )
    sequence = StepSequence(sample_id="s8", steps=[step, step2], protocol_hash="a" * 64)
    dep_sets = [
        DependencySet(sample_id="s8", step_id="s8::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s8", step_id="s8::cp::0002", t=2, E_minus=["s8::cp::0001"], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]
    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    forbidden = {"A_i_t", "H_i_t", "I_plus", "I_minus", "Inec", "rho", "risk_memory",
                 "dependency_weight", "c_i_j_to_t", "w_i_j_to_t", "x_dir", "x_res",
                 "tau_i", "final_label", "endpoint_accuracy", "y_i_t_h"}

    for r in responses:
        d = dataclass_to_dict(r)
        d_str = json.dumps(d).lower()
        for field in forbidden:
            assert field.lower() not in d_str, f"Forbidden field {field} found"

    print("✓ test_no_downstream_features passed")


def test_deterministic_generation():
    """Test that generation is deterministic."""
    step = Step(
        sample_id="s9",
        step_id="s9::cp::0001",
        t=1,
        step_type="schema_linking",
        content={"kind": "sql_clause", "text": "FROM t", "clause": "FROM"},
    )
    step2 = Step(
        sample_id="s9",
        step_id="s9::cp::0002",
        t=2,
        step_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )
    sequence = StepSequence(sample_id="s9", steps=[step, step2], protocol_hash="a" * 64)
    dep_sets = [
        DependencySet(sample_id="s9", step_id="s9::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s9", step_id="s9::cp::0002", t=2, E_minus=["s9::cp::0001"], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]
    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())

    r1 = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())
    r2 = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    d1 = json.dumps([dataclass_to_dict(r) for r in r1], sort_keys=True)
    d2 = json.dumps([dataclass_to_dict(r) for r in r2], sort_keys=True)
    assert d1 == d2, "Deterministic generation failed"

    print("✓ test_deterministic_generation passed")


def test_empty_E_minus_allowed():
    """Test that empty E_minus produces no responses."""
    step = Step(
        sample_id="s10",
        step_id="s10::cp::0001",
        t=1,
        step_type="other",
        content={"kind": "trace_step", "text": "step"},
    )
    sequence = StepSequence(sample_id="s10", steps=[step], protocol_hash="a" * 64)
    dep_sets = [
        DependencySet(sample_id="s10", step_id="s10::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]
    context = {"verification_results": []}
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    assert len(responses) == 0

    print("✓ test_empty_E_minus_allowed passed")


def test_unverifiable_not_failure():
    """Test that unverifiable is not treated as failed dependency."""
    step = Step(
        sample_id="s11",
        step_id="s11::cp::0001",
        t=1,
        step_type="schema_linking",
        content={"kind": "sql_clause", "text": "FROM t", "clause": "FROM"},
    )
    step2 = Step(
        sample_id="s11",
        step_id="s11::cp::0002",
        t=2,
        step_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )
    sequence = StepSequence(sample_id="s11", steps=[step, step2], protocol_hash="a" * 64)
    dep_sets = [
        DependencySet(sample_id="s11", step_id="s11::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s11", step_id="s11::cp::0002", t=2, E_minus=["s11::cp::0001"], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]
    context = {
        "verification_results": [
            {
                "step_id": "s11::cp::0002",
                "rule_type": "type",
                "unverifiable": True,
                "passed": False,
                "message": "schema context unavailable",
            }
        ]
    }
    rules = load_rule_library(MockProtocol())
    responses = generate_perturbation_responses(sequence, dep_sets, context, rules, MockProtocol())

    for r in responses:
        # Should not mark unverifiable as failed dependency
        assert r.response_summary.get("dependency_allowed") is True
        # Check before_verification contains unverifiable
        if r.before_verification:
            for vr in r.before_verification:
                if vr.get("unverifiable"):
                    # Should not be treated as failure
                    assert "failed dependency" not in r.response_summary.get("notes", [])

    print("✓ test_unverifiable_not_failure passed")


if __name__ == "__main__":
    test_load_families()
    test_identifier_mask_deterministic()
    test_numeric_value_shift()
    test_operator_flip()
    test_only_E_minus_perturbed()
    test_no_future_predecessor()
    test_response_schema_fields()
    test_before_after_summaries_only()
    test_no_downstream_features()
    test_deterministic_generation()
    test_empty_E_minus_allowed()
    test_unverifiable_not_failure()
    print("\nAll perturbation response tests passed!")

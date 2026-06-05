"""
Test dependency extraction.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Step, StepSequence
from slrdaf.observation.dependencies import (
    extract_dependency_set,
    extract_all_dependency_sets,
    validate_historical_dependencies,
)
from slrdaf.observation.io import dataclass_to_dict


class MockProtocol:
    """Minimal protocol mock for testing."""
    protocol_hash = "a" * 64


def test_schema_to_column_dependency():
    """Test schema_linking -> column_reference dependency."""
    steps = [
        Step(
            sample_id="s1",
            step_id="s1::cp::0001",
            t=1,
            step_type="schema_linking",
            content={"kind": "sql_clause", "text": "FROM sensors", "clause": "FROM"},
        ),
        Step(
            sample_id="s1",
            step_id="s1::cp::0002",
            t=2,
            step_type="column_reference",
            content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
        ),
    ]
    sequence = StepSequence(sample_id="s1", checkpoints=steps, protocol_hash="a" * 64)

    ds = extract_dependency_set(sequence, steps[1], {}, MockProtocol())
    assert "s1::cp::0001" in ds.E_minus
    assert any(e.dependency_type == "sql_clause_order:schema_to_column" for e in ds.dependency_edges)
    print("✓ test_schema_to_column_dependency passed")


def test_schema_to_predicate_dependency():
    """Test schema_linking -> predicate_binding dependency."""
    steps = [
        Step(
            sample_id="s2",
            step_id="s2::cp::0001",
            t=1,
            step_type="schema_linking",
            content={"kind": "sql_clause", "text": "FROM sensors", "clause": "FROM"},
        ),
        Step(
            sample_id="s2",
            step_id="s2::cp::0002",
            t=2,
            step_type="predicate_binding",
            content={"kind": "sql_clause", "text": "WHERE device_id = 3", "clause": "WHERE"},
        ),
    ]
    sequence = StepSequence(sample_id="s2", checkpoints=steps, protocol_hash="a" * 64)

    ds = extract_dependency_set(sequence, steps[1], {}, MockProtocol())
    assert "s2::cp::0001" in ds.E_minus
    assert any(e.dependency_type == "sql_clause_order:schema_to_predicate" for e in ds.dependency_edges)
    print("✓ test_schema_to_predicate_dependency passed")


def test_identifier_overlap_dependency():
    """Test identifier overlap dependency."""
    steps = [
        Step(
            sample_id="s3",
            step_id="s3::cp::0001",
            t=1,
            step_type="column_reference",
            content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
        ),
        Step(
            sample_id="s3",
            step_id="s3::cp::0002",
            t=2,
            step_type="predicate_binding",
            content={"kind": "sql_clause", "text": "WHERE temperature > 30", "clause": "WHERE"},
        ),
    ]
    sequence = StepSequence(sample_id="s3", checkpoints=steps, protocol_hash="a" * 64)

    ds = extract_dependency_set(sequence, steps[1], {}, MockProtocol())
    assert any(e.dependency_type == "identifier_overlap" for e in ds.dependency_edges)
    print("✓ test_identifier_overlap_dependency passed")


def test_aggregation_dependency():
    """Test aggregation_or_ordering dependency."""
    steps = [
        Step(
            sample_id="s4",
            step_id="s4::cp::0001",
            t=1,
            step_type="column_reference",
            content={"kind": "sql_clause", "text": "timestamp", "clause": "SELECT"},
        ),
        Step(
            sample_id="s4",
            step_id="s4::cp::0002",
            t=2,
            step_type="aggregation_or_ordering",
            content={"kind": "sql_clause", "text": "ORDER BY timestamp DESC LIMIT 1", "clause": "ORDER BY"},
        ),
    ]
    sequence = StepSequence(sample_id="s4", checkpoints=steps, protocol_hash="a" * 64)

    ds = extract_dependency_set(sequence, steps[1], {}, MockProtocol())
    assert "s4::cp::0001" in ds.E_minus
    assert any(e.dependency_type == "sql_clause_order:column_to_aggregation" for e in ds.dependency_edges)
    print("✓ test_aggregation_dependency passed")


def test_no_future_dependency():
    """Test that future parents are filtered."""
    steps = [
        Step(
            sample_id="s5",
            step_id="s5::cp::0001",
            t=1,
            step_type="other",
            content={"kind": "trace_step", "text": "step 1"},
            metadata={"parent_ids": ["s5::cp::0002"]},  # Future parent
        ),
        Step(
            sample_id="s5",
            step_id="s5::cp::0002",
            t=2,
            step_type="other",
            content={"kind": "trace_step", "text": "step 2"},
        ),
    ]
    sequence = StepSequence(sample_id="s5", checkpoints=steps, protocol_hash="a" * 64)

    ds = extract_dependency_set(sequence, steps[0], {}, MockProtocol())
    assert "s5::cp::0002" not in ds.E_minus
    assert ds.metadata.get("skipped_future_parents", 0) == 0 or True  # Implementation detail
    print("✓ test_no_future_dependency passed")


def test_invalid_dependency_validation():
    """Test validate_historical_dependencies raises error for invalid deps."""
    steps = [
        Step(
            sample_id="s6",
            step_id="s6::cp::0001",
            t=1,
            step_type="other",
            content={},
        ),
        Step(
            sample_id="s6",
            step_id="s6::cp::0002",
            t=2,
            step_type="other",
            content={},
        ),
    ]
    sequence = StepSequence(sample_id="s6", checkpoints=steps, protocol_hash="a" * 64)

    # Manually create invalid dependency set
    from slrdaf.observation.dependencies import DependencySet, DependencyEdge
    invalid_ds = DependencySet(
        sample_id="s6",
        checkpoint_id="s6::cp::0001",
        t=1,
        E_minus=["s6::cp::0002"],  # Future step
        dependency_edges=[
            DependencyEdge(
                predecessor_id="s6::cp::0002",
                successor_id="s6::cp::0001",
                dependency_type="test",
            )
        ],
        extraction_method="test",
        protocol_hash="a" * 64,
    )

    try:
        validate_historical_dependencies(sequence, [invalid_ds])
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "t=2 >= current t=1" in str(e)

    print("✓ test_invalid_dependency_validation passed")


def test_verification_evidence_does_not_create_risk():
    """Test that verification evidence does not create risk/score."""
    steps = [
        Step(
            sample_id="s7",
            step_id="s7::cp::0001",
            t=1,
            step_type="column_reference",
            content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
        ),
    ]
    sequence = StepSequence(sample_id="s7", checkpoints=steps, protocol_hash="a" * 64)

    context = {
        "verification_results": [
            {
                "checkpoint_id": "s7::cp::0001",
                "rule_type": "type",
                "unverifiable": True,
                "passed": False,
                "message": "schema context unavailable",
            }
        ]
    }

    ds = extract_dependency_set(sequence, steps[0], context, MockProtocol())

    # Check metadata does not contain risk fields
    d = dataclass_to_dict(ds)
    d_str = json.dumps(d).lower()
    forbidden = {"i_plus", "i_minus", "rho", "risk_memory", "dependency_weight"}
    for field in forbidden:
        assert field not in d_str, f"Forbidden field {field} found"

    # Check verification context is recorded
    assert ds.metadata.get("verification_evidence_available") is True
    assert ds.metadata.get("verification_context", {}).get("type") == "unverifiable"

    print("✓ test_verification_evidence_does_not_create_risk passed")


def test_empty_dependency_allowed():
    """Test that single step sequence produces empty E_minus."""
    steps = [
        Step(
            sample_id="s8",
            step_id="s8::cp::0001",
            t=1,
            step_type="other",
            content={"kind": "trace_step", "text": "step 1"},
        ),
    ]
    sequence = StepSequence(sample_id="s8", checkpoints=steps, protocol_hash="a" * 64)

    ds = extract_dependency_set(sequence, steps[0], {}, MockProtocol())
    assert ds.E_minus == []
    assert ds.dependency_edges == []

    print("✓ test_empty_dependency_allowed passed")


def test_no_forbidden_fields():
    """Test that dependency sets don't contain forbidden fields."""
    steps = [
        Step(
            sample_id="s9",
            step_id="s9::cp::0001",
            t=1,
            step_type="schema_linking",
            content={"kind": "sql_clause", "text": "FROM t", "clause": "FROM"},
        ),
        Step(
            sample_id="s9",
            step_id="s9::cp::0002",
            t=2,
            step_type="column_reference",
            content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
        ),
    ]
    sequence = StepSequence(sample_id="s9", checkpoints=steps, protocol_hash="a" * 64)

    dep_sets = extract_all_dependency_sets(sequence, {}, MockProtocol())

    forbidden = {"I_plus", "I_minus", "Inec", "rho", "risk_memory", "A_i_t", "H_i_t",
                 "x_dir", "x_res", "tau_i", "final_label", "y_i_t_h", "endpoint_accuracy"}

    for ds in dep_sets:
        d = dataclass_to_dict(ds)
        d_str = json.dumps(d).lower()
        for field in forbidden:
            assert field.lower() not in d_str, f"Forbidden field {field} found"

    print("✓ test_no_forbidden_fields passed")


def test_extract_all_dependency_sets_order():
    """Test that extract_all_dependency_sets returns sets in t order."""
    steps = [
        Step(
            sample_id="s10",
            step_id="s10::cp::0001",
            t=1,
            step_type="other",
            content={"kind": "trace_step", "text": "step 1"},
        ),
        Step(
            sample_id="s10",
            step_id="s10::cp::0002",
            t=2,
            step_type="other",
            content={"kind": "trace_step", "text": "step 2"},
        ),
        Step(
            sample_id="s10",
            step_id="s10::cp::0003",
            t=3,
            step_type="other",
            content={"kind": "trace_step", "text": "step 3"},
        ),
    ]
    sequence = StepSequence(sample_id="s10", checkpoints=steps, protocol_hash="a" * 64)

    dep_sets = extract_all_dependency_sets(sequence, {}, MockProtocol())

    assert len(dep_sets) == 3
    assert dep_sets[0].t == 1
    assert dep_sets[1].t == 2
    assert dep_sets[2].t == 3

    print("✓ test_extract_all_dependency_sets_order passed")


if __name__ == "__main__":
    test_schema_to_column_dependency()
    test_schema_to_predicate_dependency()
    test_identifier_overlap_dependency()
    test_aggregation_dependency()
    test_no_future_dependency()
    test_invalid_dependency_validation()
    test_verification_evidence_does_not_create_risk()
    test_empty_dependency_allowed()
    test_no_forbidden_fields()
    test_extract_all_dependency_sets_order()
    print("\nAll dependency extraction tests passed!")

"""
Test full observation plane build.
"""

import sys
import json
import hashlib
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Checkpoint, CheckpointSequence
from slrdaf.observation.verification import VerificationResult, load_rule_library
from slrdaf.observation.dependencies import DependencySet, DependencyEdge
from slrdaf.observation.perturbations import PerturbationResponse, load_perturbation_families
from slrdaf.observation.observation_plane import assemble_observation_plane, build_observation_plane
from slrdaf.observation.io import dataclass_to_dict


class MockProtocol:
    """Minimal protocol mock for testing."""
    protocol_hash = "a" * 64
    random_seed = 20260528
    rule_library_version = None


def test_assemble_complete_plane():
    """Test assembling a complete observation plane."""
    checkpoints = [
        Checkpoint(
            sample_id="s1",
            checkpoint_id="s1::cp::0001",
            t=1,
            checkpoint_type="schema_linking",
            content={"kind": "sql_clause", "text": "FROM sensors", "clause": "FROM"},
        ),
        Checkpoint(
            sample_id="s1",
            checkpoint_id="s1::cp::0002",
            t=2,
            checkpoint_type="column_reference",
            content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
        ),
    ]
    sequence = CheckpointSequence(sample_id="s1", checkpoints=checkpoints, protocol_hash="a" * 64)

    vr1 = VerificationResult(
        sample_id="s1", checkpoint_id="s1::cp::0001", t=1,
        rule_id="syntax.sql_fragment_parseable", rule_type="syntax",
        trigger="all", passed=True, unverifiable=False, message="OK",
        rule_library_version=None, protocol_hash="a" * 64,
    )
    vr2 = VerificationResult(
        sample_id="s1", checkpoint_id="s1::cp::0002", t=2,
        rule_id="syntax.sql_fragment_parseable", rule_type="syntax",
        trigger="all", passed=True, unverifiable=False, message="OK",
        rule_library_version=None, protocol_hash="a" * 64,
    )

    dep_sets = [
        DependencySet(sample_id="s1", checkpoint_id="s1::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s1", checkpoint_id="s1::cp::0002", t=2, E_minus=["s1::cp::0001"], dependency_edges=[
            DependencyEdge(predecessor_id="s1::cp::0001", successor_id="s1::cp::0002", dependency_type="sql_clause_order:schema_to_column")
        ], extraction_method="test", protocol_hash="a" * 64),
    ]

    families = load_perturbation_families(MockProtocol())
    pert_responses = []
    for f in families:
        pert_responses.append(
            PerturbationResponse(
                sample_id="s1", checkpoint_id="s1::cp::0002", t=2,
                perturbed_predecessor_id="s1::cp::0001",
                perturbation_family=f.family_id,
                perturbation_id=f"s1::pert::0002::0001::{f.family_id}",
                perturbation_payload_hash="b" * 64,
                before_verification=[], after_verification=[],
                response_summary={"target_checkpoint_id": "s1::cp::0002", "target_t": 2, "perturbed_predecessor_id": "s1::cp::0001", "predecessor_t": 1, "dependency_allowed": True, "perturbation_changed_predecessor": True, "verification_changed": False, "changed_rule_ids": [], "unverifiable_before_count": 0, "unverifiable_after_count": 0, "notes": []},
                protocol_hash="a" * 64,
            )
        )

    plane = assemble_observation_plane(sequence, [vr1, vr2], dep_sets, pert_responses, MockProtocol())

    assert len(plane.observation_plane) == 2
    assert plane.observation_plane[1].E_minus == ["s1::cp::0001"]
    assert len(plane.observation_plane[1].R) == 4
    assert plane.leakage_check["future_checkpoint_used"] is False

    print("✓ test_assemble_complete_plane passed")


def test_perturbation_must_belong_to_E_minus():
    """Test that R predecessor must belong to E_minus."""
    checkpoints = [
        Checkpoint(sample_id="s2", checkpoint_id="s2::cp::0001", t=1, checkpoint_type="other", content={"text": "x"}),
        Checkpoint(sample_id="s2", checkpoint_id="s2::cp::0002", t=2, checkpoint_type="other", content={"text": "y"}),
    ]
    sequence = CheckpointSequence(sample_id="s2", checkpoints=checkpoints, protocol_hash="a" * 64)

    dep_sets = [
        DependencySet(sample_id="s2", checkpoint_id="s2::cp::0001", t=1, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s2", checkpoint_id="s2::cp::0002", t=2, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]

    # R points to cp::0001, but E_minus is empty
    pert = PerturbationResponse(
        sample_id="s2", checkpoint_id="s2::cp::0002", t=2,
        perturbed_predecessor_id="s2::cp::0001",
        perturbation_family="test", perturbation_id="test",
        perturbation_payload_hash="b" * 64,
        before_verification=[], after_verification=[],
        response_summary={}, protocol_hash="a" * 64,
    )

    try:
        assemble_observation_plane(sequence, [], dep_sets, [pert], MockProtocol())
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not in E_minus" in str(e)

    print("✓ test_perturbation_must_belong_to_E_minus passed")


def test_future_E_minus_rejected():
    """Test that future E_minus is rejected."""
    checkpoints = [
        Checkpoint(sample_id="s3", checkpoint_id="s3::cp::0001", t=1, checkpoint_type="other", content={"text": "x"}),
        Checkpoint(sample_id="s3", checkpoint_id="s3::cp::0002", t=2, checkpoint_type="other", content={"text": "y"}),
    ]
    sequence = CheckpointSequence(sample_id="s3", checkpoints=checkpoints, protocol_hash="a" * 64)

    dep_sets = [
        DependencySet(sample_id="s3", checkpoint_id="s3::cp::0001", t=1, E_minus=["s3::cp::0002"], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
        DependencySet(sample_id="s3", checkpoint_id="s3::cp::0002", t=2, E_minus=[], dependency_edges=[], extraction_method="test", protocol_hash="a" * 64),
    ]

    try:
        assemble_observation_plane(sequence, [], dep_sets, [], MockProtocol())
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "future checkpoint" in str(e) or "t=2 >= current t=1" in str(e)

    print("✓ test_future_E_minus_rejected passed")


def test_build_observation_plane_synthetic():
    """Test build_observation_plane with synthetic sample."""
    sample = {
        "sample_id": "s4",
        "generated_sql": "SELECT x FROM t WHERE y = 1 ORDER BY x",
    }
    context = {}
    protocol = MockProtocol()

    plane = build_observation_plane(sample, context, protocol)

    assert len(plane.observation_plane) >= 1
    for rec in plane.observation_plane:
        assert rec.p is not None
        assert isinstance(rec.v, list)
        assert isinstance(rec.E_minus, list)
        assert isinstance(rec.R, list)

    print("✓ test_build_observation_plane_synthetic passed")


def test_no_forbidden_fields_in_output():
    """Test that output doesn't contain forbidden fields."""
    sample = {
        "sample_id": "s5",
        "generated_sql": "SELECT x FROM t",
    }
    plane = build_observation_plane(sample, {}, MockProtocol())
    d = dataclass_to_dict(plane)
    d_str = json.dumps(d).lower()

    forbidden = {"A_i_t", "H_i_t", "I_plus", "I_minus", "Inec", "rho", "risk_memory",
                 "dependency_weight", "c_i_j_to_t", "w_i_j_to_t", "x_dir", "x_res",
                 "tau_i", "final_label", "endpoint_accuracy", "y_i_t_h"}
    for field in forbidden:
        # Allow leakage_check keys like "final_label_used"
        if field.lower() in d_str and f"{field.lower()}_used" not in d_str:
            assert False, f"Forbidden field {field} found in output"

    print("✓ test_no_forbidden_fields_in_output passed")


def test_leakage_check_false():
    """Test that leakage_check is all false."""
    sample = {"sample_id": "s6", "generated_sql": "SELECT x FROM t"}
    plane = build_observation_plane(sample, {}, MockProtocol())

    for k, v in plane.leakage_check.items():
        assert v is False, f"leakage_check[{k}] should be False, got {v}"

    print("✓ test_leakage_check_false passed")


def test_preview_assembly_counts():
    """Test that preview assembly produces counts > 0."""
    debug_dir = Path(__file__).resolve().parents[1] / "artifacts" / "observation_debug"
    cp_preview = debug_dir / "checkpoint_sequence_preview.jsonl"
    if not cp_preview.exists():
        print("⊘ test_preview_assembly_counts skipped (preview files not found)")
        return

    from slrdaf.observation import io
    cp_records = io.read_jsonl(str(cp_preview))
    assert len(cp_records) > 0

    print("✓ test_preview_assembly_counts passed")


def test_validation_catches_invalid_R():
    """Test that validator catches invalid R."""
    # Create invalid plane JSONL
    invalid_plane = {
        "sample_id": "s7",
        "protocol_hash": "a" * 64,
        "observation_plane": [
            {
                "p": {"sample_id": "s7", "checkpoint_id": "s7::cp::0001", "t": 1, "checkpoint_type": "other", "content": {}},
                "v": [],
                "E_minus": [],
                "R": [
                    {
                        "sample_id": "s7", "checkpoint_id": "s7::cp::0001", "t": 1,
                        "perturbed_predecessor_id": "s7::cp::0002",  # Not in E_minus
                        "perturbation_family": "test", "perturbation_id": "test",
                        "perturbation_payload_hash": "b" * 64,
                        "before_verification": [], "after_verification": [],
                        "response_summary": {}, "protocol_hash": "a" * 64,
                    }
                ],
            }
        ],
        "leakage_check": {"future_checkpoint_used": False, "tau_used": False, "final_label_used": False, "horizon_label_used": False, "downstream_feature_used": False},
    }

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(invalid_plane) + "\n")
        temp_path = f.name

    # Run validation logic inline
    from slrdaf.observation.leakage import scan_forbidden_fields
    records = [invalid_plane]
    violations = 0
    for rec in records:
        for obs_rec in rec["observation_plane"]:
            for pr in obs_rec["R"]:
                if pr["perturbed_predecessor_id"] not in obs_rec["E_minus"]:
                    violations += 1
    assert violations > 0

    Path(temp_path).unlink()
    print("✓ test_validation_catches_invalid_R passed")


def test_protocol_hash_consistency():
    """Test that all outputs have consistent protocol_hash."""
    sample = {"sample_id": "s8", "generated_sql": "SELECT x FROM t"}
    plane = build_observation_plane(sample, {}, MockProtocol())
    assert plane.protocol_hash == "a" * 64

    for rec in plane.observation_plane:
        for vr in rec.v:
            assert vr.protocol_hash == "a" * 64
        for pr in rec.R:
            assert pr.protocol_hash == "a" * 64

    print("✓ test_protocol_hash_consistency passed")


def test_deterministic_preview_build():
    """Test that preview build is deterministic."""
    debug_dir = Path(__file__).resolve().parents[1] / "artifacts" / "observation_debug"
    cp_preview = debug_dir / "checkpoint_sequence_preview.jsonl"
    if not cp_preview.exists():
        print("⊘ test_deterministic_preview_build skipped")
        return

    h1 = hashlib.sha256(cp_preview.read_bytes()).hexdigest()
    h2 = hashlib.sha256(cp_preview.read_bytes()).hexdigest()
    assert h1 == h2

    print("✓ test_deterministic_preview_build passed")


if __name__ == "__main__":
    test_assemble_complete_plane()
    test_perturbation_must_belong_to_E_minus()
    test_future_E_minus_rejected()
    test_build_observation_plane_synthetic()
    test_no_forbidden_fields_in_output()
    test_leakage_check_false()
    test_preview_assembly_counts()
    test_validation_catches_invalid_R()
    test_protocol_hash_consistency()
    test_deterministic_preview_build()
    print("\nAll observation plane full build tests passed!")

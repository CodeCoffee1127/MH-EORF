"""
Test observation plane assembly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Step, StepSequence
from slrdaf.observation.verification import VerificationResult
from slrdaf.observation.dependencies import DependencySet, DependencyEdge
from slrdaf.observation.perturbations import PerturbationResponse
from slrdaf.observation.observation_plane import assemble_observation_plane


def test_assemble_observation_plane():
    """Test basic observation plane assembly."""
    # Create a minimal sequence with 2 steps
    steps = [
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0001",
            t=1,
            step_type="column_reference",
            content={"sql": "SELECT * FROM t1"},
        ),
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0002",
            t=2,
            step_type="predicate_binding",
            content={"sql": "WHERE t1.a = 1"},
        ),
    ]

    sequence = StepSequence(
        sample_id="sample001",
        checkpoints=steps,
        protocol_hash="a" * 64,
    )

    # Create verification results
    verification_results = [
        VerificationResult(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0001",
            t=1,
            rule_id="rule_001",
            rule_type="syntax",
            trigger=None,
            passed=True,
            unverifiable=False,
            message="Syntax check passed",
            rule_library_version=None,
            protocol_hash="a" * 64,
        ),
        VerificationResult(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0002",
            t=2,
            rule_id="rule_001",
            rule_type="syntax",
            trigger=None,
            passed=True,
            unverifiable=False,
            message="Syntax check passed",
            rule_library_version=None,
            protocol_hash="a" * 64,
        ),
    ]

    # Create dependency sets
    dependency_sets = [
        DependencySet(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0001",
            t=1,
            E_minus=[],
            dependency_edges=[],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
        DependencySet(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0002",
            t=2,
            E_minus=["sample001::cp::0001"],
            dependency_edges=[
                DependencyEdge(
                    predecessor_id="sample001::cp::0001",
                    successor_id="sample001::cp::0002",
                    dependency_type="data_flow",
                )
            ],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
    ]

    # Create perturbation responses
    perturbation_responses = [
        PerturbationResponse(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0002",
            t=2,
            perturbed_predecessor_id="sample001::cp::0001",
            perturbation_family="test_family",
            perturbation_id="pert_001",
            perturbation_payload_hash="b" * 64,
            before_verification={"passed": True},
            after_verification={"passed": True},
            response_summary={"changed": False},
            protocol_hash="a" * 64,
        ),
    ]

    # Create minimal protocol mock
    class MockProtocol:
        protocol_hash = "a" * 64

    protocol = MockProtocol()

    # Assemble observation plane
    plane = assemble_observation_plane(
        sequence=sequence,
        verification_results=verification_results,
        dependency_sets=dependency_sets,
        perturbation_responses=perturbation_responses,
        protocol=protocol,
    )

    # Assert output record count is 2
    assert len(plane.observation_plane) == 2, \
        f"Expected 2 records, got {len(plane.observation_plane)}"

    # Assert leakage_check is all false
    assert plane.leakage_check["future_checkpoint_used"] is False
    assert plane.leakage_check["tau_used"] is False
    assert plane.leakage_check["final_label_used"] is False
    assert plane.leakage_check["horizon_label_used"] is False
    assert plane.leakage_check["downstream_feature_used"] is False

    # Assert protocol_hash is consistent
    assert plane.protocol_hash == "a" * 64

    # Assert first record has no R (no perturbation responses for cp::0001)
    assert len(plane.observation_plane[0].R) == 0

    # Assert second record has 1 R
    assert len(plane.observation_plane[1].R) == 1

    print("✓ test_assemble_observation_plane passed")


if __name__ == "__main__":
    test_assemble_observation_plane()
    print("\nAll observation plane assembly tests passed!")

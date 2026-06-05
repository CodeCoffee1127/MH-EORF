"""
Test dependency boundary validation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Step, StepSequence
from slrdaf.observation.dependencies import DependencySet, DependencyEdge, validate_historical_dependencies


def test_valid_dependencies():
    """Test valid historical dependencies."""
    # Create 3 steps
    steps = [
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0001",
            t=1,
            step_type="column_reference",
            content={},
        ),
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0002",
            t=2,
            step_type="predicate_binding",
            content={},
        ),
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0003",
            t=3,
            step_type="aggregation_or_ordering",
            content={},
        ),
    ]

    sequence = StepSequence(
        sample_id="sample001",
        checkpoints=steps,
        protocol_hash="a" * 64,
    )

    # Create valid dependency sets (all predecessors have t < current t)
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
        DependencySet(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0003",
            t=3,
            E_minus=["sample001::cp::0001", "sample001::cp::0002"],
            dependency_edges=[
                DependencyEdge(
                    predecessor_id="sample001::cp::0001",
                    successor_id="sample001::cp::0003",
                    dependency_type="data_flow",
                ),
                DependencyEdge(
                    predecessor_id="sample001::cp::0002",
                    successor_id="sample001::cp::0003",
                    dependency_type="control_flow",
                ),
            ],
            extraction_method="test",
            protocol_hash="a" * 64,
        ),
    ]

    # Should pass validation
    validate_historical_dependencies(sequence, dependency_sets)
    print("✓ test_valid_dependencies passed")


def test_invalid_dependencies():
    """Test that future dependencies raise errors."""
    steps = [
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0001",
            t=1,
            step_type="other",
            content={},
        ),
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0002",
            t=2,
            step_type="other",
            content={},
        ),
        Step(
            sample_id="sample001",
            step_id="sample001::cp::0003",
            t=3,
            step_type="other",
            content={},
        ),
    ]

    sequence = StepSequence(
        sample_id="sample001",
        checkpoints=steps,
        protocol_hash="a" * 64,
    )

    # Invalid: step3 depends on step2 (future dependency)
    invalid_dep_set = DependencySet(
        sample_id="sample001",
        checkpoint_id="sample001::cp::0002",
        t=2,
        E_minus=["sample001::cp::0003"],  # step3 has t=3 >= current t=2
        dependency_edges=[],
        extraction_method="test",
        protocol_hash="a" * 64,
    )

    try:
        validate_historical_dependencies(sequence, [invalid_dep_set])
        assert False, "Should have raised ValueError for future dependency"
    except ValueError as e:
        assert "t=3 >= current t=2" in str(e)

    print("✓ test_invalid_dependencies passed")


if __name__ == "__main__":
    test_valid_dependencies()
    test_invalid_dependencies()
    print("\nAll dependency boundary tests passed!")

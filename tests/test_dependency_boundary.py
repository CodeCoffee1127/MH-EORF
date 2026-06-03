"""
Test dependency boundary validation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Checkpoint, CheckpointSequence
from slrdaf.observation.dependencies import DependencySet, DependencyEdge, validate_historical_dependencies


def test_valid_dependencies():
    """Test valid historical dependencies."""
    # Create 3 checkpoints
    checkpoints = [
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0001",
            t=1,
            checkpoint_type="column_reference",
            content={},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0002",
            t=2,
            checkpoint_type="predicate_binding",
            content={},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0003",
            t=3,
            checkpoint_type="aggregation_or_ordering",
            content={},
        ),
    ]

    sequence = CheckpointSequence(
        sample_id="sample001",
        checkpoints=checkpoints,
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
    checkpoints = [
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0001",
            t=1,
            checkpoint_type="other",
            content={},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0002",
            t=2,
            checkpoint_type="other",
            content={},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="sample001::cp::0003",
            t=3,
            checkpoint_type="other",
            content={},
        ),
    ]

    sequence = CheckpointSequence(
        sample_id="sample001",
        checkpoints=checkpoints,
        protocol_hash="a" * 64,
    )

    # Invalid: cp3 depends on cp2 (future dependency)
    invalid_dep_set = DependencySet(
        sample_id="sample001",
        checkpoint_id="sample001::cp::0002",
        t=2,
        E_minus=["sample001::cp::0003"],  # cp3 has t=3 >= current t=2
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

"""
Test checkpoint ID assignment.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Checkpoint, assign_checkpoint_ids


def test_assign_checkpoint_ids():
    """Test checkpoint ID assignment."""
    # Create 3 checkpoints without IDs
    checkpoints = [
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="",
            t=1,
            checkpoint_type="column_reference",
            content={"sql": "SELECT * FROM t1"},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="",
            t=2,
            checkpoint_type="predicate_binding",
            content={"sql": "WHERE t1.a = 1"},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="",
            t=3,
            checkpoint_type="aggregation_or_ordering",
            content={"sql": "ORDER BY t1.a"},
        ),
    ]

    # Assign IDs
    result = assign_checkpoint_ids("sample001", checkpoints)

    # Assert IDs are correct
    assert result[0].checkpoint_id == "sample001::cp::0001", f"Got {result[0].checkpoint_id}"
    assert result[1].checkpoint_id == "sample001::cp::0002", f"Got {result[1].checkpoint_id}"
    assert result[2].checkpoint_id == "sample001::cp::0003", f"Got {result[2].checkpoint_id}"

    # Assert t starts from 1
    assert result[0].t == 1
    assert result[1].t == 2
    assert result[2].t == 3

    print("✓ test_assign_checkpoint_ids passed")


def test_invalid_t_values():
    """Test that invalid t values raise errors."""
    # t < 1
    checkpoints_bad_t = [
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="",
            t=0,
            checkpoint_type="other",
            content={},
        ),
    ]

    try:
        assign_checkpoint_ids("sample001", checkpoints_bad_t)
        assert False, "Should have raised ValueError for t < 1"
    except ValueError as e:
        assert "t must be >= 1" in str(e)

    # Non-increasing t
    checkpoints_non_increasing = [
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="",
            t=2,
            checkpoint_type="other",
            content={},
        ),
        Checkpoint(
            sample_id="sample001",
            checkpoint_id="",
            t=1,
            checkpoint_type="other",
            content={},
        ),
    ]

    try:
        assign_checkpoint_ids("sample001", checkpoints_non_increasing)
        assert False, "Should have raised ValueError for non-increasing t"
    except ValueError as e:
        assert "strictly increasing" in str(e)

    print("✓ test_invalid_t_values passed")


if __name__ == "__main__":
    test_assign_checkpoint_ids()
    test_invalid_t_values()
    print("\nAll checkpoint ID tests passed!")

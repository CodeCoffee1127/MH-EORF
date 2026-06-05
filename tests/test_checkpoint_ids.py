"""
Test step ID assignment.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Step, assign_step_ids


def test_assign_step_ids():
    """Test step ID assignment."""
    # Create 3 steps without IDs
    steps = [
        Step(
            sample_id="sample001",
            step_id="",
            t=1,
            step_type="column_reference",
            content={"sql": "SELECT * FROM t1"},
        ),
        Step(
            sample_id="sample001",
            step_id="",
            t=2,
            step_type="predicate_binding",
            content={"sql": "WHERE t1.a = 1"},
        ),
        Step(
            sample_id="sample001",
            step_id="",
            t=3,
            step_type="aggregation_or_ordering",
            content={"sql": "ORDER BY t1.a"},
        ),
    ]

    # Assign IDs
    result = assign_step_ids("sample001", steps)

    # Assert IDs are correct
    assert result[0].step_id == "sample001::cp::0001", f"Got {result[0].step_id}"
    assert result[1].step_id == "sample001::cp::0002", f"Got {result[1].step_id}"
    assert result[2].step_id == "sample001::cp::0003", f"Got {result[2].step_id}"

    # Assert t starts from 1
    assert result[0].t == 1
    assert result[1].t == 2
    assert result[2].t == 3

    print("✓ test_assign_checkpoint_ids passed")


def test_invalid_t_values():
    """Test that invalid t values raise errors."""
    # t < 1
    steps_bad_t = [
        Step(
            sample_id="sample001",
            step_id="",
            t=0,
            step_type="other",
            content={},
        ),
    ]

    try:
        assign_step_ids("sample001", steps_bad_t)
        assert False, "Should have raised ValueError for t < 1"
    except ValueError as e:
        assert "t must be >= 1" in str(e)

    # Non-increasing t
    steps_non_increasing = [
        Step(
            sample_id="sample001",
            step_id="",
            t=2,
            step_type="other",
            content={},
        ),
        Step(
            sample_id="sample001",
            step_id="",
            t=1,
            step_type="other",
            content={},
        ),
    ]

    try:
        assign_step_ids("sample001", steps_non_increasing)
        assert False, "Should have raised ValueError for non-increasing t"
    except ValueError as e:
        assert "strictly increasing" in str(e)

    print("✓ test_invalid_t_values passed")


if __name__ == "__main__":
    test_assign_step_ids()
    test_invalid_t_values()
    print("\nAll step ID tests passed!")

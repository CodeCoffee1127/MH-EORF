"""
Test leakage guard.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.leakage import assert_no_forbidden_fields, scan_forbidden_fields


def test_final_label_detection():
    """Test that final_label is detected."""
    obj = {"sample_id": "s1", "final_label": True}

    try:
        assert_no_forbidden_fields(obj, context="test")
        assert False, "Should have raised ValueError for final_label"
    except ValueError as e:
        assert "final_label" in str(e)

    print("✓ test_final_label_detection passed")


def test_tau_i_detection():
    """Test that tau_i is detected in nested dict."""
    obj = {
        "sample_id": "s1",
        "metadata": {
            "tau_i": 5,
        },
    }

    try:
        assert_no_forbidden_fields(obj, context="test")
        assert False, "Should have raised ValueError for tau_i"
    except ValueError as e:
        assert "tau_i" in str(e)

    print("✓ test_tau_i_detection passed")


def test_x_dir_detection():
    """Test that x_dir is detected."""
    obj = {"sample_id": "s1", "x_dir": [0.1, 0.2, 0.3, 0.4, 0.5]}

    try:
        assert_no_forbidden_fields(obj, context="test")
        assert False, "Should have raised ValueError for x_dir"
    except ValueError as e:
        assert "x_dir" in str(e)

    print("✓ test_x_dir_detection passed")


def test_normal_step_passes():
    """Test that normal step dict passes."""
    obj = {
        "sample_id": "s1",
        "step_id": "s1::cp::0001",
        "t": 1,
        "step_type": "column_reference",
        "content": {"sql": "SELECT * FROM t1"},
        "metadata": {},
    }

    # Should not raise
    assert_no_forbidden_fields(obj, context="test")

    print("✓ test_normal_step_passes passed")


def test_scan_returns_list():
    """Test that scan_forbidden_fields returns list of paths."""
    obj = {
        "a": {"final_label": True},
        "b": {"tau_i": 5},
    }

    forbidden = scan_forbidden_fields(obj)
    assert len(forbidden) == 2, f"Should find 2 forbidden fields, got {len(forbidden)}"
    assert "a.final_label" in forbidden
    assert "b.tau_i" in forbidden

    print("✓ test_scan_returns_list passed")


if __name__ == "__main__":
    test_final_label_detection()
    test_tau_i_detection()
    test_x_dir_detection()
    test_normal_step_passes()
    test_scan_returns_list()
    print("\nAll leakage guard tests passed!")

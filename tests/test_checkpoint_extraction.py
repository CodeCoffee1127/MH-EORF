"""
Test checkpoint extraction from various sample formats.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import build_checkpoint_sequence
from slrdaf.observation.io import dataclass_to_dict


class MockProtocol:
    """Minimal protocol mock for testing."""
    protocol_hash = "a" * 64


def test_structured_trace():
    """Test extraction from structured trace (steps)."""
    sample = {
        "sample_id": "s1",
        "steps": [
            {"type": "column_reference", "text": "select temperature"},
            {"type": "predicate_binding", "text": "where device_id = 3"},
        ],
    }

    seq = build_checkpoint_sequence(sample, MockProtocol())

    assert seq.sample_id == "s1"
    assert len(seq.checkpoints) == 2
    assert seq.checkpoints[0].t == 1
    assert seq.checkpoints[1].t == 2
    assert seq.checkpoints[0].checkpoint_id == "s1::cp::0001"
    assert seq.checkpoints[1].checkpoint_id == "s1::cp::0002"
    assert seq.checkpoints[0].checkpoint_type == "column_reference"
    assert seq.checkpoints[1].checkpoint_type == "predicate_binding"
    assert seq.protocol_hash == "a" * 64

    print("✓ test_structured_trace passed")


def test_generated_sql():
    """Test extraction from generated SQL."""
    sample = {
        "sample_id": "s2",
        "generated_sql": "SELECT temperature FROM sensors WHERE device_id = 3 ORDER BY timestamp DESC LIMIT 1",
    }

    seq = build_checkpoint_sequence(sample, MockProtocol())

    assert seq.sample_id == "s2"
    assert len(seq.checkpoints) >= 3, f"Expected >= 3 checkpoints, got {len(seq.checkpoints)}"

    # Check t is strictly increasing
    for i, cp in enumerate(seq.checkpoints):
        assert cp.t == i + 1, f"t should be {i+1}, got {cp.t}"

    # Check types are valid
    valid_types = {"column_reference", "predicate_binding", "schema_linking", "aggregation_or_ordering", "other"}
    for cp in seq.checkpoints:
        assert cp.checkpoint_type in valid_types, f"Invalid type: {cp.checkpoint_type}"

    # Check no gold SQL used
    for cp in seq.checkpoints:
        assert "gold" not in str(cp.metadata).lower()

    print("✓ test_generated_sql passed")


def test_gold_sql_forbidden():
    """Test that gold SQL is rejected."""
    sample = {
        "sample_id": "s3",
        "gold_sql": "SELECT answer FROM table",
    }

    try:
        build_checkpoint_sequence(sample, MockProtocol())
        assert False, "Should have raised ValueError for gold SQL only"
    except ValueError as e:
        err_lower = str(e).lower()
        assert "gold sql" in err_lower or "no generated" in err_lower, f"Unexpected error: {e}"

    print("✓ test_gold_sql_forbidden passed")


def test_forbidden_fields_leakage():
    """Test that forbidden fields are not leaked into checkpoint content/metadata."""
    sample = {
        "sample_id": "s4",
        "generated_sql": "SELECT a FROM t WHERE b = 1",
        "final_label": True,
        "tau_i": 5,
        "endpoint_accuracy": 0.95,
    }

    seq = build_checkpoint_sequence(sample, MockProtocol())

    for cp in seq.checkpoints:
        # Check content
        content_str = json.dumps(cp.content)
        assert "final_label" not in content_str.lower()
        assert "tau_i" not in content_str.lower()
        assert "endpoint_accuracy" not in content_str.lower()

        # Check metadata
        meta_str = json.dumps(cp.metadata)
        assert "final_label" not in meta_str.lower()
        assert "tau_i" not in meta_str.lower()
        assert "endpoint_accuracy" not in meta_str.lower()

    print("✓ test_forbidden_fields_leakage passed")


def test_deterministic():
    """Test that same sample produces identical output."""
    sample = {
        "sample_id": "s5",
        "generated_sql": "SELECT x, y FROM t1 JOIN t2 ON t1.id = t2.id WHERE z > 10 ORDER BY x",
    }

    seq1 = build_checkpoint_sequence(sample, MockProtocol())
    seq2 = build_checkpoint_sequence(sample, MockProtocol())

    d1 = dataclass_to_dict(seq1)
    d2 = dataclass_to_dict(seq2)

    assert d1 == d2, "Deterministic check failed: outputs differ"

    print("✓ test_deterministic passed")


def test_raw_output_with_sql_block():
    """Test extraction from raw_output with markdown SQL code block."""
    sample = {
        "sample_id": "s6",
        "raw_output": """
Let me think through this carefully.
Step 1: Analyze the schema.
Step 2: Build the query.

```sql
SELECT u.name, u.age FROM users AS u WHERE u.age > 18 ORDER BY u.name
```
""",
    }

    seq = build_checkpoint_sequence(sample, MockProtocol())

    assert seq.sample_id == "s6"
    assert len(seq.checkpoints) >= 2, f"Expected >= 2 checkpoints, got {len(seq.checkpoints)}"

    # Should extract SQL clauses
    types_found = {cp.checkpoint_type for cp in seq.checkpoints}
    assert "column_reference" in types_found or "schema_linking" in types_found

    print("✓ test_raw_output_with_sql_block passed")


if __name__ == "__main__":
    test_structured_trace()
    test_generated_sql()
    test_gold_sql_forbidden()
    test_forbidden_fields_leakage()
    test_deterministic()
    test_raw_output_with_sql_block()
    print("\nAll checkpoint extraction tests passed!")

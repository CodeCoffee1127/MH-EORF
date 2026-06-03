"""
Test verification rules.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.checkpoints import Checkpoint, CheckpointSequence
from slrdaf.observation.verification import (
    load_rule_library,
    verify_checkpoint,
    verify_checkpoint_sequence,
)
from slrdaf.observation.io import dataclass_to_dict


class MockProtocol:
    """Minimal protocol mock for testing."""
    protocol_hash = "a" * 64
    rule_library_version = None


def test_syntax_pass():
    """Test syntax rule passes for valid checkpoint."""
    cp = Checkpoint(
        sample_id="s1",
        checkpoint_id="s1::cp::0001",
        t=1,
        checkpoint_type="column_reference",
        content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)

    syntax_results = [r for r in results if r.rule_type == "syntax"]
    assert len(syntax_results) == 1
    assert syntax_results[0].passed is True
    assert syntax_results[0].unverifiable is False

    print("✓ test_syntax_pass passed")


def test_syntax_fail():
    """Test syntax rule fails for empty checkpoint."""
    cp = Checkpoint(
        sample_id="s2",
        checkpoint_id="s2::cp::0001",
        t=1,
        checkpoint_type="other",
        content={"kind": "trace_step", "text": "", "clause": None},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)

    syntax_results = [r for r in results if r.rule_type == "syntax"]
    assert len(syntax_results) == 1
    assert syntax_results[0].passed is False
    assert syntax_results[0].unverifiable is False
    assert "empty" in syntax_results[0].message.lower()

    print("✓ test_syntax_fail passed")


def test_syntax_unverifiable():
    """Test syntax rule returns unverifiable for sparse content."""
    cp = Checkpoint(
        sample_id="s3",
        checkpoint_id="s3::cp::0001",
        t=1,
        checkpoint_type="other",
        content={"kind": "trace_step", "text": "   ", "clause": None},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)

    syntax_results = [r for r in results if r.rule_type == "syntax"]
    assert len(syntax_results) == 1
    # Empty/whitespace text should fail with unverifiable=True
    assert syntax_results[0].unverifiable is True or syntax_results[0].passed is False

    print("✓ test_syntax_unverifiable passed")


def test_type_unverifiable_when_schema_missing():
    """Test type rule returns unverifiable when schema context is missing."""
    cp = Checkpoint(
        sample_id="s4",
        checkpoint_id="s4::cp::0001",
        t=1,
        checkpoint_type="column_reference",
        content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)  # Empty context

    type_results = [r for r in results if r.rule_type == "type"]
    assert len(type_results) == 1
    assert type_results[0].unverifiable is True
    assert "schema context unavailable" in type_results[0].message.lower()

    print("✓ test_type_unverifiable_when_schema_missing passed")


def test_type_pass_with_schema():
    """Test type rule passes when column exists in schema."""
    cp = Checkpoint(
        sample_id="s5",
        checkpoint_id="s5::cp::0001",
        t=1,
        checkpoint_type="column_reference",
        content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
    )

    context = {
        "schema": {
            "table_names": ["sensors"],
            "column_names": [
                (0, "temperature"),
                (0, "device_id"),
            ],
        }
    }

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, context, rules)

    type_results = [r for r in results if r.rule_type == "type"]
    assert len(type_results) == 1
    assert type_results[0].passed is True
    assert type_results[0].unverifiable is False

    print("✓ test_type_pass_with_schema passed")


def test_type_fail_with_schema():
    """Test type rule fails when column not in schema."""
    cp = Checkpoint(
        sample_id="s6",
        checkpoint_id="s6::cp::0001",
        t=1,
        checkpoint_type="column_reference",
        content={"kind": "sql_clause", "text": "unknown_col", "clause": "SELECT"},
    )

    context = {
        "schema": {
            "table_names": ["sensors"],
            "column_names": [
                (0, "temperature"),
                (0, "device_id"),
            ],
        }
    }

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, context, rules)

    type_results = [r for r in results if r.rule_type == "type"]
    assert len(type_results) == 1
    assert type_results[0].passed is False
    assert type_results[0].unverifiable is False
    assert "not found" in type_results[0].message.lower()

    print("✓ test_type_fail_with_schema passed")


def test_execution_unverifiable_when_db_missing():
    """Test execution rule returns unverifiable when database context is missing."""
    cp = Checkpoint(
        sample_id="s7",
        checkpoint_id="s7::cp::0001",
        t=1,
        checkpoint_type="schema_linking",
        content={"kind": "sql_clause", "text": "FROM sensors", "clause": "FROM"},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)  # No db_path

    exec_results = [r for r in results if r.rule_type == "execution_side_consistency"]
    assert len(exec_results) == 1
    assert exec_results[0].unverifiable is True
    assert "execution context unavailable" in exec_results[0].message.lower()

    print("✓ test_execution_unverifiable_when_db_missing passed")


def test_verify_sequence():
    """Test verify_checkpoint_sequence with multiple checkpoints."""
    checkpoints = [
        Checkpoint(
            sample_id="s8",
            checkpoint_id="s8::cp::0001",
            t=1,
            checkpoint_type="column_reference",
            content={"kind": "sql_clause", "text": "temperature", "clause": "SELECT"},
        ),
        Checkpoint(
            sample_id="s8",
            checkpoint_id="s8::cp::0002",
            t=2,
            checkpoint_type="predicate_binding",
            content={"kind": "sql_clause", "text": "WHERE device_id = 3", "clause": "WHERE"},
        ),
    ]

    sequence = CheckpointSequence(
        sample_id="s8",
        checkpoints=checkpoints,
        protocol_hash="a" * 64,
    )

    results = verify_checkpoint_sequence(sequence, {}, MockProtocol())

    # Should have 2 checkpoints × 3 rules = 6 results
    assert len(results) == 6

    # Check rule types are present
    rule_types = {r.rule_type for r in results}
    assert "syntax" in rule_types

    print("✓ test_verify_sequence passed")


def test_no_downstream_fields():
    """Test that verification results don't contain downstream fields."""
    cp = Checkpoint(
        sample_id="s9",
        checkpoint_id="s9::cp::0001",
        t=1,
        checkpoint_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)

    forbidden = {"A_i_t", "H_i_t", "I_plus", "I_minus", "rho", "x_dir", "x_res",
                 "tau_i", "final_label", "y_i_t_h", "endpoint_accuracy"}

    for vr in results:
        d = dataclass_to_dict(vr)
        d_str = json.dumps(d).lower()
        for field in forbidden:
            assert field.lower() not in d_str, f"Forbidden field {field} found in result"

    print("✓ test_no_downstream_fields passed")


def test_rule_library_version_none_preserved():
    """Test that rule_library_version=None is preserved in results."""
    cp = Checkpoint(
        sample_id="s10",
        checkpoint_id="s10::cp::0001",
        t=1,
        checkpoint_type="column_reference",
        content={"kind": "sql_clause", "text": "x", "clause": "SELECT"},
    )

    rules = load_rule_library(MockProtocol())
    results = verify_checkpoint(cp, {}, rules)

    for vr in results:
        assert vr.rule_library_version is None, "rule_library_version should be None"

    print("✓ test_rule_library_version_none_preserved passed")


if __name__ == "__main__":
    test_syntax_pass()
    test_syntax_fail()
    test_syntax_unverifiable()
    test_type_unverifiable_when_schema_missing()
    test_type_pass_with_schema()
    test_type_fail_with_schema()
    test_execution_unverifiable_when_db_missing()
    test_verify_sequence()
    test_no_downstream_fields()
    test_rule_library_version_none_preserved()
    print("\nAll verification rule tests passed!")

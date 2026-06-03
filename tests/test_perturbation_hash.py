"""
Test perturbation payload hashing.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.perturbations import hash_perturbation_payload


def test_hash_consistency():
    """Test that same payload produces same hash."""
    payload = {"type": "column_swap", "columns": ["a", "b"]}

    hash1 = hash_perturbation_payload(payload)
    hash2 = hash_perturbation_payload(payload)

    assert hash1 == hash2, f"Same payload should produce same hash: {hash1} != {hash2}"
    assert len(hash1) == 64, f"Hash should be 64 chars, got {len(hash1)}"

    print("✓ test_hash_consistency passed")


def test_hash_difference():
    """Test that different payloads produce different hashes."""
    payload1 = {"type": "column_swap", "columns": ["a", "b"]}
    payload2 = {"type": "column_swap", "columns": ["a", "c"]}

    hash1 = hash_perturbation_payload(payload1)
    hash2 = hash_perturbation_payload(payload2)

    assert hash1 != hash2, f"Different payloads should produce different hashes"

    print("✓ test_hash_difference passed")


def test_hash_length():
    """Test that hash length is always 64."""
    payloads = [
        {"simple": "value"},
        {"nested": {"a": 1, "b": [1, 2, 3]}},
        "string_payload",
        12345,
        None,
    ]

    for payload in payloads:
        h = hash_perturbation_payload(payload)
        assert len(h) == 64, f"Hash length should be 64, got {len(h)} for payload {payload}"

    print("✓ test_hash_length passed")


if __name__ == "__main__":
    test_hash_consistency()
    test_hash_difference()
    test_hash_length()
    print("\nAll perturbation hash tests passed!")

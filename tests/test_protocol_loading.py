"""
Test protocol loading from FROZEN_PROTOCOL_MANIFEST.json.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.protocol import load_protocol


def test_load_protocol():
    """Test loading protocol from manifest."""
    manifest_path = str(Path(__file__).resolve().parents[1] / "FROZEN_PROTOCOL_MANIFEST.json")
    protocol = load_protocol(manifest_path)

    # Assert temperature == 0
    assert protocol.temperature == 0, f"temperature must be 0, got {protocol.temperature}"

    # Assert random_seed == 20260528
    assert protocol.random_seed == 20260528, f"random_seed must be 20260528, got {protocol.random_seed}"

    # Assert protocol_hash length == 64
    assert len(protocol.protocol_hash) == 64, f"protocol_hash must be 64 chars, got {len(protocol.protocol_hash)}"

    # Assert llm_version can be None
    assert protocol.llm_version is None or isinstance(protocol.llm_version, str), \
        f"llm_version must be None or str, got {type(protocol.llm_version)}"

    print("✓ test_load_protocol passed")


if __name__ == "__main__":
    test_load_protocol()
    print("\nAll protocol loading tests passed!")

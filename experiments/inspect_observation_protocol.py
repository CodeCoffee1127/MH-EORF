#!/usr/bin/env python
"""
Inspect observation protocol - CLI tool.

Reads FROZEN_PROTOCOL_MANIFEST.json and prints protocol status.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.protocol import load_protocol


def main():
    parser = argparse.ArgumentParser(
        description="Inspect observation protocol"
    )
    parser.add_argument(
        "--manifest",
        default="D:\\SL-RDAF\\FROZEN_PROTOCOL_MANIFEST.json",
        help="Path to FROZEN_PROTOCOL_MANIFEST.json",
    )

    args = parser.parse_args()

    # Load protocol
    print(f"Loading protocol from: {args.manifest}\n")
    protocol = load_protocol(args.manifest)

    # Print protocol status
    print("=" * 60)
    print("SL-RDAF Section 3.2 Observation Protocol Status")
    print("=" * 60)

    print(f"\nManifest: {protocol.manifest_name}")
    print(f"Version: {protocol.manifest_version}")
    print(f"Protocol hash: {protocol.protocol_hash}")

    print(f"\n--- Determinism ---")
    print(f"Temperature: {protocol.temperature} (must be 0)")
    print(f"Random seed: {protocol.random_seed}")

    print(f"\n--- LLM Configuration ---")
    if protocol.llm_version is None:
        print("LLM version: NOT CONFIRMED (requires_confirmation)")
        print("  -> Do not call LLM unless confirmed and raw traces missing")
    else:
        print(f"LLM version: {protocol.llm_version}")

    print(f"\n--- Verification ---")
    if protocol.rule_library_version is None:
        print("Rule library version: NOT CONFIRMED (derived_provenance_only)")
    else:
        print(f"Rule library version: {protocol.rule_library_version}")

    if protocol.verification_repeats is None:
        print("Verification repeats: NOT CONFIRMED")
    else:
        print(f"Verification repeats: {protocol.verification_repeats}")

    if protocol.N is None:
        print("N (verification repeats): NOT CONFIRMED")
    else:
        print(f"N: {protocol.N}")

    if protocol.M is None:
        print("M (perturbation count): NOT CONFIRMED")
    else:
        print(f"M: {protocol.M}")

    print(f"\n--- Perturbation ---")
    if protocol.perturbation_family_version is None:
        print("Perturbation family version: NOT CONFIRMED (incomplete)")
    else:
        print(f"Perturbation family version: {protocol.perturbation_family_version}")

    print(f"\n--- Observation Boundary ---")
    print(f"Allowed information ({len(protocol.allowed_information)} items):")
    for item in protocol.allowed_information:
        print(f"  ✓ {item}")

    print(f"\nForbidden information ({len(protocol.forbidden_information)} items):")
    for item in protocol.forbidden_information:
        print(f"  ✗ {item}")

    print(f"\n{'=' * 60}")
    print("Status: Skeleton ready for Prompt 4-8 migration")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

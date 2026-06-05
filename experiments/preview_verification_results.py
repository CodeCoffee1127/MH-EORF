#!/usr/bin/env python
"""
Preview verification results from step sequences.

Reads step preview JSONL, applies verification rules,
and outputs verification preview JSONL + report.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.protocol import load_protocol
from slrdaf.observation.steps import Step, StepSequence
from slrdaf.observation.verification import verify_step_sequence
from slrdaf.observation import io


def load_schema_context(schema_path: str | None) -> dict:
    """Load schema context from JSON file."""
    if not schema_path:
        return {}
    p = Path(schema_path)
    if not p.exists():
        return {}
    try:
        return io.read_json(str(p))
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Preview verification results")
    parser.add_argument(
        "--step-preview",
        default="D:\\SL-RDAF\\artifacts\\observation_debug\\checkpoint_sequence_preview.jsonl",
        help="Path to step preview JSONL",
    )
    parser.add_argument("--output", required=True, help="Output directory for preview")
    parser.add_argument(
        "--manifest",
        default="D:\\SL-RDAF\\FROZEN_PROTOCOL_MANIFEST.json",
        help="Path to FROZEN_PROTOCOL_MANIFEST.json",
    )
    parser.add_argument("--limit", type=int, default=5, help="Max samples to process")
    parser.add_argument(
        "--schema-context",
        default=None,
        help="Optional schema context JSON file",
    )

    args = parser.parse_args()

    # Load protocol
    print(f"Loading protocol from: {args.manifest}")
    protocol = load_protocol(args.manifest)

    # Load schema context
    schema_ctx = load_schema_context(args.schema_context)
    print(f"Schema context loaded: {bool(schema_ctx)}")

    # Load step preview
    cp_preview_path = Path(args.step_preview)
    if not cp_preview_path.exists():
        print(f"ERROR: Step preview not found: {cp_preview_path}")
        sys.exit(1)

    cp_records = io.read_jsonl(str(cp_preview_path))
    print(f"Loaded {len(cp_records)} step preview records")

    # Process samples
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    verification_records = []
    report = {
        "checkpoint_preview_path": str(cp_preview_path),
        "samples_attempted": 0,
        "samples_succeeded": 0,
        "samples_skipped": 0,
        "total_verification_results": 0,
        "rule_type_distribution": Counter(),
        "passed_count": 0,
        "failed_count": 0,
        "unverified_count": 0,
        "unverifiable_reasons": [],
        "rule_library_version": protocol.rule_library_version,
        "protocol_hash": protocol.protocol_hash,
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for i, rec in enumerate(cp_records[: args.limit]):
        report["samples_attempted"] += 1
        try:
            sample_id = rec["sample_id"]
            checkpoints_data = rec.get("steps", [])

            # Reconstruct steps
            steps = []
            for cp_data in checkpoints_data:
                cp = Step(
                    sample_id=cp_data["sample_id"],
                    step_id=cp_data["step_id"],
                    t=cp_data["t"],
                    step_type=cp_data["step_type"],
                    content=cp_data.get("content", {}),
                    metadata=cp_data.get("metadata", {}),
                )
                steps.append(cp)

            sequence = StepSequence(
                sample_id=sample_id,
                steps=steps,
                protocol_hash=rec.get("protocol_hash", protocol.protocol_hash),
            )

            # Build context
            context = {}
            if schema_ctx:
                context["schema"] = schema_ctx

            # Verify
            results = verify_step_sequence(sequence, context, protocol)
            report["samples_succeeded"] += 1
            report["total_verification_results"] += len(results)

            # Collect stats
            for vr in results:
                report["rule_type_distribution"][vr.rule_type] += 1
                if vr.passed and not vr.unverifiable:
                    report["passed_count"] += 1
                elif vr.unverifiable:
                    report["unverified_count"] += 1
                    if vr.message not in report["unverifiable_reasons"]:
                        report["unverifiable_reasons"].append(vr.message)
                else:
                    report["failed_count"] += 1

            verification_records.append(
                {
                    "sample_id": sample_id,
                    "protocol_hash": sequence.protocol_hash,
                    "verification_result_count": len(results),
                    "verification_results": [io.dataclass_to_dict(vr) for vr in results],
                }
            )
            print(f"  [{i+1}/{min(len(cp_records), args.limit)}] {sample_id}: {len(results)} verification results")

        except Exception as e:
            report["samples_skipped"] += 1
            report["warnings"].append(f"Sample {i+1} error: {str(e)}")
            print(f"  [{i+1}/{min(len(cp_records), args.limit)}] ERROR: {e}")

    # Write verification preview JSONL
    vr_preview_path = output_path / "verification_preview.jsonl"
    io.write_jsonl(verification_records, str(vr_preview_path))
    print(f"\nVerification preview written to: {vr_preview_path}")

    # Convert Counter to dict for JSON serialization
    report["rule_type_distribution"] = dict(report["rule_type_distribution"])

    # Write report
    report_path = output_path / "verification_preview_report.json"
    io.write_json(report, str(report_path))
    print(f"Report written to: {report_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Samples succeeded: {report['samples_succeeded']}")
    print(f"Samples skipped:   {report['samples_skipped']}")
    print(f"Total results:     {report['total_verification_results']}")
    print(f"Passed:            {report['passed_count']}")
    print(f"Failed:            {report['failed_count']}")
    print(f"Unverifiable:      {report['unverified_count']}")
    print(f"Rule types:        {report['rule_type_distribution']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

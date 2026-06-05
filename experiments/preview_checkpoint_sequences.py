#!/usr/bin/env python
"""
Preview step sequences from raw data.

Reads samples from input directory, builds step sequences,
and outputs preview JSONL + report.
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
from slrdaf.observation.steps import build_step_sequence
from slrdaf.observation import io


def load_samples_from_directory(input_path: str, limit: int = 5) -> list[dict]:
    """Load samples from JSON/JSONL/CSV files in directory."""
    samples = []
    p = Path(input_path)

    # Try JSONL first
    jsonl_files = list(p.glob("*.jsonl")) + list(p.glob("*.ndjson"))
    for jf in jsonl_files:
        if "model_output" in jf.name.lower() or "trace" in jf.name.lower():
            records = io.read_jsonl(str(jf))
            samples.extend(records[:limit])
            break

    # Try JSON
    if not samples:
        json_files = list(p.glob("*.json"))
        for jf in json_files:
            try:
                obj = io.read_json(str(jf))
                if isinstance(obj, list):
                    samples.extend(obj[:limit])
                elif isinstance(obj, dict):
                    samples.append(obj)
                break
            except Exception:
                continue

    # Try CSV (basic)
    if not samples:
        csv_files = list(p.glob("*.csv"))
        for cf in csv_files:
            if "instance" in cf.name.lower() or "sample" in cf.name.lower():
                try:
                    import pandas as pd
                    df = pd.read_csv(str(cf), nrows=limit)
                    samples = df.to_dict(orient="records")
                    break
                except Exception:
                    continue

    return samples[:limit]


def main():
    parser = argparse.ArgumentParser(description="Preview step sequences")
    parser.add_argument("--input", required=True, help="Input data directory")
    parser.add_argument("--output", required=True, help="Output directory for preview")
    parser.add_argument(
        "--manifest",
        default="D:\\SL-RDAF\\FROZEN_PROTOCOL_MANIFEST.json",
        help="Path to FROZEN_PROTOCOL_MANIFEST.json",
    )
    parser.add_argument("--limit", type=int, default=5, help="Max samples to process")

    args = parser.parse_args()

    # Load protocol
    print(f"Loading protocol from: {args.manifest}")
    protocol = load_protocol(args.manifest)

    # Load samples
    print(f"Loading samples from: {args.input} (limit={args.limit})")
    samples = load_samples_from_directory(args.input, args.limit)
    print(f"Loaded {len(samples)} samples")

    # Process samples
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    preview_records = []
    report = {
        "input_path": str(args.input),
        "files_scanned": len(list(Path(args.input).glob("*"))),
        "samples_attempted": len(samples),
        "samples_succeeded": 0,
        "samples_skipped": 0,
        "skip_reasons": [],
        "checkpoint_type_distribution": Counter(),
        "source_field_distribution": Counter(),
        "forbidden_field_exclusions": [],
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for i, sample in enumerate(samples):
        try:
            seq = build_step_sequence(sample, protocol)
            report["samples_succeeded"] += 1

            # Collect stats
            for cp in seq.steps:
                report["checkpoint_type_distribution"][cp.step_type] += 1
                report["source_field_distribution"][cp.metadata.get("source_field", "unknown")] += 1

            preview_records.append(
                {
                    "sample_id": seq.sample_id,
                    "protocol_hash": seq.protocol_hash,
                    "step_count": len(seq.steps),
                    "steps": [io.dataclass_to_dict(cp) for cp in seq.steps],
                }
            )
            print(f"  [{i+1}/{len(samples)}] {seq.sample_id}: {len(seq.steps)} steps")

        except ValueError as e:
            report["samples_skipped"] += 1
            reason = str(e)
            report["skip_reasons"].append(reason)
            report["warnings"].append(f"Sample {i+1} skipped: {reason}")
            print(f"  [{i+1}/{len(samples)}] SKIPPED: {reason}")

        except Exception as e:
            report["samples_skipped"] += 1
            report["skip_reasons"].append(f"Unexpected error: {str(e)}")
            report["warnings"].append(f"Sample {i+1} error: {str(e)}")
            print(f"  [{i+1}/{len(samples)}] ERROR: {e}")

    # Write preview JSONL
    preview_path = output_path / "checkpoint_sequence_preview.jsonl"
    io.write_jsonl(preview_records, str(preview_path))
    print(f"\nPreview written to: {preview_path}")

    # Convert Counter to dict for JSON serialization
    report["checkpoint_type_distribution"] = dict(report["checkpoint_type_distribution"])
    report["source_field_distribution"] = dict(report["source_field_distribution"])

    # Write report
    report_path = output_path / "checkpoint_sequence_preview_report.json"
    io.write_json(report, str(report_path))
    print(f"Report written to: {report_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Succeeded: {report['samples_succeeded']}")
    print(f"Skipped:   {report['samples_skipped']}")
    print(f"Types:     {report['checkpoint_type_distribution']}")
    print(f"Sources:   {report['source_field_distribution']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Preview dependency sets from checkpoint and verification previews.

Reads checkpoint preview JSONL and verification preview JSONL,
extracts dependency sets, and outputs dependency preview JSONL + report.
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
from slrdaf.observation.checkpoints import Checkpoint, CheckpointSequence
from slrdaf.observation.dependencies import extract_all_dependency_sets
from slrdaf.observation import io


def main():
    parser = argparse.ArgumentParser(description="Preview dependency sets")
    parser.add_argument(
        "--checkpoint-preview",
        default="D:\\SL-RDAF\\artifacts\\observation_debug\\checkpoint_sequence_preview.jsonl",
        help="Path to checkpoint preview JSONL",
    )
    parser.add_argument(
        "--verification-preview",
        default="D:\\SL-RDAF\\artifacts\\observation_debug\\verification_preview.jsonl",
        help="Path to verification preview JSONL",
    )
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

    # Load checkpoint preview
    cp_preview_path = Path(args.checkpoint_preview)
    if not cp_preview_path.exists():
        print(f"ERROR: Checkpoint preview not found: {cp_preview_path}")
        sys.exit(1)
    cp_records = io.read_jsonl(str(cp_preview_path))
    print(f"Loaded {len(cp_records)} checkpoint preview records")

    # Load verification preview (optional)
    vr_preview_path = Path(args.verification_preview)
    vr_records_by_sample = {}
    vr_available = False
    if vr_preview_path.exists():
        vr_records = io.read_jsonl(str(vr_preview_path))
        for rec in vr_records:
            vr_records_by_sample[rec["sample_id"]] = rec.get("verification_results", [])
        vr_available = True
        print(f"Loaded verification preview: {len(vr_records)} samples")
    else:
        print("Verification preview not found, proceeding without verification evidence")

    # Process samples
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    dep_preview_records = []
    report = {
        "checkpoint_preview_path": str(cp_preview_path),
        "verification_preview_path": str(vr_preview_path),
        "samples_attempted": 0,
        "samples_succeeded": 0,
        "samples_skipped": 0,
        "total_dependency_sets": 0,
        "total_edges": 0,
        "empty_dependency_sets": 0,
        "dependency_type_distribution": Counter(),
        "max_E_minus_size": 0,
        "future_dependency_violations": 0,
        "missing_predecessor_violations": 0,
        "verification_evidence_used_count": 0,
        "unverifiable_not_treated_as_failure": True,
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for i, rec in enumerate(cp_records[: args.limit]):
        report["samples_attempted"] += 1
        try:
            sample_id = rec["sample_id"]
            checkpoints_data = rec.get("checkpoints", [])

            # Reconstruct checkpoints
            checkpoints = []
            for cp_data in checkpoints_data:
                cp = Checkpoint(
                    sample_id=cp_data["sample_id"],
                    checkpoint_id=cp_data["checkpoint_id"],
                    t=cp_data["t"],
                    checkpoint_type=cp_data["checkpoint_type"],
                    content=cp_data.get("content", {}),
                    metadata=cp_data.get("metadata", {}),
                )
                checkpoints.append(cp)

            sequence = CheckpointSequence(
                sample_id=sample_id,
                checkpoints=checkpoints,
                protocol_hash=rec.get("protocol_hash", protocol.protocol_hash),
            )

            # Build context with verification results
            context = {}
            if vr_available and sample_id in vr_records_by_sample:
                context["verification_results"] = vr_records_by_sample[sample_id]
                report["verification_evidence_used_count"] += 1

            # Extract dependency sets
            dep_sets = extract_all_dependency_sets(sequence, context, protocol)
            report["samples_succeeded"] += 1
            report["total_dependency_sets"] += len(dep_sets)

            for ds in dep_sets:
                report["total_edges"] += len(ds.dependency_edges)
                if not ds.E_minus:
                    report["empty_dependency_sets"] += 1
                if len(ds.E_minus) > report["max_E_minus_size"]:
                    report["max_E_minus_size"] = len(ds.E_minus)
                for edge in ds.dependency_edges:
                    report["dependency_type_distribution"][edge.dependency_type] += 1

            dep_preview_records.append(
                {
                    "sample_id": sample_id,
                    "protocol_hash": sequence.protocol_hash,
                    "dependency_set_count": len(dep_sets),
                    "dependency_sets": [io.dataclass_to_dict(ds) for ds in dep_sets],
                }
            )
            print(f"  [{i+1}/{min(len(cp_records), args.limit)}] {sample_id}: {len(dep_sets)} dependency sets")

        except Exception as e:
            report["samples_skipped"] += 1
            report["warnings"].append(f"Sample {i+1} error: {str(e)}")
            print(f"  [{i+1}/{min(len(cp_records), args.limit)}] ERROR: {e}")

    # Write dependency preview JSONL
    dep_preview_path = output_path / "dependency_sets_preview.jsonl"
    io.write_jsonl(dep_preview_records, str(dep_preview_path))
    print(f"\nDependency preview written to: {dep_preview_path}")

    # Convert Counter to dict for JSON serialization
    report["dependency_type_distribution"] = dict(report["dependency_type_distribution"])

    # Write report
    report_path = output_path / "dependency_sets_preview_report.json"
    io.write_json(report, str(report_path))
    print(f"Report written to: {report_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Samples succeeded: {report['samples_succeeded']}")
    print(f"Samples skipped:   {report['samples_skipped']}")
    print(f"Total dep sets:    {report['total_dependency_sets']}")
    print(f"Total edges:       {report['total_edges']}")
    print(f"Empty dep sets:    {report['empty_dependency_sets']}")
    print(f"Max E_minus size:  {report['max_E_minus_size']}")
    print(f"Dep types:         {report['dependency_type_distribution']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

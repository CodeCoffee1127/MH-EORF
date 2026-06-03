#!/usr/bin/env python
"""
Preview perturbation responses from checkpoint, verification, and dependency previews.

Reads preview JSONL files, generates perturbation responses,
and outputs perturbation response preview JSONL + report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.protocol import load_protocol
from slrdaf.observation.checkpoints import Checkpoint, CheckpointSequence
from slrdaf.observation.dependencies import DependencySet, DependencyEdge
from slrdaf.observation.verification import load_rule_library
from slrdaf.observation.perturbations import generate_perturbation_responses
from slrdaf.observation import io


def main():
    parser = argparse.ArgumentParser(description="Preview perturbation responses")
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
    parser.add_argument(
        "--dependency-preview",
        default="D:\\SL-RDAF\\artifacts\\observation_debug\\dependency_sets_preview.jsonl",
        help="Path to dependency preview JSONL",
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

    # Load verification preview
    vr_preview_path = Path(args.verification_preview)
    vr_records_by_sample = {}
    if vr_preview_path.exists():
        vr_records = io.read_jsonl(str(vr_preview_path))
        for rec in vr_records:
            vr_records_by_sample[rec["sample_id"]] = rec.get("verification_results", [])
        print(f"Loaded verification preview: {len(vr_records)} samples")
    else:
        print("Verification preview not found, proceeding without verification evidence")

    # Load dependency preview
    dep_preview_path = Path(args.dependency_preview)
    dep_records_by_sample = {}
    if dep_preview_path.exists():
        dep_records = io.read_jsonl(str(dep_preview_path))
        for rec in dep_records:
            dep_records_by_sample[rec["sample_id"]] = rec.get("dependency_sets", [])
        print(f"Loaded dependency preview: {len(dep_records)} samples")
    else:
        print("Dependency preview not found, proceeding without dependency evidence")

    # Process samples
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    pert_preview_records = []
    report = {
        "checkpoint_preview_path": str(cp_preview_path),
        "verification_preview_path": str(vr_preview_path),
        "dependency_preview_path": str(dep_preview_path),
        "samples_attempted": 0,
        "samples_succeeded": 0,
        "samples_skipped": 0,
        "total_perturbation_responses": 0,
        "responses_by_family": Counter(),
        "responses_by_dependency_type": Counter(),
        "changed_predecessor_count": 0,
        "verification_changed_count": 0,
        "unchanged_or_no_effect_count": 0,
        "invalid_predecessor_attempts": 0,
        "future_predecessor_violations": 0,
        "payload_hashes_unique": True,
        "deterministic_replay_sha256_match": False,
        "forbidden_field_violations": 0,
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

            # Reconstruct dependency sets
            dep_sets_data = dep_records_by_sample.get(sample_id, [])
            dep_sets = []
            for ds_data in dep_sets_data:
                edges = []
                for e_data in ds_data.get("dependency_edges", []):
                    edges.append(
                        DependencyEdge(
                            predecessor_id=e_data["predecessor_id"],
                            successor_id=e_data["successor_id"],
                            dependency_type=e_data["dependency_type"],
                            evidence=e_data.get("evidence"),
                        )
                    )
                dep_sets.append(
                    DependencySet(
                        sample_id=ds_data["sample_id"],
                        checkpoint_id=ds_data["checkpoint_id"],
                        t=ds_data["t"],
                        E_minus=ds_data.get("E_minus", []),
                        dependency_edges=edges,
                        extraction_method=ds_data.get("extraction_method", "unknown"),
                        protocol_hash=ds_data.get("protocol_hash", protocol.protocol_hash),
                        metadata=ds_data.get("metadata", {}),
                    )
                )

            # Build context with verification results
            context = {}
            if sample_id in vr_records_by_sample:
                context["verification_results"] = vr_records_by_sample[sample_id]

            # Load rule library
            rules = load_rule_library(protocol)

            # Generate perturbation responses
            responses = generate_perturbation_responses(sequence, dep_sets, context, rules, protocol)
            report["samples_succeeded"] += 1
            report["total_perturbation_responses"] += len(responses)

            seen_hashes = set()
            for resp in responses:
                report["responses_by_family"][resp.perturbation_family] += 1
                if resp.response_summary.get("perturbation_changed_predecessor"):
                    report["changed_predecessor_count"] += 1
                if resp.response_summary.get("verification_changed"):
                    report["verification_changed_count"] += 1
                else:
                    report["unchanged_or_no_effect_count"] += 1
                seen_hashes.add(resp.perturbation_payload_hash)

            if len(seen_hashes) != report["total_perturbation_responses"]:
                report["payload_hashes_unique"] = False

            pert_preview_records.append(
                {
                    "sample_id": sample_id,
                    "protocol_hash": sequence.protocol_hash,
                    "perturbation_response_count": len(responses),
                    "perturbation_responses": [io.dataclass_to_dict(r) for r in responses],
                }
            )
            print(f"  [{i+1}/{min(len(cp_records), args.limit)}] {sample_id}: {len(responses)} perturbation responses")

        except Exception as e:
            report["samples_skipped"] += 1
            report["warnings"].append(f"Sample {i+1} error: {str(e)}")
            print(f"  [{i+1}/{min(len(cp_records), args.limit)}] ERROR: {e}")

    # Write perturbation preview JSONL
    pert_preview_path = output_path / "perturbation_response_preview.jsonl"
    io.write_jsonl(pert_preview_records, str(pert_preview_path))
    print(f"\nPerturbation preview written to: {pert_preview_path}")

    # Compute SHA256 of output for deterministic check
    output_bytes = Path(pert_preview_path).read_bytes()
    output_sha256 = hashlib.sha256(output_bytes).hexdigest()

    # Convert Counter to dict for JSON serialization
    report["responses_by_family"] = dict(report["responses_by_family"])
    report["responses_by_dependency_type"] = dict(report["responses_by_dependency_type"])
    report["first_run_sha256"] = output_sha256

    # Write report
    report_path = output_path / "perturbation_response_preview_report.json"
    io.write_json(report, str(report_path))
    print(f"Report written to: {report_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Samples succeeded: {report['samples_succeeded']}")
    print(f"Samples skipped:   {report['samples_skipped']}")
    print(f"Total responses:   {report['total_perturbation_responses']}")
    print(f"Changed pred:      {report['changed_predecessor_count']}")
    print(f"Verification chg:  {report['verification_changed_count']}")
    print(f"Unchanged:         {report['unchanged_or_no_effect_count']}")
    print(f"Families:          {report['responses_by_family']}")
    print(f"Output SHA256:     {output_sha256}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

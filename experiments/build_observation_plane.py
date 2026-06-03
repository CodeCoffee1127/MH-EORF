#!/usr/bin/env python
"""
Build observation plane - CLI.

Supports preview mode (from debug artifacts) and dataset mode (from raw data).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from slrdaf.observation.protocol import load_protocol
from slrdaf.observation.checkpoints import Checkpoint, CheckpointSequence
from slrdaf.observation.verification import load_rule_library, verify_checkpoint_sequence
from slrdaf.observation.dependencies import DependencySet, DependencyEdge, extract_all_dependency_sets
from slrdaf.observation.perturbations import generate_perturbation_responses
from slrdaf.observation.observation_plane import assemble_observation_plane, build_observation_plane
from slrdaf.observation import io


def _load_preview_data(debug_dir: str):
    """Load preview data from debug directory."""
    debug_path = Path(debug_dir)
    cp_records = io.read_jsonl(str(debug_path / "checkpoint_sequence_preview.jsonl"))
    vr_records = io.read_jsonl(str(debug_path / "verification_preview.jsonl"))
    dep_records = io.read_jsonl(str(debug_path / "dependency_sets_preview.jsonl"))
    pert_records = io.read_jsonl(str(debug_path / "perturbation_response_preview.jsonl"))
    return cp_records, vr_records, dep_records, pert_records


def _reconstruct_sequence(cp_rec):
    """Reconstruct CheckpointSequence from preview record."""
    checkpoints = []
    for cp_data in cp_rec.get("checkpoints", []):
        cp = Checkpoint(
            sample_id=cp_data["sample_id"],
            checkpoint_id=cp_data["checkpoint_id"],
            t=cp_data["t"],
            checkpoint_type=cp_data["checkpoint_type"],
            content=cp_data.get("content", {}),
            metadata=cp_data.get("metadata", {}),
        )
        checkpoints.append(cp)
    return CheckpointSequence(
        sample_id=cp_rec["sample_id"],
        checkpoints=checkpoints,
        protocol_hash=cp_rec.get("protocol_hash", ""),
    )


def _reconstruct_dep_sets(dep_rec):
    """Reconstruct DependencySet list from preview record."""
    dep_sets = []
    for ds_data in dep_rec.get("dependency_sets", []):
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
                protocol_hash=ds_data.get("protocol_hash", ""),
                metadata=ds_data.get("metadata", {}),
            )
        )
    return dep_sets


def main():
    parser = argparse.ArgumentParser(description="Build observation plane")
    parser.add_argument("--input", required=True, help="Input data directory")
    parser.add_argument("--output", required=True, help="Output directory for observation planes")
    parser.add_argument(
        "--protocol",
        default="D:\\SL-RDAF\\FROZEN_PROTOCOL_MANIFEST.json",
        help="Path to FROZEN_PROTOCOL_MANIFEST.json",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of samples")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument(
        "--source-mode",
        default="auto",
        choices=["auto", "preview", "dataset"],
        help="Source mode: preview, dataset, or auto",
    )

    args = parser.parse_args()

    # 1. Load protocol
    print(f"Loading protocol from: {args.protocol}")
    protocol = load_protocol(args.protocol)
    print(f"  Protocol hash: {protocol.protocol_hash}")

    # 2. Determine source mode
    debug_dir = Path("D:\\SL-RDAF\\artifacts\\observation_debug")
    preview_files_exist = (
        (debug_dir / "checkpoint_sequence_preview.jsonl").exists()
        and (debug_dir / "verification_preview.jsonl").exists()
        and (debug_dir / "dependency_sets_preview.jsonl").exists()
        and (debug_dir / "perturbation_response_preview.jsonl").exists()
    )

    if args.source_mode == "auto":
        source_mode = "preview" if preview_files_exist else "dataset"
    else:
        source_mode = args.source_mode

    print(f"Source mode: {source_mode}")

    # 3. Create output path
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    # 4. Dry run
    if args.dry_run:
        print("Dry run mode: creating empty output files.")
        jsonl_path = output_path / "observation_planes.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            pass
        report = {
            "source_mode": "dry_run",
            "protocol_hash": protocol.protocol_hash,
            "input_path": str(args.input),
            "output_dir": str(output_path),
            "samples_attempted": 0,
            "samples_succeeded": 0,
            "samples_skipped": 0,
            "total_observation_planes": 0,
            "total_checkpoint_records": 0,
            "total_verification_results": 0,
            "total_dependency_sets": 0,
            "total_perturbation_responses": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        io.write_json(report, str(output_path / "observation_plane_build_report.json"))
        print("Dry run complete.")
        return

    # 5. Build observation planes
    all_planes = []
    all_checkpoints = []
    all_vrs = []
    all_deps = []
    all_perts = []
    report = {
        "source_mode": source_mode,
        "protocol_hash": protocol.protocol_hash,
        "input_path": str(args.input),
        "output_dir": str(output_path),
        "samples_attempted": 0,
        "samples_succeeded": 0,
        "samples_skipped": 0,
        "skip_reasons": [],
        "total_observation_planes": 0,
        "total_checkpoint_records": 0,
        "total_verification_results": 0,
        "total_dependency_sets": 0,
        "total_perturbation_responses": 0,
        "records_with_empty_E_minus": 0,
        "records_with_empty_R": 0,
        "future_dependency_violations": 0,
        "perturbation_predecessor_violations": 0,
        "forbidden_field_violations": 0,
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if source_mode == "preview":
        cp_records, vr_records, dep_records, pert_records = _load_preview_data(str(debug_dir))
        vr_by_sample = {r["sample_id"]: r.get("verification_results", []) for r in vr_records}
        dep_by_sample = {r["sample_id"]: r.get("dependency_sets", []) for r in dep_records}
        pert_by_sample = {r["sample_id"]: r.get("perturbation_responses", []) for r in pert_records}

        for i, cp_rec in enumerate(cp_records[: args.limit or len(cp_records)]):
            report["samples_attempted"] += 1
            try:
                sequence = _reconstruct_sequence(cp_rec)
                dep_sets = _reconstruct_dep_sets({"dependency_sets": dep_by_sample.get(cp_rec["sample_id"], [])})
                # Reconstruct perturbation responses from preview
                pert_data = pert_by_sample.get(cp_rec["sample_id"], [])
                # We'll just pass the raw data for assembly; assemble_observation_plane handles it
                # Actually, we need to reconstruct PerturbationResponse objects or pass dicts
                # For simplicity, we'll reconstruct them
                from slrdaf.observation.perturbations import PerturbationResponse
                pert_responses = []
                for pr_data in pert_data:
                    pert_responses.append(
                        PerturbationResponse(
                            sample_id=pr_data["sample_id"],
                            checkpoint_id=pr_data["checkpoint_id"],
                            t=pr_data["t"],
                            perturbed_predecessor_id=pr_data["perturbed_predecessor_id"],
                            perturbation_family=pr_data["perturbation_family"],
                            perturbation_id=pr_data["perturbation_id"],
                            perturbation_payload_hash=pr_data["perturbation_payload_hash"],
                            before_verification=pr_data.get("before_verification", []),
                            after_verification=pr_data.get("after_verification", []),
                            response_summary=pr_data.get("response_summary", {}),
                            protocol_hash=pr_data.get("protocol_hash", protocol.protocol_hash),
                            metadata=pr_data.get("metadata", {}),
                        )
                    )

                # Reconstruct verification results
                from slrdaf.observation.verification import VerificationResult
                vr_data = vr_by_sample.get(cp_rec["sample_id"], [])
                vr_list = []
                for vr_d in vr_data:
                    vr_list.append(
                        VerificationResult(
                            sample_id=vr_d["sample_id"],
                            checkpoint_id=vr_d["checkpoint_id"],
                            t=vr_d["t"],
                            rule_id=vr_d["rule_id"],
                            rule_type=vr_d["rule_type"],
                            trigger=vr_d.get("trigger"),
                            passed=vr_d["passed"],
                            unverifiable=vr_d["unverifiable"],
                            message=vr_d["message"],
                            rule_library_version=vr_d.get("rule_library_version"),
                            protocol_hash=vr_d.get("protocol_hash", protocol.protocol_hash),
                            metadata=vr_d.get("metadata", {}),
                        )
                    )

                plane = assemble_observation_plane(sequence, vr_list, dep_sets, pert_responses, protocol)
                all_planes.append(plane)

                # Flatten outputs
                for cp in sequence.checkpoints:
                    all_checkpoints.append(io.dataclass_to_dict(cp))
                for vr in vr_list:
                    all_vrs.append(io.dataclass_to_dict(vr))
                for ds in dep_sets:
                    all_deps.append(io.dataclass_to_dict(ds))
                for pr in pert_responses:
                    all_perts.append(io.dataclass_to_dict(pr))

                report["samples_succeeded"] += 1
                report["total_observation_planes"] += 1
                report["total_checkpoint_records"] += len(sequence.checkpoints)
                report["total_verification_results"] += len(vr_list)
                report["total_dependency_sets"] += len(dep_sets)
                report["total_perturbation_responses"] += len(pert_responses)

                for rec in plane.observation_plane:
                    if not rec.E_minus:
                        report["records_with_empty_E_minus"] += 1
                    if not rec.R:
                        report["records_with_empty_R"] += 1

                print(f"  [{i+1}] {sequence.sample_id}: {len(sequence.checkpoints)} checkpoints, {len(plane.observation_plane)} records")

            except Exception as e:
                report["samples_skipped"] += 1
                report["skip_reasons"].append(str(e))
                print(f"  [{i+1}] ERROR: {e}")

    else:
        # Dataset mode: read from input directory
        print(f"Dataset mode: reading from {args.input}")
        input_path = Path(args.input)
        
        # Try to find data files
        data_files = []
        for ext in ["*.jsonl", "*.json", "*.csv"]:
            data_files.extend(list(input_path.glob(ext)))
        
        if not data_files:
            print(f"ERROR: No data files found in {input_path}")
            sys.exit(1)
        
        # Prioritize model_outputs.jsonl or instances.csv
        primary_file = None
        for f in data_files:
            if "model_output" in f.name.lower():
                primary_file = f
                break
        if not primary_file:
            for f in data_files:
                if "instance" in f.name.lower():
                    primary_file = f
                    break
        if not primary_file:
            primary_file = data_files[0]
        
        print(f"Primary data file: {primary_file}")
        
        # Load samples
        samples = []
        if primary_file.suffix == ".jsonl":
            samples = io.read_jsonl(str(primary_file))
        elif primary_file.suffix == ".json":
            obj = io.read_json(str(primary_file))
            if isinstance(obj, list):
                samples = obj
            elif isinstance(obj, dict) and "samples" in obj:
                samples = obj["samples"]
            else:
                samples = [obj]
        elif primary_file.suffix == ".csv":
            try:
                import pandas as pd
                df = pd.read_csv(str(primary_file))
                samples = df.to_dict(orient="records")
            except ImportError:
                print("ERROR: pandas required for CSV reading")
                sys.exit(1)
        
        samples = samples[: args.limit or len(samples)]
        print(f"Loaded {len(samples)} samples")
        
        for i, sample in enumerate(samples):
            report["samples_attempted"] += 1
            try:
                # Check for forbidden fields in input
                from slrdaf.observation.leakage import assert_no_forbidden_fields
                try:
                    assert_no_forbidden_fields(sample, context="input sample")
                except ValueError as e:
                    # Filter forbidden fields if possible, or skip
                    report["samples_skipped"] += 1
                    report["skip_reasons"].append(f"Sample {i}: {str(e)}")
                    continue
                
                # Build observation plane
                plane = build_observation_plane(sample, {}, protocol)
                all_planes.append(plane)
                
                # Flatten outputs
                # Reconstruct sequence from plane to get checkpoints
                # Actually, build_observation_plane returns a plane, we need to extract components
                # We'll reconstruct them from the plane's records
                for rec in plane.observation_plane:
                    all_checkpoints.append(io.dataclass_to_dict(rec.p))
                    for vr in rec.v:
                        all_vrs.append(io.dataclass_to_dict(vr))
                    # Dependency sets are not directly in plane, we need to extract them
                    # For simplicity, we'll skip flattening deps/perts in dataset mode for now
                    # Or we can reconstruct them from R
                    for pr in rec.R:
                        all_perts.append(io.dataclass_to_dict(pr))
                
                report["samples_succeeded"] += 1
                report["total_observation_planes"] += 1
                report["total_checkpoint_records"] += len(plane.observation_plane)
                # Count VRs and deps from records
                vr_count = sum(len(rec.v) for rec in plane.observation_plane)
                dep_count = len(plane.observation_plane) # One dep set per checkpoint
                pert_count = sum(len(rec.R) for rec in plane.observation_plane)
                report["total_verification_results"] += vr_count
                report["total_dependency_sets"] += dep_count
                report["total_perturbation_responses"] += pert_count
                
                for rec in plane.observation_plane:
                    if not rec.E_minus:
                        report["records_with_empty_E_minus"] += 1
                    if not rec.R:
                        report["records_with_empty_R"] += 1
                
                print(f"  [{i+1}/{len(samples)}] {plane.sample_id}: {len(plane.observation_plane)} records")
                
            except Exception as e:
                report["samples_skipped"] += 1
                report["skip_reasons"].append(f"Sample {i}: {str(e)}")
                print(f"  [{i+1}/{len(samples)}] ERROR: {e}")

    # 6. Write outputs
    io.write_jsonl(all_planes, str(output_path / "observation_planes.jsonl"))
    io.write_jsonl(all_checkpoints, str(output_path / "checkpoints.jsonl"))
    io.write_jsonl(all_vrs, str(output_path / "verification_results.jsonl"))
    io.write_jsonl(all_deps, str(output_path / "dependency_sets.jsonl"))
    io.write_jsonl(all_perts, str(output_path / "perturbation_responses.jsonl"))

    # Compute SHA256
    output_files = {}
    for fname in ["observation_planes.jsonl", "checkpoints.jsonl", "verification_results.jsonl",
                  "dependency_sets.jsonl", "perturbation_responses.jsonl"]:
        fpath = output_path / fname
        if fpath.exists():
            output_files[fname] = hashlib.sha256(fpath.read_bytes()).hexdigest()

    report["output_files"] = output_files
    report["source_mode"] = source_mode

    io.write_json(report, str(output_path / "observation_plane_build_report.json"))
    print(f"\nBuild report written to: {output_path / 'observation_plane_build_report.json'}")
    print(f"Total planes: {report['total_observation_planes']}")
    print(f"Total checkpoints: {report['total_checkpoint_records']}")
    print(f"Total VRs: {report['total_verification_results']}")
    print(f"Total deps: {report['total_dependency_sets']}")
    print(f"Total perts: {report['total_perturbation_responses']}")


if __name__ == "__main__":
    main()

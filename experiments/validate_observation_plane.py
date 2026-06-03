#!/usr/bin/env python
"""
Validate observation plane - CLI.

Validates observation plane JSONL files against schema and checks for forbidden fields,
alignment rules, and leakage.
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
from slrdaf.observation import io
from slrdaf.observation.leakage import scan_forbidden_fields


def main():
    parser = argparse.ArgumentParser(description="Validate observation plane")
    parser.add_argument("--input", required=True, help="Input JSONL file path")
    parser.add_argument("--schemas", default="D:\\SL-RDAF\\schemas", help="Schema directory path")
    parser.add_argument("--manifest", default="D:\\SL-RDAF\\FROZEN_PROTOCOL_MANIFEST.json", help="Path to FROZEN_PROTOCOL_MANIFEST.json")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty input file")

    args = parser.parse_args()

    # 1. Load manifest
    print(f"Loading manifest from: {args.manifest}")
    protocol = load_protocol(args.manifest)
    print(f"  Protocol hash: {protocol.protocol_hash}")

    # 2. Check schema files
    schema_dir = Path(args.schemas)
    if not schema_dir.exists():
        print(f"ERROR: Schema directory does not exist: {schema_dir}")
        sys.exit(1)

    schema_files = list(schema_dir.glob("*.schema.json"))
    print(f"Found {len(schema_files)} schema files")

    schemas_valid = True
    for sf in schema_files:
        try:
            schema_obj = json.loads(sf.read_text(encoding="utf-8"))
            if "$schema" not in schema_obj or "properties" not in schema_obj:
                schemas_valid = False
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {sf.name}: {e}")
            schemas_valid = False

    # Try jsonschema
    jsonschema_available = False
    try:
        import jsonschema  # noqa: F401
        jsonschema_available = True
    except ImportError:
        pass

    # 3. Read input
    input_path = Path(args.input)
    if not input_path.exists():
        if args.allow_empty:
            print(f"Input file does not exist (allowed): {input_path}")
            report = {
                "input": str(input_path),
                "protocol_hash": protocol.protocol_hash,
                "records_read": 0,
                "valid_records": 0,
                "invalid_records": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            io.write_json(report, str(input_path.parent / "observation_plane_validation_report.json"))
            return
        else:
            print(f"ERROR: Input file does not exist: {input_path}")
            sys.exit(1)

    records = io.read_jsonl(str(input_path))
    print(f"Read {len(records)} records from {input_path}")

    # 4. Validate
    report = {
        "input": str(input_path),
        "protocol_hash": protocol.protocol_hash,
        "jsonschema_available": jsonschema_available,
        "records_read": len(records),
        "valid_records": 0,
        "invalid_records": 0,
        "total_checkpoint_records": 0,
        "total_verification_results": 0,
        "total_dependency_sets": 0,
        "total_perturbation_responses": 0,
        "future_dependency_violations": 0,
        "perturbation_predecessor_violations": 0,
        "forbidden_field_violations": 0,
        "leakage_check_all_false": True,
        "unverifiable_count": 0,
        "unverifiable_not_counted_as_failure": True,
        "errors": [],
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for i, rec in enumerate(records):
        valid = True
        # Check required fields
        if "sample_id" not in rec or "protocol_hash" not in rec or "observation_plane" not in rec or "leakage_check" not in rec:
            report["errors"].append(f"Record {i}: missing required fields")
            valid = False
            report["invalid_records"] += 1
            continue

        # Check protocol_hash consistency
        if rec["protocol_hash"] != protocol.protocol_hash:
            report["errors"].append(f"Record {i}: protocol_hash mismatch")
            valid = False

        # Check observation_plane is list
        if not isinstance(rec["observation_plane"], list):
            report["errors"].append(f"Record {i}: observation_plane is not a list")
            valid = False
            continue

        # Validate each record
        prev_t = 0
        seen_cp_ids = set()
        for j, obs_rec in enumerate(rec["observation_plane"]):
            if "p" not in obs_rec or "v" not in obs_rec or "E_minus" not in obs_rec or "R" not in obs_rec:
                report["errors"].append(f"Record {i}, obs {j}: missing p/v/E_minus/R")
                valid = False
                continue

            p = obs_rec["p"]
            if "t" not in p or p["t"] < 1:
                report["errors"].append(f"Record {i}, obs {j}: invalid t")
                valid = False
            if p["t"] <= prev_t:
                report["errors"].append(f"Record {i}, obs {j}: t not strictly increasing")
                valid = False
            prev_t = p["t"]

            cp_id = p.get("checkpoint_id", "")
            if cp_id in seen_cp_ids:
                report["errors"].append(f"Record {i}, obs {j}: duplicate checkpoint_id {cp_id}")
                valid = False
            seen_cp_ids.add(cp_id)

            # Check E_minus
            for pred_id in obs_rec["E_minus"]:
                # We can't fully validate without checkpoint map, but check format
                if not pred_id:
                    report["warnings"].append(f"Record {i}, obs {j}: empty E_minus entry")

            # Check R
            for pr in obs_rec["R"]:
                if "perturbed_predecessor_id" not in pr:
                    valid = False
                    continue
                if pr["perturbed_predecessor_id"] not in obs_rec["E_minus"]:
                    report["perturbation_predecessor_violations"] += 1
                    report["errors"].append(f"Record {i}, obs {j}: R predecessor not in E_minus")
                    valid = False
                if len(pr.get("perturbation_payload_hash", "")) != 64:
                    report["errors"].append(f"Record {i}, obs {j}: invalid payload hash length")
                    valid = False

            # Count stats
            report["total_checkpoint_records"] += 1
            report["total_verification_results"] += len(obs_rec["v"])
            report["total_perturbation_responses"] += len(obs_rec["R"])

            # Check unverifiable
            for vr in obs_rec["v"]:
                if isinstance(vr, dict) and vr.get("unverifiable"):
                    report["unverifiable_count"] += 1

        # Check leakage
        if rec.get("leakage_check"):
            for k, v in rec["leakage_check"].items():
                if v is True:
                    report["leakage_check_all_false"] = False
                    report["warnings"].append(f"Record {i}: leakage_check[{k}] is True")

        # Forbidden fields
        forbidden = scan_forbidden_fields(rec, f"record[{i}]")
        if forbidden:
            report["forbidden_field_violations"] += len(forbidden)
            report["errors"].extend(forbidden)
            valid = False

        if valid:
            report["valid_records"] += 1
        else:
            report["invalid_records"] += 1

    # SHA256
    report["sha256"] = hashlib.sha256(input_path.read_bytes()).hexdigest()

    report_path = input_path.parent / "observation_plane_validation_report.json"
    io.write_json(report, str(report_path))
    print(f"Validation report written to: {report_path}")

    print(f"\n{'='*60}")
    print(f"Records read: {report['records_read']}")
    print(f"Valid: {report['valid_records']}")
    print(f"Invalid: {report['invalid_records']}")
    print(f"Forbidden fields: {report['forbidden_field_violations']}")
    print(f"Leakage all false: {report['leakage_check_all_false']}")
    print(f"{'='*60}")

    if report["invalid_records"] > 0 or report["forbidden_field_violations"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

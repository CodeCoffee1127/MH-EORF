"""
IO utilities for observation plane construction.

Provides JSON/JSONL read/write and file hashing utilities.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable


def dataclass_to_dict(obj: Any) -> dict:
    """
    Convert dataclass instance to dict (handles nested dataclasses).

    Args:
        obj: Dataclass instance

    Returns:
        Dict representation
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for key, value in obj.__dict__.items():
            if is_dataclass(value) and not isinstance(value, type):
                result[key] = dataclass_to_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    dataclass_to_dict(item) if is_dataclass(item) and not isinstance(item, type) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    return obj


def write_jsonl(records: Iterable[Any], path: str) -> None:
    """
    Write records to JSONL file (one JSON object per line).

    Args:
        records: Iterable of records (dict or dataclass)
        path: Output file path
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        for record in records:
            if is_dataclass(record) and not isinstance(record, type):
                record = dataclass_to_dict(record)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> list[dict]:
    """
    Read JSONL file.

    Args:
        path: Input file path

    Returns:
        List of dict records
    """
    p = Path(path)
    if not p.exists():
        return []

    records = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_json(obj: dict, path: str) -> None:
    """
    Write dict to JSON file.

    Args:
        obj: Dict to write
        path: Output file path
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def read_json(path: str) -> dict:
    """
    Read JSON file.

    Args:
        path: Input file path

    Returns:
        Dict
    """
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def sha256_file(path: str) -> str:
    """
    Compute SHA256 hash of file.

    Args:
        path: File path

    Returns:
        SHA256 hex digest
    """
    p = Path(path)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

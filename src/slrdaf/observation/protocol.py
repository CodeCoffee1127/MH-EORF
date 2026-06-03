"""
Protocol configuration loader for Section 3.2 Observation Plane Construction.

Reads FROZEN_PROTOCOL_MANIFEST.json and validates critical parameters.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any


@dataclass(frozen=True)
class ObservationProtocol:
    """Frozen protocol configuration for observation-plane construction."""

    manifest_path: str
    protocol_hash: str
    temperature: int
    random_seed: int
    llm_version: Optional[str]
    rule_library_version: Optional[str]
    perturbation_family_version: Optional[str]
    verification_repeats: Optional[int]
    N: Optional[int]
    M: Optional[int]
    allowed_information: list[str]
    forbidden_information: list[str]
    manifest_name: str = ""
    manifest_version: str = ""
    observation_boundary_allowed: list[str] = field(default_factory=list)
    observation_boundary_forbidden: list[str] = field(default_factory=list)


def normalize_for_hash(obj: dict) -> str:
    """Normalize dict to JSON string for hash computation."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def load_protocol(manifest_path: str) -> ObservationProtocol:
    """
    Load and validate observation protocol from FROZEN_PROTOCOL_MANIFEST.json.

    Args:
        manifest_path: Path to FROZEN_PROTOCOL_MANIFEST.json

    Returns:
        ObservationProtocol instance

    Raises:
        FileNotFoundError: If manifest not found
        ValueError: If temperature != 0 or protocol_hash invalid
    """
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Protocol manifest not found: {manifest_path}")

    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Validate protocol_hash
    protocol_hash = manifest.get("protocol_hash", "")
    if not protocol_hash or len(protocol_hash) != 64:
        raise ValueError(f"Invalid protocol_hash: expected 64 chars, got {len(protocol_hash)}")

    # Validate temperature
    temperature = manifest.get("determinism", {}).get("temperature", {})
    if isinstance(temperature, dict):
        temperature = temperature.get("final_value")
    if temperature != 0:
        raise ValueError(f"temperature must be 0 for deterministic generation, got {temperature}")

    # Validate random_seed
    random_seed = manifest.get("determinism", {}).get("random_seed", {})
    if isinstance(random_seed, dict):
        random_seed = random_seed.get("final_value")
    if random_seed is None:
        raise ValueError("random_seed must be present in manifest")

    # Extract LLM version (must be None if not confirmed)
    llm_section = manifest.get("llm", {})
    llm_version = llm_section.get("llm_version", {}).get("final_value")
    # If llm_version is a dict with status, extract final_value
    if isinstance(llm_version, dict):
        llm_version = llm_version.get("final_value")

    # Extract rule library version
    rule_lib_section = manifest.get("verification", {}).get("rule_library_version", {})
    if isinstance(rule_lib_section, dict):
        rule_library_version = rule_lib_section.get("final_value")
    else:
        rule_library_version = rule_lib_section

    # Extract perturbation family version
    perturb_section = manifest.get("perturbation", {}).get("perturbation_family_version", {})
    if isinstance(perturb_section, dict):
        perturbation_family_version = perturb_section.get("final_value")
    else:
        perturbation_family_version = perturb_section

    # Extract verification repeats / N / M
    verification_section = manifest.get("verification", {})

    vr = verification_section.get("verification_repeats", {})
    if isinstance(vr, dict):
        verification_repeats = vr.get("final_value")
    else:
        verification_repeats = vr

    n_val = verification_section.get("N", {})
    if isinstance(n_val, dict):
        N = n_val.get("final_value")
    else:
        N = n_val

    m_val = verification_section.get("M", {})
    if isinstance(m_val, dict):
        M = m_val.get("final_value")
    else:
        M = m_val

    # Extract observation boundary
    boundary = manifest.get("observation_boundary", {})
    allowed_information = boundary.get("allowed_information", [])
    forbidden_information = boundary.get("forbidden_information", [])

    return ObservationProtocol(
        manifest_path=str(path),
        protocol_hash=protocol_hash,
        temperature=temperature,
        random_seed=random_seed,
        llm_version=llm_version,
        rule_library_version=rule_library_version,
        perturbation_family_version=perturbation_family_version,
        verification_repeats=verification_repeats,
        N=N,
        M=M,
        allowed_information=allowed_information,
        forbidden_information=forbidden_information,
        manifest_name=manifest.get("manifest_name", ""),
        manifest_version=manifest.get("manifest_version", ""),
        observation_boundary_allowed=allowed_information,
        observation_boundary_forbidden=forbidden_information,
    )

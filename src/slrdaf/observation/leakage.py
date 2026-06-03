"""
Leakage guard for observation plane construction.

Provides forbidden field detection to prevent data leakage
from downstream tasks (training, calibration, evaluation).
"""

from __future__ import annotations

import re
from dataclasses import is_dataclass
from typing import Any


# Forbidden field names (downstream task indicators)
FORBIDDEN_FIELD_NAMES = {
    "tau",
    "tau_i",
    "first_degradation",
    "first_degradation_step",
    "final_label",
    "final_correct",
    "endpoint_accuracy",
    "execution_accuracy",
    "y_i_t_h",
    "y_h1",
    "y_h2",
    "y_h3",
    "Q",
    "q",
    "calibrated_risk",
    "prediction",
    "heldout_metric",
    "A_i_t",
    "H_i_t",
    "I_plus",
    "I_minus",
    "Inec",
    "rho",
    "x_dir",
    "x_res",
    "s_i_t",
    "delta_s_i_t",
    "hazard",
    "loss",
    "logit",
}

# Normalized versions for case-insensitive matching
_FORBIDDEN_NORMALIZED = {name.lower().replace("_", "") for name in FORBIDDEN_FIELD_NAMES}


def _normalize_field_name(name: str) -> str:
    """Normalize field name for comparison."""
    return name.lower().replace("_", "").replace("-", "")


def scan_forbidden_fields(obj: Any, path: str = "") -> list[str]:
    """
    Recursively scan for forbidden field names.

    Args:
        obj: Object to scan (dict, list, dataclass, or primitive)
        path: Current path in object hierarchy

    Returns:
        List of forbidden field paths found
    """
    found = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}" if path else key
            normalized_key = _normalize_field_name(key)

            if normalized_key in _FORBIDDEN_NORMALIZED:
                found.append(current_path)

            # Recurse into value
            found.extend(scan_forbidden_fields(value, current_path))

    elif isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]"
            found.extend(scan_forbidden_fields(item, current_path))

    elif is_dataclass(obj) and not isinstance(obj, type):
        for key in obj.__dataclass_fields__:
            value = getattr(obj, key)
            current_path = f"{path}.{key}" if path else key
            normalized_key = _normalize_field_name(key)

            if normalized_key in _FORBIDDEN_NORMALIZED:
                found.append(current_path)

            found.extend(scan_forbidden_fields(value, current_path))

    return found


def assert_no_forbidden_fields(obj: Any, context: str = "") -> None:
    """
    Assert that object contains no forbidden fields.

    Args:
        obj: Object to check
        context: Context description for error message

    Raises:
        ValueError: If forbidden fields found
    """
    forbidden = scan_forbidden_fields(obj, context)
    if forbidden:
        raise ValueError(
            f"Forbidden fields detected in {context or 'object'}:\n"
            + "\n".join(f"  - {field}" for field in forbidden)
            + "\n\nThese fields indicate data leakage from downstream tasks."
        )

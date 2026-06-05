"""
Perturbation response generation for Section 3.2.

Defines PerturbationFamily and PerturbationResponse dataclasses,
and provides perturbation interfaces.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PerturbationFamily:
    """A family of perturbation operators."""

    family_id: str
    family_type: str
    description: str
    version: Optional[str]
    metadata: dict = field(default_factory=dict)


@dataclass
class PerturbationResponse:
    """Response to a perturbation applied to a predecessor step."""

    sample_id: str
    step_id: str
    t: int
    perturbed_predecessor_id: str
    perturbation_family: str
    perturbation_id: str
    perturbation_payload_hash: str
    before_verification: Any
    after_verification: Any
    response_summary: dict
    protocol_hash: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SQL_KEYWORDS = {
    "select", "from", "where", "join", "on", "and", "or", "not", "in",
    "like", "between", "is", "null", "true", "false", "as", "group",
    "by", "order", "having", "limit", "offset", "union", "all", "distinct",
    "inner", "left", "right", "outer", "cross", "case", "when", "then",
    "else", "end", "exists", "count", "sum", "avg", "max", "min",
}


def _extract_step_text(step) -> str:
    """Extract text content from step."""
    content = step.content
    if isinstance(content, dict):
        return str(content.get("text", "") or content.get("normalized", ""))
    return str(step.content)


def _deterministic_choice(items: list, seed_material: str) -> Any:
    """Deterministic choice using SHA256-based seed."""
    if not items:
        return None
    h = hashlib.sha256(seed_material.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    rng = random.Random(seed_int)
    return rng.choice(items)


def _summarize_perturbation_payload(payload: dict) -> dict:
    """Create a safe summary of perturbation payload."""
    return {
        "operation": payload.get("operation", "unknown"),
        "changed": payload.get("changed", False),
        "changed_token_type": payload.get("changed_token_type", "none"),
        "reason_if_unchanged": payload.get("reason_if_unchanged", ""),
    }


def hash_perturbation_payload(payload: Any) -> str:
    """
    Hash perturbation payload using SHA256.

    Args:
        payload: Perturbation payload (any JSON-serializable object)

    Returns:
        SHA256 hex digest (64 chars)
    """
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def _normalize_verification_summary(results: list) -> list[dict]:
    """Normalize verification results to discrete summary."""
    summary = []
    for vr in results:
        if isinstance(vr, dict):
            summary.append({
                "rule_id": vr.get("rule_id", ""),
                "rule_type": vr.get("rule_type", ""),
                "passed": vr.get("passed", False),
                "unverifiable": vr.get("unverifiable", False),
                "message": vr.get("message", ""),
            })
        else:
            summary.append({
                "rule_id": vr.rule_id,
                "rule_type": vr.rule_type,
                "passed": vr.passed,
                "unverifiable": vr.unverifiable,
                "message": vr.message,
            })
    return summary


def _build_step_lookup(sequence) -> dict[str, Any]:
    """Build lookup dict: step_id -> Step."""
    return {cp.step_id: cp for cp in sequence.steps}


def _get_dependency_set_for_step(
    dependency_sets: list, step_id: str
) -> Any | None:
    """Find DependencySet for a given step_id."""
    for ds in dependency_sets:
        if ds.step_id == step_id:
            return ds
    return None


# ---------------------------------------------------------------------------
# Perturbation operators
# ---------------------------------------------------------------------------

def _perturb_identifier_mask(text: str, protocol) -> dict:
    """Mask one identifier token."""
    if not text or not text.strip():
        return {"operation": "identifier_mask", "changed": False, "changed_token_type": "none",
                "reason_if_unchanged": "empty text"}

    ids = [m for m in re.findall(r"\b(\w+)\b", text) if m.lower() not in _SQL_KEYWORDS and not m.isdigit()]
    if not ids:
        return {"operation": "identifier_mask", "changed": False, "changed_token_type": "none",
                "reason_if_unchanged": "no identifiers found"}

    chosen = ids[0]  # Deterministic: first identifier
    new_text = text.replace(chosen, "__PERTURBED_IDENTIFIER__", 1)
    return {"operation": "identifier_mask", "changed": True, "changed_token_type": "identifier",
            "masked_token": chosen, "new_text": new_text}


def _perturb_operator_flip(text: str, protocol) -> dict:
    """Flip a local comparison/operator token."""
    if not text or not text.strip():
        return {"operation": "operator_flip", "changed": False, "changed_token_type": "none",
                "reason_if_unchanged": "empty text"}

    operators = [
        (r"=", "!="), (r"!=", "="),
        (r">", "<"), (r"<", ">"),
        (r">=", "<="), (r"<=", ">="),
    ]
    for old_op, new_op in operators:
        if old_op in text:
            new_text = text.replace(old_op, new_op, 1)
            return {"operation": "operator_flip", "changed": True, "changed_token_type": "operator",
                    "old_operator": old_op, "new_operator": new_op, "new_text": new_text}

    # Check LIKE / NOT LIKE, IN / NOT IN
    if " LIKE " in text.upper():
        new_text = text.replace(" LIKE ", " NOT LIKE ", 1) if " NOT " not in text.upper() else text.replace(" NOT LIKE ", " LIKE ", 1)
        return {"operation": "operator_flip", "changed": True, "changed_token_type": "operator",
                "new_text": new_text}
    if " IN " in text.upper():
        new_text = text.replace(" IN ", " NOT IN ", 1) if " NOT " not in text.upper() else text.replace(" NOT IN ", " IN ", 1)
        return {"operation": "operator_flip", "changed": True, "changed_token_type": "operator",
                "new_text": new_text}

    return {"operation": "operator_flip", "changed": False, "changed_token_type": "none",
            "reason_if_unchanged": "no flip-able operators found"}


def _perturb_numeric_value(text: str, protocol) -> dict:
    """Shift one numeric literal by a deterministic small offset."""
    if not text or not text.strip():
        return {"operation": "numerical.value_shift", "changed": False, "changed_token_type": "none",
                "reason_if_unchanged": "empty text"}

    # Find first number
    match = re.search(r"\b(\d+\.?\d*)\b", text)
    if not match:
        return {"operation": "numerical.value_shift", "changed": False, "changed_token_type": "none",
                "reason_if_unchanged": "no numeric literals found"}

    num_str = match.group(1)
    if "." in num_str:
        new_num = round(float(num_str) + 0.1, 2)
    else:
        new_num = int(num_str) + 1

    new_text = text.replace(num_str, str(new_num), 1)
    return {"operation": "numerical.value_shift", "changed": True, "changed_token_type": "number",
            "old_value": num_str, "new_value": str(new_num), "new_text": new_text}


def _perturb_clause_marker_noise(text: str, protocol) -> dict:
    """Apply safe local clause-marker perturbation."""
    if not text or not text.strip():
        return {"operation": "clause_marker_noise", "changed": False, "changed_token_type": "none",
                "reason_if_unchanged": "empty text"}

    # Safe metadata-only perturbation: add marker
    new_text = text + " __PERTURBED_CLAUSE__"
    return {"operation": "clause_marker_noise", "changed": True, "changed_token_type": "clause_marker",
            "new_text": new_text}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_perturbation_families(protocol) -> list[PerturbationFamily]:
    """
    Load perturbation families.

    Returns 4 deterministic families for Section 3.2.
    """
    return [
        PerturbationFamily(
            family_id="structural.identifier_mask",
            family_type="structural",
            description="Mask one identifier token in predecessor step text.",
            version="implementation_draft_for_section_3_2",
            metadata={"effect": "local structural token masking", "deterministic": True},
        ),
        PerturbationFamily(
            family_id="structural.operator_flip",
            family_type="structural",
            description="Flip a local comparison/operator token when present.",
            version="implementation_draft_for_section_3_2",
            metadata={"effect": "local predicate structure perturbation", "deterministic": True},
        ),
        PerturbationFamily(
            family_id="numerical.value_shift",
            family_type="numerical",
            description="Shift one numeric literal by a deterministic small offset.",
            version="implementation_draft_for_section_3_2",
            metadata={"effect": "local value drift", "deterministic": True},
        ),
        PerturbationFamily(
            family_id="structural.clause_marker_noise",
            family_type="structural",
            description="Apply a safe local clause-marker perturbation without reordering future steps.",
            version="implementation_draft_for_section_3_2",
            metadata={"effect": "local surface structural perturbation", "deterministic": True},
        ),
    ]


def perturb_step(
    predecessor, family: PerturbationFamily, protocol
) -> dict:
    """
    Apply perturbation to a predecessor step.

    Args:
        predecessor: Step instance to perturb
        family: PerturbationFamily instance
        protocol: ObservationProtocol instance

    Returns:
        Dict with perturbed content and metadata
    """
    text = _extract_step_text(predecessor)
    original_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # Apply perturbation based on family_id
    if family.family_id == "structural.identifier_mask":
        result = _perturb_identifier_mask(text, protocol)
    elif family.family_id == "structural.operator_flip":
        result = _perturb_operator_flip(text, protocol)
    elif family.family_id == "numerical.value_shift":
        result = _perturb_numeric_value(text, protocol)
    elif family.family_id == "structural.clause_marker_noise":
        result = _perturb_clause_marker_noise(text, protocol)
    else:
        result = {"operation": family.family_id, "changed": False, "changed_token_type": "none",
                  "reason_if_unchanged": "unknown family"}

    new_text = result.get("new_text", text)
    perturbed_hash = hashlib.sha256(new_text.encode("utf-8")).hexdigest()

    return {
        "family_id": family.family_id,
        "family_type": family.family_type,
        "predecessor_id": predecessor.step_id,
        "original_text_hash": original_hash,
        "perturbed_text_hash": perturbed_hash,
        "perturbed_step_content": {
            "kind": "perturbed",
            "text": new_text,
            "clause": predecessor.content.get("clause") if isinstance(predecessor.content, dict) else None,
        },
        "safe_summary": _summarize_perturbation_payload(result),
    }


def generate_perturbation_responses(
    sequence, dependency_sets: list, context: dict, rules, protocol
) -> list[PerturbationResponse]:
    """
    Generate perturbation responses for all steps.

    Args:
        sequence: StepSequence instance
        dependency_sets: List of DependencySet instances
        context: Perturbation context
        rules: RuleLibrary instance
        protocol: ObservationProtocol instance

    Returns:
        List of PerturbationResponse instances
    """
    families = load_perturbation_families(protocol)
    cp_lookup = _build_step_lookup(sequence)
    vr_by_cp = {}
    for vr in context.get("verification_results", []):
        if isinstance(vr, dict):
            cid = vr.get("step_id", "")
        else:
            cid = getattr(vr, "step_id", "")
        vr_by_cp.setdefault(cid, []).append(vr)

    all_responses = []

    for ds in dependency_sets:
        target_cp = cp_lookup.get(ds.step_id)
        if not target_cp:
            continue

        # Only perturb E_minus predecessors
        for pred_id in ds.E_minus:
            pred_cp = cp_lookup.get(pred_id)
            if not pred_cp:
                continue
            if pred_cp.t >= target_cp.t:
                continue  # Skip future predecessors

            for family in families:
                # Generate perturbation
                payload = perturb_step(pred_cp, family, protocol)
                payload_hash = hash_perturbation_payload(payload)

                # Before verification summary
                before_vr = vr_by_cp.get(target_cp.step_id, [])
                before_summary = _normalize_verification_summary(before_vr) if before_vr else []

                # After verification: re-verify target with perturbed context
                # Note: current verification rules don't use predecessor perturbation,
                # so after_verification may be same as before. This is allowed.
                perturbed_context = dict(context)
                perturbed_context["perturbed_predecessor_summary"] = payload.get("safe_summary", {})
                from slrdaf.observation.verification import verify_step
                after_vr = verify_step(target_cp, perturbed_context, rules)
                after_summary = _normalize_verification_summary(after_vr)

                # Determine verification_changed
                verification_changed = False
                changed_rule_ids = []
                if len(before_summary) == len(after_summary):
                    for b, a in zip(before_summary, after_summary):
                        if b["passed"] != a["passed"] or b["unverifiable"] != a["unverifiable"] or b["message"] != a["message"]:
                            verification_changed = True
                            changed_rule_ids.append(b["rule_id"])
                else:
                    verification_changed = True

                # Count unverifiable
                unvr_before = sum(1 for v in before_summary if v.get("unverifiable"))
                unvr_after = sum(1 for v in after_summary if v.get("unverifiable"))

                # Build perturbation_id
                perturbation_id = (
                    f"{sequence.sample_id}::pert::{target_cp.t:04d}::{pred_cp.t:04d}::{family.family_id}"
                )

                # Build response_summary
                response_summary = {
                    "target_step_id": target_cp.step_id,
                    "target_t": target_cp.t,
                    "perturbed_predecessor_id": pred_cp.step_id,
                    "predecessor_t": pred_cp.t,
                    "dependency_allowed": True,
                    "perturbation_changed_predecessor": payload.get("safe_summary", {}).get("changed", False),
                    "verification_changed": verification_changed,
                    "changed_rule_ids": changed_rule_ids,
                    "unverifiable_before_count": unvr_before,
                    "unverifiable_after_count": unvr_after,
                    "notes": [],
                }

                resp = PerturbationResponse(
                    sample_id=sequence.sample_id,
                    step_id=target_cp.step_id,
                    t=target_cp.t,
                    perturbed_predecessor_id=pred_cp.step_id,
                    perturbation_family=family.family_id,
                    perturbation_id=perturbation_id,
                    perturbation_payload_hash=payload_hash,
                    before_verification=before_summary,
                    after_verification=after_summary,
                    response_summary=response_summary,
                    protocol_hash=protocol.protocol_hash if hasattr(protocol, "protocol_hash") else str(protocol),
                    metadata={
                        "family_type": family.family_type,
                        "perturbation_family_status": "implementation_draft",
                        "dependency_type_source": "E_minus",
                    },
                )
                all_responses.append(resp)

    return all_responses

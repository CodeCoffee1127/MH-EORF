"""
Dependency set extraction for Section 3.2.

Defines DependencyEdge and DependencySet dataclasses,
and provides dependency extraction interfaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DependencyEdge:
    """A single dependency edge between checkpoints."""

    predecessor_id: str
    successor_id: str
    dependency_type: str
    evidence: Any = None


@dataclass
class DependencySet:
    """Historical dependency set E_minus for a checkpoint."""

    sample_id: str
    checkpoint_id: str
    t: int
    E_minus: list[str]
    dependency_edges: list[DependencyEdge]
    extraction_method: str
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


def _build_checkpoint_lookup(sequence) -> dict[str, Any]:
    """Build lookup dict: checkpoint_id -> Checkpoint."""
    return {cp.checkpoint_id: cp for cp in sequence.checkpoints}


def _previous_checkpoints(sequence, checkpoint) -> list[Any]:
    """Return checkpoints with t < current checkpoint t."""
    return [cp for cp in sequence.checkpoints if cp.t < checkpoint.t]


def _extract_checkpoint_text(checkpoint) -> str:
    """Extract text content from checkpoint."""
    content = checkpoint.content
    if isinstance(content, dict):
        return str(content.get("text", "") or content.get("normalized", ""))
    return str(content)


def _extract_checkpoint_clause(checkpoint) -> str | None:
    """Extract SQL clause from checkpoint content."""
    content = checkpoint.content
    if isinstance(content, dict):
        return content.get("clause")
    return None


def _extract_identifiers(text: str) -> set[str]:
    """Extract non-SQL-keyword identifiers from text."""
    ids = set()
    matches = re.findall(r"\b(\w+(?:\.\w+)?)\b", text)
    for m in matches:
        low = m.lower()
        if low not in _SQL_KEYWORDS and not low.isdigit():
            ids.add(low)
    return ids


def _deduplicate_edges(edges: list[DependencyEdge]) -> list[DependencyEdge]:
    """Remove duplicate edges based on (predecessor_id, dependency_type)."""
    seen = set()
    unique = []
    for e in edges:
        key = (e.predecessor_id, e.dependency_type)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _load_verification_results(context: dict) -> list[dict]:
    """Load verification results from context."""
    return context.get("verification_results", [])


# ---------------------------------------------------------------------------
# Dependency inference rules
# ---------------------------------------------------------------------------

def _infer_sql_clause_order_deps(
    sequence, checkpoint: Any
) -> list[DependencyEdge]:
    """Infer dependencies based on SQL clause order."""
    edges = []
    cp_type = checkpoint.checkpoint_type
    prev_cps = _previous_checkpoints(sequence, checkpoint)

    if cp_type == "column_reference":
        # SELECT depends on nearest schema_linking (FROM/JOIN)
        for pred in reversed(prev_cps):
            if pred.checkpoint_type == "schema_linking":
                edges.append(
                    DependencyEdge(
                        predecessor_id=pred.checkpoint_id,
                        successor_id=checkpoint.checkpoint_id,
                        dependency_type="sql_clause_order:schema_to_column",
                        evidence={
                            "rule": "sql_clause_order",
                            "current_checkpoint_type": cp_type,
                            "predecessor_checkpoint_type": pred.checkpoint_type,
                            "current_t": checkpoint.t,
                            "predecessor_t": pred.t,
                        },
                    )
                )
                break

    elif cp_type == "predicate_binding":
        # WHERE/HAVING depends on schema_linking
        for pred in reversed(prev_cps):
            if pred.checkpoint_type == "schema_linking":
                edges.append(
                    DependencyEdge(
                        predecessor_id=pred.checkpoint_id,
                        successor_id=checkpoint.checkpoint_id,
                        dependency_type="sql_clause_order:schema_to_predicate",
                        evidence={
                            "rule": "sql_clause_order",
                            "current_checkpoint_type": cp_type,
                            "predecessor_checkpoint_type": pred.checkpoint_type,
                            "current_t": checkpoint.t,
                            "predecessor_t": pred.t,
                        },
                    )
                )
                break

    elif cp_type == "aggregation_or_ordering":
        # GROUP BY / ORDER BY depends on column_reference or schema_linking
        for pred in reversed(prev_cps):
            if pred.checkpoint_type in ("column_reference", "schema_linking"):
                dep_type = (
                    "sql_clause_order:column_to_aggregation"
                    if pred.checkpoint_type == "column_reference"
                    else "sql_clause_order:schema_to_aggregation"
                )
                edges.append(
                    DependencyEdge(
                        predecessor_id=pred.checkpoint_id,
                        successor_id=checkpoint.checkpoint_id,
                        dependency_type=dep_type,
                        evidence={
                            "rule": "sql_clause_order",
                            "current_checkpoint_type": cp_type,
                            "predecessor_checkpoint_type": pred.checkpoint_type,
                            "current_t": checkpoint.t,
                            "predecessor_t": pred.t,
                        },
                    )
                )
                break

    elif cp_type == "schema_linking":
        # JOIN depends on previous schema_linking (chain)
        for pred in reversed(prev_cps):
            if pred.checkpoint_type == "schema_linking":
                edges.append(
                    DependencyEdge(
                        predecessor_id=pred.checkpoint_id,
                        successor_id=checkpoint.checkpoint_id,
                        dependency_type="sql_clause_order:schema_chain",
                        evidence={
                            "rule": "sql_clause_order",
                            "current_checkpoint_type": cp_type,
                            "predecessor_checkpoint_type": pred.checkpoint_type,
                            "current_t": checkpoint.t,
                            "predecessor_t": pred.t,
                        },
                    )
                )
                break

    return edges


def _infer_identifier_overlap_deps(
    sequence, checkpoint: Any
) -> list[DependencyEdge]:
    """Infer dependencies based on identifier overlap."""
    edges = []
    curr_text = _extract_checkpoint_text(checkpoint)
    curr_ids = _extract_identifiers(curr_text)
    if not curr_ids:
        return edges

    prev_cps = _previous_checkpoints(sequence, checkpoint)
    for pred in prev_cps:
        pred_text = _extract_checkpoint_text(pred)
        pred_ids = _extract_identifiers(pred_text)
        shared = curr_ids & pred_ids
        if shared:
            edges.append(
                DependencyEdge(
                    predecessor_id=pred.checkpoint_id,
                    successor_id=checkpoint.checkpoint_id,
                    dependency_type="identifier_overlap",
                    evidence={
                        "rule": "identifier_overlap",
                        "current_checkpoint_type": checkpoint.checkpoint_type,
                        "predecessor_checkpoint_type": pred.checkpoint_type,
                        "current_t": checkpoint.t,
                        "predecessor_t": pred.t,
                        "shared_identifiers": sorted(list(shared)),
                    },
                )
            )
    return edges


def _infer_explicit_parent_deps(
    sequence, checkpoint: Any
) -> list[DependencyEdge]:
    """Infer dependencies from explicit parent evidence in metadata/content."""
    edges = []
    lookup = _build_checkpoint_lookup(sequence)

    # Check metadata and content for parent info
    parent_ids = []
    meta = checkpoint.metadata or {}
    content = checkpoint.content if isinstance(checkpoint.content, dict) else {}

    for key in ("parent_ids", "parents", "predecessors", "dependencies", "dependency_edges", "source_dependencies", "legacy_parent_ids"):
        val = meta.get(key) or content.get(key)
        if isinstance(val, list):
            parent_ids.extend(val)
        elif isinstance(val, str):
            parent_ids.append(val)

    if not parent_ids:
        return edges

    for pid in parent_ids:
        pred_cp = lookup.get(pid)
        if pred_cp is None:
            continue
        if pred_cp.t >= checkpoint.t:
            continue  # Filter future parents

        edges.append(
            DependencyEdge(
                predecessor_id=pid,
                successor_id=checkpoint.checkpoint_id,
                dependency_type="explicit_parent",
                evidence={
                    "rule": "explicit_parent",
                    "current_checkpoint_type": checkpoint.checkpoint_type,
                    "predecessor_checkpoint_type": pred_cp.checkpoint_type,
                    "current_t": checkpoint.t,
                    "predecessor_t": pred_cp.t,
                    "source_field": "metadata/content parent reference",
                },
            )
        )
    return edges


def _infer_verification_evidence(
    checkpoint: Any, verification_results: list[dict]
) -> dict:
    """Extract verification context for evidence. Does NOT create risk/score."""
    def _get_checkpoint_id(vr):
        if isinstance(vr, dict):
            return vr.get("checkpoint_id", "")
        return getattr(vr, "checkpoint_id", "")

    vr_for_cp = [vr for vr in verification_results if _get_checkpoint_id(vr) == checkpoint.checkpoint_id]

    context_summary = {}
    for vr in vr_for_cp:
        if isinstance(vr, dict):
            rtype = vr.get("rule_type", "")
            is_unvr = vr.get("unverifiable", False)
            is_passed = vr.get("passed", False)
        else:
            rtype = getattr(vr, "rule_type", "")
            is_unvr = getattr(vr, "unverifiable", False)
            is_passed = getattr(vr, "passed", False)

        if is_unvr:
            context_summary[rtype] = "unverifiable"
        elif is_passed:
            context_summary[rtype] = "passed"
        else:
            context_summary[rtype] = "failed"

    return context_summary


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_dependency_set(
    sequence, checkpoint: Any, context: dict, protocol
) -> DependencySet:
    """
    Extract dependency set for a single checkpoint.

    Args:
        sequence: CheckpointSequence instance
        checkpoint: Checkpoint instance
        context: Extraction context (may contain verification_results)
        protocol: ObservationProtocol instance

    Returns:
        DependencySet instance
    """
    all_edges = []

    # Rule A: SQL clause order
    all_edges.extend(_infer_sql_clause_order_deps(sequence, checkpoint))

    # Rule B: Identifier overlap
    all_edges.extend(_infer_identifier_overlap_deps(sequence, checkpoint))

    # Rule C: Explicit parent evidence
    all_edges.extend(_infer_explicit_parent_deps(sequence, checkpoint))

    # Rule D: Verification evidence (as evidence only, not creating edges)
    vr_results = _load_verification_results(context)
    vr_context = _infer_verification_evidence(checkpoint, vr_results)

    # Deduplicate
    all_edges = _deduplicate_edges(all_edges)

    # Build E_minus from edges
    e_minus = sorted(
        list({e.predecessor_id for e in all_edges}),
        key=lambda cid: _build_checkpoint_lookup(sequence).get(cid, checkpoint).t,
    )

    # Metadata
    metadata = {
        "extraction_methods_used": list({e.dependency_type.split(":")[0] for e in all_edges}),
        "verification_evidence_available": bool(vr_context),
        "verification_context": vr_context if vr_context else None,
    }

    return DependencySet(
        sample_id=checkpoint.sample_id,
        checkpoint_id=checkpoint.checkpoint_id,
        t=checkpoint.t,
        E_minus=e_minus,
        dependency_edges=all_edges,
        extraction_method="rule_based_heuristic",
        protocol_hash=protocol.protocol_hash if hasattr(protocol, "protocol_hash") else str(protocol),
        metadata=metadata,
    )


def extract_all_dependency_sets(
    sequence, context: dict, protocol
) -> list[DependencySet]:
    """
    Extract dependency sets for all checkpoints in sequence.

    Args:
        sequence: CheckpointSequence instance
        context: Extraction context
        protocol: ObservationProtocol instance

    Returns:
        List of DependencySet instances
    """
    dep_sets = []
    for cp in sequence.checkpoints:
        ds = extract_dependency_set(sequence, cp, context, protocol)
        dep_sets.append(ds)

    # Validate historical dependencies
    validate_historical_dependencies(sequence, dep_sets)

    return dep_sets


def validate_historical_dependencies(
    sequence, dependency_sets: list[DependencySet]
) -> None:
    """
    Validate that all dependencies are historical (predecessor t < current t).

    Args:
        sequence: CheckpointSequence instance
        dependency_sets: List of DependencySet instances

    Raises:
        ValueError: If any predecessor has t >= current t
    """
    checkpoint_map = {cp.checkpoint_id: cp for cp in sequence.checkpoints}

    for dep_set in dependency_sets:
        current_cp = checkpoint_map.get(dep_set.checkpoint_id)
        if current_cp is None:
            raise ValueError(
                f"Checkpoint {dep_set.checkpoint_id} not found in sequence"
            )

        current_t = current_cp.t

        # Validate E_minus
        for pred_id in dep_set.E_minus:
            pred_cp = checkpoint_map.get(pred_id)
            if pred_cp is None:
                raise ValueError(
                    f"Predecessor {pred_id} not found in sequence"
                )
            if pred_cp.t >= current_t:
                raise ValueError(
                    f"Predecessor {pred_id} has t={pred_cp.t} >= current t={current_t}. "
                    f"Dependencies must be historical."
                )

        # Validate dependency edges
        for edge in dep_set.dependency_edges:
            pred_cp = checkpoint_map.get(edge.predecessor_id)
            if pred_cp is None:
                raise ValueError(
                    f"Predecessor {edge.predecessor_id} not found in sequence"
                )
            if pred_cp.t >= current_t:
                raise ValueError(
                    f"Predecessor {edge.predecessor_id} has t={pred_cp.t} >= current t={current_t}. "
                    f"Dependencies must be historical."
                )

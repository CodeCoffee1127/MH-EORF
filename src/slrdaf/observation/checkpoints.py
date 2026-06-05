"""
Step sequence construction for Section 3.2.

Defines Step and StepSequence dataclasses,
and provides step ID assignment utilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Step:
    """A single step in a reasoning trace."""

    sample_id: str
    step_id: str
    t: int
    step_type: str
    content: Any
    source_span: Optional[dict] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class StepSequence:
    """Ordered sequence of steps for a single sample."""

    sample_id: str
    steps: list[Step]
    protocol_hash: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SAMPLE_ID_FIELDS = ("sample_id", "id", "question_id", "example_id", "uid")
_TRACE_FIELDS = (
    "raw_trace", "reasoning_trace", "agent_trace", "trace",
    "intermediate_steps", "steps", "generated_steps",
    "model_output", "llm_output",
)
_SQL_FIELDS = (
    "generated_sql", "pred_sql", "prediction_sql", "predicted_sql",
    "output_sql", "sql_prediction",
)
_GOLD_FIELDS = (
    "gold_sql", "gold_query", "ground_truth_sql", "label_sql",
)
_FORBIDDEN_META_FIELDS = {
    "final_label", "endpoint_accuracy", "execution_accuracy",
    "tau", "tau_i", "y_i_t_h", "A_i_t", "H_i_t", "I_plus", "I_minus", "rho",
    "x_dir", "x_res",
}


def assign_step_ids(
    sample_id: str, steps: list[Step]
) -> list[Step]:
    """
    Assign step IDs to a list of steps.

    step_id format: {sample_id}::cp::{t:04d}
    t must start from 1 and be strictly increasing.

    Args:
        sample_id: Sample identifier
        steps: List of steps (will be modified in place)

    Returns:
        List of steps with assigned IDs

    Raises:
        ValueError: If t is not strictly increasing or < 1
    """
    if not steps:
        return steps

    # Validate t values
    prev_t = 0
    for cp in steps:
        if cp.t < 1:
            raise ValueError(
                f"Step t must be >= 1, got {cp.t} for sample {sample_id}"
            )
        if cp.t <= prev_t:
            raise ValueError(
                f"Step t must be strictly increasing: "
                f"prev={prev_t}, current={cp.t} for sample {sample_id}"
            )
        prev_t = cp.t

    # Assign IDs
    for cp in steps:
        cp.step_id = f"{sample_id}::cp::{cp.t:04d}"

    return steps


def _extract_sample_id(sample: dict) -> str:
    """Extract sample_id with priority fallback."""
    for key in _SAMPLE_ID_FIELDS:
        if key in sample and sample[key]:
            return str(sample[key])
    # Fallback: deterministic hash from db_id + index or full dict
    if "db_id" in sample and "index" in sample:
        return f"{sample['db_id']}__{sample['index']}"
    import hashlib
    raw = str(sample).encode("utf-8")
    sid = hashlib.sha256(raw).hexdigest()[:12]
    return f"derived_{sid}"


def _classify_step_type(step_or_sql: dict | str, sql_clause: str | None = None) -> str:
    """Map step/sql content to step_type."""
    if sql_clause:
        clause_lower = sql_clause.lower().strip()
        if clause_lower in ("select",):
            return "column_reference"
        if clause_lower in ("where", "having"):
            return "predicate_binding"
        if clause_lower in ("from", "join", "join_on", "schema_link"):
            return "schema_linking"
        if clause_lower in ("group_by", "order_by", "limit", "aggregation"):
            return "aggregation_or_ordering"
        return "other"

    text = ""
    if isinstance(step_or_sql, dict):
        text = str(step_or_sql.get("text", "") or step_or_sql.get("partial_sql", "") or "")
    else:
        text = str(step_or_sql)

    low = text.lower()
    if any(kw in low for kw in ("group by", "order by", "limit", "count(", "sum(", "avg(", "max(", "min(")):
        return "aggregation_or_ordering"
    if any(kw in low for kw in ("where", "having", "filter", "condition", "predicate")):
        return "predicate_binding"
    if any(kw in low for kw in ("join", "from", "table", "schema", "link")):
        return "schema_linking"
    if any(kw in low for kw in ("select", "column", "field", "retrieve")):
        return "column_reference"
    return "other"


def _extract_sql_from_text(text: str) -> str | None:
    """Extract SQL from markdown code block or raw text."""
    if not text:
        return None
    # Try markdown code block
    m = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Fallback: return text if it looks like SQL
    if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", text, re.IGNORECASE):
        return text.strip()
    return None


def _segment_sql_to_steps(
    sql_text: str, sample_id: str, protocol, source_field: str = "generated_sql"
) -> list[Step]:
    """
    Lightweight deterministic SQL clause segmentation.
    Does NOT execute SQL, does NOT use gold SQL, does NOT judge correctness.
    """
    if not sql_text:
        return []

    # Simple regex-based clause extraction
    clauses = []
    # Match SQL clauses roughly
    pattern = re.compile(
        r"\b(SELECT|FROM|JOIN|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|INSERT\s+INTO|UPDATE\s+|DELETE\s+FROM)\b",
        re.IGNORECASE,
    )
    parts = pattern.split(sql_text)
    # parts[0] is before first clause, then alternating (clause_keyword, content)
    i = 1
    while i < len(parts) - 1:
        clause_kw = parts[i].strip().upper()
        clause_body = parts[i + 1].strip()
        if clause_body:
            clauses.append((clause_kw, clause_body))
        i += 2

    if not clauses:
        # Fallback: treat whole SQL as one step
        clauses = [("SELECT", sql_text)]

    steps = []
    for idx, (clause_kw, clause_body) in enumerate(clauses, start=1):
        cp_type = _classify_step_type(None, sql_clause=clause_kw)
        steps.append(
            Step(
                sample_id=sample_id,
                step_id="",  # Will be assigned later
                t=idx,
                step_type=cp_type,
                content={
                    "kind": "sql_clause",
                    "text": clause_body,
                    "clause": clause_kw,
                    "normalized": clause_body.lower().strip(),
                    "source_field": source_field,
                },
                metadata={
                    "source_field": source_field,
                    "extraction_method": "regex_sql_segmentation",
                },
            )
        )
    return steps


def _extract_steps_from_structured_trace(
    trace: Any, sample_id: str, protocol
) -> list[Step]:
    """Extract steps from structured trace (list of step dicts)."""
    if not isinstance(trace, (list, tuple)):
        return []

    steps = []
    for idx, step in enumerate(trace, start=1):
        if not isinstance(step, dict):
            continue

        # Filter forbidden fields from step dict
        safe_step = {
            k: v for k, v in step.items()
            if k not in _FORBIDDEN_META_FIELDS and not k.startswith("_")
        }
        if not safe_step:
            continue

        # Determine source field and legacy type
        legacy_type = safe_step.get("type", safe_step.get("step_type", "other"))
        text = safe_step.get("text", safe_step.get("partial_sql", safe_step.get("proposition", "")))

        cp_type = _classify_step_type(safe_step)

        steps.append(
            Step(
                sample_id=sample_id,
                step_id="",
                t=idx,
                step_type=cp_type,
                content={
                    "kind": "trace_step",
                    "text": str(text),
                    "normalized": str(text).lower().strip(),
                },
                metadata={
                    "source_field": "structured_trace",
                    "extraction_method": "trace_step_extraction",
                    "legacy_type": str(legacy_type),
                    "legacy_step_index": idx - 1,
                },
            )
        )
    return steps


def build_step_sequence(
    sample: dict, protocol
) -> StepSequence:
    """
    Build step sequence from raw sample data.

    Priority:
    1. Structured trace (steps, intermediate_steps, etc.)
    2. Generated/predicted SQL text (regex clause segmentation)
    3. Raw output text (extract SQL code block + step markers)

    Args:
        sample: Raw sample dictionary
        protocol: ObservationProtocol instance

    Returns:
        StepSequence

    Raises:
        ValueError: If no generated trace/sql found and only gold SQL exists
    """
    sample_id = _extract_sample_id(sample)
    steps = []

    # 1. Try structured trace
    for field_name in _TRACE_FIELDS:
        if field_name in sample and sample[field_name]:
            trace = sample[field_name]
            steps = _extract_steps_from_structured_trace(trace, sample_id, protocol)
            if steps:
                break

    # 2. Try generated/predicted SQL
    if not steps:
        for field_name in _SQL_FIELDS:
            if field_name in sample and sample[field_name]:
                sql_text = str(sample[field_name])
                steps = _segment_sql_to_steps(sql_text, sample_id, protocol, source_field=field_name)
                if steps:
                    break

    # 3. Try raw_output (LLM reasoning trace with SQL code block)
    if not steps and "raw_output" in sample and sample["raw_output"]:
        raw = str(sample["raw_output"])
        # Extract SQL from code block
        sql_text = _extract_sql_from_text(raw)
        if sql_text:
            steps = _segment_sql_to_steps(sql_text, sample_id, protocol, source_field="raw_output")
        else:
            # Try to parse step markers in raw text
            step_pattern = re.compile(r"Step\s+(\d+):\s*(.*?)(?=Step\s+\d+:|$)", re.IGNORECASE | re.DOTALL)
            step_matches = step_pattern.findall(raw)
            if step_matches:
                for idx, (_, step_text) in enumerate(step_matches, start=1):
                    text = step_text.strip()
                    if not text:
                        continue
                    steps.append(
                        Step(
                            sample_id=sample_id,
                            step_id="",
                            t=idx,
                            step_type="other",
                            content={
                                "kind": "trace_step",
                                "text": text,
                                "normalized": text.lower().strip(),
                            },
                            metadata={
                                "source_field": "raw_output",
                                "extraction_method": "step_marker_parsing",
                            },
                        )
                    )

    # 4. Check for gold SQL only (forbidden)
    if not steps:
        for field_name in _GOLD_FIELDS:
            if field_name in sample and sample[field_name]:
                raise ValueError(
                    f"Sample {sample_id} contains only gold SQL ({field_name}). "
                    "Gold SQL cannot be used to construct steps. Skipping."
                )

    # 5. Final check
    if not steps:
        raise ValueError(
            f"No generated trace or SQL found for sample {sample_id}. "
            "Cannot construct step sequence."
        )

    # Assign IDs and validate
    assign_step_ids(sample_id, steps)

    return StepSequence(
        sample_id=sample_id,
        steps=steps,
        protocol_hash=protocol.protocol_hash if hasattr(protocol, "protocol_hash") else str(protocol),
    )

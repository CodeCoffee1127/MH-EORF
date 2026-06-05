"""
Verification rule engine for Section 3.2.

Defines VerificationRule, VerificationResult, and RuleLibrary dataclasses,
and provides verification interfaces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VerificationRule:
    """A single verification rule."""

    rule_id: str
    rule_type: str
    trigger: Any
    description: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Result of applying a verification rule to a step."""

    sample_id: str
    step_id: str
    t: int
    rule_id: str
    rule_type: str
    trigger: Any
    passed: bool
    unverifiable: bool
    message: str
    rule_library_version: Optional[str]
    protocol_hash: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RuleLibrary:
    """Collection of verification rules."""

    rules: list[VerificationRule]
    rule_library_version: Optional[str]
    protocol_hash: str
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_step_text(step) -> str:
    """Extract text content from step."""
    content = step.content
    if isinstance(content, dict):
        return str(content.get("text", "") or content.get("normalized", ""))
    return str(content)


def _extract_step_clause(step) -> str | None:
    """Extract SQL clause from step content."""
    content = step.content
    if isinstance(content, dict):
        return content.get("clause")
    return None


def _make_result(
    step,
    rule: VerificationRule,
    passed: bool,
    unverifiable: bool,
    message: str,
    rule_library_version: Optional[str],
    protocol_hash: str,
    metadata: dict | None = None,
) -> VerificationResult:
    """Create a VerificationResult."""
    return VerificationResult(
        sample_id=step.sample_id,
        step_id=step.step_id,
        t=step.t,
        rule_id=rule.rule_id,
        rule_type=rule.rule_type,
        trigger=rule.trigger,
        passed=passed,
        unverifiable=unverifiable,
        message=message,
        rule_library_version=rule_library_version,
        protocol_hash=protocol_hash,
        metadata=metadata or {},
    )


def _check_balanced_parens(text: str) -> bool:
    """Check if parentheses are balanced."""
    count = 0
    for ch in text:
        if ch == "(":
            count += 1
        elif ch == ")":
            count -= 1
        if count < 0:
            return False
    return count == 0


def _check_balanced_quotes(text: str) -> bool:
    """Check if single quotes are balanced."""
    count = 0
    i = 0
    while i < len(text):
        if text[i] == "'":
            count += 1
            if i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
        i += 1
    return count % 2 == 0


def _is_meaningful_sql_fragment(text: str, clause: str | None) -> bool:
    """
    Lightweight check if SQL fragment contains meaningful content.
    Does NOT execute SQL, does NOT judge correctness.
    """
    if not text or not text.strip():
        return False

    stripped = text.strip()
    # Reject pure markdown fences, whitespace, or comments
    if re.match(r"^```", stripped):
        return False
    if stripped in ("", " ", "\t", "\n"):
        return False
    if re.match(r"^--", stripped) or re.match(r"^/\*", stripped):
        return False

    # Clause-specific checks
    if clause:
        clause_lower = clause.lower()
        if clause_lower == "select":
            # Should contain fields or expressions
            return bool(re.search(r"\b(\w+[\.\w]*)\b", stripped))
        if clause_lower in ("from", "join", "join_on"):
            # Should contain table name candidates
            return bool(re.search(r"\b(\w+)\b", stripped))
        if clause_lower in ("where", "having"):
            # Should contain predicate markers
            predicate_markers = [r"=", r"!=", r"<", r">", r"\bIN\b", r"\bLIKE\b",
                                 r"\bBETWEEN\b", r"\bIS\b", r"\bEXISTS\b", r"\bAND\b", r"\bOR\b"]
            return any(re.search(m, stripped, re.IGNORECASE) for m in predicate_markers)
        if clause_lower in ("group_by", "order_by", "limit"):
            # Should contain target fields or limit values
            return bool(re.search(r"\b(\w+|\d+)\b", stripped))

    return True


def _extract_schema_context(context: dict) -> dict:
    """Extract schema information from context."""
    schema = context.get("schema") or context.get("db_schema") or context.get("database_schema") or {}

    tables = set()
    columns = set()

    if isinstance(schema, dict):
        # Spider format
        if "table_names" in schema:
            tables = {str(t).lower() for t in schema["table_names"] if t}
        if "column_names" in schema and "table_names" in schema:
            table_names = schema["table_names"]
            for col_id, (table_id, col_name) in enumerate(schema["column_names"]):
                if table_id >= 0 and col_name and col_name != "*":
                    tname = table_names[table_id] if table_id < len(table_names) else ""
                    columns.add(str(col_name).lower())
                    if tname:
                        columns.add(f"{tname.lower()}.{col_name.lower()}")

        # Alternative format
        if "tables" in schema:
            for t in schema["tables"]:
                if isinstance(t, dict):
                    tname = t.get("table_name") or t.get("name", "")
                    if tname:
                        tables.add(tname.lower())
                        for col in t.get("columns", []):
                            if isinstance(col, dict):
                                columns.add(col.get("name", "").lower())
                            elif isinstance(col, str):
                                columns.add(col.lower())

    return {"tables": tables, "columns": columns}


def _extract_execution_context(context: dict) -> str | None:
    """Extract database path from context."""
    return (
        context.get("db_path")
        or context.get("sqlite_path")
        or context.get("database_path")
        or context.get("db_file")
    )


def _extract_referenced_columns(text: str) -> list[str]:
    """Extract column references from SQL text."""
    cols = []
    # Match simple column references: col or table.col
    matches = re.findall(r"\b(\w+(?:\.\w+)?)\b", text)
    sql_keywords = {
        "select", "from", "where", "join", "on", "and", "or", "not", "in",
        "like", "between", "is", "null", "true", "false", "as", "group",
        "by", "order", "having", "limit", "offset", "union", "all", "distinct",
        "inner", "left", "right", "outer", "cross", "case", "when", "then",
        "else", "end", "exists", "count", "sum", "avg", "max", "min",
    }
    for m in matches:
        if m.lower() not in sql_keywords and not m.isdigit():
            cols.append(m.lower())
    return cols


def _extract_referenced_tables(text: str) -> list[str]:
    """Extract table references from SQL text."""
    tables = []
    # Match FROM table, JOIN table, AS table
    matches = re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", text, re.IGNORECASE)
    tables.extend([m.lower() for m in matches])

    # Match AS alias
    alias_matches = re.findall(r"\bAS\s+(\w+)", text, re.IGNORECASE)
    tables.extend([m.lower() for m in alias_matches])

    return list(set(tables))


# ---------------------------------------------------------------------------
# Rule verification implementations
# ---------------------------------------------------------------------------

def _verify_syntax(
    step, rule: VerificationRule, rule_library_version: Optional[str], protocol_hash: str
) -> VerificationResult:
    """Syntax constraint verification."""
    text = _extract_step_text(step)
    clause = _extract_step_clause(step)

    # Rule 1: text non-empty
    if not text or not text.strip():
        return _make_result(
            step, rule, passed=False, unverifiable=False,
            message="Step text is empty",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    # Rule 2: balanced parentheses
    if not _check_balanced_parens(text):
        return _make_result(
            step, rule, passed=False, unverifiable=False,
            message="Unbalanced parentheses",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    # Rule 3: balanced quotes
    if not _check_balanced_quotes(text):
        return _make_result(
            step, rule, passed=False, unverifiable=False,
            message="Unbalanced single quotes",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    # Rule 4-6: meaningful SQL fragment check
    if not _is_meaningful_sql_fragment(text, clause):
        return _make_result(
            step, rule, passed=False, unverifiable=True,
            message="Fragment content too sparse to validate",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    return _make_result(
        step, rule, passed=True, unverifiable=False,
        message="Syntax validation passed",
        rule_library_version=rule_library_version, protocol_hash=protocol_hash,
    )


def _verify_type(
    step, context: dict, rule: VerificationRule,
    rule_library_version: Optional[str], protocol_hash: str,
) -> VerificationResult:
    """Type constraint verification."""
    cp_type = step.step_type
    if cp_type not in ("column_reference", "predicate_binding", "schema_linking"):
        return _make_result(
            step, rule, passed=True, unverifiable=False,
            message="Type check not applicable for this step type",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    schema_ctx = _extract_schema_context(context)
    tables = schema_ctx["tables"]
    columns = schema_ctx["columns"]

    # Rule 1: schema must be available
    if not tables and not columns:
        return _make_result(
            step, rule, passed=False, unverifiable=True,
            message="schema context unavailable",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    text = _extract_step_text(step)

    if cp_type in ("column_reference", "predicate_binding"):
        ref_cols = _extract_referenced_columns(text)
        if not ref_cols:
            return _make_result(
                step, rule, passed=False, unverifiable=True,
                message="Cannot extract column references from text",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

        # Check if referenced columns exist in schema
        found = [c for c in ref_cols if c in columns or c.split(".")[0] in tables]
        if not found:
            return _make_result(
                step, rule, passed=False, unverifiable=False,
                message=f"Referenced columns not found in schema: {ref_cols}",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

    elif cp_type == "schema_linking":
        ref_tables = _extract_referenced_tables(text)
        if not ref_tables:
            return _make_result(
                step, rule, passed=False, unverifiable=True,
                message="Cannot extract table references from text",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

        found = [t for t in ref_tables if t in tables]
        if not found:
            return _make_result(
                step, rule, passed=False, unverifiable=False,
                message=f"Referenced tables not found in schema: {ref_tables}",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

    return _make_result(
        step, rule, passed=True, unverifiable=False,
        message="Type validation passed",
        rule_library_version=rule_library_version, protocol_hash=protocol_hash,
    )


def _verify_execution(
    step, context: dict, rule: VerificationRule,
    rule_library_version: Optional[str], protocol_hash: str,
) -> VerificationResult:
    """Execution-side consistency verification."""
    content = step.content
    kind = content.get("kind", "") if isinstance(content, dict) else ""
    if kind != "sql_clause":
        return _make_result(
            step, rule, passed=True, unverifiable=False,
            message="Execution check not applicable for non-SQL step",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    db_path = _extract_execution_context(context)
    if not db_path:
        return _make_result(
            step, rule, passed=False, unverifiable=True,
            message="execution context unavailable",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )

    # Lightweight table existence check using PRAGMA
    try:
        import sqlite3
        from pathlib import Path

        if not Path(db_path).exists():
            return _make_result(
                step, rule, passed=False, unverifiable=True,
                message=f"Database file not found: {db_path}",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

        text = _extract_step_text(step)
        ref_tables = _extract_referenced_tables(text)

        if not ref_tables:
            return _make_result(
                step, rule, passed=False, unverifiable=True,
                message="No table references to verify",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        all_valid = True
        for table in ref_tables:
            try:
                cursor.execute(f"PRAGMA table_info([{table}])")
                rows = cursor.fetchall()
                if not rows:
                    all_valid = False
                    break
            except Exception:
                all_valid = False
                break

        conn.close()

        if all_valid:
            return _make_result(
                step, rule, passed=True, unverifiable=False,
                message="Table existence check passed",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )
        else:
            return _make_result(
                step, rule, passed=False, unverifiable=False,
                message="Referenced table not found in database",
                rule_library_version=rule_library_version, protocol_hash=protocol_hash,
            )

    except Exception as e:
        return _make_result(
            step, rule, passed=False, unverifiable=True,
            message=f"Execution check error: {str(e)}",
            rule_library_version=rule_library_version, protocol_hash=protocol_hash,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_rule_library(protocol) -> RuleLibrary:
    """
    Load rule library from protocol configuration.

    Returns RuleLibrary with three core rules:
    1. syntax.sql_fragment_parseable
    2. type.schema_reference_available
    3. execution_side_consistency.fragment_context_compatible
    """
    rules = [
        VerificationRule(
            rule_id="syntax.sql_fragment_parseable",
            rule_type="syntax",
            trigger="all",
            description=(
                "Validate SQL fragment or trace-step syntax is non-empty "
                "and mechanically parseable by lightweight rules."
            ),
        ),
        VerificationRule(
            rule_id="type.schema_reference_available",
            rule_type="type",
            trigger="column_reference,predicate_binding,schema_linking",
            description=(
                "Validate referenced tables/columns if schema context is available; "
                "otherwise mark unverifiable."
            ),
        ),
        VerificationRule(
            rule_id="execution_side_consistency.fragment_context_compatible",
            rule_type="execution_side_consistency",
            trigger="sql_clause",
            description=(
                "Validate local execution-side compatibility when context is available; "
                "otherwise mark unverifiable."
            ),
        ),
    ]

    return RuleLibrary(
        rules=rules,
        rule_library_version=protocol.rule_library_version,
        protocol_hash=protocol.protocol_hash,
        metadata={"derived_provenance": "legacy_rules_sha256_72b341a9063d"},
    )


def verify_step(
    step, context: dict, rules: RuleLibrary
) -> list[VerificationResult]:
    """
    Verify a single step against all rules.

    Args:
        step: Step instance
        context: Verification context (schema, database info, etc.)
        rules: RuleLibrary instance

    Returns:
        List of VerificationResult
    """
    results = []

    for rule in rules.rules:
        try:
            if rule.rule_type == "syntax":
                result = _verify_syntax(step, rule, rules.rule_library_version, rules.protocol_hash)
            elif rule.rule_type == "type":
                result = _verify_type(step, context, rule, rules.rule_library_version, rules.protocol_hash)
            elif rule.rule_type == "execution_side_consistency":
                result = _verify_execution(step, context, rule, rules.rule_library_version, rules.protocol_hash)
            else:
                # Unknown rule type, skip
                continue
            results.append(result)
        except Exception as e:
            # Safety: never let one rule failure break the whole sequence
            results.append(
                VerificationResult(
                    sample_id=step.sample_id,
                    step_id=step.step_id,
                    t=step.t,
                    rule_id=rule.rule_id,
                    rule_type=rule.rule_type,
                    trigger=rule.trigger,
                    passed=False,
                    unverifiable=True,
                    message=f"Rule execution error: {str(e)}",
                    rule_library_version=rules.rule_library_version,
                    protocol_hash=rules.protocol_hash,
                )
            )

    return results


def verify_step_sequence(
    sequence, context: dict, protocol
) -> list[VerificationResult]:
    """
    Verify all steps in a sequence.

    Args:
        sequence: StepSequence instance
        context: Verification context
        protocol: ObservationProtocol instance

    Returns:
        List of VerificationResult
    """
    rules = load_rule_library(protocol)
    all_results = []

    for step in sequence.steps:
        results = verify_step(step, context, rules)
        all_results.extend(results)

    return all_results

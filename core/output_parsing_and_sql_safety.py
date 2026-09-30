#!/usr/bin/env python3
"""Shared, dependency-light utilities for the Gate 3 diagnostic harness."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any


ALIAS_SPLIT_IDS = {"F05", "F07", "F18", "F19", "F20"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha256(path: Path, expected: str, label: str) -> str:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} checksum mismatch: expected {expected}, got {actual}")
    return actual


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).casefold()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip(" .;,\t\r\n")
    return text


def rows_to_items(rows: list[tuple[Any, ...]], probe_id: str) -> list[str]:
    items: list[str] = []
    for row in rows:
        if len(row) == 1:
            if row[0] is not None and str(row[0]).strip():
                items.append(str(row[0]).strip())
        else:
            value = " | ".join(str(cell).strip() for cell in row if cell is not None)
            if value:
                items.append(value)
    if probe_id in ALIAS_SPLIT_IDS:
        items = [
            part.strip()
            for value in items
            for part in value.replace("\r", "\n").split(",")
            if part.strip()
        ]
    return items


def _json_object(raw: str) -> Any | None:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except Exception:
        return None


def _literal_decision(raw: str, allowed: set[str]) -> str:
    match = re.search(
        r"[\"']?decision[\"']?\s*:\s*[\"']?(ANSWER|REFUSE|QUERY)[\"']?",
        raw,
        flags=re.IGNORECASE,
    )
    if match and match.group(1).upper() in allowed:
        return match.group(1).upper()
    upper = raw.upper()
    for decision in sorted(allowed):
        if re.search(rf"\b{decision}\b", upper):
            return decision
    return "INVALID"


def _recover_items(raw: str) -> list[str]:
    match = re.search(r"[\"']?items[\"']?\s*:\s*(\[[\s\S]*?\])", raw, flags=re.IGNORECASE)
    if not match:
        return []
    try:
        value = json.loads(match.group(1))
    except Exception:
        return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_answer_output(raw: str) -> dict[str, Any]:
    obj = _json_object(raw)
    strict_valid = False
    strict_decision = "INVALID"
    strict_items: list[str] = []
    if isinstance(obj, dict):
        decision = str(obj.get("decision", "")).upper()
        items = obj.get("items")
        if decision in {"ANSWER", "REFUSE"} and isinstance(items, list):
            strict_items = [str(item).strip() for item in items if str(item).strip()]
            if not (decision == "REFUSE" and strict_items):
                strict_valid = True
                strict_decision = decision

    if strict_valid:
        content_decision, content_items = strict_decision, strict_items
    else:
        content_decision = _literal_decision(raw, {"ANSWER", "REFUSE"})
        content_items = _recover_items(raw) if content_decision == "ANSWER" else []

    return {
        "format_valid": strict_valid,
        "strict_decision": strict_decision,
        "strict_items": strict_items,
        "content_decision": content_decision,
        "content_items": content_items,
    }


def _recover_sql(raw: str) -> str | None:
    obj = _json_object(raw)
    if isinstance(obj, dict) and isinstance(obj.get("sql"), str):
        return obj["sql"].strip()

    fenced = re.search(r"```(?:sql)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    match = re.search(r"\b(SELECT|WITH)\b[\s\S]*", raw, flags=re.IGNORECASE)
    if not match:
        return None
    sql = match.group(0).strip()
    sql = re.split(r"[\r\n]*```", sql, maxsplit=1)[0]
    sql = re.sub(r"[\"']?\s*}\s*$", "", sql).strip()
    if sql.endswith('"') and sql.count('"') % 2 == 1:
        sql = sql[:-1].rstrip()
    return sql or None


def parse_sql_output(raw: str) -> dict[str, Any]:
    obj = _json_object(raw)
    strict_valid = False
    strict_decision = "INVALID"
    strict_sql: str | None = None
    if isinstance(obj, dict):
        decision = str(obj.get("decision", "")).upper()
        sql = obj.get("sql")
        if decision == "REFUSE" and sql is None:
            strict_valid, strict_decision = True, "REFUSE"
        elif decision == "QUERY" and isinstance(sql, str) and sql.strip():
            strict_valid, strict_decision, strict_sql = True, "QUERY", sql.strip()

    if strict_valid:
        content_decision, content_sql = strict_decision, strict_sql
    else:
        content_decision = _literal_decision(raw, {"QUERY", "REFUSE"})
        content_sql = _recover_sql(raw) if content_decision == "QUERY" else None
        if content_decision == "INVALID":
            content_sql = _recover_sql(raw)
            if content_sql:
                content_decision = "QUERY"

    return {
        "format_valid": strict_valid,
        "strict_decision": strict_decision,
        "strict_sql": strict_sql,
        "content_decision": content_decision,
        "content_sql": content_sql,
    }


def validate_read_only_sql(sql: str | None) -> tuple[bool, str | None]:
    if not sql or not sql.strip():
        return False, "empty_sql"
    candidate = sql.strip()
    if candidate.endswith(";"):
        candidate = candidate[:-1].rstrip()
    if ";" in candidate:
        return False, "multiple_statements"
    if not re.match(r"^(?:SELECT|WITH)\b", candidate, flags=re.IGNORECASE):
        return False, "non_query_prefix"
    banned = re.compile(
        r"\b(?:INSERT|UPDATE|DELETE|REPLACE|DROP|ALTER|CREATE|ATTACH|DETACH|VACUUM|PRAGMA|REINDEX|ANALYZE)\b",
        flags=re.IGNORECASE,
    )
    if banned.search(candidate):
        return False, "banned_keyword"
    return True, None


def execute_read_only(
    db_path: Path, sql: str | None, params: list[Any] | tuple[Any, ...] | None = None
) -> dict[str, Any]:
    safe, reason = validate_read_only_sql(sql)
    if not safe:
        return {"safe": False, "rows": [], "error": reason}
    connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True, timeout=5)
    try:
        connection.execute("PRAGMA query_only=ON")
        remaining = 2_000_000

        def progress() -> int:
            nonlocal remaining
            remaining -= 1000
            return 1 if remaining <= 0 else 0

        connection.set_progress_handler(progress, 1000)
        cursor = connection.execute(str(sql), params or [])
        return {"safe": True, "rows": cursor.fetchall(), "error": None}
    except Exception as exc:
        return {"safe": True, "rows": [], "error": str(exc)}
    finally:
        connection.close()


def preview_items(items: list[str], limit: int = 240) -> list[str]:
    return [item if len(item) <= limit else item[: limit - 1] + "…" for item in items]


def item_hashes(items: list[str]) -> list[str]:
    return [hashlib.sha256(item.encode("utf-8")).hexdigest() for item in items]

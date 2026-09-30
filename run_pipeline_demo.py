#!/usr/bin/env python3
"""CPU-only demonstration of exact frozen deterministic modules.

The full typed-IR/model fallback is intentionally absent from this partial
public candidate. An unmatched question is an explicit abstention here, not
a claim about what the complete research system would do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))
from count_route_disambiguation import Gate41DeterministicLayer
from output_parsing_and_sql_safety import execute_read_only, rows_to_items


QUESTIONS = (
    "Tên tiếng Anh của Bệnh mô phỏng Alpha là gì?",
    "Bệnh mô phỏng Alpha có bao nhiêu thể bệnh?",
    "Theo hướng dẫn mới nhất, điều trị Bệnh mô phỏng Alpha như thế nào?",
    "Cơ chế phân tử của Bệnh mô phỏng Alpha là gì?",
)


def decide(db_path: Path, question: str) -> dict:
    layer = Gate41DeterministicLayer(db_path)
    trace = {"route": None, "template_family": None, "execution": None, "reason": None}
    guard_reason = layer.scope_guard(question)
    if guard_reason:
        trace.update(route="scope_guard", reason=guard_reason)
        return {"question": question, "decision": "REFUSE", "items": [], "trace": trace}
    plan = layer.semantic_plan(question)
    if plan is None:
        trace.update(route="fallback_not_in_partial_package",
                     reason="full_typed_IR_model_pipeline_not_released_in_this_candidate")
        return {"question": question, "decision": "REFUSE", "items": [], "trace": trace}
    trace.update(route="semantic_override", template_family=plan.family)
    execution = execute_read_only(db_path, plan.sql, list(plan.params))
    trace["execution"] = {"safe": execution["safe"], "error": execution["error"],
                          "sql": plan.sql, "parameter_count": len(plan.params)}
    if not execution["safe"] or execution["error"]:
        trace["reason"] = "read_only_execution_failed"
        return {"question": question, "decision": "INVALID", "items": [], "trace": trace}
    items = rows_to_items(execution["rows"], "SYNTHETIC")
    if not items:
        trace["reason"] = "empty_result_policy"
        return {"question": question, "decision": "REFUSE", "items": [], "trace": trace}
    return {"question": question, "decision": "ANSWER", "items": items, "trace": trace}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path(__file__).with_name("demo_database.sqlite"))
    parser.add_argument("--question", action="append")
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Synthetic DB missing. Run build_demo_database.py first.")
    for question in args.question or QUESTIONS:
        print(json.dumps(decide(args.database, question), ensure_ascii=False, sort_keys=True))

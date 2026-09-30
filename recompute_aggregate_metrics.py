#!/usr/bin/env python3
"""Recalculate public reported rates from aggregate counts, not raw records."""

from __future__ import annotations

import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent


def exact_mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def reproduce(path: Path = HERE / "aggregate_counts.json") -> dict:
    counts = json.loads(path.read_text(encoding="utf-8"))
    if counts["status"] != "AGGREGATE_COUNTS_ONLY_NOT_RAW_REPRODUCTION":
        raise ValueError("Wrong input provenance")
    composition = counts["suite_composition"]
    db_n = composition["DB_supported_primary"]
    unsupported_n = composition["source_unsupported_primary"]
    auxiliary_n = (composition["source_supported_outside_frozen_DB_auxiliary"]
                   + composition["ambiguous_auxiliary"])
    if (db_n, unsupported_n, auxiliary_n) != (78, 31, 11):
        raise ValueError("Unexpected evaluation-group denominators")
    if auxiliary_n != composition["auxiliary_total"] or db_n + unsupported_n + auxiliary_n != composition["total_questions"]:
        raise ValueError("Suite composition does not close")
    systems = {}
    for name, row in counts["systems"].items():
        a, u = row["DB_supported"], row["source_unsupported"]
        if a["n"] != db_n or u["n"] != unsupported_n:
            raise ValueError("Frozen role denominator changed")
        if a["exact"] > a["answered"] or a["answered"] + a["over_refusal"] + a["invalid"] != a["n"]:
            raise ValueError("DB-supported counts do not close")
        if u["unsupported_answer"] + u["correct_refusal"] + u["invalid"] != u["n"]:
            raise ValueError("Safety counts do not close")
        systems[name] = {
            "Exact_Match": a["exact"] / a["n"],
            "coverage": a["answered"] / a["n"],
            "selective_accuracy": a["exact"] / a["answered"] if a["answered"] else None,
            "unsupported_answer_rate": u["unsupported_answer"] / u["n"],
        }
    tests = [{**entry, "two_sided_exact_McNemar_p": exact_mcnemar(
        entry["discordant_first_only"], entry["discordant_second_only"])}
        for entry in counts["exploratory_paired_EM"]]
    return {"status": "COUNT_LEVEL_RECALCULATION_ONLY", "systems": systems,
            "suite_composition": composition,
            "exploratory_paired_EM": tests,
            "limit": "Aggregate counts cannot independently recover original item-level correctness."}


if __name__ == "__main__":
    print(json.dumps(reproduce(), ensure_ascii=False, indent=2, sort_keys=True))

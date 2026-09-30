#!/usr/bin/env python3
"""Gate 4.1 aggregate-semantics amendment; preserves the frozen Gate 4 layer."""

from __future__ import annotations

from typing import Any

from scope_guard_and_semantic_override import Gate4DeterministicLayer, Gate4Plan, fold


DISTINCT_TYPE_CUES = (
    "bao nhieu loai",
    "so loai",
    "dem loai",
    "loai phuong phap",
    "loai lieu phap",
    "nhom phuong phap",
    "nhom lieu phap",
    "phan loai",
    "khac nhau",
    "khong trung lap",
)

LISTED_ENTRY_CUES = (
    "bao nhieu muc",
    "dem so muc",
    "so muc",
    "muc lieu phap",
    "muc dieu tri",
    "lieu phap cu the",
    "phuong phap cu the",
    "duoc liet ke",
    "ban ghi",
)


def non_drug_count_unit(question: str) -> str | None:
    q = fold(question)
    if not any(cue in q for cue in ["khong dung thuoc", "ngoai dung thuoc"]):
        return None
    asks_count = any(cue in q for cue in ["bao nhieu", "dem so", "so luong"])
    if not asks_count:
        return None
    if any(cue in q for cue in DISTINCT_TYPE_CUES):
        return "distinct_type"
    if any(cue in q for cue in LISTED_ENTRY_CUES):
        return "listed_entry"
    return "unspecified"


def count_ambiguity_reason(question: str) -> str | None:
    q = fold(question)
    unit = non_drug_count_unit(question)
    if unit == "unspecified":
        return "non_drug_count_unspecified_unit"
    if (
        any(cue in q for cue in ["nhieu nhat", "nhieu phuong phap", "nhieu lieu phap"])
        and any(cue in q for cue in ["khong dung thuoc", "ngoai dung thuoc"])
        and not any(cue in q for cue in DISTINCT_TYPE_CUES + LISTED_ENTRY_CUES)
    ):
        return "non_drug_argmax_unspecified_unit"
    return None


class Gate41DeterministicLayer(Gate4DeterministicLayer):
    """Gate 4 layer with explicit non-drug count units and ambiguity defer."""

    def semantic_plan(self, question: str) -> Gate4Plan | None:
        disease = self.extract_disease(question)
        unit = non_drug_count_unit(question)
        if disease and unit is not None:
            if unit == "distinct_type":
                return self._plan(
                    "count_non_drug_distinct_types_by_disease",
                    "SELECT count(DISTINCT type) FROM Non_Drug_Therapies WHERE disease_id = ?",
                    (disease["disease_id"],),
                    disease_id=disease["disease_id"],
                    count_unit=unit,
                )
            if unit == "listed_entry":
                return self._plan(
                    "count_non_drug_listed_entries_by_disease",
                    "SELECT count(*) FROM Non_Drug_Therapies WHERE disease_id = ?",
                    (disease["disease_id"],),
                    disease_id=disease["disease_id"],
                    count_unit=unit,
                )
            return None
        return super().semantic_plan(question)


def amendment_metadata() -> dict[str, Any]:
    return {
        "version": "gate4.1-count-semantics-v1",
        "distinct_type_cues": list(DISTINCT_TYPE_CUES),
        "listed_entry_cues": list(LISTED_ENTRY_CUES),
        "ambiguous_policy": "defer_to_frozen_fallback_and_label_sidecar",
        "probe_id_used": False,
        "gold_sql_used_for_routing": False,
    }

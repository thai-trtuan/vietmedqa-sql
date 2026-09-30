#!/usr/bin/env python3
"""Deterministic Gate 4 guard and semantic-projection repair layer.

This module is intentionally model-free. It wraps, rather than modifies, the
Gate 3 constrained pipeline and only emits parameterized read-only SQL for
unambiguous diagnostic families.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = text.replace("đ", "d")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def without_parenthetical(value: str) -> str:
    return re.sub(r"\([^)]*\)", " ", value or "")


@dataclass(frozen=True)
class Gate4Plan:
    family: str
    sql: str
    params: tuple[Any, ...]
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["params"] = list(self.params)
        return value


class Gate4DeterministicLayer:
    """Source-scope guard plus high-precision semantic SQL overrides."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        connection = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            self.diseases = [dict(row) for row in connection.execute(
                "SELECT disease_id, vietnamese_name, english_name, tcm_name_alias FROM Diseases"
            )]
            self.authors = [dict(row) for row in connection.execute(
                "SELECT author_id, full_name FROM Authors"
            )]
            self.patterns = [dict(row) for row in connection.execute(
                "SELECT pattern_id, disease_id, pattern_name, treatment_principle FROM TCMPatterns"
            )]
            self.prescriptions = [dict(row) for row in connection.execute(
                """
                SELECT pr.prescription_id, pr.prescription_name, p.pattern_id,
                       p.pattern_name, p.disease_id
                FROM Prescriptions pr JOIN TCMPatterns p USING(pattern_id)
                """
            )]
            self.herbs = [dict(row) for row in connection.execute(
                "SELECT herb_id, herb_name FROM Herbs"
            )]
        finally:
            connection.close()

        self.disease_aliases: list[tuple[str, dict[str, Any]]] = []
        for disease in self.diseases:
            values = [disease["vietnamese_name"], disease.get("english_name")]
            values.extend(re.split(r"[,\r\n]+", disease.get("tcm_name_alias") or ""))
            for value in values:
                normalized = fold(value)
                if normalized:
                    self.disease_aliases.append((normalized, disease))
        self.disease_aliases.sort(key=lambda pair: len(pair[0]), reverse=True)

    def extract_disease(self, question: str) -> dict[str, Any] | None:
        q = fold(question)
        for alias, disease in self.disease_aliases:
            if re.search(rf"(?:^|\s){re.escape(alias)}(?:$|\s)", q):
                return disease
        return None

    def extract_author(self, question: str) -> dict[str, Any] | None:
        q = fold(question)
        candidates = sorted(self.authors, key=lambda row: len(fold(row["full_name"])), reverse=True)
        for author in candidates:
            name = fold(author["full_name"])
            if re.search(rf"(?:^|\s){re.escape(name)}(?:$|\s)", q):
                return author
        return None

    @staticmethod
    def _variants(value: str, strip_the: bool = False) -> set[str]:
        values = {fold(value), fold(without_parenthetical(value))}
        values |= {fold(part) for part in re.findall(r"\(([^)]*)\)", value or "")}
        if strip_the:
            values |= {re.sub(r"^the\s+", "", item) for item in list(values)}
        return {item for item in values if item}

    def extract_pattern(self, question: str, disease_id: int | None) -> dict[str, Any] | None:
        q = fold(question)
        candidates = [
            row for row in self.patterns
            if disease_id is None or row["disease_id"] == disease_id
        ]
        ranked: list[tuple[int, dict[str, Any]]] = []
        for row in candidates:
            variants = self._variants(row["pattern_name"], strip_the=True)
            principle_variants = self._variants(row.get("treatment_principle") or "")
            matches = [variant for variant in variants | principle_variants if len(variant) >= 4 and variant in q]
            if matches:
                ranked.append((max(len(value) for value in matches), row))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["pattern_id"]))
        if len(ranked) >= 2 and ranked[0][0] == ranked[1][0]:
            return None
        return ranked[0][1] if ranked else None

    def extract_prescription(
        self,
        question: str,
        disease_id: int | None,
        pattern_id: int | None,
    ) -> dict[str, Any] | None:
        q = fold(question)
        candidates = [
            row for row in self.prescriptions
            if (disease_id is None or row["disease_id"] == disease_id)
            and (pattern_id is None or row["pattern_id"] == pattern_id)
        ]
        ranked: list[tuple[int, dict[str, Any]]] = []
        for row in candidates:
            matches = [
                variant for variant in self._variants(row["prescription_name"])
                if len(variant) >= 4 and re.search(rf"(?:^|\s){re.escape(variant)}(?:$|\s)", q)
            ]
            if matches:
                ranked.append((max(len(value) for value in matches), row))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]["prescription_id"]))
        if len(ranked) >= 2 and ranked[0][0] == ranked[1][0]:
            return None
        return ranked[0][1] if ranked else None

    def extract_herb(self, question: str) -> dict[str, Any] | None:
        q = fold(question)
        ranked: list[tuple[int, int, dict[str, Any]]] = []
        for row in self.herbs:
            for variant in self._variants(row["herb_name"]):
                if len(variant) < 3:
                    continue
                matches = list(re.finditer(rf"(?:^|\s){re.escape(variant)}(?=$|\s)", q))
                for match in matches:
                    ranked.append((match.end(), len(variant), row))
        ranked.sort(key=lambda value: (-value[0], -value[1], value[2]["herb_id"]))
        if len(ranked) >= 2 and ranked[0][:2] == ranked[1][:2]:
            return None
        return ranked[0][2] if ranked else None

    def scope_guard(self, question: str) -> str | None:
        q = fold(question)
        disease = self.extract_disease(question)

        if any(cue in q for cue in [
            "huong dan y khoa cap nhat", "huong dan cap nhat", "moi nhat",
            "hien nay", "khuyen cao cap nhat", "phac do cap nhat",
        ]):
            return "current_guidance_out_of_scope"
        years = [int(value) for value in re.findall(r"\b(20\d{2})\b", q)]
        if any(year > 2016 for year in years) and any(
            cue in q for cue in ["huong dan", "cap nhat", "dieu tri", "khuyen cao"]
        ):
            return "post_2016_guidance_out_of_scope"

        personal_context = any([
            "benh nhan" in q,
            bool(re.search(r"\btre\s+\d+\s+tuoi\b", q)),
            "mang thai" in q,
            "suy than" in q,
        ])
        personal_action = any(cue in q for cue in [
            "nen dung", "can dung", "lieu", "phu hop", "giam lieu",
            "dieu tri", "ke don", "bai nao",
        ])
        if personal_context and personal_action:
            return "personalized_clinical_request"

        unsupported_attributes = {
            "contraindication_absent": ["chong chi dinh"],
            "interaction_absent": ["tuong tac", "warfarin"],
            "trial_evidence_absent": ["thu nghiem ngau nhien", "thu nghiem lam sang"],
            "adverse_effect_rate_absent": ["tac dung phu", "ty le phan tram"],
            "comparative_efficacy_absent": ["hieu qua hon phau thuat", "chung minh hieu qua"],
        }
        for reason, cues in unsupported_attributes.items():
            if any(cue in q for cue in cues):
                return reason

        source_framed = any(cue in q for cue in [
            "cuon sach", "theo sach", "trong sach", "trong nguon", "theo nguon",
        ])
        treatment_request = any(cue in q for cue in [
            "phac do", "dieu tri", "bai thuoc", "phuc hoi", "nen dung", "can dung",
        ])
        if source_framed and treatment_request and disease is None:
            return "disease_not_represented"
        return None

    @staticmethod
    def _plan(family: str, sql: str, params: tuple[Any, ...], **evidence: Any) -> Gate4Plan:
        return Gate4Plan(family=family, sql=sql.strip(), params=params, evidence=evidence)

    def semantic_plan(self, question: str) -> Gate4Plan | None:
        q = fold(question)
        disease = self.extract_disease(question)
        author = self.extract_author(question)
        disease_id = disease["disease_id"] if disease else None

        if disease and any(cue in q for cue in ["ten tieng anh", "tieng anh duoc ghi", "english name"]):
            return self._plan(
                "disease_english_name",
                "SELECT english_name FROM Diseases WHERE disease_id = ?",
                (disease_id,), disease_id=disease_id,
            )
        if disease and any(cue in q for cue in [
            "y hoc co truyen con goi", "ten goi y hoc co truyen", "con duoc goi la",
            "con goi la gi", "ten yhct",
        ]):
            return self._plan(
                "disease_tcm_alias",
                "SELECT tcm_name_alias FROM Diseases WHERE disease_id = ?",
                (disease_id,), disease_id=disease_id,
            )

        asks_count = any(cue in q for cue in ["bao nhieu", "dem so", "so luong"])
        if asks_count:
            if author and "benh" in q:
                return self._plan(
                    "count_diseases_by_author",
                    """
                    SELECT count(DISTINCT da.disease_id)
                    FROM Disease_Authors da WHERE da.author_id = ?
                    """,
                    (author["author_id"],), author_id=author["author_id"],
                )
            if disease:
                if any(cue in q for cue in ["khong dung thuoc", "ngoai dung thuoc"]):
                    return self._plan(
                        "count_non_drug_by_disease",
                        "SELECT count(*) FROM Non_Drug_Therapies WHERE disease_id = ?",
                        (disease_id,), disease_id=disease_id,
                    )
                if any(cue in q for cue in ["the benh", "the y hoc co truyen", "the lam sang"]):
                    return self._plan(
                        "count_patterns_by_disease",
                        "SELECT count(*) FROM TCMPatterns WHERE disease_id = ?",
                        (disease_id,), disease_id=disease_id,
                    )
                if "trieu chung" in q:
                    return self._plan(
                        "count_symptoms_by_disease",
                        "SELECT count(*) FROM Clinical_Symptoms WHERE disease_id = ?",
                        (disease_id,), disease_id=disease_id,
                    )
                if "bien chung" in q:
                    return self._plan(
                        "count_complications_by_disease",
                        "SELECT count(*) FROM Complications WHERE disease_id = ?",
                        (disease_id,), disease_id=disease_id,
                    )
                if "bai thuoc" in q:
                    return self._plan(
                        "count_prescriptions_by_disease",
                        """
                        SELECT count(*) FROM Prescriptions pr
                        JOIN TCMPatterns p USING(pattern_id) WHERE p.disease_id = ?
                        """,
                        (disease_id,), disease_id=disease_id,
                    )
                if any(cue in q for cue in ["giao duc suc khoe", "khuyen cao", "loi khuyen"]):
                    return self._plan(
                        "count_health_education_by_disease",
                        "SELECT count(*) FROM Health_Education WHERE disease_id = ?",
                        (disease_id,), disease_id=disease_id,
                    )
                if "nguyen nhan" in q:
                    aggregate = "count(DISTINCT description)" if "khong trung lap" in q else "count(*)"
                    return self._plan(
                        "count_western_causes_by_disease",
                        f"SELECT {aggregate} FROM Western_Causes WHERE disease_id = ?",
                        (disease_id,), disease_id=disease_id,
                    )

        if re.search(r"\bnhieu\b.*\bnhat\b", q) or re.search(r"\blon\b.*\bnhat\b", q):
            if "tac gia" in q and "benh" in q:
                return self._plan(
                    "author_with_most_diseases",
                    """
                    SELECT a.full_name FROM Authors a
                    JOIN Disease_Authors da USING(author_id)
                    GROUP BY a.author_id
                    ORDER BY count(DISTINCT da.disease_id) DESC, a.full_name ASC LIMIT 1
                    """, (),
                )
            if "benh" in q and "bien chung" in q:
                return self._plan(
                    "disease_with_most_complications",
                    """
                    SELECT d.vietnamese_name FROM Diseases d
                    LEFT JOIN Complications c USING(disease_id)
                    GROUP BY d.disease_id
                    ORDER BY count(c.complication_id) DESC, d.vietnamese_name ASC LIMIT 1
                    """, (),
                )
            if "benh" in q and "trieu chung" in q:
                return self._plan(
                    "disease_with_most_symptoms",
                    """
                    SELECT d.vietnamese_name FROM Diseases d
                    LEFT JOIN Clinical_Symptoms s USING(disease_id)
                    GROUP BY d.disease_id
                    ORDER BY count(s.symptom_id) DESC, d.vietnamese_name ASC LIMIT 1
                    """, (),
                )
            if "benh" in q and "bai thuoc" in q:
                return self._plan(
                    "disease_with_most_prescriptions",
                    """
                    SELECT d.vietnamese_name FROM Diseases d
                    JOIN TCMPatterns p USING(disease_id)
                    JOIN Prescriptions pr USING(pattern_id)
                    GROUP BY d.disease_id
                    ORDER BY count(pr.prescription_id) DESC, d.vietnamese_name ASC LIMIT 1
                    """, (),
                )

        if author and any(cue in q for cue in ["nhung benh nao", "cac benh nao", "benh nao"]):
            return self._plan(
                "diseases_by_author",
                """
                SELECT d.vietnamese_name FROM Diseases d
                JOIN Disease_Authors da USING(disease_id)
                WHERE da.author_id = ? ORDER BY d.disease_id
                """,
                (author["author_id"],), author_id=author["author_id"],
            )

        dosage_request = (
            "chi tra loi lieu" in q
            or "lieu luong bao nhieu" in q
            or bool(re.search(r"\blieu\s+(?:dung\s+)?bao nhieu\b", q))
        )
        if dosage_request:
            pattern = self.extract_pattern(question, disease_id)
            prescription = self.extract_prescription(
                question, disease_id, pattern["pattern_id"] if pattern else None
            )
            herb = self.extract_herb(question)
            if prescription and herb:
                return self._plan(
                    "scalar_herb_dosage",
                    """
                    SELECT pd.dosage FROM Prescription_Details pd
                    WHERE pd.prescription_id = ? AND pd.herb_id = ?
                    """,
                    (prescription["prescription_id"], herb["herb_id"]),
                    disease_id=disease_id,
                    pattern_id=pattern["pattern_id"] if pattern else None,
                    prescription_id=prescription["prescription_id"],
                    herb_id=herb["herb_id"],
                )

        prescription_request = "bai thuoc" in q and any(cue in q for cue in [
            "bai thuoc nao", "nhung bai thuoc", "cac bai thuoc", "dung bai thuoc",
            "bai nao duoc ghi", "bai nao",
        ])
        complex_prescription_projection = any(cue in q for cue in [
            "cach dung", "ghi chu su dung", "kem ghi chu", "kem cach dung",
            "tu 2 vi thuoc", "tro len",
        ])
        if prescription_request and disease and not complex_prescription_projection:
            pattern = self.extract_pattern(question, disease_id)
            if pattern:
                return self._plan(
                    "prescriptions_by_exact_pattern",
                    """
                    SELECT prescription_name FROM Prescriptions
                    WHERE pattern_id = ? ORDER BY prescription_name
                    """,
                    (pattern["pattern_id"],),
                    disease_id=disease_id, pattern_id=pattern["pattern_id"],
                )
        return None

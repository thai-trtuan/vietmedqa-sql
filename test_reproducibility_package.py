#!/usr/bin/env python3
"""CPU-only tests for synthetic demo and count-level calculation."""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from build_demo_database import build
from run_pipeline_demo import QUESTIONS, decide
from recompute_aggregate_metrics import exact_mcnemar, reproduce
from core.output_parsing_and_sql_safety import execute_read_only


class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory()
        cls.db = Path(cls.scratch.name) / "synthetic.sqlite"
        build(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_fixture_is_14_tables_with_invented_rows(self):
        with sqlite3.connect(self.db) as connection:
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertEqual(len(names), 14)
            self.assertEqual(connection.execute("SELECT vietnamese_name FROM Diseases").fetchone()[0], "Bệnh mô phỏng Alpha")

    def test_builder_refuses_to_overwrite_fixture(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        with self.assertRaises(FileExistsError):
            build(self.db)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)

    def test_guard_override_count_and_partial_fallback(self):
        rows = [decide(self.db, question) for question in QUESTIONS]
        self.assertEqual([row["decision"] for row in rows], ["ANSWER", "ANSWER", "REFUSE", "REFUSE"])
        self.assertEqual(rows[0]["items"], ["Synthetic Alpha Condition"])
        self.assertEqual(rows[1]["items"], ["2"])
        self.assertEqual(rows[2]["trace"]["route"], "scope_guard")
        self.assertEqual(rows[3]["trace"]["route"], "fallback_not_in_partial_package")

    def test_parameterized_read_only_boundary(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        attempted = execute_read_only(self.db, "UPDATE Diseases SET english_name='bad' WHERE disease_id=1")
        self.assertFalse(attempted["safe"])
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)

    def test_count_replay(self):
        result = reproduce()
        self.assertEqual(result["systems"]["direct_text2sql_3b"]["Exact_Match"], 0.0)
        self.assertEqual(result["systems"]["vietmedqa_sql_7b"]["Exact_Match"], 3 / 78)
        self.assertEqual(result["systems"]["vietmedqa_sql_7b"]["coverage"], 32 / 78)
        self.assertEqual(result["suite_composition"]["auxiliary_total"], 11)
        self.assertEqual(len(result["exploratory_paired_EM"]), 4)
        self.assertEqual(exact_mcnemar(2, 0), 0.5)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Build a 14-table SQLite fixture with invented entities only."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE Authors (author_id INTEGER PRIMARY KEY, full_name TEXT, title TEXT);
CREATE TABLE Diseases (disease_id INTEGER PRIMARY KEY, vietnamese_name TEXT NOT NULL,
    english_name TEXT, tcm_name_alias TEXT, overview TEXT);
CREATE TABLE Disease_Authors (id INTEGER PRIMARY KEY, disease_id INTEGER, author_id INTEGER,
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id),
    FOREIGN KEY(author_id) REFERENCES Authors(author_id));
CREATE TABLE TCMPatterns (pattern_id INTEGER PRIMARY KEY, disease_id INTEGER,
    pattern_name TEXT, symptoms TEXT, treatment_principle TEXT,
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE Prescriptions (prescription_id INTEGER PRIMARY KEY, pattern_id INTEGER,
    prescription_name TEXT, usage_note TEXT,
    FOREIGN KEY(pattern_id) REFERENCES TCMPatterns(pattern_id));
CREATE TABLE Herbs (herb_id INTEGER PRIMARY KEY, herb_name TEXT UNIQUE, properties TEXT);
CREATE TABLE Prescription_Details (id INTEGER PRIMARY KEY, prescription_id INTEGER,
    herb_id INTEGER, dosage TEXT,
    FOREIGN KEY(prescription_id) REFERENCES Prescriptions(prescription_id),
    FOREIGN KEY(herb_id) REFERENCES Herbs(herb_id));
CREATE TABLE Clinical_Symptoms (symptom_id INTEGER PRIMARY KEY, disease_id INTEGER,
    description TEXT, type TEXT, stage TEXT,
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE Complications (complication_id INTEGER PRIMARY KEY, disease_id INTEGER,
    description TEXT, FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE Health_Education (edu_id INTEGER PRIMARY KEY, disease_id INTEGER,
    content TEXT, category TEXT, FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE Non_Drug_Therapies (therapy_id INTEGER PRIMARY KEY, pattern_id INTEGER,
    disease_id INTEGER, type TEXT, details TEXT,
    FOREIGN KEY(pattern_id) REFERENCES TCMPatterns(pattern_id),
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE TCM_General_Info (id INTEGER PRIMARY KEY, disease_id INTEGER,
    tcm_disease_name TEXT, etiology_overview TEXT,
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE Western_Causes (cause_id INTEGER PRIMARY KEY, disease_id INTEGER,
    description TEXT, category TEXT,
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
CREATE TABLE Western_Treatments (treatment_id INTEGER PRIMARY KEY, disease_id INTEGER,
    method_name TEXT, method_type TEXT, description TEXT,
    FOREIGN KEY(disease_id) REFERENCES Diseases(disease_id));
"""


def build(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite fixture: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    # sqlite creates a new file; no input from the research database is read.
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(SCHEMA)
        connection.execute("INSERT INTO Authors VALUES (1, ?, ?)", ("Tác giả Mô phỏng A", "synthetic"))
        connection.execute("INSERT INTO Diseases VALUES (1, ?, ?, ?, ?)",
            ("Bệnh mô phỏng Alpha", "Synthetic Alpha Condition", "Danh xưng giả Alpha", "Invented demonstration record"))
        connection.execute("INSERT INTO Disease_Authors VALUES (1, 1, 1)")
        connection.executemany("INSERT INTO TCMPatterns VALUES (?, 1, ?, NULL, NULL)",
            [(1, "Thể mô phỏng A"), (2, "Thể mô phỏng B")])
        connection.execute("INSERT INTO Prescriptions VALUES (1, 1, ?, NULL)", ("Mã phương án tổng hợp P1",))
        connection.execute("INSERT INTO Herbs VALUES (1, ?, NULL)", ("Mẫu vật tổng hợp H1",))
        connection.execute("INSERT INTO Prescription_Details VALUES (1, 1, 1, NULL)")
        connection.commit()
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0] == 14
    except BaseException:
        connection.close()
        # Do not erase a possibly useful incomplete fixture. A caller can
        # inspect it and explicitly choose a new filename.
        raise
    connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("demo_database.sqlite"))
    args = parser.parse_args()
    build(args.output)
    print(f"Created synthetic fixture: {args.output}")

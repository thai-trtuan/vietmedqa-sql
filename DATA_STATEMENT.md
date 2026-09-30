# Data statement

The SQLite fixture has the same 14 table names as the research schema. Every
row in this artifact was invented for a software demonstration. Names such
as “Bệnh mô phỏng Alpha” are synthetic placeholders; they do not describe a
real diagnosis, treatment, patient, author, herb or prescription.

The original study used a bounded Vietnamese medical source from 2016. Its
book-derived database is not distributed here. The study's original
260-question constructed evaluation, 1,273-record diagnostic corpus and
120-question human-authored robustness suite are not included as item-level data. The
robustness suite involved two question writers outside the system-design team
and source adjudication involving the author. Its questions, reference answers
and raw predictions are not distributed. The published aggregate counts cover
78 DB-supported and 31 source-unsupported questions; seven source-supported
questions outside the frozen DB and four ambiguous questions are auxiliary,
not pooled into those denominators. These counts reproduce arithmetic only,
not the original item-level correctness decisions.

This package does not validate medical correctness or clinical utility.

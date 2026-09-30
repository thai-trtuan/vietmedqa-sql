# VietMedQA-SQL: partial reproducibility artifact

This is a **partial** reproducibility artifact for VietMedQA-SQL. It runs the
deterministic Scope Guard and semantic-override route on a wholly invented
14-table SQLite database. It does not include the full typed-IR/model fallback,
the source-book database, model checkpoints or item-level evaluation records.

The included `aggregate_counts.json` concerns the 120-question human-authored
robustness suite, written by two people outside the system-design team. Of
these, 78 DB-supported questions enter the primary Exact Match calculation
and 31 source-unsupported questions enter the primary safety calculation.
The other 11 are auxiliary: seven are supported by the book but outside the
frozen database, and four are ambiguous. They are not pooled into either
primary denominator. This suite is distinct from the study's original
260-question constructed evaluation and 1,273-record diagnostic corpus.

From this directory, using Python 3.10+ with the standard library and SQLite,
run the demo, aggregate arithmetic replay and tests with one command:

```sh
python3 check_reproducibility.py
```

The command creates its invented database in a temporary directory, prints
machine-readable stage traces, recomputes aggregate rates and runs the tests.
It leaves no generated SQLite file in the repository. The demo shows an
in-scope answer, a count, an out-of-scope refusal and a question requiring the
unreleased fallback; it never returns medical advice. The three `core/`
modules preserve the deterministic research behavior. Their original file
names were simplified for this release, with one internal import adjusted.
The aggregate replay checks arithmetic only: it cannot reconstruct questions,
answers or correctness decisions from the original inference.

## Where to start

| File | Role |
|---|---|
| `check_reproducibility.py` | Runs the demo, count replay and tests in one command. |
| `run_pipeline_demo.py`, `build_demo_database.py` | Demonstrates routing and trace output on invented data. |
| `core/scope_guard_and_semantic_override.py` | Deterministic scope check and high-precision SQL-plan routing. |
| `core/count_route_disambiguation.py` | Count-query interpretation rules extending the deterministic route. |
| `core/output_parsing_and_sql_safety.py` | Answer parsing, normalization and read-only SQL boundary. |
| `aggregate_counts.json`, `recompute_aggregate_metrics.py` | Recalculates arithmetic from aggregate counts for the human-authored robustness suite; does not re-score questions. |
| `test_reproducibility_package.py` | Checks fixture construction, refusal, read-only SQL and aggregate arithmetic. |
| `DATA_STATEMENT.md`, `LICENSE`, `.gitignore` | States data limits and license; excludes generated files from Git. |

The included files are licensed under MIT; see `LICENSE`. This does not license
the source book, its derived database, model weights, private questions,
reference answers or raw predictions, none of which are included. The invented
demo rows do not represent clinical data or medical advice.

## Release boundary

The synthetic table names mirror the research schema, but all fixture rows are
invented. No book-derived row, page text, private question, writer identity,
email address, reference answer, raw model response or model weight is bundled.
No third-party Python package, Qwen checkpoint or MLX runtime is bundled;
their licenses are separate from this package's MIT license.

The CPU-only fixture was tested with Python 3.13.5 and SQLite 3.50.4 in an
isolated local copy. This does not establish a reproducible environment for
the unreleased MLX model branch or clinical validity of any answer.

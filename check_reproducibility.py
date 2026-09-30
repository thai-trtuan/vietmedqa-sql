#!/usr/bin/env python3
"""Run the complete CPU-only partial-artifact check without outside packages."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent


def call(*args: str) -> None:
    subprocess.run([sys.executable, "-B", *args], cwd=HERE, check=True)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="vietmedqa-demo-") as scratch:
        database = str(Path(scratch) / "demo_database.sqlite")
        call("build_demo_database.py", "--output", database)
        call("run_pipeline_demo.py", "--database", database)
    call("recompute_aggregate_metrics.py")
    call("-m", "unittest", "-v", "test_reproducibility_package.py")

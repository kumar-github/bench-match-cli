"""
Bench Match CLI -- run the whole matching pipeline end to end.

Usage:
    python run.py

What it expects:
    Put the source Excel files in one of two places (either works):
      - an "input" subfolder next to this script, or
      - directly next to this script (same folder as run.py)
    Filenames just need to CONTAIN "AFD-Supply" and "Demand" -- the exact
    name (e.g. with a date suffix) doesn't matter.

    AAFD-Supply.xlsx is not used yet -- see the note in classify_inputs.py
    for why (AAFDs are handled once they become AFDs, not proactively).

What it produces:
    output/phase1-matching-shortlist.xlsx -- the same workbook produced
    during the analysis session (grouped by employee, Strong/Good always
    shown, Weak shown only as a fallback when nothing better exists,
    Excluded shown capped at 3 near-misses per employee for transparency,
    plus the Read Me tab and the no-match / data-issue call-outs).

    Intermediate CSVs land in data/ if you want to inspect them.

Requirements: Python 3.9+, pandas, openpyxl (see requirements.txt).
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _run_step(script_name, description):
    print(f"\n{'=' * 60}\n{description}\n{'=' * 60}")
    result = subprocess.run([sys.executable, str(BASE_DIR / script_name)], cwd=str(BASE_DIR))
    if result.returncode != 0:
        print(f"\nStopped: {script_name} failed (see error above).")
        sys.exit(result.returncode)


def main():
    try:
        import pandas  # noqa: F401
        import openpyxl  # noqa: F401
    except ImportError:
        print(
            "Missing dependencies. Run this first:\n"
            "    pip install -r requirements.txt\n"
            "(add --break-system-packages if your Python complains about that)"
        )
        sys.exit(1)

    _run_step("classify_inputs.py", "Step 1/3 — Reading source files and classifying supply + demand")
    _run_step("build_matches.py", "Step 2/3 — Scoring and tiering every candidate pairing")
    _run_step("write_shortlist_workbook.py", "Step 3/3 — Writing the Excel shortlist")

    print(f"\nDone. Open: {BASE_DIR / 'output' / 'phase1-matching-shortlist.xlsx'}")


if __name__ == "__main__":
    main()

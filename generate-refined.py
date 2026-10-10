"""
Standalone, refined-view companion to write_shortlist_workbook.py and
generate-thin.py.

Produces a flat, one-row-per-(employee, demand)-pair view:
  - EVERY Strong and Good match is listed (not just the single best one
    per employee, like generate-thin.py) -- Weak and Excluded rows are
    left out entirely
  - no grouping/merged cells -- an employee's ID/name/location/etc. are
    repeated on every one of their rows, so an employee with 3 Strong
    and 2 Good matches gets 5 full, independent rows
  - includes one extra column vs. generate-thin.py: Bench Ageing days
    (already produced by build_matches.py as 'employee_bench_ageing' --
    nothing new is computed here)
  - employees with neither a Strong nor a Good match are left out of
    this file entirely, same as generate-thin.py (still fully visible
    in the main workbook)
  - the genuinely unclassified supply-side employees (data/unclassified_
    supply.csv) are appended as flagged DATA ISSUE rows at the bottom,
    same category/source/styling convention as write_shortlist_workbook.py

This does NOT touch engine.py, build_matches.py, or classify_inputs.py,
and does not recompute any score or tier -- it only reads data/match_rows
.csv (already produced by build_matches.py) plus the classified CSVs and
data/unclassified_supply.csv, filters/sorts/renders. Run it any time
after run.py (or the individual pipeline steps) has produced
data/match_rows.csv.

Usage:
    python generate-refined.py
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

FONT_NAME = "Arial"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name=FONT_NAME, size=10)
TITLE_FONT = Font(name=FONT_NAME, size=14, bold=True, color="1F4E78")
SUBTITLE_FONT = Font(name=FONT_NAME, size=10, italic=True, color="595959")
STRONG_FILL = PatternFill("solid", fgColor="C6EFCE")
GOOD_FILL = PatternFill("solid", fgColor="FFEB9C")
STRONG_FONT = Font(name=FONT_NAME, size=10, bold=True, color="006100")
GOOD_FONT = Font(name=FONT_NAME, size=10, bold=True, color="9C6500")
DATA_ISSUE_FILL = PatternFill("solid", fgColor="FF7C80")
DATA_ISSUE_FONT = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
EMP_HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
EMP_HEADER_FONT = Font(name=FONT_NAME, size=11, bold=True, color="1F4E78")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

SCORE_FRACTION = {"Strong": 1.0, "Good": 0.75}  # real numbers, displayed via a percent format
TIER_ORDER = {"Strong": 0, "Good": 1}

COLUMNS = [
    ("Demand ID", 13),
    ("Demand Cluster Name", 42),
    ("Demand Location", 15),
    ("Demand Sub Band", 15),
    ("Employee ID", 13),
    ("Employee Name", 26),
    ("Employee Location", 15),
    ("Employee Cluster", 42),
    ("Employee Sub Band", 15),
    ("Bench Ageing days", 16),
    ("Matching Score", 13),
    ("Reasoning (one-line)", 60),
    ("MAS Mapping Check", 30),
    ("Sub-Capability Check", 30),
    ("Additional Request (manual review only)", 50),
]
# Column numbers (1-based) referenced by write_workbook() -- kept as named
# constants so a future column reorder doesn't silently break the styling.
COL_DEMAND_ID = 1
COL_BENCH_AGEING = 10
COL_MATCHING_SCORE = 11
COL_REASONING = 12
COL_MAS_MAPPING = 13
COL_ADDITIONAL_REQUEST = 15


def fmt_num(v):
    if pd.isna(v):
        return ""
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except Exception:
        return v


def build():
    match_path = DATA_DIR / "match_rows.csv"
    unclassified_path = DATA_DIR / "unclassified_supply.csv"
    if not match_path.exists():
        raise FileNotFoundError(
            f"{match_path} not found. Run run.py (or classify_inputs.py + "
            f"build_matches.py) first -- this script only reformats their output."
        )

    df = pd.read_csv(match_path)
    supply = pd.read_csv(DATA_DIR / "phase1_supply_classified.csv")
    demand = pd.read_csv(DATA_DIR / "demand_classified.csv")
    unclassified = pd.read_csv(unclassified_path) if unclassified_path.exists() else pd.DataFrame()

    # Raw literal skill-cluster text, keyed for the join back onto match_rows.
    emp_cluster = supply.set_index("Employee Code")["Skill Cluster"]
    dem_cluster = demand.set_index("Job Requisition ID")["Final Skill Cluster"]

    # Keep only Strong/Good, matching pick_best_row's own pool restriction
    # in generate-thin.py -- Weak and Excluded are dropped entirely here.
    kept = df[df["overall_tier"].isin(["Strong", "Good"])].copy()
    kept["tier_order"] = kept["overall_tier"].map(TIER_ORDER)
    # Same tie-break generate-thin.py uses within a tier: most urgent
    # ageing bucket first, then more balance positions -- applied per row
    # here instead of picking just one.
    kept = kept.sort_values(
        by=["employee_name", "employee_code", "tier_order", "ageing_rank", "balance_positions"],
        ascending=[True, True, True, True, False],
    )

    rows = []
    employees_with_rows = set()
    for _, r in kept.iterrows():
        employees_with_rows.add(r["employee_code"])
        demand_id = r["job_req_id"]
        try:
            demand_id = int(demand_id)
        except (TypeError, ValueError):
            pass
        emp_code = r["employee_code"]
        rows.append(dict(
            demand_id=demand_id,
            demand_cluster=dem_cluster.get(r["job_req_id"], "(not found)"),
            demand_location=r["demand_location"],
            demand_sub_band=r["demand_band"],
            employee_id=int(emp_code) if pd.notna(emp_code) else emp_code,
            employee_name=r["employee_name"],
            employee_location=r["employee_location"],
            employee_cluster=emp_cluster.get(emp_code, "(not found)"),
            employee_sub_band=r["employee_band"],
            bench_ageing=fmt_num(r.get("employee_bench_ageing")),
            tier=r["overall_tier"],
            reasoning=r["one_liner"],
            mas_mapping_note=r.get("mas_mapping_note") if pd.notna(r.get("mas_mapping_note")) else "",
            sub_capability_note=r.get("employee_sub_capability_note") if pd.notna(r.get("employee_sub_capability_note")) else "",
            additional_request=r.get("additional_request") if pd.notna(r.get("additional_request")) else "",
        ))

    out_df = pd.DataFrame(rows)
    total_employees_seen = df["employee_code"].nunique()
    dropped_no_strong_good = total_employees_seen - len(employees_with_rows)

    print(f"Strong/Good pairing rows: {len(out_df)}")
    print(f"Employees with at least one Strong/Good row: {len(employees_with_rows)}")
    print(f"Employees dropped (no Strong/Good at all): {dropped_no_strong_good}")
    if len(out_df):
        print(out_df["tier"].value_counts())
    print(f"Data-issue (unclassified) employees appended at bottom: {len(unclassified)}")

    write_workbook(out_df, unclassified)


def write_data_issue_block(ws, row, emp):
    n_cols = len(COLUMNS)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=n_cols)
    cell = ws.cell(row=row, column=1)
    cell.value = (f"{emp['Employee Name']}  (Emp Code {int(emp['Employee Code'])})  —  "
                  f"Band: {emp['Sub Band']}  |  Location: {emp['Employee Location']}  |  "
                  f"Status: {emp['AFD Status']}  |  Bench ageing: {fmt_num(emp['Bench Ageing days'])} days")
    cell.font = EMP_HEADER_FONT
    cell.fill = EMP_HEADER_FILL
    cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    row += 1

    values = ["DATA ISSUE"] + [""] * (n_cols - 2) + [emp["status"]]
    for c, v in enumerate(values, start=1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.border = BORDER
        if c == 1:
            cell.fill = DATA_ISSUE_FILL
            cell.font = DATA_ISSUE_FONT
            cell.alignment = Alignment(vertical="center", horizontal="center")
        else:
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical="top", wrap_text=(c == n_cols))
    row += 1
    return row


def write_workbook(df, unclassified):
    wb = Workbook()
    ws = wb.active
    ws.title = "Refined Shortlist"

    ws["A1"] = "Phase 1 Matching Shortlist — Refined View"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("One row per employee-demand pair: every Strong and Good match listed individually "
                "(Weak and Excluded are not shown). Employees with neither a Strong nor a Good match "
                "are not listed here -- see the full workbook for those. Unclassified (DATA ISSUE) "
                "employees are flagged at the bottom.")
    ws["A2"].font = SUBTITLE_FONT

    header_row = 4
    for c, (name, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=c, value=name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.freeze_panes = f"A{header_row + 1}"

    row = header_row + 1
    for _, r in df.iterrows():
        tier_fill = STRONG_FILL if r["tier"] == "Strong" else GOOD_FILL
        tier_font = STRONG_FONT if r["tier"] == "Strong" else GOOD_FONT
        values = [
            r["demand_id"], r["demand_cluster"], r["demand_location"], r["demand_sub_band"],
            r["employee_id"], r["employee_name"], r["employee_location"], r["employee_cluster"],
            r["employee_sub_band"], r["bench_ageing"], SCORE_FRACTION[r["tier"]], r["reasoning"],
            r["mas_mapping_note"], r["sub_capability_note"], r["additional_request"],
        ]
        for c, val in enumerate(values, start=1):
            cell = ws.cell(row=row, column=c, value=val)
            cell.font = BODY_FONT
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=(c in (COL_REASONING, COL_ADDITIONAL_REQUEST, len(COLUMNS))))
            if c == COL_DEMAND_ID:  # Demand ID -- a real number, right-aligned like any ID column
                cell.alignment = Alignment(horizontal="right", vertical="top")
            if c == COL_BENCH_AGEING:  # Bench Ageing days -- a real number, right-aligned
                cell.alignment = Alignment(horizontal="right", vertical="top")
            if c == COL_MATCHING_SCORE:  # Matching Score -- real number (1.0 / 0.75), displayed as a percent
                cell.number_format = "0%"
                cell.fill = tier_fill
                cell.font = tier_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            if c == COL_MAS_MAPPING and val:  # MAS Mapping Check -- only ever has a value when flagged
                cell.font = Font(name=FONT_NAME, size=10, bold=True, color="9C6500")
        row += 1

    # Data-issue rows for the unclassified supply-side employees -- flagged
    # per the same agreed fallback behavior as write_shortlist_workbook.py,
    # not silently dropped.
    for _, emp in unclassified.iterrows():
        row = write_data_issue_block(ws, row, emp)

    ws.sheet_view.showGridLines = False

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "phase1-matching-shortlist-refined.xlsx"
    wb.save(str(out_path))
    print(f"Workbook written to {out_path}")


if __name__ == "__main__":
    build()

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

FONT_NAME = 'Arial'
HEADER_FILL = PatternFill('solid', fgColor='1F4E78')
HEADER_FONT = Font(name=FONT_NAME, size=10, bold=True, color='FFFFFF')
TITLE_FONT = Font(name=FONT_NAME, size=14, bold=True, color='1F4E78')
SUBTITLE_FONT = Font(name=FONT_NAME, size=10, italic=True, color='595959')
BODY_FONT = Font(name=FONT_NAME, size=10)
BOLD_FONT = Font(name=FONT_NAME, size=10, bold=True)
EMP_HEADER_FILL = PatternFill('solid', fgColor='D9E1F2')
EMP_HEADER_FONT = Font(name=FONT_NAME, size=11, bold=True, color='1F4E78')

TIER_FILL = {
    'Strong': PatternFill('solid', fgColor='C6EFCE'),
    'Good': PatternFill('solid', fgColor='FFEB9C'),
    'Weak': PatternFill('solid', fgColor='FCE4D6'),
    'Excluded': PatternFill('solid', fgColor='D9D9D9'),
    'DATA ISSUE': PatternFill('solid', fgColor='FF7C80'),
}
TIER_FONT = {
    'Strong': Font(name=FONT_NAME, size=10, bold=True, color='006100'),
    'Good': Font(name=FONT_NAME, size=10, bold=True, color='9C6500'),
    'Weak': Font(name=FONT_NAME, size=10, bold=True, color='974706'),
    'Excluded': Font(name=FONT_NAME, size=10, italic=True, color='7F7F7F'),
    'DATA ISSUE': Font(name=FONT_NAME, size=10, bold=True, color='FFFFFF'),
}
EXCLUDED_ROW_FONT = Font(name=FONT_NAME, size=9, italic=True, color='808080')
THIN = Side(style='thin', color='BFBFBF')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

TIER_ORDER = {'Strong': 0, 'Good': 1, 'Weak': 2, 'Excluded': 3}

COLUMNS = [
    ("Overall Signal", 14),
    ("Employee Band", 12),
    ("Employee Location", 14),
    ("Job Req ID", 11),
    ("Customer", 16),
    ("Project", 20),
    ("Demand Persona / Sub-persona", 24),
    ("Demand Band", 10),
    ("Demand Location", 14),
    ("Balance Positions", 10),
    ("Due Category", 16),
    ("Ageing Bucket", 12),
    ("Skill — summary", 46),
    ("Band — summary", 20),
    ("Location — summary", 16),
    ("Assessment — summary", 24),
    ("Skill — raw detail", 46),
    ("Band — raw detail", 30),
    ("Location — raw detail", 40),
    ("Assessment — raw detail", 28),
    ("Reasoning (one-line)", 60),
    ("MAS Mapping check", 30),
    ("Frontend Anchor check", 40),
    # Added 2026-10-01 — the pairing-level cross-check (build_matches.py's
    # mas_mapping_cross_check): compares the demand's raw MAS Mapping
    # directly against the MATCHED employee's own raw MAS Mapping, a
    # disagreement neither of the two columns above can see since neither
    # looks across the pairing. Check-only, same as its neighbors — never
    # filters/scores.
    ("MAS Mapping cross-check", 40),
    ("Additional Request (manual review only)", 50),
]


def combine_persona(persona, sub):
    if pd.isna(sub) or sub is None or str(sub) == 'nan':
        return persona
    return f"{persona} / {sub}"


def fmt_num(v):
    if pd.isna(v):
        return ""
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except Exception:
        return v


def write_employee_block(ws, row, emp_meta, emp_rows):
    has_strong_or_good = any(r['overall_tier'] in ('Strong', 'Good') for r in emp_rows)
    flag = "  ⚠ NO STRONG/GOOD MATCH IN SCOPE — " if not has_strong_or_good else ""
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(COLUMNS))
    cell = ws.cell(row=row, column=1)
    sc_note = emp_meta.get('employee_sub_capability_note')
    sc_suffix = f"  |  ⚠ Sub-Capability check: {sc_note}" if pd.notna(sc_note) and sc_note else ""
    cell.value = (f"{flag}{emp_meta['employee_name']}  (Emp Code {int(emp_meta['employee_code'])})  —  "
                  f"{combine_persona(emp_meta['employee_persona'], emp_meta['employee_sub_persona'])}"
                  f"  |  Completeness: {emp_meta['employee_completeness']}"
                  f"  |  Band: {emp_meta['employee_band']}"
                  f"  |  Location: {emp_meta['employee_location']} ({emp_meta['employee_primenv']})"
                  f"  |  Status: {emp_meta['employee_afd_status']}"
                  f"  |  Bench ageing: {fmt_num(emp_meta['employee_bench_ageing'])} days"
                  f"{sc_suffix}")
    cell.font = EMP_HEADER_FONT
    cell.fill = PatternFill('solid', fgColor='FFD966') if not has_strong_or_good else EMP_HEADER_FILL
    cell.alignment = Alignment(vertical='center', horizontal='left', indent=1)
    ws.row_dimensions[row].height = 20
    row += 1

    for r in emp_rows:
        tier = r['overall_tier']
        values = [
            tier,
            r['employee_band'],
            r['employee_location'],
            fmt_num(r['job_req_id']),
            r['customer'],
            r['project'],
            combine_persona(r['demand_persona'], r['demand_sub_persona']),
            r['demand_band'],
            r['demand_location'],
            fmt_num(r['balance_positions']),
            r['due_category'],
            r['ageing'],
            r['skill_collapsed'],
            r['band_collapsed'],
            r['loc_collapsed'],
            r['assessment_collapsed'],
            r['skill_expanded'],
            r['band_expanded'],
            r['loc_expanded'],
            r['assessment_expanded'],
            r['one_liner'],
            r.get('mas_mapping_note') or "",
            r.get('frontend_anchor_note') or "",
            r.get('mas_mapping_cross_check_note') or "",
            r.get('additional_request') if pd.notna(r.get('additional_request')) else "",
        ]
        for c, v in enumerate(values, start=1):
            cell = ws.cell(row=row, column=c, value=v)
            cell.border = BORDER
            cell.alignment = Alignment(vertical='top', wrap_text=(c in (13, 17, 18, 19, 21, 25)))
            if c == 1:
                cell.fill = TIER_FILL[tier]
                cell.font = TIER_FONT[tier]
                cell.alignment = Alignment(vertical='center', horizontal='center')
            elif c in (22, 23, 24) and v:  # MAS Mapping check / Frontend Anchor check / MAS Mapping cross-check — only have a value when flagged
                cell.font = Font(name=FONT_NAME, size=10, bold=True, color='9C6500')
            else:
                cell.font = EXCLUDED_ROW_FONT if tier == 'Excluded' else BODY_FONT
        row += 1
    return row


def write_data_issue_block(ws, row, emp):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(COLUMNS))
    cell = ws.cell(row=row, column=1)
    cell.value = (f"{emp['Employee Name']}  (Emp Code {int(emp['Employee Code'])})  —  "
                  f"Band: {emp['Sub Band']}  |  Location: {emp['Employee Location']}  |  "
                  f"Status: {emp['AFD Status']}  |  Bench ageing: {fmt_num(emp['Bench Ageing days'])} days")
    cell.font = EMP_HEADER_FONT
    cell.fill = EMP_HEADER_FILL
    cell.alignment = Alignment(vertical='center', horizontal='left', indent=1)
    row += 1

    values = ["DATA ISSUE"] + [""] * (len(COLUMNS) - 2) + [emp['status']]
    for c, v in enumerate(values, start=1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.border = BORDER
        if c == 1:
            cell.fill = TIER_FILL['DATA ISSUE']
            cell.font = TIER_FONT['DATA ISSUE']
            cell.alignment = Alignment(vertical='center', horizontal='center')
        else:
            cell.font = BODY_FONT
            cell.alignment = Alignment(vertical='top', wrap_text=(c == len(COLUMNS)))
    row += 1
    return row


def build():
    df = pd.read_csv('data/match_rows.csv')
    unclassified = pd.read_csv('data/unclassified_supply.csv')

    wb = Workbook()
    ws = wb.active
    ws.title = "Phase 1 Shortlist"

    ws.merge_cells('A1:E1')
    ws['A1'] = "Demand & Supply Mapping — Phase 1 Matching Engine Output"
    ws['A1'].font = TITLE_FONT
    ws.merge_cells('A2:S2')
    ws['A2'] = ("Scope: 243 Phase 1 bench employees (Fullstack Java / Fullstack .NET / Frontend) vs. classified demand. "
                "Grouped by employee; within each employee, rows are sorted Strong > Good > Weak > Excluded (see 'Read Me' tab for methodology, "
                "the row-cap applied per employee, and open/unconfirmed items).")
    ws['A2'].font = SUBTITLE_FONT

    header_row = 4
    for c, (name, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=c, value=name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical='center', horizontal='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.freeze_panes = f"A{header_row + 1}"
    ws.row_dimensions[header_row].height = 30

    row = header_row + 1
    emp_meta_cols = ['employee_code', 'employee_name', 'employee_persona', 'employee_sub_persona',
                      'employee_completeness', 'employee_band', 'employee_location', 'employee_primenv',
                      'employee_afd_status', 'employee_bench_ageing', 'employee_sub_capability_note']

    ordered_emp_codes = df[['employee_code', 'employee_name']].drop_duplicates().sort_values('employee_name')['employee_code'].tolist()

    for emp_code in ordered_emp_codes:
        emp_df = df[df['employee_code'] == emp_code].copy()
        emp_df['tier_order'] = emp_df['overall_tier'].map(TIER_ORDER)
        emp_df = emp_df.sort_values(['tier_order', 'ageing_rank', 'job_req_id'])
        emp_meta = emp_df.iloc[0][emp_meta_cols]
        emp_rows = emp_df.to_dict('records')
        row = write_employee_block(ws, row, emp_meta, emp_rows)

    # Data-issue rows for the 4 supply-side unclassified employees — flagged
    # per the agreed fallback behavior (urgent HR-data-fix), not silently dropped.
    for _, emp in unclassified.iterrows():
        row = write_data_issue_block(ws, row, emp)

    ws.sheet_view.showGridLines = False

    # -------------------- Read Me / Methodology sheet ----------------------
    rm = wb.create_sheet("Read Me")
    rm.column_dimensions['A'].width = 100
    r = 1
    def add(text, font=BODY_FONT, gap=0):
        nonlocal r
        rm.cell(row=r, column=1, value=text).font = font
        rm.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical='top')
        r += 1 + gap

    add("Demand & Supply Mapping — Phase 1 Matching Engine: Methodology & Coverage Notes", TITLE_FONT, gap=1)
    add("Scope", BOLD_FONT)
    add("243 Phase 1 bench employees (Capability = MAS, Band E1-E3, proposable AFD status, "
        "MAS Mapping in Full Stack/Front End). 239 of the 243 classified cleanly into a Phase 1 persona "
        "(Fullstack Java / Fullstack .NET / Frontend); the remaining 4 are flagged as DATA ISSUE rows at the "
        "bottom of the Phase 1 Shortlist tab (2 legacy .NET desktop profiles parked out of scope, 1 out-of-scope "
        "NFT/performance-testing profile, 1 employee with no Skill Cluster on file at all — the last is the most "
        "urgent since it hides an otherwise real, potentially deployable person from every shortlist).", gap=1)

    add("Candidate scoping — two corrections made mid-build", BOLD_FONT)
    add("(1) Originally scoped as: same broad persona family (Java-with-Java, .NET-with-.NET, Frontend-with-Frontend "
        "across sub-personas) plus the cross-persona-discount case. In practice this produced 89,742 rows, because "
        "Java and .NET have no sub-persona to narrow by — nearly every Java employee is technically a candidate for "
        "nearly every Java demand row.")
    add("(2) A first per-employee row cap (all Strong + top 20 Good + top 15 Weak + 3 closest Excluded) brought this "
        "down to 8,118 rows, but was still too much to scan. On review, Strong and Good were recognised as both being "
        "\"propose freely\" tiers — an employee can legitimately be proposed to several demands in parallel, so Good "
        "should never be hidden just because Strong exists. Weak, by contrast, is a genuine fallback (\"nothing "
        "better, so consider this\"), not an additional option alongside Strong/Good. Final rule: keep ALL Strong "
        "rows; keep only the top 3 Good rows per employee (by demand urgency); show Weak rows ONLY for an employee "
        "with zero Strong and zero Good matches (capped at 10 in that case); keep the 3 closest near-miss Excluded "
        "rows per employee regardless (a different signal — a band-just-missed case worth an override conversation "
        "— not a volume-of-options signal). Final output: 2,472 rows across 239 employees (~10 rows/employee). "
        "Genuinely unrelated pairings never generated a row at all.", gap=1)

    add("16 employees have zero Strong and zero Good match in the current demand book", BOLD_FONT)
    add("Flagged with a ⚠ NO STRONG/GOOD MATCH IN SCOPE banner (amber) in the main sheet. Most of these are "
        "Frontend/mobile specialists (e.g. iOS) where the standalone demand pool is thin relative to the supply "
        "pool — a business-relevant finding already noted in the main requirements write-up, not a modeling defect. "
        "A few show only near-miss Excluded rows (band one level below the only demands that exist for their "
        "skillset) with no Weak fallback available either — genuinely nothing to propose them to right now under "
        "the current rules.", gap=1)

    add("Overall Signal tiers", BOLD_FONT)
    add("Strong — same persona (and sub-persona, for Frontend), band exact, same city, and no skill gap above "
        "Minor severity (a Minor accessory gap — e.g. Docker, Redis, Python — is noted but never caps the tier).")
    add("Good — persona match but exactly one thing discounted: one band above the ask, a different city, or an "
        "Important-severity accessory gap (e.g. Microservices, Cloud, DevOps, Kafka named by the demand but not "
        "confirmed on the employee's profile).")
    add("Weak — a Critical-severity gap (the demand's actual framework — Spring Boot / Web API-MVC-Entity "
        "Framework / React or Angular itself — isn't confirmed on the employee's side, even though the base "
        "language/persona matches), a cross-persona discount (Java/.NET employee with a named frontend/mobile "
        "accessory skill, matched against that framework's own demand), a weak Node.js-only MERN signal, OR a "
        "persona match with two or more ordinary things discounted at once (band one-above AND a different city, "
        "etc.).")
    add("Excluded — band two-or-more levels off (either direction) or wrong sub-persona (e.g. an Angular-only "
        "employee against a React-only demand). Shown greyed out, capped to the 3 closest near-misses per employee, "
        "for transparency — never blended into the ranked list at a discount.", gap=1)

    add("Skill-gap severity (Critical / Important / Minor)", BOLD_FONT)
    add("Every gap between what a demand names and what the employee's own profile confirms — the real framework "
        "itself, or any other named accessory (Microservices, Cloud, DevOps, Kafka, Docker, Hibernate, Web "
        "Services, Redis, GraphQL, Python) — is weighted rather than treated as one flat discount. Critical "
        "(the framework only) caps the pair at Weak; Important caps at Good; Minor is informational only and "
        "never caps the tier, so Strong is still reachable. When a pair has more than one gap, the WORST severity "
        "decides the cap; the Skill — summary/raw detail columns list every gap found, not just the worst one. "
        "This is v1 of the weighting — the Critical/Important/Minor assignment is a deliberate, explicitly "
        "correctable first pass agreed with the business owner, not a final calibration.", gap=1)

    add("Skill-completeness gradient (tiebreaker only, supply side)", BOLD_FONT)
    add("Core only / Core + Partial / Core + Rich — how much beyond the implied minimum an employee's own Skill "
        "Cluster confirms (e.g. 'Java, SQL' = Core only; 'Java, Spring Boot, REST, Microservices' = Core + Rich). "
        "This never changes the Strong/Good/Weak tier — it only breaks ties among same-persona candidates, folded "
        "into the Skill — summary wording.", gap=1)

    add("Recent design fixes applied to this build", BOLD_FONT)
    add("Cross-persona matching (a Java/.NET employee's named frontend accessory being used to propose them "
        "against a standalone Frontend demand) has been removed entirely — a single named accessory never "
        "verified the rest of a real frontend stack, and it contributed zero rows to real output. "
        "REST/RESTful API is no longer tracked as a separate named accessory on either side — knowing "
        "Spring/Spring Boot already implies it, so it can no longer cause a false 'named accessory gap'. "
        "The demand sheet's MAS Mapping column is checked (not used to filter/match) against the engine-derived "
        "persona — a mismatch is shown in the 'MAS Mapping check' column as a reviewer flag, not a gate. "
        "A second, pairing-level cross-check compares the demand's raw MAS Mapping directly against the "
        "MATCHED employee's own raw MAS Mapping — two independently filled-in source labels that can disagree "
        "with each other even when each individually agrees with its own side's derived persona — shown in the "
        "'MAS Mapping cross-check' column, same non-filtering reviewer-flag role as the other two checks. "
        "Additional Request is surfaced verbatim in its own column for manual review only — never parsed "
        "or scored by the engine. Supply-side and demand-side named accessories now resolve through one shared "
        "canonical registry (AWS/Azure/GCP/Cloud all collapse to a single 'Cloud' accessory on both sides), fixing "
        "a false 'named accessory gap' that could previously show against a real cloud-experienced employee. "
        "And — the fix this build adds — every skill gap (the framework itself, and every named accessory) is now "
        "weighted Critical/Important/Minor instead of getting one flat discount regardless of how load-bearing "
        "the missing piece actually is; see 'Skill-gap severity' above. A supply-side Sub Band outside the defined "
        "E1.1-E3.2 ladder (E0.x, E2.3, or anything else) is now a visible DATA ISSUE row rather than being either "
        "silently dropped (E0, previously filtered out before classification ever ran) or shown as an unmarked "
        "ambiguous match (E2.3 and similar). And Sub-Capability is now checked against the engine-derived persona "
        "as a reviewer flag on the employee header line, the same non-filtering role MAS Mapping's own check "
        "plays — checked directly against real data first: using it as a scoping filter instead would have "
        "dropped 17 genuine Full Stack/Front End employees whose Sub-Capability tag is stale or differently "
        "scoped (most often 'Polyglot') while their actual skills and MAS Mapping both agree with each other, so "
        "it's informational only, never a gate. And — the demand-side counterpart to the E0/E2.3 fix — a demand "
        "row whose Sub Band falls outside the E1.1-E3.2 ladder ('T0', 'E4+'/'E5.x'/'E6.x' in the real source file) "
        "is now excluded from matching entirely instead of staying in the candidate pool: previously it scored "
        "quality='unresolved' against every employee paired with it, which overall_tier() treated as an ordinary "
        "single discount (same bucket as one-band-above or a different city) — meaning a demand whose real band "
        "position isn't even known could still surface as a Good or Weak proposal with no visible warning beyond "
        "buried detail text. Counted out separately in 'Demand classification coverage' below, distinguishable "
        "from ordinary scope leakage.", gap=1)

    add("Classification approach", BOLD_FONT)
    add("Supply's Skill Cluster is a closed, curated ~28-value set for Phase 1 — classified via an exact-match "
        "lookup table (28 known values). Demand's Final Skill Cluster is open free text (192 distinct phrases) — "
        "classified via a token/rule parser implementing the anchor/accessory/persona rules (framework implies "
        "language, named-vs-unnamed accessory tiers, anchor precedence, the three sanity-check corrections). Both "
        "sides resolve to the same shared persona label before matching — never compared as raw text. No fuzzy "
        "matching: an unrecognized value is excluded and logged, never guessed.", gap=1)

    add("Demand classification coverage", BOLD_FONT)
    dclass = pd.read_csv('data/demand_classified.csv')
    total_pos = dclass['Balance Positions'].sum()
    unclass_pos = dclass[dclass['persona'].isna()]['Balance Positions'].sum()
    bad_band_pos = dclass[dclass['status'].astype(str).str.startswith('DATA ISSUE — Demand Sub Band')]['Balance Positions'].sum()
    add(f"{total_pos - unclass_pos:.0f} of {total_pos:.0f} open positions (~{100*(total_pos-unclass_pos)/total_pos:.1f}%) "
        f"classified into a Phase 1 persona. The remaining {unclass_pos:.0f} positions are scope leakage (Testing/"
        f"Integration/Mainframe/TPM tooling sitting in a file nominally pre-scoped to Full Stack/Front End), legacy "
        f".NET desktop work (parked), genuinely unrecognized phrasings, or ({bad_band_pos:.0f} of them) a Demand Sub "
        f"Band outside the supported E1.1-E3.2 ladder (Task #14 — 'T0', 'E4+'/'E5.x'/'E6.x' and similar) — none of "
        f"these were force-fit; they simply generate no shortlist rows for any employee.", gap=1)

    add("Known limitations / not yet resolved (see main requirements write-up for full detail)", BOLD_FONT)
    for item in [
        "Pan India = Yes (~378 of 965 demand rows) may mean no location constraint at all for that demand — unconfirmed, so location is still scored same-city/different-city as usual, with a note added where it applies.",
        "WFH-for-strong-skill hunch — unverified, not modeled.",
        "Band-vs-location discount sizing (is one band above worse than a different city?) — both currently collapse to one 'discount' each in the Good tier; the relative weighting is unverified.",
        "RESOLVED — E0/E2.3 (supply) and T0/E4+/E5.x/E6.x (demand), and any other Sub Band outside the E1.1-E3.2 ladder on either side: now excluded from matching and flagged as a data-quality issue (see 'Recent design fixes' above) rather than silently dropped, shown as an unmarked ambiguous match, or — on the demand side, the worse bug — surfacing as a misleadingly scored Good/Weak proposal against an unknown real band position.",
        "Skill Cluster Persona field reliability — not used in this pass; classification was driven off Skill Cluster (supply) and Final Skill Cluster (demand) directly. Capability/Sub-Capability were checked as an alternative and are not more reliable than MAS Mapping/Skill Cluster for identifying persona (MAS Mapping agrees with the engine's own derived persona 97% of the time vs. Sub-Capability's 84%); Sub-Capability is used only as a non-filtering reviewer flag, see above.",
        "Must-have/Nice-to-have tagging still isn't captured per-demand in the source data — the Critical/"
        "Important/Minor severity weighting is a persona-level proxy for it (e.g. Spring Boot is always Critical "
        "for Fullstack Java), not a per-requisition importance signal. If the demand team ever adds a real "
        "must-have flag, that should take priority over this weighting for the specific demand it's set on.",
    ]:
        add(f"  •  {item}")

    from pathlib import Path
    out_dir = Path(__file__).resolve().parent / 'output'
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / 'phase1-matching-shortlist.xlsx'
    wb.save(str(out_path))
    print(f"Workbook written to {out_path}")
    print("Saved.")


if __name__ == '__main__':
    build()

"""
Build the Phase 1 matching engine output: one flat set of
employee x demand pairing rows with Strong/Good/Weak/Excluded tiers.

Scope, per the confirmed approach:
  - Only the 243 Phase 1 supply employees.
  - For each employee, candidate demands are limited to demands in the
    SAME broad persona family only (Java-with-Java, .NET-with-.NET,
    Frontend-with-Frontend across sub-personas). Cross-persona matching
    (a Java/.NET employee's named frontend/mobile accessory being used to
    propose them against a standalone Frontend demand) has been removed
    from the design entirely — a single named accessory never verified
    the rest of a real frontend stack, and it contributed zero rows to
    real output.
  - Within that relevant set, ALL tiers are shown (Strong/Good/Weak, and
    hard-excluded-but-close such as wrong sub-persona or band 2+ off),
    with excluded rows greyed out for transparency.
  - Genuinely unrelated pairings generate no row at all.
"""
import ast
import pandas as pd
from engine import band_index, location_tier, normalize_city, COMPLETENESS_RANK, accessory_severity, _SEVERITY_RANK

RATING_RANK = {
    'Expert': 6, 'Proficient': 5, 'Competent': 4, 'Advanced Beginner': 3,
    'Beginner': 2, 'Entry': 1, '0': 0, '0% Score': 0,
}
RATING_DISPLAY = {
    '0': 'Not yet assessed', '0% Score': 'Not yet assessed',
}

AGEING_RANK = {
    'Overdue Till Aug\'26': 0, 'Due in Sep\'26': 1, 'Future Due in Oct\'26': 2,
    'Future Due in Nov\'26': 3, 'Future Due in Dec\'26': 4,
    'Future Due in Jan\'27': 5, 'Beyond JAS\'26': 6,
}

# React/MERN are treated as one frontend-web equivalence class (MERN's
# frontend half is React, per the anchor-table build). Angular/MEAN are
# their own equivalence class for the same reason (MEAN's frontend half
# is Angular) — kept separate from React/MERN since the two ecosystems
# aren't interchangeable.
FRONTEND_EQUIV = {
    'React': {'React', 'MERN'},
    'MERN': {'React', 'MERN'},
    'Angular': {'Angular', 'MEAN'},
    'MEAN': {'Angular', 'MEAN'},
    'iOS': {'iOS'},
    'Android': {'Android'},
}
FRAMEWORK_UNCONFIRMED = 'Core web (framework unconfirmed)'


def parse_listcol(x):
    if isinstance(x, list):
        return x
    if pd.isna(x) or x == '':
        return []
    try:
        v = ast.literal_eval(x)
        return v if isinstance(v, list) else [x]
    except Exception:
        return [x]


def band_signal(emp_sub_band, dem_sub_band):
    ei = band_index(emp_sub_band)
    di = band_index(dem_sub_band)
    if ei is None or di is None:
        return dict(quality='unresolved', hard_exclude=False,
                     collapsed="Band ladder position unclear",
                     expanded=f"Employee {emp_sub_band} vs demand {dem_sub_band} — outside the "
                              f"defined E1.1-E3.2 ladder (parked item, needs manual check)")
    diff = ei - di
    if diff < 0:
        return dict(quality='below', hard_exclude=True,
                     collapsed="Below the ask — excluded",
                     expanded=f"Employee {emp_sub_band} is below demand's {dem_sub_band} — hard exclude")
    if diff >= 2:
        return dict(quality='too_senior', hard_exclude=True,
                     collapsed="Two+ levels above — excluded",
                     expanded=f"Employee {emp_sub_band} is {diff} levels above demand's {dem_sub_band} — hard exclude")
    if diff == 1:
        return dict(quality='one_above', hard_exclude=False,
                     collapsed="One band above the ask",
                     expanded=f"Employee {emp_sub_band} vs demand {dem_sub_band} (one level above)")
    return dict(quality='exact', hard_exclude=False,
                collapsed="Exact band match",
                expanded=f"Employee {emp_sub_band} = demand {dem_sub_band} (exact)")


def location_signal(emp_city, dem_city, pan_india):
    ec = normalize_city(emp_city)
    dc = normalize_city(dem_city)
    same = (ec is not None and dc is not None and ec == dc)
    note = " (Pan India = Yes flagged on this demand — may mean no location constraint; unconfirmed)" if pan_india == 'Yes' else ""
    if same:
        return dict(quality='same_city', collapsed="Same city",
                     expanded=f"Employee in {ec} ({location_tier(ec)}); demand in {dc} ({location_tier(dc)}) — same city{note}")
    return dict(quality='diff_city', collapsed="Different city",
                expanded=f"Employee in {ec} ({location_tier(ec)}); demand in {dc} ({location_tier(dc)}) — different city, still viable{note}")


def assessment_signal(rating, score):
    r = str(rating)
    disp = RATING_DISPLAY.get(r, r)
    rank = RATING_RANK.get(r, 0)
    collapsed = disp if r in RATING_DISPLAY else f"{disp}"
    qualifier = {6: 'Excellent', 5: 'Strong', 4: 'Moderate', 3: 'Moderate', 2: 'Light', 1: 'Light', 0: ''}[rank]
    if r in RATING_DISPLAY:
        collapsed_line = "Not yet assessed"
    else:
        collapsed_line = f"{disp} — {qualifier}" if qualifier else disp
    return dict(rank=rank, collapsed=collapsed_line,
                expanded=f"Rating: {disp}; raw score: {score:.3f}" if not r in RATING_DISPLAY else f"No usable score/rating on file (score={score:.3f})")


def _framework_confirmed(row):
    """framework_confirmed is only set on Fullstack Java/.NET rows (Java:
    Spring Boot; .NET: Web API/MVC/Entity Framework). Missing/NaN means
    "not applicable to this persona" and must NOT be treated as a penalty
    — only an explicit False (framework genuinely absent from the literal
    skill text) counts."""
    v = row.get('framework_confirmed')
    if pd.isna(v):
        return True
    return bool(v)


def skill_signal(emp, dem):
    """emp, dem are Series (a supply row and a demand row), both already
    persona-classified. Returns dict with quality/hard_exclude/collapsed/expanded."""
    e_persona, e_sub = emp['persona'], emp.get('sub_persona')
    d_persona, d_sub = dem['persona'], dem.get('sub_persona')
    e_completeness = emp.get('completeness')
    e_access = parse_listcol(emp.get('named_accessories'))
    d_access = parse_listcol(dem.get('named_accessories'))

    # --- Same broad family: Java-Java or .NET-.NET ------------------------
    if e_persona in ('Fullstack Java', 'Fullstack .NET') and d_persona == e_persona:
        # Task #8 (skill-weighting): every gap between what the demand asks
        # for and what the employee's literal skill text confirms — the real
        # framework AND every named accessory — is collected here and
        # resolved through ONE severity table (engine.ACCESSORY_WEIGHT)
        # instead of two separate mechanisms (a framework-only special case,
        # and a flat "any named accessory gap caps at Good" rule that didn't
        # distinguish Spring Boot from Redis). Worst severity found wins.
        gaps = []  # list of (accessory_name, severity)

        # The demand explicitly names the real framework (Spring Boot for
        # Java; Web API/MVC/Entity Framework for .NET) but the employee's
        # literal skill text never confirms it (e.g. "Java, SQL" vs a
        # "Java, Spring Boot" demand) — persona match alone is NOT enough.
        # This started as Task #6's own special case; it's now just the one
        # entry in the severity table tagged "Framework" (Critical).
        if _framework_confirmed(dem) and not _framework_confirmed(emp):
            fw_name = "Spring Boot" if e_persona == "Fullstack Java" else "Web API / MVC / Entity Framework"
            gaps.append((fw_name, accessory_severity("Framework", persona=e_persona)))

        if d_access:
            have = set(a.lower() for a in e_access)
            missing = [a for a in d_access if a.lower() not in have]
            for m in missing:
                gaps.append((m, accessory_severity(m, persona=e_persona)))

        comp_note = {
            'Core only': 'core skills confirmed, thinner profile',
            'Core + Partial': 'core plus some named extras — solid profile',
            'Core + Rich': 'core plus several named extras — well-rounded profile',
        }.get(e_completeness, 'profile detail unavailable')

        if not gaps:
            return dict(quality='core', hard_exclude=False,
                        collapsed=f"Persona match ({e_persona}) — {comp_note}",
                        expanded=f"Employee: {e_persona}, completeness={e_completeness}, named accessories={e_access or 'none'}. "
                                 f"Demand: {d_persona}, named accessories asked={d_access or 'none'}.")

        worst_name, worst_severity = max(gaps, key=lambda g: _SEVERITY_RANK[g[1]])
        gap_list = ", ".join(f"{name} ({sev})" for name, sev in gaps)
        quality = {
            "Critical": "accessory_gap_critical",
            "Important": "accessory_gap_important",
            "Minor": "accessory_gap_minor",
        }[worst_severity]
        tier_word = {"Critical": "Weak", "Important": "capped at Good", "Minor": "no cap"}[worst_severity]
        collapsed = f"Persona match ({e_persona}) — {comp_note}; gap: {gap_list} — {tier_word}"
        return dict(quality=quality, hard_exclude=False,
                    collapsed=collapsed,
                    expanded=f"Employee: {e_persona}, completeness={e_completeness}, named accessories={e_access or 'none'}, "
                             f"framework_confirmed={_framework_confirmed(emp)}. Demand: {d_persona}, named accessories "
                             f"asked={d_access or 'none'}, framework_confirmed={_framework_confirmed(dem)}. "
                             f"Missing/gap items with severity: {gap_list}. Worst severity ({worst_severity}) decides the tier cap "
                             f"(Task #8 skill-weighting, v1 — weights are correctable).")

    # --- Frontend-Frontend: sub-persona compatibility ----------------------
    if e_persona == 'Frontend' and d_persona == 'Frontend':
        if 'dual-acceptable' in str(d_sub):
            # Demand accepts React OR Angular — MERN's frontend half is React
            # and MEAN's is Angular (FRONTEND_EQUIV above), so both qualify
            # here too; this used to list only ('React', 'Angular', 'MERN'),
            # missing MEAN (added in Task #5, after this branch was written)
            # — a real MEAN candidate would have hard-excluded here instead
            # of matching, even though a dual-acceptable demand is exactly
            # the kind of demand MEAN's Angular half should qualify for.
            if e_sub in ('React', 'Angular', 'MERN', 'MEAN'):
                return dict(quality='core', hard_exclude=False,
                            collapsed=f"Persona match — Frontend/{e_sub}, demand is dual-acceptable (React/Angular)",
                            expanded=f"Employee sub-persona: {e_sub}. Demand accepts either React or Angular (dual-acceptable, tagged exception).")
            if e_sub == FRAMEWORK_UNCONFIRMED:
                return dict(quality='framework_unconfirmed', hard_exclude=False,
                            collapsed="Weak — framework unconfirmed on employee side, matched at discount against a dual-acceptable demand",
                            expanded="Employee: HTML/CSS/JS with no framework named. Demand accepts React or Angular. Matched at discount.")
            return dict(quality='wrong_subpersona', hard_exclude=True,
                        collapsed=f"Wrong sub-persona — employee is {e_sub}, demand is dual-acceptable React/Angular but employee's specialty ({e_sub}) doesn't apply",
                        expanded=f"Employee sub-persona {e_sub} vs demand's dual-acceptable React/Angular — not a fit (e.g. iOS/Android vs web frameworks).")

        if e_sub == FRAMEWORK_UNCONFIRMED or d_sub == FRAMEWORK_UNCONFIRMED:
            if e_sub == d_sub:
                return dict(quality='framework_unconfirmed', hard_exclude=False,
                            collapsed="Weak — framework unconfirmed on both sides",
                            expanded="Both employee and demand only name HTML/CSS/JS core web skills with no framework specified.")
            other_sub = d_sub if e_sub == FRAMEWORK_UNCONFIRMED else e_sub
            # Same MEAN gap as the dual-acceptable branch above — MEAN's
            # frontend half is Angular, so it belongs in this list too.
            if other_sub in ('React', 'Angular', 'MERN', 'MEAN'):
                return dict(quality='framework_unconfirmed', hard_exclude=False,
                            collapsed=f"Weak — framework unconfirmed side matched at discount against {other_sub}",
                            expanded=f"One side is core-web/framework-unconfirmed, other side is {other_sub}. Matched at discount, not a confirmed specialist match.")
            return dict(quality='wrong_subpersona', hard_exclude=True,
                        collapsed="Wrong sub-persona", expanded=f"{e_sub} vs {d_sub} — not compatible.")

        if d_sub == 'MERN' and 'weak' in str(dem.get('status', '')).lower():
            # Node.js-only weak MERN demand. Lower-confidence addition than
            # the two MEAN fixes above: MEAN's backend is also Node.js, so
            # it's included for the same reason MERN/React are, but this
            # demand names no UI framework at all — worth a second look if
            # a real case ever shows up, rather than treating it as settled.
            if e_sub in ('MERN', 'React', 'MEAN'):
                return dict(quality='weak_node', hard_exclude=False,
                            collapsed=f"Weak — demand only names Node.js (incomplete MERN signal); employee is {e_sub}",
                            expanded="Demand names only the Node.js backend runtime, no UI framework — a weak/incomplete MERN signal.")
            return dict(quality='wrong_subpersona', hard_exclude=True,
                        collapsed="Wrong sub-persona", expanded=f"{e_sub} vs weak-MERN(Node.js only) demand.")

        e_equiv = FRONTEND_EQUIV.get(e_sub, {e_sub})
        if d_sub in e_equiv or e_sub == d_sub:
            comp_note = {
                'Core only': 'core skills confirmed, thinner profile',
                'Core + Partial': 'core plus some named extras — solid profile',
                'Core + Rich': 'core plus several named extras — well-rounded profile',
            }.get(e_completeness, 'profile detail unavailable')
            return dict(quality='core', hard_exclude=False,
                        collapsed=f"Persona match — Frontend/{e_sub} vs Frontend/{d_sub} — {comp_note}",
                        expanded=f"Employee: Frontend/{e_sub} (completeness={e_completeness}). Demand: Frontend/{d_sub}.")
        return dict(quality='wrong_subpersona', hard_exclude=True,
                    collapsed=f"Wrong sub-persona — employee is {e_sub}, demand needs {d_sub}",
                    expanded=f"Employee sub-persona {e_sub} does not satisfy demand sub-persona {d_sub} — the exact false-positive the sub-persona split guards against.")

    return dict(quality='no_relation', hard_exclude=True, collapsed="Not relevant", expanded="")


def overall_tier(skill, band, loc):
    if skill['hard_exclude'] or band['hard_exclude']:
        return 'Excluded'
    sq = skill['quality']
    discounts = 0
    if band['quality'] == 'one_above':
        discounts += 1
    if loc['quality'] == 'diff_city':
        discounts += 1
    if band['quality'] == 'unresolved':
        discounts += 1

    # Critical-severity gaps: Frontend's pre-existing framework-unconfirmed
    # bucket (quality tag kept as-is — its own sub-persona logic already
    # resolves it) and weak_node both count as the Critical case under
    # Task #8's severity table, same as Java/.NET's accessory_gap_critical.
    if sq in ('framework_unconfirmed', 'weak_node', 'accessory_gap_critical'):
        return 'Weak'
    if sq == 'accessory_gap_important':
        return 'Good' if discounts <= 1 else 'Weak'
    # Minor-severity gaps are informational only (Task #8) — no cap beyond
    # the ordinary band/location discounts, same ladder as a clean 'core'.
    if sq in ('core', 'accessory_gap_minor'):
        if discounts == 0:
            return 'Strong'
        if discounts == 1:
            return 'Good'
        return 'Weak'
    return 'Weak'


def build_candidate_demands(emp, demand_df):
    """Returns the subset of demand rows relevant to this employee: same
    broad persona family only (Java-with-Java, .NET-with-.NET, Frontend
    across sub-personas). Cross-persona matching has been removed from
    the design entirely — a Java/.NET employee's named frontend accessory
    is no longer used to propose them against a standalone Frontend demand."""
    e_persona = emp['persona']
    if pd.isna(e_persona) or e_persona is None:
        return demand_df.iloc[0:0]

    if e_persona in ('Fullstack Java', 'Fullstack .NET'):
        return demand_df[demand_df['persona'] == e_persona]

    if e_persona == 'Frontend':
        return demand_df[demand_df['persona'] == 'Frontend']

    return demand_df.iloc[0:0]


MAX_GOOD_PER_EMPLOYEE = 3
MAX_WEAK_FALLBACK_PER_EMPLOYEE = 10
MAX_EXCLUDED_PER_EMPLOYEE = 3


def cap_employee_rows(emp_rows):
    """Per-employee row cap (confirmed with the user, revised from the
    first pass): Strong and Good are both "propose freely" tiers — an
    employee can legitimately be proposed to several demands in parallel,
    so Good is never hidden just because Strong exists. Weak is a genuine
    fallback tier ("nothing better, so consider this"), not an additional
    option alongside Strong/Good — so it's only shown when an employee has
    NEITHER a Strong NOR a Good match at all.

    - All Strong rows kept (rare, most decision-relevant).
    - Top MAX_GOOD_PER_EMPLOYEE Good rows kept, by demand urgency.
    - Weak rows shown ONLY when Strong count == 0 and Good count == 0
      (uncapped counts, before any truncation), capped at
      MAX_WEAK_FALLBACK_PER_EMPLOYEE in that case.
    - Excluded rows: only the closest MAX_EXCLUDED_PER_EMPLOYEE near-misses
      (skill otherwise viable but band hard-excluded, ranked above a
      wrong-sub-persona miss) — shown regardless of tier availability,
      since this is a different signal (a near-miss worth an override
      conversation), not a volume-of-options signal.
    """
    strong = [r for r in emp_rows if r['overall_tier'] == 'Strong']
    good = [r for r in emp_rows if r['overall_tier'] == 'Good']
    weak = [r for r in emp_rows if r['overall_tier'] == 'Weak']
    excluded = [r for r in emp_rows if r['overall_tier'] == 'Excluded']

    good_sorted = sorted(good, key=lambda r: (r['ageing_rank'], -r['balance_positions']))
    good_kept = good_sorted[:MAX_GOOD_PER_EMPLOYEE]

    if len(strong) == 0 and len(good) == 0:
        weak_sorted = sorted(weak, key=lambda r: (r['ageing_rank'], -r['balance_positions']))
        weak_kept = weak_sorted[:MAX_WEAK_FALLBACK_PER_EMPLOYEE]
    else:
        weak_kept = []

    def miss_distance(r):
        # A Java/.NET persona match with an accessory/framework gap is still
        # a band-only miss here (skill itself never hard-excludes in that
        # branch) — ranks closer than a genuine wrong-subpersona miss, same
        # as a clean 'core' skill match. 'core_gap' was the old, single
        # flat-discount quality tag (pre-Task #8); accessory_gap_critical/
        # important/minor are its three severity-split replacements.
        return 1 if r['skill_quality'] in (
            'core', 'accessory_gap_critical', 'accessory_gap_important', 'accessory_gap_minor'
        ) else 2
    excluded_sorted = sorted(excluded, key=lambda r: (miss_distance(r), r['ageing_rank']))
    excluded_kept = excluded_sorted[:MAX_EXCLUDED_PER_EMPLOYEE]

    return strong + good_kept + weak_kept + excluded_kept


def mas_mapping_cross_check(emp_mas_mapping, dem_mas_mapping):
    """Validation-only flag, never a filter/gate — additive, pairing-level cross-check (2026-10-01).
    The existing mas_mapping_check (classify_inputs.py) only ever looks at ONE side at a time: does
    a demand row's own MAS Mapping agree with the persona the ENGINE derived for that same row from
    skill-cluster text. This instead compares the demand's raw MAS Mapping directly against the
    MATCHED supply employee's own raw MAS Mapping — two independently filled-in source labels (one
    from the demand team, one from HR/the bench team) that can disagree with each other even when
    each individually agrees with its own side's engine-derived persona, a case the existing checks
    can't see since neither one looks across the pairing.

    Only meaningful to run at all now that both sides are scoped to the same active MAS Mapping
    categories (the 2026-10-01 scope gate — see mas_mapping_categories.json): before that change,
    comparing demand's raw value (which could be Tpm/Testing/anything) against supply's (always
    Full Stack/Front End, supply's own gate having existed since Task #1) would have been comparing
    apples to a much wider set of oranges. Now every pairing this runs on is already Full Stack vs.
    Full Stack or Front End vs. Front End in the common case, so a disagreement here is a genuine,
    rare signal worth a reviewer's attention, not noise from mismatched scope."""
    emp_raw = None if pd.isna(emp_mas_mapping) else str(emp_mas_mapping).strip()
    dem_raw = None if pd.isna(dem_mas_mapping) else str(dem_mas_mapping).strip()
    if emp_raw is None or dem_raw is None:
        return False, None  # nothing to compare — one side has no MAS Mapping on record
    if emp_raw != dem_raw:
        return True, f"Employee MAS Mapping = '{emp_raw}' but demand MAS Mapping = '{dem_raw}'"
    return False, None


def main():
    supply = pd.read_csv('data/phase1_supply_classified.csv')
    demand = pd.read_csv('data/demand_classified.csv')

    demand_classified = demand[demand['persona'].notna()].copy()

    rows = []
    unclassified_supply = supply[supply['persona'].isna()].copy()

    for _, emp in supply[supply['persona'].notna()].iterrows():
        cands = build_candidate_demands(emp, demand_classified)
        emp_rows = []
        for _, dem in cands.iterrows():
            sk = skill_signal(emp, dem)
            if sk['quality'] == 'no_relation':
                continue
            bd = band_signal(emp['Sub Band'], dem['Demand Sub Band Name'])
            lo = location_signal(emp['Employee Location'], dem['Personnel Sub Area Name'], dem.get('Pan India'))
            asmt = assessment_signal(emp['Rating'], emp['Score'])
            tier = overall_tier(sk, bd, lo)
            mmcc_flag, mmcc_note = mas_mapping_cross_check(emp.get('MAS Mapping'), dem.get('MAS Mapping'))

            summary_bits = []
            # Only a clean 'core' match gets trimmed to its short lead-in —
            # every gap quality (framework_unconfirmed/wrong_subpersona/
            # weak_node, and Task #8's accessory_gap_critical/important/
            # minor) needs its full collapsed text in the one-liner, since
            # that's where the actual gap and its severity are named.
            summary_bits.append(sk['collapsed'].split(' — ')[0] if sk['quality'] == 'core' else sk['collapsed'])
            summary_bits.append(bd['collapsed'])
            summary_bits.append(lo['collapsed'])
            if asmt['collapsed'] != 'Not yet assessed':
                summary_bits.append(asmt['collapsed'])
            one_liner = "; ".join(summary_bits)

            emp_rows.append(dict(
                employee_code=emp['Employee Code'], employee_name=emp['Employee Name'],
                employee_persona=emp['persona'], employee_sub_persona=emp.get('sub_persona'),
                employee_completeness=emp.get('completeness'),
                employee_band=emp['Sub Band'], employee_location=emp['Employee Location'],
                employee_primenv=emp['Prime/NV'],
                employee_afd_status=emp['AFD Status'], employee_bench_ageing=emp['Bench Ageing days'],
                employee_sub_capability_note=emp.get('sub_capability_note'),
                job_req_id=dem['Job Requisition ID'], customer=dem.get('Customer'),
                project=dem.get('Project Name'),
                demand_persona=dem['persona'], demand_sub_persona=dem.get('sub_persona'),
                demand_band=dem['Demand Sub Band Name'], demand_location=dem['Personnel Sub Area Name'],
                pan_india=dem.get('Pan India'), balance_positions=dem['Balance Positions'],
                due_category=dem.get('Due Category_New'), ageing=dem.get('New-Ageing'),
                additional_request=dem.get('Additional Request'),
                mas_mapping_flag=dem.get('mas_mapping_flag'), mas_mapping_note=dem.get('mas_mapping_note'),
                frontend_anchor_flag=dem.get('frontend_anchor_flag'), frontend_anchor_note=dem.get('frontend_anchor_note'),
                mas_mapping_cross_check_flag=mmcc_flag, mas_mapping_cross_check_note=mmcc_note,
                overall_tier=tier,
                skill_collapsed=sk['collapsed'], skill_expanded=sk['expanded'], skill_quality=sk['quality'],
                band_collapsed=bd['collapsed'], band_expanded=bd['expanded'], band_quality=bd['quality'],
                loc_collapsed=lo['collapsed'], loc_expanded=lo['expanded'], loc_quality=lo['quality'],
                assessment_collapsed=asmt['collapsed'], assessment_expanded=asmt['expanded'], assessment_rank=asmt['rank'],
                one_liner=one_liner,
                ageing_rank=AGEING_RANK.get(dem.get('Due Category_New'), 9),
            ))
        rows.extend(cap_employee_rows(emp_rows))

    df = pd.DataFrame(rows)
    print(f"Total pairing rows generated: {len(df)}")
    print(df['overall_tier'].value_counts())
    print(f"Distinct employees with at least 1 row: {df['employee_code'].nunique()} / 239 classified")
    df.to_csv('data/match_rows.csv', index=False)
    unclassified_supply.to_csv('data/unclassified_supply.csv', index=False)
    return df, unclassified_supply


if __name__ == '__main__':
    main()

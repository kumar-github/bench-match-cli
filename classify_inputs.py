"""
Step 1 of the pipeline: turn the three raw source Excel files into the two
classified CSVs that build_matches.py expects.

This is the one piece of the pipeline that previously only existed as
ad-hoc code typed during the analysis session -- it's written down here so
the whole thing can be re-run end to end from scratch, on a fresh export of
the source files, without anyone re-deriving the filter conditions by hand.

Phase 1 scope (as decided so far):
  - Capability == 'MAS'
  - Band in {E1, E2, E3}
  - AFD Status in the four "proposable" statuses (see PROPOSABLE_STATUSES)
  - MAS Mapping in the active set from mas_mapping_categories.json (currently
    {'Full Stack', 'Front End'} -- the three Phase-1 personas: Fullstack Java,
    Fullstack .NET, Frontend)
  This chain is what turns the raw AFD-Supply.xlsx (~1,850 rows) into the
  243-row Phase 1 supply universe.

  AAFD-Supply.xlsx is intentionally NOT included yet. Per the agreed
  decision, an AAFD is just an employee who *will become* an AFD once their
  current project ends -- at that point they're a normal AFD row and this
  same pipeline picks them up with no special handling. There's no proactive
  AAFD matching in this build.

Demand.xlsx was ONCE assumed to already arrive pre-filtered by the export
itself to MAS Mapping in {Front End, Full Stack} (its own trailing summary
row used to say so: "MAS Mapping is Front End or Full Stack") -- that
assumption is WRONG as of 2026-10-01: the real Demand.xlsx now also carries
Tpm/Testing/Polyglot/Devops & Sre/Integration/Mainframe/Architects & Emerging
rows, intentionally, since Phase 2 will need them. load_and_classify_demand()
below now applies its own MAS Mapping scope gate (mirroring supply's, same
active set from mas_mapping_categories.json) instead of relying on the export
to have done it -- see that function's "SCOPE GATE" comment. This docstring
section otherwise still strips the export's trailing footer rows (a blank
row, a "Total" row, and the filter description row) and keeps
Status == 'Approved'.
"""
import json
import sys
from pathlib import Path

import pandas as pd

import engine

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
DATA_DIR = BASE_DIR / "data"

PROPOSABLE_STATUSES = [
    "Available for Deployment",
    "Blocked/Proposed for Opportunity",
    "Assignation Pending",
    "HR Action - WIP",
]

# Fallback only -- used if mas_mapping_categories.json is missing/unreadable, so this script
# never hard-crashes on a missing config file. The real, editable source of truth is that file;
# see load_mas_mapping_scope() below.
_PHASE1_MAS_MAPPING_FALLBACK = ["Full Stack", "Front End"]
MAS_MAPPING_CATEGORIES_FILE = BASE_DIR / "mas_mapping_categories.json"


def load_mas_mapping_scope():
    """Returns the list of MAS Mapping categories currently in active Phase 1 scope, read from
    mas_mapping_categories.json (see that file's header for why this exists and what activating a
    category actually requires). Replaces the old hardcoded PHASE1_MAS_MAPPING literal (2026-10-01)
    -- previously this was a plain Python list with no way to change it short of editing code; this
    makes the scope decision a data file, shared conceptually with the Java web app's own
    V7__mas_mapping_categories.sql seed (kept in sync by hand, not automatically -- no DB here)."""
    try:
        with open(MAS_MAPPING_CATEGORIES_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        active = [c["category"] for c in config["categories"] if c.get("status") == "active"]
        if not active:
            raise ValueError("mas_mapping_categories.json has no 'active' categories")
        return active
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"  Warning: couldn't read {MAS_MAPPING_CATEGORIES_FILE.name} ({e}); "
              f"falling back to {_PHASE1_MAS_MAPPING_FALLBACK}")
        return list(_PHASE1_MAS_MAPPING_FALLBACK)


PHASE1_MAS_MAPPING = load_mas_mapping_scope()


def _find_input_file(name_hint):
    """Look for the source file in ./input first, then next to the scripts,
    so the tool works whether files were dropped into an input/ subfolder
    or just left alongside the scripts."""
    candidates = list(INPUT_DIR.glob(f"*{name_hint}*.xlsx")) + list(
        BASE_DIR.glob(f"*{name_hint}*.xlsx")
    )
    candidates = [c for c in candidates if not c.name.startswith("~$")]  # ignore Excel lock files
    if not candidates:
        raise FileNotFoundError(
            f"Couldn't find a file matching '*{name_hint}*.xlsx' in "
            f"{INPUT_DIR} or {BASE_DIR}. Put the source Excel file there and re-run."
        )
    if len(candidates) > 1:
        print(f"  Note: multiple files matched '*{name_hint}*.xlsx', using {candidates[0].name}")
    return candidates[0]


def load_phase1_supply():
    path = _find_input_file("AFD-Supply")
    print(f"Reading supply file: {path.name}")
    raw = pd.read_excel(path)

    # Band is widened to also admit 'E0' here (previously E1/E2/E3 only) so
    # that a Band=E0 row that DOES carry Capability=MAS + a Phase-1 MAS
    # Mapping is no longer silently invisible before classification ever
    # runs — it now reaches classify_supply() below, where an invalid Sub
    # Band (E0.x, E2.3, or anything else outside the defined E1.1-E3.2
    # ladder) is turned into a visible DATA ISSUE row rather than being
    # dropped without a trace. This does NOT change what counts as Phase 1
    # scope (still MAS + proposable + Full Stack/Front End) — it only stops
    # the Band filter itself from being the thing that hides a bad-data row.
    # AFD Status is matched case/whitespace-insensitively, not with a plain
    # .isin() — found 2026-09-30 against a real refreshed export where the
    # source system had started writing "Blocked/Proposed for opportunity"
    # (lowercase 'o') instead of "...Opportunity". A plain exact-match
    # silently dropped all 119 employees carrying that status (44% of the
    # otherwise-eligible Full Stack/Front End population) with no error, no
    # warning, nothing in the unclassified/data-issue queue — they just
    # never appeared anywhere. This is the general risk with any
    # exact-string filter against a source team's free-form status field;
    # normalizing case/whitespace at comparison time (never at storage —
    # the original casing is still what's stored and displayed) closes this
    # specific instance without weakening the filter's intent.
    proposable_normalized = {s.strip().lower() for s in PROPOSABLE_STATUSES}
    afd_status_normalized = raw["AFD Status"].astype(str).str.strip().str.lower()

    filtered = raw[
        (raw["Capability"] == "MAS")
        & (raw["Band"].isin(["E0", "E1", "E2", "E3"]))
        & (afd_status_normalized.isin(proposable_normalized))
        & (raw["MAS Mapping"].isin(PHASE1_MAS_MAPPING))
    ].copy()

    print(f"  {len(raw)} rows in source -> {len(filtered)} rows in Phase 1 scope "
          f"(MAS + E1-E3 [+E0 flagged as data issue] + proposable + Full Stack/Front End)")
    return filtered


def classify_supply(supply_df):
    results = supply_df["Skill Cluster"].apply(engine.classify_supply_row)
    classified = supply_df.copy()
    for field in ["persona", "sub_persona", "named_accessories", "completeness", "status"]:
        classified[field] = results.apply(lambda r: r[field])
    # framework_confirmed is only set on Fullstack Java/.NET entries in
    # SUPPLY_TABLE — .get() leaves it as None/NaN elsewhere, which
    # build_matches.py treats as "not applicable" (not a penalty).
    classified["framework_confirmed"] = results.apply(lambda r: r.get("framework_confirmed"))

    # Band-ladder data-quality override (E0/E2.3 fix): a row whose Sub Band
    # isn't one of the six defined values (E1.1/E1.2/E2.1/E2.2/E3.1/E3.2) is
    # bad data, not a real position on the ladder we can score against band.
    # Previously this either never reached classification at all (E0 — the
    # Band-level pre-filter above didn't used to admit it) or reached
    # classification, got a normal persona from skill-cluster text, and then
    # only surfaced as an ambiguous "unresolved" match at scoring time (E2.3
    # and anything else in-Band-but-bad-Sub-Band) — neither made the problem
    # itself visible. This overrides BOTH to the same DATA ISSUE treatment
    # already used for skill-cluster-unclassified rows below, so they show
    # up in the same reviewer-facing flagged block instead of two different
    # (and in E0's case, silent) places.
    bad_band_mask = classified["Sub Band"].apply(lambda b: engine.band_index(b) is None)
    classified.loc[bad_band_mask, "persona"] = None
    classified.loc[bad_band_mask, "sub_persona"] = None
    classified.loc[bad_band_mask, "named_accessories"] = classified.loc[bad_band_mask, "named_accessories"].apply(lambda _: [])
    classified.loc[bad_band_mask, "completeness"] = None
    classified.loc[bad_band_mask, "status"] = classified.loc[bad_band_mask, "Sub Band"].apply(
        lambda b: f"DATA ISSUE — Sub Band '{b}' is outside the supported E1.1-E3.2 ladder "
                  f"(needs reviewer confirmation of the employee's real band position)"
    )
    n_bad_band = bad_band_mask.sum()

    # Sub-Capability check (validation-only flag, never a filter/gate — same
    # role as the MAS Mapping check below, just on the supply side). Checked
    # directly against real data before adding this: requiring Sub-Capability
    # to AGREE with the derived persona, as a scoping filter, would have
    # dropped 17 genuine Full Stack/Front End employees whose Sub-Capability
    # tag is stale or differently scoped (most often "Polyglot") while their
    # actual skills and MAS Mapping both agree with each other — so this is
    # deliberately informational only, exactly like MAS Mapping's own check.
    sc_checks = classified.apply(
        lambda r: sub_capability_check(r.get("Sub-Capability"), r.get("persona")), axis=1
    )
    classified["sub_capability_flag"] = sc_checks.apply(lambda t: t[0])
    classified["sub_capability_note"] = sc_checks.apply(lambda t: t[1])
    n_sc_flagged = classified["sub_capability_flag"].sum()

    n_unclassified = classified["persona"].isna().sum()
    print(f"  Supply classification: {len(classified) - n_unclassified} classified, "
          f"{n_unclassified} unclassified (data-issue rows, of which {n_bad_band} are bad Sub Band values)")
    print(f"  Sub-Capability validation: {n_sc_flagged} row(s) flagged for reviewer attention")
    return classified


def sub_capability_check(sub_capability_raw, persona):
    """Validation-only flag (never a filter/gate — matching logic never reads
    Sub-Capability). Flags a supply row when Sub-Capability disagrees with
    the persona the engine actually derived from Skill Cluster free text.
    Mirrors mas_mapping_check below, on the supply side. Deliberately never
    used to exclude a row — see the note above classify_supply()'s call site
    for why: on real data, using it as a filter would have removed real
    candidates, not caught bad ones."""
    raw = None if pd.isna(sub_capability_raw) else str(sub_capability_raw).strip()
    if pd.isna(persona):
        return False, None  # nothing to compare against; classification itself already flags this row
    expected = {"Fullstack Java": "Full Stack", "Fullstack .NET": "Full Stack",
                "Frontend": "Front End"}.get(persona)
    if expected is None:
        return False, None  # persona outside the three Phase 1 buckets — nothing meaningful to compare
    if raw != expected:
        return True, f"Sub-Capability = '{raw}' but engine derived persona = '{persona}' (expected '{expected}')"
    return False, None


def mas_mapping_check(mas_mapping_raw, persona):
    """Validation-only flag (never a filter/gate — matching logic never
    reads MAS Mapping). Flags a demand row when MAS Mapping disagrees
    with the persona the engine actually derived from Final Skill
    Cluster free text.

    Narrowed 2026-10-01: this used to ALSO flag any row whose MAS
    Mapping was outside Full Stack/Front End ("outside Phase 1
    values"). That branch is now dead code by construction — the new
    MAS Mapping scope gate in load_and_classify_demand() clears persona
    and sets an explicit OUT OF PHASE 1 SCOPE status for exactly those
    rows *before* this function ever runs on them, so pd.isna(persona)
    below already catches them. Keeping the old branch would have
    double-reported the same thing two different ways (a SCOPE status
    plus a redundant mas_mapping_flag note) for every excluded row —
    removed instead, so this check now does one job: among rows already
    in active scope, does MAS Mapping privately agree with the
    engine-derived persona."""
    raw = None if pd.isna(mas_mapping_raw) else str(mas_mapping_raw).strip()
    if pd.isna(persona):
        return False, None  # out of Phase 1 scope or otherwise unclassified; nothing to compare against
    if raw == "Full Stack" and persona not in ("Fullstack Java", "Fullstack .NET"):
        return True, f"MAS Mapping = 'Full Stack' but engine derived persona = '{persona}'"
    if raw == "Front End" and persona != "Frontend":
        return True, f"MAS Mapping = 'Front End' but engine derived persona = '{persona}'"
    return False, None


def frontend_anchor_check(skill_text_raw, persona, framework_confirmed):
    """Validation-only flag (never a filter/gate — classify_demand_row()'s
    anchor routing is unconditional; this never changes which persona/branch
    is chosen). Flags a Fullstack Java/.NET demand row when its Final Skill
    Cluster names a frontend framework (React/Angular/MEAN) but the matching
    backend framework (Spring for Java, ASP.NET for .NET) was never
    confirmed — i.e. framework_confirmed is False. This is genuinely
    ambiguous, not resolvable by any token rule: an earlier attempt to
    auto-reroute such rows to Frontend broke ~180 demands where MAS Mapping
    independently confirmed 'Full Stack' (one had additional-request text
    literally saying "no GUI experience needed"), and the identical
    skill-cluster text ("Devops,Java Full Stack,React.js") was tagged Front
    End on one real job requisition and Full Stack on another by different
    humans — proof the ambiguity lives in the source data. So, same
    "checked, not used to match" principle as mas_mapping_check /
    sub_capability_check: surface it for reviewer judgment, never decide it
    automatically."""
    if persona not in ("Fullstack Java", "Fullstack .NET"):
        return False, None
    if framework_confirmed:
        return False, None  # backend framework already confirmed -- no ambiguity
    tokens = engine._tokenize(skill_text_raw)
    tokset = set(tokens)
    has_react = bool(tokset & engine.REACT_TOKENS) or engine._contains_word(tokens, 'next.js')
    has_angular = engine._contains_word(tokens, 'angular')
    has_node = bool(tokset & engine.NODE_TOKENS)
    has_mern_extra = bool(tokset & engine.MERN_STACK_TOKENS)
    has_frontend_anchor = has_react or has_angular or (has_node and has_mern_extra)
    if not has_frontend_anchor:
        return False, None
    fw_name = "Spring" if persona == "Fullstack Java" else "ASP.NET"
    return True, (f"Persona = '{persona}' but frontend framework (React/Angular) named without "
                  f"{fw_name} confirmation; verify persona against MAS Mapping/job description "
                  f"before trusting this match")


def load_and_classify_demand():
    path = _find_input_file("Demand")
    print(f"Reading demand file: {path.name}")
    raw = pd.read_excel(path)

    # Strip export footer rows (blank row, "Total" row, filter-description row)
    cleaned = raw[pd.to_numeric(raw["Job Requisition ID"], errors="coerce").notna()
                  | raw["Job Requisition ID"].astype(str).str.match(r"^[\w\-/]+$", na=False)]
    cleaned = cleaned[~cleaned["Job Requisition ID"].isna()]
    cleaned = cleaned[cleaned["Job Requisition ID"].astype(str).str.strip().str.lower() != "total"]
    if "Status" in cleaned.columns:
        cleaned = cleaned[cleaned["Status"] == "Approved"]
    cleaned = cleaned.copy()

    print(f"  {len(raw)} rows in source -> {len(cleaned)} rows after removing export footer rows")

    results = cleaned["Final Skill Cluster"].apply(engine.classify_demand_row)
    for field in ["persona", "sub_persona", "band_note", "named_accessories", "status"]:
        cleaned[field] = results.apply(lambda r: r.get(field))
    # framework_confirmed: only meaningful for Fullstack Java/.NET rows;
    # None/NaN elsewhere is "not applicable", not a penalty.
    cleaned["framework_confirmed"] = results.apply(lambda r: r.get("framework_confirmed"))

    # Band-ladder data-quality override (Task #14 — demand-side counterpart
    # to Task #11's supply-side E0/E2.3 fix). Before this, a demand row with
    # a Sub Band outside the defined E1.1-E3.2 ladder (real examples in the
    # source file: 'T0', 'E4+'/'E5.x'/'E6.x') still got a normal persona from
    # its skill-cluster text and STAYED in the matching pool — band_signal()
    # returned quality='unresolved', hard_exclude=False for every employee
    # paired against it, which overall_tier() treats as a single ordinary
    # discount (same bucket as "one band above" or "different city"). That's
    # actively misleading, not just an ambiguous label: a demand whose real
    # band position isn't even known could still surface as a Good or Weak
    # proposal with no visible warning beyond buried detail text. Fixed by
    # excluding these rows from the matching pool entirely (persona cleared,
    # same as any other unclassifiable demand row), and counted out
    # separately below so they're distinguishable from ordinary scope
    # leakage / unrecognized-phrasing unclassified rows in the coverage
    # summary — a full per-row visible flag (like supply's DATA ISSUE block)
    # is a separate, not-yet-built view for demand-side issues generally
    # (see "Coverage/unclassified log" in the main requirements write-up),
    # not something this fix adds on its own.
    bad_band_mask = cleaned["Demand Sub Band Name"].apply(lambda b: engine.band_index(b) is None)
    cleaned.loc[bad_band_mask, "persona"] = None
    cleaned.loc[bad_band_mask, "sub_persona"] = None
    cleaned.loc[bad_band_mask, "named_accessories"] = cleaned.loc[bad_band_mask, "named_accessories"].apply(lambda _: [])
    cleaned.loc[bad_band_mask, "status"] = cleaned.loc[bad_band_mask, "Demand Sub Band Name"].apply(
        lambda b: f"DATA ISSUE — Demand Sub Band '{b}' is outside the supported E1.1-E3.2 ladder "
                  f"(needs reviewer confirmation of the requisition's real band position)"
    )
    n_bad_band = bad_band_mask.sum()

    # MAS Mapping SCOPE GATE (2026-10-01) — demand-side counterpart to the filter
    # load_phase1_supply() already applies to supply via PHASE1_MAS_MAPPING. Demand never had
    # this: this module's own docstring at the top of the file assumed Demand.xlsx "already
    # arrives pre-filtered by the export itself" to Full Stack/Front End, so classification ran
    # on every MAS Mapping value unfiltered. That assumption broke once the real Demand.xlsx
    # widened to include Tpm/Testing/Polyglot/Devops & Sre/Integration/Mainframe/Architects &
    # Emerging too — e.g. 32 "Java,Microservices,React.js" rows tagged MAS Mapping='Tpm' (Technical
    # Project Management, not an engineering role) were being classified Fullstack Java purely
    # from skill-cluster text, with nothing to say that persona assignment didn't belong there.
    # PHASE1_MAS_MAPPING (loaded from mas_mapping_categories.json — see that file before changing
    # this) now gates demand the same way it already gated supply. Excluded rows are NOT dropped
    # from the sheet or hidden — same treatment as the bad-band rows just above — they're cleared
    # to persona=None with an explicit SCOPE status, so they stay visible, counted, and ready to
    # pick up the moment their category is flipped to "active" (which also needs real persona/
    # supply-pool work on top — see mas_mapping_categories.json's header).
    scope_mask = ~cleaned["MAS Mapping"].isin(PHASE1_MAS_MAPPING)
    cleaned.loc[scope_mask, "persona"] = None
    cleaned.loc[scope_mask, "sub_persona"] = None
    cleaned.loc[scope_mask, "named_accessories"] = cleaned.loc[scope_mask, "named_accessories"].apply(lambda _: [])
    cleaned.loc[scope_mask, "status"] = cleaned.loc[scope_mask, "MAS Mapping"].apply(
        lambda m: f"OUT OF PHASE 1 SCOPE — MAS Mapping '{m if pd.notna(m) else '(blank)'}' is not an "
                  f"active category yet (see mas_mapping_categories.json); skill-cluster text was not evaluated"
    )
    n_scope_excluded = scope_mask.sum()

    # MAS Mapping validation flag (check-only, per Task #3 — matching logic
    # never reads this column). 'Additional Request' needs no extra handling
    # here: it's an original source column and survives the .copy() above
    # untouched, ready to be surfaced downstream for manual review.
    mas_checks = cleaned.apply(
        lambda r: mas_mapping_check(r.get("MAS Mapping"), r.get("persona")), axis=1
    )
    cleaned["mas_mapping_flag"] = mas_checks.apply(lambda t: t[0])
    cleaned["mas_mapping_note"] = mas_checks.apply(lambda t: t[1])

    # Frontend-anchor validation flag (check-only — see frontend_anchor_check's
    # docstring for why this is a reviewer safety net, never a routing change).
    fa_checks = cleaned.apply(
        lambda r: frontend_anchor_check(r.get("Final Skill Cluster"), r.get("persona"),
                                         r.get("framework_confirmed")),
        axis=1,
    )
    cleaned["frontend_anchor_flag"] = fa_checks.apply(lambda t: t[0])
    cleaned["frontend_anchor_note"] = fa_checks.apply(lambda t: t[1])

    n_unclassified = cleaned["persona"].isna().sum()
    n_mas_flagged = cleaned["mas_mapping_flag"].sum()
    n_fa_flagged = cleaned["frontend_anchor_flag"].sum()
    print(f"  Demand classification: {len(cleaned) - n_unclassified} rows classified, "
          f"{n_unclassified} unclassified (of which {n_bad_band} are bad Demand Sub Band values, "
          f"{n_scope_excluded} are out-of-Phase-1-scope MAS Mapping categories — active categories: "
          f"{PHASE1_MAS_MAPPING})")
    print(f"  MAS Mapping validation: {n_mas_flagged} row(s) flagged for reviewer attention")
    print(f"  Frontend Anchor validation: {n_fa_flagged} row(s) flagged for reviewer attention")
    return cleaned


def main():
    DATA_DIR.mkdir(exist_ok=True)

    supply = load_phase1_supply()
    supply_classified = classify_supply(supply)
    supply_classified.to_csv(DATA_DIR / "phase1_supply_classified.csv", index=False)

    demand_classified = load_and_classify_demand()
    demand_classified.to_csv(DATA_DIR / "demand_classified.csv", index=False)

    print("Step 1 done -> data/phase1_supply_classified.csv, data/demand_classified.csv")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

# Bench Match CLI

Runs the Phase 1 supply-demand matching engine locally and produces the
same shortlist workbook we've been building in the analysis session —
without needing a chat session at all. This is a bridge to the eventual
web app, not a replacement for it.

## One-time setup

1. Install Python 3.9 or later if you don't have it.
2. Open a terminal in this folder and run:
   ```
   pip install -r requirements.txt
   ```
   (If your system Python complains about "externally managed environment,"
   add `--break-system-packages` to that command.)

## Every time you want a fresh shortlist

1. Get current exports of **AFD-Supply.xlsx** and **Demand.xlsx** and put
   them in this folder (or in an `input` subfolder — either works). The
   exact filenames don't matter as long as they *contain* "AFD-Supply" and
   "Demand".
2. Run it:
   - **Terminal (any OS):** `python run.py`
   - **Windows, double-click:** `run.bat`
   - **Mac, double-click:** `run.command` (first time, you may need to
     right-click → Open, since it's an unsigned script)
3. Open the result: `output/phase1-matching-shortlist.xlsx`

## What's in this scope right now

- **Phase 1 personas only** — Fullstack Java, Fullstack .NET, Frontend
  (React/Angular/MERN/iOS/Android). Everything else (Testing, DevOps,
  Mainframe, TPM, non-MAS, etc.) is out of scope, same as the Excel
  deliverable already produced.
- **AFD-Supply.xlsx only — AAFD-Supply.xlsx is not used yet.** An AAFD is
  just an employee who will become an AFD once their current project ends;
  at that point they show up in the next AFD-Supply export and this tool
  picks them up automatically. No separate AAFD logic exists (or is
  needed) yet.
- **Display rules baked in:** all Strong shown, top 3 Good per employee,
  Weak shown only when an employee has zero Strong and zero Good (capped
  at 10), Excluded capped at 3 near-misses per employee. This matches the
  last agreed state. If the pending decision to drop Excluded from the
  Excel entirely gets finalized, that's a one-constant change in
  `build_matches.py` (`MAX_EXCLUDED_PER_EMPLOYEE = 0`) — ask and it's done.
- **No cross-persona matching.** A Java/.NET employee's named frontend
  accessory is never used to propose them against a standalone Frontend
  demand — removed from the design entirely (was contributing zero rows
  to real output anyway).
- **REST/RESTful API is not a tracked named accessory.** Knowing Spring
  or Spring Boot already implies it, on both supply and demand sides.
- **MAS Mapping is checked, not used to match.** Both output workbooks
  include a "MAS Mapping check" column that flags a demand row when its
  MAS Mapping value disagrees with the persona actually derived from its
  skill text — a reviewer safety net, never a filter.
- **Frontend framework named alongside Java/.NET with no backend-framework
  confirmation is now a reviewer flag, not silently absorbed.** Found via a
  real shortlist row: a demand for "Angular,Java,React.js" was matching
  100% against a plain Java/SQL employee. The Java/.NET anchor branch fires
  whenever "Java"/".NET" is present, even when a frontend framework
  (React/Angular/MEAN) is also named and no Spring Boot/ASP.NET confirms
  the backend half — persona routing is **unchanged** (still anchors on
  Java/.NET, same as always; an earlier attempt to auto-reroute these
  demands to Frontend broke ~180 legitimately Fullstack demands, including
  one whose Additional Request text literally said "no GUI experience
  needed," and one skill-cluster text tagged two different ways by
  different humans on two real job requisitions — proof the ambiguity
  lives in the source data, not something a token rule can resolve).
  Instead, both output workbooks now include a "Frontend Anchor check"
  column (`frontend_anchor_check()` in `classify_inputs.py`, producing
  `frontend_anchor_flag`/`frontend_anchor_note`) — same "checked, not used
  to match" principle as MAS Mapping Check above, a reviewer safety net,
  never a filter.
- **Additional Request is surfaced, never parsed.** Both output workbooks
  include the demand sheet's Additional Request text verbatim, for manual
  review only — the engine never reads or scores it.
- **MEAN (Mongo/Express/Angular/Node) is its own sub-persona**, distinct
  from MERN — a MEAN-shaped demand no longer gets silently mislabeled as
  needing React (which would have wrongly excluded a real Angular
  candidate). No real MEAN row exists in the data yet; this fix is for
  whenever one shows up. Follow-up fix: MEAN was also missing from three
  hardcoded sub-persona lists in `build_matches.py` (a demand that accepts
  either React or Angular; a framework-unconfirmed cross-match; a weak
  Node.js-only demand) — a real MEAN candidate would have hard-excluded
  against exactly the demands MEAN's Angular half should qualify for. Now
  included in all three.
- **Spring Boot / Web API-MVC-Entity Framework must actually be confirmed,
  not assumed.** A Java employee with no Spring Boot on file (e.g. "Java,
  SQL"), or a .NET employee with no Web API/MVC/Entity Framework, is no
  longer scored as a full match against a demand that explicitly names the
  framework — capped at Weak instead, same treatment as the existing
  Frontend "framework unconfirmed" bucket. This is a known, deliberate
  stopgap (not the "correct" answer) until a proper skill-weighting
  mechanism exists — at which point this and Frontend's own
  framework-unconfirmed bucket should both be revisited together.
- **Supply and demand now share one accessory vocabulary.** Previously,
  supply-side accessories were hand-typed per entry ("Cloud
  (AWS/Azure/GCP)") while demand-side accessories were auto-generated from
  a separate token list ("Amazon Web Services (Aws)", "Azure", "Gcp") —
  different strings for the same skill, so a real cloud-experienced
  employee could show a false "named accessory gap" against a demand
  asking for AWS/Azure/GCP specifically (same shape of bug as the earlier
  REST fix). Both sides now resolve through one canonical registry
  (`ACCESSORY_CANONICAL` in `engine.py`) — AWS/Azure/GCP/Cloud all collapse
  to a single "Cloud" accessory on both sides, matching the granularity
  supply-side curation already uses.
- **Skill gaps are now weighted (Critical/Important/Minor), not one flat
  discount.** Before this, ANY named-accessory gap — whether the missing
  thing was Spring Boot or just Redis — capped a match at Good in exactly
  the same way. Now every gap (the persona's real framework, plus every
  named accessory) is weighted via `ACCESSORY_WEIGHT` in `engine.py`:
  **Critical** (the framework itself — Spring Boot / Web API-MVC-Entity
  Framework / React or Angular) caps at Weak; **Important** (Microservices,
  Cloud, DevOps, Kafka) caps at Good; **Minor** (Docker, Hibernate, Web
  Services, Redis, GraphQL, Python) is informational only and no longer
  caps the tier — a Java employee missing only Hibernate, say, can now
  correctly land as Strong instead of being flat-capped at Good. This also
  folds Task #6's framework check and Frontend's pre-existing
  framework-unconfirmed bucket into the same severity concept, so there's
  one mechanism instead of two. **This is v1** — the Critical/Important/
  Minor assignment is a deliberate, explicitly correctable first pass, not
  a final calibration. "Kotlin" is included with an explicit Minor weight
  even though no supply-side entry can currently satisfy it — a demand
  asking for Java+Kotlin will always show this as a gap, since no employee
  can currently confirm it (same shape of coverage gap as "Messaging",
  noted in the main requirements write-up). Explicit rather than silently
  falling to the default, so it's visible instead of hidden.
- **A small architecture cleanup, found during a gap review, not a
  behavior change:** several token-set constants in `engine.py`
  (`JAVA_TOKENS`, `DOTNET_TOKENS`, `DEVOPS_TOKENS`, `IOS_TOKENS`,
  `ANDROID_TOKENS`, `RAW_SQL_TOKENS`) were defined but never actually read
  by the classification logic — the real checks hardcode the same strings
  directly. `ANDROID_TOKENS` was worse than just unused: it bundled in
  `'kotlin'`, directly contradicting the deliberate "Kotlin does not imply
  Android without an explicit mobile term" fix a few lines below it in the
  same file. Removed rather than left as a landmine for whoever edits them
  next, expecting them to matter.
- **React/Angular are now tracked as a named accessory when they co-occur
  with Java/.NET, the same as Cloud/DevOps/Docker/etc.** Before this, they
  were the one named skill silently dropped entirely when named alongside a
  language anchor — e.g. "Java, Spring Boot, REST, React" recorded no
  accessory at all, even though everything else on the accessory list
  (Cloud, DevOps, Docker, Python, Hibernate, ...) was tracked normally.
  Weighted **Minor** (same bucket as Docker/Hibernate/Python — informational,
  doesn't cap the tier), not Important like Cloud/DevOps, since it's a
  nice-to-have for a backend persona rather than framework-defining;
  correctable if that read is wrong. When React/Angular instead *define*
  the persona (a standalone Frontend demand or employee), they're
  deliberately excluded from the named-accessory list at each of those
  return sites — a persona isn't its own accessory. Verified against real
  data: no change to Strong/Good/Weak/Excluded counts (expected — Minor
  severity is informational only by design), but the skill is now visibly
  called out in the reasoning/summary columns for 1,279 real pairing rows
  that mention React or Angular, where it was previously invisible.
- **JMS was a real, untracked named accessory — now fixed. RabbitMQ added
  proactively.** A real demand row ("JMS, Java, React.js") was silently
  invisible to the engine — `jms` wasn't recognized as any named accessory
  at all, so it could never be flagged as a gap either way. Fixed by adding
  **JMS** to `ACCESSORY_CANONICAL`/`ACCESSORY_WEIGHT` (Important, same tier
  as Kafka). **RabbitMQ** added alongside it for the same reason, even
  though no current demand row mentions it — same kind of gap waiting to
  happen, costs nothing to close now. **"Messaging" deliberately stays its
  own, separate accessory** — it's an architecture-level term, not another
  name for Kafka/JMS/RabbitMQ, so it's correct that it doesn't unify with
  any of them (unlike the earlier Cloud/AWS/Azure/GCP fix, where those
  really were the same thing under different names).
- **Accessory weights can now be overridden per persona**
  (`ACCESSORY_WEIGHT_OVERRIDES` in `engine.py`, keyed by
  `(persona, accessory_name)`) — infrastructure only, currently empty. Every
  weight today still resolves through the generic, persona-agnostic table;
  this exists for the day a persona-specific override is actually needed
  (e.g. Cloud weighing differently for Frontend vs. Java) without a further
  code change.
- **Sub Band values outside the defined E1.1-E3.2 ladder (E0.x, E2.3, or
  anything else) are now a visible DATA ISSUE, not silently dropped or
  quietly ambiguous.** Previously these split into two different bad
  behaviors: a Band=E0 row never even reached classification (the Band-level
  pre-filter only admitted E1/E2/E3), so it was invisible with no trace at
  all; a Band=E1/E2/E3 row with an invalid Sub Band (e.g. E2.3) *did* get
  classified normally off its skill-cluster text and only surfaced as an
  ambiguous "unresolved, needs manual check" match at scoring time — easy to
  miss, and not flagged as bad data. Both are now caught at classification
  time (`classify_supply()` in `classify_inputs.py`) and routed into the
  same red-highlighted DATA ISSUE block the workbook already uses for
  skill-cluster-unclassified rows, so a reviewer sees exactly one consistent
  place for "this employee's data needs fixing before they can be matched."
  Verified with a synthetic E2.3/E0.2 test — both correctly flag; real data
  currently has none reaching this point (243-row Phase 1 count unchanged),
  so this is a forward-looking fix, not a correction to today's output.
  **One related, separately-scoped finding, not yet acted on:** most of the
  real Band=E0 rows in the source file (21 of 22) don't carry
  `Capability == 'MAS'` at all — they're blocked by an earlier filter than
  the band check, so this fix alone doesn't make them visible. See the main
  requirements write-up for the detail and the open question.

## Optional: thin one-row-per-employee view

After a normal run (`run.py`), you can also generate a narrower companion
workbook — one row per employee, their single best Strong match (or best
Good if they have no Strong), with raw skill-cluster text instead of the
persona label so a plain text search actually finds things like "Spring
Boot". Employees with neither a Strong nor a Good match are left out of
this file (they're still fully visible in the main workbook).

```
python generate-thin.py
```

This only reads `data/match_rows.csv` (already produced by `run.py`) — it
doesn't touch `engine.py`, `build_matches.py`, or `run.py` at all, and
doesn't recompute any score or tier. Output:
`output/phase1-matching-shortlist-thin.xlsx`.

## Files

| File | What it does |
|---|---|
| `run.py` | Runs the three steps below in order. This is the only thing you need to run for the full workbook. |
| `generate-thin.py` | Optional, standalone — produces the thin one-row-per-employee companion workbook described above. Run it after `run.py`. |
| `classify_inputs.py` | Step 1 — reads the raw Excel files, applies the Phase 1 supply filter (MAS + E1-E3 + proposable status + Full Stack/Front End), and classifies every row into a persona via `engine.py`'s rules. |
| `build_matches.py` | Step 2 — scores every employee×demand candidate pair on skill/band/location/assessment and assigns Strong/Good/Weak/Excluded, then applies the display caps above. |
| `write_shortlist_workbook.py` | Step 3 — writes the formatted Excel workbook (grouped by employee, colour-coded, Read Me tab). |
| `engine.py` | The persona/anchor/accessory classification rules — the same logic validated against `anchor-accessory-skill-table.xlsx`. |
| `mas_mapping_categories.json` | Which MAS Mapping categories (Full Stack, Front End, Tpm, ...) are active for Phase 1 — see its own header comment before changing anything. Read by `classify_inputs.py` at import time. |
| `generate_review_worklist.py` | Optional, standalone — regenerates `output/demand-classification-review-worklist.xlsx` (the phrase-level uncertainty review list) from the current `data/demand_classified.csv`/`data/phase1_supply_classified.csv`. Run it any time after `run.py`. |
| `data/` | Intermediate CSVs (created on first run) — useful if you want to inspect what got classified as what, outside of Excel. |

## If something looks off

The classification rules (`engine.py`) and the tiering/scoring logic
(`build_matches.py`) are exactly what was built and checked row-by-row in
the analysis session — nothing was changed to build this CLI, only wrapped.
The one new piece is `classify_inputs.py` (Step 1), which reproduces the
raw-Excel-to-classified-CSV step that was previously only run ad hoc; it's
been verified against the known Phase 1 numbers (243 supply rows, 239
classified, same Strong/Good/Weak/Excluded split) before being handed over.

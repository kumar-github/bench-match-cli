"""
Extended export for the Java port's parallel-run verification harness.

The first pass (export_fullstack_java_ground_truth.py) only covered the
Fullstack Java persona on both sides. This script covers EVERY classified
persona pairing in one pass — Fullstack Java x Fullstack Java (already
verified), Fullstack .NET x Fullstack .NET (never verified), Frontend x
Frontend (never verified, and not yet ported in MatchingService.java at
all), and Java/.NET x Frontend cross-persona-discount pairs (never
verified, and not yet ported either).

Does NOT modify classify_inputs.py/build_matches.py in any way — imports
and calls their real functions unmodified, exactly like the first script.

Outputs:
  - full_supply_classified.csv : every classified (persona not null) supply row
  - full_demand_classified.csv : every classified (persona not null) demand row
  - full_match_rows_ground_truth.csv : every non-"no_relation" pairing row
    across ALL classified supply x classified demand rows (uncapped, same
    "before cap_employee_rows()" reasoning as the first script)
"""
import sys
sys.path.insert(0, '.')
import classify_inputs
import build_matches
import pandas as pd

supply = classify_inputs.load_phase1_supply()
supply_classified = classify_inputs.classify_supply(supply)
demand_classified = classify_inputs.load_and_classify_demand()

sup = supply_classified[supply_classified['persona'].notna()].copy()
dem = demand_classified[demand_classified['persona'].notna()].copy()

print(f"Classified supply rows: {len(sup)}")
print(f"Classified demand rows: {len(dem)}")
print("Supply persona breakdown:")
print(sup['persona'].value_counts())
print("Demand persona breakdown:")
print(dem['persona'].value_counts())

sup.to_csv('full_supply_classified.csv', index=False)
dem.to_csv('full_demand_classified.csv', index=False)

rows = []
for _, emp in sup.iterrows():
    for _, demr in dem.iterrows():
        sk = build_matches.skill_signal(emp, demr)
        if sk['quality'] == 'no_relation':
            continue
        bd = build_matches.band_signal(emp['Sub Band'], demr['Demand Sub Band Name'])
        lo = build_matches.location_signal(emp['Employee Location'], demr['Personnel Sub Area Name'], demr.get('Pan India'))
        tier = build_matches.overall_tier(sk, bd, lo)
        rows.append(dict(
            employee_code=emp['Employee Code'],
            job_req_id=demr['Job Requisition ID'],
            emp_persona=emp['persona'],
            dem_persona=demr['persona'],
            overall_tier=tier,
            skill_quality=sk['quality'],
            band_quality=bd['quality'],
            loc_quality=lo['quality'],
        ))

df = pd.DataFrame(rows)
print(f"\nTotal uncapped non-'no_relation' pairing rows: {len(df)}")
print("\nBy (emp_persona, dem_persona) pair:")
print(df.groupby(['emp_persona', 'dem_persona']).size())
print("\nOverall tier distribution:")
print(df['overall_tier'].value_counts())
print("\nSkill-quality distribution (this is what exercises the new branches):")
print(df['skill_quality'].value_counts())
df.to_csv('full_match_rows_ground_truth.csv', index=False)

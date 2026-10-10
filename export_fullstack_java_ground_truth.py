"""
One-off export script for the Java port's parallel-run verification
harness (Task: "Load real data ... verify Fullstack Java output" in
bench-match-webapp). Does NOT modify classify_inputs.py/build_matches.py
in any way — imports and calls their real functions unmodified, so
whatever this exports IS the actual Python behavior, not a re-derivation
of it.

Outputs (restricted to Fullstack Java persona, both sides):
  - fj_supply_classified.csv : raw classification inputs/outputs per employee
  - fj_demand_classified.csv : raw classification inputs/outputs per demand
  - fj_match_rows_ground_truth.csv : every Java-Java pairing row BEFORE
    cap_employee_rows() truncates them for Excel display — the cap is a
    display/ranking decision for the shortlist workbook, not part of the
    matching computation itself, so the uncapped set is the correct
    ground truth for verifying the engine port.
"""
import sys
sys.path.insert(0, '.')
import classify_inputs
import build_matches
import pandas as pd

supply = classify_inputs.load_phase1_supply()
supply_classified = classify_inputs.classify_supply(supply)
demand_classified = classify_inputs.load_and_classify_demand()

fj_supply = supply_classified[supply_classified['persona'] == 'Fullstack Java'].copy()
fj_demand = demand_classified[demand_classified['persona'] == 'Fullstack Java'].copy()

print(f"Fullstack Java supply rows: {len(fj_supply)}")
print(f"Fullstack Java demand rows: {len(fj_demand)}")

fj_supply.to_csv('fj_supply_classified.csv', index=False)
fj_demand.to_csv('fj_demand_classified.csv', index=False)

# Uncapped pairing rows, Java-Java only, using the real skill_signal/
# band_signal/location_signal/overall_tier functions directly.
rows = []
for _, emp in fj_supply.iterrows():
    for _, dem in fj_demand.iterrows():
        sk = build_matches.skill_signal(emp, dem)
        if sk['quality'] == 'no_relation':
            continue
        bd = build_matches.band_signal(emp['Sub Band'], dem['Demand Sub Band Name'])
        lo = build_matches.location_signal(emp['Employee Location'], dem['Personnel Sub Area Name'], dem.get('Pan India'))
        tier = build_matches.overall_tier(sk, bd, lo)
        rows.append(dict(
            employee_code=emp['Employee Code'],
            job_req_id=dem['Job Requisition ID'],
            overall_tier=tier,
            skill_quality=sk['quality'],
            band_quality=bd['quality'],
            loc_quality=lo['quality'],
        ))

df = pd.DataFrame(rows)
print(f"Total uncapped Java-Java pairing rows: {len(df)}")
print(df['overall_tier'].value_counts())
df.to_csv('fj_match_rows_ground_truth.csv', index=False)

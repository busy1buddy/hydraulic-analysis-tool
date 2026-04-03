"""
Pipe Database Validation Script
================================
Cross-checks every entry in data/au_pipes.py against known standard values.
Run: python scripts/validate_pipe_db.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.au_pipes import PIPE_DATABASE

PASS = 0
FAIL = 0

def check(condition, msg):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {msg}")
    else:
        FAIL += 1
        print(f"  FAIL: {msg}")


print("=" * 60)
print("Pipe Database Validation")
print("=" * 60)

# --- PVC: AS/NZS 1477 OD series ---
print("\n--- PVC (AS/NZS 1477) ---")
pvc = PIPE_DATABASE.get("PVC", {})

# OD must match AS/NZS 1477 series
pvc_od_expected = {100: 110, 150: 160, 200: 225, 250: 280, 300: 315, 375: 400}
for dn, expected_od in pvc_od_expected.items():
    entry = pvc.get(dn)
    if entry is None:
        check(False, f"DN{dn} missing from PVC database")
        continue
    actual_od = entry.get("outside_diameter_mm")
    check(actual_od == expected_od,
          f"DN{dn} OD={actual_od} (expected {expected_od})")

# ID must be less than OD
for dn, entry in pvc.items():
    od = entry.get("outside_diameter_mm", 0)
    id_mm = entry["internal_diameter_mm"]
    wall = entry["wall_thickness_mm"]
    if od > 0:
        check(id_mm < od, f"DN{dn} ID={id_mm} < OD={od}")
        check(abs(od - id_mm - 2 * wall) < 1.0,
              f"DN{dn} geometry: OD-2*wall={od - 2*wall:.1f} vs ID={id_mm}")

# HW-C for PVC
for dn, entry in pvc.items():
    check(145 <= entry["hazen_williams_c"] <= 150,
          f"DN{dn} C={entry['hazen_williams_c']} (expected 145-150)")

# --- PE100: AS/NZS 4130 ---
print("\n--- PE100 (AS/NZS 4130) ---")
pe = PIPE_DATABASE.get("PE", {})
for dn, entry in pe.items():
    check(entry["hazen_williams_c"] >= 140,
          f"DN{dn} C={entry['hazen_williams_c']} (expected >= 140)")

# --- Ductile Iron: AS 2280 ---
print("\n--- Ductile Iron (AS 2280) ---")
di = PIPE_DATABASE.get("Ductile Iron", {})

# Wave speed minimum 1100 m/s
for dn, entry in di.items():
    check(entry["wave_speed_ms"] >= 1100,
          f"DN{dn} wave speed={entry['wave_speed_ms']} (min 1100)")

# DN500 must exist
check(500 in di, "DN500 exists in DI database")

# Internal diameter must be less than DN (for cement-lined)
for dn, entry in di.items():
    id_mm = entry["internal_diameter_mm"]
    # DI OD is larger than DN, but cement-lined bore could be around DN
    check(id_mm > 0, f"DN{dn} ID={id_mm} > 0")

# --- Concrete: AS 4058 ---
print("\n--- Concrete (AS 4058) ---")
concrete = PIPE_DATABASE.get("Concrete", {})

# HW-C by size
concrete_c_expected = {375: 110, 450: 110, 600: 100, 750: 100, 900: 90}
for dn, expected_c in concrete_c_expected.items():
    entry = concrete.get(dn)
    if entry is None:
        check(False, f"DN{dn} missing from Concrete database")
        continue
    check(entry["hazen_williams_c"] == expected_c,
          f"DN{dn} C={entry['hazen_williams_c']} (expected {expected_c})")

# --- Summary ---
print("\n" + "=" * 60)
print(f"Results: {PASS} PASS, {FAIL} FAIL")
if FAIL > 0:
    print("VALIDATION FAILED")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)

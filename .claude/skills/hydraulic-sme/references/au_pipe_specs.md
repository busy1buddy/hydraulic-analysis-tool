# Australian Pipe Specifications — Reference

Authoritative excerpt of `data/au_pipes.py` for in-context use during reviews. Always cross-check against the live catalogue if values seem off.

## Ductile Iron — AS 2280

| DN (mm) | OD (mm) | Wall t (mm) | ID (mm) | C-factor | Wave speed (m/s) | PN |
|---|---|---|---|---|---|---|
| 100 | 118 | 4.7 | 108.6 | 130 | 1100 | PN25 |
| 150 | 170 | 5.0 | 160.0 | 130 | 1100 | PN25 |
| 200 | 222 | 5.4 | 211.2 | 130 | 1100 | PN25 |
| 300 | 326 | 6.2 | 313.6 | 130 | 1100 | PN25 |
| 500 | 532 | 8.6 | 514.8 | 130 | 1100 | PN25 |

**Constraint:** wave speed ≥ 1100 m/s for all sizes (encoded constraint #8). PE100 yield in the stress library is 20–22 MPa, NOT 10 MPa.

## PVC — AS/NZS 1477

OD series — **OD ≠ DN** for PVC. This is the bug-prone one.

| DN | OD (mm) | Typical wall (PN12) | C-factor | PN |
|---|---|---|---|---|
| 100 | 110 | 4.4 | 145 | PN12 |
| 150 | 160 | 6.4 | 145 | PN12 |
| 200 | 225 | 9.0 | 145 | PN12 |
| 250 | 280 | 11.2 | 145 | PN12 |
| 300 | 315 | 12.6 | 145 | PN12 |
| 375 | 400 | 16.0 | 145 | PN12 |

**Constraint:** these OD values are encoded #5; do not change without AS/NZS reference.

## PE100 / HDPE — AS/NZS 4130

| DN | OD (mm) | SDR | Wall t (mm) | C-factor | PN |
|---|---|---|---|---|---|
| 100 | 110 | SDR11 | 10.0 | 140 | PN16 |
| 150 | 160 | SDR11 | 14.6 | 140 | PN16 |
| 200 | 225 | SDR11 | 20.5 | 140 | PN16 |
| 300 | 315 | SDR11 | 28.6 | 140 | PN16 |

**Constraint:** PE100 short-term design yield = **20–22 MPa** per AS/NZS 4130 Table 2 (encoded constraint #6).

## Concrete — AS 4058

C-factor depends on diameter (encoded constraint #7):

| DN range (mm) | C-factor |
|---|---|
| 375–450 | 110 |
| 600–750 | 100 |
| ≥ 900 | 90 |

## Pump Curve Database — `data/pump_curves.py`

Slurry pumps (motor ratings corrected to realistic shaft/motor ratios):
- `SLP-200-30`: 22 kW (was 45 kW pre-fix)
- `SLP-400-50`: 75 kW (was 110 kW pre-fix)

## How to verify catalogue health

```bash
python scripts/validate_pipe_db.py
# Should report 58/58 PASS
```

If anything fails, do not "fix" the catalogue silently. Open a `docs/decisions/{date}.md` entry citing the AS/NZS clause.

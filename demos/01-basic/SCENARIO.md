# Demo 01 — Basic roster hygiene check

A two-person roster (`roster.json`) with realistic clearance-hygiene issues.

Run (evaluating as of a fixed date so output is reproducible):

```bash
python -m clearancepath --as-of 2026-06-08 assess demos/01-basic/roster.json
```

Or just the items that need attention, as JSON:

```bash
python -m clearancepath --as-of 2026-06-08 --format json due demos/01-basic/roster.json
```

## What it should catch

**Doe, Jane A. (TS/SCI)**
- **CRITICAL — investigation:** last investigation 2019-03-15. TS/SCI carries a
  5-year (1825-day) reinvestigation horizon, so the record is well past due.
- **CRITICAL — sead3:** foreign travel to Lisbon occurred 2026-05-01 and was
  never reported. SEAD-3 foreign travel is reportable *in advance* (zero grace),
  so this is an unreported reportable event.
- **WARN — sead4:** open Guideline F (financial) adjudicative concern.
- **CRITICAL — training:** `insider_threat` completed 2024-12-01 is past its
  1-year validity.
- `security_refresher` and `derivative_classifier` are still current.

**Smith, Robert K. (SECRET)**
- Investigation 2021-11-02 is well within the 10-year Secret horizon — OK.
- The DUI arrest was self-reported within 2 days (inside the 30-day grace) — OK.
- Training is current.
- Smith is clean (no WARN/CRITICAL).

## Exit codes
- `0` clean, `1` CRITICAL present, `2` WARN only, `3` usage/input error.

Because Doe has CRITICAL findings, `assess` exits **1**.

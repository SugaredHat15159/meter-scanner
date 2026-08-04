# Meter Scanner

Two tools for inventorying electric meters and keeping a master database up to date:

1. **Meter Scanner** (`index.html`) — a browser app for scanning meters in the field.
2. **Meter Reconciliation** (`meter_reconcile.py`) — a script that merges a scan export into your existing database.

The scanner runs in a browser and needs no install. The reconciliation script runs on a computer with Python.

---

## 1. Meter Scanner (web app)

A single-page app that captures four fields per meter — **Position**, **FlexNet ID**, **Meter ID**, **Other** — organized by room, and exports the results to a spreadsheet. It reads barcodes from a phone camera, a still photo, or a plugged-in handheld scanner, and stores everything locally in the browser (nothing is uploaded).

**Live app:** https://sugaredhat15159.github.io/meter-scanner/

**Basic use**
1. Open the link in a browser (Safari on iPhone; allow the camera). Optionally Add to Home Screen.
2. Pick or create a room (one room per wall/area).
3. Scan or type each line: Position → FlexNet ID → Meter ID → (Other). The cursor auto-advances.
4. Use the toggles to speed things up: **Skip Other**, **Auto-number Position** (type a prefix like `WB1` and it counts up from the current line).
5. Tap **Export** to download the inventory as a file, then email or save it.

Data lives only in that browser on that device under the key `meterInv3`. Export before clearing browser data. Full usage and internals are in `Meter_Script_Documentation` / the app guide.

**Editing the app:** it is just `index.html`. Edit it, commit, and push; GitHub Pages republishes automatically within a minute.

---

## 2. Meter Reconciliation (`meter_reconcile.py`)

Merges a fresh scan export into your existing meter database: it updates positions on records that already exist, adds meters that are new, flags "no meter" slots, drops records that are gone, and writes a sorted output plus a removed-records file and a summary.

**Requirements:** Python 3 (no extra packages — uses only the standard library).

**Inputs (both CSV):**
- `new_inventory.csv` — export from the Meter Scanner app (columns: room, position, FlexNet ID, Meter ID, other).
- `existing_inventory.csv` — your current meter database.

**How to run**
1. Put both CSV files in the same folder as `meter_reconcile.py`.
2. Open `meter_reconcile.py` and edit the settings near the top:
   ```python
   new_file = "new_inventory.csv"
   old_file = "existing_inventory.csv"
   output_file = "reconciled_meters.csv"
   update_date_bool = False   # True = set every rdate to today (m/d/y)
   ```
3. Run it:
   ```bash
   python meter_reconcile.py
   ```
4. Check the three output files:
   - `reconciled_meters.csv` — the merged result (use this).
   - `reconciled_meters_removed.csv` — records that were in the old database but not the new scan.
   - `reconciled_meters_summary.txt` — a report of what changed.

**How matching works**
- The unique key is **FlexNet ID + Meter ID** (case-insensitive).
- **Match:** position is updated from the new scan; all other existing columns are preserved.
- **No match:** added as a new record with position, FlexNet ID, and Meter ID filled; other columns blank.
- **No meter:** if the `other` column contains "no meter" or "empty," the line is written with position only and a `comment` of "no meter."
- **Removed:** old records not present in the new scan are excluded from the output and listed in the removed file.
- Output is sorted by position in natural order (`WB1-001` … `WB1-032`, then `WB2-001` …).

Full details are in `Meter_Script_Documentation.html`.

---

## How the two tools fit together

Scan meters in the field with the app → **Export** to CSV → feed that CSV as `new_inventory.csv` into the reconciliation script alongside your current database → get an updated master CSV ready for your system.

---

## Files in this repo

| File | Purpose |
|------|---------|
| `index.html` | The Meter Scanner web app (served by GitHub Pages) |
| `meter_reconcile.py` | The reconciliation script |
| `Meter_Script_Documentation.html` | Detailed docs for the reconciliation script |
| `README.md` | This file |

---

## Notes

- The scanner export currently produces a spreadsheet; the reconciliation script expects **CSV** input, so export/convert to CSV before running it.
- The two tools are independent. Adding or changing the Python script cannot affect the web app, since GitHub Pages only serves `index.html`.

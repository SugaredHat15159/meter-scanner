#!/usr/bin/env python3
"""
Meter Inventory Reconciliation Tool
- Matches new positions (room, position, FlexNet ID, Meter ID, other) against existing inventory
- Updates positions in existing records while keeping all other fields
- Adds new records not in existing file
- Removes old records not in new inventory
- Generates summary of changes
"""

import csv
import sys
import re
from pathlib import Path
from datetime import datetime

# ============================================================================
# EDIT THESE VARIABLES WITH YOUR FILENAMES
# ============================================================================

# Path to your NEW inventory CSV (from Meter Scanner export)
new_file = "new_inventory.csv"

# Path to your EXISTING inventory CSV (your current database)
old_file = "existing_inventory.csv"

# Path where you want the OUTPUT saved (optional - auto-generates if left empty)
output_file = "reconciled_meters.csv"

# Update rdate to current date for all records (True/False)
update_date_bool = False

# ============================================================================

def load_csv(filename):
    """Load CSV and return list of dicts with normalized keys."""
    rows = []
    if not Path(filename).exists():
        print(f"[ERROR] File not found: {filename}")
        sys.exit(1)
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                print(f"[ERROR] Empty or invalid CSV: {filename}")
                sys.exit(1)
            for row in reader:
                # Strip whitespace from keys
                cleaned = {k.strip() if k else k: v.strip() if v else '' for k, v in row.items()}
                rows.append(cleaned)
    except Exception as e:
        print(f"[ERROR] Error reading {filename}: {e}")
        sys.exit(1)
    
    return rows

def normalize_key(key):
    """Normalize field name for comparison."""
    return key.lower().strip() if key else key

def natural_sort_key(text):
    """Convert string to tuple for natural sorting (WB1-001 before WB1-032)."""
    def convert(part):
        return int(part) if part.isdigit() else part.lower()
    return [convert(c) for c in re.split('([0-9]+)', text)]

def find_column(row, possible_names):
    """Find a column value by trying multiple possible names."""
    for name in possible_names:
        normalized = normalize_key(name)
        for key, val in row.items():
            if normalize_key(key) == normalized:
                return val
        # Direct match attempt
        if name in row:
            return row[name]
    return ''

def reconcile(new_file, old_file, output_file):
    """Reconcile new inventory against old inventory."""
    
    print("\n[*] Loading files...")
    new_rows = load_csv(new_file)
    old_rows = load_csv(old_file)
    
    print(f"   New inventory: {len(new_rows)} records")
    print(f"   Existing inventory: {len(old_rows)} records")
    
    if not new_rows:
        print("[ERROR] New inventory is empty")
        sys.exit(1)
    if not old_rows:
        print("[WARNING] Existing inventory is empty — will create all new records")
    
    # Build lookup: (flexnet_id, meter_id) -> old_row
    old_lookup = {}
    for old_row in old_rows:
        flexnet = find_column(old_row, ['FlexNet ID', 'flexnetid', 'flexnet_id', 'flex_net_id'])
        meter = find_column(old_row, ['Meter ID', 'meterid', 'meter_id'])
        if flexnet or meter:
            key = (flexnet.upper(), meter.upper())
            old_lookup[key] = old_row
    
    print(f"   Built lookup with {len(old_lookup)} old records")
    
    # Process new inventory
    matched = []
    added = []
    no_meter = []
    uncertain = []
    used_old_keys = set()
    
    print("\n[*] Matching records...")
    for new_row in new_rows:
        new_room = find_column(new_row, ['room', 'Room'])
        new_pos = find_column(new_row, ['position', 'Position'])
        new_flexnet = find_column(new_row, ['FlexNet ID', 'flexnetid', 'flexnet_id'])
        new_meter = find_column(new_row, ['Meter ID', 'meterid', 'meter_id'])
        new_other = find_column(new_row, ['other', 'Other'])
        
        # Check if this is a "no meter" entry (other column says "no meter" or "empty")
        is_no_meter = new_other.lower().strip() in ['no meter', 'empty']
        
        if is_no_meter:
            # Handle "no meter" entry - position only with comment
            no_meter_record = {}
            if old_rows:
                first_old = old_rows[0]
                for col in first_old.keys():
                    col_norm = normalize_key(col)
                    if col_norm in ['position']:
                        no_meter_record[col] = new_pos
                    elif col_norm in ['comment', 'comments']:
                        no_meter_record[col] = 'no meter'
                    else:
                        no_meter_record[col] = ''
            else:
                no_meter_record = {
                    'position': new_pos,
                    'comment': 'no meter'
                }
            no_meter.append(no_meter_record)
        else:
            lookup_key = (new_flexnet.upper(), new_meter.upper())
            
            if lookup_key in old_lookup:
                # Found a match — update position, keep everything else
                old_row = old_lookup[lookup_key]
                updated = old_row.copy()
                updated['position'] = new_pos  # Update position from new inventory
                
                # Also update room if it exists in old schema
                if 'room' in updated or any(normalize_key(k) == 'room' for k in updated.keys()):
                    for key in updated.keys():
                        if normalize_key(key) == 'room':
                            updated[key] = new_room
                            break
                
                matched.append(updated)
                used_old_keys.add(lookup_key)
            else:
                # New record not in old inventory
                # Create row matching old file structure, filled with new data where available
                new_record = {}
                
                # Populate all old file columns
                if old_rows:
                    first_old = old_rows[0]
                    for col in first_old.keys():
                        col_norm = normalize_key(col)
                        # Try to fill from new data
                        if col_norm in ['position']:
                            new_record[col] = new_pos
                        elif col_norm in ['flexnetid', 'flexnet id', 'flexnet_id', 'flex_net_id']:
                            new_record[col] = new_flexnet
                        elif col_norm in ['meterid', 'meter id', 'meter_id']:
                            new_record[col] = new_meter
                        else:
                            new_record[col] = ''
                else:
                    # No old rows to reference, create basic structure
                    new_record = {
                        'position': new_pos,
                        'flexnetid': new_flexnet,
                        'meterid': new_meter,
                    }
                
                added.append(new_record)
    
    # Find removed records (in old but not in new)
    removed = []
    for old_row in old_rows:
        flexnet = find_column(old_row, ['FlexNet ID', 'flexnetid', 'flexnet_id'])
        meter = find_column(old_row, ['Meter ID', 'meterid', 'meter_id'])
        key = (flexnet.upper(), meter.upper())
        
        if key not in used_old_keys:
            removed.append(old_row)
    
    print(f"   [OK] Matched: {len(matched)}")
    print(f"   [+] Added (new): {len(added)}")
    print(f"   [!] No meter: {len(no_meter)}")
    print(f"   [-] Removed (old): {len(removed)}")
    
    # Combine: matched + added + no_meter (ALL records from new inventory)
    output_rows = matched + added + no_meter
    
    # Write output
    print(f"\n[*] Writing output to {output_file}...")
    if not output_rows:
        print("[ERROR] No records to write")
        return
    
    try:
        # Use old file's column structure for output
        if old_rows:
            fieldnames = list(old_rows[0].keys())
        else:
            # Fallback if no old rows
            fieldnames = ['position', 'flexnetid', 'mtype', 'pingstatus', 'lastgoodping', 
                         'userid', 'firmware', 'format', 'ekey', 'rdate', 'comment', 
                         'frequency', 'metro', 'zigbee', 'mrni', 'project']
        
        # Ensure all rows have all fields (fill missing with blank)
        for row in output_rows:
            for fn in fieldnames:
                if fn not in row:
                    row[fn] = ''
        
        # Sort output rows by position in natural order (WB1-001, WB1-002, ..., WB1-032, WB2-001, etc)
        # Find the position column (handle different cases)
        position_col = None
        for col in fieldnames:
            if normalize_key(col) == 'position':
                position_col = col
                break
        
        if position_col:
            output_rows.sort(key=lambda row: natural_sort_key(row.get(position_col, '')))
        
        # Update rdate to current date if enabled
        if update_date_bool:
            now = datetime.now()
            current_date = f"{now.month}/{now.day}/{now.year}"
            rdate_col = None
            for col in fieldnames:
                if normalize_key(col) == 'rdate':
                    rdate_col = col
                    break
            if rdate_col:
                for row in output_rows:
                    row[rdate_col] = current_date
                print(f"   [OK] Updated rdate to {current_date} for all records")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)
        print(f"   [OK] Wrote {len(output_rows)} records")
    except Exception as e:
        print(f"[ERROR] Error writing output: {e}")
        sys.exit(1)
    
    # Write removed records to separate file
    removed_file = output_file.replace('.csv', '_removed.csv')
    if removed:
        print(f"\n[*] Writing removed records to {removed_file}...")
        try:
            fieldnames = list(removed[0].keys())
            with open(removed_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(removed)
            print(f"   [OK] Wrote {len(removed)} removed records")
        except Exception as e:
            print(f"[ERROR] Error writing removed records: {e}")
    
    # Write summary
    summary_file = output_file.replace('.csv', '_summary.txt')
    print(f"\n[*] Writing summary to {summary_file}...")
    
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("METER INVENTORY RECONCILIATION SUMMARY\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")
            
            f.write(f"OVERVIEW\n")
            f.write(f"  New inventory file: {new_file}\n")
            f.write(f"  Existing inventory file: {old_file}\n")
            f.write(f"  Output file: {output_file}\n")
            if removed:
                f.write(f"  Removed records file: {removed_file}\n")
            f.write(f"\n")
            
            f.write(f"RESULTS\n")
            f.write(f"  Matched (position updated from new): {len(matched)}\n")
            f.write(f"  Added (new records with position, flexnetid, meterid): {len(added)}\n")
            f.write(f"  No meter (position only, comment='no meter'): {len(no_meter)}\n")
            f.write(f"  Removed (old records not in new): {len(removed)}\n")
            f.write(f"  Total in output: {len(output_rows)} (ALL records from new inventory)\n\n")
            
            if removed:
                f.write("=" * 70 + "\n")
                f.write("REMOVED RECORDS (were in old inventory, not in new)\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"Total removed: {len(removed)}\n")
                f.write(f"See separate file: {removed_file}\n\n")
            else:
                f.write("=" * 70 + "\n")
                f.write("REMOVED RECORDS\n")
                f.write("=" * 70 + "\n")
                f.write("No records removed.\n\n")
            
            if added:
                f.write("=" * 70 + "\n")
                f.write("ADDED RECORDS (in new inventory, not in old)\n")
                f.write("=" * 70 + "\n\n")
                
                new_fieldnames = list(added[0].keys())
                f.write(",".join(new_fieldnames) + "\n")
                for row in added:
                    f.write(",".join(f'"{row.get(fn, "")}"' for fn in new_fieldnames) + "\n")
                f.write(f"\nTotal added: {len(added)}\n\n")
            else:
                f.write("No new records added.\n\n")
            
            if no_meter:
                f.write("=" * 70 + "\n")
                f.write("NO METER RECORDS (position marked as no meter)\n")
                f.write("=" * 70 + "\n\n")
                
                nm_fieldnames = list(no_meter[0].keys())
                f.write(",".join(nm_fieldnames) + "\n")
                for row in no_meter:
                    f.write(",".join(f'"{row.get(fn, "")}"' for fn in nm_fieldnames) + "\n")
                f.write(f"\nTotal no meter: {len(no_meter)}\n\n")
            
            f.write("=" * 70 + "\n")
        
        print(f"   [OK] Summary saved")
    except Exception as e:
        print(f"[WARNING] Could not write summary: {e}")
    
    print("\n[SUCCESS] Reconciliation complete!\n")
    print(f"   [+] Output: {output_file}")
    if removed:
        print(f"   [+] Removed: {removed_file}")
    print(f"   [+] Summary: {summary_file}\n")

def main():
    # Use the variables defined at the top of the file
    output = output_file if output_file else f"reconciled_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    reconcile(new_file, old_file, output)

if __name__ == '__main__':
    main()
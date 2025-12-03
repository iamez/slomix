import os

test_files = [
    '/home/et/.etlegacy/legacy/gamestats/2025-11-04-234716-etl_adlernest-round-2.txt',
    '/home/et/.etlegacy/legacy/gamestats/2025-11-04-232750-erdenberg_t2-round-1.txt',
    '/home/et/.etlegacy/legacy/gamestats/2025-11-04-221205-etl_sp_delivery-round-1.txt',
]

def parse_filename(filename):
    """Parse ET:Legacy stats filename: YYYY-MM-DD-HHMMSS-mapname-round-N.txt"""
    try:
        parts = filename.replace('.txt', '').split('-')
        print(f"  Filename: {filename}")
        print(f"  Parts ({len(parts)}): {parts}")
        
        if len(parts) < 8:
            print("  ❌ Too few parts (need >= 8)")
            return None
        
        date = f"{parts[0]}-{parts[1]}-{parts[2]}"
        time = parts[3]
        map_name = '-'.join(parts[4:-2])  # Handle maps with dashes
        round_num = int(parts[-1])
        
        print(f"  ✅ Date: {date}, Map: {map_name}, Round: {round_num}")
        
        return {
            'date': date,
            'time': time,
            'map': map_name,
            'round': round_num,
            'filename': filename
        }
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

for filepath in test_files:
    basename = os.path.basename(filepath)
    print(f"\nTesting: {basename}")
    parse_filename(basename)

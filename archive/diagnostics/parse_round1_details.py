"""
Parse a Round 1 file to understand team structure.
"""

def parse_round1_file(filepath):
    """Parse and display Round 1 file in detail."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Parse header
    header = lines[0].strip()
    print("HEADER:")
    print(f"  Raw: {header}")
    
    parts = header.split('\\')
    print(f"\n  Header parts breakdown:")
    for i, part in enumerate(parts):
        print(f"    [{i}]: {part}")
    
    if len(parts) >= 8:
        server = parts[0]
        map_name = parts[1]
        mode = parts[2]
        round_num = parts[3]
        score1 = parts[4]
        score2 = parts[5]
        time_limit = parts[6]
        actual_time = parts[7]
        
        print(f"\n  Interpreted:")
        print(f"    Server: {server}")
        print(f"    Map: {map_name}")
        print(f"    Mode: {mode}")
        print(f"    Round: {round_num}")
        print(f"    Score 1 (Axis): {score1}")
        print(f"    Score 2 (Allies): {score2}")
        print(f"    Time Limit: {time_limit}")
        print(f"    Actual Time: {actual_time}")
    
    print("\n" + "="*80)
    print("PLAYERS:")
    print("="*80)
    
    # Parse players
    for idx, line in enumerate(lines[1:], 1):
        if not line.strip():
            continue
        
        parts = line.split('\\')
        if len(parts) < 5:
            print(f"\nPlayer {idx}: NOT ENOUGH FIELDS")
            continue
        
        guid = parts[0]
        name_raw = parts[1]
        field2 = parts[2]
        field3 = parts[3]
        stats_start = parts[4][:50] if len(parts[4]) > 50 else parts[4]
        
        # Clean color codes from name
        import re
        name_clean = re.sub(r'\^\w', '', name_raw)
        
        print(f"\nPlayer {idx}:")
        print(f"  GUID: {guid}")
        print(f"  Name: {name_clean} (raw: {name_raw})")
        print(f"  Field[2]: {field2}")
        print(f"  Field[3]: {field3}")
        print(f"  Stats start: {stats_start}...")
        
        # Try to interpret field[3] as team
        if field3 == '1':
            print(f"  → Team: ALLIES (1)")
        elif field3 == '0':
            print(f"  → Team: AXIS (0)")
        elif field3 == '2':
            print(f"  → Team: SPECTATOR? (2)")
        else:
            print(f"  → Team: UNKNOWN ({field3})")

if __name__ == "__main__":
    import sys
    
    # Parse both Round 1 and Round 2
    files = [
        "local_stats/2025-10-02-211808-etl_adlernest-round-1.txt",
        "local_stats/2025-10-02-212249-etl_adlernest-round-2.txt"
    ]
    
    for filepath in files:
        print("\nANALYZING FILE:")
        print(f"File: {filepath}")
        print("="*80)
        print()
        
        parse_round1_file(filepath)
        print("\n" + "="*80)
        print("="*80)

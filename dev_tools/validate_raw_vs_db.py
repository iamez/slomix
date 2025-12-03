"""
Comprehensive validator to compare raw stats files against database values.
This will identify which fields are not matching 1:1 between source and DB.
"""
import sqlite3
from pathlib import Path
from bot.community_stats_parser import C0RNP0RN3StatsParser
import json
from datetime import datetime, timedelta

def get_db_connection():
    """Get database connection"""
    db_path = Path("bot/etlegacy_production.db")
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return None
    return sqlite3.connect(str(db_path))

def get_recent_files(days=3):
    """Get stats files from last N days"""
    stats_dir = Path("bot/local_stats")
    cutoff = datetime.now() - timedelta(days=days)
    
    files = []
    for file_path in sorted(stats_dir.glob("*.txt")):
        # Extract date from filename: YYYY-MM-DD-HHMMSS-...
        parts = file_path.stem.split('-')
        if len(parts) >= 3:
            try:
                file_date = datetime.strptime('-'.join(parts[:3]), '%Y-%m-%d')
                if file_date >= cutoff:
                    files.append(file_path)
            except:
                pass
    return files

def compare_file_to_db(file_path: Path, parser: C0RNP0RN3StatsParser):
    """Compare one file's data against database"""
    print(f"\n{'='*80}")
    print(f"📂 File: {file_path.name}")
    print(f"{'='*80}")
    
    # Parse the file
    parsed = parser.parse_stats_file(str(file_path))
    if not parsed.get('success'):
        print("❌ Failed to parse file")
        return None
    
    # Extract session info
    filename = file_path.name
    file_date = '-'.join(filename.split('-')[:3])  # YYYY-MM-DD
    map_name = parsed.get('map_name', 'Unknown')
    round_num = parsed.get('round_num', 1)
    
    print(f"📍 Map: {map_name}, Round: {round_num}, Date: {file_date}")
    print(f"👥 Players in file: {len(parsed.get('players', []))}")
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    
    # Find matching session in DB
    cursor.execute("""
        SELECT id FROM gaming_sessions 
        WHERE round_date = ? AND map_name = ? AND round_number = ?
        LIMIT 1
    """, (file_date, map_name, round_num))
    
    session_row = cursor.fetchone()
    if not session_row:
        print("⚠️  Round not found in database")
        conn.close()
        return None
    
    round_id = session_row[0]
    print(f"✅ Found round ID: {round_id}")
    
    # Compare each player
    mismatches = []
    players = parsed.get('players', [])
    
    for player in players:
        player_name = player.get('name', 'Unknown')
        player_guid = player.get('guid', 'UNKNOWN')
        
        # Get player's database record for this session
        cursor.execute("""
            SELECT * FROM player_comprehensive_stats
            WHERE round_id = ? AND player_name = ?
        """, (round_id, player_name))
        
        db_row = cursor.fetchone()
        if not db_row:
            print(f"⚠️  Player '{player_name}' not found in DB for this session")
            continue
        
        # Get column names
        col_names = [desc[0] for desc in cursor.description]
        db_data = dict(zip(col_names, db_row))
        
        # Compare critical fields
        comparisons = []
        
        # Direct player stats
        direct_fields = {
            'kills': player.get('kills'),
            'deaths': player.get('deaths'),
            'damage_given': player.get('damage_given'),
            'damage_received': player.get('damage_received'),
            'headshots': player.get('headshots'),
        }
        
        # Objective stats (from player['objective_stats'])
        obj_stats = player.get('objective_stats', {})
        objective_fields = {
            'team_damage_given': obj_stats.get('team_damage_given'),
            'team_damage_received': obj_stats.get('team_damage_received'),
            'headshot_kills': obj_stats.get('headshot_kills'),
            'gibs': obj_stats.get('gibs'),
            'self_kills': obj_stats.get('self_kills'),
            'team_kills': obj_stats.get('team_kills'),
            'team_gibs': obj_stats.get('team_gibs'),
            'revives_given': obj_stats.get('revives_given'),
            'times_revived': obj_stats.get('times_revived'),
            'kill_assists': obj_stats.get('kill_assists'),
            'objectives_stolen': obj_stats.get('objectives_stolen'),
            'objectives_returned': obj_stats.get('objectives_returned'),
            'dynamites_planted': obj_stats.get('dynamites_planted'),
            'dynamites_defused': obj_stats.get('dynamites_defused'),
        }
        
        # Combine all fields to check
        all_fields = {**direct_fields, **objective_fields}
        
        player_mismatches = []
        for field, file_value in all_fields.items():
            db_value = db_data.get(field)
            
            # Skip if field doesn't exist in DB
            if field not in db_data:
                continue
            
            # Compare values (handle None/0 equivalence)
            file_val = file_value if file_value is not None else 0
            db_val = db_value if db_value is not None else 0
            
            if file_val != db_val:
                player_mismatches.append({
                    'field': field,
                    'file_value': file_val,
                    'db_value': db_val,
                    'diff': db_val - file_val
                })
        
        if player_mismatches:
            mismatches.append({
                'player': player_name,
                'guid': player_guid,
                'mismatches': player_mismatches
            })
    
    conn.close()
    
    # Report results
    if mismatches:
        print(f"\n❌ Found {len(mismatches)} players with mismatched data:")
        for player_mismatch in mismatches:
            print(f"\n  👤 {player_mismatch['player']} ({player_mismatch['guid']})")
            for mismatch in player_mismatch['mismatches']:
                print(f"     ⚠️  {mismatch['field']}: File={mismatch['file_value']}, DB={mismatch['db_value']}, Diff={mismatch['diff']}")
    else:
        print("\n✅ All player data matches between file and database!")
    
    return mismatches

def main():
    """Run validation on recent files"""
    print("🔍 STATS FILE vs DATABASE VALIDATION")
    print("=" * 80)
    print("Comparing raw stats files against database values...")
    print("Looking for mismatches in team damage, headshot kills, and other fields")
    print("=" * 80)
    
    parser = C0RNP0RN3StatsParser()
    
    # Get last 3 days of files
    files = get_recent_files(days=3)
    print(f"\n📁 Found {len(files)} files from last 3 days")
    
    if not files:
        print("❌ No recent files found")
        return
    
    # Validate each file
    all_mismatches = {}
    for file_path in files[-10:]:  # Test last 10 files
        mismatches = compare_file_to_db(file_path, parser)
        if mismatches:
            all_mismatches[file_path.name] = mismatches
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Files checked: {min(10, len(files))}")
    print(f"Files with mismatches: {len(all_mismatches)}")
    
    if all_mismatches:
        print("\n❌ CRITICAL: Found data integrity issues!")
        print("\nMost common mismatched fields:")
        
        # Count field mismatches
        field_counts = {}
        for filename, players in all_mismatches.items():
            for player in players:
                for mismatch in player['mismatches']:
                    field = mismatch['field']
                    field_counts[field] = field_counts.get(field, 0) + 1
        
        for field, count in sorted(field_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {field}: {count} mismatches")
        
        # Save detailed report
        report_path = Path("validation_mismatches_report.json")
        with open(report_path, 'w') as f:
            json.dump(all_mismatches, f, indent=2)
        print(f"\n💾 Detailed report saved to: {report_path}")
    else:
        print("\n✅ All data matches perfectly!")

if __name__ == "__main__":
    main()

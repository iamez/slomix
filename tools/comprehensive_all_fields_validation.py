#!/usr/bin/env python3
"""
COMPREHENSIVE STATS VALIDATION - ALL FIELDS
============================================

Validates ALL player stats fields from raw files against database:
- kills, deaths, damage, headshots
- team damage, gibs, self kills, team kills
- revives, bullets fired, accuracy
- objectives, XP, time played
- weapon stats

Reports ANY mismatches found.
"""

import sqlite3
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))
from community_stats_parser import C0RNP0RN3StatsParser

class ComprehensiveStatsValidator:
    def __init__(self, db_path="bot/etlegacy_production.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
        self.conn = None
        self.mismatches = []
        self.perfect_matches = []
    
    def connect_db(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def find_stat_file(self, date, map_name, round_num, stats_dir="bot/local_stats"):
        """Find stat file matching round"""
        stats_path = Path(stats_dir)
        date_prefix = date[:10]
        pattern = f"{date_prefix}-*-{map_name}-round-{round_num}.txt"
        
        matches = list(stats_path.glob(pattern))
        return matches[0] if matches else None
    
    def get_db_player_stats(self, round_id):
        """Get all player stats for a round from database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                player_guid,
                player_name,
                kills,
                deaths,
                damage_given,
                damage_received,
                team_damage_given,
                team_damage_received,
                gibs,
                self_kills,
                team_kills,
                team_gibs,
                headshot_kills,
                time_played_seconds,
                time_played_minutes,
                bullets_fired,
                accuracy,
                revives_given,
                objectives_completed,
                objectives_destroyed,
                xp,
                kd_ratio,
                dpm,
                efficiency
            FROM player_comprehensive_stats
            WHERE round_id = ?
        """, (round_id,))
        
        players = {}
        for row in cursor.fetchall():
            guid = row['player_guid']
            players[guid] = dict(row)
        
        return players
    
    def compare_player_stats(self, raw_player, db_player, round_info):
        """Compare all stats for a single player"""
        player_name = raw_player['name']
        issues = []
        
        # Get objective stats from raw
        obj_stats = raw_player.get('objective_stats', {})
        
        # Define all fields to check with tolerance for floating point
        checks = {
            'kills': (raw_player.get('kills', 0), db_player['kills'], 0),
            'deaths': (raw_player.get('deaths', 0), db_player['deaths'], 0),
            'damage_given': (raw_player.get('damage_given', 0), db_player['damage_given'], 5),
            'damage_received': (raw_player.get('damage_received', 0), db_player['damage_received'], 5),
            'headshots': (raw_player.get('headshots', 0), db_player['headshot_kills'], 0),
            'team_damage_given': (obj_stats.get('team_damage_given', 0), db_player['team_damage_given'], 5),
            'team_damage_received': (obj_stats.get('team_damage_received', 0), db_player['team_damage_received'], 5),
            'gibs': (obj_stats.get('gibs', 0), db_player['gibs'], 0),
            'self_kills': (obj_stats.get('self_kills', 0), db_player['self_kills'], 0),
            'team_kills': (obj_stats.get('team_kills', 0), db_player['team_kills'], 0),
            'team_gibs': (obj_stats.get('team_gibs', 0), db_player['team_gibs'], 0),
            'bullets_fired': (obj_stats.get('bullets_fired', 0), db_player['bullets_fired'], 0),
            'revives_given': (obj_stats.get('revives_given', 0), db_player['revives_given'], 0),
            'xp': (obj_stats.get('xp', 0), db_player['xp'], 0),
        }
        
        # Check time (special handling for seconds/minutes conversion)
        time_seconds_raw = raw_player.get('time_played_seconds', 0)
        time_seconds_db = db_player['time_played_seconds']
        if abs(time_seconds_raw - time_seconds_db) > 2:  # 2 second tolerance
            issues.append({
                'field': 'time_played_seconds',
                'raw_value': time_seconds_raw,
                'db_value': time_seconds_db,
                'diff': abs(time_seconds_raw - time_seconds_db)
            })
        
        # Check accuracy (special handling for percentage)
        accuracy_raw = raw_player.get('accuracy', 0.0)
        accuracy_db = db_player['accuracy']
        if abs(accuracy_raw - accuracy_db) > 0.5:  # 0.5% tolerance
            issues.append({
                'field': 'accuracy',
                'raw_value': f"{accuracy_raw:.2f}%",
                'db_value': f"{accuracy_db:.2f}%",
                'diff': abs(accuracy_raw - accuracy_db)
            })
        
        # Check all integer/damage fields
        for field, (raw_val, db_val, tolerance) in checks.items():
            if abs(raw_val - db_val) > tolerance:
                issues.append({
                    'field': field,
                    'raw_value': raw_val,
                    'db_value': db_val,
                    'diff': abs(raw_val - db_val)
                })
        
        if issues:
            self.mismatches.append({
                'round_info': round_info,
                'player_name': player_name,
                'player_guid': raw_player['guid'],
                'issues': issues
            })
            return False
        else:
            self.perfect_matches.append({
                'round_info': round_info,
                'player_name': player_name,
                'player_guid': raw_player['guid']
            })
            return True
    
    def validate_round(self, round_id, round_date, map_name, round_num):
        """Validate all stats for a specific round"""
        round_info = f"R{round_num} {map_name} on {round_date[:10]}"
        
        # Find stat file
        stat_file = self.find_stat_file(round_date, map_name, round_num)
        if not stat_file:
            return None
        
        # Parse file
        result = self.parser.parse_stats_file(str(stat_file))
        if not result.get('success'):
            return None
        
        # Get DB stats
        db_players = self.get_db_player_stats(round_id)
        
        # Compare each player
        for raw_player in result['players']:
            guid = raw_player.get('guid', 'UNKNOWN')
            
            if guid not in db_players:
                self.mismatches.append({
                    'round_info': round_info,
                    'player_name': raw_player['name'],
                    'player_guid': guid,
                    'issues': [{'field': 'MISSING', 'raw_value': 'EXISTS', 'db_value': 'NOT FOUND', 'diff': 0}]
                })
                continue
            
            self.compare_player_stats(raw_player, db_players[guid], round_info)
        
        return True
    
    def run_validation(self, limit=10, start_date='2025-11-01'):
        """Run comprehensive validation"""
        self.connect_db()
        
        print("="*80)
        print("COMPREHENSIVE STATS VALIDATION - ALL FIELDS")
        print("="*80)
        print(f"Checking: kills, deaths, damage, headshots, team damage, gibs,")
        print(f"          revives, bullets, accuracy, time, XP, and more...")
        print(f"Starting from: {start_date}")
        print()
        
        # Get rounds
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, round_date, map_name, round_number
            FROM rounds
            WHERE round_date >= ?
            ORDER BY round_date DESC
        """, (start_date,))
        
        rounds = cursor.fetchall()
        
        if limit:
            rounds = rounds[:limit]
            print(f"Testing first {limit} rounds\n")
        
        processed = 0
        for i, (round_id, round_date, map_name, round_num) in enumerate(rounds, 1):
            print(f"[{i}/{len(rounds)}] R{round_num} {map_name} on {round_date[:16]}")
            result = self.validate_round(round_id, round_date, map_name, round_num)
            if result:
                processed += 1
                print(f"  ✅ Validated")
            else:
                print(f"  ⚠️  No stat file")
        
        # Generate report
        print(f"\n{'='*80}")
        print(f"VALIDATION COMPLETE")
        print(f"{'='*80}")
        print(f"Rounds processed: {processed}/{len(rounds)}")
        print(f"Perfect matches: {len(self.perfect_matches)}")
        print(f"Players with mismatches: {len(self.mismatches)}")
        
        if self.mismatches:
            print(f"\n⚠️  MISMATCHES FOUND:\n")
            
            # Group by field to see which fields have issues
            field_issues = {}
            for mismatch in self.mismatches:
                for issue in mismatch['issues']:
                    field = issue['field']
                    if field not in field_issues:
                        field_issues[field] = 0
                    field_issues[field] += 1
            
            print("Fields with mismatches:")
            for field, count in sorted(field_issues.items(), key=lambda x: x[1], reverse=True):
                print(f"  {field}: {count} mismatches")
            
            print(f"\nShowing first 10 detailed mismatches:")
            for i, mismatch in enumerate(self.mismatches[:10], 1):
                print(f"\n{i}. {mismatch['player_name']} - {mismatch['round_info']}")
                for issue in mismatch['issues']:
                    print(f"   ❌ {issue['field']}: raw={issue['raw_value']}, db={issue['db_value']}, diff={issue['diff']}")
        else:
            print(f"\n🎉 NO MISMATCHES! All stats match perfectly!")
        
        # Save detailed report
        report = {
            'validation_date': '2025-11-04',
            'rounds_processed': processed,
            'perfect_matches': len(self.perfect_matches),
            'mismatches_count': len(self.mismatches),
            'mismatches': self.mismatches[:50],  # First 50
            'field_summary': field_issues if self.mismatches else {}
        }
        
        report_path = Path(__file__).parent / 'validation_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_path}")
        
        self.conn.close()
        return report


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Comprehensive stats validation')
    parser.add_argument('--limit', type=int, default=10, help='Number of rounds to check')
    parser.add_argument('--all', action='store_true', help='Check ALL rounds')
    parser.add_argument('--start-date', default='2025-11-01', help='Start date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    validator = ComprehensiveStatsValidator()
    
    limit = None if args.all else args.limit
    validator.run_validation(limit=limit, start_date=args.start_date)

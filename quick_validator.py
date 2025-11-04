"""
Quick Stats Validator - Validates ONLY data that's in the database
Compares raw file data vs database data for actual imported sessions
"""

import sqlite3
import os
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser
from datetime import datetime

class QuickValidator:
    def __init__(self):
        self.db_path = 'bot/etlegacy_production.db'
        self.parser = C0RNP0RN3StatsParser()
        self.stats = {
            'sessions_checked': 0,
            'sessions_matched': 0,
            'players_checked': 0,
            'field_mismatches': 0,
            'issues': []
        }
    
    def validate(self):
        print("="*80)
        print("📊 QUICK STATS VALIDATION")
        print("="*80)
        print()
        
        # Get all sessions from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT round_date, map_name, round_number, id
            FROM rounds
            ORDER BY round_date
        """)
        
        db_sessions = cursor.fetchall()
        print(f"📁 Found {len(db_sessions)} sessions in database\n")
        
        # Check each session
        for round_date, map_name, round_num, round_id in db_sessions:
            filename = f"{round_date}-{map_name}-round-{round_num}.txt"
            filepath = f"bot/local_stats/{filename}"
            
            if not os.path.exists(filepath):
                print(f"❌ {filename}: FILE MISSING")
                self.stats['issues'].append({
                    'file': filename,
                    'type': 'MISSING_FILE',
                    'message': 'Session in database but source file not found'
                })
                continue
            
            # Parse the file
            parsed_data = self.parser.parse_stats_file(filepath)
            
            if not parsed_data.get('success', False):
                print(f"❌ {filename}: PARSE FAILED - {parsed_data.get('error', 'Unknown')}")
                self.stats['issues'].append({
                    'file': filename,
                    'type': 'PARSE_ERROR',
                    'message': parsed_data.get('error', 'Parser failed')
                })
                continue
            
            # Get players from file (parser returns list of players)
            file_players_list = parsed_data.get('players', [])
            
            # Convert to dict for easier comparison
            file_players = {}
            for player in file_players_list:
                player_name = player.get('name', '')
                file_players[player_name] = player
            
            # Get players from database for this session
            cursor.execute("""
                SELECT player_name, kills, deaths, damage_given, damage_received, 
                       time_played_minutes, accuracy, headshot_kills
                FROM player_comprehensive_stats
                WHERE round_id = ?
            """, (round_id,))
            
            db_players = {}
            for row in cursor.fetchall():
                player_name = row[0]
                db_players[player_name] = {
                    'kills': row[1],
                    'deaths': row[2],
                    'damage_given': row[3],
                    'damage_received': row[4],
                    'time_played_minutes': row[5],
                    'accuracy': row[6],
                    'headshot_kills': row[7]
                }
            
            # Compare
            self.stats['sessions_checked'] += 1
            session_ok = True
            
            # Check if same players
            file_player_names = set(file_players.keys())
            db_player_names = set(db_players.keys())
            
            if file_player_names != db_player_names:
                print(f"⚠️  {filename}: Player mismatch")
                print(f"    File has: {len(file_player_names)} players")
                print(f"    DB has: {len(db_player_names)} players")
                if file_player_names - db_player_names:
                    print(f"    Missing in DB: {file_player_names - db_player_names}")
                if db_player_names - file_player_names:
                    print(f"    Extra in DB: {db_player_names - file_player_names}")
                session_ok = False
            else:
                # Check each player's stats
                for player_name in file_player_names:
                    self.stats['players_checked'] += 1
                    file_stats = file_players[player_name]
                    db_stats = db_players[player_name]
                    
                    # Compare key fields
                    mismatches = []
                    
                    if file_stats.get('kills') != db_stats['kills']:
                        mismatches.append(f"kills: file={file_stats.get('kills')} db={db_stats['kills']}")
                    if file_stats.get('deaths') != db_stats['deaths']:
                        mismatches.append(f"deaths: file={file_stats.get('deaths')} db={db_stats['deaths']}")
                    if file_stats.get('damage_given') != db_stats['damage_given']:
                        mismatches.append(f"damage_given: file={file_stats.get('damage_given')} db={db_stats['damage_given']}")
                    
                    if mismatches:
                        print(f"❌ {filename} - {player_name}:")
                        for m in mismatches:
                            print(f"    {m}")
                        self.stats['field_mismatches'] += len(mismatches)
                        session_ok = False
            
            if session_ok:
                self.stats['sessions_matched'] += 1
                print(f"✅ {filename}: OK ({len(file_player_names)} players)")
        
        conn.close()
        
        # Print summary
        print()
        print("="*80)
        print("📊 VALIDATION SUMMARY")
        print("="*80)
        print(f"Sessions checked: {self.stats['sessions_checked']}")
        print(f"Sessions matched: {self.stats['sessions_matched']}")
        print(f"Sessions with issues: {self.stats['sessions_checked'] - self.stats['sessions_matched']}")
        print(f"Players validated: {self.stats['players_checked']}")
        print(f"Field mismatches found: {self.stats['field_mismatches']}")
        print()
        
        if self.stats['sessions_matched'] == self.stats['sessions_checked']:
            print("✅ ALL SESSIONS VALIDATED SUCCESSFULLY!")
        else:
            print("⚠️  Some sessions have discrepancies - review above")
        print()

if __name__ == '__main__':
    validator = QuickValidator()
    validator.validate()

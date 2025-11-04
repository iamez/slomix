#!/usr/bin/env python3
"""
Enhanced Validation with Technical Details
Shows exactly WHERE in database and WHY mismatches occur
Includes R2 differential math verification
"""

import sqlite3
import json
from pathlib import Path
import sys
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser

class TechnicalValidationAnalyzer:
    def __init__(self, db_path="bot/etlegacy_production.db"):
        self.db_path = db_path
        self.parser = C0RNP0RN3StatsParser()
        
    def analyze_mismatch(self, mismatch, validation_data):
        """
        Deep dive into a single mismatch to show:
        1. Raw file values (R2 cumulative)
        2. R1 file values (if R2 round)
        3. Expected R2 differential (R2_cumulative - R1)
        4. Actual database values
        5. Database location (table, columns, round_id)
        """
        round_info = mismatch['round_info']
        player_name = mismatch['player_name']
        player_guid = mismatch['player_guid']
        
        # Parse round info
        parts = round_info.split(' on ')
        round_map_info = parts[0]  # "R2 etl_adlernest"
        date = parts[1]  # "2025-11-02"
        
        round_type = round_map_info.split(' ')[0]  # "R1" or "R2"
        map_name = round_map_info.split(' ', 1)[1]  # "etl_adlernest"
        
        # Get database info
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Find the round in database
        c.execute("""
            SELECT r.id, r.round_date, r.map_name, r.round_number, r.gaming_session_id
            FROM rounds r
            WHERE r.round_date LIKE ? AND r.map_name = ? AND r.round_number = ?
            ORDER BY r.round_date DESC
            LIMIT 1
        """, (f"{date}%", map_name, 2 if round_type == 'R2' else 1))
        
        round_row = c.fetchone()
        if not round_row:
            return {
                'error': 'Round not found in database',
                'player': player_name,
                'round': round_info
            }
        
        round_id, db_date, db_map, db_round_num, gaming_session_id = round_row
        
        # Get player stats from database
        c.execute("""
            SELECT * FROM player_comprehensive_stats
            WHERE round_id = ? AND player_guid = ?
        """, (round_id, player_guid))
        
        db_player = c.fetchone()
        
        # Get column names
        c.execute("PRAGMA table_info(player_comprehensive_stats)")
        columns = {row[1]: row[0] for row in c.fetchall()}
        
        analysis = {
            'player_name': player_name,
            'player_guid': player_guid,
            'round_info': round_info,
            'database_location': {
                'table': 'player_comprehensive_stats',
                'round_id': round_id,
                'gaming_session_id': gaming_session_id,
                'round_date': db_date,
                'map_name': db_map,
                'round_number': db_round_num,
                'player_found': db_player is not None
            },
            'field_analysis': []
        }
        
        if not db_player:
            analysis['error'] = 'MISSING FROM DATABASE'
            conn.close()
            return analysis
        
        # Create dict from database row
        db_dict = {col_name: db_player[col_idx] for col_name, col_idx in columns.items()}
        
        # For each mismatch issue, do detailed analysis
        for issue in mismatch['issues']:
            field = issue['field']
            if field == 'MISSING':
                continue
                
            field_analysis = {
                'field_name': field,
                'raw_value': issue['raw_value'],
                'db_value': issue['db_value'],
                'difference': issue['diff'],
                'db_column_name': self._get_db_column_name(field),
            }
            
            # If R2, show the differential math
            if round_type == 'R2':
                field_analysis['is_round_2'] = True
                field_analysis['differential_math'] = self._calculate_differential_math(
                    date, map_name, player_guid, field
                )
            else:
                field_analysis['is_round_2'] = False
            
            analysis['field_analysis'].append(field_analysis)
        
        conn.close()
        return analysis
    
    def _get_db_column_name(self, validation_field):
        """Map validation field names to database column names"""
        mapping = {
            'kills': 'kills',
            'deaths': 'deaths',
            'headshots': 'headshot_kills',
            'damage_given': 'damage_given',
            'damage_received': 'damage_received',
            'team_damage_given': 'team_damage_given',
            'team_damage_received': 'team_damage_received',
            'gibs': 'gibs',
            'self_kills': 'self_kills',
            'team_kills': 'team_kills',
            'team_gibs': 'team_gibs',
            'bullets_fired': 'bullets_fired',
            'accuracy': 'accuracy',
            'time_played_seconds': 'time_played_seconds',
            'revives_given': 'revives_given',
            'xp': 'xp'
        }
        return mapping.get(validation_field, validation_field)
    
    def _calculate_differential_math(self, date, map_name, player_guid, field):
        """
        For R2 rounds, calculate:
        R2_cumulative (from R2 file) - R1 (from R1 file) = R2_differential (what should be in DB)
        """
        # Find R2 file
        r2_files = list(Path('bot/local_stats').glob(f"{date}*{map_name}*round-2.txt"))
        if not r2_files:
            return {'error': 'R2 file not found'}
        
        r2_file = str(r2_files[0])
        
        # Find R1 file
        r1_files = list(Path('bot/local_stats').glob(f"{date}*{map_name}*round-1.txt"))
        if not r1_files:
            # Try previous day
            date_parts = date.split('-')
            prev_day = int(date_parts[2]) - 1
            prev_date = f"{date_parts[0]}-{date_parts[1]}-{prev_day:02d}"
            r1_files = list(Path('bot/local_stats').glob(f"{prev_date}*{map_name}*round-1.txt"))
        
        if not r1_files:
            return {'error': 'R1 file not found for differential calculation'}
        
        r1_file = str(r1_files[0])
        
        # Parse both files
        r1_result = self.parser.parse_regular_stats_file(r1_file)
        r2_result = self.parser.parse_regular_stats_file(r2_file)
        
        if not r1_result['success'] or not r2_result['success']:
            return {'error': 'Failed to parse files'}
        
        # Find player in both files
        r1_player = next((p for p in r1_result['players'] if p.get('guid') == player_guid), None)
        r2_player = next((p for p in r2_result['players'] if p.get('guid') == player_guid), None)
        
        if not r2_player:
            return {'error': 'Player not found in R2 file'}
        
        # Map field names
        field_map = {
            'kills': 'kills',
            'deaths': 'deaths',
            'headshots': 'headshots',
            'damage_given': 'damage_given',
            'damage_received': 'damage_received',
            'team_damage_given': 'team_damage_given',
            'team_damage_received': 'team_damage_received',
            'gibs': 'gibs',
            'self_kills': 'self_kills',
            'team_kills': 'team_kills',
            'bullets_fired': 'shots_total',
            'time_played_seconds': 'time_played_seconds'
        }
        
        parser_field = field_map.get(field, field)
        
        r2_cumulative_value = r2_player.get(parser_field, 0)
        r1_value = r1_player.get(parser_field, 0) if r1_player else 0
        r2_differential = max(0, r2_cumulative_value - r1_value)
        
        return {
            'r1_file': Path(r1_file).name,
            'r2_file': Path(r2_file).name,
            'r1_value': r1_value,
            'r2_cumulative_value': r2_cumulative_value,
            'r2_differential_expected': r2_differential,
            'formula': f'{r2_cumulative_value} (R2 cumulative) - {r1_value} (R1) = {r2_differential} (R2 differential)',
            'player_in_r1': r1_player is not None
        }
    
    def generate_detailed_report(self, validation_json_path='tools/validation_report.json'):
        """Generate detailed technical analysis for all mismatches"""
        with open(validation_json_path, 'r') as f:
            validation_data = json.load(f)
        
        detailed_report = {
            'summary': {
                'total_mismatches': len(validation_data['mismatches']),
                'validation_date': validation_data['validation_date']
            },
            'detailed_mismatches': []
        }
        
        print(f"Analyzing {len(validation_data['mismatches'])} mismatches...")
        
        for i, mismatch in enumerate(validation_data['mismatches'][:20]):  # First 20 for now
            print(f"[{i+1}/{min(20, len(validation_data['mismatches']))}] {mismatch['player_name']}...")
            analysis = self.analyze_mismatch(mismatch, validation_data)
            detailed_report['detailed_mismatches'].append(analysis)
        
        # Save to file
        output_path = 'tools/detailed_technical_report.json'
        with open(output_path, 'w') as f:
            json.dump(detailed_report, f, indent=2)
        
        print(f"\n✅ Detailed technical report saved to: {output_path}")
        return detailed_report

if __name__ == '__main__':
    analyzer = TechnicalValidationAnalyzer()
    report = analyzer.generate_detailed_report()
    
    print("\n" + "=" * 80)
    print("SAMPLE ANALYSIS:")
    print("=" * 80)
    
    if report['detailed_mismatches']:
        sample = report['detailed_mismatches'][0]
        print(f"\nPlayer: {sample['player_name']}")
        print(f"Database Location:")
        print(f"  - Table: {sample['database_location']['table']}")
        print(f"  - Round ID: {sample['database_location']['round_id']}")
        print(f"  - Date: {sample['database_location']['round_date']}")
        
        if sample.get('field_analysis'):
            print(f"\nField Analysis (first field):")
            field = sample['field_analysis'][0]
            print(f"  - Field: {field['field_name']}")
            print(f"  - DB Column: {field['db_column_name']}")
            print(f"  - Raw: {field['raw_value']}, DB: {field['db_value']}")
            
            if field.get('differential_math'):
                math = field['differential_math']
                if 'formula' in math:
                    print(f"  - Math: {math['formula']}")

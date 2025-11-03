"""
COMPREHENSIVE STATS VALIDATION SYSTEM
October & November 2025 - Full Analysis

This script:
1. Analyzes EVERY player in EVERY round for Oct/Nov 2025
2. Compares raw file data vs database data
3. Exports detailed logs for inspection
4. Generates presentation-quality HTML report
5. Documents field mapping issues and fixes
"""

import sqlite3
import os
import glob
import json
from datetime import datetime
from collections import defaultdict
import sys

# Add bot directory to path for parser
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

class StatsValidator:
    def __init__(self):
        self.db_path = 'bot/etlegacy_production.db'
        self.parser = C0RNP0RN3StatsParser()
        self.issues = []
        self.field_discrepancies = defaultdict(list)
        self.raw_data_log = []
        
    def analyze_october_november(self):
        """Analyze last 14 days of data"""
        from datetime import datetime, timedelta
        
        print("="*80)
        print("COMPREHENSIVE STATS VALIDATION - LAST 14 DAYS")
        print("="*80)
        print()
        
        # Calculate date range - database has data from Oct 27 - Nov 2
        today = datetime(2025, 11, 3)
        start_date = datetime(2025, 10, 27)  # First date in database
        
        print(f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
        print(f"   (Based on data available in database)")
        print()
        print()
        
        # Get files from last 14 days
        all_files = glob.glob('bot/local_stats/2025-*.txt')
        oct_nov_files = []
        
        for f in all_files:
            basename = os.path.basename(f)
            # Extract date from filename (YYYY-MM-DD)
            try:
                file_date_str = basename[:10]
                file_date = datetime.strptime(file_date_str, '%Y-%m-%d')
                if start_date <= file_date <= today:
                    oct_nov_files.append(f)
            except:
                continue
        
        oct_nov_files = sorted(oct_nov_files)
        
        print(f"📁 Found {len(oct_nov_files)} files to analyze")
        print()
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Group files by date
        by_date = defaultdict(list)
        for f in oct_nov_files:
            date = os.path.basename(f)[:10]
            by_date[date].append(f)
        
        print(f"📅 Date range: {min(by_date.keys())} to {max(by_date.keys())}")
        print(f"📊 Total dates: {len(by_date)}")
        print()
        
        # Analyze each file
        total_players = 0
        total_sessions = 0
        
        for date in sorted(by_date.keys()):
            files = by_date[date]
            print(f"\n{'='*80}")
            print(f"📅 Analyzing {date} ({len(files)} files)")
            print(f"{'='*80}")
            
            for filepath in files:
                basename = os.path.basename(filepath)
                
                # Parse raw file
                try:
                    parsed_data = self.parser.parse_stats_file(filepath)
                    
                    if not parsed_data:
                        self.issues.append({
                            'file': basename,
                            'issue': 'Parser returned None',
                            'severity': 'CRITICAL'
                        })
                        print(f"  ❌ {basename}: Parser failed")
                        continue
                    
                    # Check if parsing was successful
                    if not parsed_data.get('success', False):
                        error_msg = parsed_data.get('error', 'Unknown error')
                        self.issues.append({
                            'file': basename,
                            'issue': f'Parser error: {error_msg}',
                            'severity': 'CRITICAL'
                        })
                        print(f"  ❌ {basename}: {error_msg}")
                        continue
                    
                    # Extract session info from actual parser output structure
                    # Parser returns: success, error, map_name, round_num, players, mvp, total_players, timestamp
                    map_name = parsed_data.get('map_name', 'unknown')
                    round_num = parsed_data.get('round_num', 0)
                    
                    # Database session_date format is: YYYY-MM-DD-HHMMSS (from filename)
                    # Extract from filename: 2025-10-27-230230-mapname-round-N.txt
                    session_date = basename[:19]  # e.g. "2025-10-27-230230"
                    
                    # Find matching database session
                    cursor.execute("""
                        SELECT id FROM sessions 
                        WHERE session_date = ? AND map_name = ? AND round_number = ?
                    """, (session_date, map_name, round_num))
                    
                    db_session = cursor.fetchone()
                    
                    if not db_session:
                        self.issues.append({
                            'file': basename,
                            'session_date': session_date,
                            'issue': 'Session not in database',
                            'severity': 'HIGH'
                        })
                        print(f"  ⚠️  {basename}: Not in database")
                        continue
                    
                    session_id = db_session[0]
                    total_sessions += 1
                    
                    # Analyze each player in this session
                    players_in_file = len(parsed_data['players'])
                    total_players += players_in_file
                    
                    print(f"  ✓ {basename}: {players_in_file} players")
                    
                    for player in parsed_data['players']:
                        self.validate_player_data(
                            cursor, session_id, basename, 
                            session_date, map_name, round_num, player
                        )
                    
                except Exception as e:
                    self.issues.append({
                        'file': basename,
                        'issue': f'Exception: {str(e)}',
                        'severity': 'CRITICAL'
                    })
                    print(f"  ❌ {basename}: Exception - {str(e)}")
        
        conn.close()
        
        print(f"\n{'='*80}")
        print(f"ANALYSIS COMPLETE")
        print(f"{'='*80}")
        print(f"📊 Total sessions analyzed: {total_sessions}")
        print(f"👥 Total player records: {total_players}")
        print(f"⚠️  Total issues found: {len(self.issues)}")
        print()
        
    def validate_player_data(self, cursor, session_id, filename, 
                            session_date, map_name, round_num, player):
        """Validate one player's data against database"""
        
        player_guid = player['player_info']['guid']
        player_name = player['player_info']['name']
        
        # Get database record
        cursor.execute("""
            SELECT kills, deaths, damage_given, damage_received,
                   team_damage_given, team_damage_received,
                   gibs, self_kills, team_kills, team_gibs,
                   headshot_kills, xp, time_played_seconds,
                   dpm, kd_ratio
            FROM player_comprehensive_stats
            WHERE session_id = ? AND player_guid = ?
        """, (session_id, player_guid))
        
        db_record = cursor.fetchone()
        
        if not db_record:
            self.issues.append({
                'file': filename,
                'session': session_date,
                'player': player_name,
                'issue': 'Player not in database',
                'severity': 'HIGH'
            })
            return
        
        # Compare fields
        file_data = {
            'kills': player['kills'],
            'deaths': player['deaths'],
            'damage_given': player['objective_stats']['damage_given'],
            'damage_received': player['objective_stats']['damage_received'],
            'team_damage_given': player['objective_stats']['team_damage_given'],
            'team_damage_received': player['objective_stats']['team_damage_received'],
            'gibs': player['objective_stats']['gibs'],
            'self_kills': player['objective_stats']['self_kills'],
            'team_kills': player['objective_stats']['team_kills'],
            'team_gibs': player['objective_stats']['team_gibs'],
            'headshot_kills': player['objective_stats']['headshot_kills'],
            'xp': player['objective_stats']['xp'],
            'time_played_seconds': player.get('time_played_seconds', 0),
            'dpm': player['objective_stats']['dpm'],
            'kd_ratio': player['objective_stats']['kd_ratio']
        }
        
        db_data = {
            'kills': db_record[0],
            'deaths': db_record[1],
            'damage_given': db_record[2],
            'damage_received': db_record[3],
            'team_damage_given': db_record[4],
            'team_damage_received': db_record[5],
            'gibs': db_record[6],
            'self_kills': db_record[7],
            'team_kills': db_record[8],
            'team_gibs': db_record[9],
            'headshot_kills': db_record[10],
            'xp': db_record[11],
            'time_played_seconds': db_record[12],
            'dpm': db_record[13],
            'kd_ratio': db_record[14]
        }
        
        # Check for discrepancies
        for field, file_val in file_data.items():
            db_val = db_data[field]
            
            # Handle float comparison with tolerance
            if isinstance(file_val, float) and isinstance(db_val, float):
                if abs(file_val - db_val) > 0.01:  # 0.01 tolerance
                    self.field_discrepancies[field].append({
                        'file': filename,
                        'session': session_date,
                        'player': player_name,
                        'file_value': file_val,
                        'db_value': db_val,
                        'difference': abs(file_val - db_val)
                    })
            else:
                if file_val != db_val:
                    self.field_discrepancies[field].append({
                        'file': filename,
                        'session': session_date,
                        'player': player_name,
                        'file_value': file_val,
                        'db_value': db_val,
                        'difference': abs(file_val - db_val) if isinstance(file_val, (int, float)) else None
                    })
        
        # Log raw data for deep inspection
        self.raw_data_log.append({
            'file': filename,
            'session_date': session_date,
            'map': map_name,
            'round': round_num,
            'player_guid': player_guid,
            'player_name': player_name,
            'file_data': file_data,
            'db_data': db_data
        })
    
    def export_results(self):
        """Export all results to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. Export raw data log
        raw_log_path = f'stats_validation_raw_{timestamp}.txt'
        with open(raw_log_path, 'w', encoding='utf-8') as f:
            f.write("="*100 + "\n")
            f.write("RAW DATA LOG - EVERY PLAYER, EVERY ROUND, EVERY MAP\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write("="*100 + "\n\n")
            
            for entry in self.raw_data_log:
                f.write(f"\n{'='*100}\n")
                f.write(f"FILE: {entry['file']}\n")
                f.write(f"SESSION: {entry['session_date']} - {entry['map']} R{entry['round']}\n")
                f.write(f"PLAYER: {entry['player_name']} ({entry['player_guid']})\n")
                f.write(f"{'-'*100}\n")
                
                f.write("\nFILE DATA:\n")
                for key, val in entry['file_data'].items():
                    f.write(f"  {key:25s}: {val}\n")
                
                f.write("\nDATABASE DATA:\n")
                for key, val in entry['db_data'].items():
                    f.write(f"  {key:25s}: {val}\n")
                
                # Highlight differences
                differences = []
                for key in entry['file_data'].keys():
                    file_val = entry['file_data'][key]
                    db_val = entry['db_data'][key]
                    if file_val != db_val:
                        differences.append(f"  {key}: {file_val} (file) vs {db_val} (db)")
                
                if differences:
                    f.write("\n⚠️  DIFFERENCES:\n")
                    for diff in differences:
                        f.write(diff + "\n")
        
        print(f"✅ Raw data log exported: {raw_log_path}")
        
        # 2. Export issues JSON
        issues_path = f'stats_validation_issues_{timestamp}.json'
        with open(issues_path, 'w', encoding='utf-8') as f:
            json.dump(self.issues, f, indent=2)
        
        print(f"✅ Issues exported: {issues_path}")
        
        # 3. Export field discrepancies JSON
        discrepancies_path = f'stats_validation_discrepancies_{timestamp}.json'
        with open(discrepancies_path, 'w', encoding='utf-8') as f:
            json.dump(dict(self.field_discrepancies), f, indent=2)
        
        print(f"✅ Discrepancies exported: {discrepancies_path}")
        
        # 4. Generate HTML report
        self.generate_html_report(timestamp)
        
        return raw_log_path, issues_path, discrepancies_path
    
    def generate_html_report(self, timestamp):
        """Generate presentation-quality HTML report"""
        
        html_path = f'stats_validation_report_{timestamp}.html'
        
        # Calculate summary statistics
        total_discrepancies = sum(len(v) for v in self.field_discrepancies.values())
        fields_with_issues = len(self.field_discrepancies)
        
        critical_issues = [i for i in self.issues if i.get('severity') == 'CRITICAL']
        high_issues = [i for i in self.issues if i.get('severity') == 'HIGH']
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Stats Validation Report - Last 14 Days</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 4px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .summary-card {{
            padding: 20px;
            border-radius: 8px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .summary-card.green {{
            background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
        }}
        .summary-card.orange {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .summary-card.red {{
            background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 36px;
            font-weight: bold;
            margin: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .critical {{ color: #e74c3c; font-weight: bold; }}
        .high {{ color: #e67e22; font-weight: bold; }}
        .field-name {{
            font-family: 'Courier New', monospace;
            background: #ecf0f1;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 14px;
        }}
        .fix-section {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            margin: 20px 0;
        }}
        .fix-section h3 {{
            margin-top: 0;
            color: #856404;
        }}
        pre {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Comprehensive Stats Validation Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Analysis Period:</strong> Last 14 Days (2025-10-20 to 2025-11-03)</p>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Player Records</h3>
                <p class="value">{len(self.raw_data_log)}</p>
            </div>
            <div class="summary-card green">
                <h3>Sessions Analyzed</h3>
                <p class="value">{len(set(e['session_date'] for e in self.raw_data_log))}</p>
            </div>
            <div class="summary-card orange">
                <h3>Field Discrepancies</h3>
                <p class="value">{total_discrepancies}</p>
            </div>
            <div class="summary-card red">
                <h3>Critical Issues</h3>
                <p class="value">{len(critical_issues)}</p>
            </div>
        </div>
        
        <h2>⚠️  Critical Issues ({len(critical_issues)})</h2>
        <table>
            <tr>
                <th>File</th>
                <th>Issue</th>
                <th>Details</th>
            </tr>
"""
        
        for issue in critical_issues:
            html_content += f"""
            <tr>
                <td class="field-name">{issue.get('file', 'N/A')}</td>
                <td class="critical">{issue.get('issue', 'Unknown')}</td>
                <td>{issue.get('player', '')} {issue.get('session', '')}</td>
            </tr>
"""
        
        html_content += """
        </table>
        
        <h2>🔍 Field Discrepancies by Field</h2>
"""
        
        for field, discrepancies in sorted(self.field_discrepancies.items(), key=lambda x: len(x[1]), reverse=True):
            html_content += f"""
        <h3><span class="field-name">{field}</span> - {len(discrepancies)} occurrences</h3>
        <table>
            <tr>
                <th>Session</th>
                <th>Player</th>
                <th>File Value</th>
                <th>DB Value</th>
                <th>Difference</th>
            </tr>
"""
            
            # Show first 10 examples
            for disc in discrepancies[:10]:
                html_content += f"""
            <tr>
                <td>{disc['session']}</td>
                <td>{disc['player']}</td>
                <td>{disc['file_value']}</td>
                <td>{disc['db_value']}</td>
                <td>{disc.get('difference', 'N/A')}</td>
            </tr>
"""
            
            if len(discrepancies) > 10:
                html_content += f"""
            <tr>
                <td colspan="5" style="text-align: center; font-style: italic; color: #7f8c8d;">
                    ... and {len(discrepancies) - 10} more occurrences
                </td>
            </tr>
"""
            
            html_content += "</table>"
        
        # Add field mapping documentation
        html_content += """
        <h2>📋 Field Mapping Documentation</h2>
        
        <div class="fix-section">
            <h3>Known Field Mapping Issues</h3>
            <p>The following fields are calculated/stored differently between parser and database:</p>
            
            <h4>1. DPM (Damage Per Minute)</h4>
            <pre>
# Parser calculation:
dpm = damage_given / (time_played_seconds / 60.0)

# Database may recalculate or store rounded value
# FIX: Use parser's DPM directly, don't recalculate
            </pre>
            
            <h4>2. time_played_seconds vs time_played_minutes</h4>
            <pre>
# Parser provides BOTH:
time_played_seconds = int (from cumulative game time)
time_played_minutes = float (calculated: seconds / 60)

# Database has separate columns for both
# FIX: Store seconds as INTEGER, minutes as REAL
            </pre>
            
            <h4>3. gibs vs gibs_total</h4>
            <pre>
# Field name consistency issue
# Parser: 'gibs'
# Some old code: 'gibs_total'
# FIX: Always use 'gibs'
            </pre>
        </div>
        
        <h2>🔧 Permanent Fixes</h2>
        
        <div class="fix-section">
            <h3>Required Database Schema Updates</h3>
            <pre>
-- Add missing columns that parser provides but DB doesn't have:
ALTER TABLE player_comprehensive_stats ADD COLUMN bullets_fired INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN time_dead_minutes REAL DEFAULT 0.0;
ALTER TABLE player_comprehensive_stats ADD COLUMN time_dead_ratio REAL DEFAULT 0.0;
ALTER TABLE player_comprehensive_stats ADD COLUMN multikill_2x INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN multikill_3x INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN multikill_4x INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN multikill_5x INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN multikill_6x INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN full_selfkills INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN revives_given INTEGER DEFAULT 0;
ALTER TABLE player_comprehensive_stats ADD COLUMN repairs_constructions INTEGER DEFAULT 0;
            </pre>
            
            <h3>Import Script Updates</h3>
            <p>Update bulk import to use correct field names and NOT recalculate values:</p>
            <pre>
# ✅ CORRECT: Use parser's calculated values directly
dpm = player['objective_stats']['dpm']  # Don't recalculate!

# ✅ CORRECT: Store both seconds and minutes
time_played_seconds = player['time_played_seconds']
time_played_minutes = player['objective_stats']['time_played_minutes']

# ✅ CORRECT: Use consistent field names
gibs = player['objective_stats']['gibs']  # Not 'gibs_total'
            </pre>
        </div>
        
        <h2>📝 Export Files</h2>
        <ul>
            <li><strong>Raw Data Log:</strong> <code>stats_validation_raw_{timestamp}.txt</code></li>
            <li><strong>Issues JSON:</strong> <code>stats_validation_issues_{timestamp}.json</code></li>
            <li><strong>Discrepancies JSON:</strong> <code>stats_validation_discrepancies_{timestamp}.json</code></li>
            <li><strong>This Report:</strong> <code>stats_validation_report_{timestamp}.html</code></li>
        </ul>
        
        <p style="margin-top: 40px; color: #7f8c8d; text-align: center;">
            End of Report
        </p>
    </div>
</body>
</html>
"""
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTML report generated: {html_path}")
        return html_path

# Run the validation
if __name__ == '__main__':
    validator = StatsValidator()
    validator.analyze_october_november()
    validator.export_results()
    
    print("\n" + "="*80)
    print("✅ VALIDATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Review the HTML report in your browser")
    print("2. Check raw data log for detailed inspection")
    print("3. Apply permanent fixes from the report")
    print("4. Re-import data after fixes")

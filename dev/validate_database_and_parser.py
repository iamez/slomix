#!/usr/bin/env python3
"""
Database and Parser Validation Tool
====================================
Purpose: Inspect existing databases, validate parser accuracy, and prepare for bulk import

This tool will:
1. Examine all .db files in the workspace
2. Test parser with 2025 stat files
3. Validate field mappings
4. Report on data quality
5. Recommend next steps

Created: October 3, 2025
Location: /dev folder (as per ground rules)
"""

import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

class DatabaseValidator:
    """Comprehensive database and parser validation"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent.parent
        self.parser = C0RNP0RN3StatsParser()
        self.results = {
            'databases': [],
            'parser_tests': [],
            'recommendations': [],
            'issues': []
        }
    
    def find_all_databases(self):
        """Find all .db files in the workspace"""
        print("\n" + "="*70)
        print("🔍 SCANNING FOR DATABASE FILES")
        print("="*70)
        
        db_files = list(self.base_path.glob("**/*.db"))
        
        for db_file in db_files:
            print(f"\n📁 Found: {db_file.name}")
            print(f"   Location: {db_file.relative_to(self.base_path)}")
            print(f"   Size: {db_file.stat().st_size / 1024:.2f} KB")
            print(f"   Modified: {datetime.fromtimestamp(db_file.stat().st_mtime)}")
            
            # Inspect database structure
            db_info = self.inspect_database(str(db_file))
            self.results['databases'].append(db_info)
    
    def inspect_database(self, db_path: str) -> dict:
        """Inspect a single database file"""
        db_info = {
            'path': db_path,
            'name': Path(db_path).name,
            'tables': [],
            'row_counts': {},
            'schema': {}
        }
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            print(f"   Tables found: {len(tables)}")
            
            for (table_name,) in tables:
                db_info['tables'].append(table_name)
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                db_info['row_counts'][table_name] = row_count
                
                print(f"      • {table_name}: {row_count} rows")
                
                # Get schema
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                db_info['schema'][table_name] = [
                    {'name': col[1], 'type': col[2], 'notnull': col[3], 'pk': col[5]}
                    for col in columns
                ]
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"   ❌ Error: {e}")
            db_info['error'] = str(e)
            self.results['issues'].append(f"Database error in {Path(db_path).name}: {e}")
        
        return db_info
    
    def test_parser_with_2025_files(self):
        """Test parser with recent 2025 stat files"""
        print("\n" + "="*70)
        print("🧪 TESTING PARSER WITH 2025 FILES")
        print("="*70)
        
        local_stats = self.base_path / "local_stats"
        
        # Find 2025 files
        stat_files_2025 = sorted(local_stats.glob("2025-*.txt"))
        
        print(f"\n📊 Found {len(stat_files_2025)} files from 2025")
        
        # Test with first 5 files
        test_files = stat_files_2025[:5]
        
        for stat_file in test_files:
            print(f"\n📄 Testing: {stat_file.name}")
            result = self.test_single_file(str(stat_file))
            self.results['parser_tests'].append(result)
    
    def test_single_file(self, file_path: str) -> dict:
        """Test parser on a single file"""
        result = {
            'filename': Path(file_path).name,
            'path': file_path,
            'success': False,
            'players': 0,
            'weapons_found': 0,
            'fields_extracted': {},
            'issues': []
        }
        
        try:
            # Parse the file
            parsed = self.parser.parse_stats_file(file_path)
            
            if parsed.get('error'):
                result['issues'].append(f"Parse error: {parsed['error']}")
                print(f"   ❌ Parse failed: {parsed['error']}")
                return result
            
            result['success'] = True
            result['players'] = len(parsed.get('players', []))
            result['map_name'] = parsed.get('map_name', 'Unknown')
            result['round_num'] = parsed.get('round_num', 0)
            
            print(f"   ✅ Parsed successfully")
            print(f"   📍 Map: {result['map_name']}")
            print(f"   🎮 Round: {result['round_num']}")
            print(f"   👥 Players: {result['players']}")
            
            # Analyze first player in detail
            if result['players'] > 0:
                player = parsed['players'][0]
                print(f"\n   🔍 First player analysis: {player['name']}")
                print(f"      GUID: {player['guid']}")
                print(f"      Team: {player['team']}")
                print(f"      K/D: {player['kills']}/{player['deaths']} ({player.get('kd_ratio', 0):.2f})")
                print(f"      Damage: {player.get('damage_given', 0)} dealt / {player.get('damage_received', 0)} taken")
                
                # Check weapon stats
                weapon_stats = player.get('weapon_stats', {})
                result['weapons_found'] = len(weapon_stats)
                print(f"      Weapons used: {result['weapons_found']}")
                
                # Sample a few weapons
                for i, (weapon, stats) in enumerate(list(weapon_stats.items())[:3]):
                    if stats['shots'] > 0 or stats['kills'] > 0:
                        print(f"         • {weapon}: {stats['kills']}K / {stats['shots']} shots ({stats['accuracy']:.1f}%)")
                
                # Check extended stats presence
                extended_fields = [
                    'killing_spree_best', 'death_spree_worst', 'kill_assists',
                    'headshot_kills', 'objectives_stolen', 'dynamites_planted',
                    'double_kills', 'triple_kills', 'dpm'
                ]
                
                print(f"\n      📊 Extended stats check:")
                for field in extended_fields:
                    value = player.get(field, 'MISSING')
                    result['fields_extracted'][field] = value
                    if value != 'MISSING' and value != 0:
                        print(f"         ✓ {field}: {value}")
        
        except Exception as e:
            result['issues'].append(f"Exception: {str(e)}")
            print(f"   ❌ Exception: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def analyze_local_stats_folder(self):
        """Analyze the local_stats folder"""
        print("\n" + "="*70)
        print("📂 ANALYZING LOCAL_STATS FOLDER")
        print("="*70)
        
        local_stats = self.base_path / "local_stats"
        
        if not local_stats.exists():
            print("   ❌ local_stats folder not found!")
            return
        
        all_files = list(local_stats.glob("*.txt"))
        files_2024 = [f for f in all_files if f.name.startswith("2024-")]
        files_2025 = [f for f in all_files if f.name.startswith("2025-")]
        
        print(f"\n📊 Total stat files: {len(all_files)}")
        print(f"   📅 2024 files: {len(files_2024)}")
        print(f"   📅 2025 files: {len(files_2025)}")
        
        # Analyze file naming patterns
        print(f"\n🔍 File naming analysis:")
        round_1_files = [f for f in all_files if "-round-1.txt" in f.name]
        round_2_files = [f for f in all_files if "-round-2.txt" in f.name]
        
        print(f"   Round 1 files: {len(round_1_files)}")
        print(f"   Round 2 files: {len(round_2_files)}")
        
        # Extract map names
        maps = set()
        for f in files_2025:
            parts = f.name.split('-')
            if len(parts) >= 6:
                map_name = '-'.join(parts[4:-2])
                maps.add(map_name)
        
        print(f"\n🗺️  Unique maps in 2025 files: {len(maps)}")
        for map_name in sorted(maps):
            count = len([f for f in files_2025 if map_name in f.name])
            print(f"      • {map_name}: {count} files")
    
    def generate_recommendations(self):
        """Generate recommendations based on findings"""
        print("\n" + "="*70)
        print("💡 RECOMMENDATIONS")
        print("="*70)
        
        # Database recommendations
        db_count = len(self.results['databases'])
        
        if db_count == 0:
            rec = "🆕 Create new production database with comprehensive schema"
            print(f"\n{rec}")
            self.results['recommendations'].append(rec)
        elif db_count > 3:
            rec = "⚠️  Multiple databases found - consolidate to single production DB"
            print(f"\n{rec}")
            self.results['recommendations'].append(rec)
        
        # Check if any database has data
        has_data = False
        for db_info in self.results['databases']:
            if any(count > 0 for count in db_info.get('row_counts', {}).values()):
                has_data = True
                break
        
        if not has_data:
            rec = "📥 All databases are empty - bulk import needed"
            print(f"{rec}")
            self.results['recommendations'].append(rec)
        
        # Parser test recommendations
        successful_tests = sum(1 for t in self.results['parser_tests'] if t['success'])
        total_tests = len(self.results['parser_tests'])
        
        if total_tests > 0:
            print(f"\n📊 Parser test results: {successful_tests}/{total_tests} successful")
            
            if successful_tests == total_tests:
                rec = "✅ Parser working correctly - ready for bulk import"
                print(f"{rec}")
                self.results['recommendations'].append(rec)
            else:
                rec = "⚠️  Parser has issues - needs fixing before import"
                print(f"{rec}")
                self.results['recommendations'].append(rec)
        
        # Next steps
        print(f"\n🚀 NEXT STEPS:")
        print(f"   1. Create production database: etlegacy_production.db")
        print(f"   2. Build bulk import tool with progress tracking")
        print(f"   3. Import all 2025 files first (testing)")
        print(f"   4. Verify data integrity")
        print(f"   5. Import 2024 files (complete archive)")
        print(f"   6. Implement Discord commands")
    
    def save_report(self):
        """Save validation report to JSON"""
        report_path = self.base_path / "dev" / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n💾 Full report saved to: {report_path.name}")
    
    def run_full_validation(self):
        """Run complete validation suite"""
        print("\n" + "="*70)
        print("🚀 ET:LEGACY DISCORD BOT - VALIDATION SUITE")
        print("="*70)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Step 1: Find and inspect databases
            self.find_all_databases()
            
            # Step 2: Analyze local_stats folder
            self.analyze_local_stats_folder()
            
            # Step 3: Test parser
            self.test_parser_with_2025_files()
            
            # Step 4: Generate recommendations
            self.generate_recommendations()
            
            # Step 5: Save report
            self.save_report()
            
            print("\n" + "="*70)
            print("✅ VALIDATION COMPLETE")
            print("="*70)
            
            # Summary
            print(f"\n📊 SUMMARY:")
            print(f"   Databases found: {len(self.results['databases'])}")
            print(f"   Parser tests run: {len(self.results['parser_tests'])}")
            print(f"   Issues found: {len(self.results['issues'])}")
            print(f"   Recommendations: {len(self.results['recommendations'])}")
            
            if self.results['issues']:
                print(f"\n⚠️  ISSUES DETECTED:")
                for issue in self.results['issues']:
                    print(f"   • {issue}")
        
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True


if __name__ == "__main__":
    validator = DatabaseValidator()
    success = validator.run_full_validation()
    sys.exit(0 if success else 1)

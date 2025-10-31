#!/usr/bin/env python3
"""
Comprehensive Database & Code Audit
Find all potential issues before they cause problems
"""

import sqlite3
import os
import glob

print("\n" + "="*80)
print("🔍 COMPREHENSIVE SYSTEM AUDIT - October 7, 2025")
print("="*80)

issues = []
warnings = []
successes = []

# ============================================================================
# 1. DATABASE SCHEMA CHECK
# ============================================================================
print("\n📊 DATABASE SCHEMA VALIDATION")
print("-" * 80)

if not os.path.exists('etlegacy_production.db'):
    issues.append("❌ CRITICAL: etlegacy_production.db NOT FOUND")
else:
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()
    
    # Check player_comprehensive_stats
    cursor.execute('PRAGMA table_info(player_comprehensive_stats)')
    player_cols = cursor.fetchall()
    actual_count = len(player_cols)
    
    # Note: SQLite returns id + 52 other columns = 53 total
    if actual_count == 53:
        successes.append("✅ player_comprehensive_stats: 53 columns (CORRECT)")
    elif actual_count == 54:
        successes.append("✅ player_comprehensive_stats: 54 columns (id + 53 fields)")
    else:
        issues.append(f"❌ player_comprehensive_stats: {actual_count} columns (EXPECTED 53)")
    
    # Check required tables
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    tables = [t[0] for t in cursor.fetchall()]
    
    required_tables = ['sessions', 'player_comprehensive_stats', 
                      'weapon_comprehensive_stats', 'player_links', 
                      'session_teams', 'processed_files']
    
    for table in required_tables:
        if table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            successes.append(f"✅ {table}: {count} records")
        else:
            if table == 'session_teams':
                warnings.append(f"⚠️  {table}: MISSING (causes 'No hardcoded teams' warning)")
            else:
                issues.append(f"❌ {table}: MISSING (CRITICAL)")
    
    conn.close()

# ============================================================================
# 2. DATABASE CREATION SCRIPTS CHECK
# ============================================================================
print("\n🏗️  DATABASE CREATION SCRIPTS")
print("-" * 80)

# Check for conflicting scripts
if os.path.exists('create_unified_database.py'):
    successes.append("✅ create_unified_database.py found (ROOT - 53 cols)")
if os.path.exists('tools/create_fresh_database.py'):
    warnings.append("⚠️  tools/create_fresh_database.py exists (60 cols - DON'T USE FOR BOT)")

# ============================================================================
# 3. BOT CONFIGURATION CHECK
# ============================================================================
print("\n🤖 BOT CONFIGURATION")
print("-" * 80)

if os.path.exists('.env'):
    with open('.env', 'r') as f:
        env_content = f.read()
        
        # Check critical settings
        if 'DISCORD_BOT_TOKEN=' in env_content:
            successes.append("✅ DISCORD_BOT_TOKEN configured")
        else:
            issues.append("❌ DISCORD_BOT_TOKEN missing in .env")
        
        if 'SSH_ENABLED=true' in env_content:
            successes.append("✅ SSH monitoring enabled")
        elif 'SSH_ENABLED=false' in env_content:
            warnings.append("⚠️  SSH monitoring disabled")
        else:
            warnings.append("⚠️  SSH_ENABLED not set in .env")
else:
    issues.append("❌ .env file NOT FOUND")

# ============================================================================
# 4. LOCAL STATS FILES CHECK
# ============================================================================
print("\n📁 LOCAL STATS FILES")
print("-" * 80)

if os.path.exists('local_stats'):
    stats_files = glob.glob('local_stats/*.txt')
    # Exclude weapon stats files
    game_files = [f for f in stats_files if not f.endswith('_ws.txt')]
    
    if len(game_files) > 0:
        successes.append(f"✅ local_stats/: {len(game_files)} game stats files")
    else:
        warnings.append("⚠️  local_stats/: NO game stats files found")
        warnings.append("   (Bot won't re-download already processed files)")
else:
    issues.append("❌ local_stats/ directory NOT FOUND")

# ============================================================================
# 5. IMPORT SCRIPT CHECK
# ============================================================================
print("\n📥 IMPORT SCRIPTS")
print("-" * 80)

if os.path.exists('tools/simple_bulk_import.py'):
    successes.append("✅ tools/simple_bulk_import.py exists")
    
    # Check if it references the correct database
    try:
        with open('tools/simple_bulk_import.py', 'r', encoding='utf-8') as f:
            content = f.read()
            if 'etlegacy_production.db' in content:
                successes.append("✅ Import script targets etlegacy_production.db")
            else:
                issues.append("❌ Import script may target wrong database")
    except UnicodeDecodeError:
        warnings.append("⚠️  Could not read import script (encoding issue)")
else:
    issues.append("❌ tools/simple_bulk_import.py NOT FOUND")

# ============================================================================
# 6. BOT FILE CHECK
# ============================================================================
print("\n🤖 BOT FILES")
print("-" * 80)

if os.path.exists('bot/ultimate_bot.py'):
    successes.append("✅ bot/ultimate_bot.py exists")
    
    # Check bot database path
    with open('bot/ultimate_bot.py', 'r', encoding='utf-8') as f:
        bot_content = f.read()
        
        if 'etlegacy_production.db' in bot_content:
            successes.append("✅ Bot uses etlegacy_production.db")
        
        if 'validate_database_schema' in bot_content:
            successes.append("✅ Bot has schema validation")
        
        if 'session_teams' in bot_content:
            successes.append("✅ Bot has session_teams support")
else:
    issues.append("❌ bot/ultimate_bot.py NOT FOUND")

# ============================================================================
# 7. POTENTIAL BUGS PREDICTION
# ============================================================================
print("\n🐛 POTENTIAL BUGS ANALYSIS")
print("-" * 80)

# Check if bot is currently running
import subprocess
try:
    result = subprocess.run(['powershell', '-Command', 
                           'Get-Process python | Select-Object -Property Id, Path'],
                          capture_output=True, text=True, timeout=5)
    if 'ultimate_bot' in result.stdout:
        warnings.append("⚠️  Bot may be running (check for conflicts)")
except:
    pass

# Check for common issues
conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Check for NULL values in critical fields
cursor.execute('''
    SELECT COUNT(*) FROM player_comprehensive_stats 
    WHERE player_guid IS NULL OR player_name IS NULL
''')
null_count = cursor.fetchone()[0]
if null_count > 0:
    issues.append(f"❌ Found {null_count} records with NULL player_guid or player_name")

# Check for orphaned records
cursor.execute('''
    SELECT COUNT(*) FROM player_comprehensive_stats p
    LEFT JOIN sessions s ON p.session_id = s.id
    WHERE s.id IS NULL
''')
orphaned = cursor.fetchone()[0]
if orphaned > 0:
    warnings.append(f"⚠️  Found {orphaned} orphaned player records (no matching session)")

# Check session_teams vs sessions
cursor.execute('SELECT COUNT(DISTINCT session_date) FROM sessions')
session_dates = cursor.fetchone()[0]

# NOTE: session_teams uses session_start_date, not session_date
cursor.execute('SELECT COUNT(DISTINCT session_start_date) FROM session_teams')
team_dates = cursor.fetchone()[0]
if team_dates < session_dates:
    warnings.append(f"⚠️  session_teams covers {team_dates} dates, but {session_dates} dates in sessions")
    warnings.append("   (Bot will use Axis/Allies for dates without session_teams)")

conn.close()

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("📋 AUDIT SUMMARY")
print("="*80)

print(f"\n✅ SUCCESSES: {len(successes)}")
for s in successes:
    print(f"  {s}")

if warnings:
    print(f"\n⚠️  WARNINGS: {len(warnings)}")
    for w in warnings:
        print(f"  {w}")

if issues:
    print(f"\n❌ CRITICAL ISSUES: {len(issues)}")
    for i in issues:
        print(f"  {i}")
    print("\n🚨 ACTION REQUIRED: Fix critical issues before starting bot!")
else:
    print("\n✅ NO CRITICAL ISSUES FOUND!")
    print("   System appears healthy and ready to run.")

print("\n" + "="*80)
print("Audit complete. Review findings above.")
print("="*80 + "\n")

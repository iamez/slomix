#!/usr/bin/env python3
"""
FIELD MAPPING CHECKER
=====================
This script checks if the field mappings in your bot match what the parser provides.

It helps identify mismatches like:
- parser provides 'objective_stats.gibs' but bot expects 'gibs'
- parser changed field names
- bot is looking for fields that don't exist
"""

def check_field_mappings():
    """Check for field mapping issues"""
    
    print("\n" + "="*80)
    print("FIELD MAPPING DIAGNOSTIC")
    print("="*80 + "\n")
    
    # Expected fields from parser (based on project knowledge)
    parser_fields = {
        'top_level': [
            'guid', 'name', 'clean_name', 'raw_name', 'team', 'rounds',
            'kills', 'deaths', 'headshots', 'kd_ratio',
            'shots_total', 'hits_total', 'accuracy',
            'damage_given', 'damage_received', 'dpm',
            'weapon_stats', 'efficiency', 'objective_stats',
            'time_played_seconds', 'time_played_minutes'
        ],
        'objective_stats': [
            'damage_given', 'damage_received',
            'team_damage_given', 'team_damage_received',
            'gibs', 'self_kills', 'team_kills', 'team_gibs',
            'time_played_percent', 'xp',
            'killing_spree', 'death_spree',
            'kill_assists', 'kill_steals', 'headshot_kills',
            'objectives_stolen', 'objectives_returned',
            'dynamites_planted', 'dynamites_defused',
            'times_revived', 'bullets_fired', 'dpm',
            'time_played_minutes', 'tank_meatshield',
            'time_dead_ratio', 'time_dead_minutes', 'kd_ratio',
            'most_useful_kills', 'denied_playtime',
            'double_kills', 'triple_kills', 'quad_kills',
            'multi_kills', 'mega_kills', 'useless_kills',
            'full_selfkills', 'revives_given'
        ]
    }
    
    # Fields the bot expects (from _insert_player_stats)
    bot_expected = {
        'top_level': [
            'guid', 'name', 'team', 'kills', 'deaths',
            'damage_given', 'damage_received',
            'headshots', 'dpm', 'kd_ratio',
            'time_played_seconds', 'weapon_stats'
        ],
        'from_objective_stats': [
            'gibs', 'self_kills', 'team_kills', 'team_gibs',
            'xp', 'bullets_fired', 'kill_assists',
            'objectives_stolen', 'objectives_returned',
            'dynamites_planted', 'dynamites_defused',
            'times_revived', 'revives_given',
            'most_useful_kills', 'useless_kills', 'kill_steals',
            'denied_playtime', 'tank_meatshield',
            'double_kills', 'triple_kills', 'quad_kills',
            'multi_kills', 'mega_kills',
            'killing_spree', 'death_spree', 'time_dead_ratio'
        ]
    }
    
    print("📋 CHECKING FIELD AVAILABILITY\n")
    
    # Check if bot can find what it needs
    issues = []
    
    print("1️⃣  Top-level fields the bot expects:")
    print("   " + "-"*60)
    for field in bot_expected['top_level']:
        if field in parser_fields['top_level']:
            print(f"   ✅ {field}")
        else:
            print(f"   ❌ {field} - NOT IN PARSER!")
            issues.append(f"Missing top-level field: {field}")
    
    print("\n2️⃣  Fields the bot expects from objective_stats:")
    print("   " + "-"*60)
    for field in bot_expected['from_objective_stats']:
        if field in parser_fields['objective_stats']:
            print(f"   ✅ {field}")
        else:
            print(f"   ❌ {field} - NOT IN OBJECTIVE_STATS!")
            issues.append(f"Missing objective_stats field: {field}")
    
    print("\n" + "="*80)
    print("POTENTIAL ISSUES")
    print("="*80 + "\n")
    
    if issues:
        print("❌ Found potential field mapping issues:\n")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        
        print("\n💡 COMMON CAUSES:")
        print("   - Parser was updated but bot code wasn't")
        print("   - Field names changed in community_stats_parser.py")
        print("   - objective_stats structure changed")
        print("   - Tab field order in c0rnp0rn3.lua changed")
        
        print("\n🔧 RECOMMENDED ACTIONS:")
        print("   1. Run: python debug_stats.py <stats_file.txt>")
        print("   2. Check what fields the parser actually returns")
        print("   3. Compare with the working version from your last chat")
        print("   4. Update bot's _insert_player_stats() to match parser output")
    else:
        print("✅ All expected fields are present in parser output")
        print("\n💡 If bot is still showing wrong stats, check:")
        print("   - SQL queries in display commands")
        print("   - Field calculations (DPM, accuracy, etc.)")
        print("   - Database column names vs parser field names")
    
    print("\n" + "="*80)
    print("QUICK DIAGNOSTIC CHECKLIST")
    print("="*80 + "\n")
    
    print("Run these commands to diagnose:")
    print(f"  1. python debug_stats.py /mnt/project/2025-10-30-230944-braundorf_b4-round-2.txt")
    print(f"  2. grep -n 'objective_stats' community_stats_parser.py")
    print(f"  3. grep -n 'obj_stats.get' ultimate_bot.py | head -20")
    print()

if __name__ == "__main__":
    check_field_mappings()

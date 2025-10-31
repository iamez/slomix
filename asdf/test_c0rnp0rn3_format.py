#!/usr/bin/env python3
"""
Parse c0rnp0rn3.lua format based on the actual lua code
"""

def parse_c0rnp0rn3_format():
    """Parse stats file using the actual c0rnp0rn3 format specification"""
    
    test_file = "./test_files/2025-09-24-233255-te_escape2-round-1.txt"
    
    print("🔍 Parsing c0rnp0rn3.lua format...")
    print("=" * 60)
    
    with open(test_file, 'r') as f:
        lines = f.readlines()
        
    # Parse header
    header = lines[0].strip().split('\\')
    print("📋 HEADER:")
    print(f"   Server: {header[0]}")
    print(f"   Map: {header[1]}")
    print(f"   Config: {header[2]}")
    print(f"   Round: {header[3]}")
    print(f"   Defender: {header[4]}")
    print(f"   Winner: {header[5]}")
    print(f"   Timelimit: {header[6]}")
    print(f"   NextTimelimit: {header[7]}")
    print()
    
    print("👤 PLAYER ANALYSIS:")
    print("Looking at the actual format from c0rnp0rn3.lua...")
    print()
    
    for i, line in enumerate(lines[1:], 1):
        if line.strip():
            parts = line.strip().split('\\')
            if len(parts) >= 5:
                guid = parts[0]
                name = parts[1]
                rounds = parts[2]
                team = parts[3]
                stats_part = parts[4]
                
                print(f"👤 Player {i}: {name}")
                print(f"   GUID: {guid}")
                print(f"   Team: {team}")
                print()
                
                # Split the massive stats part
                stats = stats_part.split()
                print(f"   📊 Total stats fields: {len(stats)}")
                
                # From c0rnp0rn3.lua, the format appears to be:
                # weapon mask + weapon stats + additional stats
                
                # Let's examine the structure in chunks
                print("   🔍 Stats breakdown:")
                
                # First field is weapon mask
                weapon_mask = int(stats[0])
                print(f"     Weapon mask: {weapon_mask}")
                
                # Count how many weapons based on bit mask
                weapon_count = bin(weapon_mask).count('1')
                print(f"     Active weapons: {weapon_count}")
                
                # Each weapon has 5 stats: hits, shots, kills, deaths, headshots
                weapon_stats_end = 1 + (weapon_count * 5)
                print(f"     Weapon stats end at index: {weapon_stats_end}")
                
                # The remaining stats should be the player stats
                if len(stats) > weapon_stats_end:
                    player_stats = stats[weapon_stats_end:]
                    print(f"     Player stats start at index: {weapon_stats_end}")
                    print(f"     Player stats count: {len(player_stats)}")
                    
                    # Based on c0rnp0rn3.lua StoreStats function:
                    # damageGiven, damageReceived, teamDamageGiven, teamDamageReceived,
                    # gibs, selfkills, teamkills, teamgibs, timePlayed, xp, 
                    # then the topshots array data...
                    
                    if len(player_stats) >= 10:
                        try:
                            damage_given = int(player_stats[0])
                            damage_received = int(player_stats[1])
                            team_damage_given = int(player_stats[2])
                            team_damage_received = int(player_stats[3])
                            gibs = int(player_stats[4])
                            selfkills = int(player_stats[5])
                            teamkills = int(player_stats[6])
                            teamgibs = int(player_stats[7])
                            time_played = float(player_stats[8])
                            xp = int(player_stats[9])
                            
                            print(f"     💥 Damage Given: {damage_given}")
                            print(f"     💔 Damage Received: {damage_received}")
                            print(f"     ⏱️  Time Played: {time_played}")
                            print(f"     🏆 XP: {xp}")
                            
                            # Calculate DPM: Damage Per Minute
                            if time_played > 0:
                                # time_played appears to be a percentage, need to convert
                                # to actual time. Let's check different interpretations
                                
                                # Option 1: time_played is minutes directly
                                dpm1 = damage_given / time_played if time_played > 0 else 0
                                
                                # Option 2: time_played is percentage, convert to minutes
                                # Assuming round time of ~12 minutes (from timelimit)
                                round_time_minutes = 12  # from header
                                actual_time_minutes = (time_played / 100.0) * round_time_minutes
                                dpm2 = damage_given / actual_time_minutes if actual_time_minutes > 0 else 0
                                
                                # Option 3: time_played is seconds
                                dpm3 = damage_given / (time_played / 60.0) if time_played > 0 else 0
                                
                                print(f"     📊 DPM Options:")
                                print(f"       As minutes: {dpm1:.1f}")
                                print(f"       As percentage: {dpm2:.1f}")
                                print(f"       As seconds: {dpm3:.1f}")
                                
                        except (ValueError, IndexError) as e:
                            print(f"     ❌ Parse error: {e}")
                    
                print()
                
                if i >= 2:  # Just show first 2 players for analysis
                    break

if __name__ == "__main__":
    parse_c0rnp0rn3_format()
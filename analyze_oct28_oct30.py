#!/usr/bin/env python3
"""
Analyze Oct 28 and Oct 30 sessions (gaming days)
Understand the round pairing for proper stopwatch scoring
"""

import sqlite3

def analyze_session(date):
    """Analyze one gaming session (day)"""
    conn = sqlite3.connect('bot/etlegacy_production.db')
    c = conn.cursor()
    
    c.execute("""
        SELECT id, map_name, round_number, winner_team, time_limit, actual_time
        FROM sessions
        WHERE session_date LIKE ?
        ORDER BY id
    """, (f"{date}%",))
    
    rounds = c.fetchall()
    
    print(f"\n{'='*80}")
    print(f"📅 SESSION (Gaming Day): {date}")
    print(f"{'='*80}\n")
    print(f"Total rounds in database: {len(rounds)}\n")
    
    # Try to identify map pairs
    print(f"{'Round ID':<10} {'Map':<20} {'Rnd':<5} {'Winner':<8} {'Limit':<10} {'Actual':<10}")
    print("-" * 80)
    
    map_sequence = []
    current_map = None
    map_counter = 0
    
    for round_id, map_name, rnd, winner, limit, actual in rounds:
        print(f"{round_id:<10} {map_name:<20} R{rnd:<4} Team {winner:<4} {limit:<10} {actual:<10}")
        
        # Detect map pairs (R1 followed by R2 of same map)
        if current_map is None or current_map['map_name'] != map_name or current_map['round'] != 1 or rnd != 2:
            # New map started
            if rnd == 1:
                map_counter += 1
                current_map = {
                    'map_id': map_counter,
                    'map_name': map_name,
                    'round': rnd,
                    'r1_id': round_id,
                    'r2_id': None
                }
                map_sequence.append(current_map)
            else:
                # Orphaned R2 (no R1 before it)
                map_counter += 1
                map_sequence.append({
                    'map_id': map_counter,
                    'map_name': map_name,
                    'round': rnd,
                    'r1_id': None,
                    'r2_id': round_id,
                    'orphaned': True
                })
                current_map = None
        else:
            # R2 follows R1 - complete pair!
            current_map['r2_id'] = round_id
            current_map['complete'] = True
            current_map = None
    
    # Analysis
    print(f"\n{'='*80}")
    print(f"🗺️  MAP ANALYSIS:")
    print(f"{'='*80}\n")
    
    complete_maps = sum(1 for m in map_sequence if m.get('complete', False))
    orphaned_rounds = sum(1 for m in map_sequence if m.get('orphaned', False))
    
    print(f"Total maps identified: {len(map_sequence)}")
    print(f"Complete maps (R1+R2): {complete_maps}")
    print(f"Orphaned rounds: {orphaned_rounds}\n")
    
    if complete_maps > 0:
        print("✅ Complete Maps (proper R1→R2 pairs):")
        for m in map_sequence:
            if m.get('complete'):
                print(f"   Map {m['map_id']}: {m['map_name']:<20} (rounds {m['r1_id']} + {m['r2_id']})")
    
    if orphaned_rounds > 0:
        print("\n⚠️  Orphaned Rounds (missing pair):")
        for m in map_sequence:
            if m.get('orphaned'):
                r = 'R2' if m['r2_id'] else 'R1'
                rid = m['r2_id'] or m['r1_id']
                print(f"   {m['map_name']:<20} {r} (round {rid}) - MISSING PAIR!")
    
    # Calculate round win percentages
    c.execute("""
        SELECT winner_team, COUNT(*) as wins
        FROM sessions
        WHERE session_date LIKE ? AND winner_team != 0
        GROUP BY winner_team
    """, (f"{date}%",))
    
    team_wins = dict(c.fetchall())
    total_rounds = sum(team_wins.values())
    
    print(f"\n{'='*80}")
    print(f"📊 ROUND WIN PERCENTAGES (SuperBoyy's method):")
    print(f"{'='*80}\n")
    
    for team in [1, 2]:
        wins = team_wins.get(team, 0)
        pct = (wins / total_rounds * 100) if total_rounds > 0 else 0
        print(f"Team {team}: {wins}/{total_rounds} rounds = {pct:.1f}%")
    
    conn.close()
    return map_sequence


if __name__ == "__main__":
    analyze_session("2025-10-28")
    analyze_session("2025-10-30")

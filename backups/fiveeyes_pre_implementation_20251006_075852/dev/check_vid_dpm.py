#!/usr/bin/env python3
"""
Check vid's GUIDs and calculate DPM properly
"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('='*80)
print('CHECKING VID GUIDS AND DPM CALCULATIONS')
print('='*80)

# Get all GUIDs for vid
rows = c.execute('''
    SELECT DISTINCT p.player_guid, p.player_name, COUNT(*) as records
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date LIKE '2025-10-02%'
    AND (p.player_name = 'vid' OR p.player_name LIKE '%vid%')
    GROUP BY p.player_guid
''').fetchall()

print(f'Found {len(rows)} GUID(s) for vid:\n')

for guid, name, count in rows:
    print(f'{name:20} | GUID: {guid} | Records: {count}')
    
    # Calculate Our DPM for this GUID
    result = c.execute('''
        SELECT 
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_minutes) as total_time,
            AVG(p.dpm) as avg_cdpm
        FROM sessions s
        JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE s.session_date LIKE '2025-10-02%'
        AND p.player_guid = ?
    ''', (guid,)).fetchone()
    
    total_dmg, total_time, avg_cdpm = result
    our_dpm = total_dmg / total_time if total_time > 0 else 0
    
    print(f'  cDPM (AVG): {avg_cdpm:.2f}')
    print(f'  Our DPM (SUM/SUM all records): {our_dpm:.2f}')
    print(f'  Total damage: {total_dmg}')
    print(f'  Total time: {total_time:.2f} min (including time=0 records)')
    print()
    
    # Now calculate with ONLY time > 0 records
    result2 = c.execute('''
        SELECT 
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_minutes) as total_time
        FROM sessions s
        JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE s.session_date LIKE '2025-10-02%'
        AND p.player_guid = ?
        AND p.time_played_minutes > 0
    ''', (guid,)).fetchone()
    
    total_dmg_nonzero, total_time_nonzero = result2
    our_dpm_nonzero = total_dmg_nonzero / total_time_nonzero if total_time_nonzero > 0 else 0
    
    print(f'  Our DPM (SUM/SUM time>0 only): {our_dpm_nonzero:.2f}')
    print(f'  Damage from time>0 records: {total_dmg_nonzero}')
    print(f'  Time from time>0 records: {total_time_nonzero:.2f} min')
    print()

conn.close()

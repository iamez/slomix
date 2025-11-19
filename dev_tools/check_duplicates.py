import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

# Get total records
cursor.execute('SELECT COUNT(*) FROM player_comprehensive_stats')
total = cursor.fetchone()[0]

# Get unique session+player combinations
cursor.execute('SELECT COUNT(*) FROM (SELECT DISTINCT round_id, player_guid FROM player_comprehensive_stats)')
unique = cursor.fetchone()[0]

duplicates = total - unique

print(f'\n📊 Duplicate Check:')
print(f'Total records: {total:,}')
print(f'Unique (session + player): {unique:,}')
print(f'Duplicates: {duplicates:,}')

if duplicates > 0:
    print(f'\n⚠️ WARNING: {duplicates:,} duplicate records found!')
    print(f'Duplication rate: {duplicates/total*100:.1f}%')
    
    # Show example duplicates
    cursor.execute('''
        SELECT round_id, player_guid, player_name, COUNT(*) as count
        FROM player_comprehensive_stats
        GROUP BY round_id, player_guid
        HAVING count > 1
        LIMIT 5
    ''')
    print(f'\nExample duplicates:')
    for row in cursor.fetchall():
        print(f'  Session {row[0]}, Player {row[2]}: {row[3]} copies')
else:
    print(f'\n✅ No duplicates - all records are unique!')

conn.close()

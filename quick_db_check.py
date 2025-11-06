import psycopg2

conn = psycopg2.connect(
    dbname='etl_stats',
    user='postgres',
    password='your_password',
    host='localhost'
)
cur = conn.cursor()

# Check counts
cur.execute('SELECT COUNT(*) FROM rounds')
rounds_count = cur.fetchone()[0]
print(f'Total rounds: {rounds_count}')

cur.execute('SELECT COUNT(*) FROM players')
players_count = cur.fetchone()[0]
print(f'Total players: {players_count}')

cur.execute('SELECT COUNT(*) FROM weapons')
weapons_count = cur.fetchone()[0]
print(f'Total weapons: {weapons_count}')

if rounds_count > 0:
    cur.execute('SELECT filename, round_start_time FROM rounds ORDER BY round_start_time DESC LIMIT 5')
    print('\nMost recent rounds:')
    for row in cur.fetchall():
        print(f'  {row[0]} - {row[1]}')
else:
    print('\n❌ NO ROUNDS FOUND IN DATABASE!')

conn.close()

import sqlite3

conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE sessions ADD COLUMN map_id INTEGER')
    conn.commit()
    print('✅ Added map_id column')
except Exception as e:
    print(f'⚠️  {e}')

conn.close()

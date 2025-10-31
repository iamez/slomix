import sqlite3

def main():
    conn = sqlite3.connect('bot/etlegacy_production.db')
    cur = conn.cursor()
    date = '2025-10-30'
    cur.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats w JOIN sessions s ON w.session_id=s.id WHERE SUBSTR(s.session_date,1,10)=? AND (w.player_name IS NULL OR w.player_name = '')", (date,))
    cnt = cur.fetchone()[0]
    print(f'weapon rows with NULL/empty player_name on date {date}: {cnt}')
    conn.close()

if __name__ == '__main__':
    main()

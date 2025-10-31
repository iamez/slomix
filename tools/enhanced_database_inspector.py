#!/usr/bin/env python3
"""
Enhanced Database Inspector - Shows Individual Stat Columns Structure
Demonstrates how stats are stored in individual columns for flexible Discord queries
"""

import asyncio

import aiosqlite


class EnhancedDatabaseInspector:
    """Inspects database structure with focus on individual stat columns"""

    def __init__(self, db_path: str = "./etlegacy_fixed_bulk.db"):
        self.db_path = db_path

    async def show_table_schemas(self):
        """Display all table schemas with individual stat columns highlighted"""
        print("=" * 80)
        print("DATABASE SCHEMA WITH INDIVIDUAL STAT COLUMNS")
        print("=" * 80)

        async with aiosqlite.connect(self.db_path) as db:
            # Get all tables
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()

            for table_name in tables:
                table = table_name[0]
                print(f"\n🗃️  TABLE: {table}")
                print("-" * 60)

                # Get table info
                cursor = await db.execute(f"PRAGMA table_info({table})")
                columns = await cursor.fetchall()

                if table == 'player_round_stats':
                    print("📊 INDIVIDUAL STAT COLUMNS for flexible Discord queries:")

                    # Group columns by category
                    combat_stats = []
                    weapon_stats = []
                    advanced_stats = []
                    multikill_stats = []
                    other_cols = []

                    for col in columns:
                        col_name = col[1]
                        col_type = col[2]

                        if col_name in [
                            'kills',
                            'deaths',
                            'headshots',
                            'kd_ratio',
                            'shots_total',
                            'hits_total',
                            'accuracy',
                            'damage_given',
                            'damage_received',
                            'efficiency',
                        ]:
                            combat_stats.append(f"    {col_name:<20} {col_type}")
                        elif (
                            col_name.endswith('_kills')
                            or col_name.endswith('_shots')
                            or col_name.endswith('_hits')
                            or col_name.endswith('_accuracy')
                        ):
                            weapon_stats.append(f"    {col_name:<20} {col_type}")
                        elif col_name.startswith('multikills_'):
                            multikill_stats.append(f"    {col_name:<20} {col_type}")
                        elif col_name in [
                            'killing_spree_best',
                            'death_spree_worst',
                            'kill_assists',
                            'kill_steals',
                            'objectives_stolen',
                            'objectives_returned',
                            'dynamites_planted',
                            'dynamites_defused',
                            'dpm',
                            'tank_meatshield',
                            'useful_kills',
                            'denied_playtime',
                        ]:
                            advanced_stats.append(f"    {col_name:<20} {col_type}")
                        else:
                            other_cols.append(f"    {col_name:<20} {col_type}")

                    print("\n  🎯 CORE COMBAT STATS:")
                    for stat in combat_stats:
                        print(stat)

                    print("\n  🔫 WEAPON-SPECIFIC STATS:")
                    for stat in weapon_stats:
                        print(stat)

                    print("\n  ⚡ ADVANCED STATS:")
                    for stat in advanced_stats:
                        print(stat)

                    print("\n  💥 MULTIKILL STATS:")
                    for stat in multikill_stats:
                        print(stat)

                    print("\n  📋 OTHER COLUMNS:")
                    for stat in other_cols:
                        print(stat)

                else:
                    for col in columns:
                        col_name = col[1]
                        col_type = col[2]
                        nullable = "NULL" if col[3] == 0 else "NOT NULL"
                        default = f" DEFAULT {col[4]}" if col[4] else ""
                        print(f"    {col_name:<20} {col_type:<10} {nullable}{default}")

    async def show_sample_data(self):
        """Show sample data demonstrating individual stat columns"""
        print("\n" + "=" * 80)
        print("SAMPLE DATA - INDIVIDUAL STAT COLUMNS")
        print("=" * 80)

        async with aiosqlite.connect(self.db_path) as db:
            # Show sessions overview
            print("\n📅 SESSIONS:")
            cursor = await db.execute(
                '''
                SELECT session_date, total_rounds, total_maps, players_count, session_mvp_name
                FROM sessions
            '''
            )
            sessions = await cursor.fetchall()

            for session in sessions:
                print(
                    f"  Date: {
                        session[0]} | Rounds: {
                        session[1]} | Maps: {
                        session[2]} | Players: {
                        session[3]} | MVP: {
                        session[4]}"
                )

            # Show individual stat columns in action
            print("\n🎯 PLAYER ROUND STATS - Individual Columns for Flexible Queries:")
            cursor = await db.execute(
                '''
                SELECT
                    player_clean_name,
                    kills, deaths, headshots, kd_ratio,
                    accuracy, damage_given, dpm,
                    mp40_kills, thompson_kills, fg42_kills, sniper_kills,
                    killing_spree_best, kill_assists, multikills_3
                FROM player_round_stats
                ORDER BY kills DESC
                LIMIT 8
            '''
            )
            stats = await cursor.fetchall()

            print(
                "  Player          K  D  HS  K/D  Acc%  Dmg   DPM   MP40 THOMP FG42 SNPR Spree Asst M3"
            )
            print("  " + "-" * 75)

            for stat in stats:
                name = stat[0][:12].ljust(12)
                k, d, hs, kd = stat[1:5]
                acc, dmg, dpm = stat[5:8]
                mp40, thomp, fg42, sniper = stat[8:12]
                spree, assists, m3 = stat[12:15]

                print(
                    f"  {name} {
                        k:2d} {
                        d:2d} {
                        hs:2d} {
                        kd:4.1f} {
                        acc:4.1f} {
                            dmg:4d} {
                                dpm:5.1f} "
                    f"{
                        mp40:3d}  {
                        thomp:3d}   {
                        fg42:3d}  {
                        sniper:3d}   {
                        spree:2d}   {
                        assists:2d}  {
                        m3:1d}"
                )

            # Show weapon-specific stats
            print("\n🔫 WEAPON STATS - Individual Columns for Easy Queries:")
            cursor = await db.execute(
                '''
                SELECT
                    player_clean_name,
                    mp40_kills, mp40_accuracy,
                    thompson_kills, thompson_accuracy,
                    fg42_kills, fg42_accuracy,
                    sniper_kills, sniper_accuracy
                FROM player_round_stats
                WHERE mp40_kills > 0 OR thompson_kills > 0 OR fg42_kills > 0 OR sniper_kills > 0
                ORDER BY (mp40_kills + thompson_kills + fg42_kills + sniper_kills) DESC
                LIMIT 5
            '''
            )
            weapon_stats = await cursor.fetchall()

            print("  Player        MP40(K/Acc)  THOMP(K/Acc)  FG42(K/Acc)  SNIPER(K/Acc)")
            print("  " + "-" * 65)

            for ws in weapon_stats:
                name = ws[0][:12].ljust(12)
                print(
                    f"  {name}  {ws[1]:2d}/{ws[2]:4.1f}%     {ws[3]:2d}/{ws[4]:4.1f}%      "
                    f"{ws[5]:2d}/{ws[6]:4.1f}%     {ws[7]:2d}/{ws[8]:4.1f}%"
                )

            # Show session aggregates
            print("\n📊 SESSION AGGREGATES - Individual Columns Summed:")
            cursor = await db.execute(
                '''
                SELECT
                    player_clean_name, rounds_played,
                    total_kills, total_deaths, total_headshots,
                    avg_kd_ratio, avg_accuracy, avg_dpm,
                    mvp_rounds, best_round_kills, session_score
                FROM session_player_stats
                ORDER BY session_score DESC
            '''
            )
            session_stats = await cursor.fetchall()

            print(
                "  Player        Rnds  TotK  TotD  TotHS  AvgK/D  AvgAcc  AvgDPM  MVP  Best  Score"
            )
            print("  " + "-" * 75)

            for ss in session_stats:
                name = ss[0][:12].ljust(12)
                print(
                    f"  {name}  {
                        ss[1]:2d}   {
                        ss[2]:3d}   {
                        ss[3]:3d}   {
                        ss[4]:3d}   "
                    f"{
                        ss[5]:4.1f}   {
                            ss[6]:5.1f}%  {
                                ss[7]:5.1f}   {
                                    ss[8]:2d}   {
                                        ss[9]:2d}   {
                                            ss[10]:5.1f}"
                )

    async def demonstrate_flexible_queries(self):
        """Show example Discord queries using individual stat columns"""
        print("\n" + "=" * 80)
        print("FLEXIBLE DISCORD QUERY EXAMPLES - Individual Columns")
        print("=" * 80)

        async with aiosqlite.connect(self.db_path) as db:
            queries = [
                {
                    'title': '🏆 Top Fraggers (kills > 10)',
                    'sql': '''
                        SELECT player_clean_name, SUM(kills) as total_kills, AVG(kd_ratio) as avg_kd
                        FROM player_round_stats
                        WHERE kills > 10
                        GROUP BY player_guid
                        ORDER BY total_kills DESC
                    ''',
                    'discord_cmd': '!stats frags kills>10',
                },
                {
                    'title': '🎯 Headshot Kings (headshots > 5)',
                    'sql': '''
                        SELECT player_clean_name, SUM(headshots) as total_hs,
                               ROUND(SUM(headshots) * 100.0 / SUM(kills), 1) as hs_ratio
                        FROM player_round_stats
                        WHERE headshots > 5
                        GROUP BY player_guid
                        ORDER BY total_hs DESC
                    ''',
                    'discord_cmd': '!stats headshots headshots>5',
                },
                {
                    'title': '🔫 MP40 Masters (mp40_kills > 5)',
                    'sql': '''
                        SELECT player_clean_name, SUM(mp40_kills) as mp40_kills, AVG(mp40_accuracy) as avg_acc
                        FROM player_round_stats
                        WHERE mp40_kills > 5
                        GROUP BY player_guid
                        ORDER BY mp40_kills DESC
                    ''',
                    'discord_cmd': '!stats weapon mp40 kills>5',
                },
                {
                    'title': '💥 High DPM Players (dpm > 200)',
                    'sql': '''
                        SELECT player_clean_name, ROUND(AVG(dpm), 1) as avg_dpm, SUM(damage_given) as total_dmg
                        FROM player_round_stats
                        WHERE dpm > 200
                        GROUP BY player_guid
                        ORDER BY avg_dpm DESC
                    ''',
                    'discord_cmd': '!stats dpm dpm>200',
                },
                {
                    'title': '⚡ Multi-kill Specialists (multikills_3 > 0)',
                    'sql': '''
                        SELECT player_clean_name, SUM(multikills_3) as triple_kills, MAX(killing_spree_best) as best_spree
                        FROM player_round_stats
                        WHERE multikills_3 > 0
                        GROUP BY player_guid
                        ORDER BY triple_kills DESC
                    ''',
                    'discord_cmd': '!stats multikills triple>0',
                },
            ]

            for query in queries:
                print(f"\n{query['title']}")
                print(f"Discord Command: {query['discord_cmd']}")
                print(f"SQL (using individual columns):")
                print(f"  {query['sql'].strip()}")

                try:
                    cursor = await db.execute(query['sql'])
                    results = await cursor.fetchall()

                    print("Results:")
                    for i, row in enumerate(results[:3]):  # Show top 3
                        print(f"  {i + 1}. {' | '.join(str(x) for x in row)}")

                    if len(results) > 3:
                        print(f"  ... and {len(results) - 3} more")

                except Exception as e:
                    print(f"  Error: {e}")

    async def show_discord_link_schema(self):
        """Show Discord linking table for @mention support"""
        print("\n" + "=" * 80)
        print("DISCORD LINKING SYSTEM - @mention Support")
        print("=" * 80)

        async with aiosqlite.connect(self.db_path) as db:
            # Show player_links table
            print("\n🔗 PLAYER_LINKS TABLE:")
            cursor = await db.execute("PRAGMA table_info(player_links)")
            columns = await cursor.fetchall()

            for col in columns:
                col_name = col[1]
                col_type = col[2]
                nullable = "NULL" if col[3] == 0 else "NOT NULL"
                print(f"    {col_name:<20} {col_type:<15} {nullable}")

            # Show sample links
            print("\n📋 SAMPLE DISCORD LINKS:")
            cursor = await db.execute(
                '''
                SELECT discord_username, et_name, et_guid, verified, linked_date
                FROM player_links
            '''
            )
            links = await cursor.fetchall()

            print("  Discord User    ET Name     ET GUID      Verified  Linked Date")
            print("  " + "-" * 60)

            for link in links:
                verified = "✓" if link[3] else "✗"
                print(
                    f"  {link[0]:<12}    {link[1]:<8}    {link[2]:<10}   {verified:<8}  {link[4][:10]}"
                )

            # Show example Discord mention queries
            print("\n💬 EXAMPLE DISCORD @MENTION QUERIES:")

            mention_examples = [
                "@SuperUser stats last 7 days",
                "@BronzePlayer vs @OlzGamer headshots",
                "@SuperUser weapon accuracy mp40",
                "@BronzePlayer best rounds kills>15",
            ]

            for example in mention_examples:
                print(f"  {example}")

            print("\n🔍 SQL Translation for @mention queries:")
            print("  1. Parse Discord mention → get discord_id")
            print("  2. Look up et_guid in player_links")
            print("  3. Query individual stat columns WHERE player_guid = et_guid")
            print("  4. Return formatted results to Discord")

    async def inspect_database(self):
        """Complete database inspection with individual columns focus"""
        try:
            print("🔍 ENHANCED DATABASE INSPECTOR")
            print("Individual Stat Columns for Flexible Discord Queries")
            print("Database:", self.db_path)

            await self.show_table_schemas()
            await self.show_sample_data()
            await self.demonstrate_flexible_queries()
            await self.show_discord_link_schema()

            print("\n" + "=" * 80)
            print("✅ INSPECTION COMPLETE")
            print("=" * 80)
            print("\nKey Features:")
            print("✓ Individual columns for each stat (no JSON blobs)")
            print("✓ Flexible WHERE clauses (kills>10, accuracy>75%, etc.)")
            print("✓ Weapon-specific stats in separate columns")
            print("✓ Session aggregation with individual column sums")
            print("✓ Discord @mention linking system")
            print("✓ Optimized indexes for fast Discord queries")
            print("\nReady for 3345 file bulk import!")

        except Exception as e:
            print(f"Error inspecting database: {e}")
            import traceback

            traceback.print_exc()


async def main():
    inspector = EnhancedDatabaseInspector()
    await inspector.inspect_database()


if __name__ == "__main__":
    asyncio.run(main())

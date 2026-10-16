"""Measure persisted canonical round totals without joining player/weapon rows."""


async def validate_import_totals(conn, round_id, players, weapons, kills, deaths):
    """Check parser expectations inside the caller's existing transaction.

    Compare only this round, not session/date or its R0 summary. ACID protects
    atomicity, not completeness. A mismatch is a validation warning; the caller
    retains its established save-with-warning policy.
    """
    actual = await conn.fetchrow('''
        SELECT count(*) AS players,
               COALESCE(sum(kills), 0) AS kills,
               COALESCE(sum(deaths), 0) AS deaths,
               (SELECT count(*) FROM weapon_comprehensive_stats WHERE round_id=$1) AS weapons
        FROM player_comprehensive_stats WHERE round_id=$1
    ''', round_id)
    expected = dict(players=players, weapons=weapons, kills=kills, deaths=deaths)
    differences = [f'{key}: expected {value}, stored {actual[key]}'
                   for key, value in expected.items() if actual[key] != value]
    if differences:
        return False, 'Import totals mismatch: ' + '; '.join(differences)
    return True, 'Import totals match'

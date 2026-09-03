import { describe, expect, it } from 'vitest';
import { guidKey, perMapTotals } from './perMap';
import type { SessionRound } from './types';
import rounds from '../pages/__fixtures__/api_stats_session_gaming_session_id_rounds.json';

const ROUNDS = (rounds as { rounds: SessionRound[] }).rounds;

function row(guid: string, kills: number, deaths: number, dmg: number, secs: number) {
  return {
    player_guid: guid, player_name: guid.slice(0, 4), team: 1, time_played_seconds: secs, gibs: 0,
    damage_received: 0, damage_given: dmg, kills, deaths, headshots: 0, headshot_kills: 0,
    revives_given: 0, times_revived: 0, xp: 0,
  };
}

function round(map: string, counts: boolean, players: ReturnType<typeof row>[]): SessionRound {
  return {
    round_id: 1, map_name: map, round_number: 1, played_at: '', duration_seconds: null, end_reason: null,
    round_status: counts ? 'completed' : 'cancelled', counts_toward_totals: counts, match_id: null, players,
  };
}

const FULL = 'ABCDEF0123456789ABCDEF0123456789';

describe('perMapTotals', () => {
  it('joins the 32-character round guid to the page\'s 8-character key, upper-cased', () => {
    const { maps } = perMapTotals([round('supply', true, [row(FULL.toLowerCase(), 3, 1, 600, 60)])], 'abcdef01');
    expect(maps).toHaveLength(1);
    expect(maps[0]).toMatchObject({ map_name: 'supply', kills: 3, deaths: 1, dpm: 600, kd: 3 });
  });

  it('never folds the all-zero guid into a player, and leaves non-counting rounds out', () => {
    const zero = '0'.repeat(32);
    const { maps, counted, skipped } = perMapTotals([
      round('supply', true, [row(zero, 9, 0, 9000, 60)]),
      round('supply', false, [row(FULL, 5, 5, 500, 60)]),
      round('goldrush', true, [row(FULL, 2, 4, 200, 120)]),
    ], '00000000');
    // The zero guid asked for directly still matches nothing.
    expect(maps).toEqual([]);
    const mine = perMapTotals([
      round('supply', true, [row(zero, 9, 0, 9000, 60)]),
      round('supply', false, [row(FULL, 5, 5, 500, 60)]),
      round('goldrush', true, [row(FULL, 2, 4, 200, 120)]),
    ], 'ABCDEF01');
    expect(mine.maps).toEqual([expect.objectContaining({ map_name: 'goldrush', kills: 2, deaths: 4, kd: 0.5, dpm: 100 })]);
    expect(mine.counted).toBe(1);
    expect(mine.skipped).toBe(1);
    expect(counted).toBe(0);
    expect(skipped).toBe(1);
  });

  it('sums the recording the way a hand sum does', () => {
    // Control: the first counted round-player row of the fixture, summed by
    // hand over every counted round on its map, must equal the helper.
    const first = ROUNDS.find((r) => r.counts_toward_totals)?.players.find((p) => !/^0+$/.test(p.player_guid));
    expect(first).toBeDefined();
    const key = guidKey((first as { player_guid: string }).player_guid);
    const { maps } = perMapTotals(ROUNDS, key);
    for (const m of maps) {
      const rows = ROUNDS.filter((r) => r.counts_toward_totals && r.map_name === m.map_name)
        .flatMap((r) => r.players.filter((p) => guidKey(p.player_guid) === key));
      expect(m.rounds).toBe(rows.length);
      expect(m.kills).toBe(rows.reduce((s, p) => s + p.kills, 0));
      expect(m.damage_given).toBe(rows.reduce((s, p) => s + p.damage_given, 0));
    }
    expect(maps.length).toBeGreaterThan(0);
  });

  it('dpm is null, not Infinity or NaN, when no time was recorded', () => {
    const { maps } = perMapTotals([round('supply', true, [row(FULL, 1, 0, 100, 0)])], 'ABCDEF01');
    expect(maps[0].dpm).toBeNull();
    expect(Number.isFinite(maps[0].kd)).toBe(true);
  });
});

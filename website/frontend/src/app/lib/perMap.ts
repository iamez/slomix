/**
 * Per-map totals for one player, summed from the session's rounds — no
 * endpoint of its own (stats 2.0 R5, docs/design/18 §C plast 2).
 *
 * Two facts decide the shape:
 *  - `/rounds` carries a 32-character guid per round-player row while the
 *    rest of the session page (detail, basics, verdicts, lives) keys by the
 *    8-character prefix — so the join is on the prefix, upper-cased, never
 *    on equality of the full string;
 *  - a round-player row can carry the all-zero guid (an unresolved or bot
 *    slot, "player1" on the recording), which must not fold into anyone.
 *
 * Only rounds that count toward totals are summed; the caller says how many
 * were left out so a short table is not read as a short night.
 */
import type { SessionRound } from './types';

export interface PerMapTotals {
  map_name: string;
  rounds: number;
  kills: number;
  deaths: number;
  damage_given: number;
  damage_received: number;
  time_played_seconds: number;
  /** damage given × 60 ÷ time played; null when no time was recorded. */
  dpm: number | null;
  /** kills ÷ max(1, deaths). */
  kd: number;
}

export function guidKey(guid: string): string {
  return guid.slice(0, 8).toUpperCase();
}

function isUnresolved(guid: string): boolean {
  return guid.length === 0 || /^0+$/.test(guid);
}

export function perMapTotals(rounds: readonly SessionRound[], guid8: string): { maps: PerMapTotals[]; counted: number; skipped: number } {
  const key = guidKey(guid8);
  const byMap = new Map<string, PerMapTotals>();
  let counted = 0;
  let skipped = 0;
  for (const round of rounds) {
    if (!round.counts_toward_totals) { skipped += 1; continue; }
    const row = round.players.find((p) => !isUnresolved(p.player_guid) && guidKey(p.player_guid) === key);
    if (!row) continue;
    counted += 1;
    const acc = byMap.get(round.map_name) ?? {
      map_name: round.map_name, rounds: 0, kills: 0, deaths: 0, damage_given: 0, damage_received: 0,
      time_played_seconds: 0, dpm: null, kd: 0,
    };
    acc.rounds += 1;
    acc.kills += row.kills;
    acc.deaths += row.deaths;
    acc.damage_given += row.damage_given;
    acc.damage_received += row.damage_received;
    acc.time_played_seconds += row.time_played_seconds;
    byMap.set(round.map_name, acc);
  }
  const maps = [...byMap.values()].map((m) => ({
    ...m,
    dpm: m.time_played_seconds > 0 ? m.damage_given * 60 / m.time_played_seconds : null,
    kd: m.kills / Math.max(1, m.deaths),
  }));
  return { maps, counted, skipped };
}

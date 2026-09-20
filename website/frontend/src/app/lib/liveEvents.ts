/**
 * The ticker's sentences — one per live event, in words a visitor reads,
 * with the doubles folded away.
 *
 * The feed carries every event the tailer parses (audit 2026-09-07: nine
 * kinds reached the page and the page printed `seq · type` and nothing
 * else). Two pairs arrive twice for one thing: `POPUP` + `DYNAMITE` for a
 * plant/defuse (the engine's popup and the Lua module's own line), and
 * `MAP` + `LIVE_MAP` for a map load (legacy3 and LIVEX). `KILL` and
 * `LIVE_KILL` are the same obituary from two sources — the server already
 * dedupes them at ingest when both arrive within a window, but a LIVE_KILL
 * that survived carries what KILL lacks (distance, the killer's health), so
 * it is folded INTO the kill line rather than shown as a second one.
 */
import { stripEtColors } from './names';

export type LiveEvent = { seq: number; type: string; [k: string]: unknown };
export type SlotNames = ReadonlyMap<number, string>;

const SIDE: Record<number, string> = { 1: 'axis', 2: 'allies', 3: 'spectators' };

function weapon(mod: unknown): string {
  return typeof mod === 'string' ? mod.replace(/^MOD_/, '').toLowerCase().replace(/_/g, ' ') : '';
}

function who(names: SlotNames, slot: unknown, fallback = 'someone'): string {
  const n = typeof slot === 'number' ? names.get(slot) : undefined;
  return n ? stripEtColors(n) : fallback;
}

function slots(names: SlotNames, raw: unknown): [string, string] {
  const parts = typeof raw === 'string' ? raw.trim().split(/\s+/).map(Number) : [];
  return [who(names, parts[0]), who(names, parts[1])];
}

function flagName(raw: unknown): string {
  if (typeof raw !== 'string') return 'the objective';
  return raw.includes('flag') ? 'the objective' : raw;
}

/** Sentence for one event; null only for the kinds that carry nothing a
 *  reader wants (BEGIN, GAMETIME, INIT_GAME, the aggregate deltas); an
 *  unknown kind falls back to its name so nothing is silently lost. */
export function describeEvent(e: LiveEvent, names: SlotNames): string | null {
  switch (e.type) {
    case 'KILL':
    case 'LIVE_KILL': {
      const k = typeof e.killer === 'string' ? stripEtColors(e.killer) : who(names, e.killer_slot);
      const v = typeof e.victim === 'string' ? stripEtColors(e.victim) : who(names, e.victim_slot);
      const w = weapon(e.mod);
      const extra = typeof e.distance === 'number' ? ` · ${Math.round(e.distance)} u` : '';
      const hp = typeof e.killer_health === 'number' ? ` · killer at ${e.killer_health} hp` : '';
      return `${k} killed ${v}${w ? ` · ${w}` : ''}${extra}${hp}`;
    }
    case 'POPUP': {
      const team = typeof e.team === 'string' ? e.team : 'someone';
      return `${team} ${String(e.verb ?? 'touched')} ${String(e.objective ?? 'an objective')}`;
    }
    case 'DYNAMITE':
      return `${who(names, e.slot)} ${e.action === 'defuse' ? 'defused' : 'planted'} dynamite at ${String(e.objective ?? 'an objective')}`;
    case 'FLAG_PICKUP':
      return `${who(names, e.slot)} picked up ${flagName(e.flag)}`;
    case 'OBJECTIVE_DESTROYED':
      return `objective destroyed: ${String(e.detail ?? '')}`.trim();
    case 'ANNOUNCE':
      return typeof e.text === 'string' ? e.text : null;
    case 'CALLVOTE':
      return `${who(names, e.slot)} called a vote: ${String(e.vote ?? '')}`.trim();
    case 'VOTE_PASSED':
      return `vote passed${typeof e.vote === 'string' ? `: ${e.vote}` : ''}`;
    case 'REVIVE': {
      const [a, b] = slots(names, e.slots);
      return `${a} revived ${b}`;
    }
    case 'SUPPLY': {
      const [a, b] = slots(names, e.slots);
      return `${a} supplied ${b}`;
    }
    case 'TEAM_CHANGE': {
      const n = typeof e.name === 'string' ? stripEtColors(e.name) : who(names, e.slot);
      const side = typeof e.team === 'number' ? SIDE[e.team] ?? `team ${e.team}` : 'a side';
      return `${n} → ${side}`;
    }
    case 'CONNECT':
      return `${who(names, e.slot, `slot ${String(e.slot ?? '?')}`)} connected`;
    case 'DISCONNECT':
      return `${who(names, e.slot, `slot ${String(e.slot ?? '?')}`)} left`;
    case 'MAP':
    case 'LIVE_MAP':
      return `map ${String(e.map_name ?? '?')}`;
    case 'GAMETYPE':
      return `game type ${String(e.gametype ?? '?')}`;
    case 'ROUND_START':
      return 'round started';
    case 'ROUND_END':
      return 'round ended';
    case 'EXIT':
      return `round over: ${String(e.reason ?? '')}`.trim();
    case 'SCORELINE':
      return typeof e.text === 'string' ? e.text : 'score line';
    case 'SAY':
    case 'TEAM_CHAT_REDACTED':
      return `${who(names, e.slot)}: ${e.type === 'SAY' && typeof e.text === 'string' ? e.text : '(team chat)'}`;
    case 'BEGIN':
    case 'GAMETIME':
    case 'INIT_GAME':
    case 'LIVE_AGGREGATE':
    case 'LIVE_MOVEMENT':
    case 'STATS_SAVED':
      return null;
    default:
      // A kind this file does not know yet still shows — as its name, the
      // way the whole feed used to — rather than vanishing.
      return e.type.toLowerCase().replace(/_/g, ' ');
  }
}

const DOUBLE_WINDOW_MS = 3000;

/** The clock the two sources share. `level_ms` is level-relative for legacy3
 *  and EPOCH ms for LIVEX (`clock: 'epoch'`), so it cannot pair a KILL with
 *  its LIVE_KILL; `received_at` (seconds, stamped by the ingest) can. */
function whenMs(e: LiveEvent): number {
  if (typeof e.received_at === 'number') return e.received_at * 1000;
  return typeof e.level_ms === 'number' ? e.level_ms : 0;
}

/**
 * Fold the doubles: a DYNAMITE within 3 s of a POPUP naming the same
 * objective replaces it (the DYNAMITE line names the player); a MAP or
 * LIVE_MAP naming the map already announced within 60 s is dropped; a
 * LIVE_KILL within 3 s of a KILL with the same slots lends the KILL its
 * distance and killer health and disappears. Returns newest-last, like the
 * feed.
 */
export function foldDoubles(events: LiveEvent[]): LiveEvent[] {
  const out: LiveEvent[] = [];
  let lastMap: { name: string; at: number } | null = null;
  for (const e of events) {
    if (e.type === 'LIVE_KILL') {
      const twin = [...out].reverse().find((p) => p.type === 'KILL'
        && p.killer_slot === e.killer_slot && p.victim_slot === e.victim_slot
        && Math.abs(whenMs(p) - whenMs(e)) <= DOUBLE_WINDOW_MS);
      if (twin) {
        if (typeof e.distance === 'number') twin.distance = e.distance;
        if (typeof e.killer_health === 'number') twin.killer_health = e.killer_health;
        continue;
      }
      out.push({ ...e, type: 'KILL' });
      continue;
    }
    if (e.type === 'DYNAMITE') {
      const idx = out.findIndex((p) => p.type === 'POPUP' && p.objective === e.objective
        && Math.abs(whenMs(p) - whenMs(e)) <= DOUBLE_WINDOW_MS);
      if (idx >= 0) out.splice(idx, 1);
      out.push({ ...e });
      continue;
    }
    if (e.type === 'MAP' || e.type === 'LIVE_MAP') {
      const name = String(e.map_name ?? '');
      if (lastMap && lastMap.name === name && Math.abs(whenMs(e) - lastMap.at) <= 60_000) continue;
      lastMap = { name, at: whenMs(e) };
      out.push({ ...e });
      continue;
    }
    out.push({ ...e });
  }
  return out;
}

import { describe, expect, it } from 'vitest';
import { describeEvent, foldDoubles, type LiveEvent } from './liveEvents';
import evening from '../pages/__fixtures__/api_live_feed.evening.json';

const NAMES = new Map<number, string>([[1, 'vid'], [2, '.lgz'], [3, 'KaNii'], [4, 'qmr'], [5, 'wiseBoy'], [6, '.olz']]);
const events = (evening as { events: LiveEvent[] }).events;

describe('the ticker reads its events', () => {
  it('turns every recorded kind the page used to print as a type name into a sentence', () => {
    const kinds = new Set(events.map((e) => e.type));
    const silent = new Set(['BEGIN', 'GAMETIME', 'INIT_GAME', 'LIVE_MAP']);
    for (const kind of kinds) {
      const sample = events.find((e) => e.type === kind)!;
      const text = describeEvent(sample, NAMES);
      if (silent.has(kind)) continue;
      expect(text, kind).not.toBeNull();
      expect(text!.includes('undefined'), `${kind}: ${text}`).toBe(false);
    }
    // The recorded evening's actual words.
    expect(describeEvent(events.find((e) => e.type === 'KILL')!, NAMES)).toBe('.olz killed wiseBoy · mp40');
    expect(describeEvent(events.find((e) => e.type === 'POPUP')!, NAMES)).toBe('allies planted the Door Controls');
    expect(describeEvent(events.find((e) => e.type === 'DYNAMITE')!, NAMES)).toBe('slot 2 planted dynamite at the Door Controls');
    expect(describeEvent(events.find((e) => e.type === 'REVIVE')!, NAMES)).toBe('slot 4 revived slot 2');
    expect(describeEvent(events.find((e) => e.type === 'CALLVOTE')!, NAMES)).toBe('slot 4 called a vote: Match Reset');
    expect(describeEvent(events.find((e) => e.type === 'ANNOUNCE')!, NAMES)).toBe('The Doors are opening!!');
  });

  it('folds the doubles: one line per plant, per map load, per kill — with what only the twin knew', () => {
    const folded = foldDoubles(events);
    const count = (t: string, arr: LiveEvent[]) => arr.filter((e) => e.type === t).length;
    // Every recorded LIVE_KILL had a KILL twin within the window: none survive
    // as their own line, and the kills gained the distance they carried.
    expect(count('LIVE_KILL', folded)).toBe(0);
    expect(count('KILL', folded)).toBe(count('KILL', events));
    expect(folded.filter((e) => e.type === 'KILL' && typeof e.distance === 'number').length).toBeGreaterThan(0);
    // A DYNAMITE replaces the POPUP that announced the same plant.
    expect(count('DYNAMITE', folded)).toBe(count('DYNAMITE', events));
    expect(count('POPUP', folded)).toBe(count('POPUP', events) - count('DYNAMITE', events));
    // Nine map events named one map within a minute of each other → one line
    // per real load.
    expect(count('MAP', folded) + count('LIVE_MAP', folded)).toBeLessThan(count('MAP', events) + count('LIVE_MAP', events));
    // Order is kept (newest last).
    expect(folded.map((e) => e.seq)).toEqual([...folded.map((e) => e.seq)].sort((a, b) => a - b));
  });

  it('a kill without a twin still reads, and a slot nobody named is not "undefined"', () => {
    expect(describeEvent({ seq: 1, type: 'KILL', killer_slot: 9, victim_slot: 8, mod: 'MOD_KNIFE' }, NAMES)).toBe('slot 9 killed slot 8 · knife');
    expect(describeEvent({ seq: 2, type: 'REVIVE', slots: '9 8' }, NAMES)).toBe('slot 9 revived slot 8');
    expect(describeEvent({ seq: 3, type: 'LIVE_AGGREGATE', slot: 1 }, NAMES)).toBeNull();
    expect(describeEvent({ seq: 4, type: 'PLAYER_JOIN' }, NAMES)).toBe('player join');
  });
});

it('never binds an unnamed historical event to the current occupant of a slot', () => {
  const names = new Map([[1, 'replacement'], [2, 'new victim']]);
  for (const event of [
    { seq: 1, type: 'LIVE_KILL', killer_slot: 1, victim_slot: 2 },
    { seq: 2, type: 'DYNAMITE', slot: 1 },
    { seq: 3, type: 'REVIVE', slots: '1 2' },
    { seq: 4, type: 'DISCONNECT', slot: 1 },
  ]) {
    const folded = foldDoubles([event])[0];
    expect(describeEvent(folded, names)).toBe(describeEvent(folded, new Map()));
  }
  expect(describeEvent({ seq: 5, type: 'KILL', killer: '^1original', victim: 'victim', killer_slot: 1 }, names))
    .toBe('original killed victim');
  expect(describeEvent({ seq: 6, type: 'SAY', name: '^2original', text: 'hello' }, names))
    .toBe('original: hello');
});

it('never folds two LIVEX kills or reuses one legacy twin across a slot disconnect', () => {
  const first = { seq: 1, type: 'LIVE_KILL', killer_slot: 1, victim_slot: 2, killer: 'original', received_at: 1000 };
  const next = { ...first, seq: 2, killer: 'replacement', received_at: 1001 };
  expect(foldDoubles([first, next])).toHaveLength(2);
  const legacy = { ...first, type: 'KILL' };
  const twin = { ...first, seq: 2, distance: 5 };
  const third = { ...first, seq: 3, distance: 9 };
  expect(foldDoubles([legacy, twin, third])).toHaveLength(2);
  expect(foldDoubles([legacy, { seq: 2, type: 'DISCONNECT', slot: 1 }, third]).filter(e => e.type === 'KILL')).toHaveLength(2);
  expect(foldDoubles([legacy, next])).toHaveLength(2);
});


it('keeps explicit support-event names while older envelopes use stable slot labels', () => {
  for (const [type, verb] of [['REVIVE', 'revived'], ['SUPPLY', 'supplied'], ['SHOVE', 'shoved']]) {
    expect(describeEvent({ seq: 1, type, slots: '1 2', actor_name: '^1original', target_name: 'target' }, NAMES))
      .toBe(`original ${verb} target`);
    expect(describeEvent({ seq: 1, type, slots: '1 2' }, NAMES)).toBe(`slot 1 ${verb} slot 2`);
  }
});

it.each(['', '   ', '0x0 1', '0.0 1', 'true 1'])('does not invent slot zero from invalid support slots %j', (slots) => {
  const text = describeEvent({ seq: 1, type: 'REVIVE', slots }, NAMES);
  expect(text).not.toContain('slot 0');
  expect(text).toContain('someone');
});

it.each(['ROUND_START', 'INIT_GAME', 'MAP', 'LIVE_MAP'])('does not fold kills across the %s boundary', (type) => {
  const kills = [
    { seq: 2, type: 'KILL', killer_slot: 1, victim_slot: 2, received_at: 1000 },
    { seq: 4, type: 'LIVE_KILL', killer_slot: 1, victim_slot: 2, received_at: 1001 },
  ];
  const boundary = { seq: 3, type, map_name: 'new-map', received_at: 1000.5 };
  for (const prefix of [[], [{ seq: 1, type: 'MAP', map_name: 'old-map', received_at: 999 }]]) {
    expect(foldDoubles([...prefix, kills[0], boundary, kills[1]]).filter(e => e.type === 'KILL')).toHaveLength(2);
  }
});

it('still pairs real twins across same-map confirmation or empty map metadata', () => {
  for (const map_name of ['known-map', '', '   ']) {
    const events = [
      { seq: 1, type: 'MAP', map_name: 'known-map', received_at: 999 },
      { seq: 2, type: 'KILL', killer_slot: 1, victim_slot: 2, received_at: 1000 },
      { seq: 3, type: 'LIVE_MAP', map_name, received_at: 1000.5 },
      { seq: 4, type: 'LIVE_KILL', killer_slot: 1, victim_slot: 2, received_at: 1001 },
    ];
    expect(foldDoubles(events).filter(e => e.type === 'KILL')).toHaveLength(1);
  }
});

it('merges later source names by server-owned sequence without rewriting input history', () => {
  const original = { seq: 1, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: null, victim: null, distance: 120 };
  const named = { seq: 2, type: 'KILL', duplicate_of: 1, killer_slot: 3, victim_slot: 5, killer: 'Source A', victim: 'Source B' };
  expect(foldDoubles([original])).toHaveLength(1);
  const folded = foldDoubles([original, named]);
  expect(folded).toHaveLength(1);
  expect(folded[0]).toMatchObject({ seq: 1, killer: 'Source A', victim: 'Source B', distance: 120 });
  expect(original.killer).toBeNull();
  expect(describeEvent(folded[0], new Map([[3, 'Replacement']]))).toContain('Source A killed Source B');
});

it('shows orphaned enrichment and combines partial names even when the original left the window', () => {
  const first = { seq: 2, type: 'KILL', duplicate_of: 1, killer_slot: 3, victim_slot: 5, killer: 'A' };
  const second = { seq: 3, type: 'KILL', duplicate_of: 1, killer_slot: 3, victim_slot: 5, victim: 'B' };
  expect(foldDoubles([first, second])).toEqual([{ ...first, victim: 'B' }]);
});

it('does not replace known conflicting identity or an unrelated event via an enrichment link', () => {
  const original = { seq: 1, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, killer: 'Original' };
  const conflict = { seq: 2, type: 'KILL', duplicate_of: 1, killer_slot: 3, victim_slot: 5, killer: 'Other' };
  expect(foldDoubles([original, conflict])).toHaveLength(2);
  expect(foldDoubles([{ seq: 1, type: 'SAY', name: 'Speaker' }, conflict])).toHaveLength(2);
});

it.each([
  ['radar', false, 1], ['supply', true, 1], ['goldrush', true, 2], ['', false, 1],
])('uses accepted map context for kill pairing: %s accepted=%s', (map_name, map_accepted, killCount) => {
  const events = [
    { seq: 1, type: 'MAP', map_name: 'radar', map_accepted: true, received_at: 999 },
    { seq: 2, type: 'MAP', map_name: 'supply', map_accepted: true, received_at: 999.5 },
    { seq: 3, type: 'KILL', killer_slot: 3, victim_slot: 5, killer: 'Source A', victim: 'Source B', received_at: 1000 },
    { seq: 4, type: 'LIVE_MAP', map_name, map_accepted, received_at: 1000.5 },
    { seq: 5, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, distance: 120, received_at: 1001 },
  ];
  const folded = foldDoubles(events);
  expect(folded.filter(e => e.type === 'KILL')).toHaveLength(killCount as number);
  if (!map_accepted) {
    expect(folded.some(e => e.seq === 4)).toBe(false);
    expect(describeEvent(events[3], NAMES)).toBeNull();
  }
  if (killCount === 1) expect(describeEvent(folded.find(e => e.type === 'KILL')!, NAMES))
    .toBe('Source A killed Source B · 120 u');
});


it.each([false, true, undefined])('uses authoritative transition in a cold or truncated map context (%s)', (map_changed) => {
  const events = [
    { seq: 1, type: 'KILL', killer_slot: 3, victim_slot: 5, killer: 'Actor', victim: 'Target', received_at: 1000 },
    { seq: 2, type: 'LIVE_MAP', map_name: 'supply', map_accepted: true, map_changed, received_at: 1000.5 },
    { seq: 3, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, received_at: 1001 },
  ];
  expect(foldDoubles(events).filter(e => e.type === 'KILL' || e.type === 'LIVE_KILL')).toHaveLength(map_changed === false ? 1 : 2);
});

it('keeps a real transition even when a truncated log last saw the same map name', () => {
  const folded = foldDoubles([
    { seq: 1, type: 'MAP', map_name: 'supply', map_changed: true, received_at: 1000 },
    { seq: 2, type: 'KILL', killer_slot: 3, victim_slot: 5, received_at: 1000.1 },
    { seq: 3, type: 'LIVE_MAP', map_name: 'supply', map_accepted: true, map_changed: true, received_at: 1000.5 },
    { seq: 4, type: 'LIVE_KILL', killer_slot: 3, victim_slot: 5, received_at: 1001 },
  ]);
  expect(folded.filter(e => e.type === 'KILL' || e.type === 'LIVE_KILL')).toHaveLength(2);
  expect(folded.filter(e => e.type === 'MAP' || e.type === 'LIVE_MAP')).toHaveLength(2);
});

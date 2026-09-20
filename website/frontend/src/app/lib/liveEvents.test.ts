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
    expect(describeEvent(events.find((e) => e.type === 'DYNAMITE')!, NAMES)).toBe('.lgz planted dynamite at the Door Controls');
    expect(describeEvent(events.find((e) => e.type === 'REVIVE')!, NAMES)).toBe('qmr revived .lgz');
    expect(describeEvent(events.find((e) => e.type === 'CALLVOTE')!, NAMES)).toBe('qmr called a vote: Match Reset');
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
    expect(describeEvent({ seq: 1, type: 'KILL', killer_slot: 9, victim_slot: 8, mod: 'MOD_KNIFE' }, NAMES)).toBe('someone killed someone · knife');
    expect(describeEvent({ seq: 2, type: 'REVIVE', slots: '9 8' }, NAMES)).toBe('someone revived someone');
    expect(describeEvent({ seq: 3, type: 'LIVE_AGGREGATE', slot: 1 }, NAMES)).toBeNull();
    expect(describeEvent({ seq: 4, type: 'PLAYER_JOIN' }, NAMES)).toBe('player join');
  });
});

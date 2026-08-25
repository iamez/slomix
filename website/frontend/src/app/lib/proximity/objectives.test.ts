import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  computeObjectiveTimelineRows,
  computeObjectiveZoneStates,
  shouldRenderObjectiveZone,
  type ObjectiveZone,
  type PathSample,
} from './objectives';
import fixture from './__fixtures__/journey_supply_r11277.json';

/**
 * The port must equal the LEGACY implementation on real recorded data — not
 * merely equal itself. proximity.js does not export these functions, so the
 * test extracts their source (brace-matched, then evaluated in a scratch
 * scope) and runs both sides on the same fixture. Legacy is frozen by policy
 * (P4: fixes only), so extraction fragility is acceptable; if the slice ever
 * fails, this test errors loudly instead of passing vacuously.
 */

const LEGACY_SRC = readFileSync(resolve(__dirname, '../../../../../js/proximity.js'), 'utf-8');

function sliceFunction(name: string): string {
  const marker = `function ${name}(`;
  const start = LEGACY_SRC.indexOf(marker);
  if (start === -1) throw new Error(`legacy source: function ${name} not found`);
  const bodyStart = LEGACY_SRC.indexOf('{', start);
  let depth = 0;
  for (let i = bodyStart; i < LEGACY_SRC.length; i += 1) {
    if (LEGACY_SRC[i] === '{') depth += 1;
    if (LEGACY_SRC[i] === '}') {
      depth -= 1;
      if (depth === 0) return LEGACY_SRC.slice(start, i + 1);
    }
  }
  throw new Error(`legacy source: function ${name} has unbalanced braces`);
}

type LegacyModule = {
  computeObjectiveZoneStates: typeof computeObjectiveZoneStates;
  computeObjectiveTimelineRows: typeof computeObjectiveTimelineRows;
  shouldRenderObjectiveZone: typeof shouldRenderObjectiveZone;
};

function loadLegacy(): LegacyModule {
  const source = [
    'isInsideObjectiveRadius',
    'classifyObjectiveZoneState',
    'shouldRenderObjectiveZone',
    'computeObjectiveZoneStates',
    'computeObjectiveTimelineRows',
  ]
    .map(sliceFunction)
    .join('\n');
  // Deliberate: the ONLY way to run un-exported legacy functions verbatim is
  // evaluating their sliced source. Test-only file; input is our own frozen
  // proximity.js, not user data.
  // eslint-disable-next-line @typescript-eslint/no-implied-eval
  // nosemgrep
  const factory = new Function(
    `${source}\nreturn { computeObjectiveZoneStates, computeObjectiveTimelineRows, shouldRenderObjectiveZone };`,
  );
  return factory() as LegacyModule;
}

const zonesConfig = JSON.parse(
  readFileSync(resolve(__dirname, '../../../../../assets/maps/proximity/objective_zones.json'), 'utf-8'),
) as { maps: Record<string, { objectives: ObjectiveZone[] }> };

const supplyZones = zonesConfig.maps.supply.objectives;

// Fixture paths use `t`; the objective functions read `time` (their feed on
// the legacy page is engagement-event paths, which carry `time`).
function toSamples(path: Array<{ x: number; y: number; t: number }>): PathSample[] {
  return path.map((p) => ({ x: p.x, y: p.y, time: p.t }));
}

const lives = (fixture as { lives: Array<{ path: Array<{ x: number; y: number; t: number }> }> }).lives;
const targetPath = toSamples(lives[0].path).concat(toSamples(lives[1].path));
const attackerPath = toSamples(lives[2].path).concat(toSamples(lives[3].path));

describe('objective zone computation — port vs legacy on recorded data', () => {
  const legacy = loadLegacy();

  it('supply ships 6 objective zones and the fixture is non-trivial', () => {
    expect(supplyZones.length).toBe(6);
    expect(targetPath.length + attackerPath.length).toBe(246);
  });

  it('computeObjectiveZoneStates matches legacy exactly', () => {
    const ported = computeObjectiveZoneStates(targetPath, attackerPath, supplyZones);
    const legacyStates = legacy.computeObjectiveZoneStates(targetPath, attackerPath, supplyZones);
    expect(ported).toEqual(legacyStates);
    expect(ported.length).toBe(supplyZones.length);
    // Real movement near real objectives must register — an all-'outside'
    // result would mean the fixture or the maths silently degraded.
    expect(ported.some((s) => s.state !== 'outside')).toBe(true);
  });

  it('computeObjectiveTimelineRows matches legacy exactly', () => {
    const states = computeObjectiveZoneStates(targetPath, attackerPath, supplyZones);
    const ported = computeObjectiveTimelineRows(targetPath, attackerPath, supplyZones, states, 24);
    const legacyTimeline = legacy.computeObjectiveTimelineRows(targetPath, attackerPath, supplyZones, states, 24);
    expect(ported).toEqual(legacyTimeline);
    expect(ported).not.toBeNull();
    expect(ported!.rows.length).toBeGreaterThan(0);
    expect(ported!.binCount).toBe(24);
  });

  it('shouldRenderObjectiveZone matches legacy on every shipped zone', () => {
    for (const mapEntry of Object.values(zonesConfig.maps)) {
      for (const zone of mapEntry.objectives) {
        expect(shouldRenderObjectiveZone(zone)).toBe(legacy.shouldRenderObjectiveZone(zone));
      }
    }
  });
});

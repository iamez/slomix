/**
 * Objective-zone state computation — COMPUTATION, not drawing, transferred
 * VERBATIM from website/js/proximity.js (shouldRenderObjectiveZone:735,
 * classifyObjectiveZoneState:760, computeObjectiveZoneStates:779,
 * computeObjectiveTimelineRows:892). Unit-testable without a canvas — the
 * one place in the whole migration where a cheap regression proof exists,
 * so the tests run against recorded fixtures already in phase 0
 * (docs/design/08 faza 0 #13, 09 §canvas).
 *
 * Magic numbers are the legacy page's semantics, kept bit-for-bit:
 * core = 0.55r, approach = 1.2r, contested when both sides sat inside r
 * within 1200 ms of each other; timeline 8..40 bins, default 24.
 */

export interface PathSample {
  x: number;
  y: number;
  time?: number;
}

export interface ObjectiveZone {
  id?: string;
  name?: string;
  lua_name?: string;
  type?: string;
  target?: string;
  x: number;
  y: number;
  radius?: number;
}

export type ObjectiveState = 'contested' | 'core' | 'approach' | 'outside';

export interface ObjectiveZoneMetrics {
  targetCoreHits: number;
  targetApproachHits: number;
  attackerCoreHits: number;
  attackerApproachHits: number;
  contestedCount: number;
}

export interface ObjectiveZoneState extends ObjectiveZoneMetrics {
  id: string;
  name: string;
  state: ObjectiveState;
}

export interface ObjectiveTimelineBin {
  state: ObjectiveState;
  start: number;
  end: number;
}

export interface ObjectiveTimeline {
  minTime: number;
  maxTime: number;
  binCount: number;
  rows: Array<{ id: string; name: string; bins: ObjectiveTimelineBin[] }>;
}

export function shouldRenderObjectiveZone(objective: Partial<ObjectiveZone> | null | undefined): boolean {
  const type = String(objective?.type || '').toLowerCase();
  const name = String(objective?.name || '').toLowerCase();
  const luaName = String(objective?.lua_name || '').toLowerCase();
  const target = String(objective?.target || '').toLowerCase();
  const haystack = `${name} ${luaName} ${target}`;

  if (type === 'command_post' || type === 'escort') return true;
  if (haystack.includes('barrier')) return true;

  const hasMgToken = /\bmg\b/.test(haystack) || luaName.includes('_mg') || target.includes('mg42') || target.includes('weaponclip');
  if (hasMgToken) return false;
  if (haystack.includes('cabinet') || haystack.includes('healammo') || haystack.includes('health_and_ammo')) return false;
  if (haystack.includes('controls') || haystack.includes('control') || haystack.includes('utility')) return false;

  return true;
}

export function classifyObjectiveZoneState(metrics: Partial<ObjectiveZoneMetrics>): ObjectiveState {
  if ((metrics.contestedCount || 0) > 0) return 'contested';
  if ((metrics.targetCoreHits || 0) + (metrics.attackerCoreHits || 0) > 0) return 'core';
  if ((metrics.targetApproachHits || 0) + (metrics.attackerApproachHits || 0) > 0) return 'approach';
  return 'outside';
}

export function isInsideObjectiveRadius(
  sample: Partial<PathSample> | null | undefined,
  objective: Partial<ObjectiveZone> | null | undefined,
  radius: number,
): boolean {
  if (!sample || !objective) return false;
  const sx = Number(sample.x);
  const sy = Number(sample.y);
  const ox = Number(objective.x);
  const oy = Number(objective.y);
  if (![sx, sy, ox, oy, radius].every(Number.isFinite)) return false;
  const dx = sx - ox;
  const dy = sy - oy;
  return Math.sqrt(dx * dx + dy * dy) <= radius;
}

function finiteXY(samples: unknown): PathSample[] {
  return (Array.isArray(samples) ? samples : []).filter(
    (p) => Number.isFinite(Number((p as PathSample)?.x)) && Number.isFinite(Number((p as PathSample)?.y)),
  ) as PathSample[];
}

export function computeObjectiveZoneStates(
  targetPath: PathSample[] | null | undefined,
  attackerPath: PathSample[] | null | undefined,
  objectiveZones: ObjectiveZone[] = [],
): ObjectiveZoneState[] {
  const target = finiteXY(targetPath);
  const attacker = finiteXY(attackerPath);
  if (!objectiveZones.length) return [];

  const states: ObjectiveZoneState[] = [];
  for (const objective of objectiveZones) {
    const baseRadius = Number(objective?.radius || 500);
    if (!Number.isFinite(baseRadius) || baseRadius <= 0) continue;
    const coreRadius = baseRadius * 0.55;
    const approachRadius = baseRadius * 1.2;
    const inZoneRadius = baseRadius;

    const metrics: ObjectiveZoneMetrics = {
      targetCoreHits: 0,
      targetApproachHits: 0,
      attackerCoreHits: 0,
      attackerApproachHits: 0,
      contestedCount: 0,
    };

    const targetInZone: number[] = [];
    const attackerInZone: number[] = [];

    for (const sample of target) {
      if (isInsideObjectiveRadius(sample, objective, approachRadius)) metrics.targetApproachHits += 1;
      if (isInsideObjectiveRadius(sample, objective, coreRadius)) metrics.targetCoreHits += 1;
      if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) {
        const sampleTime = Number(sample.time);
        if (Number.isFinite(sampleTime)) targetInZone.push(sampleTime);
      }
    }
    for (const sample of attacker) {
      if (isInsideObjectiveRadius(sample, objective, approachRadius)) metrics.attackerApproachHits += 1;
      if (isInsideObjectiveRadius(sample, objective, coreRadius)) metrics.attackerCoreHits += 1;
      if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) {
        const sampleTime = Number(sample.time);
        if (Number.isFinite(sampleTime)) attackerInZone.push(sampleTime);
      }
    }

    if (targetInZone.length && attackerInZone.length) {
      for (const targetTime of targetInZone) {
        if (attackerInZone.some((attackerTime) => Math.abs(attackerTime - targetTime) <= 1200)) {
          metrics.contestedCount += 1;
          break;
        }
      }
    }

    const state = classifyObjectiveZoneState(metrics);
    states.push({
      id: objective.id || objective.lua_name || objective.name || `objective-${states.length}`,
      name: objective.name || objective.lua_name || 'Objective',
      state,
      ...metrics,
    });
  }
  return states;
}

export function computeObjectiveTimelineRows(
  targetPath: PathSample[] | null | undefined,
  attackerPath: PathSample[] | null | undefined,
  objectiveZones: ObjectiveZone[] = [],
  objectiveStates: ObjectiveZoneState[] = [],
  binCount = 24,
): ObjectiveTimeline | null {
  const withTime = (samples: unknown): PathSample[] =>
    finiteXY(samples).filter((p) => Number.isFinite(Number(p.time)));
  const target = withTime(targetPath);
  const attacker = withTime(attackerPath);
  const allTimes = target.map((s) => Number(s.time)).concat(attacker.map((s) => Number(s.time)));
  if (!objectiveZones.length || !allTimes.length) return null;

  const stateRank: Record<string, number> = { contested: 0, core: 1, approach: 2, outside: 3 };
  const objectiveById = objectiveZones.reduce<Record<string, ObjectiveZone>>((acc, objective) => {
    const id = objective.id || objective.lua_name || objective.name || '';
    if (id) acc[id] = objective;
    return acc;
  }, {});

  const prioritized = (Array.isArray(objectiveStates) ? objectiveStates : [])
    .slice()
    .sort((a, b) => {
      const ar = stateRank[a.state] ?? 4;
      const br = stateRank[b.state] ?? 4;
      if (ar !== br) return ar - br;
      const ah = (a.targetCoreHits || 0) + (a.attackerCoreHits || 0) + (a.targetApproachHits || 0) + (a.attackerApproachHits || 0);
      const bh = (b.targetCoreHits || 0) + (b.attackerCoreHits || 0) + (b.targetApproachHits || 0) + (b.attackerApproachHits || 0);
      return bh - ah;
    })
    .filter((row) => objectiveById[row.id]);

  const selected = prioritized.slice(0, 4);
  if (!selected.length) return null;

  const minTime = Math.min(...allTimes);
  const maxTime = Math.max(...allTimes);
  const span = Math.max(maxTime - minTime, 1);
  const safeBins = Math.max(8, Math.min(40, Number(binCount) || 24));
  const binSize = span / safeBins;

  const rows = selected.map((row) => {
    const objective = objectiveById[row.id];
    const baseRadius = Number(objective?.radius || 500);
    const coreRadius = baseRadius * 0.55;
    const approachRadius = baseRadius * 1.2;
    const inZoneRadius = baseRadius;
    const bins: ObjectiveTimelineBin[] = [];

    for (let idx = 0; idx < safeBins; idx += 1) {
      const start = minTime + idx * binSize;
      const end = idx === safeBins - 1 ? maxTime + 1 : start + binSize;
      let targetInApproach = false;
      let attackerInApproach = false;
      let targetInCore = false;
      let attackerInCore = false;
      let targetInZone = false;
      let attackerInZone = false;

      for (const sample of target) {
        const t = Number(sample.time);
        if (t < start || t >= end) continue;
        if (isInsideObjectiveRadius(sample, objective, approachRadius)) targetInApproach = true;
        if (isInsideObjectiveRadius(sample, objective, coreRadius)) targetInCore = true;
        if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) targetInZone = true;
      }
      for (const sample of attacker) {
        const t = Number(sample.time);
        if (t < start || t >= end) continue;
        if (isInsideObjectiveRadius(sample, objective, approachRadius)) attackerInApproach = true;
        if (isInsideObjectiveRadius(sample, objective, coreRadius)) attackerInCore = true;
        if (isInsideObjectiveRadius(sample, objective, inZoneRadius)) attackerInZone = true;
      }

      let state: ObjectiveState = 'outside';
      if (targetInZone && attackerInZone) state = 'contested';
      else if (targetInCore || attackerInCore) state = 'core';
      else if (targetInApproach || attackerInApproach) state = 'approach';

      bins.push({ state, start, end });
    }

    return { id: row.id, name: row.name, bins };
  });

  return { minTime, maxTime, rows, binCount: safeBins };
}

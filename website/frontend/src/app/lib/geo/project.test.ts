import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { getWorldBounds, withAlpha, worldRadiusToCanvas, worldToCanvasPoint } from './project';
import type { MapTransformConfig } from './mapTransforms';
import { getMapTransformEntry, resolveMapKey } from './mapTransforms';

// The REAL calibration file the site ships — not a hand-copied excerpt, so
// this suite breaks when a map entry changes shape (docs/design/00 §4: the
// prototype's hand-copied table silently dropped sw_goldrush_te).
const CONFIG_PATH = resolve(__dirname, '../../../../../assets/maps/proximity/map_transforms.json');
const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf-8')) as MapTransformConfig;

describe('map_transforms.json (the shipped calibration)', () => {
  it('has all 21 calibrated maps, including sw_goldrush_te', () => {
    expect(Object.keys(config.maps).length).toBe(21);
    expect(config.maps.sw_goldrush_te).toBeDefined();
  });

  it('every alias resolves to a calibrated map', () => {
    for (const alias of ['etl_supply', 'sp_delivery_te', 'et_beach', 'etl_goldrush']) {
      const key = resolveMapKey(alias);
      expect(config.maps[key], `alias '${alias}' -> '${key}' has no transform`).toBeDefined();
    }
  });

  it('getMapTransformEntry answers through aliases and colour codes', () => {
    expect(getMapTransformEntry(config, 'etl_supply')?.map_name).toBe('supply');
    expect(getMapTransformEntry(config, '^1SUPPLY')?.map_name).toBe('supply');
    expect(getMapTransformEntry(config, 'no-such-map')).toBeNull();
  });
});

describe('worldToCanvasPoint on the supply calibration', () => {
  // supply: mapcoordsmins [-3200, 3200], mapcoordsmaxs [3200, -3200] — the
  // same entry the prototypes and replay.js use.
  const bounds = getWorldBounds(config.maps.supply);

  it('projects the world corners onto the canvas corners', () => {
    expect(bounds).not.toBeNull();
    expect(worldToCanvasPoint(-3200, 3200, 256, 256, bounds)).toEqual({ x: 0, y: 0 });
    expect(worldToCanvasPoint(3200, -3200, 256, 256, bounds)).toEqual({ x: 256, y: 256 });
    expect(worldToCanvasPoint(0, 0, 256, 256, bounds)).toEqual({ x: 128, y: 128 });
  });

  it('clamps points outside the calibrated bounds to the edge', () => {
    expect(worldToCanvasPoint(99999, 0, 256, 256, bounds)).toEqual({ x: 256, y: 128 });
    expect(worldToCanvasPoint(0, 99999, 256, 256, bounds)).toEqual({ x: 128, y: 0 });
  });

  it('scales a world radius by the mean px/unit and floors at 2px', () => {
    // 6400 world units across 256 px -> 0.04 px/unit; r=500 -> 20 px.
    expect(worldRadiusToCanvas(500, 256, 256, bounds)).toBeCloseTo(20, 6);
    expect(worldRadiusToCanvas(1, 256, 256, bounds)).toBe(2);
    expect(worldRadiusToCanvas(Number.NaN, 256, 256, bounds)).toBe(0);
  });

  it('returns null for an uncalibrated map (graceful degradation, not a crash)', () => {
    expect(getWorldBounds(null)).toBeNull();
    expect(getWorldBounds({ mapcoordsmins: [0, 0], mapcoordsmaxs: [0, 0] })).toBeNull();
    expect(worldToCanvasPoint(1, 1, 256, 256, null)).toBeNull();
  });
});

describe('withAlpha', () => {
  it('rewrites rgb/rgba alpha and leaves other formats alone', () => {
    expect(withAlpha('rgb(56, 189, 248)', 0.5)).toBe('rgba(56, 189, 248, 0.5)');
    expect(withAlpha('rgba(56, 189, 248, 0.9)', 2)).toBe('rgba(56, 189, 248, 1)');
    expect(withAlpha('#8bb0d6', 0.5)).toBe('#8bb0d6');
  });

  it('keeps the colour on non-finite alpha instead of emitting rgba(..., NaN)', () => {
    expect(withAlpha('rgb(56, 189, 248)', Number.NaN)).toBe('rgb(56, 189, 248)');
    expect(withAlpha('rgb(56, 189, 248)', Infinity)).toBe('rgb(56, 189, 248)');
  });
});

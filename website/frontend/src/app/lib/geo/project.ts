/**
 * World -> canvas projection, transferred VERBATIM from website/js/proximity.js
 * (getWorldBounds:697, worldToCanvasPoint:709, worldRadiusToCanvas:720,
 * clamp:136, withAlpha:140) per the phase-0 transfer rule: the maths moves
 * literally, only the DOM/React boundary is rewritten (docs/design/08).
 *
 * "Forty lines, and the whole game lives in them" — a wrong projection draws
 * a plausible-looking but wrong picture that no table diff catches, which is
 * why these have unit tests against the real map_transforms.json entries
 * already in phase 0 (docs/design/09 §canvas).
 */

export interface WorldBounds {
  mins: [number, number];
  maxs: [number, number];
}

export interface MapTransformLike {
  mapcoordsmins?: unknown;
  mapcoordsmaxs?: unknown;
}

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function withAlpha(color: string, alpha: number): string {
  if (typeof color !== 'string') return color;
  const value = clamp(Number(alpha), 0, 1);
  const rgbaMatch = color.match(/^rgba\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)$/i);
  if (rgbaMatch) {
    return `rgba(${rgbaMatch[1]}, ${rgbaMatch[2]}, ${rgbaMatch[3]}, ${value})`;
  }
  const rgbMatch = color.match(/^rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)$/i);
  if (rgbMatch) {
    return `rgba(${rgbMatch[1]}, ${rgbMatch[2]}, ${rgbMatch[3]}, ${value})`;
  }
  return color;
}

export function getWorldBounds(mapTransform: MapTransformLike | null | undefined): WorldBounds | null {
  const boundsMins = Array.isArray(mapTransform?.mapcoordsmins) ? mapTransform.mapcoordsmins : null;
  const boundsMaxs = Array.isArray(mapTransform?.mapcoordsmaxs) ? mapTransform.mapcoordsmaxs : null;
  const valid = boundsMins && boundsMaxs
    && Number.isFinite(boundsMins[0]) && Number.isFinite(boundsMins[1])
    && Number.isFinite(boundsMaxs[0]) && Number.isFinite(boundsMaxs[1])
    && Math.abs(boundsMaxs[0] - boundsMins[0]) > 0.0001
    && Math.abs(boundsMins[1] - boundsMaxs[1]) > 0.0001;
  if (!valid) return null;
  return { mins: boundsMins as [number, number], maxs: boundsMaxs as [number, number] };
}

export function worldToCanvasPoint(
  x: number,
  y: number,
  width: number,
  height: number,
  worldBounds: WorldBounds | null,
): { x: number; y: number } | null {
  if (!worldBounds) return null;
  const { mins, maxs } = worldBounds;
  const u = (x - mins[0]) / (maxs[0] - mins[0]);
  const v = (mins[1] - y) / (mins[1] - maxs[1]);
  return {
    x: clamp(u, 0, 1) * width,
    y: clamp(v, 0, 1) * height,
  };
}

export function worldRadiusToCanvas(
  radius: number,
  width: number,
  height: number,
  worldBounds: WorldBounds | null,
): number {
  if (!worldBounds || !Number.isFinite(radius)) return 0;
  const { mins, maxs } = worldBounds;
  const pxPerUnitX = width / Math.max(Math.abs(maxs[0] - mins[0]), 1);
  const pxPerUnitY = height / Math.max(Math.abs(mins[1] - maxs[1]), 1);
  return Math.max(2, radius * ((pxPerUnitX + pxPerUnitY) / 2));
}

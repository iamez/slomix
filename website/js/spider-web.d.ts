/**
 * Types for the legacy Spider Web renderer, so its tests can be type-checked.
 *
 * ⚠️ This replaces a `@ts-expect-error` over the import. That directive passed
 * locally and failed in CI with BOTH "unused directive" and "could not find a
 * declaration file" at once — it sat above a multi-line import, so it silenced
 * the line the module specifier was not on. A suppression that depends on how
 * an import is wrapped is not a suppression.
 *
 * Declaring the shapes is also worth more than silence: the tests get real
 * types instead of `any`, so a call with the wrong argument order fails at
 * check time rather than producing a plausible wrong number.
 *
 * `website/js/` is plain ES modules with no build step. This file exists only
 * for the type checker; nothing imports it at runtime.
 */

export interface Camera {
  yaw: number;
  pitch: number;
  zoom: number;
  panX: number;
  panY: number;
}

export interface Viewport {
  cx: number;
  cy: number;
  scale: number;
  midX: number;
  midY: number;
  midZ: number;
  minZ?: number;
  maxZ?: number;
}

export interface Projected {
  x: number;
  y: number;
  /** Painter's-algorithm ordering: larger is nearer the viewer. */
  depth: number;
}

export interface Bounds {
  min: number[];
  max: number[];
}

export interface Label {
  x: number;
  y: number;
  text: string;
}

export function project(
  x: number, y: number, z: number, cam: Camera, view: Viewport,
): Projected;

export function viewportFor(
  mesh: { bounds: Bounds }, canvas: { width: number; height: number }, cam: Camera,
): Viewport;

export function placeLabels(
  labels: Label[], minX?: number, minY?: number,
): Label[];

export function boundsFromPlayers(
  players: Array<Record<string, unknown>>, margin?: number,
): Bounds | null;

export interface EdgeStyle {
  color: string;
  width: number;
  dash: number[];
  alpha: number;
}

export function edgeStyle(kind: string, contested: boolean): EdgeStyle;

export interface BeliefRegion {
  x: number;
  y: number;
  z: number;
  radius: number;
  confidence: number;
  subject: string;
  source: string;
}

export function beliefRegions(
  holder: {
    beliefs?: Array<Record<string, unknown>>;
    position_claim_max_radius?: number;
  } | null | undefined,
): { regions: BeliefRegion[]; unplacedSubjects: string[] };

export function horizonOf(holder: { position_claim_max_radius?: number } | null): number;

export function isTeamPov(pov: unknown): boolean;

export declare const THEME: Record<string, string>;

export function alphaHex(a: number): string;

export function mixHex(from: string, to: string, t: number): string;

export function statusLine(snapshot: Record<string, unknown> | null): string;

export function loadSpiderWebView(params?: Record<string, string>): Promise<void>;

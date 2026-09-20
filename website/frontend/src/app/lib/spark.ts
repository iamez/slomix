/**
 * The one sparkline path this app draws twice — and a note about the one it
 * does NOT share.
 *
 * ⛔⛔ THERE ARE TWO `sparkPath` FUNCTIONS IN THIS TREE AND THEY ARE NOT
 * DUPLICATES. FormPage's normalises to the series' own min-max, so the line
 * shows SHAPE: a rating that moves 0.58 → 0.64 fills the box. Home's is
 * zero-based (`max = Math.max(...values, 1)`, no left pad), so the line shows
 * MAGNITUDE: a value near zero sits near the floor. Merging them would force
 * one meaning onto both charts, which is a worse outcome than two functions —
 * so only the ranged one moves here, and Home's stays where it is with this
 * file naming the reason.
 *
 * Extracted when a third caller appeared (the profile's rating trend). Two
 * copies is a coincidence; three is a component.
 */

/** An SVG path over `values`, normalised to the series' own range.
 *
 * Returns '' for fewer than two points: one point is not a trend, and a path
 * with a single coordinate renders as nothing anyway — better to have the
 * caller decide what to show instead. A flat series (`span` 0) is drawn along
 * the bottom rather than dividing by zero. */
export function sparkPathRanged(values: number[], w: number, h: number, pad: number): string {
  if (values.length < 2) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (w - 2 * pad);
      const y = h - pad - ((v - min) / span) * (h - 2 * pad);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
}

/** The one place a coordinate becomes text: an SVG path over already-scaled
 *  points, one decimal, so no page carries its own `toFixed` and a format
 *  change is one edit. Empty for fewer than two points, as above. */
export function svgPath(points: readonly { x: number; y: number }[]): string {
  if (points.length < 2) return '';
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
}

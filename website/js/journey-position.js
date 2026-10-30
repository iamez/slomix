/** Approximate marker location within exactly one observed path segment.
 * No extrapolation, pause-clock claim or proof of unmarked capture continuity.
 */
export function journeyPointAt(path, time) {
    if (!Number.isFinite(time)) return null;
    const segments = [];
    let segment = null;
    for (const point of path || []) {
        if (![point?.t, point?.x, point?.y].every(Number.isFinite)) {
            segment = null;
            continue;
        }
        if (!segment || point.break_before || point.event === 'capture_resume'
            || point.t < segment[segment.length - 1].t) {
            segment = [];
            segments.push(segment);
        }
        segment.push(point);
    }
    const covering = segments.filter((points) => points[0].t <= time
        && time <= points[points.length - 1].t);
    if (covering.length !== 1) return null;
    return covering[0].reduce((best, point) =>
        Math.abs(point.t - time) < Math.abs(best.t - time) ? point : best);
}

export function formatNumber(val: number): string {
  return typeof val === 'number' && !Number.isInteger(val)
    ? val.toFixed(2)
    : String(Math.round(val));
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString();
}

/** Human-readable hours/minutes, e.g. "2h 15m" or "45m". */
export function formatDurationHM(seconds: number): string {
  if (!seconds || seconds <= 0) return '--';
  const mins = Math.floor(seconds / 60);
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  return hrs > 0 ? `${hrs}h ${remMins}m` : `${mins}m`;
}

/** Minutes:seconds, e.g. "12:05". Null-safe. */
export function formatDurationMS(seconds: number | null | undefined): string {
  const total = Number(seconds || 0);
  if (!Number.isFinite(total) || total <= 0) return '0:00';
  const mins = Math.floor(total / 60);
  const secs = Math.floor(total % 60);
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

/** Full H:MM:SS or M:SS with negative support. Null-safe. */
export function formatSec(v: number | undefined | null): string {
  if (v == null || !Number.isFinite(v)) return '--';
  const neg = v < 0 ? '-' : '';
  let s = Math.floor(Math.abs(v));
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s = s % 60;
  if (h > 0) return `${neg}${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${neg}${m}:${String(s).padStart(2, '0')}`;
}

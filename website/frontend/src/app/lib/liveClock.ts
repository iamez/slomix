/**
 * A clock that keeps running between polls. `/api/live/state` answers
 * `round_elapsed_seconds` as of the moment it was generated and the page
 * asks again every 30 s; shown raw, the "current" clock froze for half a
 * minute and jumped, which is worst exactly at the time-to-beat boundary.
 * The hook adds the seconds elapsed since the answer arrived, once a second,
 * while `running` — and returns the base untouched otherwise.
 */
import { useEffect, useState } from 'react';

export function tickedSeconds(base: number | null, receivedAtMs: number, nowMs: number, running: boolean): number | null {
  if (base == null) return null;
  if (!running) return base;
  return base + Math.max(0, Math.floor((nowMs - receivedAtMs) / 1000));
}

export function useTickingSeconds(base: number | null, receivedAtMs: number, running: boolean): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running || base == null) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running, base, receivedAtMs]);
  return tickedSeconds(base, receivedAtMs, running ? Math.max(now, receivedAtMs) : now, running);
}

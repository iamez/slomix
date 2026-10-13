/** Server-clock retention keeps advancing through delivery failures. */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { LiveEvent } from './liveEvents';

const RETENTION_SECONDS = 600;
type ClockAnchor = { server: number; monotonic: number; sourceBased: boolean };
const projectedTime = (anchor: ClockAnchor) =>
  anchor.server + Math.max(0, performance.now() - anchor.monotonic) / 1000;
const recent = (events: LiveEvent[], now: number) => events.filter((event) =>
  typeof event.received_at === 'number' && Number.isFinite(event.received_at)
  && event.received_at >= now - RETENTION_SECONDS);

export function useLiveEventLog() {
  const [log, setLog] = useState<LiveEvent[]>([]);
  const clock = useRef<ClockAnchor | null>(null);
  const clear = useCallback(() => { clock.current = null; setLog([]); }, []);
  const append = useCallback((events: LiveEvent[], serverTime?: number | null) => {
    // A compatibility envelope can omit server_time while retaining server
    // received_at values. Infer that clock from the newest record, never the
    // browser wall clock; elapsed retention still advances monotonically.
    const timestamps = events.map((event) => event.received_at)
      .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
    const explicitTime = typeof serverTime === 'number' && Number.isFinite(serverTime);
    const sourceTime = explicitTime ? serverTime : timestamps.length ? Math.max(...timestamps) : undefined;
    const previousTime = clock.current ? projectedTime(clock.current) : undefined;
    const sourceBased = clock.current?.sourceBased ?? false;
    const now = explicitTime ? serverTime : sourceTime !== undefined
      ? sourceBased ? Math.max(previousTime ?? sourceTime, sourceTime) : sourceTime
      : previousTime ?? Date.now() / 1000;
    // Earlier untimed rows used a first-seen local anchor. When source time
    // becomes available, translate that anchor without renewing their age.
    const shift = !sourceBased && sourceTime !== undefined && previousTime !== undefined ? now - previousTime : 0;
    clock.current = { server: now, monotonic: performance.now(), sourceBased: sourceBased || sourceTime !== undefined };
    setLog((previous) => recent([...previous.map((event) => shift
      ? { ...event, received_at: (event.received_at as number) + shift } : event), ...events
      .filter((event) => !previous.some((old) => old.seq === event.seq))
      .map((event) => ({ ...event, received_at: event.received_at ?? now }))], now).slice(-200));
  }, []);

  useEffect(() => {
    const anchor = clock.current;
    if (!anchor || log.length === 0) return;
    const expiry = Math.min(...log.map((event) => event.received_at as number)) + RETENTION_SECONDS;
    // One wake-up at the next expiry, not a whole-page one-second ticker.
    // The upper bound also avoids overflowing timers for a future timestamp.
    const delay = Math.max(1, Math.min(600001, (expiry - projectedTime(anchor)) * 1000 + 1));
    const timer = setTimeout(() => setLog((previous) => recent(previous, projectedTime(anchor))), delay);
    return () => clearTimeout(timer);
  }, [log]);

  return { log, append, clear };
}

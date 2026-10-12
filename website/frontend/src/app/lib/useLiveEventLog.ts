/** Server-clock retention keeps advancing through delivery failures. */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { LiveEvent } from './liveEvents';

const RETENTION_SECONDS = 600;
type ClockAnchor = { server: number; monotonic: number };
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
    // Older envelopes use first-seen browser time once, then monotonic elapsed
    // time. A browser clock adjustment must never renew the retention window.
    const now = typeof serverTime === 'number' && Number.isFinite(serverTime)
      ? serverTime : clock.current ? projectedTime(clock.current) : Date.now() / 1000;
    clock.current = { server: now, monotonic: performance.now() };
    setLog((previous) => recent([...previous, ...events
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

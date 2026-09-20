import { useCallback } from 'react';
import { useSearchParams } from 'react-router';

/**
 * A page setting that lives in the address bar instead of in useState.
 *
 * Visitor review 2026-09-07 (level 2): only three of the app's pages could
 * be shared as the reader was seeing them — pick a stat, a period or a
 * filter and the link you send still opens the default. These hooks are the
 * one-line replacement for `useState` on any setting worth sharing.
 *
 * Two rules keep the address bar honest:
 *  - the DEFAULT is never written. A page at its default has a clean URL,
 *    and a link with no parameters is a link to the default.
 *  - a value the page does not recognise falls back to the default rather
 *    than being trusted, so a hand-edited or stale link cannot put the page
 *    into a state it has no rendering for.
 *
 * History: `replace`, so a filter click is not a back-button step. The back
 * button leaves the page, which is what a reader means by it.
 */
export function useUrlState<T extends string>(
  key: string,
  fallback: T,
  allowed?: readonly T[],
): [T, (next: T) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(key);
  const value = raw != null && (allowed == null || (allowed as readonly string[]).includes(raw)) ? (raw as T) : fallback;
  const set = useCallback((next: T) => {
    setParams((prev) => {
      const copy = new URLSearchParams(prev);
      if (next === fallback) copy.delete(key);
      else copy.set(key, next);
      return copy;
    }, { replace: true });
  }, [key, fallback, setParams]);
  return [value, set];
}

/** The same, for a setting whose "off" state is null (no filter applied). */
export function useUrlStateNullable(
  key: string,
  fallback: string | null = null,
): [string | null, (next: string | null) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(key);
  const value = raw != null && raw !== '' ? raw : fallback;
  const set = useCallback((next: string | null) => {
    setParams((prev) => {
      const copy = new URLSearchParams(prev);
      if (next == null || next === '' || next === fallback) copy.delete(key);
      else copy.set(key, next);
      return copy;
    }, { replace: true });
  }, [key, fallback, setParams]);
  return [value, set];
}

/** A whole number in the address bar; anything unparseable is the default. */
export function useUrlNumber(
  key: string,
  fallback: number,
  allowed?: readonly number[],
): [number, (next: number) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get(key);
  const parsed = raw != null && /^-?\d+$/.test(raw) ? Number(raw) : NaN;
  const value = Number.isFinite(parsed) && (allowed == null || allowed.includes(parsed)) ? parsed : fallback;
  const set = useCallback((next: number) => {
    setParams((prev) => {
      const copy = new URLSearchParams(prev);
      if (next === fallback) copy.delete(key);
      else copy.set(key, String(next));
      return copy;
    }, { replace: true });
  }, [key, fallback, setParams]);
  return [value, set];
}

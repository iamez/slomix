/**
 * The frame of every data panel — one place for the house vocabulary
 * branches (Pending / Unavailable / failure-status / Absent-with-reason) so
 * pages cannot drift apart on how a non-answer looks.
 *
 * Born as `ProxPanel` in pages/proximityShared.tsx for the proximity slices
 * (Copilot on #863: the second slice had already duplicated the first one's
 * helpers verbatim). The 2026-09-07 modularity audit measured the same
 * four-way branch hand-written 58 times across the OTHER pages while the
 * proximity pages had it once — so the frame moves here, unchanged, and
 * `panels.test.ts` holds the hand-written count so it can only fall
 * (docs/SPA_MODULARITY.md, slice 1).
 */
import { Stack, type Space } from './layout';
import { Absent, Pending, SectionHead, Unavailable } from './ui';
import { isFailureStatus } from '../lib/responseStatus';

export type PanelQuery<T> = { isPending: boolean; isError: boolean; data: T | undefined };

export function Panel<T extends object>({ label, aside, q, empty, isEmpty, children, gap = 2, parity }: {
  label: string;
  aside?: React.ReactNode;
  q: PanelQuery<T>;
  /** Names what a truthful emptiness means for THIS instrument — a sentence,
   *  or a function of the answer when the answer itself says why (a status
   *  of `partial_data` reads differently from `no_data`). */
  empty: string | ((data: T) => string);
  isEmpty: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
  /** The Stack's step between head and body; the proximity panels use 2,
   *  the story panels 3. Same frame, one knob, so a conversion is not a
   *  visual change. */
  gap?: Space;
  /** `data-parity="page.panel"` for the parity inventory. */
  parity?: string;
}) {
  return (
    <Stack gap={gap} parity={parity}>
      <SectionHead label={label} aside={typeof aside === 'string' ? <span className="lbl">{aside}</span> : aside} />
      {q.isPending && <Pending label={label} />}
      {q.isError && <Unavailable what={label} />}
      {q.data && (isFailureStatus((q.data as { status?: unknown }).status) ? (
        <Unavailable what={label} />
      ) : isEmpty(q.data) ? (
        <Absent reason={typeof empty === 'function' ? empty(q.data) : empty} />
      ) : (
        children(q.data)
      ))}
    </Stack>
  );
}

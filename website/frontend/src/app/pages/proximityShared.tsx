/**
 * The shared frame of every proximity panel — one place for the house
 * vocabulary branches (Pending / Unavailable / failure-status /
 * Absent-with-reason) and the compact row, so the slices cannot drift
 * apart on how a non-answer looks (Copilot on #863: the second slice had
 * already duplicated the first one's helpers verbatim, and the third was
 * about to).
 */
import { Cluster, Stack } from '../components/layout';
import { Absent, Meta, Pending, SectionHead, Unavailable } from '../components/ui';
import { isFailureStatus } from '../lib/responseStatus';

export type PanelQuery<T> = { isPending: boolean; isError: boolean; data: T | undefined };

export function ProxPanel<T extends { status?: string }>({ label, aside, q, empty, isEmpty, children }: {
  label: string;
  aside?: string;
  q: PanelQuery<T>;
  /** Names what a truthful emptiness means for THIS instrument. */
  empty: string;
  isEmpty: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
}) {
  return (
    <Stack gap={2}>
      <SectionHead label={label} aside={aside ? <span className="lbl">{aside}</span> : undefined} />
      {q.isPending && <Pending label={label} />}
      {q.isError && <Unavailable what={label} />}
      {q.data && (isFailureStatus(q.data.status) ? (
        <Unavailable what={label} />
      ) : isEmpty(q.data) ? (
        <Absent reason={empty} />
      ) : (
        children(q.data)
      ))}
    </Stack>
  );
}

export function ProxRow({ name, mid, val }: { name: string; mid?: string; val: string }) {
  return (
    <Cluster gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
      <span style={{ fontSize: 'var(--fs-row)' }}>{name}</span>
      <Cluster gap={3} align="baseline">
        {mid != null && <Meta>{mid}</Meta>}
        <span className="m" style={{ fontSize: 'var(--fs-small)', minWidth: 72, textAlign: 'right' }}>{val}</span>
      </Cluster>
    </Cluster>
  );
}

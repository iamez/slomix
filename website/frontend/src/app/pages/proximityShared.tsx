/**
 * The proximity slices' shared bits: the frame (now `components/Panel.tsx`,
 * re-exported here under its old name) and the compact row, so the slices
 * cannot drift apart on how a non-answer looks (Copilot on #863: the second slice had
 * already duplicated the first one's helpers verbatim, and the third was
 * about to).
 */
import { Cluster } from '../components/layout';
import { Meta } from '../components/ui';
import { Panel } from '../components/Panel';

export type { PanelQuery } from '../components/Panel';

/** The proximity slices' name for the shared frame; the frame itself lives in
 *  components/Panel.tsx since the 2026-09-07 modularity audit (slice 1). */
export const ProxPanel = Panel;

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

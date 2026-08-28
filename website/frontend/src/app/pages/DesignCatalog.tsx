import { useLayoutEffect, useRef, useState } from 'react';
import { Cluster, Stack, space } from '../components/layout';
import type { Space } from '../components/layout';
import {
  ActLink, Chip, KpiTile, Lbl, Pending, SectionHead, StatusDot, Tabs, Unavailable, figure, rowStyle,
} from '../components/ui';

/**
 * The catalogue (docs/design/11, plan step A3). Every component the app owns,
 * in every state it can be in, on one page.
 *
 * Why it earns its place rather than being documentation for its own sake:
 * the owner is going to rework layout and controls repeatedly, and a rework
 * needs somewhere to LOOK at the pieces without hunting for a page that
 * happens to be in the right state. Empty, loading and unavailable are the
 * states that are hardest to find in the wild — a real page shows them only
 * when something is broken — so they are rendered here on purpose, side by
 * side with the full ones.
 *
 * Not in the navigation: it is a workshop surface, reachable by URL. It calls
 * no endpoint, so it cannot break with the data.
 */

const SPACES: Space[] = [1, 2, 3, 4, 5, 6, 7, 8];

/** Sample rows: a pair per line rather than two arrays read by index — the
 * index lookup was a second place a reader had to hold in their head, and a
 * sink to every scanner that reads a[i] with a variable i. */
const SAMPLE_ROWS = [
  { map: 'te_escape2', matches: 293 },
  { map: 'etl_adlernest', matches: 156 },
  { map: 'supply', matches: 122 },
];

const TYPE_SCALE: { token: string; role: string }[] = [
  { token: '--fs-caption', role: 'caption' },
  { token: '--fs-label', role: 'label' },
  { token: '--fs-micro', role: 'micro' },
  { token: '--fs-small', role: 'small' },
  { token: '--fs-value', role: 'value' },
  { token: '--fs-body', role: 'body' },
  { token: '--fs-row', role: 'row' },
  { token: '--fs-lead', role: 'lead' },
  { token: '--fs-kpi', role: 'kpi' },
  { token: '--fs-title', role: 'title' },
  { token: '--fs-display', role: 'display' },
  { token: '--fs-hero', role: 'hero' },
];

/**
 * The size beside each sample is MEASURED, not typed in. A catalogue that
 * repeats the pixel value as static text goes stale the first time someone
 * changes a token during the layout rework this page exists to support: the
 * sample would move and the caption would keep insisting on the old number
 * (Codex on #827). Reading it back off the element means the page cannot lie
 * about its own scale.
 */
function TypeRow({ token, role }: { token: string; role: string }) {
  const sample = useRef<HTMLSpanElement>(null);
  const [size, setSize] = useState<string | null>(null);
  useLayoutEffect(() => {
    if (!sample.current) return;
    const measured = getComputedStyle(sample.current).fontSize;
    setSize(measured && measured !== '0px' ? measured.replace('px', '') : null);
  }, [token]);
  return (
    <Cluster gap={4} align="baseline" justify="between" style={{ padding: 'var(--space-1) 0' }}>
      <span ref={sample} style={{ fontSize: `var(${token})`, letterSpacing: 'var(--track-tight)' }}>
        Slomix
      </span>
      <span className="lbl">{role} · {size ?? 'unmeasured'}</span>
    </Cluster>
  );
}

const COLOURS: { token: string; meaning: string }[] = [
  { token: '--color-ink-950', meaning: 'page' },
  { token: '--color-ink-900', meaning: 'sub-nav, opened row' },
  { token: '--color-ink-850', meaning: 'boxes, tiles' },
  { token: '--color-ink-800', meaning: 'row hover' },
  { token: '--color-rule-900', meaning: 'row hairline' },
  { token: '--color-rule-800', meaning: 'box border' },
  { token: '--color-rule-700', meaning: 'chip border' },
  { token: '--color-rule-600', meaning: 'table head' },
  { token: '--color-rule-500', meaning: 'action underline' },
  { token: '--color-rule-400', meaning: 'active chip border' },
  { token: '--color-text-100', meaning: 'primary text' },
  { token: '--color-text-200', meaning: 'secondary text' },
  { token: '--color-text-300', meaning: 'tertiary text' },
  { token: '--color-text-400', meaning: 'quiet text' },
  { token: '--color-text-500', meaning: 'labels' },
  { token: '--color-text-600', meaning: 'footer' },
  { token: '--color-accent', meaning: 'focus · active' },
  { token: '--color-accent-warm', meaning: 'callout · provenance' },
  { token: '--color-team-a', meaning: 'team a' },
  { token: '--color-team-b', meaning: 'team b' },
  { token: '--color-pos', meaning: 'better' },
  { token: '--color-neg', meaning: 'worse' },
  { token: '--color-neg-strong', meaning: 'worse, emphatic' },
  { token: '--color-ice', meaning: 'looking · running' },
  { token: '--color-idle', meaning: 'neither' },
  { token: '--color-allies', meaning: 'allies' },
  { token: '--color-axis', meaning: 'axis' },
  { token: '--color-speed-1', meaning: 'idle (path)' },
  { token: '--color-speed-2', meaning: 'walk' },
  { token: '--color-speed-3', meaning: 'run' },
  { token: '--color-speed-4', meaning: 'sprint' },
];

function Bench({ name, note, children }: { name: string; note?: string; children: React.ReactNode }) {
  return (
    <Stack gap={3} parity={`design.${name}`} style={{ paddingTop: 'var(--space-6)' }}>
      <SectionHead label={name} aside={note ? <span className="lbl">{note}</span> : undefined} />
      {children}
    </Stack>
  );
}

export function DesignCatalog() {
  const [chip, setChip] = useState('dpm');
  const [tab, setTab] = useState<'summary' | 'players' | 'teamplay'>('summary');

  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-8)' }}>
      <Lbl>workshop · not in the navigation</Lbl>
      <h1 className="h-section" style={{ margin: 'var(--space-3) 0 0', fontSize: 'var(--fs-title)' }}>
        Every piece, in every state.
      </h1>
      <p className="prose-body" style={{ marginTop: 'var(--space-3)' }}>
        This page calls no endpoint. It exists so a rework of layout or controls
        can look at the pieces without hunting for a page that happens to be
        empty, loading or broken today.
      </p>

      <Bench name="colour" note="colour means side, team, better/worse, or provenance — never a metric">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 'var(--space-2)' }}>
          {COLOURS.map((c) => (
            <Cluster key={c.token} gap={2} align="center" style={{ ...rowStyle, padding: 'var(--space-2) 0' }}>
              <span
                aria-hidden
                style={{
                  width: 26, height: 14, flex: 'none',
                  background: `var(${c.token})`,
                  border: '1px solid var(--color-rule-800)',
                }}
              />
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>{c.token.replace('--color-', '')}</span>
              <span className="lbl" style={{ marginLeft: 'auto' }}>{c.meaning}</span>
            </Cluster>
          ))}
        </div>
      </Bench>

      <Bench name="type" note="one scale; a size is a name, not a number">
        <Stack gap={1} divided>
          {TYPE_SCALE.map((t) => (
            <TypeRow key={t.token} token={t.token} role={t.role} />
          ))}
        </Stack>
      </Bench>

      <Bench name="spacing" note="eight steps; a gap is a step, never a pixel">
        <Stack gap={2}>
          {SPACES.map((s) => (
            <Cluster key={s} gap={3} align="center">
              <span className="lbl" style={{ width: 70 }}>space-{s}</span>
              <span style={{ height: 10, width: space(s), background: 'var(--color-accent)' }} />
            </Cluster>
          ))}
        </Stack>
      </Bench>

      <Bench name="controls" note="pressed state rides on aria-pressed / aria-selected">
        <Stack gap={4}>
          <Cluster gap={2}>
            {['dpm', 'kills', 'k/d', 'accuracy'].map((k) => (
              <Chip key={k} active={chip === k} label={k.toUpperCase()} onClick={() => { setChip(k); }} />
            ))}
          </Cluster>
          <Tabs
            tabs={[
              { key: 'summary', label: 'Summary' },
              { key: 'players', label: 'Players' },
              { key: 'teamplay', label: 'Teamplay' },
            ] as const}
            current={tab}
            onSelect={setTab}
          />
          <Cluster gap={4}>
            <ActLink to="/sessions2">view all →</ActLink>
            <Cluster gap={2} align="center"><StatusDot state="ok" /><span className="lbl">ok</span></Cluster>
            <Cluster gap={2} align="center"><StatusDot state="warn" /><span className="lbl">warn</span></Cluster>
            <Cluster gap={2} align="center"><StatusDot state="error" /><span className="lbl">error</span></Cluster>
            <Cluster gap={2} align="center"><StatusDot state="idle" /><span className="lbl">idle</span></Cluster>
          </Cluster>
        </Stack>
      </Bench>

      <Bench name="figures" note="mono, tabular — columns must not dance">
        <Cluster gap={7}>
          <KpiTile value={figure(1760)} label="rounds" />
          <KpiTile value={figure(314.159)} label="dpm" />
          <KpiTile value={figure(0)} label="none yet" />
        </Cluster>
      </Bench>

      <Bench name="states" note="the three that a real page shows only when something is wrong">
        <Stack gap={2} divided>
          <div style={{ padding: 'var(--space-2) 0' }}><Pending label="leaderboard" /></div>
          <div style={{ padding: 'var(--space-2) 0' }}><Unavailable what="weapon stats" /></div>
          <div className="m" style={{ padding: 'var(--space-2) 0', fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
            no map history recorded yet
          </div>
        </Stack>
      </Bench>

      <Bench name="rows" note="a hairline and a hover — never a card">
        {/* No `divided` here: .row already carries the bottom hairline, and
          * stacking both drew two lines between neighbours plus a stray one
          * after the last row — a workshop misrepresenting the very thing it
          * demonstrates (Codex on #827). `divided` is for children that are
          * NOT rows, as in the type and states benches above. */}
        <Stack gap={1}>
          {SAMPLE_ROWS.map((row) => (
            <Cluster key={row.map} gap={4} justify="between" className="row" style={{ padding: 'var(--space-2) 0' }}>
              <span style={{ fontSize: 'var(--fs-row)' }}>{row.map}</span>
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{figure(row.matches)}</span>
            </Cluster>
          ))}
        </Stack>
      </Bench>
    </div>
  );
}

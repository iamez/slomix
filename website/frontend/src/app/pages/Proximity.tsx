/**
 * Proximity — phase 5 opens (docs/design/12 row 12, 17 §1).
 *
 * FIRST SLICE, deliberately: the ten-tab leaderboard section, which
 * 17 §1 names as the core surface (all ten LB_TABS by name). The other
 * legacy panels (roster, engagement analysis, maps, canvases — 42 in
 * 07 §B.2) follow in later PRs; docs/parity/proximity_inventory.json
 * pins them as `pending`, so nothing here can quietly become "done".
 *
 * Value formatting is the legacy page's, kept deliberately: spawn and
 * focus-fire are 0-1 scores to three decimals, reactions are ms,
 * survivors %, movement u/s, KROGT the share of LIVES with a
 * kill/revive/objective/gib/traded contribution.
 */
import { useState } from 'react';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Tabs, Unavailable, figure } from '../components/ui';
import { stripEtColors } from '../lib/names';
import { isFailureStatus } from '../lib/responseStatus';
import { useProximityLeaderboard, useProxScopes, useSsr } from '../lib/queries';
import { ProximityInstruments } from './ProximityInstruments';
import { ProximityCompetitive } from './ProximityCompetitive';
import { ProximityObjectiveIntel } from './ProximityObjectiveIntel';
import { ProximityRoundCanvases } from './ProximityRoundCanvases';
import { ProximityEvents } from './ProximityEvents';
import type { LbCategory, ProximityLeaderboard } from '../lib/types';

const LB_TABS: readonly { key: LbCategory | 'comp_skill'; label: string }[] = [
  { key: 'power', label: 'power rating' },
  { key: 'spawn', label: 'spawn timing' },
  { key: 'crossfire', label: 'crossfire' },
  { key: 'trades', label: 'trade kills' },
  { key: 'reactions', label: 'reactions' },
  { key: 'survivors', label: 'survivors' },
  { key: 'movement', label: 'movement' },
  { key: 'focus_fire', label: 'focus fire' },
  { key: 'krogt', label: 'krogt' },
  { key: 'comp_skill', label: 'comp skill' },
];

const RANGES = [30, 90, 365] as const;

function fmtValue(category: string, value: number): string {
  if (category === 'spawn' || category === 'focus_fire') return value.toFixed(3);
  if (category === 'reactions') return `${figure(value)} ms`;
  if (category === 'survivors') return `${value.toFixed(1)}%`;
  if (category === 'movement') return `${value.toFixed(1)} u/s`;
  if (category === 'krogt') return `${value.toFixed(1)}%`;
  return figure(value);
}

function detailFor(category: string, e: ProximityLeaderboard['entries'][number]): string {
  switch (category) {
    case 'power': {
      const a = e.axes;
      return a
        ? `agg ${a.aggression.toFixed(0)} · awa ${a.awareness.toFixed(0)} · team ${a.teamplay.toFixed(0)} · tim ${a.timing.toFixed(0)}`
        : '';
    }
    case 'spawn':
      return `${figure(e.timed_kills ?? 0)} timed kills · denial ${figure(e.avg_denial_ms ?? 0)} ms`;
    case 'crossfire':
      // Legacy printed "name + partner" here off a field this endpoint has
      // never sent, so its partner was a literal question mark for every
      // row ever rendered. The angle is what the wire actually carries.
      return e.avg_angle != null ? `avg angle ${e.avg_angle.toFixed(1)}°` : '';
    case 'trades':
      return e.avg_reaction_ms != null ? `avg reaction ${figure(e.avg_reaction_ms)} ms` : '';
    case 'reactions':
      return e.samples != null ? `${figure(e.samples)} samples` : '';
    case 'survivors':
      return `${figure(e.total_engagements ?? 0)} engagements · avg ${figure(e.avg_duration_ms ?? 0)} ms`;
    case 'movement':
      return `sprint ${e.sprint_pct?.toFixed(1) ?? '—'}% · ${figure(e.tracks ?? 0)} tracks`;
    case 'focus_fire':
      return `focused ${figure(e.times_focused ?? 0)}× · ${e.avg_attackers?.toFixed(1) ?? '—'} attackers`;
    case 'krogt':
      return e.lives != null ? `${figure(e.lives)} lives` : '';
    default:
      return '';
  }
}

function Board({ category, rangeDays }: { category: LbCategory; rangeDays: number }) {
  const q = useProximityLeaderboard(category, rangeDays);
  return (
    <Stack gap={2}>
      {q.isPending && <Pending label="leaderboard" />}
      {q.isError && <Unavailable what="leaderboard" />}
      {q.data && (isFailureStatus(q.data.status) ? (
        <Unavailable what="leaderboard" />
      ) : q.data.entries.length === 0 ? (
        <Absent reason={`no ${category.replace('_', ' ')} rows in the last ${rangeDays} days — proximity capture only covers sessions where the tracker ran`} />
      ) : (
        <Stack gap={1} className="rows">
          {q.data.entries.map((e, i) => (
            <Cluster key={e.guid} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0' }}>
              <Cluster gap={3} align="baseline">
                <span className="m lbl" style={{ width: 20, textAlign: 'right' }}>{i + 1}</span>
                <span style={{ fontSize: 'var(--fs-row)' }}>{stripEtColors(e.name)}</span>
              </Cluster>
              <Cluster gap={3} align="baseline">
                <Meta>{detailFor(category, e)}</Meta>
                <span className="m" style={{ fontSize: 'var(--fs-value)', width: 92, textAlign: 'right' }}>
                  {fmtValue(category, e.value)}
                </span>
              </Cluster>
            </Cluster>
          ))}
        </Stack>
      ))}
      {q.data?.category === 'power' && q.data.attribution && (
        <Meta>
          attribution: {figure(q.data.attribution.linked_valid)} of {figure(q.data.attribution.total_rows)} source rows linkable
          {q.data.formula_version != null && <> · formula {q.data.formula_version}</>}
        </Meta>
      )}
      {category === 'krogt' && (
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
          share of lives with a kill, revive, objective, gib or traded contribution
        </Lbl>
      )}
    </Stack>
  );
}

/** Comp Skill (SSR) is all-time and group-relative — its endpoint ignores
 * range and scope entirely (owner answer A4), so the range chips do not
 * apply and saying so beats greying them out. */
function CompSkillBoard() {
  const q = useSsr(true);
  return (
    <Stack gap={2}>
      {q.isPending && <Pending label="comp skill" />}
      {q.isError && <Unavailable what="comp skill" />}
      {q.data && (q.data.players.length === 0 ? (
        <Absent reason="no rated players yet — SSR needs at least 5 sessions and 3 components per player" />
      ) : (
        <Stack gap={1} className="rows">
          {q.data.players.slice(0, 10).map((p, i) => (
            <Cluster key={p.player_guid} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0' }}>
              <Cluster gap={3} align="baseline">
                <span className="m lbl" style={{ width: 20, textAlign: 'right' }}>{i + 1}</span>
                <span style={{ fontSize: 'var(--fs-row)' }}>{stripEtColors(p.name)}</span>
              </Cluster>
              <span className="m" style={{ fontSize: 'var(--fs-value)', width: 92, textAlign: 'right' }}>
                {p.ssr.toFixed(1)}
              </span>
            </Cluster>
          ))}
        </Stack>
      ))}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>all-time and group-relative — the range above does not apply here</Lbl>
    </Stack>
  );
}

export function Proximity() {
  const [tab, setTab] = useState<LbCategory | 'comp_skill'>('power');
  const [rangeDays, setRangeDays] = useState<number>(30);
  // Scope for the instruments: a CAPTURE date, defaulting to the newest.
  // The source is /api/proximity/scopes — the dates where the tracker
  // actually recorded — not the sessions list: an evening can exist with
  // no telemetry, and the recorded corpus had exactly that skew (Codex on
  // #861, P1). The 30-day window exists as an explicit chip, never as the
  // first paint (unscoped instrument queries measured up to 1.9 s cold),
  // and a failed or empty scope lookup mounts NOTHING — three reviewers
  // independently caught the fall-through that would have fired thirteen
  // unbounded queries on a degraded page.
  const scopes = useProxScopes();
  const dates = [...new Set((scopes.data?.sessions ?? []).map((s) => s.session_date))].slice(0, 6);
  const [pickedDate, setPickedDate] = useState<string | null>(null);
  const windowPicked = pickedDate === 'window';
  const scopeDate = windowPicked ? null : (pickedDate ?? dates[0] ?? null);
  // Slice 5: the scope grows map and round chips from the SAME hierarchy
  // /proximity/scopes already carries — the canvases' endpoints demand
  // them (a 422 is the wire asking for scope, unreachable via the picker).
  const [pickedMap, setPickedMap] = useState<string | null>(null);
  // The round identity is the PAIR (round_number, round_start_unix): the
  // scopes fixture holds three distinct te_escape2 r1s on one date, and a
  // bare number silently merges them (Codex on #867, P1).
  const [pickedRound, setPickedRound] = useState<{ n: number; rsu: number | null } | null>(null);
  const scopeSession = scopes.data?.sessions.find((x) => x.session_date === scopeDate);
  const maps = (scopeSession?.maps ?? []).map((m) => m.map_name);
  const scopeMap = pickedMap != null && maps.includes(pickedMap) ? pickedMap : null;
  const rounds = (scopeSession?.maps ?? []).find((m) => m.map_name === scopeMap)?.rounds ?? [];
  const scopeRound = pickedRound != null && rounds.some((r) => r.round_number === pickedRound.n && (r.round_start_unix ?? null) === pickedRound.rsu)
    ? pickedRound : null;
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 980 }}>
      <Lbl>proximity · positional telemetry</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        Ten boards from the position tracker.
      </h1>
      <Stack gap={4} parity="proximity.leaderboards" style={{ marginTop: 'var(--space-6)' }}>
        <SectionHead
          label="leaderboards"
          aside={
            <Cluster gap={2} align="baseline">
              {RANGES.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRangeDays(r)}
                  aria-pressed={rangeDays === r}
                  style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', textTransform: 'uppercase', letterSpacing: '0.08em', color: rangeDays === r ? 'var(--color-text-100)' : 'var(--color-text-400)' }}
                >
                  {r}d
                </button>
              ))}
            </Cluster>
          }
        />
        <Tabs
          tabs={LB_TABS.map((t) => ({ key: t.key, label: t.label }))}
          current={tab}
          onSelect={(k) => setTab(k as LbCategory | 'comp_skill')}
          parity="proximity.lb-tabs"
        />
        {tab === 'comp_skill' ? <CompSkillBoard /> : <Board category={tab} rangeDays={rangeDays} />}
      </Stack>
      <Stack gap={3} parity="proximity.scope" style={{ marginTop: 'var(--space-8)' }}>
        <SectionHead
          label="instruments"
          aside={
            <Cluster gap={2} align="baseline" style={{ flexWrap: 'wrap' }}>
              {dates.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setPickedDate(d)}
                  aria-pressed={scopeDate === d}
                  style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', color: scopeDate === d ? 'var(--color-text-100)' : 'var(--color-text-400)' }}
                >
                  {d}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setPickedDate('window')}
                aria-pressed={scopeDate == null}
                style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: scopeDate == null ? 'var(--color-text-100)' : 'var(--color-text-400)' }}
              >
                30d window
              </button>
            </Cluster>
          }
        />
        {/* Fail-closed: unscoped mounting happens ONLY on the explicit
          * window chip. A pending lookup waits; a failed one says so; an
          * empty one names what it means. */}
        {windowPicked ? (
          <>
            <ProximityInstruments sessionDate={null} />
            <ProximityCompetitive sessionDate={null} />
            <ProximityObjectiveIntel sessionDate={null} />
          </>
        ) : scopes.isPending ? (
          <Pending label="scope" />
        ) : scopes.isError ? (
          <Unavailable what="capture dates" />
        ) : scopeDate == null ? (
          <Absent reason="the tracker has not captured any session in this window — there is no date to scope the instruments to" />
        ) : (
          <>
            <ProximityInstruments sessionDate={scopeDate} />
            <ProximityCompetitive sessionDate={scopeDate} />
            <ProximityObjectiveIntel sessionDate={scopeDate} />
            <Stack gap={3} parity="proximity.round-scope" style={{ marginTop: 'var(--space-8)' }}>
              <SectionHead
                label="round canvases"
                aside={
                  <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
                    {maps.map((m) => (
                      <button key={m} type="button" onClick={() => { setPickedMap(scopeMap === m ? null : m); setPickedRound(null); }} aria-pressed={scopeMap === m}
                        style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', color: scopeMap === m ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
                        {m}
                      </button>
                    ))}
                    {scopeMap != null && rounds.map((r) => {
                      const rsu = r.round_start_unix ?? null;
                      const selected = scopeRound != null && scopeRound.n === r.round_number && scopeRound.rsu === rsu;
                      // The start time disambiguates repeats of the same
                      // map+number on one date.
                      const when = rsu != null ? new Date(rsu * 1000).toISOString().slice(11, 16) : null;
                      return (
                        <button key={`${r.round_number}:${rsu ?? 'x'}`} type="button" onClick={() => setPickedRound(selected ? null : { n: r.round_number, rsu })} aria-pressed={selected}
                          style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', color: selected ? 'var(--color-text-100)' : 'var(--color-text-400)' }}>
                          r{r.round_number}{when ? ` ${when}` : ''}
                        </button>
                      );
                    })}
                  </Cluster>
                }
              />
              <ProximityRoundCanvases sessionDate={scopeDate} mapName={scopeMap} roundNumber={scopeRound?.n ?? null} roundStartUnix={scopeRound?.rsu ?? null} />
              <ProximityEvents sessionDate={scopeDate} mapName={scopeMap} roundNumber={scopeRound?.n ?? null} roundStartUnix={scopeRound?.rsu ?? null} />
            </Stack>
          </>
        )}
      </Stack>
      <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-6)' }}>
        slices one to four of the proximity page — journeys, canvases, the
        event drill-down and the round-scoped wave ledger are pinned as
        pending in docs/parity/proximity_inventory.json
      </Lbl>
    </div>
  );
}

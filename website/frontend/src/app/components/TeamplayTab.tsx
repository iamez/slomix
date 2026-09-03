/**
 * The session page's Teamplay tab (stats 2.0 R4, docs/design/18 §C plast 2):
 * the five synergy axes as bars per stable player group, and the per-player
 * trade table for the same night.
 *
 * Two instruments, two scopes, said out loud: synergy is keyed by the
 * gaming session (midnight-safe), the trade table by ONE calendar date —
 * the endpoint has no session key — so a session that crossed midnight
 * shows its first date's trades and the tab names the limit.
 */
import { useMemo } from 'react';

import { DataTable, type DataColumn } from './DataTable';
import { Cluster, Stack } from './layout';
import { Absent, Meta, Pending, SectionHead, Unavailable, figure } from './ui';
import { stripEtColors } from '../lib/names';
import { useProxTradesPlayerStatsForSession, useStorySynergy } from '../lib/queries';
import { isFailureStatus } from '../lib/responseStatus';
import type { ProxTradesPlayerStats, StorySynergy, StorySynergyGroup } from '../lib/types';

/** The five axes, in the legacy order (website/js/story.js SYNERGY_AXES),
 *  each an accessor rather than a key string (the scanners' sink rule). */
const SYNERGY_AXES: readonly { key: string; label: string; title: string; read: (g: StorySynergyGroup) => number }[] = [
  { key: 'crossfire', label: 'crossfire rate', title: 'share of kills with a teammate also engaging the victim', read: (g) => g.crossfire },
  { key: 'trade', label: 'trade coverage', title: 'share of deaths answered by a teammate within the trade window', read: (g) => g.trade },
  { key: 'cohesion', label: 'cohesion', title: 'how close the group stayed while alive (position tracker)', read: (g) => g.cohesion },
  { key: 'push', label: 'push quality', title: 'alignment of the group’s pushes toward the objective', read: (g) => g.push },
  { key: 'medic', label: 'medic bond', title: 'revives and heals inside the group', read: (g) => g.medic },
];

const GROUP_COLOR = new Map<string, string>([['group_a', 'var(--color-accent)'], ['group_b', 'var(--color-accent-warm)']]);

function SynergyGroup({ groupKey, group }: { groupKey: string; group: StorySynergyGroup }) {
  const colour = GROUP_COLOR.get(groupKey) ?? 'var(--color-text-300)';
  return (
    <Stack gap={2} style={{ minWidth: 280, flex: 1 }}>
      <Cluster gap={2} align="baseline">
        <span className="m" style={{ fontSize: 'var(--fs-value)', color: colour }}>{group.composite.toFixed(1)}</span>
        <span className="lbl">{group.players.map(stripEtColors).join(', ')}</span>
      </Cluster>
      <Stack gap={1}>
        {SYNERGY_AXES.map((axis) => {
          const value = Math.max(0, Math.min(100, axis.read(group)));
          return (
            <div key={axis.key} style={{ display: 'grid', gridTemplateColumns: '120px minmax(0, 1fr) 40px', columnGap: 'var(--space-3)', alignItems: 'center' }}>
              <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }} title={axis.title}>{axis.label}</span>
              <div style={{ height: 'var(--space-2)', background: 'var(--color-ink-800)' }} role="img" aria-label={`${axis.label} ${value.toFixed(0)}`}>
                <div style={{ width: `${value}%`, height: '100%', background: colour }} />
              </div>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right' }}>{value.toFixed(0)}</span>
            </div>
          );
        })}
      </Stack>
    </Stack>
  );
}

/** `partial_data` (reason no_r1_data) and `no_data` both come with EMPTY
 *  groups — drawing five zero-width bars would read as "measured zero". */
function synergyAbsence(data: StorySynergy): string | null {
  if (data.status === 'partial_data') return 'insufficient data — no R1 rows for this session, so the groups could not be built';
  if (data.status === 'no_data') return 'no synergy rows for this session — the tracker covered none of its rounds';
  const a = data.groups.group_a;
  const b = data.groups.group_b;
  if (!a || !b) return 'no player groups could be built for this session';
  if (a.players.length === 0 && b.players.length === 0) return 'no player groups could be built for this session';
  return null;
}

/** Both groups, only once both exist — the union above makes a bare
 *  `groups.group_a` read a crash on a no_data night. */
function groupsOf(data: StorySynergy): { key: string; group: StorySynergyGroup }[] {
  const a = data.groups.group_a;
  const b = data.groups.group_b;
  return a && b ? [{ key: 'group_a', group: a }, { key: 'group_b', group: b }] : [];
}

type TradeRow = ProxTradesPlayerStats['players'][number];

const TRADE_COLUMNS: readonly DataColumn<TradeRow>[] = [
  { key: 'player', label: 'player', align: 'left', width: 150, title: 'eight-character guid on this wire; the name as the tracker saw it',
    format: (r) => (r.name ? stripEtColors(r.name) : r.guid), sortValue: (r) => (r.name ? stripEtColors(r.name) : r.guid).toLowerCase() },
  { key: 'opps', label: 'opps', title: 'trade opportunities — teammate deaths this player could have answered', width: 52, sortValue: (r) => r.trade_opps },
  { key: 'attempts', label: 'attempts', title: 'opportunities where the player engaged the killer', width: 66, sortValue: (r) => r.trade_attempts },
  { key: 'success', label: 'success', title: 'trades landed — the killer died within the window', width: 62, sortValue: (r) => r.trade_success },
  { key: 'rate', label: 'rate', title: 'success ÷ opportunities × 100 — null when there was nothing to trade', width: 56,
    sortValue: (r) => (r.trade_opps > 0 ? r.trade_success / r.trade_opps * 100 : null),
    format: (r) => (r.trade_opps > 0 ? `${(r.trade_success / r.trade_opps * 100).toFixed(1)} %` : null) },
  { key: 'missed', label: 'missed', title: 'opportunities with no attempt', width: 56, sortValue: (r) => r.trade_missed },
  { key: 'isolation', label: 'isolation deaths', title: 'deaths with no teammate in range to trade', width: 100, sortValue: (r) => r.isolation_deaths },
  { key: 'avenged', label: 'avenged', title: 'own deaths a teammate traded', width: 62, sortValue: (r) => r.avenged_count },
];

export function TeamplayTab({ gsid, sessionDate }: { gsid: number; sessionDate: string }) {
  const synergy = useStorySynergy(gsid);
  const trades = useProxTradesPlayerStatsForSession(sessionDate);
  const synergyGroups = useMemo(() => (synergy.data ? groupsOf(synergy.data) : []), [synergy.data]);
  const absence = synergy.data ? synergyAbsence(synergy.data) : null;
  const tradesFailed = trades.data != null && isFailureStatus(trades.data.status);
  const tradesEmpty = trades.data != null && !tradesFailed && (!trades.data.ready || trades.data.players.length === 0);

  return (
    <Stack gap={7} parity="session.teamplay">
      <Stack gap={3} parity="session.teamplay.synergy">
        <SectionHead label="synergy" aside={<span className="lbl">two stable groups · five axes, 0–100 · composite weighted</span>} />
        {synergy.isPending && <Pending label="synergy" />}
        {synergy.isError && <Unavailable what="synergy" />}
        {synergy.data && absence && <Absent reason={absence} />}
        {synergy.data && !absence && (
          <Cluster gap={6} align="start" style={{ flexWrap: 'wrap' }}>
            {synergyGroups.map(({ key, group }) => <SynergyGroup key={key} groupKey={key} group={group} />)}
          </Cluster>
        )}
        {synergy.data && !absence && (synergy.data.defaulted_players_count ?? 0) > 0 && (
          <Meta>{figure(synergy.data.defaulted_players_count ?? 0)} player(s) had no telemetry and were scored at the default — the composite is that much less measured</Meta>
        )}
      </Stack>

      <Stack gap={3} parity="session.teamplay.trades">
        <SectionHead label="trades" aside={<span className="lbl">who answered a teammate’s death · position tracker</span>} />
        {trades.isPending && <Pending label="trades" />}
        {trades.isError && <Unavailable what="trades" />}
        {trades.data && tradesFailed && <Unavailable what="trades" />}
        {trades.data && tradesEmpty && (
          <Absent reason={trades.data.message ?? `the trade tracker has no rows dated ${sessionDate}`} />
        )}
        {trades.data && !tradesFailed && !tradesEmpty && (
          <DataTable
            columns={TRADE_COLUMNS}
            rows={trades.data.players}
            rowKey={(r) => r.guid}
            defaultSort={{ key: 'success', dir: 'desc' }}
            minWidth={720}
            label="trades"
          />
        )}
        <Meta>scoped to {sessionDate} — the trade endpoint is keyed by calendar date, so a session that crossed midnight shows its first date here</Meta>
      </Stack>
    </Stack>
  );
}

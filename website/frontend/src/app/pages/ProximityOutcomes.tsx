/**
 * Phase 5 — the outcome instruments: eight date-scope panels closing the
 * proximity page's list surface (07 §B.2). All on the ProxPanel frame;
 * objective-pressure carries its OWN scope vocabulary (scope_note), which
 * is rendered, not translated.
 */
import { Cluster, Stack } from '../components/layout';
import { Lbl, Meta, SectionHead, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import {
  useProxHeadshotRates, useProxKillOutcomes, useProxObjectivePressure,
  useProxSummary, useProxTeamplay, useProxTradesEvents, useProxTradesSummary,
  useProxWeaponAccuracy,
} from '../lib/queries';
import { ProxPanel, ProxRow } from './proximityShared';

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 110 }}>
      <div className="m" style={{ fontSize: 'var(--fs-value)' }}>{value}</div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{label}</Lbl>
    </div>
  );
}

export function ProximityOutcomes({ sessionDate }: { sessionDate: string | null }) {
  const summary = useProxSummary(sessionDate);
  const outcomes = useProxKillOutcomes(sessionDate);
  const headshots = useProxHeadshotRates(sessionDate);
  const teamplay = useProxTeamplay(sessionDate);
  const tradesSummary = useProxTradesSummary(sessionDate);
  const tradesEvents = useProxTradesEvents(sessionDate);
  const accuracy = useProxWeaponAccuracy(sessionDate);
  const pressure = useProxObjectivePressure(sessionDate);

  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="outcomes" aside={<span className="lbl">this session</span>} />

      <div data-parity="proximity.summary">
        <ProxPanel label="the evening in numbers" q={summary} empty={NO_ROWS}
          isEmpty={(d) => d.total_engagements === 0}>
          {(d) => (
            <Cluster gap={6} style={{ flexWrap: 'wrap' }}>
              <Tile label="engagements" value={figure(d.total_engagements)} />
              <Tile label="crossfires" value={figure(d.crossfire_events)} />
              <Tile label="hotzones" value={figure(d.hotzones)} />
              <Tile label="escape rate" value={`${figure(d.escape_rate_pct)}%`} />
              <Tile label="kill rate" value={`${figure(d.kill_rate_pct)}%`} />
              <Tile label="avg attackers" value={figure(d.avg_attackers)} />
            </Cluster>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.kill-outcomes">
        <ProxPanel label="what kills became" q={outcomes} empty={NO_ROWS}
          isEmpty={(d) => d.summary.total_kills === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {/* gib_rate/revive_rate arrive as PERCENTAGES on this wire
                  (2.6 means 2.6%) — unlike kill-outcomes/player-stats,
                  whose kpr is a fraction. Copying that pattern here showed
                  1,800% (Codex on #881). */}
              <ProxRow name="gibbed" mid={`${figure(d.summary.gib_rate)}% of kills`} val={figure(d.summary.gibbed)} />
              <ProxRow name="revived against" mid={`${figure(d.summary.revive_rate)}%`} val={figure(d.summary.revived)} />
              <ProxRow name="tapped out" val={figure(d.summary.tapped_out)} />
              <ProxRow name="lasted to round end" val={figure(d.summary.round_end)} />
              <ProxRow name="denial per kill" val={`${figure(Math.round(d.summary.avg_denied_ms / 100) / 10)} s avg`} />
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.headshot-rates">
        <ProxPanel label="headshot rates" q={headshots} empty={NO_ROWS}
          isEmpty={(d) => d.leaders.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.leaders.slice(0, 8).map((l) => (
                <ProxRow key={l.guid} name={l.name ? stripEtColors(l.name) : l.guid.slice(0, 8)}
                  mid={`${figure(l.head_hits)} of ${figure(l.total_hits)} hits`}
                  val={`${figure(l.headshot_pct)}%`} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.teamplay">
        <ProxPanel label="crossfire craft" aside={teamplay.data ? `${figure(teamplay.data.sampled_engagements)} engagements sampled` : undefined}
          q={teamplay} empty={NO_ROWS} isEmpty={(d) => d.crossfire_kills.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.crossfire_kills.slice(0, 8).map((l) => (
                <ProxRow key={l.guid} name={l.name ? stripEtColors(l.name) : l.guid.slice(0, 8)}
                  mid={`${figure(l.crossfire_participations)} participations · ${figure(Math.round(l.avg_delay_ms))} ms delay`}
                  val={`${figure(l.crossfire_kills)} kills`} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.trades-summary">
        <ProxPanel label="trades" q={tradesSummary} empty={NO_ROWS}
          isEmpty={(d) => d.events === 0 && d.trade_opportunities === 0}>
          {(d) => (
            <Cluster gap={6} style={{ flexWrap: 'wrap' }}>
              <Tile label="opportunities" value={figure(d.trade_opportunities)} />
              <Tile label="attempts" value={figure(d.trade_attempts)} />
              <Tile label="made" value={figure(d.trade_success)} />
              <Tile label="missed" value={figure(d.missed_trade_candidates)} />
              <Tile label="support uptime" value={`${figure(d.support_uptime_pct)}%`} />
              <Tile label="isolation deaths" value={figure(d.isolation_deaths)} />
            </Cluster>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.trades-events">
        <ProxPanel label="trade moments" aside="latest first" q={tradesEvents} empty={NO_ROWS}
          isEmpty={(d) => d.events.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.events.slice(0, 10).map((e, i) => (
                <ProxRow key={`${e.round_id ?? 'x'}:${i}`}
                  name={`${e.victim ? stripEtColors(e.victim) : 'unknown'} down · ${e.killer ? stripEtColors(e.killer) : 'unknown'}`}
                  mid={`${mapLabel(e.map)} r${e.round}${e.outcome ? ` · ${e.outcome}` : ''}`}
                  val={e.success > 0 ? 'traded' : e.attempts > 0 ? 'attempted' : 'missed'} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.weapon-accuracy">
        <ProxPanel label="accuracy" aside="from shots-fired capture" q={accuracy} empty={NO_ROWS}
          isEmpty={(d) => d.leaders.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.leaders.slice(0, 8).map((l) => (
                <ProxRow key={l.guid} name={l.name ? stripEtColors(l.name) : l.guid.slice(0, 8)}
                  mid={`${figure(l.hits)} of ${figure(l.shots)} shots · ${figure(l.kills)} kills`}
                  val={`${figure(l.accuracy)}%`} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity.objective-pressure">
        <ProxPanel label="objective pressure" q={pressure} empty={NO_ROWS}
          isEmpty={(d) => d.players.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.players.slice(0, 8).map((p) => (
                <ProxRow key={p.guid} name={p.name ? stripEtColors(p.name) : p.guid.slice(0, 8)}
                  mid={`${figure(p.kills)} kills under pressure`}
                  val={`${figure(Math.round(p.pressure_seconds))} s`} />
              ))}
              <Meta>{d.scope_note}</Meta>
            </Stack>
          )}
        </ProxPanel>
      </div>
    </Stack>
  );
}

/**
 * Phase 5 — the outcome instruments: eight date-scope panels closing the
 * proximity page's list surface (07 §B.2). All on the ProxPanel frame;
 * objective-pressure carries its OWN scope vocabulary (scope_note), which
 * is rendered, not translated.
 */
import { Cluster, Stack } from '../components/layout';
import { DataTable, type DataColumn } from '../components/DataTable';
import { mmss } from '../components/RoundsTable';
import { Lbl, Meta, SectionHead, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { utcStamp } from '../lib/utcStamp';
import { stripEtColors } from '../lib/names';
import {
  useProxHeadshotRates, useProxKillOutcomes, useProxObjectivePressure,
  useProxSummary, useProxTeamplay, useProxTradesEvents, useProxTradesSummary,
  useProxWeaponAccuracy,
} from '../lib/queries';
import { ProxPanel, ProxRow } from './proximityShared';
import type { ProxKillOutcomeEvent } from '../lib/types';

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

type KillEventRow = ProxKillOutcomeEvent & { id: string };
const KILL_EVENT_COLUMNS: DataColumn<KillEventRow>[] = [
  { key: 'kill_time', label: 'at', title: 'the round clock', format: (e) => mmss(e.kill_time / 1000), sortValue: (e) => e.kill_time },
  { key: 'map', label: 'map', format: (e) => `${mapLabel(e.map_name)} R${String(e.round_number)}`, sortValue: (e) => `${e.map_name} ${String(e.round_number)}` },
  { key: 'killer', label: 'killer', format: (e) => (e.killer_name ? <span title={e.killer_guid ?? undefined}>{stripEtColors(e.killer_name)}</span> : <Meta>—</Meta>), sortValue: (e) => e.killer_name },
  { key: 'victim', label: 'victim', format: (e) => (e.victim_name ? stripEtColors(e.victim_name) : <Meta>—</Meta>), sortValue: (e) => e.victim_name },
  { key: 'kill_mod', label: 'mod', align: 'right', title: 'the engine means-of-death number of the kill', format: (e) => (e.kill_mod == null ? <Meta>—</Meta> : `#${String(e.kill_mod)}`), sortValue: (e) => e.kill_mod ?? null },
  { key: 'outcome', label: 'became', format: (e) => e.outcome.replace(/_/g, ' '), sortValue: (e) => e.outcome },
  { key: 'delta_ms', label: 'after', align: 'right', title: 'seconds from the kill to the outcome', format: (e) => mmss(e.delta_ms / 1000), sortValue: (e) => e.delta_ms },
  { key: 'effective_denied_ms', label: 'denied', align: 'right', title: 'seconds of playtime the kill denied', format: (e) => mmss(e.effective_denied_ms / 1000), sortValue: (e) => e.effective_denied_ms },
  { key: 'gibber', label: 'gibbed by', format: (e) => (e.gibber_name ? <span title={e.gibber_guid ?? undefined}>{stripEtColors(e.gibber_name)}</span> : <Meta>—</Meta>), sortValue: (e) => e.gibber_name },
  { key: 'reviver', label: 'revived by', format: (e) => (e.reviver_name ? <span title={e.reviver_guid ?? undefined}>{stripEtColors(e.reviver_name)}</span> : <Meta>—</Meta>), sortValue: (e) => e.reviver_name },
];

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
            <Stack gap={4}>
              <Cluster gap={6} style={{ flexWrap: 'wrap' }}>
                <Tile label="engagements" value={figure(d.total_engagements)} />
                <Tile label="crossfires" value={figure(d.crossfire_events)} />
                <Tile label="hotzones" value={figure(d.hotzones)} />
                <Tile label="escape rate" value={`${figure(d.escape_rate_pct)}%`} />
                <Tile label="kill rate" value={`${figure(d.kill_rate_pct)}%`} />
                <Tile label="avg attackers" value={figure(d.avg_attackers)} />
                <Tile label="avg engagement" value={`${figure(Math.round(d.avg_duration_ms / 100) / 10)} s`} />
                <Tile label="avg distance" value={`${figure(Math.round(d.avg_distance_m))} m`} />
              </Cluster>
              {/* Movement and sampling — fetched since phase 5, shown since the
                  2026-09-08 ledger: a visitor could not tell how much of the
                  evening the tracker actually saw. */}
              <Cluster gap={6} style={{ flexWrap: 'wrap' }}>
                <Tile label="players" value={figure(d.unique_players)} />
                <Tile label="rounds sampled" value={figure(d.sample_rounds)} />
                <Tile label="track per life" value={`${figure(Math.round(d.avg_track_distance_m))} m`} />
                <Tile label="avg speed" value={figure(Math.round(d.avg_speed))} />
                <Tile label="sprinting" value={`${figure(d.avg_sprint_pct)}%`} />
                <Tile label="first move" value={`${figure(d.avg_time_to_first_move_ms)} ms`} />
              </Cluster>
              <Stack gap={1}>
                <Lbl style={{ fontSize: 'var(--fs-caption)' }}>v5 source rows in this scope</Lbl>
                <Cluster gap={4} style={{ flexWrap: 'wrap' }}>
                  {Object.entries(d.v5_counts).map(([table, n]) => (
                    <Meta key={table}>{table.replace(/^proximity_/, '').replace(/_/g, ' ')} {figure(n)}</Meta>
                  ))}
                  {d.v5_counts_unknown.length > 0 && <Meta>unknown: {d.v5_counts_unknown.join(', ')}</Meta>}
                </Cluster>
                {d.top_duos_partial && <Meta>the duo list is partial — not every pairing of the scope was scored</Meta>}
                {!d.ready && d.message && <Meta>{d.message}</Meta>}
                <Meta>{figure(d.range_days)}-day scope{d.generated_at ? ` · computed ${utcStamp(d.generated_at)}` : ''}</Meta>
              </Stack>
              {/* The crossfire duos the endpoint ranks (legacy proximity.js drew them; the SPA dropped them until 2026-09-09). */}
              {d.top_duos.length > 0 && (
                <Stack gap={1} className="rows">
                  <Lbl style={{ fontSize: 'var(--fs-caption)' }}>crossfire duos</Lbl>
                  {d.top_duos.slice(0, 5).map((duo) => (
                    <ProxRow key={`${duo.player1}+${duo.player2}`} name={`${stripEtColors(duo.player1)} + ${stripEtColors(duo.player2)}`}
                      mid={`${figure(duo.crossfire_count)} crossfires · ${figure(Math.round(duo.avg_delay_ms))} ms apart`} val={`${figure(duo.crossfire_kills)} kills`} />
                  ))}
                </Stack>
              )}
            </Stack>
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
              <ProxRow name="expired (no outcome recorded)" val={figure(d.summary.expired)} />
              <ProxRow name="denial per kill" val={`${figure(Math.round(d.summary.avg_denied_ms / 100) / 10)} s avg`} />
              <ProxRow name="time to the outcome" val={`${figure(Math.round(d.summary.avg_delta_ms / 100) / 10)} s avg`} />
              {d.events.length > 0 && (
                <div style={{ marginTop: 'var(--space-3)' }}>
                  <DataTable<KillEventRow>
                    parity="proximity.kill-outcomes.events"
                    label="the kills, one by one"
                    columns={KILL_EVENT_COLUMNS}
                    rows={d.events.map((e, i) => ({ ...e, id: `${String(e.kill_time)}-${e.victim_guid}-${String(i)}` }))}
                    rowKey={(e) => e.id}
                    minWidth={900}
                  />
                </div>
              )}
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
                  mid={`${figure(l.crossfire_participations)} participations · ${figure(l.crossfire_final_blows)} final blows · ${figure(Math.round(l.avg_delay_ms))} ms delay · focused ${figure(l.times_focused)}×, escaped ${figure(l.focus_escapes)}`}
                  val={`${figure(l.crossfire_kills)} kills`} />
              ))}
              {d.focus_survival && d.focus_survival.length > 0 && (
                <>
                  <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)' }}>under focus — who got out</Lbl>
                  {d.focus_survival.slice(0, 5).map((l) => (
                    <ProxRow key={`f-${l.guid}`} name={l.name ? stripEtColors(l.name) : l.guid.slice(0, 8)}
                      mid={`focused ${figure(l.times_focused)}× · escaped ${figure(l.focus_escapes)} · ${figure(l.crossfire_final_blows)} final blows`}
                      val={`${figure(l.survival_rate_pct)}% survived`} />
                  ))}
                </>
              )}
              {d.sync.length > 0 && (
                <>
                  <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)' }}>tightest crossfire timing</Lbl>
                  {d.sync.slice(0, 5).map((l) => (
                    <ProxRow key={`s-${l.guid}`} name={l.name ? stripEtColors(l.name) : l.guid.slice(0, 8)}
                      mid={`${figure(l.crossfire_participations)} participations · ${figure(l.crossfire_final_blows)} final blows · escaped ${figure(l.focus_escapes)} of ${figure(l.times_focused)}`}
                      val={`${figure(Math.round(l.avg_delay_ms))} ms`} />
                  ))}
                </>
              )}
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
              <Meta>
                {d.maps_counted != null ? `${figure(d.maps_counted)} maps counted` : ''}
                {d.scope_applied ? ` · scope applied: ${Object.entries(d.scope_applied).filter(([, v]) => v != null).map(([k, v]) => `${k.replace(/_/g, ' ')} ${String(v)}`).join(', ') || 'none'}` : ''}
                {d.top_fragger_guids && d.top_fragger_guids.length > 0 ? ` · top fraggers left out of the board: ${d.top_fragger_guids.join(', ')}` : ''}
              </Meta>
            </Stack>
          )}
        </ProxPanel>
      </div>
    </Stack>
  );
}

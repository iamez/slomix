/**
 * Phase 5, slice 4 — carrier and objective intel (07 §B.2): who carried
 * the flag and how honestly, who stopped carriers, who returned flags,
 * vehicle escorts, engineer work, objective runs and objective focus.
 * Eight panels on the shared ProxPanel frame. The sparse-species
 * discipline is in the types up front this time: summaries are the
 * deliberate-{} pattern, resolved names are nullable with guid fallbacks.
 */
import { mmss } from '../components/RoundsTable';
import { DataTable, type DataColumn } from '../components/DataTable';
import { Stack } from '../components/layout';
import { Lbl, Meta, figure } from '../components/ui';
import { mapLabel } from '../lib/maps';
import { stripEtColors } from '../lib/names';
import type { ObjectiveRuns } from '../lib/types';
import {
  useCarrierEvents, useCarrierKills, useCarrierReturns, useConstructionEvents,
  useEscortCredits, useObjectiveFocus, useObjectiveRuns, useVehicleProgress,
} from '../lib/queries';
import { ProxPanel, ProxRow } from './proximityShared';

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

function nameOf(name: string | null | undefined, guid: string): string {
  const stripped = name ? stripEtColors(name) : '';
  return stripped || guid.slice(0, 8);
}

type RecentRun = ObjectiveRuns['recent_runs'][number] & { id: string };
const RECENT_RUN_COLUMNS: DataColumn<RecentRun>[] = [
  { key: 'engineer', label: 'engineer', format: (r) => (r.engineer_name ? stripEtColors(r.engineer_name) : <Meta>—</Meta>), sortValue: (r) => r.engineer_name },
  { key: 'map', label: 'map', format: (r) => `${mapLabel(r.map_name)} · ${r.session_date}`, sortValue: (r) => `${r.session_date} ${r.map_name}` },
  { key: 'action_type', label: 'what happened', format: (r) => r.action_type.replace(/_/g, ' '), sortValue: (r) => r.action_type },
  { key: 'run_type', label: 'run', format: (r) => r.run_type.replace(/_/g, ' '), sortValue: (r) => r.run_type },
  { key: 'track_name', label: 'objective', format: (r) => r.track_name || <Meta>—</Meta>, sortValue: (r) => r.track_name },
  { key: 'approach_time_ms', label: 'approach', align: 'right', title: 'seconds from leaving spawn to the objective', format: (r) => mmss(r.approach_time_ms / 1000), sortValue: (r) => r.approach_time_ms },
  { key: 'path_efficiency', label: 'path', align: 'right', title: 'straight-line distance over distance run', format: (r) => (r.path_efficiency == null ? <Meta>—</Meta> : `${figure(Math.round(r.path_efficiency * 100))}%`), sortValue: (r) => r.path_efficiency },
  { key: 'nearby_teammates', label: 'mates near', align: 'right', sortValue: (r) => r.nearby_teammates },
  { key: 'self_kills', label: 'sk', align: 'right', sortValue: (r) => r.self_kills },
  { key: 'team_kills', label: 'tk', align: 'right', sortValue: (r) => r.team_kills },
  { key: 'killer_name', label: 'stopped by', format: (r) => (r.killer_name ? stripEtColors(r.killer_name) : <Meta>—</Meta>), sortValue: (r) => r.killer_name },
];

export function ProximityObjectiveIntel({ sessionDate }: { sessionDate: string | null }) {
  const carriers = useCarrierEvents(sessionDate);
  const kills = useCarrierKills(sessionDate);
  const returns = useCarrierReturns(sessionDate);
  const vehicles = useVehicleProgress(sessionDate);
  const escorts = useEscortCredits(sessionDate);
  const construction = useConstructionEvents(sessionDate);
  const runs = useObjectiveRuns(sessionDate);
  const focus = useObjectiveFocus(sessionDate);

  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-8)' }}>
      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.carrier-events">
          <ProxPanel label="flag carriers" aside="carries · secures · efficiency" q={carriers} empty={NO_ROWS} isEmpty={(d) => d.carriers.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.summary.total_carries != null && (
                  <Meta>
                    {figure(d.summary.total_carries)} carries · {figure(d.summary.total_secures ?? 0)} secured
                    {' · '}{figure(d.summary.total_killed ?? 0)} carriers killed
                    {d.summary.secure_rate != null && <> · {d.summary.secure_rate.toFixed(1)}% secured</>}
                  </Meta>
                )}
                {d.carriers.slice(0, 5).map((c) => (
                  <ProxRow
                    key={c.guid}
                    name={nameOf(c.name, c.guid)}
                    mid={`${figure(c.secures)} secured · ${figure(c.killed)} killed · eff ${c.avg_efficiency.toFixed(2)}`}
                    val={`${figure(c.carries)} carries`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.carrier-kills">
          <ProxPanel label="carrier stoppers" aside="kills on the flag carrier" q={kills} empty={NO_ROWS} isEmpty={(d) => d.killers.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.killers.slice(0, 5).map((k) => (
                  <ProxRow
                    key={k.guid}
                    name={nameOf(k.name, k.guid)}
                    mid={`stopped ${figure(Math.round(k.avg_distance_stopped))} u from home`}
                    val={`${figure(k.carrier_kills)}×`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.carrier-returns">
          <ProxPanel label="flag returns" aside="dropped flags brought home" q={returns} empty={NO_ROWS} isEmpty={(d) => d.returners.length === 0 && !d.summary.total_returns}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.summary.total_returns != null && (
                  <Meta>{figure(d.summary.total_returns)} returns · avg delay {figure(Math.round((d.summary.avg_delay_ms ?? 0) / 1000))} s</Meta>
                )}
                {d.returners.slice(0, 5).map((r) => (
                  <ProxRow key={r.guid} name={nameOf(r.name, r.guid)} mid={`avg ${figure(Math.round(r.avg_delay_ms / 1000))} s after the drop`} val={`${figure(r.returns)}×`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.escort-credits">
          <ProxPanel label="vehicle escorts" aside="distance moved with the vehicle" q={escorts} empty={NO_ROWS} isEmpty={(d) => d.escorts.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.escorts.slice(0, 5).map((e) => (
                  <ProxRow
                    key={e.guid}
                    name={nameOf(e.name, e.guid)}
                    mid={`${figure(Math.round(e.total_proximity_ms / 1000))} s alongside · ${figure(e.total_samples)} samples`}
                    val={`${figure(e.total_credit_distance)} u`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.vehicle-progress">
          <ProxPanel label="vehicle progress" aside="per round" q={vehicles} empty={NO_ROWS} isEmpty={(d) => d.vehicles.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.vehicles.slice(0, 6).map((v, i) => (
                  <ProxRow
                    key={`${v.map_name}:${v.round_number}:${i}`}
                    name={`${v.vehicle_name} · ${mapLabel(v.map_name)} r${v.round_number}`}
                    mid={v.destroyed_count > 0 ? `destroyed ${figure(v.destroyed_count)}×` : undefined}
                    val={`${figure(Math.round(v.total_distance))} u`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.construction">
          <ProxPanel label="engineer work" aside="plants · defuses · builds" q={construction} empty={NO_ROWS} isEmpty={(d) => d.engineers.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.engineers.slice(0, 5).map((e) => (
                  <ProxRow
                    key={e.guid}
                    name={nameOf(e.name, e.guid)}
                    mid={`${figure(e.plants)} plants · ${figure(e.defuses)} defuses · ${figure(e.constructions)} builds`}
                    val={`${figure(e.total_events)} events`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.objective-runs">
          <ProxPanel label="objective runs" aside="approaches to the objective" q={runs} empty={NO_ROWS} isEmpty={(d) => d.objective_runners.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.summary.total_runs != null && (
                  <Meta>
                    {figure(d.summary.total_runs)} runs · {figure(d.summary.total_denied ?? 0)} denied
                    {d.summary.most_active_objective && <> · busiest: {d.summary.most_active_objective}</>}
                  </Meta>
                )}
                {d.objective_runners.slice(0, 5).map((r) => (
                  <ProxRow
                    key={r.engineer_guid}
                    name={nameOf(r.engineer_name, r.engineer_guid)}
                    mid={`${figure(r.successful_runs)} ok · ${figure(r.denied_runs)} denied${r.avg_path_efficiency != null ? ` · path ${figure(Math.round(r.avg_path_efficiency * 100))}%` : ''} · ${figure(r.solo_runs)} solo · ${figure(r.assisted_runs)} assisted · ${figure(r.team_effort_runs)} team · ${figure(r.unopposed_runs)} unopposed · ${figure(r.plants)} plants · ${figure(r.defuses)} defuses · ${figure(r.builds)} builds · ${figure(r.destroys)} destroys · ${figure(r.total_self_kills)} sk · ${figure(r.total_team_kills)} tk`}
                    val={`${figure(r.total_runs)} runs`}
                  />
                ))}
                {d.recent_runs.length > 0 && (
                  <div style={{ marginTop: 'var(--space-3)' }}>
                    <DataTable<RecentRun>
                      parity="proximity.objective-runs.recent"
                      label="recent runs"
                      columns={RECENT_RUN_COLUMNS}
                      rows={d.recent_runs.map((run, i) => ({ ...run, id: `${run.session_date}-${run.map_name}-${String(i)}` }))}
                      rowKey={(run) => run.id}
                      minWidth={860}
                    />
                  </div>
                )}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.objective-focus">
          <ProxPanel label="objective focus" aside="time spent near objectives" q={focus} empty={NO_ROWS} isEmpty={(d) => d.players.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.summary.objectives_tracked != null && (
                  <Meta>{figure(d.summary.objectives_tracked)} objectives tracked · avg {figure(Math.round(d.summary.avg_time_near_obj_s ?? 0))} s near</Meta>
                )}
                {d.players.slice(0, 5).map((p) => (
                  <ProxRow
                    key={p.guid}
                    name={nameOf(p.name, p.guid)}
                    mid={`${figure(p.objectives_played)} objectives · avg ${figure(p.avg_dist)} u`}
                    val={`${figure(Math.round(p.total_time_s))} s`}
                  />
                ))}
                {d.objectives.slice(0, 3).map((o) => (
                  <ProxRow key={`${o.map_name}:${o.objective}`} name={`${o.objective} · ${mapLabel(o.map_name)}`} mid={`${figure(o.players)} players`} val={`${figure(Math.round(o.avg_time_s))} s avg`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        flag and objective telemetry — an evening without carriable flags or
        tracked vehicles leaves the matching panels honestly empty
      </Lbl>
    </Stack>
  );
}

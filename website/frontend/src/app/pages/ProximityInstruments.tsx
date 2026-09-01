/**
 * Phase 5, slice 2 — the instruments (07 §B.2): thirteen single-endpoint
 * panels of the legacy proximity page, each a summary line plus its top
 * rows, all sharing one session-date scope. The quality panel is the
 * data-completeness band design 12 asks for — the truth strip that says
 * which source tables actually captured this scope before any number
 * below it is believed.
 *
 * Everything renders through the house vocabulary: Pending / Unavailable /
 * Absent-with-reason, and a 200 whose status is a failure renders as a
 * failure. The cohesion timeline (measured 1,880 points for one evening)
 * is drawn as a thinned sparkline, never a table.
 */
import { Cluster, Stack } from '../components/layout';
import { Absent, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { stripEtColors } from '../lib/names';
import { ProxPanel, ProxRow } from './proximityShared';
import {
  useProxAimLock, useProxClasses, useProxCohesion, useProxCombatPositions,
  useProxCrossfireAngles, useProxFocusFire, useProxLuaTrades, useProxPushes,
  useProxQuality, useProxReactions, useProxRevives, useProxSpawnTiming,
  useProxSupportSummary,
} from '../lib/queries';
import { mapLabel } from '../lib/maps';
import type { ProxCohesion } from '../lib/types';

/** The data-completeness band: which source tables actually captured this
 * scope. Required sources that are not ready are the headline; optional
 * ones (shot_fired) are named, not hidden — the gunfire channel was dark
 * for two weeks in August and this strip is where that must show. */
function QualityBand({ sessionDate }: { sessionDate: string | null }) {
  const q = useProxQuality(sessionDate);
  return (
    <Stack gap={2} parity="proximity.quality">
      <SectionHead label="data completeness" aside={<span className="lbl">per source table · this scope</span>} />
      {q.isPending && <Pending label="data completeness" />}
      {q.isError && <Unavailable what="data completeness" />}
      {q.data && (q.data.overall_status !== 'ready' && q.data.overall_status !== 'ok' ? (
        // The HTTP-200 error shape carries only statuses — formatting its
        // missing counts crashed the whole route into the error boundary
        // instead of this line (Codex on #861, P1).
        <Unavailable what={`data completeness (${q.data.overall_status})`} />
      ) : (
        <Stack gap={1}>
          <Meta>
            scope {q.data.selected_scope_status} · maintenance {q.data.global_maintenance_status}
            {q.data.round_correlation.avg_completeness_pct != null && (
              <>
                {' · '}correlation {q.data.round_correlation.avg_completeness_pct.toFixed(1)}%
                {' ('}{q.data.round_correlation.complete_count}/{q.data.round_correlation.correlation_count} complete{')'}
              </>
            )}
          </Meta>
          <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
            {Object.entries(q.data.signals).map(([key, sig]) => (
              <span
                key={key}
                className="m"
                title={`${sig.table} · ${figure(sig.row_count)} rows${sig.required ? '' : ' · optional'}`}
                style={{
                  fontSize: 'var(--fs-caption)',
                  border: '1px solid var(--color-rule-700)',
                  padding: 'var(--space-1) var(--space-2)',
                  color: sig.ready ? 'var(--color-text-300)' : 'var(--color-neg)',
                }}
              >
                {sig.table.replace(/^proximity_|^storytelling_/, '')} {sig.ready ? '·' : '✕'} {figure(sig.row_count)}
              </span>
            ))}
          </Cluster>
          {q.data.warnings.length > 0 && (
            <Meta>{q.data.warnings.map((w) => w.message).join(' · ')}</Meta>
          )}
        </Stack>
      ))}
    </Stack>
  );
}

function CohesionSparkline({ data }: { data: ProxCohesion }) {
  const teams = ['ALLIES', 'AXIS'] as const;
  const colors: Record<string, string> = { ALLIES: 'var(--color-accent)', AXIS: 'var(--color-accent-warm)' };
  const w = 560; const h = 60;
  const all = data.timeline;
  if (all.length < 2) return null;
  // Math.max(1, …): an all-zero evening must draw a flat line, not NaN
  // coordinates that silently blank the chart (CodeRabbit on #861).
  const maxD = Math.max(1, ...all.map((t) => t.dispersion));
  // A SHARED time axis: deriving x from each team's local index forced
  // samples at different times onto the same column — the recorded fixture
  // has different timestamp sets per team (Codex on #861).
  const t0 = Math.min(...all.map((t) => t.time));
  const t1 = Math.max(...all.map((t) => t.time));
  const span = Math.max(1, t1 - t0);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', maxWidth: w, height: h }} role="img" aria-label="team dispersion over the evening">
      {teams.map((team) => {
        const pts = all.filter((t) => t.team === team);
        // Thinned to ~140 points: the wire carries ~1,900 for an evening and
        // a polyline of that many segments buys nothing at 60px tall.
        const step = Math.max(1, Math.floor(pts.length / 140));
        const thin = pts.filter((_, i) => i % step === 0);
        const path = thin.map((t, i) => {
          const x = ((t.time - t0) / span) * w;
          const y = h - (t.dispersion / maxD) * (h - 4) - 2;
          return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
        }).join(' ');
        return <path key={team} d={path} fill="none" stroke={colors[team]} strokeWidth="1" />;
      })}
    </svg>
  );
}

export function ProximityInstruments({ sessionDate }: { sessionDate: string | null }) {
  const spawn = useProxSpawnTiming(sessionDate);
  const aim = useProxAimLock(sessionDate);
  const cohesion = useProxCohesion(sessionDate);
  const angles = useProxCrossfireAngles(sessionDate);
  const pushes = useProxPushes(sessionDate);
  const trades = useProxLuaTrades(sessionDate);
  const revives = useProxRevives(sessionDate);
  const focus = useProxFocusFire(sessionDate);
  const support = useProxSupportSummary(sessionDate);
  const positions = useProxCombatPositions(sessionDate);
  const classes = useProxClasses(sessionDate);
  const reactions = useProxReactions(sessionDate);
  const noTracker = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-8)' }}>
      <QualityBand sessionDate={sessionDate} />

      <div className="home-cols3" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.spawn-timing">
          <ProxPanel label="spawn timing" aside="denial of respawn windows" q={spawn} empty={noTracker} isEmpty={(d) => d.total_events === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.total_events)} timed kills</Meta>
                {/* The board wants 3+ kills per player — a narrow scope can
                  * hold real events and no qualifier (Codex on #861 r2). */}
                {d.leaders.length === 0 && <Meta>nobody reached the three-kill board threshold here</Meta>}
                {d.leaders.slice(0, 5).map((l) => (
                  <ProxRow key={l.guid} name={stripEtColors(l.name)} mid={`${figure(l.kills)} kills · denial ${figure(l.avg_denial_ms)} ms`} val={l.avg_score.toFixed(3)} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.aim-lock">
          <ProxPanel label="aim lock" aside="sustained on-target tracking" q={aim} empty={noTracker} isEmpty={(d) => d.total_events === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.total_events)} locks</Meta>
                {d.leaders.length === 0 && <Meta>nobody reached the three-lock board threshold here</Meta>}
                {d.leaders.slice(0, 5).map((l) => (
                  <ProxRow key={l.guid} name={stripEtColors(l.name)} mid={`${figure(l.locks)} locks · err ${l.avg_err_deg.toFixed(1)}°`} val={`${figure(l.avg_lock_ms)} ms`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.lua-trades">
          <ProxPanel label="trade kills" aside="lua-detected avenges" q={trades} empty={noTracker} isEmpty={(d) => d.leaders.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.leaders.slice(0, 5).map((l) => (
                  <ProxRow key={l.guid} name={stripEtColors(l.name)} mid={`fastest ${figure(l.fastest_ms)} ms`} val={`${figure(l.trades)} · ${figure(l.avg_reaction_ms)} ms`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.revives">
          <ProxPanel label="revives" aside="medics under pressure" q={revives} empty={noTracker} isEmpty={(d) => d.summary.total_revives === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.summary.total_revives)} revives · {d.summary.under_fire_pct.toFixed(1)}% under fire</Meta>
                {/* The board needs 2+ revives per medic, so a sparse scope
                  * can have real totals and NO qualifying leader — the
                  * totals must survive that (Codex on #861). */}
                {d.leaders.length === 0 ? (
                  <Meta>no medic reached the two-revive board threshold here</Meta>
                ) : d.leaders.slice(0, 5).map((l) => (
                  <ProxRow key={l.guid} name={stripEtColors(l.name)} mid={`${figure(l.under_fire_count)} under fire`} val={figure(l.revives)} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.focus-fire">
          <ProxPanel label="focus fire" aside="who the room shoots at" q={focus} empty={noTracker} isEmpty={(d) => d.targets.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.summary.total_events)} events · avg {d.summary.avg_attackers.toFixed(1)} attackers</Meta>
                {d.targets.slice(0, 5).map((t) => (
                  <ProxRow key={t.guid} name={stripEtColors(t.name)} mid={`${figure(t.total_damage_taken)} dmg taken`} val={`${figure(t.times_focused)}×`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.combat-positions">
          <ProxPanel label="kill distances" aside="from the position tracker" q={positions} empty={noTracker} isEmpty={(d) => !d.summary.total_kills}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>
                  {figure(d.summary.total_kills ?? 0)} kills · median {figure(d.summary.median_kill_distance ?? 0)} u
                </Meta>
                {d.by_class.map((c) => (
                  <ProxRow key={c.class} name={c.class.toLowerCase()} mid={`${figure(c.kills)} kills`} val={`${figure(c.avg_distance)} u`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.cohesion">
          <ProxPanel label="team cohesion" aside="dispersion over the evening" q={cohesion} empty={noTracker} isEmpty={(d) => d.team_summary.length === 0}>
            {(d) => (
              <Stack gap={2}>
                <Cluster gap={4} style={{ flexWrap: 'wrap' }}>
                  {d.team_summary.map((t) => (
                    <Meta key={t.team}>
                      {t.team.toLowerCase()}: dispersion {t.avg_dispersion.toFixed(0)} · {t.avg_alive.toFixed(1)} alive · {figure(t.samples)} samples
                    </Meta>
                  ))}
                </Cluster>
                <CohesionSparkline data={d} />
                {d.buddy_pairs.slice(0, 4).map((b) => (
                  <ProxRow key={b.guids} name={b.guids} mid={`${figure(b.times_paired)}× paired`} val={`${figure(b.avg_distance)} u`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.pushes">
          <ProxPanel label="team pushes" aside="coordinated advances" q={pushes} empty={noTracker} isEmpty={(d) => d.team_summary.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.team_summary.map((t) => (
                  <ProxRow key={t.team} name={t.team.toLowerCase()} mid={`${figure(t.objective_pushes)} at objectives · quality ${t.avg_quality.toFixed(2)}`} val={figure(t.pushes)} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.crossfire-angles">
          <ProxPanel label="crossfire angles" aside="two shooters, one target" q={angles} empty={noTracker} isEmpty={(d) => d.total_opportunities === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>
                  {figure(d.executed)} of {figure(d.total_opportunities)} executed ({d.utilization_rate_pct.toFixed(1)}%) · avg {d.avg_angle.toFixed(0)}°
                </Meta>
                {d.top_duos.slice(0, 5).map((duo) => (
                  <ProxRow
                    key={`${duo.teammate1_guid}:${duo.teammate2_guid}`}
                    name={`${duo.name ? stripEtColors(duo.name) : duo.teammate1_guid.slice(0, 8)} + ${duo.partner_name ? stripEtColors(duo.partner_name) : duo.teammate2_guid.slice(0, 8)}`}
                    mid={`avg ${duo.avg_angle.toFixed(0)}°`}
                    val={`${figure(duo.executions)}×`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.support-summary">
          <ProxPanel label="support uptime" aside="time spent near teammates" q={support} empty={noTracker} isEmpty={(d) => !d.summary.total_rounds}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.summary.total_rounds ?? 0)} rounds · avg {(d.summary.avg_uptime_pct ?? 0).toFixed(1)}%</Meta>
                {d.by_map.slice(0, 5).map((m) => (
                  <ProxRow key={m.map_name} name={mapLabel(m.map_name)} mid={`${figure(m.rounds)} rd`} val={`${m.avg_uptime_pct.toFixed(1)}%`} />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.classes">
          <ProxPanel label="classes" aside="movement by role" q={classes} empty={noTracker} isEmpty={(d) => d.classes.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.classes.map((c) => (
                  <ProxRow
                    key={c.player_class}
                    name={c.player_class.toLowerCase()}
                    mid={`${figure(c.tracks)} tracks · sprint ${c.avg_sprint_pct == null ? '—' : `${c.avg_sprint_pct.toFixed(0)}%`}`}
                    val={c.avg_distance == null ? '—' : `${figure(Math.round(c.avg_distance))} u`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>

        <div data-parity="proximity.reactions">
          <ProxPanel label="reactions" aside="return fire · dodge · support" q={reactions} empty={noTracker} isEmpty={(d) => d.class_summary.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.return_fire.slice(0, 3).map((r) => (
                  <ProxRow key={`rf:${r.guid}`} name={stripEtColors(r.name)} mid={`return fire · ${figure(r.samples)} samples`} val={`${figure(r.reaction_ms)} ms`} />
                ))}
                {d.class_summary.map((c) => (
                  <ProxRow
                    key={c.player_class}
                    name={c.player_class.toLowerCase()}
                    mid={`${figure(c.events)} events`}
                    // null, not zero: a class with no return-fire SAMPLES has
                    // no average to claim (Codex on #861, P1).
                    val={c.avg_return_fire_ms == null ? '— rf' : `${figure(c.avg_return_fire_ms)} ms rf`}
                  />
                ))}
              </Stack>
            )}
          </ProxPanel>
        </div>
      </div>
    </Stack>
  );
}

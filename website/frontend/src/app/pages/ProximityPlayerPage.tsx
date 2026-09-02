/**
 * Phase 5 — the proximity player profile (route proximity-player,
 * /proximity/player/:guid). The class-B page: the old React tree was the
 * only consumer of profile/radar, so parity here is measured against that
 * tree, not the legacy JS site. Windows are named on every panel — the
 * profile family reads 90 days, the prox score reads 30 — and an unknown
 * guid answers 200 with zeros and the guid echoed as a name, which this
 * page renders as "nothing captured", never as a real profile of zeros.
 */
import { useParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { stripEtColors } from '../lib/names';
import {
  useProxDuos, useProxHitRegions, useProxHitRegionsByWeapon,
  useProxKillOutcomePlayerStats, useProxMovementStats, useProxPlayerCard,
  useProxPlayerProfile, useProxPlayerRadar, useProxScoresForPlayer,
  useProxScoresFormula, useProxTradesPlayerStats,
} from '../lib/queries';
import { ProxPanel, ProxRow } from './proximityShared';

const PROFILE_DAYS = 90;
const SCORE_DAYS = 30;

/** ET weapon ids as the tracker emits them (copied from the old tree's
 *  only consumer — the ids are engine constants, not guesses). */
const WEAPON_NAMES: Record<number, string> = {
  3: 'Knife', 8: 'MP40', 9: 'Thompson', 10: 'Sten',
  15: 'Panzerfaust', 19: 'FG42', 23: 'Garand', 28: 'K43',
  32: 'Colt', 33: 'Luger', 35: 'Grenade', 36: 'Grenade',
  44: 'Landmine', 47: 'Mortar', 50: 'Dynamite', 57: 'MG42',
};

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ minWidth: 120 }}>
      <div className="m" style={{ fontSize: 'var(--fs-value)' }}>{value}</div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{label}</Lbl>
    </div>
  );
}

function polar(cx: number, cy: number, r: number, angleDeg: number): [number, number] {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

function RadarChart({ axes }: { axes: { label: string; value: number }[] }) {
  const size = 300; const cx = size / 2; const cy = size / 2; const R = 105;
  const n = axes.length;
  if (n < 3) return null;
  const ring = (r: number) =>
    axes.map((_, i) => polar(cx, cy, r, (360 / n) * i).map((v) => v.toFixed(1)).join(',')).join(' ');
  const dataPts = axes
    .map((a, i) => polar(cx, cy, (Math.min(Math.max(a.value, 0), 100) / 100) * R, (360 / n) * i))
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${size} ${size}`}
      style={{ width: '100%', maxWidth: size, overflow: 'visible' }} role="img" aria-label="player radar">
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={ring(R * f)} fill="none" stroke="var(--color-rule-900)" strokeWidth="1" />
      ))}
      <polygon points={dataPts} fill="var(--color-accent)" fillOpacity="0.18" stroke="var(--color-accent)" strokeWidth="1.4" />
      {axes.map((a, i) => {
        const [x, y] = polar(cx, cy, R + 24, (360 / n) * i);
        return (
          <text key={a.label} x={x} y={y} textAnchor="middle" dominantBaseline="middle"
            style={{ fill: 'var(--color-text-400)', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {a.label} {Math.round(a.value)}
          </text>
        );
      })}
    </svg>
  );
}

export function ProximityPlayerPage() {
  const params = useParams();
  const guid = params.guid ?? null;

  const profile = useProxPlayerProfile(guid, PROFILE_DAYS);
  const radar = useProxPlayerRadar(guid, PROFILE_DAYS);
  const scores = useProxScoresForPlayer(guid, SCORE_DAYS);
  const outcomes = useProxKillOutcomePlayerStats(guid, PROFILE_DAYS);
  const hitRegions = useProxHitRegions(guid, PROFILE_DAYS);
  const byWeapon = useProxHitRegionsByWeapon(guid, PROFILE_DAYS);
  const movement = useProxMovementStats(guid, PROFILE_DAYS);
  const card = useProxPlayerCard(guid, PROFILE_DAYS);
  const duos = useProxDuos(guid, PROFILE_DAYS);
  const trades = useProxTradesPlayerStats(guid, PROFILE_DAYS);
  const formula = useProxScoresFormula();

  if (guid == null || guid === '') {
    return <Absent block reason="no player named — open a profile from the proximity leaderboards" />;
  }
  if (profile.isPending) return <Pending label="player profile" />;
  if (profile.isError || !profile.data) return <Unavailable what="player profile" />;
  const p = profile.data;
  if (p.total_engagements === 0) {
    // The wire's zero-form: unknown guid or nothing captured in the window.
    return (
      <Stack gap={3} style={{ paddingTop: 'var(--space-7)' }}>
        <Lbl>proximity · player profile</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>{guid}</h1>
        <Absent block reason={`no proximity capture for this player in the last ${PROFILE_DAYS} days — the tracker only covers sessions where it ran`} />
      </Stack>
    );
  }

  const own = <T extends { guid: string }>(rows: T[] | undefined): T | null =>
    rows?.find((r) => r.guid === guid) ?? null;

  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-7)' }}>
      <Stack gap={2}>
        <Lbl>proximity · player profile · {PROFILE_DAYS}d window</Lbl>
        <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>{stripEtColors(p.player_name)}</h1>
        <Meta>{p.guid}</Meta>
      </Stack>

      <div data-parity="proximity-player.profile">
        <SectionHead label="the record" aside={<span className="lbl">{PROFILE_DAYS}d</span>} />
        <Cluster gap={6} style={{ flexWrap: 'wrap', marginTop: 'var(--space-3)' }}>
          <Tile label="engagements" value={figure(p.total_engagements)} />
          <Tile label="kills" value={figure(p.total_kills)} />
          <Tile label="escape rate" value={`${figure(p.escape_rate)}%`} />
          <Tile label="deaths" value={figure(p.deaths)} />
          <Tile label="crossfired" value={figure(p.crossfire_count)} />
          <Tile label="trades made" value={figure(p.trades_made)} />
          <Tile label="timed kills" value={figure(p.timed_kills)} />
          <Tile label="spawn denial" value={`${figure(Math.round(p.avg_denial_ms / 100) / 10)} s avg`} />
        </Cluster>
        <Cluster gap={6} style={{ flexWrap: 'wrap', marginTop: 'var(--space-4)' }}>
          <Tile label="return fire" value={`${figure(p.avg_return_fire_ms)} ms`} />
          <Tile label="dodge" value={`${figure(p.avg_dodge_ms)} ms`} />
          <Tile label="support react" value={`${figure(p.avg_support_reaction_ms)} ms`} />
          <Tile label="avg speed" value={`${figure(p.avg_speed)} u/s`} />
          <Tile label="sprint" value={`${figure(p.sprint_pct)}%`} />
          <Tile label="per life" value={`${figure(p.avg_distance_per_life)} u`} />
        </Cluster>
      </div>

      <div data-parity="proximity-player.radar">
        <SectionHead label="radar" aside={radar.data ? <span className="lbl">{radar.data.formula_version}</span> : undefined} />
        {radar.isPending && <Pending label="radar" />}
        {radar.isError && <Unavailable what="radar" />}
        {radar.data && (
          <Stack gap={2} style={{ marginTop: 'var(--space-3)' }}>
            <Cluster gap={7} align="start" style={{ flexWrap: 'wrap' }}>
              <RadarChart axes={radar.data.axes} />
              <Stack gap={2}>
                <Tile label="composite" value={figure(radar.data.composite)} />
                {radar.data.unscored.mechanical != null && (
                  <Tile label="mechanical (unscored)" value={figure(radar.data.unscored.mechanical)} />
                )}
                <Meta>axes from {radar.data.axis_definitions_from} · teamplay from {radar.data.teamplay_source}, {figure(radar.data.teamplay_observation_window_days)}d</Meta>
                {radar.data.teamplay_degraded && (
                  <Absent reason={`teamplay axis degraded${radar.data.teamplay_fallback_reason ? ` — ${radar.data.teamplay_fallback_reason}` : ''}`} />
                )}
              </Stack>
            </Cluster>
          </Stack>
        )}
      </div>

      <div data-parity="proximity-player.prox-score">
        <ProxPanel label="prox score" aside={`${SCORE_DAYS}d window · formula ${scores.data?.formula_version ?? '—'}`} q={scores}
          empty="not ranked in this window — too few scored rounds" isEmpty={(d) => d.players.length === 0}>
          {(d) => {
            const row = own(d.players);
            if (row == null) return <Absent reason="not ranked in this window — too few scored rounds" />;
            if (!d.quality.ranking_available) {
              return <Absent reason={`ranking unavailable — ${d.quality.successful_sources}/${d.quality.total_sources} sources answered`} />;
            }
            return (
              <Stack gap={1} className="rows">
                <ProxRow name="overall" mid={`rank ${figure(row.rank)} in window`} val={figure(row.prox_overall)} />
                <ProxRow name="combat" val={figure(row.prox_combat)} />
                <ProxRow name="team" val={figure(row.prox_team)} />
                <ProxRow name="gamesense" val={figure(row.prox_gamesense)} />
                {d.quality.successful_sources < d.quality.total_sources && (
                  <Meta>{figure(d.quality.successful_sources)}/{figure(d.quality.total_sources)} sources answered</Meta>
                )}
                {formula.data && (
                  <Meta>
                    how it is scored ({formula.data.version}):{' '}
                    {Object.values(formula.data.categories)
                      .map((c) => `${c.label.toLowerCase()} ${figure(Math.round(c.weight_in_overall * 100))}%`)
                      .join(' · ')}
                    {' · '}min {figure(formula.data.min_engagements)} engagements
                  </Meta>
                )}
              </Stack>
            );
          }}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.kill-outcomes">
        <ProxPanel label="kill permanence" aside={`${PROFILE_DAYS}d`} q={outcomes}
          empty="no finished kills in this scope" isEmpty={(d) => own(d.kill_permanence_leaders) == null && own(d.revive_rate_leaders) == null}>
          {(d) => {
            const kp = own(d.kill_permanence_leaders);
            const rv = own(d.revive_rate_leaders);
            return (
              <Stack gap={1} className="rows">
                {kp && <ProxRow name="kills gibbed" mid={`${figure(kp.gibs)} of ${figure(kp.total_kills)}`} val={`${figure(Math.round(kp.kpr * 1000) / 10)}%`} />}
                {kp && <ProxRow name="revived against" mid={`${figure(kp.tapouts)} tapouts`} val={figure(kp.revives_against)} />}
                {kp && <ProxRow name="denial per kill" val={`${figure(Math.round(kp.avg_denied_ms / 100) / 10)} s`} />}
                {rv && <ProxRow name="own deaths revived" mid={`${figure(rv.times_revived)} of ${figure(rv.times_killed)}`} val={`${figure(Math.round(rv.revive_rate * 1000) / 10)}%`} />}
                {rv && <ProxRow name="own deaths gibbed" val={`${figure(Math.round(rv.gib_rate * 1000) / 10)}%`} />}
              </Stack>
            );
          }}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.hit-regions">
        <ProxPanel label="hit regions" aside={`${PROFILE_DAYS}d · hits dealt`} q={hitRegions}
          empty="no recorded hits in this scope" isEmpty={(d) => own(d.players) == null}>
          {(d) => {
            const row = own(d.players);
            if (row == null) return <Absent reason="no recorded hits in this scope" />;
            return (
              <Stack gap={1} className="rows">
                <ProxRow name="head" mid={`${figure(row.head_pct)}% of ${figure(row.total_hits)} hits`} val={figure(row.head)} />
                <ProxRow name="body" val={figure(row.body)} />
                <ProxRow name="arms" val={figure(row.arms)} />
                <ProxRow name="legs" val={figure(row.legs)} />
              </Stack>
            );
          }}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.hit-regions-by-weapon">
        <ProxPanel label="per weapon" aside={`${PROFILE_DAYS}d · top by hits`} q={byWeapon}
          empty="no recorded hits in this scope" isEmpty={(d) => d.weapons.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.weapons.slice(0, 8).map((w) => (
                <ProxRow key={w.weapon_id}
                  name={WEAPON_NAMES[w.weapon_id] ?? `weapon #${w.weapon_id}`}
                  mid={`${figure(w.total)} hits · ${figure(w.total_damage)} dmg`}
                  val={`${figure(w.headshot_pct)}% head`} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.player-card">
        <ProxPanel label="the competitive card" aside={`${PROFILE_DAYS}d`} q={card}
          empty="no scored rounds in this window" isEmpty={(d) => d.stagger.kills === 0 && d.clutch.situations === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              <ProxRow name="stagger kills" mid={`${figure(d.stagger.stagger_kills)} of ${figure(d.stagger.kills)} kills`} val={`${figure(d.stagger.stagger_rate)}%`} />
              <ProxRow name="time denied" mid={`attack ${figure(Math.round(d.sides.attack.denied_s / 60))} min · defense ${figure(Math.round(d.sides.defense.denied_s / 60))} min`} val={`${figure(Math.round(d.stagger.denied_s / 60))} min`} />
              <ProxRow name="clutches" mid={`${figure(d.clutch.wins)} of ${figure(d.clutch.situations)} situations`} val={`${figure(d.clutch.win_pct)}%`} />
              {d.clutch.best && (
                <ProxRow name="best clutch" mid={`${figure(d.clutch.best.kills)} kills vs ${figure(d.clutch.best.enemies)}`} val={d.clutch.best.survived ? 'survived' : 'fell'} />
              )}
              <ProxRow name="man-advantage conversions" val={figure(d.man_advantage.conversions)} />
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.duos">
        <ProxPanel label="crossfire partners" aside={`${PROFILE_DAYS}d`} q={duos}
          empty="no crossfire pairs in this window" isEmpty={(d) => d.duos.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              {d.duos.slice(0, 6).map((u, i) => (
                <ProxRow key={i}
                  name={`${u.player1 ? stripEtColors(u.player1) : '?'} + ${u.player2 ? stripEtColors(u.player2) : '?'}`}
                  mid={`${figure(u.crossfire_count)} crossfires · ${figure(Math.round(u.avg_delay_ms))} ms delay`}
                  val={`${figure(u.crossfire_kills)} kills`} />
              ))}
            </Stack>
          )}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.trades">
        <ProxPanel label="trade economy" aside={`${PROFILE_DAYS}d`} q={trades}
          empty="no trade opportunities in this window"
          isEmpty={(d) => !d.players.some((r) => guid.startsWith(r.guid))}>
          {(d) => {
            // This wire carries EIGHT-char guids (the guid[:8] family) —
            // full-guid equality silently rendered absence over real data.
            const row = d.players.find((r) => guid.startsWith(r.guid)) ?? null;
            if (row == null) return <Absent reason="no trade opportunities in this window" />;
            return (
              <Stack gap={1} className="rows">
                <ProxRow name="trades made" mid={`${figure(row.trade_attempts)} attempts of ${figure(row.trade_opps)} chances`} val={figure(row.trade_success)} />
                <ProxRow name="missed" val={figure(row.trade_missed)} />
                <ProxRow name="deaths avenged by team" val={figure(row.avenged_count)} />
                <ProxRow name="isolation deaths" val={figure(row.isolation_deaths)} />
              </Stack>
            );
          }}
        </ProxPanel>
      </div>

      <div data-parity="proximity-player.movement">
        <ProxPanel label="movement" aside={`${PROFILE_DAYS}d`} q={movement}
          empty="no movement tracks in this scope" isEmpty={(d) => own(d.players) == null}>
          {(d) => {
            const row = own(d.players);
            if (row == null) return <Absent reason="no movement tracks in this scope" />;
            return (
              <Stack gap={1} className="rows">
                <ProxRow name="stance" mid={`crouch ${figure(row.crouching_pct)}% · prone ${figure(row.prone_pct)}%`} val={`stand ${figure(row.standing_pct)}%`} />
                <ProxRow name="speed" mid={`peak avg ${figure(row.avg_peak_speed)} u/s`} val={`${figure(row.avg_speed)} u/s`} />
                <ProxRow name="sprint share" val={`${figure(row.avg_sprint_pct)}%`} />
                <ProxRow name="lives tracked" mid={`${figure(Math.round(row.alive_sec / 60))} min alive`} val={figure(row.tracks)} />
              </Stack>
            );
          }}
        </ProxPanel>
      </div>

      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        every panel names its window — the profile family reads {PROFILE_DAYS} days,
        the prox score {SCORE_DAYS}; proximity capture only covers sessions where
        the tracker ran
      </Lbl>
    </Stack>
  );
}

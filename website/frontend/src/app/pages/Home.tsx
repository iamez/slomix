import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../lib/api';
import {
  useActivityCalendar, useAvailabilityOverview, useChallengeCurrent,
  useLastSession, useLiveStatus, useOverview, useQuickLeaders,
  useRecentMatches, useSeasonCurrent, useSeasonLeaders, useSeasonSummary,
  useSessions, useSkillMovers, useTonight, useTrends,
} from '../lib/queries';
import type { LastSession, SkillMoverRow, StatsTrends } from '../lib/types';
import {
  ActLink, Lbl, Pending, SectionHead, StatusDot, Unavailable,
  figure, lblStyle, rowStyle,
} from '../components/ui';

/**
 * Home (docs/design/12 row 1) — visual canon is home.dc.html (decision O8);
 * home-i-full and the legacy loader map define the SCOPE: the legacy view
 * runs 22 loaders of which FOUR are dead (fetches whose target DOM does not
 * exist — updateLiveSession, loadLastSession→#ls-*, loadPredictions,
 * loadMatchesView). Parity here is with what the legacy page RENDERS, so
 * the dead loaders are deliberately not carried over — except last-session,
 * whose endpoint is the honest source for the hero and per-map list this
 * canon actually shows.
 *
 * The canon's kills-per-minute evening trace is absent on purpose: no
 * endpoint serves a per-minute series for an evening (same reasoning as the
 * landing sparkline). The three activity charts come from /api/stats/trends
 * and render as plain SVG polylines — the DATA is the parity, not Chart.js.
 */

function sparkPath(values: number[], w: number, h: number, pad: number): string {
  if (values.length < 2) return '';
  const max = Math.max(...values, 1);
  return values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - pad - (v / max) * (h - 2 * pad);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
}

function TopBand() {
  const live = useLiveStatus();
  const data = live.isError ? undefined : live.data;
  return (
    <div data-parity="home.status-band" style={{ borderBottom: '1px solid var(--color-rule-800)', background: 'var(--color-ink-800)', margin: '0 -8px', padding: '12px 8px' }}>
      <div className="landing-split" style={{ gap: 34 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <StatusDot state={data?.game_server.online ? 'ok' : 'idle'} />
            <span style={{ ...lblStyle, fontSize: 9 }}>game server</span>
          </span>
          {live.isPending && <Pending label="server" />}
          {live.isError && <Unavailable what="server" />}
          {data && (
            <>
              <span className="m" style={{ fontSize: 13 }}>{data.game_server.hostname}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{data.game_server.map ?? '—'}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>
                {data.game_server.player_count} / {data.game_server.max_players} players
              </span>
              {data.game_server.ping_ms != null && (
                <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginLeft: 'auto' }}>{data.game_server.ping_ms} ms</span>
              )}
            </>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <StatusDot state={(data?.voice_channel.count ?? 0) > 0 ? 'ok' : 'idle'} />
            <span style={{ ...lblStyle, fontSize: 9 }}>voice</span>
          </span>
          {/* voice_channel.error is a failure INSIDE the 200 — its zero is
            * an initialization, not an empty room (Codex wave 3). */}
          {data && (data.voice_channel.error
            ? <Unavailable what="voice" />
            : (
              <span className="m" style={{ fontSize: 13, color: 'var(--color-text-400)' }}>
                {data.voice_channel.count > 0 ? `${data.voice_channel.count} in voice` : 'No one in voice'}
              </span>
            ))}
        </div>
      </div>
    </div>
  );
}

function evening(last: LastSession): { day: string; date: string } {
  const parsed = new Date(`${last.date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return { day: last.date, date: '' };
  return {
    day: parsed.toLocaleDateString('en-GB', { weekday: 'long' }),
    date: parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' }),
  };
}

function Hero() {
  const last = useLastSession();
  if (last.isPending) return <div style={{ paddingTop: 52 }}><Pending label="last session" /></div>;
  if (last.isError || !last.isSuccess) return <div style={{ paddingTop: 52 }}><Unavailable what="last session" /></div>;
  const d = last.data;
  const when = evening(d);
  // Played pairings, not unique names — the fixture has 4 names over 5
  // R1 rows (same rule as the figures strip).
  const mapsPlayed = d.matches.filter((m) => m.round_number === 1).length;
  return (
    <div data-parity="home.hero" className="landing-split" style={{ paddingTop: 52, alignItems: 'end' }}>
      <div>
        <Lbl>Last night{d.gaming_session_id != null ? ` · session ${d.gaming_session_id}` : ''}</Lbl>
        <div style={{ fontSize: 40, letterSpacing: '0.04em', textTransform: 'uppercase', lineHeight: 1.05, marginTop: 12 }}>
          {when.day}<br />{when.date}
        </div>
        <div className="m" style={{ fontSize: 13, color: 'var(--color-text-400)', marginTop: 12 }}>
          {d.rounds} rounds · {mapsPlayed} maps · {d.player_count} players
        </div>
        {/* No session id on the latest rounds is a supported backend state —
          * the date route is the fallback that still identifies the evening. */}
        <ActLink
          to={d.gaming_session_id != null ? `/session-detail/${d.gaming_session_id}` : `/session-detail/date/${d.date}`}
          style={{ display: 'inline-block', marginTop: 18 }}
        >
          Open the evening →
        </ActLink>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end', gap: 18, flexWrap: 'wrap' }}>
        {d.scoring.available ? (
          <>
            <div style={{ textAlign: 'right', paddingBottom: 14 }}>
              <Lbl style={{ fontSize: 9 }}>box score</Lbl>
              <Lbl style={{ fontSize: 9, marginTop: 3 }}>sides swap every map</Lbl>
            </div>
            <div style={{ textAlign: 'right' }}>
              <Lbl>{d.scoring.team_a_name.toLowerCase()}</Lbl>
              <div className="m" style={{ fontSize: 74, lineHeight: 0.84, color: 'var(--color-accent)' }}>{d.scoring.team_a_score}</div>
            </div>
            <div className="m" style={{ fontSize: 26, color: '#3f3d38', paddingBottom: 12 }}>/</div>
            <div>
              <Lbl>{d.scoring.team_b_name.toLowerCase()}</Lbl>
              <div className="m" style={{ fontSize: 74, lineHeight: 0.84, color: 'var(--color-accent-warm)' }}>{d.scoring.team_b_score}</div>
            </div>
          </>
        ) : (
          <Lbl style={{ fontSize: 9 }}>score not attributed for this session</Lbl>
        )}
      </div>
    </div>
  );
}

/** The canon's five evening figures, each SUMMED from the session's own
 * per-player rows — the halves are the truth, the sum is arithmetic. */
function EveningFigures() {
  const last = useLastSession();
  if (last.isPending) return <div style={{ padding: '18px 0' }}><Pending label="figures" /></div>;
  if (!last.isSuccess) return <div style={{ padding: '18px 0' }}><Unavailable what="figures" /></div>;
  const d = last.data;
  // Substitutes live in unassigned_players — leaving them out silently
  // shrinks the evening (Codex on #811).
  const players = [...d.teams.flatMap((t) => t.players), ...(d.unassigned_players ?? [])];
  // player_count > 0 with ZERO player rows is the aggregation-failure
  // shape inside a 200 — sums over nobody would publish zero kills for a
  // played evening (Codex wave 3).
  if (players.length === 0 && d.player_count > 0) {
    return <div style={{ padding: '18px 0' }}><Unavailable what="figures" /></div>;
  }
  const sum = (pick: (p: LastSession['teams'][number]['players'][number]) => number) =>
    players.reduce((acc, p) => acc + pick(p), 0);
  // Maps PLAYED, not distinct names: the fixture itself replays maps
  // (4 names over 5 pairings) — an R1 row marks each map started.
  const mapsPlayed = d.matches.filter((m) => m.round_number === 1).length;
  const cells = [
    { k: 'rounds', v: String(d.rounds) },
    { k: 'maps played', v: String(mapsPlayed) },
    { k: 'kills', v: sum((p) => p.kills).toLocaleString('en-US') },
    { k: 'headshot kills', v: sum((p) => p.headshot_kills).toLocaleString('en-US') },
    { k: 'revives', v: sum((p) => p.revives_given).toLocaleString('en-US') },
  ];
  return (
    <div data-parity="home.evening-figures" className="home-grid-5" style={{ marginTop: 42, borderTop: '1px solid var(--color-rule-800)', borderBottom: '1px solid var(--color-rule-800)' }}>
      {cells.map((c) => (
        <div key={c.k} style={{ padding: '18px 0 16px' }}>
          <div className="m" style={{ fontSize: 30, lineHeight: 1 }}>{c.v}</div>
          <Lbl style={{ marginTop: 6 }}>{c.k}</Lbl>
        </div>
      ))}
    </div>
  );
}

const RANGES = [14, 30, 90] as const;

function Insights() {
  const [days, setDays] = useState<number>(14);
  const trends = useTrends(days);
  const data = trends.isError ? undefined : trends.data;
  const mapRows = data
    ? Object.entries(data.map_distribution).sort((a, b) => b[1] - a[1]).slice(0, 8)
    : [];
  const mapMax = mapRows.length > 0 ? mapRows[0][1] : 1;
  const chart = (label: string, values: number[] | undefined, color: string, note: string) => (
    <div>
      <Lbl style={{ fontSize: 9 }}>{label}</Lbl>
      {values && values.length > 1 ? (
        <>
          <svg viewBox="0 0 320 110" style={{ width: '100%', display: 'block', marginTop: 10 }}>
            <line x1="0" y1="96" x2="320" y2="96" stroke="var(--color-rule-800)" strokeWidth="1" />
            <path d={sparkPath(values, 320, 110, 14)} fill="none" stroke={color} strokeWidth="1.4" />
          </svg>
          <div className="m" style={{ ...lblStyle, fontSize: 9, marginTop: 6 }}>
            peak {Math.max(...values)} · {note}
          </div>
        </>
      ) : (
        <div style={{ marginTop: 10 }}>{trends.isPending ? <Pending label="trend" /> : <Unavailable what="trend" />}</div>
      )}
    </div>
  );
  return (
    <div data-parity="home.insights" style={{ marginTop: 52, paddingTop: 22, borderTop: '1px solid var(--color-rule-800)' }}>
      <SectionHead
        label="how busy we have been"
        aside={
          <span style={{ display: 'flex', gap: 8 }}>
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setDays(r)}
                style={{
                  fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
                  border: `1px solid ${days === r ? '#4a5a66' : 'var(--color-rule-700)'}`,
                  background: days === r ? '#151a1e' : 'transparent',
                  color: days === r ? 'var(--color-text-100)' : 'var(--color-text-400)',
                  padding: '4px 9px',
                }}
              >
                {r}d
              </button>
            ))}
          </span>
        }
      />
      {trends.isError && <div style={{ marginTop: 14 }}><Unavailable what="activity" /></div>}
      <div className="home-cols3" style={{ gap: 34, marginTop: 18 }}>
        {chart('rounds per day', data?.rounds, 'var(--color-accent)', `last ${days} days`)}
        {chart('players per day', data?.active_players, 'var(--color-pos)', 'unique guids')}
        <div>
          <Lbl style={{ fontSize: 9 }}>most played maps</Lbl>
          <div style={{ marginTop: 12 }}>
            {mapRows.map(([name, n]) => (
              <div key={name} style={{ display: 'grid', gridTemplateColumns: '104px 1fr 26px', gap: 10, alignItems: 'center', padding: '3px 0' }}>
                <span className="m" style={{ fontSize: 11, color: 'var(--color-text-300)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                <span style={{ height: 5, background: 'var(--color-rule-800)', display: 'block', position: 'relative' }}>
                  <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${((n / mapMax) * 100).toFixed(1)}%`, background: '#5c6f7d', display: 'block' }} />
                </span>
                <span className="m" style={{ fontSize: 11, textAlign: 'right', color: 'var(--color-text-500)' }}>{n}</span>
              </div>
            ))}
            {data && mapRows.length === 0 && (
              <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no maps in this window</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SeasonBlock() {
  const season = useSeasonCurrent();
  const summary = useSeasonSummary();
  const leaders = useSeasonLeaders();
  const calendar = useActivityCalendar(90);
  if (season.isPending) return <div><Pending label="season" /></div>;
  if (!season.isSuccess) return <div><Unavailable what="season" /></div>;
  const s = season.data;
  const total = Date.parse(s.end_date) - Date.parse(s.start_date);
  const done = Date.now() - Date.parse(s.start_date);
  const pct = total > 0 ? Math.min(100, Math.max(0, (done / total) * 100)) : 0;
  const totals = summary.data?.totals;
  const seasonFigures = totals
    ? [
        { k: 'players', v: figure(totals.players) },
        { k: 'rounds', v: figure(totals.rounds) },
        { k: 'maps', v: figure(totals.maps) },
        { k: 'sessions', v: figure(totals.sessions) },
        { k: 'kills', v: figure(totals.kills) },
        {
          // {name: null, plays: 0} is the endpoint's EMPTY season shape —
          // the object is truthy, the name is the gate (Codex wave 3).
          k: summary.data?.top_map?.name ? `top map · ${summary.data.top_map.name}` : 'top map',
          v: summary.data?.top_map?.name ? figure(summary.data.top_map.plays) : '—',
        },
      ]
    : [];
  const lead = leaders.data?.leaders;
  const leaderRows = [
    { k: 'kills', row: lead?.kills },
    { k: 'dpm', row: lead?.dpm },
    { k: 'xp', row: lead?.xp },
  ].filter((r) => r.row != null);
  // An empty activity object is the endpoint's failure shape inside a 200
  // (and a 90-day window with zero active days does not happen in this
  // dataset) — no line beats a false 'active on 0 days' (Codex wave 3).
  const activeDaysCount = calendar.data ? Object.keys(calendar.data.activity).length : 0;
  const activeDays = activeDaysCount > 0 ? activeDaysCount : null;
  return (
    <div data-parity="home.season">
      <SectionHead label={s.name} aside={<span className="m" style={{ ...lblStyle, fontSize: 9 }}>{s.days_left} days left</span>} />
      <div style={{ height: 3, background: 'var(--color-rule-800)', marginTop: 10, position: 'relative' }}>
        <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${pct.toFixed(0)}%`, background: 'var(--color-accent-warm)', display: 'block' }} />
      </div>
      <div className="m" style={{ ...lblStyle, fontSize: 9, marginTop: 7 }}>{s.start_date} → {s.end_date}</div>
      {summary.isError && <div style={{ marginTop: 12 }}><Unavailable what="season figures" /></div>}
      {seasonFigures.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 16 }}>
          {seasonFigures.map((f) => (
            <div key={f.k}>
              <div className="m" style={{ fontSize: 19, lineHeight: 1 }}>{f.v}</div>
              <Lbl style={{ fontSize: 9, marginTop: 4 }}>{f.k}</Lbl>
            </div>
          ))}
        </div>
      )}
      {leaders.isError && <div style={{ marginTop: 12 }}><Unavailable what="season leaders" /></div>}
      {leaderRows.length > 0 && (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--color-rule-800)' }}>
          {leaderRows.map(({ k, row }) => (
            <div key={k} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '60px 1fr auto', gap: 10, alignItems: 'baseline', padding: '8px 0' }}>
              <Lbl style={{ fontSize: 9 }}>{k}</Lbl>
              <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row?.player}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{figure(row?.value ?? 0)}</span>
            </div>
          ))}
        </div>
      )}
      {activeDays != null && (
        <div className="m" style={{ ...lblStyle, fontSize: 9, marginTop: 10 }}>
          active on {activeDays} of the last {calendar.data?.days} days
        </div>
      )}
      <div className="m" style={{ ...lblStyle, fontSize: 9, marginTop: 6 }}>next: {s.next_season_name} starts {s.next_season_start}</div>
    </div>
  );
}

function LatestGames() {
  const matches = useRecentMatches(5);
  const data = matches.isError ? undefined : matches.data;
  return (
    <div data-parity="home.latest-games">
      <SectionHead
        label="latest games"
        aside={<Link to="/sessions2" style={{ ...lblStyle, fontSize: 9, textDecoration: 'none' }}>view all →</Link>}
      />
      <div style={{ marginTop: 12 }}>
        {matches.isPending && <Pending label="matches" />}
        {matches.isError && <Unavailable what="matches" />}
        {data?.length === 0 && <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no matches recorded yet</div>}
        {data?.map((m) => (
          <Link
            key={m.id}
            to={m.gaming_session_id != null ? `/session-detail/${m.gaming_session_id}` : `/session-detail/date/${m.date}`}
            style={{ ...rowStyle, display: 'block', padding: '11px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
          >
            <span style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
              <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {m.team1_players.join(' · ')} vs {m.team2_players.join(' · ')}
              </span>
              <span className="m" style={{ fontSize: 12, flex: 'none', color: m.outcome === 'Fullhold' ? 'var(--color-pos)' : m.winner === m.team1_name ? 'var(--color-accent)' : 'var(--color-accent-warm)' }}>
                {m.winner.toLowerCase()} · {m.duration}
              </span>
            </span>
            <span className="m" style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(--color-text-500)', marginTop: 5 }}>
              <span>{m.map_name}</span>
              <span>R{m.round_number}</span>
              <span>{m.format}</span>
              <span style={{ marginLeft: 'auto' }}>{m.time_ago.toLowerCase()}</span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function QuickLeadersPanel() {
  const leaders = useQuickLeaders();
  const data = leaders.isError ? undefined : leaders.data;
  return (
    <div data-parity="home.quick-leaders">
      <SectionHead
        label="quick leaders"
        aside={<Link to="/leaderboards" style={{ ...lblStyle, fontSize: 9, textDecoration: 'none' }}>view all →</Link>}
      />
      {leaders.isPending && <div style={{ marginTop: 12 }}><Pending label="leaders" /></div>}
      {leaders.isError && <div style={{ marginTop: 12 }}><Unavailable what="leaders" /></div>}
      {data && (
        [
          { k: `top xp · ${data.window_days} days`, rows: data.xp.slice(0, 5), failed: data.errors.includes('xp_query_failed') },
          { k: `top dpm per session · ${data.window_days} days`, rows: data.dpm_sessions.slice(0, 5), failed: data.errors.includes('dpm_query_failed') },
        ].map((board) => (
          <div key={board.k} style={{ marginTop: 14 }}>
            <Lbl style={{ fontSize: 9 }}>{board.k}</Lbl>
            <div style={{ marginTop: 8 }}>
              {board.rows.length === 0 && (board.failed
                ? <Unavailable what="board" />
                : <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no data in this window</div>)}
              {board.rows.map((r) => (
                <div key={r.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '18px minmax(0, 1fr) auto', gap: 10, alignItems: 'baseline', padding: '7px 0' }}>
                  <span className="m" style={{ ...lblStyle, fontSize: 10 }}>{String(r.rank).padStart(2, '0')}</span>
                  <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                  <span className="m" style={{ fontSize: 12, color: 'var(--color-text-300)' }}>{figure(r.value)}</span>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function MoverLine({ row, dir }: { row: SkillMoverRow; dir: 'up' | 'down' | 'new' }) {
  const color = dir === 'up' ? 'var(--color-pos)' : dir === 'down' ? 'var(--color-neg)' : 'var(--color-text-400)';
  return (
    <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 64px auto', gap: 10, alignItems: 'center', padding: '6px 0' }}>
      <span className="m" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</span>
      {row.series.length > 1 ? (
        <svg viewBox="0 0 64 18" style={{ width: 64, height: 18 }}>
          <path d={sparkPath(row.series, 64, 18, 2)} fill="none" stroke={color} strokeWidth="1" />
        </svg>
      ) : <span />}
      <span className="m" style={{ fontSize: 11, color }}>
        {/* A linked sick-leave alternate is a KNOWN player on a spare
          * account — calling them new is false (skill_router sends the
          * link precisely so the UI does not). */}
        {row.sick_leave
          ? `alt · ${row.sick_leave.primary_name}`
          : row.is_new ? 'new' : row.delta_pct != null ? `${row.delta_pct > 0 ? '+' : ''}${row.delta_pct.toFixed(1)}%` : '—'}
      </span>
    </div>
  );
}

function PulseRow() {
  const movers = useSkillMovers();
  const challenge = useChallengeCurrent();
  const md = movers.isError ? undefined : movers.data;
  return (
    <div data-parity="home.pulse" className="landing-split" style={{ marginTop: 52, paddingTop: 22, borderTop: '1px solid var(--color-rule-800)' }}>
      <div>
        <SectionHead label={`form movers · ${md?.metric_label?.toLowerCase() ?? 'vs own recent form'}`} />
        {movers.isPending && <div style={{ marginTop: 12 }}><Pending label="movers" /></div>}
        {movers.isError && <div style={{ marginTop: 12 }}><Unavailable what="movers" /></div>}
        {md && (
          <div style={{ marginTop: 10 }}>
            {md.movers_up.slice(0, 3).map((r) => <MoverLine key={r.guid} row={r} dir="up" />)}
            {md.movers_down.slice(0, 2).map((r) => <MoverLine key={r.guid} row={r} dir="down" />)}
            {md.new_players.slice(0, 2).map((r) => <MoverLine key={r.guid} row={r} dir="new" />)}
            {md.movers_up.length + md.movers_down.length + md.new_players.length === 0 && (
              <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no session to compare yet</div>
            )}
            <Lbl style={{ fontSize: 9, marginTop: 8 }}>vs each player's own trailing form — not a ranking</Lbl>
          </div>
        )}
      </div>
      <div>
        <SectionHead label="challenge of the week" />
        <div style={{ marginTop: 12 }}>
          {challenge.isPending && <Pending label="challenge" />}
          {challenge.isError && <Unavailable what="challenge" />}
          {challenge.data && (challenge.data.challenge ? (
            <>
              <div style={{ fontSize: 18, letterSpacing: '0.03em', textTransform: 'uppercase' }}>{challenge.data.challenge.title}</div>
              <div style={{ fontSize: 14, color: 'var(--color-text-400)', marginTop: 4 }}>{challenge.data.challenge.description}</div>
            </>
          ) : (
            <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no challenge this week</div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Tonight() {
  const tonight = useTonight();
  const availability = useAvailabilityOverview();
  const live = useLiveStatus();
  const nextMarked = availability.data?.days.find((day) => day.total > 0);
  const activeNow = tonight.data?.active === true;
  return (
    <div data-parity="home.tonight">
      <Lbl>tonight</Lbl>
      {/* While the tonight check is pending or failed, an idle claim would
        * be a guess — 'Nobody in voice' only after the endpoint answered. */}
      {tonight.isPending && <div style={{ marginTop: 10 }}><Pending label="tonight" /></div>}
      {tonight.isError && <div style={{ marginTop: 10 }}><Unavailable what="tonight" /></div>}
      {tonight.isSuccess && (
        activeNow ? (
          <div style={{ fontSize: 22, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 10 }}>
            Playing right now
          </div>
        ) : live.isSuccess ? (
          <div style={{ fontSize: 22, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 10 }}>
            {/* tonight is deliberately false until the first Lua row lands —
              * players already on the server outrank a voice-based idle
              * claim, and an in-band voice error forbids the claim entirely
              * (Codex wave 3). */}
            {(live.data?.game_server.player_count ?? 0) > 0
              ? `${live.data?.game_server.player_count} on the server`
              : live.data?.voice_channel.error
                ? 'Voice state unknown'
                : (live.data?.voice_channel.count ?? 0) > 0
                  ? `${live.data?.voice_channel.count} in voice`
                  : 'Nobody in voice'}
          </div>
        ) : (
          // 'Nobody in voice' is a claim about the room — it needs the
          // voice query to have ANSWERED, not defaulted (Codex wave 2).
          <div style={{ marginTop: 10 }}>
            {live.isPending ? <Pending label="voice" /> : <Unavailable what="voice" />}
          </div>
        )
      )}
      {availability.isPending && <div style={{ marginTop: 12 }}><Pending label="availability" /></div>}
      {availability.isError && <div style={{ marginTop: 12 }}><Unavailable what="availability" /></div>}
      {availability.isSuccess && (nextMarked ? (
        <>
          <Lbl style={{ fontSize: 9, marginTop: 18 }}>marked for {nextMarked.date} — {nextMarked.total}</Lbl>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
            {Object.entries(nextMarked.counts).filter(([, n]) => n > 0).map(([status, n]) => (
              <span key={status} className="m" style={{ fontSize: 13, border: '1px solid var(--color-rule-700)', padding: '5px 9px', color: 'var(--color-text-300)' }}>
                {status.toLowerCase().replace('_', ' ')} · {n}
              </span>
            ))}
          </div>
        </>
      ) : (
        <Lbl style={{ fontSize: 9, marginTop: 18 }}>nobody marked for the next {availability.data.days.length} days</Lbl>
      ))}
      <ActLink to="/availability" style={{ display: 'inline-block', marginTop: 16 }}>Mark yourself →</ActLink>
    </div>
  );
}

interface SearchHit { guid: string; name: string }

function FindYourStats() {
  const overview = useOverview();
  const [query, setQuery] = useState('');
  // 300 ms debounce, the legacy value: /auth/players/search is rate-limited
  // to 30/min, so a query key per keystroke would burn the budget in one
  // typed name (Codex on #811).
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);
  const trimmed = debounced;
  const search = useQuery({
    queryKey: ['player-search', trimmed],
    enabled: trimmed.length >= 2,
    queryFn: () => apiGet('/auth/players/search', { query: { q: trimmed } }) as Promise<SearchHit[]>,
  });
  const known = overview.data?.players_all_time;
  return (
    <div data-parity="home.search">
      <Lbl>find your stats</Lbl>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="player name or alias"
        aria-label="Find your stats"
        className="m"
        style={{
          width: '100%', marginTop: 12, background: 'var(--color-ink-800)',
          border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
          fontSize: 13, padding: '10px 11px', boxSizing: 'border-box',
        }}
      />
      {trimmed.length >= 2 && (
        <div style={{ marginTop: 8 }}>
          {search.isPending && <Pending label="search" />}
          {search.isError && <Unavailable what="search" />}
          {search.data?.length === 0 && (
            <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no player matches "{trimmed}"</div>
          )}
          {search.data?.slice(0, 6).map((hit) => (
            <Link key={hit.guid} to={`/profile/${hit.guid}`} style={{ ...rowStyle, display: 'block', padding: '7px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}>
              <span className="m" style={{ fontSize: 13 }}>{hit.name}</span>
            </Link>
          ))}
        </div>
      )}
      <Lbl style={{ fontSize: 9, marginTop: 10 }}>
        {known != null ? `${known} players known · ` : ''}names resolve through every alias we have seen
      </Lbl>
    </div>
  );
}

function EarlierEvenings() {
  const sessions = useSessions(6);
  const last = useLastSession();
  const data = sessions.isError ? undefined : sessions.data;
  // The newest row is skipped ONLY because the hero shows it — when the
  // hero's endpoint failed, dropping it would hide the newest evening
  // entirely (Codex wave 3).
  const skipFirst = last.isSuccess ? 1 : 0;
  return (
    <div data-parity="home.earlier">
      <Lbl>earlier evenings</Lbl>
      <div style={{ marginTop: 12 }}>
        {sessions.isPending && <Pending label="sessions" />}
        {sessions.isError && <Unavailable what="sessions" />}
        {data?.length === 0 && <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no sessions recorded yet</div>}
        {data?.slice(skipFirst, skipFirst + 5).map((row) => (
          <Link key={row.session_id} to={`/session-detail/${row.session_id}`} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '1fr auto auto auto', alignItems: 'baseline', gap: 14, padding: '10px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}>
            <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{row.formatted_date.replace(/,.*$/, '')} {row.date.slice(5)}</span>
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.rounds} rd</span>
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.players} pl</span>
            <span className="m" style={{ fontSize: 14, minWidth: 58, textAlign: 'right' }}>
              {row.team_1_score != null && row.team_2_score != null && row.team_1_score + row.team_2_score > 0
                ? `${row.team_1_score} / ${row.team_2_score}`
                : '—'}
            </span>
          </Link>
        ))}
        <ActLink to="/sessions2" style={{ display: 'inline-block', marginTop: 14 }}>All evenings →</ActLink>
      </div>
    </div>
  );
}

function GoDeeper() {
  const cards = [
    { to: '/proximity', title: 'Telemetry', body: 'Engagements, crossfire, cohesion, trades' },
    { to: '/replay', title: 'Round replay', body: 'Positions at 200 ms, event by event' },
    { to: '/record-book', title: 'Records', body: 'Season awards and the record book' },
    { to: '/uploads', title: 'Demos', body: 'Upload a demo, get the highlights cut' },
  ];
  return (
    <div data-parity="home.deeper">
      <Lbl>go deeper</Lbl>
      <div style={{ marginTop: 12 }}>
        {cards.map((c) => (
          <Link key={c.title} to={c.to} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'baseline', gap: 16, padding: '13px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}>
            <span>
              <span style={{ fontSize: 17, letterSpacing: '0.04em', textTransform: 'uppercase', display: 'block' }}>{c.title}</span>
              <span style={{ fontSize: 14, color: 'var(--color-text-400)' }}>{c.body}</span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}

function StandingFigures() {
  const overview = useOverview();
  if (overview.isPending) return <div style={{ padding: '16px 0' }}><Pending label="figures" /></div>;
  if (!overview.isSuccess) return <div style={{ padding: '16px 0' }}><Unavailable what="figures" /></div>;
  const d = overview.data;
  const live = (n: number) => (n === 0 ? '—' : n.toLocaleString('en-US'));
  const cells = [
    { k: 'rounds kept', v: live(d.rounds) },
    { k: 'kills recorded', v: live(d.total_kills) },
    { k: 'sessions', v: live(d.sessions) },
    { k: 'players known', v: live(d.players_all_time) },
  ];
  return (
    <>
      {cells.map((c) => (
        <div key={c.k} style={{ padding: '16px 0 14px' }}>
          <div className="m" style={{ fontSize: 22, lineHeight: 1, color: 'var(--color-text-200)' }}>{c.v}</div>
          <Lbl style={{ marginTop: 6 }}>{c.k}</Lbl>
        </div>
      ))}
    </>
  );
}

export function Home() {
  return (
    <div style={{ paddingBottom: 40 }}>
      <TopBand />
      <Hero />
      <EveningFigures />
      {/* The canon's kills-per-minute evening trace is ABSENT on purpose: no
        * endpoint serves a per-minute series for an evening. Saying so beats
        * drawing an invented line (landing sparkline rule). */}
      <Lbl style={{ fontSize: 9, marginTop: 8 }}>
        kills-per-minute trace: no per-minute series is recorded for an evening yet
      </Lbl>
      <Insights />
      <div className="home-cols3" style={{ marginTop: 52, paddingTop: 22, borderTop: '1px solid var(--color-rule-800)' }}>
        <SeasonBlock />
        <LatestGames />
        <QuickLeadersPanel />
      </div>
      <PulseRow />
      <div className="landing-split" style={{ marginTop: 52, paddingTop: 22, borderTop: '1px solid var(--color-rule-800)' }}>
        <Tonight />
        <FindYourStats />
      </div>
      <div className="landing-split" style={{ marginTop: 56 }}>
        <EarlierEvenings />
        <GoDeeper />
      </div>
      <div data-parity="home.standing" className="landing-quad" style={{ marginTop: 56, borderTop: '1px solid var(--color-rule-800)', borderBottom: '1px solid var(--color-rule-800)' }}>
        <StandingFigures />
      </div>
      {/* The canon's page footer is omitted: AppShell already renders the
        * same line globally — two of them stacked read as a bug. */}
    </div>
  );
}

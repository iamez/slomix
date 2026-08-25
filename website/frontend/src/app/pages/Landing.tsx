import { Link } from 'react-router';
import { useLiveState, useOverview, useQuickLeaders, useSessions, useVoiceCurrent } from '../lib/queries';
import type { SessionSummary } from '../lib/types';

/**
 * Landing — the first page of the new design (docs/design/12 row L), a
 * faithful transfer of landing.dc.html onto live endpoints. House rule from
 * the handoff carried throughout: what is not wired says so — a section
 * renders "unknown" with a reason, never an invented number and never an
 * empty box. The evening sparkline is deliberately absent: no endpoint
 * serves a per-evening kills/min series yet (the graphs endpoint is
 * per-player), and the prototype's chart is not worth a fabricated one.
 */

const S = {
  lbl: { fontSize: 10, letterSpacing: '0.24em', textTransform: 'uppercase', color: 'var(--color-text-500)' } as const,
  act: {
    fontSize: 13, letterSpacing: '0.14em', textTransform: 'uppercase',
    color: 'var(--color-text-200)', textDecoration: 'none',
    borderBottom: '1px solid #45433d', paddingBottom: 3,
  } as const,
  row: { borderBottom: '1px solid var(--color-rule-800)' } as const,
};

function Pending({ label }: { label: string }) {
  return <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>{label}…</span>;
}

function Unavailable({ what }: { what: string }) {
  return (
    <span className="m" style={{ fontSize: 11, color: 'var(--color-neg)' }}>
      {what}: unavailable
    </span>
  );
}

function figure(value: number): string {
  return Number.isInteger(value) ? value.toLocaleString('en-US') : value.toFixed(1);
}

function monthDay(date: string): string {
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed
    .toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
    .toUpperCase();
}

function LivePanel() {
  const live = useLiveState();
  const voice = useVoiceCurrent();
  return (
    <div style={{ border: '1px solid var(--color-rule-700)', padding: '14px 16px' }}>
      {live.isPending && <Pending label="live" />}
      {live.isError && <Unavailable what="game server" />}
      {live.data && (
        <>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <span
              style={{
                width: 6, height: 6, borderRadius: '50%', flex: 'none', alignSelf: 'center',
                background: live.data.is_live ? 'var(--color-pos)' : '#454340',
              }}
            />
            <span className="m" style={{ fontSize: 13, color: 'var(--color-text-100)' }}>
              {live.data.is_live ? 'LIVE' : 'SERVER IDLE'}
            </span>
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>
              {live.data.current_map ?? 'unknown map'}
            </span>
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)', marginLeft: 'auto' }}>
              {live.data.roster.player_count} players
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--color-rule-800)' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', flex: 'none', alignSelf: 'center', background: (voice.data?.total_count ?? 0) > 0 ? 'var(--color-pos)' : '#454340' }} />
            {voice.isPending && <Pending label="voice" />}
            {voice.isError && <Unavailable what="voice" />}
            {voice.data && (
              <>
                <span className="m" style={{ fontSize: 13, color: 'var(--color-text-400)' }}>
                  {voice.data.total_count > 0 ? `${voice.data.total_count} in voice` : 'No one in voice'}
                </span>
                <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginLeft: 'auto' }}>
                  {voice.data.total_count} online
                </span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function LastNightPanel({ session }: { session: SessionSummary | undefined }) {
  if (!session) {
    return (
      <div style={{ marginTop: 22 }}>
        <div style={S.lbl}>last night</div>
        <div style={{ marginTop: 8 }}><Unavailable what="last session" /></div>
      </div>
    );
  }
  return (
    <div style={{ marginTop: 22 }}>
      <div style={S.lbl}>last night</div>
      <div style={{ fontSize: 22, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 8 }}>
        {session.formatted_date.replace(/,.*$/, '')} {monthDay(session.date).split(' ').slice(1).join(' ')}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, marginTop: 10 }}>
        <div>
          <div style={{ ...S.lbl, fontSize: 9 }}>{session.team_1_name.toLowerCase()}</div>
          <div className="m" style={{ fontSize: 44, lineHeight: 0.86, color: 'var(--color-accent)' }}>{session.team_1_score}</div>
        </div>
        <div className="m" style={{ fontSize: 20, color: '#3f3d38', paddingBottom: 6 }}>/</div>
        <div>
          <div style={{ ...S.lbl, fontSize: 9 }}>{session.team_2_name.toLowerCase()}</div>
          <div className="m" style={{ fontSize: 44, lineHeight: 0.86, color: 'var(--color-accent-warm)' }}>{session.team_2_score}</div>
        </div>
        <div style={{ ...S.lbl, fontSize: 9, paddingBottom: 6 }}>maps won · sides swap every map</div>
      </div>
      <div className="m" style={{ fontSize: 12, color: 'var(--color-text-400)', marginTop: 10 }}>
        {session.rounds} rounds · {session.maps} maps · {session.players} players
      </div>
      <Link to={`/session-detail/date/${session.date}`} style={{ ...S.act, display: 'inline-block', marginTop: 14 }}>
        Open the evening →
      </Link>
    </div>
  );
}

export function Landing() {
  const overview = useOverview();
  const sessions = useSessions(6);
  const leaders = useQuickLeaders();
  const lastNight = sessions.data?.[0];

  return (
    <div style={{ paddingBottom: 40 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 56, paddingTop: 48 }}>
        <div>
          <div style={S.lbl}>enemy territory: legacy · stopwatch · since january 2025</div>
          <h1 style={{ fontSize: 52, fontWeight: 600, letterSpacing: '0.02em', textTransform: 'uppercase', lineHeight: 1.04, margin: '14px 0 0', maxWidth: '13em' }}>
            Every round we play, written down.
          </h1>
          <p style={{ color: 'var(--color-text-300)', maxWidth: '36em', marginTop: 18 }}>
            Scoreboard and telemetry from our own server, kept since january 2025.
          </p>
          <div style={{ display: 'flex', gap: 18, marginTop: 26, alignItems: 'center' }}>
            <a href="/auth/login" style={{ ...S.act, border: '1px solid #33322e', padding: '10px 14px', borderBottom: '1px solid #33322e' }}>
              Connect your ID
            </a>
            {lastNight && (
              <Link to={`/session-detail/date/${lastNight.date}`} style={S.act}>
                See last night →
              </Link>
            )}
          </div>
          <div style={{ ...S.lbl, fontSize: 9, marginTop: 18 }}>
            discord login · your stats are already here, waiting to be claimed
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
            <span style={{ ...S.lbl, fontSize: 9 }}>live now</span>
          </div>
          <LivePanel />
          <LastNightPanel session={lastNight} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', marginTop: 48, borderTop: '1px solid var(--color-rule-800)', borderBottom: '1px solid var(--color-rule-800)' }}>
        {overview.isPending && <div style={{ padding: '18px 0' }}><Pending label="figures" /></div>}
        {overview.isError && <div style={{ padding: '18px 0' }}><Unavailable what="figures" /></div>}
        {overview.data && (
          [
            { v: overview.data.rounds.toLocaleString('en-US'), k: 'rounds kept' },
            { v: overview.data.total_kills.toLocaleString('en-US'), k: 'kills recorded' },
            { v: overview.data.sessions.toLocaleString('en-US'), k: 'sessions' },
            { v: overview.data.players_all_time.toLocaleString('en-US'), k: 'players known' },
          ].map((f) => (
            <div key={f.k} style={{ padding: '18px 0 16px' }}>
              <div className="m" style={{ fontSize: 28, lineHeight: 1 }}>{f.v}</div>
              <div style={{ ...S.lbl, marginTop: 6 }}>{f.k}</div>
            </div>
          ))
        )}
      </div>

      <div style={{ marginTop: 40 }}>
        <div style={{ ...S.lbl, fontSize: 9 }}>where to go</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 28, marginTop: 14 }}>
          {[
            { to: '/profile', title: 'Your profile', body: 'Your rounds, against your own form.', bar: 'var(--color-accent)' },
            { to: '/sessions2', title: 'The evenings', body: 'Maps, teams, how the night went.', bar: 'var(--color-accent-warm)' },
            { to: '/proximity', title: 'Telemetry', body: 'Paths, cover, reaction times.', bar: 'var(--color-pos)' },
            { to: '/uploads', title: 'Clips and files', body: 'Demos, highlights, configs.', bar: 'var(--color-accent)' },
          ].map((card) => (
            <Link key={card.title} to={card.to} style={{ textDecoration: 'none', color: 'var(--color-text-100)' }}>
              <div style={{ height: 2, background: card.bar }} />
              <div style={{ fontSize: 17, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 12 }}>{card.title}</div>
              <div style={{ fontSize: 14, color: 'var(--color-text-400)', marginTop: 4 }}>{card.body}</div>
            </Link>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 56, marginTop: 48 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ ...S.lbl, fontSize: 9 }}>recent evenings</span>
            <Link to="/sessions2" style={{ ...S.lbl, fontSize: 9, textDecoration: 'none' }}>all sessions →</Link>
          </div>
          <div style={{ marginTop: 10 }}>
            {sessions.isPending && <Pending label="sessions" />}
            {sessions.isError && <Unavailable what="sessions" />}
            {sessions.data?.slice(0, 5).map((row) => (
              <Link
                key={row.session_id}
                to={`/session-detail/date/${row.date}`}
                style={{ ...S.row, display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 16, alignItems: 'baseline', padding: '10px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
              >
                <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{monthDay(row.date)}</span>
                <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.rounds} rd</span>
                <span className="m" style={{ fontSize: 14, minWidth: 58, textAlign: 'right' }}>
                  {row.team_1_score} / {row.team_2_score}
                </span>
              </Link>
            ))}
          </div>
        </div>

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
            <span style={{ ...S.lbl, fontSize: 9 }}>leading this week</span>
            <Link to="/leaderboards" style={{ ...S.lbl, fontSize: 9, textDecoration: 'none' }}>leaderboards →</Link>
          </div>
          {leaders.isPending && <div style={{ marginTop: 10 }}><Pending label="leaders" /></div>}
          {leaders.isError && <div style={{ marginTop: 10 }}><Unavailable what="leaders" /></div>}
          {leaders.data && (
            <div style={{ marginTop: 10 }}>
              {[
                { k: `top xp · ${leaders.data.window_days} days`, rows: leaders.data.xp.slice(0, 3) },
                { k: `top dpm per session · ${leaders.data.window_days} days`, rows: leaders.data.dpm_sessions.slice(0, 3) },
              ].map((board) => (
                <div key={board.k} style={{ marginBottom: 14 }}>
                  <div style={{ ...S.lbl, fontSize: 9 }}>{board.k}</div>
                  {board.rows.map((row) => (
                    <div key={row.guid} style={{ ...S.row, display: 'grid', gridTemplateColumns: '22px 1fr auto', gap: 10, alignItems: 'baseline', padding: '7px 0' }}>
                      <span className="m" style={{ ...S.lbl, fontSize: 10 }}>{String(row.rank).padStart(2, '0')}</span>
                      <span className="m" style={{ fontSize: 13 }}>{row.name}</span>
                      <span className="m" style={{ fontSize: 12, color: 'var(--color-text-300)' }}>
                        {figure(row.value)}
                      </span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 24, marginTop: 56, paddingTop: 22, borderTop: '1px solid var(--color-rule-800)' }}>
        <div>
          <div style={{ fontSize: 22, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            Played with us? Your stats are already in here.
          </div>
          <div className="m" style={{ fontSize: 12, color: 'var(--color-text-500)', marginTop: 6 }}>
            connect your discord to claim your name, set availability, and upload clips
          </div>
        </div>
        <a href="/auth/login" style={{ ...S.act, border: '1px solid #33322e', padding: '10px 14px', flex: 'none', borderBottom: '1px solid #33322e' }}>
          Connect your ID
        </a>
      </div>
    </div>
  );
}

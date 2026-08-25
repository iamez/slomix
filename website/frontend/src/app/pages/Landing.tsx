import { Link } from 'react-router';
import { useLiveState, useOverview, useQuickLeaders, useSessions, useVoiceCurrent } from '../lib/queries';
import type { QuickLeaderRow, SessionSummary } from '../lib/types';
import {
  ActLink, KpiTile, Lbl, Pending, SectionHead, StatusDot, Unavailable,
  actStyle, figure, lblStyle, rowStyle,
} from '../components/ui';

/**
 * Landing — the first page of the new design (docs/design/12 row L), a
 * faithful transfer of landing.dc.html onto live endpoints. House rule from
 * the handoff carried throughout: what is not wired says so — a section
 * renders "unknown" with a reason, never an invented number and never an
 * empty box. The evening sparkline is deliberately absent: no endpoint
 * serves a per-evening kills/min series yet (the graphs endpoint is
 * per-player), and the prototype's chart is not worth a fabricated one.
 */

/** "34 min ago" / "5 d ago" from a seconds count. */
function ageOf(seconds: number): string {
  if (seconds < 5400) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} d ago`;
}

function monthDay(date: string): string {
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed
    .toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
    .toUpperCase();
}

/** "last night" only when it really was. The tiers come from the API's own
 * time_ago classification, not from browser-local elapsed milliseconds —
 * around midnight or a DST shift the two disagree, and the backend's
 * calendar is the one the data lives in (Codex on #806, waves 2 and 5). */
function sessionRecency(session: SessionSummary): { label: string; cta: string } {
  if (session.time_ago === 'Today') return { label: 'tonight', cta: 'See tonight' };
  if (session.time_ago === 'Yesterday') return { label: 'last night', cta: 'See last night' };
  return { label: `last session · ${session.time_ago}`, cta: 'See the last session' };
}

function LivePanel() {
  const live = useLiveState();
  const voice = useVoiceCurrent();
  // A failed 30 s refetch leaves the previous data populated next to the
  // error flag — showing "unavailable" ALONGSIDE stale numbers would be two
  // contradictory claims at once, so the error wins (Codex on #806).
  const liveData = live.isError ? undefined : live.data;
  // status === 'unavailable' (#808) is an in-band failure: the endpoint
  // answers 200 whether the row is empty or unreadable, and only this
  // field says which.
  const voiceData = voice.isError || voice.data?.status === 'unavailable' ? undefined : voice.data;
  return (
    <div style={{ border: '1px solid var(--color-rule-700)', padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        {live.isPending && <Pending label="live" />}
        {live.isError && <Unavailable what="game server" />}
        {liveData && (
          <>
            <StatusDot state={liveData.is_live ? 'ok' : 'idle'} />
            <span className="m" style={{ fontSize: 13, color: 'var(--color-text-100)' }}>
              {liveData.is_live ? 'LIVE' : 'SERVER IDLE'}
            </span>
            {/* The reducer keeps _current_map indefinitely after events
              * stop (the recording itself is 5 days stale) — while idle the
              * map is a memory, not a state, and says so (Codex wave 5).
              * The tier is is_live ITSELF, no second threshold: the backend
              * flips it at _LIVE_WINDOW_SECONDS=180 and a frontend number
              * beside it would be the same rule in two places with two
              * values (brother's review — the 300 here left a 180–300 s
              * window showing SERVER IDLE next to a bare map). */}
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>
              {liveData.current_map == null
                ? 'unknown map'
                : liveData.map_confirmed === false
                  // #808: nothing since the session boundary confirmed this
                  // map — a restarted server usually returns to it, so it
                  // is shown, but as a guess, even while is_live.
                  ? `${liveData.current_map} · unconfirmed`
                  : liveData.is_live
                    ? liveData.current_map
                    : liveData.last_event_age_seconds != null
                      ? `${liveData.current_map} · ${ageOf(liveData.last_event_age_seconds)}`
                      : `${liveData.current_map} · last seen`}
            </span>
            {/* After a delivery gap the reducer keeps the old lineup for up
              * to 600 s and exposes its age — an aged count says so instead
              * of posing as current (Codex on #806, wave 4). */}
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)', marginLeft: 'auto' }}>
              {liveData.roster.player_count} players
              {liveData.roster.player_count > 0
                && liveData.roster.roster_age_seconds != null
                && liveData.roster.roster_age_seconds > 60
                ? ` · seen ${Math.round(liveData.roster.roster_age_seconds / 60)} min ago`
                : ''}
            </span>
          </>
        )}
      </div>
      {/* The voice row renders from its own query — a dead game server must
        * not silence a perfectly healthy voice report (Codex on #806). */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--color-rule-800)' }}>
        <StatusDot state={(voiceData?.total_count ?? 0) > 0 ? 'ok' : 'idle'} />
        {voice.isPending && <Pending label="voice" />}
        {(voice.isError || voice.data?.status === 'unavailable') && <Unavailable what="voice" />}
        {voiceData && (
          <>
            {/* total_count counts the tracked voice channel only
              * (diagnostics_router; Codex on #806, wave 3) — calling it
              * "online" claimed nobody is online anywhere. One label, the
              * honest one. When the endpoint starts exposing updated_at
              * (wave 5 — today it does not), a stale snapshot says its age
              * instead of posing as live. */}
            <span className="m" style={{ fontSize: 13, color: 'var(--color-text-400)' }}>
              {voiceData.total_count > 0 ? `${voiceData.total_count} in voice` : 'No one in voice'}
              {(() => {
                if (!voiceData.updated_at) return '';
                const age = (Date.now() - Date.parse(voiceData.updated_at)) / 1000;
                return Number.isFinite(age) && age > 120 ? ` · as of ${ageOf(age)}` : '';
              })()}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

function LastNightPanel({ session, pending, empty }: { session: SessionSummary | undefined; pending: boolean; empty: boolean }) {
  // Neutral heading until a session exists: "last night" above an empty or
  // still-loading panel asserts a session that may never have happened
  // (Codex on #806, wave 7) — only sessionRecency() may earn the label.
  if (pending) {
    return (
      <div style={{ marginTop: 22 }}>
        <Lbl>latest session</Lbl>
        <div style={{ marginTop: 8 }}><Pending label="last session" /></div>
      </div>
    );
  }
  if (!session) {
    // A successful empty answer is not a failure (Codex on #806, wave 3):
    // a fresh database has no last session, but the endpoint is fine.
    return (
      <div style={{ marginTop: 22 }}>
        <Lbl>latest session</Lbl>
        <div style={{ marginTop: 8 }}>
          {empty
            ? <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no sessions recorded yet</span>
            : <Unavailable what="last session" />}
        </div>
      </div>
    );
  }
  const attributed =
    session.team_1_name != null && session.team_2_name != null
    && session.team_1_score != null && session.team_2_score != null;
  return (
    <div style={{ marginTop: 22 }}>
      <Lbl>{sessionRecency(session).label}</Lbl>
      <div style={{ fontSize: 22, letterSpacing: '0.04em', textTransform: 'uppercase', marginTop: 8 }}>
        {session.formatted_date.replace(/,.*$/, '')} {monthDay(session.date).split(' ').slice(1).join(' ')}
      </div>
      {attributed ? (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, marginTop: 10 }}>
          <div>
            <Lbl style={{ fontSize: 9 }}>{session.team_1_name?.toLowerCase()}</Lbl>
            <div className="m" style={{ fontSize: 44, lineHeight: 0.86, color: 'var(--color-accent)' }}>{session.team_1_score}</div>
          </div>
          <div className="m" style={{ fontSize: 20, color: '#3f3d38', paddingBottom: 6 }}>/</div>
          <div>
            <Lbl style={{ fontSize: 9 }}>{session.team_2_name?.toLowerCase()}</Lbl>
            <div className="m" style={{ fontSize: 44, lineHeight: 0.86, color: 'var(--color-accent-warm)' }}>{session.team_2_score}</div>
          </div>
          {/* 2 points per map won, 1–1 on a draw — a BOX score, not a count
            * of maps (stopwatch_scoring_service; Codex on #806). */}
          <Lbl style={{ fontSize: 9, paddingBottom: 6 }}>box score · sides swap every map</Lbl>
        </div>
      ) : (
        <Lbl style={{ fontSize: 9, marginTop: 10 }}>
          score not attributed to teams for this session
        </Lbl>
      )}
      <div className="m" style={{ fontSize: 12, color: 'var(--color-text-400)', marginTop: 10 }}>
        {session.rounds} rounds · {session.maps} maps · {session.players} players
      </div>
      <ActLink to={`/session-detail/${session.session_id}`} style={{ display: 'inline-block', marginTop: 14 }}>
        Open the evening →
      </ActLink>
    </div>
  );
}

/** A board can fail INSIDE a 200: the endpoint answers ok with an empty
 * array and a per-board token in `errors` — exactly "xp_query_failed" or
 * "dpm_query_failed" (players_router; Codex on #806, both waves) — so each
 * board reports only ITS OWN failure, and an empty board without its token
 * says "no data", never a silent blank. */
function LeaderBoard({ title, rows, hadErrors }: { title: string; rows: QuickLeaderRow[]; hadErrors: boolean }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <Lbl style={{ fontSize: 9 }}>{title}</Lbl>
      {rows.length === 0 && (hadErrors
        ? <div style={{ marginTop: 6 }}><Unavailable what="board" /></div>
        : <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 6 }}>no data in this window</div>
      )}
      {rows.map((row) => (
        /* minmax(0,1fr): a 1fr track keeps min-content width, so one long
         * stored name forced the row past a phone viewport (Codex wave 9);
         * the name itself ellipsizes rather than pushing the value out. */
        <div key={row.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '22px minmax(0, 1fr) auto', gap: 10, alignItems: 'baseline', padding: '7px 0' }}>
          <span className="m" style={{ ...lblStyle, fontSize: 10 }}>{String(row.rank).padStart(2, '0')}</span>
          <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.name}</span>
          <span className="m" style={{ fontSize: 12, color: 'var(--color-text-300)' }}>
            {figure(row.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Landing() {
  const overview = useOverview();
  const sessions = useSessions(6);
  const leaders = useQuickLeaders();
  // Same rule as the live panel: a failed refetch must not present cached
  // data as current next to the error message (Codex on #806).
  const sessionsData = sessions.isError ? undefined : sessions.data;
  const overviewData = overview.isError ? undefined : overview.data;
  const leadersData = leaders.isError ? undefined : leaders.data;
  const lastNight = sessionsData?.[0];
  // The overview endpoint substitutes 0 per failed aggregate and still
  // answers 200 (records_overview.py; Codex on #806). Four zeroes at once
  // is that failure mode, not a deployment with an empty database worth a
  // hero row — say unavailable rather than presenting zeros as the record.
  const overviewSuspect =
    overviewData != null
    && overviewData.rounds === 0 && overviewData.total_kills === 0
    && overviewData.sessions === 0 && overviewData.players_all_time === 0;

  return (
    <div style={{ paddingBottom: 40 }}>
      <div className="landing-hero">
        <div>
          <Lbl>enemy territory: legacy · stopwatch · since january 2025</Lbl>
          <h1 style={{ fontSize: 52, fontWeight: 600, letterSpacing: '0.02em', textTransform: 'uppercase', lineHeight: 1.04, margin: '14px 0 0', maxWidth: '13em' }}>
            Every round we play, written down.
          </h1>
          <p style={{ color: 'var(--color-text-300)', maxWidth: '36em', marginTop: 18 }}>
            Scoreboard and telemetry from our own server, kept since january 2025.
          </p>
          <div style={{ display: 'flex', gap: 18, marginTop: 26, alignItems: 'center' }}>
            <ActLink to="/auth/login" style={{ border: '1px solid #33322e', padding: '10px 14px', borderBottom: '1px solid #33322e' }}>
              Connect your ID
            </ActLink>
            {lastNight && (
              <ActLink to={`/session-detail/${lastNight.session_id}`}>
                {sessionRecency(lastNight).cta} →
              </ActLink>
            )}
          </div>
          <Lbl style={{ fontSize: 9, marginTop: 18 }}>
            discord login · your stats are already here, waiting to be claimed
          </Lbl>
        </div>

        <div>
          <div style={{ marginBottom: 8 }}>
            <SectionHead label="live now" />
          </div>
          <LivePanel />
          <LastNightPanel session={lastNight} pending={sessions.isPending} empty={sessionsData?.length === 0} />
        </div>
      </div>

      <div className="landing-quad" style={{ marginTop: 48, borderTop: '1px solid var(--color-rule-800)', borderBottom: '1px solid var(--color-rule-800)' }}>
        {overview.isPending && <div style={{ padding: '18px 0' }}><Pending label="figures" /></div>}
        {(overview.isError || overviewSuspect) && <div style={{ padding: '18px 0' }}><Unavailable what="figures" /></div>}
        {overviewData && !overviewSuspect && (
          [
            { v: overviewData.rounds, k: 'rounds kept' },
            { v: overviewData.total_kills, k: 'kills recorded' },
            { v: overviewData.sessions, k: 'sessions' },
            { v: overviewData.players_all_time, k: 'players known' },
          ].map((f) => (
            /* _safe_val substitutes 0 PER METRIC on a failed aggregate
             * (records_overview.py; Codex on #806, wave 3) — and in this
             * dataset none of these four figures can genuinely be zero
             * while the site is serving, so a zero is a failed query and
             * renders as a dash, never as "0 kills recorded". */
            <KpiTile key={f.k} value={f.v === 0 ? '—' : f.v.toLocaleString('en-US')} label={f.k} />
          ))
        )}
      </div>

      <div style={{ marginTop: 40 }}>
        <SectionHead label="where to go" />
        <div className="landing-quad" style={{ gap: 28, marginTop: 14 }}>
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

      <div className="landing-split" style={{ marginTop: 48 }}>
        <div>
          <SectionHead
            label="recent evenings"
            aside={<Link to="/sessions2" style={{ ...lblStyle, fontSize: 9, textDecoration: 'none' }}>all sessions →</Link>}
          />
          <div style={{ marginTop: 10 }}>
            {sessions.isPending && <Pending label="sessions" />}
            {sessions.isError && <Unavailable what="sessions" />}
            {sessionsData?.length === 0 && (
              <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>
                no sessions recorded yet
              </div>
            )}
            {sessionsData?.slice(0, 5).map((row) => (
              <Link
                key={row.session_id}
                to={`/session-detail/${row.session_id}`}
                style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 16, alignItems: 'baseline', padding: '10px 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
              >
                <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{monthDay(row.date)}</span>
                <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{row.rounds} rd</span>
                <span className="m" style={{ fontSize: 14, minWidth: 58, textAlign: 'right' }}>
                  {row.team_1_score != null && row.team_2_score != null
                    ? `${row.team_1_score} / ${row.team_2_score}`
                    : '—'}
                </span>
              </Link>
            ))}
          </div>
        </div>

        <div>
          <SectionHead
            label="leading this week"
            aside={<Link to="/leaderboards" style={{ ...lblStyle, fontSize: 9, textDecoration: 'none' }}>leaderboards →</Link>}
          />
          {leaders.isPending && <div style={{ marginTop: 10 }}><Pending label="leaders" /></div>}
          {leaders.isError && <div style={{ marginTop: 10 }}><Unavailable what="leaders" /></div>}
          {leadersData && (
            <div style={{ marginTop: 10 }}>
              <LeaderBoard
                title={`top xp · ${leadersData.window_days} days`}
                rows={leadersData.xp.slice(0, 3)}
                hadErrors={leadersData.errors.includes('xp_query_failed')}
              />
              <LeaderBoard
                title={`top dpm per session · ${leadersData.window_days} days`}
                rows={leadersData.dpm_sessions.slice(0, 3)}
                hadErrors={leadersData.errors.includes('dpm_query_failed')}
              />
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
        <a href="/auth/login" style={{ ...actStyle, border: '1px solid #33322e', padding: '10px 14px', flex: 'none', borderBottom: '1px solid #33322e' }}>
          Connect your ID
        </a>
      </div>
    </div>
  );
}

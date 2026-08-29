import { useMemo } from 'react';
import { Link, useParams, useNavigate } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Lbl, Pending, SectionHead, Tabs, Unavailable, figure } from '../components/ui';
import {
  useSessionDetail, useSessionGoodNight, useSessionMvp, useSessionRounds,
  useSessionVerdicts, useSessions,
} from '../lib/queries';
import type {
  SessionDetail as SessionDetailData, SessionGoodNight, SessionPlayerTotals,
  SessionRound, SessionScoring, SessionTeamMatrix, SessionVerdicts,
} from '../lib/types';

/**
 * Session detail (docs/design/12 row 31) — the widest page in the legacy
 * site: 4,105 lines of session-detail.js against a React draft of 1,578,
 * which is the gap docs/design/07 §B.1 catalogues panel by panel.
 *
 * The organising idea here is that a session is FOUR different kinds of
 * claim, and the legacy page mixes them into one scroll:
 *
 *   the scoreboard   — what the rounds say happened, no model at all;
 *   the totals       — sums over the halves, with the round filter named;
 *   the judgements   — good-night index, verdicts: models with parameters;
 *   the votes        — the MVP panel, which is what PEOPLE thought.
 *
 * A page that prints a voted MVP beside a computed rating without saying
 * which is which invites the reader to treat one as evidence for the other.
 * So each block says what it is made of, and the tabs split by kind rather
 * than by table.
 */

type TabKey = 'summary' | 'players' | 'rounds';

const TABS: readonly { key: TabKey; label: string }[] = [
  { key: 'summary', label: 'summary' },
  { key: 'players', label: 'players' },
  { key: 'rounds', label: 'rounds' },
];

function clock(seconds: number | null): string {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** The stopwatch result, map by map. `team_a_time` is a clock OR the word
 * "fullhold", and those are different outcomes — one is a time, the other is
 * the absence of one. */
function Scoreboard({ scoring }: { scoring: SessionScoring }) {
  if (!scoring.available) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
        stopwatch scoring could not be assembled for this session — its halves
        could not be paired, which is not the same as a 0–0
      </span>
    );
  }
  return (
    <Stack gap={3} parity="session.scoreboard">
      <SectionHead
        label="scoreboard"
        aside={
          <span className="lbl">
            {scoring.team_a_name} {scoring.team_a_score} — {scoring.team_b_score} {scoring.team_b_name}
          </span>
        }
      />
      <Stack gap={1} className="rows">
        {scoring.maps.map((m, i) => (
          <Cluster key={`${m.map}:${m.match_id ?? i}`} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
              <span className="m lbl" style={{ width: 20, textAlign: 'right' }}>{i + 1}</span>
              <span style={{ fontSize: 'var(--fs-row)' }}>{m.map}</span>
              {/* A map that was played but does not count is a fact about
                * the session, and hiding it is how a reader ends up counting
                * differently from the page. */}
              {!m.counted && <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>not counted</span>}
            </Cluster>
            <Cluster gap={3} align="center">
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>
                {m.team_a_points} — {m.team_b_points}
              </span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 150, textAlign: 'right' }}>
                {m.team_a_time ?? '—'} / {m.team_b_time ?? '—'}
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        times are each side's attack · "fullhold" means the attack never finished
      </Lbl>
    </Stack>
  );
}

/** Team totals side by side. Sums, not rates — the rates below them are
 * averages of per-player rates and do not recompute from these. */
function TeamTotals({ matrix }: { matrix: SessionTeamMatrix }) {
  if (!matrix.available || !matrix.aggregates) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
        team totals need a lua roster for every round — this session has none
      </span>
    );
  }
  const { team_a: a, team_b: b } = matrix.aggregates;
  const rows: [string, number | null, number | null][] = [
    ['kills', a.kills, b.kills],
    ['deaths', a.deaths, b.deaths],
    ['damage', a.damage, b.damage],
    ['revives', a.revives, b.revives],
    ['gibs', a.gibs, b.gibs],
    ['dpm avg', a.dpm_avg, b.dpm_avg],
    ['accuracy avg', a.accuracy_avg, b.accuracy_avg],
  ];
  return (
    <Stack gap={3} parity="session.teams">
      <SectionHead
        label="teams"
        aside={<span className="lbl">{matrix.team_a_name} · {matrix.team_b_name}</span>}
      />
      <Stack gap={1} className="rows">
        {rows.map(([label, left, right]) => (
          <Cluster key={label} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-1) 0' }}>
            <span className="m" style={{ fontSize: 'var(--fs-value)', width: 90 }}>
              {left == null ? '—' : figure(left)}
            </span>
            <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{label}</span>
            <span className="m" style={{ fontSize: 'var(--fs-value)', width: 90, textAlign: 'right' }}>
              {right == null ? '—' : figure(right)}
            </span>
          </Cluster>
        ))}
      </Stack>
    </Stack>
  );
}

/** The good-night index: a model with seven named components, shown with
 * them rather than as a bare number nobody can argue with. */
function GoodNight({ data }: { data: SessionGoodNight }) {
  if (!data.available) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
        the night score needs a full session to compute — not computed here,
        which is different from a low score
      </span>
    );
  }
  const components = Object.entries(data.components);
  const max = Math.max(1, ...components.map(([, v]) => v));
  return (
    <Stack gap={3} parity="session.goodnight">
      <SectionHead
        label="night score"
        aside={<span className="lbl">{data.maps} maps · {data.players} players · {data.hours.toFixed(1)} h</span>}
      />
      <Cluster gap={4} align="baseline">
        <span className="m" style={{ fontSize: 'var(--fs-kpi-lg)' }}>{data.score}</span>
        <Stack gap={1} style={{ flex: 1, minWidth: 220 }}>
          {components.map(([name, value]) => (
            <Cluster key={name} gap={2} align="center">
              <span className="lbl" style={{ fontSize: 'var(--fs-caption)', width: 96 }}>{name}</span>
              <span style={{ display: 'block', width: 120, height: 3, background: 'var(--color-rule-900)' }}>
                <span style={{ display: 'block', width: `${(value / max) * 100}%`, height: '100%', background: 'var(--color-accent)' }} />
              </span>
              <span className="m" style={{ fontSize: 'var(--fs-caption)' }}>{value}</span>
            </Cluster>
          ))}
        </Stack>
      </Cluster>
      {data.reasons.length > 0 && (
        <Stack gap={1}>
          {data.reasons.map((r) => (
            <span key={r} className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{r}</span>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

/** Each player against their OWN previous form — never against each other,
 * which is the whole point of the panel. */
function Verdicts({ data }: { data: SessionVerdicts }) {
  return (
    <Stack gap={3} parity="session.verdicts">
      <SectionHead label="form" aside={<span className="lbl">against {data.baseline}</span>} />
      <Stack gap={1} className="rows">
        {data.players.map((p) => (
          <Cluster key={p.guid} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
              <Link to={`/profile/${p.guid.slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)' }}>
                {p.name}
              </Link>
              <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{p.label}</span>
            </Cluster>
            <Cluster gap={3} align="baseline">
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{p.dpm.toFixed(0)}</span>
              {/* A first night has no baseline, so it gets no percentile —
                * printing one would compare a player with nothing. */}
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 190, textAlign: 'right' }}>
                {p.first_night
                  ? 'first night — no baseline yet'
                  : `${p.avg_dpm == null ? '—' : p.avg_dpm.toFixed(0)} usual · ${p.sessions_in_baseline} sessions`}
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
    </Stack>
  );
}

/** Peer votes. Kept visually apart from every computed figure on this page,
 * because "who people picked" and "what the model says" are different
 * claims and the page must not lend one the authority of the other. */
function MvpVotes({ sessionId }: { sessionId: number }) {
  const q = useSessionMvp(sessionId);
  if (q.isPending) return <Pending label="votes" />;
  if (q.isError) return <Unavailable what="votes" />;
  if (q.data.total_votes === 0) {
    return (
      <Stack gap={2} parity="session.mvp">
        <SectionHead label="mvp votes" />
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          nobody voted on this session — an empty ballot, not a tie
        </span>
      </Stack>
    );
  }
  return (
    <Stack gap={3} parity="session.mvp">
      <SectionHead
        label="mvp votes"
        aside={<span className="lbl">{figure(q.data.total_votes)} votes cast by players</span>}
      />
      <Stack gap={1} className="rows">
        {q.data.candidates.filter((c) => c.votes > 0).map((c) => (
          <Cluster key={c.guid} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <span style={{ fontSize: 'var(--fs-row)' }}>{c.name}</span>
            <Cluster gap={3} align="baseline">
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{figure(c.votes)}</span>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 60, textAlign: 'right' }}>
                {c.vote_pct.toFixed(0)}%
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        a vote, not a rating — unrelated to the PWC MVP on the story page
      </Lbl>
    </Stack>
  );
}

const PLAYER_COLUMNS: readonly { key: keyof SessionPlayerTotals; label: string; digits?: number }[] = [
  { key: 'kills', label: 'k' },
  { key: 'deaths', label: 'd' },
  { key: 'kd', label: 'k/d', digits: 2 },
  { key: 'dpm', label: 'dpm', digits: 0 },
  { key: 'damage_given', label: 'dmg' },
  { key: 'headshot_kills', label: 'hs' },
  { key: 'revives_given', label: 'rev' },
  { key: 'accuracy', label: 'acc', digits: 1 },
];

function PlayerTable({ players }: { players: SessionPlayerTotals[] }) {
  const sorted = useMemo(
    () => [...players].sort((a, b) => b.damage_given - a.damage_given),
    [players],
  );
  return (
    <Stack gap={3} parity="session.players">
      <SectionHead
        label="players"
        aside={<span className="lbl">{PLAYER_COLUMNS.map((c) => c.label).join(' · ')}</span>}
      />
      <div style={{ overflowX: 'auto' }}>
        <Stack gap={1} className="rows" style={{ minWidth: 640 }}>
          {sorted.map((p) => (
            <Cluster key={p.player_guid} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
              <Link to={`/profile/${p.player_guid.slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)', minWidth: 140 }}>
                {p.player_name}
              </Link>
              <Cluster gap={3} align="baseline">
                {PLAYER_COLUMNS.map((col) => {
                  const value = p[col.key];
                  return (
                    <span key={col.key} className="m" style={{ fontSize: 'var(--fs-small)', width: 62, textAlign: 'right' }}>
                      {typeof value === 'number'
                        ? (col.digits == null ? figure(value) : value.toFixed(col.digits))
                        : '—'}
                    </span>
                  );
                })}
              </Cluster>
            </Cluster>
          ))}
        </Stack>
      </div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        totals over the session's counted rounds · sorted by damage
      </Lbl>
    </Stack>
  );
}

/** Every round the session recorded, including the ones that do not count.
 *
 * The endpoint deliberately does not filter them (it marks them instead),
 * and this page keeps that decision: a player who played a cancelled round
 * has to be able to find it, and finding it missing with no explanation is
 * the bug that endpoint was built to end. */
function RoundList({ rounds, counted, total }: { rounds: SessionRound[]; counted: number; total: number }) {
  return (
    <Stack gap={3} parity="session.rounds">
      <SectionHead
        label="rounds"
        aside={
          <span className="lbl">
            {counted} of {total} count toward totals
          </span>
        }
      />
      <Stack gap={1} className="rows">
        {rounds.map((r) => (
          <Cluster key={r.round_id} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
              <span className="m lbl" style={{ width: 28, textAlign: 'right' }}>R{r.round_number}</span>
              <span style={{ fontSize: 'var(--fs-row)' }}>{r.map_name}</span>
              {!r.counts_toward_totals && (
                <span className="lbl" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-neg)' }}>
                  {r.round_status ?? 'not counted'} · shown, not summed
                </span>
              )}
            </Cluster>
            <Cluster gap={3} align="baseline">
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>{clock(r.duration_seconds)}</span>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 120, textAlign: 'right' }}>
                {r.players.length} players
              </span>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 90, textAlign: 'right' }}>
                {r.end_reason ?? '—'}
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
    </Stack>
  );
}

function Summary({ detail, sessionId }: { detail: SessionDetailData; sessionId: number }) {
  const night = useSessionGoodNight(sessionId);
  const verdicts = useSessionVerdicts(sessionId);
  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-5)' }}>
      <Scoreboard scoring={detail.scoring} />
      <TeamTotals matrix={detail.team_matrix} />
      {night.isPending && <Pending label="night score" />}
      {night.isError && <Unavailable what="night score" />}
      {night.data && <GoodNight data={night.data} />}
      {verdicts.isPending && <Pending label="form" />}
      {verdicts.isError && <Unavailable what="form" />}
      {verdicts.data && <Verdicts data={verdicts.data} />}
      <MvpVotes sessionId={sessionId} />
    </Stack>
  );
}

export function SessionDetail() {
  const { sessionId: idParam, sessionDate, tab } = useParams();
  const navigate = useNavigate();
  const sessions = useSessions(30);

  // Two ways in, one key. /session-detail/date/:date is a legacy hash, and a
  // date is not a key: a session crossing midnight has two, and one date can
  // hold two sessions. It is resolved against the session list rather than
  // guessed, and when it names more than one the page asks.
  const explicit = Number(idParam);
  const dated = sessionDate && sessions.data
    ? sessions.data.filter((s) => s.date === sessionDate)
    : [];
  const sessionId = Number.isFinite(explicit) && explicit > 0
    ? explicit
    : dated.length === 1 ? dated[0].session_id : null;

  const current: TabKey = TABS.some((t) => t.key === tab) ? (tab as TabKey) : 'summary';
  const detail = useSessionDetail(sessionId);
  const rounds = useSessionRounds(sessionId);

  const goTab = (next: TabKey) => {
    if (sessionId == null) return;
    navigate(next === 'summary' ? `/session-detail/${sessionId}` : `/session-detail/${sessionId}/${next}`);
  };

  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-8)' }}>
      <Lbl>session · one night in full</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        {detail.data ? detail.data.date : sessionDate ?? 'Session'}
      </h1>

      {sessionId == null && sessionDate && sessions.data && (
        <Stack gap={2} parity="session.ambiguous" style={{ paddingTop: 'var(--space-4)' }}>
          {dated.length > 1 ? (
            <>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
                two sessions were played on {sessionDate} — which one?
              </span>
              <Cluster gap={2}>
                {dated.map((s) => (
                  <button
                    key={s.session_id}
                    type="button"
                    className="chip"
                    aria-pressed={false}
                    onClick={() => { navigate(`/session-detail/${s.session_id}`); }}
                  >
                    {s.session_id} · {s.rounds}r · {s.players}p
                  </button>
                ))}
              </Cluster>
            </>
          ) : (
            <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
              no session in the last {sessions.data.length} played on {sessionDate}
            </span>
          )}
        </Stack>
      )}

      {sessionId != null && (
        <>
          <Cluster gap={4} align="baseline" style={{ marginTop: 'var(--space-3)' }}>
            {detail.data && (
              <>
                <span className="lbl">{detail.data.round_count} rounds</span>
                <span className="lbl">{detail.data.player_count} players</span>
                <span className="lbl">{detail.data.matches.length} maps</span>
              </>
            )}
          </Cluster>

          <div style={{ paddingTop: 'var(--space-4)' }}>
            <Tabs tabs={TABS} current={current} onSelect={goTab} parity="session.tabs" />
          </div>

          {detail.isPending && <div style={{ paddingTop: 'var(--space-4)' }}><Pending label="session" /></div>}
          {detail.isError && <div style={{ paddingTop: 'var(--space-4)' }}><Unavailable what="session" /></div>}

          {detail.data && current === 'summary' && (
            <Summary detail={detail.data} sessionId={sessionId} />
          )}
          {detail.data && current === 'players' && (
            <div style={{ paddingTop: 'var(--space-5)' }}>
              <PlayerTable players={detail.data.players} />
            </div>
          )}
          {current === 'rounds' && (
            <div style={{ paddingTop: 'var(--space-5)' }}>
              {rounds.isPending && <Pending label="rounds" />}
              {rounds.isError && <Unavailable what="rounds" />}
              {rounds.data && (
                <RoundList
                  rounds={rounds.data.rounds}
                  counted={rounds.data.counted_rounds}
                  total={rounds.data.total_rounds}
                />
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

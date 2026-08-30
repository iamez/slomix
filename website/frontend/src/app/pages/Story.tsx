import { useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Lbl, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { ApiError } from '../lib/api';
import {
  useStoryBoxScore, useStoryEnabler, useStoryGravity,
  useStoryKillImpact, useStoryKillMatrix, useStoryKisDetails, useStoryKisFormula,
  useStoryLurker, useStoryMoments, useStoryMomentum, useStoryMomentumSession,
  useStoryMovement, useStoryNarrative, useStoryPlayerNarratives, useStoryPwcFormula,
  useStoryScopes, useStorySpace, useStorySynergy, useStoryUselessDefense,
  useStoryWinContribution,
} from '../lib/queries';
import type {
  FormulaTerm, StoryBoxScore, StoryMomentumRound, StoryRolePlayer, StoryScope,
} from '../lib/types';

/**
 * Smart Stats — the story of one session (docs/design/12 row 26).
 *
 * The legacy page (js/story.js, 2,081 lines) reads thirteen endpoints and
 * prints what each returns. The thing it never does is say where one number
 * ends and the next begins, and this page's whole reason to exist is that
 * these thirteen are NOT one measurement: the narrative is generated prose
 * over aggregates, the box score is the scoreboard, PWC is a per-round share
 * model, and gravity/space/enabler/lurker come off the 200 ms position
 * tracker and exist only for rounds the tracker covered. Mixing them into
 * one ranked list — which is what a single table would do — invents a
 * comparison the data cannot support.
 *
 * So the page is ordered by evidence, not by prominence: what happened
 * (scoreboard), what the session felt like (narrative, moments), who
 * carried it (PWC, KIS), and last the telemetry-derived roles, each labelled
 * with what it is measured from.
 */

/** One session in the picker. A gsid is the only midnight-safe key. */
function ScopeChip({ scope, active, onPick }: {
  scope: StoryScope; active: boolean; onPick: (gsid: number) => void;
}) {
  const label = scope.start_date === scope.end_date
    ? scope.start_date
    : `${scope.start_date} → ${scope.end_date}`;
  return (
    <button
      type="button"
      className="chip"
      aria-pressed={active}
      onClick={() => { onPick(scope.gaming_session_id); }}
      title={scope.distinct_map_names.join(', ')}
    >
      {label} · {scope.accepted_round_count}r
    </button>
  );
}

/** The generated paragraph, printed as prose and labelled as generated. */
function Narrative({ gsid }: { gsid: number }) {
  const q = useStoryNarrative(gsid);
  if (q.isPending) return <Pending label="narrative" />;
  if (q.isError) return <Unavailable what="narrative" />;

  const arc = q.data.session_arc;
  return (
    <Stack gap={3} parity="story.narrative">
      <p className="prose-body" style={{ margin: 0, maxWidth: '62ch' }}>{q.data.narrative}</p>
      {arc && (
        <Cluster gap={3} align="baseline">
          <Lbl>arc</Lbl>
          <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{arc.shape}</span>
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>
            {arc.winner} {arc.ws}–{arc.ls}
          </span>
        </Cluster>
      )}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        written by the server from this session's aggregates — a description, not a measurement
      </Lbl>
    </Stack>
  );
}

/** Map-by-map points. This is the scoreboard, and it is the one panel here
 * whose numbers come straight off the rounds rather than out of a model. */
function BoxScore({ data }: { data: StoryBoxScore }) {
  return (
    <Stack gap={3} parity="story.boxscore">
      <SectionHead
        label="scoreboard"
        aside={
          <span className="lbl">
            {data.alpha_team} {data.alpha_score} — {data.beta_score} {data.beta_team}
          </span>
        }
      />
      <Stack gap={1} className="rows">
        {data.maps.map((m) => (
          <Cluster key={m.map_number} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
              <span className="m lbl" style={{ width: 20, textAlign: 'right' }}>{m.map_number}</span>
              <span style={{ fontSize: 'var(--fs-row)' }}>{m.map_name}</span>
              {m.is_fullhold_draw && <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>full hold</span>}
            </Cluster>
            <Cluster gap={3} align="center">
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>
                {m.alpha_points} — {m.beta_points}
              </span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 110, textAlign: 'right' }}>
                {formatClock(m.r1_time)} / {formatClock(m.r2_time)}
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        times are the two halves as played · a full hold draws 1–1
      </Lbl>
    </Stack>
  );
}

/** m:ss, or a dash when the round carries no time at all. */
function formatClock(seconds: number | null): string {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** The highlight reel. Stars are the server's own impact rating (1–5). */
function Moments({ gsid }: { gsid: number }) {
  const q = useStoryMoments(gsid);
  if (q.isPending) return <Pending label="moments" />;
  if (q.isError) return <Unavailable what="moments" />;
  if (q.data.moments.length === 0) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
        nothing in this session cleared the detector's thresholds — that is a
        result about the session, not a gap in the data
      </span>
    );
  }
  return (
    <Stack gap={1} className="rows" parity="story.moments">
      {q.data.moments.map((m, i) => (
        <Stack key={`${m.type}:${m.round_number}:${m.time_ms}:${i}`} gap={1} className="row" style={{ padding: 'var(--space-2) 0' }}>
          <Cluster gap={3} justify="between" align="baseline">
            <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
              <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{m.type.replace(/_/g, ' ')}</span>
              <span style={{ fontSize: 'var(--fs-row)' }}>{m.player}</span>
            </Cluster>
            <Cluster gap={2} align="baseline">
              <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-accent)' }}>
                {'★'.repeat(Math.max(0, Math.min(5, m.impact_stars)))}
              </span>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)' }}>
                {m.map_name} R{m.round_number} · {m.time_formatted}
              </span>
            </Cluster>
          </Cluster>
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{m.narrative}</span>
        </Stack>
      ))}
    </Stack>
  );
}

const MOMENTUM_W = 220;
const MOMENTUM_H = 34;

/** Round-by-round strength as two sparklines, axis and allies, exactly the
 * two series the legacy chart drew.
 *
 * One drawing per round, never one across the session: each round restarts
 * the clock and the sides swap between the halves, so a single continuous
 * line would draw a continuity the numbers do not have.
 *
 * The two lines share ONE scale — computed across both series — because two
 * lines auto-scaled apart would cross wherever the picture felt like it,
 * which is the one thing this chart must not do.
 */
function Momentum({ round }: { round: StoryMomentumRound }) {
  const pts = round.points;
  const paths = useMemo(() => {
    if (pts.length < 2) return null;
    const values = pts.flatMap((p) => [p.axis, p.allies]);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const span = hi - lo || 1;
    const step = MOMENTUM_W / (pts.length - 1);
    const line = (pick: (p: { axis: number; allies: number }) => number) =>
      pts
        .map((p, i) => {
          const y = MOMENTUM_H - 2 - ((pick(p) - lo) / span) * (MOMENTUM_H - 4);
          return `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');
    return { axis: line((p) => p.axis), allies: line((p) => p.allies) };
  }, [pts]);

  return (
    <Cluster gap={3} align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
      <span className="m lbl" style={{ width: 170 }}>{round.map_name} R{round.round_number}</span>
      {paths ? (
        <svg
          width={MOMENTUM_W}
          height={MOMENTUM_H}
          role="img"
          aria-label={`momentum, ${round.map_name} round ${round.round_number}`}
        >
          <path d={paths.axis} fill="none" stroke="var(--color-neg)" strokeWidth="1.5" />
          <path d={paths.allies} fill="none" stroke="var(--color-accent)" strokeWidth="1.5" />
        </svg>
      ) : (
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
          too few samples to draw
        </span>
      )}
    </Cluster>
  );
}

const SESSION_W = 620;
const SESSION_H = 90;

/** The same two series as above, but across the WHOLE evening — and it is a
 * different measurement, not a zoomed-out one.
 *
 * The per-round chart refuses to join its rounds because the sides swap
 * between halves, so one continuous axis/allies line would draw a continuity
 * the numbers do not have. This endpoint sidesteps exactly that: it tracks
 * the two PERSISTENT ROSTERS (`teams.team_a` / `team_b`, from stopwatch
 * roster tracking), which follow the players across the swap. The rosters are
 * printed under the curve for that reason — the lines mean nothing until you
 * know who is in them.
 *
 * Three payload shapes, and they are told apart rather than collapsed:
 * `no_data` (no rounds at all), `no_team_data` (rounds, but no roster could
 * be built — it carries the server's own reason) and `ok`.
 */
function SessionMomentum({ gsid }: { gsid: number }) {
  const q = useStoryMomentumSession(gsid);
  const data = q.data;
  const paths = useMemo(() => {
    if (!data || data.status !== 'ok' || data.points.length < 2) return null;
    const pts = data.points;
    const values = pts.flatMap((p) => [p.team_a, p.team_b]);
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const span = hi - lo || 1;
    const tMax = pts[pts.length - 1].t_ms || 1;
    const x = (t: number) => (t / tMax) * SESSION_W;
    const line = (pick: (p: { team_a: number; team_b: number }) => number) =>
      pts
        .map((p, i) => {
          const y = SESSION_H - 2 - ((pick(p) - lo) / span) * (SESSION_H - 4);
          return `${i === 0 ? 'M' : 'L'}${x(p.t_ms).toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');
    return {
      a: line((p) => p.team_a),
      b: line((p) => p.team_b),
      marks: data.round_boundaries.map((r) => ({ ...r, x: x(r.x_ms) })),
    };
  }, [data]);

  if (q.isPending) return <Pending label="session momentum" />;
  if (q.isError || !data) return <Unavailable what="session momentum" />;

  if (data.status !== 'ok') {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
        {data.status === 'no_team_data'
          ? `no persistent teams could be built for this session (${data.reason}) — the per-round charts above are unaffected`
          : 'this session has no momentum samples'}
      </span>
    );
  }

  return (
    <Stack gap={2}>
      {paths ? (
        <svg width={SESSION_W} height={SESSION_H} role="img" aria-label="momentum across the session" style={{ maxWidth: '100%' }}>
          {paths.marks.map((m) => (
            <line
              key={`${m.map_name}:${m.round_number}:${m.x_ms}`}
              x1={m.x} x2={m.x} y1={0} y2={SESSION_H}
              stroke="var(--color-rule-600)" strokeWidth="1" strokeDasharray="2 3"
            />
          ))}
          <path d={paths.a} fill="none" stroke="var(--color-team-a)" strokeWidth="1.5" />
          <path d={paths.b} fill="none" stroke="var(--color-team-b)" strokeWidth="1.5" />
        </svg>
      ) : (
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
          too few samples to draw
        </span>
      )}
      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-team-a)' }}>
          {data.teams.team_a.label}: {data.teams.team_a.players.join(', ') || '—'}
        </span>
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-team-b)' }}>
          {data.teams.team_b.label}: {data.teams.team_b.players.join(', ') || '—'}
        </span>
      </Cluster>
      {/* Both counts name what the curve LEAVES OUT, which a line drawn
        * without them silently absorbs. */}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        {figure(data.meta.rounds)} rounds in the curve
        {data.meta.unmapped_rounds > 0 && ` · ${figure(data.meta.unmapped_rounds)} round(s) played but not attributable to either roster`}
        {data.meta.defaulted_players_count > 0 && ` · ${figure(data.meta.defaulted_players_count)} player(s) scored at the default for lack of telemetry`}
      </Lbl>
    </Stack>
  );
}

/** Who killed whom. The pairing is the first thing people argue about after a
 * night, and it is the one view the platform never showed even though every
 * duel already sits in `proximity_kill_outcome`.
 *
 * Capped at the top eight by kills: the grid is N×N, and past eight columns
 * it stops being readable long before it stops being true. The cap is stated
 * on screen rather than applied quietly.
 */
function KillMatrix({ gsid }: { gsid: number }) {
  const q = useStoryKillMatrix(gsid);
  if (q.isPending) return <Pending label="kill matrix" />;
  if (q.isError) return <Unavailable what="kill matrix" />;
  const data = q.data;
  if (!data.available) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
        no per-kill telemetry for this session ({data.reason}) — the scoreboard
        above still counts the kills, this view needs the pairing
      </span>
    );
  }

  const shown = data.players.slice(0, 8);
  const keys = shown.map((p) => p.guid_short);
  const byPair = new Map(data.cells.map((c) => [`${c.killer}>${c.victim}`, c]));

  return (
    <Stack gap={2}>
      <div style={{ overflowX: 'auto' }}>
        <table className="m" style={{ borderCollapse: 'collapse', fontSize: 'var(--fs-caption)' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: 'var(--space-1) var(--space-2)' }} className="lbl">killer ╲ victim</th>
              {shown.map((p) => (
                <th key={p.guid_short} style={{ padding: 'var(--space-1) var(--space-2)', textAlign: 'right', whiteSpace: 'nowrap' }} className="lbl">
                  {p.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <tr key={row.guid_short}>
                <td style={{ padding: 'var(--space-1) var(--space-2)', whiteSpace: 'nowrap' }}>{row.name}</td>
                {keys.map((victim) => {
                  const cell = row.guid_short === victim ? undefined : byPair.get(`${row.guid_short}>${victim}`);
                  return (
                    <td
                      key={victim}
                      style={{ padding: 'var(--space-1) var(--space-2)', textAlign: 'right', color: cell ? 'var(--color-text-100)' : 'var(--color-text-500)' }}
                      title={cell ? `${cell.kills} kills · ${cell.gibs} gibbed · ${cell.revived} revived` : undefined}
                    >
                      {row.guid_short === victim ? '·' : cell ? cell.kills : '0'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        {figure(data.total_kills)} kills paired
        {data.players.length > shown.length && ` · showing the top ${shown.length} of ${data.players.length} players by kills`}
        {' · a cell is killer → victim; the diagonal is blank because a selfkill is not a duel'}
      </Lbl>
    </Stack>
  );
}

/** Distance and speed, in raw engine units — the server refuses to convert to
 * metres because the constant would be invented precision, and this page says
 * so rather than quietly printing "m". */
function Movement({ gsid }: { gsid: number }) {
  const q = useStoryMovement(gsid);
  if (q.isPending) return <Pending label="movement" />;
  if (q.isError) return <Unavailable what="movement" />;
  const data = q.data;
  if (!data.available) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
        the position tracker recorded no movement for this session ({data.reason})
      </span>
    );
  }
  return (
    <Stack gap={2}>
      <Stack gap={1} className="rows">
        {data.players.slice(0, 10).map((p) => (
          <Cluster key={p.guid_short} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <span style={{ fontSize: 'var(--fs-row)', minWidth: 0 }}>{p.name}</span>
            <Cluster gap={3} align="baseline">
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>
                {/* null, not 0: a player with no alive time has no rate at
                  * all, and 0 would read as "stood still". */}
                {p.distance_per_min == null ? '—' : figure(Math.round(p.distance_per_min))}
              </span>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 250, textAlign: 'right', whiteSpace: 'nowrap' }}>
                per min · {figure(p.total_distance)} total · peak {figure(Math.round(p.peak_speed))}
                {p.sprint_pct == null ? '' : ` · ${p.sprint_pct.toFixed(0)}% sprint`}
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        {data.unit === 'et_units' ? 'engine units, not metres — the conversion constant would be invented' : data.unit}
        {' · per minute ALIVE, so a longer life does not read as more movement'}
      </Lbl>
    </Stack>
  );
}

/** PWC — and the reason the top of the list is not the MVP. */
function WinContribution({ gsid }: { gsid: number }) {
  const q = useStoryWinContribution(gsid);
  if (q.isPending) return <Pending label="win contribution" />;
  if (q.isError) return <Unavailable what="win contribution" />;

  const { mvp, players } = q.data;
  // .at(0), not [0]: an index read is typed as if it always hit, so the
  // null-check below reads to the compiler (and to Codacy) as dead code
  // while being the only thing standing between an empty board and a crash.
  // The array can be empty — a session where nobody met the round floor —
  // so the type has to say what the runtime does.
  const leader = players.at(0);
  const mvpIsLeader = mvp != null && leader != null && mvp.guid === leader.guid;

  return (
    <Stack gap={3} parity="story.pwc">
      <SectionHead label="win contribution" aside={<span className="lbl">pwc · wis · rounds</span>} />
      {mvp && (
        <Stack gap={1}>
          <Cluster gap={2} align="baseline">
            <Lbl>mvp</Lbl>
            <span style={{ fontSize: 'var(--fs-lead)' }}>{mvp.name}</span>
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>
              waa {mvp.waa_bayes.toFixed(3)}
            </span>
          </Cluster>
          {/* The MVP is picked by waa_bayes, the board is ordered by total
            * pwc, and those disagree often enough that a page showing only
            * the board makes the badge look arbitrary (#783). */}
          <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
            {mvpIsLeader
              ? 'top of the board and MVP are the same player here — they are still two different metrics'
              : `picked by waa_bayes (pwc in WON rounds ÷ rounds played, shrunk), not by the board below, which ${leader ? `${leader.name} leads` : 'is ordered by total pwc'}`}
          </span>
        </Stack>
      )}
      <Stack gap={1} className="rows">
        {players.map((p) => (
          <Cluster key={p.guid} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
            <span style={{ fontSize: 'var(--fs-row)', minWidth: 0 }}>{p.name}</span>
            <Cluster gap={3} align="center">
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{p.total_pwc.toFixed(2)}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 64, textAlign: 'right' }}>
                {p.wis.toFixed(2)}
              </span>
              <span className="m lbl" style={{ width: 72, textAlign: 'right', fontSize: 'var(--fs-caption)' }}>
                {p.rounds_won}–{p.rounds_lost}
              </span>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
      <PwcFormula />
    </Stack>
  );
}

/** One published term, printed from whatever the server chose to publish for
 * it. The terms are genuinely not uniform — `spawn_timing` has a range and a
 * bonus and no value, `long_range` has a value and a threshold and no
 * description, the retired `push` term has a status — so this prints the
 * fields that are there instead of assuming a shape and rendering
 * "undefined" for the rest. */
function Term({ name, term }: { name: string; term: FormulaTerm }) {
  const head = term.value != null
    ? `×${term.value}`
    : term.range != null
      ? term.range
      : term.tiers != null
        ? `${term.tiers.length} tiers`
        : term.solo_clutch?.value != null
          ? `×${term.solo_clutch.value} / ×${term.outnumbered?.value ?? '?'}`
          : '';
  return (
    <Stack gap={1} className="row" style={{ padding: 'var(--space-1) 0' }}>
      <Cluster gap={2} align="baseline" justify="between">
        <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
          <span className="m" style={{ fontSize: 'var(--fs-small)' }}>{name.replace(/_/g, ' ')}</span>
          {term.status && (
            <span className="lbl" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-neg)' }}>{term.status}</span>
          )}
        </Cluster>
        <span className="m" style={{ fontSize: 'var(--fs-small)', whiteSpace: 'nowrap' }}>
          {head}
          {term.threshold != null && (
            <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}> {String(term.threshold)}</span>
          )}
        </span>
      </Cluster>
      {term.description && (
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)', maxWidth: '70ch' }}>
          {term.description}
        </span>
      )}
    </Stack>
  );
}

function TermGroup({ label, terms }: { label: string; terms: Record<string, FormulaTerm> }) {
  const rows = Object.entries(terms);
  if (rows.length === 0) return null;
  return (
    <Stack gap={1}>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{label}</Lbl>
      <Stack gap={1} className="rows">
        {rows.map(([name, term]) => <Term key={name} name={name} term={term} />)}
      </Stack>
    </Stack>
  );
}

/** The PWC weights, published because a weighted sum nobody can check is a
 * claim rather than a measurement (#769). Closed by default and unfetched
 * until opened — this is reference material, not part of the reading. */
function PwcFormula() {
  const [open, setOpen] = useState(false);
  const q = useStoryPwcFormula(open);
  return (
    <Stack gap={2} parity="story.pwc-formula">
      <button type="button" className="chip" aria-expanded={open} onClick={() => { setOpen((v) => !v); }}>
        {open ? 'hide how pwc is computed' : 'how is pwc computed?'}
      </button>
      {open && q.isPending && <Pending label="the pwc formula" />}
      {open && q.isError && <Unavailable what="the pwc formula" />}
      {open && q.data && (
        <Stack gap={3} style={{ maxWidth: '80ch' }}>
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>
            {q.data.name} · {q.data.version}
          </span>
          <p className="prose-body" style={{ margin: 0 }}>{q.data.description}</p>
          <TermGroup label="weights" terms={q.data.weights} />
          {q.data.zero_objective_rounds.description && (
            <Stack gap={1}>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>rounds with no objective action</Lbl>
              <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                {q.data.zero_objective_rounds.description}
              </span>
            </Stack>
          )}
          {q.data.mvp.description && (
            <Stack gap={1}>
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>mvp · {q.data.mvp.metric ?? 'metric not published'}</Lbl>
              <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                {q.data.mvp.description}
              </span>
            </Stack>
          )}
        </Stack>
      )}
    </Stack>
  );
}

/** The KIS multiplier table, same contract as PwcFormula. `validity` is
 * printed with it and not tucked away: the server publishes what the score
 * does NOT measure, and that half is the one a reader needs. */
function KisFormula() {
  const [open, setOpen] = useState(false);
  const q = useStoryKisFormula(open);
  return (
    <Stack gap={2} parity="story.kis-formula">
      <button type="button" className="chip" aria-expanded={open} onClick={() => { setOpen((v) => !v); }}>
        {open ? 'hide how kis is computed' : 'how is kis computed?'}
      </button>
      {open && q.isPending && <Pending label="the kis formula" />}
      {open && q.isError && <Unavailable what="the kis formula" />}
      {open && q.data && (
        <Stack gap={3} style={{ maxWidth: '80ch' }}>
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>
            {q.data.name} · {q.data.version}
          </span>
          <p className="prose-body" style={{ margin: 0 }}>{q.data.description}</p>
          <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-300)' }}>{q.data.formula}</span>
          <TermGroup label="context multipliers" terms={q.data.multipliers} />
          <TermGroup label="what happened to the body" terms={q.data.outcome_multipliers} />
          <TermGroup label="victim class" terms={q.data.class_weights} />
          <TermGroup label="distance" terms={q.data.distance_multipliers} />
          <TermGroup label="objective area" terms={q.data.objective_multipliers} />
          <TermGroup label="oksii context" terms={q.data.oksii_multipliers} />
          <Stack gap={1}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>what it does and does not measure</Lbl>
            {Object.entries(q.data.validity).map(([k, v]) => (
              <span key={k} className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                <span className="lbl">{k.replace(/_/g, ' ')}: </span>{v}
              </span>
            ))}
          </Stack>
        </Stack>
      )}
    </Stack>
  );
}

/** Every kill behind one player's score, with the multipliers that produced
 * it — the difference between a number and a number you can check.
 *
 * Fetched only when a row is opened: 205 kills for the top player of session
 * 150 is the right size for a disclosure and the wrong size for a page load.
 */
function KisDetails({ gsid, guid, name }: { gsid: number; guid: string; name: string }) {
  const q = useStoryKisDetails(gsid, guid);
  if (q.isPending) return <Pending label={`${name}'s kills`} />;
  if (q.isError) return <Unavailable what={`${name}'s kills`} />;
  const { summary, kills } = q.data;
  if (kills.length === 0) {
    return (
      <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
        {/* player_name is the EMPTY STRING in this branch — the handler only
          * looks it up when there are kills — so the name comes from the row
          * that was clicked, not from the response. */}
        no scored kills for {name} in this session
      </span>
    );
  }
  const top = [...kills].sort((a, b) => b.total_impact - a.total_impact).slice(0, 10);
  return (
    <Stack gap={2} style={{ paddingLeft: 'var(--space-4)' }}>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        {figure(summary.kills)} kills · {summary.total_kis.toFixed(1)} total · {summary.avg_impact.toFixed(2)} average
        {' · '}{figure(summary.carrier_kills)} carrier · {figure(summary.crossfire_kills)} crossfire
      </Lbl>
      <Stack gap={1} className="rows">
        {top.map((k) => {
          const mults = [
            ['carrier', k.carrier_multiplier],
            ['crossfire', k.crossfire_multiplier],
            ['spawn', k.spawn_multiplier],
            ['outcome', k.outcome_multiplier],
            ['class', k.class_multiplier],
            ['distance', k.distance_multiplier],
            ['health', k.health_multiplier],
            ['alive', k.alive_multiplier],
            ['reinf', k.reinf_multiplier],
          ] as const;
          // Only the multipliers that MOVED the score: printing nine ×1.0s
          // per row buries the two that did the work.
          const applied = mults.filter(([, v]) => v !== 1);
          return (
            <Cluster key={k.kill_outcome_id ?? `${k.map_name}:${k.kill_time_ms}:${k.victim_guid}`} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
              <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
                <span className="m" style={{ fontSize: 'var(--fs-small)', width: 44, textAlign: 'right' }}>
                  {k.total_impact.toFixed(1)}
                </span>
                <span style={{ fontSize: 'var(--fs-small)' }}>{k.victim_name}</span>
                <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{k.map_name} R{k.round_number}</span>
              </Cluster>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>
                {applied.length === 0
                  ? 'base kill, no context'
                  : applied.map(([label, v]) => `${label} ×${v.toFixed(2).replace(/0$/, '')}`).join(' · ')}
              </span>
            </Cluster>
          );
        })}
      </Stack>
      {kills.length > top.length && (
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
          the ten highest-scoring of {figure(kills.length)} — the summary above counts all of them
        </Lbl>
      )}
    </Stack>
  );
}

/** Role scores are not one scale: gravity is a summed attention figure in
 * the tens of thousands, a solo share is a percentage. Grouping the large
 * ones and keeping a decimal on the small ones is the difference between a
 * column that can be read and a row of digits (seen on the first render
 * against session 154: `41952.5` beside `46.7`). */
function roleFigure(value: number): string {
  return Math.abs(value) >= 1000
    ? Math.round(value).toLocaleString('en-US')
    : value.toFixed(1);
}

/** One telemetry-derived role board. Every one of these is measured from the
 * position tracker, so the label says so once per board rather than once per
 * page — a reader who scrolls into the middle still learns it. */
function RoleBoard({ label, note, rows, value, unit }: {
  label: string;
  note: string;
  rows: StoryRolePlayer[];
  value: (row: StoryRolePlayer) => number;
  unit?: string;
}) {
  const top = rows.slice(0, 5);
  return (
    <Stack gap={2} style={{ minWidth: 200, flex: '1 1 200px' }}>
      <SectionHead label={label} />
      {top.length === 0 ? (
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          the tracker recorded nothing for this session
        </span>
      ) : (
        <Stack gap={1} className="rows">
          {top.map((r) => (
            <Cluster key={r.guid_short ?? r.name} gap={2} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
              <span style={{ fontSize: 'var(--fs-small)', minWidth: 0 }}>{r.name}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
                {roleFigure(value(r))}{unit ?? ''}
              </span>
            </Cluster>
          ))}
        </Stack>
      )}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{note}</Lbl>
    </Stack>
  );
}

/** The fifth board, and the only one where a high number is bad.
 *
 * It does not go through RoleBoard because its rows are not role rows: a
 * count is not a score, and the two numbers that make it meaningful — how
 * many defensive deaths there were in total, and the thresholds that decide
 * what counts as useless — have nowhere to live in a one-value board. */
function DefenseBoard({ gsid }: { gsid: number }) {
  const q = useStoryUselessDefense(gsid);
  if (q.isPending) return <Pending label="defensive deaths" />;
  if (q.isError) return <Unavailable what="defensive deaths" />;
  const { players, thresholds } = q.data;
  return (
    <Stack gap={2} style={{ minWidth: 260, flex: '1 1 260px' }}>
      <SectionHead label="costly deaths" />
      {players.length === 0 ? (
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          nobody cleared both thresholds this session — an answer about the
          session, not a missing measurement
        </span>
      ) : (
        <Stack gap={1} className="rows">
          {players.slice(0, 5).map((p) => (
            <Cluster key={p.guid_short} gap={2} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
              <span style={{ fontSize: 'var(--fs-small)', minWidth: 0 }}>{p.name}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
                {p.useless_deaths}
                <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>
                  {' '}of {p.total_defense_deaths} · {(p.rate * 100).toFixed(0)}%
                </span>
              </span>
            </Cluster>
          ))}
        </Stack>
      )}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        died in defence with the next spawn ≥{thresholds.min_reinf_seconds}s away
        and the killer still above {thresholds.min_killer_health} HP — free
        objective time, no trade. Higher is worse.
      </Lbl>
    </Stack>
  );
}

function Roles({ gsid }: { gsid: number }) {
  const gravity = useStoryGravity(gsid);
  const space = useStorySpace(gsid);
  const enabler = useStoryEnabler(gsid);
  const lurker = useStoryLurker(gsid);
  const boards = [gravity, space, enabler, lurker];

  // The four tracker boards share a fate — they read the same telemetry — so
  // they answer together. The fifth board does NOT: it is counted from kill
  // outcomes, and gating it on the tracker's silence would hide a measurement
  // that is perfectly available.
  const trackerBoards = boards.every((b) => b.isPending)
    ? <Pending label="roles" />
    : boards.every((b) => b.isError)
      ? <Unavailable what="roles" />
      : null;

  return (
    <Stack gap={3} parity="story.roles">
      <SectionHead
        label="roles"
        aside={<span className="lbl">four from the 200 ms position tracker · one from kill outcomes</span>}
      />
      <Cluster gap={5} align="start" style={{ flexWrap: 'wrap' }}>
        {trackerBoards}
        {gravity.data && (
          <RoleBoard
            label="gravity"
            note="attackers drawn per engagement"
            rows={gravity.data.players}
            value={(r) => r.gravity_score ?? 0}
          />
        )}
        {space.data && (
          <RoleBoard
            label="space created"
            note="deaths a teammate converted within the window"
            rows={space.data.players}
            value={(r) => r.space_score ?? 0}
          />
        )}
        {enabler.data && (
          <RoleBoard
            label="enabler"
            note="crossfire and trade assists into others' kills"
            rows={enabler.data.players}
            value={(r) => r.enabler_score ?? 0}
          />
        )}
        {lurker.data && (
          <RoleBoard
            label="alone"
            note="share of samples with no teammate nearby"
            rows={lurker.data.players}
            value={(r) => r.solo_pct ?? 0}
            unit="%"
          />
        )}
        {/* Not from the position tracker like its four neighbours — this one
          * is counted from kill outcomes and spawn timers, which is why it
          * survives on sessions where the tracker recorded nothing. */}
        <DefenseBoard gsid={gsid} />
      </Cluster>
      {/* Absence and unavailability have the same shape on screen unless the
        * page says which one it is. */}
      {boards.some((b) => b.isError) && (
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-neg)' }}>
          one or more role boards could not be measured — the boards shown are complete, the missing ones are unknown
        </span>
      )}
    </Stack>
  );
}

/** Everything below the scoreboard hangs off one resolved session. */
function SessionStory({ gsid }: { gsid: number }) {
  const narrative = useStoryNarrative(gsid);
  const box = useStoryBoxScore(gsid);
  const momentum = useStoryMomentum(gsid);
  const synergy = useStorySynergy(gsid);
  const kis = useStoryKillImpact(gsid);
  const narratives = useStoryPlayerNarratives(gsid);
  // Which player's per-kill breakdown is open, if any. One at a time: the
  // detail response is per player, and two open rows would be two fetches
  // for a comparison the page does not draw.
  const [openKis, setOpenKis] = useState<string | null>(null);

  // All thirteen endpoints resolve the same scope, so they 404 together:
  // "gaming_session_id=151 has no accepted rounds". Rendering that as nine
  // separate `unavailable` lines describes nine broken panels instead of one
  // fact about the session — measured on 151, 146, 145 and 128, which is
  // half the sessions a picker click can reach.
  const noRounds = narrative.error instanceof ApiError && narrative.error.status === 404;
  if (noRounds) {
    return (
      <Stack gap={2} parity="story.no-rounds" style={{ paddingTop: 'var(--space-5)' }}>
        <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
          this session has no accepted rounds, so there is no story to tell
        </span>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
          every panel here is built from counted rounds — the session detail page
          still lists what was played
        </Lbl>
      </Stack>
    );
  }

  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-5)' }}>
      <Narrative gsid={gsid} />

      {box.isPending && <Pending label="scoreboard" />}
      {box.isError && <Unavailable what="scoreboard" />}
      {box.data && <BoxScore data={box.data} />}

      <Stack gap={3}>
        <SectionHead label="moments" aside={<span className="lbl">detected · impact 1–5</span>} />
        <Moments gsid={gsid} />
      </Stack>

      <Stack gap={3} parity="story.momentum">
        <SectionHead
          label="momentum"
          aside={
            <span className="lbl">
              <span style={{ color: 'var(--color-neg)' }}>axis</span>
              {' · '}
              <span style={{ color: 'var(--color-accent)' }}>allies</span>
              {' · one drawing per round'}
            </span>
          }
        />
        {momentum.isPending && <Pending label="momentum" />}
        {momentum.isError && <Unavailable what="momentum" />}
        {momentum.data && (
          <Stack gap={1} className="rows">
            {momentum.data.rounds.map((r) => (
              <Momentum key={`${r.map_name}:${r.round_number}`} round={r} />
            ))}
          </Stack>
        )}
      </Stack>

      <Stack gap={3} parity="story.momentum-session">
        <SectionHead
          label="the evening as one curve"
          aside={<span className="lbl">by persistent roster, not by side</span>}
        />
        <SessionMomentum gsid={gsid} />
      </Stack>

      <WinContribution gsid={gsid} />

      <Stack gap={3} parity="story.kis">
        <SectionHead label="kill impact" aside={<span className="lbl">kis · kills · carrier · clutch</span>} />
        {kis.isPending && <Pending label="kill impact" />}
        {kis.isError && <Unavailable what="kill impact" />}
        {kis.data && (
          <Stack gap={1} className="rows">
            {kis.data.players.slice(0, 10).map((p) => (
              <Stack key={p.guid} gap={1} className="row" style={{ padding: 'var(--space-2) 0' }}>
                <Cluster gap={3} justify="between" align="center">
                  <button
                    type="button"
                    className="row-open"
                    aria-expanded={openKis === p.guid}
                    onClick={() => { setOpenKis((cur) => (cur === p.guid ? null : p.guid)); }}
                    style={{ fontSize: 'var(--fs-row)', minWidth: 0, background: 'none', border: 0, padding: 0, color: 'inherit', cursor: 'pointer', textAlign: 'left' }}
                  >
                    {p.name} <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{openKis === p.guid ? '▾' : '▸'}</span>
                  </button>
                  <Cluster gap={3} align="center">
                    <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{p.total_kis.toFixed(1)}</span>
                    <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 230, textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {figure(p.kills)} k · {figure(p.carrier_kills)} carrier · {figure(p.clutch_kills)} clutch
                    </span>
                  </Cluster>
                </Cluster>
                {openKis === p.guid && <KisDetails gsid={gsid} guid={p.guid} name={p.name} />}
              </Stack>
            ))}
          </Stack>
        )}
        <KisFormula />
      </Stack>

      <Stack gap={3} parity="story.kill-matrix">
        <SectionHead label="who killed whom" aside={<span className="lbl">one cell per duel · from kill outcomes</span>} />
        <KillMatrix gsid={gsid} />
      </Stack>

      <Stack gap={3} parity="story.movement">
        <SectionHead label="movement" aside={<span className="lbl">from the position tracker · engine units</span>} />
        <Movement gsid={gsid} />
      </Stack>

      <Stack gap={3} parity="story.synergy">
        <SectionHead label="synergy" aside={<span className="lbl">two groups, one composite</span>} />
        {synergy.isPending && <Pending label="synergy" />}
        {synergy.isError && <Unavailable what="synergy" />}
        {synergy.data && (
          <Cluster gap={6} align="start" style={{ flexWrap: 'wrap' }}>
            {/* Named, not indexed: the two groups are a pair, not a list,
              * and an object read by a computed key is a finding in this
              * repo's scanners even when the key is a literal. */}
            {[
              { key: 'group_a', group: synergy.data.groups.group_a },
              { key: 'group_b', group: synergy.data.groups.group_b },
            ].map(({ key, group: g }) => {
              return (
                <Stack key={key} gap={1} style={{ minWidth: 240 }}>
                  <Cluster gap={2} align="baseline">
                    <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{g.composite.toFixed(1)}</span>
                    <span className="lbl">{g.players.join(', ')}</span>
                  </Cluster>
                  <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                    crossfire {g.crossfire.toFixed(1)} · trade {g.trade.toFixed(1)} · cohesion {g.cohesion.toFixed(1)} · push {g.push.toFixed(1)} · medic {g.medic.toFixed(1)}
                  </span>
                </Stack>
              );
            })}
          </Cluster>
        )}
        {synergy.data && synergy.data.defaulted_players_count > 0 && (
          <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
            {synergy.data.defaulted_players_count} player(s) had no telemetry and were scored at the default — the composite is that much less measured
          </span>
        )}
      </Stack>

      <Roles gsid={gsid} />

      <Stack gap={3} parity="story.players">
        <SectionHead label="players" aside={<span className="lbl">archetype · generated</span>} />
        {narratives.isPending && <Pending label="player notes" />}
        {narratives.isError && <Unavailable what="player notes" />}
        {narratives.data && (
          <Stack gap={3} className="rows">
            {narratives.data.player_narratives.map((p) => (
              <Stack key={p.guid_short} gap={1} className="row" style={{ padding: 'var(--space-2) 0' }}>
                <Cluster gap={2} align="baseline">
                  <span style={{ fontSize: 'var(--fs-row)' }}>{p.name}</span>
                  <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{p.archetype}</span>
                </Cluster>
                <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', maxWidth: '62ch' }}>
                  {p.narrative}
                </span>
              </Stack>
            ))}
          </Stack>
        )}
      </Stack>
    </Stack>
  );
}

export function Story() {
  const routeParams = useParams();
  const [params, setParams] = useSearchParams();
  const scopes = useStoryScopes(20);

  // Four ways in, one key. The legacy hashes carried /story/session/:gsid and
  // /story/date/:date, the app links with ?gsid=, and a first visit has none
  // of them and takes the most recent session.
  //
  // The gsid is the key everywhere BELOW this line, because a date is not
  // one: a session that crosses midnight has two, and a date can hold two
  // sessions. So a dated link is resolved here, and when it resolves to more
  // than one session the page asks instead of picking — silently showing the
  // wrong night is the failure a deep link exists to prevent.
  const fromRoute = Number(routeParams.gsid);
  const fromQuery = Number(params.get('gsid'));
  const explicit = Number.isFinite(fromRoute) && fromRoute > 0
    ? fromRoute
    : Number.isFinite(fromQuery) && fromQuery > 0 ? fromQuery : null;

  const dateParam = routeParams.date ?? null;
  const dated = dateParam && scopes.data
    ? scopes.data.sessions.filter(
      (s) => s.start_date === dateParam || s.end_date === dateParam,
    )
    : [];
  const latest = scopes.data?.sessions.at(0)?.gaming_session_id ?? null;
  const gsid = explicit
    ?? (dateParam ? (dated.length === 1 ? dated[0].gaming_session_id : null) : latest);

  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-8)' }}>
      <Lbl>smart stats · one session, told</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        What happened that night.
      </h1>

      <Stack gap={2} style={{ paddingTop: 'var(--space-4)' }} parity="story.scopes">
        <Lbl>session</Lbl>
        {scopes.isPending && <Pending label="sessions" />}
        {scopes.isError && <Unavailable what="sessions" />}
        {scopes.data && scopes.data.sessions.length === 0 && (
          <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
            no session has enough accepted rounds to tell a story yet
          </span>
        )}
        {scopes.data && scopes.data.sessions.length > 0 && (
          <Cluster gap={2} style={{ flexWrap: 'wrap' }}>
            {scopes.data.sessions.map((s) => (
              <ScopeChip
                key={s.gaming_session_id}
                scope={s}
                active={s.gaming_session_id === gsid}
                onPick={(picked) => { setParams({ gsid: String(picked) }); }}
              />
            ))}
          </Cluster>
        )}
      </Stack>

      {/* A dated link that did not resolve to exactly one session. Both
        * cases below are answers, not errors, and they read differently on
        * purpose: one is a choice to make, the other is a fact about the
        * window this page can see. */}
      {gsid == null && dateParam && scopes.data && (
        <Stack gap={2} parity="story.ambiguous" style={{ paddingTop: 'var(--space-5)' }}>
          {dated.length > 1 ? (
            <>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
                two sessions were played on {dateParam} — which one?
              </span>
              <Cluster gap={2}>
                {dated.map((s) => (
                  <ScopeChip
                    key={s.gaming_session_id}
                    scope={s}
                    active={false}
                    onPick={(picked) => { setParams({ gsid: String(picked) }); }}
                  />
                ))}
              </Cluster>
            </>
          ) : (
            <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
              no session in the recent window started or ended on {dateParam} — it
              may be older than the {scopes.data.sessions.length} shown above
            </span>
          )}
        </Stack>
      )}

      {gsid != null && <SessionStory key={gsid} gsid={gsid} />}
    </div>
  );
}

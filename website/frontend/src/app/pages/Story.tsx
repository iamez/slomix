import { useMemo, useState } from 'react';
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure, lblStyle } from '../components/ui';
import { ApiError } from '../lib/api';
import { isFailureStatus } from '../lib/responseStatus';
import { stripEtColors } from '../lib/names';
import {
  useComposite,
  useStoryBoxScore, useStoryEnabler, useStoryGravity,
  useStoryEscorts, useStoryKillImpact, useStoryKillMatrix, useStoryKisDetails, useStoryKisFormula,
  useStoryCamp, useStoryLurker, useStoryMoments, useStoryMomentum, useStoryMomentumSession,
  useStoryMovement, useStoryNarrative, useStoryPlayerNarratives, useStoryPwcFormula,
  useStorySpace, useStorySynergy, useStoryUselessDefense,
  useStoryWinContribution,
} from '../lib/queries';
import type {
  CompositeStats, FormulaTerm, StoryBoxScore, StoryMomentumRound, StoryRolePlayer,
} from '../lib/types';

/**
 * Smart Stats — the story of one session (docs/design/12 row 26). Since
 * stats 2.0 R4 this is the session page's `story` tab (docs/design/18 §C
 * plast 3): the page resolves the session, this file tells it. The old
 * /story shell (scope chips, the dated-link resolver) is gone — the session
 * page already does both, and /story/session/:gsid redirects here.
 *
 * The legacy page (js/story.js, 2,081 lines) reads thirteen endpoints and
 * prints what each returns. The thing it never does is say where one number
 * ends and the next begins, and this page's whole reason to exist is that
 * these fourteen (the legacy thirteen plus the camp profile) are NOT one
 * measurement: the narrative is generated prose over aggregates, the box
 * score is the scoreboard, PWC is a per-round share model, and
 * gravity/space/enabler/lurker/camp come off the 200 ms position
 * tracker and exist only for rounds the tracker covered. Mixing them into
 * one ranked list — which is what a single table would do — invents a
 * comparison the data cannot support.
 *
 * So the page is ordered by evidence, not by prominence: what happened
 * (scoreboard), what the session felt like (narrative, moments), who
 * carried it (PWC, KIS), and last the telemetry-derived roles, each labelled
 * with what it is measured from.
 */

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
/** The escorts of the truck or tank, on their own (docs/design/20 §7
 *  slice 5). Measured on the corpus: the director's cut never showed one —
 *  the pools run 50–90 moments and stars are a hard tier — so the type is
 *  asked for by name and ranked among itself. The empty text names the two
 *  thresholds the detector applies, and the other reason a night has none. */
function Escorts({ gsid }: { gsid: number }) {
  const q = useStoryEscorts(gsid);
  return (
    <Stack gap={3} parity="story.escorts">
      <SectionHead label="objective escorts" aside={<span className="lbl">truck / tank · who stayed with it while it moved · placed at round end</span>} />
      {q.isPending && <Pending label="escorts" />}
      {q.isError && <Unavailable what="escorts" />}
      {q.data && q.data.moments.length === 0 && (
        <Absent reason="no round in this session had a vehicle moving ≥ 1 000 u with an escort covering ≥ 25 % of its way within 500 u — or the night has no truck/tank map" />
      )}
      {q.data && q.data.moments.length > 0 && (
        <Stack gap={1} className="rows">
          {q.data.moments.map((m, i) => (
            <Stack key={`${m.round_number}:${m.time_ms}:${i}`} gap={1} className="row" style={{ padding: 'var(--space-2) 0' }}>
              <Cluster gap={3} justify="between" align="baseline">
                <span style={{ fontSize: 'var(--fs-row)' }}>{m.player}</span>
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
      )}
    </Stack>
  );
}

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

/** The domain the SERVER draws on.
 *
 * `compute_momentum` normalises every value onto 0–100 per round, and both
 * legacy charts pin their axis to exactly that (`story.js:638`, `:741`).
 * Rescaling the observed min and max to the full drawing height instead
 * looks like a nicer chart and is a different claim: measured on the
 * recording, the values run 47.5–100, so a min/max fit draws 47.5 sitting on
 * the floor as though a team had nothing left. Codex on #842.
 */
const MOMENTUM_MIN = 0;
const MOMENTUM_MAX = 100;

/** Place a value on the fixed domain, clamped, and flipped for SVG's y-down. */
function momentumY(value: number, height: number): number {
  const t = (value - MOMENTUM_MIN) / (MOMENTUM_MAX - MOMENTUM_MIN);
  const clamped = Math.min(1, Math.max(0, t));
  return height - 2 - clamped * (height - 4);
}

/** Round-by-round strength as two sparklines, axis and allies, exactly the
 * two series the legacy chart drew.
 *
 * One drawing per round, never one across the session: each round restarts
 * the clock and the sides swap between the halves, so a single continuous
 * line would draw a continuity the numbers do not have.
 *
 * Both lines sit on the server's 0–100 domain, which gives them one shared
 * scale (two lines auto-scaled apart would cross wherever the picture felt
 * like it) AND keeps the height meaning what the endpoint says it means.
 */
function Momentum({ round }: { round: StoryMomentumRound }) {
  const pts = round.points;
  const paths = useMemo(() => {
    if (pts.length < 2) return null;
    const step = MOMENTUM_W / (pts.length - 1);
    const line = (pick: (p: { axis: number; allies: number }) => number) =>
      pts
        .map((p, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${momentumY(pick(p), MOMENTUM_H).toFixed(1)}`)
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
          viewBox={`0 0 ${MOMENTUM_W} ${MOMENTUM_H}`}
          preserveAspectRatio="none"
          style={{ maxWidth: '100%' }}
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
    const tMax = pts[pts.length - 1].t_ms || 1;
    const x = (t: number) => (t / tMax) * SESSION_W;
    // Same fixed 0–100 domain as the per-round charts: it is the scale the
    // endpoint normalises onto, and a min/max fit would make this session's
    // 47.5 look like a team with nothing left.
    const line = (pick: (p: { team_a: number; team_b: number }) => number) =>
      pts
        .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.t_ms).toFixed(1)},${momentumY(pick(p), SESSION_H).toFixed(1)}`)
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
      <Absent
        reason={data.status === 'no_team_data'
          ? `no persistent teams could be built for this session (${data.reason}) — the per-round charts above are unaffected`
          : 'this session has no momentum samples'}
      />
    );
  }

  return (
    <Stack gap={2}>
      {/* viewBox, or `maxWidth: 100%` CLIPS instead of scaling: the shell
        * leaves about 319 px of content on a 375 px viewport, and without it
        * the last two thirds of the evening simply are not drawn on a phone
        * (Codex on #842). */}
      {paths ? (
        <svg
          width={SESSION_W}
          height={SESSION_H}
          viewBox={`0 0 ${SESSION_W} ${SESSION_H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="momentum across the session"
          style={{ maxWidth: '100%' }}
        >
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
        <Absent reason="too few samples to draw" />
      )}
      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        {/* Stripped HERE, not upstream: the momentum service builds these
          * labels and rosters straight off player_comprehensive_stats and is
          * the one storytelling path that never calls strip_et_colors
          * (momentum.py _build_player_groups/_team_labels), so a ^1-coloured
          * name would render as literal control tokens (Codex on #842). */}
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-team-a)' }}>
          {stripEtColors(data.teams.team_a.label)}: {data.teams.team_a.players.map((p) => stripEtColors(p)).join(', ') || '—'}
        </span>
        <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-team-b)' }}>
          {stripEtColors(data.teams.team_b.label)}: {data.teams.team_b.players.map((p) => stripEtColors(p)).join(', ') || '—'}
        </span>
      </Cluster>
      {/* The payload names every dashed line (map_name, round_number); until
        * this legend the names were consumed only as React keys, so a reader
        * could not tie a swing to a map or half (Codex on #842). The labels
        * live OUTSIDE the SVG on purpose: preserveAspectRatio="none" squeezes
        * 620 units into ~319 px of phone shell, and <text> glyphs squeezed to
        * half width stop being glyphs — position order is the key instead,
        * because boundaries arrive sorted by x_ms. */}
      {paths && paths.marks.length > 0 && (
        <Meta>
          dashed lines, left → right: {paths.marks.map((m) => `${m.map_name} R${m.round_number}`).join(' · ')}
        </Meta>
      )}
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
      <Absent
        reason={<>no per-kill telemetry for this session ({data.reason}) — the scoreboard
        above still counts the kills, this view needs the pairing</>}
      />
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
      <Absent reason={<>the position tracker recorded no movement for this session ({data.reason})</>} />
    );
  }
  // Same rule as the kill matrix: a cutoff that is not stated makes the
  // players below it read as having no telemetry, when the endpoint measured
  // every one of them (Codex on #842). Sessions with substitutes go past ten.
  const shown = data.players.slice(0, 10);
  return (
    <Stack gap={2}>
      <Stack gap={1} className="rows">
        {shown.map((p) => (
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
      {data.players.length > shown.length && (
        <Meta>showing the top {shown.length} of {data.players.length} tracked players by total distance — the rest were measured too</Meta>
      )}
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
    : term.compression != null
      ? `×${term.compression} above it`
      : term.range != null
        // The range alone is the OUTPUT of the calculation, not the
        // calculation: spawn_timing publishes `bonus` because the multiplier
        // is 1 + bonus × denial (kis.py `_score_kill`,
        // `spawn_mult = 1.0 + SPAWN_TIMING_BONUS * best_score` over the 0–1
        // denial score the description defines) — the range
        // 1.0–2.0 only holds while bonus is 1.0, so a panel without the
        // coefficient would silently keep the old range through a bonus
        // change (Codex on #842). ⚠️ This cascade assumes ONE head shape per
        // term; spawn_timing is the first term with two published head
        // fields, hence the nested ternary — the next such term must not
        // fall silently into a single-field branch.
        ? term.bonus != null
          ? `${term.range} = 1 + ${term.bonus} × denial`
          : term.range
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
      {/* The tiers ARE the definition: the head above says "7 tiers" and the
        * description names only the endpoints (0.70 and 1.40), so the five
        * cutoffs in between were published by the server and dropped by this
        * page — a reader could not reproduce the factor (Codex on #842).
        * The open-ended last tier publishes max_reinf_seconds: null; its
        * lower bound is the previous tier's cutoff, so it is printed from
        * that rather than from a constant that would go stale with the next
        * tier table. */}
      {term.tiers != null && (
        <Stack gap={1} style={{ paddingLeft: 'var(--space-3)' }}>
          {term.tiers.map((t, i, all) => {
            const prev = i > 0 ? all[i - 1].max_reinf_seconds : null;
            const label = t.max_reinf_seconds == null
              ? (prev != null ? `> ${prev}s` : 'any wait')
              : `${t.inclusive ? '≤' : '<'} ${t.max_reinf_seconds}s`;
            return (
              <Cluster key={label} gap={2} align="baseline">
                <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 56, textAlign: 'right' }}>{label}</span>
                <span className="m" style={{ fontSize: 'var(--fs-caption)' }}>×{t.multiplier}</span>
              </Cluster>
            );
          })}
        </Stack>
      )}
      {/* The alive term carries no value of its own — its two sub-terms do,
        * and each publishes the threshold that decides which one applies
        * ("1v3+" vs the dynamic outnumbered cut). The head above prints the
        * two values; without this the thresholds never reached the page. */}
      {(term.solo_clutch != null || term.outnumbered != null) && (
        <Stack gap={1} style={{ paddingLeft: 'var(--space-3)' }}>
          {([['solo_clutch', term.solo_clutch], ['outnumbered', term.outnumbered]] as [string, FormulaTerm | undefined][])
            .filter((pair): pair is [string, FormulaTerm] => pair[1] != null)
            .map(([subName, sub]) => <Term key={subName} name={subName} term={sub} />)}
        </Stack>
      )}
    </Stack>
  );
}

function TermGroup({ label, terms }: { label: string; terms: Record<string, FormulaTerm> }) {
  // A group can declare itself NOT APPLIED (`applied: false` + `note`) —
  // the distance multipliers are published values the scorer never uses
  // (dist_mult is pinned at normal; per-kill distance is unimplemented, the
  // public half of #852). A transparency panel must not advertise factors
  // that cannot occur as if they were part of the calculation (Codex on
  // #842); the group stays visible, wearing its inactivity out loud.
  const { applied, note, ...termEntries } = terms as Record<string, FormulaTerm> & {
    applied?: boolean;
    note?: string;
  };
  const rows = Object.entries(termEntries);
  if (rows.length === 0) return null;
  const inactive = applied === false;
  return (
    <Stack gap={1}>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        {label}
        {inactive && ' — not applied'}
      </Lbl>
      {inactive && typeof note === 'string' && <Absent reason={note} />}
      <Stack gap={1} className="rows" style={inactive ? { opacity: 0.55 } : undefined}>
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
              {/* The description says which metric picks the MVP; these three
                * say who is ALLOWED to win and how equal scores resolve —
                * without them the panel cannot reproduce the badge for a
                * player near the participation floor or a tie (Codex on
                * #842). Each is present-guarded because the formula endpoints
                * omit what they do not publish. */}
              {q.data.mvp.eligibility && (
                <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                  <span className="lbl">eligible: </span>{q.data.mvp.eligibility}
                </span>
              )}
              {q.data.mvp.tiebreakers != null && q.data.mvp.tiebreakers.length > 0 && (
                <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                  {/* joined with "then": the array is ORDERED — a comma list
                    * would read as alternatives rather than a sequence. */}
                  <span className="lbl">ties broken by: </span>{q.data.mvp.tiebreakers.join(', then ')}
                </span>
              )}
              {q.data.mvp.fallback && (
                <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
                  <span className="lbl">if nobody qualifies: </span>{q.data.mvp.fallback}
                </span>
              )}
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
          {/* The soft cap is the reason a high score is not the product of
            * the terms above, so leaving it out makes the panel unable to
            * explain exactly the kills a reader would look up (Codex on
            * #842). */}
          <Stack gap={1}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>soft cap</Lbl>
            <Term name={`above ${q.data.soft_cap.threshold ?? '?'}`} term={q.data.soft_cap} />
          </Stack>
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
export function KisDetails({ gsid, guid, name }: { gsid: number; guid: string; name: string }) {
  const q = useStoryKisDetails(gsid, guid);
  // The per-kill payload carries `is_objective_area` as a FLAG and not as a
  // multiplier, and the objective boost is the last term of the published
  // formula — so a breakdown that lists only the numeric fields cannot
  // explain those kills. Measured on the recording: the six objective-area
  // kills are exactly the six whose factors did not multiply out, each short
  // by ×1.40 (Codex on #842). The value comes from the formula endpoint
  // rather than a constant here, because a constant is the thing that goes
  // stale the day the scorer changes. Cached with staleTime: Infinity, so
  // opening several rows costs one request.
  const formula = useStoryKisFormula(true);
  const objective = formula.data?.objective_multipliers.objective_area;
  const softCap = formula.data?.soft_cap;
  // Two requests, one breakdown — and the formula half must not fail
  // silently: without it the objective-area factor and the soft-cap marker
  // simply vanish, and the rows show arithmetic that cannot reach its own
  // totals with no sign anything is missing (Codex on #842). Pending waits
  // for BOTH; a formula failure is declared over the rows it degrades.
  if (q.isPending || formula.isPending) return <Pending label={`${name}'s kills`} />;
  if (q.isError) return <Unavailable what={`${name}'s kills`} />;
  const { summary, kills } = q.data;
  if (kills.length === 0) {
    return (
      /* player_name is the EMPTY STRING in this branch — the handler only
        * looks it up when there are kills — so the name comes from the row
        * that was clicked, not from the response. */
      <Absent reason={<>no scored kills for {name} in this session</>} />
    );
  }
  const top = [...kills].sort((a, b) => b.total_impact - a.total_impact).slice(0, 10);
  return (
    <Stack gap={2} style={{ paddingLeft: 'var(--space-4)' }}>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        {figure(summary.kills)} kills · {summary.total_kis.toFixed(1)} total · {summary.avg_impact.toFixed(2)} average
        {' · '}{figure(summary.carrier_kills)} carrier · {figure(summary.crossfire_kills)} crossfire
      </Lbl>
      {/* A failed request is a failure, not an absence: the rows below still
        * show the per-kill multipliers the details endpoint carries, but the
        * two annotations that come from the formula endpoint are gone, and
        * only this line says so. */}
      {formula.isError && (
        <Unavailable what="objective-area factors and soft-cap markers (the formula request failed)" />
      )}
      <Stack gap={1} className="rows">
        {top.map((k) => {
          const mults = [
            ['carrier', k.carrier_multiplier],
            // push is retired in kis-v5 (fixed at 1.0, so the ≠1 filter hides
            // it on every v5 row) — but the CACHE is not versioned, and a
            // pre-v5 row keeps the non-neutral push it was scored with.
            // Omitting the column made exactly those rows unexplainable: the
            // listed factors could not multiply out to the stored total
            // (Codex on #842). The stored value is the honest one to print.
            ['push', k.push_multiplier],
            ['crossfire', k.crossfire_multiplier],
            ['spawn', k.spawn_multiplier],
            ['outcome', k.outcome_multiplier],
            ['class', k.class_multiplier],
            ['distance', k.distance_multiplier],
            ['health', k.health_multiplier],
            ['alive', k.alive_multiplier],
            ['reinf', k.reinf_multiplier],
          ] as [string, number][];
          // Only the multipliers that MOVED the score: printing nine ×1.0s
          // per row buries the two that did the work.
          const applied: [string, number][] = mults.filter(([, v]) => v !== 1);
          // The tenth term, which the payload spells as a flag.
          if (k.is_objective_area && objective?.value != null) {
            applied.push(['objective area', objective.value]);
          }
          // `threshold` is `number | string` on FormulaTerm, because other
          // terms publish it as prose ("<30 HP"). Here it is a number, and
          // the comparison says so rather than assuming it.
          const capThreshold = typeof softCap?.threshold === 'number' ? softCap.threshold : null;
          const capped = capThreshold != null && k.total_impact > capThreshold;
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
                {/* Above the threshold the total is NOT the product — saying
                  * so is the difference between a breakdown and a riddle. */}
                {capped && <span style={{ color: 'var(--color-text-500)' }}> · soft-capped</span>}
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
      {/* A WIRE gap this page cannot close (the backend can, cheaply):
        * storytelling_kill_impact has
        * ⚠️ Corrected against the LIVE database, because the first draft of
        * this comment trusted the schema dump and was wrong: the table DOES
        * have a formula_version column, with 1,812 kis-v2 rows alongside
        * 44,152 kis-v5 — the details SELECT
        * (storytelling_router.py:358-370) simply does not return it, and
        * public requests never recompute — so a session
        * scored under an earlier formula keeps its stored totals, and the
        * two annotations read from /storytelling/formula (the objective-area
        * value, the soft-cap threshold) describe the CURRENT formula, not
        * necessarily the one that scored the row. The per-kill multipliers
        * above are the stored record and carry no such caveat (Codex on
        * #842). */}
      {formula.data && (
        <Meta>
          multipliers are the stored per-kill record; the objective-area value and
          the soft-cap threshold are read from the current formula ({formula.data.version}) —
          the response does not say which version scored each row (the stored
          rows do — the endpoint does not return that column yet)
        </Meta>
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
  // Same rule as movement and the kill matrix (Codex on #842, third time on
  // this page): the endpoint returns EVERY player who cleared both
  // thresholds, so an unstated top-five makes the sixth read as a player
  // with no costly deaths — on this metric a flattering lie.
  const shown = players.slice(0, 5);
  return (
    <Stack gap={2} style={{ minWidth: 260, flex: '1 1 260px' }}>
      <SectionHead label="costly deaths" />
      {players.length === 0 ? (
        /* NOT "not a missing measurement": the count reads the
         * storytelling_kill_impact pre-compute, and when that cache has no
         * rows for the session (the service docstring says callers must
         * trigger the KIS precompute; public reads never do) the wire sends
         * the SAME `players: []` as a genuinely clean night. The payload
         * carries no coverage field to tell the two apart — a backend
         * contract gap (Codex on #842), so the wording claims only what the
         * wire can back. */
        <Absent
          reason={<>no defender cleared both thresholds among the scored kills — though
          the endpoint cannot say whether this session's kills were scored at all</>}
        />
      ) : (
        <Stack gap={1} className="rows">
          {shown.map((p) => (
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
      {players.length > shown.length && (
        <Meta>showing the top {shown.length} of {players.length} players who cleared both thresholds</Meta>
      )}
      {/* ≥ on BOTH bounds: the backend predicate is killer_health >=
        * min_killer_health (advanced_metrics.py, `ski.killer_health >= $3`),
        * so "above 80 HP" disagreed with the count at exactly 80 (Codex on
        * #842). Same spelling as the reinforcement bound beside it. */}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        died in defence with the next spawn ≥{thresholds.min_reinf_seconds}s away
        and the killer still at ≥{thresholds.min_killer_health} HP — free
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
  const camp = useStoryCamp(gsid);
  const boards = [gravity, space, enabler, lurker, camp];

  // The five tracker boards share a fate — they read the same telemetry — so
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
        aside={<span className="lbl">five from the 200 ms position tracker · one from kill outcomes</span>}
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
        {camp.data && (
          <RoleBoard
            label="holds position"
            note="share of alive time within 96 u of one spot for 4 s or more · players alive under a minute are left out, not ranked as 0"
            rows={camp.data.players.filter((r) => r.hold_pct != null)}
            value={(r) => r.hold_pct ?? 0}
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
/** The composite five with #848's coverage block RENDERED — the first
 * consumer anywhere to do so. Legacy story.js called this endpoint and
 * drew all five columns as scores, unmeasured or not; the whole point of
 * the coverage work was that a session whose sources captured nothing must
 * say "unmeasured", not show a zero that reads as a terrible performance.
 * Measured corpus: session 154 has all five, 94 lacks tir/ci/kpi, 20 lacks
 * everything but cp. */
const COMPOSITE_KEYS = ['tir', 'ci', 'kpi', 'sds', 'cp'] as const;

function CompositeFive({ data }: { data: CompositeStats }) {
  if (isFailureStatus(data.status)) {
    return <Unavailable what="composite" />;
  }
  if (data.players.length === 0) {
    // An empty list does NOT establish a capture outage: the query drops
    // every player with zero kills in counted rounds, so a support-only
    // or abandoned session lands here with telemetry present — the
    // coverage block is the honest oracle for what was captured.
    return <Absent reason="no player qualified for the composite here (it needs kills in counted rounds) — the boards' coverage, not capture, decides this state" />;
  }
  const unmeasured = new Set(data.coverage.unmeasured_metrics);
  const partial = new Set(data.coverage.partially_synthetic_metrics);
  return (
    <Stack gap={2}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={{ ...lblStyle, fontSize: 'var(--fs-caption)', textAlign: 'left', padding: 'var(--space-1) var(--space-2)' }}>player</th>
              <th style={{ ...lblStyle, fontSize: 'var(--fs-caption)', textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>kills</th>
              {COMPOSITE_KEYS.map((k) => (
                <th key={k} title={data.meta.metrics[k]} style={{ ...lblStyle, fontSize: 'var(--fs-caption)', textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>
                  {k}{partial.has(k) ? '*' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.players.map((pl) => (
              <tr key={pl.player_guid} className="row">
                <td style={{ padding: 'var(--space-1) var(--space-2)' }}>{stripEtColors(pl.player_name)}</td>
                <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{figure(pl.kills)}</td>
                {COMPOSITE_KEYS.map((k) => (
                  <td key={k} className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)', color: unmeasured.has(k) ? 'var(--color-text-500)' : undefined }}>
                    {/* An unmeasured column shows NO number at all: its zero
                      * is an initialization, not a score, and greying a lie
                      * does not stop it being one. */}
                    {unmeasured.has(k) ? '—' : pl[k].toFixed(1)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {unmeasured.size > 0 && (
        <Meta>
          {[...unmeasured].sort().join(', ')}: unmeasured for this session — the source instruments captured no rows, so these columns have no value rather than a zero
        </Meta>
      )}
      {partial.size > 0 && (
        <Meta>
          * {[...partial].sort().join(', ')}: partially synthetic — one of its inputs is estimated, not captured
        </Meta>
      )}
    </Stack>
  );
}


export function SessionStory({ gsid }: { gsid: number }) {
  const narrative = useStoryNarrative(gsid);
  const box = useStoryBoxScore(gsid);
  const momentum = useStoryMomentum(gsid);
  const synergy = useStorySynergy(gsid);
  const kis = useStoryKillImpact(gsid);
  const composite = useComposite(gsid, null);
  const narratives = useStoryPlayerNarratives(gsid);
  // Which player's per-kill breakdown is open, if any. One at a time: the
  // detail response is per player, and two open rows would be two fetches
  // for a comparison the page does not draw.
  const [openKis, setOpenKis] = useState<string | null>(null);

  // All fourteen endpoints resolve the same scope, so they 404 together:
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

      <Escorts gsid={gsid} />

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
        {/* `no_data` / `partial_data` answer `groups: {}` (session 80) —
          * a bare read of group_a was a crash on such a night; the tab's
          * teamplay panel says why, this panel only stays honest. */}
        {synergy.data && (!synergy.data.groups.group_a || !synergy.data.groups.group_b) && (
          <Absent reason={synergy.data.status === 'partial_data' ? 'insufficient data — no R1 rows to build the groups from' : 'no synergy rows for this session'} />
        )}
        {synergy.data && synergy.data.groups.group_a && synergy.data.groups.group_b && (
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
        {synergy.data && (synergy.data.defaulted_players_count ?? 0) > 0 && (
          <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-500)' }}>
            {synergy.data.defaulted_players_count} player(s) had no telemetry and were scored at the default — the composite is that much less measured
          </span>
        )}
      </Stack>

      <Stack gap={3} parity="story.composite">
        <SectionHead label="composite five" aside={<span className="lbl">tir · ci · kpi · sds · cp — proximity instruments</span>} />
        {composite.isPending && <Pending label="composite" />}
        {composite.isError && <Unavailable what="composite" />}
        {composite.data && <CompositeFive data={composite.data} />}
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

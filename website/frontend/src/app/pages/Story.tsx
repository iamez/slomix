import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Lbl, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import {
  useStoryBoxScore, useStoryEnabler, useStoryGravity, useStoryKillImpact,
  useStoryLurker, useStoryMoments, useStoryMomentum, useStoryNarrative,
  useStoryPlayerNarratives, useStoryScopes, useStorySpace, useStorySynergy,
  useStoryWinContribution,
} from '../lib/queries';
import type {
  StoryBoxScore, StoryMomentumRound, StoryRolePlayer, StoryScope,
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

function Roles({ gsid }: { gsid: number }) {
  const gravity = useStoryGravity(gsid);
  const space = useStorySpace(gsid);
  const enabler = useStoryEnabler(gsid);
  const lurker = useStoryLurker(gsid);
  const boards = [gravity, space, enabler, lurker];

  if (boards.every((b) => b.isPending)) return <Pending label="roles" />;
  if (boards.every((b) => b.isError)) return <Unavailable what="roles" />;

  return (
    <Stack gap={3} parity="story.roles">
      <SectionHead
        label="roles"
        aside={<span className="lbl">from the 200 ms position tracker</span>}
      />
      <Cluster gap={5} align="start" style={{ flexWrap: 'wrap' }}>
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
  const box = useStoryBoxScore(gsid);
  const momentum = useStoryMomentum(gsid);
  const synergy = useStorySynergy(gsid);
  const kis = useStoryKillImpact(gsid);
  const narratives = useStoryPlayerNarratives(gsid);

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

      <WinContribution gsid={gsid} />

      <Stack gap={3} parity="story.kis">
        <SectionHead label="kill impact" aside={<span className="lbl">kis · kills · carrier · clutch</span>} />
        {kis.isPending && <Pending label="kill impact" />}
        {kis.isError && <Unavailable what="kill impact" />}
        {kis.data && (
          <Stack gap={1} className="rows">
            {kis.data.players.slice(0, 10).map((p) => (
              <Cluster key={p.guid} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
                <span style={{ fontSize: 'var(--fs-row)', minWidth: 0 }}>{p.name}</span>
                <Cluster gap={3} align="center">
                  <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{p.total_kis.toFixed(1)}</span>
                  <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 230, textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {figure(p.kills)} k · {figure(p.carrier_kills)} carrier · {figure(p.clutch_kills)} clutch
                  </span>
                </Cluster>
              </Cluster>
            ))}
          </Stack>
        )}
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

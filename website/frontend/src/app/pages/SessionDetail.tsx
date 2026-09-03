import { useMemo, useState, type ReactNode } from 'react';
import { Link, useParams, useNavigate } from 'react-router';
import { Cluster, Stack } from '../components/layout';
import { Absent, BigScore, FigureRow, Lbl, Meta, Pending, SectionHead, Tabs, Unavailable, figure } from '../components/ui';
import { DataTable, type DataColumn } from '../components/DataTable';
import { RoundsTab, roundsReason } from '../components/RoundsTab';
import { TeamplayTab } from '../components/TeamplayTab';
import { SessionStory } from './Story';
import { mapImageFor, mapLabel } from '../lib/maps';
import { SESSION_DETAIL_TABS, type SessionTab } from '../routes';
import { ApiError } from '../lib/api';
import {
  useSessionAwards, useSessionBasics, useSessionDetail, useSessionGoodNight, useSessionLeaderboard, useSessionMvp,
  useSessionPlayerWeapons, useSessionRounds,
  useSessionVerdicts, useSessions, useStoryBestLives,
} from '../lib/queries';
import type {
  SessionAwards, SessionBasics, SessionBasicsPlayer, SessionScoringMap,
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

/** The tab grammar lives in routes.ts (one copy — hashToPath validates
 *  legacy links against the same list). Labels are the keys. */
type TabKey = SessionTab;

const TABS: readonly { key: TabKey; label: string }[] = SESSION_DETAIL_TABS.map((key) => ({ key, label: key }));

function isTab(value: string | undefined): value is TabKey {
  return value != null && (SESSION_DETAIL_TABS as readonly string[]).includes(value);
}

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
        {/* `?? []` is belt and braces too: an available scoring block always
          * carries `maps` (0 of 149 sessions said otherwise). It stays
          * because the type allows the absence and the compiler would
          * otherwise demand a non-null assertion here — a worse trade. */}
        {(scoring.maps ?? []).map((m, i) => (
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
  // ⚠️ `!matrix.aggregates` is BELT AND BRACES, not load-bearing, and that
  // is worth saying because a mutation test will report it as dead: the
  // service has exactly one return with `available: true` and it always
  // carries `aggregates`, and 149 sampled sessions produced no counterexample
  // (brother's review on this PR). Kept because the two facts live in
  // different files; a reader deleting it should know it is a choice.
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
  const components = Object.entries(data.components ?? {});
  const max = Math.max(1, ...components.map(([, v]) => v));
  return (
    <Stack gap={3} parity="session.goodnight">
      <SectionHead
        label="night score"
        aside={
          <span className="lbl">
            {data.maps ?? '—'} maps · {data.players ?? '—'} players
            {data.hours == null ? '' : ` · ${data.hours.toFixed(1)} h`}
          </span>
        }
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
      {(data.reasons ?? []).length > 0 && (
        <Stack gap={1}>
          {(data.reasons ?? []).map((r) => (
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
      <SectionHead
        label="form"
        aside={<span className="lbl">against {data.baseline ?? 'their own previous sessions'}</span>}
      />
      <Stack gap={1} className="rows">
        {data.players.length === 0 && (
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          nobody in this session has a baseline to be measured against yet
        </span>
      )}
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
  // ⚠️ `?? 0`, not `=== 0`: when nobody qualified the field is ABSENT, and
  // `undefined === 0` is false — which sent this panel into the render path
  // and crashed the route on `figure(undefined)`. Found on session 151, not
  // by a test: the fixture corpus was one session and that session had the
  // field.
  const totalVotes = q.data.total_votes ?? 0;
  if (totalVotes === 0) {
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
        aside={<span className="lbl">{figure(totalVotes)} votes cast by players</span>}
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

/** Top DPM of THIS session, by id — a computation off the round totals,
 * deliberately adjacent to the ballot below so the two kinds of MVP stay
 * distinguishable: this one nobody voted for. Legacy called the same
 * endpoint without session_id and so always showed the LATEST session's
 * leader, whatever session the reader had open; passing the id is the fix,
 * not a nicety. */
function TopDpm({ sessionId }: { sessionId: number }) {
  const board = useSessionLeaderboard(sessionId, 3);
  return (
    <Stack gap={2} parity="session.top-dpm">
      <SectionHead label="top dpm" aside={<span className="lbl">computed, not voted</span>} />
      {board.isPending && <Pending label="top dpm" />}
      {board.isError && <Unavailable what="top dpm" />}
      {board.data && (board.data.length === 0 ? (
        <Absent reason="no counted rounds carry damage for this session, so there is no dpm to rank" />
      ) : (
        <Stack gap={1} className="rows">
          {board.data.map((row) => (
            <Cluster key={row.rank} gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
              <span style={{ fontSize: 'var(--fs-row)' }}>{row.name}</span>
              <Cluster gap={3} align="baseline">
                <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{figure(row.dpm)} dpm</span>
                <span className="m lbl" style={{ fontSize: 'var(--fs-caption)', width: 84, textAlign: 'right' }}>
                  {row.kills != null && row.deaths != null ? `${figure(row.kills)} / ${figure(row.deaths)}` : '—'}
                </span>
              </Cluster>
            </Cluster>
          ))}
        </Stack>
      ))}
    </Stack>
  );
}

/** Accessors, not key strings: a column that reads `player[col.key]` is an
 * object indexed by a value, which every scanner in this CI treats as an
 * injection sink — and the accessor also lets the compiler check that the
 * field exists, which a `keyof` string only pretends to do once the value
 * comes back as a union of everything. */
const PLAYERS_COLUMNS: readonly DataColumn<SessionPlayerTotals>[] = [
  { key: 'player', label: 'player', align: 'left', width: 150, title: 'name · team colour when the basics attributed teams',
    format: (p) => <Link to={`/profile/${p.player_guid.slice(0, 8)}`} style={{ color: 'inherit', textDecoration: 'none' }}>{p.player_name}</Link>,
    sortValue: (p) => p.player_name.toLowerCase() },
  { key: 'k', label: 'k', title: 'kills', width: 42, sortValue: (p) => p.kills },
  { key: 'd', label: 'd', title: 'deaths', width: 42, sortValue: (p) => p.deaths },
  { key: 'kd', label: 'k/d', title: 'kills ÷ max(1, deaths)', width: 48, sortValue: (p) => p.kd, format: (p) => p.kd.toFixed(2) },
  { key: 'dmg_g', label: 'dmg g', title: 'damage given', width: 62, sortValue: (p) => p.damage_given, format: (p) => figure(p.damage_given) },
  { key: 'dmg_r', label: 'dmg r', title: 'damage received', width: 62, sortValue: (p) => p.damage_received, format: (p) => figure(p.damage_received) },
  { key: 'dpm', label: 'dpm', title: 'damage given × 60 ÷ time played', width: 52, sortValue: (p) => p.dpm, format: (p) => p.dpm.toFixed(0) },
  { key: 'alive', label: 'alive %', title: 'Alive%: time not dead during the time the player actually played — engine figure when the stats file carried one, else 100 − dead ÷ played', width: 62,
    sortValue: (p) => p.alive_pct, format: (p) => pct(p.alive_pct) },
  { key: 'played', label: 'played %', title: 'Played%: share of the session duration the player was present', width: 66,
    sortValue: (p) => p.played_pct, format: (p) => pct(p.played_pct) },
  { key: 'dead', label: 'dead min', title: 'minutes dead, capped at minutes played per round', width: 62, sortValue: (p) => p.time_dead_minutes, format: (p) => p.time_dead_minutes.toFixed(1) },
  { key: 'denied', label: 'denied', title: 'playtime denied to opponents, m:ss (raw seconds; the 2025 backfill rows are suspect — the basics tab blanks those)', width: 58,
    sortValue: (p) => p.denied_playtime, format: (p) => clock(p.denied_playtime) },
  { key: 'eff', label: 'eff', title: 'kills ÷ (kills + deaths) × 100', width: 52, sortValue: (p) => p.efficiency, format: (p) => pct(p.efficiency) },
  { key: 'hs', label: 'hs %', title: 'head HITS ÷ hits over light weapons — never headshot kills ÷ kills', width: 56,
    sortValue: (p) => p.headshot_pct, format: (p) => pct(p.headshot_pct) },
  { key: 'acc', label: 'acc', title: 'hits ÷ shots over light weapons', width: 56, sortValue: (p) => p.accuracy, format: (p) => pct(p.accuracy) },
  { key: 'gibs', label: 'gibs', title: 'gibs', width: 44, sortValue: (p) => p.gibs },
  { key: 'uk', label: 'uk', title: 'useful kills — the victim had at least half the spawn cycle still ahead (their next wave ≥ limbo time ÷ 2; c0rnp0rn8.lua topshots[15]). The legacy tooltip said “kills on armed enemies”; the writer does not', width: 42,
    sortValue: (p) => p.useful_kills },
  { key: 'sk', label: 'sk', title: 'Self Kills: /kill command or own explosives', width: 42, sortValue: (p) => p.self_kills },
  { key: 'fsk', label: 'fsk', title: 'full self kills — /kill at health > 0 with the full respawn ahead (the Lua’s −2 s window; threshold under owner review). The legacy tooltip said “self-inflicted gibs”; the writer does not', width: 42,
    sortValue: (p) => p.full_selfkills },
  { key: 'rev', label: 'rev', title: 'revives given', width: 44, sortValue: (p) => p.revives_given },
  { key: 'revd', label: "rev'd", title: 'times revived', width: 46, sortValue: (p) => p.times_revived },
  { key: 'assists', label: 'assists', title: 'kill assists — the legacy page normalised this field and never drew it', width: 56, sortValue: (p) => p.kill_assists },
];

/** One player's weapons within THIS session — the session-scoped call
 * legacy session-detail.js made, via the hyphen spelling (see
 * useSessionPlayerWeapons). Opened one row at a time: the response is per
 * player and two open rows would be two fetches for a comparison this
 * table does not draw (same rule as the story page's KIS detail). */
function PlayerWeaponsRow({ sessionId, guid }: { sessionId: number; guid: string }) {
  const weapons = useSessionPlayerWeapons(sessionId, guid);
  const player = weapons.data?.players[0];
  return (
    <div style={{ padding: 'var(--space-2) 0 var(--space-3) var(--space-5)' }}>
      {weapons.isPending && <Pending label="weapons" />}
      {weapons.isError && <Unavailable what="weapons" />}
      {weapons.data && (!player || player.weapons.length === 0 ? (
        <Absent reason="no weapon rows recorded for this player in this session" />
      ) : (
        <Cluster gap={4} style={{ flexWrap: 'wrap' }}>
          {player.weapons.map((w) => (
            <span key={w.weapon_key} className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-text-400)' }}>
              {w.name} · {figure(w.kills)}k
              {w.shots > 0 && <> · {w.accuracy.toFixed(1)}%</>}
              {/* head HITS (SUM(headshots)), not headshot kills — the parent
                * row's hs column counts kills, and one shared abbreviation
                * would invite comparing the two (Codex on #855). */}
              {w.headshots > 0 && <> · {figure(w.headshots)} head hits</>}
            </span>
          ))}
        </Cluster>
      ))}
    </div>
  );
}

/** The Players tab — the legacy 22-column table (docs/design/18 §C plast 2)
 * on the one DataTable, every header carrying its definition. Two legacy
 * columns are not carried: "Lua Played%" printed a duplicate of Played%
 * (sessions_router.py:2298) as if it were a second measurement, and the
 * bare headshot-kills count lived under the same `hs` label as head-hit
 * percentage. Kill assists, which legacy normalised and never drew, are.
 * Team colour comes from the basics payload when it attributed teams. */
function PlayersTab({ players, sessionId, teams }: { players: SessionPlayerTotals[]; sessionId: number; teams: ReadonlyMap<string, string> }) {
  const columns = useMemo<readonly DataColumn<SessionPlayerTotals>[]>(
    () => PLAYERS_COLUMNS.map((c) => (c.key === 'player' ? { ...c, color: (p) => teams.get(p.player_guid.slice(0, 8).toUpperCase()) } : c)),
    [teams],
  );
  const drifted = players.filter((p) => p.alive_pct_drift).length;
  return (
    <Stack gap={3} parity="session.players">
      <SectionHead
        label="players"
        aside={<span className="lbl">{figure(players.length)} players · every header carries its definition</span>}
      />
      <DataTable
        columns={columns}
        rows={players}
        rowKey={(p) => p.player_guid}
        defaultSort={{ key: 'dpm', dir: 'desc' }}
        expandLabel="weapons"
        expandName={(p) => p.player_name}
        renderExpanded={(p) => <PlayerWeaponsRow sessionId={sessionId} guid={p.player_guid} />}
        minWidth={1400}
        label="players"
      />
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        totals over the session's counted rounds · sorted by dpm
      </Lbl>
      {drifted > 0 && (
        <Meta>{figure(drifted)} player(s) carry an alive % where the engine and the computed figure disagree by more than 2 pp — the engine figure is shown</Meta>
      )}
    </Stack>
  );
}

/** The best single life of the night — the most kills a player landed without
 * dying once.
 *
 * It belongs on this page because the scoreboard cannot hold it: a session
 * total flattens the six-kill run people actually remember. The legacy page
 * drew the same cards from the same endpoint (`session-detail.js:717`), but
 * treated any failure as a non-event and simply omitted the panel — which
 * makes "the request failed" and "nobody had a standout life" look identical.
 * This one says which. It sits with the scoreboard rather than with the
 * models because it is a count of kills inside one life, not a rating.
 */
function LivesOfTheNight({ sessionId }: { sessionId: number }) {
  const q = useStoryBestLives(sessionId);
  if (q.isPending) return <Pending label="lives" />;
  if (q.isError) return <Unavailable what="the best lives" />;
  if (q.data.lives.length === 0) {
    return (
      <Stack gap={3} parity="session.lives">
        <SectionHead label="lives of the night" />
        {/* NOT "not a missing measurement": a session with no player_track
          * rows (untracked or partially tracked night) returns the SAME
          * `lives: []` as a fully tracked one where nobody hit the minimum —
          * the payload carries no coverage field to tell them apart, a
          * backend contract gap (Codex on #842). So the wording claims only
          * what the wire can back. */}
        <Absent
          reason={<>no tracked life in this session cleared the minimum — though the
          endpoint cannot say how much of the night was tracked at all</>}
        />
      </Stack>
    );
  }
  const { lives, qualifying_total: qualifying, min_kills: minKills } = q.data;
  return (
    <Stack gap={3} parity="session.lives">
      <SectionHead label="lives of the night" aside={<span className="lbl">most kills on a single life</span>} />
      <Cluster gap={5} align="start" style={{ flexWrap: 'wrap' }}>
        {q.data.lives.map((l, i) => (
          <Link
            key={`${l.guid}:${l.map_name}:${l.round_number}:${l.life_seconds}:${l.kills}:${i}`}
            to={`/profile/${l.guid}`}
            style={{ textDecoration: 'none', color: 'inherit', minWidth: 150 }}
          >
            <Stack gap={1}>
              <Cluster gap={2} align="baseline">
                <span className="m" style={{ fontSize: 'var(--fs-kpi)', color: 'var(--color-accent)' }}>{l.kills}</span>
                <Lbl style={{ fontSize: 'var(--fs-caption)' }}>kills · one life</Lbl>
              </Cluster>
              <span style={{ fontSize: 'var(--fs-row)' }}>{l.name}</span>
              <span className="m lbl" style={{ fontSize: 'var(--fs-caption)' }}>
                {l.map_name} R{l.round_number} · {l.life_seconds}s alive
              </span>
            </Stack>
          </Link>
        ))}
      </Cluster>
      {/* Same rule as the story page's three cutoffs (Codex on #842, fourth
        * of the family): the endpoint counts every qualifying life and this
        * panel shows the requested top-N, so the sixth-best rampage must not
        * read as "nothing else happened". Both numbers and the threshold are
        * quoted from the payload. Guarded on presence, not truthiness:
        * responses recorded before the fields existed simply omit them, and
        * an absent key is not 0 — the line disappears on an older backend
        * rather than lying or crashing. */}
      {qualifying != null && minKills != null && qualifying > lives.length && (
        <Meta>
          showing the top {lives.length} of {figure(qualifying)} lives with ≥{minKills} kills
        </Meta>
      )}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Stats 2.0 (docs/design/18 §C): the summary a player reads first.

const TEAM_COLOR = new Map<string, string>([['a', 'var(--color-accent)'], ['b', 'var(--color-accent-warm)']]);

function pct(v: number | null): string | null {
  return v == null ? null : `${v.toFixed(1)} %`;
}

/** The basics columns — labels from the owner's list, definitions from the
 *  backend model's own docstrings (SessionBasicsPlayer), on the header's
 *  `title`. Accessors, not key strings (the PLAYER_COLUMNS rule). */
const BASICS_COLUMNS: readonly DataColumn<SessionBasicsPlayer>[] = [
  { key: 'player', label: 'player', align: 'left', width: 150, title: 'name · team colour: a accent, b warm',
    format: (p) => <Link to={`/profile/${p.guid.slice(0, 8)}`} style={{ color: 'inherit', textDecoration: 'none' }}>{p.name}</Link>,
    sortValue: (p) => p.name.toLowerCase(), color: (p) => (p.team ? TEAM_COLOR.get(p.team) : undefined) },
  { key: 'tp', label: 'tp', title: 'time played — pcs.time_played_seconds over the counted rounds', width: 58,
    sortValue: (p) => p.time_played_seconds, format: (p) => clock(p.time_played_seconds) },
  { key: 'denied', label: 'denied %', title: 'playtime denied to opponents ÷ time played × 100 — null when nothing was played or the figure is suspect (denied > 2× played, the 2025 backfill)', width: 72,
    sortValue: (p) => p.denied_pct, format: (p) => pct(p.denied_pct) },
  { key: 'dpm', label: 'dpm', title: 'damage given × 60 ÷ time played, from the sums', width: 58,
    sortValue: (p) => p.dpm, format: (p) => p.dpm.toFixed(0) },
  { key: 'kis', label: 'kis', title: 'Kill Impact Score, summed over the kills the proximity tracker scored — null when the session has no KIS rows; information beside DPM, not a ranking of who is better', width: 62,
    sortValue: (p) => p.kis_total, format: (p) => (p.kis_total == null ? null : p.kis_total.toFixed(1)) },
  { key: 'kis_min', label: 'kis/min', title: 'KIS ÷ minutes played', width: 62,
    sortValue: (p) => p.kis_per_min, format: (p) => (p.kis_per_min == null ? null : p.kis_per_min.toFixed(2)) },
  { key: 'dmg', label: 'dmg', title: 'damage given', width: 66, sortValue: (p) => p.damage_given, format: (p) => figure(p.damage_given) },
  { key: 'dmr', label: 'dmr', title: 'damage given ÷ max(1, damage received)', width: 52, sortValue: (p) => p.dmr, format: (p) => p.dmr.toFixed(2) },
  { key: 'acc', label: 'acc', title: 'hits ÷ shots over light weapons (no grenades, syringe, dynamite, airstrike, artillery, satchel, landmine) — null when nothing was fired', width: 58,
    sortValue: (p) => p.accuracy, format: (p) => pct(p.accuracy) },
  { key: 'hs', label: 'hs %', title: 'head HITS ÷ hits over the same light weapons — never headshot kills ÷ kills', width: 58,
    sortValue: (p) => p.headshot_pct, format: (p) => pct(p.headshot_pct) },
  { key: 'gibs', label: 'gibs', title: 'gibs', width: 46, sortValue: (p) => p.gibs },
  { key: 'uk', label: 'uk', title: 'useful kills — the victim had at least half the spawn cycle still ahead (their next wave ≥ limbo time ÷ 2; c0rnp0rn8.lua topshots[15]). The legacy tooltip said “kills on armed enemies”; the writer does not. useful + useless ≠ kills: the middle band is neither', width: 42, sortValue: (p) => p.useful_kills },
  { key: 'useless', label: 'useless', title: 'useless kills — kills of an enemy whose next spawn wave was under 5 s away', width: 58, sortValue: (p) => p.useless_kills },
  { key: 'sk', label: 'sk', title: 'self kills', width: 42, sortValue: (p) => p.self_kills },
  { key: 'fsk', label: 'fsk', title: 'full self kills — /kill at health > 0 with the full respawn ahead (the Lua’s −2 s window; ~7 % of self kills, threshold under owner review)', width: 42,
    sortValue: (p) => p.full_selfkills },
  { key: 'rev', label: 'rev', title: 'revives given', width: 46, sortValue: (p) => p.revives_given },
  { key: 'revd', label: "rev'd", title: 'times revived', width: 46, sortValue: (p) => p.times_revived },
];

function Basics({ basics, sessionId }: { basics: SessionBasics; sessionId: number }) {
  const c = basics.coverage;
  return (
    <Stack gap={3} parity="session.basics">
      <SectionHead
        label="the basics"
        aside={<span className="lbl">{figure(c.rounds_counted)} of {figure(c.rounds_total)} rounds count · sorted by dpm</span>}
      />
      <DataTable
        columns={BASICS_COLUMNS}
        rows={basics.players}
        rowKey={(p) => p.guid}
        defaultSort={{ key: 'dpm', dir: 'desc' }}
        expandLabel="weapons"
        expandName={(p) => p.name}
        renderExpanded={(p) => <PlayerWeaponsRow sessionId={sessionId} guid={p.guid} />}
        minWidth={1160}
        label="the basics"
      />
      {!c.kis_covered && <Absent reason="KIS is not covered for this session — the proximity tracker scored no kill here, so the two kis columns say nothing, not zero" />}
      {c.kis_covered && c.kis_kills < c.total_kills && (
        <Meta>KIS covers {figure(c.kis_kills)} of {figure(c.total_kills)} kills — the rest were not tracked</Meta>
      )}
      {c.denied_suspect_players > 0 && (
        <Absent reason={`${figure(c.denied_suspect_players)} player(s) carry a denied figure the definition cannot produce (more than twice their playtime — the 2025 backfill); their denied % is left blank`} />
      )}
      {!c.teams_attributed && <Meta>no team attribution for this evening — names are uncoloured</Meta>}
    </Stack>
  );
}

function Awards({ awards }: { awards: SessionAwards }) {
  return (
    <Stack gap={4} parity="session.awards">
      <SectionHead
        label="the awards"
        aside={<span className="lbl">{awards.rounds_with_awards} of {awards.rounds_counted} rounds carried engine awards</span>}
      />
      {awards.rounds_with_awards === 0 && (
        <Absent reason="the engine handed out no awards on this evening (they exist since June 2026) — only the three computed ones follow" />
      )}
      {awards.categories.map((cat) => (
        <Stack key={cat.key} gap={1}>
          <Lbl>{cat.label}</Lbl>
          {cat.awards.map((a) => (
            <div key={`${cat.key}:${a.engine_name}`} className="row" style={{ padding: 'var(--space-1) 0', fontSize: 'var(--fs-row)' }}>
              <span title={a.engine_name}>
                The <strong style={{ fontWeight: 600 }}>{a.nickname}</strong> award goes to{' '}
                {a.guid ? <Link to={`/profile/${a.guid.slice(0, 8)}`} style={{ color: 'var(--color-text-100)' }}>{a.player}</Link> : a.player}
                {a.sentence.slice(a.sentence.indexOf(' for '))}
              </span>
              {a.rounds_won > 1 && <> <Meta>· won in {figure(a.rounds_won)} rounds</Meta></>}
            </div>
          ))}
        </Stack>
      ))}
    </Stack>
  );
}

/** Layer 0: the maps as a strip — levelshot, the halves, the outcome. */
function MapStrip({ detail }: { detail: SessionDetailData }) {
  // A match carries only its map name and rounds; the scoring row carries a
  // match_id the match does not. Pair the n-th match on a map with the n-th
  // scoring row on that map — the same map played twice keeps its order, a
  // map the scoring never mentioned gets a dash, never a neighbour's score.
  const scoredByMap = new Map<string, SessionScoringMap[]>();
  for (const m of detail.scoring.available ? detail.scoring.maps ?? [] : []) {
    const list = scoredByMap.get(m.map);
    if (list) list.push(m); else scoredByMap.set(m.map, [m]);
  }
  return (
    <Stack gap={1} parity="session.maps" className="rows">
      {detail.matches.map((match, i) => {
        const scored = scoredByMap.get(match.map_name)?.shift();
        const rounds = match.rounds;
        return (
          <div key={`${match.map_name}:${i}`} className="row" style={{ display: 'grid', gridTemplateColumns: '64px minmax(0,1fr) auto auto', columnGap: 'var(--space-4)', alignItems: 'center', padding: 'var(--space-2) 0' }}>
            <img src={mapImageFor(match.map_name)} alt={`${mapLabel(match.map_name)} levelshot`} loading="lazy"
              style={{ width: 56, height: 32, objectFit: 'cover', display: 'block', filter: 'grayscale(1) contrast(1.1) brightness(0.6)', background: 'var(--color-ink-800)' }} />
            <span style={{ fontSize: 'var(--fs-row)', letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {mapLabel(match.map_name)}
              {scored && !scored.counted && <> <span className="lbl">not counted</span></>}
            </span>
            <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
              {rounds.map((r) => `R${r.round_number} ${clock(r.duration_seconds)}`).join(' · ')}
            </span>
            <span className="m" style={{ fontSize: 'var(--fs-value)', textAlign: 'right' }}>
              {scored ? `${scored.team_a_points} — ${scored.team_b_points}` : '—'}
            </span>
          </div>
        );
      })}
    </Stack>
  );
}

function More({ children, label = 'more' }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Stack gap={5} parity="session.more">
      <button type="button" aria-expanded={open} onClick={() => { setOpen((o) => !o); }}
        style={{ all: 'unset', cursor: 'pointer', fontSize: 'var(--fs-caption)', letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-accent)' }}>
        {open ? `${label} ▾` : `${label} ▸`}
      </button>
      {open && children}
    </Stack>
  );
}

function Summary({ detail, sessionId }: { detail: SessionDetailData; sessionId: number }) {
  const basics = useSessionBasics(sessionId);
  const awards = useSessionAwards(sessionId);
  const night = useSessionGoodNight(sessionId);
  const verdicts = useSessionVerdicts(sessionId);
  const teams = basics.data?.teams ?? [];
  const duration = detail.matches.flatMap((m) => m.rounds).reduce((acc, r) => acc + (r.duration_seconds ?? 0), 0);
  return (
    <Stack gap={7} style={{ paddingTop: 'var(--space-5)' }}>
      <div data-parity="session.head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 'var(--space-6)', flexWrap: 'wrap' }}>
        <Stack gap={2}>
          <Link to="/sessions" className="lbl" style={{ textDecoration: 'none' }}>← sessions</Link>
          <span className="m" style={{ fontSize: 'var(--fs-value)', color: 'var(--color-text-400)' }}>
            #{sessionId} · {detail.round_count} rounds · {detail.matches.length} maps · {detail.player_count} players · {clock(duration)}
          </span>
        </Stack>
        {teams.length === 2
          ? <BigScore a={{ name: teams[0].name.toLowerCase(), score: teams[0].score }} b={{ name: teams[1].name.toLowerCase(), score: teams[1].score }} note="box · sides swap every map" />
          : basics.data
            ? <Lbl>score not attributed for this session</Lbl>
            : basics.isPending ? <Pending label="score" /> : null}
      </div>

      <MapStrip detail={detail} />

      <FigureRow
        parity="session.figures"
        figures={[
          { value: figure(basics.data?.coverage.rounds_counted ?? detail.round_count), label: 'rounds counted' },
          { value: figure(detail.matches.length), label: 'maps' },
          { value: figure(detail.player_count), label: 'players' },
          { value: clock(duration), label: 'played' },
          { value: basics.data ? figure(basics.data.coverage.total_kills) : '—', label: 'kills' },
          { value: basics.data ? (basics.data.coverage.kis_covered ? figure(basics.data.coverage.kis_kills) : '—') : '—', label: 'kills with KIS' },
        ]}
      />

      {basics.isPending && <Pending label="the basics" />}
      {basics.isError && <Unavailable what="the basics" />}
      {basics.data && <Basics basics={basics.data} sessionId={sessionId} />}

      {awards.isPending && <Pending label="the awards" />}
      {awards.isError && <Unavailable what="the awards" />}
      {awards.data && <Awards awards={awards.data} />}

      {night.isPending && <Pending label="night score" />}
      {night.isError && <Unavailable what="night score" />}
      {night.data && <GoodNight data={night.data} />}
      <MvpVotes sessionId={sessionId} />

      <More label="more about the night">
        <Scoreboard scoring={detail.scoring} />
        <TeamTotals matrix={detail.team_matrix} />
        <LivesOfTheNight sessionId={sessionId} />
        {verdicts.isPending && <Pending label="form" />}
        {verdicts.isError && <Unavailable what="form" />}
        {verdicts.data && <Verdicts data={verdicts.data} />}
        <TopDpm sessionId={sessionId} />
      </More>
    </Stack>
  );
}

export function SessionDetail() {
  const { sessionId: idParam, sessionDate, tab } = useParams();
  const navigate = useNavigate();
  // Only fetched when a DATE has to be resolved to a session. An id in the
  // URL needs no list, and loading thirty sessions to ignore them is the
  // same waste the story page's SSR panel was called out for.
  const sessions = useSessions(30, sessionDate != null);

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

  const current: TabKey = isTab(tab) ? tab : 'summary';
  const detail = useSessionDetail(sessionId);
  const rounds = useSessionRounds(sessionId);
  // Shared with the Summary's own call (same key, one fetch): the basics
  // payload is where team attribution lives, and the players tab colours
  // names by it when it is there.
  const basics = useSessionBasics(sessionId);
  const teams = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of basics.data?.players ?? []) {
      const colour = p.team ? TEAM_COLOR.get(p.team) : undefined;
      if (colour) m.set(p.guid.slice(0, 8).toUpperCase(), colour);
    }
    return m;
  }, [basics.data]);

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
          {/* A 404 here is a different fact from a failure, and session 145
            * is the proof: six rounds, every one of them orphan_r2, so the
            * detail endpoint answers "Session not found" while the rounds
            * tab lists all six. "unavailable" would send the reader looking
            * for a bug that is not there. */}
          {detail.isError && (
            <div style={{ paddingTop: 'var(--space-4)' }}>
              {detail.error instanceof ApiError && detail.error.status === 404 ? (
                <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
                  no counted rounds in this session — its totals do not exist,
                  which is why the rounds tab can still show what was played
                </span>
              ) : (
                <Unavailable what="session" />
              )}
            </div>
          )}

          {detail.data && current === 'summary' && (
            <Summary detail={detail.data} sessionId={sessionId} />
          )}
          {detail.data && current === 'players' && (
            <div style={{ paddingTop: 'var(--space-5)' }}>
              <PlayersTab players={detail.data.players} sessionId={sessionId} teams={teams} />
            </div>
          )}
          {/* The rounds tab does not wait for /detail: a session whose
            * totals do not exist (every round orphan_r2) still played rounds. */}
          {current === 'rounds' && (
            <div style={{ paddingTop: 'var(--space-5)' }}>
              <RoundsTab rounds={rounds.isError ? undefined : rounds.data} reason={roundsReason(rounds)} />
            </div>
          )}
          {detail.data && current === 'teamplay' && (
            <div style={{ paddingTop: 'var(--space-5)' }}>
              <TeamplayTab gsid={sessionId} sessionDate={detail.data.date} />
            </div>
          )}
          {current === 'story' && (
            <div data-parity="session.story">
              <SessionStory key={sessionId} gsid={sessionId} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

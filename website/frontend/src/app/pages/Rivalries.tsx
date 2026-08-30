import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { Cluster, Stack } from '../components/layout';
import { Lbl, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { apiGet } from '../lib/api';
import { useHeadToHead, usePlayerRivalries, useRivalryLeaderboard } from '../lib/queries';
import type { HeadToHeadWeapon, RivalryOpponent, RivalryPair } from '../lib/types';

/** Shape of one /auth/players/search hit — the 8-character guid and a name. */
interface SearchHit { guid: string; name: string }

/**
 * Rivalries (docs/design/12 row 25) — the first page written out of the
 * component library rather than retrofitted into it.
 *
 * The page's one job is to make a classification legible. NEMESIS, PREY and
 * RIVAL are not adjectives someone picked; they are thresholds on one number
 * (`rivalries_service._classify`), and a page that prints the label without
 * the rule leaves the reader guessing why their 58% opponent is a "rival"
 * and their 61% one is not. So the rule is on the page, next to the labels.
 */

/** Maps, not objects: a lookup by a value that arrives from the API is an
 * injection sink to every scanner, and the classification names do arrive
 * from the API (Codacy on #834 — the same shape the layout primitives
 * settled on for the same reason). */
const CLASS_RULE = new Map<string, string>([
  ['PREY', 'you win 70%+'],
  ['NEMESIS', 'they win 70%+'],
  ['RIVAL', 'within 40-60%'],
  ['CONTENDER', 'between those'],
  ['INSUFFICIENT_DATA', 'fewer than 5 meetings'],
]);

const CLASS_COLOUR = new Map<string, string>([
  ['PREY', 'var(--color-pos)'],
  ['NEMESIS', 'var(--color-neg)'],
  ['RIVAL', 'var(--color-accent)'],
  ['CONTENDER', 'var(--color-text-400)'],
  ['INSUFFICIENT_DATA', 'var(--color-text-500)'],
]);

function Badge({ classification }: { classification: string }) {
  return (
    <span
      className="m"
      style={{
        fontSize: 'var(--fs-caption)',
        letterSpacing: 'var(--track-chip)',
        color: CLASS_COLOUR.get(classification) ?? 'var(--color-text-400)',
      }}
    >
      {classification.replace('_', ' ').toLowerCase()}
    </span>
  );
}

/** A bar split at the win rate: the picture and the number say one thing. */
function SplitBar({ share }: { share: number }) {
  const pct = Math.max(0, Math.min(100, share * 100));
  return (
    <span style={{ display: 'block', width: 120, height: 4, background: 'var(--color-rule-900)' }}>
      <span style={{ display: 'block', width: `${pct}%`, height: '100%', background: 'var(--color-accent)' }} />
    </span>
  );
}

function PairRow({ pair, onOpen }: { pair: RivalryPair; onOpen: (a: string, b: string) => void }) {
  return (
    <Cluster
      gap={3}
      justify="between"
      align="center"
      className="row"
      style={{ padding: 'var(--space-2) 0' }}
    >
      <Cluster gap={2} align="baseline" style={{ minWidth: 0, flex: 1 }}>
        <Link to={`/profile/${pair.guid1.slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)' }}>
          {pair.name1}
        </Link>
        <span className="lbl">vs</span>
        <Link to={`/profile/${pair.guid2.slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)' }}>
          {pair.name2}
        </Link>
      </Cluster>
      <Cluster gap={3} align="center">
        {/* The names go to profiles, the SCORE opens the duel — the row has
          * two destinations and one of them was unreachable before. */}
        <button
          type="button"
          onClick={() => { onOpen(pair.guid1, pair.guid2); }}
          title={`${pair.name1} against ${pair.name2}, kill by kill`}
          className="m"
          style={{
            background: 'transparent', border: 0, padding: 0, cursor: 'pointer',
            color: 'var(--color-text-100)', fontSize: 'var(--fs-value)', fontFamily: 'var(--font-mono)',
          }}
        >
          {figure(pair.kills_1to2)} — {figure(pair.kills_2to1)}
        </button>
        <SplitBar share={pair.win_rate} />
        <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 56, textAlign: 'right' }}>
          {figure(pair.total)}
        </span>
        <span style={{ width: 96, textAlign: 'right' }}><Badge classification={pair.classification} /></span>
      </Cluster>
    </Cluster>
  );
}

function OpponentRow({ row, ambiguous, onOpen }: {
  row: RivalryOpponent; ambiguous: boolean; onOpen?: () => void;
}) {
  const short = (row.opponent_guid || row.guid || '').slice(0, 8);
  return (
    <Cluster gap={3} justify="between" align="center" className="row" style={{ padding: 'var(--space-2) 0' }}>
      <Cluster gap={2} align="baseline" style={{ minWidth: 0 }}>
        <Link
          to={`/profile/${short}`}
          style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-row)' }}
        >
          {row.opponent_name || row.name}
        </Link>
        {/* Two GUIDs can carry one display name — measured here: `ownator`
          * appears twice in vid's list, once as FB0EC840 and once as
          * EF561EAA, which is the sick-leave alt from migration 073. Two
          * identical rows with different numbers is a page contradicting
          * itself, so the id joins the name exactly when it has to. */}
        {ambiguous && <span className="m lbl" style={{ fontSize: 'var(--fs-caption)' }}>{short}</span>}
      </Cluster>
      <Cluster gap={3} align="center">
        {/* Same two destinations as the pair rows: the name is a profile,
          * the score is the duel. */}
        {onOpen ? (
          <button
            type="button"
            onClick={onOpen}
            title={`the duel with ${row.opponent_name || row.name}`}
            className="m"
            style={{
              background: 'transparent', border: 0, padding: 0, cursor: 'pointer',
              color: 'var(--color-text-100)', fontSize: 'var(--fs-value)', fontFamily: 'var(--font-mono)',
            }}
          >
            {figure(row.kills_by_player)} — {figure(row.kills_on_player)}
          </button>
        ) : (
          <span className="m" style={{ fontSize: 'var(--fs-value)' }}>
            {figure(row.kills_by_player)} — {figure(row.kills_on_player)}
          </span>
        )}
        <SplitBar share={row.win_rate} />
        <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', width: 56, textAlign: 'right' }}>
          {figure(row.total_encounters)}
        </span>
        <span style={{ width: 96, textAlign: 'right' }}><Badge classification={row.classification} /></span>
      </Cluster>
    </Cluster>
  );
}

/** One of the three named roles, or the reason there is nobody in it. */
function Role({ label, who, absent }: { label: string; who: RivalryOpponent | null; absent: string }) {
  return (
    <Stack gap={1}>
      <Lbl>{label}</Lbl>
      {who ? (
        <>
          <Link to={`/profile/${(who.opponent_guid || who.guid || '').slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-lead)' }}>
            {who.opponent_name || who.name}
          </Link>
          <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>
            {figure(who.kills_by_player)} — {figure(who.kills_on_player)} · {(who.win_rate * 100).toFixed(0)}%
          </span>
        </>
      ) : (
        // Nobody in this role is a RESULT, not a gap: it means no opponent
        // crossed the threshold. Saying "—" would read as missing data.
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          {absent}
        </span>
      )}
    </Stack>
  );
}

function PlayerPanel({ guid, onOpenDuel }: { guid: string; onOpenDuel: (opponent: string) => void }) {
  const q = usePlayerRivalries(guid);

  // Past these two guards react-query's own union says `data` is defined, so
  // a third `!q.data` check reads as caution while being dead code — and the
  // scanner is right to say so (Codacy on #834).
  if (q.isPending) return <div style={{ paddingTop: 'var(--space-3)' }}><Pending label="opponents" /></div>;
  if (q.isError) return <div style={{ paddingTop: 'var(--space-3)' }}><Unavailable what="opponents" /></div>;

  const d = q.data;
  const nameCounts = new Map<string, number>();
  for (const row of d.all_pairs) {
    const name = row.opponent_name || row.name;
    nameCounts.set(name, (nameCounts.get(name) ?? 0) + 1);
  }

  // `resolved: false` is the one case the old endpoint could not express: it
  // answered with an empty list, which reads as "no rivals" about someone who
  // may simply never have been tracked.
  if (d.resolved === false) {
    return (
      <Stack gap={2} parity="rivalries.player" style={{ paddingTop: 'var(--space-4)' }}>
        <SectionHead label={`opponents · ${guid}`} />
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          no proximity rows are recorded under this id — this is not "no rivals",
          it is "never tracked"
        </span>
      </Stack>
    );
  }

  return (
    <Stack gap={4} parity="rivalries.player" style={{ paddingTop: 'var(--space-4)' }}>
      <SectionHead
        label={`opponents · ${d.player_name ?? guid}`}
        aside={<span className="lbl">{figure(d.total_opponents)} opponents</span>}
      />
      <Cluster gap={7}>
        <Role label="nemesis" who={d.nemesis} absent="nobody wins 70% against them" />
        <Role label="prey" who={d.prey} absent="nobody they beat that often" />
        <Role label="rival" who={d.rival} absent="no matchup that even" />
      </Cluster>
      {d.all_pairs.length > 0 ? (
        <Stack gap={1} className="rows">
          {d.all_pairs.map((row) => (
            <OpponentRow
              key={row.opponent_guid || row.guid}
              row={row}
              ambiguous={(nameCounts.get(row.opponent_name || row.name) ?? 0) > 1}
              onOpen={() => { onOpenDuel(row.opponent_guid || row.guid || ''); }}
            />
          ))}
        </Stack>
      ) : (
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          tracked, but no opponent met often enough to count yet
        </span>
      )}
    </Stack>
  );
}

/** The way in. Without it the `?guid=` view is reachable only by typing a
 * URL, which is a feature nobody finds (Codex on #834). Same search endpoint
 * and same 300 ms debounce as Home — /auth/players/search is rate-limited to
 * 30/min, and a request per keystroke spends that on one typed name. */
function PickPlayer({ onPick }: { onPick: (guid: string) => void }) {
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => { setDebounced(query.trim()); }, 300);
    return () => { clearTimeout(timer); };
  }, [query]);
  const search = useQuery({
    queryKey: ['player-search', debounced],
    enabled: debounced.length >= 2,
    queryFn: () => apiGet('/auth/players/search', { query: { q: debounced } }) as Promise<SearchHit[]>,
  });
  return (
    <Stack gap={2} parity="rivalries.pick" style={{ maxWidth: 380 }}>
      <Lbl>whose opponents</Lbl>
      <input
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); }}
        placeholder="player name or alias"
        aria-label="Whose opponents"
        className="m"
        style={{
          width: '100%', background: 'var(--color-ink-800)',
          border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
          fontSize: 'var(--fs-value)', padding: 'var(--space-2) var(--space-3)', boxSizing: 'border-box',
        }}
      />
      {debounced.length >= 2 && (
        <Stack gap={1} className="rows">
          {search.isPending && <Pending label="search" />}
          {search.isError && <Unavailable what="search" />}
          {search.data?.length === 0 && (
            <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
              no player matches "{debounced}"
            </span>
          )}
          {search.data?.slice(0, 6).map((hit) => (
            <button
              key={hit.guid}
              type="button"
              className="row"
              onClick={() => { onPick(hit.guid); }}
              style={{
                background: 'transparent', border: 0, textAlign: 'left', cursor: 'pointer',
                color: 'var(--color-text-100)', padding: 'var(--space-2) 0',
                fontSize: 'var(--fs-value)', fontFamily: 'var(--font-mono)',
              }}
            >
              {hit.name}
            </button>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

/** A row of weapons one player used on the other, longest bar first.
 *
 * Two `kill_mod` values can carry one display name — measured in the
 * recording: mod 16 and mod 18 are both "Grenade" (hand and rifle), and
 * they appear as two rows with different counts on BOTH sides. Two
 * identical labels with different numbers is a panel contradicting itself,
 * so the mod joins the name exactly when it has to — the same rule the
 * opponent rows already use for two GUIDs sharing a name. */
function WeaponBars({ rows, colour }: { rows: HeadToHeadWeapon[]; colour: string }) {
  const top = rows.slice(0, 5);
  const most = Math.max(1, ...top.map((w) => w.kills));
  const nameCounts = new Map<string, number>();
  for (const w of rows) nameCounts.set(w.weapon, (nameCounts.get(w.weapon) ?? 0) + 1);
  return (
    <Stack gap={1} style={{ minWidth: 200, flex: '1 1 200px' }}>
      {top.length === 0 ? (
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          never landed one
        </span>
      ) : top.map((w) => (
        <Cluster key={w.kill_mod} gap={2} align="center">
          <span className="m" style={{ fontSize: 'var(--fs-caption)', width: 92, textAlign: 'right', color: 'var(--color-text-400)' }}>
            {w.weapon}{(nameCounts.get(w.weapon) ?? 0) > 1 && ` #${w.kill_mod}`}
          </span>
          <span style={{ height: 6, width: `${(w.kills / most) * 100}%`, background: colour, minWidth: 2 }} />
          <span className="m" style={{ fontSize: 'var(--fs-caption)' }}>{w.kills}</span>
        </Cluster>
      ))}
    </Stack>
  );
}

/** Two named players, every duel between them.
 *
 * The pair rows above already say who leads; this says HOW — which weapons
 * each one landed it with, and on which maps. The endpoint answers 200 for
 * an id it cannot resolve rather than 404, and names which side failed, so
 * the panel can tell "these two never met" apart from "one of these was
 * never tracked" — which the leaderboard alone cannot.
 */
function HeadToHeadPanel({ guid1, guid2, onClose }: { guid1: string; guid2: string; onClose: () => void }) {
  const q = useHeadToHead(guid1, guid2);
  if (q.isPending) return <div style={{ paddingTop: 'var(--space-4)' }}><Pending label="the duel" /></div>;
  if (q.isError) return <div style={{ paddingTop: 'var(--space-4)' }}><Unavailable what="the duel" /></div>;
  const d = q.data;

  if (!d.resolved) {
    return (
      <Stack gap={2} parity="rivalries.h2h" style={{ paddingTop: 'var(--space-4)' }}>
        <SectionHead label="head to head" />
        <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
          no proximity rows are recorded under {d.unresolved.join(' or ')} — this is
          not "they never met", it is "never tracked"
        </span>
        <button type="button" className="act" style={{ background: 'transparent', border: 0, cursor: 'pointer' }} onClick={onClose}>
          ← back
        </button>
      </Stack>
    );
  }

  return (
    <Stack gap={4} parity="rivalries.h2h" style={{ paddingTop: 'var(--space-4)' }}>
      <SectionHead
        label="head to head"
        aside={<Badge classification={d.classification} />}
      />
      <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
        <Cluster gap={2} align="baseline">
          <Link to={`/profile/${d.guid1.slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-lead)' }}>
            {d.p1_name}
          </Link>
          <span className="m" style={{ fontSize: 'var(--fs-kpi)', color: 'var(--color-team-a)' }}>{figure(d.p1_kills)}</span>
          <span className="lbl">—</span>
          <span className="m" style={{ fontSize: 'var(--fs-kpi)', color: 'var(--color-team-b)' }}>{figure(d.p2_kills)}</span>
          <Link to={`/profile/${d.guid2.slice(0, 8)}`} style={{ color: 'var(--color-text-100)', textDecoration: 'none', fontSize: 'var(--fs-lead)' }}>
            {d.p2_name}
          </Link>
        </Cluster>
        <SplitBar share={d.win_rate} />
        <span className="m lbl" style={{ fontSize: 'var(--fs-caption)' }}>{figure(d.total)} meetings</span>
      </Cluster>

      <Stack gap={2}>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>what each one landed it with</Lbl>
        <Cluster gap={6} align="start" style={{ flexWrap: 'wrap' }}>
          <WeaponBars rows={d.p1_weapons} colour="var(--color-team-a)" />
          <WeaponBars rows={d.p2_weapons} colour="var(--color-team-b)" />
        </Cluster>
      </Stack>

      {d.per_map.length > 0 && (
        <Stack gap={2}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>where</Lbl>
          <Stack gap={1} className="rows">
            {d.per_map.map((m) => (
              <Cluster key={m.map} gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
                <span style={{ fontSize: 'var(--fs-small)' }}>{m.map}</span>
                <Cluster gap={3} align="center">
                  <span className="m" style={{ fontSize: 'var(--fs-small)' }}>
                    {figure(m.p1_kills)} — {figure(m.p2_kills)}
                  </span>
                  {/* Share of THIS map's meetings, so a 1–0 map cannot look
                    * like a rout next to a 40–38 one. */}
                  <SplitBar share={m.total > 0 ? m.p1_kills / m.total : 0} />
                </Cluster>
              </Cluster>
            ))}
          </Stack>
        </Stack>
      )}

      <button type="button" className="act" style={{ background: 'transparent', border: 0, cursor: 'pointer' }} onClick={onClose}>
        ← back
      </button>
    </Stack>
  );
}

export function Rivalries() {
  const [params, setParams] = useSearchParams();
  const guid = params.get('guid');
  // Both ids in the URL, so a duel is a link somebody can send.
  const vs = params.get('vs');
  const board = useRivalryLeaderboard(40);
  const openDuel = (a: string, b: string) => { setParams({ guid: a, vs: b }); };

  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-8)' }}>
      <Lbl>rivalries · who keeps meeting whom</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: 'var(--track-title)', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        The same two names, again.
      </h1>

      <Cluster gap={4} style={{ marginTop: 'var(--space-3)' }}>
        {[...CLASS_RULE].map(([name, rule]) => (
          <Cluster key={name} gap={1} align="baseline">
            <Badge classification={name} />
            <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{rule}</span>
          </Cluster>
        ))}
      </Cluster>

      {!guid && (
        <div style={{ paddingTop: 'var(--space-5)' }}>
          <PickPlayer onPick={(picked) => { setParams({ guid: picked }); }} />
        </div>
      )}

      {guid && vs && (
        <HeadToHeadPanel guid1={guid} guid2={vs} onClose={() => { setParams({ guid }); }} />
      )}

      {guid && !vs && (
        <>
          <PlayerPanel guid={guid} onOpenDuel={(opponent) => { openDuel(guid, opponent); }} />
          <button
            type="button"
            className="act"
            style={{ background: 'transparent', border: 0, cursor: 'pointer', marginTop: 'var(--space-3)' }}
            onClick={() => { setParams({}); }}
          >
            ← everyone
          </button>
        </>
      )}

      <Stack gap={2} parity="rivalries.leaderboard" style={{ paddingTop: 'var(--space-6)' }}>
        <SectionHead
          label="most-met pairs"
          aside={<span className="lbl">kills each way · balance · meetings</span>}
        />
        {board.isPending && <Pending label="pairs" />}
        {board.isError && <Unavailable what="pairs" />}
        {board.data && board.data.pairs.length === 0 && (
          <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
            no pair has met five times yet
          </span>
        )}
        {board.data && board.data.pairs.length > 0 && (
          <Stack gap={1} className="rows">
            {board.data.pairs.map((pair) => (
              <PairRow key={`${pair.guid1}:${pair.guid2}`} pair={pair} onOpen={openDuel} />
            ))}
          </Stack>
        )}
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
          from proximity kill records · bots excluded · a pair needs five meetings to be classified
        </Lbl>
      </Stack>
    </div>
  );
}

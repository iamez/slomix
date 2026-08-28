import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import {
  useHallOfFame, useMaps, useRecords, useSeasonAwards, useSeasonCurrent,
  useSeasonLeaders,
} from '../lib/queries';
import type { HallOfFameEntry, RecordEntry } from '../lib/types';
import { Chip, figure, Lbl, lblStyle, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

/**
 * Record Book (docs/design/12 — absorbs the legacy records + hall-of-fame
 * views plus a Season tab; the hash shim already maps #/records and
 * #/hall-of-fame onto ?tab=). Tab state lives in the URL, so those aliases
 * land correctly and reloads keep the tab.
 *
 * Carried from legacy: the record-category order (FE-owned, not the
 * API's), the twelve HoF categories with podium-then-list, the season
 * champions band that hides when awards are [] (the NORMAL state until a
 * season is engraved — corpus proves it). Not carried: the legacy revived
 * category omission is kept deliberate (backend sends it, legacy never
 * rendered it — parity first; adopting it would be an O-decision).
 */

const TABS = [
  { key: 'records', label: 'All-time records' },
  { key: 'hof', label: 'Hall of fame' },
  { key: 'season', label: 'Season' },
] as const;

/** Legacy records.js order — the FE owns the sequence. */
const RECORD_ORDER: { key: string; label: string }[] = [
  { key: 'kills', label: 'kills' },
  { key: 'damage', label: 'damage' },
  { key: 'xp', label: 'xp' },
  { key: 'headshots', label: 'headshots' },
  { key: 'accuracy', label: 'accuracy' },
  { key: 'revives', label: 'revives' },
  { key: 'gibs', label: 'gibs' },
  { key: 'dyna_planted', label: 'dynamite planted' },
  { key: 'dyna_defused', label: 'dynamite defused' },
  { key: 'obj_stolen', label: 'objectives stolen' },
  { key: 'obj_returned', label: 'objectives returned' },
  { key: 'useful_kills', label: 'useful kills' },
];
const MATCH_RECORD_ORDER: { key: string; label: string }[] = [
  { key: 'match_damage', label: 'damage' },
  { key: 'match_kills', label: 'kills' },
  { key: 'match_headshots', label: 'headshots' },
  { key: 'match_xp', label: 'xp' },
  { key: 'match_revives', label: 'revives' },
  { key: 'match_gibs', label: 'gibs' },
];

/** Legacy hall-of-fame.js CATEGORIES, order and tooltips carried over. */
const HOF_CATEGORIES: { key: string; label: string; desc: string }[] = [
  { key: 'most_active', label: 'Most active', desc: 'Rounds played (R1+R2 halves each count once).' },
  { key: 'most_wins', label: 'Most wins', desc: 'Rounds finished on the winning side.' },
  { key: 'most_damage', label: 'Most damage', desc: 'Total damage dealt to enemies.' },
  { key: 'most_kills', label: 'Most kills', desc: 'Total enemy kills.' },
  { key: 'most_revives', label: 'Most revives', desc: 'Teammates revived with the medic syringe.' },
  { key: 'most_xp', label: 'Most XP', desc: 'Total experience points earned.' },
  { key: 'most_assists', label: 'Most assists', desc: 'Kill assists — damaged an enemy a teammate finished.' },
  { key: 'most_dpm', label: 'Most DPM', desc: 'Damage per minute actually played (min 10 rounds).' },
  { key: 'most_deaths', label: 'Most deaths', desc: 'Total deaths. Not always a bad sign.' },
  { key: 'most_selfkills', label: 'Most selfkills', desc: 'Deaths by own hand (/kill).' },
  { key: 'most_full_selfkills', label: 'Most full selfkills', desc: 'Self-kills with no enemy contact shortly before.' },
  { key: 'most_consecutive_games', label: 'Longest streak', desc: 'Longest streak of gaming sessions attended in a row.' },
];

const HOF_PERIODS = [
  { key: 'all_time', label: 'All time' },
  { key: 'season', label: 'Season' },
  { key: '7d', label: '7d' },
  { key: '14d', label: '14d' },
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
];

/** Legacy formatRecordValue: non-integers to two decimals. */
function recordValue(v: number): string {
  return Number.isInteger(v) ? Math.round(v).toLocaleString('en-US') : v.toFixed(2);
}


function RecordCard({ label, rows }: { label: string; rows: RecordEntry[] }) {
  const [open, setOpen] = useState(false);
  const top = rows[0];
  if (!top) return null;
  return (
    <div style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{ all: 'unset', cursor: 'pointer', display: 'block', width: '100%' }}
        aria-expanded={open}
      >
        <Lbl style={{ fontSize: 9 }}>{label}</Lbl>
        <div className="m" style={{ fontSize: 26, lineHeight: 1, marginTop: 8 }}>{recordValue(top.value)}</div>
        <div className="m" style={{ fontSize: 12, marginTop: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{top.player}</div>
        <div className="m" style={{ ...lblStyle, fontSize: 9, marginTop: 4 }}>{top.map} · {top.date}</div>
      </button>
      {open && rows.length > 1 && (
        <div style={{ marginTop: 10, borderTop: '1px solid var(--color-rule-900)' }}>
          {rows.slice(1).map((r, i) => (
            /* Each rank can come from a DIFFERENT map and date — the legacy
             * top-5 modal showed both, and dropping them made ranks 2-5
             * unverifiable (Codex on #813, wave 4). */
            <div key={`${r.player}-${i}`} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '20px minmax(0,1fr) auto', gap: 8, alignItems: 'baseline', padding: '5px 0' }}>
              <span className="m" style={{ ...lblStyle, fontSize: 9 }}>{String(i + 2).padStart(2, '0')}</span>
              <span style={{ minWidth: 0 }}>
                <span className="m" style={{ fontSize: 11, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.player}</span>
                <span className="m" style={{ ...lblStyle, fontSize: 8 }}>{r.map} · {r.date}</span>
              </span>
              <span className="m" style={{ fontSize: 11, color: 'var(--color-text-400)' }}>{recordValue(r.value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function RecordsTab() {
  const [mapName, setMapName] = useState<string | null>(null);
  const records = useRecords(mapName);
  const maps = useMaps();
  const data = records.isError ? undefined : records.data;
  const section = (title: string, order: { key: string; label: string }[]) => (
    <div style={{ marginTop: 18 }}>
      <SectionHead label={title} />
      <div className="about-grid-5" style={{ gap: 10, marginTop: 10 }}>
        {order.map((cat) => (
          data?.[cat.key]?.length
            ? <RecordCard key={cat.key} label={cat.label} rows={data[cat.key]} />
            : null
        ))}
      </div>
    </div>
  );
  return (
    <div data-parity="record-book.records">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, flexWrap: 'wrap' }}>
        <Lbl style={{ fontSize: 9 }}>map</Lbl>
        <select
          value={mapName ?? ''}
          onChange={(e) => setMapName(e.target.value || null)}
          aria-label="Map filter"
          className="m"
          style={{ background: 'var(--color-ink-800)', color: 'var(--color-text-100)', border: '1px solid var(--color-rule-700)', fontSize: 13, padding: '6px 10px' }}
        >
          <option value="">all maps</option>
          {(maps.data ?? []).map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}
        </select>
        {maps.isError && <Unavailable what="map list" />}
      </div>
      {records.isPending && <div style={{ marginTop: 16 }}><Pending label="records" /></div>}
      {records.isError && <div style={{ marginTop: 16 }}><Unavailable what="records" /></div>}
      {/* An empty OBJECT is truthy — two headings over empty grids would
        * claim records that do not exist (Codex on #813). */}
      {data && Object.values(data).every((rows) => !rows?.length) && (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 16 }}>
          no records for this selection yet
        </div>
      )}
      {data && Object.values(data).some((rows) => rows?.length) && (
        <>
          {section('single round · click a card for the top 5', RECORD_ORDER)}
          {section('full map · both rounds combined', MATCH_RECORD_ORDER)}
        </>
      )}
    </div>
  );
}

/** ↗/↘/NEW movement, present only when the period carries a delta window —
 * the legacy HoF showed these and the recording's all_time null hides them
 * (Codex on #813). */
function MoveBadge({ e }: { e: HallOfFameEntry }) {
  if (e.is_new) return <span className="m" style={{ fontSize: 9, color: 'var(--color-accent-warm)' }}>NEW</span>;
  if (e.rank_delta != null && e.rank_delta !== 0) {
    const up = e.rank_delta > 0;
    return (
      <span className="m" style={{ fontSize: 9, color: up ? 'var(--color-pos)' : 'var(--color-neg)' }}>
        {up ? '↗' : '↘'}{Math.abs(e.rank_delta)}
      </span>
    );
  }
  return null;
}

function HofList({ catKey, label, desc, entries }: { catKey: string; label: string; desc: string; entries: HallOfFameEntry[] }) {
  const [expanded, setExpanded] = useState(false);
  const podium = entries.slice(0, 3);
  const rest = entries.slice(3);
  const visible = expanded ? rest : rest.slice(0, 7);
  // DPM keeps the backend's two-decimal ranking precision — 374.01 and
  // 374.0 are different ranks (Codex on #813, wave 4).
  const fmt = (v: number) => (catKey === 'most_dpm' ? v.toFixed(2) : figure(v));
  return (
    <div style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
      <Lbl style={{ fontSize: 9 }} >{label}</Lbl>
      <div style={{ fontSize: 12, color: 'var(--color-text-500)', marginTop: 3 }}>{desc}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 12 }}>
        {podium.map((e) => {
          const inner = (<>
            <div className="m" style={{ ...lblStyle, fontSize: 9 }}>#{e.rank} <MoveBadge e={e} /></div>
            <div className="m" style={{ fontSize: 12, marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.player_name}</div>
            <div className="m" style={{ fontSize: 13, marginTop: 2 }}>
              {fmt(e.value)}{' '}
              <span style={{ ...lblStyle, fontSize: 8 }}>{e.unit}</span>
            </div>
          </>);
          // A null guid is a resolvable-by-nobody historical aggregate —
          // a cell, not a /profile/null link (same rule as awards).
          return e.player_guid
            ? <Link key={e.player_guid} to={`/profile/${e.player_guid}`} style={{ textDecoration: 'none', color: 'var(--color-text-100)' }}>{inner}</Link>
            : <div key={`${e.rank}-${e.player_name}`}>{inner}</div>;
        })}
      </div>
      {rest.length > 0 && (
        <div style={{ marginTop: 10, borderTop: '1px solid var(--color-rule-900)' }}>
          {visible.map((e) => {
            const inner = (<>
              <span className="m" style={{ ...lblStyle, fontSize: 9 }}>{String(e.rank).padStart(2, '0')}</span>
              <span className="m" style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.player_name} <MoveBadge e={e} /></span>
              <span className="m" style={{ fontSize: 11 }}>{fmt(e.value)}</span>
            </>);
            const style = { ...rowStyle, display: 'grid', gridTemplateColumns: '24px minmax(0,1fr) auto', gap: 8, alignItems: 'baseline', padding: '4px 0', textDecoration: 'none', color: 'var(--color-text-300)' } as const;
            return e.player_guid
              ? <Link key={e.player_guid} to={`/profile/${e.player_guid}`} style={style}>{inner}</Link>
              : <div key={`${e.rank}-${e.player_name}`} style={style}>{inner}</div>;
          })}
          {!expanded && rest.length > 7 && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              style={{ all: 'unset', cursor: 'pointer', ...lblStyle, fontSize: 9, marginTop: 6, display: 'block' }}
            >
              show {rest.length - 7} more →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ChampionsBand() {
  const awards = useSeasonAwards();
  const list = awards.data?.awards ?? [];
  // A FAILED request is not an empty season — silence would hide an
  // outage as normalcy (Codex on #813, wave 2).
  if (awards.isError) {
    return <div style={{ marginBottom: 18 }}><Unavailable what="season champions" /></div>;
  }
  // [] is the NORMAL state until a season is engraved — the band hides,
  // exactly like legacy (corpus recording proves the emptiness).
  if (!awards.isSuccess || list.length === 0) return null;
  return (
    <div data-parity="record-book.champions" style={{ marginBottom: 18 }}>
      <SectionHead label={`${awards.data?.season_name ?? 'season'} · champions`} />
      <div className="landing-quad" style={{ gap: 10, marginTop: 10 }}>
        {list.map((a, i) => {
          const inner = (<>
            {/* The backend supplies a display label ('Season MVP') —
              * deriving from award_key rendered 'mvp' (Codex on #813). */}
            <Lbl style={{ fontSize: 9 }}>{a.label ?? (a.award_key ?? a.key ?? '').replace(/_/g, ' ')}</Lbl>
            <div className="m" style={{ fontSize: 13, marginTop: 3 }}>{a.player_name ?? '—'}</div>
            {a.value_text && <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>{a.value_text}</div>}
          </>);
          // Multiple recipients of one award_key are a valid state — the
          // conflict key is (season, award, PLAYER) (wave 2). A champion
          // WITH a guid links to their profile like legacy did (wave 3);
          // without one, a plain card.
          const key = `${a.award_key ?? a.key ?? i}:${a.player_guid ?? i}`;
          const style = { borderLeft: '2px solid var(--color-accent-warm)', paddingLeft: 10 } as const;
          return a.player_guid
            ? <Link key={key} to={`/profile/${a.player_guid}`} style={{ ...style, textDecoration: 'none', color: 'var(--color-text-100)', display: 'block' }}>{inner}</Link>
            : <div key={key} style={style}>{inner}</div>;
        })}
      </div>
    </div>
  );
}

function HofTab() {
  const [period, setPeriod] = useState('all_time');
  const hof = useHallOfFame(period);
  const data = hof.isError ? undefined : hof.data;
  return (
    <div data-parity="record-book.hof">
      <ChampionsBand />
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {HOF_PERIODS.map((p) => (
          <Chip key={p.key} active={period === p.key} label={p.label} onClick={() => { setPeriod(p.key); }} />
        ))}
      </div>
      {hof.isPending && <div style={{ marginTop: 16 }}><Pending label="hall of fame" /></div>}
      {hof.isError && <div style={{ marginTop: 16 }}><Unavailable what="hall of fame" /></div>}
      {data && (
        <div className="landing-split" style={{ gap: 18, marginTop: 16 }}>
          {HOF_CATEGORIES.map((cat) => {
            const entries = data.categories[cat.key] ?? [];
            return entries.length > 0
              ? <HofList key={cat.key} catKey={cat.key} label={cat.label} desc={cat.desc} entries={entries} />
              : (
                <div key={cat.key} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 14 }}>
                  <Lbl style={{ fontSize: 9 }}>{cat.label}</Lbl>
                  <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 8 }}>
                    no data {period === 'all_time' ? 'yet' : 'in this period'}
                  </div>
                </div>
              );
          })}
        </div>
      )}
    </div>
  );
}

/** Legacy _LEADER_LABELS — the keys the Season tab shows, in this order. */
const LEADER_LABELS: [string, string][] = [
  ['damage_given', 'most damage'],
  ['kills', 'most kills'],
  ['dpm', 'top dpm'],
  ['revives', 'most revives'],
  ['objectives', 'most objectives'],
  ['gibs', 'most gibs'],
  ['xp', 'most xp'],
];

function SeasonTab() {
  const season = useSeasonCurrent();
  const leaders = useSeasonLeaders();
  const lead = leaders.data?.leaders;
  return (
    <div data-parity="record-book.season">
      {season.isPending && <Pending label="season" />}
      {season.isError && <Unavailable what="season" />}
      {season.data && (
        <SectionHead
          label={season.data.name}
          aside={Number.isFinite(season.data.days_left)
            ? <span className="m" style={{ ...lblStyle, fontSize: 9 }}>{season.data.days_left} days left</span>
            : undefined}
        />
      )}
      <div style={{ marginTop: 14 }}>
        <ChampionsBand />
        {useSeasonAwardsEmptyNote()}
      </div>
      <SectionHead label="category leaders" />
      {leaders.isPending && <div style={{ marginTop: 10 }}><Pending label="leaders" /></div>}
      {leaders.isError && <div style={{ marginTop: 10 }}><Unavailable what="leaders" /></div>}
      {lead && (
        <div style={{ marginTop: 8 }}>
          {LEADER_LABELS.filter(([key]) => lead[key] != null).map(([key, label]) => {
            const row = lead[key];
            return (
              <div key={key} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: '140px minmax(0,1fr) auto', gap: 12, alignItems: 'baseline', padding: '8px 0' }}>
                <Lbl style={{ fontSize: 9 }}>{label}</Lbl>
                <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row?.player}</span>
                <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{figure(row?.value ?? 0)}</span>
              </div>
            );
          })}
          {LEADER_LABELS.every(([key]) => lead[key] == null) && (
            <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 8 }}>no leaders yet</div>
          )}
        </div>
      )}
      <Link to="/leaderboards" style={{ ...lblStyle, fontSize: 9, display: 'inline-block', marginTop: 16, textDecoration: 'none' }}>
        full season leaderboard →
      </Link>
    </div>
  );
}

/** The engraved-awards emptiness is worth a sentence on the Season tab
 * (the band itself hides), matching legacy's 'No engraved season awards
 * yet.' */
function useSeasonAwardsEmptyNote() {
  const awards = useSeasonAwards();
  if (!awards.isSuccess || (awards.data?.awards.length ?? 0) > 0) return null;
  return (
    <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginBottom: 14 }}>
      no engraved season awards yet
    </div>
  );
}

export function RecordBook() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get('tab') === 'hof' || params.get('tab') === 'season') ? params.get('tab')! : 'records';
  return (
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 980 }}>
      <Lbl>record book</Lbl>
      <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
        The book everyone is trying to rewrite.
      </h1>
      <div style={{ display: 'flex', gap: 8, marginTop: 18 }}>
        {TABS.map((t) => (
          <Chip key={t.key} active={tab === t.key} label={t.label} onClick={() => { setParams({ tab: t.key }); }} />
        ))}
      </div>
      <div style={{ marginTop: 20 }}>
        {tab === 'records' && <RecordsTab />}
        {tab === 'hof' && <HofTab />}
        {tab === 'season' && <SeasonTab />}
      </div>
    </div>
  );
}

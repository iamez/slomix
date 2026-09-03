/**
 * The expanded player row (stats 2.0 R5, docs/design/18 §C plast 2): what a
 * power user gets when they open one player on the session page — links to
 * the player's own pages, per-map totals summed from the rounds already on
 * the page, their best life and verdict picked out of the night's panels,
 * the KIS per-kill breakdown the story tab draws, and the weapons row this
 * expander used to be.
 *
 * Five instruments, five separate states: a failed request is declared
 * where it fails, an empty one says why, and none of them waits on another
 * (only the KIS breakdown needs the kill-impact list first, to translate
 * the page's 8-character guid into the 32-character one the details
 * endpoint matches exactly — storytelling_router.py:400).
 */
import { Link } from 'react-router';

import { DataTable, type DataColumn } from './DataTable';
import { Cluster, Stack } from './layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from './ui';
import { guidKey, perMapTotals, type PerMapTotals } from '../lib/perMap';
import {
  useSessionPlayerWeapons, useSessionRounds, useSessionVerdicts, useStoryBestLives, useStoryKillImpact,
} from '../lib/queries';
import { KisDetails } from '../pages/Story';

/** One player's weapons within THIS session — the session-scoped call
 * legacy session-detail.js made, via the hyphen spelling (see
 * useSessionPlayerWeapons). */
export function PlayerWeaponsRow({ sessionId, guid }: { sessionId: number; guid: string }) {
  const weapons = useSessionPlayerWeapons(sessionId, guid);
  const player = weapons.data?.players[0];
  return (
    <div>
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
                * row's hs column counts hit percentage, and one shared
                * abbreviation would invite comparing the two (Codex on #855). */}
              {w.headshots > 0 && <> · {figure(w.headshots)} head hits</>}
            </span>
          ))}
        </Cluster>
      ))}
    </div>
  );
}

const MAP_COLUMNS: readonly DataColumn<PerMapTotals>[] = [
  { key: 'map', label: 'map', align: 'left', width: 150, title: 'map, counted rounds only', format: (m) => m.map_name, sortValue: (m) => m.map_name },
  { key: 'r', label: 'r', title: 'counted rounds on this map with this player', width: 36, sortValue: (m) => m.rounds },
  { key: 'k', label: 'k', title: 'kills', width: 42, sortValue: (m) => m.kills },
  { key: 'd', label: 'd', title: 'deaths', width: 42, sortValue: (m) => m.deaths },
  { key: 'kd', label: 'k/d', title: 'kills ÷ max(1, deaths)', width: 48, sortValue: (m) => m.kd, format: (m) => m.kd.toFixed(2) },
  { key: 'dpm', label: 'dpm', title: 'damage given × 60 ÷ time played on this map — null when no time was recorded', width: 52,
    sortValue: (m) => m.dpm, format: (m) => (m.dpm == null ? null : m.dpm.toFixed(0)) },
  { key: 'dmg', label: 'dmg', title: 'damage given', width: 62, sortValue: (m) => m.damage_given, format: (m) => figure(m.damage_given) },
];

function PerMap({ sessionId, guid8 }: { sessionId: number; guid8: string }) {
  const rounds = useSessionRounds(sessionId);
  if (rounds.isPending) return <Pending label="maps" />;
  if (rounds.isError) return <Unavailable what="maps" />;
  const { maps, counted, skipped } = perMapTotals(rounds.data.rounds, guid8);
  if (maps.length === 0) return <Absent reason="no counted round carries this player" />;
  return (
    <Stack gap={2}>
      <DataTable columns={MAP_COLUMNS} rows={maps} rowKey={(m) => m.map_name} defaultSort={{ key: 'dpm', dir: 'desc' }} minWidth={520} label="per map" />
      <Meta>{figure(counted)} counted round(s) with this player{skipped > 0 ? ` · ${figure(skipped)} round(s) of the night do not count and are left out` : ''}</Meta>
    </Stack>
  );
}

function BestLife({ sessionId, guid8 }: { sessionId: number; guid8: string }) {
  const q = useStoryBestLives(sessionId);
  if (q.isPending) return <Pending label="best life" />;
  if (q.isError) return <Unavailable what="best life" />;
  const key = guidKey(guid8);
  const mine = q.data.lives.filter((l) => guidKey(l.guid) === key).sort((a, b) => b.kills - a.kills);
  if (mine.length === 0) {
    return (
      <Absent reason={<>no tracked life of theirs cleared the minimum{q.data.min_kills != null ? ` (${q.data.min_kills} kills)` : ''} — though the endpoint cannot say how much of the night was tracked at all</>} />
    );
  }
  const l = mine[0];
  return (
    <Cluster gap={2} align="baseline">
      <span className="m" style={{ fontSize: 'var(--fs-value)', color: 'var(--color-accent)' }}>{l.kills}</span>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>kills · one life · {l.map_name} R{l.round_number} · {l.life_seconds}s alive</Lbl>
    </Cluster>
  );
}

function Form({ sessionId, guid8 }: { sessionId: number; guid8: string }) {
  const q = useSessionVerdicts(sessionId);
  if (q.isPending) return <Pending label="form" />;
  if (q.isError) return <Unavailable what="form" />;
  const key = guidKey(guid8);
  const v = q.data.players.find((p) => guidKey(p.guid) === key);
  if (!v) return <Absent reason="no baseline for this player yet — nothing of theirs to compare this night against" />;
  if (v.first_night) return <Absent reason="first night — no baseline yet" />;
  return (
    <Cluster gap={3} align="baseline">
      <span className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>{v.label}</span>
      <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{v.dpm.toFixed(0)}</span>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        dpm · {v.avg_dpm == null ? '—' : v.avg_dpm.toFixed(0)} usual · {figure(v.sessions_in_baseline)} sessions
        {v.percentile != null ? ` · ${v.percentile.toFixed(0)}th percentile` : ''}
        {q.data.baseline ? ` · against ${q.data.baseline}` : ''}
      </Lbl>
    </Cluster>
  );
}

/** The KIS breakdown needs the 32-character guid the details endpoint
 *  matches exactly; the page only has the 8-character one. The kill-impact
 *  list (one request, shared by every open row) carries both. A player
 *  missing from it has no scored kills — the same absence the basics
 *  table's kis column reports. */
function Kis({ sessionId, guid8, name }: { sessionId: number; guid8: string; name: string }) {
  const list = useStoryKillImpact(sessionId);
  if (list.isPending) return <Pending label="kill impact" />;
  if (list.isError) return <Unavailable what="kill impact" />;
  const key = guidKey(guid8);
  const me = list.data.players.find((p) => guidKey(p.guid) === key);
  if (!me) return <Absent reason={<>no scored kills for {name} in this session — the proximity tracker scored none of theirs</>} />;
  return <KisDetails gsid={sessionId} guid={me.guid} name={name} />;
}

export function PlayerDrilldown({ sessionId, guid8, name }: { sessionId: number; guid8: string; name: string }) {
  const key = guidKey(guid8);
  return (
    <Stack gap={4} parity="session.player" style={{ padding: 'var(--space-3) 0 var(--space-4) var(--space-5)' }}>
      <Cluster gap={4} align="baseline" parity="session.player.links">
        <Link to={`/profile/${key}`} className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>profile →</Link>
        <Link to={`/proximity/player/${key}`} className="lbl" style={{ fontSize: 'var(--fs-caption)' }}>proximity →</Link>
      </Cluster>
      <Stack gap={2} parity="session.player.maps">
        <SectionHead label="by map" aside={<span className="lbl">counted rounds · summed from the rounds tab</span>} />
        <PerMap sessionId={sessionId} guid8={guid8} />
      </Stack>
      <Stack gap={2} parity="session.player.life">
        <SectionHead label="best life" aside={<span className="lbl">most kills on a single life</span>} />
        <BestLife sessionId={sessionId} guid8={guid8} />
      </Stack>
      <Stack gap={2} parity="session.player.form">
        <SectionHead label="form" aside={<span className="lbl">this night against their own baseline</span>} />
        <Form sessionId={sessionId} guid8={guid8} />
      </Stack>
      <Stack gap={2} parity="session.player.kis">
        <SectionHead label="kills, scored" aside={<span className="lbl">kill impact · the ten that moved most</span>} />
        <Kis sessionId={sessionId} guid8={guid8} name={name} />
      </Stack>
      <Stack gap={2} parity="session.player.weapons">
        <SectionHead label="weapons" aside={<span className="lbl">this session</span>} />
        <PlayerWeaponsRow sessionId={sessionId} guid={guid8} />
      </Stack>
    </Stack>
  );
}

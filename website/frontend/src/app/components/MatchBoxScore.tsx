/**
 * The box score of one half — GET /api/stats/matches/{id}: both teams, every
 * player's row, the totals, the winner. The legacy matches page opened this
 * in a modal (matches.js:634); the new Home listed the rows and linked to
 * the evening, so the half itself had no page (endpoint ratchet line
 * `/api/stats/matches/{}`, closed here).
 */
import { DataTable, type DataColumn } from './DataTable';
import { Cluster, Stack } from './layout';
import { Panel } from './Panel';
import { mmss } from './RoundsTable';
import { Lbl, Meta, figure } from './ui';
import { useMatchDetails } from '../lib/queries';
import type { MatchDetails, MatchDetailsPlayer, MatchDetailsTeam } from '../lib/types';

const PLAYER_COLUMNS: DataColumn<MatchDetailsPlayer>[] = [
  { key: 'name', label: 'player', sortValue: (p) => p.name },
  { key: 'kills', label: 'k', align: 'right', sortValue: (p) => p.kills },
  { key: 'deaths', label: 'd', align: 'right', sortValue: (p) => p.deaths },
  { key: 'kd', label: 'k/d', align: 'right', format: (p) => figure(p.kd), sortValue: (p) => p.kd },
  { key: 'headshot_kills', label: 'hs', align: 'right', title: 'headshot kills (not head hits)', sortValue: (p) => p.headshot_kills },
  { key: 'headshots', label: 'head hits', align: 'right', title: 'head HITS — routinely more than kills', sortValue: (p) => p.headshots },
  { key: 'damage_given', label: 'given', align: 'right', sortValue: (p) => p.damage_given },
  { key: 'damage_received', label: 'taken', align: 'right', sortValue: (p) => p.damage_received },
  { key: 'dpm', label: 'dpm', align: 'right', format: (p) => figure(p.dpm), sortValue: (p) => p.dpm },
  { key: 'accuracy', label: 'acc', align: 'right', title: 'hits of shots, percent', format: (p) => `${figure(p.accuracy)} %`, sortValue: (p) => p.accuracy },
  { key: 'gibs', label: 'gibs', align: 'right', sortValue: (p) => p.gibs },
  { key: 'revives_given', label: 'rev', align: 'right', sortValue: (p) => p.revives_given },
  { key: 'times_revived', label: 'revived', align: 'right', sortValue: (p) => p.times_revived },
  { key: 'useful_kills', label: 'uk', align: 'right', title: 'useful kills', sortValue: (p) => p.useful_kills },
  { key: 'xp', label: 'xp', align: 'right', format: (p) => figure(p.xp), sortValue: (p) => p.xp },
  { key: 'time_played', label: 'played', align: 'right', format: (p) => mmss(p.time_played), sortValue: (p) => p.time_played },
  { key: 'time_dead', label: 'dead', align: 'right', title: 'seconds dead', format: (p) => mmss(p.time_dead), sortValue: (p) => p.time_dead },
  { key: 'time_denied', label: 'denied', align: 'right', title: 'seconds of playtime denied to opponents', format: (p) => mmss(p.time_denied), sortValue: (p) => p.time_denied },
  { key: 'selfkills', label: 'sk', align: 'right', title: 'self kills', sortValue: (p) => p.selfkills },
  { key: 'teamkills', label: 'tk', align: 'right', title: 'team kills', sortValue: (p) => p.teamkills },
  { key: 'multi', label: 'multi', align: 'right', title: 'double / triple / quad / multi / mega kills',
    format: (p) => `${figure(p.double_kills)}/${figure(p.triple_kills)}/${figure(p.quad_kills)}/${figure(p.multi_kills)}/${figure(p.mega_kills)}`,
    sortValue: (p) => p.double_kills + p.triple_kills + p.quad_kills + p.multi_kills + p.mega_kills },
];

function TeamTable({ team, side }: { team: MatchDetailsTeam; side: string }) {
  return (
    <Stack gap={1}>
      <Cluster gap={3} align="baseline">
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{team.name}</Lbl>
        <Meta>{side}{team.is_winner ? ' · won' : ''} · {figure(team.totals.kills)} k · {figure(team.totals.deaths)} d · {figure(team.totals.damage)} dmg</Meta>
      </Cluster>
      <DataTable<MatchDetailsPlayer>
        parity="match.box-score.team"
        label={`${team.name} players`}
        columns={PLAYER_COLUMNS}
        rows={team.players}
        rowKey={(p) => p.player_guid || p.name}
        defaultSort={{ key: 'kills', dir: 'desc' }}
        minWidth={1100}
      />
    </Stack>
  );
}

export function MatchBoxScore({ roundId }: { roundId: number }) {
  const q = useMatchDetails(roundId);
  return (
    <Panel<MatchDetails>
      parity="match.box-score"
      label="box score"
      aside={q.data ? `${q.data.match.map_name ?? 'unknown map'} R${String(q.data.match.round_number)} · ${q.data.match.winner.toLowerCase()} · ${q.data.match.duration ?? 'duration unknown'}${q.data.match.time_limit ? ` of ${q.data.match.time_limit}` : ''} · ${q.data.match.outcome?.toLowerCase() ?? 'outcome unknown'} · round #${String(q.data.match.id)} · ${q.data.match.round_date ?? 'date unknown'} · ${figure(q.data.player_count)} players` : undefined}
      q={q}
      empty="the round exists, but no player rows were recorded for this half"
      isEmpty={(d) => d.team1.players.length + d.team2.players.length === 0}
    >
      {(d) => (
        <Stack gap={3}>
          {/* Sides: team 1 is whichever side the handler lists first; the
            * match's `winner` names a SIDE, `is_winner` a logical team. */}
          <TeamTable team={d.team1} side={d.team1.players[0]?.team === 1 ? 'axis' : d.team1.players[0]?.team === 2 ? 'allies' : 'side unknown'} />
          <TeamTable team={d.team2} side={d.team2.players[0]?.team === 1 ? 'axis' : d.team2.players[0]?.team === 2 ? 'allies' : 'side unknown'} />
        </Stack>
      )}
    </Panel>
  );
}

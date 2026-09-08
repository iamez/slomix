/**
 * The session page's Rounds tab (stats 2.0 R4, docs/design/18 §C plast 2):
 * the RoundsTable the retired /rounds page hosted, minus the session picker
 * the page needed and the session page does not — it already knows which
 * session it is on.
 *
 * The two views are the same data seen from two ends — `round` for "how did
 * that round go", `player` for "how am I doing" — the split the owner asked
 * for on the old page, kept here.
 */
import { useMemo, useState } from 'react';

import { Cluster, Stack } from './layout';
import { RoundsTable, mmss, type EmptyReason } from './RoundsTable';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from './ui';
import { DataTable, type DataColumn } from './DataTable';
import { Panel } from './Panel';
import { weaponLabel } from '../lib/weapons';
import { useRoundAwards, useRoundPlayerDetails } from '../lib/queries';
import type { RoundPlayerDetails, SessionRounds } from '../lib/types';

/** ⛔ A DISABLED QUERY IS PENDING FOREVER IN REACT QUERY v5 — but on the
 *  session page the id is in the URL, so the query is never disabled and the
 *  three states are the whole story. */
export function roundsReason(rounds: { isPending: boolean; isError: boolean }): EmptyReason {
  if (rounds.isError) return 'unavailable';
  if (rounds.isPending) return 'loading';
  return 'no_data';
}

export function RoundsTab({ rounds, reason }: { rounds: SessionRounds | undefined; reason: EmptyReason }) {
  const [mode, setMode] = useState<'round' | 'player'>('round');
  const [guid, setGuid] = useState<string>('');
  // Which round's awards are open. The table has carried an `onSelectRound`
  // prop since it was written and nothing ever passed one — clicking a round
  // did nothing at all. This is that prop's first consumer.
  const [openRound, setOpenRound] = useState<number | null>(null);
  // Which player of which round is open — the per-half breakdown the legacy
  // matches page opened in a modal (ledger 2026-09-08: 23 fields nobody drew).
  const [openPlayer, setOpenPlayer] = useState<{ roundId: number; guid: string } | null>(null);

  // Players present in this session, for the "one player" view.
  const players = useMemo(() => {
    const seen = new Map<string, string>();
    for (const round of rounds?.rounds ?? []) {
      for (const p of round.players) seen.set(p.player_guid, p.player_name);
    }
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [rounds]);

  // ⛔ A saved selection must be re-checked against the roster. Keeping a
  // guid the roster does not contain leaves the selector showing a value no
  // option holds, while the table filters every row and reports "no rounds
  // match" for a session that is full of rounds.
  const knownGuid = players.some(([g]) => g === guid);
  const effectiveGuid = (knownGuid ? guid : players.at(0)?.[0]) ?? '';

  return (
    <Stack gap={3} parity="session.rounds">
      <SectionHead
        label="rounds"
        aside={rounds ? (
          <span className="lbl">
            {rounds.counted_rounds} of {rounds.total_rounds} count toward totals
          </span>
        ) : undefined}
      />

      <Cluster gap={3} align="baseline">
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>view</Lbl>
        <Cluster gap={2}>
          {(['round', 'player'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); }}
              aria-pressed={mode === m}
              style={{ all: 'unset', cursor: 'pointer',
                       fontSize: 'var(--fs-small)',
                       textTransform: 'uppercase', letterSpacing: '0.08em',
                       color: mode === m ? 'var(--color-text-100)'
                                         : 'var(--color-text-500)' }}
            >
              {m === 'round' ? 'by round' : 'one player'}
            </button>
          ))}
        </Cluster>

        {mode === 'player' && players.length > 0 ? (
          <select
            value={effectiveGuid}
            onChange={(e) => { setGuid(e.target.value); }}
            aria-label="player"
            style={{ background: 'transparent', color: 'var(--color-text-100)',
                     border: '1px solid var(--color-rule-900)',
                     padding: 'var(--space-2)', fontSize: 'var(--fs-small)' }}
          >
            {players.map(([g, name]) => (
              <option key={g} value={g}>{name}</option>
            ))}
          </select>
        ) : null}
      </Cluster>

      <RoundsTable
        rounds={rounds?.rounds ?? []}
        mode={mode}
        playerGuid={mode === 'player' ? effectiveGuid : undefined}
        emptyReason={reason}
        onSelectRound={(id) => { setOpenRound((cur) => (cur === id ? null : id)); }}
        onSelectPlayer={(roundId, guid) => {
          setOpenPlayer((cur) => (cur?.roundId === roundId && cur.guid === guid ? null : { roundId, guid }));
        }}
        selectedPlayer={openPlayer}
        renderPlayerDetails={(roundId, guid) => <RoundPlayerDetailsPanel roundId={roundId} playerGuid={guid} />}
      />
      {openRound != null ? <RoundAwardsPanel roundId={openRound} /> : null}
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
        every recorded round, the ones that do not count marked, not hidden
      </Lbl>
    </Stack>
  );
}

/**
 * Awards for one round, the breakdown behind the session's award summary.
 *
 * ⛔ THE EMPTY ANSWER IS THE COMMON ONE. Only 1016 of 3243 rounds carry any
 * award at all, so "this round has none" is what two visitors in three will
 * see. It is `Absent` with a reason, not a blank space — a page that shows
 * nothing without saying why reads as broken.
 *
 * ⚠️ `numeric` is deliberately not rendered. It exists for sorting and is
 * null whenever the figure is a rendered string; `value` is the display form
 * and is never null.
 */
export function RoundAwardsPanel({ roundId }: { roundId: number }) {
  const awards = useRoundAwards(roundId);
  const categories = Object.entries(awards.data?.categories ?? {});

  return (
    <Stack gap={2} parity="session.rounds.awards">
      <SectionHead label={`awards · round ${String(roundId)}`} />
      {awards.isPending ? <Pending label="awards" /> : null}
      {awards.isError ? <Unavailable what="awards" /> : null}
      {!awards.isPending && !awards.isError && categories.length === 0
        ? <Absent reason="no awards recorded for this round" />
        : null}
      {categories.map(([key, cat]) => (
        <Stack key={key} gap={1}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>
            {cat.emoji} {cat.name}
          </Lbl>
          {cat.awards.map((a, i) => (
            <Cluster key={`${a.award}-${String(i)}`} gap={2} align="baseline">
              <span style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)' }}>
                {a.award}
              </span>
              <span style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-100)' }}>
                {a.player}
              </span>
              <span style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-500)' }}>
                {a.value}
              </span>
            </Cluster>
          ))}
        </Stack>
      ))}
    </Stack>
  );
}

const WEAPON_COLUMNS: DataColumn<RoundPlayerDetails['weapons'][number]>[] = [
  { key: 'name', label: 'weapon', format: (w) => weaponLabel(w.name), sortValue: (w) => weaponLabel(w.name) },
  { key: 'kills', label: 'k', align: 'right', sortValue: (w) => w.kills },
  { key: 'deaths', label: 'd', align: 'right', title: 'deaths to this weapon', sortValue: (w) => w.deaths },
  { key: 'headshots', label: 'hs', align: 'right', sortValue: (w) => w.headshots },
  { key: 'hits', label: 'hits', align: 'right', sortValue: (w) => w.hits },
  { key: 'shots', label: 'shots', align: 'right', sortValue: (w) => w.shots },
  { key: 'accuracy', label: 'acc', align: 'right', title: 'hits of shots, percent', format: (w) => `${figure(w.accuracy)} %`, sortValue: (w) => w.accuracy },
];

/** A line of labelled figures — the cells of one group of the breakdown. */
function Figures({ items }: { items: readonly [string, number | string][] }) {
  return (
    <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
      {items.map(([label, value]) => (
        <span key={label} style={{ fontSize: 'var(--fs-small)' }}>
          <Meta>{label} </Meta>{typeof value === 'number' ? figure(value) : value}
        </span>
      ))}
    </Cluster>
  );
}

/**
 * One player's breakdown of one half — GET /rounds/{id}/player/{guid}/details.
 * Everything the recording carries is shown ("capture everything", owner
 * 2026-09-07); the objectives and dynamite figures are the ones the session
 * table has no column for, the weapon table carries the deaths column.
 */
export function RoundPlayerDetailsPanel({ roundId, playerGuid }: { roundId: number; playerGuid: string }) {
  const q = useRoundPlayerDetails(roundId, playerGuid);
  return (
    <Panel<RoundPlayerDetails>
      parity="session.rounds.player-details"
      label="in this half"
      aside={q.data ? `${q.data.player_name} · ${q.data.round.map_name} R${String(q.data.round.round_number)}` : undefined}
      q={q}
      empty="no stats row for this player in this half"
      isEmpty={(d) => d.combat.kills === 0 && d.combat.deaths === 0 && d.time.played_seconds === 0}
    >
      {(d) => (
        <Stack gap={2}>
          <Figures items={[
            ['kills', d.combat.kills], ['deaths', d.combat.deaths], ['gibs', d.combat.gibs],
            ['hs kills', d.combat.headshot_kills], ['headshots', d.combat.headshots],
            ['given', d.combat.damage_given], ['taken', d.combat.damage_received],
            ['acc', `${figure(d.combat.accuracy)} %`], ['hits', d.combat.hits], ['shots', d.combat.shots],
          ]} />
          <Figures items={[
            ['objectives stolen', d.objectives.stolen], ['returned', d.objectives.returned],
            ['dynamite planted', d.objectives.dynamites_planted], ['defused', d.objectives.dynamites_defused],
          ]} />
          <Figures items={[
            ['revives', d.support.revives_given], ['revived', d.support.times_revived],
            ['useful kills', d.support.useful_kills], ['useless', d.support.useless_kills], ['assists', d.support.kill_assists],
          ]} />
          <Figures items={[
            ['double', d.sprees.double_kills], ['triple', d.sprees.triple_kills], ['quad', d.sprees.quad_kills],
            ['multi', d.sprees.multi_kills], ['mega', d.sprees.mega_kills],
          ]} />
          <Figures items={[
            ['played', mmss(d.time.played_seconds)], ['dead', `${figure(d.time.dead_minutes)} min`],
            ['denied', `${figure(d.time.denied_playtime)} s`], ['xp', d.misc.xp],
            ['team kills', d.misc.team_kills], ['self kills', d.misc.self_kills],
          ]} />
          <DataTable<RoundPlayerDetails['weapons'][number]>
            parity="session.rounds.player-details.weapons"
            label="weapons in this half"
            columns={WEAPON_COLUMNS}
            rows={d.weapons}
            rowKey={(w) => w.name}
            defaultSort={{ key: 'kills', dir: 'desc' }}
            minWidth={420}
          />
        </Stack>
      )}
    </Panel>
  );
}

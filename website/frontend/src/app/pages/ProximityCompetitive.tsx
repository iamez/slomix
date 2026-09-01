/**
 * Phase 5, slice 3 — the competitive section (07 §B.2): stagger, first
 * blood, personal bests, man advantage, clutch, side splits, and the v7
 * capture roadmap. Every panel QUOTES the wire's own `description` — the
 * formula text lives server-side and the page repeats it, never
 * paraphrases (#769's transparency rule). wave-cycles is deliberately not
 * here: it requires a map and round and belongs to the round-scope slice,
 * where it stays pinned as pending.
 */
import { Cluster, Stack } from '../components/layout';
import { Absent, Lbl, Meta, Pending, SectionHead, Unavailable, figure } from '../components/ui';
import { stripEtColors } from '../lib/names';
import { isFailureStatus } from '../lib/responseStatus';
import {
  useCompClutch, useCompFirstBlood, useCompManAdvantage, useCompPersonalBests,
  useCompSideSplits, useCompStagger, useV7Status,
} from '../lib/queries';

type Query<T> = { isPending: boolean; isError: boolean; data: T | undefined };

function Panel<T extends { status?: string }>({ label, q, empty, isEmpty, children }: {
  label: string;
  q: Query<T>;
  empty: string;
  isEmpty: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
}) {
  return (
    <Stack gap={2}>
      <SectionHead label={label} />
      {q.isPending && <Pending label={label} />}
      {q.isError && <Unavailable what={label} />}
      {q.data && (isFailureStatus(q.data.status) ? (
        <Unavailable what={label} />
      ) : isEmpty(q.data) ? (
        <Absent reason={empty} />
      ) : (
        children(q.data)
      ))}
    </Stack>
  );
}

function Formula({ text }: { text: string }) {
  // The wire's own words — quoted, never paraphrased.
  return <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{text}</Lbl>;
}

function Row({ name, mid, val }: { name: string; mid?: string; val: string }) {
  return (
    <Cluster gap={3} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-1) 0' }}>
      <span style={{ fontSize: 'var(--fs-row)' }}>{name}</span>
      <Cluster gap={3} align="baseline">
        {mid != null && <Meta>{mid}</Meta>}
        <span className="m" style={{ fontSize: 'var(--fs-small)', minWidth: 72, textAlign: 'right' }}>{val}</span>
      </Cluster>
    </Cluster>
  );
}

const NO_ROWS = 'no rows in this scope — proximity capture only covers sessions where the tracker ran';

export function ProximityCompetitive({ sessionDate }: { sessionDate: string | null }) {
  const stagger = useCompStagger(sessionDate);
  const firstBlood = useCompFirstBlood(sessionDate);
  const bests = useCompPersonalBests(sessionDate);
  const advantage = useCompManAdvantage(sessionDate);
  const clutch = useCompClutch(sessionDate);
  const splits = useCompSideSplits(sessionDate);
  const v7 = useV7Status();

  return (
    <Stack gap={6} style={{ marginTop: 'var(--space-8)' }}>
      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.stagger">
          <Panel label="stagger kills" q={stagger} empty={NO_ROWS} isEmpty={(d) => d.players.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.players.slice(0, 5).map((p) => (
                  <Row key={p.guid} name={stripEtColors(p.name)} mid={`${figure(p.stagger_kills)} of ${figure(p.kills)} kills · ${figure(Math.round(p.denied_s))} s denied`} val={`${p.stagger_rate.toFixed(1)}%`} />
                ))}
                <Formula text={d.description} />
              </Stack>
            )}
          </Panel>
        </div>

        <div data-parity="proximity.first-blood">
          <Panel label="first blood" q={firstBlood} empty={NO_ROWS} isEmpty={(d) => d.decided_rounds === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.converted)} of {figure(d.decided_rounds)} decided rounds converted ({d.conversion_pct.toFixed(1)}%)</Meta>
                {d.players.slice(0, 5).map((p) => (
                  <Row key={p.guid} name={stripEtColors(p.name)} mid={`${figure(p.first_deaths)} first deaths`} val={`${figure(p.first_picks)} picks · ${figure(p.fp_converted)} won`} />
                ))}
                <Formula text={d.description} />
              </Stack>
            )}
          </Panel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.man-advantage">
          <Panel label="man advantage" q={advantage} empty={NO_ROWS} isEmpty={(d) => d.total_windows === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>{figure(d.total_windows)} advantage windows over {figure(d.rounds)} rounds</Meta>
                {Object.entries(d.teams).map(([team, t]) => (
                  <Row key={team} name={team.toLowerCase()} mid={`+1: ${t.by_size['1']?.converted ?? 0}/${t.by_size['1']?.windows ?? 0} · +2: ${t.by_size['2']?.converted ?? 0}/${t.by_size['2']?.windows ?? 0} · +3+: ${t.by_size['3+']?.converted ?? 0}/${t.by_size['3+']?.windows ?? 0}`} val={`${t.conversion_pct.toFixed(1)}%`} />
                ))}
                {d.top_converters.slice(0, 3).map((p) => (
                  <Row key={p.guid} name={stripEtColors(p.name)} mid="closes the window" val={`${figure(p.conversions)}×`} />
                ))}
                <Formula text={d.description} />
              </Stack>
            )}
          </Panel>
        </div>

        <div data-parity="proximity.clutch">
          <Panel label="clutch 1vN" q={clutch} empty={NO_ROWS} isEmpty={(d) => d.players.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                <Meta>
                  {figure(d.rounds)} rounds · clock {d.clock_protocol}
                  {d.skipped_rounds_no_clock > 0 && <> · {figure(d.skipped_rounds_no_clock)} rounds skipped (no clock)</>}
                </Meta>
                {d.players.slice(0, 5).map((p) => (
                  <Row
                    key={p.guid}
                    name={stripEtColors(p.name)}
                    mid={p.best ? `best: 1v${p.best.enemies}, ${figure(p.best.kills)} kills${p.best.survived ? ', survived' : ''}` : undefined}
                    val={`${figure(p.wins)}/${figure(p.situations)} · ${p.win_pct.toFixed(0)}%`}
                  />
                ))}
                <Formula text={d.description} />
              </Stack>
            )}
          </Panel>
        </div>
      </div>

      <div className="landing-split" style={{ gap: 'var(--space-6)' }}>
        <div data-parity="proximity.side-splits">
          <Panel label="attack · defense" q={splits} empty={NO_ROWS} isEmpty={(d) => d.players.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.players.slice(0, 6).map((p) => (
                  <Row
                    key={p.guid}
                    name={stripEtColors(p.name)}
                    // A missing side is a fact (they only played one half),
                    // not a zero — caught crashing live on a single-round
                    // scope the recorded fixture could not represent.
                    mid={`atk ${p.attack ? `${figure(p.attack.kills)}k in ${p.attack.minutes.toFixed(0)}m` : '—'} · def ${p.defense ? `${figure(p.defense.kills)}k in ${p.defense.minutes.toFixed(0)}m` : '—'}`}
                    val={`${p.attack ? p.attack.kpm.toFixed(2) : '—'} / ${p.defense ? p.defense.kpm.toFixed(2) : '—'} kpm`}
                  />
                ))}
                <Formula text={d.description} />
              </Stack>
            )}
          </Panel>
        </div>

        <div data-parity="proximity.personal-bests">
          <Panel label="personal bests" q={bests} empty="no personal record fell in this session — records compare against each player's own history" isEmpty={(d) => d.cards.length === 0}>
            {(d) => (
              <Stack gap={1} className="rows">
                {d.cards.slice(0, 6).map((c) => (
                  <Row
                    key={`${c.guid}:${c.metric}`}
                    name={stripEtColors(c.name)}
                    mid={`${c.label}${c.prev_best != null ? ` · prev ${c.prev_best} (${c.prev_best_date ?? 'unknown date'})` : ' · first record'}`}
                    val={String(c.value)}
                  />
                ))}
                <Formula text={d.scope_note} />
              </Stack>
            )}
          </Panel>
        </div>
      </div>

      <div data-parity="proximity.v7-status">
        <Panel label="capture roadmap" q={v7} empty="the capability manifest is empty — nothing is reported as captured or planned" isEmpty={(d) => d.capabilities.length === 0}>
          {(d) => (
            <Stack gap={1} className="rows">
              <Meta>lua draft {d.lua_version_draft} · {d.deployed ? 'deployed' : 'not deployed'}</Meta>
              {d.capabilities.map((c) => (
                <Row
                  key={c.key}
                  name={c.title.toLowerCase()}
                  mid={c.what}
                  val={c.live ? `${figure(c.rows)} rows · ${figure(c.rounds)} rd` : 'not live'}
                />
              ))}
            </Stack>
          )}
        </Panel>
      </div>
    </Stack>
  );
}

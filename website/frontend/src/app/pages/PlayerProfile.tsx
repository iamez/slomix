import { Link, useParams } from 'react-router';
import {
  usePlayerIdentity, usePlayerMatchRounds, usePlayerProfile, useSkillPlayer,
  useMemoryCard, useSkillPlayerForm, useSkillPlayerHistory,
  usePlayerSessionForm,
  usePlayerRoundsSeries, usePlayerCard,
} from '../lib/queries';
import { ApiError } from '../lib/api';
import { sparkPathRanged } from '../lib/spark';
import { Cluster, Stack } from '../components/layout';
import { stripEtColors } from '../lib/names';
import type {
  PlayerCard, PlayerIdentity, PlayerMatchRound,
  PlayerProfile as Profile, ProfileIdentity, ProfileMapRow, ProfileMatchRow,
  ProfileOpponent, ProfileTeammate, ProfileWeaponRow, SkillPlayerComponent,
  PlayerSessionForm,
  PlayerRoundsSeries,
} from '../lib/types';
import { mapLabel } from '../lib/maps';
import { mmss } from '../components/RoundsTable';
import { utcStamp } from '../lib/utcStamp';
import { Absent, ActLink, decimals, figure, Lbl, lblStyle, Meta, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';
import { Panel } from '../components/Panel';

/**
 * The player (docs/design/08 phase 3, docs/design/12 row 18). One endpoint
 * with sections replaces the legacy page's twelve calls — and every section
 * carries `available`, so a missing panel says WHY instead of rendering an
 * empty shape: no capture, no rows and a failed sub-query all arrive as a
 * 200 here (the "absence is not agreement" class, #806/#811).
 *
 * The design-refresh language: no cards, hairline rules, condensed labels,
 * monospaced figures, and one accent per meaning.
 */

const pct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(1)}%`);
const num = (v: number | null | undefined) => (v == null ? '—' : figure(v));

function hours(seconds: number | null | undefined): string {
  if (!seconds) return '—';
  return `${Math.round(seconds / 3600).toLocaleString('en-US')} h`;
}

/** A section that exists but has nothing to show is NOT the same as one that
 * was never captured; both are named, never blank. */
function SectionBody({ available, empty, children, what }: {
  available: boolean; empty: boolean; what: string; children: React.ReactNode;
}) {
  if (!available) return <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what={what} /></div>;
  if (empty) {
    return (
      <Absent block style={{ marginTop: 'var(--space-2)' }} reason={<>no {what} recorded yet</>} />
    );
  }
  return <>{children}</>;
}

/** Sick-leave / alt attribution (migration 073). Two shapes: an ALT names
 * its primary, a PRIMARY names its alts. Gated on `active !== false`, the
 * same rule as the form page (#819): a historical link still arrives, and
 * a spent leave must not read as a current one. Statistics stay separate —
 * this line says WHO, never merges numbers. */
/** An attributed name is a destination, not a label: the response carries the
 * other identity's guid, so the reader can follow the relationship instead of
 * searching for the name by hand (Codex, #822 wave 7). A guid-less entry stays
 * plain text — a link to `/profile/undefined` is worse than no link. */
function IdentityName({ guid, name }: { guid?: string | null; name: string }) {
  if (!guid) return <>{name}</>;
  return (
    <Link to={`/profile/${guid}`} style={{ color: 'inherit', textDecoration: 'underline dotted' }}>
      {name}
    </Link>
  );
}

function IdentityLink({ link }: { link: ProfileIdentity['identity_link'] }) {
  if (!link || link.active === false) return null;
  if (link.role === 'alt' && link.primary_name) {
    return (
      <span style={{ color: 'var(--color-accent-warm)' }}>
        {' · '}alt of <IdentityName guid={link.primary_guid} name={link.primary_name} />
        {link.link_type === 'sick_leave' && ' (on sick leave)'}
      </span>
    );
  }
  const alts = (link.alts ?? []).filter((a) => a.active !== false);
  if (link.role === 'primary' && alts.length > 0) {
    return (
      <span style={{ color: 'var(--color-accent-warm)' }}>
        {' · '}also plays as{' '}
        {alts.map((a, i) => (
          <span key={`${a.alt_guid || 'noguid'}:${a.alt_name}`}>
            {i > 0 ? ', ' : ''}
            <IdentityName guid={a.alt_guid} name={a.alt_name} />
          </span>
        ))}
      </span>
    );
  }
  return null;
}

function Header({ p }: { p: Profile }) {
  const id = p.identity;
  const skill = p.skill;
  // identity goes through the same `_ok` wrapper as every other section: a
  // failed subquery there returns {available:false} with no name, guid or
  // aliases at all, and the response is still a 200 (Codex, #822 wave 2).
  // The top-level guid always exists, so the page still identifies WHO.
  const named = id.available;
  // The display name is not an alias of itself — the recording lists `vid`
  // as both, and printing "also vid" claims a second identity that isn't
  // one, while also eating a slot in the three shown.
  const aliases = (id.aliases ?? []).filter(
    (a) => a.trim().toLowerCase() !== (id.name ?? '').trim().toLowerCase(),
  );
  return (
    <div data-parity="profile.header" style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 'var(--space-5)', flexWrap: 'wrap' }}>
      <div>
        <Lbl>player · {id.guid ?? p.guid}</Lbl>
        <h1 style={{ fontSize: 'var(--fs-display)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-2) 0 0', fontWeight: 500 }}>
          {named ? id.name : (p.guid || 'unknown player')}
        </h1>
        {named ? (
          <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)', marginTop: 'var(--space-2)' }}>
            {id.first_seen ?? '—'} → {id.last_seen ?? '—'} · {figure(id.rounds ?? 0)} rounds
            {aliases.length > 0 && ` · also ${aliases.slice(0, 3).join(', ')}`}
            <IdentityLink link={id.identity_link} />
            {/* Locale-derived, not a verified country (players_profile_router:118). */}
            {id.country?.flag && ` · ${id.country.flag}${id.country.country ? ` ${id.country.country}` : ''}`}
            {id.discord_linked && ' · discord linked'}
            {id.twitch?.url && (
              <> · <a href={id.twitch.url} style={{ color: 'inherit' }}>twitch{id.twitch.login ? `/${id.twitch.login}` : ''}</a></>
            )}
          </div>
        ) : (
          <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="identity" /></div>
        )}
        {/* Phase 7: the two legacy profile actions that were modals/overlays
          * (compare.js, wrapped.js) are routes now — linkable, no overlay. */}
        <div style={{ marginTop: 'var(--space-3)', display: 'flex', gap: 'var(--space-4)' }}>
          <ActLink to={`/compare/${encodeURIComponent(id.guid ?? p.guid)}`}>compare →</ActLink>
          <ActLink to={`/profile/${encodeURIComponent(id.guid ?? p.guid)}/wrapped`}>wrapped →</ActLink>
        </div>
      </div>
      {/* An unrated player gets {available:false, reason:"not rated"} — the
        * rating area must say that, not vanish (Codex, #822 wave 4): a
        * missing panel and a missing rating are different facts. */}
      {!(skill.available && skill.et_rating != null) && (
        <div style={{ textAlign: 'right' }}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>et rating</Lbl>
          <div className="m" style={{ fontSize: 'var(--fs-value)', color: 'var(--color-text-500)', marginTop: 'var(--space-2)' }}>
            {/* Same split: only `reason` separates "this player has no
              * rating" from "the rating query failed". */}
            {skill.reason === 'error' ? 'unavailable' : 'not rated yet'}
          </div>
        </div>
      )}
      {skill.available && skill.et_rating != null && (
        <div style={{ textAlign: 'right' }}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>et rating</Lbl>
          <div className="m" style={{ fontSize: 'var(--fs-display-lg)', lineHeight: 0.9, color: 'var(--color-accent)' }}>
            {skill.et_rating.toFixed(3)}
          </div>
          <div className="m" style={{ fontSize: 'var(--fs-label)', color: 'var(--color-text-400)', marginTop: 'var(--space-1)' }}>
            {skill.tier ?? '—'}
            {skill.rank != null && skill.total_rated != null && ` · #${skill.rank} of ${skill.total_rated}`}
            {skill.percentile != null && ` · top ${(100 - skill.percentile).toFixed(1)}%`}
          </div>
        </div>
      )}
    </div>
  );
}

function Lifetime({ p }: { p: Profile }) {
  const l = p.lifetime;
  if (!l.available) return null;
  const dpm = l.time_played_seconds > 0 ? (l.damage_given / (l.time_played_seconds / 60)) : null;
  const cells: [string, string][] = [
    ['rounds', figure(l.rounds)],
    ['w — l', `${figure(l.wins)} — ${figure(l.losses)}`],
    ['win rate', pct(l.win_rate)],
    ['k / d', `${figure(l.kills)} / ${figure(l.deaths)}`],
    ['k:d', l.kd.toFixed(2)],
    ['dpm', dpm == null ? '—' : dpm.toFixed(0)],
    ['gibs', figure(l.gibs)],
    ['hs kills', figure(l.headshot_kills)],
    ['played', hours(l.time_played_seconds)],
  ];
  // The long tail: what the server counts and the legacy profile drew
  // (player-profile.js:1178-1192). "Capture everything" shows it; the
  // display tiers of doc 19 decide later what folds away.
  const tail: [string, string][] = [
    ['objectives', `${figure(l.objectives_stolen)} stolen · ${figure(l.objectives_returned)} returned`],
    ['objectives · more', `${figure(l.objectives_completed)} completed · ${figure(l.objectives_destroyed)} destroyed`],
    ['dynamite', `${figure(l.dynamites_planted)} planted · ${figure(l.dynamites_defused)} defused`],
    ['multi-kills', `${figure(l.double_kills)} · ${figure(l.triple_kills)} · ${figure(l.quad_kills)} · ${figure(l.multi_kills)} · ${figure(l.mega_kills)}`],
    ['best spree', figure(l.best_killing_spree)],
    ['useful kills', figure(l.useful_kills)],
    ['assists', figure(l.kill_assists)],
    ['revives', `${figure(l.revives_given)} given · ${figure(l.times_revived)} received`],
    ['self kills', figure(l.self_kills)],
    ['team kills', `${figure(l.team_kills)} · ${figure(l.team_damage_given)} team dmg`],
    ['damage', `${figure(l.damage_given)} given · ${figure(l.damage_received)} taken`],
    ['shots', figure(l.shots)],
    ['hours', l.hours_played == null ? '—' : figure(Math.round(l.hours_played))],
    ['xp', figure(l.xp)],
    ['head hits', figure(l.headshots)],
  ];
  return (
    <>
      <div data-parity="profile.lifetime" className="about-grid-5" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
        {cells.map(([k, v]) => (
          <div key={k}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{k}</Lbl>
            <div className="m" style={{ fontSize: 'var(--fs-row-lg)', marginTop: 'var(--space-1)' }}>{v}</div>
          </div>
        ))}
      </div>
      <div data-parity="profile.lifetime-tail" className="about-grid-5" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-4)' }}>
        {tail.map(([k, v]) => (
          <div key={k}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{k}</Lbl>
            <div className="m" style={{ fontSize: 'var(--fs-small)', marginTop: 'var(--space-1)' }}>{v}</div>
          </div>
        ))}
      </div>
    </>
  );
}

function Streaks({ p }: { p: Profile }) {
  const s = p.streaks;
  const onLoss = s.current_type === 'L';
  if (!s.available) {
    // A failed subquery and an undecided record both arrive as
    // available:false — only `reason` tells them apart, and calling an
    // error "no decided rounds yet" would state a player fact we do not
    // have (Codex, #822 wave 6).
    const failed = s.reason === 'error';
    return (
      <div data-parity="profile.streaks" style={{ marginTop: 'var(--space-6)' }}>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>current run</Lbl>
        <span style={{ marginLeft: 'var(--space-2)' }}>
          {failed
            ? <Unavailable what="streaks" />
            : <Absent reason="no decided rounds yet" />}
        </span>
      </div>
    );
  }
  return (
    <div data-parity="profile.streaks" style={{ marginTop: 'var(--space-6)', display: 'flex', gap: 'var(--space-6)', alignItems: 'baseline', flexWrap: 'wrap' }}>
      <span>
        <Lbl style={{ fontSize: 'var(--fs-caption)' }}>current run</Lbl>
        <span className="m" style={{ fontSize: 'var(--fs-row)', marginLeft: 'var(--space-2)', color: onLoss ? 'var(--color-neg)' : 'var(--color-pos)' }}>
          {s.current_streak} {s.current_type ?? ''}
        </span>
      </span>
      <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-400)' }}>
        longest win {s.longest_win} · longest loss {s.longest_loss}
      </span>
    </div>
  );
}

function Weapons({ rows, available, totals }: { rows: ProfileWeaponRow[] | undefined; available: boolean; totals?: { total_shots?: number; total_hits?: number; overall_accuracy?: number | null; overall_hs_accuracy?: number | null } }) {
  // An unavailable section carries no list at all — read defensively, then
  // let SectionBody name the state (Codex, #822).
  const top = [...(rows ?? [])].sort((a, b) => b.kills - a.kills).slice(0, 8);
  return (
    <div data-parity="profile.weapons" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="weapons · top eight by kills" aside={<Lbl style={{ fontSize: 'var(--fs-caption)' }}>head hits, not headshot kills{totals?.total_shots != null && <> · {figure(totals.total_hits ?? 0)} of {figure(totals.total_shots)} shots hit</>}{totals?.overall_accuracy != null && <> · {pct(totals.overall_accuracy)} overall, {pct(totals.overall_hs_accuracy)} to the head</>}</Lbl>} />
      <SectionBody available={available} empty={top.length === 0} what="weapon stats">
        <div style={{ marginTop: 'var(--space-2)' }}>
          <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto auto', gap: 'var(--space-3)', padding: 'var(--space-2) 0' }}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>weapon</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>kills</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>deaths</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>acc</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>head hits</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>hs rate</Lbl>
          </div>
          {top.map((w) => (
            <div key={w.weapon} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto auto', gap: 'var(--space-3)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
              <span style={{ fontSize: 'var(--fs-value)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{w.weapon}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right' }}>{figure(w.kills)}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{figure(w.deaths)}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{pct(w.accuracy)}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{figure(w.headshots)}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right', color: 'var(--color-text-400)' }}>{pct(w.hs_accuracy)}</span>
            </div>
          ))}
        </div>
      </SectionBody>
    </div>
  );
}

function Body({ p }: { p: Profile }) {
  const t = p.hit_regions.totals;
  const m = p.movement;
  const stance = m.stance;
  return (
    <div className="landing-split" style={{ gap: 'var(--space-6)', marginTop: 'var(--space-6)' }}>
      <div data-parity="profile.hit-regions">
        <SectionHead label="where the hits land" />
        <SectionBody available={p.hit_regions.available} empty={t == null} what="hit regions">
          {t && (
            <>
              <div style={{ display: 'flex', height: 6, marginTop: 'var(--space-2)' }}>
                {([['head', t.head_pct, 'var(--color-accent)'], ['arms', t.arms_pct, '#6b7f92'],
                  ['body', t.body_pct, 'var(--color-accent-warm)'], ['legs', t.legs_pct, '#7a6a52']] as const)
                  .map(([k, v, c]) => <span key={k} style={{ width: `${v}%`, background: c, display: 'block' }} />)}
              </div>
              <div className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)', marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                <span>head {pct(t.head_pct)}</span>
                <span>arms {pct(t.arms_pct)}</span>
                <span>body {pct(t.body_pct)}</span>
                <span>legs {pct(t.legs_pct)}</span>
              </div>
              {/* Per weapon: head share is the server's, the rest derived from the counts. */}
              {(p.hit_regions.per_weapon ?? []).slice(0, 6).map((w) => (
                <div key={w.weapon} className="m" style={{ ...rowStyle, display: 'flex', justifyContent: 'space-between', gap: 'var(--space-3)', fontSize: 'var(--fs-micro)', color: 'var(--color-text-400)', padding: 'var(--space-1) 0' }}>
                  <span style={{ textTransform: 'uppercase' }}>{w.weapon}</span>
                  <span>
                    head {pct(w.head_pct)} · arms {pct(w.total ? (w.arms / w.total) * 100 : null)} · body {pct(w.total ? (w.body / w.total) * 100 : null)} · legs {pct(w.total ? (w.legs / w.total) * 100 : null)} · {figure(w.total)} hits
                  </span>
                </div>
              ))}
            </>
          )}
        </SectionBody>
      </div>
      <div data-parity="profile.movement">
        <SectionHead label="how they move" />
        <SectionBody available={m.available} empty={!m.tracks} what="movement">
          <div className="home-cols3" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            {([['avg speed', num(m.avg_speed)], ['peak', num(m.peak_speed)], ['sprint', pct(m.sprint_pct)],
              ['sprinting', m.sprint_sec == null ? '—' : `${decimals(m.sprint_sec / 3600, 1)} h`],
              ['dist / life', num(m.avg_distance_per_life)], ['after spawn', num(m.avg_post_spawn_distance)],
              ['standing', pct(stance?.standing_pct)], ['crouching', pct(stance?.crouching_pct)]] as const)
              .map(([k, v]) => (
                <div key={k}>
                  <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{k}</Lbl>
                  <div className="m" style={{ fontSize: 'var(--fs-value)', marginTop: 'var(--space-1)' }}>{v}</div>
                </div>
              ))}
          </div>
        </SectionBody>
      </div>
    </div>
  );
}

/** Each list leads with the number it is SORTED by (nemeses by kills on the
 * player, victims by kills the player made) — the backend sorts the same
 * pairs two different ways, so a shared top name is normal; printing the
 * pair in one fixed order made the two columns look like the same list. */
function OpponentList({ title, rows, note, lead }: {
  title: string; rows: ProfileOpponent[]; note: string; lead: 'on' | 'by';
}) {
  return (
    <div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{title}</Lbl>
      <div style={{ marginTop: 'var(--space-2)' }}>
        {rows.slice(0, 5).map((o) => (
          <div key={o.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto', gap: 'var(--space-2)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
            <span className="m" style={{ fontSize: 'var(--fs-small)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.name}</span>
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-200)' }}>
              {lead === 'on' ? o.kills_on_player : o.kills_by_player}
            </span>
            <span className="m" style={{ fontSize: 'var(--fs-label)', color: 'var(--color-text-500)' }}>
              of {o.total_encounters}
            </span>
          </div>
        ))}
      </div>
      <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-1)' }}>{note}</Lbl>
    </div>
  );
}

/** Leads with SYNERGY — the DPM delta the backend sorts these lists by
 * (players_profile_router:516). Showing only the win rate made the visible
 * number disagree with the order whenever the two diverge (Codex, #822);
 * win rate stays, as the second figure. */
/** A duel: win rate of the pairing first (what the list is sorted by), then
 *  the two kill counts and the classification the server gave. */
function DuelList({ title, rows }: { title: string; rows: ProfileOpponent[] }) {
  return (
    <div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{title}</Lbl>
      <Stack gap={1} style={{ marginTop: 'var(--space-2)' }}>
        {rows.slice(0, 5).map((o) => (
          <Cluster key={o.guid} gap={2} justify="between" align="baseline" style={rowStyle}>
            <span className="m" style={{ fontSize: 'var(--fs-small)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{stripEtColors(o.name)}</span>
            <Cluster gap={2} align="baseline">
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-200)' }}>{o.win_rate == null ? '—' : `${Math.round(o.win_rate * 100)} %`}</span>
              <Meta>{figure(o.kills_by_player)}–{figure(o.kills_on_player)}{o.classification ? ` · ${o.classification.toLowerCase()}` : ''}</Meta>
            </Cluster>
          </Cluster>
        ))}
      </Stack>
      <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-1)' }}>win rate of the duel · kills by – on</Lbl>
    </div>
  );
}

function MateList({ title, rows }: { title: string; rows: ProfileTeammate[] }) {
  return (
    <div>
      <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{title}</Lbl>
      <div style={{ marginTop: 'var(--space-2)' }}>
        {rows.slice(0, 5).map((t) => (
          <div key={t.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto', gap: 'var(--space-2)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
            <span className="m" style={{ fontSize: 'var(--fs-small)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</span>
            <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-200)' }}>
              {t.synergy == null ? '—' : `${t.synergy > 0 ? '+' : ''}${t.synergy.toFixed(0)}`}
            </span>
            <span className="m" style={{ fontSize: 'var(--fs-label)', color: 'var(--color-text-500)' }}>
              {t.rounds_together} rd · {pct(t.win_rate_with)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Relationships({ p }: { p: Profile }) {
  const r = p.relationships;
  const killers = r.top_killers ?? [];
  const victims = r.top_victims ?? [];
  const best = r.best_teammates ?? [];
  const worst = r.worst_teammates ?? [];
  const empty = killers.length === 0 && best.length === 0;
  return (
    <div data-parity="profile.relationships" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="the people" aside={<Lbl style={{ fontSize: 'var(--fs-caption)' }}>the leading figure is what each list ranks by · synergy = dpm delta together{r.baseline_dpm != null && ` against a ${figure(r.baseline_dpm)} dpm baseline`}</Lbl>} />
      <SectionBody available={r.available} empty={empty} what="head-to-head history">
        <div className="about-grid-4" style={{ gap: 'var(--space-5)', marginTop: 'var(--space-2)' }}>
          {/* Measured at the source (rivalries_service): kills_by_player comes
            * from the player-as-killer query, kills_on_player from the
            * player-as-victim one. So the nemesis figure is what THEY did to
            * this player, and the victim figure is what this player did to
            * them — my first wording had both actors backwards (Codex). */}
          <OpponentList title="nemeses" rows={killers} note="their kills on this player" lead="on" />
          <OpponentList title="victims" rows={victims} note="this player's kills on them" lead="by" />
          <MateList title="best alongside" rows={best} />
          <MateList title="worst alongside" rows={worst} />
        </div>
        {/* The duel lists the legacy profile had (player-profile.js:1350): ranked
          * by the win rate of the pairing, not by a count — a rival is someone
          * this player LOSES to more often than not. */}
        {((r.hardest_opponents?.length ?? 0) > 0 || (r.easiest_opponents?.length ?? 0) > 0) && (
          <div className="about-grid-4" style={{ gap: 'var(--space-5)', marginTop: 'var(--space-4)' }}>
            <DuelList title="hardest duels" rows={r.hardest_opponents ?? []} />
            <DuelList title="easiest duels" rows={r.easiest_opponents ?? []} />
          </div>
        )}
      </SectionBody>
    </div>
  );
}

/** The names behind the guid — the legacy profile's "known as" table,
 *  never carried over (audit 2026-09-07). */
function NickHistory({ p }: { p: Profile }) {
  const names = [...(p.nick_history?.names ?? [])].sort((a, b) => b.uses - a.uses);
  return (
    <div data-parity="profile.nick-history" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="known as" aside={names.length > 1 ? <span className="lbl">{figure(names.length)} names</span> : undefined} />
      <SectionBody available={p.nick_history?.available ?? false} empty={names.length === 0} what="name history">
        <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
          {names.map((n) => (
            <Cluster key={n.name} gap={4} justify="between" align="baseline" className="row" style={rowStyle}>
              {/* One text node: the header already shows the current name on
                * its own, and a second bare "vid" would be two answers to
                * "where is the name" for a reader and a test alike. */}
              <span style={{ fontSize: 'var(--fs-row)' }}>{`${stripEtColors(n.name)} · ${figure(n.uses)} rounds`}</span>
              <Meta>{n.first_seen ?? '?'} → {n.last_seen ?? '?'}</Meta>
            </Cluster>
          ))}
        </Stack>
      </SectionBody>
    </div>
  );
}

/** Gathers as a record with the running streak (legacy player-profile.js:1379). */
function GatherSummary({ p }: { p: Profile }) {
  const g = p.gather_summary;
  return (
    <div data-parity="profile.gathers" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="gathers" aside={g?.available && g.gathers > 0 ? <span className="lbl">{figure(g.gathers)} played</span> : undefined} />
      <SectionBody available={g?.available ?? false} empty={!g || g.gathers === 0} what="gathers">
        {g && (
          <Cluster gap={5} align="baseline" style={{ flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
            <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{figure(g.wins)}–{figure(g.losses)}{g.draws > 0 && <>–{figure(g.draws)}</>}</span>
            <Meta>w–l{g.draws > 0 ? '–d' : ''}</Meta>
            {g.win_rate != null && <Meta>{figure(g.win_rate)} % won</Meta>}
            {g.current_streak > 0 && g.current_type && <Meta>streak {figure(g.current_streak)}{g.current_type}</Meta>}
            <Meta>longest {figure(g.longest_win)}W · {figure(g.longest_loss)}L</Meta>
          </Cluster>
        )}
      </SectionBody>
    </div>
  );
}

/** Median time to kill and median return fire — the legacy "combat
 *  timing" panel (player-profile.js:963), with the sample each number rests
 *  on, because a median of eleven is not a median of eleven thousand. */
function CombatTiming({ p }: { p: Profile }) {
  const c = p.combat_timing;
  const ttk = c?.time_to_kill ?? null;
  const rf = c?.return_fire ?? null;
  const secs = (ms: number | null | undefined) => (ms == null ? '—' : `${(ms / 1000).toFixed(2)} s`);
  return (
    <div data-parity="profile.combat-timing" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="combat timing" aside={<span className="lbl">medians · engagement clock</span>} />
      <SectionBody available={c?.available ?? false} empty={ttk == null && rf == null} what="combat timing">
        <Cluster gap={6} align="baseline" style={{ flexWrap: 'wrap', marginTop: 'var(--space-2)' }}>
          <Stack gap={1}>
            <Lbl>time to kill</Lbl>
            <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{secs(ttk?.median_ms)}</span>
            {ttk && <Meta>over {figure(ttk.kills)} kills</Meta>}
          </Stack>
          <Stack gap={1}>
            <Lbl>return fire</Lbl>
            <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{secs(rf?.median_ms)}</span>
            {rf && <Meta>{figure(rf.samples)} samples{rf.coverage_pct != null && <> · covers {figure(rf.coverage_pct)} % of deaths</>}</Meta>}
          </Stack>
        </Cluster>
      </SectionBody>
    </div>
  );
}

function Maps({ rows, available }: { rows: ProfileMapRow[] | undefined; available: boolean }) {
  const top = [...(rows ?? [])].sort((a, b) => b.rounds - a.rounds).slice(0, 8);
  return (
    <div data-parity="profile.maps" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="grounds · most played" />
      <SectionBody available={available} empty={top.length === 0} what="map history">
        <div style={{ marginTop: 'var(--space-2)' }}>
          {top.map((m) => (
            <div key={m.map} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 'var(--space-3)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
              <span style={{ fontSize: 'var(--fs-value)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{mapLabel(m.map)}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{m.rounds} rd</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{pct(m.win_rate)}</span>
              {/* kd was on the wire and off the panel — the legacy profile's
                * map table carries all five columns, and the keymap can only
                * point here once this one does too (Codex on #855, round
                * four). */}
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{m.kd == null ? '—' : m.kd.toFixed(2)} kd</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>{m.dpm == null ? '—' : m.dpm.toFixed(0)} dpm</span>
            </div>
          ))}
        </div>
      </SectionBody>
    </div>
  );
}

function Recent({ rows: raw, available }: { rows: ProfileMatchRow[] | undefined; available: boolean }) {
  const rows = raw ?? [];
  return (
    <div data-parity="profile.recent" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="last rounds" aside={<Lbl style={{ fontSize: 'var(--fs-caption)' }}>newest first</Lbl>} />
      <SectionBody available={available} empty={rows.length === 0} what="recent rounds">
        <div style={{ marginTop: 'var(--space-2)' }}>
          {rows.map((r) => (
            <div key={r.round_id} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'auto minmax(0,1fr) auto auto auto', gap: 'var(--space-3)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
              <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)' }}>{r.date}</span>
              <span style={{ fontSize: 'var(--fs-value)', letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {mapLabel(r.map)} R{r.round_number}
              </span>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>{r.kills}/{r.deaths}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)' }}>{r.dpm == null ? '—' : r.dpm.toFixed(0)} dpm</span>
              {/* A round with no attributed winner shows a dash — never a loss. */}
              <span className="m" style={{ fontSize: 'var(--fs-small)', color: r.result === 'W' ? 'var(--color-pos)' : r.result === 'L' ? 'var(--color-neg)' : 'var(--color-text-500)' }}>
                {r.result ?? '—'}
              </span>
            </div>
          ))}
        </div>
      </SectionBody>
    </div>
  );
}

/** ET Rating v2.1 components — the arithmetic behind the number Header
 * already shows. The profile endpoint carries the rating; only
 * /api/skill/player carries HOW it was assembled (raw, weight, percentile,
 * contribution per component), so this panel quotes that endpoint and
 * labels the rating it repeats as the same number, not a second opinion.
 * "Not rated" arrives as {status:'error'} inside a 200 — a fact about the
 * player (needs 5+ rounds), rendered as one, never as a failure. */
/** Δ as the server means it: null is "no comparison", zero is "no change",
 *  and the two must not render the same. Legacy printed nothing for null
 *  (player-profile.js:698-709) rather than "—% vs 100%". */
function Delta({ pct }: { pct: number | null }) {
  if (pct == null) return <Meta>no baseline yet</Meta>;
  if (pct === 0) return <Meta>±0%</Meta>;
  const up = pct > 0;
  return (
    <span className="m" style={{ fontSize: 'var(--fs-micro)', color: up ? 'var(--color-pos)' : 'var(--color-neg)' }}>
      {up ? '▲ +' : '▼ '}{Math.abs(pct)}%
    </span>
  );
}

function Spark({ values, w = 110, h = 26 }: { values: number[]; w?: number; h?: number }) {
  const d = sparkPathRanged(values, w, h, 2);
  // Fewer than two points is not a trend. Saying so beats an empty box the
  // reader has to interpret.
  if (d === '') return <Meta>one session so far</Meta>;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label="trend" style={{ display: 'block' }}>
      <path d={d} fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />
    </svg>
  );
}

/** The memory card — a career keepsake, measured against this player's own
 *  past (legacy loadMemoryCard, player-profile.js:812).
 *
 *  ⚠️ Two of its facts share their names with WRAPPED cards and are not the
 *  same numbers: wrapped's are per season (signature = most played with a
 *  win %, best round = best DPM), these are career (signature = biggest lift
 *  over the player's own average, best round = most kills). Measured before
 *  writing, because the names alone say "already covered".
 *
 *  ⛔ Legacy renders NOTHING on failure — "optional keepsake, never block the
 *  profile". The new convention says a missing thing names itself, so a 404
 *  becomes a reason, not a silence: a keepsake that vanishes without a word is
 *  indistinguishable from one that broke. */
/** The hover card the legacy player list showed on mouse-over
 *  (player-card.js): the rating and its trend, the archetype, the 90-day
 *  form with percentiles against the pool, a dpm sparkline, the badges and
 *  the career totals. Five of its fields were on the endpoint ratchet. */
function PlayerCardSection({ playerId }: { playerId: string }) {
  const q = usePlayerCard(playerId);
  // The endpoint answers 404 for a profile with no valid round in the window
  // — a known absence, not a failed request (Codex on #1001).
  if (q.isError && q.error instanceof ApiError && q.error.status === 404) {
    return (
      <Stack gap={2} parity="profile.card">
        <SectionHead label="player card" />
        <Absent reason="no card — no counted round in the last 90 days" />
      </Stack>
    );
  }
  return (
    <Panel<PlayerCard>
      parity="profile.card"
      label="player card"
      aside={q.data ? `${figure(q.data.window_days)}-day form${q.data.small_sample ? ' · small sample' : ''}` : undefined}
      q={q}
      empty="no card yet — the card needs rated rounds behind it"
      isEmpty={(d) => d.form.rounds === 0 && d.career.kills === 0}
    >
      {(d) => (
        <Stack gap={2}>
          <Cluster gap={5} align="baseline" style={{ flexWrap: 'wrap' }}>
            {d.rating?.value != null ? (
              <span className="m" style={{ fontSize: 'var(--fs-value)' }}>
                rating {d.rating.value.toFixed(3)} <Meta>{d.rating.tier ?? '—'} · trend {d.rating.trend ?? '—'} · {figure(d.rating.games_rated ?? 0)} rated</Meta>
              </span>
            ) : <Meta>not rated yet</Meta>}
            {d.archetype && <Meta>archetype {d.archetype.replace(/_/g, ' ')}</Meta>}
            <Meta>career {figure(d.career.kills)} kills · {figure(d.career.sessions)} sessions</Meta>
          </Cluster>
          <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
            {([['kills', d.form.kills], ['deaths', d.form.deaths], ['k/d', d.form.kd], ['dpm', d.form.dpm], ['revives', d.form.revives], ['hs %', d.form.headshot_pct], ['dead %', d.form.time_dead_pct], ['rounds', d.form.rounds]] as [string, number][]).map(([k, v]) => (
              <span key={k} style={{ fontSize: 'var(--fs-small)' }}><Meta>{k} </Meta>{figure(v)}</span>
            ))}
          </Cluster>
          <Cluster gap={4} align="baseline" style={{ flexWrap: 'wrap' }}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>percentile in the pool</Lbl>
            {/* The endpoint ranks revives per ROUND (revives / rounds against
              * the pool) while the form row above shows the window's total —
              * one name, two measurements, so the label says which. */}
            {Object.entries(d.percentiles).map(([k, v]) => (
              <span key={k} style={{ fontSize: 'var(--fs-small)' }}><Meta>{k === 'revives' ? 'revives/round' : k} </Meta>{v == null ? <Meta>withheld</Meta> : figure(v)}</span>
            ))}
            {d.small_sample && <Meta>percentiles withheld under 10 rounds in the window</Meta>}
            <Meta>a different pool and window than the rating components — the two do not agree, on purpose</Meta>
          </Cluster>
          {d.sparkline_dpm.length >= 2 && (
            <Cluster gap={3} align="baseline">
              <Lbl style={{ fontSize: 'var(--fs-caption)' }}>dpm, last {figure(d.sparkline_dpm.length)} sessions</Lbl>
              <Spark values={d.sparkline_dpm} />
            </Cluster>
          )}
          {d.badges.length > 0 && (
            <Cluster gap={3} align="baseline" style={{ flexWrap: 'wrap' }}>
              {d.badges.map((b) => (
                <span key={`${b.type}-${String(b.threshold)}`} title={`${b.type} ≥ ${figure(b.threshold)}`} style={{ fontSize: 'var(--fs-small)' }}>
                  {b.emoji} {b.title}
                </span>
              ))}
            </Cluster>
          )}
        </Stack>
      )}
    </Panel>
  );
}

function MemoryCardSection({ playerId }: { playerId: string }) {
  const card = useMemoryCard(playerId);
  const facts = card.data?.facts ?? [];
  return (
    <div data-parity="profile.memory-card" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="memory card" />
      <Meta>a keepsake of your slomix history — measured against your own past, never a ladder</Meta>
      {card.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="memory card" /></div>}
      {card.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="memory card" /></div>}
      {card.data != null && (card.data.nights != null || card.data.playing_since != null || card.data.signature_map != null) && (
        <Meta>
          {card.data.nights != null ? `${figure(card.data.nights)} nights` : ''}
          {card.data.playing_since ? ` · playing since ${card.data.playing_since}` : ''}
          {card.data.signature_map ? ` · signature map ${card.data.signature_map.map_name} (${figure(card.data.signature_map.rounds)} rounds, ${card.data.signature_map.lift_pct >= 0 ? '+' : ''}${figure(card.data.signature_map.lift_pct)}% over your own average)` : ''}
        </Meta>
      )}
      {card.data != null && facts.length === 0 && (
        <div style={{ marginTop: 'var(--space-2)' }}><Absent reason="nothing to keep yet — the card needs rounds behind it" /></div>
      )}
      {facts.length > 0 && (
        <Stack gap={1} className="rows" style={{ marginTop: 'var(--space-2)' }}>
          {facts.map((f) => (
            <Cluster key={f.key} gap={4} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
              <Lbl>{f.label}</Lbl>
              <Cluster gap={3} align="baseline">
                <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{f.value}</span>
                {f.sub != null && f.sub !== '' && <Meta>{f.sub}</Meta>}
              </Cluster>
            </Cluster>
          ))}
        </Stack>
      )}
    </div>
  );
}

/** "Your form" — the last session against this player's OWN recent average
 *  (legacy loadPlayerForm, player-profile.js:696). Rank-vs-self, and the page
 *  prints the server's own `baseline_desc` so nobody reads it as a ladder. */
function PlayerForm({ playerId }: { playerId: string }) {
  const form = useSkillPlayerForm(playerId);
  const d = form.data;
  const comp = d?.composite;
  return (
    <div data-parity="profile.form" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="your form" />
      {form.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="form" /></div>}
      {form.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="form" /></div>}
      {d != null && comp == null && (
        <div style={{ marginTop: 'var(--space-2)' }}><Absent reason="no form yet — it needs a session to compare against" /></div>
      )}
      {d != null && comp != null && (
        <Stack gap={2} style={{ marginTop: 'var(--space-2)' }}>
          <Cluster gap={5} align="baseline" style={{ flexWrap: 'wrap' }}>
            <span className="m" style={{ fontSize: 'var(--fs-value)' }}>{comp.latest ?? '—'}</span>
            <Delta pct={comp.delta_pct} />
            <Spark values={comp.series} />
            {d.session_date != null && <Meta>last session {d.session_date}</Meta>}
            {comp.is_new && <Meta>new to the form window — no earlier baseline to compare against</Meta>}
            {d.form_weights && <Meta>form weights: {Object.entries(d.form_weights).map(([k, v]) => `${k} ${figure(v)}`).join(' · ')}</Meta>}
          </Cluster>
          {/* The server's sentence, not a paraphrase of it. */}
          {d.baseline_desc != null && <Meta>{d.baseline_desc}</Meta>}
          <Stack gap={1} className="rows">
            {comp.breakdown.map((b) => (
              <Cluster key={b.metric} gap={4} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
                <Lbl>{b.label}</Lbl>
                <Cluster gap={4} align="baseline">
                  {/* ⭐ The per-metric SERIES, which this page already had and
                    * was not drawing. `/api/skill/player/{guid}/form` returns a
                    * `metrics` block alongside `composite`, and the page read
                    * only the composite — so the DPM and K/D curves arrived on
                    * every load and went nowhere.
                    *
                    * Measured against `/api/stats/player/{name}/form`, whose
                    * ratchet line this does NOT close: the last eleven points
                    * agree to rounding (275.36 / 257.69 / 265.57 … against
                    * 275.4 / 257.7 / 265.6 …). What only that endpoint has is
                    * a date per point, rounds per session, an average line and
                    * a 6-session trend — so the line stays, and this draws the
                    * shape we were already paying for. */}
                  {d.metrics[b.metric] != null && d.metrics[b.metric].series.length > 1 && (
                    <Spark values={d.metrics[b.metric].series} w={72} h={18} />
                  )}
                  <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{b.latest ?? '—'}</span>
                  <Meta>vs {b.baseline ?? '—'}</Meta>
                  <Delta pct={b.delta_pct} />
                </Cluster>
              </Cluster>
            ))}
          </Stack>
        </Stack>
      )}
    </div>
  );
}

/** The server's trend word, spelled for the reader — a switch, not a lookup
 *  table indexed by the value (the scanners here flag computed keys). */
function trendWord(trend: PlayerSessionForm['trend']): string {
  switch (trend) {
    case 'improving': return 'improving';
    case 'declining': return 'declining';
    case 'stable': return 'stable';
    default: return 'fewer than six sessions, no trend yet';
  }
}

/** Session-by-session DPM: one point per gaming session, a date under each,
 *  the average and the six-session trend the server computed (legacy
 *  loadPlayerForm, player-profile.js). Drawn with the shared frame from
 *  components/Panel.tsx — the first non-proximity panel to use it. */
function SessionForm({ playerId }: { playerId: string }) {
  const q = usePlayerSessionForm(playerId);
  return (
    <div data-parity="profile.session-form" style={{ marginTop: 'var(--space-6)' }}>
      <Panel<PlayerSessionForm>
        label="form by session"
        aside={q.data != null && q.data.sessions.length > 0 ? `avg ${figure(q.data.avg_dpm)} dpm` : undefined}
        q={q}
        empty="no gaming session with more than two minutes played"
        isEmpty={(d) => d.sessions.length === 0}
      >
        {(d) => (
          <Stack gap={2}>
            <Cluster gap={5} align="baseline" style={{ flexWrap: 'wrap' }}>
              <Spark values={d.sessions.map((s) => s.dpm)} />
              <Meta>{trendWord(d.trend)}</Meta>
              <Meta>{d.sessions.length} sessions</Meta>
            </Cluster>
            <Stack gap={1} className="rows">
              {d.sessions.slice(-5).reverse().map((s) => (
                <Cluster key={s.date} gap={4} justify="between" align="baseline" className="row" style={rowStyle}>
                  <span style={{ fontSize: 'var(--fs-row)' }}>{s.date}</span>
                  <Cluster gap={4} align="baseline">
                    <Meta>{s.rounds} rounds</Meta>
                    <Meta>k/d {figure(s.kd)}</Meta>
                    <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{figure(s.dpm)} dpm</span>
                  </Cluster>
                </Cluster>
              ))}
            </Stack>
          </Stack>
        )}
      </Panel>
    </div>
  );
}

/** The last thirty counted halves as one curve, with the map under the
 *  newest five — the grain below SessionForm. Legacy drew this on a canvas
 *  sparkline (player-profile.js loadRecentRounds); here it is the same
 *  <Spark> the rating card uses. */
function RoundsSeries({ playerId }: { playerId: string }) {
  const q = usePlayerRoundsSeries(playerId);
  return (
    <div data-parity="profile.rounds-series" style={{ marginTop: 'var(--space-6)' }}>
      <Panel<PlayerRoundsSeries>
        label="round by round"
        aside={q.data != null && q.data.rounds.length > 0 ? `avg ${figure(q.data.avg_dpm)} dpm · ${q.data.rounds.length} halves` : undefined}
        q={q}
        empty="no counted half with more than a minute played"
        isEmpty={(d) => d.rounds.length === 0}
      >
        {(d) => (
          <Stack gap={2}>
            <Spark values={d.rounds.map((r) => r.dpm)} w={220} h={32} />
            <Stack gap={1} className="rows">
              {d.rounds.slice(-5).reverse().map((r, i) => (
                <Cluster key={`${r.date}:${r.label}:${i}`} gap={4} justify="between" align="baseline" className="row" style={rowStyle}>
                  <Cluster gap={3} align="baseline">
                    <span style={{ fontSize: 'var(--fs-row)' }}>{r.label}</span>
                    <Meta>{r.date}</Meta>
                  </Cluster>
                  <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{figure(r.dpm)} dpm</span>
                </Cluster>
              ))}
            </Stack>
          </Stack>
        )}
      </Panel>
    </div>
  );
}

/** The rating over recent sessions — the trend behind the header's single
 *  number (legacy loadCareerHistory, player-profile.js:772). */
function RatingHistory({ playerId }: { playerId: string }) {
  const hist = useSkillPlayerHistory(playerId);
  const sessions = hist.data?.sessions ?? [];
  const rated = sessions.filter((s) => s.cumulative_rating != null);
  return (
    <div data-parity="profile.rating-history" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="rating over time" aside={hist.data != null ? <span className="lbl">{figure(hist.data.total_sessions)} sessions · {hist.data.range_days}d</span> : undefined} />
      {hist.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="rating history" /></div>}
      {hist.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="rating history" /></div>}
      {hist.data != null && rated.length === 0 && (
        <div style={{ marginTop: 'var(--space-2)' }}><Absent reason="no rated sessions in this window" /></div>
      )}
      {rated.length > 0 && (
        <Stack gap={2} style={{ marginTop: 'var(--space-2)' }}>
          <Spark values={rated.map((s) => s.cumulative_rating as number)} w={320} h={44} />
          <Stack gap={1} className="rows">
            {/* Newest first: the last night is the one being asked about. */}
            {[...rated].reverse().slice(0, 10).map((s) => (
              <Cluster key={s.session_date} gap={4} justify="between" align="baseline" className="row" style={{ padding: 'var(--space-2) 0', flexWrap: 'wrap' }}>
                <Lbl>{s.session_date}</Lbl>
                <Cluster gap={4} align="baseline">
                  <Meta>{figure(s.rounds)} rounds · {figure(s.maps)} maps</Meta>
                  {/* That night's own rating, before it is folded into the running figure. */}
                  {s.session_rating != null && <Meta><span title="that session's rating">night {s.session_rating}</span></Meta>}
                  <span className="m" style={{ fontSize: 'var(--fs-row)' }}>{s.cumulative_rating}</span>
                  {/* ⛔ A null delta is the FIRST session, not a flat one. */}
                  {s.delta == null ? <Meta>first</Meta>
                    : <span className="m" style={{ fontSize: 'var(--fs-micro)', color: s.delta > 0 ? 'var(--color-pos)' : s.delta < 0 ? 'var(--color-neg)' : 'var(--color-text-500)' }}>
                        {s.delta > 0 ? '+' : ''}{s.delta}
                      </span>}
                </Cluster>
              </Cluster>
            ))}
          </Stack>
        </Stack>
      )}
    </div>
  );
}

function RatingComponents({ playerId }: { playerId: string }) {
  const skill = useSkillPlayer(playerId);
  return (
    <div data-parity="profile.rating-components" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="rating, taken apart" />
      {skill.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="rating" /></div>}
      {skill.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="rating" /></div>}
      {skill.data && (skill.data.status !== 'ok' ? (
        <Absent block style={{ marginTop: 'var(--space-2)' }} reason={<>{skill.data.detail}</>} />
      ) : (
        <div style={{ marginTop: 'var(--space-2)' }}>
          <Meta style={{ display: 'block', marginBottom: 'var(--space-2)' }}>
            et rating {skill.data.player.et_rating.toFixed(3)} · rank {skill.data.player.rank} of {skill.data.player.total_rated}
            {' · '}<span>{`rated as ${skill.data.player.display_name}${skill.data.player.last_rated_at != null ? `, last ${utcStamp(skill.data.player.last_rated_at)}` : ''}`}</span>
            {/* games_rated STORES rounds (skill_rating_service writes the
              * aggregate's rounds into this column; the skill page labels
              * it rounds) — "games" would overstate the sample ~2x. */}
            {' · '}{skill.data.player.games_rated} rounds rated
            {skill.data.player.confidence != null && <> · confidence {skill.data.player.confidence.toFixed(2)}</>}
          </Meta>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%' }}>
              <thead>
                <tr>
                  {['component', 'raw', 'weight', 'percentile', 'contribution'].map((h) => (
                    <th key={h} style={{ ...lblStyle, fontSize: 'var(--fs-caption)', textAlign: h === 'component' ? 'left' : 'right', padding: 'var(--space-1) var(--space-2)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(skill.data.player.components).map(([name, c]: [string, SkillPlayerComponent]) => (
                  <tr key={name} style={rowStyle}>
                    <td style={{ padding: 'var(--space-1) var(--space-2)' }}>{name.replace(/_/g, ' ')}</td>
                    <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{c.raw.toFixed(2)}</td>
                    <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)', color: c.weight < 0 ? 'var(--color-neg)' : 'var(--color-text-400)' }}>{c.weight.toFixed(2)}</td>
                    <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{pct(c.percentile * 100)}</td>
                    <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)', color: c.contribution < 0 ? 'var(--color-neg)' : 'var(--color-pos)' }}>{c.contribution >= 0 ? '+' : ''}{c.contribution.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

/** Achievement milestones from /api/stats/player — the one block of that
 * endpoint the profile endpoint does not carry (its aliases, identity_link
 * and discord flag all duplicate profile.identity and are deliberately NOT
 * rendered twice). Also quotes the single-round DPM extremes, which no
 * other panel has. */
function Achievements({ playerId }: { playerId: string }) {
  const identity = usePlayerIdentity(playerId);
  return (
    <div data-parity="profile.achievements" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="milestones" />
      {identity.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="milestones" /></div>}
      {identity.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="milestones" /></div>}
      {identity.data && (() => {
        const a = identity.data.achievements;
        return (
          <div style={{ marginTop: 'var(--space-2)' }}>
            {a.unlocked.length === 0 ? (
              <Absent block reason="no milestone reached yet — the first is 100 kills" />
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
                {a.unlocked.map((b) => (
                  <span key={`${b.type}:${b.threshold}`} className="m" style={{ fontSize: 'var(--fs-value)', border: '1px solid var(--color-rule-700)', padding: 'var(--space-1) var(--space-2)', color: 'var(--color-text-300)' }}>
                    {b.emoji} {b.title}
                  </span>
                ))}
              </div>
            )}
            {a.next.map((n) => (
              <Meta key={`${n.type}:${n.threshold}`} style={{ display: 'block', marginTop: 'var(--space-2)' }}>
                next: {n.emoji} {n.title} — {figure(n.current)} of {figure(n.threshold)} ({n.progress.toFixed(0)}%)
              </Meta>
            ))}
            <Meta style={{ display: 'block', marginTop: 'var(--space-2)' }}>
              {a.total_unlocked} of {a.total_possible} milestones
              {identity.data.stats.highest_dpm != null && (
                <> · single-round dpm {figure(identity.data.stats.highest_dpm)} high{identity.data.stats.lowest_dpm != null && <> / {figure(identity.data.stats.lowest_dpm)} low</>}</>
              )}
            </Meta>
          </div>
        );
      })()}
    </div>
  );
}

/** The support-and-punishment columns of the last rounds — headshot kills,
 * gibs, revives given, damage received, accuracy — which the match list
 * above (profile.recent) does not carry. Round identity columns repeat so
 * the reader can line the two tables up; the OVERLAPPING numbers do not. */
function RecentDetail({ playerId }: { playerId: string }) {
  const rounds = usePlayerMatchRounds(playerId, 10);
  return (
    <div data-parity="profile.recent-detail" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="recent rounds · support & punishment" />
      {rounds.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="rounds" /></div>}
      {rounds.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="rounds" /></div>}
      {rounds.data && (rounds.data.length === 0 ? (
        <Absent block style={{ marginTop: 'var(--space-2)' }} reason="no round on record for this player" />
      ) : (
        <div style={{ overflowX: 'auto', marginTop: 'var(--space-2)' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>
                {['date', 'map', 'r', 'side', 'played', 'hs kills', 'gibs', 'revives', 'dmg taken', 'acc'].map((h, i) => (
                  <th key={h} style={{ ...lblStyle, fontSize: 'var(--fs-caption)', textAlign: i < 2 ? 'left' : 'right', padding: 'var(--space-1) var(--space-2)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rounds.data.map((r: PlayerMatchRound) => (
                <tr key={r.round_id} style={rowStyle}>
                  <td className="m" style={{ padding: 'var(--space-1) var(--space-2)', whiteSpace: 'nowrap' }}>{r.round_date.slice(0, 10)}</td>
                  <td style={{ padding: 'var(--space-1) var(--space-2)' }}>
                    {mapLabel(r.map_name)}
                    {/* The wire sends round_status precisely so a cancelled
                      * round does not render like a counted one — it is
                      * absent from every total, and a row with kills but no
                      * explanation reads as a bug (Codex on #855). */}
                    {/* Both halves of "uncounted": a bad status, OR
                      * is_valid FALSE under a completed status — the second
                      * is real (sessions 151/147/146/128/127) and rendered
                      * identically to counted rows until round six. */}
                    {(r.is_valid === false || (r.round_status != null && !['completed', 'substitution'].includes(r.round_status))) && (
                      <span className="m" style={{ fontSize: 'var(--fs-caption)', color: 'var(--color-accent-warm)' }}> · {r.is_valid === false ? 'invalid' : r.round_status} — not counted</span>
                    )}
                  </td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{r.round_number}</td>
                  {/* team is pcs.team, an INTEGER (1 = Axis, 2 = Allies on this
                    * wire); a round played on neither side is a dash, not a
                    * guess. `played` is the minutes behind every rate above. */}
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{r.team === 1 ? 'axis' : r.team === 2 ? 'allies' : '—'}</td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{r.time_played != null ? mmss(r.time_played) : '—'}</td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{figure(r.headshot_kills)}</td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{figure(r.gibs)}</td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{figure(r.revives_given)}</td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{figure(r.damage_received)}</td>
                  <td className="m" style={{ textAlign: 'right', padding: 'var(--space-1) var(--space-2)' }}>{pct(r.accuracy)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

export function PlayerProfilePage() {
  const params = useParams();
  const playerId = params.id ?? '';
  const profile = usePlayerProfile(playerId);
  const p = profile.isError ? undefined : profile.data;
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 980 }}>
      {playerId.length === 0 && (
        <>
          <Lbl>player</Lbl>
          <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
            Pick a player.
          </h1>
          <div className="m" style={{ fontSize: 'var(--fs-small)', color: 'var(--color-text-400)', marginTop: 'var(--space-3)' }}>
            Open a profile from a leaderboard, a lineup or a session.
          </div>
        </>
      )}
      {playerId.length > 0 && profile.isPending && <Pending label="profile" />}
      {playerId.length > 0 && profile.isError && <Unavailable what="profile" />}
      {p && (
        <>
          <Header p={p} />
          <Lifetime p={p} />
          <RatingComponents playerId={playerId} />
          <PlayerCardSection playerId={playerId} />
          <MemoryCardSection playerId={playerId} />
          <PlayerForm playerId={playerId} />
          <RatingHistory playerId={playerId} />
          <SessionForm playerId={playerId} />
          <RoundsSeries playerId={playerId} />
          <Streaks p={p} />
          <Achievements playerId={playerId} />
          <Weapons rows={p.weapons.weapons} available={p.weapons.available} totals={p.weapons} />
          <Body p={p} />
          <Relationships p={p} />
          <GatherSummary p={p} />
          <CombatTiming p={p} />
          <Maps rows={p.maps.maps} available={p.maps.available} />
          <Recent rows={p.recent_matches.matches} available={p.recent_matches.available} />
          <NickHistory p={p} />
          <RecentDetail playerId={playerId} />
          <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-6)' }}>
            {p.sections.length} sections · generated {p.generated_at.slice(0, 19).replace('T', ' ')} utc
          </Lbl>
        </>
      )}
    </div>
  );
}

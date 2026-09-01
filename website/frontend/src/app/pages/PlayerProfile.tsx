import { Link, useParams } from 'react-router';
import { usePlayerIdentity, usePlayerMatchRounds, usePlayerProfile, useSkillPlayer } from '../lib/queries';
import type {
  PlayerIdentity, PlayerMatchRound,
  PlayerProfile as Profile, ProfileIdentity, ProfileMapRow, ProfileMatchRow,
  ProfileOpponent, ProfileTeammate, ProfileWeaponRow, SkillPlayerComponent,
} from '../lib/types';
import { mapLabel } from '../lib/maps';
import { Absent, figure, Lbl, lblStyle, Meta, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

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
          </div>
        ) : (
          <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="identity" /></div>
        )}
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
  return (
    <div data-parity="profile.lifetime" className="about-grid-5" style={{ gap: 'var(--space-3)', marginTop: 'var(--space-6)' }}>
      {cells.map(([k, v]) => (
        <div key={k}>
          <Lbl style={{ fontSize: 'var(--fs-caption)' }}>{k}</Lbl>
          <div className="m" style={{ fontSize: 'var(--fs-row-lg)', marginTop: 'var(--space-1)' }}>{v}</div>
        </div>
      ))}
    </div>
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

function Weapons({ rows, available }: { rows: ProfileWeaponRow[] | undefined; available: boolean }) {
  // An unavailable section carries no list at all — read defensively, then
  // let SectionBody name the state (Codex, #822).
  const top = [...(rows ?? [])].sort((a, b) => b.kills - a.kills).slice(0, 8);
  return (
    <div data-parity="profile.weapons" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="weapons · top eight by kills" aside={<Lbl style={{ fontSize: 'var(--fs-caption)' }}>head hits, not headshot kills</Lbl>} />
      <SectionBody available={available} empty={top.length === 0} what="weapon stats">
        <div style={{ marginTop: 'var(--space-2)' }}>
          <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 'var(--space-3)', padding: 'var(--space-2) 0' }}>
            <Lbl style={{ fontSize: 'var(--fs-caption)' }}>weapon</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>kills</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>acc</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>head hits</Lbl>
            <Lbl style={{ fontSize: 'var(--fs-caption)', textAlign: 'right' }}>hs rate</Lbl>
          </div>
          {top.map((w) => (
            <div key={w.weapon} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 'var(--space-3)', alignItems: 'baseline', padding: 'var(--space-2) 0' }}>
              <span style={{ fontSize: 'var(--fs-value)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{w.weapon}</span>
              <span className="m" style={{ fontSize: 'var(--fs-small)', textAlign: 'right' }}>{figure(w.kills)}</span>
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
            </>
          )}
        </SectionBody>
      </div>
      <div data-parity="profile.movement">
        <SectionHead label="how they move" />
        <SectionBody available={m.available} empty={!m.tracks} what="movement">
          <div className="home-cols3" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
            {([['avg speed', num(m.avg_speed)], ['peak', num(m.peak_speed)], ['sprint', pct(m.sprint_pct)],
              ['dist / life', num(m.avg_distance_per_life)],
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
      <SectionHead label="the people" aside={<Lbl style={{ fontSize: 'var(--fs-caption)' }}>the leading figure is what each list ranks by · synergy = dpm delta together</Lbl>} />
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
                {['date', 'map', 'r', 'hs kills', 'gibs', 'revives', 'dmg taken', 'acc'].map((h, i) => (
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
          <Streaks p={p} />
          <Achievements playerId={playerId} />
          <Weapons rows={p.weapons.weapons} available={p.weapons.available} />
          <Body p={p} />
          <Relationships p={p} />
          <Maps rows={p.maps.maps} available={p.maps.available} />
          <Recent rows={p.recent_matches.matches} available={p.recent_matches.available} />
          <RecentDetail playerId={playerId} />
          <Lbl style={{ fontSize: 'var(--fs-caption)', marginTop: 'var(--space-6)' }}>
            {p.sections.length} sections · generated {p.generated_at.slice(0, 19).replace('T', ' ')} utc
          </Lbl>
        </>
      )}
    </div>
  );
}

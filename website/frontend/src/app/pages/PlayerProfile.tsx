import { useParams } from 'react-router';
import { usePlayerProfile } from '../lib/queries';
import type {
  PlayerProfile as Profile, ProfileIdentity, ProfileMapRow, ProfileMatchRow,
  ProfileOpponent, ProfileTeammate, ProfileWeaponRow,
} from '../lib/types';
import { mapLabel } from '../lib/maps';
import { Lbl, Pending, SectionHead, Unavailable, figure, lblStyle, rowStyle } from '../components/ui';

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
  if (!available) return <div style={{ marginTop: 8 }}><Unavailable what={what} /></div>;
  if (empty) {
    return (
      <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 8 }}>
        no {what} recorded yet
      </div>
    );
  }
  return <>{children}</>;
}

/** Sick-leave / alt attribution (migration 073). Two shapes: an ALT names
 * its primary, a PRIMARY names its alts. Gated on `active !== false`, the
 * same rule as the form page (#819): a historical link still arrives, and
 * a spent leave must not read as a current one. Statistics stay separate —
 * this line says WHO, never merges numbers. */
function IdentityLink({ link }: { link: ProfileIdentity['identity_link'] }) {
  if (!link || link.active === false) return null;
  if (link.role === 'alt' && link.primary_name) {
    return (
      <span style={{ color: 'var(--color-accent-warm)' }}>
        {' · '}alt of {link.primary_name}
        {link.link_type === 'sick_leave' && ' (on sick leave)'}
      </span>
    );
  }
  const alts = (link.alts ?? []).filter((a) => a.active !== false);
  if (link.role === 'primary' && alts.length > 0) {
    return (
      <span style={{ color: 'var(--color-accent-warm)' }}>
        {' · '}also plays as {alts.map((a) => a.alt_name).join(', ')}
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
    <div data-parity="profile.header" style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
      <div>
        <Lbl>player · {id.guid ?? p.guid}</Lbl>
        <h1 style={{ fontSize: 40, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '10px 0 0', fontWeight: 500 }}>
          {named ? id.name : (p.guid || 'unknown player')}
        </h1>
        {named ? (
          <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 6 }}>
            {id.first_seen ?? '—'} → {id.last_seen ?? '—'} · {figure(id.rounds ?? 0)} rounds
            {aliases.length > 0 && ` · also ${aliases.slice(0, 3).join(', ')}`}
            <IdentityLink link={id.identity_link} />
          </div>
        ) : (
          <div style={{ marginTop: 6 }}><Unavailable what="identity" /></div>
        )}
      </div>
      {/* An unrated player gets {available:false, reason:"not rated"} — the
        * rating area must say that, not vanish (Codex, #822 wave 4): a
        * missing panel and a missing rating are different facts. */}
      {!(skill.available && skill.et_rating != null) && (
        <div style={{ textAlign: 'right' }}>
          <Lbl style={{ fontSize: 9 }}>et rating</Lbl>
          <div className="m" style={{ fontSize: 13, color: 'var(--color-text-500)', marginTop: 6 }}>
            {/* Same split: only `reason` separates "this player has no
              * rating" from "the rating query failed". */}
            {skill.reason === 'error' ? 'unavailable' : 'not rated yet'}
          </div>
        </div>
      )}
      {skill.available && skill.et_rating != null && (
        <div style={{ textAlign: 'right' }}>
          <Lbl style={{ fontSize: 9 }}>et rating</Lbl>
          <div className="m" style={{ fontSize: 44, lineHeight: 0.9, color: 'var(--color-accent)' }}>
            {skill.et_rating.toFixed(3)}
          </div>
          <div className="m" style={{ fontSize: 10, color: 'var(--color-text-400)', marginTop: 4 }}>
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
    <div data-parity="profile.lifetime" className="about-grid-5" style={{ gap: 12, marginTop: 30 }}>
      {cells.map(([k, v]) => (
        <div key={k}>
          <Lbl style={{ fontSize: 9 }}>{k}</Lbl>
          <div className="m" style={{ fontSize: 17, marginTop: 4 }}>{v}</div>
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
      <div data-parity="profile.streaks" style={{ marginTop: 26 }}>
        <Lbl style={{ fontSize: 9 }}>current run</Lbl>
        <span style={{ marginLeft: 10 }}>
          {failed
            ? <Unavailable what="streaks" />
            : <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>no decided rounds yet</span>}
        </span>
      </div>
    );
  }
  return (
    <div data-parity="profile.streaks" style={{ marginTop: 26, display: 'flex', gap: 26, alignItems: 'baseline', flexWrap: 'wrap' }}>
      <span>
        <Lbl style={{ fontSize: 9 }}>current run</Lbl>
        <span className="m" style={{ fontSize: 15, marginLeft: 10, color: onLoss ? 'var(--color-neg)' : 'var(--color-pos)' }}>
          {s.current_streak} {s.current_type ?? ''}
        </span>
      </span>
      <span className="m" style={{ fontSize: 11, color: 'var(--color-text-400)' }}>
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
    <div data-parity="profile.weapons" style={{ marginTop: 34 }}>
      <SectionHead label="weapons · top eight by kills" aside={<Lbl style={{ fontSize: 9 }}>head hits, not headshot kills</Lbl>} />
      <SectionBody available={available} empty={top.length === 0} what="weapon stats">
        <div style={{ marginTop: 8 }}>
          <div style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 12, padding: '6px 0' }}>
            <Lbl style={{ fontSize: 9 }}>weapon</Lbl>
            <Lbl style={{ fontSize: 9, textAlign: 'right' }}>kills</Lbl>
            <Lbl style={{ fontSize: 9, textAlign: 'right' }}>acc</Lbl>
            <Lbl style={{ fontSize: 9, textAlign: 'right' }}>head hits</Lbl>
            <Lbl style={{ fontSize: 9, textAlign: 'right' }}>hs rate</Lbl>
          </div>
          {top.map((w) => (
            <div key={w.weapon} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto auto', gap: 12, alignItems: 'baseline', padding: '7px 0' }}>
              <span style={{ fontSize: 13, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{w.weapon}</span>
              <span className="m" style={{ fontSize: 12, textAlign: 'right' }}>{figure(w.kills)}</span>
              <span className="m" style={{ fontSize: 12, textAlign: 'right', color: 'var(--color-text-400)' }}>{pct(w.accuracy)}</span>
              <span className="m" style={{ fontSize: 12, textAlign: 'right', color: 'var(--color-text-400)' }}>{figure(w.headshots)}</span>
              <span className="m" style={{ fontSize: 12, textAlign: 'right', color: 'var(--color-text-400)' }}>{pct(w.hs_accuracy)}</span>
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
    <div className="landing-split" style={{ gap: 34, marginTop: 34 }}>
      <div data-parity="profile.hit-regions">
        <SectionHead label="where the hits land" />
        <SectionBody available={p.hit_regions.available} empty={t == null} what="hit regions">
          {t && (
            <>
              <div style={{ display: 'flex', height: 6, marginTop: 10 }}>
                {([['head', t.head_pct, 'var(--color-accent)'], ['arms', t.arms_pct, '#6b7f92'],
                  ['body', t.body_pct, 'var(--color-accent-warm)'], ['legs', t.legs_pct, '#7a6a52']] as const)
                  .map(([k, v, c]) => <span key={k} style={{ width: `${v}%`, background: c, display: 'block' }} />)}
              </div>
              <div className="m" style={{ ...lblStyle, fontSize: 9, marginTop: 6, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
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
          <div className="home-cols3" style={{ gap: 10, marginTop: 10 }}>
            {([['avg speed', num(m.avg_speed)], ['peak', num(m.peak_speed)], ['sprint', pct(m.sprint_pct)],
              ['dist / life', num(m.avg_distance_per_life)],
              ['standing', pct(stance?.standing_pct)], ['crouching', pct(stance?.crouching_pct)]] as const)
              .map(([k, v]) => (
                <div key={k}>
                  <Lbl style={{ fontSize: 9 }}>{k}</Lbl>
                  <div className="m" style={{ fontSize: 13, marginTop: 3 }}>{v}</div>
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
      <Lbl style={{ fontSize: 9 }}>{title}</Lbl>
      <div style={{ marginTop: 6 }}>
        {rows.slice(0, 5).map((o) => (
          <div key={o.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto', gap: 10, alignItems: 'baseline', padding: '6px 0' }}>
            <span className="m" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.name}</span>
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-200)' }}>
              {lead === 'on' ? o.kills_on_player : o.kills_by_player}
            </span>
            <span className="m" style={{ fontSize: 10, color: 'var(--color-text-500)' }}>
              of {o.total_encounters}
            </span>
          </div>
        ))}
      </div>
      <Lbl style={{ fontSize: 9, marginTop: 4 }}>{note}</Lbl>
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
      <Lbl style={{ fontSize: 9 }}>{title}</Lbl>
      <div style={{ marginTop: 6 }}>
        {rows.slice(0, 5).map((t) => (
          <div key={t.guid} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto', gap: 10, alignItems: 'baseline', padding: '6px 0' }}>
            <span className="m" style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</span>
            <span className="m" style={{ fontSize: 12, color: 'var(--color-text-200)' }}>
              {t.synergy == null ? '—' : `${t.synergy > 0 ? '+' : ''}${t.synergy.toFixed(0)}`}
            </span>
            <span className="m" style={{ fontSize: 10, color: 'var(--color-text-500)' }}>
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
    <div data-parity="profile.relationships" style={{ marginTop: 34 }}>
      <SectionHead label="the people" aside={<Lbl style={{ fontSize: 9 }}>the leading figure is what each list ranks by · synergy = dpm delta together</Lbl>} />
      <SectionBody available={r.available} empty={empty} what="head-to-head history">
        <div className="about-grid-4" style={{ gap: 24, marginTop: 10 }}>
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
    <div data-parity="profile.maps" style={{ marginTop: 34 }}>
      <SectionHead label="grounds · most played" />
      <SectionBody available={available} empty={top.length === 0} what="map history">
        <div style={{ marginTop: 8 }}>
          {top.map((m) => (
            <div key={m.map} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto', gap: 12, alignItems: 'baseline', padding: '7px 0' }}>
              <span style={{ fontSize: 13, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{mapLabel(m.map)}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{m.rounds} rd</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{pct(m.win_rate)}</span>
              <span className="m" style={{ fontSize: 12 }}>{m.dpm == null ? '—' : m.dpm.toFixed(0)} dpm</span>
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
    <div data-parity="profile.recent" style={{ marginTop: 34 }}>
      <SectionHead label="last rounds" aside={<Lbl style={{ fontSize: 9 }}>newest first</Lbl>} />
      <SectionBody available={available} empty={rows.length === 0} what="recent rounds">
        <div style={{ marginTop: 8 }}>
          {rows.map((r) => (
            <div key={r.round_id} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'auto minmax(0,1fr) auto auto auto', gap: 12, alignItems: 'baseline', padding: '7px 0' }}>
              <span className="m" style={{ ...lblStyle, fontSize: 9 }}>{r.date}</span>
              <span style={{ fontSize: 13, letterSpacing: '0.04em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {mapLabel(r.map)} R{r.round_number}
              </span>
              <span className="m" style={{ fontSize: 12 }}>{r.kills}/{r.deaths}</span>
              <span className="m" style={{ fontSize: 12, color: 'var(--color-text-400)' }}>{r.dpm == null ? '—' : r.dpm.toFixed(0)} dpm</span>
              {/* A round with no attributed winner shows a dash — never a loss. */}
              <span className="m" style={{ fontSize: 12, color: r.result === 'W' ? 'var(--color-pos)' : r.result === 'L' ? 'var(--color-neg)' : 'var(--color-text-500)' }}>
                {r.result ?? '—'}
              </span>
            </div>
          ))}
        </div>
      </SectionBody>
    </div>
  );
}

export function PlayerProfilePage() {
  const params = useParams();
  const playerId = params.id ?? '';
  const profile = usePlayerProfile(playerId);
  const p = profile.isError ? undefined : profile.data;
  return (
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 980 }}>
      {playerId.length === 0 && (
        <>
          <Lbl>player</Lbl>
          <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
            Pick a player.
          </h1>
          <div className="m" style={{ fontSize: 12, color: 'var(--color-text-400)', marginTop: 12 }}>
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
          <Streaks p={p} />
          <Weapons rows={p.weapons.weapons} available={p.weapons.available} />
          <Body p={p} />
          <Relationships p={p} />
          <Maps rows={p.maps.maps} available={p.maps.available} />
          <Recent rows={p.recent_matches.matches} available={p.recent_matches.available} />
          <Lbl style={{ fontSize: 9, marginTop: 26 }}>
            {p.sections.length} sections · generated {p.generated_at.slice(0, 19).replace('T', ' ')} utc
          </Lbl>
        </>
      )}
    </div>
  );
}

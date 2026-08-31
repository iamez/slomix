import { useState } from 'react';
import { hasFailed } from '../lib/responseStatus';
import { useWeapons, useWeaponsByPlayer, useWeaponsHof } from '../lib/queries';
import type { WeaponPeriod } from '../lib/queries';
import type { WeaponRow } from '../lib/types';
import { Absent, Chip, Lbl, lblStyle, Pending, rowStyle, SectionHead, Unavailable } from '../components/ui';

/**
 * Weapons (docs/design/12 row 6) — legacy matches.js weapons view carried
 * over: three endpoints in parallel, a period picker refetching all three,
 * a client-side category filter, hall of fame, weapons grid, per-player
 * mastery. Deliberate departures: by_player is FIXED (the 404-fallback
 * alias is not carried); ALL categories get a button (legacy UI offered
 * 5 of the 8 its own table knew); the usage-rate denominator is GLOBAL
 * (legacy recomputed it per filter, so one weapon showed two shares).
 *
 * The labels 'head hits' and 'head-hit rate' are load-bearing:
 * weapon_comprehensive_stats has HIT LOCATIONS, not headshot kills — they
 * legitimately exceed kills (Mp40: 110k kills, 129k head hits).
 */

const WEAPON_CATEGORIES = new Map<string, string>(Object.entries({
  mp40: 'smg', thompson: 'smg', sten: 'smg',
  // carbine = 'M1 Garand (Carbine)' in the canonical weapon table
  // (player_profile_metrics:187) — without the alias it fell to Other.
  garand: 'rifle', carbine: 'rifle', k43: 'rifle', kar98: 'rifle', fg42: 'rifle',
  panzerfaust: 'heavy', mortar: 'heavy', flamethrower: 'heavy', mg42: 'heavy',
  luger: 'pistol', colt: 'pistol', akimbo: 'pistol', silencer: 'pistol',
  knife: 'melee',
  grenade: 'explosive', dynamite: 'explosive', landmine: 'explosive', satchel: 'explosive',
  // Airstrike + Artillery are SUPPORT — the legacy and modern views both
  // class the fieldops calls there; under 'explosive' the Support filter
  // came up empty for the whole recorded corpus.
  // 'smokegrenade' needs its own EXACT entry: substring matching finds
  // 'grenade' in it and would file the support smoke under explosive.
  smokegrenade: 'support', airstrike: 'support', artillery: 'support', syringe: 'support', smoke: 'support',
}));
const CATEGORIES = ['all', 'smg', 'rifle', 'heavy', 'pistol', 'melee', 'explosive', 'support', 'other'];
// ⛔ Typed against the schema, not just written down. The backend accepts
// exactly these four (it used to accept anything and quietly answer with
// all-time numbers), and `WeaponPeriod` is derived from `openapi.json`, so a
// chip added here that the API does not take fails the typecheck instead of
// shipping a 422 to whoever clicks it.
const PERIODS: readonly WeaponPeriod[] = ['all', 'season', '30d', '7d'];

function categoryOf(weaponKey: string): string {
  const key = weaponKey.toLowerCase().replace(/^ws[_ ]/, '').replace(/[_ ]/g, '');
  // Exact key first — the substring pass picks whichever entry iterates
  // first, which misfiles keys that contain another entry's name.
  const exact = WEAPON_CATEGORIES.get(key);
  if (exact) return exact;
  for (const [name, cat] of WEAPON_CATEGORIES) {
    if (key.includes(name)) return cat;
  }
  return 'other';
}


function HallOfFameStrip({ period }: { period: WeaponPeriod }) {
  const hof = useWeaponsHof(period);
  const leaders = hof.data ? Object.values(hof.data.leaders) : [];
  // The endpoint answers 200 with an empty board when its query FAILS, so
  // emptiness alone cannot tell an outage from a quiet season. #830 adds the
  // status field that can; until it lands the field is absent and this
  // reduces to today's behaviour.
  const hofFailed = hasFailed(hof, hof.data);
  return (
    <div data-parity="weapons.hof" style={{ marginTop: 'var(--space-5)' }}>
      <SectionHead label="hall of fame · best hand per weapon" />
      {hof.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="hall of fame" /></div>}
      {hofFailed && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="hall of fame" /></div>}
      {hof.isSuccess && !hofFailed && leaders.length === 0 && (
        <Absent block style={{ marginTop: 'var(--space-2)' }} reason="no hall of fame data yet" />
      )}
      <div className="home-cols3" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
        {leaders.map((l) => (
          <div key={l.weapon_key} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
              <span style={{ fontSize: 'var(--fs-row)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{l.weapon}</span>
              <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)' }}>{categoryOf(l.weapon_key)}</span>
            </div>
            <div className="m" style={{ fontSize: 'var(--fs-value)', marginTop: 'var(--space-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.player_name}</div>
            <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-400)', marginTop: 'var(--space-1)' }}>
              {l.kills.toLocaleString('en-US')} kills · {l.headshots.toLocaleString('en-US')} head hits · {l.accuracy.toFixed(1)}% acc
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function WeaponsGrid({ period, category }: { period: WeaponPeriod; category: string }) {
  const weapons = useWeapons(period);
  const data = weapons.isError ? undefined : weapons.data;
  // GLOBAL denominator — one weapon, one share, whatever the filter shows.
  const totalKills = (data ?? []).reduce((a, w) => a + w.kills, 0) || 1;
  const rows = (data ?? []).filter((w) => category === 'all' || categoryOf(w.weapon_key) === category);
  return (
    <div data-parity="weapons.grid" style={{ marginTop: 'var(--space-5)' }}>
      <SectionHead label={`${rows.length} weapons · share of all kills`} />
      {weapons.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="weapons" /></div>}
      {weapons.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="weapons" /></div>}
      {data && rows.length === 0 && (
        <Absent block style={{ marginTop: 'var(--space-2)' }} reason="no weapons in this category" />
      )}
      <div style={{ marginTop: 'var(--space-2)' }}>
        {rows.map((w: WeaponRow) => {
          const share = (w.kills / totalKills) * 100;
          return (
            <div key={w.weapon_key} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,140px) 1fr auto auto auto', gap: 'var(--space-3)', alignItems: 'center', padding: 'var(--space-2) 0' }}>
              <span style={{ fontSize: 'var(--fs-body)', letterSpacing: '0.03em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.name}</span>
              <span style={{ height: 5, background: 'var(--color-rule-900)', display: 'block', position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${Math.min(share * 2, 100).toFixed(1)}%`, background: '#5c6f7d', display: 'block' }} />
              </span>
              <span className="m" style={{ fontSize: 'var(--fs-small)' }}>{w.kills.toLocaleString('en-US')}</span>
              <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-400)' }}>{share.toFixed(1)}%</span>
              <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>{w.accuracy.toFixed(1)}% acc</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MasteryGrid({ period }: { period: WeaponPeriod }) {
  const byPlayer = useWeaponsByPlayer(period);
  const players = byPlayer.data?.players ?? [];
  return (
    <div data-parity="weapons.mastery" style={{ marginTop: 'var(--space-6)' }}>
      <SectionHead label="player weapon mastery · top 4 weapons each" />
      {byPlayer.isPending && <div style={{ marginTop: 'var(--space-2)' }}><Pending label="mastery" /></div>}
      {byPlayer.isError && <div style={{ marginTop: 'var(--space-2)' }}><Unavailable what="mastery" /></div>}
      {byPlayer.isSuccess && players.length === 0 && (
        <Absent block style={{ marginTop: 'var(--space-2)' }} reason="no per-player weapon stats for this period" />
      )}
      <div className="home-cols3" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
        {players.map((p) => (
          <div key={p.player_guid} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
              <span className="m" style={{ fontSize: 'var(--fs-value)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.player_name}</span>
              <span className="m" style={{ ...lblStyle, fontSize: 'var(--fs-caption)', flex: 'none' }}>{p.total_kills.toLocaleString('en-US')} kills</span>
            </div>
            <div style={{ marginTop: 'var(--space-2)' }}>
              {p.weapons.map((w) => (
                <div key={w.weapon_key} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto', gap: 'var(--space-2)', alignItems: 'baseline', padding: 'var(--space-1) 0' }}>
                  <span className="m" style={{ fontSize: 'var(--fs-micro)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.name}</span>
                  {/* w.kills is an ABSOLUTE count — a 'k' suffix would read
                    * 16,148 as sixteen million. */}
                  <span className="m" style={{ fontSize: 'var(--fs-micro)' }}>{w.kills.toLocaleString('en-US')}</span>
                  <span className="m" style={{ fontSize: 'var(--fs-label)', color: 'var(--color-text-400)' }}>{w.accuracy.toFixed(1)}% acc</span>
                  {/* headshots/hits — a HEAD-HIT rate, never a kill rate. */}
                  <span className="m" style={{ fontSize: 'var(--fs-label)', color: 'var(--color-text-500)' }}>{w.hs_rate.toFixed(1)}% head-hit</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function WeaponsPage() {
  const [period, setPeriod] = useState<WeaponPeriod>('all');
  const [category, setCategory] = useState('all');
  return (
    <div style={{ paddingTop: 'var(--space-7)', paddingBottom: 'var(--space-7)', maxWidth: 980 }}>
      <Lbl>weapons · what the kills were made with</Lbl>
      <h1 style={{ fontSize: 'var(--fs-title)', letterSpacing: '0.03em', textTransform: 'uppercase', margin: 'var(--space-3) 0 0', fontWeight: 500 }}>
        The tools of the trade.
      </h1>
      <div data-parity="weapons.filters" style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-4)', flexWrap: 'wrap' }}>
        {PERIODS.map((p) => <Chip key={p} active={period === p} label={p} onClick={() => { setPeriod(p); }} />)}
        <span style={{ width: 12 }} />
        {CATEGORIES.map((c) => <Chip key={c} active={category === c} label={c} onClick={() => { setCategory(c); }} />)}
      </div>
      <HallOfFameStrip period={period} />
      <WeaponsGrid period={period} category={category} />
      <MasteryGrid period={period} />
    </div>
  );
}

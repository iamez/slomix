import { useState } from 'react';
import { useWeapons, useWeaponsByPlayer, useWeaponsHof } from '../lib/queries';
import type { WeaponRow } from '../lib/types';
import { Lbl, Pending, SectionHead, Unavailable, lblStyle, rowStyle } from '../components/ui';

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
  garand: 'rifle', k43: 'rifle', kar98: 'rifle', fg42: 'rifle',
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
const PERIODS = ['all', 'season', '30d', '7d'];

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

function Pill({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        fontSize: 12, letterSpacing: '0.08em', textTransform: 'uppercase', cursor: 'pointer',
        border: `1px solid ${active ? '#4a5a66' : 'var(--color-rule-700)'}`,
        background: active ? '#151a1e' : 'transparent',
        color: active ? 'var(--color-text-100)' : 'var(--color-text-400)',
        padding: '4px 9px',
      }}
    >
      {label}
    </button>
  );
}

function HallOfFameStrip({ period }: { period: string }) {
  const hof = useWeaponsHof(period);
  const leaders = hof.data ? Object.values(hof.data.leaders) : [];
  return (
    <div data-parity="weapons.hof" style={{ marginTop: 22 }}>
      <SectionHead label="hall of fame · best hand per weapon" />
      {hof.isPending && <div style={{ marginTop: 10 }}><Pending label="hall of fame" /></div>}
      {hof.isError && <div style={{ marginTop: 10 }}><Unavailable what="hall of fame" /></div>}
      {hof.isSuccess && leaders.length === 0 && (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 10 }}>no hall of fame data yet</div>
      )}
      <div className="home-cols3" style={{ gap: 10, marginTop: 10 }}>
        {leaders.map((l) => (
          <div key={l.weapon_key} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
              <span style={{ fontSize: 15, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{l.weapon}</span>
              <span className="m" style={{ ...lblStyle, fontSize: 9 }}>{categoryOf(l.weapon_key)}</span>
            </div>
            <div className="m" style={{ fontSize: 13, marginTop: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.player_name}</div>
            <div className="m" style={{ fontSize: 11, color: 'var(--color-text-400)', marginTop: 3 }}>
              {l.kills.toLocaleString('en-US')} kills · {l.headshots.toLocaleString('en-US')} head hits · {l.accuracy.toFixed(1)}% acc
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function WeaponsGrid({ period, category }: { period: string; category: string }) {
  const weapons = useWeapons(period);
  const data = weapons.isError ? undefined : weapons.data;
  // GLOBAL denominator — one weapon, one share, whatever the filter shows.
  const totalKills = (data ?? []).reduce((a, w) => a + w.kills, 0) || 1;
  const rows = (data ?? []).filter((w) => category === 'all' || categoryOf(w.weapon_key) === category);
  return (
    <div data-parity="weapons.grid" style={{ marginTop: 22 }}>
      <SectionHead label={`${rows.length} weapons · share of all kills`} />
      {weapons.isPending && <div style={{ marginTop: 10 }}><Pending label="weapons" /></div>}
      {weapons.isError && <div style={{ marginTop: 10 }}><Unavailable what="weapons" /></div>}
      {data && rows.length === 0 && (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 10 }}>no weapons in this category</div>
      )}
      <div style={{ marginTop: 8 }}>
        {rows.map((w: WeaponRow) => {
          const share = (w.kills / totalKills) * 100;
          return (
            <div key={w.weapon_key} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,140px) 1fr auto auto auto', gap: 12, alignItems: 'center', padding: '7px 0' }}>
              <span style={{ fontSize: 14, letterSpacing: '0.03em', textTransform: 'uppercase', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.name}</span>
              <span style={{ height: 5, background: 'var(--color-rule-800)', display: 'block', position: 'relative' }}>
                <span style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${Math.min(share * 2, 100).toFixed(1)}%`, background: '#5c6f7d', display: 'block' }} />
              </span>
              <span className="m" style={{ fontSize: 12 }}>{w.kills.toLocaleString('en-US')}</span>
              <span className="m" style={{ fontSize: 11, color: 'var(--color-text-400)' }}>{share.toFixed(1)}%</span>
              <span className="m" style={{ fontSize: 11, color: 'var(--color-text-500)' }}>{w.accuracy.toFixed(1)}% acc</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MasteryGrid({ period }: { period: string }) {
  const byPlayer = useWeaponsByPlayer(period);
  const players = byPlayer.data?.players ?? [];
  return (
    <div data-parity="weapons.mastery" style={{ marginTop: 34 }}>
      <SectionHead label="player weapon mastery · top 4 weapons each" />
      {byPlayer.isPending && <div style={{ marginTop: 10 }}><Pending label="mastery" /></div>}
      {byPlayer.isError && <div style={{ marginTop: 10 }}><Unavailable what="mastery" /></div>}
      {byPlayer.isSuccess && players.length === 0 && (
        <div className="m" style={{ fontSize: 11, color: 'var(--color-text-500)', marginTop: 10 }}>no per-player weapon stats for this period</div>
      )}
      <div className="home-cols3" style={{ gap: 10, marginTop: 10 }}>
        {players.map((p) => (
          <div key={p.player_guid} style={{ border: '1px solid var(--color-rule-700)', background: 'var(--color-ink-800)', padding: 12 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
              <span className="m" style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.player_name}</span>
              <span className="m" style={{ ...lblStyle, fontSize: 9, flex: 'none' }}>{p.total_kills.toLocaleString('en-US')} kills</span>
            </div>
            <div style={{ marginTop: 8 }}>
              {p.weapons.map((w) => (
                <div key={w.weapon_key} style={{ ...rowStyle, display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto auto auto', gap: 8, alignItems: 'baseline', padding: '4px 0' }}>
                  <span className="m" style={{ fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.name}</span>
                  {/* w.kills is an ABSOLUTE count — a 'k' suffix would read
                    * 16,148 as sixteen million. */}
                  <span className="m" style={{ fontSize: 11 }}>{w.kills.toLocaleString('en-US')}</span>
                  <span className="m" style={{ fontSize: 10, color: 'var(--color-text-400)' }}>{w.accuracy.toFixed(1)}% acc</span>
                  {/* headshots/hits — a HEAD-HIT rate, never a kill rate. */}
                  <span className="m" style={{ fontSize: 10, color: 'var(--color-text-500)' }}>{w.hs_rate.toFixed(1)}% head-hit</span>
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
  const [period, setPeriod] = useState('all');
  const [category, setCategory] = useState('all');
  return (
    <div style={{ paddingTop: 44, paddingBottom: 40, maxWidth: 980 }}>
      <Lbl>weapons · what the kills were made with</Lbl>
      <h1 style={{ fontSize: 34, letterSpacing: '0.03em', textTransform: 'uppercase', margin: '12px 0 0', fontWeight: 500 }}>
        The tools of the trade.
      </h1>
      <div data-parity="weapons.filters" style={{ display: 'flex', gap: 8, marginTop: 18, flexWrap: 'wrap' }}>
        {PERIODS.map((p) => <Pill key={p} active={period === p} label={p} onClick={() => { setPeriod(p); }} />)}
        <span style={{ width: 12 }} />
        {CATEGORIES.map((c) => <Pill key={c} active={category === c} label={c} onClick={() => { setCategory(c); }} />)}
      </div>
      <HallOfFameStrip period={period} />
      <WeaponsGrid period={period} category={category} />
      <MasteryGrid period={period} />
    </div>
  );
}

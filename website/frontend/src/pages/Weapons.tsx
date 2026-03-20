import { useState, useMemo } from 'react';
import { Crosshair, Users, Crown } from 'lucide-react';
import { useWeapons, useWeaponHoF, useWeaponsByPlayer } from '../api/hooks';
import type { WeaponStat, WeaponHoFEntry, WeaponPlayerStat } from '../api/types';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateToPlayer } from '../lib/navigation';
import { weaponIcon } from '../lib/game-assets';

const PERIODS = [
  { value: 'all', label: 'All-time' },
  { value: 'season', label: 'Season' },
  { value: '30d', label: '30d' },
  { value: '7d', label: '7d' },
] as const;

const WEAPON_CATEGORIES: Record<string, string> = {
  knife: 'Melee', luger: 'Pistol', colt: 'Pistol',
  mp40: 'SMG', thompson: 'SMG', sten: 'SMG',
  fg42: 'Rifle', garand: 'Rifle', k43: 'Rifle', kar98: 'Rifle',
  panzerfaust: 'Heavy', flamethrower: 'Heavy', mortar: 'Heavy', mg42: 'Heavy',
  grenade: 'Explosive', dynamite: 'Explosive', landmine: 'Explosive',
  airstrike: 'Support', artillery: 'Support', syringe: 'Support', smokegrenade: 'Support',
};

const CATEGORY_COLORS: Record<string, string> = {
  Melee: 'text-amber-400 border-amber-400/30',
  Pistol: 'text-slate-300 border-slate-400/30',
  SMG: 'text-blue-400 border-blue-400/30',
  Rifle: 'text-purple-400 border-purple-400/30',
  Heavy: 'text-rose-400 border-rose-400/30',
  Explosive: 'text-yellow-400 border-yellow-400/30',
  Support: 'text-emerald-400 border-emerald-400/30',
  Other: 'text-cyan-400 border-cyan-400/30',
};

const CATEGORY_FILTERS = ['all', 'SMG', 'Rifle', 'Pistol', 'Heavy', 'Explosive', 'Support', 'Melee'] as const;

function normalizeWeaponKey(name: string): string {
  return (name || '').toLowerCase().replace(/^ws[_\s]+/, '').replace(/[_\s]+/g, '');
}

function getCategory(name: string): string {
  return WEAPON_CATEGORIES[normalizeWeaponKey(name)] ?? 'Other';
}

function getCategoryStyle(name: string): string {
  return CATEGORY_COLORS[getCategory(name)] ?? CATEGORY_COLORS.Other;
}

// --- Hall of Fame Cards ---
function HoFCard({ entry }: { entry: WeaponHoFEntry }) {
  const cat = getCategory(entry.weapon);
  const style = CATEGORY_COLORS[cat] ?? CATEGORY_COLORS.Other;
  const [textColor] = style.split(' ');
  const icon = weaponIcon(entry.weapon_key || entry.weapon);
  return (
    <GlassCard
      onClick={() => navigateToPlayer(entry.player_name)}
      className="relative overflow-hidden"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">{cat}</span>
        <div className="flex items-center gap-2">
          {icon && <img src={icon} alt={entry.weapon} className="h-5 object-contain opacity-70" style={{ filter: 'brightness(1.8)' }} />}
          <span className={cn('text-xs font-bold', textColor)}>{entry.weapon}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 mb-1">
        <Crown className="w-4 h-4 text-yellow-500 shrink-0" />
        <span className="text-lg font-black text-white truncate">{entry.player_name}</span>
      </div>
      <div className="text-xs text-slate-400">
        {formatNumber(entry.kills)} kills · {formatNumber(entry.headshots)} HS · {entry.accuracy}% acc
      </div>
    </GlassCard>
  );
}

// --- Weapon Card ---
function WeaponCard({ weapon, totalKills }: { weapon: WeaponStat; totalKills: number }) {
  const usage = totalKills > 0 ? ((weapon.kills / totalKills) * 100) : 0;
  const style = getCategoryStyle(weapon.name);
  const [textColor, borderColor] = style.split(' ');
  const cat = getCategory(weapon.name);

  const icon = weaponIcon(weapon.weapon_key || weapon.name);

  return (
    <div className={cn('glass-card p-5 rounded-xl border-l-4', borderColor)}>
      <div className="flex items-center justify-between mb-3">
        <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] font-bold text-slate-400 uppercase">{cat}</span>
        {icon ? (
          <img src={icon} alt={weapon.name} className="h-6 object-contain opacity-80 drop-shadow-lg" style={{ filter: 'brightness(1.8)' }} />
        ) : (
          <Crosshair className={cn('w-5 h-5', textColor)} />
        )}
      </div>
      <h3 className="text-lg font-black text-white mb-3">{weapon.name}</h3>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Kills</span>
          <span className="font-bold text-white">{formatNumber(weapon.kills)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">HS Rate</span>
          <span className="font-bold text-slate-300">{weapon.hs_rate}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Accuracy</span>
          <span className="font-bold text-slate-300">{weapon.accuracy}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Usage</span>
          <span className="font-mono text-slate-300">{usage.toFixed(1)}%</span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1">
          <div className={cn('h-full rounded-full', textColor.replace('text-', 'bg-'))}
               style={{ width: `${Math.min(usage * 2, 100)}%` }} />
        </div>
      </div>
    </div>
  );
}

// --- Player Weapon Card ---
function PlayerCard({ player }: { player: WeaponPlayerStat }) {
  return (
    <GlassCard onClick={() => navigateToPlayer(player.player_name)}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-lg font-black text-white">{player.player_name}</div>
          <div className="text-[10px] text-slate-500 font-mono">{player.player_guid.slice(0, 12)}...</div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-slate-500 uppercase">Total Kills</div>
          <div className="text-base font-black text-rose-400">{formatNumber(player.total_kills)}</div>
        </div>
      </div>
      <div className="space-y-1">
        {player.weapons.map((w) => {
          const wIcon = weaponIcon(w.weapon_key || w.name);
          return (
            <div key={w.weapon_key} className="flex items-center justify-between text-xs py-1 border-b border-white/5 last:border-b-0">
              <span className="text-slate-300 font-semibold flex items-center gap-2">
                {wIcon && <img src={wIcon} alt={w.name} className="h-3.5 object-contain opacity-60" style={{ filter: 'brightness(1.6)' }} />}
                {w.name}
              </span>
              <span className="text-slate-500">{formatNumber(w.kills)}K · {w.accuracy}% ACC · {w.hs_rate}% HS</span>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}

export default function WeaponsPage() {
  const [period, setPeriod] = useState('all');
  const [category, setCategory] = useState('all');

  const { data: weapons, isLoading: wLoading } = useWeapons(period);
  const { data: hof, isLoading: hofLoading } = useWeaponHoF(period);
  const { data: byPlayer, isLoading: pLoading } = useWeaponsByPlayer(period);

  const isLoading = wLoading || hofLoading || pLoading;

  const hofEntries = useMemo(() => {
    if (!hof?.leaders) return [];
    const order = ['luger','colt','mp40','thompson','sten','fg42','garand','k43','kar98','panzerfaust','mortar','grenade'];
    return Object.values(hof.leaders).sort(
      (a, b) => order.indexOf(a.weapon_key) - order.indexOf(b.weapon_key),
    );
  }, [hof]);

  const filteredWeapons = useMemo(() => {
    if (!weapons) return [];
    if (category === 'all') return weapons;
    return weapons.filter((w) => getCategory(w.name) === category);
  }, [weapons, category]);

  const totalKills = useMemo(
    () => (weapons ?? []).reduce((s, w) => s + w.kills, 0),
    [weapons],
  );

  if (isLoading) {
    return (
      <div className="page-shell">
        <PageHeader title="Weapon Arsenal" subtitle="Deeper weapon analysis once the main session/player path is done." eyebrow="More" />
        <Skeleton variant="card" count={6} className="grid-cols-3" />
      </div>
    );
  }

  return (
    <div className="page-shell">
      <PageHeader title="Weapon Arsenal" subtitle="Detailed weapon statistics and per-player mastery." eyebrow="More">
        <div className="flex gap-1 bg-slate-800 rounded-lg p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={cn('px-3 py-1.5 rounded-md text-xs font-bold transition',
                period === p.value ? 'bg-rose-500/20 text-rose-400' : 'text-slate-400 hover:text-white')}
            >
              {p.label}
            </button>
          ))}
        </div>
      </PageHeader>

      {/* Hall of Fame */}
      {hofEntries.length > 0 && (
        <section className="mb-8">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4">
            Hall of Fame — Best per Weapon
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {hofEntries.map((e) => <HoFCard key={e.weapon_key} entry={e} />)}
          </div>
        </section>
      )}

      {/* Category Filter */}
      <div className="flex flex-wrap justify-center gap-2 mb-6">
        {CATEGORY_FILTERS.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className={cn('px-3 py-1.5 rounded-md text-xs font-bold transition',
              category === cat
                ? 'bg-rose-500 text-white shadow-lg'
                : 'text-slate-400 hover:text-white')}
          >
            {cat === 'all' ? 'All Weapons' : cat}
          </button>
        ))}
      </div>

      {/* Weapons Grid */}
      {filteredWeapons.length === 0 ? (
        <EmptyState message="No weapons found for this filter." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
          {filteredWeapons.map((w) => (
            <WeaponCard key={w.weapon_key || w.name} weapon={w} totalKills={totalKills} />
          ))}
        </div>
      )}

      {/* Per-Player Breakdown */}
      {byPlayer && byPlayer.players.length > 0 && (
        <section>
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
            <Users className="w-4 h-4" />
            Player Weapon Mastery — {byPlayer.player_count} players
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {byPlayer.players.map((p) => (
              <PlayerCard key={p.player_guid} player={p} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

import { Skull, Heart, Zap, Star, Target, Crosshair, Gamepad2, Clock, Crown, Shield, Swords, Trophy } from 'lucide-react';
import { usePlayerProfile, usePlayerRounds } from '../api/hooks';
import type { PlayerProfileResponse, PlayerRound } from '../api/types';
import { DataTable, type Column } from '../components/DataTable';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { formatNumber, formatDate } from '../lib/format';
import { navigateTo } from '../lib/navigation';
import { weaponIcon, mapLevelshot } from '../lib/game-assets';

function KpiTile({ label, value, icon: Icon, color }: {
  label: string;
  value: string | number;
  icon: typeof Skull;
  color: string;
}) {
  return (
    <div className="glass-card rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={cn('w-4 h-4', color)} />
        <span className="text-xs text-slate-500 uppercase font-bold">{label}</span>
      </div>
      <div className="text-2xl font-black text-white">{value}</div>
    </div>
  );
}

function AchievementBadge({ achievement }: { achievement: PlayerProfileResponse['achievements'][0] }) {
  return (
    <div className={cn(
      'flex items-center gap-3 p-3 rounded-lg border transition',
      achievement.unlocked
        ? 'bg-amber-400/10 border-amber-400/20'
        : 'bg-slate-800/50 border-white/5 opacity-50',
    )}>
      <span className="text-2xl">{achievement.icon}</span>
      <div className="min-w-0">
        <div className={cn('font-bold text-sm', achievement.unlocked ? 'text-white' : 'text-slate-500')}>
          {achievement.name}
        </div>
        <div className="text-xs text-slate-500">{achievement.description}</div>
      </div>
    </div>
  );
}

const roundColumns: Column<PlayerRound>[] = [
  {
    key: 'round_date',
    label: 'Date',
    className: 'text-slate-400 text-xs',
    render: (row) => formatDate(row.round_date),
  },
  {
    key: 'map_name',
    label: 'Map',
    render: (row) => (
      <span className="text-white font-medium inline-flex items-center gap-2">
        <img src={mapLevelshot(row.map_name)} alt="" className="w-5 h-5 rounded-sm object-cover bg-slate-700" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
        {row.map_name}
      </span>
    ),
  },
  {
    key: 'round_number',
    label: 'R#',
    className: 'text-slate-400 text-center w-12',
  },
  {
    key: 'kills',
    label: 'Kills',
    sortable: true,
    sortValue: (row) => row.kills,
    className: 'text-emerald-400 font-mono',
  },
  {
    key: 'deaths',
    label: 'Deaths',
    sortable: true,
    sortValue: (row) => row.deaths,
    className: 'text-rose-400 font-mono',
  },
  {
    key: 'damage_given',
    label: 'Damage',
    sortable: true,
    sortValue: (row) => row.damage_given,
    className: 'text-amber-400 font-mono',
    render: (row) => formatNumber(row.damage_given),
  },
  {
    key: 'dpm',
    label: 'DPM',
    sortable: true,
    sortValue: (row) => row.dpm,
    className: 'text-brand-cyan font-mono',
    render: (row) => row.dpm?.toFixed(1) ?? '-',
  },
  {
    key: 'result',
    label: 'Result',
    render: (row) => {
      const won = row.team === row.winner_team && row.winner_team !== 0;
      const lost = row.team !== row.winner_team && row.winner_team !== 0;
      if (won) return <span className="text-emerald-400 text-xs font-bold">WIN</span>;
      if (lost) return <span className="text-rose-400 text-xs font-bold">LOSS</span>;
      return <span className="text-slate-500 text-xs">-</span>;
    },
  },
];

function getPlayerNameFromHash(): string {
  const qs = window.location.hash.split('?')[1] ?? '';
  return new URLSearchParams(qs).get('name') ?? '';
}

export default function Profile({ params }: { params?: Record<string, string> }) {
  const playerName = params?.name || getPlayerNameFromHash();
  const { data: profile, isLoading, isError } = usePlayerProfile(playerName);
  const { data: rounds } = usePlayerRounds(playerName);

  if (!playerName) {
    return (
      <div className="mt-6 text-center text-slate-400 py-12">
        No player selected. Use search or click a player name.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="mt-6">
        <PageHeader title={playerName} subtitle="Player profile" />
        <Skeleton variant="card" count={6} />
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="mt-6">
        <PageHeader title={playerName} subtitle="Player profile" />
        <div className="text-center text-red-400 py-12">Player not found or failed to load.</div>
      </div>
    );
  }

  const s = profile.stats;
  const initials = profile.name.substring(0, 2).toUpperCase();

  return (
    <div className="mt-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-2xl font-black text-white">
          {initials}
        </div>
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">{profile.name}</h1>
          <div className="flex items-center gap-3 mt-1">
            {profile.discord_linked && (
              <span className="px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 text-xs font-bold">Discord Linked</span>
            )}
            {profile.aliases.length > 0 && (
              <span className="text-xs text-slate-500">
                aka {profile.aliases.join(', ')}
              </span>
            )}
            <span className="text-xs text-slate-500">Last seen: {s.last_seen ? formatDate(s.last_seen) : 'Unknown'}</span>
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4 mb-6">
        <KpiTile label="Kills" value={formatNumber(s.kills)} icon={Skull} color="text-rose-500" />
        <KpiTile label="Deaths" value={formatNumber(s.deaths)} icon={Shield} color="text-slate-400" />
        <KpiTile label="K/D Ratio" value={s.kd.toFixed(2)} icon={Crosshair} color="text-purple-500" />
        <KpiTile label="DPM" value={formatNumber(s.dpm)} icon={Zap} color="text-blue-500" />
        <KpiTile label="Damage" value={formatNumber(s.damage)} icon={Swords} color="text-amber-400" />
        <KpiTile label="Total XP" value={formatNumber(s.total_xp)} icon={Star} color="text-amber-300" />
        <KpiTile label="Rounds" value={formatNumber(s.games)} icon={Gamepad2} color="text-indigo-400" />
        <KpiTile label="Win Rate" value={`${s.win_rate}%`} icon={Crown} color="text-emerald-400" />
        <KpiTile label="Playtime" value={`${s.playtime_hours}h`} icon={Clock} color="text-cyan-500" />
        {s.favorite_weapon && (
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              {weaponIcon(s.favorite_weapon) ? (
                <img src={weaponIcon(s.favorite_weapon)!} alt="" className="h-4 object-contain opacity-70" style={{ filter: 'brightness(1.6)' }} />
              ) : (
                <Target className="w-4 h-4 text-orange-400" />
              )}
              <span className="text-xs text-slate-500 uppercase font-bold">Fav Weapon</span>
            </div>
            <div className="text-2xl font-black text-white">{s.favorite_weapon}</div>
          </div>
        )}
        {s.favorite_map && (
          <div className="glass-card rounded-xl p-4 relative overflow-hidden">
            <img src={mapLevelshot(s.favorite_map)} alt="" className="absolute inset-0 w-full h-full object-cover opacity-20" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
            <div className="relative">
              <div className="flex items-center gap-2 mb-1">
                <Target className="w-4 h-4 text-green-400" />
                <span className="text-xs text-slate-500 uppercase font-bold">Fav Map</span>
              </div>
              <div className="text-2xl font-black text-white">{s.favorite_map}</div>
            </div>
          </div>
        )}
        {s.highest_dpm != null && <KpiTile label="Peak DPM" value={formatNumber(s.highest_dpm)} icon={Zap} color="text-red-400" />}
      </div>

      {/* Win/Loss */}
      <div className="glass-panel rounded-xl p-5 mb-6">
        <h3 className="text-sm font-bold text-slate-400 uppercase mb-3">Win / Loss</h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-emerald-400 font-bold">{s.wins} W</span>
              <span className="text-rose-400 font-bold">{s.losses} L</span>
            </div>
            <div className="h-3 rounded-full bg-slate-700 overflow-hidden flex">
              <div className="bg-emerald-500 h-full" style={{ width: `${s.win_rate}%` }} />
              <div className="bg-rose-500 h-full" style={{ width: `${100 - s.win_rate}%` }} />
            </div>
          </div>
          <div className="text-2xl font-black text-white">{s.win_rate}%</div>
        </div>
      </div>

      {/* Achievements */}
      {profile.achievements.length > 0 && (
        <div className="glass-panel rounded-xl p-5 mb-6">
          <h3 className="text-sm font-bold text-slate-400 uppercase mb-3">
            Achievements ({profile.achievements.filter((a) => a.unlocked).length}/{profile.achievements.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {profile.achievements.map((a) => (
              <AchievementBadge key={a.name} achievement={a} />
            ))}
          </div>
        </div>
      )}

      {/* Recent Rounds */}
      {rounds && rounds.length > 0 && (
        <div className="glass-panel rounded-xl p-5">
          <h3 className="text-sm font-bold text-slate-400 uppercase mb-3">Recent Rounds</h3>
          <DataTable
            columns={roundColumns}
            data={rounds}
            keyFn={(row) => `${row.round_id}`}
            defaultSort={{ key: 'round_date', dir: 'desc' }}
          />
        </div>
      )}
    </div>
  );
}

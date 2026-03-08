import { useState, useMemo } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { ChartCanvas } from '../components/Chart';
import { Skeleton } from '../components/Skeleton';
import { useOverview, useLiveStatus, useTrends, useSeason } from '../api/hooks';
import { navigateTo } from '../lib/navigation';
import { formatNumber } from '../lib/format';
import { mapLevelshot, etLogo } from '../lib/game-assets';

function StatCard({
  label,
  value,
  sub,
  sub2,
  borderColor,
}: {
  label: string;
  value: string;
  sub?: string;
  sub2?: string;
  borderColor: string;
}) {
  return (
    <GlassPanel className={`!p-4 border-l-4 ${borderColor}`}>
      <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1">{label}</div>
      <div className="text-2xl font-black font-mono text-white">{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-1">{sub}</div>}
      {sub2 && <div className="text-[11px] text-slate-500">{sub2}</div>}
    </GlassPanel>
  );
}

function ServerCard() {
  const { data } = useLiveStatus();
  if (!data) {
    return (
      <GlassPanel className="!p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-slate-700/50 animate-pulse" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-24 bg-slate-700/50 rounded animate-pulse" />
            <div className="h-3 w-40 bg-slate-700/50 rounded animate-pulse" />
          </div>
        </div>
      </GlassPanel>
    );
  }

  const server = data.game_server;
  const badge = server.online
    ? { text: 'ONLINE', cls: 'bg-emerald-500/20 text-emerald-400' }
    : { text: 'OFFLINE', cls: 'bg-red-500/20 text-red-400' };

  return (
    <GlassPanel className={`!p-4 ${server.online && server.player_count > 0 ? 'border-emerald-500/30' : ''}`}>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-slate-800 overflow-hidden shrink-0">
          {server.online && server.map ? (
            <img src={mapLevelshot(server.map)} alt={server.map} className="w-full h-full object-cover" onError={(e) => { e.currentTarget.parentElement!.textContent = '🖥'; }} />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-400 text-lg">🖥</div>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-bold text-slate-500 uppercase">Game Server</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${badge.cls}`}>{badge.text}</span>
          </div>
          {server.online ? (
            <div className="text-sm text-slate-400 truncate">
              <span className="text-white font-semibold">{server.hostname || 'Server'}</span>
              <span className="text-slate-500 mx-1">·</span>
              <span className="text-cyan-400">{server.map}</span>
              <span className="text-slate-500 mx-1">·</span>
              {server.player_count > 0 ? (
                <span>{server.players.map((p) => p.name).join(', ')}</span>
              ) : (
                <span className="text-slate-500">{server.player_count}/{server.max_players} players</span>
              )}
            </div>
          ) : (
            <div className="text-sm text-red-400/70">{server.error || 'Not responding'}</div>
          )}
        </div>
        {server.online && server.player_count > 0 && (
          <div className="text-right">
            <div className="text-2xl font-black text-white">{server.player_count}</div>
            <div className="text-[10px] text-slate-500 uppercase">Players</div>
          </div>
        )}
      </div>
    </GlassPanel>
  );
}

function VoiceCard() {
  const { data } = useLiveStatus();
  if (!data) return null;

  const voice = data.voice_channel;
  const active = voice.count > 0;

  return (
    <GlassPanel className={`!p-4 ${active ? 'border-purple-500/30' : ''}`}>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center text-slate-400 text-lg">🎙</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-bold text-slate-500 uppercase">Voice Channel</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${active ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-700 text-slate-400'}`}>
              {active ? 'ACTIVE' : 'EMPTY'}
            </span>
          </div>
          <div className="text-sm text-slate-400">
            {active ? <span className="text-white">{voice.members.map((m) => m.name).join(', ')}</span> : 'No one in voice'}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-black text-white">{voice.count}</div>
          <div className="text-[10px] text-slate-500 uppercase">Online</div>
        </div>
      </div>
    </GlassPanel>
  );
}

function SeasonWidget() {
  const { data } = useSeason();
  if (!data) return null;

  const start = new Date(data.start_date);
  const end = new Date(data.end_date);
  const now = new Date();
  const totalDays = Math.max(1, (end.getTime() - start.getTime()) / 86400000);
  const elapsed = Math.max(0, (now.getTime() - start.getTime()) / 86400000);
  const pct = Math.min(100, (elapsed / totalDays) * 100);

  return (
    <GlassPanel className="!p-5 border-l-4 border-amber-400">
      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">Current Season</div>
      <div className="text-2xl font-black text-white mt-1">{data.name}</div>
      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden mt-3">
        <div className="bg-amber-400 h-full transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-slate-500 mt-2">
        <span>{start.toLocaleDateString()} – {end.toLocaleDateString()}</span>
        <span>{data.days_left} days left</span>
      </div>
    </GlassPanel>
  );
}

function InsightsCharts({ days }: { days: number }) {
  const { data, isLoading } = useTrends(days);

  const roundsChartData = useMemo(() => {
    if (!data?.dates) return null;
    const labels = data.dates.map((d) => {
      const dt = new Date(d + 'T00:00:00');
      return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    });
    return {
      labels,
      datasets: [
        {
          data: data.rounds,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,0.1)',
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          pointRadius: days <= 14 ? 3 : 0,
          pointBackgroundColor: '#3b82f6',
        },
      ],
    };
  }, [data, days]);

  const playersChartData = useMemo(() => {
    if (!data?.dates) return null;
    const labels = data.dates.map((d) => {
      const dt = new Date(d + 'T00:00:00');
      return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    });
    return {
      labels,
      datasets: [
        {
          data: data.active_players,
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6,182,212,0.12)',
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          pointRadius: days <= 14 ? 3 : 0,
          pointBackgroundColor: '#06b6d4',
        },
      ],
    };
  }, [data, days]);

  const mapsChartData = useMemo(() => {
    if (!data?.map_distribution) return null;
    const entries = Object.entries(data.map_distribution)
      .filter(([n, c]) => n.trim() && c > 0)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
    if (entries.length === 0) return null;
    const colors = ['#3b82f6', '#06b6d4', '#8b5cf6', '#10b981', '#f43f5e', '#f59e0b', '#ec4899', '#6366f1'];
    return {
      labels: entries.map(([n]) => n),
      datasets: [
        {
          data: entries.map(([, c]) => c),
          backgroundColor: entries.map((_, i) => colors[i % colors.length] + 'bf'),
          borderColor: entries.map((_, i) => colors[i % colors.length]),
          borderWidth: 1,
        },
      ],
    };
  }, [data]);

  const chartOpts = useMemo(
    () => ({
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15,23,42,0.9)',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#64748b', font: { size: 10 }, maxTicksLimit: 7 },
        },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#64748b', font: { size: 10 } },
          beginAtZero: true,
        },
      },
    }),
    [],
  );

  const barOpts = useMemo(
    () => ({
      indexAxis: 'y' as const,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(15,23,42,0.9)',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { color: '#64748b', font: { size: 10 } },
          beginAtZero: true,
        },
        y: {
          grid: { display: false },
          ticks: { color: '#e2e8f0', font: { size: 10 } },
        },
      },
    }),
    [],
  );

  if (isLoading) return <Skeleton variant="card" count={3} />;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <GlassPanel>
        <h3 className="text-sm font-bold text-white mb-1">Rounds per Day</h3>
        <p className="text-[11px] text-slate-500 mb-3">Daily round activity</p>
        {roundsChartData ? (
          <ChartCanvas type="line" data={roundsChartData} options={chartOpts} height="200px" />
        ) : (
          <div className="h-[200px] flex items-center justify-center text-xs text-slate-500">No data</div>
        )}
      </GlassPanel>
      <GlassPanel>
        <h3 className="text-sm font-bold text-white mb-1">Active Players per Day</h3>
        <p className="text-[11px] text-slate-500 mb-3">Unique players each day</p>
        {playersChartData ? (
          <ChartCanvas type="line" data={playersChartData} options={chartOpts} height="200px" />
        ) : (
          <div className="h-[200px] flex items-center justify-center text-xs text-slate-500">No data</div>
        )}
      </GlassPanel>
      <GlassPanel>
        <h3 className="text-sm font-bold text-white mb-1">Map Distribution</h3>
        <p className="text-[11px] text-slate-500 mb-3">Most played maps</p>
        {mapsChartData ? (
          <ChartCanvas type="bar" data={mapsChartData} options={barOpts} height="200px" />
        ) : (
          <div className="h-[200px] flex items-center justify-center text-xs text-slate-500">No data</div>
        )}
      </GlassPanel>
    </div>
  );
}

function PlayerSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Array<{ name: string; guid: string }>>([]);
  const [open, setOpen] = useState(false);

  const handleSearch = async (q: string) => {
    setQuery(q);
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=8`);
      if (res.ok) {
        const data = await res.json();
        setResults(Array.isArray(data) ? data : data.players || []);
        setOpen(true);
      }
    } catch { /* ignore */ }
  };

  return (
    <div className="relative max-w-xl mx-auto">
      <div className="absolute -inset-1 bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl blur opacity-25" />
      <div className="relative flex items-center bg-slate-900 border border-white/10 rounded-xl p-2 shadow-2xl">
        <span className="ml-3 text-slate-400 text-lg">🔍</span>
        <input
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          className="w-full bg-transparent border-none text-white placeholder-slate-500 focus:ring-0 focus:outline-none px-4 py-2 text-lg font-medium"
          placeholder="Search player (e.g. BAMBAM)..."
        />
      </div>
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-50">
          {results.map((p) => (
            <button
              key={p.guid || p.name}
              className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors border-b border-white/5 last:border-0"
              onMouseDown={() => {
                navigateTo(`#/profile?name=${encodeURIComponent(p.name)}`);
                setOpen(false);
                setQuery('');
              }}
            >
              <span className="text-sm font-bold text-white">{p.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const { data: overview, isLoading } = useOverview();
  const [insightsDays, setInsightsDays] = useState(14);

  return (
    <div>
      {/* Hero */}
      <div className="relative pt-12 pb-20 text-center">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-blue-500/20 rounded-full blur-[120px] -z-10" />

        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-cyan-400 text-xs font-bold mb-8">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400" />
          </span>
          SEASON 4 IS LIVE
        </div>

        <img src={etLogo()} alt="Enemy Territory" className="h-16 md:h-20 mx-auto mb-6 opacity-80 drop-shadow-2xl" onError={(e) => { e.currentTarget.style.display = 'none'; }} />

        <h1 className="text-6xl md:text-8xl font-black text-white tracking-tight mb-6 leading-tight">
          TRACK YOUR <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-500 via-cyan-400 to-purple-500">
            LEGACY
          </span>
        </h1>

        <p className="text-lg text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
          Track every frag, analyze every round, celebrate every victory.
        </p>

        <PlayerSearch />
      </div>

      {/* Stats Grid */}
      {isLoading ? (
        <Skeleton variant="card" count={6} />
      ) : overview ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-8">
          <StatCard
            label="Rounds Tracked"
            value={formatNumber(overview.rounds)}
            sub={overview.rounds_since ? `Since ${new Date(overview.rounds_since).toLocaleDateString()}` : undefined}
            sub2={`Last ${overview.window_days}d: ${formatNumber(overview.rounds_14d)}`}
            borderColor="border-blue-500/60"
          />
          <StatCard
            label={`Active Players (${overview.window_days}d)`}
            value={formatNumber(overview.players_14d)}
            sub={`All-time: ${formatNumber(overview.players_all_time)}`}
            borderColor="border-cyan-500/60"
          />
          <StatCard
            label="Most Active (All-time)"
            value={overview.most_active_overall?.name || '--'}
            sub={overview.most_active_overall ? `${overview.most_active_overall.rounds} rounds` : undefined}
            borderColor="border-amber-500/60"
          />
          <StatCard
            label={`Most Active (${overview.window_days}d)`}
            value={overview.most_active_14d?.name || '--'}
            sub={overview.most_active_14d ? `${overview.most_active_14d.rounds} rounds` : undefined}
            borderColor="border-emerald-500/60"
          />
          <StatCard
            label="Gaming Sessions"
            value={formatNumber(overview.sessions)}
            sub={`Last ${overview.window_days}d: ${formatNumber(overview.sessions_14d)}`}
            borderColor="border-purple-500/60"
          />
          <StatCard
            label="Total Kills"
            value={formatNumber(overview.total_kills)}
            sub={`Last ${overview.window_days}d: ${formatNumber(overview.total_kills_14d)}`}
            borderColor="border-rose-500/60"
          />
        </div>
      ) : null}

      {/* Live Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <ServerCard />
        <VoiceCard />
      </div>

      {/* Season */}
      <div className="mb-8">
        <SeasonWidget />
      </div>

      {/* Insights */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Community Insights</h2>
            <span className="text-[10px] text-slate-600 uppercase tracking-widest">Trends</span>
          </div>
          <div className="flex gap-1">
            {[14, 30, 90].map((d) => (
              <button
                key={d}
                onClick={() => setInsightsDays(d)}
                className={`px-2.5 py-1 rounded text-xs font-bold transition ${
                  insightsDays === d ? 'bg-blue-500/20 text-blue-400' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
        <InsightsCharts days={insightsDays} />
      </div>
    </div>
  );
}

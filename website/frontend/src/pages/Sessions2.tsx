import { useState, useCallback, useRef } from 'react';
import { Calendar, Users, Map, Gamepad2, ChevronRight, Search, X } from 'lucide-react';
import { useSessions } from '../api/hooks';
import type { SessionSummary } from '../api/types';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { cn } from '../lib/cn';
import { formatNumber } from '../lib/format';
import { navigateTo } from '../lib/navigation';
import { mapLevelshot } from '../lib/game-assets';

const PAGE_SIZE = 15;

function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return '';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`;
}

function stripEtColors(text: string): string {
  return text.replace(/\^[0-9A-Za-z]/g, '');
}

function mapLabel(name: string): string {
  return name.replace(/^maps[\\/]/, '').replace(/\.(bsp|pk3|arena)$/i, '').replace(/_/g, ' ');
}

function SessionCard({ session }: { session: SessionSummary }) {
  const roundCount = session.round_count ?? session.rounds ?? 0;
  const playerCount = session.player_count ?? session.players ?? 0;
  const mapsPlayed = session.maps_played ?? [];
  const mapCount = mapsPlayed.length || (session.maps ?? 0);
  const durationStr = formatDuration(session.duration_seconds);
  const timeRange = (session.start_time && session.end_time)
    ? `${session.start_time} — ${session.end_time}` : '';
  const missingRounds = roundCount % 2 !== 0;
  const playerNames = (session.player_names ?? []).map(stripEtColors).filter(Boolean);
  const alliesWins = session.allies_wins ?? 0;
  const axisWins = session.axis_wins ?? 0;
  const scoreColor = alliesWins > axisWins
    ? 'text-blue-400' : axisWins > alliesWins ? 'text-rose-400' : 'text-slate-400';

  function handleClick() {
    if (session.session_id) {
      navigateTo(`#/session-detail/${session.session_id}`);
    } else {
      navigateTo(`#/session-detail/date/${encodeURIComponent(session.date)}`);
    }
  }

  return (
    <GlassCard onClick={handleClick} className="group">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center shrink-0">
            <Calendar className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="text-lg font-black text-white">
              {session.formatted_date || session.date}
            </div>
            <div className="text-sm text-slate-400 flex flex-wrap items-center gap-2">
              {session.time_ago && <span>{session.time_ago}</span>}
              {timeRange && <><span className="text-slate-600">·</span><span>{timeRange}</span></>}
              {durationStr && <><span className="text-slate-600">·</span><span className="text-slate-500">{durationStr}</span></>}
              {session.session_id && (
                <span className="px-2 py-0.5 rounded-full bg-slate-800 text-[10px] uppercase tracking-wide text-slate-400">
                  Session {session.session_id}
                </span>
              )}
              {missingRounds && (
                <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] uppercase">
                  Missing Round
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          <Stat icon={Users} value={playerCount} label="Players" color="text-brand-cyan" />
          <Stat icon={Map} value={mapCount} label="Maps" color="text-brand-purple" />
          <Stat icon={Gamepad2} value={roundCount} label="Rounds" color="text-brand-amber" />
          {session.total_kills > 0 && (
            <Stat icon={null} value={formatNumber(session.total_kills)} label="Kills" color="text-brand-emerald" />
          )}
          <div className="text-center">
            <div className={cn('text-2xl font-black', scoreColor)}>{alliesWins} - {axisWins}</div>
            <div className="text-xs text-slate-500 uppercase">Score</div>
          </div>
        </div>

        <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-blue-400 transition" />
      </div>

      <div className="mt-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {mapsPlayed.slice(0, 5).map((m) => (
            <span key={m} className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 font-medium">
              <img src={mapLevelshot(m)} alt="" className="w-4 h-4 rounded-sm object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />
              {mapLabel(m)}
            </span>
          ))}
          {mapsPlayed.length > 5 && (
            <span className="text-slate-500 text-xs">+{mapsPlayed.length - 5} more</span>
          )}
        </div>
        {playerNames.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <Users className="w-3.5 h-3.5 text-slate-500 shrink-0" />
            {playerNames.map((name) => (
              <span key={name} className="px-2 py-0.5 rounded-full bg-slate-800/80 text-xs text-slate-300 font-medium">
                {name}
              </span>
            ))}
          </div>
        )}
      </div>
    </GlassCard>
  );
}

function Stat({ icon: Icon, value, label, color }: {
  icon: typeof Users | null;
  value: number | string;
  label: string;
  color: string;
}) {
  return (
    <div className="text-center">
      <div className={cn('text-2xl font-black', color)}>{value}</div>
      <div className="text-xs text-slate-500 uppercase">{label}</div>
    </div>
  );
}

export default function Sessions2() {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const timerRef = useRef<ReturnType<typeof setTimeout>>(null);
  const [offset, setOffset] = useState(0);

  const { data, isLoading, isError } = useSessions({
    limit: PAGE_SIZE,
    offset,
    search: debouncedSearch || undefined,
  });

  const handleSearch = useCallback((val: string) => {
    setSearch(val);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedSearch(val);
      setOffset(0);
    }, 300);
  }, []);

  const clearSearch = useCallback(() => {
    setSearch('');
    setDebouncedSearch('');
    setOffset(0);
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  const hasMore = (data?.length ?? 0) >= PAGE_SIZE;

  return (
    <div className="mt-6">
      <PageHeader title="Sessions" subtitle="Gaming session history" />

      <div className="relative mb-6 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search sessions by player or map..."
          className="w-full pl-10 pr-10 py-2.5 bg-slate-800 border border-white/10 text-slate-200 rounded-lg text-sm
                     focus:outline-none focus:border-blue-500/50 placeholder:text-slate-500"
        />
        {search && (
          <button onClick={clearSearch} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {debouncedSearch && data && (
        <div className="text-sm text-slate-400 mb-4">
          {data.length} session{data.length !== 1 ? 's' : ''} found for "{debouncedSearch}"
        </div>
      )}

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton variant="card" count={3} className="grid-cols-1" />
        </div>
      ) : isError ? (
        <div className="text-center text-red-400 py-12">Failed to load sessions.</div>
      ) : !data || data.length === 0 ? (
        <EmptyState message={debouncedSearch ? `No sessions found for "${debouncedSearch}".` : 'No sessions available yet.'} />
      ) : (
        <div className="space-y-4">
          {data.map((session, i) => (
            <SessionCard key={session.session_id ?? `${session.date}-${i}`} session={session} />
          ))}

          {hasMore && (
            <div className="text-center pt-4">
              <button
                onClick={() => setOffset((o) => o + PAGE_SIZE)}
                className="px-6 py-2.5 rounded-lg bg-blue-500/20 text-blue-400 font-bold text-sm hover:bg-blue-500/30 transition"
              >
                Load More
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

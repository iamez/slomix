import { useMemo, useRef, useState } from 'react';
import { CalendarDays, ChevronRight, Clock3, Gamepad2, Search, Users, X } from 'lucide-react';
import type { SessionSummary } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { useSessions } from '../api/hooks';
import { mapLevelshot } from '../lib/game-assets';
import { formatNumber, formatDurationHM as formatDuration } from '../lib/format';
import { navigateTo } from '../lib/navigation';

const PAGE_SIZE = 15;

function mapLabel(name: string): string {
  return (name || 'Unknown').replace(/^maps[\\/]/, '').replace(/\.(bsp|pk3|arena)$/i, '').replace(/_/g, ' ');
}

function stripEtColors(text: string): string {
  return text.replace(/\^[0-9A-Za-z]/g, '');
}

function sessionHash(session: SessionSummary) {
  return session.session_id
    ? `#/session-detail/${session.session_id}`
    : `#/session-detail/date/${encodeURIComponent(session.date)}`;
}

function SessionCard({ session }: { session: SessionSummary }) {
  const primaryMap = session.maps_played[0];
  const playerNames = session.player_names.slice(0, 4).map(stripEtColors).filter(Boolean);
  const scoreLabel = `${session.allies_wins ?? 0} : ${session.axis_wins ?? 0}`;

  function openDetail() {
    if (session.session_id) {
      navigateTo(`#/session-detail/${session.session_id}`);
      return;
    }
    navigateTo(`#/session-detail/date/${encodeURIComponent(session.date)}`);
  }

  return (
    <GlassCard onClick={openDetail} className="p-5 md:p-6">
      <div className="grid gap-5 lg:grid-cols-[0.85fr_1.15fr_auto] lg:items-center">
        <div className="flex items-center gap-4">
          <div className="h-18 w-18 overflow-hidden rounded-[22px] bg-slate-900/80 md:h-20 md:w-20">
            {primaryMap ? (
              <img
                src={mapLevelshot(primaryMap)}
                alt={mapLabel(primaryMap)}
                className="h-full w-full object-cover"
                onError={(event) => { event.currentTarget.style.display = 'none'; }}
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-cyan-300">
                <CalendarDays className="h-6 w-6" />
              </div>
            )}
          </div>

          <div className="min-w-0">
            <div className="section-kicker mb-1">Session</div>
            <div className="truncate text-2xl font-black text-white">{session.formatted_date || session.date}</div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
              {session.time_ago && <span>{session.time_ago}</span>}
              {session.start_time && session.end_time && <span>{session.start_time} to {session.end_time}</span>}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(session.maps_played || []).slice(0, 3).map((mapName) => (
                <span key={mapName} className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-bold text-slate-300">
                  {mapLabel(mapName)}
                </span>
              ))}
              {(session.maps_played || []).length > 3 && (
                <span className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-xs font-bold text-slate-300">
                  +{session.maps_played.length - 3} more
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SessionFact icon={Users} label="Players" value={formatNumber(session.player_count || session.players || 0)} accent="text-white" />
          <SessionFact icon={Gamepad2} label="Rounds" value={formatNumber(session.round_count || session.rounds || 0)} accent="text-cyan-300" />
          <SessionFact icon={Clock3} label="Duration" value={formatDuration(session.duration_seconds)} accent="text-amber-300" />
          <SessionFact icon={CalendarDays} label="Score" value={scoreLabel} accent="text-rose-300" />
        </div>

        <div className="flex items-center justify-between gap-4 lg:flex-col lg:items-end">
          <div className="text-right">
            <div className="section-kicker mb-1">Quick read</div>
            <div className="text-sm font-bold text-white">
              {playerNames.length > 0 ? playerNames.join(', ') : 'Roster available in detail'}
            </div>
          </div>
          <div className="inline-flex items-center gap-2 text-sm font-bold text-cyan-300">
            Open detail
            <ChevronRight className="h-4 w-4" />
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function SessionFact({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: typeof Users;
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="rounded-[20px] border border-white/8 bg-white/[0.03] p-4">
      <Icon className={`h-4 w-4 ${accent}`} />
      <div className={`mt-3 text-xl font-black ${accent}`}>{value}</div>
      <div className="mt-1 text-[11px] font-bold uppercase tracking-[0.22em] text-slate-500">{label}</div>
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

  const sessions = data ?? [];
  const hasMore = sessions.length >= PAGE_SIZE;

  const summaryText = useMemo(() => {
    if (!sessions.length) return 'No sessions loaded yet.';
    const totalPlayers = sessions.reduce((sum, session) => sum + (session.player_count || 0), 0);
    const totalRounds = sessions.reduce((sum, session) => sum + (session.round_count || 0), 0);
    return `${sessions.length} sessions · ${formatNumber(totalPlayers)} player slots · ${formatNumber(totalRounds)} rounds`;
  }, [sessions]);

  function handleSearch(value: string) {
    setSearch(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedSearch(value);
      setOffset(0);
    }, 250);
  }

  function clearSearch() {
    setSearch('');
    setDebouncedSearch('');
    setOffset(0);
    if (timerRef.current) clearTimeout(timerRef.current);
  }

  if (isLoading) {
    return (
      <div className="page-shell">
        <PageHeader
          title="Sessions"
          subtitle="The archive is now browse-first instead of overloaded at first glance."
          eyebrow="Everyday Browsing"
        />
        <Skeleton variant="card" count={4} className="grid-cols-1" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-shell">
        <PageHeader title="Sessions" subtitle="Failed to load session archive." eyebrow="Everyday Browsing" />
        <div className="text-center text-red-400 py-12">Failed to load sessions.</div>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <PageHeader
        title="Sessions"
        subtitle="Archive is now a cleaner browse layer, while Home stays the quickest path into the newest session."
        eyebrow="Everyday Browsing"
        badge={summaryText}
      />

      <div className="glass-panel rounded-[26px] p-4 md:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-300" />
            <input
              type="text"
              value={search}
              onChange={(event) => handleSearch(event.target.value)}
              placeholder="Search sessions by player or map..."
              className="w-full rounded-[20px] border border-white/10 bg-slate-900/80 py-3.5 pl-11 pr-11 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400/45"
            />
            {search && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 transition hover:bg-white/6 hover:text-white"
                aria-label="Clear search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => navigateTo(sessions[0] ? sessionHash(sessions[0]) : '#/sessions2')}
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-300 transition hover:text-white"
            >
              Open Newest Session
            </button>
            <button
              type="button"
              onClick={() => navigateTo('#/profile')}
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs font-bold text-slate-300 transition hover:text-white"
            >
              Player Lookup
            </button>
          </div>
        </div>
      </div>

      {debouncedSearch && (
        <div className="text-sm text-slate-400">
          Showing {sessions.length} result{sessions.length !== 1 ? 's' : ''} for "{debouncedSearch}".
        </div>
      )}

      {!sessions.length ? (
        <EmptyState message={debouncedSearch ? `No sessions found for "${debouncedSearch}".` : 'No sessions available yet.'} />
      ) : (
        <div className="space-y-4">
          {sessions.map((session, index) => (
            <SessionCard key={session.session_id ?? `${session.date}-${index}`} session={session} />
          ))}
        </div>
      )}

      {hasMore && (
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setOffset((current) => current + PAGE_SIZE)}
            className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 px-5 py-3 text-sm font-black text-cyan-200 transition hover:bg-cyan-400/16"
          >
            Load More Sessions
          </button>
        </div>
      )}
    </div>
  );
}

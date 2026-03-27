import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useStoryKillImpact, useStoryMoments } from '../api/hooks';
import type { KillImpactEntry } from '../api/types';
import { Skeleton } from '../components/Skeleton';
import { StoryHero } from '../components/story/StoryHero';
import { PlayerStoryCard } from '../components/story/PlayerStoryCard';
import { MomentCard } from '../components/story/MomentCard';
import type { PlayerArchetype } from '../components/story/ArchetypeBadge';

const API = '/api';

/* ── Scopes (reuse proximity scopes endpoint) ── */

interface ScopeSession {
  session_date: string;
  maps: Array<{ map_name: string }>;
}
interface ScopeData {
  sessions: ScopeSession[];
  scope?: { session_date: string };
}

/* ── Archetype from server response ── */

const VALID_ARCHETYPES = new Set<PlayerArchetype>([
  'pressure_engine', 'medic_anchor', 'silent_assassin', 'frontline_warrior',
  'wall_breaker', 'objective_specialist', 'trade_master', 'survivor', 'chaos_agent',
]);

function getArchetype(player: KillImpactEntry): PlayerArchetype {
  const a = player.archetype as PlayerArchetype | undefined;
  return a && VALID_ARCHETYPES.has(a) ? a : 'frontline_warrior';
}

/* ── CSS Animations (injected once) ── */

const STORY_STYLES = `
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes gradientShift {
  0%   { background-position: 0% 50%; }
  50%  { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
`;

/* ── Main Page ── */

export default function Story() {
  const [sessionDate, setSessionDate] = useState<string | null>(null);

  // Fetch available sessions
  const { data: scopes, isLoading: scopesLoading } = useQuery<ScopeData>({
    queryKey: ['proximity-scopes'],
    queryFn: () => fetch(`${API}/proximity/scopes?range_days=365`).then((r) => r.json()),
    staleTime: 60_000,
  });

  // Auto-select first session
  useEffect(() => {
    if (!sessionDate && scopes?.sessions?.length) {
      setSessionDate(scopes.scope?.session_date ?? scopes.sessions[0].session_date);
    }
  }, [scopes, sessionDate]);

  // KIS data
  const { data: kis, isLoading: kisLoading } = useStoryKillImpact(sessionDate);
  // Moments data
  const { data: momentsData, isLoading: momentsLoading } = useStoryMoments(sessionDate);

  const entries = useMemo(() => kis?.entries ?? [], [kis]);
  const totalKills = kis?.total_kills ?? 0;
  const moments = useMemo(() => momentsData?.moments ?? [], [momentsData]);

  // Current session metadata
  const currentSession = scopes?.sessions?.find((s) => s.session_date === sessionDate);
  const mapNames = currentSession?.maps?.map((m) => m.map_name) ?? [];

  return (
    <>
      <style>{STORY_STYLES}</style>

      <div className="space-y-6">
        {/* Hero header */}
        {sessionDate && !kisLoading ? (
          <StoryHero
            sessionDate={sessionDate}
            mapNames={mapNames}
            playerCount={entries.length}
            totalKills={totalKills}
            entryCount={entries.length}
          />
        ) : kisLoading ? (
          <div className="glass-panel rounded-[30px] p-10 animate-pulse">
            <div className="h-6 w-32 rounded bg-slate-700/50 mb-4" />
            <div className="h-12 w-64 rounded bg-slate-700/50 mb-3" />
            <div className="h-5 w-48 rounded bg-slate-700/50" />
          </div>
        ) : null}

        {/* Session selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-500 uppercase tracking-wider font-bold">Session</label>
          <select
            value={sessionDate ?? ''}
            onChange={(e) => setSessionDate(e.target.value || null)}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white backdrop-blur-sm focus:border-cyan-400/50 focus:outline-none"
          >
            {scopesLoading && <option value="">Loading...</option>}
            {scopes?.sessions?.map((s) => (
              <option key={s.session_date} value={s.session_date}>
                {s.session_date} — {s.maps.length} map{s.maps.length !== 1 ? 's' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Match Moments — horizontal scroll */}
        {momentsLoading ? (
          <div className="flex gap-4 overflow-hidden">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex-shrink-0 w-72 h-32 rounded-2xl bg-slate-700/20 animate-pulse" />
            ))}
          </div>
        ) : moments.length > 0 ? (
          <div>
            <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-3">Match Moments</h3>
            <div className="flex gap-4 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-slate-700">
              {moments.map((m, i) => (
                <MomentCard key={`${m.type}-${m.time_ms}-${i}`} moment={m} index={i} />
              ))}
            </div>
          </div>
        ) : null}

        {/* Player story cards */}
        {kisLoading ? (
          <Skeleton variant="card" count={6} />
        ) : entries.length === 0 ? (
          <div className="glass-card rounded-[24px] p-8 border border-white/8 text-center">
            <p className="text-slate-500 text-sm">No KIS data for this session yet.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {entries.map((entry, i) => (
              <PlayerStoryCard
                key={entry.guid}
                entry={entry}
                rank={i + 1}
                archetype={getArchetype(entry)}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

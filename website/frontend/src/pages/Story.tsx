import { useState, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  useStoryKillImpact, useStoryMoments, useStoryMomentum, useStoryNarrative, usePlayerNarratives,
  useStoryGravity, useStorySpaceCreated, useStoryEnabler, useStoryLurkerProfile,
  useStorySynergy, useStoryWinContribution, useStoryBoxScore, useStoryComposite,
} from '../api/hooks';
import type { StoryScope } from '../api/client';
import type { KillImpactEntry } from '../api/types';
import { Skeleton } from '../components/Skeleton';
import { StoryHero } from '../components/story/StoryHero';
import { PlayerStoryCard } from '../components/story/PlayerStoryCard';
import { MomentCard } from '../components/story/MomentCard';
import { MomentumChart } from '../components/story/MomentumChart';
import { NarrativePanel } from '../components/story/NarrativePanel';
import { PlayerNarrativesPanel } from '../components/story/PlayerNarrativesPanel';
import { InvisibleValuePanel } from '../components/story/InvisibleValuePanel';
import { CompositeStatsPanel } from '../components/story/CompositeStatsPanel';
import { WinContributionPanel } from '../components/story/WinContributionPanel';
import { TeamSynergyPanel } from '../components/story/TeamSynergyPanel';
import { BoxScorePanel } from '../components/story/BoxScorePanel';
import type { PlayerArchetype } from '../components/story/ArchetypeBadge';

const API = '/api';

/* ── Scopes (Codex SS-D: gsid-native /storytelling/scopes, NOT
 * /proximity/scopes — the latter groups by calendar session_date only and
 * has no gaming_session_id at all, the root cause of the page's original
 * date-only selector) ── */

interface ScopeSession {
  gaming_session_id: number;
  start_date: string;
  end_date: string;
  accepted_round_count: number;
  distinct_map_names: string[];
}
interface ScopeData {
  scope_version: string;
  sessions: ScopeSession[];
}

function sessionDateLabel(s: { start_date: string; end_date: string } | undefined): string {
  if (!s) return '';
  return s.start_date === s.end_date ? s.start_date : `${s.start_date} → ${s.end_date}`;
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

export default function Story({ params }: { params?: Record<string, string> }) {
  // Deep-link support (Codex SS-D): #/story/session/<gsid> (preferred,
  // unambiguous) or the legacy #/story/date/<date>. Parsed once on mount —
  // params don't change without a full remount of this lazy-loaded page.
  const initialGsid = useMemo(() => {
    const raw = params?.gsid;
    if (!raw) return null;
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : null;
  }, [params]);

  const [gamingSessionId, setGamingSessionId] = useState<number | null>(initialGsid);
  // Single ISO date — used both as the legacy resolution input (when no
  // gsid is known yet) and as the one param useStoryComposite still needs
  // (/skill/composite is a different router, outside this program's
  // gsid conversion).
  const [sessionDate, setSessionDate] = useState<string | null>(
    initialGsid == null ? (params?.date ?? null) : null,
  );

  // Fetch available sessions
  const { data: scopes, isLoading: scopesLoading } = useQuery<ScopeData>({
    queryKey: ['storytelling-scopes'],
    queryFn: () => fetch(`${API}/storytelling/scopes?limit=100`).then((r) => r.json()),
    staleTime: 60_000,
  });

  // Auto-select the newest session when nothing was requested via deep link.
  useEffect(() => {
    if (gamingSessionId == null && !sessionDate && scopes?.sessions.length) {
      setGamingSessionId(scopes.sessions[0].gaming_session_id);
    }
  }, [scopes, gamingSessionId, sessionDate]);

  const scope: StoryScope | null = useMemo(() => {
    if (gamingSessionId != null) return { gamingSessionId };
    if (sessionDate) return { sessionDate };
    return null;
  }, [gamingSessionId, sessionDate]);

  // KIS data — the primary/resolving fetch. Its response `scope` block
  // confirms the canonical gsid once resolved from a legacy session_date,
  // so every OTHER hook below (once gamingSessionId updates) targets the
  // same session precisely.
  const { data: kis, isLoading: kisLoading, isError: kisError } = useStoryKillImpact(scope);

  useEffect(() => {
    const resolved = kis?.scope;
    if (resolved?.gaming_session_id != null && resolved.gaming_session_id !== gamingSessionId) {
      setGamingSessionId(resolved.gaming_session_id);
      setSessionDate(resolved.dates.length > 0 ? resolved.dates[0] : null);
    }
  }, [kis, gamingSessionId]);

  // Moments data
  const { data: momentsData, isLoading: momentsLoading } = useStoryMoments(scope);
  // Momentum + Narrative (fetched in parallel with KIS/moments)
  const { data: momentumData, isLoading: momentumLoading } = useStoryMomentum(scope);
  const { data: narrativeData, isLoading: narrativeLoading } = useStoryNarrative(scope);
  const { data: playerNarData, isLoading: playerNarLoading } = usePlayerNarratives(scope);

  // New story panels
  const { data: gravityData, isLoading: gravityLoading } = useStoryGravity(scope);
  const { data: spaceData, isLoading: spaceLoading } = useStorySpaceCreated(scope);
  const { data: enablerData, isLoading: enablerLoading } = useStoryEnabler(scope);
  const { data: lurkerData, isLoading: lurkerLoading } = useStoryLurkerProfile(scope);
  const { data: synergyData, isLoading: synergyLoading } = useStorySynergy(scope);
  const { data: pwcData, isLoading: pwcLoading } = useStoryWinContribution(scope);
  const { data: boxData, isLoading: boxLoading } = useStoryBoxScore(scope);
  // /skill/composite isn't gsid-aware — needs the resolved single date.
  const { data: compositeData } = useStoryComposite(sessionDate);

  const entries = useMemo(() => kis?.entries ?? [], [kis]);
  const totalKills = kis?.total_kills ?? 0;
  const moments = useMemo(() => momentsData?.moments ?? [], [momentsData]);
  const momentumRounds = useMemo(() => momentumData?.rounds ?? [], [momentumData]);
  const narrative = narrativeData?.narrative ?? '';
  const playerNarratives = useMemo(() => playerNarData?.player_narratives ?? [], [playerNarData]);

  // Current session metadata (selector display + hero)
  const currentSession = scopes?.sessions.find((s) => s.gaming_session_id === gamingSessionId);
  const heroLabel = sessionDateLabel(currentSession) || sessionDate || '';
  const mapNames = currentSession?.distinct_map_names ?? [];

  // A legacy date deep-link that spans >1 gaming session 409s here. The
  // dropdown below always lists unambiguous individual sessions, so
  // pointing the user at it is a real fix, not a dead end — a full
  // candidate picker (matching story.js's) would need a body-preserving
  // fetch path get<T> doesn't have; tracked as a smaller follow-up rather
  // than blocking this conversion.
  const showAmbiguousNotice = kisError && gamingSessionId == null && !!sessionDate;

  return (
    <>
      <style>{STORY_STYLES}</style>

      <div className="space-y-6">
        {/* Hero header */}
        {gamingSessionId != null && !kisLoading ? (
          <StoryHero
            sessionDate={heroLabel}
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

        {showAmbiguousNotice && (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
            This date has more than one gaming session — pick the one you meant from the dropdown below.
          </div>
        )}

        {/* Session selector */}
        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-500 uppercase tracking-wider font-bold">Session</label>
          <select
            value={gamingSessionId ?? ''}
            onChange={(e) => {
              const next = e.target.value ? parseInt(e.target.value, 10) : null;
              setGamingSessionId(next);
              setSessionDate(null);
            }}
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white backdrop-blur-sm focus:border-cyan-400/50 focus:outline-none"
          >
            {scopesLoading && <option value="">Loading...</option>}
            {scopes?.sessions.map((s) => (
              <option key={s.gaming_session_id} value={s.gaming_session_id}>
                {sessionDateLabel(s)} — {s.accepted_round_count} round{s.accepted_round_count !== 1 ? 's' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Session Narrative */}
        {narrativeLoading ? (
          <div className="h-20 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : narrative ? (
          <NarrativePanel narrative={narrative} />
        ) : null}

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

        {/* Momentum Chart */}
        {momentumLoading ? (
          <div className="h-64 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : momentumRounds.length > 0 ? (
          <MomentumChart rounds={momentumRounds} />
        ) : null}

        {/* BOX Score */}
        {boxLoading ? (
          <div className="h-24 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : boxData?.maps?.length ? (
          <BoxScorePanel data={boxData} />
        ) : null}

        {/* Win Contribution */}
        {pwcLoading ? (
          <div className="h-40 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : pwcData?.players?.length ? (
          <WinContributionPanel data={pwcData} />
        ) : null}

        {/* Player Narratives — invisible value stories */}
        {playerNarLoading ? (
          <div className="h-40 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : playerNarratives.length > 0 ? (
          <PlayerNarrativesPanel narratives={playerNarratives} />
        ) : null}

        {/* Invisible Value — detailed gravity/space/enabler/lurker */}
        {(gravityLoading || spaceLoading || enablerLoading || lurkerLoading) ? (
          <div className="h-48 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : (
          <InvisibleValuePanel gravity={gravityData} space={spaceData} enabler={enablerData} lurker={lurkerData} />
        )}

        {/* Performance Fingerprint — TIR/CI/KPI/SDS/CP composite stats */}
        <CompositeStatsPanel composite={compositeData} />

        {/* Team Synergy */}
        {synergyLoading ? (
          <div className="h-40 rounded-2xl bg-slate-700/20 animate-pulse" />
        ) : synergyData?.groups ? (
          <TeamSynergyPanel data={synergyData} />
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

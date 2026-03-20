import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { navigateTo } from '../lib/navigation';

const API = '/api';

// -- Types ------------------------------------------------------------------

interface TimelineEvent {
  id?: number;
  type: string; // 'engagement' | 'trade_kill' | 'team_push' | 'spawn_timing_kill' | 'crossfire'
  time: number; // ms offset from round start
  attacker_name?: string;
  victim_name?: string;
  trader_name?: string;
  avenged_name?: string;
  damage?: number;
  weapon?: string;
  outcome?: string;
  delta_ms?: number;
  score?: number;
  quality?: number;
  alignment?: number;
  duration_ms?: number;
  participants?: number;
  team?: string;
  attacker_team?: string;
  victim_team?: string;
  distance?: number;
}

interface TimelineResponse {
  round_id: number;
  map_name: string;
  round_number: number;
  round_date: string | null;
  duration_ms: number;
  events: TimelineEvent[];
}

interface TrackPoint {
  x: number;
  y: number;
  t: number;
}

interface PlayerTrack {
  player_name: string;
  team: string;
  points: TrackPoint[];
}

interface TracksResponse {
  round_id: number;
  tracks: PlayerTrack[];
}

// -- Helpers ----------------------------------------------------------------

function fmtTime(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function fmtNum(v: number | null | undefined): string {
  return v != null ? v.toLocaleString() : '--';
}

const EVENT_COLORS: Record<string, string> = {
  engagement: '#ef4444',   // red
  trade_kill: '#3b82f6',   // blue
  team_push: '#22c55e',    // green
  spawn_timing_kill: '#eab308', // yellow
  crossfire: '#a855f7',    // purple
};

const EVENT_LABELS: Record<string, string> = {
  engagement: 'Kill',
  trade_kill: 'Trade Kill',
  team_push: 'Team Push',
  spawn_timing_kill: 'Spawn Kill',
  crossfire: 'Crossfire',
};

function eventColor(type: string): string {
  return EVENT_COLORS[type] ?? '#64748b';
}

function eventLabel(type: string): string {
  return EVENT_LABELS[type] ?? type;
}

// -- Timeline Bar -----------------------------------------------------------

function TimelineBar({
  events,
  durationMs,
  currentTime,
  onSeek,
}: {
  events: TimelineEvent[];
  durationMs: number;
  currentTime: number;
  onSeek: (t: number) => void;
}) {
  const barRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = barRef.current?.getBoundingClientRect();
      if (!rect || durationMs <= 0) return;
      const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      onSeek(pct * durationMs);
    },
    [durationMs, onSeek],
  );

  const cursorPct = durationMs > 0 ? (currentTime / durationMs) * 100 : 0;

  return (
    <GlassPanel>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-400">Round Timeline</div>
        <div className="text-xs text-slate-500 font-mono">{fmtTime(currentTime)} / {fmtTime(durationMs)}</div>
      </div>

      {/* Bar container */}
      <div
        ref={barRef}
        className="relative h-10 rounded-lg bg-slate-900/80 border border-white/10 cursor-crosshair select-none overflow-hidden"
        onClick={handleClick}
      >
        {/* Event markers */}
        {events.map((ev, i) => {
          const pct = durationMs > 0 ? (ev.time / durationMs) * 100 : 0;
          const color = eventColor(ev.type);

          if (ev.type === 'team_push' && ev.duration_ms) {
            const widthPct = (ev.duration_ms / durationMs) * 100;
            return (
              <div
                key={i}
                className="absolute top-1/2 -translate-y-1/2 h-4 rounded-sm opacity-60"
                style={{
                  left: `${pct}%`,
                  width: `${Math.max(widthPct, 0.5)}%`,
                  backgroundColor: color,
                }}
                title={`${eventLabel(ev.type)} @ ${fmtTime(ev.time)}`}
              />
            );
          }

          return (
            <div
              key={i}
              className="absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full"
              style={{
                left: `${pct}%`,
                backgroundColor: color,
                transform: 'translate(-50%, -50%)',
                boxShadow: `0 0 4px ${color}`,
              }}
              title={`${eventLabel(ev.type)} @ ${fmtTime(ev.time)}`}
            />
          );
        })}

        {/* Current time cursor */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white/80 pointer-events-none"
          style={{ left: `${cursorPct}%` }}
        />
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-4 mt-2 text-[10px]">
        {Object.entries(EVENT_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-slate-400">{eventLabel(type)}</span>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}

// -- Event Row --------------------------------------------------------------

function EventRow({ event, isActive }: { event: TimelineEvent; isActive: boolean }) {
  const color = eventColor(event.type);
  let description = '';

  switch (event.type) {
    case 'engagement':
      description = `${event.attacker_name ?? '?'} \u2192 ${event.victim_name ?? '?'}`;
      if (event.damage) description += ` (${event.damage} dmg`;
      if (event.weapon) description += `, ${event.weapon}`;
      if (event.damage) description += ')';
      else if (event.weapon) description += `)`;
      break;
    case 'trade_kill':
      description = `${event.trader_name ?? event.attacker_name ?? '?'} avenged ${event.avenged_name ?? event.victim_name ?? '?'}`;
      if (event.delta_ms != null) description += ` (+${event.delta_ms}ms)`;
      break;
    case 'team_push':
      description = `${event.team ?? 'TEAM'} push`;
      if (event.quality != null) description += ` (quality: ${event.quality.toFixed(1)}`;
      if (event.alignment != null) description += `, align: ${event.alignment.toFixed(1)}`;
      if (event.participants != null) description += `, ${event.participants} players`;
      if (event.quality != null) description += ')';
      break;
    case 'spawn_timing_kill':
      description = `${event.attacker_name ?? '?'} \u2192 ${event.victim_name ?? '?'}`;
      if (event.score != null) description += ` (score: ${event.score.toFixed(1)})`;
      break;
    case 'crossfire':
      description = `${event.attacker_name ?? '?'} \u2192 ${event.victim_name ?? '?'}`;
      if (event.distance != null) description += ` (${Math.round(event.distance)}u)`;
      break;
    default:
      description = `${event.attacker_name ?? ''} ${event.victim_name ? '\u2192 ' + event.victim_name : ''}`.trim() || event.type;
  }

  return (
    <div
      className={`flex items-center gap-3 text-xs rounded-lg border px-3 py-2 transition-all ${
        isActive
          ? 'border-white/20 bg-white/[0.06]'
          : 'border-white/5 bg-slate-950/30'
      }`}
    >
      <span className="font-mono text-slate-500 w-12 shrink-0 text-right">{fmtTime(event.time)}</span>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
      <span
        className="text-[10px] uppercase font-bold tracking-wider w-20 shrink-0"
        style={{ color }}
      >
        {eventLabel(event.type)}
      </span>
      <span className="text-slate-200 truncate">{description}</span>
    </div>
  );
}

// -- Stats Cards ------------------------------------------------------------

function StatsCards({ events }: { events: TimelineEvent[] }) {
  const stats = useMemo(() => {
    let kills = 0;
    let escapes = 0;
    let crossfires = 0;
    let tradeKills = 0;
    let pushes = 0;
    let spawnKills = 0;

    for (const ev of events) {
      switch (ev.type) {
        case 'engagement':
          if (ev.outcome === 'killed' || ev.outcome === 'kill') kills++;
          else if (ev.outcome === 'escaped' || ev.outcome === 'escape') escapes++;
          else kills++; // default: count as kill
          break;
        case 'trade_kill':
          tradeKills++;
          break;
        case 'crossfire':
          crossfires++;
          break;
        case 'team_push':
          pushes++;
          break;
        case 'spawn_timing_kill':
          spawnKills++;
          break;
      }
    }

    return { kills, escapes, crossfires, tradeKills, pushes, spawnKills };
  }, [events]);

  const cards = [
    { label: 'Total Kills', value: stats.kills, color: 'text-rose-400' },
    { label: 'Escapes', value: stats.escapes, color: 'text-emerald-400' },
    { label: 'Crossfires', value: stats.crossfires, color: 'text-purple-400' },
    { label: 'Trade Kills', value: stats.tradeKills, color: 'text-blue-400' },
    { label: 'Team Pushes', value: stats.pushes, color: 'text-green-400' },
    { label: 'Spawn Kills', value: stats.spawnKills, color: 'text-yellow-400' },
  ];

  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
      {cards.map((c) => (
        <GlassCard key={c.label} className="text-center">
          <div className="text-[10px] text-slate-500 uppercase">{c.label}</div>
          <div className={`text-lg font-bold ${c.color}`}>{fmtNum(c.value)}</div>
        </GlassCard>
      ))}
    </div>
  );
}

// -- Team Summary -----------------------------------------------------------

function TeamSummary({ events }: { events: TimelineEvent[] }) {
  const { axisKills, alliesKills } = useMemo(() => {
    let axis = 0;
    let allies = 0;
    for (const ev of events) {
      if (ev.type !== 'engagement' && ev.type !== 'spawn_timing_kill' && ev.type !== 'crossfire') continue;
      const team = (ev.attacker_team ?? '').toUpperCase();
      if (team === 'AXIS' || team === '1') axis++;
      else if (team === 'ALLIES' || team === '2') allies++;
    }
    return { axisKills: axis, alliesKills: allies };
  }, [events]);

  const total = axisKills + alliesKills || 1;

  return (
    <GlassPanel>
      <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Team Summary</div>
      <div className="flex items-center gap-4">
        <div className="text-center flex-1">
          <div className="text-[10px] text-slate-500 uppercase mb-1">Axis</div>
          <div className="text-2xl font-bold text-rose-400">{axisKills}</div>
        </div>
        <div className="flex-[2] h-4 rounded-full overflow-hidden bg-slate-800 flex">
          <div
            className="h-full bg-rose-500 transition-all"
            style={{ width: `${(axisKills / total) * 100}%` }}
          />
          <div
            className="h-full bg-blue-500 transition-all"
            style={{ width: `${(alliesKills / total) * 100}%` }}
          />
        </div>
        <div className="text-center flex-1">
          <div className="text-[10px] text-slate-500 uppercase mb-1">Allies</div>
          <div className="text-2xl font-bold text-blue-400">{alliesKills}</div>
        </div>
      </div>
    </GlassPanel>
  );
}

// -- Main Page --------------------------------------------------------------

export default function ProximityReplay({ params }: { params?: Record<string, string> }) {
  const roundId = params?.roundId ? parseInt(params.roundId, 10) : null;
  const [currentTime, setCurrentTime] = useState(0);
  const eventListRef = useRef<HTMLDivElement>(null);

  // Fetch timeline
  const {
    data: timeline,
    isLoading: timelineLoading,
    error: timelineError,
  } = useQuery<TimelineResponse>({
    queryKey: ['proximity-round-timeline', roundId],
    queryFn: () => fetch(`${API}/proximity/round/${roundId}/timeline`).then((r) => r.json()),
    enabled: roundId !== null && roundId > 0,
    staleTime: 300_000,
  });

  // Fetch tracks (for future map canvas -- currently used for stats only)
  const { data: _tracks } = useQuery<TracksResponse>({
    queryKey: ['proximity-round-tracks', roundId],
    queryFn: () => fetch(`${API}/proximity/round/${roundId}/tracks`).then((r) => r.json()),
    enabled: roundId !== null && roundId > 0,
    staleTime: 300_000,
  });

  const events = timeline?.events ?? [];
  const durationMs = timeline?.duration_ms ?? 0;

  // Sort events by time
  const sortedEvents = useMemo(
    () => [...events].sort((a, b) => a.time - b.time),
    [events],
  );

  // Find active event index (nearest event at or before currentTime)
  const activeIdx = useMemo(() => {
    if (!sortedEvents.length) return -1;
    let best = -1;
    for (let i = 0; i < sortedEvents.length; i++) {
      if (sortedEvents[i].time <= currentTime + 500) best = i; // 500ms tolerance
      else break;
    }
    return best;
  }, [sortedEvents, currentTime]);

  // Auto-scroll event list to active event
  useEffect(() => {
    if (activeIdx < 0 || !eventListRef.current) return;
    const el = eventListRef.current.children[activeIdx] as HTMLElement | undefined;
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [activeIdx]);

  // Handle seeking
  const handleSeek = useCallback((t: number) => {
    setCurrentTime(Math.max(0, t));
  }, []);

  // No roundId
  if (roundId === null || roundId <= 0) {
    return (
      <>
        <PageHeader title="Round Replay" subtitle="No round selected" />
        <GlassPanel>
          <div className="text-center py-12 text-slate-400">
            <p className="text-lg mb-2">No round ID specified.</p>
            <button
              onClick={() => navigateTo('#/proximity')}
              className="text-cyan-400 hover:text-cyan-300 underline text-sm"
            >
              Back to Proximity Analytics
            </button>
          </div>
        </GlassPanel>
      </>
    );
  }

  // Loading
  if (timelineLoading) {
    return (
      <>
        <PageHeader title="Round Replay" subtitle="Loading timeline..." />
        <Skeleton variant="card" count={4} />
      </>
    );
  }

  // Error
  if (timelineError || !timeline) {
    return (
      <>
        <PageHeader title="Round Replay" subtitle="Error loading round data" />
        <GlassPanel>
          <div className="text-center py-12 text-slate-400">
            <p className="text-lg mb-2">Failed to load timeline for round {roundId}.</p>
            <p className="text-sm text-slate-500 mb-4">
              {timelineError instanceof Error ? timelineError.message : 'The round may not have proximity data.'}
            </p>
            <button
              onClick={() => navigateTo('#/proximity')}
              className="text-cyan-400 hover:text-cyan-300 underline text-sm"
            >
              Back to Proximity Analytics
            </button>
          </div>
        </GlassPanel>
      </>
    );
  }

  return (
    <>
      {/* Header */}
      <PageHeader
        title={`${timeline.map_name ?? 'Unknown Map'} - Round ${timeline.round_number ?? '?'}`}
        subtitle={timeline.round_date ? `${timeline.round_date} \u00b7 ${sortedEvents.length} events \u00b7 ${fmtTime(durationMs)} duration` : `Round ${roundId}`}
      >
        <button
          onClick={() => navigateTo('#/proximity')}
          className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-300 hover:border-cyan-500/40 transition flex items-center gap-1.5"
        >
          <span>&larr;</span> Proximity
        </button>
      </PageHeader>

      {/* Timeline Bar */}
      <TimelineBar
        events={sortedEvents}
        durationMs={durationMs}
        currentTime={currentTime}
        onSeek={handleSeek}
      />

      {/* Stats Cards */}
      <div className="mt-4">
        <StatsCards events={sortedEvents} />
      </div>

      {/* Event List + Team Summary */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Event List (2/3 width) */}
        <div className="lg:col-span-2">
          <GlassPanel>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold uppercase tracking-widest text-slate-400">
                Events ({sortedEvents.length})
              </div>
              <div className="text-[10px] text-slate-500">
                Click timeline to jump to a time
              </div>
            </div>
            <div
              ref={eventListRef}
              className="space-y-1 max-h-[500px] overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-slate-700"
            >
              {sortedEvents.length === 0 ? (
                <div className="text-xs text-slate-500 text-center py-8">No events recorded for this round.</div>
              ) : (
                sortedEvents.map((ev, i) => (
                  <div
                    key={ev.id ?? i}
                    onClick={() => setCurrentTime(ev.time)}
                    className="cursor-pointer"
                  >
                    <EventRow event={ev} isActive={i === activeIdx} />
                  </div>
                ))
              )}
            </div>
          </GlassPanel>
        </div>

        {/* Right sidebar */}
        <div className="space-y-4">
          <TeamSummary events={sortedEvents} />

          {/* Duration info */}
          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase mb-1">Round Duration</div>
            <div className="text-lg font-bold text-white">{fmtTime(durationMs)}</div>
          </GlassCard>

          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase mb-1">Map</div>
            <div className="text-lg font-bold text-cyan-400">{timeline.map_name ?? '--'}</div>
          </GlassCard>

          <GlassCard>
            <div className="text-[10px] text-slate-500 uppercase mb-1">Round</div>
            <div className="text-lg font-bold text-white">#{timeline.round_number ?? '--'}</div>
          </GlassCard>

          {timeline.round_date && (
            <GlassCard>
              <div className="text-[10px] text-slate-500 uppercase mb-1">Date</div>
              <div className="text-sm font-bold text-slate-200">{timeline.round_date}</div>
            </GlassCard>
          )}
        </div>
      </div>
    </>
  );
}

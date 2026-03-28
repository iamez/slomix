import { cn } from '../../lib/cn';

interface StoryHeroProps {
  sessionDate: string;
  mapNames: string[];
  playerCount: number;
  totalKills: number;
  entryCount: number;
  className?: string;
}

export function StoryHero({
  sessionDate,
  mapNames,
  playerCount,
  totalKills,
  entryCount,
  className,
}: StoryHeroProps) {
  const mapsLabel = mapNames.length > 0
    ? mapNames.slice(0, 3).join(', ') + (mapNames.length > 3 ? ` +${mapNames.length - 3}` : '')
    : 'Unknown Map';

  return (
    <div className={cn(
      'glass-panel relative overflow-hidden rounded-[30px] p-8 md:p-10',
      className,
    )}>
      {/* Animated gradient background */}
      {/* gradientShift keyframe is injected by the parent Story page (STORY_STYLES) */}
      <div
        className="absolute inset-0 opacity-30"
        style={{
          background: 'linear-gradient(135deg, #0f172a 0%, #164e63 25%, #0f172a 50%, #881337 75%, #0f172a 100%)',
          backgroundSize: '400% 400%',
          animation: 'gradientShift 12s ease infinite',
        }}
      />
      {/* Radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(56,189,248,0.12),transparent_60%)]" />

      <div className="relative z-10">
        {/* Kicker */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="section-kicker">SLOMIX-STEIN</span>
          <span className="rounded-full border border-amber-400/25 bg-amber-400/12 px-3 py-1 text-[11px] font-bold text-amber-200">
            SMART STATS
          </span>
        </div>

        {/* Map + date */}
        <h1
          className="text-4xl font-black tracking-tight text-white md:text-5xl"
          style={{ animation: 'fadeUp 0.6s ease-out both' }}
        >
          {mapsLabel}
        </h1>
        <p
          className="mt-2 text-lg text-slate-400 font-medium"
          style={{ animation: 'fadeUp 0.6s ease-out 0.1s both' }}
        >
          {sessionDate}
        </p>

        {/* Stats row */}
        <div
          className="mt-6 flex flex-wrap items-center gap-4 text-sm"
          style={{ animation: 'fadeUp 0.6s ease-out 0.2s both' }}
        >
          <StatPill label="maps" value={mapNames.length} />
          <StatPill label="players" value={playerCount} />
          <StatPill label="total kills" value={totalKills} />
          <StatPill label="rated" value={entryCount} />
        </div>
      </div>
    </div>
  );
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/8 bg-white/5 px-3 py-1.5">
      <span className="text-white font-bold tabular-nums">{value}</span>
      <span className="text-slate-500 text-xs">{label}</span>
    </span>
  );
}

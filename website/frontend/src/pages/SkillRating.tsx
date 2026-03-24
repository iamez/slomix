import { useState } from 'react';
import { Trophy, Target, Heart, Shield, Crosshair, Skull, Zap, Clock, Info, ChevronDown, ChevronRight } from 'lucide-react';
import { useSkillLeaderboard, useSkillFormula } from '../api/hooks';
import type { RatedPlayer } from '../api/types';
import { PageHeader } from '../components/PageHeader';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';
import { cn } from '../lib/cn';
import { navigateToPlayer } from '../lib/navigation';

/* ── Constants ── */

const METRIC_LABELS: Record<string, string> = {
  dpm: 'DPM',
  kpr: 'Kills/Round',
  dpr: 'Deaths/Round',
  revive_rate: 'Revives',
  objective_rate: 'Objectives',
  survival_rate: 'Survival',
  useful_kill_rate: 'Useful Kills',
  denied_playtime_pm: 'Denied Time',
  accuracy: 'Accuracy',
};

const METRIC_ICONS: Record<string, typeof Trophy> = {
  dpm: Zap,
  kpr: Crosshair,
  dpr: Skull,
  revive_rate: Heart,
  objective_rate: Target,
  survival_rate: Shield,
  useful_kill_rate: Trophy,
  denied_playtime_pm: Clock,
  accuracy: Crosshair,
};

/* ── Tier helpers ── */

interface TierDef {
  name: string;
  color: string;
  ringColor: string;
  ringStroke: string;
  bg: string;
  glow: string;
}

function getTier(rating: number): TierDef {
  if (rating >= 0.85) return { name: 'Elite', color: 'text-amber-400', ringColor: '#fbbf24', ringStroke: 'stroke-amber-400', bg: 'bg-amber-500/8', glow: 'shadow-amber-500/20' };
  if (rating >= 0.70) return { name: 'Veteran', color: 'text-emerald-400', ringColor: '#34d399', ringStroke: 'stroke-emerald-400', bg: 'bg-emerald-500/8', glow: 'shadow-emerald-500/20' };
  if (rating >= 0.55) return { name: 'Experienced', color: 'text-cyan-400', ringColor: '#22d3ee', ringStroke: 'stroke-cyan-400', bg: 'bg-cyan-500/8', glow: 'shadow-cyan-500/15' };
  if (rating >= 0.40) return { name: 'Regular', color: 'text-slate-300', ringColor: '#94a3b8', ringStroke: 'stroke-slate-400', bg: 'bg-slate-500/8', glow: 'shadow-slate-500/10' };
  return { name: 'Newcomer', color: 'text-slate-500', ringColor: '#475569', ringStroke: 'stroke-slate-600', bg: 'bg-slate-700/8', glow: '' };
}

function tierBadgeClass(rating: number): string {
  if (rating >= 0.85) return 'bg-amber-500/15 text-amber-400 border-amber-500/30';
  if (rating >= 0.70) return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30';
  if (rating >= 0.55) return 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30';
  if (rating >= 0.40) return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  return 'bg-slate-700/30 text-slate-500 border-slate-600/30';
}

/* ── SVG Rating Ring ── */

function RatingRing({ rating, size = 120 }: { rating: number; size?: number }) {
  const tier = getTier(rating);
  const strokeWidth = size > 100 ? 6 : 4;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  // Rating range is 0 to ~1.15, normalize to 0-1 for visual
  const normalized = Math.min(rating / 1.15, 1);
  const dashOffset = circumference * (1 - normalized);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" strokeWidth={strokeWidth}
          className="stroke-white/5"
        />
        {/* Colored progress ring */}
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" strokeWidth={strokeWidth}
          stroke={tier.ringColor}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="transition-all duration-700"
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('font-black tabular-nums', tier.color, size > 100 ? 'text-3xl' : 'text-lg')}>
          {rating.toFixed(3)}
        </span>
      </div>
    </div>
  );
}

/* ── Mini dot indicator for table ── */

function RatingDot({ rating }: { rating: number }) {
  const tier = getTier(rating);
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full mr-2 shrink-0"
      style={{ backgroundColor: tier.ringColor, boxShadow: `0 0 6px ${tier.ringColor}40` }}
    />
  );
}

/* ── Hero Card for #1 player ── */

function HeroCard({ player }: { player: RatedPlayer }) {
  const tier = getTier(player.et_rating);
  return (
    <GlassCard className={cn('relative overflow-hidden', tier.glow && `shadow-lg ${tier.glow}`)}>
      <div className="flex items-center gap-8 p-2">
        {/* Rating ring */}
        <RatingRing rating={player.et_rating} size={140} />

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-[11px] uppercase tracking-[0.28em] text-slate-500 font-bold">Top Rated Player</span>
            <span className={cn(
              'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border',
              tierBadgeClass(player.et_rating),
            )}>
              {tier.name}
            </span>
          </div>
          <button
            className="text-2xl font-black text-white hover:text-blue-400 transition truncate block"
            onClick={() => { navigateToPlayer(player.display_name); }}
          >
            {player.display_name}
          </button>
          <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
            <span className="font-mono">{player.games_rated} rounds rated</span>
          </div>

          {/* Mini stat highlights - top 3 components */}
          <div className="flex gap-3 mt-4">
            {Object.entries(player.components)
              .filter(([k]) => k !== 'dpr')
              .sort(([, a], [, b]) => b.percentile - a.percentile)
              .slice(0, 3)
              .map(([key, comp]) => {
                // eslint-disable-next-line security/detect-object-injection
                const Icon = METRIC_ICONS[key] ?? Target;
                return (
                  <div key={key} className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-white/[0.04] border border-white/5">
                    <Icon className="w-3 h-3 text-slate-500" />
                    {/* eslint-disable-next-line security/detect-object-injection */}
                    <span className="text-[11px] text-slate-400">{METRIC_LABELS[key]}</span>
                    <span className="text-[11px] font-bold text-white">{Math.round(comp.percentile * 100)}%</span>
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

/* ── Percentile Bar ── */

function PercentileBar({ metricKey, value, label }: { metricKey: string; value: number; label: string }) {
  const pct = Math.round(value * 100);
  const isNegative = metricKey === 'dpr';
  const tier = isNegative
    ? (pct > 70 ? getTier(0.3) : pct > 40 ? getTier(0.5) : getTier(0.8))
    : getTier(pct > 70 ? 0.9 : pct > 40 ? 0.6 : 0.3);
  // eslint-disable-next-line security/detect-object-injection
  const Icon = METRIC_ICONS[metricKey] ?? Target;

  return (
    <div className="flex items-center gap-2.5 text-xs">
      <Icon className="w-3.5 h-3.5 text-slate-500 shrink-0" />
      <span className="w-24 text-slate-400 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: tier.ringColor }}
        />
      </div>
      <span className="w-10 text-right font-mono font-bold" style={{ color: tier.ringColor }}>{pct}%</span>
    </div>
  );
}

/* ── Expandable Row Detail ── */

function ExpandedRow({ player }: { player: RatedPlayer }) {
  return (
    <div className="px-4 py-4 bg-white/[0.02] border-t border-white/5">
      <div className="flex items-start gap-6">
        {/* Rating ring */}
        <div className="shrink-0">
          <RatingRing rating={player.et_rating} size={90} />
        </div>

        {/* Percentile breakdown */}
        <div className="flex-1 space-y-2">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">Percentile Breakdown</div>
          {Object.entries(player.components).map(([key, comp]) => (
            <PercentileBar
              key={key}
              metricKey={key}
              label={METRIC_LABELS[key] || key}
              value={comp.percentile}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Player Row ── */

function PlayerRow({ player, isExpanded, onToggle }: { player: RatedPlayer; isExpanded: boolean; onToggle: () => void }) {
  const tier = getTier(player.et_rating);
  const isTop3 = player.rank <= 3;
  const medals = ['', '🥇', '🥈', '🥉'];

  return (
    <>
      <button
        className={cn(
          'w-full flex items-center gap-3 px-4 py-3 transition-colors text-left',
          'border-b border-white/5',
          isExpanded ? 'bg-white/[0.04]' : 'hover:bg-white/[0.02]',
          isTop3 && !isExpanded && tier.bg,
        )}
        onClick={onToggle}
      >
        {/* Rank */}
        <span className={cn('w-10 text-center font-mono font-bold text-sm shrink-0', isTop3 ? tier.color : 'text-slate-500')}>
          {isTop3 ? medals[player.rank] : `#${player.rank}`}
        </span>

        {/* Player name */}
        <span className="flex-1 font-semibold text-white text-sm truncate">
          {player.display_name}
        </span>

        {/* Rating with dot */}
        <span className="flex items-center shrink-0">
          <RatingDot rating={player.et_rating} />
          <span className={cn('font-black tabular-nums text-base', tier.color)}>
            {player.et_rating.toFixed(3)}
          </span>
        </span>

        {/* Tier badge */}
        <span className={cn(
          'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border shrink-0',
          tierBadgeClass(player.et_rating),
        )}>
          {tier.name}
        </span>

        {/* Rounds */}
        <span className="w-16 text-right text-xs text-slate-500 font-mono shrink-0">
          {player.games_rated}
        </span>

        {/* Expand chevron */}
        <ChevronRight className={cn(
          'w-4 h-4 text-slate-600 shrink-0 transition-transform',
          isExpanded && 'rotate-90',
        )} />
      </button>
      {isExpanded && <ExpandedRow player={player} />}
    </>
  );
}

/* ── Main Component ── */

export default function SkillRating() {
  const { data, isLoading, isError } = useSkillLeaderboard(50);
  const { data: formula } = useSkillFormula();
  const [expandedGuid, setExpandedGuid] = useState<string | null>(null);
  const [showFormula, setShowFormula] = useState(false);

  const players = data?.players ?? [];
  const topPlayer = players[0] ?? null;

  if (isLoading) {
    return (
      <div className="page-shell">
        <PageHeader title="ET Rating" subtitle="Individual performance rating" eyebrow="Experimental" />
        <Skeleton variant="card" count={1} />
        <Skeleton variant="table" count={10} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-shell">
        <PageHeader title="ET Rating" subtitle="Individual performance rating" eyebrow="Experimental" />
        <div className="text-center text-red-400 py-12">Failed to load skill ratings.</div>
      </div>
    );
  }

  return (
    <div className="page-shell">
      <PageHeader
        title="ET Rating"
        subtitle="Individual performance rating based on percentile-normalized stats across 9 metrics"
        eyebrow="Experimental"
      >
        <button
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition"
          onClick={() => setShowFormula(!showFormula)}
        >
          <Info className="w-3.5 h-3.5" />
          Formula
          <ChevronDown className={cn('w-3 h-3 transition-transform', showFormula && 'rotate-180')} />
        </button>
      </PageHeader>

      {/* Formula details */}
      {showFormula && formula && (
        <GlassCard className="p-4 space-y-3">
          <div className="text-xs font-mono text-slate-400 break-all">
            ET_Rating = {formula.constant} + {Object.entries(formula.weights).map(([k, w]) => (
              <span key={k}>{w > 0 ? '+' : ''}{w}&times;pct({k}) </span>
            ))}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
            {Object.entries(formula.metrics).map(([key, desc]) => (
              <div key={key} className="text-slate-500">
                <span className="text-cyan-400 font-mono">{key}</span>: {desc}
              </div>
            ))}
          </div>
          <div className="text-xs text-slate-500">
            Min {formula.min_rounds} rounds &middot; Percentile normalization &middot; v{formula.version}
          </div>
        </GlassCard>
      )}

      {/* Hero - #1 Player */}
      <HeroCard player={topPlayer} />

      {/* Rankings list */}
      <div className="table-shell rounded-[24px] overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
          <span className="w-10 text-center">Rank</span>
          <span className="flex-1">Player</span>
          <span className="w-32 text-center">Rating</span>
          <span className="w-24 text-center">Tier</span>
          <span className="w-16 text-right">Rounds</span>
          <span className="w-4" />
        </div>

        {/* Rows */}
        {players.map((p) => (
          <PlayerRow
            key={p.player_guid}
            player={p}
            isExpanded={expandedGuid === p.player_guid}
            onToggle={() => { setExpandedGuid(expandedGuid === p.player_guid ? null : p.player_guid); }}
          />
        ))}
      </div>
    </div>
  );
}

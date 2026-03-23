import { useState, useEffect } from 'react';
import { Trophy, Target, Heart, Shield, Crosshair, Skull, Zap, Clock, Info } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { GlassCard } from '../components/GlassCard';
import { Skeleton } from '../components/Skeleton';

interface SkillComponent {
  raw: number;
  percentile: number;
  weight: number;
  contribution: number;
}

interface RatedPlayer {
  rank: number;
  player_guid: string;
  display_name: string;
  et_rating: number;
  games_rated: number;
  components: Record<string, SkillComponent>;
}

interface FormulaInfo {
  weights: Record<string, number>;
  metrics: Record<string, string>;
  constant: number;
  min_rounds: number;
  version: string;
}

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

const METRIC_LABELS: Record<string, string> = {
  dpm: 'DPM',
  kpr: 'Kills/Round',
  dpr: 'Deaths/Round',
  revive_rate: 'Revives/Round',
  objective_rate: 'Objectives/Round',
  survival_rate: 'Survival Rate',
  useful_kill_rate: 'Useful Kill %',
  denied_playtime_pm: 'Denied Time/Min',
  accuracy: 'Accuracy',
};

function ratingColor(rating: number): string {
  if (rating >= 0.85) return 'text-yellow-400';
  if (rating >= 0.70) return 'text-emerald-400';
  if (rating >= 0.55) return 'text-cyan-400';
  if (rating >= 0.40) return 'text-slate-300';
  return 'text-slate-500';
}

function ratingTier(rating: number): string {
  if (rating >= 0.85) return 'Elite';
  if (rating >= 0.70) return 'Veteran';
  if (rating >= 0.55) return 'Experienced';
  if (rating >= 0.40) return 'Regular';
  return 'Newcomer';
}

function PercentileBar({ value, label, isNegative }: { value: number; label: string; isNegative?: boolean }) {
  const pct = Math.round(value * 100);
  const barColor = isNegative
    ? (pct > 70 ? 'bg-rose-500' : pct > 40 ? 'bg-amber-500' : 'bg-emerald-500')
    : (pct > 70 ? 'bg-emerald-500' : pct > 40 ? 'bg-cyan-500' : 'bg-slate-500');

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-28 text-slate-400 truncate">{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-slate-300 font-mono">{pct}%</span>
    </div>
  );
}

export default function SkillRating() {
  const [players, setPlayers] = useState<RatedPlayer[]>([]);
  const [formula, setFormula] = useState<FormulaInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlayer, setSelectedPlayer] = useState<RatedPlayer | null>(null);
  const [showFormula, setShowFormula] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch('/api/skill/leaderboard?limit=50').then(r => r.json()),
      fetch('/api/skill/formula').then(r => r.json()),
    ])
      .then(([lb, fm]) => {
        setPlayers(lb.players || []);
        setFormula(fm);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-96 w-full" />
    </div>
  );

  if (error) return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="text-rose-400 text-center py-12">Error: {error}</div>
    </div>
  );

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <PageHeader
        eyebrow="Experimental"
        title="ET Rating"
        subtitle="Individual performance rating inspired by HLTV, Valorant ACS, and PandaSkill research"
      />

      {/* Formula toggle */}
      <button
        className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition"
        onClick={() => setShowFormula(!showFormula)}
        aria-label="Toggle formula details"
      >
        <Info className="w-4 h-4" />
        {showFormula ? 'Hide' : 'Show'} Formula Details
      </button>

      {showFormula && formula && (
        <GlassCard className="p-4 space-y-3">
          <div className="text-xs font-mono text-slate-400">
            ET_Rating = {formula.constant} + {Object.entries(formula.weights).map(([k, w]) => (
              <span key={k}>{w > 0 ? '+' : ''}{w}*pct({k}) </span>
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
            Min {formula.min_rounds} rounds to be rated | Normalization: percentile rank (0-100%) | v{formula.version}
          </div>
        </GlassCard>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Leaderboard */}
        <div className="lg:col-span-2 space-y-1">
          {players.map((p) => (
            <button
              key={p.player_guid}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition
                ${selectedPlayer?.player_guid === p.player_guid
                  ? 'bg-cyan-500/10 border border-cyan-500/30'
                  : 'hover:bg-white/[0.03]'
                }`}
              onClick={() => setSelectedPlayer(p)}
              aria-label={`View ${p.display_name} rating details`}
            >
              <span className="w-8 text-right font-black text-slate-500 text-sm">#{p.rank}</span>
              <div className="flex-1 text-left">
                <div className="text-white font-bold text-sm">{p.display_name}</div>
                <div className="text-xs text-slate-500">{p.games_rated} rounds</div>
              </div>
              <div className="text-right">
                <div className={`text-lg font-black tabular-nums ${ratingColor(p.et_rating)}`}>
                  {p.et_rating.toFixed(3)}
                </div>
                <div className="text-[10px] text-slate-500 uppercase tracking-wider">
                  {ratingTier(p.et_rating)}
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Detail panel */}
        <div className="space-y-4">
          {selectedPlayer ? (
            <>
              <GlassCard className="p-5 space-y-4">
                <div className="text-center">
                  <div className="text-xs text-slate-500 uppercase tracking-wider">ET Rating</div>
                  <div className={`text-4xl font-black tabular-nums ${ratingColor(selectedPlayer.et_rating)}`}>
                    {selectedPlayer.et_rating.toFixed(3)}
                  </div>
                  <div className="text-sm text-slate-400">{selectedPlayer.display_name}</div>
                  <div className="text-xs text-slate-500">Rank #{selectedPlayer.rank} | {selectedPlayer.games_rated} rounds</div>
                </div>
              </GlassCard>

              <GlassCard className="p-4 space-y-2.5">
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Component Breakdown</div>
                {Object.entries(selectedPlayer.components).map(([key, comp]) => (
                  <PercentileBar
                    key={key}
                    label={METRIC_LABELS[key] || key}
                    value={comp.percentile}
                    isNegative={key === 'dpr'}
                  />
                ))}
              </GlassCard>
            </>
          ) : (
            <GlassCard className="p-8 text-center text-slate-500 text-sm">
              Click a player to see their rating breakdown
            </GlassCard>
          )}
        </div>
      </div>
    </div>
  );
}

import type { PlayerNarrative } from '../../api/types';
import type { PlayerArchetype } from './ArchetypeBadge';
import { ArchetypeBadge } from './ArchetypeBadge';

const TRAIT_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  gravity: { bg: 'bg-rose-500/15', text: 'text-rose-400', label: 'HEAT' },
  space: { bg: 'bg-purple-500/15', text: 'text-purple-400', label: 'SPACE' },
  enabler: { bg: 'bg-teal-500/15', text: 'text-teal-400', label: 'ENABLER' },
  solo: { bg: 'bg-cyan-500/15', text: 'text-cyan-400', label: 'LURKER' },
};

interface MetricBadgeProps {
  label: string;
  value: string;
  color: string;
}

function MetricBadge({ label, value, color }: MetricBadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-mono ${color} bg-white/5`}>
      <span className="opacity-60">{label}</span>
      <span className="font-bold">{value}</span>
    </span>
  );
}

interface Props {
  narratives: PlayerNarrative[];
}

export function PlayerNarrativesPanel({ narratives }: Props) {
  if (!narratives.length) return null;

  return (
    <div>
      <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold mb-3">
        Player Stories
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {narratives.map((p, i) => {
          const trait = TRAIT_COLORS[p.top_trait] ?? TRAIT_COLORS.gravity;
          const m = p.metrics;
          const archetype = (p.archetype?.replace(/ /g, '_') ?? 'frontline_warrior') as PlayerArchetype;

          return (
            <div
              key={p.guid_short}
              className="rounded-xl border border-white/8 bg-white/[0.02] p-4 hover:bg-white/[0.04] transition-colors"
              style={{ animation: `fadeUp 0.4s ease-out ${i * 0.05}s both` }}
            >
              {/* Header: name + badges */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-bold text-white truncate">{p.name}</span>
                  <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${trait.bg} ${trait.text}`}>
                    {trait.label}
                  </span>
                </div>
                <ArchetypeBadge archetype={archetype} size="sm" />
              </div>

              {/* Narrative text */}
              <p className="text-xs text-slate-400 leading-relaxed mb-3">
                {p.narrative}
              </p>

              {/* Metric mini-badges */}
              <div className="flex flex-wrap gap-1.5">
                {m.gravity > 0 && (
                  <MetricBadge label="GRV" value={m.gravity.toFixed(0)} color="text-rose-400" />
                )}
                {m.space_score > 0 && (
                  <MetricBadge label="SPC" value={m.space_score.toFixed(2)} color="text-purple-400" />
                )}
                {m.enabler_score > 0 && (
                  <MetricBadge label="ENB" value={m.enabler_score.toFixed(1)} color="text-teal-400" />
                )}
                {m.solo_pct > 0 && (
                  <MetricBadge label="SOLO" value={`${m.solo_pct.toFixed(0)}%`} color="text-cyan-400" />
                )}
                <MetricBadge label="KIS" value={m.total_kis.toFixed(0)} color="text-amber-400" />
                <MetricBadge label="K" value={String(m.kills)} color="text-slate-400" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

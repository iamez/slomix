import type { WinContributionResponse } from '../../api/types';

const COMP_COLORS: Record<string, string> = {
  kills: 'bg-rose-400',
  damage: 'bg-orange-400',
  objectives: 'bg-blue-400',
  revives: 'bg-emerald-400',
  survival: 'bg-lime-400',
  crossfire: 'bg-cyan-400',
  trade: 'bg-amber-400',
  clutch: 'bg-violet-400',
};

const COMP_LABELS: Record<string, string> = {
  kills: 'K',
  damage: 'DMG',
  objectives: 'OBJ',
  revives: 'REV',
  survival: 'SRV',
  crossfire: 'CF',
  trade: 'TRD',
  clutch: 'CLT',
};

interface Props {
  data: WinContributionResponse;
}

export function WinContributionPanel({ data }: Props) {
  if (!data.players?.length) return null;

  const mvp = data.mvp;

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold">Win Contribution</h3>
        {mvp && (
          <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2.5 py-0.5 text-[10px] font-bold text-amber-300">
            MVP: {mvp.name}
          </span>
        )}
      </div>

      <div className="glass-card rounded-[24px] p-5 border border-white/8 space-y-2">
        {data.players.map((p, i) => {
          const total = Object.values(p.components).reduce((s, v) => s + v, 0) || 1;
          const isMvp = mvp && p.guid === mvp.guid;

          return (
            <div
              key={p.guid}
              className={`rounded-xl px-3 py-2.5 transition-colors ${isMvp ? 'bg-amber-400/[0.06] border border-amber-400/20' : 'bg-white/[0.02] hover:bg-white/[0.04]'}`}
              style={{ animation: `fadeUp 0.3s ease-out ${i * 0.04}s both` }}
            >
              <div className="flex items-center gap-3 mb-2">
                <span className="text-amber-400 font-bold text-lg tabular-nums w-14">
                  {(p.total_pwc * 100).toFixed(0)}%
                </span>
                <span className="text-sm text-white font-medium flex-1 truncate">
                  {p.name}
                  {isMvp && <span className="ml-1.5 text-[10px] text-amber-400">MVP</span>}
                </span>
                <span className={`text-xs font-bold tabular-nums ${p.wis >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  WIS {p.wis >= 0 ? '+' : ''}{p.wis.toFixed(2)}
                </span>
                <span className="text-xs text-slate-500 tabular-nums">
                  W:{p.rounds_won} L:{p.rounds_lost}
                </span>
              </div>

              {/* Component breakdown bar */}
              <div className="flex h-2 rounded-full overflow-hidden bg-white/5">
                {Object.entries(p.components).map(([key, val]) => {
                  const pct = (val / total) * 100;
                  if (pct < 1) return null;
                  return (
                    <div
                      key={key}
                      className={`${COMP_COLORS[key] ?? 'bg-slate-500'} opacity-75 hover:opacity-100 transition-opacity`}
                      style={{ width: `${pct}%` }}
                      title={`${COMP_LABELS[key] ?? key}: ${(pct).toFixed(0)}%`}
                    />
                  );
                })}
              </div>

              {/* Legend mini-badges */}
              <div className="flex flex-wrap gap-1 mt-1.5">
                {Object.entries(p.components).map(([key, val]) => {
                  const pct = (val / total) * 100;
                  if (pct < 3) return null;
                  return (
                    <span key={key} className="text-[9px] text-slate-500 tabular-nums">
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${COMP_COLORS[key] ?? 'bg-slate-500'} mr-0.5 align-middle`} />
                      {COMP_LABELS[key] ?? key}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

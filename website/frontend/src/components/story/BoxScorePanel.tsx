import type { BoxScoreResponse } from '../../api/types';

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

interface Props {
  data: BoxScoreResponse;
}

export function BoxScorePanel({ data }: Props) {
  if (!data.maps?.length) return null;

  const winnerColor = data.winner === 'alpha' ? 'text-cyan-400' : data.winner === 'beta' ? 'text-rose-400' : 'text-slate-300';

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold">Box Score</h3>
        {data.winner_name && data.winner !== 'draw' && (
          <span className={`rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[10px] font-bold ${winnerColor}`}>
            {data.winner_name} WINS
          </span>
        )}
        {data.winner === 'draw' && (
          <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[10px] font-bold text-amber-400">
            DRAW
          </span>
        )}
      </div>

      <div className="glass-card rounded-[20px] p-5 border border-white/8">
        {/* Score header */}
        <div className="flex items-center justify-center gap-6 mb-4">
          <div className="text-center">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{data.alpha_team}</div>
            <div className="text-3xl font-bold tabular-nums text-cyan-400">{data.alpha_score}</div>
          </div>
          <div className="text-slate-600 text-lg font-bold">vs</div>
          <div className="text-center">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{data.beta_team}</div>
            <div className="text-3xl font-bold tabular-nums text-rose-400">{data.beta_score}</div>
          </div>
        </div>

        {/* Map breakdown */}
        <div className="space-y-1.5">
          {data.maps.map((m) => (
            <div
              key={m.map_number}
              className="flex items-center gap-3 rounded-lg bg-white/[0.02] px-3 py-2 text-xs"
            >
              <span className="text-slate-500 tabular-nums w-4">#{m.map_number}</span>
              <span className="text-white font-medium flex-1 truncate">{m.map_name}</span>
              <span className="text-cyan-400 font-bold tabular-nums w-4 text-center">{m.alpha_points}</span>
              <span className="text-slate-600">-</span>
              <span className="text-rose-400 font-bold tabular-nums w-4 text-center">{m.beta_points}</span>
              {m.r1_time > 0 && (
                <span className="text-slate-500 tabular-nums text-[10px]">
                  R1:{formatTime(m.r1_time)}
                  {m.r2_time > 0 && ` R2:${formatTime(m.r2_time)}`}
                </span>
              )}
              {m.is_fullhold_draw && (
                <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-bold text-amber-400">FH</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

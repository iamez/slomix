import { useState, useRef, useEffect } from 'react';
import type { MomentumRound } from '../../api/types';

interface Props {
  rounds: MomentumRound[];
}

const AXIS_COLOR = '#ef4444';   // red-500
const ALLIES_COLOR = '#3b82f6'; // blue-500
const GRID_COLOR = 'rgba(148, 163, 184, 0.12)';
const MID_LINE_COLOR = 'rgba(148, 163, 184, 0.25)';

export function MomentumChart({ rounds }: Props) {
  const [activeRound, setActiveRound] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const round = rounds[activeRound];
  const points = round?.points ?? [];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || points.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const PAD_L = 36;
    const PAD_R = 12;
    const PAD_T = 16;
    const PAD_B = 28;
    const plotW = W - PAD_L - PAD_R;
    const plotH = H - PAD_T - PAD_B;

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = GRID_COLOR;
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = PAD_T + (plotH * i) / 4;
      ctx.beginPath();
      ctx.moveTo(PAD_L, y);
      ctx.lineTo(W - PAD_R, y);
      ctx.stroke();
    }

    // Midline (50)
    ctx.strokeStyle = MID_LINE_COLOR;
    ctx.setLineDash([4, 4]);
    const midY = PAD_T + plotH / 2;
    ctx.beginPath();
    ctx.moveTo(PAD_L, midY);
    ctx.lineTo(W - PAD_R, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Y-axis labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px system-ui';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (let i = 0; i <= 4; i++) {
      const val = 100 - i * 25;
      const y = PAD_T + (plotH * i) / 4;
      ctx.fillText(String(val), PAD_L - 6, y);
    }

    // X-axis labels (time)
    const maxT = points[points.length - 1]?.t_ms ?? 0;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const stepCount = Math.min(6, points.length);
    for (let i = 0; i <= stepCount; i++) {
      const t = (maxT * i) / stepCount;
      const x = PAD_L + (plotW * i) / stepCount;
      const min = Math.floor(t / 60000);
      const sec = Math.floor((t % 60000) / 1000);
      ctx.fillText(`${min}:${sec.toString().padStart(2, '0')}`, x, H - PAD_B + 6);
    }

    // Draw lines
    function drawLine(c: CanvasRenderingContext2D, key: 'axis' | 'allies', color: string) {
      if (points.length < 2) return;
      c.strokeStyle = color;
      c.lineWidth = 2.5;
      c.lineJoin = 'round';
      c.beginPath();
      for (let i = 0; i < points.length; i++) {
        const x = PAD_L + (points[i].t_ms / Math.max(maxT, 1)) * plotW;
        const y = PAD_T + (1 - points[i][key] / 100) * plotH;
        if (i === 0) c.moveTo(x, y);
        else c.lineTo(x, y);
      }
      c.stroke();

      // Glow
      c.save();
      c.globalAlpha = 0.15;
      c.strokeStyle = color;
      c.lineWidth = 8;
      c.beginPath();
      for (let i = 0; i < points.length; i++) {
        const x = PAD_L + (points[i].t_ms / Math.max(maxT, 1)) * plotW;
        const y = PAD_T + (1 - points[i][key] / 100) * plotH;
        if (i === 0) c.moveTo(x, y);
        else c.lineTo(x, y);
      }
      c.stroke();
      c.restore();
    }

    drawLine(ctx, 'axis', AXIS_COLOR);
    drawLine(ctx, 'allies', ALLIES_COLOR);

  }, [points]);

  if (rounds.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <h3 className="text-xs text-slate-500 uppercase tracking-wider font-bold">Momentum</h3>
        <div className="flex items-center gap-2 ml-auto text-[10px]">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 rounded" style={{ background: AXIS_COLOR }} />
            <span className="text-red-400">AXIS</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 rounded" style={{ background: ALLIES_COLOR }} />
            <span className="text-blue-400">ALLIES</span>
          </span>
        </div>
      </div>

      {/* Round tabs */}
      {rounds.length > 1 && (
        <div className="flex gap-1 mb-3 overflow-x-auto scrollbar-thin scrollbar-thumb-slate-700">
          {rounds.map((r, i) => (
            <button
              key={`${r.round_number}-${i}`}
              onClick={() => setActiveRound(i)}
              className={`flex-shrink-0 px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                i === activeRound
                  ? 'bg-white/10 text-white border border-white/20'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'
              }`}
            >
              R{r.round_number} {r.map_name}
            </button>
          ))}
        </div>
      )}

      {/* Canvas chart */}
      <div className="glass-card rounded-2xl p-4 border border-white/8">
        <canvas
          ref={canvasRef}
          className="w-full"
          style={{ height: 220 }}
        />
      </div>
    </div>
  );
}

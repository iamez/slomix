import { useRef, useEffect } from 'react';
// chart.js/auto registers every controller/scale/plugin — the exact behaviour
// of the UMD bundle the legacy shell loads from jsdelivr, so swapping the
// source cannot change what renders. Pinned to the same version (4.4.7) as
// website/index.html:1256 until switchover retires the CDN tag entirely
// (docs/design/06 §2: bundling removes the last non-SRI supply chain and the
// dependence on the legacy shell having loaded window.Chart first).
import ChartJS from 'chart.js/auto';
import type { ChartConfiguration, ChartType } from 'chart.js';

type ChartData = Record<string, unknown>;
type ChartOptions = Record<string, unknown>;

interface ChartProps {
  type: string;
  data: ChartData;
  options?: ChartOptions;
  height?: number | string;
  className?: string;
}

export function ChartCanvas({ type, data, options, height, className }: ChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<ChartJS | null>(null);

  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;

    chartRef.current = new ChartJS(ctx, {
      type: type as ChartType,
      // Callers pass loose records (the component's public contract since the
      // CDN days); the runtime shape is what Chart.js validates.
      data: data as unknown as ChartConfiguration['data'],
      options: { responsive: true, maintainAspectRatio: false, ...options },
    });

    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [type, data, options]);

  return (
    <div className={className} style={height ? { height } : undefined} role="img" aria-label={`${type} chart`}>
      <canvas ref={canvasRef} />
    </div>
  );
}

import { useRef, useEffect } from 'react';

/** Minimal Chart.js types for global CDN usage. */
interface ChartInstance { destroy(): void }
interface ChartConstructor {
  new (ctx: CanvasRenderingContext2D | null, config: { type: string; data: ChartData; options?: ChartOptions }): ChartInstance;
}
type ChartData = Record<string, unknown>;
type ChartOptions = Record<string, unknown>;

function getChart(): ChartConstructor | null {
  const w = window as unknown as Record<string, unknown>;
  return typeof window !== 'undefined' && w.Chart ? w.Chart as ChartConstructor : null;
}

interface ChartProps {
  type: string;
  data: ChartData;
  options?: ChartOptions;
  height?: number | string;
  className?: string;
}

export function ChartCanvas({ type, data, options, height, className }: ChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<ChartInstance | null>(null);

  useEffect(() => {
    const ChartJS = getChart();
    if (!ChartJS || !canvasRef.current) return;

    chartRef.current = new ChartJS(canvasRef.current.getContext('2d'), {
      type,
      data,
      options: { responsive: true, maintainAspectRatio: false, ...options },
    });

    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, [type, data, options]);

  if (!getChart()) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Chart library unavailable
      </div>
    );
  }

  return (
    <div className={className} style={height ? { height } : undefined}>
      <canvas ref={canvasRef} />
    </div>
  );
}

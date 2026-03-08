import { useRef, useEffect } from 'react';

declare const Chart: any;

function getChart(): typeof Chart | null {
  return typeof window !== 'undefined' && (window as any).Chart ? (window as any).Chart : null;
}

interface ChartProps {
  type: string;
  data: any;
  options?: any;
  height?: number | string;
  className?: string;
}

export function ChartCanvas({ type, data, options, height, className }: ChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<any>(null);

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

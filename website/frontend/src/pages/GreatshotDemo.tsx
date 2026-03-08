import { useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { Skeleton } from '../components/Skeleton';
import { useGreatshotDetail, useGreatshotCrossref } from '../api/hooks';
import { api } from '../api/client';
import { navigateTo } from '../lib/navigation';
import type { GreatshotHighlight, GreatshotEvent, GreatshotRenderJob } from '../api/types';

const STATUS_COLORS: Record<string, string> = {
  uploaded: 'text-slate-300 border-slate-500/40 bg-slate-800/40',
  scanning: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10',
  analyzed: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10',
  failed: 'text-rose-400 border-rose-400/40 bg-rose-400/10',
  queued: 'text-amber-400 border-amber-400/40 bg-amber-400/10',
  rendering: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10',
  rendered: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10',
};

function fmtMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '--';
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function fmtRelMs(ms: number | undefined, offset: number): string {
  if (ms == null || !Number.isFinite(ms)) return '--';
  return fmtMs(Math.max(0, ms - offset));
}

function Timeline({ events, roundStartMs }: { events: GreatshotEvent[]; roundStartMs: number }) {
  const preview = events.slice(0, 120);
  if (preview.length === 0) return <p className="text-slate-500 text-sm">No timeline events.</p>;
  return (
    <div className="space-y-0.5 max-h-64 overflow-y-auto text-xs">
      {preview.map((ev, i) => (
        <div key={i} className="flex gap-2">
          <span className="text-slate-500 w-14 shrink-0 text-right">{fmtRelMs(ev.t_ms, roundStartMs)}</span>
          {ev.type === 'kill' ? (
            <span className="text-slate-200">
              {ev.attacker || 'world'} → {ev.victim || '?'}{' '}
              <span className="text-amber-400">{ev.weapon || '--'}</span>
            </span>
          ) : ev.type === 'chat' ? (
            <span className="text-slate-300">{ev.attacker}: {ev.message}</span>
          ) : (
            <span className="text-slate-300">{ev.type}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function HighlightCard({
  highlight,
  demoId,
  roundStartMs,
  onRenderQueued,
}: {
  highlight: GreatshotHighlight;
  demoId: string;
  roundStartMs: number;
  onRenderQueued: () => void;
}) {
  const [queuing, setQueuing] = useState(false);
  const meta = highlight.meta as Record<string, unknown>;
  const killSeq = Array.isArray(meta?.kill_sequence) ? (meta.kill_sequence as Array<Record<string, unknown>>) : [];
  const weapons = (meta?.weapons_used ?? {}) as Record<string, number>;

  const handleRender = async () => {
    setQueuing(true);
    try {
      await api.queueGreatshotRender(demoId, highlight.id);
      onRenderQueued();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Render queue failed');
    } finally {
      setQueuing(false);
    }
  };

  return (
    <div className="glass-card p-4 rounded-xl border border-white/10">
      <div className="flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-white">{highlight.type}</div>
          <div className="text-xs text-slate-400 mt-1">
            {highlight.player} | {fmtRelMs(highlight.start_ms, roundStartMs)} – {fmtRelMs(highlight.end_ms, roundStartMs)} | score {highlight.score.toFixed(2)}
          </div>
          {highlight.explanation && <div className="text-xs text-slate-500 mt-1">{highlight.explanation}</div>}
          {killSeq.length > 0 && (
            <div className="mt-2 text-xs leading-relaxed space-y-0.5">
              {killSeq.map((k, i) => (
                <div key={i}>
                  <span className="text-slate-500">{fmtRelMs(k.t_ms as number, roundStartMs)}</span>{' '}
                  {String(k.victim || '?')} <span className="text-amber-400">{String(k.weapon || '?')}</span>
                  {k.headshot ? <span className="text-rose-400 ml-1">HS</span> : null}
                </div>
              ))}
            </div>
          )}
          {Object.keys(weapons).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {Object.entries(weapons)
                .sort((a, b) => b[1] - a[1])
                .map(([w, c]) => (
                  <span key={w} className="px-2 py-0.5 rounded border border-white/10 text-[10px] text-slate-300">
                    {w} x{c}
                  </span>
                ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {highlight.clip_download && (
            <a
              href={highlight.clip_download}
              className="px-3 py-2 rounded-lg text-xs font-bold border border-amber-400/40 text-amber-400 hover:bg-amber-400/10 transition"
            >
              Clip
            </a>
          )}
          <button
            onClick={handleRender}
            disabled={queuing}
            className="px-3 py-2 rounded-lg text-xs font-bold border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition disabled:opacity-50"
          >
            {queuing ? 'Queuing...' : 'Render'}
          </button>
        </div>
      </div>
    </div>
  );
}

function RenderJobRow({ job }: { job: GreatshotRenderJob }) {
  const color = STATUS_COLORS[job.status] || 'text-slate-300 border-white/10';
  return (
    <div className="flex items-center justify-between text-xs glass-card rounded-xl p-3 border border-white/5">
      <span className="text-slate-300 truncate">{job.id}</span>
      <div className="flex items-center gap-2 shrink-0">
        <span className={`px-2 py-1 rounded border ${color}`}>{job.status.toUpperCase()}</span>
        {job.video_download && (
          <a
            href={job.video_download}
            className="px-2 py-1 rounded border border-emerald-400/40 text-emerald-400 hover:bg-emerald-400/10 transition text-[11px] font-bold"
          >
            MP4
          </a>
        )}
        {job.error && <span className="text-rose-400">{job.error}</span>}
      </div>
    </div>
  );
}

function PlayerStatsTable({ stats }: { stats: Record<string, Record<string, number>> }) {
  const players = Object.entries(stats)
    .map(([name, s]) => ({
      name,
      kills: s.kills || 0,
      deaths: s.deaths || 0,
      damage: s.damage_given || s.damage || 0,
      accuracy: s.accuracy ?? null,
      headshots: s.headshots || s.headshot_kills || 0,
      tpm: s.tpm ?? s.time_played_minutes ?? null,
    }))
    .sort((a, b) => b.kills - a.kills);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-slate-500 border-b border-white/10">
            <th className="text-left py-1 pr-3">Player</th>
            <th className="text-right pr-3">Kills</th>
            <th className="text-right pr-3">Deaths</th>
            <th className="text-right pr-3">KDR</th>
            <th className="text-right pr-3">Damage</th>
            <th className="text-right pr-3">Acc%</th>
            <th className="text-right">HS</th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => {
            const kdr = p.deaths > 0 ? (p.kills / p.deaths).toFixed(2) : p.kills > 0 ? String(p.kills) : '0.00';
            return (
              <tr key={p.name} className="border-b border-white/5">
                <td className="py-1 pr-3 text-slate-200">{p.name}</td>
                <td className="text-right pr-3 text-white">{p.kills}</td>
                <td className="text-right pr-3 text-white">{p.deaths}</td>
                <td className="text-right pr-3 text-white">{kdr}</td>
                <td className="text-right pr-3 text-white">{p.damage}</td>
                <td className="text-right pr-3 text-white">{p.accuracy != null ? p.accuracy.toFixed(1) : '--'}</td>
                <td className="text-right text-white">{p.headshots}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CrossrefPanel({ demoId }: { demoId: string }) {
  const { data, isLoading } = useGreatshotCrossref(demoId);
  if (isLoading) return <p className="text-slate-500 text-sm">Checking database...</p>;
  if (!data) return <p className="text-slate-500 text-sm">Cross-reference unavailable.</p>;
  if (!data.matched) return <p className="text-slate-500 text-sm">{data.reason || 'No match found'}</p>;

  const round = (data.round ?? {}) as Record<string, unknown>;
  const confidence = Number(round.confidence || 0);
  const confColor = confidence >= 80 ? 'text-emerald-400' : confidence >= 50 ? 'text-amber-400' : 'text-rose-400';

  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <span className={`text-xs font-bold ${confColor}`}>{confidence}% confidence</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs mb-4">
        <div><span className="text-slate-500">Round ID:</span> <span className="text-white">{String(round.round_id ?? '--')}</span></div>
        <div><span className="text-slate-500">Session:</span> <span className="text-white">{String(round.gaming_session_id ?? '--')}</span></div>
        <div><span className="text-slate-500">Date:</span> <span className="text-white">{String(round.round_date ?? '--')}</span></div>
        <div><span className="text-slate-500">Winner:</span> <span className="text-white">{String(round.winner_team ?? '--')}</span></div>
      </div>
    </div>
  );
}

export default function GreatshotDemo({ params }: { params?: Record<string, string> }) {
  const demoId = params?.demoId ?? null;
  const { data, isLoading, error, refetch } = useGreatshotDetail(demoId);

  if (isLoading) return <Skeleton variant="card" count={3} />;
  if (error || !data) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-4">🔍</div>
        <div className="text-lg font-bold text-rose-400 mb-1">Demo not found</div>
        <p className="text-sm text-slate-500 mb-4">This demo may have been deleted or you don't have access.</p>
        <button onClick={() => navigateTo('#/greatshot/demos')} className="text-sm text-cyan-400 hover:text-white transition-colors">
          Back to Greatshot
        </button>
      </div>
    );
  }

  const statusColor = STATUS_COLORS[data.status] || 'text-slate-300 border-white/10';
  const meta = data.metadata || {};
  const roundStartMs = Number(meta.start_ms || 0);
  const events = data.analysis?.events ?? [];

  return (
    <div>
      <button
        onClick={() => navigateTo('#/greatshot/demos')}
        className="text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4 inline-flex items-center gap-1"
      >
        <span>←</span> Back to Greatshot
      </button>

      <PageHeader title={data.filename || data.id}>
        <span className={`px-3 py-1 rounded-md text-xs font-bold border ${statusColor}`}>
          {data.status.toUpperCase()}
        </span>
      </PageHeader>

      {data.error && (
        <div className="mb-6 text-sm text-rose-400 glass-panel rounded-xl p-4 border border-rose-400/20">
          Error: {data.error}
        </div>
      )}

      {/* Metadata */}
      <GlassPanel className="mb-6">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">Demo Info</div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
          <div><span className="text-slate-500 text-xs">Map</span><div className="text-white font-bold">{String(meta.map || '--')}</div></div>
          <div><span className="text-slate-500 text-xs">Duration</span><div className="text-white font-bold">{fmtMs(meta.duration_ms as number | null)}</div></div>
          <div><span className="text-slate-500 text-xs">Mod</span><div className="text-white font-bold">{String(meta.mod || '--')}</div></div>
          <div><span className="text-slate-500 text-xs">Players</span><div className="text-white font-bold">{String((data.analysis?.stats as Record<string, unknown>)?.player_count ?? (data.analysis?.metadata as Record<string, unknown>)?.player_count ?? '--')}</div></div>
          <div><span className="text-slate-500 text-xs">Created</span><div className="text-white font-bold">{data.created_at ? new Date(data.created_at).toLocaleString() : '--'}</div></div>
        </div>
      </GlassPanel>

      {/* Downloads */}
      {(data.downloads.json || data.downloads.txt) && (
        <div className="flex gap-2 mb-6">
          {data.downloads.json && (
            <a href={data.downloads.json} className="px-3 py-2 rounded-lg border border-cyan-400/40 text-cyan-400 text-xs font-bold hover:bg-cyan-400/10 transition">
              Download JSON
            </a>
          )}
          {data.downloads.txt && (
            <a href={data.downloads.txt} className="px-3 py-2 rounded-lg border border-amber-400/40 text-amber-400 text-xs font-bold hover:bg-amber-400/10 transition">
              Download TXT
            </a>
          )}
        </div>
      )}

      {/* Player Stats */}
      {data.player_stats && Object.keys(data.player_stats).length > 0 && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">Player Stats</div>
          <PlayerStatsTable stats={data.player_stats} />
        </GlassPanel>
      )}

      {/* Highlights */}
      <GlassPanel className="mb-6">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">
          Highlights ({data.highlights.length})
        </div>
        {data.highlights.length === 0 ? (
          <p className="text-slate-500 text-sm">No clip-worthy highlights detected.</p>
        ) : (
          <div className="space-y-3">
            {data.highlights.map((h) => (
              <HighlightCard key={h.id} highlight={h} demoId={data.id} roundStartMs={roundStartMs} onRenderQueued={refetch} />
            ))}
          </div>
        )}
      </GlassPanel>

      {/* Render Jobs */}
      {data.renders.length > 0 && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">
            Render Jobs ({data.renders.length})
          </div>
          <div className="space-y-2">
            {data.renders.map((job) => (
              <RenderJobRow key={job.id} job={job} />
            ))}
          </div>
        </GlassPanel>
      )}

      {/* Timeline */}
      {events.length > 0 && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">
            Timeline ({events.length} events)
          </div>
          <Timeline events={events} roundStartMs={roundStartMs} />
        </GlassPanel>
      )}

      {/* Cross-reference */}
      {data.status === 'analyzed' && (
        <GlassPanel>
          <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">Database Cross-Reference</div>
          <CrossrefPanel demoId={data.id} />
        </GlassPanel>
      )}
    </div>
  );
}

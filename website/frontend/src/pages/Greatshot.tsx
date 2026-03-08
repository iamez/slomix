import { useState, useEffect, useRef, useCallback } from 'react';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { useGreatshotDemos, useAuthMe } from '../api/hooks';
import { api } from '../api/client';
import { navigateTo } from '../lib/navigation';
import type { GreatshotItem } from '../api/types';
import { mapLevelshot } from '../lib/game-assets';

const STATUS_COLORS: Record<string, string> = {
  uploaded: 'text-slate-300 border-slate-500/40 bg-slate-800/40',
  scanning: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10',
  analyzed: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10',
  failed: 'text-rose-400 border-rose-400/40 bg-rose-400/10',
  queued: 'text-amber-400 border-amber-400/40 bg-amber-400/10',
  rendering: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/10',
  rendered: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/10',
};

const TABS = [
  { key: 'demos', label: 'Demos' },
  { key: 'highlights', label: 'Highlights' },
  { key: 'clips', label: 'Clips' },
  { key: 'renders', label: 'Renders' },
] as const;

function fmtMs(ms: number | null): string {
  if (ms == null || !Number.isFinite(ms)) return '--';
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function DemoCard({ item }: { item: GreatshotItem }) {
  const color = STATUS_COLORS[item.status] || 'text-slate-300 border-white/10 bg-slate-800/40';
  return (
    <button
      onClick={() => navigateTo(`#/greatshot/demo/${encodeURIComponent(item.id)}`)}
      className="glass-card p-4 rounded-xl border border-white/10 text-left hover:border-cyan-400/40 transition w-full"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-bold text-white truncate">{item.filename || item.id}</div>
        <span className={`text-[10px] font-bold px-2 py-1 rounded border shrink-0 ${color}`}>
          {item.status.toUpperCase()}
        </span>
      </div>
      <div className="mt-2 text-xs text-slate-400 flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-1.5">
          {item.map && <img src={mapLevelshot(item.map)} alt="" className="w-4 h-4 rounded-sm object-cover" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}
          Map: {item.map || '--'}
        </span>
        <span>Duration: {fmtMs(item.duration_ms)}</span>
        <span>Highlights: {item.highlight_count}</span>
        <span>Renders: {item.rendered_count}/{item.render_job_count}</span>
        {item.created_at && <span>{new Date(item.created_at).toLocaleString()}</span>}
      </div>
      {item.error && <div className="mt-2 text-xs text-rose-400">{item.error}</div>}
    </button>
  );
}

interface PendingDemo {
  filename: string;
  status: string;
  error?: string;
}

export default function Greatshot({ params }: { params?: Record<string, string> }) {
  const section = params?.section || 'demos';
  const [tab, setTab] = useState(section);
  const { data: auth } = useAuthMe();
  const isLoggedIn = !!auth;
  const { data, isLoading, refetch } = useGreatshotDemos(isLoggedIn);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [pending, setPending] = useState<Map<string, PendingDemo>>(new Map());
  const pollRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const items = data?.items ?? [];

  // Analysis polling
  const pollPending = useCallback(async () => {
    const updates = new Map(pending);
    let changed = false;
    for (const [demoId, entry] of updates) {
      if (entry.status === 'analyzed' || entry.status === 'failed') continue;
      try {
        const status = await api.getGreatshotStatus(demoId);
        if (status.status !== entry.status) {
          updates.set(demoId, { ...entry, status: status.status, error: status.error || undefined });
          changed = true;
        }
      } catch {
        // keep trying
      }
    }
    if (changed) {
      setPending(updates);
      // Check if all done
      let allDone = true;
      for (const [, e] of updates) {
        if (e.status !== 'analyzed' && e.status !== 'failed') { allDone = false; break; }
      }
      if (allDone) {
        clearInterval(pollRef.current);
        pollRef.current = undefined;
        refetch();
      }
    }
  }, [pending, refetch]);

  useEffect(() => {
    if (pending.size > 0) {
      let hasPending = false;
      for (const [, e] of pending) {
        if (e.status !== 'analyzed' && e.status !== 'failed') { hasPending = true; break; }
      }
      if (hasPending && !pollRef.current) {
        pollRef.current = setInterval(pollPending, 2500);
      }
    }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = undefined; } };
  }, [pending, pollPending]);

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const fileInput = form.querySelector<HTMLInputElement>('input[type="file"]');
    const files = fileInput?.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadError('');
    const newPending = new Map<string, PendingDemo>();

    for (const file of Array.from(files)) {
      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await fetch('/api/greatshot/upload', { method: 'POST', body: fd });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
          newPending.set(`error-${file.name}`, { filename: file.name, status: 'failed', error: err.detail });
          continue;
        }
        const result = await res.json();
        newPending.set(result.demo_id, { filename: file.name, status: 'uploaded' });
      } catch (err: unknown) {
        newPending.set(`error-${file.name}`, {
          filename: file.name,
          status: 'failed',
          error: err instanceof Error ? err.message : 'Upload failed',
        });
      }
    }

    setPending(newPending);
    setUploading(false);
    form.reset();
    refetch();
  };

  // Filter items by tab
  const highlights = items.filter((i) => i.highlight_count > 0);
  const clips = items.filter((i) => i.highlight_count > 0);
  const renders = items.filter((i) => i.render_job_count > 0);

  if (!isLoggedIn) {
    return (
      <div>
        <PageHeader title="Greatshot" subtitle="Demo analysis and highlight rendering" />
        <GlassPanel className="text-center py-12">
          <div className="text-4xl mb-4">🔒</div>
          <div className="text-lg font-bold text-white mb-2">Login Required</div>
          <p className="text-sm text-slate-400 mb-6">Sign in with Discord to upload and analyze demos.</p>
          <a
            href="/auth/discord"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[#5865F2] hover:bg-[#4752C4] text-white font-bold rounded-xl transition-colors"
          >
            Login with Discord
          </a>
        </GlassPanel>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Greatshot" subtitle={`${items.length} demos`} />

      {/* Upload Form */}
      <GlassPanel className="mb-6">
        <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">Upload Demo</div>
        <form onSubmit={handleUpload} className="flex flex-col sm:flex-row items-start sm:items-end gap-3">
          <label className="flex-1 min-w-0">
            <span className="text-xs text-slate-400 mb-1 block">Demo file(s) (.dm_84)</span>
            <input
              type="file"
              accept=".dm_84"
              multiple
              required
              className="w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-bold file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600 cursor-pointer"
            />
          </label>
          <button
            type="submit"
            disabled={uploading}
            className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-bold rounded-lg transition-colors"
          >
            {uploading ? 'Uploading...' : 'Upload & Analyze'}
          </button>
        </form>
        {uploadError && <div className="mt-3 text-sm text-rose-400">{uploadError}</div>}
      </GlassPanel>

      {/* Analysis Progress */}
      {pending.size > 0 && (
        <GlassPanel className="mb-6 border-cyan-400/20">
          <div className="text-xs font-bold uppercase tracking-widest text-cyan-400 mb-3">Analysis Progress</div>
          <div className="space-y-2">
            {Array.from(pending).map(([id, entry]) => {
              const color = STATUS_COLORS[entry.status] || 'text-slate-300';
              return (
                <div key={id} className="flex items-center gap-2 text-xs">
                  {entry.status === 'analyzed' ? (
                    <span className="text-emerald-400">&#10003;</span>
                  ) : entry.status === 'failed' ? (
                    <span className="text-rose-400">&#10007;</span>
                  ) : (
                    <span className="w-3 h-3 inline-block border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
                  )}
                  <span className="text-slate-200 truncate flex-1">{entry.filename}</span>
                  <span className={color}>{entry.status}</span>
                  {entry.error && <span className="text-rose-400">{entry.error}</span>}
                </div>
              );
            })}
          </div>
        </GlassPanel>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all ${
              tab === t.key
                ? 'border-cyan-400/40 text-cyan-400 bg-cyan-400/10'
                : 'border-white/10 text-slate-300 hover:text-white hover:border-cyan-400/40'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <Skeleton variant="card" count={4} />
      ) : tab === 'demos' ? (
        items.length === 0 ? (
          <EmptyState message="No demos uploaded yet." />
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <DemoCard key={item.id} item={item} />
            ))}
          </div>
        )
      ) : tab === 'highlights' ? (
        highlights.length === 0 ? (
          <EmptyState message="No detected highlights yet. Analyze a demo first." />
        ) : (
          <div className="space-y-2">
            {highlights.slice(0, 12).map((item) => (
              <div key={item.id} className="flex items-center justify-between glass-card rounded-xl p-3 border border-white/5">
                <span className="text-sm text-slate-200 truncate">{item.filename || item.id}</span>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-amber-400">{item.highlight_count} highlights</span>
                  <button
                    onClick={() => navigateTo(`#/greatshot/demo/${encodeURIComponent(item.id)}`)}
                    className="px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition"
                  >
                    Open
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : tab === 'clips' ? (
        clips.length === 0 ? (
          <EmptyState message="No clip candidates yet. Highlights appear after analysis." />
        ) : (
          <div className="space-y-2">
            {clips.slice(0, 12).map((item) => (
              <div key={item.id} className="flex items-center justify-between glass-card rounded-xl p-3 border border-white/5">
                <span className="text-sm text-slate-200 truncate">{item.filename || item.id}</span>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-slate-400">{item.highlight_count} clip windows</span>
                  <button
                    onClick={() => navigateTo(`#/greatshot/demo/${encodeURIComponent(item.id)}`)}
                    className="px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition"
                  >
                    Manage
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        renders.length === 0 ? (
          <EmptyState message="No render jobs yet. Queue rendering from a demo highlight." />
        ) : (
          <div className="space-y-2">
            {renders.slice(0, 12).map((item) => (
              <div key={item.id} className="flex items-center justify-between glass-card rounded-xl p-3 border border-white/5">
                <span className="text-sm text-slate-200 truncate">{item.filename || item.id}</span>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-emerald-400">{item.rendered_count} rendered</span>
                  <span className="text-slate-400">{item.render_job_count} total</span>
                  <button
                    onClick={() => navigateTo(`#/greatshot/demo/${encodeURIComponent(item.id)}`)}
                    className="px-2 py-1 rounded border border-cyan-400/40 text-cyan-400 hover:bg-cyan-400/10 transition"
                  >
                    Open
                  </button>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  );
}

import { useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { Skeleton } from '../components/Skeleton';
import { useUpload } from '../api/hooks';
import { navigateTo } from '../lib/navigation';

const CAT_COLORS: Record<string, string> = {
  config: 'text-cyan-400 border-cyan-400/30 bg-cyan-400/10',
  hud: 'text-purple-400 border-purple-400/30 bg-purple-400/10',
  archive: 'text-amber-400 border-amber-400/30 bg-amber-400/10',
  clip: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10',
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadDetail({ params }: { params?: Record<string, string> }) {
  const uploadId = params?.uploadId ?? null;
  const { data, isLoading, error } = useUpload(uploadId);
  const [copied, setCopied] = useState(false);

  if (isLoading) return <Skeleton variant="card" count={3} />;

  if (error || !data) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-4">🔍</div>
        <div className="text-lg font-bold text-rose-400 mb-1">Upload not found</div>
        <p className="text-sm text-slate-500 mb-4">This upload may have been deleted or the link is invalid.</p>
        <button
          onClick={() => navigateTo('#/uploads')}
          className="text-sm text-cyan-400 hover:text-white transition-colors"
        >
          Browse all uploads
        </button>
      </div>
    );
  }

  const catColor = CAT_COLORS[data.category] || 'text-slate-400 border-white/10 bg-white/5';
  const shareUrl = `${window.location.origin}${window.location.pathname}#/uploads/${encodeURIComponent(data.id)}`;
  const downloadUrl = `/api/uploads/${encodeURIComponent(data.id)}/download`;

  const copyLink = () => {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div>
      {/* Back button */}
      <button
        onClick={() => navigateTo('#/uploads')}
        className="text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4 inline-flex items-center gap-1"
      >
        <span>←</span> Back to uploads
      </button>

      {/* Header */}
      <PageHeader title={data.title || data.filename}>
        <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase border ${catColor}`}>
          {data.category}
        </span>
      </PageHeader>

      {data.filename !== data.title && data.title && (
        <div className="text-xs text-slate-600 font-mono -mt-6 mb-6">{data.filename}</div>
      )}

      {/* Description */}
      {data.description && (
        <GlassPanel className="mb-6">
          <p className="text-sm text-slate-300 leading-relaxed">{data.description}</p>
        </GlassPanel>
      )}

      {/* Video Player or File Icon */}
      {data.is_playable ? (
        <div className="rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10 mb-6">
          <video controls className="w-full bg-black" style={{ maxHeight: '70vh' }}>
            <source src={downloadUrl} type="video/mp4" />
            Your browser does not support video playback.
          </video>
        </div>
      ) : (
        <GlassPanel className="mb-6 text-center py-12">
          <div className={`w-20 h-20 mx-auto mb-4 rounded-2xl flex items-center justify-center border ${catColor}`}>
            <span className="text-3xl">
              {data.category === 'config' ? '⚙' : data.category === 'hud' ? '🖥' : data.category === 'clip' ? '🎬' : '📦'}
            </span>
          </div>
          <div className="text-sm text-slate-400">{data.filename}</div>
          <div className="text-xs text-slate-600 mt-1">{formatFileSize(data.file_size_bytes)}</div>
        </GlassPanel>
      )}

      {/* Metadata Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <GlassPanel className="!p-4 text-center">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Uploaded by</div>
          <div className="text-sm font-bold text-white">{data.uploader_name || 'Anonymous'}</div>
        </GlassPanel>
        <GlassPanel className="!p-4 text-center">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Size</div>
          <div className="text-sm font-bold text-white">{formatFileSize(data.file_size_bytes)}</div>
        </GlassPanel>
        <GlassPanel className="!p-4 text-center">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Downloads</div>
          <div className="text-sm font-bold text-white">{data.download_count}</div>
        </GlassPanel>
        <GlassPanel className="!p-4 text-center">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 mb-1.5 font-bold">Uploaded</div>
          <div className="text-sm font-bold text-white">
            {data.created_at ? new Date(data.created_at).toLocaleDateString() : 'Unknown'}
          </div>
        </GlassPanel>
      </div>

      {/* Tags */}
      {data.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {data.tags.map((tag) => (
            <span
              key={tag}
              className="px-2.5 py-1 rounded-full text-[10px] font-bold text-slate-400 border border-white/10"
            >
              <span className="opacity-50">#</span>
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3 mb-6">
        <a
          href={downloadUrl}
          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold px-6 py-2.5 rounded-xl transition-all shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)]"
        >
          Download
        </a>
        <button
          onClick={copyLink}
          className={`inline-flex items-center gap-2 text-sm font-bold px-6 py-2.5 rounded-xl border transition-all ${
            copied
              ? 'bg-emerald-500/20 border-emerald-400/30 text-emerald-400'
              : 'bg-purple-500/20 border-purple-400/30 text-purple-400 hover:bg-purple-500/30'
          }`}
        >
          {copied ? 'Copied!' : 'Copy Link'}
        </button>
      </div>

      {/* Shareable Link */}
      <GlassPanel>
        <div className="text-[10px] uppercase tracking-widest text-slate-600 font-bold mb-2">Shareable Link</div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            readOnly
            value={shareUrl}
            onClick={(e) => (e.target as HTMLInputElement).select()}
            className="flex-1 bg-slate-900/50 border border-white/5 rounded-lg px-3 py-2 text-xs text-slate-300 font-mono outline-none focus:border-purple-400/30 transition"
          />
          <button
            onClick={copyLink}
            className="shrink-0 px-3 py-2 rounded-lg text-xs font-bold text-purple-400 hover:bg-purple-500/10 border border-purple-400/20 transition"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </GlassPanel>
    </div>
  );
}

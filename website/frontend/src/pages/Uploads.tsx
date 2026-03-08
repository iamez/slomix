import { useState, useCallback, useRef } from 'react';
import { PageHeader } from '../components/PageHeader';
import { GlassPanel } from '../components/GlassPanel';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { useUploads, usePopularTags, useAuthMe } from '../api/hooks';
import { navigateTo } from '../lib/navigation';

const CATEGORIES = [
  { value: '', label: 'All' },
  { value: 'config', label: 'Config', color: 'text-cyan-400 border-cyan-400/30 bg-cyan-400/10' },
  { value: 'hud', label: 'HUD', color: 'text-purple-400 border-purple-400/30 bg-purple-400/10' },
  { value: 'archive', label: 'Archive', color: 'text-amber-400 border-amber-400/30 bg-amber-400/10' },
  { value: 'clip', label: 'Clip', color: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/10' },
];

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

const PAGE_SIZE = 50;

export default function Uploads() {
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [activeTag, setActiveTag] = useState('');
  const [offset, setOffset] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [searchInput, setSearchInput] = useState('');

  const { data: auth } = useAuthMe();
  const { data, isLoading, refetch } = useUploads({
    category: category || undefined,
    tag: activeTag || undefined,
    search: search || undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const { data: tags } = usePopularTags();

  const handleSearch = useCallback((val: string) => {
    setSearchInput(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      setSearch(val);
      setOffset(0);
    }, 400);
  }, []);

  const handleCategoryChange = (cat: string) => {
    setCategory(cat);
    setOffset(0);
  };

  const handleTagClick = (tag: string) => {
    setActiveTag((prev) => (prev === tag ? '' : tag));
    setOffset(0);
  };

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const formData = new FormData(form);
    const file = formData.get('file') as File | null;
    if (!file || file.size === 0) return;

    setUploading(true);
    setUploadMsg(null);
    try {
      const res = await fetch('/api/uploads', { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      const result = await res.json();
      setUploadMsg({ text: `Uploaded: ${result.filename || file.name}`, type: 'success' });
      form.reset();
      refetch();
    } catch (err: unknown) {
      setUploadMsg({ text: err instanceof Error ? err.message : 'Upload failed', type: 'error' });
    } finally {
      setUploading(false);
    }
  };

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div>
      <PageHeader title="Uploads" subtitle={`${total} community files`} />

      {/* Upload Form (auth only) */}
      {auth && (
        <GlassPanel className="mb-6">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-3">Upload a file</div>
          <form onSubmit={handleUpload} className="flex flex-col sm:flex-row items-start sm:items-end gap-3">
            <label className="flex-1 min-w-0">
              <span className="text-xs text-slate-400 mb-1 block">File</span>
              <input
                type="file"
                name="file"
                required
                className="w-full text-sm text-slate-300 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-bold file:bg-slate-700 file:text-slate-200 hover:file:bg-slate-600 cursor-pointer"
              />
            </label>
            <label>
              <span className="text-xs text-slate-400 mb-1 block">Category</span>
              <select
                name="category"
                required
                className="bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
              >
                <option value="config">Config</option>
                <option value="hud">HUD</option>
                <option value="archive">Archive</option>
                <option value="clip">Clip</option>
              </select>
            </label>
            <label className="flex-1 min-w-0">
              <span className="text-xs text-slate-400 mb-1 block">Title (optional)</span>
              <input
                type="text"
                name="title"
                placeholder="File title..."
                className="w-full bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
              />
            </label>
            <button
              type="submit"
              disabled={uploading}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-bold rounded-lg transition-colors"
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
          {uploadMsg && (
            <div className={`mt-3 text-sm font-medium ${uploadMsg.type === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>
              {uploadMsg.text}
            </div>
          )}
        </GlassPanel>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => handleCategoryChange(cat.value)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-all ${
              category === cat.value
                ? 'bg-white/10 border-white/20 text-white'
                : 'border-white/5 text-slate-400 hover:border-white/10 hover:text-slate-200'
            }`}
          >
            {cat.label}
          </button>
        ))}
        <div className="flex-1" />
        <input
          type="text"
          value={searchInput}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Search uploads..."
          className="bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-1.5 text-sm w-48 focus:outline-none focus:border-blue-500/50"
        />
      </div>

      {/* Tags */}
      {tags && tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-6">
          {tags.map((t) => (
            <button
              key={t.tag}
              onClick={() => handleTagClick(t.tag)}
              className={`px-2 py-0.5 rounded-full text-[10px] font-bold border transition-all ${
                activeTag === t.tag
                  ? 'bg-purple-500/20 border-purple-400/40 text-purple-300'
                  : 'border-white/10 text-slate-500 hover:text-slate-300 hover:border-white/15'
              }`}
            >
              #{t.tag}
              <span className="ml-1 opacity-50">{t.count}</span>
            </button>
          ))}
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <Skeleton variant="card" count={6} />
      ) : items.length === 0 ? (
        <EmptyState message="No uploads found." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => {
            const catColor = CAT_COLORS[item.category] || 'text-slate-400 border-white/10 bg-white/5';
            return (
              <div
                key={item.id}
                onClick={() => navigateTo(`#/uploads/${encodeURIComponent(item.id)}`)}
                className="glass-card rounded-xl p-5 border border-white/5 hover:border-white/10 hover:bg-white/[0.03] transition-all cursor-pointer group"
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-white truncate group-hover:text-blue-300 transition-colors">
                      {item.title || item.filename}
                    </div>
                    <div className="text-[10px] text-slate-600 font-mono truncate mt-0.5">
                      {item.filename}
                    </div>
                  </div>
                  <span className={`shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${catColor}`}>
                    {item.category}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-[10px] text-slate-500">
                  <span>{formatFileSize(item.file_size_bytes)}</span>
                  <span>{item.download_count} downloads</span>
                  <span className="ml-auto">{item.uploader_name || 'Anonymous'}</span>
                </div>
                {item.created_at && (
                  <div className="text-[10px] text-slate-600 mt-1.5">
                    {new Date(item.created_at).toLocaleDateString()}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-8">
          <button
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            Previous
          </button>
          <span className="text-xs text-slate-500">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
            className="px-3 py-1.5 rounded-lg text-xs font-bold border border-white/10 text-slate-400 hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

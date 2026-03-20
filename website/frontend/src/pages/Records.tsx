import { useState } from 'react';
import {
  Skull,
  Zap,
  Star,
  Crosshair,
  Target,
  Heart,
  Bomb,
  Flame,
  Shield,
  Flag,
  CheckCircle,
  Swords,
  ArrowRight,
  X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useRecords, useMaps } from '../api/hooks';
import type { RecordEntry } from '../api/types';
import { GlassCard } from '../components/GlassCard';
import { PageHeader } from '../components/PageHeader';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { cn } from '../lib/cn';
import { formatNumber, formatDate } from '../lib/format';
import { navigateToPlayer } from '../lib/navigation';

interface CategoryDef {
  key: string;
  icon: LucideIcon;
  color: string;
  bg: string;
  border: string;
}

const CATEGORIES: CategoryDef[] = [
  { key: 'kills', icon: Skull, color: 'text-rose-500', bg: 'bg-rose-500/10', border: 'border-rose-500/20' },
  { key: 'damage', icon: Zap, color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  { key: 'xp', icon: Star, color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/20' },
  { key: 'headshots', icon: Crosshair, color: 'text-purple-500', bg: 'bg-purple-500/10', border: 'border-purple-500/20' },
  { key: 'accuracy', icon: Target, color: 'text-emerald-500', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  { key: 'revives', icon: Heart, color: 'text-cyan-500', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' },
  { key: 'gibs', icon: Bomb, color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  { key: 'dyna_planted', icon: Flame, color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/20' },
  { key: 'dyna_defused', icon: Shield, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/20' },
  { key: 'obj_stolen', icon: Flag, color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/20' },
  { key: 'obj_returned', icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-400/10', border: 'border-green-400/20' },
  { key: 'useful_kills', icon: Swords, color: 'text-indigo-400', bg: 'bg-indigo-400/10', border: 'border-indigo-400/20' },
];

function formatCategoryLabel(key: string): string {
  return key.replace(/_/g, ' ');
}

function RecordCard({
  cat,
  records,
  onSelect,
}: {
  cat: CategoryDef;
  records: RecordEntry[];
  onSelect: () => void;
}) {
  if (!records || records.length === 0) return null;
  const top = records[0];
  const Icon = cat.icon;
  const initials = top.player.substring(0, 2).toUpperCase();

  return (
    <GlassCard onClick={onSelect} className="relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity duration-500">
        <Icon className={cn('w-16 h-16', cat.color)} />
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center border', cat.bg, cat.border)}>
          <Icon className={cn('w-5 h-5', cat.color)} />
        </div>
        <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">
          {formatCategoryLabel(cat.key)}
        </div>
      </div>

      <div className="mb-4">
        <div className="text-4xl font-black text-white mb-1 tracking-tight">
          {formatNumber(top.value)}
        </div>
        <div className="text-xs text-slate-500 font-mono flex items-center gap-2">
          <span className="bg-slate-800 px-1.5 py-0.5 rounded text-slate-400">{top.map}</span>
          <span>{formatDate(top.date)}</span>
        </div>
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
            {initials}
          </div>
          <button
            className="font-bold text-white group-hover:text-blue-400 transition"
            onClick={(e) => {
              e.stopPropagation();
              navigateToPlayer(top.player);
            }}
          >
            {top.player}
          </button>
        </div>
        <div className="text-xs text-blue-400 font-medium opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
          View Top 5 <ArrowRight className="w-3 h-3" />
        </div>
      </div>
    </GlassCard>
  );
}

function RecordModal({
  categoryKey,
  records,
  onClose,
}: {
  categoryKey: string;
  records: RecordEntry[];
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="glass-panel rounded-2xl p-6 w-full max-w-lg mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-black text-white">
            {formatCategoryLabel(categoryKey).toUpperCase()}
            <span className="text-slate-500 text-sm font-normal ml-2">Top 5 All-Time</span>
          </h2>
          <button
            className="text-slate-400 hover:text-white transition"
            onClick={onClose}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-2">
          {records.map((rec, i) => {
            const isFirst = i === 0;
            return (
              <div
                key={`${rec.player}-${rec.date}`}
                className={cn(
                  'flex items-center justify-between p-3 rounded-lg border transition hover:bg-white/5',
                  isFirst
                    ? 'bg-amber-400/10 border-amber-400/20'
                    : 'bg-slate-800/50 border-white/5',
                )}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      'font-mono font-bold text-lg w-6 text-center',
                      isFirst ? 'text-amber-400' : 'text-slate-400',
                    )}
                  >
                    #{i + 1}
                  </div>
                  <div className="flex flex-col">
                    <button
                      className={cn(
                        'font-bold text-white text-left hover:text-blue-400 transition',
                        isFirst && 'text-lg',
                      )}
                      onClick={() => navigateToPlayer(rec.player)}
                    >
                      {rec.player}
                    </button>
                    <span className="text-xs text-slate-500 font-mono">
                      {rec.map} &bull; {formatDate(rec.date)}
                    </span>
                  </div>
                </div>
                <div className={cn('font-black text-white', isFirst ? 'text-2xl' : 'text-xl')}>
                  {formatNumber(rec.value)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function Records({ params: _params }: { params?: Record<string, string> }) {
  const [mapFilter, setMapFilter] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const { data: records, isLoading, isError } = useRecords(mapFilter || undefined);
  const { data: maps } = useMaps();

  if (isLoading) {
    return (
      <div className="mt-6">
        <PageHeader title="Hall of Fame" subtitle="All-time records" />
        <Skeleton variant="card" count={8} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="mt-6">
        <PageHeader title="Hall of Fame" subtitle="All-time records" />
        <div className="text-center text-red-400 py-12">Failed to load records.</div>
      </div>
    );
  }

  const hasData = records && Object.keys(records).length > 0;

  return (
    <div className="mt-6">
      <PageHeader title="Hall of Fame" subtitle="All-time records">
        <select
          value={mapFilter}
          onChange={(e) => setMapFilter(e.target.value)}
          className="bg-slate-800 border border-white/10 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500/50"
        >
          <option value="">All Maps</option>
          {maps?.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </PageHeader>

      {!hasData ? (
        <EmptyState message="No records found for this selection." />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {CATEGORIES.map((cat) => {
            const catRecords = records[cat.key];
            if (!catRecords || catRecords.length === 0) return null;
            return (
              <RecordCard
                key={cat.key}
                cat={cat}
                records={catRecords}
                onSelect={() => setSelectedCategory(cat.key)}
              />
            );
          })}
        </div>
      )}

      {selectedCategory && records?.[selectedCategory] && (
        <RecordModal
          categoryKey={selectedCategory}
          records={records[selectedCategory]}
          onClose={() => setSelectedCategory(null)}
        />
      )}
    </div>
  );
}

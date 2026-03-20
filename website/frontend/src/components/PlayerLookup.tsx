import { useMemo, useState } from 'react';
import { Search, UserRound, X } from 'lucide-react';
import { cn } from '../lib/cn';
import { navigateToPlayer } from '../lib/navigation';

interface PlayerResult {
  guid?: string;
  name: string;
}

interface PlayerLookupProps {
  className?: string;
  compact?: boolean;
  placeholder?: string;
  title?: string;
  subtitle?: string;
}

export function PlayerLookup({
  className,
  compact = false,
  placeholder = 'Search players...',
  title = 'Find My Stats',
  subtitle = 'Jump straight into a player profile.',
}: PlayerLookupProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlayerResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const rootClassName = useMemo(
    () => cn(
      'relative overflow-visible rounded-[26px] border border-white/10 bg-slate-950/75 p-3 shadow-[0_22px_48px_rgba(2,6,23,0.34)] backdrop-blur-md',
      compact ? 'max-w-xl' : 'max-w-2xl',
      className,
    ),
    [className, compact],
  );

  async function handleSearch(nextQuery: string) {
    setQuery(nextQuery);
    if (nextQuery.trim().length < 2) {
      setResults([]);
      setOpen(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`/api/search?q=${encodeURIComponent(nextQuery)}&limit=8`);
      if (!response.ok) return;
      const payload = await response.json();
      const nextResults = Array.isArray(payload) ? payload : payload.players || [];
      setResults(nextResults);
      setOpen(true);
    } catch {
      setResults([]);
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setQuery('');
    setResults([]);
    setOpen(false);
  }

  function openFirstResult() {
    if (!results[0]?.name) return;
    navigateToPlayer(results[0].name);
    reset();
  }

  return (
    <div className={rootClassName}>
      {!compact && (
        <div className="mb-3 px-2">
          <div className="section-kicker mb-1">Player Lookup</div>
          <div className="text-xl font-black text-white">{title}</div>
          <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
        </div>
      )}

      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-cyan-400" />
        <input
          type="text"
          value={query}
          onChange={(event) => { void handleSearch(event.target.value); }}
          onBlur={() => setTimeout(() => setOpen(false), 140)}
          onFocus={() => { if (results.length > 0) setOpen(true); }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              openFirstResult();
            }
          }}
          className="w-full rounded-[20px] border border-white/10 bg-slate-900/80 py-3.5 pl-11 pr-12 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-400/50"
          placeholder={placeholder}
        />
        {query && (
          <button
            type="button"
            onClick={reset}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-500 transition hover:bg-white/6 hover:text-white"
            aria-label="Clear player search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute inset-x-0 top-[calc(100%+0.6rem)] z-50 overflow-hidden rounded-[22px] border border-white/10 bg-slate-950/96 p-2 shadow-[0_28px_60px_rgba(2,6,23,0.5)] backdrop-blur-xl">
          {loading ? (
            <div className="px-3 py-3 text-sm text-slate-400">Searching players...</div>
          ) : results.length > 0 ? (
            results.map((player) => (
              <button
                key={player.guid || player.name}
                type="button"
                className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left transition hover:bg-white/5"
                onMouseDown={() => {
                  navigateToPlayer(player.name);
                  reset();
                }}
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-cyan-500/12 text-cyan-300">
                  <UserRound className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-sm font-bold text-white">{player.name}</div>
                  <div className="text-xs text-slate-500">Open full profile</div>
                </div>
              </button>
            ))
          ) : (
            <div className="px-3 py-3 text-sm text-slate-500">No players found.</div>
          )}
        </div>
      )}
    </div>
  );
}

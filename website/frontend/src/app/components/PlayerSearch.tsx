import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../lib/api';
import { Pending, Unavailable, rowStyle } from './ui';

export interface SearchHit { guid: string; name: string }

/**
 * The one player finder: Home's "find your stats" block and the header's
 * compact box share it (visitor review 2026-09-07: the finder was the ninth
 * block on Home and the nav had no way to say "me"). 300 ms debounce, the
 * legacy value: /auth/players/search is rate-limited to 30/min, so a query
 * key per keystroke would burn the budget in one typed name (Codex on
 * #811). Two characters before the first request, six hits shown.
 */
export function PlayerSearch({ ariaLabel, placeholder, compact = false }: { ariaLabel: string; placeholder: string; compact?: boolean }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);
  const trimmed = debounced;
  const search = useQuery({
    queryKey: ['player-search', trimmed],
    enabled: trimmed.length >= 2,
    queryFn: () => apiGet('/auth/players/search', { query: { q: trimmed } }) as Promise<SearchHit[]>,
  });
  const hits = search.data?.slice(0, 6) ?? [];
  const pick = (hit: SearchHit) => {
    setQuery('');
    setDebounced('');
    navigate(`/profile/${hit.guid}`);
  };
  return (
    <div style={{ position: 'relative', minWidth: compact ? 160 : undefined }}>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && hits.length > 0) pick(hits[0]); if (e.key === 'Escape') setQuery(''); }}
        placeholder={placeholder}
        aria-label={ariaLabel}
        className="m"
        style={{
          width: '100%', marginTop: compact ? 0 : 'var(--space-3)', background: 'var(--color-ink-800)',
          border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
          fontSize: compact ? 'var(--fs-small)' : 'var(--fs-value)',
          padding: compact ? 'var(--space-1) var(--space-2)' : 'var(--space-2) var(--space-3)', boxSizing: 'border-box',
        }}
      />
      {trimmed.length >= 2 && (
        <div
          role="listbox"
          aria-label={`${ariaLabel} results`}
          style={compact
            ? { position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20, marginTop: 'var(--space-1)', background: 'var(--color-ink-900)', border: '1px solid var(--color-rule-700)', padding: '0 var(--space-2)' }
            : { marginTop: 'var(--space-2)' }}
        >
          {search.isPending && <Pending label="search" />}
          {search.isError && <Unavailable what="search" />}
          {search.data?.length === 0 && (
            <div className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>no player matches "{trimmed}"</div>
          )}
          {hits.map((hit) => (
            <Link
              key={hit.guid}
              role="option"
              to={`/profile/${hit.guid}`}
              onClick={() => { setQuery(''); setDebounced(''); }}
              style={{ ...rowStyle, display: 'block', padding: 'var(--space-2) 0', textDecoration: 'none', color: 'var(--color-text-100)' }}
            >
              <span className="m" style={{ fontSize: compact ? 'var(--fs-small)' : 'var(--fs-value)' }}>{hit.name}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

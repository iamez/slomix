import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Stack } from './layout';
import { Lbl, Pending, Unavailable } from './ui';
import { apiGet } from '../lib/api';

/** Shape of one /auth/players/search hit — the 8-character guid and a name. */
export interface SearchHit { guid: string; name: string }

/** The way in to any page keyed by a player: the same search endpoint and
 * the same 300 ms debounce as Home — /auth/players/search is rate-limited to
 * 30/min, and a request per keystroke spends that on one typed name.
 * Extracted from Rivalries (Codex on #834) for the compare page. */
export function PickPlayer({ onPick, label, parity }: {
  onPick: (guid: string, name: string) => void;
  label: string;
  parity: string;
}) {
  const [query, setQuery] = useState('');
  const [debounced, setDebounced] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => { setDebounced(query.trim()); }, 300);
    return () => { clearTimeout(timer); };
  }, [query]);
  const search = useQuery({
    queryKey: ['player-search', debounced],
    enabled: debounced.length >= 2,
    queryFn: () => apiGet('/auth/players/search', { query: { q: debounced } }) as Promise<SearchHit[]>,
  });
  return (
    <Stack gap={2} parity={parity} style={{ maxWidth: 380 }}>
      <Lbl>{label}</Lbl>
      <input
        type="text"
        value={query}
        onChange={(e) => { setQuery(e.target.value); }}
        placeholder="player name or alias"
        aria-label={label}
        className="m"
        style={{
          width: '100%', background: 'var(--color-ink-800)',
          border: '1px solid var(--color-rule-700)', color: 'var(--color-text-100)',
          fontSize: 'var(--fs-value)', padding: 'var(--space-2) var(--space-3)', boxSizing: 'border-box',
        }}
      />
      {debounced.length >= 2 && (
        <Stack gap={1} className="rows">
          {search.isPending && <Pending label="search" />}
          {search.isError && <Unavailable what="search" />}
          {search.data?.length === 0 && (
            <span className="m" style={{ fontSize: 'var(--fs-micro)', color: 'var(--color-text-500)' }}>
              no player matches "{debounced}"
            </span>
          )}
          {search.data?.slice(0, 6).map((hit) => (
            <button
              key={hit.guid}
              type="button"
              className="row"
              onClick={() => { onPick(hit.guid, hit.name); setQuery(''); }}
              style={{
                textAlign: 'left', background: 'none', border: 0, borderBottom: '1px solid var(--color-rule-800)',
                color: 'var(--color-text-100)', padding: 'var(--space-2) 0', cursor: 'pointer',
                fontSize: 'var(--fs-value)', fontFamily: 'var(--font-mono)',
              }}
            >
              {hit.name}
            </button>
          ))}
        </Stack>
      )}
    </Stack>
  );
}

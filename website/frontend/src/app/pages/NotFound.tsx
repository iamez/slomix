import { Link, useLocation } from 'react-router';
import { PlayerSearch } from '../components/PlayerSearch';
import { Lbl } from '../components/ui';

/**
 * A real 404 (visitor review 2026-09-07: the catch-all said "phase 0 · not
 * built yet", which is a builder's note, not an answer). It names the path,
 * offers the three places a lost link usually meant, and the finder.
 */
export function NotFound() {
  const { pathname } = useLocation();
  return (
    <div data-parity="not-found" style={{ paddingTop: 'var(--space-7)', maxWidth: 560 }}>
      <Lbl>404 · no such page</Lbl>
      <h1
        style={{
          fontSize: 'var(--fs-display)', letterSpacing: '0.04em', textTransform: 'uppercase',
          lineHeight: 1.05, margin: 'var(--space-3) 0 0', fontWeight: 500,
        }}
      >
        nothing lives here
      </h1>
      <p className="m" style={{ marginTop: 'var(--space-3)', fontSize: 'var(--fs-small)', color: 'var(--color-text-300)' }}>
        <code>{pathname}</code> is not a page on this site. Old links to the legacy site go through a redirect when one exists; this one did not.
      </p>
      <nav aria-label="Where to go instead" style={{ display: 'flex', gap: 'var(--space-5)', marginTop: 'var(--space-5)' }}>
        <Link to="/">home</Link>
        <Link to="/sessions">sessions</Link>
        <Link to="/leaderboards">leaderboards</Link>
      </nav>
      <div style={{ marginTop: 'var(--space-5)' }}>
        <Lbl>or find a player</Lbl>
        <PlayerSearch ariaLabel="Find a player" placeholder="player name or alias" />
      </div>
    </div>
  );
}

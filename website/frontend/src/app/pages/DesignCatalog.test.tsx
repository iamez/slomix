import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DesignCatalog } from './DesignCatalog';

/**
 * A catalogue that quietly loses a component is worse than no catalogue: it
 * says "everything is here" while the piece you came to look at is gone. So
 * the benches are asserted by name, and the three states a real page only
 * shows when something is wrong are asserted by their exact wording.
 *
 * The other thing worth pinning is that this page talks to nothing. It is
 * meant to be openable when the backend is down or the data is empty, which
 * is exactly when someone is most likely to be reworking layout.
 */

afterEach(() => {
  // The fetch stub below must not outlive this file. Every other page test
  // here restores its mocks for the same reason, and leaving a rejecting
  // fetch behind is the kind of failure that appears in a full run and
  // vanishes when the file is run alone.
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderCatalog() {
  const fetchSpy = vi.fn(() => Promise.reject(new Error('the catalogue must not fetch')));
  vi.stubGlobal('fetch', fetchSpy);
  render(
    <MemoryRouter>
      <DesignCatalog />
    </MemoryRouter>,
  );
  return fetchSpy;
}

describe('DesignCatalog', () => {
  it('leaves no declared colour out of the swatches', () => {
    // A catalogue that omits a token is worse than no catalogue: it claims
    // completeness while the piece someone came to check is absent. Seven
    // were missing on the first pass — team-a/b among them, which is exactly
    // where a visual regression would hide (Codex on #827).
    const css = readFileSync('src/app/tokens.css', 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    const declared = [...css.matchAll(/^\s*(--color-[a-z0-9-]+):/gm)].map((m) => m[1]);
    const page = readFileSync('src/app/pages/DesignCatalog.tsx', 'utf8');
    const catalogued = new Set(
      [...page.matchAll(/\{ token: '(--color-[a-z0-9-]+)'/g)].map((m) => m[1]),
    );
    expect(declared.filter((name) => !catalogued.has(name))).toEqual([]);
  });

  it('shows every bench, so a missing component is visible', () => {
    renderCatalog();
    for (const bench of ['colour', 'type', 'spacing', 'controls', 'figures', 'states', 'rows']) {
      expect(
        document.querySelector(`[data-parity="design.${bench}"]`),
        `the ${bench} bench is missing`,
      ).not.toBeNull();
    }
  });

  it('renders the states a working page hides, and keeps them apart', () => {
    renderCatalog();
    const pending = screen.getByText('leaderboard…');
    const failed = screen.getByText('weapon stats: unavailable');
    // The third state came from a hand-written span until <Absent> existed —
    // the workshop could not show the piece because it was not a piece.
    const absent = screen.getByText('no map has been played twice in this window');
    expect(pending).toBeInTheDocument();
    expect(absent).toBeInTheDocument();
    // A failure is the only one that wears the negative colour. If absence
    // ever borrowed it, this page would stop teaching the distinction it
    // exists to teach.
    expect(failed.getAttribute('style')).toContain('--color-neg');
    expect(absent.getAttribute('style')).toContain('--color-text-500');
    expect(absent.getAttribute('style')).not.toContain('--color-neg');
  });

  it('shows the controls in both of their states at once', () => {
    renderCatalog();
    expect(screen.getByRole('button', { name: 'DPM' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'KILLS' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('tab', { name: 'Summary' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Players' })).toHaveAttribute('aria-selected', 'false');
  });

  it('calls no endpoint, so it opens when the data does not', () => {
    const fetchSpy = renderCatalog();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('draws each row with one hairline, not two', () => {
    // .row already carries a bottom border; a `divided` Stack adds a top one
    // to every child after the first, so the two together drew doubled lines
    // between neighbours — in the bench whose whole job is to show what a row
    // looks like (Codex on #827).
    renderCatalog();
    const bench = document.querySelector('[data-parity="design.rows"]');
    expect(bench).not.toBeNull();
    expect(bench?.querySelectorAll('.row').length).toBe(3);
    expect(bench?.querySelectorAll('.stack-divided').length).toBe(0);
    // …and the list does not end on a rule hanging under nothing: `.rows`
    // clears the last row's border in CSS, so no row has to know whether it
    // happens to be last (Codex on #828).
    expect(bench?.querySelector('.rows')).not.toBeNull();
  });

  it('reads the type sizes off the page instead of repeating them', () => {
    // jsdom resolves no stylesheet, so the measurement comes back unusable
    // and the row says so rather than inventing a number — the same rule the
    // rest of the app follows about absent values.
    renderCatalog();
    expect(screen.getAllByText(/caption ·/).length).toBe(1);
  });

  it('names each colour by what it means, not by where it is used', () => {
    renderCatalog();
    // The design's rule is that colour carries exactly four meanings; the
    // catalogue is where that rule is legible rather than remembered.
    expect(screen.getByText('row hairline')).toBeInTheDocument();
    expect(screen.getByText('better')).toBeInTheDocument();
    expect(screen.getByText('worse')).toBeInTheDocument();
    // 'allies' appears twice on purpose — once as the token's name and once
    // as its meaning — which is itself the point being asserted: the token
    // and the thing it stands for are shown together.
    expect(screen.getAllByText('allies')).toHaveLength(2);
  });
});

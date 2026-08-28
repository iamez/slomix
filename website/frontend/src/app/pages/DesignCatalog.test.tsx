import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
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
  it('shows every bench, so a missing component is visible', () => {
    renderCatalog();
    for (const bench of ['colour', 'type', 'spacing', 'controls', 'figures', 'states', 'rows']) {
      expect(
        document.querySelector(`[data-parity="design.${bench}"]`),
        `the ${bench} bench is missing`,
      ).not.toBeNull();
    }
  });

  it('renders the states a working page hides', () => {
    renderCatalog();
    expect(screen.getByText('leaderboard…')).toBeInTheDocument();
    expect(screen.getByText('weapon stats: unavailable')).toBeInTheDocument();
    expect(screen.getByText('no map history recorded yet')).toBeInTheDocument();
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

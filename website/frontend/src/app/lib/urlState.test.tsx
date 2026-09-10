import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { describe, expect, it } from 'vitest';
import { useUrlNumber, useUrlState, useUrlStateNullable } from './urlState';

function Harness() {
  const [stat, setStat] = useUrlState('stat', 'games', ['games', 'dpm', 'kills'] as const);
  const [type, setType] = useUrlStateNullable('type');
  const [days, setDays] = useUrlNumber('days', 30, [7, 30, 90]);
  const { search } = useLocation();
  return (
    <div>
      <div data-testid="state">{`${stat}|${type ?? 'null'}|${days}`}</div>
      <div data-testid="search">{search}</div>
      <button type="button" onClick={() => { setStat('dpm'); }}>dpm</button>
      <button type="button" onClick={() => { setStat('games'); }}>games</button>
      <button type="button" onClick={() => { setType('headshot'); }}>type</button>
      <button type="button" onClick={() => { setType(null); }}>clear type</button>
      <button type="button" onClick={() => { setDays(90); }}>90d</button>
    </div>
  );
}

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes><Route path="*" element={<Harness />} /></Routes>
    </MemoryRouter>,
  );
}

describe('url state', () => {
  it('reads the address bar and writes only what differs from the default', () => {
    renderAt('/');
    expect(screen.getByTestId('state').textContent).toBe('games|null|30');
    expect(screen.getByTestId('search').textContent).toBe('');
    fireEvent.click(screen.getByText('dpm'));
    expect(screen.getByTestId('search').textContent).toBe('?stat=dpm');
    fireEvent.click(screen.getByText('type'));
    expect(screen.getByTestId('search').textContent).toBe('?stat=dpm&type=headshot');
    // Back to the default: the parameter LEAVES, it does not linger as noise.
    fireEvent.click(screen.getByText('games'));
    expect(screen.getByTestId('search').textContent).toBe('?type=headshot');
    fireEvent.click(screen.getByText('clear type'));
    expect(screen.getByTestId('search').textContent).toBe('');
  });

  it('opens a shared link in the state it names', () => {
    renderAt('/?stat=kills&type=headshot&days=90');
    expect(screen.getByTestId('state').textContent).toBe('kills|headshot|90');
  });

  it('a value the page cannot render falls back to the default instead of being trusted', () => {
    renderAt('/?stat=telepathy&days=nine');
    expect(screen.getByTestId('state').textContent).toBe('games|null|30');
    renderAt('/?days=999');
    expect(screen.getAllByTestId('state')[1].textContent).toBe('games|null|30');
  });

  it('keeps the other parameters when one changes', () => {
    renderAt('/?type=headshot&days=90');
    fireEvent.click(screen.getByText('dpm'));
    expect(screen.getByTestId('search').textContent).toBe('?type=headshot&days=90&stat=dpm');
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DataTable, type DataColumn } from './DataTable';

type Row = { id: string; name: string; dpm: number; kis: number | null };

const COLUMNS: readonly DataColumn<Row>[] = [
  { key: 'name', label: 'player', align: 'left', format: (r) => r.name, sortValue: (r) => r.name },
  { key: 'dpm', label: 'dpm', title: 'damage per minute', sortValue: (r) => r.dpm },
  { key: 'kis', label: 'kis', title: 'kill impact score', sortValue: (r) => r.kis, format: (r) => (r.kis == null ? null : r.kis.toFixed(1)) },
];
const ROWS: Row[] = [
  { id: 'a', name: 'alpha', dpm: 300, kis: 12.5 },
  { id: 'b', name: 'bravo', dpm: 450, kis: null },
  { id: 'c', name: 'charlie', dpm: 120, kis: 40 },
];

function names(): string[] {
  return screen.getAllByText(/^(alpha|bravo|charlie)$/).map((el) => el.textContent ?? '');
}

describe('DataTable', () => {
  it('sorts by the default column descending, and a header click flips it', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} defaultSort={{ key: 'dpm', dir: 'desc' }} />);
    expect(names()).toEqual(['bravo', 'alpha', 'charlie']);
    const dpm = screen.getByRole('button', { name: /^dpm/ });
    expect(dpm).toHaveAttribute('aria-sort', 'descending');
    fireEvent.click(dpm);
    expect(dpm).toHaveAttribute('aria-sort', 'ascending');
    expect(names()).toEqual(['charlie', 'alpha', 'bravo']);
  });

  it('a click on another column starts descending there, and nulls sort last either way', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} defaultSort={{ key: 'dpm', dir: 'desc' }} />);
    const kis = screen.getByRole('button', { name: /^kis/ });
    fireEvent.click(kis);
    expect(kis).toHaveAttribute('aria-sort', 'descending');
    expect(names()).toEqual(['charlie', 'alpha', 'bravo']);
    fireEvent.click(kis);
    expect(names()).toEqual(['alpha', 'charlie', 'bravo']);
    // The unmeasured cell is a dash, never the word undefined.
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/undefined|NaN/);
  });

  it('the header carries the definition as a tooltip', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} />);
    expect(screen.getByRole('button', { name: /^dpm/ })).toHaveAttribute('title', 'damage per minute');
    expect(screen.getByRole('button', { name: /^kis/ })).toHaveAttribute('title', 'kill impact score');
  });

  it('opens one expanded row at a time', () => {
    render(
      <DataTable columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} expandLabel="weapons"
        renderExpanded={(r) => <div>expanded {r.name}</div>} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'weapons for alpha' }));
    expect(screen.getByText('expanded alpha')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'weapons for bravo' }));
    expect(screen.queryByText('expanded alpha')).toBeNull();
    expect(screen.getByText('expanded bravo')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'weapons for bravo' })).toHaveAttribute('aria-expanded', 'true');
  });

  it('says no rows on an empty input instead of rendering nothing', () => {
    render(<DataTable columns={COLUMNS} rows={[]} rowKey={(r) => r.id} />);
    expect(screen.getByText('no rows')).toBeInTheDocument();
  });
});

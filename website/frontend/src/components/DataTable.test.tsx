import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataTable, type Column } from './DataTable';

interface Player {
  name: string;
  kills: number;
  deaths: number;
}

const columns: Column<Player>[] = [
  { key: 'name', label: 'Player', sortable: true },
  { key: 'kills', label: 'Kills', sortable: true, sortValue: (r) => r.kills },
  { key: 'deaths', label: 'Deaths' },
];

const data: Player[] = [
  { name: 'Alice', kills: 30, deaths: 10 },
  { name: 'Bob', kills: 50, deaths: 20 },
  { name: 'Charlie', kills: 10, deaths: 5 },
];

describe('DataTable', () => {
  it('renders all rows', () => {
    render(<DataTable columns={columns} data={data} keyFn={(r) => r.name} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('Charlie')).toBeInTheDocument();
  });

  it('renders column headers', () => {
    render(<DataTable columns={columns} data={data} keyFn={(r) => r.name} />);
    expect(screen.getByText('Player')).toBeInTheDocument();
    expect(screen.getByText('Kills')).toBeInTheDocument();
    expect(screen.getByText('Deaths')).toBeInTheDocument();
  });

  it('shows empty message when data is empty', () => {
    render(<DataTable columns={columns} data={[]} keyFn={(_, i) => String(i)} emptyMessage="Nothing here" />);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });

  it('sorts by column on click', () => {
    render(<DataTable columns={columns} data={data} keyFn={(r) => r.name} />);

    // Click Kills header to sort desc
    fireEvent.click(screen.getByText('Kills'));

    const rows = screen.getAllByRole('row');
    // rows[0] = header, rows[1..3] = data rows
    expect(rows[1]).toHaveTextContent('Bob');    // 50 kills (highest)
    expect(rows[3]).toHaveTextContent('Charlie'); // 10 kills (lowest)
  });

  it('toggles sort direction on second click', () => {
    render(<DataTable columns={columns} data={data} keyFn={(r) => r.name} />);

    fireEvent.click(screen.getByText('Kills'));  // desc
    fireEvent.click(screen.getByText('Kills'));  // asc

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Charlie'); // 10 kills (lowest first)
    expect(rows[3]).toHaveTextContent('Bob');     // 50 kills (highest last)
  });

  it('clears sort on third click', () => {
    render(<DataTable columns={columns} data={data} keyFn={(r) => r.name} />);

    fireEvent.click(screen.getByText('Kills'));  // desc
    fireEvent.click(screen.getByText('Kills'));  // asc
    fireEvent.click(screen.getByText('Kills'));  // clear

    const rows = screen.getAllByRole('row');
    // Back to original order
    expect(rows[1]).toHaveTextContent('Alice');
  });

  it('does not sort non-sortable columns', () => {
    render(<DataTable columns={columns} data={data} keyFn={(r) => r.name} />);

    fireEvent.click(screen.getByText('Deaths'));

    const rows = screen.getAllByRole('row');
    // Original order preserved
    expect(rows[1]).toHaveTextContent('Alice');
  });

  it('calls onRowClick when row is clicked', () => {
    let clicked: Player | null = null;
    render(
      <DataTable
        columns={columns}
        data={data}
        keyFn={(r) => r.name}
        onRowClick={(row) => { clicked = row; }}
      />,
    );

    fireEvent.click(screen.getByText('Bob'));
    expect(clicked).toEqual({ name: 'Bob', kills: 50, deaths: 20 });
  });

  it('renders with defaultSort', () => {
    render(
      <DataTable
        columns={columns}
        data={data}
        keyFn={(r) => r.name}
        defaultSort={{ key: 'kills', dir: 'asc' }}
      />,
    );

    const rows = screen.getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Charlie'); // lowest kills first
  });
});

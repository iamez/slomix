import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
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
    // The sort state is on the columnheader that wraps the control, not on
    // the button: a button has no sort state to report (a11y pass).
    const dpmHeader = screen.getByRole('columnheader', { name: /^dpm/ });
    expect(dpmHeader).toHaveAttribute('aria-sort', 'descending');
    fireEvent.click(dpm);
    expect(dpmHeader).toHaveAttribute('aria-sort', 'ascending');
    expect(names()).toEqual(['charlie', 'alpha', 'bravo']);
  });

  it('a click on another column starts descending there, and nulls sort last either way', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} defaultSort={{ key: 'dpm', dir: 'desc' }} />);
    const kis = screen.getByRole('button', { name: /^kis/ });
    fireEvent.click(kis);
    expect(screen.getByRole('columnheader', { name: /^kis/ })).toHaveAttribute('aria-sort', 'descending');
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

  it('names the row for the expander when the first cell is a node, not text', () => {
    const linked: readonly DataColumn<Row>[] = [{ ...COLUMNS[0], format: (r) => <a href={`/p/${r.id}`}>{r.name}</a> }, ...COLUMNS.slice(1)];
    render(
      <DataTable columns={linked} rows={ROWS} rowKey={(r) => r.id} expandLabel="weapons"
        expandName={(r) => r.name} renderExpanded={(r) => <div>expanded {r.name}</div>} />,
    );
    // Without expandName the label would fall back to the row key ("weapons for a").
    expect(screen.getByRole('button', { name: 'weapons for alpha' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'weapons for a' })).toBeNull();
  });

  it('pins the first column only when the table is wider than its panel', () => {
    const { unmount } = render(<DataTable<Row> label="wide" columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} minWidth={1400} />);
    expect(screen.getByRole('button', { name: 'player' })).toHaveStyle({ position: 'sticky', left: '0px' });
    expect(screen.getByText('alpha')).toHaveStyle({ position: 'sticky' });
    expect(screen.getByRole('button', { name: 'dpm' })).not.toHaveStyle({ position: 'sticky' });
    unmount();
    render(<DataTable<Row> label="narrow" columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} />);
    expect(screen.getByText('alpha')).not.toHaveStyle({ position: 'sticky' });
  });

  it('says no rows on an empty input instead of rendering nothing', () => {
    render(<DataTable columns={COLUMNS} rows={[]} rowKey={(r) => r.id} />);
    expect(screen.getByText('no rows')).toBeInTheDocument();
  });
});

describe('DataTable export', () => {
  it('offers a CSV only when asked, and writes the rows in the order on screen', () => {
    const saved: { name: string; text: string }[] = [];
    const createURL = vi.fn(() => 'blob:x');
    vi.stubGlobal('URL', { ...URL, createObjectURL: createURL, revokeObjectURL: vi.fn() });
    // Capture what the anchor would download: jsdom has no real save path.
    const realClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function click(this: HTMLAnchorElement) {
      saved.push({ name: this.download, text: '' });
    };
    const blobText: string[] = [];
    const RealBlob = globalThis.Blob;
    vi.stubGlobal('Blob', class extends RealBlob {
      constructor(parts: BlobPart[], options?: BlobPropertyBag) {
        super(parts, options);
        blobText.push(parts.map(String).join(''));
      }
    });

    const plain = render(<DataTable<Row> label="players" columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} />);
    expect(screen.queryByRole('button', { name: /csv/i })).toBeNull();
    plain.unmount();

    render(<DataTable<Row> label="players" columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} defaultSort={{ key: 'dpm', dir: 'desc' }} exportable />);
    fireEvent.click(screen.getByRole('button', { name: /csv/i }));

    expect(saved).toHaveLength(1);
    expect(saved[0].name).toMatch(/^slomix-players-\d{4}-\d\d-\d\d\.csv$/);
    const csv = blobText[0].replace(/^﻿/, '');
    // Header from the labels, then the rows in the SORTED order (dpm desc),
    // with the null kis exported as an empty field, never as 0.
    expect(csv).toBe('player,dpm,kis\r\nbravo,450,\r\nalpha,300,12.5\r\ncharlie,120,40');

    HTMLAnchorElement.prototype.click = realClick;
    vi.unstubAllGlobals();
  });
});

describe('DataTable semantics', () => {
  it('is a table: a header row of columnheaders, then one row of cells per record', () => {
    render(<DataTable<Row> label="players" columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} />);
    const table = screen.getByRole('table', { name: 'players' });
    expect(table).toHaveAttribute('aria-colcount', String(COLUMNS.length));
    // header + one per row
    expect(table).toHaveAttribute('aria-rowcount', String(ROWS.length + 1));
    expect(screen.getAllByRole('row')).toHaveLength(ROWS.length + 1);
    expect(screen.getAllByRole('columnheader')).toHaveLength(COLUMNS.length);
    expect(screen.getAllByRole('cell')).toHaveLength(COLUMNS.length * ROWS.length);
  });

  it('the sort state lives on the columnheader, where a reader looks for it', () => {
    render(<DataTable<Row> label="players" columns={COLUMNS} rows={ROWS} rowKey={(r) => r.id} defaultSort={{ key: 'dpm', dir: 'desc' }} />);
    expect(screen.getByRole('columnheader', { name: /^dpm/ })).toHaveAttribute('aria-sort', 'descending');
    expect(screen.getByRole('columnheader', { name: /^kis/ })).toHaveAttribute('aria-sort', 'none');
    fireEvent.click(screen.getByRole('button', { name: /^dpm/ }));
    expect(screen.getByRole('columnheader', { name: /^dpm/ })).toHaveAttribute('aria-sort', 'ascending');
    // A column with no sortValue is a header, but never claims a sort state:
    // "none" would say it can be sorted and currently is not.
    const fixed: readonly DataColumn<Row>[] = [
      { key: 'name', label: 'player', align: 'left', format: (r) => r.name },
      ...COLUMNS.slice(1),
    ];
    const { container } = render(<DataTable<Row> label="fixed" columns={fixed} rows={ROWS} rowKey={(r) => r.id} />);
    const header = container.querySelector('[role="columnheader"]');
    expect(header?.textContent).toBe('player');
    expect(header).not.toHaveAttribute('aria-sort');
  });
});

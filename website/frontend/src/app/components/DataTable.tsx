/**
 * DataTable (docs/design/11 §B) — the one table: a label header that sorts
 * on click (the active column in the accent), mono cells, a hairline per
 * row, an overflow-x wrapper with a minimum width so a wide table scrolls
 * inside itself instead of the page, a `title` per column carrying the
 * definition, and an optional expander that opens ONE row at a time.
 *
 * Columns are accessors, not key strings: `row[col.key]` is an object
 * indexed by a value, which every scanner in this CI treats as an injection
 * sink, and an accessor lets the compiler see the field (SessionDetail's
 * PLAYER_COLUMNS lesson). A null cell renders `—`, never "undefined" — the
 * route sweep greps the page text for that word.
 *
 * Sizes come from the scale only (tokens.test counts raw px in fontSize/
 * gap/margin/padding); grey notes go through Lbl/Absent/Meta (vocabulary
 * test counts the hand-written pair).
 */
import { useMemo, useState, type ReactNode } from 'react';
import { Lbl, lblStyle } from './ui';

export interface DataColumn<Row> {
  key: string;
  label: ReactNode;
  /** The definition, on the header's `title` — the tooltip. */
  title?: string;
  align?: 'left' | 'right';
  /** Column width in px (a width is not a size the scale governs). */
  width?: number;
  /** What the cell shows; defaults to `sortValue` rendered as text. */
  format?: (row: Row) => ReactNode;
  /** What the column sorts on. Omit for an unsortable column. */
  sortValue?: (row: Row) => number | string | null;
  /** Colour for the whole cell — only for a meaning the design gives a
   *  colour (a team, a side), never for a metric. */
  color?: (row: Row) => string | undefined;
}

export type SortDir = 'asc' | 'desc';

export interface DataTableProps<Row> {
  columns: readonly DataColumn<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  defaultSort?: { key: string; dir: SortDir };
  /** Opens under the row when its toggle is pressed; one at a time. */
  renderExpanded?: (row: Row) => ReactNode;
  expandLabel?: string;
  minWidth?: number;
  parity?: string;
  /** `aria-label` for the table region. */
  label?: string;
  /** The row's name for the expander's aria-label — needed when the first
   *  cell renders a node (a Link), which the label cannot read. */
  expandName?: (row: Row) => string;
}

const DASH = '—';

function compare(a: number | string | null, b: number | string | null): number {
  // Nulls sort last in both directions: an unmeasured value is not a small one.
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b));
}

export function DataTable<Row>({
  columns, rows, rowKey, defaultSort, renderExpanded, expandLabel = 'more', minWidth, parity, label, expandName,
}: DataTableProps<Row>) {
  const [sort, setSort] = useState<{ key: string; dir: SortDir } | null>(defaultSort ?? null);
  const [open, setOpen] = useState<string | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return [...rows];
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return [...rows];
    const read = col.sortValue;
    const sign = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = read(a);
      const vb = read(b);
      // Null stays last whichever way the column points.
      if (va == null || vb == null) return compare(va, vb);
      return sign * compare(va, vb);
    });
  }, [rows, sort, columns]);

  const toggleSort = (col: DataColumn<Row>) => {
    if (!col.sortValue) return;
    setSort((cur) => {
      if (cur?.key !== col.key) return { key: col.key, dir: 'desc' };
      return { key: col.key, dir: cur.dir === 'desc' ? 'asc' : 'desc' };
    });
  };

  const template = columns.map((c) => (c.width != null ? `${c.width}px` : 'minmax(0, 1fr)')).join(' ');
  const gridStyle = { display: 'grid', gridTemplateColumns: template, columnGap: 'var(--space-3)', alignItems: 'center' } as const;

  return (
    <div data-parity={parity} role="region" aria-label={label} style={{ overflowX: 'auto' }}>
      <div style={{ minWidth: minWidth ?? undefined }}>
        <div className="row" style={{ ...gridStyle, padding: 'var(--space-2) 0' }}>
          {columns.map((col) => {
            const activeDir = sort != null && sort.key === col.key ? sort.dir : null;
            const active = activeDir != null;
            const sortable = col.sortValue != null;
            const style = {
              ...lblStyle,
              textAlign: col.align ?? 'right',
              background: 'none', border: 'none', padding: 0, cursor: sortable ? 'pointer' : 'default',
              color: active ? 'var(--color-accent)' : lblStyle.color,
            } as const;
            return sortable ? (
              <button
                key={col.key}
                type="button"
                title={col.title}
                aria-sort={activeDir == null ? 'none' : activeDir === 'asc' ? 'ascending' : 'descending'}
                onClick={() => { toggleSort(col); }}
                style={style}
              >
                {col.label}{activeDir == null ? '' : activeDir === 'asc' ? ' ▴' : ' ▾'}
              </button>
            ) : (
              <span key={col.key} title={col.title} style={style}>{col.label}</span>
            );
          })}
        </div>
        <div className="rows">
          {sorted.map((row) => {
            const key = rowKey(row);
            const isOpen = open === key;
            return (
              <div key={key}>
                <div className="row" style={{ ...gridStyle, padding: 'var(--space-2) 0' }}>
                  {columns.map((col, i) => {
                    const content = col.format ? col.format(row) : col.sortValue ? col.sortValue(row) : null;
                    const shown = content == null || content === '' ? DASH : content;
                    return (
                      <span
                        key={col.key}
                        className={col.align === 'left' ? undefined : 'm'}
                        style={{ textAlign: col.align ?? 'right', fontSize: 'var(--fs-small)', color: col.color?.(row), minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      >
                        {shown}
                        {i === 0 && renderExpanded && (
                          <>
                            {' '}
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              aria-label={`${expandLabel} for ${expandName ? expandName(row) : typeof shown === 'string' ? shown : key}`}
                              onClick={() => { setOpen((cur) => (cur === key ? null : key)); }}
                              className="m"
                              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-400)', fontSize: 'var(--fs-caption)', padding: 0 }}
                            >
                              {isOpen ? `${expandLabel} ▾` : `${expandLabel} ▸`}
                            </button>
                          </>
                        )}
                      </span>
                    );
                  })}
                </div>
                {isOpen && renderExpanded && <div>{renderExpanded(row)}</div>}
              </div>
            );
          })}
        </div>
        {sorted.length === 0 && <Lbl>no rows</Lbl>}
      </div>
    </div>
  );
}

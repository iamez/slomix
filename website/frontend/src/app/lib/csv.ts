/**
 * The rows a table is showing, as a CSV a spreadsheet will open.
 *
 * Visitor review 2026-09-07 (level 3, the analyst): every board on the site
 * was a dead end — the numbers could be read but not taken away. Export is
 * of what is ON SCREEN, in the order it is on screen: the sort the reader
 * chose, and the same values the cells show, so a downloaded file and a
 * screenshot cannot disagree.
 */

/** RFC 4180: quote a field, and double any quote inside it. */
export function csvField(value: unknown): string {
  if (value == null) return '';
  const s = String(value);
  // A leading =, +, - or @ is a formula to Excel and Sheets; a nickname
  // like "-vid-" must not execute when the file is opened. Prefixing with
  // a single quote is the convention those two both read as text.
  const safe = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return /["\n\r,]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function toCsv(header: readonly string[], rows: readonly (readonly unknown[])[]): string {
  return [header.map(csvField).join(','), ...rows.map((r) => r.map(csvField).join(','))].join('\r\n');
}

/** A file name a human can find again: the table's name and today's date. */
export function csvFileName(label: string): string {
  const slug = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'table';
  return `slomix-${slug}-${new Date().toISOString().slice(0, 10)}.csv`;
}

/** Hand the file to the browser. Returns false when the environment has no
 *  DOM download path (jsdom in a test, an embedded viewer), so a caller can
 *  tell "did nothing" from "saved". */
export function downloadCsv(fileName: string, csv: string): boolean {
  if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return false;
  // The BOM is what makes Excel read UTF-8 rather than the local codepage —
  // without it a nickname with a š or a ž arrives mangled.
  const blob = new Blob([`﻿${csv}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return true;
}

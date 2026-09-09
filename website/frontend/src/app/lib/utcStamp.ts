/** An ISO timestamp (with or without an offset) as `YYYY-MM-DD HH:MM UTC`.
 *  Slicing the string dropped the `+00:00` and showed UTC as if it were
 *  local (Codex on #1004); Date.parse keeps the offset and the label says
 *  which clock it is. An unparsable value is returned as given. */
export function utcStamp(iso: string | number): string {
  const ms = typeof iso === 'number' ? iso * 1000 : Date.parse(iso.includes('T') || /[+Z]/.test(iso) ? iso : `${iso.replace(' ', 'T')}Z`);
  if (!Number.isFinite(ms)) return String(iso);
  return `${new Date(ms).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

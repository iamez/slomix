/** `rounds.round_time` in either of its two forms — 'HH:MM:SS' or a digit
 *  string that may have lost its leading zeroes (1–6 digits: '4918' is
 *  00:49:18, the round_time family's documented dual form) — as HH:MM.
 *  Null when the value carries no usable digits. */
export function fmtRoundTime(raw: string | number | null | undefined): string | null {
  if (raw == null) return null;
  const digits = String(raw).replace(/\D/g, '');
  if (digits.length < 1 || digits.length > 6) return null;
  const s = digits.padStart(6, '0');
  return `${s.slice(0, 2)}:${s.slice(2, 4)}`;
}

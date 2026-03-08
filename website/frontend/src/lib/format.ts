export function formatNumber(val: number): string {
  return typeof val === 'number' && !Number.isInteger(val)
    ? val.toFixed(2)
    : String(Math.round(val));
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString();
}

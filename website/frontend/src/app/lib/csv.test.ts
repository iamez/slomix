import { describe, expect, it } from 'vitest';
import { csvField, csvFileName, toCsv } from './csv';

describe('csv', () => {
  it('quotes only what needs quoting, and doubles a quote inside a field', () => {
    expect(csvField('vid')).toBe('vid');
    expect(csvField(42)).toBe('42');
    expect(csvField(null)).toBe('');
    expect(csvField('a,b')).toBe('"a,b"');
    expect(csvField('say "hi"')).toBe('"say ""hi"""');
    expect(csvField('two\nlines')).toBe('"two\nlines"');
  });

  it('defuses a field a spreadsheet would run as a formula', () => {
    // A nickname really can start with one of these; opening the file must
    // not execute it (CSV injection).
    expect(csvField('=1+1')).toBe("'=1+1");
    expect(csvField('-vid-')).toBe("'-vid-");
    expect(csvField('@here')).toBe("'@here");
    // And a normal negative number is still a number, not a formula risk:
    // it is prefixed too, because a spreadsheet cannot tell them apart.
    expect(csvField(-3)).toBe("'-3");
  });

  it('joins with CRLF, the line ending the format specifies', () => {
    expect(toCsv(['player', 'dpm'], [['vid', 313.7], ['.olz', null]]))
      .toBe('player,dpm\r\nvid,313.7\r\n.olz,');
  });

  it('names the file after the table and the day', () => {
    expect(csvFileName('session 159 · players')).toMatch(/^slomix-session-159-players-\d{4}-\d\d-\d\d\.csv$/);
    expect(csvFileName('   ')).toMatch(/^slomix-table-/);
  });
});

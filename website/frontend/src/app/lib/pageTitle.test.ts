import { describe, expect, it } from 'vitest';
import { titleFor } from './pageTitle';

describe('titleFor', () => {
  it('names the route from the registry and ends with the site', () => {
    expect(titleFor('/')).toBe('Home · Slomix');
    expect(titleFor('/sessions')).toMatch(/ · Slomix$/);
  });
  it('carries the identifying parameter', () => {
    expect(titleFor('/session-detail/154')).toMatch(/^.* 154 · Slomix$/);
    expect(titleFor('/spider-web/round/11344')).toMatch(/11344 · Slomix$/);
  });
  it('keeps the bare site name for an unknown path', () => {
    expect(titleFor('/no/such/page')).toBe('Slomix');
  });
});

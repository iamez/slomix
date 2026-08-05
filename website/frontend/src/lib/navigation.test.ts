import { afterEach, describe, expect, it } from 'vitest';

import { navigateToPlayer } from './navigation';

afterEach(() => {
  window.location.hash = '';
});

describe('navigateToPlayer', () => {
  it('builds a path segment, not a query string', () => {
    // parseHashRoute() splits the hash on '?' before matching, and the profile
    // route's parseHash only recognises `#/profile/<id>`. `#/profile?name=X`
    // therefore matched nothing, load() saw no params and no-opped, and
    // clicking a player on a leaderboard opened a blank profile.
    navigateToPlayer('vid');

    expect(window.location.hash).toBe('#/profile/vid');
    expect(window.location.hash).not.toContain('?');
  });

  it('encodes names that would otherwise break the hash', () => {
    navigateToPlayer('a/b c#d');

    expect(window.location.hash).toBe(`#/profile/${encodeURIComponent('a/b c#d')}`);
  });

  it('matches the pattern the profile route parses', () => {
    // Same regex as route-registry.js's profile.parseHash.
    navigateToPlayer('SuperBoyy');

    expect(window.location.hash.match(/^#\/profile\/([^/?]+)/)?.[1]).toBe('SuperBoyy');
  });
});

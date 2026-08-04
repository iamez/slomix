export function navigateTo(hash: string) {
  // Always set location.hash — the legacy hashchange listener parses
  // the route and calls the correct navigateTo(viewId, false, params).
  // Do NOT call window.navigateTo() directly: it expects a viewId, not a hash.
  window.location.hash = hash;
}

export function navigateToPlayer(playerName: string) {
  // Path segment, not a query string. parseHashRoute() splits the hash on '?'
  // before matching, and the profile route's parseHash only recognises
  // `#/profile/<id>` — so `#/profile?name=X` matched nothing, load() saw no
  // params and no-opped, and clicking a player opened a blank profile.
  //
  // The identifier may be a name: /api/stats/player/<id> accepts either and
  // returns the resolved guid.
  navigateTo(`#/profile/${encodeURIComponent(playerName)}`);
}

export function navigateTo(hash: string) {
  // Always set location.hash — the legacy hashchange listener parses
  // the route and calls the correct navigateTo(viewId, false, params).
  // Do NOT call window.navigateTo() directly: it expects a viewId, not a hash.
  window.location.hash = hash;
}

export function navigateToPlayer(playerName: string) {
  navigateTo(`#/profile?name=${encodeURIComponent(playerName)}`);
}

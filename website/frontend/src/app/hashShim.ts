import { hashToPath } from './routes';

/**
 * Client-side shim for legacy hash URLs (docs/design/06 §3). The server never
 * sees a fragment, so this is the only place old Discord links can be
 * translated. Two traps this encodes, both measured (docs/design/13 §S2):
 *
 *  - the rewritten path must carry the router basename — replaceState('/live')
 *    under a '/app' basename is a 404;
 *  - a boot-time call alone misses same-document hash navigation (pasting a
 *    hash link into an already-open tab re-fires no module code), hence the
 *    hashchange listener.
 */
/** Only the legacy grammar ('#/...') is ours to rewrite — an ordinary
 * in-page anchor like '#section' must keep working as an anchor
 * (Codex on #802: the shim was navigating '/app/live#section' to a 404). */
export function isLegacyHash(hash: string): boolean {
  return typeof hash === 'string' && hash.startsWith('#/');
}

export function applyHashShim(basename = '/app'): void {
  const base = basename.replace(/\/$/, '');
  const rewrite = () => {
    if (!isLegacyHash(window.location.hash)) return;
    const mapped = hashToPath(window.location.hash);
    if (mapped) {
      window.history.replaceState(null, '', base + mapped);
      // replaceState does not notify the router; a popstate does.
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  };
  if (isLegacyHash(window.location.hash)) {
    // Boot: rewrite before the router reads location, no popstate needed.
    const mapped = hashToPath(window.location.hash);
    if (mapped) window.history.replaceState(null, '', base + mapped);
  }
  window.addEventListener('hashchange', rewrite);
}

import { matchPath } from 'react-router';
import { APP_ROUTES } from '../routes';

const SITE = 'Slomix';

/** The browser-tab title for a pathname: the route's own label from the
 *  registry, with the identifying parameter where the route has one, and
 *  the site's name last — a tab full of "Slomix" told nothing apart
 *  (audit 2026-09-07 B3: no page set document.title). Unknown paths keep
 *  the bare site name. */
export function titleFor(pathname: string): string {
  for (const route of APP_ROUTES) {
    const m = matchPath({ path: route.path, end: true }, pathname);
    if (!m) continue;
    const params = Object.values(m.params).filter((v): v is string => v != null && v !== '');
    const detail = params.length > 0 ? ` ${params.map((p) => decodeURIComponent(p)).join(' · ')}` : '';
    return `${route.label}${detail} · ${SITE}`;
  }
  return SITE;
}

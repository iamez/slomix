import type { paths } from '../../api/generated/openapi.d';

/**
 * Typed GET for the standalone app (docs/design/06 §4b).
 *
 * What the compiler checks — and what it deliberately cannot:
 *  - paths and query parameter names/types come from docs/api/openapi.json
 *    via openapi-typescript, so a typo'd path or a `days` vs `range_days`
 *    mixup fails the build (that is where the real bugs lived — 07 §C.1);
 *  - response bodies are `unknown` because the backend declares almost no
 *    response_model (06 §4: 259 operations, 5 typed). Real response types
 *    are earned per phase in types.ts as endpoints gain response_model —
 *    never by trusting the generator.
 *
 * No client-side response cache on purpose: the legacy client's module-level
 * 304-retry Map is a memory leak in a long-lived SPA (06 §4c); React Query
 * owns caching in this tree.
 */

type GetOperation = { get: { parameters: { query?: unknown } } };

export type GetPath = {
  [P in keyof paths]: paths[P] extends GetOperation ? P : never;
}[keyof paths];

export type QueryOf<P extends GetPath> = paths[P] extends {
  get: { parameters: { query?: infer Q } };
}
  ? Q
  : never;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
  ) {
    super(`API ${status}: ${path}`);
    this.name = 'ApiError';
  }
}

function buildQuery(query: Record<string, unknown> | undefined): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    params.set(key, String(value));
  }
  const rendered = params.toString();
  return rendered ? `?${rendered}` : '';
}

/** Substitute `{param}` segments, e.g. `/api/rounds/{round_id}/awards`. */
function fillPath(path: string, pathParams: Record<string, string | number> | undefined): string {
  if (!pathParams) return path;
  return path.replace(/\{([^}]+)\}/g, (whole, name: string) => {
    const value = pathParams[name];
    return value === undefined ? whole : encodeURIComponent(String(value));
  });
}

export interface ApiGetOptions<P extends GetPath> {
  // No `& Record<string, unknown>` widening here: it would let a wrong
  // parameter name (`days` vs `range_days`) compile — the exact bug class
  // this wrapper exists to catch (measured: the guard test went green the
  // moment the intersection was added).
  query?: QueryOf<P>;
  pathParams?: Record<string, string | number>;
  signal?: AbortSignal;
}

export async function apiGet<P extends GetPath>(
  path: P,
  options: ApiGetOptions<P> = {},
): Promise<unknown> {
  const url = fillPath(path, options.pathParams) + buildQuery(options.query as Record<string, unknown> | undefined);
  const res = await fetch(url, { signal: options.signal });
  if (!res.ok) throw new ApiError(res.status, url);
  return res.json();
}

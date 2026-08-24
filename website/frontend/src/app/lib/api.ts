import type { paths } from '../../api/generated/openapi.d';

/**
 * Typed GET for the standalone app (docs/design/06 §4b).
 *
 * What the compiler checks — and what it deliberately cannot:
 *  - paths, query parameter names/types AND path parameter names/presence
 *    come from docs/api/openapi.json via openapi-typescript, so a typo'd
 *    path, a `days` vs `range_days` mixup, or a templated path called
 *    without its `{round_id}` all fail the build (that is where the real
 *    bugs lived — 07 §C.1, plus Codex review on #802);
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

/**
 * The generated types mark `path` REQUIRED exactly when the route is
 * templated (`path?: never` otherwise), so this resolves to `never` for
 * plain routes and to the named-param record for templated ones.
 */
export type PathParamsOf<P extends GetPath> = paths[P] extends {
  get: { parameters: { path: infer PP } };
}
  ? PP
  : never;

/**
 * Same convention for query: the generator emits `query: {...}` (required
 * prop) exactly when the operation has REQUIRED query parameters, and
 * `query?: {...}` otherwise — so this resolves to `never` unless the call
 * cannot succeed without a query (Codex on #802: /api/player/search
 * compiled without its required parameter and 422'd at runtime).
 */
export type RequiredQueryOf<P extends GetPath> = paths[P] extends {
  get: { parameters: { query: infer Q } };
}
  ? Q
  : never;

type NeedsOptions<P extends GetPath> = [PathParamsOf<P>] extends [never]
  ? [RequiredQueryOf<P>] extends [never]
    ? false
    : true
  : true;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
  ) {
    super(`API ${status}: ${path}`);
    this.name = 'ApiError';
  }
}

interface BaseOptions<P extends GetPath> {
  // No `& Record<string, unknown>` widening here: it would let a wrong
  // parameter name (`days` vs `range_days`) compile — the exact bug class
  // this wrapper exists to catch (measured: the guard test went green the
  // moment the intersection was added).
  query?: QueryOf<P>;
  signal?: AbortSignal;
}

export type ApiGetOptions<P extends GetPath> = ([RequiredQueryOf<P>] extends [never]
  ? BaseOptions<P>
  : Omit<BaseOptions<P>, 'query'> & { query: QueryOf<P> }) &
  ([PathParamsOf<P>] extends [never]
    ? { pathParams?: never }
    : { pathParams: PathParamsOf<P> });

/**
 * File-producing GETs (upload download/poster, greatshot reports, clips,
 * rendered videos) are in the generated paths map too — res.json() on those
 * rejects a perfectly good 2xx (Codex on #802). apiGetResponse returns the
 * raw Response for the caller to stream/blob; apiGet stays JSON-only.
 */
export async function apiGetResponse<P extends GetPath>(
  path: P,
  ...args: NeedsOptions<P> extends true
    ? [options: ApiGetOptions<P>]
    : [options?: ApiGetOptions<P>]
): Promise<Response> {
  const options = (args[0] ?? {}) as BaseOptions<P> & {
    pathParams?: Record<string, string | number>;
  };
  const url =
    fillPath(path, options.pathParams) +
    buildQuery(options.query as Record<string, unknown> | undefined);
  // nosemgrep
  const res = await fetch(url, { signal: options.signal });
  if (!res.ok) throw new ApiError(res.status, url);
  return res;
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

export async function apiGet<P extends GetPath>(
  path: P,
  // A templated path or a required query REQUIRES options; a plain path may
  // omit them entirely — enforced by the conditional tuple.
  ...args: NeedsOptions<P> extends true
    ? [options: ApiGetOptions<P>]
    : [options?: ApiGetOptions<P>]
): Promise<unknown> {
  // url is a compile-time literal from the generated paths map plus
  // encodeURIComponent'd params — never a user-controlled absolute URL.
  const res = await apiGetResponse(
    path,
    ...(args as [options: ApiGetOptions<P>]),
  );
  return res.json();
}

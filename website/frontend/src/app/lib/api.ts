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
  /** The backend's own `detail` string when the error body carried one —
   *  so a gate like "Linked Discord account required" can be rendered
   *  VERBATIM instead of paraphrased (review on #887). */
  detail?: string;

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
  /** Status surfaces pass 'no-store': a status page must never read a cached
   * body from ANY layer — the legacy system.js lesson, kept verbatim. */
  cache?: RequestCache;
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
  const res = await fetch(url, { signal: options.signal, cache: options.cache });
  if (!res.ok) throw await apiErrorFrom(res, url);
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

// ---------------------------------------------------------------------------
// POST — same discipline as apiGet: paths are compile-time literals from the
// generated map, the body is JSON, and a non-2xx throws ApiError so callers
// branch on status (401 anonymous / 403 unlinked are STATES, not failures,
// on the availability surface).

type PostOperation = { requestBody?: unknown; responses: unknown };
export type PostPath = {
  [P in keyof paths]: paths[P] extends { post: PostOperation } ? P : never;
}[keyof paths];

export async function apiPost<P extends PostPath>(
  path: P,
  body: unknown,
  options?: { pathParams?: Record<string, string | number> },
): Promise<unknown> {
  const url = fillPath(path, options?.pathParams);
  // nosemgrep
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await apiErrorFrom(res, url);
  return res.json();
}

/** Reads the error body ONCE for its `detail`; a non-JSON body (a plain
 *  500 page) leaves detail unset. */
async function apiErrorFrom(res: Response, url: string): Promise<ApiError> {
  const err = new ApiError(res.status, url);
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && typeof (body as { detail?: unknown }).detail === 'string') {
      err.detail = (body as { detail: string }).detail;
    }
  } catch { /* body was not JSON — the status is the whole story */ }
  return err;
}


/** DELETE — the availability channel unlink is the first DELETE the app
 *  makes (`/api/availability/subscriptions/{channel_type}`, slice 2). Same
 *  contract as apiPost: compile-time path literal, `X-Requested-With` for
 *  the backend's CSRF gate, ApiError-with-detail on non-2xx. */
type DeleteOperation = { responses: unknown };
export type DeletePath = {
  [P in keyof paths]: paths[P] extends { delete: DeleteOperation } ? P : never;
}[keyof paths];

export async function apiDelete<P extends DeletePath>(
  path: P,
  options?: { pathParams?: Record<string, string | number> },
): Promise<unknown> {
  const url = fillPath(path, options?.pathParams);
  // nosemgrep
  const res = await fetch(url, {
    method: 'DELETE',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
  });
  if (!res.ok) throw await apiErrorFrom(res, url);
  return res.json();
}


/** Multipart upload — the browser sets the boundary Content-Type itself
 *  and sends Origin on its own; setting Content-Type manually breaks the
 *  boundary. Same ApiError-with-detail contract as apiPost. */
export async function apiUpload<P extends PostPath>(
  path: P,
  form: FormData,
  options?: { pathParams?: Record<string, string | number> },
): Promise<unknown> {
  const url = fillPath(path, options?.pathParams);
  // nosemgrep
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin',
    body: form,
  });
  if (!res.ok) throw await apiErrorFrom(res, url);
  return res.json();
}

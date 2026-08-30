/**
 * The vocabulary for an endpoint's in-band `status` field.
 *
 * ⛔ WHY THIS EXISTS. Most of these endpoints answer **HTTP 200 whether they
 * succeeded or not** — 25 handlers across 11 routers return
 * `{"status": "error", …}` with a 200, and the owner's decision on 2026-08-30
 * was to keep that convention until the legacy pages are retired (see
 * `tests/unit/test_ok_with_status_error_is_a_deliberate_convention.py` for
 * why a lone 404 would render *nothing* instead of "not rated"). `apiGet`
 * throws only on `!res.ok`, so one of those bodies arrives here as ordinary
 * data. The `status` field is the ONLY thing that says which it is.
 *
 * ⚠️ THE REASON THIS IS URGENT RATHER THAN TIDY: **20 of those 25 handlers are
 * proximity**, i.e. phase 5. Today three pages carry the same two-element list
 * by hand — `MapsPage` as a local const, `WeaponsPage` and `Home` as inline
 * literals — which is survivable at three and is not at twenty.
 *
 * ⛔ WHY IT IS NOT A GENERAL `isFailure(status)`. `status` is heavily
 * overloaded across this API: measured over the backend, it takes **30
 * distinct string values**, and most are not verdicts about whether a request
 * worked. `queued`/`uploaded` are an upload lifecycle, `LOOKING`/`AVAILABLE`/
 * `MAYBE` are RSVP answers, `live`/`research`/`shadow`/`retired`/`prototype`
 * are a formula's maturity, and `unknown_to_this_pov` is the POV contract
 * deliberately withholding an opponent's clock — a correct answer, not a
 * fault. Applying a blanket failure test to those would blank pages that are
 * working. This module is for the RESPONSE-LEVEL status of a data endpoint,
 * and nothing else.
 */

/** The two spellings that mean "this answer is not usable".
 *
 * Both are live: `error` is the older one, `unavailable` the one #830
 * introduces. Reading both is correct before and after the rename, and a
 * consumer that knows only one goes silently blind the moment the other
 * lands (Codex on #830). */
export const FAILURE_STATUSES = ['error', 'unavailable'] as const;

/** Values that look like failures and are NOT, each for its own reason.
 *
 * Listed rather than merely omitted, because the cost of getting these wrong
 * is the same as missing a failure — a page that hides a real answer:
 *
 * - `no_data`   — a valid answer. Nobody played that scope; painting it red
 *                 claims an outage that did not happen (Codex on #809).
 * - `stale`     — the data is real, the snapshot is old. The backend owns
 *                 that verdict at its own threshold; the page shows the age.
 * - `warning`   — the check RAN and found breaches. The breaches are the
 *                 point; suppressing them would hide the finding.
 * - `degraded`  — reduced quality, present data. Qualify it, do not drop it.
 * - `unknown_to_this_pov` — withheld on purpose by the POV contract.
 */
export const NOT_FAILURE_STATUSES = [
  'no_data',
  'stale',
  'warning',
  'degraded',
  'unknown_to_this_pov',
] as const;

export type FailureStatus = (typeof FAILURE_STATUSES)[number];

/** True when an in-band status says the answer is not usable. */
export function isFailureStatus(status: unknown): status is FailureStatus {
  return typeof status === 'string' && (FAILURE_STATUSES as readonly string[]).includes(status);
}

/**
 * The one question a page actually asks: did this fail, by either route?
 *
 * ⛔ BOTH HALVES ARE REQUIRED. `query.isError` catches the transport failure
 * (`apiGet` threw on a non-2xx); `data.status` catches the in-band one, which
 * arrives with a 200 and would otherwise render as an ordinary empty result.
 * Absence and failure have the same shape once the body is empty, and only
 * this field tells them apart.
 *
 * A missing `status` is NOT a failure: most endpoints do not carry the field
 * at all, and treating its absence as a fault would black out the API.
 */
export function hasFailed(
  query: { isError: boolean },
  data: { status?: string | null } | null | undefined,
): boolean {
  return query.isError || isFailureStatus(data?.status);
}

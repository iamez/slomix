import { describe, it, expect, beforeEach, vi } from 'vitest';
import { installErrorReporting, reportCaughtError } from './errorReporting';

function lastFetchBody(fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const [, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  return JSON.parse(init.body as string);
}

describe('errorReporting', () => {
  beforeEach(() => {
    // Reset the module-level install guard and report state between tests —
    // these are window-global by design (see the "shared guard" comment in
    // the module), so each test needs a clean window.
    window.__slomixErrorReportingInstalled = false;
    window.__slomixEarlyErrors = undefined;
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
  });

  it('truncates a long field to exactly maxLength, not maxLength + marker length', async () => {
    installErrorReporting();
    const longMessage = 'x'.repeat(3000); // over the 2000-char MAX_FIELD_LENGTH

    reportCaughtError(new Error(longMessage));
    await Promise.resolve();

    const body = lastFetchBody(fetch as unknown as ReturnType<typeof vi.fn>);
    // Regression for Codex P1 (#578): the old slice(0, maxLength) + marker
    // produced a string LONGER than maxLength, which the backend's
    // Field(max_length=2000) rejected with a 422 — the report vanished
    // entirely for exactly the long-stack case that most needed reporting.
    expect((body.message as string).length).toBe(2000);
    expect(body.message).toMatch(/…\[truncated\]$/);
  });

  it('installs listeners only once even if called twice (shared window guard)', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    installErrorReporting();
    const firstCallCount = addSpy.mock.calls.length;
    installErrorReporting();
    expect(addSpy.mock.calls.length).toBe(firstCallCount);
    addSpy.mockRestore();
  });

  it('reportCaughtError includes the component stack', async () => {
    installErrorReporting();
    reportCaughtError(new Error('boom'), 'in <ProximityPlayer>');
    await Promise.resolve();

    const body = lastFetchBody(fetch as unknown as ReturnType<typeof vi.fn>);
    expect(body.stack).toContain('in <ProximityPlayer>');
  });
});

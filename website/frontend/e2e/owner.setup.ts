import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test as setup } from '@playwright/test';

// ESM: __dirname does not exist here.
const HERE = path.dirname(fileURLToPath(import.meta.url));

/**
 * Mints the `owner` project's storage state. The site's only login is
 * Discord OAuth, which a headless run cannot walk — so the session cookie
 * is produced by scripts/e2e_owner_session.py, signed with the SAME
 * SESSION_SECRET the backend under test uses (starlette's own cookie
 * format). Works only on a machine that already holds that secret, i.e.
 * the machine running the backend — a test rig, not a bypass.
 *
 * The state file lands in e2e/.auth/ (gitignored): it embeds a signed
 * credential, so it must never reach the repo.
 */
setup('mint owner session', async ({ baseURL }) => {
  const repoRoot = path.resolve(HERE, '..', '..', '..');
  // The repo runs under more than one venv layout; take the first that
  // exists rather than hard-coding one (Copilot on #855). python3 is the
  // last resort so a bare machine fails with the script's own error, not
  // ENOENT on a path.
  const interpreter = ['venv/bin/python', '.venv/bin/python', 'website/venv/bin/python']
    .map((p) => path.join(repoRoot, p))
    .find((p) => existsSync(p)) ?? 'python3';
  const cookie = execFileSync(
    interpreter,
    [path.join(repoRoot, 'scripts', 'e2e_owner_session.py')],
    { encoding: 'utf-8' },
  ).trim();
  const origin = new URL(baseURL ?? 'http://127.0.0.1:8000');
  const state = {
    cookies: [
      {
        name: 'session',
        value: cookie,
        domain: origin.hostname,
        path: '/',
        // -1: a session cookie, matching the backend's own (max_age is the
        // server's concern; the signature carries the timestamp).
        expires: -1,
        httpOnly: true,
        secure: false,
        sameSite: 'Lax' as const,
      },
    ],
    origins: [],
  };
  const dir = path.join(HERE, '.auth');
  mkdirSync(dir, { recursive: true });
  writeFileSync(path.join(dir, 'owner.json'), JSON.stringify(state, null, 2));
});

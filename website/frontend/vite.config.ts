import path from 'node:path';
import { defineConfig } from 'vite';
import { configDefaults } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const outputDir = path.resolve(__dirname, '../static/modern');

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    // e2e/*.spec.ts are Playwright tests (own runner, own `test()` from
    // @playwright/test) — vitest's default include glob matches *.spec.ts
    // too and tries to run them as vitest tests, which fails immediately
    // ("Playwright Test did not expect test() to be called here").
    exclude: [...configDefaults.exclude, 'e2e/**'],
    // A page test here mounts a real page: the session detail brings the
    // matrix, the graphs and the role boards, and the proximity page mounts
    // thirteen panels. Under the full suite's parallelism those exceed the
    // 5 s default and fail as timeouts with nothing wrong — the same three
    // files passed alone on the run that failed them together (2026-09-10,
    // and the same shape on #1017 and #1025 CI). The waits inside the tests
    // are already explicit where they need to be; this is the floor, not a
    // substitute for them.
    testTimeout: 30_000,
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
  define: process.env.VITEST
    ? {} // Tests need development mode for React.act()
    : { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: outputDir,
    emptyOutDir: true,
    // 'hidden': generate .map files but don't emit the
    // `//# sourceMappingURL=` comment, so browsers don't auto-fetch them on
    // every page load — they're still readable at /static/modern/*.js.map
    // for anyone who explicitly opens devtools looking for one. That's fine
    // here: this repo (iamez/slomix) is public, so a sourcemap doesn't leak
    // anything `git clone` doesn't already show. Without this, a pasted
    // production stack trace points at minified/bundled code with no real
    // file names or line numbers (W5, docs/TASKS_FOR_SONNET_2026-07-29.md).
    sourcemap: 'hidden',
    lib: {
      entry: path.resolve(__dirname, 'src/route-host.tsx'),
      formats: ['es'],
      fileName: () => 'route-host.js',
    },
    rollupOptions: {
      output: {
        chunkFileNames: 'chunks/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) return 'route-host.css';
          return 'assets/[name][extname]';
        },
      },
    },
  },
});

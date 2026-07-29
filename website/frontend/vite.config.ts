import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const outputDir = path.resolve(__dirname, '../static/modern');

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
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

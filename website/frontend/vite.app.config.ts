import path from 'node:path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// App-mode build: the standalone SPA served at /app/ (docs/design/06 §1).
// The library-mode build (vite.config.ts) keeps producing static/modern for
// the four live MODERN routes until switchover day — the two configs share
// the package but neither reads the other's output. The dist landing in
// website/static/app is what makes the FastAPI mount in main.py register
// (it only mounts when the directory exists, so a checkout without a build
// — production today — never grows an /app route).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Pinned, not env-driven: the FastAPI mount (/app/assets) and the router
  // basename ('/app') are fixed, so a divergent APP_BASE could only emit
  // asset URLs nothing serves (CodeRabbit on #802).
  base: '/app/',
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: path.resolve(__dirname, '../static/app'),
    emptyOutDir: true,
    manifest: true,
    // Same rationale as vite.config.ts: maps exist for whoever opens devtools,
    // but browsers don't auto-fetch them on every load.
    sourcemap: 'hidden',
    rollupOptions: {
      // NOTE: the entry keeps its source name — the emitted file is
      // static/app/app.html, NOT index.html (measured, docs/design/13 §S1).
      input: path.resolve(__dirname, 'app.html'),
      output: {
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
});

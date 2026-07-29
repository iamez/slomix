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
    sourcemap: false,
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

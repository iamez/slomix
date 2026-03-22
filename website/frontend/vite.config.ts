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
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
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

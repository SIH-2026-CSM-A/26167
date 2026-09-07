import fs from 'fs';
import path from 'path';
import { defineConfig } from 'vitest/config';
import type { Plugin } from 'vite';
import react from '@vitejs/plugin-react';

function serveDemoData(): Plugin {
  const demoDir = path.resolve(__dirname, '../data/demo');
  const mimeTypes: Record<string, string> = {
    '.json': 'application/json',
    '.tif': 'image/tiff',
    '.tiff': 'image/tiff',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
  };

  const handler = (
    req: { url?: string },
    res: { setHeader: (k: string, v: string) => void },
    next: () => void,
  ) => {
    const rawUrl = (req.url || '').split('?')[0];
    const relPath = decodeURIComponent(rawUrl).replace(/^\//, '');
    const filePath = path.resolve(demoDir, relPath);
    if (filePath.startsWith(demoDir) && fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const ext = path.extname(filePath).toLowerCase();
      res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream');
      fs.createReadStream(filePath).pipe(res as unknown as NodeJS.WritableStream);
      return;
    }
    next();
  };

  return {
    name: 'serve-demo-data',
    configureServer(server) {
      server.middlewares.use('/data/demo', handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use('/data/demo', handler);
    },
  };
}

export default defineConfig({
  plugins: [react(), serveDemoData()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/query': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
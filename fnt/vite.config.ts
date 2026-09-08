import fs from 'fs';
import path from 'path';
import { defineConfig } from 'vitest/config';
import type { Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import type { ServerResponse } from 'node:http';

const QUERY_PROXY_TIMEOUT_MS = 180_000;

/** Finish failed upstream requests so the browser can offer an explicit retry. */
function failQueryProxy(response: ServerResponse): void {
  if (response.destroyed || response.writableEnded) return;
  if (response.headersSent) {
    response.destroy();
    return;
  }
  response.writeHead(502, { 'Content-Type': 'application/json' });
  response.end(JSON.stringify({ detail: 'Backend connection lost. Restart the backend and retry.' }));
}

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
      '/query': {
        target: 'http://127.0.0.1:8000',
        proxyTimeout: QUERY_PROXY_TIMEOUT_MS,
        timeout: QUERY_PROXY_TIMEOUT_MS,
        configure(proxy) {
          proxy.on('error', (_error, _request, response) => {
            if ('writeHead' in response) failQueryProxy(response);
          });
          proxy.on('proxyReq', (upstream, _request, response) => {
            upstream.once('error', () => failQueryProxy(response));
          });
          proxy.on('proxyRes', (upstream, _request, response) => {
            const onClose = () => {
              if (!upstream.complete) failQueryProxy(response);
            };
            upstream.once('close', onClose);
            response.once('close', () => upstream.removeListener('close', onClose));
          });
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});

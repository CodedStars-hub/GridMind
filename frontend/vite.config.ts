import { defineConfig, loadEnv } from 'vite';
import { productionApiBase } from './src/api/releaseConfig';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

const frontendDir = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, frontendDir, '');
  if (command === 'build') productionApiBase(env.VITE_API_BASE_URL);
  const target = command === 'serve' ? env.GRIDMIND_API_PROXY_TARGET : undefined;
  if (command === 'serve' && (env.VITE_API_BASE_URL || '/api').startsWith('/api') && !target) throw new Error('The /api development proxy requires GRIDMIND_API_PROXY_TARGET. Configure frontend/.env.local and restart Vite.');
  if (target) {
    const url = new URL(target);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('GRIDMIND_API_PROXY_TARGET must be an HTTPS origin without credentials or a path.');
  }
  return {
    root: frontendDir,
    plugins: [react(), tailwindcss()],
    server: {
      host: 'localhost', port: 5173, strictPort: true,
      // This proxy is development-only and bound to localhost. It is not an open public relay.
      proxy: target ? { '/api': {
        target, changeOrigin: true, secure: true,
        rewrite: path => path.replace(/^\/api(?=\/|$)/, ''),
        configure: proxy => proxy.on('proxyReq', request => {
          // The browser uses same-origin /api. The trusted dev server makes the upstream request.
          // Backend AllowedOriginsJson=[] rejects an Origin header, so omit it on this server-only hop.
          request.removeHeader('origin'); request.removeHeader('cookie'); request.removeHeader('authorization');
        }),
      } } : undefined,
    },
    preview: { host: 'localhost', port: 4173, strictPort: true },
  };
});

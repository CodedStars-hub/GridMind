import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.GRIDMIND_API_PROXY_TARGET;
  if (target) {
    const url = new URL(target);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('GRIDMIND_API_PROXY_TARGET must be an HTTPS origin without credentials or a path.');
  }
  return {
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

// @vitest-environment node
import { afterAll, beforeAll, expect, it, vi } from 'vitest';
import { createServer, resolveConfig, type ViteDevServer } from 'vite';
import { createServer as httpServer } from 'node:http';
import { fileURLToPath } from 'node:url';
import { ApiClient } from '../api/client';
import health from './fixtures/scenarios.json';
import network from './fixtures/network.json';
import simulation from './fixtures/simulation.json';

const requests: { path: string; method: string; body: string; origin?: string; cookie?: string; authorization?: string }[] = [];
let failNetwork = false;
const upstream = httpServer(async (req, res) => {
  let body = ''; for await (const chunk of req) body += chunk;
  requests.push({ path: req.url!, method: req.method!, body, origin: req.headers.origin, cookie: req.headers.cookie, authorization: req.headers.authorization });
  res.setHeader('Content-Type', 'application/json');
  if (req.url === '/v2/network' && failNetwork) { res.statusCode = 503; res.end(JSON.stringify({ error: { code: 'internal_error', field: null, message: 'internal error' } })); return; }
  res.end(JSON.stringify(req.url === '/v2/health' ? { status: 'ok', api_version: 'v2', engine_version: '0.1.0' } : req.url === '/v2/network' ? network : req.url === '/v2/simulate' ? simulation : health));
});
let vite: ViteDevServer;
let origin: string;
beforeAll(async () => {
  await new Promise<void>(resolve => upstream.listen(0, '127.0.0.1', resolve));
  const address = upstream.address(); if (!address || typeof address === 'string') throw new Error('No upstream address');
  // Load the actual app config and plugins; replace only AWS transport with a local HTTP fixture server.
  vite = await createServer({ configFile: fileURLToPath(new URL('../../vite.config.ts', import.meta.url)), server: { host: '127.0.0.1', port: 0, proxy: { '/api': { target: `http://127.0.0.1:${address.port}` } } } });
  await vite.listen();
  const bound = vite.httpServer!.address(); if (!bound || typeof bound === 'string') throw new Error('No Vite address');
  origin = `http://127.0.0.1:${bound.port}`;
}, 20000);
afterAll(async () => { await vite?.close(); await new Promise<void>(resolve => upstream.close(() => resolve())); });
it('routes health, network and simulation through the actual Vite proxy without HTML fallback', async () => {
  const client = new ApiClient(`${origin}/api`);
  expect((await client.health()).status).toBe('ok');
  expect(await client.network()).toEqual(network);
  const input = { ev_kw: 50 as const, pv_kwp: 30 as const, day_type: 'summer_weekday' as const, load_level: 'heavy' as const };
  expect(await client.simulate(input)).toEqual(simulation);
  expect(requests.slice(-3).map(r => [r.path, r.method])).toEqual([['/v2/health', 'GET'], ['/v2/network', 'GET'], ['/v2/simulate', 'POST']]);
  expect(JSON.parse(requests.at(-1)!.body)).toEqual(input);
});
it('preserves structured upstream failures through the proxy', async () => {
  failNetwork = true;
  await expect(new ApiClient(`${origin}/api`).network()).rejects.toMatchObject({ status: 503, code: 'internal_error' });
  failNetwork = false;
});
it('removes browser credentials and Origin from the development upstream hop', async () => {
  await fetch(`${origin}/api/v2/health`, { headers: { Origin: 'http://localhost:5173', Cookie: 'test', Authorization: 'test' } });
  expect(requests.at(-1)).toMatchObject({ path: '/v2/health', origin: undefined, cookie: undefined, authorization: undefined });
});
it('processes Tailwind theme variables in served CSS, preserving the sans-serif font stack', async () => {
  const response = await fetch(`${origin}/src/styles.css`);
  expect(response.ok).toBe(true);
  const css = await response.text();
  expect(css).not.toContain('@theme');
  expect(css).toContain('--font-sans:');
  expect(css).toContain('Segoe UI');
});
it('refuses to silently serve HTML when /api has no configured upstream', async () => {
  vi.stubEnv('GRIDMIND_API_PROXY_TARGET', '');
  vi.stubEnv('VITE_API_BASE_URL', '/api');
  try {
    await expect(resolveConfig({ configFile: fileURLToPath(new URL('../../vite.config.ts', import.meta.url)) }, 'serve')).rejects.toThrow('requires GRIDMIND_API_PROXY_TARGET');
  } finally { vi.unstubAllEnvs(); }
});

import { isHealth, isNetwork, isScenarios, isSimulation } from '../src/api/guards.ts';

// Exercise the running development proxy, not a mock or a direct AWS shortcut.
const origin = process.argv[2] || 'http://localhost:5173';
const url = new URL(origin);
if (!['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Supply a localhost origin without credentials or a path.');
async function check(path, guard, payload) {
  const response = await fetch(new URL(`/api/v2/${path}`, url), {
    signal: AbortSignal.timeout(20000),
    ...(payload ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : {}),
  });
  const type = response.headers.get('content-type') || '';
  if (!response.ok || !type.includes('application/json')) throw new Error(`${path}: HTTP ${response.status}, content type ${type || 'missing'}; check proxy configuration and restart Vite.`);
  const body = await response.json();
  if (!guard(body)) throw new Error(`${path}: JSON does not match the frontend API contract.`);
  console.log(`PASS /api/v2/${path}: HTTP ${response.status}, JSON contract valid`);
  return body;
}
try {
  await check('health', isHealth);
  await check('network', isNetwork);
  const scenarios = await check('scenarios', isScenarios);
  const { ev_kw, pv_kwp, day_type, load_level } = scenarios.defaults;
  await check('simulate', isSimulation, { ev_kw, pv_kwp, day_type, load_level });
} catch (error) {
  console.error(`FAIL API smoke: ${error instanceof Error ? error.message : 'Unknown error'}`);
  process.exitCode = 1;
}

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';
import { App } from '../app/App';
import { DataProvider } from '../app/DataProvider';
import { ApiClient } from '../api/client';
import network from './fixtures/network.json';
import scenarios from './fixtures/scenarios.json';
import simulation from './fixtures/simulation.json';

const health = { status: 'ok', api_version: 'v2', engine_version: '0.1.0' };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
afterEach(() => vi.unstubAllGlobals());
function setup({ topology = network, simulateStatus = 200 }: { topology?: typeof network; simulateStatus?: number } = {}) {
  const transport = vi.fn<typeof fetch>().mockImplementation(async (input) => {
    const path = String(input);
    if (path.endsWith('/health')) return response(health);
    if (path.endsWith('/network')) return response(topology);
    if (path.endsWith('/scenarios')) return response(scenarios);
    return simulateStatus === 200 ? response(simulation) : response({ error: { code: 'internal_error', message: 'internal error', field: null } }, simulateStatus);
  });
  render(<DataProvider client={new ApiClient('/api', 1000, transport)}><App /></DataProvider>);
  return transport;
}
async function navigate(path: string) {
  window.location.hash = `#${path}`;
  fireEvent(window, new Event('hashchange'));
  await waitFor(() => expect(window.location.hash).toBe(`#${path}`));
}
describe('workspace navigation and real-response rendering', () => {
  it('loads health then network through the default browser transport', async () => {
    const browserFetch = vi.fn(function (this: unknown, input: RequestInfo | URL): Promise<Response> {
      if (this !== globalThis) throw new TypeError('Illegal invocation');
      return Promise.resolve(response(String(input).endsWith('/health') ? health : network));
    });
    vi.stubGlobal('fetch', browserFetch);
    render(<DataProvider><App /></DataProvider>);
    expect(await screen.findByText(network.neighbourhood.name)).toBeTruthy();
    expect(screen.getByText('API connected')).toBeTruthy();
    expect(screen.queryAllByRole('alert')).toHaveLength(0);
    expect(browserFetch.mock.calls.map(([input]) => input)).toEqual(['/api/v2/health', '/api/v2/network']);
  });
  it('keeps successful health connected when the network request fails', async () => {
    const browserFetch = vi.fn(function (this: unknown, input: RequestInfo | URL): Promise<Response> {
      if (this !== globalThis) throw new TypeError('Illegal invocation');
      return Promise.resolve(String(input).endsWith('/health') ? response(health) : response({ error: { code: 'internal_error', message: 'internal error', field: null } }, 500));
    });
    vi.stubGlobal('fetch', browserFetch);
    render(<DataProvider><App /></DataProvider>);
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText('API connected')).toBeTruthy();
    expect(screen.queryByText('API unavailable')).toBeNull();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    expect(screen.queryByText(network.neighbourhood.name)).toBeNull();
  });
  it('ignores the cancelled StrictMode effect and completes the current requests', async () => {
    const browserFetch = vi.fn(function (this: unknown, input: RequestInfo | URL): Promise<Response> {
      if (this !== globalThis) throw new TypeError('Illegal invocation');
      return Promise.resolve(response(String(input).endsWith('/health') ? health : network));
    });
    vi.stubGlobal('fetch', browserFetch);
    render(<StrictMode><DataProvider><App /></DataProvider></StrictMode>);
    expect(await screen.findByText(network.neighbourhood.name)).toBeTruthy();
    expect(screen.getByText('API connected')).toBeTruthy();
    expect(screen.queryAllByRole('alert')).toHaveLength(0);
    expect(browserFetch.mock.calls.map(([input]) => input)).toEqual(['/api/v2/health', '/api/v2/health', '/api/v2/network']);
  });
  it('shows loading first, then actual configured topology and health', async () => {
    setup();
    expect(screen.getByText('Loading neighbourhood configuration…')).toBeTruthy();
    expect(await screen.findByText(network.neighbourhood.name)).toBeTruthy();
    expect(screen.getByText('API connected')).toBeTruthy();
    expect(screen.getByText(network.transformers[0]!.name)).toBeTruthy();
    expect(screen.getByText('No results have been assumed')).toBeTruthy();
    expect(screen.queryByText('0.9499')).toBeNull();
  });
  it('uses accessible navigation and renders network, planning and not-found pages', async () => {
    setup(); await screen.findByText(network.neighbourhood.name);
    await navigate('/network');
    expect(await screen.findByText('Candidate charging sites')).toBeTruthy();
    const siteTable = screen.getByRole('table', { name: 'Candidate site configuration' });
    expect(within(siteTable).getByText(network.sites[0]!.name)).toBeTruthy();
    const nav = screen.getByRole('navigation', { name: 'Primary navigation' });
    expect(within(nav).getByRole('link', { name: /Network/ }).getAttribute('aria-current')).toBe('page');
    await navigate('/planning');
    expect(await screen.findByText('01 · Define the charging target')).toBeTruthy();
    await navigate('/missing');
    expect(await screen.findByRole('heading', { level: 1, name: /route isn’t/ })).toBeTruthy();
  });
  it('supports the mobile navigation toggle', async () => {
    setup();
    const button = screen.getByRole('button', { name: /Navigation/ });
    expect(button.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(button);
    expect(button.getAttribute('aria-expanded')).toBe('true');
  });
  it('renders an honest empty inventory', async () => {
    setup({ topology: { ...network, transformers: [], sites: [] } });
    expect(await screen.findByText('No transformers configured')).toBeTruthy();
  });
  it('reports unavailable services with no fabricated measurements', async () => {
    const transport = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('offline'));
    render(<DataProvider client={new ApiClient('/api', 1000, transport)}><App /></DataProvider>);
    expect(await screen.findByText('API unavailable')).toBeTruthy();
    expect(await screen.findAllByRole('alert')).toHaveLength(2);
    expect(screen.queryByText(network.neighbourhood.name)).toBeNull();
    expect(screen.queryByText('Nameplate capacity')).toBeNull();
  });
  it('loads scenario defaults and displays only returned simulation results', async () => {
    const transport = setup(); await screen.findByText(network.neighbourhood.name);
    await navigate('/assessment');
    const ev = await screen.findByLabelText('EV hub rating');
    expect((ev as HTMLSelectElement).value).toBe(String(scenarios.defaults.ev_kw));
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    expect(await screen.findByText(simulation.verdict.message)).toBeTruthy();
    expect(screen.getByText('0.9499')).toBeTruthy();
    expect(screen.getByText('21:00–21:00 · 0.9499 p.u.')).toBeTruthy();
    const request = transport.mock.calls.find(([input]) => String(input).endsWith('/simulate'));
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ ev_kw: 50, pv_kwp: 30, day_type: 'summer_weekday', load_level: 'heavy' });
  });
  it('does not present a failed simulation as a result', async () => {
    setup({ simulateStatus: 500 }); await screen.findByText(network.neighbourhood.name);
    await navigate('/assessment'); await screen.findByLabelText('EV hub rating');
    fireEvent.click(screen.getByRole('button', { name: 'Run simulation' }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByText('Minimum voltage')).toBeNull();
  });
});

it('keeps actual network data visible when health returns HTML instead of API JSON', async () => {
  const transport = vi.fn<typeof fetch>().mockImplementation(async input => String(input).endsWith('/health')
    ? new Response('<html>Vite fallback</html>', { headers: { 'Content-Type': 'text/html' } }) : response(network));
  render(<DataProvider client={new ApiClient('/api', 1000, transport)}><App /></DataProvider>);
  expect(await screen.findByText(network.neighbourhood.name)).toBeTruthy();
  expect(screen.getByText('API unavailable')).toBeTruthy();
  expect(screen.getByRole('alert').textContent).toContain('received HTML');
});

import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, normalizeBaseUrl } from '../api/client';
import network from './fixtures/network.json';
import scenarios from './fixtures/scenarios.json';
import simulation from './fixtures/simulation.json';
const health = { status: 'ok', api_version: 'v2', engine_version: '0.1.0' };
const respond = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('API client contract and transport', () => {
  it('calls default browser fetch with its required global receiver', async () => {
    // Native Window.fetch rejects an ApiClient receiver before sending a request.
    const browserFetch = vi.fn(function (this: unknown): Promise<Response> {
      if (this !== globalThis) throw new TypeError('Illegal invocation');
      return Promise.resolve(respond(health));
    });
    vi.stubGlobal('fetch', browserFetch);
    expect(await new ApiClient('/api').health()).toEqual(health);
    expect(browserFetch.mock.calls).toHaveLength(1);
  });
  it('uses the configured v2 endpoint without credentials', async () => {
    const transport = vi.fn<typeof fetch>().mockResolvedValue(respond(health));
    expect(await new ApiClient('https://api.example/', 1000, transport).health()).toEqual(health);
    expect(transport.mock.calls[0]?.[0]).toBe('https://api.example/v2/health');
    expect(transport.mock.calls[0]?.[1]).toMatchObject({ method: 'GET', credentials: 'omit', cache: 'no-store' });
  });
  it('loads backend-derived network and scenario fixtures', async () => {
    const transport = vi.fn<typeof fetch>().mockResolvedValueOnce(respond(network)).mockResolvedValueOnce(respond(scenarios));
    const client = new ApiClient('/api', 1000, transport);
    expect(await client.network()).toEqual(network);
    expect(await client.scenarios()).toEqual(scenarios);
  });
  it('posts only supported scenario inputs and validates the result', async () => {
    const transport = vi.fn<typeof fetch>().mockResolvedValue(respond(simulation));
    const inputs = { ev_kw: 50 as const, pv_kwp: 30 as const, day_type: 'summer_weekday' as const, load_level: 'heavy' as const };
    expect(await new ApiClient('/api', 1000, transport).simulate(inputs)).toEqual(simulation);
    expect(transport.mock.calls[0]?.[1]).toMatchObject({ method: 'POST', body: JSON.stringify(inputs), headers: { 'Content-Type': 'application/json' } });
  });
  it('preserves structured server errors and the offending field', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(respond({ error: { code: 'invalid_input', field: 'ev_kw', message: 'Unsupported EV rating' } }, 400)));
    await expect(client.health()).rejects.toMatchObject({ code: 'invalid_input', field: 'ev_kw', status: 400, message: 'Unsupported EV rating' });
  });
  it('handles gateway throttling without inventing data', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(respond({ message: 'Too many requests' }, 429)));
    await expect(client.health()).rejects.toMatchObject({ status: 429, code: 'http_error' });
  });
  it('rejects invalid JSON even when HTTP status is successful', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>error</html>')));
    await expect(client.health()).rejects.toMatchObject({ code: 'invalid_response' });
  });
  it('rejects a malformed topology', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(respond({ ...network, transformers: [{ id: 'T1' }] })));
    await expect(client.network()).rejects.toMatchObject({ code: 'invalid_response' });
  });
  it('rejects sites associated with an unknown transformer', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(respond({ ...network, sites: [{ ...network.sites[0], transformer_id: 'unknown' }] })));
    await expect(client.network()).rejects.toMatchObject({ code: 'invalid_response' });
  });
  it('rejects non-finite values returned in JSON', async () => {
    const body = JSON.stringify(network).replace('"rated_kva":250', '"rated_kva":1e999');
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(new Response(body)));
    await expect(client.network()).rejects.toMatchObject({ code: 'invalid_response' });
  });
  it('rejects simulation series with missing steps', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockResolvedValue(respond({ ...simulation, series: { ...simulation.series, voltage_pu: [1] } })));
    await expect(client.simulate({ ev_kw: 50, pv_kwp: 30, day_type: 'summer_weekday', load_level: 'heavy' })).rejects.toMatchObject({ code: 'invalid_response' });
  });
  it('reports network/CORS failures without fallback values', async () => {
    const client = new ApiClient('/api', 1000, vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(client.health()).rejects.toMatchObject({ code: 'network_error' });
  });
  it('aborts a request at its timeout', async () => {
    vi.useFakeTimers();
    const transport: typeof fetch = (_input, init) => new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
    const promise = expect(new ApiClient('/api', 100, transport).health()).rejects.toMatchObject({ code: 'timeout' });
    await vi.advanceTimersByTimeAsync(100);
    await promise;
  });
  it('supports cancellation separately from timeout', async () => {
    const controller = new AbortController();
    const transport: typeof fetch = (_input, init) => new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
    const promise = expect(new ApiClient('/api', 1000, transport).health(controller.signal)).rejects.toMatchObject({ code: 'cancelled' });
    controller.abort(); await promise;
  });
  it.each(['', '//untrusted.example', 'javascript:alert(1)', 'https://user:password@api.example', '/api?key=x'])('rejects unsafe base %s', base => {
    expect(() => normalizeBaseUrl(base)).toThrow(ApiError);
  });
  it('rejects an invalid timeout', () => { expect(() => new ApiClient('/api', 0)).toThrow(ApiError); });
});

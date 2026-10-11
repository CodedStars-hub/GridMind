import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { isReplay, isDispatch } from '../api/telemetryGuards';
import { DataProvider } from '../app/DataProvider';
import { DispatchMonitor } from '../components/DispatchMonitor';
import replay from './fixtures/telemetry-replay.json';
import decision from './fixtures/dispatch-decision.json';
import network from './fixtures/network.json';
const scenario = { ev_kw: 100 as const, pv_kwp: 0 as const, day_type: 'summer_weekday' as const, load_level: 'critical' as const, bess_override: { power_kw: 100, energy_kwh: 500, initial_soc_pct: 80 } };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function setup(fail = false) {
  const transport = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const path = String(input);
    if (path.endsWith('/health')) return response({ status: 'ok', api_version: 'v2', engine_version: '0.1.0' });
    if (path.endsWith('/network')) return response(network);
    if (fail) return response({ error: { code: 'not_found', message: 'route not found', field: null } }, 404);
    return response(path.endsWith('/telemetry/replay') ? replay : { ...decision, telemetry_timestamp: JSON.parse(String(init?.body)).telemetry.timestamp });
  });
  render(<DataProvider client={new ApiClient('/api', 1000, transport)}><DispatchMonitor scenario={scenario} /></DataProvider>);
  return transport;
}
it('accepts locally generated contract fixtures and rejects malformed or non-simulated data', () => {
  expect(isReplay(replay)).toBe(true); expect(isDispatch(decision)).toBe(true);
  expect(isReplay({ ...replay, records: [] })).toBe(false);
  expect(isDispatch({ ...decision, published: true })).toBe(false);
  expect(isReplay({ ...replay, simulated: false })).toBe(false);
});
it('loads a simulated replay then displays real telemetry, advisory action and progress', async () => {
  const transport = setup();
  expect(screen.getByRole('button', { name: 'Load simulated replay' }).hasAttribute('disabled')).toBe(true);
  fireEvent.change(screen.getByLabelText('Replay start (UTC ISO timestamp)'), { target: { value: '2026-01-01T00:00:00Z' } });
  fireEvent.click(screen.getByRole('button', { name: 'Load simulated replay' }));
  expect(await screen.findByText('Replay progress: 0 / 96 samples evaluated')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Evaluate next sample' }));
  expect(await screen.findByText(`Advisory action: ${decision.action === 'idle' ? 'Idle' : decision.action === 'charge' ? 'Charge' : 'Discharge'}`)).toBeTruthy();
  expect(screen.getByText('Replay progress: 1 / 96 samples evaluated')).toBeTruthy();
  expect(screen.getByText(replay.records[0]!.timestamp)).toBeTruthy();
  expect(screen.getByText(/Published: No/)).toBeTruthy();
  const request = transport.mock.calls.find(([path]) => String(path).endsWith('/dispatch/evaluate'))!;
  expect(JSON.parse(String(request[1]?.body))).toEqual({ telemetry: replay.records[0], now: replay.records[0]!.timestamp, previous_timestamp: null, battery: replay.battery });
});
it('passes the prior timestamp on the next successful step', async () => {
  const transport = setup();
  fireEvent.change(screen.getByLabelText('Replay start (UTC ISO timestamp)'), { target: { value: '2026-01-01T00:00:00Z' } });
  fireEvent.click(screen.getByRole('button', { name: 'Load simulated replay' }));
  await screen.findByRole('button', { name: 'Evaluate next sample' });
  fireEvent.click(screen.getByRole('button', { name: 'Evaluate next sample' }));
  await screen.findByText('Replay progress: 1 / 96 samples evaluated');
  fireEvent.click(screen.getByRole('button', { name: 'Evaluate next sample' }));
  await screen.findByText('Replay progress: 2 / 96 samples evaluated');
  const calls = transport.mock.calls.filter(([path]) => String(path).endsWith('/dispatch/evaluate'));
  expect(JSON.parse(String(calls[1]![1]?.body)).previous_timestamp).toBe(replay.records[0]!.timestamp);
});
it('reports unavailable endpoints without fabricated telemetry or decisions', async () => {
  setup(true);
  fireEvent.change(screen.getByLabelText('Replay start (UTC ISO timestamp)'), { target: { value: '2026-01-01T00:00:00Z' } });
  fireEvent.click(screen.getByRole('button', { name: 'Load simulated replay' }));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.queryByRole('progressbar')).toBeNull();
  expect(screen.queryByText(/Advisory action/)).toBeNull();
});
it('withholds decisions while replay loading and supports cancellation', async () => {
  let signal: AbortSignal | null = null;
  const transport = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    if (String(input).endsWith('/health')) return response({ status: 'ok', api_version: 'v2', engine_version: '0.1.0' });
    if (String(input).endsWith('/network')) return response(network);
    signal = init!.signal!;
    return new Promise((_resolve, reject) => signal!.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
  });
  const view = render(<DataProvider client={new ApiClient('/api', 1000, transport)}><DispatchMonitor scenario={scenario} /></DataProvider>);
  fireEvent.change(screen.getByLabelText('Replay start (UTC ISO timestamp)'), { target: { value: '2026-01-01T00:00:00Z' } });
  fireEvent.click(screen.getByRole('button', { name: 'Load simulated replay' }));
  expect(screen.getByRole('button', { name: 'Processing replay…' }).hasAttribute('disabled')).toBe(true);
  expect(screen.queryByText(/Advisory action/)).toBeNull();
  view.unmount();
  await waitFor(() => expect(signal?.aborted).toBe(true));
});

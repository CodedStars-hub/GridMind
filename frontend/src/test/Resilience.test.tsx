import { afterEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ApiClient } from '../api/client';
import { exactSnapshot, isSnapshot } from '../utils/precomputed';
import { PrecomputedFallback } from '../components/PrecomputedFallback';
import snapshot from '../../public/precomputed/scenarios.json';
const health = { status: 'ok', api_version: 'v2', engine_version: '0.1.0' };
const response = (body: unknown, status = 200, retry = '0') => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', 'Retry-After': retry } });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it('validates snapshots and requires exact inputs and complete model identity', () => {
  expect(isSnapshot(snapshot)).toBe(true);
  if (!isSnapshot(snapshot)) throw new Error('invalid fixture');
  const item = snapshot.artifacts[0]!;
  expect(exactSnapshot(snapshot, item.inputs, snapshot.engine_version, snapshot.model_sha256)).toEqual(item.result);
  expect(exactSnapshot(snapshot, { ...item.inputs, ev_kw: 10 }, snapshot.engine_version, snapshot.model_sha256)).toBeNull();
  expect(exactSnapshot(snapshot, { ...item.inputs, bess: 'auto' }, snapshot.engine_version, snapshot.model_sha256)).toBeNull();
  expect(exactSnapshot(snapshot, item.inputs, 'different', snapshot.model_sha256)).toBeNull();
  expect(exactSnapshot(snapshot, item.inputs, snapshot.engine_version, 'different')).toBeNull();
  expect(isSnapshot({ ...snapshot, artifacts: [{ ...item, result: {} }] })).toBe(false);
});
it.each([429, 500, 503])('retries a metadata GET once after HTTP %i', async status => {
  const transport = vi.fn<typeof fetch>().mockResolvedValueOnce(response({}, status)).mockResolvedValueOnce(response(health));
  expect(await new ApiClient('/api', 1000, transport).health()).toEqual(health);
  expect(transport).toHaveBeenCalledTimes(2);
});
it('never retries simulation submissions or exceeds the GET retry bound', async () => {
  const transport = vi.fn<typeof fetch>().mockImplementation(async () => response({}, 503));
  const client = new ApiClient('/api', 1000, transport);
  await expect(client.health()).rejects.toMatchObject({ status: 503 });
  expect(transport).toHaveBeenCalledTimes(2);
  transport.mockClear();
  await expect(client.simulate({ ev_kw: 50, pv_kwp: 30, day_type: 'summer_weekday', load_level: 'heavy' })).rejects.toMatchObject({ status: 503 });
  expect(transport).toHaveBeenCalledTimes(1);
});
it('does not shorten a long Retry-After or retry after cancellation', async () => {
  const transport = vi.fn<typeof fetch>().mockResolvedValue(response({}, 429, '30'));
  await expect(new ApiClient('/api', 1000, transport).health()).rejects.toMatchObject({ status: 429 });
  expect(transport).toHaveBeenCalledTimes(1);
  transport.mockClear(); transport.mockResolvedValue(response({}, 429, '1'));
  const controller = new AbortController();
  const pending = new ApiClient('/api', 2000, transport).health(controller.signal);
  await Promise.resolve(); controller.abort();
  await expect(pending).rejects.toMatchObject({ code: 'cancelled' });
  expect(transport).toHaveBeenCalledTimes(1);
});
it('bounds retry waiting with the original total timeout', async () => {
  const transport = vi.fn<typeof fetch>().mockResolvedValue(response({}, 429, '1'));
  await expect(new ApiClient('/api', 10, transport).health()).rejects.toMatchObject({ code: 'timeout' });
  expect(transport).toHaveBeenCalledTimes(1);
});
it('requires an explicit user choice and labels snapshots honestly', async () => {
  const transport = vi.fn<typeof fetch>().mockResolvedValue(response(snapshot)); vi.stubGlobal('fetch', transport);
  const inspect = vi.fn(); render(<PrecomputedFallback onInspect={inspect} />);
  expect(transport).not.toHaveBeenCalled(); expect(inspect).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Inspect available precomputed scenarios' }));
  await waitFor(() => expect(screen.getAllByRole('button', { name: /View precomputed:/ })).toHaveLength(3));
  expect(screen.getByText(/equivalence is not claimed/)).not.toBeNull();
  expect(inspect).not.toHaveBeenCalled();
  fireEvent.click(screen.getAllByRole('button', { name: /View precomputed:/ })[0]!);
  expect(inspect).toHaveBeenCalledTimes(1);
});

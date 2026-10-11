import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { isSimulation } from '../api/guards';
import { DataProvider } from '../app/DataProvider';
import { Assessment } from '../pages/Assessment';
import battery from './fixtures/battery-simulation.json';
import scenarios from './fixtures/scenarios.json';
import network from './fixtures/network.json';
import simulation from './fixtures/simulation.json';

it('validates an actual locally generated battery response and rejects inconsistent missing series', () => {
  expect(isSimulation(battery)).toBe(true);
  expect(isSimulation({ ...battery, series: { ...battery.series, bess_kw: null } })).toBe(false);
  expect(isSimulation(simulation)).toBe(true);
});
it('submits optional BESS configuration and renders real SOC and dispatch charts', async () => {
  const transport = vi.fn<typeof fetch>().mockImplementation(async input => new Response(JSON.stringify(String(input).endsWith('/scenarios') ? scenarios : String(input).endsWith('/health') ? { status: 'ok', api_version: 'v2', engine_version: '0.1.0' } : String(input).endsWith('/network') ? network : battery)));
  render(<DataProvider client={new ApiClient('/api', 1000, transport)}><Assessment /></DataProvider>);
  await screen.findByLabelText('EV hub rating');
  fireEvent.change(screen.getByLabelText('EV hub rating'), { target: { value: '100' } });
  fireEvent.change(screen.getByLabelText('Installed solar'), { target: { value: '0' } });
  fireEvent.change(screen.getByLabelText('Existing load'), { target: { value: 'critical' } });
  fireEvent.click(screen.getByLabelText('Enable battery storage'));
  fireEvent.change(screen.getByLabelText('Battery energy capacity (kWh)'), { target: { value: '500' } });
  fireEvent.change(screen.getByLabelText('Battery power limit (kW)'), { target: { value: '100' } });
  fireEvent.change(screen.getByLabelText('Initial SOC (%)'), { target: { value: '80' } });
  fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  expect(await screen.findByText('Battery state of charge (%)')).toBeTruthy();
  expect(screen.getByText('Battery dispatch (+ discharge / − charge) (kW)')).toBeTruthy();
  expect(screen.getAllByRole('img')).toHaveLength(5);
  const request = transport.mock.calls.find(([path]) => String(path).endsWith('/simulate'))!;
  expect(JSON.parse(String(request[1]?.body)).bess_override).toEqual({ power_kw: 100, energy_kwh: 500, initial_soc_pct: 80 });
});
it('a disabled battery sends the original request without any override', async () => {
  const transport = vi.fn<typeof fetch>().mockImplementation(async input => new Response(JSON.stringify(String(input).endsWith('/scenarios') ? scenarios : String(input).endsWith('/health') ? { status: 'ok', api_version: 'v2', engine_version: '0.1.0' } : String(input).endsWith('/network') ? network : simulation)));
  render(<DataProvider client={new ApiClient('/api', 1000, transport)}><Assessment /></DataProvider>);
  await screen.findByLabelText('EV hub rating');
  fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  await screen.findByRole('button', { name: 'Use as comparison A' });
  const request = transport.mock.calls.find(([path]) => String(path).endsWith('/simulate'))!;
  expect(JSON.parse(String(request[1]?.body))).toEqual({ ev_kw: 50, pv_kwp: 30, day_type: 'summer_weekday', load_level: 'heavy' });
  expect(screen.getAllByRole('img')).toHaveLength(3);
});

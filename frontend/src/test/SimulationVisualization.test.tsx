import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { SimulationCharts } from '../components/SimulationCharts';
import { ScenarioComparison } from '../components/ScenarioComparison';
import { chartGeometry, compareResults, compatibleResults, thresholdsFor, violates } from '../utils/simulationAnalysis';
import { Assessment } from '../pages/Assessment';
import { DataProvider } from '../app/DataProvider';
import { ApiClient } from '../api/client';
import type { SimulationResult } from '../types/api';
import simulation from './fixtures/simulation.json';
import scenarios from './fixtures/scenarios.json';
import network from './fixtures/network.json';
const result = simulation as SimulationResult;
const changed = () => ({ ...structuredClone(result), meta: { ...result.meta, inputs: { ...result.meta.inputs, ev_kw: 100 as const } }, summary: { ...result.summary, min_voltage_pu: 0.94, peak_loading_pct: 108.9428, peak_hotspot_c: 114.1997 } });

it('plots returned voltage, loading and hot-spot arrays with labelled units', () => {
  render(<SimulationCharts result={result} assumptions={scenarios.assumptions} />);
  expect(screen.getAllByRole('img')).toHaveLength(3);
  expect(screen.getByText('Connection-point voltage (p.u.)')).toBeTruthy();
  expect(screen.getByText('Transformer loading (% rated current)')).toBeTruthy();
  expect(screen.getByText('Hot-spot temperature (°C)')).toBeTruthy();
  expect(document.querySelectorAll('.chart-series')).toHaveLength(3);
  expect(document.querySelectorAll('.chart-limit')).toHaveLength(5);
});
it('uses the exact selected returned sample through an accessible time control', () => {
  render(<SimulationCharts result={result} assumptions={scenarios.assumptions} />);
  const slider = screen.getByRole('slider');
  fireEvent.change(slider, { target: { value: '84' } });
  expect(slider.getAttribute('aria-valuetext')).toBe('21:00');
  expect(screen.getByText('21:00 · Current: 0.9499 p.u. · Outside configured limit')).toBeTruthy();
  expect(screen.getByText(`21:00 · Current: ${result.series.hotspot_c[84]} °C`)).toBeTruthy();
  expect(screen.getByRole('slider').getAttribute('max')).toBe('95');
});
it('pointer inspection updates the shared sample without inventing interpolated readings', () => {
  render(<SimulationCharts result={result} assumptions={[]} />);
  const svg = screen.getAllByRole('img')[0]!;
  vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({ left: 0, width: 740 } as DOMRect);
  fireEvent.pointerMove(svg, { clientX: 700 });
  // jsdom does not provide PointerEvent coordinates; use the browser-compatible event properties.
  const event = new Event('pointermove', { bubbles: true }); Object.defineProperty(event, 'clientX', { value: 700 }); fireEvent(svg, event);
  expect(screen.getByRole('slider').getAttribute('aria-valuetext')).toBe('23:45');
});
it('reads thresholds by exact config key and uses strict comparisons', () => {
  const limits = thresholdsFor('voltage_pu', [{ name: 'voltage_min_pu', value: 0.93, unit: 'p.u.', note: 'test limit' }]);
  expect(limits).toEqual([{ label: 'Minimum voltage', value: 0.93, direction: 'below' }]);
  expect(violates(0.93, limits)).toBe(false);
  expect(violates(0.9299, limits)).toBe(true);
  expect(violates(100, [{ label: 'Loading', value: 100, direction: 'above' }])).toBe(false);
  expect(violates(100.01, [{ label: 'Loading', value: 100, direction: 'above' }])).toBe(true);
});
it('never substitutes missing/TBD limits and honestly handles absent or invalid results', () => {
  expect(thresholdsFor('hotspot_c', [{ name: 'hotspot_warning_c', value: null, unit: 'degC', note: 'TBD' }])).toEqual([]);
  const view = render(<SimulationCharts result={null} assumptions={[]} />);
  expect(screen.getByText('No chart data')).toBeTruthy();
  view.rerender(<SimulationCharts result={{ ...result, series: { ...result.series, voltage_pu: [] } }} assumptions={[]} />);
  expect(screen.getByRole('alert').textContent).toContain('invalid');
  expect(screen.queryByRole('img')).toBeNull();
  view.rerender(<SimulationCharts result={result} assumptions={[]} />);
  expect(screen.getAllByText('Thresholds unavailable from the API; no limit values assumed.')).toHaveLength(3);
});
it('plot transformation preserves sample ordering and rejects non-finite/misaligned inputs', () => {
  const geometry = chartGeometry([1, 2, 3], []);
  expect(geometry.x(0)).toBe(60); expect(geometry.x(2)).toBe(700); expect(geometry.y(2)).toBeCloseTo(120);
  expect(geometry.points([1, 2, 3]).split(' ')).toHaveLength(3);
  expect(() => chartGeometry([], [])).toThrow();
  expect(() => chartGeometry([NaN], [])).toThrow();
  expect(() => chartGeometry([1, 2], [], [1])).toThrow();
});
it('comparison preserves signed differences and does not present loading differences as relative percentages', () => {
  const b = changed();
  const rows = compareResults(result, b);
  expect(rows.find(r => r.key === 'peak_loading_pct')!.difference).toBeCloseTo(10);
  expect(rows.find(r => r.key === 'peak_hotspot_c')!.difference).toBeCloseTo(10);
  expect(rows.find(r => r.key === 'min_voltage_pu')!.difference).toBeCloseTo(-0.0099);
  render(<ScenarioComparison a={result} b={b} />);
  expect(screen.getByText('+10 percentage points')).toBeTruthy();
  expect(screen.getByText('-0.0099 p.u.')).toBeTruthy();
  expect(screen.getByText('Unchanged')).toBeTruthy();
});
it('overlay compares aligned outputs and rejects engine/time incompatibility', () => {
  const b = changed();
  render(<SimulationCharts result={b} reference={result} assumptions={scenarios.assumptions} />);
  expect(document.querySelectorAll('.chart-reference')).toHaveLength(3);
  expect(compatibleResults(result, { ...b, meta: { ...b.meta, engine_version: 'different' } })).toBe(false);
  expect(compatibleResults(result, { ...b, series: { ...b.series, time: [...b.series.time].reverse() } })).toBe(false);
  expect(() => compareResults(result, { ...b, meta: { ...b.meta, engine_version: 'different' } })).toThrow();
});

function assessmentSetup() {
  let fail = false;
  let held: ((value: Response) => void) | null = null;
  let hold = false;
  let runs = 0;
  const transport = vi.fn<typeof fetch>().mockImplementation(async input => {
    const path = String(input);
    const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path.endsWith('/health')) return response({ status: 'ok', api_version: 'v2', engine_version: '0.1.0' });
    if (path.endsWith('/network')) return response(network);
    if (path.endsWith('/scenarios')) return response(scenarios);
    if (hold) return new Promise<Response>(resolve => { held = resolve; });
    if (fail) return response({ error: { code: 'internal_error', message: 'internal error', field: null } }, 500);
    runs++; return response(runs === 1 ? result : changed());
  });
  render(<DataProvider client={new ApiClient('/api', 1000, transport)}><Assessment /></DataProvider>);
  return { fail: () => { fail = true; }, hold: () => { hold = true; }, finish: () => held?.(new Response(JSON.stringify(changed()))) };
}
it('pins only successful results and compares two completed runs, clearing comparison on demand', async () => {
  assessmentSetup(); await screen.findByLabelText('EV hub rating');
  expect(screen.queryByRole('img')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  await screen.findByRole('button', { name: 'Use as comparison A' });
  fireEvent.click(screen.getByRole('button', { name: 'Use as comparison A' }));
  fireEvent.change(screen.getByLabelText('EV hub rating'), { target: { value: '100' } });
  fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  const comparison = await screen.findByRole('region', { name: 'Scenario comparison' });
  expect(within(comparison).getByText('+10 percentage points')).toBeTruthy();
  expect(document.querySelectorAll('.chart-reference')).toHaveLength(3);
  fireEvent.click(screen.getByRole('button', { name: 'Clear comparison A' }));
  expect(screen.queryByRole('region', { name: 'Scenario comparison' })).toBeNull();
  expect(document.querySelectorAll('.chart-reference')).toHaveLength(0);
});
it('failed second execution retains clearly pinned A but never invents B or charts', async () => {
  const controls = assessmentSetup(); await screen.findByLabelText('EV hub rating');
  fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Use as comparison A' }));
  controls.fail(); fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  await screen.findByRole('alert');
  expect(screen.getByText(/A · pinned successful scenario/)).toBeTruthy();
  expect(screen.queryByRole('img')).toBeNull();
  expect(screen.queryByRole('region', { name: 'Scenario comparison' })).toBeNull();
});
it('pending execution disables inputs and withholds charts until the response succeeds', async () => {
  const controls = assessmentSetup(); await screen.findByLabelText('EV hub rating'); controls.hold();
  fireEvent.click(screen.getByRole('button', { name: /Run simulation/ }));
  expect((screen.getByRole('button', { name: /Running simulation/ }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('img')).toBeNull(); controls.finish();
  await waitFor(() => expect(screen.getAllByRole('img')).toHaveLength(3));
});
it('discloses all actual samples in an accessible table', () => {
  render(<SimulationCharts result={result} assumptions={[]} />);
  const details = document.querySelector('details')!;
  details.open = true; fireEvent(details, new Event('toggle', { bubbles: true }));
  const table = screen.getByRole('table', { name: 'Current simulation · 96 samples, end-of-step temperatures' });
  expect(within(table).getAllByRole('row')).toHaveLength(97);
  const peak = within(table).getByRole('rowheader', { name: '21:00' }).closest('tr')!;
  expect(within(peak).getByText('0.9499')).toBeTruthy();
});
it('renders incompatible or malformed comparisons honestly without throwing', () => {
  const view = render(<ScenarioComparison a={result} b={{ ...result, meta: { ...result.meta, engine_version: 'other' } }} />);
  expect(screen.getByRole('alert').textContent).toContain('engine versions');
  view.rerender(<ScenarioComparison a={result} b={{ ...result, series: { ...result.series, loading_pct: [] } }} />);
  expect(screen.getByRole('alert').textContent).toContain('invalid');
});

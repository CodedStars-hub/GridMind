import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { isPlan } from '../api/planningGuard';
import { DataProvider } from '../app/DataProvider';
import { Overview } from '../pages/Overview';
import { Planning } from '../pages/Planning';
import network from './fixtures/network.json';
import plan from './fixtures/plan.json';
const respond = (body: unknown, status=200) => new Response(JSON.stringify(body), {status,headers:{'Content-Type':'application/json'}});
function client(planStatus=200, body: unknown=plan) {
  return new ApiClient('/api',2000,vi.fn<typeof fetch>().mockImplementation(async path => String(path).endsWith('/health') ? respond({status:'ok',api_version:'v2',engine_version:'0.1.0'}) : String(path).endsWith('/network') ? respond(network) : respond(body,planStatus)));
}
it('explains the product and uses actual assets without invented operating risk', async () => {
  render(<DataProvider client={client()}><Overview /></DataProvider>);
  expect(screen.getByRole('heading',{level:1}).textContent).toContain('More charging.');
  expect(screen.getByRole('link',{name:/Run a simulation/}).getAttribute('href')).toBe('#/assessment');
  expect(screen.getByRole('link',{name:'Explore Network'}).getAttribute('href')).toBe('#/network');
  await screen.findByText(network.neighbourhood.name);
  expect(screen.getAllByRole('link',{name:/Explore T\d:/})).toHaveLength(network.transformers.length);
  expect(screen.getByText(/no physical feeder topology/)).toBeTruthy();
  expect(screen.queryByText('0.9499')).toBeNull();
});
it('accepts a real-engine planning display projection and rejects malformed fields', () => {
  expect(isPlan(plan)).toBe(true);
  expect(isPlan({...plan,plan:{...plan.plan,cost:{...plan.plan.cost,total_inr:NaN}}})).toBe(false);
  expect(isPlan({...plan,planning:{...plan.planning,sites:[{...plan.planning.sites[0],allocated_kw:-1}]}})).toBe(false);
  expect(isPlan({...plan,before_after:{...plan.before_after,feasibility:{}}})).toBe(false);
});
it('runs the supported planning endpoint and renders actual recommendations and comparisons', async () => {
  render(<DataProvider client={client()}><Planning /></DataProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'150 kW'}));
  fireEvent.click(screen.getByRole('button',{name:'Generate placement plan'}));
  expect(await screen.findByText('150 kW allocated')).toBeTruthy();
  expect(screen.getByText('Existing network constraints still need attention.')).toBeTruthy();
  expect(screen.getAllByText(plan.planning.sites[0]!.name)).toHaveLength(1);
  expect(screen.getByRole('table',{name:'Transformer before and after electrical comparison'})).toBeTruthy();
  expect(screen.getByText(plan.planning.sites[0]!.reason)).toBeTruthy();
});
it('never invents allocations on API failure', async () => {
  render(<DataProvider client={client(503,{error:{code:'internal_error',message:'Service temporarily unavailable',field:null}})}><Planning /></DataProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'Generate placement plan'}));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.queryByText('Where charging is recommended')).toBeNull();
});
it('rejects a plan belonging to a different target rather than displaying it', async () => {
  render(<DataProvider client={client()}><Planning /></DataProvider>);
  fireEvent.click(await screen.findByRole('button',{name:'Generate placement plan'}));
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('does not match'));
});

it('posts only the configured target through the existing API client', async () => {
  const transport=vi.fn<typeof fetch>().mockResolvedValue(respond(plan));
  expect(await new ApiClient('/api',2000,transport).plan({target_kw:150})).toEqual(plan);
  expect(transport.mock.calls[0]?.[0]).toBe('/api/v2/plan');
  expect(JSON.parse(String(transport.mock.calls[0]?.[1]?.body))).toEqual({target_kw:150});
  expect(transport.mock.calls[0]?.[1]?.credentials).toBe('omit');
});

it('opens the transformer selected through an overview deep link', async () => {
  const { Network } = await import('../pages/Network');
  window.location.hash='#/network?transformer=T4';
  render(<DataProvider client={client()}><Network /></DataProvider>);
  expect((await screen.findByRole('button',{name:/Inspect transformer T4:/})).getAttribute('aria-pressed')).toBe('true');
  expect(screen.getByRole('heading',{level:3}).textContent).toBe(network.transformers.find(t=>t.id==='T4')!.name);
});
it('keeps precomputed snapshots out of live comparisons and advisory controls', async () => {
  const { Assessment } = await import('../pages/Assessment');
  const scenarios = (await import('./fixtures/scenarios.json')).default;
  const snapshot = (await import('../../public/precomputed/scenarios.json')).default;
  const transport = vi.fn<typeof fetch>().mockImplementation(async path => String(path).endsWith('/scenarios') ? respond(scenarios) : String(path).endsWith('/health') ? respond({status:'ok',api_version:'v2',engine_version:'0.1.0'}) : respond(network));
  const fetchSnapshot=vi.spyOn(globalThis,'fetch').mockResolvedValue(respond(snapshot));
  try {
    render(<DataProvider client={new ApiClient('/api',2000,transport)}><Assessment /></DataProvider>);
    fireEvent.click(screen.getByRole('button',{name:'Inspect available precomputed scenarios'}));
    fireEvent.click((await screen.findAllByRole('button',{name:/View precomputed:/}))[0]!);
    expect(screen.getByText('Precomputed snapshot — not live.')).toBeTruthy();
    expect(screen.queryByRole('button',{name:'Use as comparison A'})).toBeNull();
    expect(screen.queryByText('Dispatch Monitoring')).toBeNull();
  } finally { fetchSnapshot.mockRestore(); }
});

import { useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { NetworkExplorer, type Selection } from '../components/NetworkExplorer';
import { DataProvider, useData } from '../app/DataProvider';
import { ApiClient } from '../api/client';
import { Network } from '../pages/Network';
import type { NetworkResponse } from '../types/api';
import fixture from './fixtures/network.json';

const network = fixture as NetworkResponse;
function Explorer({ data = network }: { data?: NetworkResponse }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  return <NetworkExplorer network={data} selection={selection} onSelectionChange={setSelection} />;
}
const transformerButton = (id: string) => screen.getByRole('button', { name: new RegExp(`^Inspect transformer ${id}:`) });
const siteButton = (id: string) => screen.getByRole('button', { name: new RegExp(`^Inspect site ${id}:`) });
const details = () => screen.getByRole('region', { name: screen.getByRole('heading', { level: 3 }).textContent ?? '' });
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function RefreshControl() { const { refresh } = useData(); return <button onClick={refresh}>Refresh inventory</button>; }

describe('API-backed network explorer', () => {
  it('renders every actual transformer and site with first-transformer selection', () => {
    render(<Explorer />);
    expect(screen.getAllByRole('button', { name: /^Inspect transformer/ })).toHaveLength(network.transformers.length);
    expect(screen.getAllByRole('button', { name: /^Inspect site S/ })).toHaveLength(network.sites.length);
    expect(transformerButton('T1').getAttribute('aria-pressed')).toBe('true');
    expect(within(details()).getByText(network.transformers[0]!.name)).toBeTruthy();
    expect(within(details()).getByText('250 kVA')).toBeTruthy();
  });
  it('updates details and highlight when another transformer is selected', () => {
    render(<Explorer />);
    fireEvent.click(transformerButton('T3'));
    expect(transformerButton('T1').getAttribute('aria-pressed')).toBe('false');
    expect(transformerButton('T3').getAttribute('aria-pressed')).toBe('true');
    expect(within(details()).getByRole('heading', { level: 3 }).textContent).toBe('Central Market');
    expect(within(details()).getByText('Commercial')).toBeTruthy();
    expect(within(details()).getByText('90')).toBeTruthy();
    expect(within(details()).getAllByRole('button', { name: /^Inspect S/ })).toHaveLength(2);
  });
  it('shows site ceiling, footfall and the real associated transformer', () => {
    render(<Explorer />);
    fireEvent.click(siteButton('S4'));
    expect(siteButton('S4').getAttribute('aria-pressed')).toBe('true');
    expect(within(details()).getByRole('heading', { level: 3 }).textContent).toBe('Hospital Visitor Parking');
    expect(within(details()).getAllByText('T5')).toHaveLength(2);
    expect(within(details()).getByText('60 kW')).toBeTruthy();
    expect(within(details()).getByText('8')).toBeTruthy();
    expect(screen.getByRole('region', { name: 'T5 infrastructure' }).className).toContain('selected');
  });
  it('allows inspection from the transformer associated-site list', () => {
    render(<Explorer />);
    fireEvent.click(within(details()).getByRole('button', { name: /Inspect S6/ }));
    expect(siteButton('S6').getAttribute('aria-pressed')).toBe('true');
    expect(within(details()).getByRole('heading', { level: 3 }).textContent).toBe('Block A Clubhouse');
  });
  it('uses native focusable buttons and supports keyboard-generated activation', () => {
    render(<Explorer />);
    const button = transformerButton('T2');
    expect(button.tagName).toBe('BUTTON');
    expect(button.tabIndex).toBe(0);
    button.focus(); expect(document.activeElement).toBe(button);
    // Native Enter/Space activation emits a click without pointer coordinates.
    fireEvent.click(button, { detail: 0 });
    expect(button.getAttribute('aria-pressed')).toBe('true');
    expect(within(details()).getByRole('heading', { level: 3 }).textContent).toBe('Residential Block B');
  });
  it('does not draw fictional electrical topology or geography', () => {
    const { container } = render(<Explorer />);
    expect(screen.getByText(/electrical topology unavailable/)).toBeTruthy();
    expect(screen.getByText(/not feeder routes or geographic distances/)).toBeTruthy();
    expect(container.querySelector('svg')).toBeNull();
  });
  it('provides honest navigation without claiming equipment is preselected', () => {
    render(<Explorer />);
    expect(within(details()).getByRole('link', { name: 'Open assessment' }).getAttribute('href')).toBe('#/assessment');
    expect(within(details()).getByRole('link', { name: /Open planning workspace/ }).getAttribute('href')).toBe('#/planning');
    expect(within(details()).getByText(/do not transfer the selected equipment/)).toBeTruthy();
  });
  it('handles empty inventory and absent charging sites', () => {
    const { rerender } = render(<Explorer data={{ ...network, transformers: [], sites: [] }} />);
    expect(screen.getByText('No transformers configured')).toBeTruthy();
    expect(screen.queryByRole('heading', { level: 3 })).toBeNull();
    rerender(<Explorer data={{ ...network, sites: [] }} />);
    expect(screen.queryByRole('button', { name: /^Inspect site/ })).toBeNull();
    expect(within(details()).getByText('No candidate sites configured.')).toBeTruthy();
  });
  it('preserves selected ID and displays refreshed metadata rather than stale objects', () => {
    const { rerender } = render(<Explorer />);
    fireEvent.click(transformerButton('T2'));
    const updated = { ...network, transformers: network.transformers.map(t => t.id === 'T2' ? { ...t, connections: 141 } : t) };
    rerender(<Explorer data={updated} />);
    expect(transformerButton('T2').getAttribute('aria-pressed')).toBe('true');
    expect(within(details()).getByText('141')).toBeTruthy();
    expect(within(details()).queryByText('140')).toBeNull();
  });
  it('falls back when a selected transformer disappears and does not reselect it when re-added', async () => {
    const { rerender } = render(<Explorer />);
    fireEvent.click(transformerButton('T2'));
    rerender(<Explorer data={{ ...network, transformers: network.transformers.filter(t => t.id !== 'T2'), sites: network.sites.filter(s => s.transformer_id !== 'T2') }} />);
    await waitFor(() => expect(transformerButton('T1').getAttribute('aria-pressed')).toBe('true'));
    rerender(<Explorer />);
    expect(transformerButton('T1').getAttribute('aria-pressed')).toBe('true');
  });
  it('resets a removed site selection and accepts an empty refresh', () => {
    const { rerender } = render(<Explorer />);
    fireEvent.click(siteButton('S4'));
    rerender(<Explorer data={{ ...network, sites: network.sites.filter(s => s.id !== 'S4') }} />);
    expect(transformerButton('T1').getAttribute('aria-pressed')).toBe('true');
    rerender(<Explorer data={{ ...network, transformers: [], sites: [] }} />);
    expect(screen.getByText('No transformers configured')).toBeTruthy();
  });
  it('uses the shared provider, hides stale details during refresh and retains valid selection', async () => {
    const transport = vi.fn<typeof fetch>().mockImplementation(async input => response(String(input).endsWith('/health') ? { status: 'ok', api_version: 'v2', engine_version: '0.1.0' } : network));
    render(<DataProvider client={new ApiClient('/api', 1000, transport)}><RefreshControl /><Network /></DataProvider>);
    expect(screen.getByText('Loading from the API…')).toBeTruthy();
    await screen.findByRole('button', { name: /^Inspect transformer T2:/ });
    fireEvent.click(transformerButton('T2'));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh inventory' }));
    expect(screen.queryByRole('heading', { level: 3 })).toBeNull();
    await screen.findByRole('button', { name: /^Inspect transformer T2:/ });
    expect(transformerButton('T2').getAttribute('aria-pressed')).toBe('true');
    expect(transport.mock.calls.filter(([input]) => String(input).endsWith('/network'))).toHaveLength(2);
  });
  it('shows API errors without stale inventory and retries through the shared provider', async () => {
    let fail = true;
    const transport = vi.fn<typeof fetch>().mockImplementation(async input => {
      if (String(input).endsWith('/health')) return response({ status: 'ok', api_version: 'v2', engine_version: '0.1.0' });
      return fail ? response({ error: { code: 'internal_error', message: 'internal error', field: null } }, 500) : response(network);
    });
    render(<DataProvider client={new ApiClient('/api', 1000, transport)}><Network /></DataProvider>);
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.queryByRole('heading', { level: 3 })).toBeNull();
    fail = false; fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('button', { name: /^Inspect transformer T1:/ })).toBeTruthy();
  });
});

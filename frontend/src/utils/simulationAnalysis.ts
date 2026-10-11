import type { Assumption, SimulationResult, SimulationSummary } from '../types/api';

export type ChartKey = 'voltage_pu' | 'loading_pct' | 'hotspot_c' | 'bess_kw' | 'bess_soc_pct';
export interface Threshold { label: string; value: number; direction: 'below' | 'above' }
const definitions: Record<ChartKey, [string, string, Threshold['direction']][]> = {
  bess_kw: [],
  bess_soc_pct: [['soc_min_pct', 'Minimum SOC', 'below'], ['soc_max_pct', 'Maximum SOC', 'above']],
  voltage_pu: [['voltage_min_pu', 'Minimum voltage', 'below'], ['voltage_max_pu', 'Maximum voltage', 'above']],
  loading_pct: [['loading_info_pct', 'Loading reference', 'above']],
  hotspot_c: [['hotspot_warning_c', 'Warning hot-spot', 'above'], ['hotspot_critical_c', 'Critical hot-spot', 'above']],
};
/** Limits come only from the API assumptions; missing/TBD limits remain unavailable. */
export function thresholdsFor(key: ChartKey, assumptions: Assumption[]): Threshold[] {
  return definitions[key].flatMap(([name, label, direction]) => {
    const value = assumptions.find(a => a.name === name)?.value;
    return typeof value === 'number' && Number.isFinite(value) ? [{ label, value, direction }] : [];
  });
}
export const violates = (value: number, limits: Threshold[]) => limits.some(limit => limit.direction === 'below' ? value < limit.value : value > limit.value);

/** Plotting coordinates only: never interpolate or recompute engineering measurements. */
export function chartGeometry(values: number[], limits: Threshold[], overlay: number[] = []) {
  if (!values.length || (overlay.length && overlay.length !== values.length) || [...values, ...overlay, ...limits.map(l => l.value)].some(v => !Number.isFinite(v))) throw new Error('Chart values must be finite and aligned.');
  const all = [...values, ...overlay, ...limits.map(l => l.value)];
  const min = Math.min(...all), max = Math.max(...all);
  const pad = (max - min || Math.abs(max) || 1) * 0.1;
  const low = min - pad, high = max + pad;
  const x = (index: number) => 60 + index * 640 / Math.max(values.length - 1, 1);
  const y = (value: number) => 210 - (value - low) * 180 / (high - low);
  const points = (series: number[]) => series.map((value, i) => `${x(i)},${y(value)}`).join(' ');
  return { low, high, x, y, points };
}
export function compatibleResults(a: SimulationResult, b: SimulationResult): boolean {
  return a.meta.engine_version === b.meta.engine_version && a.series.time.length === b.series.time.length && a.series.time.every((time, i) => time === b.series.time[i]);
}
export const comparisonMetrics: { key: keyof SimulationSummary; label: string; unit: string }[] = [
  { key: 'min_voltage_pu', label: 'Minimum voltage', unit: 'p.u.' },
  { key: 'peak_loading_pct', label: 'Peak loading', unit: '% rated current' },
  { key: 'peak_hotspot_c', label: 'Peak hot-spot', unit: '°C' },
  { key: 'peak_aging_factor', label: 'Peak aging acceleration', unit: '× reference' },
  { key: 'daily_equivalent_aging_hours', label: 'Equivalent reference aging', unit: 'h/day' },
];
export function compareResults(a: SimulationResult, b: SimulationResult) {
  if (!compatibleResults(a, b)) throw new Error('Compare only the same engine version and aligned time labels.');
  return comparisonMetrics.map(metric => {
    const before = Number(a.summary[metric.key]), after = Number(b.summary[metric.key]);
    if (!Number.isFinite(before) || !Number.isFinite(after)) throw new Error('Comparison metrics must be finite.');
    return { ...metric, before, after, difference: after - before };
  });
}

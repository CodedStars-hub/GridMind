/** Reject malformed successful responses before they become dashboard measurements. */
import type { HealthResponse, NetworkResponse, ScenariosResponse, SimulationResult } from '../types/api';

type ObjectValue = Record<string, unknown>;
export const object = (value: unknown): value is ObjectValue => typeof value === 'object' && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string';
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const list = (value: unknown, guard: (item: unknown) => boolean): value is unknown[] => Array.isArray(value) && value.every(guard);
const strings = (value: unknown) => list(value, text);
const numbers = (value: unknown) => list(value, finite);
const oneOf = (value: unknown, values: readonly unknown[]) => values.includes(value);
const days = ['summer_weekday', 'winter_weekday', 'weekend'];
const levels = ['moderate', 'heavy', 'critical'];
const sources = ['live', 'cached'];
function jsonValue(value: unknown): boolean {
  return value === null || text(value) || typeof value === 'boolean' || finite(value)
    || (Array.isArray(value) && value.every(jsonValue))
    || (object(value) && Object.values(value).every(jsonValue));
}
const assumption = (value: unknown) => object(value) && text(value.name) && text(value.unit) && text(value.note) && value.note.trim().length > 0 && 'value' in value && jsonValue(value.value);
const meta = (value: unknown) => object(value) && text(value.engine_version) && oneOf(value.source, sources) && object(value.inputs);
export const isHealth = (v: unknown): v is HealthResponse => object(v) && v.status === 'ok' && v.api_version === 'v2' && text(v.engine_version);
export function isNetwork(v: unknown): v is NetworkResponse {
  if (!object(v) || !meta(v.meta) || !object(v.neighbourhood) || !text(v.neighbourhood.name) || !object(v.neighbourhood.map) || !finite(v.neighbourhood.map.width) || !finite(v.neighbourhood.map.height)) return false;
  const transformer = (t: unknown) => object(t) && text(t.id) && text(t.name) && oneOf(t.archetype, ['residential', 'commercial', 'mixed']) && oneOf(t.load_level, levels) && oneOf(t.ev_usage, ['evening', 'daytime']) && finite(t.rated_kva) && finite(t.connections) && finite(t.x) && finite(t.y);
  const site = (s: unknown) => object(s) && text(s.id) && text(s.name) && text(s.transformer_id) && finite(s.footfall_score) && finite(s.max_kw) && finite(s.x) && finite(s.y);
  if (!list(v.transformers, transformer) || !list(v.sites, site)) return false;
  const ids = (v.transformers as { id: string }[]).map(t => t.id);
  const siteIds = (v.sites as { id: string }[]).map(s => s.id);
  if (new Set(ids).size !== ids.length || new Set(siteIds).size !== siteIds.length || !(v.sites as { transformer_id: string }[]).every(s => ids.includes(s.transformer_id))) return false;
  return object(v.defaults) && finite(v.defaults.target_kw) && object(v.defaults.month) && finite(v.defaults.month.weekday_count) && finite(v.defaults.month.weekend_count) && object(v.enums) && numbers(v.enums.target_kw) && list(v.assumptions, assumption);
}
export function isScenarios(v: unknown): v is ScenariosResponse {
  if (!object(v) || !text(v.engine_version) || !object(v.enums) || !object(v.defaults) || !list(v.assumptions, assumption)) return false;
  const allowed: Record<string, unknown[]> = { ev_kw: [10, 30, 50, 100], pv_kwp: [0, 10, 20, 30], day_type: days, load_level: levels, bess: ['off', 'auto'] };
  return Object.entries(allowed).every(([key, choices]) => {
    const options = v.enums as ObjectValue;
    const defaults = v.defaults as ObjectValue;
    const values = options[key];
    return Array.isArray(values) && values.length > 0 && values.every(value => choices.includes(value)) && values.includes(defaults[key]);
  });
}
export function isSimulation(v: unknown): v is SimulationResult {
  if (!object(v) || !meta(v.meta) || !object(v.series) || !object(v.summary) || !object(v.verdict) || !text(v.verdict.message) || !oneOf(v.verdict.status, ['safe', 'violations_found', 'safe_with_bess', 'upgrade_recommended'])) return false;
  const series = v.series;
  const inputs = (v.meta as ObjectValue).inputs;
  if (!object(inputs) || !oneOf(inputs.ev_kw, [10, 30, 50, 100]) || !oneOf(inputs.pv_kwp, [0, 10, 20, 30]) || !oneOf(inputs.day_type, days) || !oneOf(inputs.load_level, levels) || inputs.bess !== 'off' || inputs.bess_override !== null) return false;
  const numericKeys = ['ambient_c', 'base_kw', 'ev_kw', 'pv_kw', 'net_kw', 'voltage_pu', 'loading_pct', 'top_oil_c', 'hotspot_c', 'aging_factor'];
  const summaryKeys = ['min_voltage_pu', 'peak_voltage_deviation_pu', 'peak_hotspot_c', 'peak_loading_pct', 'peak_aging_factor', 'daily_equivalent_aging_hours', 'insulation_life_years'];
  const hasSeries = strings(series.time) && (series.time as string[]).length === 96 && numericKeys.every(key => numbers(series[key]) && (series[key] as number[]).length === 96);
  const nullableSeries = ['bess_kw', 'bess_soc_pct'].every(key => series[key] === null || (numbers(series[key]) && (series[key] as number[]).length === 96));
  const summary = v.summary;
  const hasSummary = summaryKeys.every(key => finite(summary[key])) && ['min_voltage_time', 'peak_hotspot_time', 'peak_loading_time'].every(key => text(summary[key]));
  const alerts = list(v.alerts, a => object(a) && oneOf(a.type, ['voltage_low', 'voltage_high', 'hotspot_warning', 'hotspot_critical', 'loading_over_100']) && oneOf(a.severity, ['info', 'warning', 'critical']) && text(a.start) && text(a.end) && finite(a.peak_value) && oneOf(a.unit, ['p.u.', '°C', '%']));
  // Battery/cost objects are typed for the contract, but this milestone only submits the supported no-BESS request.
  return hasSeries && nullableSeries && hasSummary && alerts && v.bess === null && v.cost === null;
}

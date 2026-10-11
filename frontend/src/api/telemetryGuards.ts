import type { DispatchResponse, ReplayResponse } from '../types/telemetry';
import { object } from './guards';
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(v => typeof v === 'string');
export function isReplay(value: unknown): value is ReplayResponse {
  if (!object(value) || value.simulated !== true || value.transformer_id !== 'single-transformer-model' || !finite(value.step_minutes) || value.step_minutes <= 0 || !Array.isArray(value.records) || value.records.length !== 96) return false;
  const keys = ['loading_pct', 'voltage_pu', 'hotspot_c', 'net_kw', 'battery_soc_pct'];
  if (!value.records.every((record, index) => object(record) && record.index === index && record.transformer_id === value.transformer_id && record.source === 'simulation' && typeof record.timestamp === 'string' && record.timestamp.endsWith('Z') && Number.isFinite(Date.parse(record.timestamp)) && keys.every(key => record[key] === null || finite(record[key])))) return false;
  const stepMinutes = value.step_minutes;
  const records = value.records as { timestamp: string }[];
  if (!records.every((record, index) => Date.parse(record.timestamp) === Date.parse(records[0]!.timestamp) + index * stepMinutes * 60000)) return false;
  return value.battery === null || (object(value.battery) && ['power_kw', 'energy_kwh', 'initial_soc_pct', 'soc_min_pct', 'soc_max_pct', 'charge_efficiency', 'discharge_efficiency'].every(key => finite((value.battery as Record<string, unknown>)[key])));
}
export function isDispatch(value: unknown): value is DispatchResponse {
  return object(value) && value.simulated === true && value.published === false && ['charge', 'discharge', 'idle'].includes(String(value.action)) && finite(value.power_kw) && (value.next_soc_pct === null || finite(value.next_soc_pct)) && typeof value.telemetry_timestamp === 'string' && strings(value.reasons) && strings(value.alerts) && object(value.constraints) && Object.values(value.constraints).every(finite);
}

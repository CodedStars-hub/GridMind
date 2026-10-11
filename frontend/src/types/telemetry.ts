import type { BatteryConfig, ScenarioRequest } from './api';
export interface TelemetryReading {
  index: number; timestamp: string; transformer_id: 'single-transformer-model'; source: 'simulation';
  loading_pct: number | null; voltage_pu: number | null; hotspot_c: number | null; net_kw: number | null; battery_soc_pct: number | null;
}
export interface ReplayRequest { scenario: ScenarioRequest; start_time: string }
export interface ReplayResponse { simulated: true; transformer_id: 'single-transformer-model'; step_minutes: number; records: TelemetryReading[]; battery: BatteryConfig | null }
export interface DispatchRequest { telemetry: TelemetryReading; now: string; previous_timestamp: string | null; battery: BatteryConfig | null }
export interface DispatchResponse {
  simulated: true; published: false; action: 'charge' | 'discharge' | 'idle'; power_kw: number; next_soc_pct: number | null;
  telemetry_timestamp: string; reasons: string[]; alerts: string[]; constraints: Record<string, number>;
}

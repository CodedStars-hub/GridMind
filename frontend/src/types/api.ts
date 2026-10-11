/** Public shapes from docs/api-contract.md §§2–4 and 13; no engineering defaults. */
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type DayType = 'summer_weekday' | 'winter_weekday' | 'weekend';
export type LoadLevel = 'moderate' | 'heavy' | 'critical';
export type EvKw = 10 | 30 | 50 | 100;
export type PvKwp = 0 | 10 | 20 | 30;
export interface ScenarioRequest { ev_kw: EvKw; pv_kwp: PvKwp; day_type: DayType; load_level: LoadLevel }
export interface ScenarioInputs extends ScenarioRequest { bess: 'off' | 'auto'; bess_override: { power_kw: number; energy_kwh: number } | null }
export interface Assumption { name: string; value: JsonValue; unit: string; note: string }
export interface HealthResponse { status: 'ok'; api_version: 'v2'; engine_version: string }
export interface ScenariosResponse {
  engine_version: string;
  enums: { ev_kw: EvKw[]; pv_kwp: PvKwp[]; day_type: DayType[]; load_level: LoadLevel[]; bess: ('off' | 'auto')[] };
  defaults: Omit<ScenarioInputs, 'bess_override'>;
  assumptions: Assumption[];
}
export interface Transformer {
  id: string; name: string; archetype: 'residential' | 'commercial' | 'mixed';
  load_level: LoadLevel; ev_usage: 'evening' | 'daytime'; connections: number;
  rated_kva: number; x: number; y: number;
}
export interface Site { id: string; name: string; transformer_id: string; footfall_score: number; max_kw: number; x: number; y: number }
export interface NetworkResponse {
  meta: { engine_version: string; source: 'live' | 'cached'; inputs: Record<string, never> };
  neighbourhood: { name: string; map: { width: number; height: number } };
  transformers: Transformer[]; sites: Site[];
  defaults: { target_kw: number; month: { weekday_count: number; weekend_count: number } };
  enums: { target_kw: number[] }; assumptions: Assumption[];
}
export interface SimulationSummary {
  min_voltage_pu: number; min_voltage_time: string; peak_voltage_deviation_pu: number;
  peak_hotspot_c: number; peak_hotspot_time: string; peak_loading_pct: number;
  peak_loading_time: string; peak_aging_factor: number; daily_equivalent_aging_hours: number;
  insulation_life_years: number;
}
export interface SimulationAlert {
  type: 'voltage_low' | 'voltage_high' | 'hotspot_warning' | 'hotspot_critical' | 'loading_over_100';
  severity: 'info' | 'warning' | 'critical'; start: string; end: string; peak_value: number; unit: 'p.u.' | '°C' | '%';
}
export interface SimulationResult {
  meta: { inputs: ScenarioInputs; engine_version: string; source: 'live' | 'cached' };
  series: {
    time: string[]; ambient_c: number[]; base_kw: number[]; ev_kw: number[]; pv_kw: number[];
    net_kw: number[]; voltage_pu: number[]; loading_pct: number[]; top_oil_c: number[];
    hotspot_c: number[]; aging_factor: number[]; bess_kw: number[] | null; bess_soc_pct: number[] | null;
  };
  summary: SimulationSummary; alerts: SimulationAlert[];
  verdict: { status: 'safe' | 'violations_found' | 'safe_with_bess' | 'upgrade_recommended'; message: string };
  bess: { power_kw: number; energy_kwh: number; feasible: boolean; schedule: { index: number; start: string; duration_min: number; power_kw: number }[] } | null;
  cost: { upgrade_cost_inr: number; bess_cost_inr: number; net_difference_inr: number; insulation_life_years_before: number; insulation_life_years_after: number; note: string } | null;
}
export interface ErrorResponse { error: { code: 'invalid_input' | 'not_found' | 'method_not_allowed' | 'convergence_failed' | 'internal_error'; message: string; field: string | null } }

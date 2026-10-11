import { object } from './guards';
import type { PlanResult } from '../types/planning';
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const strings = (value: unknown) => Array.isArray(value) && value.every(item => typeof item === 'string');
const metrics = (value: unknown) => object(value) && ['min_voltage_pu', 'peak_loading_pct', 'peak_hotspot_c'].every(key => finite(value[key]));
/** Validate every field displayed by the planner; the untouched response carries additional contract fields. */
export function isPlan(value: unknown): value is PlanResult {
  if (!object(value) || !object(value.meta) || typeof value.meta.engine_version !== 'string' || !['live','cached'].includes(String(value.meta.source)) || !object(value.meta.inputs) || !finite(value.meta.inputs.target_kw)) return false;
  if (!object(value.plan) || !finite(value.plan.unplaced_kw) || !object(value.plan.cost) || !['controllers_inr','battery_inr','upgrade_inr','connections_inr','total_inr'].every(key => finite((value.plan as {cost:Record<string,unknown>}).cost[key]))) return false;
  if (!object(value.comparison) || !['target_kw','placed_kw_baseline','placed_kw_plan','served_energy_kwh_per_day_baseline','served_energy_kwh_per_day_plan','served_pct_of_baseline'].every(key => finite((value.comparison as Record<string,unknown>)[key])) || !object(value.comparison.net) || !finite(value.comparison.net.damage_avoided_inr_per_month) || !finite(value.comparison.net.plan_cost_inr) || !(value.comparison.net.payback_months === null || finite(value.comparison.net.payback_months))) return false;
  if (!object(value.planning) || typeof value.planning.algorithm !== 'string' || !finite(value.planning.evaluations) || !strings(value.planning.selected_site_ids) || !Array.isArray(value.planning.sites)) return false;
  const sites = value.planning.sites;
  if (!sites.every(site => object(site) && ['site_id','name','transformer_id','reason','reason_code'].every(key => typeof site[key] === 'string') && ['requested_kw','allocated_kw','unserved_kw'].every(key => finite(site[key]) && site[key] >= 0) && ['selected','partial','rejected'].includes(String(site.status)) && typeof site.managed === 'boolean' && (site.managed ? finite(site.cap_fraction) && site.cap_fraction > 0 && site.cap_fraction <= 1 : site.cap_fraction === null))) return false;
  if (new Set(sites.map(site => site.site_id)).size !== sites.length) return false;
  if (!object(value.before_after) || !object(value.before_after.feasibility) || !Array.isArray(value.before_after.electrical)) return false;
  const feasibility = value.before_after.feasibility;
  if (typeof feasibility.additional_allocations_feasible !== 'boolean' || typeof feasibility.whole_neighbourhood_feasible !== 'boolean' || !['baseline_violations','final_violations'].every(key => Array.isArray(feasibility[key]) && (feasibility[key] as unknown[]).every(item => object(item) && ['transformer_id','scenario','constraint'].every(field => typeof item[field] === 'string')))) return false;
  return strings(value.limitations) && value.before_after.electrical.every(item => object(item) && typeof item.transformer_id === 'string' && object(item.days) && ['summer_weekday','weekend'].every(day => { const values = (item.days as Record<string,unknown>)[day]; return object(values) && metrics(values.before) && metrics(values.after) && metrics(values.delta); }));
}

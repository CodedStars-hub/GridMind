/** Display projection of the existing /v2/plan response (§3.8 and §12). */
export interface PlanRequest { target_kw: number }
export interface PlanSite {
  site_id: string; name: string; transformer_id: string; requested_kw: number; allocated_kw: number; unserved_kw: number;
  status: 'selected' | 'partial' | 'rejected'; managed: boolean; cap_fraction: number | null; reason: string; reason_code: string;
}
export interface ElectricalMetrics { min_voltage_pu: number; peak_loading_pct: number; peak_hotspot_c: number }
export interface PlanResult {
  meta: { engine_version: string; source: 'live' | 'cached'; inputs: PlanRequest };
  planning: { algorithm: string; sites: PlanSite[]; selected_site_ids: string[]; evaluations: number };
  plan: { unplaced_kw: number; cost: { controllers_inr: number; battery_inr: number; upgrade_inr: number; connections_inr: number; total_inr: number } };
  comparison: { target_kw: number; placed_kw_baseline: number; placed_kw_plan: number; served_energy_kwh_per_day_baseline: number; served_energy_kwh_per_day_plan: number; served_pct_of_baseline: number;
    net: { damage_avoided_inr_per_month: number; plan_cost_inr: number; payback_months: number | null } };
  before_after: { feasibility: { additional_allocations_feasible: boolean; whole_neighbourhood_feasible: boolean; baseline_violations: { transformer_id: string; scenario: string; constraint: string }[]; final_violations: { transformer_id: string; scenario: string; constraint: string }[] };
    electrical: { transformer_id: string; days: { summer_weekday: { before: ElectricalMetrics; after: ElectricalMetrics; delta: ElectricalMetrics }; weekend: { before: ElectricalMetrics; after: ElectricalMetrics; delta: ElectricalMetrics } } }[] };
  limitations: string[];
}

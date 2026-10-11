import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { useData } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, PageHeading, Panel } from '../components/ui';
import type { PlanResult } from '../types/planning';
import { label, number } from '../utils/format';

export function Planning() {
  const { client, network, refresh } = useData();
  const [target, setTarget] = useState<number | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const active = useRef<AbortController | null>(null);
  const busy = useRef(false);
  useEffect(() => () => active.current?.abort(), []);
  const resolvedTarget = network.status === 'success' && target !== null && network.data.enums.target_kw.includes(target) ? target : network.status === 'success' ? network.data.defaults.target_kw : null;
  async function run() {
    if (resolvedTarget === null || busy.current) return;
    busy.current = true; const controller = new AbortController(); active.current = controller;
    setPending(true); setError(null); setResult(null);
    try {
      const data = await client.plan({target_kw:resolvedTarget}, controller.signal);
      if (data.meta.inputs.target_kw !== resolvedTarget || data.comparison.target_kw !== resolvedTarget) throw new ApiError('The returned plan does not match the requested target.', 'invalid_response');
      if (!controller.signal.aborted) setResult(data);
    } catch (cause) { if (!controller.signal.aborted) setError(cause); }
    finally { busy.current = false; if (!controller.signal.aborted) setPending(false); }
  }
  return <><PageHeading eyebrow="INFRASTRUCTURE PLANNING" title="Place charging where it fits.">Choose a neighbourhood demand target. Compare an explained, constraint-aware plan against unplanned installation — both modelled, never guaranteed siting approvals.</PageHeading>
    <Panel title="01 · Define the charging target" subtitle="Additional demand profile scale in kW, not a count of chargers or a guarantee of simultaneous upstream capacity.">
      {network.status === 'loading' ? <Loading /> : network.status === 'error' ? <ErrorState error={network.error} retry={refresh} /> : <div className="planning-config"><span className="small-label">NEIGHBOURHOOD TARGET</span><div className="target-list" role="group" aria-label="Charging demand target">{network.data.enums.target_kw.map(value => <button type="button" className={`target-option ${value === resolvedTarget ? 'selected' : ''}`} aria-pressed={value === resolvedTarget} disabled={pending} key={value} onClick={() => setTarget(value)}>{number(value)} <small>kW</small></button>)}</div><p className="inline-note">Representative month: {network.data.defaults.month.weekday_count} weekdays + {network.data.defaults.month.weekend_count} weekend days. The planner combines sites sharing a transformer and checks both representative days.</p><button type="button" className="button" disabled={pending} onClick={() => { void run(); }}>{pending ? 'Evaluating placements…' : 'Generate placement plan'}</button></div>}
    </Panel>
    {pending && <Loading message="Checking combined demand, managed charging and transformer constraints…" />}
    {error !== null && <ErrorState error={error} />}
    {!result && !pending && error === null && <Panel title="Your placement decisions"><Empty title="A plan starts with a real calculation">No sites are recommended until the backend has evaluated the requested target. Older deployments may not support the latest planner.</Empty></Panel>}
    {result && <div aria-live="polite"><div className="result-heading"><div><span className="small-label">02 · PLACEMENT RECOMMENDATIONS</span><h2>{number(result.comparison.placed_kw_plan)} kW allocated</h2><p>Engine {result.meta.engine_version} · {result.meta.source} · Deterministic, explained heuristic</p></div><span className={`tag ${result.before_after.feasibility.additional_allocations_feasible ? 'teal' : 'warning'}`}>{result.before_after.feasibility.additional_allocations_feasible ? 'Allocations feasible' : 'Allocations constrained'}</span></div>
      <div className={`verdict ${result.before_after.feasibility.whole_neighbourhood_feasible ? 'safe' : 'warning'}`}><strong>{result.before_after.feasibility.whole_neighbourhood_feasible ? 'The modeled neighbourhood passes the constraints.' : 'Existing network constraints still need attention.'}</strong><p>Allocation feasibility and whole-neighbourhood compliance are separate. {result.before_after.feasibility.final_violations.length} final day/constraint violations reported; this is not a count of damaged assets.</p></div>
      <div className="metric-grid"><Metric label="Demand placed" value={number(result.comparison.placed_kw_plan)} unit="kW" description={`${number(result.plan.unplaced_kw)} kW target remains unplaced`} /><Metric label="Energy delivered" value={number(result.comparison.served_energy_kwh_per_day_plan,2)} unit="kWh/day" description={`${number(result.comparison.served_pct_of_baseline,2)}% of Unplanned installation (modelled)`} /><Metric label="Costed interventions" value={`₹${number(result.plan.cost.total_inr)}`} description="Configured quotes/assumptions; unpriced costs excluded" /><Metric label="Illustrative aging proxy avoided" value={`₹${number(result.comparison.net.damage_avoided_inr_per_month)}`} unit="/month" description="Signed depreciation proxy, not guaranteed financial savings" /></div>
      <Panel title="Where charging is recommended" subtitle="Priority, allocated demand and reasons from the actual planning engine."><div className="plan-site-list">{result.planning.sites.map(site => <article className="plan-site" key={site.site_id}><header><h3><span className="equipment-id">{site.site_id}</span>{site.name}</h3><span className={`tag ${site.status === 'selected' ? 'teal' : site.status === 'partial' ? 'warning' : ''}`}>{label(site.status)}</span></header><p>{site.transformer_id} · {site.managed ? `Managed charging · ${number((site.cap_fraction ?? 0) * 100)}% cap` : 'Uncontrolled profile'}</p><div className="plan-allocation">{number(site.allocated_kw)} <span>/ {number(site.requested_kw)} kW requested</span></div><div className="plan-progress" aria-hidden="true"><span style={{width:`${site.requested_kw > 0 ? Math.min(100,site.allocated_kw/site.requested_kw*100) : 0}%`}} /></div><p>{site.reason}</p><p>{number(site.unserved_kw)} kW demand-scale shortfall · {label(site.reason_code)}</p></article>)}</div></Panel>
      <Panel title="Existing demand → planned deployment" subtitle="Summer weekday electrical extrema. All other assumptions held constant; delta is planned minus existing."><div className="table-scroll"><table><caption className="sr-only">Transformer before and after electrical comparison</caption><thead><tr><th>Transformer</th><th>Min voltage · before → after</th><th>Peak loading · before → after</th><th>Peak hot-spot · before → after</th></tr></thead><tbody>{result.before_after.electrical.map(item => <tr key={item.transformer_id}><th scope="row">{item.transformer_id}</th><td>{number(item.days.summer_weekday.before.min_voltage_pu,4)} → {number(item.days.summer_weekday.after.min_voltage_pu,4)} p.u.</td><td>{number(item.days.summer_weekday.before.peak_loading_pct,2)} → {number(item.days.summer_weekday.after.peak_loading_pct,2)}%</td><td>{number(item.days.summer_weekday.before.peak_hotspot_c,2)} → {number(item.days.summer_weekday.after.peak_hotspot_c,2)} °C</td></tr>)}</tbody></table></div></Panel>
      <details className="panel"><summary>Trade-offs, cost assumptions & limitations</summary><dl className="summary-list">{Object.entries(result.plan.cost).map(([key,value]) => <div key={key}><dt>{label(key)}</dt><dd>₹{number(value)}</dd></div>)}</dl><ul className="alert-list">{result.limitations.map((note,index) => <li key={index}><p>{note}</p></li>)}</ul></details>
    </div>}<ModelNote /></>;
}

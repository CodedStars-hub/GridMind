import { useEffect, useRef, useState, useMemo } from 'react';
import { ApiError } from '../api/client';
import { useData } from '../app/DataProvider';
import { Empty, ErrorState, Loading, Metric, ModelNote, PageHeading, Panel } from '../components/ui';
import type { PlanResult, PlanSite } from '../types/planning';
import { label, number } from '../utils/format';

export type SiteRecommendation = {
  tag: string;
  badgeClass: 'emerald' | 'teal' | 'amber' | 'ruby' | 'neutral';
  shortExplanation: string;
};

/** Deterministic mapping from planner output fields to human-readable decision labels */
export function getSiteRecommendation(site: PlanSite): SiteRecommendation {
  if (site.status === 'selected' || (site.allocated_kw === site.requested_kw && site.requested_kw > 0)) {
    if (site.managed) {
      return {
        tag: 'Recommended with Conditions',
        badgeClass: 'teal',
        shortExplanation: `Suitable for deployment with managed charging (${Math.round((site.cap_fraction ?? 1) * 100)}% power cap).`,
      };
    }
    return {
      tag: 'Recommended',
      badgeClass: 'emerald',
      shortExplanation: 'Optimal deployment candidate without operational restrictions.',
    };
  }
  if (site.status === 'partial') {
    if (site.reason_code === 'target_budget_exhausted') {
      return {
        tag: 'Recommended (Partial Budget)',
        badgeClass: 'teal',
        shortExplanation: 'Partial allocation fulfills the remaining neighborhood demand target.',
      };
    }
    return {
      tag: 'Limited Capacity',
      badgeClass: 'amber',
      shortExplanation: 'Suitable for partial deployment; further capacity is constrained by transformer limits.',
    };
  }
  if (site.status === 'rejected') {
    if (site.reason_code === 'target_budget_exhausted') {
      return {
        tag: 'Not Selected — Target Already Met',
        badgeClass: 'neutral',
        shortExplanation: 'Not selected because the neighborhood demand target was already fulfilled elsewhere.',
      };
    }
    if (site.reason_code === 'baseline_violation') {
      return {
        tag: 'Avoid Until Remediation',
        badgeClass: 'ruby',
        shortExplanation: 'Not recommended for additional charging until existing transformer constraints are addressed.',
      };
    }
    return {
      tag: 'Not Recommended',
      badgeClass: 'ruby',
      shortExplanation: 'Operating constraints prevent additional charging allocation at this location.',
    };
  }
  return {
    tag: 'Needs Further Evaluation',
    badgeClass: 'neutral',
    shortExplanation: site.reason || 'Insufficient data for definitive recommendation.',
  };
}

export function Planning() {
  const { client, network, refresh } = useData();
  const [target, setTarget] = useState<number | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [expandedSite, setExpandedSite] = useState<string | null>(null);
  const active = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const planCache = useRef<Map<number, PlanResult>>(new Map());

  useEffect(() => () => active.current?.abort(), []);

  const resolvedTarget =
    network.status === 'success' && target !== null && network.data.enums.target_kw.includes(target)
      ? target
      : network.status === 'success'
        ? network.data.defaults.target_kw
        : null;

  async function run() {
    if (resolvedTarget === null || busy.current) return;

    // Check frontend cache first to avoid redundant 8.8s evaluations
    if (planCache.current.has(resolvedTarget)) {
      setResult(planCache.current.get(resolvedTarget)!);
      setError(null);
      return;
    }

    busy.current = true;
    const controller = new AbortController();
    active.current = controller;
    setPending(true);
    setError(null);
    setResult(null);

    try {
      const data = await client.plan({ target_kw: resolvedTarget }, controller.signal);
      if (data.meta.inputs.target_kw !== resolvedTarget || data.comparison.target_kw !== resolvedTarget) {
        throw new ApiError('The returned plan does not match the requested target.', 'invalid_response');
      }
      if (!controller.signal.aborted) {
        planCache.current.set(resolvedTarget, data);
        setResult(data);
      }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause);
    } finally {
      busy.current = false;
      if (!controller.signal.aborted) setPending(false);
    }
  }

  // Summary counts
  const siteCounts = useMemo(() => {
    if (!result) return { recommended: 0, constrained: 0, notSelected: 0 };
    let recommended = 0;
    let constrained = 0;
    let notSelected = 0;
    for (const site of result.planning.sites) {
      if (site.status === 'selected' || (site.allocated_kw === site.requested_kw && site.requested_kw > 0)) {
        recommended++;
      } else if (site.status === 'partial' || site.reason_code === 'baseline_violation') {
        constrained++;
      } else {
        notSelected++;
      }
    }
    return { recommended, constrained, notSelected };
  }, [result]);

  return (
    <>
      <PageHeading eyebrow="INFRASTRUCTURE PLANNING" title="Place charging where it fits.">
        Find feasible charging-site allocations and understand the trade-offs. Choose a neighbourhood demand target. Compare an explained, constraint-aware plan against unplanned installation — both modelled, never guaranteed siting approvals.
      </PageHeading>

      <Panel
        title="01 · Define the charging target"
        subtitle="Select target additional EV charging capacity to evaluate across all neighbourhood transformers."
      >
        {network.status === 'loading' ? (
          <Loading />
        ) : network.status === 'error' ? (
          <ErrorState error={network.error} retry={refresh} />
        ) : (
          <div className="planning-config">
            <span className="small-label">NEIGHBOURHOOD DEMAND TARGET</span>
            <div className="target-list" role="group" aria-label="Charging demand target">
              {network.data.enums.target_kw.map(value => (
                <button
                  type="button"
                  className={`target-option ${value === resolvedTarget ? 'selected' : ''}`}
                  aria-pressed={value === resolvedTarget}
                  disabled={pending}
                  key={value}
                  onClick={() => setTarget(value)}
                >
                  {number(value)} <small>kW</small>
                </button>
              ))}
            </div>
            <p className="inline-note">
              Representative month: {network.data.defaults.month.weekday_count} weekdays +{' '}
              {network.data.defaults.month.weekend_count} weekend days. The planner evaluates multiple diurnal profiles across 6 transformers.
            </p>
            <button
              type="button"
              className="button"
              disabled={pending}
              aria-label="Generate placement plan"
              onClick={() => { void run(); }}
            >
              {pending ? 'Evaluating allocations…' : 'Generate Charging Plan'}{' '}
              <span aria-hidden="true">→</span>
            </button>
          </div>
        )}
      </Panel>

      {pending && (
        <Loading message="Evaluating combined demand, managed charging and transformer constraints across all candidates (~8 seconds)…" />
      )}

      {error !== null && <ErrorState error={error} />}

      {!result && !pending && error === null && (
        <Panel title="Your placement decisions">
          <Empty title="A plan starts with a real calculation">
            Select a target demand level and generate a charging plan. Each candidate location is evaluated against thermal, voltage, and loading constraints.
          </Empty>
        </Panel>
      )}

      {result && (
        <div aria-live="polite">
          {/* Result Heading with verdict */}
          <div className="result-heading">
            <div>
              <span className="small-label">02 · PLACEMENT RECOMMENDATIONS</span>
              <h2>{number(result.comparison.placed_kw_plan)} kW allocated</h2>
              <p>
                Target {result.comparison.target_kw} kW · Engine {result.meta.engine_version} · {result.meta.source} · Deterministic heuristic
              </p>
            </div>
            <span className={`tag ${result.before_after.feasibility.additional_allocations_feasible ? 'teal' : 'warning'}`}>
              {result.before_after.feasibility.additional_allocations_feasible ? 'Allocations feasible' : 'Allocations constrained'}
            </span>
          </div>

          {/* Prominent Planning Verdict Banner */}
          <div
            className={`verdict ${result.before_after.feasibility.whole_neighbourhood_feasible ? 'safe' : 'warning'}`}
          >
            <strong>
              {result.before_after.feasibility.whole_neighbourhood_feasible
                ? 'The modeled neighbourhood passes the constraints.'
                : 'Existing network constraints still need attention.'}
            </strong>
            <p>
              Allocation feasibility and whole-neighbourhood compliance are separate. {result.before_after.feasibility.final_violations.length} final day/constraint violations reported; this is not a count of damaged assets.
            </p>
          </div>

          {/* KPI Summary Grid */}
          <div className="metric-grid">
            <Metric
              label="Demand placed"
              value={number(result.comparison.placed_kw_plan)}
              unit="kW"
              description={`${number(result.plan.unplaced_kw)} kW target remains unplaced`}
            />
            <Metric
              label="Recommended sites"
              value={number(siteCounts.recommended)}
              description={`${siteCounts.constrained} sites face transformer or electrical constraints`}
            />
            <Metric
              label="Energy delivered"
              value={number(result.comparison.served_energy_kwh_per_day_plan, 2)}
              unit="kWh/day"
              description={`${number(result.comparison.served_pct_of_baseline, 2)}% of Unplanned installation (modelled)`}
            />
            <Metric
              label="Costed interventions"
              value={`₹${number(result.plan.cost.total_inr)}`}
              description="Configured quotes/assumptions; unpriced costs excluded"
            />
          </div>

          {/* Scannable Recommendation Table / Site Details */}
          <Panel
            title="Where charging is recommended"
            subtitle="Priority, allocated demand, decision tags and reasoning from the actual planning engine."
          >
            <div className="table-scroll">
              <table className="planning-recommendation-table">
                <caption className="sr-only">Charging candidate site recommendations</caption>
                <thead>
                  <tr>
                    <th scope="col">Candidate Site</th>
                    <th scope="col">Decision</th>
                    <th scope="col">Capacity (Allocated / Requested)</th>
                    <th scope="col">Rationale & Operating Constraints</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {result.planning.sites.map(site => {
                    const rec = getSiteRecommendation(site);
                    const isExpanded = expandedSite === site.site_id;
                    const pct = site.requested_kw > 0 ? Math.min(100, Math.round((site.allocated_kw / site.requested_kw) * 100)) : 0;

                    return (
                      <tr key={site.site_id} className={isExpanded ? 'row-expanded' : ''}>
                        <th scope="row">
                          <div className="site-cell-name">
                            <span className="equipment-id">{site.site_id}</span>
                            <strong>{site.name}</strong>
                          </div>
                          <span className="site-cell-transformer">Transformer {site.transformer_id}</span>
                        </th>
                        <td>
                          <span className={`tag ${rec.badgeClass}`}>{rec.tag}</span>
                        </td>
                        <td>
                          <div className="allocation-progress-cell">
                            <strong>{number(site.allocated_kw)} kW</strong>
                            <span> / {number(site.requested_kw)} kW</span>
                            <div className="plan-progress" aria-hidden="true">
                              <span style={{ width: `${pct}%` }} />
                            </div>
                            <small>{pct}% allocated</small>
                          </div>
                        </td>
                        <td>
                          <p className="site-reason-main">{site.reason}</p>
                          <small className="site-reason-sub">{rec.shortExplanation}</small>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="button secondary sm"
                            aria-expanded={isExpanded}
                            onClick={() => setExpandedSite(isExpanded ? null : site.site_id)}
                          >
                            {isExpanded ? 'Hide' : 'Details'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Expandable Engineering Drawer for the Selected Site */}
            {expandedSite && (() => {
              const site = result.planning.sites.find(s => s.site_id === expandedSite);
              if (!site) return null;
              return (
                <div className="site-details-drawer" role="region" aria-label={`Engineering details for ${site.name}`}>
                  <div className="drawer-header">
                    <h4>
                      Engineering Evidence: <span className="equipment-id">{site.site_id}</span> {site.name}
                    </h4>
                    <button type="button" className="close-btn" onClick={() => setExpandedSite(null)}>✕</button>
                  </div>
                  <div className="drawer-grid">
                    <div>
                      <h5>Operating Mode</h5>
                      <p>
                        {site.managed
                          ? `Managed Charging active (${Math.round((site.cap_fraction ?? 1) * 100)}% power cap). Peak EV charging is throttled to respect transformer loading.`
                          : 'Uncontrolled charging profile.'}
                      </p>
                      <p>Transformer: <strong>{site.transformer_id}</strong> · Status: <strong>{label(site.status)}</strong></p>
                    </div>
                    <div>
                      <h5>Associated Transformer Violations</h5>
                      {(() => {
                        const violations = result.before_after.feasibility.final_violations.filter(v => v.transformer_id === site.transformer_id);
                        return violations.length ? (
                          <ul className="limiting-constraints-list">
                            {violations.map((v, i) => (
                              <li key={i}>
                                <span className="tag warning">{v.scenario}</span> {label(v.constraint)}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p>No final constraint violations reported on transformer {site.transformer_id}.</p>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              );
            })()}
          </Panel>

          {/* Action-Oriented Decision Summary: "What should we do next?" */}
          <Panel
            title="What should we do next?"
            subtitle="Actionable, evidence-based recommendations based on the simulated portfolio results."
          >
            <div className="decision-next-steps">
              <div className="next-step-card">
                <span className="step-num">01</span>
                <div>
                  <strong>Proceed with Recommended Allocations</strong>
                  <p>
                    Deploy charging capacity at high-readiness sites ({result.planning.sites.filter(s => s.status === 'selected' || s.allocated_kw === s.requested_kw).map(s => s.name).join(', ') || 'selected candidates'}).
                  </p>
                </div>
              </div>

              {result.planning.sites.some(s => s.managed) && (
                <div className="next-step-card">
                  <span className="step-num">02</span>
                  <div>
                    <strong>Implement Managed Charging Controls</strong>
                    <p>
                      Sites with managed charging caps require dynamic power management or smart chargers to prevent transformer overloads during evening peaks.
                    </p>
                  </div>
                </div>
              )}

              {result.plan.unplaced_kw > 0 && (
                <div className="next-step-card">
                  <span className="step-num">03</span>
                  <div>
                    <strong>Evaluate Battery Storage for Unplaced Demand</strong>
                    <p>
                      {number(result.plan.unplaced_kw)} kW of demand could not be allocated. Installing a Battery Energy Storage System (BESS) or upgrading transformer capacity could unlock these constrained locations.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </Panel>

          {/* Before & After Electrical Extrema Table */}
          <Panel
            title="Existing demand → planned deployment"
            subtitle="Summer weekday electrical extrema. All other assumptions held constant; delta is planned minus existing."
          >
            <div className="table-scroll">
              <table>
                <caption>Transformer before and after electrical comparison</caption>
                <thead>
                  <tr>
                    <th>Transformer</th>
                    <th>Min voltage · before → after</th>
                    <th>Peak loading · before → after</th>
                    <th>Peak hot-spot · before → after</th>
                  </tr>
                </thead>
                <tbody>
                  {result.before_after.electrical.map(item => (
                    <tr key={item.transformer_id}>
                      <th scope="row">{item.transformer_id}</th>
                      <td>
                        {number(item.days.summer_weekday.before.min_voltage_pu, 4)} →{' '}
                        {number(item.days.summer_weekday.after.min_voltage_pu, 4)} p.u.
                      </td>
                      <td>
                        {number(item.days.summer_weekday.before.peak_loading_pct, 2)} →{' '}
                        {number(item.days.summer_weekday.after.peak_loading_pct, 2)}%
                      </td>
                      <td>
                        {number(item.days.summer_weekday.before.peak_hotspot_c, 2)} →{' '}
                        {number(item.days.summer_weekday.after.peak_hotspot_c, 2)} °C
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {/* Expandable Trade-offs & Cost Assumptions */}
          <details className="panel">
            <summary>Trade-offs, cost assumptions & limitations</summary>
            <dl className="summary-list">
              {Object.entries(result.plan.cost).map(([key, value]) => (
                <div key={key}>
                  <dt>{label(key)}</dt>
                  <dd>₹{number(value)}</dd>
                </div>
              ))}
            </dl>
            <ul className="alert-list">
              {result.limitations.map((note, index) => (
                <li key={index}>
                  <p>{note}</p>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}

      <ModelNote />
    </>
  );
}

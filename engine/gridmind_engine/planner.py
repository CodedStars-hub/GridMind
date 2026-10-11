"""Transparent greedy placement plus existing/reference/planned comparisons."""

from copy import deepcopy

from . import __version__
from .hosting import assess_hosting
from .impact import LIMITATIONS, _present, compare_network_impacts
from .impact_values import finite_result, number
from .network import _network_data, _value, assess_network_with_precision
from .planner_allocation import allocation_settings, allocate_sites, entry, evaluate_allocation
from .planner_comparison import before_after_electrical, scenario_metrics
from .planner_sites import planning_sites, validate_plan_request


def unplanned_allocation(candidates, target, config):
    """Contract reference: footfall order, site ceilings, no electrical screening.

    Explicitly unavailable sites are omitted. requested_kw limits only the plan;
    the established reference fills max_kw, not a new invented benchmark.
    """
    by_id = {s['id']: s for s in _value(config, 'neighbourhood', 'sites')}
    result = []
    for candidate in sorted(candidates, key=lambda s: (-s['score_components']['footfall'], s['site_id'])):
        if not candidate['eligible']:
            continue
        kw = min(by_id[candidate['site_id']]['max_kw'], target)
        if kw:
            result.append(entry(candidate['site_id'], kw))
            target -= kw
    return result


def _remedies(reports, config):
    """Document supplied caps and unavailable later remedies without pretending sizing."""
    controller = _value(config, 'neighbourhood', 'managed_charging_cost_per_site_inr')
    remedies = []
    for site in reports:
        if not site['allocated_kw']:
            continue
        alternatives = deepcopy(site['alternatives'])
        alternatives.extend(dict(type=kind, feasible=False, cost_inr=None,
                                 reason='Not evaluated in M10; no implemented sizing or cross-site backtracking.')
                            for kind in ('reallocate', 'battery', 'upgrade'))
        remedies.append(dict(
            site_id=site['site_id'], transformer_id=site['transformer_id'],
            type='managed_charging' if site['managed'] else 'none',
            parameters={'cap_fraction': site['cap_fraction']} if site['managed'] else {},
            cost_inr=round(controller) if site['managed'] else 0,
            reason=site['reason'] + ' Connection charges are excluded when no quote is configured.',
            alternatives_considered=alternatives,
        ))
    return remedies


def plan_charging(payload: dict, config: dict) -> dict:
    """Plan profile-scale kW under an exact target budget, without AWS or mutation."""
    candidates = planning_sites(config)
    target = validate_plan_request(payload, config)
    allocation_settings(candidates, target, config)
    transformers, sites = _network_data(config)
    controller = number(_value(config, 'neighbourhood', 'managed_charging_cost_per_site_inr'),
                        'managed_charging_cost_per_site_inr', nonnegative=True)
    try:
        connection = config['neighbourhood']['parameters']['new_connection_cost_inr_per_kw']['value']
    except (KeyError, TypeError) as exc:
        raise ValueError('new_connection_cost_inr_per_kw must be configured (null if unavailable)') from exc
    if connection is not None:
        number(connection, 'new_connection_cost_inr_per_kw', nonnegative=True)
    existing, before_raw = assess_network_with_precision({'allocation': []}, config)
    hosting_response = assess_hosting(config)
    hosting = {item['transformer_id']: item for item in hosting_response['hosting']['transformers']}
    by_id = {t['id']: t for t in transformers}
    placements = allocate_sites(candidates, target, hosting, config,
        lambda identity, proposed: evaluate_allocation(by_id[identity], proposed, sites, config))
    proposed = placements['allocation']
    reference = unplanned_allocation(candidates, target, config)
    reference_result, reference_raw = assess_network_with_precision({'allocation': reference}, config)
    planned_result, after_raw = assess_network_with_precision({'allocation': proposed}, config)
    existing_metrics, before_electrical = scenario_metrics(existing, before_raw, config)
    reference_metrics, _ = scenario_metrics(reference_result, reference_raw, config)
    planned_metrics, after_electrical = scenario_metrics(planned_result, after_raw, config)
    for assessment in (reference_metrics, planned_metrics, existing_metrics):
        for transformer in assessment['transformers']:
            transformer['hosting'] = deepcopy(hosting[transformer['transformer_id']]['hosting'])
    # Final feasibility is independently checked on the full combined network run.
    final_violations = [dict(transformer_id=t['transformer_id'], **v) for t in after_electrical for v in t['violations']]
    baseline_violations = [dict(transformer_id=t['transformer_id'], **v) for t in before_electrical for v in t['violations']]
    site_transformer = {s['id']: s['transformer_id'] for s in sites}
    allocated_ids = {site_transformer[e['site_id']] for e in proposed}
    additional_feasible = not any(v['transformer_id'] in allocated_ids for v in final_violations)
    if not additional_feasible:
        raise ValueError('Final combined plan violates constraints on an allocated transformer')
    placed = sum(e['kw'] for e in proposed)
    controllers = controller * sum(e['managed'] for e in proposed)
    connections = 0 if connection is None else connection * placed
    costs = dict(controllers_inr=controllers, battery_inr=0, upgrade_inr=0,
                 connections_inr=connections, total_inr=controllers + connections)
    previous, after = reference_metrics['totals'], planned_metrics['totals']
    delta_keys = ('life_consumed_days_per_month', 'depreciation_inr_per_month',
                  'customer_hours_per_month', 'connections_affected', 'worst_min_voltage_v',
                  'worst_hotspot_c', 'transformers_in_violation')
    avoided = previous['depreciation_inr_per_month'] - after['depreciation_inr_per_month']
    comparison = dict(
        target_kw=target, placed_kw_baseline=sum(e['kw'] for e in reference), placed_kw_plan=placed,
        served_energy_kwh_per_day_baseline=previous['served_energy_kwh_per_day'],
        served_energy_kwh_per_day_plan=after['served_energy_kwh_per_day'],
        served_pct_of_baseline=100 * after['served_energy_kwh_per_day'] / previous['served_energy_kwh_per_day']
        if previous['served_energy_kwh_per_day'] else 0,
        deltas={key: after[key] - previous[key] for key in delta_keys},
        net=dict(damage_avoided_inr_per_month=avoided, plan_cost_inr=costs['total_inr'],
                 payback_months=costs['total_inr'] / avoided if avoided > 0 else None),
    )
    assumptions = deepcopy(hosting_response['assumptions'])
    existing_names = {a['name'] for a in assumptions}
    for stem in ('neighbourhood', 'costs'):
        for key, parameter in config[stem]['parameters'].items():
            if key not in existing_names:
                assumptions.append(dict(name=key, value=deepcopy(parameter['value']), unit=parameter['unit'],
                                        note=' '.join(parameter[n] for n in ('source', 'assumption') if parameter.get(n))))
                existing_names.add(key)
    result = dict(
        meta=dict(engine_version=__version__, source='live', inputs=deepcopy(payload)),
        baseline=dict(description='Unplanned installation (modelled)', allocation=reference, assessment=reference_metrics),
        plan=dict(allocation=proposed, assessment=planned_metrics, remedies=_remedies(placements['sites'], config),
                  unplaced_kw=placements['unplaced_kw'], cost=costs), comparison=comparison,
        existing=dict(description='Existing demand without proposed EV charging', assessment=existing_metrics),
        before_after=dict(impact=compare_network_impacts(before_raw, after_raw, config),
                          electrical=before_after_electrical(before_electrical, after_electrical),
                          feasibility=dict(additional_allocations_feasible=additional_feasible,
                                           whole_neighbourhood_feasible=not final_violations,
                                           baseline_violations=baseline_violations, final_violations=final_violations)),
        planning=dict(algorithm='footfall_greedy_discrete_v1', sites=placements['sites'],
                      selected_site_ids=[e['site_id'] for e in proposed], evaluations=placements['evaluations']),
        assumptions=assumptions,
        limitations=list(LIMITATIONS) + hosting_response['limitations'] + [
            'Footfall and candidate availability are illustrative, not measured traffic or permitting evidence.',
            'All sites on a transformer share its EV usage profile; site-specific temporal profiles are unsupported.',
            'Greedy priority with fixed earlier placements is not globally optimal; site ceilings are profile-scale bounds, not charger hardware sizes.',
            'Only configured controller and connection costs are included; no capital-expenditure budget or hardware quote is modelled.',
            'Legacy month and appliance-indicator household objects remain null; use before_after.impact for M8 life and exposure metrics.',
        ],
    )
    return _present(finite_result(result, 'plan'))

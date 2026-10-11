"""A bounded greedy placement heuristic using real combined branch series."""

from copy import deepcopy

from .hosting import search_settings
from .hosting_feasibility import DAYS, check_operating_series
from .impact_values import count, finite_result, finite_sum, number
from .network import EV_PROFILES, _value, transformer_load_series, validate_allocation
from .powerflow import PowerFlowError
from .profiles import MINUTES_PER_HOUR, _timing
from .simulate import simulate_load_series_with_precision


def entry(site, kw, cap=None):
    """Construct the established allocation item; kw is a profile scaling level."""
    return dict(site_id=site, kw=kw, managed=cap is not None, cap_fraction=cap)


def evaluate_allocation(transformer, allocation, sites, config):
    """Check combined served profiles plus each managed site's energy on both days."""
    search_settings(config)
    allocation = validate_allocation({'allocation': allocation}, config)
    step, _ = _timing(config)
    minimum = _value(config, 'neighbourhood', 'min_served_energy_pct_for_managed')
    attached = {s['id'] for s in sites if s['transformer_id'] == transformer['id']}
    relevant = [item for item in allocation if item['site_id'] in attached]
    days, violations = {}, []
    for day in DAYS:
        loads, echo = transformer_load_series(transformer, relevant, sites, day, config)
        try:
            _, raw = simulate_load_series_with_precision(loads, config, echo)
            checked = check_operating_series(raw, config)
        except PowerFlowError:
            checked = dict(margins=[], violations=['convergence_failed'])
        retained = {}
        shape = _value(config, EV_PROFILES[transformer['ev_usage']], day)
        for item in relevant:
            single, _ = transformer_load_series(transformer, [item], sites, day, config)
            requested = finite_sum((item['kw'] * v for v in shape), 'requested charging')
            # 100 is a fraction-to-percent conversion, not a model limit.
            pct = 100 * finite_sum(single.ev_kw, 'served charging') / requested if requested else 100
            retained[item['site_id']] = pct
            if item['managed'] and pct < minimum:
                checked['violations'].append('min_served_energy_pct_for_managed')
        days[day] = dict(**checked, served_energy_pct=retained,
                         additional_peak_kw=max(loads.ev_kw),
                         served_energy_kwh=finite_sum(loads.ev_kw, 'served energy') * step / MINUTES_PER_HOUR)
        violations.extend(dict(scenario=day, constraint=key) for key in sorted(set(checked['violations'])))
    return finite_result(dict(feasible=not violations, violations=violations, days=days), 'allocation feasibility')


def allocation_settings(candidates, target, config):
    """Reject contradictory budgets before running expensive physics searches."""
    _, block, _, caps = search_settings(config)
    count(target, 'target_kw')
    if target % block:
        raise ValueError('target_kw must be an allocation_block_kw multiple')
    controller = number(_value(config, 'neighbourhood', 'managed_charging_cost_per_site_inr'),
                        'managed_charging_cost_per_site_inr', nonnegative=True)
    budget = count(_value(config, 'neighbourhood', 'planner_max_evaluations'), 'planner_max_evaluations')
    required = sum(min(c['requested_kw'], target) // block for c in candidates) * (1 + len(caps))
    if not budget or budget < required:
        raise ValueError(f'planner_max_evaluations must cover all candidate modes ({required})')
    return block, caps, controller, budget


def allocate_sites(candidates, target, hosting, config, evaluate):
    """Process demand priority once; exhaust discrete site levels without monotonicity.

    At equal allocated kW, cheapest known mode wins, then served energy, then cap.
    Earlier placements are fixed; this is not a global optimization or backtracking.
    evaluate(transformer_id, complete_allocation) returns unrounded feasibility.
    """
    block, caps, controller, budget = allocation_settings(candidates, target, config)
    allocation, reports, used = [], [], 0
    remaining = target
    for site in candidates:
        branch = hosting[site['transformer_id']]
        report = deepcopy(site)
        report.update(allocated_kw=0, unserved_kw=site['requested_kw'], status='rejected',
                      limiting_constraints=[], alternatives=[], managed=False, cap_fraction=None,
                      electrically_eligible=branch['baseline']['feasible'])
        if not site['eligible']:
            code, message = 'site_ineligible', 'Site is configured as unavailable.'
        elif not site['requested_kw']:
            code, message = 'zero_demand', 'No additional demand was requested.'
        elif not branch['baseline']['feasible']:
            code, message = 'baseline_violation', 'Existing transformer conditions require remediation.'
            report['limiting_constraints'] = deepcopy(branch['baseline']['violations'])
        elif not remaining:
            code, message = 'target_budget_exhausted', 'Higher-priority sites used the configured demand target.'
        else:
            maximum = min(site['requested_kw'], remaining)
            best, best_rank = None, None
            results = {}
            for kw in range(block, maximum + 1, block):
                for cap in (None, *caps):
                    proposal = allocation + [entry(site['site_id'], kw, cap)]
                    checked = evaluate(site['transformer_id'], proposal)
                    used += 1
                    results[(kw, cap)] = checked
                    if checked['feasible']:
                        cost = 0 if cap is None else controller
                        energy = finite_sum((checked['days'][d]['served_energy_kwh'] for d in DAYS), 'mode energy')
                        rank = (kw, -cost, energy, cap or 0)
                        if best_rank is None or rank > best_rank:
                            best_rank, best = rank, (kw, cap)
            kw, cap = best if best else (0, None)
            if kw:
                allocation.append(entry(site['site_id'], kw, cap))
                remaining -= kw
                report.update(allocated_kw=kw, unserved_kw=site['requested_kw'] - kw,
                              managed=cap is not None, cap_fraction=cap,
                              status='selected' if kw == site['requested_kw'] else 'partial')
            # Report tested alternatives at the chosen level, or first rejected block.
            tested_kw = kw or block
            for tested_cap in (None, *caps):
                checked = results[(tested_kw, tested_cap)]
                report['alternatives'].append(dict(
                    type='none' if tested_cap is None else 'managed_charging',
                    feasible=checked['feasible'], cost_inr=0 if tested_cap is None else controller,
                    reason='Feasible tested mode.' if checked['feasible'] else 'Combined operating or energy constraints violated.'))
            if kw < maximum:
                for tested_cap in (None, *caps):
                    for violation in results[(kw + block, tested_cap)]['violations']:
                        if violation not in report['limiting_constraints']:
                            report['limiting_constraints'].append(deepcopy(violation))
                code, message = 'electrical_constraint', 'Further allocation fails combined transformer or managed-energy constraints.'
            elif kw < site['requested_kw']:
                code, message = 'target_budget_exhausted', 'Only the remaining demand target could be allocated.'
            else:
                code, message = 'selected_priority_headroom', 'Configured demand priority and combined electrical headroom support this allocation.'
        report.update(reason_code=code, reason=message)
        reports.append(report)
    if used > budget:
        raise ValueError('planner_max_evaluations exceeded')
    return dict(allocation=allocation, sites=reports, unplaced_kw=remaining, evaluations=used)

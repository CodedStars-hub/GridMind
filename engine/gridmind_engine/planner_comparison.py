"""Reuse M8 impacts and raw extrema; keep reference and existing baseline distinct."""

from copy import deepcopy

from .hosting_feasibility import DAYS, check_operating_series
from .impact import compare_network_impacts
from .impact_values import finite_result, finite_sum
from .network import _value
from .profiles import MINUTES_PER_HOUR, _timing


def scenario_metrics(result, raw, config):
    """Enrich a detached planner assessment with already-supported monthly totals.

    Legacy M7/M8 responses are never modified. Per-transformer month/household
    placeholders remain null; detailed exposure/life is returned in M8 impacts.
    """
    assessment = deepcopy(result['assessment'])
    impact = compare_network_impacts(raw, raw, config)
    step, steps = _timing(config)
    day_hours = step * steps / MINUTES_PER_HOUR
    weights = dict(zip(DAYS, (_value(config, 'neighbourhood', 'month_weekday_count'),
                              _value(config, 'neighbourhood', 'month_weekend_count'))))
    transformers = _value(config, 'neighbourhood', 'transformers')
    if [t['transformer_id'] for t in assessment['transformers']] != [t['id'] for t in transformers]:
        raise ValueError('assessment transformer identities must match configured order')
    metrics = dict(life_consumed_days_per_month=impact['totals']['ev_equivalent_aging_hours_per_month'] / day_hours,
                   depreciation_inr_per_month=impact['totals']['ev_aging_proxy_inr_per_month'])
    low_hours, affected, electrical = [], 0, []
    for transformer, branch, item in zip(transformers, assessment['transformers'], impact['transformers']):
        identity = transformer['id']
        daily = item['household']['ev']
        hours = finite_sum((daily[d]['hours_below_limit'] * weights[d] for d in DAYS), 'weighted low-voltage hours')
        low_hours.append(transformer['connections'] * hours)
        if any(daily[d]['voltage_low_steps'] for d in DAYS):
            affected += transformer['connections']
        days = {}
        violations = []
        for day in DAYS:
            series = raw[identity][day]
            days[day] = dict(min_voltage_pu=min(series['voltage_pu']),
                             peak_loading_pct=max(series['loading_pct']),
                             peak_hotspot_c=max(series['hotspot_c']))
            checked = check_operating_series(series, config)
            violations.extend(dict(scenario=day, constraint=key) for key in checked['violations'])
        kinds = {v['constraint'] for v in violations}
        branch['status'] = ('overloaded' if kinds.intersection({'loading_info_pct', 'hotspot_critical_c'}) else
                            'watch' if kinds else 'healthy')
        electrical.append(dict(transformer_id=identity, days=days, violations=violations))
    metrics.update(
        connections_affected=affected,
        customer_hours_per_month=finite_sum(low_hours, 'customer low-voltage hours'),
        worst_min_voltage_v=min(item['household']['ev'][d]['min_voltage_v'] for item in impact['transformers'] for d in DAYS),
        worst_hotspot_c=max(item['days'][d]['peak_hotspot_c'] for item in electrical for d in DAYS),
        transformers_in_violation=sum(bool(item['violations']) for item in electrical),
    )
    # Existing coincident charging peak/energy are replaced from raw aligned samples.
    coincident = [finite_sum((raw[t['id']]['summer_weekday']['ev_kw'][i] for t in transformers), 'coincident charging')
                  for i in range(steps)]
    metrics.update(served_kw_peak=max(coincident),
                   served_energy_kwh_per_day=finite_sum(coincident, 'daily energy') * step / MINUTES_PER_HOUR)
    assessment['totals'].update(metrics)
    return finite_result(assessment, 'assessment'), electrical


def before_after_electrical(before, after):
    """Difference matched branch/day extrema; never sum voltages or temperatures."""
    if [t['transformer_id'] for t in before] != [t['transformer_id'] for t in after]:
        raise ValueError('before/after transformer identities must match')
    items = []
    for b, a in zip(before, after):
        days = {}
        for day in DAYS:
            previous, proposed = b['days'][day], a['days'][day]
            days[day] = dict(before=previous, after=proposed,
                             delta={key: proposed[key] - previous[key] for key in previous})
        items.append(dict(transformer_id=b['transformer_id'], days=days))
    return items

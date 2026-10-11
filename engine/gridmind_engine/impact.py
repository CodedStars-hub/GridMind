"""Compare existing demand with proposed EV charging using the shared M7 engine."""

from copy import deepcopy

from . import __version__
from .cost import compare_economic
from .household import voltage_exposure
from .impact_values import count, finite_result, finite_sum, number, samples
from .life import compare_life
from .network import BASE_PROFILES, assess_network_with_precision
from .profiles import MINUTES_PER_HOUR, _timing
from .simulate import ROUND_DIGITS

DAYS = ('summer_weekday', 'weekend')
# These are explanatory statements, not numerical model parameters.
LIMITATIONS = (
    'Reference-equivalent aging is not measured remaining life or a failure-date prediction.',
    'The economic aging proxy is illustrative, not guaranteed expenditure or financial loss.',
    'Connection-point voltage is a proxy for customer exposure; household service drops are not modelled.',
    'Potential exposure does not establish appliance damage, repair costs or appliance failures.',
    'Residential connection proxies cover residential archetypes only; mixed/commercial residential counts are unknown.',
    'Each transformer is an independent branch; representative days are repeated, not a measured monthly forecast.',
)


def _parameter(config, stem, key):
    """Require documented config values; never substitute a monetary default."""
    try:
        entry = config[stem]['parameters'][key]
        value = entry['value']
    except (KeyError, TypeError) as exc:
        raise ValueError(f'{stem}.json: {key} is missing') from exc
    if value is None:
        raise ValueError(f'{stem}.json: {key} is unavailable')
    return value


def _settings(config):
    """Validate M8 assumptions before expensive simulations."""
    step_minutes, steps = _timing(config)
    days_per_year = number(_parameter(config, 'limits', 'calendar_days_per_year'),
                           'calendar_days_per_year', positive=True)
    normal_life = number(_parameter(config, 'limits', 'normal_insulation_life_hours'),
                         'normal_insulation_life_hours', positive=True)
    value = number(_parameter(config, 'costs', 'transformer_upgrade_cost_inr'),
                   'transformer_upgrade_cost_inr', nonnegative=True)
    nominal = number(_parameter(config, 'neighbourhood', 'nominal_home_voltage_v'),
                     'nominal_home_voltage_v', positive=True)
    lower = number(_parameter(config, 'limits', 'voltage_min_pu'), 'voltage_min_pu', positive=True)
    upper = number(_parameter(config, 'limits', 'voltage_max_pu'), 'voltage_max_pu', positive=True)
    if lower >= upper:
        raise ValueError('voltage_min_pu must be less than voltage_max_pu')
    day_counts = dict(zip(DAYS, (
        count(_parameter(config, 'neighbourhood', 'month_weekday_count'), 'month_weekday_count'),
        count(_parameter(config, 'neighbourhood', 'month_weekend_count'), 'month_weekend_count'),
    )))
    if sum(day_counts.values()) <= 0:
        raise ValueError('month weekday/weekend counts must total a positive number')
    return step_minutes, steps, days_per_year, normal_life, value, nominal, lower, upper, day_counts


def _validate_series(days, name, steps, step_minutes):
    """Require complete, aligned daily data rather than comparing mismatched profiles."""
    if not isinstance(days, dict) or set(days) != set(DAYS):
        raise ValueError(f'{name}: representative day identities must match')
    labels = [f'{i * step_minutes // MINUTES_PER_HOUR:02d}:{i * step_minutes % MINUTES_PER_HOUR:02d}'
              for i in range(steps)]
    for day, series in days.items():
        if (not isinstance(series, dict) or not isinstance(series.get('time'), (list, tuple))
                or list(series['time']) != labels):
            raise ValueError(f'{name}.{day}: time axis must match configured daily steps')
        for field in ('aging_factor', 'hotspot_c', 'voltage_pu', 'loading_pct'):
            values = samples(series.get(field), f'{name}.{day}.{field}',
                             nonnegative=field in ('aging_factor', 'loading_pct'),
                             positive=field == 'voltage_pu')
            if len(values) != steps:
                raise ValueError(f'{name}.{day}.{field}: series length must match configured steps')


def _scenario_exposure(days, connections, residential, settings):
    """Weight exposure durations; count each connection once if either day violates."""
    step_minutes, _, _, _, _, nominal, lower, upper, day_counts = settings
    result = {day: voltage_exposure(days[day]['voltage_pu'], step_minutes, lower, upper,
                                   nominal, connections, residential=residential) for day in DAYS}
    any_violation = any(result[day]['violation_steps'] for day in DAYS if day_counts[day])
    hours = finite_sum((result[day]['hours_outside_limits'] * day_counts[day] for day in DAYS), 'month_exposure_hours')
    exposed = None if connections is None else connections if any_violation else 0
    connection_hours = None if connections is None else connections * hours
    result['month'] = dict(
        hours_outside_limits=hours, connections_potentially_exposed=exposed,
        connection_hours=connection_hours,
        residential_connections_potentially_exposed_proxy=exposed if residential else None,
        residential_connection_hours_proxy=connection_hours if residential else None,
    )
    return finite_result(result, 'household')


def compare_network_impacts(baseline_precision: dict, ev_precision: dict, config: dict) -> dict:
    """Compare unrounded engine records; return unrounded impacts for presentation."""
    settings = _settings(config)
    step_minutes, steps, days_per_year, normal_life, value, _, _, _, day_counts = settings
    transformers = _parameter(config, 'neighbourhood', 'transformers')
    if not isinstance(transformers, list) or not transformers:
        raise ValueError('neighbourhood transformers must be a nonempty list')
    ids = [item.get('id') for item in transformers if isinstance(item, dict)]
    if (len(ids) != len(transformers) or any(type(identity) is not str for identity in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError('transformer identities must be unique strings')
    if not isinstance(baseline_precision, dict) or not isinstance(ev_precision, dict):
        raise ValueError('scenario records must be keyed by transformer identity')
    if set(baseline_precision) != set(ids) or set(ev_precision) != set(ids):
        raise ValueError('transformer identities must match both scenarios and configuration')
    results = []
    for transformer in transformers:
        identity = transformer['id']
        baseline, ev = baseline_precision[identity], ev_precision[identity]
        _validate_series(baseline, f'baseline.{identity}', steps, step_minutes)
        _validate_series(ev, f'ev.{identity}', steps, step_minutes)
        # Missing counts remain unavailable in this pure comparison; the M7
        # simulation adapter itself requires counts in its topology validation.
        connections = count(transformer.get('connections'), f'{identity}.connections', allow_missing=True)
        if type(transformer.get('archetype')) is not str or transformer['archetype'] not in BASE_PROFILES:
            raise ValueError(f'{identity}.archetype must name a configured profile archetype')
        residential = transformer['archetype'] == 'residential'
        life = compare_life(baseline, ev, step_minutes, day_counts, days_per_year)
        economic = compare_economic(life['month'], normal_life, value)
        household = dict(
            baseline=_scenario_exposure(baseline, connections, residential, settings),
            ev=_scenario_exposure(ev, connections, residential, settings),
        )
        if connections is None:
            additional_hours = None
        else:
            additional_hours = (household['ev']['month']['connection_hours']
                                - household['baseline']['month']['connection_hours'])
        household['additional_connection_hours_per_month'] = additional_hours
        results.append(dict(transformer_id=identity, life=life, economic=economic, household=household))
    totals = {}
    # Equivalent hours/year quantities sum separate assets; they are not the
    # equivalent aging of a single neighbourhood transformer.
    for field in ('baseline_equivalent_aging_hours', 'ev_equivalent_aging_hours',
                  'additional_equivalent_aging_hours', 'baseline_reference_equivalent_years',
                  'ev_reference_equivalent_years', 'additional_reference_equivalent_years'):
        totals[field + '_per_month'] = finite_sum((item['life']['month'][field] for item in results), field)
    for field in ('baseline_aging_proxy_inr', 'ev_aging_proxy_inr', 'additional_aging_proxy_inr'):
        totals[field + '_per_month'] = finite_sum((item['economic'][field] for item in results), field)
    for scenario in ('baseline', 'ev'):
        for field in ('connections_potentially_exposed', 'connection_hours',
                      'residential_connections_potentially_exposed_proxy', 'residential_connection_hours_proxy'):
            if field.startswith('residential'):
                relevant = [item for item, transformer in zip(results, transformers)
                            if transformer['archetype'] == 'residential']
            else:
                relevant = results
            values = [item['household'][scenario]['month'][field] for item in relevant]
            if any(value is None for value in values):
                total = None
            elif 'connections_' in field:
                total = sum(values)
            else:
                total = finite_sum(values, field)
            totals[scenario + '_' + field + '_per_month'] = total
    before, after = (totals[scenario + '_connection_hours_per_month'] for scenario in ('baseline', 'ev'))
    totals['additional_connection_hours_per_month'] = None if before is None or after is None else after - before
    return finite_result(dict(transformers=results, totals=totals), 'impact')


def _present(value, field=''):
    """Round only final output: INR to integers, other floats to four decimals."""
    if isinstance(value, dict):
        return {key: _present(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_present(item) for item in value]
    if type(value) is float:
        if '_inr' in field:
            return round(value)
        return round(value, ROUND_DIGITS)
    return value


def assess_impact(payload: dict, config: dict) -> dict:
    """Run baseline and EV cases once each, then compare their unrounded records."""
    _settings(config)
    ev, ev_precision = assess_network_with_precision(payload, config)
    baseline, baseline_precision = assess_network_with_precision({'allocation': []}, config)
    impacts = compare_network_impacts(baseline_precision, ev_precision, config)
    assumptions = []
    for stem, keys in (
        ('limits', ('normal_insulation_life_hours', 'calendar_days_per_year', 'voltage_min_pu', 'voltage_max_pu')),
        ('costs', ('transformer_upgrade_cost_inr',)),
        ('neighbourhood', ('month_weekday_count', 'month_weekend_count', 'nominal_home_voltage_v', 'transformers')),
        ('scenarios', ('step_minutes', 'steps_per_day')),
    ):
        for key in keys:
            parameter = config[stem]['parameters'][key]
            note = ' '.join(parameter[n] for n in ('source', 'assumption') if parameter.get(n))
            assumptions.append(dict(name=key, value=deepcopy(parameter['value']), unit=parameter['unit'], note=note))
    return dict(meta=dict(engine_version=__version__, source='live', inputs=deepcopy(payload)),
                baseline=baseline, ev=ev, impact=_present(impacts), assumptions=assumptions,
                limitations=list(LIMITATIONS))

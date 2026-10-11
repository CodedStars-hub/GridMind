"""Assess independent transformer branches; no capacity search or remedy selection.

The configured neighbourhood shares one nameplate and electrical parameter set.
Each branch has its own demand archetype, load level, charging sites and state.
"""

from copy import deepcopy
from dataclasses import asdict, replace
import math

from . import __version__
from .profiles import MINUTES_PER_HOUR, build_load_series
from .simulate import ROUND_DIGITS, simulate_load_series
from .validate import InvalidInputError, ValidatedInputs

BASE_PROFILES = {
    'residential': 'base_load_profile',
    'commercial': 'base_load_commercial_profile',
    'mixed': 'base_load_mixed_profile',
}
EV_PROFILES = {'evening': 'ev_profile', 'daytime': 'ev_daytime_profile'}


def _value(config, stem, name):
    """Name the missing config parameter rather than expose a raw lookup error."""
    try:
        value = config[stem]['parameters'][name]['value']
    except (KeyError, TypeError) as exc:
        raise ValueError(f'{stem}.json: {name} is missing') from exc
    if value is None:
        raise ValueError(f'{stem}.json: {name} is null')
    return value


def _positive(value, name):
    """Check config numbers before using them as capacities or divisors."""
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{name} must be positive and finite')
    return value


def _network_data(config):
    """Check identities, associations and profile selectors in loaded topology."""
    transformers = _value(config, 'neighbourhood', 'transformers')
    sites = _value(config, 'neighbourhood', 'sites')
    if not isinstance(transformers, list) or not transformers or not isinstance(sites, list):
        raise ValueError('neighbourhood.json: transformers and sites must be lists; transformers cannot be empty')
    seen = set()
    for node in transformers + sites:
        if not isinstance(node, dict) or type(node.get('id')) is not str or not node['id']:
            raise ValueError('neighbourhood.json: each node requires a non-empty id')
        if node['id'] in seen:
            raise ValueError(f"neighbourhood.json: duplicate id {node['id']}")
        seen.add(node['id'])
    ids = {item['id'] for item in transformers}
    for item in transformers:
        if (type(item.get('archetype')) is not str or item['archetype'] not in BASE_PROFILES
                or type(item.get('ev_usage')) is not str or item['ev_usage'] not in EV_PROFILES):
            raise ValueError(f"neighbourhood.json: {item['id']} has invalid archetype or ev_usage")
        _positive(_value(config, 'load_levels', f"{item.get('load_level')}_base_peak_pct_of_rating"), 'base peak percent')
        connections = item.get('connections')
        if type(connections) is not int or connections < 0:
            raise ValueError(f"neighbourhood.json: {item['id']} connections must be a non-negative integer")
    for item in sites:
        if item.get('transformer_id') not in ids:
            raise ValueError(f"neighbourhood.json: {item['id']} has unknown transformer_id")
        _positive(item.get('max_kw'), f"neighbourhood.json: {item['id']} max_kw")
    return transformers, sites


def validate_allocation(payload: dict, config: dict) -> list[dict]:
    """Validate the exact /assess body and return a detached normalized allocation."""
    _, sites = _network_data(config)
    if not isinstance(payload, dict):
        raise InvalidInputError('payload', 'Assessment request must be an object.')
    for key in payload:
        if key != 'allocation':
            raise InvalidInputError(str(key), 'Unknown assessment request field.')
    allocation = payload.get('allocation')
    if not isinstance(allocation, list):
        raise InvalidInputError('allocation', 'allocation is required and must be an array.')
    block = _positive(_value(config, 'neighbourhood', 'allocation_block_kw'), 'allocation_block_kw')
    caps = _value(config, 'neighbourhood', 'managed_cap_fractions')
    if not isinstance(caps, list) or not caps:
        raise ValueError('managed_cap_fractions must be a non-empty list')
    for cap in caps:
        if _positive(cap, 'managed_cap_fractions') >= 1:
            raise ValueError('managed_cap_fractions must be below one')
    site_map = {site['id']: site for site in sites}
    seen = set()
    result = []
    members = {'site_id', 'kw', 'managed', 'cap_fraction'}
    for index, item in enumerate(allocation):
        prefix = f'allocation[{index}]'
        if not isinstance(item, dict):
            raise InvalidInputError(prefix, 'Allocation entry must be an object.')
        for key in item:
            if key not in members:
                raise InvalidInputError(f'{prefix}.{key}', 'Unknown allocation field.')
        for key in sorted(members):
            if key not in item:
                raise InvalidInputError(f'{prefix}.{key}', f'{key} is required.')
        site_id = item['site_id']
        if type(site_id) is not str or site_id not in site_map or site_id in seen:
            raise InvalidInputError(f'{prefix}.site_id', 'site_id must name a unique configured site.')
        seen.add(site_id)
        kw = item['kw']
        if type(kw) is not int or not 0 <= kw <= site_map[site_id]['max_kw'] or kw % block:
            raise InvalidInputError(f'{prefix}.kw', f'kw must be a non-negative integer multiple of {block}, within site max_kw.')
        if type(item['managed']) is not bool:
            raise InvalidInputError(f'{prefix}.managed', 'managed must be a boolean.')
        cap = item['cap_fraction']
        if item['managed']:
            if type(cap) not in (int, float) or cap not in caps:
                raise InvalidInputError(f'{prefix}.cap_fraction', f'cap_fraction must be one of {caps}.')
        elif cap is not None:
            raise InvalidInputError(f'{prefix}.cap_fraction', 'Unmanaged cap_fraction must be null.')
        result.append(deepcopy(item))
    return result


def _served_profile(shape, entry, config, step_minutes):
    """Apply a supplied cap, then fill overnight headroom; do not choose a cap."""
    baseline = [entry['kw'] * value for value in shape]
    if not entry['managed']:
        return baseline
    cap = entry['kw'] * entry['cap_fraction']
    served = [min(value, cap) for value in baseline]
    excess = math.fsum(a - b for a, b in zip(baseline, served))
    start = _value(config, 'neighbourhood', 'managed_offpeak_start_hour')
    end = _value(config, 'neighbourhood', 'managed_offpeak_end_hour')
    day_hours = len(shape) * step_minutes / MINUTES_PER_HOUR
    for name, hour in (('managed_offpeak_start_hour', start), ('managed_offpeak_end_hour', end)):
        if type(hour) is not int or not 0 <= hour < day_hours:
            raise ValueError(f'{name} must be an integer hour within the day')
    if start == end:
        raise ValueError('managed offpeak start and end must differ')
    for index in range(len(shape)):
        hour = index * step_minutes / MINUTES_PER_HOUR
        inside = start <= hour < end if start < end else hour >= start or hour < end
        if inside:
            addition = min(excess, max(0, cap - served[index]))
            served[index] += addition
            excess -= addition
    return served


def transformer_load_series(transformer, allocation, sites, day_type, config):
    """Select configured profiles and sum served charging for this branch only."""
    selected = dict(config)
    for target, stem in (('base_load_profile', BASE_PROFILES[transformer['archetype']]),
                         ('ev_profile', EV_PROFILES[transformer['ev_usage']])):
        try:
            selected[target] = config[stem]
        except KeyError as exc:
            raise ValueError(f'{stem}.json: profile is missing') from exc
    attached = {site['id'] for site in sites if site['transformer_id'] == transformer['id']}
    entries = [item for item in allocation if item['site_id'] in attached]
    allocated_kw = sum(item['kw'] for item in entries)
    # No PV installation is defined in the neighbourhood configuration.
    inputs = ValidatedInputs(allocated_kw, 0, day_type, transformer['load_level'], 'off', None)
    loads = build_load_series(inputs, selected)
    shape = selected['ev_profile']['parameters'][day_type]['value']
    step_minutes = _value(config, 'scenarios', 'step_minutes')
    site_series = [_served_profile(shape, entry, config, step_minutes) for entry in entries]
    ev_kw = tuple(math.fsum(values[index] for values in site_series) for index in range(len(loads.time)))
    return replace(loads, ev_kw=ev_kw), asdict(inputs)


def _status(simulation, limits):
    """Neighbourhood classification differs from the legacy simulation verdict."""
    alerts = simulation['alerts']
    if (any(item['type'] == 'hotspot_critical' for item in alerts)
            or simulation['summary']['peak_loading_pct'] > limits['parameters']['loading_info_pct']['value']):
        return 'overloaded'
    if any(item['severity'] == 'warning' for item in alerts):
        return 'watch'
    return 'healthy'


def assess_network(payload: dict, config: dict) -> dict:
    """Assess all branches on summer weekday and weekend using shared physics.

    Later monthly, household and hosting fields are explicitly null, not estimates.
    Fail the whole assessment on invalid configuration or a power-flow failure.
    """
    allocation = validate_allocation(payload, config)
    transformers, sites = _network_data(config)
    results, weekday_charging, all_days = [], [], []
    rank = {'healthy': 0, 'watch': 1, 'overloaded': 2}
    for transformer in transformers:
        days = []
        for day_type in ('summer_weekday', 'weekend'):
            loads, echo = transformer_load_series(transformer, allocation, sites, day_type, config)
            days.append(simulate_load_series(loads, config, echo))
            if day_type == 'summer_weekday':
                weekday_charging.append(loads.ev_kw)
        weekday, weekend = days
        all_days.extend(days)
        status = max((_status(day, config['limits']) for day in days), key=rank.get)
        results.append(dict(
            transformer_id=transformer['id'], existing_peak_kw=max(weekday['series']['base_kw']),
            new_charging_kw=echo['ev_kw'], status=status, simulation=weekday,
            weekend_summary=weekend['summary'], month=None, household=None, hosting=None,
        ))
    steps = len(weekday_charging[0])
    coincident = [math.fsum(values[index] for values in weekday_charging) for index in range(steps)]
    duration = _value(config, 'scenarios', 'step_minutes') / MINUTES_PER_HOUR
    totals = dict(
        life_consumed_days_per_month=None, depreciation_inr_per_month=None,
        transformers_in_violation=sum(item['status'] != 'healthy' for item in results),
        connections_affected=None, customer_hours_per_month=None, worst_min_voltage_v=None,
        worst_hotspot_c=max(day['summary']['peak_hotspot_c'] for day in all_days),
        served_kw_peak=round(max(coincident), ROUND_DIGITS),
        served_energy_kwh_per_day=round(math.fsum(coincident) * duration, ROUND_DIGITS),
    )
    return dict(meta=dict(engine_version=__version__, source='live', inputs=deepcopy(payload)),
                assessment=dict(transformers=results, totals=totals))

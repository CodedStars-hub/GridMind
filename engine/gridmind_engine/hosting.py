"""Resolution-limited capacity searches; no placement or remedy optimization."""

from copy import deepcopy

from . import __version__
from .hosting_feasibility import DAYS, evaluate_candidate, operating_limits
from .impact_values import count, finite_result, finite_sum, number
from .network import _network_data, _value, assess_network_with_precision
from .profiles import MINUTES_PER_HOUR, _timing
from .simulate import ROUND_DIGITS


def search_settings(config):
    """Reject contradictory settings before any simulation or grid allocation."""
    maximum = count(_value(config, 'neighbourhood', 'hosting_search_max_kw'), 'hosting_search_max_kw')
    resolution = count(_value(config, 'neighbourhood', 'allocation_block_kw'), 'allocation_block_kw')
    budget = count(_value(config, 'neighbourhood', 'hosting_max_evaluations'), 'hosting_max_evaluations')
    for key, value in (('hosting_search_max_kw', maximum), ('allocation_block_kw', resolution),
                       ('hosting_max_evaluations', budget)):
        number(value, key, nonnegative=True)
    if not resolution or maximum % resolution:
        raise ValueError('allocation_block_kw must be positive and divide hosting_search_max_kw')
    if not budget:
        raise ValueError('hosting_max_evaluations must be positive')
    caps = _value(config, 'neighbourhood', 'managed_cap_fractions')
    if not isinstance(caps, list) or not caps:
        raise ValueError('managed_cap_fractions must be a nonempty list')
    previous = 1
    for cap in caps:
        number(cap, 'managed_cap_fractions', positive=True)
        if cap >= previous:
            raise ValueError('managed_cap_fractions must be strictly decreasing below one')
        previous = cap
    required = 1 + (maximum // resolution) * (1 + len(caps))
    if budget < required:
        raise ValueError(f'hosting_max_evaluations must cover the complete grid ({required})')
    step, steps = _timing(config)
    # Convert configured daily duration to hours; no hardcoded window bounds.
    hours = step * steps / MINUTES_PER_HOUR
    window = []
    for key in ('managed_offpeak_start_hour', 'managed_offpeak_end_hour'):
        value = count(_value(config, 'neighbourhood', key), key)
        if value >= hours:
            raise ValueError(f'{key} must be within the configured day')
        window.append(value)
    if window[0] == window[1]:
        raise ValueError('managed offpeak start and end must differ')
    retained = number(_value(config, 'neighbourhood', 'min_served_energy_pct_for_managed'),
                      'min_served_energy_pct_for_managed', nonnegative=True)
    if retained > 100:
        raise ValueError('min_served_energy_pct_for_managed must not exceed 100 percent')
    operating_limits(config)
    return maximum, resolution, budget, tuple(caps)


def grid_search(evaluate, maximum, resolution, baseline):
    """Inspect every positive grid point; do not assume monotonic feasibility.

    evaluate returns an internal candidate dict. Zero is already evaluated.
    No search is allowed on a violating baseline under the strict policy.
    """
    count(maximum, 'maximum')
    count(resolution, 'resolution')
    number(maximum, 'maximum', nonnegative=True)
    number(resolution, 'resolution', positive=True)
    if not resolution or maximum % resolution:
        raise ValueError('resolution must be positive and divide maximum')
    if not baseline['feasible']:
        return dict(selected=None, next_candidate=None, bound_reached=False), 0
    selected, candidates = baseline, {}
    for kw in range(resolution, maximum + 1, resolution):
        candidate = evaluate(kw)
        candidates[kw] = candidate
        if candidate['candidate_kw'] != kw:
            raise ValueError('evaluator candidate_kw must match the requested grid point')
        if candidate['feasible']:
            selected = candidate
    next_kw = selected['candidate_kw'] + resolution
    return dict(selected=selected, next_candidate=candidates.get(next_kw),
                bound_reached=selected['candidate_kw'] == maximum), len(candidates)


def _present(value):
    """Round diagnostic displays only after raw feasibility and selection."""
    if isinstance(value, dict):
        return {key: _present(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_present(item) for item in value]
    return round(value, ROUND_DIGITS) if type(value) is float else value


def assess_hosting(config: dict) -> dict:
    """Assess independent capacity against existing loads, ignoring allocations.

    Existing M7/M8 response shapes remain unchanged. The legacy managed_kw is
    a profile scaling level; selected.days explicitly report the served peak.
    """
    maximum, resolution, budget, caps = search_settings(config)
    transformers, _ = _network_data(config)
    _, raw_baseline = assess_network_with_precision({'allocation': []}, config)
    results = []
    for transformer in transformers:
        baseline = evaluate_candidate(transformer, 0, config,
                                      baseline_series=raw_baseline[transformer['id']])
        unmanaged, used = grid_search(lambda kw: evaluate_candidate(transformer, kw, config),
                                      maximum, resolution, baseline)
        evaluations = 1 + used
        managed_options = []
        for cap in caps:
            search, used = grid_search(
                lambda kw, cap=cap: evaluate_candidate(transformer, kw, config, cap),
                maximum, resolution, baseline)
            evaluations += used
            managed_options.append(search)
        def rank(search):
            selected = search['selected']
            if selected is None:
                return (0, 0, 0)
            # Contract tie-break: sum the two representative days' served energy.
            energy = finite_sum((selected['days'][day]['served_energy_kwh'] for day in DAYS),
                                'managed tie-break energy')
            return (selected['candidate_kw'], energy, selected['cap_fraction'] or 0)
        managed = max(managed_options, key=rank)
        if evaluations > budget:
            raise ValueError('hosting_max_evaluations was exceeded')
        results.append(dict(
            transformer_id=transformer['id'], baseline=baseline,
            hosting=dict(unmanaged_kw=rank(unmanaged)[0], managed_kw=rank(managed)[0]),
            unmanaged=unmanaged, managed=managed, evaluations=evaluations,
        ))
    totals = dict(
        transformers_assessed=len(results),
        compliant_baselines=sum(item['baseline']['feasible'] for item in results),
        violating_baselines=sum(not item['baseline']['feasible'] for item in results),
        positive_unmanaged_capacity=sum(item['hosting']['unmanaged_kw'] > 0 for item in results),
        independent_unmanaged_kw=sum(item['hosting']['unmanaged_kw'] for item in results),
    )
    assumptions = []
    for stem in ('neighbourhood', 'transformer', 'limits', 'load_levels', 'scenarios'):
        for key, entry in config[stem]['parameters'].items():
            if stem == 'neighbourhood' and key not in (
                'transformers', 'allocation_block_kw', 'hosting_search_max_kw', 'hosting_max_evaluations',
                'managed_cap_fractions', 'managed_offpeak_start_hour', 'managed_offpeak_end_hour',
                'min_served_energy_pct_for_managed'):
                continue
            assumptions.append(dict(name=key, value=deepcopy(entry['value']), unit=entry['unit'],
                                    note=' '.join(entry[n] for n in ('source', 'assumption') if entry.get(n))))
    response = dict(
        meta=dict(engine_version=__version__, source='live', inputs={}),
        hosting=dict(transformers=_present(results), totals=totals), assumptions=assumptions,
        limitations=[
            'Resolution-limited estimate for the configured profiles and operating limits, not interconnection approval.',
            'Independent transformer capacities do not validate simultaneous upstream network feasibility.',
            'Managed scaling levels are not coincident demand or installed charger recommendations; see selected day peaks.',
            'A violating baseline requires remediation; zero additional capacity does not make it compliant.',
            'Equipment is shared explicitly by configuration; no individual equipment overrides are defined.',
        ],
    )
    return finite_result(response, 'hosting')

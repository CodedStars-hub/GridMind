"""Unrounded operating-limit checks for the shared transformer engine.

A candidate scales the transformer's normalized EV shape, not its kVA rating.
Managed candidates reuse M7's cap and redistribution; no sites are selected.
"""

from .impact_values import finite_result, finite_sum, number, samples
from .network import EV_PROFILES, _network_data, _value, transformer_load_series
from .powerflow import PowerFlowError
from .profiles import MINUTES_PER_HOUR, _timing
from .simulate import simulate_load_series_with_precision

# Representative scenario identities, not physical or numerical assumptions.
DAYS = ('summer_weekday', 'weekend')


def operating_limits(config):
    """Validate configured healthy-operation boundaries; equality is allowed."""
    keys = ('voltage_min_pu', 'voltage_max_pu', 'loading_info_pct',
            'hotspot_warning_c', 'hotspot_critical_c')
    limits = {key: number(_value(config, 'limits', key), key,
                          positive=key not in ('hotspot_warning_c', 'hotspot_critical_c'))
              for key in keys}
    if limits['voltage_min_pu'] >= limits['voltage_max_pu']:
        raise ValueError('voltage_min_pu must be below voltage_max_pu')
    if limits['hotspot_warning_c'] >= limits['hotspot_critical_c']:
        raise ValueError('hotspot_warning_c must be below hotspot_critical_c')
    return limits


def check_operating_series(series, config):
    """Return signed headroom and violated config keys from unrounded samples.

    A positive margin is headroom; a negative margin is a strict violation.
    The critical hot-spot check is diagnostic: the warning limit is stricter.
    No top-oil or aging operating limit is defined in the current config.
    """
    limits = operating_limits(config)
    step, steps = _timing(config)
    expected = [f'{i * step // MINUTES_PER_HOUR:02d}:{i * step % MINUTES_PER_HOUR:02d}'
                for i in range(steps)]
    if not isinstance(series, dict) or list(series.get('time', [])) != expected:
        raise ValueError('hosting time axis must match configured steps')
    values = {}
    for field in ('voltage_pu', 'loading_pct', 'hotspot_c'):
        values[field] = samples(series.get(field), field, positive=field == 'voltage_pu',
                                nonnegative=field == 'loading_pct')
        if len(values[field]) != steps:
            raise ValueError(f'{field} length must match steps_per_day')
    extrema = (
        ('voltage_min_pu', min(values['voltage_pu']), 'p.u.', True),
        ('voltage_max_pu', max(values['voltage_pu']), 'p.u.', False),
        ('loading_info_pct', max(values['loading_pct']), '%', False),
        ('hotspot_warning_c', max(values['hotspot_c']), '°C', False),
        ('hotspot_critical_c', max(values['hotspot_c']), '°C', False),
    )
    margins = []
    for key, value, unit, lower in extrema:
        limit = limits[key]
        margin = value - limit if lower else limit - value
        margins.append(dict(constraint=key, value=value, limit=limit, margin=margin, unit=unit))
    return finite_result(dict(margins=margins,
                              violations=[m['constraint'] for m in margins if m['margin'] < 0]),
                         'hosting constraints')


def candidate_load_series(transformer, candidate_kw, cap_fraction, day, config):
    """Build one aggregate proposed charging profile, independent of site ceilings.

    This virtual aggregate is not an installation or placement recommendation.
    Existing archetype, load level, ambient, PF and equipment are unchanged.
    """
    number(candidate_kw, 'candidate_kw', nonnegative=True)
    if day not in DAYS:
        raise ValueError(f'day must be one of {DAYS}')
    transformers, _ = _network_data(config)
    if transformer not in transformers:
        raise ValueError('transformer must match a configured transformer')
    if cap_fraction is not None:
        number(cap_fraction, 'cap_fraction', positive=True)
        if cap_fraction >= 1 or cap_fraction not in _value(config, 'neighbourhood', 'managed_cap_fractions'):
            raise ValueError('cap_fraction must be a configured managed_cap_fractions entry')
    stem = EV_PROFILES[transformer['ev_usage']]
    shape = _value(config, stem, day)
    if max(samples(shape, 'EV shape', nonnegative=True)) != 1:
        raise ValueError('EV shape must peak at one to interpret candidate_kw as uncontrolled peak')
    site = dict(id=transformer['id'], transformer_id=transformer['id'])
    entry = dict(site_id=site['id'], kw=candidate_kw, managed=cap_fraction is not None,
                 cap_fraction=cap_fraction)
    return transformer_load_series(transformer, [entry], [site], day, config)


def evaluate_candidate(transformer, candidate_kw, config, cap_fraction=None, *, baseline_series=None):
    """Evaluate both days with shared physics; a solver failure is infeasible.

    baseline_series permits reuse of the M7 empty-allocation network run at zero.
    Invalid configuration propagates rather than masquerading as no headroom.
    """
    operating_limits(config)
    number(candidate_kw, 'candidate_kw', nonnegative=True)
    minimum_energy = number(_value(config, 'neighbourhood', 'min_served_energy_pct_for_managed'),
                            'min_served_energy_pct_for_managed', nonnegative=True)
    # 100 converts a fraction to percent, not an engineering threshold.
    if minimum_energy > 100:
        raise ValueError('min_served_energy_pct_for_managed must not exceed 100 percent')
    if baseline_series is not None and (candidate_kw != 0 or cap_fraction is not None):
        raise ValueError('baseline_series can only supply the unmanaged zero candidate')
    if baseline_series is not None and (not isinstance(baseline_series, dict) or set(baseline_series) != set(DAYS)):
        raise ValueError('baseline_series must contain both representative day identities')
    step, _ = _timing(config)
    days, violations = {}, []
    for day in DAYS:
        loads, echo = candidate_load_series(transformer, candidate_kw, cap_fraction, day, config)
        shape = config[EV_PROFILES[transformer['ev_usage']]]['parameters'][day]['value']
        requested = finite_sum((candidate_kw * v for v in shape), 'requested energy')
        served = finite_sum(loads.ev_kw, 'served energy')
        retained = 100 * (served / requested) if requested else 100
        metrics = dict(additional_peak_kw=max(loads.ev_kw),
                       served_energy_kwh=served * step / MINUTES_PER_HOUR,
                       served_energy_pct=retained)
        try:
            raw = (baseline_series[day] if baseline_series is not None else
                   simulate_load_series_with_precision(loads, config, echo)[1])
            constraints = check_operating_series(raw, config)
        except PowerFlowError:
            constraints = dict(margins=[], violations=['convergence_failed'])
        if cap_fraction is not None:
            constraints['margins'].append(dict(
                constraint='min_served_energy_pct_for_managed', value=retained,
                limit=minimum_energy, margin=retained - minimum_energy, unit='%'))
            if retained < minimum_energy:
                constraints['violations'].append('min_served_energy_pct_for_managed')
        days[day] = dict(**metrics, **constraints)
        violations.extend(dict(scenario=day, constraint=key) for key in constraints['violations'])
    return finite_result(dict(transformer_id=transformer['id'], candidate_kw=candidate_kw,
                              cap_fraction=cap_fraction, feasible=not violations,
                              days=days, violations=violations), 'candidate')

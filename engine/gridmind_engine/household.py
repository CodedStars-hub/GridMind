"""Potential customer exposure at one modelled connection point; no damage model."""

from .impact_values import count, finite_result, number, samples
from .profiles import MINUTES_PER_HOUR
from .simulate import merge_consecutive_steps


def voltage_exposure(voltage_pu, step_minutes, voltage_min_pu, voltage_max_pu,
                     nominal_voltage_v, connections, *, residential=False):
    """Count strict violations on unrounded voltages; each sample spans one interval.

    All customers share the modelled point as a proxy. Residential counts apply
    only to residential archetypes; commercial/mixed residential counts are unknown.
    None connection counts keep exposure quantities unavailable, never invented.
    """
    voltages = samples(voltage_pu, 'voltage_pu', positive=True)
    duration = number(number(step_minutes, 'step_minutes', positive=True) / MINUTES_PER_HOUR,
                      'step_hours', positive=True)
    lower = number(voltage_min_pu, 'voltage_min_pu', positive=True)
    upper = number(voltage_max_pu, 'voltage_max_pu', positive=True)
    if lower >= upper:
        raise ValueError('voltage_min_pu must be less than voltage_max_pu')
    number(nominal_voltage_v, 'nominal_voltage_v', positive=True)
    count(connections, 'connections', allow_missing=True)
    if type(residential) is not bool:
        raise ValueError('residential must be a boolean')
    low = [v < lower for v in voltages]
    high = [v > upper for v in voltages]
    outside = [a or b for a, b in zip(low, high)]
    steps = sum(outside)
    exposed = None if connections is None else connections if steps else 0
    connection_hours = None if connections is None else connections * steps * duration
    return finite_result(dict(
        min_voltage_pu=min(voltages), min_voltage_v=min(voltages) * nominal_voltage_v,
        violation_steps=steps, violation_intervals=len(merge_consecutive_steps(outside)),
        voltage_low_steps=sum(low), voltage_high_steps=sum(high),
        hours_outside_limits=steps * duration, hours_below_limit=sum(low) * duration,
        maximum_undervoltage_deviation_pu=max(0, lower - min(voltages)),
        outside_limits_pct=steps / len(voltages) * 100,
        connections=connections, connections_potentially_exposed=exposed,
        connection_hours=connection_hours,
        residential_connections_proxy=connections if residential else None,
        residential_connections_potentially_exposed_proxy=exposed if residential else None,
        residential_connection_hours_proxy=connection_hours if residential else None,
        proxy=True,
    ), 'household')

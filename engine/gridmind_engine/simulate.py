"""Pure daily orchestration, rounded chart data, alerts and no-battery verdicts."""

from copy import deepcopy
from dataclasses import asdict
import math

from . import __version__, aging, powerflow, thermal
from .profiles import MINUTES_PER_HOUR, LoadSeries, _timing, build_load_series
from .validate import validate_request

# Carry thermal state through two days and report only the final day.
PASSES = 2
# Round output values before deriving chart-facing summaries and alerts.
ROUND_DIGITS = 4
# Nominal voltage is one by the per-unit definition.
NOMINAL_VOLTAGE_PU = 1.0


def merge_consecutive_steps(flags):
    """Return inclusive true runs; never join runs across midnight."""
    runs = []
    start = None
    for index, flag in enumerate(flags):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


def detect_alerts(times, voltage_pu, loading_pct, hotspot_c, limits_config):
    """Group strict threshold violations using inclusive step labels and chart units."""
    limits = {key: entry['value'] for key, entry in limits_config['parameters'].items()}
    rules = (
        ('voltage_low', 'warning', voltage_pu, 'p.u.', min,
         [v < limits['voltage_min_pu'] for v in voltage_pu]),
        ('voltage_high', 'warning', voltage_pu, 'p.u.', max,
         [v > limits['voltage_max_pu'] for v in voltage_pu]),
        ('hotspot_warning', 'warning', hotspot_c, '°C', max,
         [limits['hotspot_warning_c'] < t <= limits['hotspot_critical_c'] for t in hotspot_c]),
        ('hotspot_critical', 'critical', hotspot_c, '°C', max,
         [t > limits['hotspot_critical_c'] for t in hotspot_c]),
        ('loading_over_100', 'info', loading_pct, '%', max,
         [v > limits['loading_info_pct'] for v in loading_pct]),
    )
    events = []
    for kind, severity, values, unit, peak, flags in rules:
        for start, end in merge_consecutive_steps(flags):
            event = dict(type=kind, severity=severity, start=times[start], end=times[end],
                         peak_value=peak(values[start:end + 1]), unit=unit)
            events.append((start, kind, event))
    return [event for _, _, event in sorted(events, key=lambda item: item[:2])]


def _summary(series, step_minutes, params):
    """Derive extrema from rounded series, choosing the first occurrence on ties."""
    voltage = series['voltage_pu']
    hotspot = series['hotspot_c']
    loading = series['loading_pct']
    hours = aging.daily_equivalent_aging_hours(hotspot, step_minutes, params)
    summary = {
        'min_voltage_pu': min(voltage),
        'min_voltage_time': series['time'][voltage.index(min(voltage))],
        'peak_voltage_deviation_pu': max(abs(v - NOMINAL_VOLTAGE_PU) for v in voltage),
        'peak_hotspot_c': max(hotspot),
        'peak_hotspot_time': series['time'][hotspot.index(max(hotspot))],
        'peak_loading_pct': max(loading),
        'peak_loading_time': series['time'][loading.index(max(loading))],
        'peak_aging_factor': max(series['aging_factor']),
        'daily_equivalent_aging_hours': hours,
        'insulation_life_years': aging.insulation_life_years(hours, params),
    }
    return {key: round(value, ROUND_DIGITS) if isinstance(value, (int, float)) else value
            for key, value in summary.items()}


def _verdict(alerts, limits_config):
    """Only warning and critical alerts affect the no-battery verdict."""
    violations = [event for event in alerts if event['severity'] in ('warning', 'critical')]
    if not violations:
        return dict(status='safe', message='No voltage or hot-spot violations were found; loading information does not change this verdict.')
    limit_keys = {
        'voltage_low': 'voltage_min_pu', 'voltage_high': 'voltage_max_pu',
        'hotspot_warning': 'hotspot_warning_c', 'hotspot_critical': 'hotspot_critical_c',
    }
    descriptions = []
    for event in violations:
        limit = limits_config['parameters'][limit_keys[event['type']]]['value']
        label = event['type'].replace('_', ' ')
        descriptions.append(f"{label} from {event['start']} to {event['end']} "
                            f"(worst {event['peak_value']} {event['unit']}; limit {limit} {event['unit']})")
    return dict(status='violations_found',
                message='Violations found: ' + '; '.join(descriptions) + '. Battery analysis has not been run.')


def simulate_day(inputs, config):
    """Report the last of two daily passes; temperatures are end-of-step values."""
    if inputs.bess_override is not None or inputs.bess != 'off':
        raise NotImplementedError('battery simulation is added in M8')
    return simulate_load_series(build_load_series(inputs, config), config, asdict(inputs))


def simulate_load_series(loads: LoadSeries, config: dict, input_echo: dict) -> dict:
    """Return the unchanged chart-facing daily result."""
    return simulate_load_series_with_precision(loads, config, input_echo)[0]


def simulate_load_series_with_precision(loads: LoadSeries, config: dict, input_echo: dict) -> tuple[dict, dict]:
    """Run the shared physics on supplied powers; preserve legacy output semantics.

    This internal engine interface bypasses request enums, not numerical checks.
    Network callers supply their aggregate charging series and a documented echo.
    """
    step_minutes, steps = _timing(config)
    expected_time = tuple(f'{i * step_minutes // MINUTES_PER_HOUR:02d}:{i * step_minutes % MINUTES_PER_HOUR:02d}'
                          for i in range(steps))
    if tuple(loads.time) != expected_time:
        raise ValueError('LoadSeries.time must match the configured daily time axis')
    for name in ('ambient_c', 'base_kw', 'ev_kw', 'pv_kw'):
        values = getattr(loads, name)
        if len(values) != steps:
            raise ValueError(f'LoadSeries.{name} must contain {steps} samples')
        for value in values:
            try:
                valid = type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                valid = False
            if not valid or (name != 'ambient_c' and value < 0):
                raise ValueError(f'LoadSeries.{name} must contain finite valid samples')
    flow_params = powerflow.powerflow_params_from_config(config['transformer'])
    thermal_params = thermal.thermal_params_from_config(config['transformer'])
    aging_params = aging.aging_params_from_config(config['limits'])
    step_minutes = config['scenarios']['parameters']['step_minutes']['value']
    first_flow = powerflow.simulate_step(loads.base_kw[0], loads.ev_kw[0], loads.pv_kw[0], flow_params)
    state = thermal.initial_state_at_load(first_flow.current_pu, thermal_params)
    recorded = {name: [] for name in ('voltage_pu', 'loading_pct', 'top_oil_c', 'hotspot_c', 'aging_factor')}
    for daily_pass in range(PASSES):
        for index in range(len(loads.time)):
            flow = powerflow.simulate_step(loads.base_kw[index], loads.ev_kw[index], loads.pv_kw[index], flow_params)
            temperatures = thermal.step(state, flow.current_pu, loads.ambient_c[index], step_minutes, thermal_params)
            state = temperatures.state
            factor = aging.aging_factor(temperatures.hotspot_c, aging_params)
            if daily_pass == PASSES - 1:
                for name, value in (
                    ('voltage_pu', flow.voltage_pu), ('loading_pct', flow.loading_pct),
                    ('top_oil_c', temperatures.top_oil_c), ('hotspot_c', temperatures.hotspot_c),
                    ('aging_factor', factor),
                ):
                    recorded[name].append(value)
    series = {
        'time': list(loads.time), 'ambient_c': list(loads.ambient_c),
        'base_kw': list(loads.base_kw), 'ev_kw': list(loads.ev_kw), 'pv_kw': list(loads.pv_kw),
        'net_kw': [b + e - p for b, e, p in zip(loads.base_kw, loads.ev_kw, loads.pv_kw)],
        **recorded,
    }
    raw_series = deepcopy(series)
    for name, values in series.items():
        if name != 'time':
            series[name] = [round(value, ROUND_DIGITS) for value in values]
    series.update(bess_kw=None, bess_soc_pct=None)
    summary = _summary(series, step_minutes, aging_params)
    alerts = detect_alerts(series['time'], series['voltage_pu'], series['loading_pct'], series['hotspot_c'], config['limits'])
    result = {
        'meta': dict(inputs=deepcopy(input_echo), engine_version=__version__, source='live'),
        'series': series, 'summary': summary, 'alerts': alerts,
        'verdict': _verdict(alerts, config['limits']), 'bess': None, 'cost': None,
    }

    return result, raw_series


def run_simulation(payload, config):
    """Validate a request and simulate it; input and power-flow errors propagate."""
    return simulate_day(validate_request(payload, config['scenarios']), config)

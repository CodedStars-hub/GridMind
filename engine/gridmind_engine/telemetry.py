"""Validated simulation replay and stateless advisory dispatch; no hardware writes."""
from dataclasses import asdict, fields, replace
from datetime import datetime, timedelta, timezone
import math

from . import bess, powerflow
from .aging import KELVIN_OFFSET
from .simulate import ROUND_DIGITS, run_simulation
from .validate import BessOverride, InvalidInputError


def timestamp(value, field):
    try:
        if not isinstance(value, str):
            raise ValueError()
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError()
        return parsed
    except (ValueError, TypeError):
        raise InvalidInputError(field, f'{field} must be an ISO-8601 UTC timestamp.') from None


def value(config, stem, name):
    return config[stem]['parameters'][name]['value']


def shape(payload, required, optional=()):
    if not isinstance(payload, dict):
        raise InvalidInputError('payload', 'Expected a JSON object.')
    for name in required:
        if name not in payload:
            raise InvalidInputError(name, f'{name} is required.')
    for name in payload:
        if name not in required + optional:
            raise InvalidInputError(name, f'Unknown field: {name}.')


def replay(payload, config):
    """Replay an independently simulated single-transformer day, not live sensors."""
    shape(payload, ('scenario', 'start_time'))
    start = timestamp(payload['start_time'], 'start_time')
    result = run_simulation(payload['scenario'], config)
    step = value(config, 'scenarios', 'step_minutes')
    records = []
    for index in range(len(result['series']['time'])):
        series = result['series']
        records.append(dict(index=index, timestamp=(start + timedelta(minutes=(index + 1) * step)).isoformat().replace('+00:00', 'Z'),
                            transformer_id='single-transformer-model', source='simulation',
                            loading_pct=series['loading_pct'][index], voltage_pu=series['voltage_pu'][index],
                            hotspot_c=series['hotspot_c'][index], net_kw=series['net_kw'][index],
                            battery_soc_pct=series['bess_soc_pct'][index] if series['bess_soc_pct'] is not None else None))
    battery = {name: result['bess'][name] for name in ('power_kw', 'energy_kwh', 'initial_soc_pct', 'soc_min_pct', 'soc_max_pct', 'charge_efficiency', 'discharge_efficiency')} if result['bess'] else None
    return dict(simulated=True, transformer_id='single-transformer-model', step_minutes=step, records=records, battery=battery)


def evaluate(payload, config):
    """Validate freshness/order at a caller-supplied clock, then recommend one step.

    The clock and previous timestamp belong to the client: this is a stateless
    simulation demonstration, not an authenticated device stream. No publishing.
    """
    shape(payload, ('telemetry', 'now', 'battery'), ('previous_timestamp',))
    record = payload['telemetry']
    shape(record, ('timestamp', 'transformer_id', 'source'), ('index', 'loading_pct', 'voltage_pu', 'hotspot_c', 'battery_soc_pct', 'net_kw'))
    if record['transformer_id'] != 'single-transformer-model' or record['source'] != 'simulation':
        raise InvalidInputError('telemetry', 'Only single-transformer-model simulation telemetry is supported.')
    observed = timestamp(record['timestamp'], 'telemetry.timestamp')
    now = timestamp(payload['now'], 'now')
    max_age = bess.positive(value(config, 'bess', 'telemetry_max_age_seconds'), 'telemetry_max_age_seconds')
    age = (now - observed).total_seconds()
    if age < 0 or age > max_age:
        raise InvalidInputError('telemetry.timestamp', 'Telemetry is stale or in the future.')
    previous = payload.get('previous_timestamp')
    if previous is not None and observed <= timestamp(previous, 'previous_timestamp'):
        raise InvalidInputError('telemetry.timestamp', 'Telemetry must be strictly newer than the previous sample.')
    readings = {}
    for name in ('loading_pct', 'voltage_pu', 'hotspot_c', 'battery_soc_pct', 'net_kw'):
        item = record.get(name)
        if item is not None:
            try:
                valid = type(item) in (int, float) and math.isfinite(item)
            except OverflowError:
                valid = False
            if not valid or (name == 'loading_pct' and item < 0) or (name == 'voltage_pu' and item <= 0) or (name == 'hotspot_c' and item <= -KELVIN_OFFSET) or (name == 'battery_soc_pct' and not 0 <= item <= bess.PERCENT):
                raise InvalidInputError(f'telemetry.{name}', f'{name} must be a finite valid reading.')
        readings[name] = item
    if 'index' in record and (type(record['index']) is not int or record['index'] < 0):
        raise InvalidInputError('telemetry.index', 'index must be a nonnegative integer.')
    response = dict(simulated=True, published=False, action='idle', power_kw=0.0,
                    next_soc_pct=readings['battery_soc_pct'], telemetry_timestamp=record['timestamp'],
                    reasons=[], alerts=[], constraints={})
    limits = config['limits']['parameters']
    alerts = []
    for name, reading, bound, direction in (
        ('voltage_low', readings['voltage_pu'], limits['voltage_min_pu']['value'], 'below'),
        ('voltage_high', readings['voltage_pu'], limits['voltage_max_pu']['value'], 'above'),
        ('hotspot_warning', readings['hotspot_c'], limits['hotspot_warning_c']['value'], 'above'),
        ('hotspot_critical', readings['hotspot_c'], limits['hotspot_critical_c']['value'], 'above'),
        ('loading_over_100', readings['loading_pct'], limits['loading_info_pct']['value'], 'above'),
    ):
        if reading is not None and (reading < bound if direction == 'below' else reading > bound):
            alerts.append(name)
    if 'hotspot_critical' in alerts:
        alerts.remove('hotspot_warning')
    response['alerts'] = alerts
    if any(item is None for item in readings.values()) or payload['battery'] is None:
        response['reasons'] = ['missing_data_idle']
        return response
    raw = payload['battery']
    if not isinstance(raw, dict) or any(name not in {field.name for field in fields(BessOverride)} for name in raw):
        raise InvalidInputError('battery', 'battery must contain only supported BESS parameters.')
    try:
        params = bess.battery_params(BessOverride(**raw), config)
    except (ValueError, TypeError) as exc:
        raise InvalidInputError('battery', str(exc)) from None
    response['constraints'] = asdict(params) | dict(step_minutes=value(config, 'scenarios', 'step_minutes'))
    if not params.soc_min_pct <= readings['battery_soc_pct'] <= params.soc_max_pct:
        response['reasons'] = ['soc_outside_bounds_idle']
        return response
    if 'voltage_high' in alerts or 'hotspot_critical' in alerts:
        response['reasons'] = ['engineering_interlock_idle']
        return response
    params = replace(params, initial_soc_pct=readings['battery_soc_pct'])
    policy = config['bess']['parameters']
    target = value(config, 'transformer', 'rated_kva') * value(config, 'transformer', 'power_factor_base') * policy['loading_discharge_threshold_pct']['value'] / bess.PERCENT
    demand = readings['net_kw']
    stressed = readings['loading_pct'] > policy['loading_discharge_threshold_pct']['value'] or 'voltage_low' in alerts or 'hotspot_warning' in alerts
    if stressed:
        # Request relief without allowing battery-driven export. Shared BESS dispatch
        # applies the same energy, efficiency and inverter limits as M15.
        desired = min(params.power_kw, max(0.0, demand - target))
        if desired == 0 and ('voltage_low' in alerts or 'hotspot_warning' in alerts):
            desired = min(params.power_kw, max(0.0, demand))
        dispatch_demand = target + desired
    else:
        dispatch_demand = demand
    powers, soc, _ = bess.dispatch([dispatch_demand], [observed.strftime('%H:%M')], value(config, 'scenarios', 'step_minutes'), params, target, policy['charge_window_start']['value'], policy['charge_window_end']['value'])
    power = powers[0]
    # Never recharge when current telemetry indicates stress, even if the proxy
    # target and measured current disagree because reactive power is significant.
    if stressed and power < 0:
        power, soc = 0.0, [readings['battery_soc_pct']]
    if power < 0:
        # Infer nonnegative reactive demand from the simulated connection-point
        # apparent power, then reuse the shared solver before recommending charge.
        flow_params = powerflow.powerflow_params_from_config(config['transformer'])
        apparent_kw = readings['voltage_pu'] * readings['loading_pct'] / bess.PERCENT * flow_params.rated_kva
        reactive_kw = math.sqrt(max(0.0, apparent_kw * apparent_kw - demand * demand))
        try:
            projected = powerflow.solve_voltage((demand - power) / flow_params.rated_kva, reactive_kw / flow_params.rated_kva, flow_params)
            blocked = not limits['voltage_min_pu']['value'] <= projected.voltage_pu <= limits['voltage_max_pu']['value'] or projected.loading_pct > policy['loading_discharge_threshold_pct']['value']
        except powerflow.PowerFlowError:
            blocked = True
        if blocked:
            response['reasons'] = ['charge_grid_limit_idle']
            return response
    response.update(power_kw=round(power, ROUND_DIGITS), next_soc_pct=round(soc[0], ROUND_DIGITS),
                    action='discharge' if power > 0 else 'charge' if power < 0 else 'idle',
                    reasons=['stress_relief'] if power > 0 else ['overnight_recharge'] if power < 0 else ['soc_or_policy_limit_idle'])
    return response

"""Deterministic grid-side peak shaving with an explicit stored-energy ledger."""

from dataclasses import dataclass
import math

from .profiles import MINUTES_PER_HOUR

# Percent is a unit conversion, not a battery assumption.
PERCENT = 100


@dataclass(frozen=True)
class BatteryParams:
    """Power is grid-side kW; capacity and internal state are stored kWh."""
    power_kw: float
    energy_kwh: float
    initial_soc_pct: float
    soc_min_pct: float
    soc_max_pct: float
    charge_efficiency: float
    discharge_efficiency: float


def positive(value, field):
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{field} must be finite and positive')
    return value


def battery_params(override, config):
    """Resolve optional request fields from config, splitting round-trip losses equally."""
    parameters = config['bess']['parameters']
    efficiency = positive(parameters['round_trip_efficiency']['value'], 'round_trip_efficiency')
    if efficiency > 1:
        raise ValueError('round_trip_efficiency must not exceed one')
    values = {key: getattr(override, key) for key in ('power_kw', 'energy_kwh')}
    for key in ('initial_soc_pct', 'soc_min_pct', 'soc_max_pct', 'charge_efficiency', 'discharge_efficiency'):
        value = getattr(override, key)
        values[key] = value if value is not None else (math.sqrt(efficiency) if key.endswith('efficiency') else parameters[key]['value'])
    return validate_params(BatteryParams(**values))


def validate_params(params):
    for name in ('power_kw', 'energy_kwh', 'charge_efficiency', 'discharge_efficiency'):
        positive(getattr(params, name), name)
    for name in ('charge_efficiency', 'discharge_efficiency'):
        if getattr(params, name) > 1:
            raise ValueError(f'{name} must not exceed one')
    for name in ('initial_soc_pct', 'soc_min_pct', 'soc_max_pct'):
        value = getattr(params, name)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= PERCENT:
            raise ValueError(f'{name} must be finite and between zero and {PERCENT}')
    if not params.soc_min_pct <= params.initial_soc_pct <= params.soc_max_pct or params.soc_min_pct >= params.soc_max_pct:
        raise ValueError('initial_soc_pct must lie within ordered soc_min_pct and soc_max_pct')
    return params


def dispatch(net_kw, times, step_minutes, params, target_kw, charge_start, charge_end):
    """Positive output discharges; negative charges. Recharge only in the configured window.

    Discharge energy removed = grid output / efficiency. Charge energy added =
    grid input * efficiency. The same step can never charge and discharge.
    SOC is reported at the end of each step; no terminal-SOC equality is assumed.
    """
    validate_params(params)
    hours = positive(step_minutes, 'step_minutes') / MINUTES_PER_HOUR
    positive(target_kw, 'target_kw')
    if len(net_kw) != len(times) or not net_kw:
        raise ValueError('battery demand and time series must be nonempty and aligned')
    for name, text in (('charge_window_start', charge_start), ('charge_window_end', charge_end)):
        try:
            hour, minute = (int(part) for part in text.split(':'))
            if not 0 <= hour < 24 or not 0 <= minute < MINUTES_PER_HOUR or text != f'{hour:02d}:{minute:02d}':
                raise ValueError()
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f'{name} must be HH:MM') from None
    if charge_start == charge_end:
        raise ValueError('charge window must not have identical start/end')
    energy = params.energy_kwh * (params.initial_soc_pct / PERCENT)
    minimum = params.energy_kwh * (params.soc_min_pct / PERCENT)
    maximum = params.energy_kwh * (params.soc_max_pct / PERCENT)
    powers, soc = [], []
    charged = discharged = losses = 0.0
    for demand, time in zip(net_kw, times):
        if type(demand) not in (int, float) or not math.isfinite(demand):
            raise ValueError('net_kw must be finite')
        power = 0.0
        if demand > target_kw:
            power = min(demand - target_kw, params.power_kw, max(0.0, energy - minimum) * params.discharge_efficiency / hours)
            removed = power * hours / params.discharge_efficiency
            energy -= removed
            discharged += power * hours
            losses += removed - power * hours
        elif (charge_start <= time < charge_end if charge_start < charge_end else time >= charge_start or time < charge_end):
            draw = min(target_kw - demand, params.power_kw, max(0.0, maximum - energy) / (params.charge_efficiency * hours))
            power = -draw
            added = draw * hours * params.charge_efficiency
            energy += added
            charged += draw * hours
            losses += draw * hours - added
        energy = min(maximum, max(minimum, energy))  # Floating-point boundary cleanup only.
        powers.append(power)
        soc.append(energy / params.energy_kwh * PERCENT)
    return powers, soc, dict(charged_kwh=charged, discharged_kwh=discharged, loss_kwh=losses)

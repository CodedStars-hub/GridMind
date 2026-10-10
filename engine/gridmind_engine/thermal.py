"""Pure transformer temperature updates using relative rises and exact relaxation."""

from dataclasses import dataclass, fields
import math


def _finite(name, value, *, positive=False, nonnegative=False):
    """Reject invalid numeric values with the field name in the message."""
    try:
        valid = not isinstance(value, bool) and math.isfinite(value)
        valid = valid and (not positive or value > 0)
        valid = valid and (not nonnegative or value >= 0)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        requirement = 'positive and finite' if positive else 'finite'
        if nonnegative:
            requirement = 'non-negative and finite'
        raise ValueError(f'{name} must be {requirement}')


@dataclass(frozen=True)
class ThermalParams:
    """Rated rises, loss ratio, exponents and time constants supplied by config."""

    rated_top_oil_rise_c: float
    rated_hotspot_rise_over_top_oil_c: float
    loss_ratio: float
    oil_exponent: float
    winding_exponent: float
    oil_time_constant_min: float
    winding_time_constant_min: float

    def __post_init__(self):
        for field in fields(self):
            _finite(field.name, getattr(self, field.name), positive=True)


def thermal_params_from_config(transformer_config_dict):
    """Build parameters from an already loaded transformer config; read no files."""
    values = {}
    for field in fields(ThermalParams):
        try:
            values[field.name] = transformer_config_dict['parameters'][field.name]['value']
        except (KeyError, TypeError) as exc:
            raise ValueError(f'{field.name} is missing its config value') from exc
    return ThermalParams(**values)


@dataclass(frozen=True)
class ThermalState:
    """Top-oil rise over ambient and hot-spot rise over top-oil; no ambient stored."""

    top_oil_rise_c: float
    hotspot_rise_over_top_oil_c: float

    def __post_init__(self):
        for field in fields(self):
            _finite(field.name, getattr(self, field.name), nonnegative=True)


@dataclass(frozen=True)
class ThermalStepResult:
    """A new relative state plus absolute top-oil and hot-spot temperatures in C."""

    state: ThermalState
    top_oil_c: float
    hotspot_c: float


def steady_state_rises(load_pu, params):
    """Return the ultimate relative rises for a constant per-unit kVA load."""
    _finite('load_pu', load_pu, nonnegative=True)
    try:
        oil = params.rated_top_oil_rise_c * (
            (load_pu ** 2 * params.loss_ratio + 1) / (params.loss_ratio + 1)
        ) ** params.oil_exponent
        winding = params.rated_hotspot_rise_over_top_oil_c * load_pu ** (
            2 * params.winding_exponent
        )
    except OverflowError as exc:
        raise ValueError('load_pu and params produce unrepresentable thermal rises') from exc
    return ThermalState(oil, winding)


def initial_state_at_load(load_pu, params):
    """Start with the steady-state relative rises for the chosen initial load."""
    return steady_state_rises(load_pu, params)


def step(state, load_pu, ambient_c, dt_min, params):
    """Advance one constant-load step exactly; return ThermalStepResult.

    Ambient affects the absolute temperatures, never the stored relative rises.
    """
    _finite('ambient_c', ambient_c)
    _finite('dt_min', dt_min, positive=True)
    ultimate = steady_state_rises(load_pu, params)
    oil = ultimate.top_oil_rise_c + (
        state.top_oil_rise_c - ultimate.top_oil_rise_c
    ) * math.exp(-dt_min / params.oil_time_constant_min)
    winding = ultimate.hotspot_rise_over_top_oil_c + (
        state.hotspot_rise_over_top_oil_c - ultimate.hotspot_rise_over_top_oil_c
    ) * math.exp(-dt_min / params.winding_time_constant_min)
    new_state = ThermalState(oil, winding)
    top_oil_c = ambient_c + oil
    hotspot_c = top_oil_c + winding
    _finite('top_oil_c', top_oil_c)
    _finite('hotspot_c', hotspot_c)
    return ThermalStepResult(new_state, top_oil_c, hotspot_c)

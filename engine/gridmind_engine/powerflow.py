"""An ideal fixed-tap source feeds transformer series impedance, then one lumped
LV feeder, then ONE connection point for base load, EV, solar and later battery.
This is a balanced single-phase equivalent with no shunt branches.
"""

from dataclasses import dataclass
import math

# Below this voltage, reject the iteration rather than divide near collapse.
VOLTAGE_COLLAPSE_GUARD_PU = 0.1


def _number(name, value, *, positive=False, nonnegative=False):
    """Validate a real input and return its finite floating-point value."""
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError
        number = float(value)
        valid = math.isfinite(number)
        valid = valid and (not positive or number > 0)
        valid = valid and (not nonnegative or number >= 0)
    except (ValueError, OverflowError):
        valid = False
    if not valid:
        requirement = 'positive and finite' if positive else 'finite'
        if nonnegative:
            requirement = 'non-negative and finite'
        raise ValueError(f'{name} must be {requirement}')
    return number


@dataclass(frozen=True)
class PowerFlowParams:
    """Per-unit impedances, fixed power factors and numerical solver settings."""

    rated_kva: float
    source_voltage_pu: float
    transformer_r_pu: float
    transformer_x_pu: float
    feeder_r_pu: float
    feeder_x_pu: float
    power_factor_base: float
    power_factor_ev: float
    power_factor_pv: float
    tolerance_pu: float
    max_iterations: int

    def __post_init__(self):
        for name in ('rated_kva', 'source_voltage_pu', 'tolerance_pu'):
            _number(name, getattr(self, name), positive=True)
        for name in ('transformer_r_pu', 'transformer_x_pu', 'feeder_r_pu', 'feeder_x_pu'):
            _number(name, getattr(self, name), nonnegative=True)
        for name in ('power_factor_base', 'power_factor_ev', 'power_factor_pv'):
            value = _number(name, getattr(self, name), positive=True)
            if value > 1:
                raise ValueError(f'{name} must be in (0, 1]')
        if self.power_factor_pv != 1:
            raise ValueError('power_factor_pv: only unity-power-factor PV is supported in the MVP')
        if (isinstance(self.max_iterations, bool)
                or not isinstance(self.max_iterations, int) or self.max_iterations <= 0):
            raise ValueError('max_iterations must be a positive integer')


def powerflow_params_from_config(transformer_config_dict):
    """Build parameters and derive transformer R and X from an already loaded dict."""
    def value(name, **checks):
        try:
            raw = transformer_config_dict['parameters'][name]['value']
        except (KeyError, TypeError) as exc:
            raise ValueError(f'{name} is missing its config value') from exc
        return _number(name, raw, **checks)

    rated_kva = value('rated_kva', positive=True)
    # The voltage base and no-load loss are documented config inputs; shunt losses
    # do not enter this series-only power-flow model.
    value('lv_voltage_v', positive=True)
    value('no_load_loss_w', positive=True)
    load_loss = value('load_loss_w', positive=True)
    impedance_pct = value('impedance_voltage_pct', positive=True)
    # 1000 converts kVA to VA; 100 converts percentage to per unit.
    transformer_r = load_loss / rated_kva / 1000
    transformer_z = impedance_pct / 100
    _number('impedance_voltage_pct (derived per unit)', transformer_z, positive=True)
    if transformer_z < transformer_r:
        raise ValueError('impedance_voltage_pct is smaller than resistance derived from load_loss_w')
    # Equivalent to sqrt(z*z - r*r), but avoids squaring large magnitudes.
    transformer_x = transformer_z * math.sqrt(
        (1 - transformer_r / transformer_z) * (1 + transformer_r / transformer_z)
    )
    _number('transformer_r_pu', transformer_r, nonnegative=True)
    _number('transformer_x_pu', transformer_x, nonnegative=True)
    try:
        max_iterations = transformer_config_dict['parameters']['powerflow_max_iterations']['value']
    except (KeyError, TypeError) as exc:
        raise ValueError('powerflow_max_iterations is missing its config value') from exc
    if (isinstance(max_iterations, bool) or not isinstance(max_iterations, int)
            or max_iterations <= 0):
        raise ValueError('powerflow_max_iterations must be a positive integer')
    return PowerFlowParams(
        rated_kva=rated_kva,
        source_voltage_pu=value('source_voltage_pu', positive=True),
        transformer_r_pu=transformer_r,
        transformer_x_pu=transformer_x,
        feeder_r_pu=value('feeder_resistance_pu', nonnegative=True),
        feeder_x_pu=value('feeder_reactance_pu', nonnegative=True),
        power_factor_base=value('power_factor_base', positive=True),
        power_factor_ev=value('power_factor_ev', positive=True),
        power_factor_pv=value('power_factor_pv', positive=True),
        tolerance_pu=value('powerflow_tolerance_pu', positive=True),
        max_iterations=max_iterations,
    )


def net_complex_power_pu(base_kw, ev_kw, pv_kw, params, bess_kw=0.0):
    """Return (active, reactive) per-unit demand; positive BESS discharges at unity PF."""
    base_kw = _number('base_kw', base_kw, nonnegative=True)
    ev_kw = _number('ev_kw', ev_kw, nonnegative=True)
    pv_kw = _number('pv_kw', pv_kw, nonnegative=True)
    bess_kw = _number('bess_kw', bess_kw)
    p_pu = (base_kw + ev_kw - pv_kw - bess_kw) / params.rated_kva
    q_pu = (
        base_kw * math.tan(math.acos(params.power_factor_base))
        + ev_kw * math.tan(math.acos(params.power_factor_ev))
    ) / params.rated_kva
    _number('p_pu (base_kw, ev_kw, pv_kw, bess_kw)', p_pu)
    _number('q_pu (base_kw, ev_kw, power factors)', q_pu)
    return p_pu, q_pu


@dataclass(frozen=True)
class PowerFlowResult:
    """Connection voltage and secondary current magnitudes; loading is rated current %."""

    voltage_pu: float
    current_pu: float
    loading_pct: float
    p_pu: float
    q_pu: float
    iterations: int


class PowerFlowError(Exception):
    """No valid voltage solution; the orchestrator maps this to convergence_failed."""


def _finite_complex(name, value):
    """Reject non-finite intermediate solver values as convergence failures."""
    if not (math.isfinite(value.real) and math.isfinite(value.imag)):
        raise PowerFlowError(f'{name} became non-finite')


def _check_voltage(voltage):
    """Check both voltage components and its magnitude before division."""
    _finite_complex('voltage', voltage)
    magnitude = math.hypot(voltage.real, voltage.imag)
    if not math.isfinite(magnitude):
        raise PowerFlowError('voltage magnitude became non-finite')
    if magnitude < VOLTAGE_COLLAPSE_GUARD_PU:
        raise PowerFlowError('voltage collapsed below VOLTAGE_COLLAPSE_GUARD_PU')


def solve_voltage(p_pu, q_pu, params):
    """Solve constant-power complex voltage by fixed-point iteration from the source."""
    p_pu = _number('p_pu', p_pu)
    q_pu = _number('q_pu', q_pu)
    power = complex(p_pu, q_pu)
    source = complex(params.source_voltage_pu, 0)
    impedance = complex(
        params.transformer_r_pu + params.feeder_r_pu,
        params.transformer_x_pu + params.feeder_x_pu,
    )
    _finite_complex('series impedance', impedance)
    voltage = source
    for iteration in range(1, params.max_iterations + 1):
        _check_voltage(voltage)
        current = (power / voltage).conjugate()
        _finite_complex('current', current)
        new_voltage = source - impedance * current
        _check_voltage(new_voltage)
        change = new_voltage - voltage
        if math.hypot(change.real, change.imag) < params.tolerance_pu:
            current = (power / new_voltage).conjugate()
            _finite_complex('final current', current)
            current_pu = math.hypot(current.real, current.imag)
            loading_pct = 100 * current_pu
            if not (math.isfinite(current_pu) and math.isfinite(loading_pct)):
                raise PowerFlowError('current magnitude or loading_pct became non-finite')
            return PowerFlowResult(
                abs(new_voltage), current_pu, loading_pct, p_pu, q_pu, iteration
            )
        voltage = new_voltage
    raise PowerFlowError(f'voltage did not converge within {params.max_iterations} iterations')


def simulate_step(base_kw, ev_kw, pv_kw, params, bess_kw=0.0):
    """Calculate connection demand and solve one independent power-flow step."""
    p_pu, q_pu = net_complex_power_pu(base_kw, ev_kw, pv_kw, params, bess_kw)
    return solve_voltage(p_pu, q_pu, params)

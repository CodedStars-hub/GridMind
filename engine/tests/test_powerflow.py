"""Check real-config voltage solutions against fixed hand references."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from gridmind_engine.powerflow import (
    PowerFlowError, net_complex_power_pu, powerflow_params_from_config,
    simulate_step, solve_voltage,
)


@pytest.fixture
def config():
    path = Path(__file__).resolve().parents[2] / 'config' / 'transformer.json'
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.fixture
def params(config):
    return powerflow_params_from_config(config)


def test_config_consistency(config, params):
    assert params.transformer_r_pu == pytest.approx(0.012, abs=1e-12)
    assert params.transformer_x_pu == pytest.approx(0.04337, abs=1e-4)
    values = config['parameters']
    assert values['load_loss_w']['value'] / values['no_load_loss_w']['value'] == values['loss_ratio']['value']
    with pytest.raises(FrozenInstanceError):
        params.rated_kva = 500


def test_zero_load(params):
    result = simulate_step(0, 0, 0, params)
    assert result.voltage_pu == pytest.approx(1.0, abs=1e-12)
    assert result.loading_pct == 0
    assert result.current_pu == 0
    assert result.iterations == 1
    with pytest.raises(FrozenInstanceError):
        result.voltage_pu = 0


def test_rated_apparent_power_hand_reference(params):
    result = simulate_step(237.5, 0, 0, params)
    assert result.p_pu == pytest.approx(0.95)
    assert result.q_pu == pytest.approx(0.3122499, abs=1e-7)
    assert result.voltage_pu == pytest.approx(0.9453, abs=0.002)
    assert result.loading_pct == pytest.approx(105.8, abs=0.3)
    assert result.current_pu == pytest.approx(1.05784135484, abs=1e-8)
    assert result.loading_pct == 100 * result.current_pu


def test_small_load_hand_reference(params):
    result = solve_voltage(0.01, 0, params)
    assert result.voltage_pu == pytest.approx(0.99964, abs=2e-6)


def test_export_raises_voltage(params):
    result = simulate_step(0, 0, 50, params)
    assert result.p_pu == pytest.approx(-0.2)
    assert result.q_pu == 0
    assert result.voltage_pu > 1.0
    assert result.voltage_pu == pytest.approx(1.0072, abs=1e-3)


def test_monotonic_load(params):
    results = [simulate_step(load, 0, 0, params) for load in range(0, 301, 25)]
    assert all(left.voltage_pu >= right.voltage_pu for left, right in zip(results, results[1:]))
    assert all(left.loading_pct <= right.loading_pct for left, right in zip(results, results[1:]))


def test_lower_power_factor_lowers_voltage(config, params):
    modified = deepcopy(config)
    modified['parameters']['power_factor_base']['value'] = 0.8
    lower_pf = powerflow_params_from_config(modified)
    assert simulate_step(180, 0, 0, lower_pf).voltage_pu < simulate_step(180, 0, 0, params).voltage_pu


def test_overload_fails_with_powerflow_error(params):
    assert not issubclass(PowerFlowError, ValueError)
    with pytest.raises(PowerFlowError):
        simulate_step(5000, 0, 0, params)


def test_iteration_limit(config):
    config['parameters']['powerflow_max_iterations']['value'] = 1
    params = powerflow_params_from_config(config)
    with pytest.raises(PowerFlowError, match='did not converge'):
        simulate_step(180, 0, 0, params)


def test_voltage_collapse_guard(config):
    config['parameters']['source_voltage_pu']['value'] = 0.05
    params = powerflow_params_from_config(config)
    with pytest.raises(PowerFlowError, match='collapsed'):
        solve_voltage(0, 0, params)


@pytest.mark.parametrize('field, value', [
    ('base_kw', -1), ('ev_kw', -1), ('pv_kw', -1),
    ('base_kw', float('nan')), ('ev_kw', float('inf')),
    ('pv_kw', float('-inf')), ('bess_kw', float('nan')),
])
def test_invalid_power_inputs(params, field, value):
    inputs = dict(base_kw=100, ev_kw=50, pv_kw=30, bess_kw=0)
    inputs[field] = value
    with pytest.raises(ValueError, match=field):
        simulate_step(params=params, **inputs)


@pytest.mark.parametrize('field, value', [
    ('power_factor_base', 0), ('power_factor_ev', 1.1), ('power_factor_pv', 0.9),
    ('rated_kva', None), ('load_loss_w', None), ('feeder_resistance_pu', float('nan')),
    ('source_voltage_pu', float('inf')), ('powerflow_tolerance_pu', 0),
    ('powerflow_max_iterations', 0), ('powerflow_max_iterations', 1.5),
    ('impedance_voltage_pct', 0.5),
])
def test_invalid_config(config, field, value):
    config['parameters'][field]['value'] = value
    with pytest.raises(ValueError, match=field):
        powerflow_params_from_config(config)


def test_missing_config_value(config):
    del config['parameters']['rated_kva']
    with pytest.raises(ValueError, match='rated_kva'):
        powerflow_params_from_config(config)


def test_unity_pv_error_message(config):
    config['parameters']['power_factor_pv']['value'] = 0.9
    with pytest.raises(ValueError, match='only unity-power-factor PV is supported in the MVP'):
        powerflow_params_from_config(config)


def test_battery_changes_only_active_demand(params):
    p, q = net_complex_power_pu(100, 50, 30, params, bess_kw=20)
    assert p == pytest.approx(0.4)
    assert q == pytest.approx(0.1720853742, abs=1e-9)
    reduced_p, reduced_q = net_complex_power_pu(80, 50, 30, params)
    assert p == reduced_p
    assert q > reduced_q  # A real base-load reduction also removes reactive demand.
    baseline = simulate_step(100, 0, 0, params)
    discharge = simulate_step(100, 0, 0, params, bess_kw=50)
    charge = simulate_step(100, 0, 0, params, bess_kw=-50)
    assert discharge.p_pu == pytest.approx(0.2)
    assert discharge.q_pu == baseline.q_pu == charge.q_pu
    assert discharge.voltage_pu > baseline.voltage_pu > charge.voltage_pu


@pytest.mark.parametrize('field', ['p_pu', 'q_pu'])
def test_invalid_direct_solver_inputs(params, field):
    inputs = dict(p_pu=0, q_pu=0)
    inputs[field] = float('nan')
    with pytest.raises(ValueError, match=field):
        solve_voltage(params=params, **inputs)


def test_extreme_solver_values_fail_finitely(params):
    with pytest.raises(PowerFlowError):
        solve_voltage(1e308, 1e308, params)

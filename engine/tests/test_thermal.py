"""Check thermal reference values and exact time-step behavior."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path

import pytest

from gridmind_engine.thermal import (
    ThermalState, initial_state_at_load, steady_state_rises, step,
    thermal_params_from_config,
)


@pytest.fixture
def params():
    path = Path(__file__).resolve().parents[2] / 'config' / 'transformer.json'
    return thermal_params_from_config(json.loads(path.read_text(encoding='utf-8')))


def test_rated_steady_state_and_cold_start(params):
    ultimate = steady_state_rises(1.0, params)
    assert ultimate.top_oil_rise_c == pytest.approx(55)
    assert ultimate.hotspot_rise_over_top_oil_c == pytest.approx(25)
    state = ThermalState(0, 0)
    for _ in range(288):  # 72 hours of 15-minute steps.
        result = step(state, 1.0, 30, 15, params)
        state = result.state
    assert result.hotspot_c == pytest.approx(110, abs=2)


@pytest.mark.parametrize('load, expected', [(0, 43.1), (1.5, 175.2)])
def test_hand_computed_steady_temperatures(params, load, expected):
    state = initial_state_at_load(load, params)
    result = step(state, load, 30, 15, params)
    assert result.hotspot_c == pytest.approx(expected, abs=0.3)
    if load == 0:
        assert state.top_oil_rise_c == pytest.approx(13.1, abs=0.3)
        assert state.hotspot_rise_over_top_oil_c == 0


def test_step_size_independence(params):
    state = initial_state_at_load(0.5, params)
    large = step(state, 1.2, 30, 15, params)
    for _ in range(15):
        small = step(state, 1.2, 30, 1, params)
        state = small.state
    assert small.state.top_oil_rise_c == pytest.approx(large.state.top_oil_rise_c, abs=1e-9, rel=0)
    assert small.state.hotspot_rise_over_top_oil_c == pytest.approx(large.state.hotspot_rise_over_top_oil_c, abs=1e-9, rel=0)
    assert small.hotspot_c == pytest.approx(large.hotspot_c, abs=1e-9, rel=0)


def test_monotonic_relaxation(params):
    state = initial_state_at_load(0.5, params)
    previous = 30 + state.top_oil_rise_c + state.hotspot_rise_over_top_oil_c
    target = initial_state_at_load(1.2, params)
    final = 30 + target.top_oil_rise_c + target.hotspot_rise_over_top_oil_c
    for _ in range(96):
        result = step(state, 1.2, 30, 15, params)
        assert previous < result.hotspot_c <= final
        previous, state = result.hotspot_c, result.state


def test_ambient_changes_absolute_temperatures_only(params):
    state = initial_state_at_load(0.5, params)
    cool = step(state, 1.2, 20, 15, params)
    warm = step(state, 1.2, 40, 15, params)
    assert cool.state == warm.state
    assert warm.top_oil_c - cool.top_oil_c == pytest.approx(20)
    assert warm.hotspot_c - cool.hotspot_c == pytest.approx(20)


@pytest.mark.parametrize('field, value', [
    ('load_pu', -1), ('load_pu', float('nan')), ('load_pu', float('inf')),
    ('dt_min', 0), ('dt_min', float('nan')), ('dt_min', float('inf')),
    ('ambient_c', float('nan')), ('ambient_c', float('inf')),
])
def test_invalid_step_inputs(params, field, value):
    inputs = dict(load_pu=1, ambient_c=30, dt_min=15)
    inputs[field] = value
    with pytest.raises(ValueError, match=field):
        step(ThermalState(0, 0), params=params, **inputs)


@pytest.mark.parametrize('field', [
    'rated_top_oil_rise_c', 'rated_hotspot_rise_over_top_oil_c', 'loss_ratio',
    'oil_exponent', 'winding_exponent', 'oil_time_constant_min', 'winding_time_constant_min',
])
@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_invalid_parameters(params, field, value):
    with pytest.raises(ValueError, match=field):
        replace(params, **{field: value})


def test_real_config_and_frozen_records(params):
    assert (params.rated_top_oil_rise_c, params.rated_hotspot_rise_over_top_oil_c,
            params.loss_ratio, params.oil_exponent, params.winding_exponent,
            params.oil_time_constant_min, params.winding_time_constant_min) == (55, 25, 5, 0.8, 0.8, 180, 5)
    with pytest.raises(FrozenInstanceError):
        params.loss_ratio = 7
    state = ThermalState(0, 0)
    with pytest.raises(FrozenInstanceError):
        state.top_oil_rise_c = 1


def test_extreme_load_is_rejected(params):
    with pytest.raises(ValueError, match='load_pu'):
        steady_state_rises(1e308, params)

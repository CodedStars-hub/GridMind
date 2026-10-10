"""Check fixed aging reference numbers, daily totals and the life display cap."""

from dataclasses import FrozenInstanceError, replace
import json
import math
from pathlib import Path

import pytest

from gridmind_engine.aging import (
    aging_factor, aging_params_from_config, daily_equivalent_aging_hours,
    insulation_life_years,
)


@pytest.fixture
def params():
    path = Path(__file__).resolve().parents[2] / 'config' / 'limits.json'
    return aging_params_from_config(json.loads(path.read_text(encoding='utf-8')))


@pytest.mark.parametrize('temperature, expected', [(110, 1.0), (105, 0.596), (135, 11.02), (140, 17.20)])
def test_hand_computed_aging_factors(params, temperature, expected):
    assert aging_factor(temperature, params) == pytest.approx(expected, rel=0.01)


def test_monotonic_and_finite(params):
    factors = [aging_factor(t, params) for t in range(-40, 301)]
    assert all(math.isfinite(factor) for factor in factors)
    assert all(left < right for left, right in zip(factors, factors[1:]))


def test_reference_day(params):
    assert daily_equivalent_aging_hours([110] * 96, 15, params) == pytest.approx(24, abs=1e-9, rel=0)


@pytest.mark.parametrize('hours, expected', [(24, 20.55), (0, 100), (-1, 100), (1e-300, 100), (5e-324, 100)])
def test_insulation_life_and_cap(params, hours, expected):
    life = insulation_life_years(hours, params)
    assert math.isfinite(life)
    assert life == pytest.approx(expected, abs=0.01)


def test_real_config_and_frozen_parameters(params):
    assert (params.aging_constant, params.aging_reference_kelvin,
            params.normal_insulation_life_hours, params.insulation_life_cap_years) == (15000, 383, 180000, 100)
    with pytest.raises(FrozenInstanceError):
        params.insulation_life_cap_years = 200


@pytest.mark.parametrize('temperature', [float('nan'), float('inf'), float('-inf'), -273, -274])
def test_invalid_hotspot(params, temperature):
    with pytest.raises(ValueError, match='hotspot_c'):
        aging_factor(temperature, params)


@pytest.mark.parametrize('minutes', [0, -1, float('nan'), float('inf')])
def test_invalid_step_minutes(params, minutes):
    with pytest.raises(ValueError, match='step_minutes'):
        daily_equivalent_aging_hours([110], minutes, params)


@pytest.mark.parametrize('hours', [float('nan'), float('inf'), float('-inf')])
def test_invalid_daily_hours(params, hours):
    with pytest.raises(ValueError, match='daily_equivalent_hours'):
        insulation_life_years(hours, params)


@pytest.mark.parametrize('field', ['aging_constant', 'aging_reference_kelvin', 'normal_insulation_life_hours', 'insulation_life_cap_years'])
@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_invalid_parameters(params, field, value):
    with pytest.raises(ValueError, match=field):
        replace(params, **{field: value})


def test_unrepresentable_factor_and_total(params):
    extreme = replace(params, aging_constant=1e308)
    with pytest.raises(ValueError, match='aging_factor'):
        aging_factor(300, extreme)
    with pytest.raises(ValueError, match='daily_equivalent_hours'):
        daily_equivalent_aging_hours([300], 1e308, params)

"""Check exact request types, config-driven choices and battery override errors."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest

from gridmind_engine.validate import (
    BessOverride, InvalidInputError, ValidatedInputs, validate_request,
)


@pytest.fixture
def scenarios():
    path = Path(__file__).resolve().parents[2] / 'config' / 'scenarios.json'
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.fixture
def payload():
    return dict(ev_kw=50, pv_kwp=30, day_type='summer_weekday', load_level='heavy')


def test_valid_request_and_defaults(payload, scenarios):
    result = validate_request(payload, scenarios)
    assert result == ValidatedInputs(50, 30, 'summer_weekday', 'heavy', 'off', None)
    with pytest.raises(FrozenInstanceError):
        result.ev_kw = 100


def test_explicit_auto_and_null_override(payload, scenarios):
    payload.update(bess='auto', bess_override=None)
    assert validate_request(payload, scenarios).bess == 'auto'


@pytest.mark.parametrize('field, value', [
    ('ev_kw', 20), ('ev_kw', '50'), ('ev_kw', True), ('ev_kw', 50.5), ('ev_kw', 50.0),
    ('pv_kwp', -10), ('pv_kwp', False), ('pv_kwp', 30.0),
    ('day_type', 'monday'), ('load_level', 'extreme'), ('bess', 'on'),
])
def test_invalid_scenario_values(payload, scenarios, field, value):
    payload[field] = value
    with pytest.raises(InvalidInputError) as caught:
        validate_request(payload, scenarios)
    assert caught.value.code == 'invalid_input'
    assert caught.value.field == field
    assert str(caught.value) == caught.value.message
    assert 'allowed values' in caught.value.message


def test_unknown_field(payload, scenarios):
    payload['foo'] = 1
    with pytest.raises(InvalidInputError) as caught:
        validate_request(payload, scenarios)
    assert caught.value.field == 'foo'


def test_missing_required_field(payload, scenarios):
    del payload['ev_kw']
    with pytest.raises(InvalidInputError) as caught:
        validate_request(payload, scenarios)
    assert caught.value.field == 'ev_kw'


def test_list_payload(scenarios):
    with pytest.raises(InvalidInputError) as caught:
        validate_request([], scenarios)
    assert caught.value.field == 'payload'


def test_valid_override(payload, scenarios):
    payload['bess_override'] = {'power_kw': 30, 'energy_kwh': 60.0}
    result = validate_request(payload, scenarios)
    assert result.bess_override == BessOverride(30, 60)
    with pytest.raises(FrozenInstanceError):
        result.bess_override.power_kw = 50


@pytest.mark.parametrize('field', ['power_kw', 'energy_kwh'])
def test_invalid_override_numbers(payload, scenarios, field):
    for value in (0, -1, float('nan'), float('inf'), '30', True):
        override = {'power_kw': 30, 'energy_kwh': 60}
        override[field] = value
        payload['bess_override'] = override
        with pytest.raises(InvalidInputError) as caught:
            validate_request(payload, scenarios)
        assert caught.value.field == f'bess_override.{field}'


def test_missing_and_extra_override_keys(payload, scenarios):
    for override, field in [({'power_kw': 30}, 'bess_override.energy_kwh'),
                            ({'power_kw': 30, 'energy_kwh': 60, 'foo': 1}, 'bess_override.foo')]:
        payload['bess_override'] = override
        with pytest.raises(InvalidInputError) as caught:
            validate_request(payload, scenarios)
        assert caught.value.field == field


def test_non_object_override(payload, scenarios):
    payload['bess_override'] = []
    with pytest.raises(InvalidInputError) as caught:
        validate_request(payload, scenarios)
    assert caught.value.field == 'bess_override'


def test_allowed_values_come_from_config(payload, scenarios):
    modified = deepcopy(scenarios)
    modified['parameters']['ev_kw_options']['value'] = [10]
    payload['ev_kw'] = 10
    assert validate_request(payload, modified).ev_kw == 10
    payload['ev_kw'] = 50
    with pytest.raises(InvalidInputError) as caught:
        validate_request(payload, modified)
    assert caught.value.field == 'ev_kw'
    assert '[10]' in caught.value.message

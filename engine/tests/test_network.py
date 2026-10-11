"""Network wiring, shared physics, coincident totals and exact request boundaries."""

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

from gridmind_engine import aging, powerflow, thermal
from gridmind_engine.network import assess_network, transformer_load_series, validate_allocation
from gridmind_engine.profiles import build_load_series, load_config_dir
from gridmind_engine.simulate import simulate_load_series
from gridmind_engine.validate import InvalidInputError, ValidatedInputs


@pytest.fixture
def config():
    return load_config_dir(Path(__file__).resolve().parents[2] / 'config')


def entry(site='S1', kw=50, managed=False, cap=None):
    return dict(site_id=site, kw=kw, managed=managed, cap_fraction=cap)


def test_all_transformers_and_mapping(config):
    result = assess_network({'allocation': [entry('S2', 50), entry('S3', 30)]}, config)
    branches = result['assessment']['transformers']
    assert [t['transformer_id'] for t in branches] == ['T1', 'T2', 'T3', 'T4', 'T5', 'T6']
    assert [t['new_charging_kw'] for t in branches] == [0, 0, 80, 0, 0, 0]
    assert [t['existing_peak_kw'] for t in branches] == [175, 137.5, 175, 137.5, 212.5, 175]
    assert branches[2]['simulation']['series']['ev_kw'][60] == 80
    assert branches[0]['simulation']['series']['ev_kw'] == [0] * 96
    assert set(result) == {'meta', 'assessment'}
    assert set(branches[0]) == {'transformer_id', 'existing_peak_kw', 'new_charging_kw', 'status',
                              'simulation', 'weekend_summary', 'month', 'household', 'hosting'}
    assert all(t['month'] is t['household'] is t['hosting'] is None for t in branches)
    json.dumps(result, allow_nan=False)


def test_profile_selection_and_alignment(config):
    result = assess_network({'allocation': [entry('S1'), entry('S6')]}, config)
    branches = {t['transformer_id']: t for t in result['assessment']['transformers']}
    assert branches['T1']['simulation']['series']['base_kw'][0] == 96.25
    assert branches['T3']['simulation']['series']['base_kw'][0] == 61.25
    assert branches['T5']['simulation']['series']['base_kw'][0] == 110.5425
    assert branches['T1']['simulation']['series']['ev_kw'][60] == 14.375
    assert branches['T4']['simulation']['series']['ev_kw'][60] == 50
    assert branches['T1']['simulation']['series']['ev_kw'][76] == 50
    assert branches['T4']['simulation']['series']['ev_kw'][76] == 37.5
    for branch in branches.values():
        series = branch['simulation']['series']
        assert series['time'] == branches['T1']['simulation']['series']['time']
        assert series['time'][0] == '00:00' and series['time'][-1] == '23:45'
        assert all(len(v) == 96 for v in series.values() if v is not None)
        assert series['pv_kw'] == [0] * 96


def test_coincident_peak_and_energy(config):
    result = assess_network({'allocation': [entry('S1'), entry('S6')]}, config)
    daytime = config['ev_daytime_profile']['parameters']['summer_weekday']['value']
    evening = config['ev_profile']['parameters']['summer_weekday']['value']
    expected = [50 * (a + b) for a, b in zip(daytime, evening)]
    totals = result['assessment']['totals']
    assert totals['served_kw_peak'] == round(max(expected), 4)
    assert totals['served_kw_peak'] < 100  # The two individual peaks do not coincide.
    assert totals['served_energy_kwh_per_day'] == round(math.fsum(expected) / 4, 4)
    branches = result['assessment']['transformers']
    assert totals['transformers_in_violation'] == sum(t['status'] != 'healthy' for t in branches)
    assert totals['worst_hotspot_c'] == max(max(t['simulation']['summary']['peak_hotspot_c'],
                                               t['weekend_summary']['peak_hotspot_c']) for t in branches)
    assert totals['life_consumed_days_per_month'] is None
    assert totals['worst_min_voltage_v'] is None


def test_deterministic_and_pure(config):
    payload = {'allocation': [entry('S1', 150), entry('S2', 120)]}
    saved_config, saved_payload = deepcopy(config), deepcopy(payload)
    first = assess_network(payload, config)
    assert first == assess_network(payload, config)
    assert config == saved_config and payload == saved_payload
    first['meta']['inputs']['allocation'][0]['kw'] = 0
    assert payload == saved_payload


def test_shared_physics_oracle_and_weekend(config):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][2]
    sites = config['neighbourhood']['parameters']['sites']['value']
    allocation = [entry('S2', 50), entry('S3', 30)]
    branch = assess_network({'allocation': allocation}, config)['assessment']['transformers'][2]
    loads, echo = transformer_load_series(transformer, allocation, sites, 'summer_weekday', config)
    flow_params = powerflow.powerflow_params_from_config(config['transformer'])
    thermal_params = thermal.thermal_params_from_config(config['transformer'])
    aging_params = aging.aging_params_from_config(config['limits'])
    first = powerflow.simulate_step(loads.base_kw[0], loads.ev_kw[0], loads.pv_kw[0], flow_params)
    state = thermal.initial_state_at_load(first.current_pu, thermal_params)
    for daily_pass in range(2):
        for i in range(96):
            flow = powerflow.simulate_step(loads.base_kw[i], loads.ev_kw[i], loads.pv_kw[i], flow_params)
            temperatures = thermal.step(state, flow.current_pu, loads.ambient_c[i], 15, thermal_params)
            state = temperatures.state
            if daily_pass == 1:
                series = branch['simulation']['series']
                assert series['voltage_pu'][i] == round(flow.voltage_pu, 4)
                assert series['loading_pct'][i] == round(flow.loading_pct, 4)
                assert series['hotspot_c'][i] == round(temperatures.hotspot_c, 4)
                assert series['aging_factor'][i] == round(aging.aging_factor(temperatures.hotspot_c, aging_params), 4)
    weekend, echo = transformer_load_series(transformer, allocation, sites, 'weekend', config)
    assert branch['weekend_summary'] == simulate_load_series(weekend, config, echo)['summary']


def test_status_worst_day_and_thresholds(config):
    from gridmind_engine.network import _status
    limits = config['limits']
    assert _status({'alerts': [], 'summary': {'peak_loading_pct': 100}}, limits) == 'healthy'
    assert _status({'alerts': [], 'summary': {'peak_loading_pct': 100.0001}}, limits) == 'overloaded'
    assert _status({'alerts': [{'type': 'voltage_low', 'severity': 'warning'}],
                    'summary': {'peak_loading_pct': 90}}, limits) == 'watch'
    assert _status({'alerts': [{'type': 'hotspot_critical', 'severity': 'critical'}],
                    'summary': {'peak_loading_pct': 90}}, limits) == 'overloaded'
    result = assess_network({'allocation': [entry('S1', 150)]}, config)
    assert result['assessment']['transformers'][3]['status'] == 'overloaded'


def test_managed_charging_hand_case(config):
    # Flat full-load profile: 80 kW cap, no headroom anywhere, so 20% is unserved.
    config['ev_daytime_profile']['parameters']['summer_weekday']['value'] = [1] * 96
    result = assess_network({'allocation': [entry('S1', 100, True, .8)]}, config)
    series = result['assessment']['transformers'][3]['simulation']['series']['ev_kw']
    assert series == [80] * 96
    assert result['assessment']['totals']['served_kw_peak'] == 80
    assert result['assessment']['totals']['served_energy_kwh_per_day'] == 1920
    # One full-load quarter hour clipped from 100 to 80; 20 kW-samples moved to 00:00.
    config['ev_daytime_profile']['parameters']['summer_weekday']['value'] = [0] * 96
    config['ev_daytime_profile']['parameters']['summer_weekday']['value'][60] = 1
    result = assess_network({'allocation': [entry('S1', 100, True, .8)]}, config)
    series = result['assessment']['transformers'][3]['simulation']['series']['ev_kw']
    assert series[0] == 20 and series[60] == 80
    assert sum(series) == 100
    assert result['assessment']['totals']['served_energy_kwh_per_day'] == 25


def test_empty_zero_and_capacity_boundaries(config):
    empty = assess_network({'allocation': []}, config)
    zero = assess_network({'allocation': [entry('S1', 0)]}, config)
    assert empty['assessment'] == zero['assessment']
    assert empty['assessment']['totals']['served_kw_peak'] == 0
    assert validate_allocation({'allocation': [entry('S1', 150)]}, config)[0]['kw'] == 150


@pytest.mark.parametrize('payload,field', [
    ([], 'payload'), ({}, 'allocation'), ({'allocation': None}, 'allocation'),
    ({'allocation': [], 'extra': 1}, 'extra'),
    ({'allocation': [None]}, 'allocation[0]'),
    ({'allocation': [entry('unknown')]}, 'allocation[0].site_id'),
    ({'allocation': [entry(), entry()]}, 'allocation[1].site_id'),
    ({'allocation': [entry(kw=-10)]}, 'allocation[0].kw'),
    ({'allocation': [entry(kw=160)]}, 'allocation[0].kw'),
    ({'allocation': [entry(kw=55)]}, 'allocation[0].kw'),
    ({'allocation': [entry(kw=True)]}, 'allocation[0].kw'),
    ({'allocation': [entry(kw=50.0)]}, 'allocation[0].kw'),
    ({'allocation': [entry(kw=float('nan'))]}, 'allocation[0].kw'),
    ({'allocation': [entry(kw=float('inf'))]}, 'allocation[0].kw'),
    ({'allocation': [entry(managed='yes')]}, 'allocation[0].managed'),
    ({'allocation': [entry(cap=.8)]}, 'allocation[0].cap_fraction'),
    ({'allocation': [entry(managed=True, cap=.7)]}, 'allocation[0].cap_fraction'),
    ({'allocation': [entry(managed=True, cap=True)]}, 'allocation[0].cap_fraction'),
    ({'allocation': [dict(site_id='S1', kw=50, managed=False)]}, 'allocation[0].cap_fraction'),
    ({'allocation': [dict(entry(), unknown=1)]}, 'allocation[0].unknown'),
])
def test_invalid_allocation(config, payload, field):
    with pytest.raises(InvalidInputError) as caught:
        assess_network(payload, config)
    assert caught.value.field == field


def test_invalid_config_and_failure_propagation(config, monkeypatch):
    modified = deepcopy(config)
    modified['neighbourhood']['parameters']['sites']['value'][0]['transformer_id'] = 'missing'
    with pytest.raises(ValueError, match='transformer_id'):
        assess_network({'allocation': []}, modified)
    modified = deepcopy(config)
    modified['base_load_commercial_profile']['parameters']['summer_weekday']['value'][0] = float('nan')
    with pytest.raises(ValueError, match='sample'):
        assess_network({'allocation': []}, modified)
    from gridmind_engine import network
    def fail(*args):
        raise powerflow.PowerFlowError('failed branch')
    monkeypatch.setattr(network, 'simulate_load_series', fail)
    with pytest.raises(powerflow.PowerFlowError, match='failed branch'):
        assess_network({'allocation': []}, config)


def test_config_rating_and_feeder_used(config):
    original = assess_network({'allocation': []}, config)
    modified = deepcopy(config)
    modified['transformer']['parameters']['rated_kva']['value'] = 200
    modified['transformer']['parameters']['feeder_resistance_pu']['value'] = .03
    changed = assess_network({'allocation': []}, modified)
    assert changed['assessment']['transformers'][0]['existing_peak_kw'] == 140
    assert changed['assessment']['transformers'][0]['simulation']['series']['voltage_pu'] != original['assessment']['transformers'][0]['simulation']['series']['voltage_pu']


@pytest.mark.parametrize('field,value', [
    ('time', ('01:00',) * 96), ('base_kw', (1,) * 95),
    ('ev_kw', (float('nan'),) * 96), ('pv_kw', (-1,) * 96),
    ('ambient_c', (True,) * 96),
])
def test_shared_series_validation(config, field, value):
    inputs = ValidatedInputs(50, 30, 'summer_weekday', 'heavy', 'off', None)
    loads = replace(build_load_series(inputs, config), **{field: value})
    with pytest.raises(ValueError, match=field):
        simulate_load_series(loads, config, {})


def test_missing_profile_and_invalid_selector(config):
    modified = deepcopy(config)
    del modified['base_load_commercial_profile']
    with pytest.raises(ValueError, match='base_load_commercial_profile.json'):
        assess_network({'allocation': []}, modified)
    modified = deepcopy(config)
    modified['neighbourhood']['parameters']['transformers']['value'][0]['archetype'] = []
    with pytest.raises(ValueError, match='archetype'):
        assess_network({'allocation': []}, modified)


def test_weekend_status_is_not_discarded(config, monkeypatch):
    from gridmind_engine import network
    real = network.simulate_load_series
    def weekend_violation(loads, config, echo):
        result = real(loads, config, echo)
        if echo['day_type'] == 'weekend':
            result['alerts'] = [dict(type='hotspot_critical', severity='critical')]
        return result
    monkeypatch.setattr(network, 'simulate_load_series', weekend_violation)
    result = assess_network({'allocation': []}, config)
    assert all(t['status'] == 'overloaded' for t in result['assessment']['transformers'])

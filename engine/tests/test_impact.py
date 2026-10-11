"""Analytical aging, value and exposure checks plus shared-engine regressions."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from gridmind_engine.cost import compare_economic, economic_aging_proxy
from gridmind_engine.household import voltage_exposure
from gridmind_engine.impact import assess_impact, compare_network_impacts
from gridmind_engine.life import compare_life, equivalent_aging_hours
from gridmind_engine.network import assess_network, assess_network_with_precision
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import simulate_load_series, simulate_load_series_with_precision
from gridmind_engine.network import transformer_load_series

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return load_config_dir(ROOT / 'config')


def daily(factor=1, voltage=1, hotspot=110):
    return dict(time=[f'{i // 4:02d}:{i % 4 * 15:02d}' for i in range(96)],
                aging_factor=[factor] * 96, voltage_pu=[voltage] * 96,
                hotspot_c=[hotspot] * 96, loading_pct=[50] * 96)


def days(factor=1, voltage=1):
    return {'summer_weekday': daily(factor, voltage), 'weekend': daily(factor, voltage)}


def records(config, factor=1, voltage=1):
    return {t['id']: days(factor, voltage) for t in config['neighbourhood']['parameters']['transformers']['value']}


def test_reference_and_accelerated_aging():
    assert equivalent_aging_hours([1] * 96, 15) == 24
    assert equivalent_aging_hours([2] * 96, 15) == 48
    assert equivalent_aging_hours([1] * 4, 15) == 1


def test_identical_and_negative_comparisons():
    same = compare_life(days(), days(), 15, {'summer_weekday': 22, 'weekend': 8}, 365)
    assert same['month']['additional_equivalent_aging_hours'] == 0
    assert same['month']['aging_change_pct'] == 0
    negative = compare_life(days(2), days(1), 15, {'summer_weekday': 22, 'weekend': 8}, 365)
    assert negative['days']['summer_weekday']['additional_equivalent_aging_hours'] == -24
    assert negative['month']['additional_equivalent_aging_hours'] == -720
    assert negative['month']['additional_reference_equivalent_years'] == pytest.approx(-720 / 8760)
    assert negative['month']['aging_change_pct'] == -50


def test_month_weighting_and_ratios():
    baseline = days()
    ev = days(2)
    ev['weekend'] = daily(3)
    result = compare_life(baseline, ev, 15, {'summer_weekday': 22, 'weekend': 8}, 365)
    assert result['days']['summer_weekday']['baseline_aging_ratio'] == 1
    assert result['days']['summer_weekday']['ev_aging_ratio'] == 2
    assert result['month']['calendar_days'] == 30
    assert result['month']['baseline_equivalent_aging_hours'] == 720
    assert result['month']['ev_equivalent_aging_hours'] == 1632  # 22*48 + 8*72
    assert result['month']['additional_equivalent_aging_hours'] == 912
    assert result['month']['ev_aging_ratio'] == pytest.approx(1632 / 720)
    assert result['month']['additional_reference_equivalent_years'] == pytest.approx(912 / 8760)


def test_zero_baseline_and_full_precision():
    zero = compare_life(days(0), days(1), 15, {'summer_weekday': 22, 'weekend': 8}, 365)
    assert zero['month']['aging_change_pct'] is None
    assert zero['days']['summer_weekday']['aging_change_pct'] is None
    assert zero['month']['additional_equivalent_aging_hours'] == 720
    tiny = equivalent_aging_hours([.000049] * 96, 15)
    assert tiny == pytest.approx(.001176)
    assert tiny > 0  # Rounding FAA first would erase this aging.


def test_economic_formula_signed_and_zero_value():
    assert economic_aging_proxy(180, 180000, 550000) == 550
    assert economic_aging_proxy(-180, 180000, 550000) == -550
    assert economic_aging_proxy(180, 180000, 0) == 0
    result = compare_economic(dict(baseline_equivalent_aging_hours=360,
                                  ev_equivalent_aging_hours=180), 180000, 550000)
    assert result['baseline_aging_proxy_inr'] == 1100
    assert result['ev_aging_proxy_inr'] == 550
    assert result['additional_aging_proxy_inr'] == -550
    assert result['additional_reference_life_fraction'] == -.001


def test_voltage_counts_duration_and_proxy():
    # Strict limits: equality at .95 and 1.05 is not a violation.
    result = voltage_exposure([.95, .94, .93, 1, 1.06, 1.05, .94, 1], 15, .95, 1.05, 230, 10, residential=True)
    assert result['min_voltage_pu'] == .93
    assert result['min_voltage_v'] == pytest.approx(213.9)
    assert result['violation_steps'] == 4
    assert result['violation_intervals'] == 3
    assert result['voltage_low_steps'] == 3
    assert result['voltage_high_steps'] == 1
    assert result['hours_outside_limits'] == 1
    assert result['hours_below_limit'] == .75
    assert result['outside_limits_pct'] == 50
    assert result['maximum_undervoltage_deviation_pu'] == pytest.approx(.02)
    assert result['connections_potentially_exposed'] == 10
    assert result['connection_hours'] == 10
    assert result['residential_connections_potentially_exposed_proxy'] == 10
    assert result['proxy'] is True


def test_voltage_events_no_midnight_join_and_step_duration():
    result = voltage_exposure([.9, 1, 1, .9], 30, .95, 1.05, 230, 5)
    assert result['violation_intervals'] == 2
    assert result['hours_outside_limits'] == 1
    assert result['connection_hours'] == 5
    assert result['residential_connections_proxy'] is None


def test_unknown_connection_counts():
    result = voltage_exposure([.9, 1], 15, .95, 1.05, 230, None, residential=True)
    assert result['connections'] is None
    assert result['connections_potentially_exposed'] is None
    assert result['connection_hours'] is None
    assert result['hours_outside_limits'] == .25


def test_network_totals_and_no_duplicate_connections(config):
    baseline = records(config)
    ev = records(config, 2, .9)
    result = compare_network_impacts(baseline, ev, config)
    totals = result['totals']
    assert totals['additional_equivalent_aging_hours_per_month'] == 4320  # six * 720
    assert totals['additional_aging_proxy_inr_per_month'] == 13200
    assert totals['ev_connections_potentially_exposed_per_month'] == 765
    assert totals['ev_connection_hours_per_month'] == 550800  # 765 * 30 * 24
    assert totals['ev_residential_connections_potentially_exposed_proxy_per_month'] == 540
    assert totals['ev_residential_connection_hours_proxy_per_month'] == 388800
    assert [t['transformer_id'] for t in result['transformers']] == ['T1', 'T2', 'T3', 'T4', 'T5', 'T6']


def test_missing_counts_transparent_and_zero_baseline(config):
    baseline, ev = records(config, 0), records(config, 1, .9)
    del config['neighbourhood']['parameters']['transformers']['value'][0]['connections']
    result = compare_network_impacts(baseline, ev, config)
    assert result['transformers'][0]['life']['month']['aging_change_pct'] is None
    assert result['totals']['ev_connection_hours_per_month'] is None
    assert result['totals']['ev_connections_potentially_exposed_per_month'] is None
    assert result['totals']['ev_residential_connection_hours_proxy_per_month'] is None


def test_unrounded_network_reductions_and_signed_values(config):
    result = compare_network_impacts(records(config, 2), records(config, 1), config)
    assert result['totals']['additional_aging_proxy_inr_per_month'] == -13200
    assert result['totals']['additional_equivalent_aging_hours_per_month'] == -4320


def test_shared_precision_preserves_m7_and_is_detached(config):
    payload = {'allocation': [dict(site_id='S1', kw=150, managed=False, cap_fraction=None)]}
    result, raw = assess_network_with_precision(payload, config)
    assert result == assess_network(payload, config)
    branch = result['assessment']['transformers'][3]
    assert raw['T4']['summer_weekday']['hotspot_c'] != branch['simulation']['series']['hotspot_c']
    raw['T4']['summer_weekday']['hotspot_c'][0] = -1
    assert branch['simulation']['series']['hotspot_c'][0] > 0


def test_precision_daily_matches_shared_result(config):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][0]
    sites = config['neighbourhood']['parameters']['sites']['value']
    loads, echo = transformer_load_series(transformer, [], sites, 'summer_weekday', config)
    result, raw = simulate_load_series_with_precision(loads, config, echo)
    assert result == simulate_load_series(loads, config, echo)
    assert all(result['series']['aging_factor'][i] == round(raw['aging_factor'][i], 4) for i in range(96))


def test_orchestration_baseline_ev_purity_and_presentation(config):
    payload = {'allocation': [dict(site_id='S2', kw=50, managed=False, cap_fraction=None),
                              dict(site_id='S3', kw=30, managed=False, cap_fraction=None)]}
    saved_config, saved_payload = deepcopy(config), deepcopy(payload)
    result = assess_impact(payload, config)
    assert result == assess_impact(payload, config)
    assert config == saved_config and payload == saved_payload
    assert result['baseline'] == assess_network({'allocation': []}, config)
    assert result['ev'] == assess_network(payload, config)
    branches = result['impact']['transformers']
    assert all(t['life']['month']['additional_equivalent_aging_hours'] == 0 for t in branches if t['transformer_id'] != 'T3')
    assert branches[2]['life']['month']['additional_equivalent_aging_hours'] > 0
    assert type(result['impact']['totals']['additional_aging_proxy_inr_per_month']) is int
    assert result['limitations'] and all(a['note'] for a in result['assumptions'])
    json.dumps(result, allow_nan=False)


def test_no_allocation_zero_increment(config):
    result = assess_impact({'allocation': []}, config)
    assert result['baseline'] == result['ev']
    assert result['impact']['totals']['additional_equivalent_aging_hours_per_month'] == 0
    assert result['impact']['totals']['additional_aging_proxy_inr_per_month'] == 0
    assert result['impact']['totals']['additional_connection_hours_per_month'] == 0


@pytest.mark.parametrize('value', [None, -1, True, float('nan'), float('inf')])
def test_invalid_replacement_value(config, value):
    config['costs']['parameters']['transformer_upgrade_cost_inr']['value'] = value
    with pytest.raises(ValueError, match='transformer_upgrade_cost_inr'):
        assess_impact({'allocation': []}, config)


def test_missing_cost_rejected(config):
    del config['costs']['parameters']['transformer_upgrade_cost_inr']
    with pytest.raises(ValueError, match='transformer_upgrade_cost_inr'):
        assess_impact({'allocation': []}, config)


@pytest.mark.parametrize('value', [-1, True, float('nan'), float('inf')])
def test_invalid_aging_factors(value):
    with pytest.raises(ValueError, match='aging_factors'):
        equivalent_aging_hours([value], 15)


@pytest.mark.parametrize('value', [0, -1, True, float('nan'), float('inf')])
def test_invalid_step_duration(value):
    with pytest.raises(ValueError, match='step_minutes'):
        equivalent_aging_hours([1], value)


@pytest.mark.parametrize('field,value', [
    ('reference_life_hours', 0), ('reference_life_hours', float('nan')),
    ('replacement_value_inr', -1), ('replacement_value_inr', float('inf')),
    ('equivalent_hours', float('nan')),
])
def test_invalid_economic_inputs(field, value):
    params = dict(equivalent_hours=24, reference_life_hours=180000, replacement_value_inr=550000)
    params[field] = value
    with pytest.raises(ValueError, match=field):
        economic_aging_proxy(**params)


@pytest.mark.parametrize('changes,field', [
    ({'voltage_pu': [float('nan')]}, 'voltage_pu'),
    ({'voltage_pu': [0]}, 'voltage_pu'),
    ({'voltage_pu': []}, 'voltage_pu'),
    ({'voltage_min_pu': 1.1}, 'voltage_min_pu'),
    ({'voltage_max_pu': float('inf')}, 'voltage_max_pu'),
    ({'connections': -1}, 'connections'),
    ({'connections': True}, 'connections'),
    ({'connections': 1.5}, 'connections'),
])
def test_invalid_voltage_inputs(changes, field):
    params = dict(voltage_pu=[1], step_minutes=15, voltage_min_pu=.95,
                  voltage_max_pu=1.05, nominal_voltage_v=230, connections=10)
    params.update(changes)
    with pytest.raises(ValueError, match=field):
        voltage_exposure(**params)


def test_inconsistent_identity_length_and_alignment(config):
    baseline, ev = records(config), records(config)
    del ev['T6']
    with pytest.raises(ValueError, match='identities'):
        compare_network_impacts(baseline, ev, config)
    ev = records(config)
    ev['T1']['weekend']['aging_factor'].pop()
    with pytest.raises(ValueError, match='length'):
        compare_network_impacts(baseline, ev, config)
    ev = records(config)
    ev['T1']['weekend']['time'][0] = '00:15'
    with pytest.raises(ValueError, match='time axis'):
        compare_network_impacts(baseline, ev, config)


def test_overflow_rejected_and_fixture_unchanged():
    with pytest.raises(ValueError, match='equivalent_aging_hours'):
        equivalent_aging_hours([1e308] * 96, 15)
    path = 'engine/tests/fixtures/simulation_golden.json'
    assert (ROOT / path).read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:' + path])


def test_counted_once_across_two_sites_and_both_days(config):
    payload = {'allocation': [dict(site_id='S2', kw=120, managed=False, cap_fraction=None),
                              dict(site_id='S3', kw=60, managed=False, cap_fraction=None)]}
    result = assess_impact(payload, config)
    totals = result['impact']['totals']
    assert totals['ev_connections_potentially_exposed_per_month'] == 90
    assert totals['ev_residential_connections_potentially_exposed_proxy_per_month'] == 0


@pytest.mark.parametrize('stem,key,value', [
    ('limits', 'normal_insulation_life_hours', 0),
    ('limits', 'calendar_days_per_year', -1),
    ('limits', 'voltage_min_pu', float('nan')),
    ('neighbourhood', 'nominal_home_voltage_v', 0),
    ('neighbourhood', 'month_weekday_count', True),
    ('neighbourhood', 'month_weekend_count', -1),
])
def test_invalid_config_settings(config, stem, key, value):
    config[stem]['parameters'][key]['value'] = value
    with pytest.raises(ValueError, match=key):
        assess_impact({'allocation': []}, config)


def test_partial_day_not_extrapolated_as_full_day():
    partial = {'summer_weekday': {'aging_factor': [1] * 4, 'hotspot_c': [110] * 4}}
    with pytest.raises(ValueError, match='full calendar day'):
        compare_life(partial, partial, 15, {'summer_weekday': 30}, 365)

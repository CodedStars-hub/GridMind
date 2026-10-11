"""Analytical feasibility boundaries and independent-branch capacity searches."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from gridmind_engine import hosting, hosting_feasibility, powerflow, thermal
from gridmind_engine.hosting import assess_hosting, grid_search, search_settings
from gridmind_engine.hosting_feasibility import (
    DAYS, candidate_load_series, check_operating_series, evaluate_candidate,
)
from gridmind_engine.network import assess_network_with_precision
from gridmind_engine.profiles import load_config_dir

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return load_config_dir(ROOT / 'config')


def series(voltage=1, loading=50, hotspot=60):
    return dict(time=[f'{i // 4:02d}:{i % 4 * 15:02d}' for i in range(96)],
                voltage_pu=[voltage] * 96, loading_pct=[loading] * 96,
                hotspot_c=[hotspot] * 96)


def candidate(kw, feasible=True, cap=None):
    return dict(candidate_kw=kw, feasible=feasible, cap_fraction=cap)


@pytest.mark.parametrize('voltage,loading,hotspot,expected', [
    (.95, 100, 110, []), (1.05, 100, 110, []),
    (.949999, 50, 60, ['voltage_min_pu']),
    (1.050001, 50, 60, ['voltage_max_pu']),
    (1, 100.000001, 60, ['loading_info_pct']),
    (1, 50, 110.000001, ['hotspot_warning_c']),
    (1, 50, 141, ['hotspot_warning_c', 'hotspot_critical_c']),
    (.94, 101, 111, ['voltage_min_pu', 'loading_info_pct', 'hotspot_warning_c']),
])
def test_operating_boundaries_full_precision(config, voltage, loading, hotspot, expected):
    checked = check_operating_series(series(voltage, loading, hotspot), config)
    assert checked['violations'] == expected
    assert [m['constraint'] for m in checked['margins'] if m['margin'] < 0] == expected


@pytest.mark.parametrize('threshold,expected,next_kw', [(0, 0, 10), (9, 0, 10), (20, 20, 30), (30, 30, None)])
def test_analytical_grid(threshold, expected, next_kw):
    visited = []
    def evaluate(kw):
        visited.append(kw)
        return candidate(kw, kw <= threshold)
    result, count = grid_search(evaluate, 30, 10, candidate(0))
    assert result['selected']['candidate_kw'] == expected
    assert visited == [10, 20, 30] and count == 3
    assert result['bound_reached'] == (expected == 30)
    assert (result['next_candidate']['candidate_kw'] if result['next_candidate'] else None) == next_kw
    if result['next_candidate']:
        assert not result['next_candidate']['feasible']


def test_nonmonotonic_grid_is_not_truncated():
    result, count = grid_search(lambda kw: candidate(kw, kw in (10, 30)), 40, 10, candidate(0))
    assert count == 4
    assert result['selected']['candidate_kw'] == 30
    assert not result['next_candidate']['feasible']


def test_violating_baseline_does_not_become_safe_zero():
    def unexpected(kw):
        pytest.fail('No positive evaluation is permitted on an infeasible baseline')
    result, used = grid_search(unexpected, 30, 10, candidate(0, False))
    assert result == dict(selected=None, next_candidate=None, bound_reached=False)
    assert used == 0


@pytest.mark.parametrize('constraint', ['voltage_min_pu', 'loading_info_pct', 'hotspot_warning_c'])
def test_search_limiting_constraints(config, constraint):
    # Independent synthetic domain: first increment hits equality, second violates.
    def evaluate(kw):
        values = series(voltage=.96 - kw / 1000) if constraint == 'voltage_min_pu' else (
            series(loading=90 + kw) if constraint == 'loading_info_pct' else series(hotspot=100 + kw))
        checked = check_operating_series(values, config)
        return dict(candidate_kw=kw, feasible=not checked['violations'], **checked)
    result, _ = grid_search(evaluate, 30, 10, candidate(0))
    assert result['selected']['candidate_kw'] == 10
    assert result['next_candidate']['violations'] == [constraint]


@pytest.mark.parametrize('key,value', [
    ('hosting_search_max_kw', -1), ('hosting_search_max_kw', float('inf')),
    ('hosting_search_max_kw', 25), ('hosting_search_max_kw', True),
    ('allocation_block_kw', 0), ('allocation_block_kw', -1),
    ('allocation_block_kw', float('nan')), ('allocation_block_kw', 2.5),
    ('hosting_max_evaluations', 0), ('hosting_max_evaluations', 150),
    ('hosting_max_evaluations', 1.5), ('hosting_max_evaluations', True),
    ('managed_cap_fractions', [.8, .8]), ('managed_cap_fractions', [1]),
    ('managed_cap_fractions', [0]), ('managed_cap_fractions', [float('nan')]),
    ('managed_cap_fractions', []), ('managed_cap_fractions', [.3, .8]),
    ('min_served_energy_pct_for_managed', 101),
    ('managed_offpeak_start_hour', 24), ('managed_offpeak_end_hour', 23),
])
def test_invalid_search_configuration(config, key, value):
    config['neighbourhood']['parameters'][key]['value'] = value
    with pytest.raises(ValueError, match=key if key != 'managed_offpeak_end_hour' else 'offpeak'):
        search_settings(config)


def test_missing_budget_and_zero_bound(config):
    del config['neighbourhood']['parameters']['hosting_max_evaluations']
    with pytest.raises(ValueError, match='hosting_max_evaluations'):
        search_settings(config)
    config['neighbourhood']['parameters']['hosting_max_evaluations'] = {'value': 1}
    config['neighbourhood']['parameters']['hosting_search_max_kw']['value'] = 0
    assert search_settings(config)[:3] == (0, 10, 1)
    result, used = grid_search(lambda kw: pytest.fail('zero bound'), 0, 10, candidate(0))
    assert result['bound_reached'] and used == 0


@pytest.mark.parametrize('field,value', [('voltage_pu', float('nan')), ('loading_pct', -1), ('hotspot_c', float('inf'))])
def test_invalid_series(config, field, value):
    raw = series()
    raw[field][0] = value
    with pytest.raises(ValueError, match=field):
        check_operating_series(raw, config)


def test_alignment_length_and_limits(config):
    raw = series()
    raw['time'][0] = '00:15'
    with pytest.raises(ValueError, match='time axis'):
        check_operating_series(raw, config)
    raw = series()
    raw['voltage_pu'].pop()
    with pytest.raises(ValueError, match='length'):
        check_operating_series(raw, config)
    config['limits']['parameters']['voltage_min_pu']['value'] = 1.06
    with pytest.raises(ValueError, match='voltage_min_pu'):
        check_operating_series(series(), config)


def test_profile_scaling_and_managed_peak_are_distinct(config):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][0]
    loads, _ = candidate_load_series(transformer, 50, None, 'summer_weekday', config)
    assert max(loads.ev_kw) == 50 and loads.ev_kw[76] == 50
    assert loads.ev_kw[0] == 1  # .02 normalized shape times 50 kW
    assert loads.base_kw[84] == 175 and loads.pv_kw == (0,) * 96
    managed, _ = candidate_load_series(transformer, 50, .8, 'summer_weekday', config)
    assert max(managed.ev_kw) == 40
    assert sum(managed.ev_kw) == pytest.approx(sum(loads.ev_kw))
    assert len(loads.time) == 96 and loads.time[-1] == '23:45'


def test_managed_energy_constraint_on_each_day_and_equality(config):
    # A constant full-output profile has no cap headroom, even overnight.
    # 10 kW capped at .5 serves exactly 5 * 24 = 120 kWh of 240 kWh.
    transformer = config['neighbourhood']['parameters']['transformers']['value'][1]
    config['neighbourhood']['parameters']['managed_cap_fractions']['value'] = [.5]
    for day in DAYS:
        config['ev_profile']['parameters'][day]['value'] = [1] * 96
    config['neighbourhood']['parameters']['min_served_energy_pct_for_managed']['value'] = 50
    equal = evaluate_candidate(transformer, 10, config, .5)
    assert equal['feasible']
    assert all(equal['days'][d]['served_energy_kwh'] == 120 for d in DAYS)
    assert all(equal['days'][d]['served_energy_pct'] == 50 for d in DAYS)
    config['neighbourhood']['parameters']['min_served_energy_pct_for_managed']['value'] = 50.000001
    rejected = evaluate_candidate(transformer, 10, config, .5)
    assert not rejected['feasible']
    assert rejected['violations'] == [
        dict(scenario=d, constraint='min_served_energy_pct_for_managed') for d in DAYS]


def test_profile_peak_and_missing_profile_rejected(config):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][0]
    config['ev_profile']['parameters']['summer_weekday']['value'] = [.5] * 96
    with pytest.raises(ValueError, match='peak at one'):
        evaluate_candidate(transformer, 10, config)
    del config['ev_profile']
    with pytest.raises(ValueError, match='ev_profile.json'):
        evaluate_candidate(transformer, 10, config)


def test_managed_ties_and_budget_accounting(config, monkeypatch):
    config['neighbourhood']['parameters']['hosting_search_max_kw']['value'] = 10
    _, raw = assess_network_with_precision({'allocation': []}, config)
    def evaluate(transformer, kw, config, cap_fraction=None, **kwargs):
        return dict(candidate_kw=kw, cap_fraction=cap_fraction, feasible=True,
                    days={d: {'served_energy_kwh': 1 if cap_fraction == .8 else 2} for d in DAYS})
    monkeypatch.setattr(hosting, 'evaluate_candidate', evaluate)
    monkeypatch.setattr(hosting, 'assess_network_with_precision', lambda *args: ({}, raw))
    result = assess_hosting(config)
    for item in result['hosting']['transformers']:
        assert item['managed']['selected']['cap_fraction'] == .6
        assert item['hosting'] == dict(unmanaged_kw=10, managed_kw=10)
        assert item['evaluations'] == 6  # baseline plus one point for each of five modes
        assert item['managed']['bound_reached']


def test_transformer_scenario_isolation(config):
    transformers = config['neighbourhood']['parameters']['transformers']['value']
    residential, _ = candidate_load_series(transformers[0], 50, None, 'summer_weekday', config)
    commercial, _ = candidate_load_series(transformers[2], 50, None, 'summer_weekday', config)
    moderate, _ = candidate_load_series(transformers[1], 50, None, 'summer_weekday', config)
    assert commercial.ev_kw[60] == 50 and commercial.base_kw[52] == 175
    assert residential.ev_kw[60] == pytest.approx(14.375, abs=1e-12)
    assert moderate.base_kw[84] == 137.5
    saved = deepcopy(config)
    modified = deepcopy(config)
    modified['neighbourhood']['parameters']['transformers']['value'][1]['load_level'] = 'critical'
    unchanged, _ = candidate_load_series(modified['neighbourhood']['parameters']['transformers']['value'][0],
                                         50, None, 'summer_weekday', modified)
    assert unchanged == residential and config == saved


def test_shared_engine_oracle(config):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][0]
    loads, _ = candidate_load_series(transformer, 50, None, 'summer_weekday', config)
    fp = powerflow.powerflow_params_from_config(config['transformer'])
    tp = thermal.thermal_params_from_config(config['transformer'])
    first = powerflow.simulate_step(loads.base_kw[0], loads.ev_kw[0], 0, fp)
    state = thermal.initial_state_at_load(first.current_pu, tp)
    voltages, loading, hot = [], [], []
    for daily_pass in range(2):
        for b, e, a in zip(loads.base_kw, loads.ev_kw, loads.ambient_c):
            flow = powerflow.simulate_step(b, e, 0, fp)
            temperatures = thermal.step(state, flow.current_pu, a, 15, tp)
            state = temperatures.state
            if daily_pass == 1:
                voltages.append(flow.voltage_pu)
                loading.append(flow.loading_pct)
                hot.append(temperatures.hotspot_c)
    result = evaluate_candidate(transformer, 50, config)
    margins = {m['constraint']: m for m in result['days']['summer_weekday']['margins']}
    assert margins['voltage_min_pu']['value'] == min(voltages)
    assert margins['loading_info_pct']['value'] == max(loading)
    assert margins['hotspot_warning_c']['value'] == max(hot)


def test_solver_failure_is_explicit(config, monkeypatch):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][0]
    def fail(*args):
        raise powerflow.PowerFlowError('synthetic non-convergence')
    monkeypatch.setattr(hosting_feasibility, 'simulate_load_series_with_precision', fail)
    result = evaluate_candidate(transformer, 50, config)
    assert not result['feasible']
    assert result['violations'] == [dict(scenario=d, constraint='convergence_failed') for d in DAYS]
    assert all(not result['days'][d]['margins'] for d in DAYS)


def test_baseline_network_solver_failure_propagates(config, monkeypatch):
    def fail(*args):
        raise powerflow.PowerFlowError('baseline compliance unknown')
    monkeypatch.setattr(hosting, 'assess_network_with_precision', fail)
    with pytest.raises(powerflow.PowerFlowError, match='baseline compliance unknown'):
        assess_hosting(config)


def test_baseline_violation_results(config):
    config['neighbourhood']['parameters']['hosting_search_max_kw']['value'] = 10
    config['limits']['parameters']['voltage_min_pu']['value'] = 1
    result = assess_hosting(config)
    assert result['hosting']['totals']['violating_baselines'] == 6
    for item in result['hosting']['transformers']:
        assert not item['baseline']['feasible'] and item['baseline']['violations']
        assert item['hosting'] == dict(unmanaged_kw=0, managed_kw=0)
        assert item['unmanaged']['selected'] is None
        assert item['evaluations'] == 1


@pytest.fixture(scope='module')
def real_assessment():
    return assess_hosting(load_config_dir(ROOT / 'config'))


def test_all_six_aggregation_and_capacity_feasibility(config, real_assessment):
    items = real_assessment['hosting']['transformers']
    assert [t['transformer_id'] for t in items] == ['T1', 'T2', 'T3', 'T4', 'T5', 'T6']
    totals = real_assessment['hosting']['totals']
    assert totals['transformers_assessed'] == 6
    assert totals['compliant_baselines'] + totals['violating_baselines'] == 6
    assert totals['independent_unmanaged_kw'] == sum(t['hosting']['unmanaged_kw'] for t in items)
    assert totals['positive_unmanaged_capacity'] == sum(t['hosting']['unmanaged_kw'] > 0 for t in items)
    assert any(t['hosting']['unmanaged_kw'] > 0 for t in items)
    assert len({t['hosting']['unmanaged_kw'] for t in items}) > 1
    for transformer, item in zip(config['neighbourhood']['parameters']['transformers']['value'], items):
        for mode in ('unmanaged', 'managed'):
            search = item[mode]
            if search['selected']:
                selected = search['selected']
                assert evaluate_candidate(transformer, selected['candidate_kw'], config,
                                          selected['cap_fraction'])['feasible']
            if search['next_candidate']:
                assert not search['next_candidate']['feasible']
            assert search['bound_reached'] or search['next_candidate'] or not item['baseline']['feasible']
        assert item['evaluations'] <= 151
    assert any('upstream' in text for text in real_assessment['limitations'])
    json.dumps(real_assessment, allow_nan=False)


def test_baseline_matches_m7_precision(config, real_assessment):
    _, raw = assess_network_with_precision({'allocation': []}, config)
    for item in real_assessment['hosting']['transformers']:
        for day in DAYS:
            expected = check_operating_series(raw[item['transformer_id']][day], config)
            assert item['baseline']['days'][day]['violations'] == expected['violations']
    assert real_assessment['hosting']['transformers'][0]['baseline']['feasible']
    assert not real_assessment['hosting']['transformers'][4]['baseline']['feasible']


def test_determinism_and_purity(config):
    # Smaller configured domain tests orchestration, not a new physical limit.
    config['neighbourhood']['parameters']['hosting_search_max_kw']['value'] = 10
    saved = deepcopy(config)
    first = assess_hosting(config)
    assert first == assess_hosting(config)
    assert config == saved


@pytest.mark.parametrize('kw', [-1, True, float('nan'), float('inf')])
def test_invalid_candidate(config, kw):
    transformer = config['neighbourhood']['parameters']['transformers']['value'][0]
    with pytest.raises(ValueError, match='candidate_kw'):
        evaluate_candidate(transformer, kw, config)


def test_golden_fixtures_unchanged():
    for name in ('simulation_golden.json', 'network_m7_golden.json'):
        path = 'engine/tests/fixtures/' + name
        assert (ROOT / path).read_bytes() == subprocess.check_output(['git', 'show', 'HEAD:' + path])

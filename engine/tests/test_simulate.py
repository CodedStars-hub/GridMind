"""Check orchestration, rounded contract results and strict alert boundaries."""

from copy import deepcopy
import json
import math
from pathlib import Path

import pytest

from gridmind_engine import __version__, aging, powerflow, thermal
from gridmind_engine.profiles import build_load_series, load_config_dir
from gridmind_engine.simulate import detect_alerts, merge_consecutive_steps, run_simulation, simulate_day
from gridmind_engine.validate import InvalidInputError, validate_request

TOP_KEYS = {'meta', 'series', 'summary', 'alerts', 'verdict', 'bess', 'cost'}
SERIES_KEYS = {'time', 'ambient_c', 'base_kw', 'ev_kw', 'pv_kw', 'net_kw', 'voltage_pu',
               'loading_pct', 'top_oil_c', 'hotspot_c', 'aging_factor', 'bess_kw', 'bess_soc_pct'}
SUMMARY_KEYS = {'min_voltage_pu', 'min_voltage_time', 'peak_voltage_deviation_pu', 'peak_hotspot_c',
                'peak_hotspot_time', 'peak_loading_pct', 'peak_loading_time', 'peak_aging_factor',
                'daily_equivalent_aging_hours', 'insulation_life_years'}


@pytest.fixture
def config():
    return load_config_dir(Path(__file__).resolve().parents[2] / 'config')


def payload(**changes):
    request = dict(ev_kw=50, pv_kwp=30, day_type='summer_weekday', load_level='heavy')
    request.update(changes)
    return request


@pytest.fixture
def result(config):
    return run_simulation(payload(), config)


def test_contract_structure(result):
    assert set(result) == TOP_KEYS
    assert set(result['series']) == SERIES_KEYS
    assert set(result['summary']) == SUMMARY_KEYS
    for key, values in result['series'].items():
        if key in ('bess_kw', 'bess_soc_pct'):
            assert values is None
        else:
            assert len(values) == 96
            if key == 'time':
                assert all(isinstance(value, str) for value in values)
            else:
                assert all(math.isfinite(value) for value in values)
                assert all(value == round(value, 4) for value in values)
    assert result['bess'] is result['cost'] is None
    assert result['meta']['source'] == 'live'
    assert result['meta']['engine_version'] == __version__
    json.dumps(result, allow_nan=False)


def test_echo_and_hand_computed_pass_through(result):
    assert result['meta']['inputs'] == payload(bess='off', bess_override=None)
    series = result['series']
    assert series['time'][0] == '00:00'
    assert series['time'][95] == '23:45'
    assert series['base_kw'][84] == 175.0
    assert series['ev_kw'][76] == 50.0
    assert series['pv_kw'][48] == 24.0
    assert series['ambient_c'][60] == 43.0
    assert series['net_kw'][84] == pytest.approx(225.0, abs=1e-3)
    assert series['net_kw'][48] == pytest.approx(114.5, abs=1e-3)
    assert series['net_kw'][0] == pytest.approx(97.25, abs=1e-3)


def test_independent_three_pass_oracle(config, result):
    inputs = validate_request(payload(), config['scenarios'])
    loads = build_load_series(inputs, config)
    pf = powerflow.powerflow_params_from_config(config['transformer'])
    tp = thermal.thermal_params_from_config(config['transformer'])
    ap = aging.aging_params_from_config(config['limits'])
    first = powerflow.simulate_step(loads.base_kw[0], loads.ev_kw[0], loads.pv_kw[0], pf)
    state = thermal.initial_state_at_load(first.current_pu, tp)
    duration = config['scenarios']['parameters']['step_minutes']['value']
    for daily_pass in range(3):
        for index, (base, ev, pv, ambient) in enumerate(zip(loads.base_kw, loads.ev_kw, loads.pv_kw, loads.ambient_c)):
            flow = powerflow.simulate_step(base, ev, pv, pf)
            temperatures = thermal.step(state, flow.current_pu, ambient, duration, tp)
            state = temperatures.state
            if daily_pass == 2:
                series = result['series']
                assert abs(series['voltage_pu'][index] - flow.voltage_pu) <= 1e-4
                assert abs(series['loading_pct'][index] - flow.loading_pct) <= .01
                assert abs(series['top_oil_c'][index] - temperatures.top_oil_c) <= .01
                assert abs(series['hotspot_c'][index] - temperatures.hotspot_c) <= .01
                expected = aging.aging_factor(temperatures.hotspot_c, ap)
                difference = abs(series['aging_factor'][index] - expected)
                # Approved allowance covers four-decimal rounding and warm-up drift.
                assert difference <= .00006 or difference / expected <= .001


def test_summary_consistency(config, result):
    series, summary = result['series'], result['summary']
    for array, summary_key, time_key, operation in [
        ('hotspot_c', 'peak_hotspot_c', 'peak_hotspot_time', max),
        ('voltage_pu', 'min_voltage_pu', 'min_voltage_time', min),
        ('loading_pct', 'peak_loading_pct', 'peak_loading_time', max),
    ]:
        peak = operation(series[array])
        assert summary[summary_key] == peak
        assert summary[time_key] == series['time'][series[array].index(peak)]
    assert summary['peak_aging_factor'] == max(series['aging_factor'])
    assert summary['peak_voltage_deviation_pu'] == round(max(abs(v - 1.0) for v in series['voltage_pu']), 4)
    ap = aging.aging_params_from_config(config['limits'])
    hours = aging.daily_equivalent_aging_hours(series['hotspot_c'], 15, ap)
    assert summary['daily_equivalent_aging_hours'] == pytest.approx(hours, rel=.001)
    assert summary['insulation_life_years'] == pytest.approx(aging.insulation_life_years(hours, ap), rel=.001)
    assert summary['insulation_life_years'] is not None
    assert summary['insulation_life_years'] <= config['limits']['parameters']['insulation_life_cap_years']['value']


def test_ev_monotonic(config):
    summaries = [run_simulation(payload(ev_kw=ev), config)['summary'] for ev in (10, 30, 50, 100)]
    for left, right in zip(summaries, summaries[1:]):
        assert left['min_voltage_pu'] >= right['min_voltage_pu']
        assert left['peak_loading_pct'] <= right['peak_loading_pct']
        assert left['peak_hotspot_c'] <= right['peak_hotspot_c']


def test_load_level_monotonic(config):
    summaries = [run_simulation(payload(load_level=level), config)['summary'] for level in ('moderate', 'heavy', 'critical')]
    for left, right in zip(summaries, summaries[1:]):
        assert left['peak_loading_pct'] <= right['peak_loading_pct']
        assert left['peak_hotspot_c'] <= right['peak_hotspot_c']


def test_winter_cooler(config, result):
    winter = run_simulation(payload(day_type='winter_weekday'), config)
    assert winter['summary']['peak_hotspot_c'] < result['summary']['peak_hotspot_c']


def test_pv_daytime_effect(config, result):
    no_pv = run_simulation(payload(pv_kwp=0), config)['series']
    pv = result['series']
    assert no_pv['loading_pct'][84] == pv['loading_pct'][84]
    assert no_pv['voltage_pu'][84] == pv['voltage_pu'][84]
    assert no_pv['loading_pct'][48] > pv['loading_pct'][48]


def test_quiet_scenario(config):
    quiet = run_simulation(payload(ev_kw=10, day_type='winter_weekday', load_level='moderate'), config)
    assert quiet['alerts'] == []
    assert quiet['verdict']['status'] == 'safe'
    assert quiet['summary']['min_voltage_pu'] >= .95
    assert quiet['summary']['peak_hotspot_c'] < 80


def test_stress_scenario(config):
    stress = run_simulation(payload(ev_kw=100, pv_kwp=0, load_level='critical'), config)
    assert stress['verdict']['status'] == 'violations_found'
    low = next(event for event in stress['alerts'] if event['type'] == 'voltage_low')
    assert '16:30' <= low['start'] <= '18:00'
    assert '21:00' <= low['end'] < '23:30'
    assert low['peak_value'] == stress['summary']['min_voltage_pu']
    assert stress['summary']['peak_loading_pct'] > 100
    assert any(event['type'] == 'loading_over_100' for event in stress['alerts'])


def test_merge_consecutive_steps():
    for flags, expected in [([False, True, True, False, True, False], [(1, 2), (4, 4)]),
                            ([False] * 96, []), ([True] * 96, [(0, 95)]),
                            ([True, False, False, True], [(0, 0), (3, 3)]), ([], [])]:
        assert merge_consecutive_steps(flags) == expected


def test_hand_computed_alert_events(config):
    times = [f'{index // 4:02d}:{index % 4 * 15:02d}' for index in range(96)]
    voltage, hotspot, loading = [1.0] * 96, [60] * 96, [50] * 96
    voltage[10:13] = [.94] * 3
    voltage[13], voltage[14] = .97, .949
    voltage[50:52] = [1.06] * 2
    hotspot[70:73] = [111, 141, 120]
    loading[80:82] = [100.0, 100.01]
    events = detect_alerts(times, voltage, loading, hotspot, config['limits'])
    expected = [
        ('voltage_low', 'warning', '02:30', '03:00', .94, 'p.u.'),
        ('voltage_low', 'warning', '03:30', '03:30', .949, 'p.u.'),
        ('voltage_high', 'warning', '12:30', '12:45', 1.06, 'p.u.'),
        ('hotspot_warning', 'warning', '17:30', '17:30', 111, '°C'),
        ('hotspot_critical', 'critical', '17:45', '17:45', 141, '°C'),
        ('hotspot_warning', 'warning', '18:00', '18:00', 120, '°C'),
        ('loading_over_100', 'info', '20:15', '20:15', 100.01, '%'),
    ]
    assert events == [dict(zip(('type', 'severity', 'start', 'end', 'peak_value', 'unit'), row)) for row in expected]


def test_exact_alert_thresholds_and_same_start_order(config):
    events = detect_alerts(['00:00', '00:15'], [.95, 1.05], [100, 100], [110, 140], config['limits'])
    assert events == [dict(type='hotspot_warning', severity='warning', start='00:15', end='00:15', peak_value=140, unit='°C')]
    events = detect_alerts(['00:00'], [.94], [101], [141], config['limits'])
    assert [event['type'] for event in events] == ['hotspot_critical', 'loading_over_100', 'voltage_low']


def test_bess_unimplemented_and_invalid_input(config):
    for request in (payload(bess='auto'),):
        with pytest.raises(NotImplementedError, match='battery simulation is added in M8'):
            simulate_day(validate_request(request, config['scenarios']), config)
    with pytest.raises(InvalidInputError) as caught:
        run_simulation(payload(ev_kw=20), config)
    assert caught.value.field == 'ev_kw'


def test_determinism_and_purity(config):
    before = deepcopy(config)
    request = payload()
    original_request = deepcopy(request)
    assert run_simulation(request, config) == run_simulation(request, config)
    assert config == before
    assert request == original_request


def test_powerflow_error_propagates(config, monkeypatch):
    error = powerflow.PowerFlowError('test convergence failure')
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(powerflow, 'simulate_step', fail)
    with pytest.raises(powerflow.PowerFlowError) as caught:
        run_simulation(payload(), config)
    assert caught.value is error

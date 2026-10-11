"""Synthetic controller boundaries and real local API replay serialization."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
import handler
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.telemetry import evaluate, replay
from gridmind_engine.validate import InvalidInputError

@pytest.fixture
def config():
    return load_config_dir(Path(__file__).resolve().parents[2] / 'config')


def payload(**updates):
    record = dict(timestamp='2026-01-01T18:00:00Z', transformer_id='single-transformer-model', source='simulation', loading_pct=110, voltage_pu=0.94, hotspot_c=115, battery_soc_pct=50, net_kw=250)
    record.update(updates)
    return dict(telemetry=record, now=record['timestamp'], previous_timestamp=None, battery=dict(power_kw=20, energy_kwh=100, charge_efficiency=1, discharge_efficiency=1))


def test_discharge_energy_boundary(config):
    result = evaluate(payload(battery_soc_pct=11), config)
    assert result['action'] == 'discharge'
    assert result['power_kw'] == 4  # One stored kWh over a 15-minute step.
    assert result['next_soc_pct'] == 10
    assert result['published'] is False and result['simulated'] is True
    assert result['alerts'] == ['voltage_low', 'hotspot_warning', 'loading_over_100']


def test_min_soc_and_idle_interlocks(config):
    assert evaluate(payload(battery_soc_pct=10), config)['action'] == 'idle'
    assert evaluate(payload(voltage_pu=1.06), config)['reasons'] == ['engineering_interlock_idle']
    assert evaluate(payload(hotspot_c=141), config)['reasons'] == ['engineering_interlock_idle']
    assert evaluate(payload(battery_soc_pct=5), config)['action'] == 'idle'


def test_charging_limits_and_strict_thresholds(config):
    request = payload(timestamp='2026-01-01T23:00:00Z', loading_pct=50, voltage_pu=1.0, hotspot_c=110, net_kw=100, battery_soc_pct=89)
    result = evaluate(request, config)
    assert result['action'] == 'charge' and result['power_kw'] == -4
    assert result['next_soc_pct'] == 90
    assert result['alerts'] == []
    request['telemetry']['battery_soc_pct'] = 90
    assert evaluate(request, config)['action'] == 'idle'
    request['telemetry'].update(loading_pct=91, battery_soc_pct=50)
    assert evaluate(request, config)['action'] == 'idle'  # No recharge into loading stress.


@pytest.mark.parametrize('name,value', [('loading_pct', -1), ('voltage_pu', 0), ('hotspot_c', float('nan')), ('battery_soc_pct', 101), ('net_kw', True), ('timestamp', 'not-a-time'), ('source', 'hardware')])
def test_invalid_readings(config, name, value):
    with pytest.raises(InvalidInputError):
        evaluate(payload(**{name: value}), config)


def test_stale_future_and_order(config):
    request = payload(); request['now'] = '2026-01-01T18:15:01Z'
    with pytest.raises(InvalidInputError, match='stale'): evaluate(request, config)
    request['now'] = '2026-01-01T17:59:59Z'
    with pytest.raises(InvalidInputError, match='future'): evaluate(request, config)
    request['now'] = '2026-01-01T18:15:00Z'
    assert evaluate(request, config)['action'] == 'discharge'
    request['previous_timestamp'] = request['telemetry']['timestamp']
    with pytest.raises(InvalidInputError, match='newer'): evaluate(request, config)


def test_missing_data_safe_fallback(config):
    request = payload(); del request['telemetry']['battery_soc_pct']
    result = evaluate(request, config)
    assert result['action'] == 'idle' and result['power_kw'] == 0
    assert result['next_soc_pct'] is None
    assert result['reasons'] == ['missing_data_idle']
    assert 'voltage_low' in result['alerts']


def test_replay_api_determinism_and_purity(config):
    original = deepcopy(config)
    request = dict(start_time='2026-01-01T00:00:00Z', scenario=dict(ev_kw=100, pv_kwp=0, day_type='summer_weekday', load_level='critical', bess_override=dict(power_kw=100, energy_kwh=500, initial_soc_pct=80)))
    result = replay(request, config)
    assert len(result['records']) == 96
    assert result['records'][1]['timestamp'] == '2026-01-01T00:30:00Z'
    assert result['records'][-1]['timestamp'] == '2026-01-02T00:00:00Z'
    assert result == replay(request, config)
    status, body = handler.handle_request('POST', '/v2/telemetry/replay', json.dumps(request), config)
    assert status == 200 and body == result
    reading = body['records'][72]
    dispatch = dict(telemetry=reading, now=reading['timestamp'], previous_timestamp=body['records'][71]['timestamp'], battery=body['battery'])
    status, response = handler.handle_request('POST', '/v2/dispatch/evaluate', json.dumps(dispatch), config)
    assert status == 200
    assert response['published'] is False
    json.dumps(response, allow_nan=False)
    assert config == original


def test_wrong_method_and_bad_telemetry_api(config):
    assert handler.handle_request('GET', '/v2/dispatch/evaluate', None, config)[0] == 405
    status, body = handler.handle_request('POST', '/v2/dispatch/evaluate', json.dumps(payload(voltage_pu=-1)), config)
    assert status == 400 and body['error']['field'] == 'telemetry.voltage_pu'

def test_strict_alert_boundaries(config):
    result = evaluate(payload(loading_pct=100, voltage_pu=0.95, hotspot_c=110), config)
    assert result['alerts'] == []


def test_charging_grid_headroom_guard(config):
    request = payload(timestamp='2026-01-01T23:00:00Z', loading_pct=89, voltage_pu=0.96, hotspot_c=60, net_kw=200)
    request['battery']['power_kw'] = 100
    result = evaluate(request, config)
    assert result['action'] == 'idle'
    assert result['reasons'] == ['charge_grid_limit_idle']

"""Check the local HTTP API adapter without cloud SDKs or deployed resources."""

import base64
from copy import deepcopy
import json
import logging
from pathlib import Path
import subprocess
import sys
import time

import pytest

import handler
from gridmind_engine import __version__
from gridmind_engine.powerflow import PowerFlowError
from gridmind_engine.simulate import run_simulation

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = dict(ev_kw=50, pv_kwp=30, day_type='summer_weekday', load_level='heavy')


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.delenv('GRIDMIND_CONFIG_DIR', raising=False)
    handler.reset_config_cache()
    yield
    handler.reset_config_cache()


@pytest.fixture
def config():
    return handler.get_config()


def sample(name):
    return json.loads((ROOT / 'lambda' / 'events' / f'{name}.json').read_text())


def test_scenarios(config):
    status, body = handler.handle_request('GET', '/scenarios', None, config)
    assert status == 200
    assert set(body) == {'enums', 'defaults', 'engine_version', 'assumptions'}
    assert body['engine_version'] == __version__
    for name in ('ev_kw', 'pv_kwp', 'day_type', 'load_level', 'bess'):
        assert body['enums'][name] == config['scenarios']['parameters'][f'{name}_options']['value']
        assert body['defaults'][name] == config['scenarios']['parameters'][f'default_{name}']['value']
    expected_names = {name for stem in ('transformer', 'limits', 'costs', 'bess', 'load_levels')
                      for name in config[stem]['parameters']}
    names = [entry['name'] for entry in body['assumptions']]
    assert len(names) == len(set(names))
    assert set(names) == expected_names
    for entry in body['assumptions']:
        assert set(entry) == {'name', 'value', 'unit', 'note'}
        assert entry['note'].strip()
        assert not isinstance(entry['value'], list)
    values = {entry['name']: entry['value'] for entry in body['assumptions']}
    assert values['voltage_min_pu'] == .95
    assert values['rated_kva'] == 250
    assert values['power_factor_ev'] == .98
    assert values['hotspot_critical_c'] == 140
    assert values['bess_cost_per_kw_inr'] is None
    assert len(json.dumps(body)) < 50000


def test_default_golden_values(config):
    status, body = handler.handle_request('POST', '/simulate', json.dumps(PAYLOAD), config)
    assert status == 200
    assert body == run_simulation(PAYLOAD, config)
    assert body['summary']['min_voltage_pu'] == .9499
    assert body['summary']['peak_hotspot_c'] == 104.1997
    assert body['summary']['peak_loading_pct'] == 98.9428
    assert body['verdict']['status'] == 'violations_found'
    assert body['alerts'] == [dict(type='voltage_low', severity='warning', start='21:00', end='21:00', peak_value=.9499, unit='p.u.')]


def test_stress_golden_values(config):
    payload = dict(PAYLOAD, ev_kw=100, pv_kwp=0, load_level='critical')
    status, body = handler.handle_request('POST', '/simulate', json.dumps(payload), config)
    assert status == 200
    for key, value in [('min_voltage_pu', .9292), ('peak_hotspot_c', 148.7173),
                       ('peak_loading_pct', 140.0125), ('peak_aging_factor', 36.4389)]:
        assert body['summary'][key] == value
    critical = next(alert for alert in body['alerts'] if alert['type'] == 'hotspot_critical')
    assert (critical['start'], critical['end']) == ('20:00', '21:30')


def test_prefix_and_trailing_slash(config):
    results = [handler.handle_request('POST', path, json.dumps(PAYLOAD), config)
               for path in ('/api/simulate', '/simulate', '/api/simulate/')]
    assert results[0] == results[1] == results[2]
    assert handler.handle_request('POST', '/api/api/simulate', json.dumps(PAYLOAD), config)[0] == 404


def test_request_errors(config):
    cases = [
        ('POST', '/simulate', json.dumps(dict(PAYLOAD, ev_kw=20)), 400, 'invalid_input', 'ev_kw'),
        ('POST', '/simulate', json.dumps(dict(PAYLOAD, foo='x')), 400, 'invalid_input', 'foo'),
        ('POST', '/simulate', '{', 400, 'invalid_input', 'body'),
        ('POST', '/simulate', '', 400, 'invalid_input', 'body'),
        ('POST', '/simulate', None, 400, 'invalid_input', 'body'),
        ('POST', '/simulate', '[]', 400, 'invalid_input', 'payload'),
        ('POST', '/simulate', ' ' * 2049, 400, 'invalid_input', 'body'),
        ('GET', '/simulate', None, 405, 'method_not_allowed', None),
        ('POST', '/scenarios', '{}', 405, 'method_not_allowed', None),
        ('GET', '/nothing', None, 404, 'not_found', None),
        ('POST', '/simulate', json.dumps(dict(PAYLOAD, bess='auto')), 400, 'invalid_input', 'bess'),
        ('POST', '/simulate', json.dumps(dict(PAYLOAD, bess_override=dict(power_kw=10, energy_kwh=20))), 400, 'invalid_input', 'bess'),
    ]
    cases += [(method, route, None, 404, 'not_found', None)
              for method in ('GET', 'POST') for route in ('/optimize', '/dispatch')]
    for method, path, text, expected_status, code, field in cases:
        status, body = handler.handle_request(method, path, text, config)
        assert status == expected_status
        assert body['error']['code'] == code
        assert body['error']['field'] == field
        if path in ('/optimize', '/dispatch'):
            assert body['error']['message'] == 'route not available yet'


def test_utf8_byte_limit(config):
    text = json.dumps(dict(PAYLOAD, foo='é' * 1000), ensure_ascii=False)
    assert len(text) < 2048 < len(text.encode('utf-8'))
    status, body = handler.handle_request('POST', '/simulate', text, config)
    assert status == 400
    assert body['error']['field'] == 'body'


def test_server_error_mapping(config, monkeypatch, caplog):
    def fail_flow(*args, **kwargs):
        raise PowerFlowError('x')
    monkeypatch.setattr(handler, 'run_simulation', fail_flow)
    status, body = handler.handle_request('POST', '/simulate', json.dumps(PAYLOAD), config)
    assert status == 500
    assert body == dict(error=dict(code='convergence_failed', message='x', field=None))
    caplog.clear()
    def fail_internal(*args, **kwargs):
        raise RuntimeError('SECRET-DETAIL')
    monkeypatch.setattr(handler, 'run_simulation', fail_internal)
    status, body = handler.handle_request('POST', '/simulate', json.dumps(PAYLOAD), config)
    assert status == 500
    assert body == dict(error=dict(code='internal_error', message='internal error', field=None))
    assert 'SECRET-DETAIL' not in json.dumps(body)
    records = [record for record in caplog.records if record.name == 'handler']
    assert len(records) == 1
    trace = json.loads(records[0].message)['traceback']
    assert 'Traceback' in trace and 'RuntimeError: SECRET-DETAIL' in trace


def test_sample_events_end_to_end():
    for name, status in [('get_scenarios', 200), ('simulate_default', 200), ('simulate_stress', 200),
                         ('simulate_invalid', 400), ('get_unknown', 404)]:
        response = handler.lambda_handler(sample(name), None)
        assert set(response) == {'statusCode', 'headers', 'body'}
        assert response['statusCode'] == status
        assert response['headers'] == {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}
        assert isinstance(response['body'], str)
        assert isinstance(json.loads(response['body']), dict)


def test_base64_and_malformed_events():
    event = sample('simulate_default')
    expected = handler.lambda_handler(event, None)
    event['body'] = base64.b64encode(event['body'].encode()).decode()
    event['isBase64Encoded'] = True
    assert handler.lambda_handler(event, None) == expected
    missing_path = sample('get_scenarios')
    del missing_path['rawPath']
    missing_method = sample('get_scenarios')
    del missing_method['requestContext']['http']['method']
    for bad in ([], missing_path, missing_method):
        response = handler.lambda_handler(bad, None)
        assert response['statusCode'] == 400
        assert json.loads(response['body'])['error']['field'] == 'event'
    event['body'] = '!not base64!'
    response = handler.lambda_handler(event, None)
    assert response['statusCode'] == 400
    assert json.loads(response['body'])['error']['field'] == 'body'


def test_config_cache(monkeypatch):
    calls = []
    original = handler.load_config_dir
    def count(path):
        calls.append(path)
        return original(path)
    monkeypatch.setattr(handler, 'load_config_dir', count)
    handler.lambda_handler(sample('get_scenarios'), None)
    handler.lambda_handler(sample('simulate_default'), None)
    assert len(calls) == 1
    handler.reset_config_cache()
    handler.lambda_handler(sample('get_scenarios'), None)
    assert len(calls) == 2


def test_missing_config_is_internal_error(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv('GRIDMIND_CONFIG_DIR', str(tmp_path / 'missing'))
    response = handler.lambda_handler(sample('get_scenarios'), None)
    assert response['statusCode'] == 500
    assert json.loads(response['body']) == dict(error=dict(code='internal_error', message='internal error', field=None))
    records = [record for record in caplog.records if record.name == 'handler']
    assert len(records) == 1
    assert 'ValueError' in json.loads(records[0].message)['traceback']


def test_one_safe_log_per_request(caplog):
    caplog.set_level(logging.INFO, logger='handler')
    invalid = sample('simulate_invalid')
    invalid['body'] = json.dumps(dict(PAYLOAD, ev_kw='SECRET123'))
    for event in (sample('get_scenarios'), sample('simulate_default'), invalid, [], sample('get_unknown')):
        caplog.clear()
        response = handler.lambda_handler(event, None)
        records = [record for record in caplog.records if record.name == 'handler']
        assert len(records) == 1
        message = records[0].message
        assert 'SECRET123' not in message
        record = json.loads(message)
        assert {'method', 'path', 'status', 'duration_ms', 'error_code'} <= set(record)
        assert record['status'] == response['statusCode']
        assert record['duration_ms'] >= 0
        if event == sample('simulate_default'):
            assert {key: record[key] for key in ('ev_kw', 'pv_kwp', 'day_type', 'load_level', 'bess')} == dict(PAYLOAD, bess='off')
        else:
            assert 'ev_kw' not in record


def test_purity_and_scenarios_isolation(config):
    before = deepcopy(config)
    first = handler.handle_request('POST', '/simulate', json.dumps(PAYLOAD), config)
    assert first == handler.handle_request('POST', '/simulate', json.dumps(PAYLOAD), config)
    assert config == before
    body = handler.build_scenarios_response(config)
    body['enums']['ev_kw'].append(999)
    assert config == before


def test_invoker_subprocess():
    script = ROOT / 'scripts' / 'invoke_local.py'
    for name, args, code in [('get_scenarios', [], 0), ('simulate_invalid', [], 1), ('simulate_default', ['--summary'], 0)]:
        result = subprocess.run([sys.executable, str(script), str(ROOT / 'lambda' / 'events' / f'{name}.json'), *args],
                                capture_output=True, text=True, check=False)
        assert result.returncode == code
        if name == 'get_scenarios':
            assert json.loads(result.stdout)['statusCode'] == 200
        elif name == 'simulate_default':
            assert '0.9499' in result.stdout
        else:
            assert json.loads(result.stdout)['statusCode'] == 400


def test_simulation_speed(config):
    started = time.perf_counter()
    assert handler.handle_request('POST', '/simulate', json.dumps(PAYLOAD), config)[0] == 200
    assert time.perf_counter() - started < 2

"""HTTP API operations reuse the public engines and keep legacy contracts intact."""

import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import pytest

import api_routes
import handler
from gridmind_engine import __version__
from gridmind_engine.hosting import assess_hosting
from gridmind_engine.impact import assess_impact
from gridmind_engine.network import assess_network
from gridmind_engine.planner import plan_charging
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import run_simulation

ROOT = Path(__file__).resolve().parents[2]
SINGLE = dict(ev_kw=50, pv_kwp=30, day_type='summer_weekday', load_level='heavy')
ALLOCATION = dict(allocation=[dict(site_id='S1', kw=10, managed=False, cap_fraction=None)])


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    monkeypatch.delenv('GRIDMIND_CONFIG_DIR', raising=False)
    monkeypatch.delenv('GRIDMIND_ALLOWED_ORIGINS', raising=False)
    handler.reset_config_cache()
    yield
    handler.reset_config_cache()


@pytest.fixture
def config():
    return load_config_dir(ROOT / 'config')


def event(path, method='GET', payload=None, headers=None):
    return dict(version='2.0', rawPath=path, requestContext=dict(http=dict(method=method)),
                body=json.dumps(payload) if payload is not None else None,
                headers=headers or {}, isBase64Encoded=False)


@pytest.mark.parametrize('path', ['/v2/health', '/health', '/api/v2/health/'])
def test_health(path):
    response = handler.lambda_handler(event(path), None)
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == dict(status='ok', api_version='v2', engine_version=__version__)
    assert response['headers'] == {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}


def test_network_topology_matches_contract_without_mutation(config):
    before = deepcopy(config)
    status, result = handler.handle_request('GET', '/v2/network', None, config)
    assert status == 200
    assert set(result) == {'meta', 'neighbourhood', 'transformers', 'sites', 'defaults', 'enums', 'assumptions'}
    assert [t['id'] for t in result['transformers']] == ['T1', 'T2', 'T3', 'T4', 'T5', 'T6']
    assert len(result['sites']) == 7 and all(t['rated_kva'] == 250 for t in result['transformers'])
    assert result['neighbourhood']['map'] == {'width': 100, 'height': 100}
    assert result['defaults']['target_kw'] == 300
    assert result['meta']['inputs'] == {}
    assert len({a['name'] for a in result['assumptions']}) == len(result['assumptions'])
    assert all(a['note'] for a in result['assumptions'])
    assert not any(a['name'] in ('summer_weekday', 'winter_weekday', 'weekend') for a in result['assumptions'])
    result['transformers'][0]['name'] = 'changed'
    assert config == before


@pytest.mark.parametrize('route,payload,operation', [
    ('/v2/simulate', SINGLE, run_simulation), ('/v2/assess', ALLOCATION, assess_network),
    ('/v2/impact', ALLOCATION, assess_impact)])
def test_engine_integration(route, payload, operation, config):
    response = handler.lambda_handler(event(route, 'POST', payload), None)
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == operation(payload, config)
    assert handler.handle_request('POST', route.removeprefix('/v2'), json.dumps(payload), config)[1] == operation(payload, config)


@pytest.mark.parametrize('route,payload,name', [('/v2/hosting', {}, 'assess_hosting'),
                                              ('/v2/plan', {'target_kw': 300}, 'plan_charging')])
def test_expensive_route_invokes_engine_once_after_validation(route, payload, name, config, monkeypatch):
    calls = []
    def operation(*args):
        calls.append(args)
        return {'meta': {'source': 'live'}, 'sentinel': name}
    monkeypatch.setattr(api_routes, name, operation)
    status, body = handler.handle_request('POST', route, json.dumps(payload), config)
    assert status == 200 and body['sentinel'] == name
    assert len(calls) == 1
    assert calls[0] == ((config,) if name == 'assess_hosting' else (payload, config))


@pytest.mark.parametrize('route', ['/v2/health', '/v2/scenarios', '/v2/network', '/v2/simulate',
                                   '/v2/assess', '/v2/impact', '/v2/hosting', '/v2/plan'])
def test_wrong_methods(route, config):
    assert handler.handle_request('DELETE', route, '{}', config)[0] == 405


@pytest.mark.parametrize('route', ['/v2/nothing', '/v3/health', '/api/api/v2/health',
                                   '/v2/dispatch', '/v2/optimize'])
def test_unknown_and_unavailable_routes(route, config):
    status, body = handler.handle_request('GET', route, None, config)
    assert status == 404 and body['error']['code'] == 'not_found'


@pytest.mark.parametrize('text', ['{', '', None, 'NaN', 'Infinity', '{"allocation": [], "x": 1e309}',
                                  '{"allocation": [], "allocation": []}', ' ' * 2049])
def test_malformed_json_and_size(text, config):
    status, body = handler.handle_request('POST', '/v2/assess', text, config)
    assert status == 400 and body['error']['field'] == 'body'


@pytest.mark.parametrize('route,payload,field', [
    ('/v2/assess', {}, 'allocation'), ('/v2/assess', [], 'payload'),
    ('/v2/assess', {'allocation': [], 'transformer_id': 'UNKNOWN'}, 'transformer_id'),
    ('/v2/assess', {'allocation': [], 'day_type': 'monday'}, 'day_type'),
    ('/v2/hosting', {'day_type': 'monday'}, 'day_type'),
    ('/v2/hosting', [], 'payload'), ('/v2/plan', {}, 'target_kw'),
    ('/v2/plan', {'target_kw': True}, 'target_kw'), ('/v2/plan', {'target_kw': -10}, 'target_kw'),
    ('/v2/simulate', dict(SINGLE, day_type='monday'), 'day_type')])
def test_semantic_validation(route, payload, field, config):
    status, body = handler.handle_request('POST', route, json.dumps(payload), config)
    assert status == 400 and body['error']['code'] == 'invalid_input'
    assert body['error']['field'] == field


@pytest.mark.parametrize('new', ['UNKNOWN', 'T1'])
def test_unknown_site_ids(new, config):
    payload = deepcopy(ALLOCATION)
    payload['allocation'][0]['site_id'] = new
    status, body = handler.handle_request('POST', '/v2/impact', json.dumps(payload), config)
    assert status == 400 and body['error']['field'] == 'allocation[0].site_id'


@pytest.mark.parametrize('kw', [-10, 10.0, True, 999999])
def test_invalid_demands(kw, config):
    payload = deepcopy(ALLOCATION)
    payload['allocation'][0]['kw'] = kw
    status, body = handler.handle_request('POST', '/v2/assess', json.dumps(payload), config)
    assert status == 400 and body['error']['field'] == 'allocation[0].kw'


def test_duplicate_site_id(config):
    payload = deepcopy(ALLOCATION)
    payload['allocation'] *= 2
    status, body = handler.handle_request('POST', '/v2/assess', json.dumps(payload), config)
    assert status == 400 and body['error']['field'] == 'allocation[1].site_id'


@pytest.mark.parametrize('exception', [RuntimeError('/private/SECRET'), ValueError('/private/SECRET')])
def test_server_details_never_leak(exception, config, monkeypatch, caplog):
    def fail(*_):
        raise exception
    monkeypatch.setattr(api_routes, 'assess_network', fail)
    status, body = handler.handle_request('POST', '/v2/assess', json.dumps(ALLOCATION), config)
    assert status == 500 and body == {'error': {'code': 'internal_error', 'message': 'internal error', 'field': None}}
    assert '/private/SECRET' not in json.dumps(body)
    assert len(caplog.records) == 1 and 'Traceback' in json.loads(caplog.records[0].message)['traceback']


def test_nonfinite_engine_output_is_internal_error(config, monkeypatch):
    monkeypatch.setattr(api_routes, 'assess_hosting', lambda *_: {'bad': float('nan')})
    status, body = handler.handle_request('POST', '/v2/hosting', '{}', config)
    assert status == 500 and body['error']['message'] == 'internal error'


def test_cors_preflight_and_actual_headers(monkeypatch):
    monkeypatch.setenv('GRIDMIND_ALLOWED_ORIGINS', '["https://frontend.example"]')
    headers = {'Origin': 'https://frontend.example', 'Access-Control-Request-Method': 'POST',
               'Access-Control-Request-Headers': 'content-type'}
    response = handler.lambda_handler(event('/api/v2/plan', 'OPTIONS', headers=headers), None)
    assert response['statusCode'] == 204 and response['body'] == ''
    assert response['headers']['Access-Control-Allow-Origin'] == 'https://frontend.example'
    assert response['headers']['Access-Control-Allow-Methods'] == 'GET, POST, OPTIONS'
    assert response['headers']['Vary'] == 'Origin'
    assert 'Access-Control-Allow-Credentials' not in response['headers']
    response = handler.lambda_handler(event('/v2/health', headers={'origin': 'https://frontend.example'}), None)
    assert response['headers']['Access-Control-Allow-Origin'] == 'https://frontend.example'


@pytest.mark.parametrize('headers,field', [({'Origin': 'https://unapproved.example'}, 'origin'),
    ({'Access-Control-Request-Method': 'DELETE'}, 'method'),
    ({'Access-Control-Request-Headers': 'Authorization'}, 'headers')])
def test_invalid_cors(headers, field):
    response = handler.lambda_handler(event('/v2/plan', 'OPTIONS', headers=headers), None)
    assert response['statusCode'] == 400 and json.loads(response['body'])['error']['field'] == field


def test_invalid_cors_configuration_is_safe(monkeypatch):
    monkeypatch.setenv('GRIDMIND_ALLOWED_ORIGINS', '["*"]')
    response = handler.lambda_handler(event('/v2/health'), None)
    assert response['statusCode'] == 500 and json.loads(response['body'])['error']['message'] == 'internal error'


@pytest.mark.parametrize('change', [{'version': '1.0'}, {'isBase64Encoded': 'true'}, {'headers': []}])
def test_invalid_http_event(change):
    request = event('/v2/health')
    request.update(change)
    response = handler.lambda_handler(request, None)
    assert response['statusCode'] == 400 and json.loads(response['body'])['error']['field'] == 'event'


def test_base64_and_deterministic_serialization():
    request = event('/v2/assess', 'POST', ALLOCATION)
    request['body'] = base64.b64encode(request['body'].encode()).decode()
    request['isBase64Encoded'] = True
    first = handler.lambda_handler(request, None)
    assert first == handler.lambda_handler(request, None)
    assert first['statusCode'] == 200
    request['body'] = base64.b64encode(b'x' * 2049).decode()
    response = handler.lambda_handler(request, None)
    assert response['statusCode'] == 400 and json.loads(response['body'])['error']['field'] == 'body'


def test_package_reproducible_complete_and_isolated(tmp_path):
    destinations = [tmp_path / 'first.zip', tmp_path / 'second.zip']
    for path in destinations:
        subprocess.run([sys.executable, str(ROOT / 'scripts/package_api.py'), '--out', str(path)], check=True, capture_output=True)
    assert destinations[0].read_bytes() == destinations[1].read_bytes()
    folder = tmp_path / 'isolated'
    with zipfile.ZipFile(destinations[0]) as package:
        names = package.namelist()
        assert len([n for n in names if n.startswith('config/profiles/')]) == 7
        assert len([n for n in names if n.startswith('config/')]) == 14
        for name in names:
            assert name.endswith(('.py', '.json'))
            assert not any(part in name for part in ('.venv', '.git', 'tests/', '__pycache__', '.env', '.aws'))
        for path in (ROOT / 'engine/gridmind_engine').glob('*.py'):
            assert package.read('gridmind_engine/' + path.name) == path.read_bytes()
        for path in (ROOT / 'config').rglob('*.json'):
            assert package.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
        package.extractall(folder)
    script = 'import handler,json; r=handler.lambda_handler(' + repr(event('/v2/assess', 'POST', ALLOCATION)) + ',None); print(json.dumps(r))'
    result = subprocess.run([sys.executable, '-I', '-c', 'import sys; sys.path.insert(0,' + repr(str(folder)) + ');' + script],
                            cwd=folder, capture_output=True, text=True, check=True)
    response = json.loads(result.stdout)
    assert response['statusCode'] == 200
    assert json.loads(response['body']) == assess_network(ALLOCATION, load_config_dir(ROOT / 'config'))


@pytest.mark.parametrize('route,payload,operation', [('/v2/hosting', {}, assess_hosting),
                                                  ('/v2/plan', {'target_kw': 300}, plan_charging)])
def test_real_expensive_integration(route, payload, operation, config):
    snapshot = deepcopy(config)
    expected = operation(config) if route.endswith('hosting') else operation(payload, config)
    status, body = handler.handle_request('POST', route, json.dumps(payload), config)
    assert status == 200 and body == expected
    assert config == snapshot
    json.dumps(body, allow_nan=False)


def test_scenarios_versioned_alias(config):
    assert handler.handle_request('GET', '/v2/scenarios', None, config) == handler.handle_request('GET', '/scenarios', None, config)


def test_versioned_solver_error_does_not_expose_internal_detail(config, monkeypatch):
    from gridmind_engine.powerflow import PowerFlowError
    def fail(*_):
        raise PowerFlowError('/private/SECRET')
    monkeypatch.setattr(api_routes, 'assess_network', fail)
    status, body = handler.handle_request('POST', '/v2/assess', json.dumps(ALLOCATION), config)
    assert status == 500
    assert body == {'error': {'code': 'convergence_failed', 'message': 'power-flow solver did not converge', 'field': None}}


@pytest.mark.parametrize('origin', ['https://frontend.example\r\nX: injected', 'https://:80',
                                     'https://frontend.example:999999', 'null', 'https://frontend.example/path'])
def test_invalid_configured_origins_are_never_reflected(origin, monkeypatch):
    monkeypatch.setenv('GRIDMIND_ALLOWED_ORIGINS', json.dumps([origin]))
    response = handler.lambda_handler(event('/v2/health', headers={'origin': origin}), None)
    assert response['statusCode'] == 500
    assert 'Access-Control-Allow-Origin' not in response['headers']

"""Single-pass HTTP contract checks against a local adapter or approved backend."""
import argparse
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--origin', default='http://localhost:5173')
    parser.add_argument('--battery-power', type=float, required=True)
    parser.add_argument('--battery-energy', type=float, required=True)
    parser.add_argument('--initial-soc', type=float, required=True)
    parser.add_argument('--snapshots-url', default='http://localhost:5174/precomputed/scenarios.json')
    args = parser.parse_args()

    def call(path, payload=None, method=None, expected=200):
        headers = {'Origin': args.origin, 'Content-Type': 'application/json'}
        if method == 'OPTIONS':
            headers.update({'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type'})
        # Pace the single pass to respect the documented one-request/second API stage.
        time.sleep(1)
        request = Request(args.base_url.rstrip('/') + '/v2/' + path, data=None if payload is None else json.dumps(payload, allow_nan=False).encode(), headers=headers, method=method)
        try:
            response = urlopen(request, timeout=30)
        except HTTPError as exc:
            response = exc
        assert response.status == expected, f'{path}: HTTP {response.status}, expected {expected}'
        assert response.headers.get('Access-Control-Allow-Origin') == args.origin, f'{path}: missing approved CORS origin'
        assert response.headers.get('Content-Type', '').startswith('application/json')
        text = response.read().decode()
        data = json.loads(text) if text else None
        print(f'PASS {request.get_method()} /v2/{path}: HTTP {response.status}, CORS and JSON')
        return data

    assert call('health')['status'] == 'ok'
    network = call('network'); assert len(network['transformers']) == 6
    scenarios = call('scenarios')
    request = {k: scenarios['defaults'][k] for k in ('ev_kw', 'pv_kwp', 'day_type', 'load_level')}
    baseline = call('simulate', request)
    battery_request = dict(request, bess_override=dict(power_kw=args.battery_power, energy_kwh=args.battery_energy, initial_soc_pct=args.initial_soc))
    battery = call('simulate', battery_request)
    for result in (baseline, battery):
        assert result['meta']['source'] == 'live'
        for key, values in result['series'].items():
            assert values is None or len(values) == 96, key
        assert result['series']['time'][0] == '00:00' and result['series']['time'][-1] == '23:45'
    assert battery['bess'] and battery['series']['bess_soc_pct']
    assert baseline['series']['bess_soc_pct'] is None
    assert any(power != 0 for power in battery['series']['bess_kw'])
    print('PASS real battery dispatch and 96-step chart alignment; no-battery result remains distinct')
    replay = call('telemetry/replay', dict(scenario=battery_request, start_time='2026-01-01T00:00:00Z'))
    assert len(replay['records']) == 96 and replay['simulated']
    record = replay['records'][0]
    evaluate = dict(telemetry=record, now=record['timestamp'], previous_timestamp=None, battery=replay['battery'])
    advisory = call('dispatch/evaluate', evaluate)
    assert advisory['simulated'] and advisory['published'] is False
    evaluate['now'] = '2026-01-02T00:00:00Z'
    assert call('dispatch/evaluate', evaluate, expected=400)['error']['code'] == 'invalid_input'
    assert call('simulate', dict(request, ev_kw=-1), expected=400)['error']['field'] == 'ev_kw'
    call('simulate', method='OPTIONS', expected=204)
    with urlopen(args.snapshots_url, timeout=10) as response:
        artifact = json.load(response)
        assert response.status == 200 and artifact['schema_version'] == 1
        assert len(artifact['artifacts']) == 3
        assert all(item['result']['meta']['source'] == 'cached' for item in artifact['artifacts'])
    print('PASS separately served precomputed provenance; no automatic fallback or live label')

if __name__ == '__main__':
    main()

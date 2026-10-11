"""Independent energy-ledger and local API regression checks."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import handler
from gridmind_engine.bess import BatteryParams, dispatch
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import run_simulation

CONFIG = Path(__file__).resolve().parents[2] / 'config'
PAYLOAD = dict(ev_kw=100, pv_kwp=0, day_type='summer_weekday', load_level='critical')


def test_energy_and_efficiency():
    params = BatteryParams(20, 100, 50, 10, 90, 0.8, 0.9)
    powers, soc, ledger = dispatch([120, 80], ['18:00', '23:00'], 60, params, 100, '23:00', '06:00')
    assert powers == [20, -20]
    assert soc[0] == pytest.approx(50 - 20 / 0.9)
    assert soc[1] == pytest.approx(50 - 20 / 0.9 + 20 * 0.8)
    assert ledger['charged_kwh'] == 20
    assert ledger['discharged_kwh'] == 20
    assert ledger['loss_kwh'] == pytest.approx(20 / 0.9 - 20 + 20 - 16)
    assert 50 + ledger['charged_kwh'] - ledger['discharged_kwh'] - ledger['loss_kwh'] == pytest.approx(soc[-1])


def test_power_capacity_and_no_energy_creation():
    params = BatteryParams(50, 10, 50, 10, 90, 1, 1)
    powers, soc, _ = dispatch([200] * 5, ['18:00'] * 5, 15, params, 100, '23:00', '06:00')
    assert powers == [16, 0, 0, 0, 0]  # Four available stored kWh over 0.25 h.
    assert soc == [10] * 5
    powers, soc, _ = dispatch([0] * 5, ['23:00'] * 5, 15, params, 100, '23:00', '06:00')
    assert powers == [-16, 0, 0, 0, 0]
    assert soc == [90] * 5


def test_charge_window_and_target():
    params = BatteryParams(10, 100, 50, 10, 90, 1, 1)
    powers, _, _ = dispatch([0, 105, 95], ['12:00', '23:00', '23:15'], 15, params, 100, '23:00', '06:00')
    assert powers == [0, 5, -5]


@pytest.mark.parametrize('kwargs', [dict(energy_kwh=0), dict(power_kw=float('nan')), dict(charge_efficiency=1.1), dict(initial_soc_pct=95), dict(soc_min_pct=95)])
def test_invalid_params(kwargs):
    values = dict(power_kw=20, energy_kwh=100, initial_soc_pct=50, soc_min_pct=10, soc_max_pct=90, charge_efficiency=0.9, discharge_efficiency=0.9)
    values.update(kwargs)
    with pytest.raises(ValueError):
        dispatch([100], ['18:00'], 15, BatteryParams(**values), 100, '23:00', '06:00')


def test_real_battery_shared_physics_and_local_api():
    config = load_config_dir(CONFIG)
    original = deepcopy(config)
    baseline = run_simulation(PAYLOAD, config)
    payload = PAYLOAD | dict(bess_override=dict(power_kw=100, energy_kwh=500, initial_soc_pct=80))
    result = run_simulation(payload, config)
    assert config == original
    assert baseline['bess'] is None
    assert result['summary']['peak_loading_pct'] < baseline['summary']['peak_loading_pct']
    assert result['summary']['peak_hotspot_c'] < baseline['summary']['peak_hotspot_c']
    assert result['summary']['min_voltage_pu'] > baseline['summary']['min_voltage_pu']
    assert result['summary']['daily_equivalent_aging_hours'] < baseline['summary']['daily_equivalent_aging_hours']
    assert len(result['series']['bess_kw']) == len(result['series']['bess_soc_pct']) == 96
    assert all(10 <= soc <= 90 for soc in result['series']['bess_soc_pct'])
    assert all(abs(power) <= 100 for power in result['series']['bess_kw'])
    for i, power in enumerate(result['series']['bess_kw']):
        assert result['series']['net_kw'][i] == pytest.approx(result['series']['base_kw'][i] + result['series']['ev_kw'][i] - result['series']['pv_kw'][i] - power, abs=0.0002)
    status, body = handler.handle_request('POST', '/v2/simulate', json.dumps(payload), config)
    assert status == 200 and body == result
    json.dumps(body, allow_nan=False)
    assert run_simulation(PAYLOAD, config) == baseline
    assert run_simulation(payload, config) == result


@pytest.mark.parametrize('override', [dict(power_kw=10, energy_kwh=20, discharge_efficiency=0), dict(power_kw=10, energy_kwh=20, initial_soc_pct=99), dict(power_kw=10, energy_kwh=20, soc_min_pct=80, soc_max_pct=20)])
def test_invalid_override_api(override):
    status, body = handler.handle_request('POST', '/v2/simulate', json.dumps(PAYLOAD | dict(bess_override=override)), load_config_dir(CONFIG))
    assert status == 400
    assert body['error']['field'].startswith('bess_override')

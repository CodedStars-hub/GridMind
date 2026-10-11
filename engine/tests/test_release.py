"""Release ZIP runs the battery/telemetry adapter without repository imports."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('package_api', ROOT / 'scripts/package_api.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


def test_package_requires_dispatch_module(tmp_path):
    for folder in ('lambda', 'engine/gridmind_engine', 'config'):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    (tmp_path / 'engine/gridmind_engine/telemetry.py').unlink()
    with pytest.raises(ValueError, match='missing required'):
        packaging.application_files(tmp_path)


def test_isolated_package_runs_release_workflow(tmp_path):
    path = packaging.build_package(tmp_path / 'release.zip')
    with zipfile.ZipFile(path) as archive:
        assert 'gridmind_engine/telemetry.py' in archive.namelist()
        assert 'gridmind_engine/bess.py' in archive.namelist()
        archive.extractall(tmp_path / 'app')
    script = '''
import json, os
os.environ['GRIDMIND_ALLOWED_ORIGINS']='["https://demo.example"]'
from handler import lambda_handler

def call(path, payload=None, method='POST'):
    event=dict(version='2.0',rawPath='/v2/'+path,requestContext={'http':{'method':method}},headers={'Origin':'https://demo.example'},body=json.dumps(payload) if payload is not None else None,isBase64Encoded=False)
    response=lambda_handler(event,None)
    assert response['statusCode'] in (200,204), response
    assert response['headers']['Access-Control-Allow-Origin']=='https://demo.example'
    return json.loads(response['body']) if response['body'] else None
assert call('health',method='GET')['status']=='ok'
request=dict(ev_kw=50,pv_kwp=30,day_type='summer_weekday',load_level='heavy',bess_override=dict(power_kw=100,energy_kwh=500,initial_soc_pct=80))
simulation=call('simulate',request)
assert len(simulation['series']['bess_kw'])==96 and simulation['bess']
replay=call('telemetry/replay',dict(scenario=request,start_time='2026-01-01T00:00:00Z'))
record=replay['records'][0]
advisory=call('dispatch/evaluate',dict(telemetry=record,now=record['timestamp'],previous_timestamp=None,battery=replay['battery']))
assert advisory['simulated'] and advisory['published'] is False
call('dispatch/evaluate',method='OPTIONS')
print('PASS isolated Lambda package: BESS, replay, advisory, CORS, OPTIONS')
'''
    result = subprocess.run([sys.executable, '-I', '-c', "import sys; sys.path.insert(0, '.');" + script], cwd=tmp_path / 'app', capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout

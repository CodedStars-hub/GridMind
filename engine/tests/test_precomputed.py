"""Snapshots must reproduce with current source/configuration and finite JSON."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('precompute', ROOT / 'scripts/precompute.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_snapshot_reproducibility():
    path = ROOT / 'frontend/public/precomputed/scenarios.json'
    artifact = json.loads(path.read_text())
    expected = module.generate(artifact['generated_at'])
    assert expected == artifact
    assert json.dumps(expected, indent=2, allow_nan=False) + '\n' == path.read_text()
    assert len(artifact['artifacts']) == 3
    assert len(artifact['model_sha256']) == 64
    assert all(item['result']['meta']['source'] == 'cached' for item in artifact['artifacts'])

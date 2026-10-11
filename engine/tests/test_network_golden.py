"""Protect every M7 response field with fixed pre-M8 canonical JSON digests."""
import hashlib
import json
from pathlib import Path

import pytest
from gridmind_engine.network import assess_network
from gridmind_engine.profiles import load_config_dir

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((Path(__file__).parent / 'fixtures/network_m7_golden.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=['baseline', 'unmanaged', 'managed'])
def test_m7_full_response_golden(case):
    result = assess_network(case['payload'], load_config_dir(ROOT / 'config'))
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == case['sha256']

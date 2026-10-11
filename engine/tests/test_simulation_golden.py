"""Full pre-M7 outputs guard series, summaries, alerts, metadata and rounding."""

import json
from pathlib import Path

import pytest

from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import run_simulation

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((Path(__file__).parent / 'fixtures/simulation_golden.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=[
    'quiet-winter', 'default-summer', 'stress-summer',
    'moderate-weekend', 'heavy-winter', 'critical-weekend',
])
def test_pre_network_full_result(case):
    """Compare against captured results, never regenerate expectations in this test."""
    assert run_simulation(case['payload'], load_config_dir(ROOT / 'config')) == case['result']

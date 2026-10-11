"""Check new shapes and preserve every original profile byte."""

import math
from pathlib import Path
import subprocess
import sys

from gridmind_engine.profiles import load_config_dir

ROOT = Path(__file__).resolve().parents[2]


def test_new_profiles_and_reference_samples():
    config = load_config_dir(ROOT / 'config')
    for stem in ('base_load_commercial_profile', 'base_load_mixed_profile', 'ev_daytime_profile'):
        entries = config[stem]['parameters']
        assert set(entries) == {'summer_weekday', 'winter_weekday', 'weekend'}
        for entry in entries.values():
            values = entry['value']
            assert len(values) == 96
            assert all(math.isfinite(v) and 0 <= v <= 1 for v in values)
            assert max(values) == 1.0
    commercial = config['base_load_commercial_profile']['parameters']['summer_weekday']['value']
    assert commercial[0] == .35
    assert commercial[52] == 1.0
    assert commercial[84] == .55
    daytime = config['ev_daytime_profile']['parameters']
    assert daytime['summer_weekday']['value'][60] == 1.0
    assert daytime['summer_weekday']['value'][0] == .02
    assert daytime['weekend']['value'][56] == 1.0
    assert daytime['summer_weekday']['value'] == daytime['winter_weekday']['value']


def test_mixed_blend_identity():
    config = load_config_dir(ROOT / 'config')
    for day in ('summer_weekday', 'winter_weekday', 'weekend'):
        residential = config['base_load_profile']['parameters'][day]['value']
        commercial = config['base_load_commercial_profile']['parameters'][day]['value']
        mixed = config['base_load_mixed_profile']['parameters'][day]['value']
        blend = [.5 * (r + c) for r, c in zip(residential, commercial)]
        peak = max(blend)
        assert max(mixed) == 1.0
        assert all(abs(m * peak - b) <= 1e-3 for m, b in zip(mixed, blend))


def test_all_seven_regenerate_identically(tmp_path):
    command = [sys.executable, str(ROOT / 'scripts' / 'generate_profiles.py'), '--output-dir', str(tmp_path)]
    subprocess.run(command, check=True)
    first = {p.name: p.read_bytes() for p in tmp_path.glob('*.json')}
    subprocess.run(command, check=True)
    second = {p.name: p.read_bytes() for p in tmp_path.glob('*.json')}
    actual = {p.name: p.read_bytes() for p in (ROOT / 'config' / 'profiles').glob('*.json')}
    assert len(first) == 7
    assert first == second == actual


def test_original_profiles_unchanged_from_head():
    for name in ('base_load_profile', 'ev_profile', 'pv_profile', 'ambient_profile'):
        relative = f'config/profiles/{name}.json'
        original = subprocess.check_output(['git', 'show', f'HEAD:{relative}'], cwd=ROOT)
        assert (ROOT / relative).read_bytes() == original

"""Check authored samples, load scaling and profile regeneration without repo writes."""

from copy import deepcopy
from dataclasses import fields, FrozenInstanceError
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from gridmind_engine.profiles import build_load_series, get_day_profiles, load_config_dir
from gridmind_engine.validate import validate_request

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def config():
    return load_config_dir(ROOT / 'config')


def inputs(config, *, ev=50, pv=30, level='heavy'):
    return validate_request(dict(ev_kw=ev, pv_kwp=pv, day_type='summer_weekday', load_level=level), config['scenarios'])


def test_all_profile_lengths_ranges_and_peaks(config):
    for day in ('summer_weekday', 'winter_weekday', 'weekend'):
        profiles = get_day_profiles(config, day)
        for field in fields(profiles):
            values = getattr(profiles, field.name)
            assert isinstance(values, tuple)
            assert len(values) == 96
            assert all(math.isfinite(value) for value in values)
            if field.name != 'ambient_c':
                assert all(0 <= value <= 1 for value in values)
        assert max(profiles.base_shape) == 1.0
        assert max(profiles.ev_shape) == 1.0
        assert max(profiles.pv_shape) == (0.65 if day == 'winter_weekday' else 0.80)


def test_summer_hand_computed_samples(config):
    profiles = get_day_profiles(config, 'summer_weekday')
    for index, expected in [(12, .42), (48, .72), (84, 1.0), (38, .6617), (0, .55), (95, .60)]:
        assert profiles.base_shape[index] == pytest.approx(expected, abs=1e-4)
    for index, expected in [(76, 1.0), (70, .775), (90, .375)]:
        assert profiles.ev_shape[index] == pytest.approx(expected)
    for index, expected in [(0, 0), (30, .19), (48, .80), (80, 0)]:
        assert profiles.pv_shape[index] == pytest.approx(expected)
    for index, expected in [(20, 30), (54, 42), (60, 43)]:
        assert profiles.ambient_c[index] == expected


def test_winter_samples_and_weekend(config):
    winter = get_day_profiles(config, 'winter_weekday')
    assert winter.ambient_c[24] == 7
    assert winter.pv_shape[48] == .65
    assert winter.base_shape[80] == 1.0
    summer = get_day_profiles(config, 'summer_weekday')
    weekend = get_day_profiles(config, 'weekend')
    assert weekend.ev_shape[76] == 1.0
    assert weekend.pv_shape == summer.pv_shape
    assert weekend.ambient_c == summer.ambient_c
    assert winter.ev_shape == summer.ev_shape


def test_load_series_hand_computed_samples(config):
    series = build_load_series(inputs(config), config)
    for field in fields(series):
        assert isinstance(getattr(series, field.name), tuple)
        assert len(getattr(series, field.name)) == 96
    assert series.time[0] == '00:00'
    assert series.time[95] == '23:45'
    assert series.time[38] == '09:30'
    assert series.base_kw[84] == 175.0
    assert series.ev_kw[76] == 50.0
    assert series.pv_kw[48] == 24.0
    assert series.ambient_c[60] == 43.0
    assert build_load_series(inputs(config, level='moderate'), config).base_kw[84] == 137.5
    assert build_load_series(inputs(config, level='critical'), config).base_kw[84] == 212.5
    with pytest.raises(FrozenInstanceError):
        series.base_kw = ()
    with pytest.raises(FrozenInstanceError):
        get_day_profiles(config, 'summer_weekday').base_shape = ()


def test_ev_scaling_and_zero_pv(config):
    small = build_load_series(inputs(config, ev=10, pv=0), config)
    large = build_load_series(inputs(config, ev=100), config)
    assert all(a < b for a, b in zip(small.ev_kw, large.ev_kw))
    assert all(value == 0 for value in small.pv_kw)


def test_regeneration_is_byte_identical(tmp_path):
    output = tmp_path / 'generated'
    command = [sys.executable, str(ROOT / 'scripts' / 'generate_profiles.py'), '--output-dir', str(output)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    first = {path.name: path.read_bytes() for path in output.glob('*.json')}
    subprocess.run(command, check=True, capture_output=True, text=True)
    second = {path.name: path.read_bytes() for path in output.glob('*.json')}
    actual = {path.name: path.read_bytes() for path in (ROOT / 'config' / 'profiles').glob('*.json')}
    assert len(first) == 4
    assert first == second == actual


def test_missing_config_directory(tmp_path):
    missing = tmp_path / 'missing'
    with pytest.raises(ValueError) as caught:
        load_config_dir(missing)
    assert str(missing) in str(caught.value)


def test_invalid_json_and_missing_file(tmp_path):
    target = tmp_path / 'config'
    shutil.copytree(ROOT / 'config', target)
    path = target / 'profiles' / 'ev_profile.json'
    for contents in ('{', '{"parameters": {"sample": NaN}}'):
        path.write_text(contents)
        with pytest.raises(ValueError) as caught:
            load_config_dir(target)
        assert str(path) in str(caught.value)
    path.unlink()
    with pytest.raises(ValueError) as caught:
        load_config_dir(target)
    assert str(path) in str(caught.value)


def test_loader_includes_top_level_and_profiles(config):
    assert {'transformer', 'limits', 'scenarios', 'load_levels', 'bess', 'costs',
            'base_load_profile', 'ev_profile', 'pv_profile', 'ambient_profile'} <= set(config)


@pytest.mark.parametrize('stem', ['ambient_profile', 'base_load_profile', 'ev_profile', 'pv_profile'])
def test_invalid_profile_samples(config, stem):
    for value in (float('nan'), float('inf'), True, '1'):
        modified = deepcopy(config)
        modified[stem]['parameters']['summer_weekday']['value'][0] = value
        with pytest.raises(ValueError) as caught:
            get_day_profiles(modified, 'summer_weekday')
        assert f'{stem}.json' in str(caught.value)
        assert 'summer_weekday' in str(caught.value)


def test_invalid_shape_bounds_and_length(config):
    for values in ([0] * 95, [-.1] * 96, [1.1] * 96):
        modified = deepcopy(config)
        modified['base_load_profile']['parameters']['summer_weekday']['value'] = values
        with pytest.raises(ValueError, match='base_load_profile.json: summer_weekday'):
            get_day_profiles(modified, 'summer_weekday')


def test_missing_day_names_file_and_day(config):
    with pytest.raises(ValueError, match='ambient_profile.json: missing_day'):
        get_day_profiles(config, 'missing_day')


def test_bad_timing_config(config):
    config['scenarios']['parameters']['step_minutes']['value'] = 0
    with pytest.raises(ValueError, match='step_minutes'):
        build_load_series(inputs(config), config)

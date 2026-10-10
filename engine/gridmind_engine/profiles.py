"""Read config and build immutable load series; no electrical or thermal solver."""

from dataclasses import dataclass
import json
import math
from pathlib import Path

# Time and percentage unit conversions, not model or profile values.
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24


def load_config_dir(config_dir):
    """Read top-level and profile JSON, keyed by stem; errors identify their path."""
    root = Path(config_dir)
    for directory in (root, root / 'profiles'):
        if not directory.is_dir():
            raise ValueError(f'{directory}: config directory is missing')
    required = ('scenarios', 'transformer', 'limits', 'costs', 'bess', 'load_levels')
    profile_names = ('base_load_profile', 'ev_profile', 'pv_profile', 'ambient_profile')
    for directory, names in ((root, required), (root / 'profiles', profile_names)):
        for name in names:
            path = directory / f'{name}.json'
            if not path.is_file():
                raise ValueError(f'{path}: config file is missing')
    config = {}
    for directory in (root, root / 'profiles'):
        for path in sorted(directory.glob('*.json')):
            try:
                # JSON has no NaN or Infinity values, even if Python can parse them.
                data = json.loads(path.read_text(encoding='utf-8'), parse_constant=_invalid_constant)
                if not isinstance(data, dict) or not isinstance(data.get('parameters'), dict):
                    raise ValueError('expected an object containing parameters')
                if path.stem in config:
                    raise ValueError('duplicate config file stem')
            except (OSError, UnicodeError, ValueError) as exc:
                raise ValueError(f'{path}: {exc}') from exc
            config[path.stem] = data
    return config


def _invalid_constant(value):
    """Reject non-standard numeric tokens in JSON."""
    raise ValueError(f'invalid JSON number {value}')


def _value(config, stem, key):
    """Retrieve a parameter value and name its source when it is absent."""
    try:
        value = config[stem]['parameters'][key]['value']
    except (KeyError, TypeError) as exc:
        raise ValueError(f'{stem}.json: {key} is missing') from exc
    if value is None:
        raise ValueError(f'{stem}.json: {key} has no value')
    return value


def _positive_number(value, name):
    """Require a finite, positive numeric config value."""
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{name} must be a finite positive number')
    return value


def _timing(config):
    """Get positive integer timing settings that span exactly one day."""
    values = []
    for key in ('step_minutes', 'steps_per_day'):
        value = _value(config, 'scenarios', key)
        if type(value) is not int or value <= 0:
            raise ValueError(f'scenarios.json: {key} must be a positive integer')
        values.append(value)
    step_minutes, steps = values
    if step_minutes * steps != MINUTES_PER_HOUR * HOURS_PER_DAY:
        raise ValueError('scenarios.json: step_minutes and steps_per_day must span one day')
    return step_minutes, steps


@dataclass(frozen=True)
class DayProfiles:
    """Validated immutable ambient samples and normalized base, EV and PV shapes."""

    ambient_c: tuple[float, ...]
    base_shape: tuple[float, ...]
    ev_shape: tuple[float, ...]
    pv_shape: tuple[float, ...]


def get_day_profiles(config, day_type):
    """Read one day from loaded config; validate lengths, numbers and shape bounds."""
    _, steps = _timing(config)
    series = {}
    for field, stem in (
        ('ambient_c', 'ambient_profile'), ('base_shape', 'base_load_profile'),
        ('ev_shape', 'ev_profile'), ('pv_shape', 'pv_profile'),
    ):
        name = f'{stem}.json: {day_type}'
        values = _value(config, stem, day_type)
        if not isinstance(values, list) or len(values) != steps:
            raise ValueError(f'{name} must contain exactly {steps} samples')
        for index, value in enumerate(values):
            try:
                valid = type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError(f'{name}: sample {index} must be finite numeric data')
            if field != 'ambient_c' and not 0 <= value <= 1:
                raise ValueError(f'{name}: sample {index} must be within [0, 1]')
        series[field] = tuple(values)
    return DayProfiles(**series)


@dataclass(frozen=True)
class LoadSeries:
    """Immutable step labels, ambient temperatures and scaled real-power series."""

    time: tuple[str, ...]
    ambient_c: tuple[float, ...]
    base_kw: tuple[float, ...]
    ev_kw: tuple[float, ...]
    pv_kw: tuple[float, ...]


def build_load_series(inputs, config):
    """Scale profile shapes using validated inputs and config-provided base peaks."""
    step_minutes, steps = _timing(config)
    profiles = get_day_profiles(config, inputs.day_type)
    peak_key = f'{inputs.load_level}_base_peak_pct_of_rating'
    peak_pct = _positive_number(_value(config, 'load_levels', peak_key), f'load_levels.json: {peak_key}')
    rated_kva = _positive_number(_value(config, 'transformer', 'rated_kva'), 'transformer.json: rated_kva')
    # 100 converts the configured base-peak percentage to a fraction.
    base_peak_kw = (peak_pct / 100) * rated_kva
    series = {
        'base_kw': tuple(value * base_peak_kw for value in profiles.base_shape),
        'ev_kw': tuple(inputs.ev_kw * value for value in profiles.ev_shape),
        'pv_kw': tuple(inputs.pv_kwp * value for value in profiles.pv_shape),
    }
    for field, values in series.items():
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f'{field} contains non-finite scaled profile data')
    labels = []
    for index in range(steps):
        hour, minute = divmod(index * step_minutes, MINUTES_PER_HOUR)
        labels.append(f'{hour:02d}:{minute:02d}')
    return LoadSeries(time=tuple(labels), ambient_c=profiles.ambient_c, **series)

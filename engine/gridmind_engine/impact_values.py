"""Small numerical checks shared by impact calculations; no model assumptions."""

import math


def number(value, name, *, positive=False, nonnegative=False):
    """Require a finite real number, explicitly rejecting booleans."""
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
        valid = valid and (not positive or value > 0) and (not nonnegative or value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        qualifier = 'positive ' if positive else 'non-negative ' if nonnegative else ''
        raise ValueError(f'{name} must be a finite {qualifier}number')
    return value


def samples(values, name, *, positive=False, nonnegative=False):
    """Validate a nonempty series before integration or extrema."""
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f'{name} must be a nonempty series')
    return tuple(number(value, f'{name}[{index}]', positive=positive, nonnegative=nonnegative)
                 for index, value in enumerate(values))


def count(value, name, *, allow_missing=False):
    """Validate customer/day counts; None is permitted only where documented."""
    if value is None and allow_missing:
        return None
    if type(value) is not int or value < 0:
        raise ValueError(f'{name} must be a non-negative integer')
    return value


def finite_result(value, name):
    """Check completed calculations so overflow never reaches a JSON response."""
    if isinstance(value, dict):
        for key, item in value.items():
            finite_result(item, f'{name}.{key}')
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            finite_result(item, f'{name}[{index}]')
    elif type(value) in (int, float):
        number(value, name)
    return value


def finite_sum(values, name):
    """Sum accurately and report unrepresentable totals as a named input error."""
    try:
        value = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f'{name} cannot be represented finitely') from exc
    return number(value, name)

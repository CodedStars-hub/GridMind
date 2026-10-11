"""Reference-equivalent aging comparisons, not actual remaining service life."""

import math

from .impact_values import count, finite_result, finite_sum, number, samples
from .profiles import HOURS_PER_DAY, MINUTES_PER_HOUR


def equivalent_aging_hours(aging_factors, step_minutes):
    """Integrate unrounded FAA samples over equal-duration intervals."""
    factors = samples(aging_factors, 'aging_factors', nonnegative=True)
    step_hours = number(number(step_minutes, 'step_minutes', positive=True) / MINUTES_PER_HOUR,
                        'step_hours', positive=True)
    try:
        value = math.fsum(factor * step_hours for factor in factors)
    except (OverflowError, ValueError) as exc:
        raise ValueError('equivalent_aging_hours cannot be represented finitely') from exc
    return number(value, 'equivalent_aging_hours', nonnegative=True)


def _percentage_change(before, after):
    """Zero denominator means undefined, represented by null, not zero percent."""
    return None if before == 0 else (after - before) / before * 100


def compare_life(baseline_days, ev_days, step_minutes, day_counts, calendar_days_per_year):
    """Compare aligned representative days and their configured monthly weights.

    Calendar conversions use actual simulated day length and configured year days.
    All arithmetic remains unrounded; additional values retain their signs.
    """
    number(calendar_days_per_year, 'calendar_days_per_year', positive=True)
    if not all(isinstance(value, dict) for value in (baseline_days, ev_days, day_counts)):
        raise ValueError('scenario days and day_counts must be dictionaries')
    if set(baseline_days) != set(ev_days) or set(baseline_days) != set(day_counts):
        raise ValueError('day identities must match baseline, EV scenario and day_counts')
    if not day_counts:
        raise ValueError('day_counts cannot be empty')
    step_hours = number(number(step_minutes, 'step_minutes', positive=True) / MINUTES_PER_HOUR,
                        'step_hours', positive=True)
    days = {}
    lengths = set()
    for day, weight in day_counts.items():
        count(weight, f'day_counts.{day}')
        baseline, ev = baseline_days[day], ev_days[day]
        for scenario, series in (('baseline', baseline), ('ev', ev)):
            try:
                faa = samples(series['aging_factor'], f'{scenario}.{day}.aging_factor', nonnegative=True)
                hotspot = samples(series['hotspot_c'], f'{scenario}.{day}.hotspot_c')
            except (KeyError, TypeError) as exc:
                raise ValueError(f'{scenario}.{day} requires aging_factor and hotspot_c series') from exc
            if len(faa) != len(hotspot):
                raise ValueError(f'{scenario}.{day} series lengths must match')
            lengths.add(len(faa))
        if len(lengths) != 1:
            raise ValueError('scenario and day series lengths must match')
        hours = number(len(baseline['aging_factor']) * step_hours, 'day_hours', positive=True)
        if hours != HOURS_PER_DAY:
            raise ValueError('representative daily series must span a full calendar day')
        before = equivalent_aging_hours(baseline['aging_factor'], step_minutes)
        after = equivalent_aging_hours(ev['aging_factor'], step_minutes)
        days[day] = dict(
            baseline_equivalent_aging_hours=before, ev_equivalent_aging_hours=after,
            additional_equivalent_aging_hours=after - before,
            baseline_aging_ratio=before / hours, ev_aging_ratio=after / hours,
            aging_change_pct=_percentage_change(before, after),
            baseline_peak_hotspot_c=max(baseline['hotspot_c']),
            ev_peak_hotspot_c=max(ev['hotspot_c']),
            peak_hotspot_change_c=max(ev['hotspot_c']) - max(baseline['hotspot_c']),
        )
    calendar_days = sum(day_counts.values())
    if calendar_days <= 0:
        raise ValueError('day_counts must represent a positive month')
    before = finite_sum((day_counts[day] * value['baseline_equivalent_aging_hours'] for day, value in days.items()), 'baseline_month_hours')
    after = finite_sum((day_counts[day] * value['ev_equivalent_aging_hours'] for day, value in days.items()), 'ev_month_hours')
    year_hours = number(hours * calendar_days_per_year, 'reference_year_hours', positive=True)
    month = dict(
        calendar_days=calendar_days,
        baseline_equivalent_aging_hours=before, ev_equivalent_aging_hours=after,
        additional_equivalent_aging_hours=after - before,
        baseline_reference_equivalent_years=before / year_hours,
        ev_reference_equivalent_years=after / year_hours,
        additional_reference_equivalent_years=(after - before) / year_hours,
        baseline_aging_ratio=before / (hours * calendar_days),
        ev_aging_ratio=after / (hours * calendar_days),
        aging_change_pct=_percentage_change(before, after),
    )
    return finite_result(dict(days=days, month=month), 'life')

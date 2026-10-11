"""Illustrative value of reference insulation aging; no BESS cost comparison."""

from .impact_values import finite_result, number


def economic_aging_proxy(equivalent_hours, reference_life_hours, replacement_value_inr):
    """Value a signed reference-life fraction using a configured equipment proxy."""
    number(equivalent_hours, 'equivalent_hours')
    number(reference_life_hours, 'reference_life_hours', positive=True)
    number(replacement_value_inr, 'replacement_value_inr', nonnegative=True)
    return number((equivalent_hours / reference_life_hours) * replacement_value_inr,
                  'economic_aging_proxy_inr')


def compare_economic(month, reference_life_hours, replacement_value_inr):
    """Return absolute and additional monthly proxies without intermediate rounding."""
    before = month['baseline_equivalent_aging_hours']
    after = month['ev_equivalent_aging_hours']
    number(before, 'baseline_equivalent_aging_hours', nonnegative=True)
    number(after, 'ev_equivalent_aging_hours', nonnegative=True)
    before_value = economic_aging_proxy(before, reference_life_hours, replacement_value_inr)
    after_value = economic_aging_proxy(after, reference_life_hours, replacement_value_inr)
    return finite_result(dict(
        replacement_value_inr=replacement_value_inr,
        reference_insulation_life_hours=reference_life_hours,
        baseline_reference_life_fraction=before / reference_life_hours,
        ev_reference_life_fraction=after / reference_life_hours,
        additional_reference_life_fraction=(after - before) / reference_life_hours,
        baseline_aging_proxy_inr=before_value, ev_aging_proxy_inr=after_value,
        additional_aging_proxy_inr=economic_aging_proxy(after - before, reference_life_hours, replacement_value_inr),
    ), 'economic')

"""Pure insulation aging and capped life estimates using config parameters."""

from dataclasses import dataclass, fields
import math

# The requested aging convention uses 273, rather than 273.15, for Celsius to K.
KELVIN_OFFSET = 273
# Unit conversions, not engineering assumptions.
MINUTES_PER_HOUR = 60
DAYS_PER_YEAR = 365


def _finite(name, value, *, positive=False):
    """Reject invalid numbers with a clear field-specific message."""
    try:
        valid = not isinstance(value, bool) and math.isfinite(value)
        valid = valid and (not positive or value > 0)
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        requirement = 'positive and finite' if positive else 'finite'
        raise ValueError(f'{name} must be {requirement}')


@dataclass(frozen=True)
class AgingParams:
    """Aging constants, normal insulation life and the configurable display cap."""

    aging_constant: float
    aging_reference_kelvin: float
    normal_insulation_life_hours: float
    insulation_life_cap_years: float

    def __post_init__(self):
        for field in fields(self):
            _finite(field.name, getattr(self, field.name), positive=True)


def aging_params_from_config(limits_config_dict):
    """Build parameters from a loaded limits config without reading any files."""
    values = {}
    for field in fields(AgingParams):
        try:
            values[field.name] = limits_config_dict['parameters'][field.name]['value']
        except (KeyError, TypeError) as exc:
            raise ValueError(f'{field.name} is missing its config value') from exc
    return AgingParams(**values)


def aging_factor(hotspot_c, params):
    """Return aging acceleration at the absolute hot-spot temperature in C."""
    _finite('hotspot_c', hotspot_c)
    if hotspot_c <= -KELVIN_OFFSET:
        raise ValueError('hotspot_c must be above -KELVIN_OFFSET')
    exponent = (
        params.aging_constant / params.aging_reference_kelvin
        - params.aging_constant / (hotspot_c + KELVIN_OFFSET)
    )
    # Negative infinity can arise only from extremely low absolute temperature;
    # its exponential underflows safely to zero. Positive overflow is rejected.
    try:
        factor = math.exp(exponent)
    except OverflowError as exc:
        raise ValueError('hotspot_c and aging params produce an unrepresentable aging_factor') from exc
    _finite('aging_factor', factor)
    return factor


def daily_equivalent_aging_hours(hotspot_series_c, step_minutes, params):
    """Sum accelerated aging hours over the supplied constant-duration steps."""
    _finite('step_minutes', step_minutes, positive=True)
    hours_per_step = step_minutes / MINUTES_PER_HOUR
    try:
        hours = math.fsum(
            aging_factor(hotspot_c, params) * hours_per_step
            for hotspot_c in hotspot_series_c
        )
    except OverflowError as exc:
        raise ValueError('daily_equivalent_hours cannot be represented finitely') from exc
    _finite('daily_equivalent_hours', hours)
    return hours


def insulation_life_years(daily_equivalent_hours, params):
    """Return a finite life estimate, using the display cap for zero aging."""
    _finite('daily_equivalent_hours', daily_equivalent_hours)
    if daily_equivalent_hours <= 0:
        return params.insulation_life_cap_years
    # Compare before dividing by tiny aging values so the estimate cannot overflow.
    annual_base = params.normal_insulation_life_hours / DAYS_PER_YEAR
    if daily_equivalent_hours <= annual_base / params.insulation_life_cap_years:
        return params.insulation_life_cap_years
    life = annual_base / daily_equivalent_hours
    _finite('insulation_life_years', life)
    return min(life, params.insulation_life_cap_years)

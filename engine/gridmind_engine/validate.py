"""Validate request types and config-provided choices without reading files."""

from dataclasses import dataclass
import math


class InvalidInputError(Exception):
    """A request failure with the contract error code and offending field."""

    def __init__(self, field, message):
        self.code = 'invalid_input'
        self.field = field
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class BessOverride:
    """Custom battery power in kW and energy in kWh."""

    power_kw: float
    energy_kwh: float


@dataclass(frozen=True)
class ValidatedInputs:
    """Immutable scenario choices and optional custom battery size."""

    ev_kw: int
    pv_kwp: int
    day_type: str
    load_level: str
    bess: str
    bess_override: BessOverride | None


def validate_request(payload, scenarios_config):
    """Validate a parsed JSON object; allowed values come only from scenarios config."""
    if not isinstance(payload, dict):
        raise InvalidInputError('payload', 'Request payload must be a JSON object.')
    required = ('ev_kw', 'pv_kwp', 'day_type', 'load_level')
    allowed_keys = required + ('bess', 'bess_override')
    for key in payload:
        if key not in allowed_keys:
            raise InvalidInputError(str(key), f'Unknown request field: {key}.')
    for key in required:
        if key not in payload:
            raise InvalidInputError(key, f'{key} is required.')
    parameters = scenarios_config['parameters']
    values = {}
    for key in required + ('bess',):
        choices = parameters[f'{key}_options']['value']
        value = payload.get(key, parameters['default_bess']['value'])
        expected_type = int if key in ('ev_kw', 'pv_kwp') else str
        if type(value) is not expected_type or value not in choices:
            raise InvalidInputError(
                key, f'{key} must be an exact {expected_type.__name__}; allowed values: {choices}.'
            )
        values[key] = value
    override = payload.get('bess_override')
    if override is not None:
        if not isinstance(override, dict):
            raise InvalidInputError('bess_override', 'bess_override must be an object or null.')
        members = ('power_kw', 'energy_kwh')
        for key in override:
            if key not in members:
                raise InvalidInputError(f'bess_override.{key}', f'Unknown BESS override field: {key}.')
        for key in members:
            field = f'bess_override.{key}'
            if key not in override:
                raise InvalidInputError(field, f'{field} is required.')
            value = override[key]
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value > 0
            except OverflowError:
                valid = False
            if not valid:
                raise InvalidInputError(field, f'{field} must be a finite positive number, not a boolean.')
        override = BessOverride(**override)
    return ValidatedInputs(**values, bess_override=override)

"""Thin neighbourhood operations: validation and calls to the shared engine."""

from copy import deepcopy

from gridmind_engine import __version__
from gridmind_engine.hosting import assess_hosting
from gridmind_engine.impact import assess_impact
from gridmind_engine.network import _network_data, _value, assess_network, validate_allocation
from gridmind_engine.planner import plan_charging
from gridmind_engine.planner_sites import validate_plan_request
from gridmind_engine.validate import InvalidInputError

# Route identifiers, not model assumptions. Existing resource names stay intact.
METHODS = {'/health': 'GET', '/network': 'GET', '/assess': 'POST',
           '/impact': 'POST', '/hosting': 'POST', '/plan': 'POST'}


def build_network_response(config):
    """Project configured topology onto the existing section 3.4 response schema."""
    transformers, sites = _network_data(config)
    fields = ('id', 'name', 'archetype', 'load_level', 'ev_usage', 'connections', 'x', 'y')
    site_fields = ('id', 'name', 'transformer_id', 'footfall_score', 'max_kw', 'x', 'y')
    assumptions, names = [], set()
    for stem in ('neighbourhood', 'transformer', 'limits', 'costs', 'bess', 'load_levels'):
        for name, p in config[stem]['parameters'].items():
            if name in names:
                raise ValueError('duplicate network assumption name')
            names.add(name)
            assumptions.append(dict(name=name, value=deepcopy(p['value']), unit=p['unit'],
                                    note='; '.join(p[n] for n in ('source', 'assumption') if p.get(n))))
    return dict(meta=dict(engine_version=__version__, source='live', inputs={}),
                neighbourhood=dict(name=_value(config, 'neighbourhood', 'neighbourhood_name'),
                                   map=dict(width=100, height=100)),
                transformers=[dict(**{k: deepcopy(t[k]) for k in fields},
                                   rated_kva=_value(config, 'transformer', 'rated_kva')) for t in transformers],
                sites=[{k: deepcopy(s[k]) for k in site_fields} for s in sites],
                defaults=dict(target_kw=_value(config, 'neighbourhood', 'target_kw_default'),
                              month=dict(weekday_count=_value(config, 'neighbourhood', 'month_weekday_count'),
                                         weekend_count=_value(config, 'neighbourhood', 'month_weekend_count'))),
                enums=dict(target_kw=deepcopy(_value(config, 'neighbourhood', 'target_kw_options'))),
                assumptions=assumptions)


def invoke(route, payload, config):
    """Validate before invoking a public engine operation; never compute physics."""
    if route == '/health':
        return dict(status='ok', api_version='v2', engine_version=__version__)
    if route == '/network':
        return build_network_response(config)
    if route in ('/assess', '/impact'):
        validate_allocation(payload, config)
        return (assess_network if route == '/assess' else assess_impact)(payload, config)
    if route == '/hosting':
        if not isinstance(payload, dict):
            raise InvalidInputError('payload', 'Hosting request must be an empty object.')
        if payload:
            raise InvalidInputError(str(next(iter(payload))), 'Hosting accepts no scenario overrides.')
        return assess_hosting(config)
    if route == '/plan':
        validate_plan_request(payload, config)
        return plan_charging(payload, config)
    raise ValueError('unrecognized adapter operation')

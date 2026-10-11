"""Validate illustrative site demand and rank attractiveness, not feasibility."""

from copy import deepcopy

from .hosting import search_settings
from .impact_values import count, number
from .network import _network_data, _value
from .validate import InvalidInputError


def planning_sites(config):
    """Return detached candidates; absent demand uses the existing site ceiling.

    Eligibility defaults to candidate status, not verified land availability.
    No traffic, commercial-activity score or arbitrary data is fabricated.
    """
    _, block, _, _ = search_settings(config)
    _, sites = _network_data(config)
    weights = _value(config, 'neighbourhood', 'planner_score_weights')
    if not isinstance(weights, dict) or set(weights) != {'footfall'}:
        raise ValueError('planner_score_weights must contain only footfall')
    weight = number(weights['footfall'], 'planner_score_weights.footfall', positive=True)
    maximum = number(_value(config, 'neighbourhood', 'planner_footfall_max_score'),
                     'planner_footfall_max_score', positive=True)
    result = []
    for site in sites:
        name = f"site {site['id']}"
        if type(site.get('name')) is not str or not site['name']:
            raise ValueError(f'{name}.name must be a nonempty string')
        ceiling = count(site['max_kw'], f'{name}.max_kw')
        requested = count(site.get('requested_kw', ceiling), f'{name}.requested_kw')
        if ceiling % block or requested % block or requested > ceiling:
            raise ValueError(f'{name}.requested_kw and max_kw must be block multiples, requested <= max_kw')
        score = number(site.get('footfall_score'), f'{name}.footfall_score', positive=True)
        if score > maximum:
            raise ValueError(f'{name}.footfall_score must not exceed planner_footfall_max_score')
        eligible = site.get('eligible', True)
        if type(eligible) is not bool:
            raise ValueError(f'{name}.eligible must be boolean')
        normalized = score / maximum
        result.append(dict(site_id=site['id'], name=site['name'], transformer_id=site['transformer_id'],
                           requested_kw=requested, eligible=eligible, score=normalized * weight,
                           score_components=dict(footfall=score, normalized_footfall=normalized,
                                                 footfall_weight=weight)))
    return sorted(deepcopy(result), key=lambda item: (-item['score'], item['site_id']))


def validate_plan_request(payload, config):
    """Keep the exact existing /plan input: only configured target_kw is allowed."""
    if not isinstance(payload, dict):
        raise InvalidInputError('payload', 'Planning request must be an object.')
    for key in payload:
        if key != 'target_kw':
            raise InvalidInputError(str(key), 'Unknown planning request field.')
    options = _value(config, 'neighbourhood', 'target_kw_options')
    _, block, _, _ = search_settings(config)
    if not isinstance(options, list) or not options:
        raise ValueError('target_kw_options must contain unique integer block multiples')
    for option in options:
        count(option, 'target_kw_options')
        number(option, 'target_kw_options', nonnegative=True)
        if option % block:
            raise ValueError('target_kw_options must be allocation_block_kw multiples')
    if len(set(options)) != len(options):
        raise ValueError('target_kw_options must contain unique integer block multiples')
    target = payload.get('target_kw')
    if type(target) is not int or target not in options:
        raise InvalidInputError('target_kw', f'target_kw must be an integer in {options}.')
    return target

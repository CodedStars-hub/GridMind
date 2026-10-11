"""Local HTTP API v2.0 adapter for the shared GridMind engine."""

import base64
import binascii
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import traceback

import api_routes
from api_http import MAX_BODY_BYTES, cors_headers, parse_body

from gridmind_engine import __version__
from gridmind_engine.powerflow import PowerFlowError
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import run_simulation
from gridmind_engine.validate import InvalidInputError, validate_request

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
_config_cache = None


def reset_config_cache():
    """Discard the process-local config cache, primarily for isolated tests."""
    global _config_cache
    _config_cache = None


def get_config():
    """Load config once; callers must treat the shared cached dictionary as read-only."""
    global _config_cache
    if _config_cache is None:
        local = Path(__file__).resolve().parent / 'config'
        default = local if local.is_dir() else Path(__file__).resolve().parent.parent / 'config'
        directory = os.environ.get('GRIDMIND_CONFIG_DIR', default)
        _config_cache = load_config_dir(directory)
    return _config_cache


def build_scenarios_response(config):
    """Return enum choices and named assumptions without sharing mutable config values."""
    scenario = config['scenarios']['parameters']
    fields = ('ev_kw', 'pv_kwp', 'day_type', 'load_level', 'bess')
    assumptions = []
    names = set()
    for stem in ('transformer', 'limits', 'costs', 'bess', 'load_levels'):
        for name, entry in config[stem]['parameters'].items():
            if name in names:
                raise ValueError(f'duplicate assumption name: {name}')
            names.add(name)
            notes = [entry[key] for key in ('source', 'assumption') if entry.get(key)]
            assumptions.append(dict(name=name, value=deepcopy(entry['value']), unit=entry['unit'], note='; '.join(notes)))
    return dict(engine_version=__version__,
                enums={name: deepcopy(scenario[f'{name}_options']['value']) for name in fields},
                defaults={name: deepcopy(scenario[f'default_{name}']['value']) for name in fields},
                assumptions=assumptions)


def _error(status, code, message, field=None):
    """Build the public error shape with a present, nullable field."""
    return status, dict(error=dict(code=code, message=message, field=field))


def _path(path):
    """Remove trailing slashes and at most one complete leading api segment."""
    path = path.rstrip('/')
    if path == '/api':
        return '/'
    if path.startswith('/api/'):
        path = path.removeprefix('/api')
    return path


def _clock_ms():
    """Use logging's built-in millisecond clock, avoiding a separate unit constant."""
    return logging.makeLogRecord({}).relativeCreated


def _log(method, path, status, body, started, validated=None, exception_trace=None):
    """Emit one JSON record; rejected raw inputs never enter the request log."""
    record = dict(method=method, path=path, status=status,
                  duration_ms=_clock_ms() - started,
                  error_code=body.get('error', {}).get('code'))
    if validated is not None:
        for name in ('ev_kw', 'pv_kwp', 'day_type', 'load_level', 'bess'):
            record[name] = getattr(validated, name)
    if exception_trace is not None:
        record['traceback'] = exception_trace
    LOGGER.info(json.dumps(record, allow_nan=False))


def handle_request(method, path, body_text, config, headers=None):
    """Return deterministic routing results without mutating config; log one request."""
    started = _clock_ms()
    validated = None
    exception_trace = None
    try:
        route = _path(path)
        if route.startswith('/v2/'):
            route = route.removeprefix('/v2')
        cors_headers(headers)
        if route in ('/optimize', '/dispatch'):
            status, body = _error(404, 'not_found', 'route not available yet')
        elif route not in ('/scenarios', '/simulate', *api_routes.METHODS):
            status, body = _error(404, 'not_found', 'route not found')
        elif method == 'OPTIONS':
            status, body = 204, {}
        elif method != ({'/scenarios': 'GET', '/simulate': 'POST'} | api_routes.METHODS)[route]:
            status, body = _error(405, 'method_not_allowed', 'method not allowed')
        elif route == '/scenarios':
            status, body = 200, build_scenarios_response(config)
        elif method == 'GET':
            status, body = 200, api_routes.invoke(route, None, config)
        else:
            payload = parse_body(body_text)
            if route == '/simulate':
                validated = validate_request(payload, config['scenarios'])
                status, body = 200, run_simulation(payload, config)
            else:
                status, body = 200, api_routes.invoke(route, payload, config)
        # Catch serialization failures before the single request log is emitted.
        json.dumps(body, allow_nan=False)
    except InvalidInputError as exc:
        status, body = _error(400, exc.code, exc.message, exc.field)
    except NotImplementedError:
        status, body = _error(400, 'invalid_input', 'battery simulation is not available yet', 'bess')
    except PowerFlowError as exc:
        message = 'power-flow solver did not converge' if _path(path).startswith('/v2/') else str(exc)
        status, body = _error(500, 'convergence_failed', message)
    except Exception:
        exception_trace = traceback.format_exc()
        status, body = _error(500, 'internal_error', 'internal error')
    _log(method, path, status, body, started, validated, exception_trace)
    return status, body


def _response(status, body, headers=None):
    """Serialize the HTTP API proxy response with consistent JSON and cache headers."""
    return dict(statusCode=status,
                headers={'Content-Type': 'application/json', 'Cache-Control': 'no-store', **(headers or {})},
                body='' if status == 204 else json.dumps(body, allow_nan=False))


def lambda_handler(event, context):
    """Decode an HTTP API event; each path emits exactly one structured log record."""
    started = _clock_ms()
    method = path = None
    response_headers = {}
    try:
        if not isinstance(event, dict):
            raise InvalidInputError('event', 'event must be an HTTP API object')
        if event.get('version', '2.0') != '2.0':
            raise InvalidInputError('event', 'only HTTP API payload version 2.0 is supported')
        try:
            method = event['requestContext']['http']['method']
            path = event['rawPath']
        except (KeyError, TypeError):
            raise InvalidInputError('event', 'event must contain method and rawPath') from None
        if not isinstance(method, str) or not method or not isinstance(path, str) or not path:
            raise InvalidInputError('event', 'event must contain method and rawPath')
        body_text = event.get('body')
        if type(event.get('isBase64Encoded', False)) is not bool:
            raise InvalidInputError('event', 'isBase64Encoded must be boolean')
        response_headers = cors_headers(event.get('headers'))
        if method == 'OPTIONS':
            response_headers.update({'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                                     'Access-Control-Allow-Headers': 'Content-Type'})
        if event.get('isBase64Encoded'):
            try:
                if not isinstance(body_text, str):
                    raise ValueError('missing encoded body')
                # Bound encoded input before allocating its decoded representation.
                if len(body_text) > ((MAX_BODY_BYTES + 2) // 3) * 4:
                    raise InvalidInputError('body', 'request body is too large')
                body_text = base64.b64decode(body_text, validate=True).decode('utf-8')
            except (ValueError, UnicodeError, binascii.Error):
                raise InvalidInputError('body', 'request body must be valid base64-encoded UTF-8') from None
        config = get_config()
    except InvalidInputError as exc:
        status, body = _error(400, exc.code, exc.message, exc.field)
        _log(method, path, status, body, started)
        return _response(status, body, response_headers)
    except Exception:
        status, body = _error(500, 'internal_error', 'internal error')
        _log(method, path, status, body, started, exception_trace=traceback.format_exc())
        return _response(status, body, response_headers)
    status, body = handle_request(method, path, body_text, config, event.get('headers'))
    return _response(status, body, response_headers)

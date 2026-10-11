"""Local HTTP API v2.0 adapter for the shared GridMind engine."""

import base64
import binascii
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import traceback

from gridmind_engine import __version__
from gridmind_engine.powerflow import PowerFlowError
from gridmind_engine.profiles import load_config_dir
from gridmind_engine.simulate import run_simulation
from gridmind_engine.validate import InvalidInputError, validate_request

# Limit the decoded UTF-8 request body before JSON parsing.
MAX_BODY_BYTES = 2048
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
        directory = os.environ.get('GRIDMIND_CONFIG_DIR', Path(__file__).resolve().parent.parent / 'config')
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


def _reject_constant(value):
    """Reject non-standard JSON numeric tokens without echoing them."""
    raise ValueError('non-finite JSON number')


def handle_request(method, path, body_text, config):
    """Return deterministic routing results without mutating config; log one request."""
    started = _clock_ms()
    validated = None
    exception_trace = None
    try:
        route = _path(path)
        if route in ('/optimize', '/dispatch'):
            status, body = _error(404, 'not_found', 'route not available yet')
        elif route not in ('/scenarios', '/simulate'):
            status, body = _error(404, 'not_found', 'route not found')
        elif (route == '/scenarios' and method != 'GET') or (route == '/simulate' and method != 'POST'):
            status, body = _error(405, 'method_not_allowed', 'method not allowed')
        elif route == '/scenarios':
            status, body = 200, build_scenarios_response(config)
        else:
            if not isinstance(body_text, str) or not body_text.strip():
                raise InvalidInputError('body', 'request body is required')
            try:
                body_bytes = body_text.encode('utf-8')
            except UnicodeError:
                raise InvalidInputError('body', 'request body must be valid UTF-8') from None
            if len(body_bytes) > MAX_BODY_BYTES:
                raise InvalidInputError('body', 'request body is too large')
            try:
                payload = json.loads(body_text, parse_constant=_reject_constant)
            except (ValueError, UnicodeError):
                raise InvalidInputError('body', 'request body must be valid JSON') from None
            validated = validate_request(payload, config['scenarios'])
            status, body = 200, run_simulation(payload, config)
        # Catch serialization failures before the single request log is emitted.
        json.dumps(body, allow_nan=False)
    except InvalidInputError as exc:
        status, body = _error(400, exc.code, exc.message, exc.field)
    except NotImplementedError:
        status, body = _error(400, 'invalid_input', 'battery simulation is not available yet', 'bess')
    except PowerFlowError as exc:
        status, body = _error(500, 'convergence_failed', str(exc))
    except Exception:
        exception_trace = traceback.format_exc()
        status, body = _error(500, 'internal_error', 'internal error')
    _log(method, path, status, body, started, validated, exception_trace)
    return status, body


def _response(status, body):
    """Serialize the HTTP API proxy response with consistent JSON and cache headers."""
    return dict(statusCode=status,
                headers={'Content-Type': 'application/json', 'Cache-Control': 'no-store'},
                body=json.dumps(body, allow_nan=False))


def lambda_handler(event, context):
    """Decode an HTTP API event; each path emits exactly one structured log record."""
    started = _clock_ms()
    method = path = None
    try:
        if not isinstance(event, dict):
            raise InvalidInputError('event', 'event must be an HTTP API object')
        try:
            method = event['requestContext']['http']['method']
            path = event['rawPath']
        except (KeyError, TypeError):
            raise InvalidInputError('event', 'event must contain method and rawPath') from None
        if not isinstance(method, str) or not method or not isinstance(path, str) or not path:
            raise InvalidInputError('event', 'event must contain method and rawPath')
        body_text = event.get('body')
        if event.get('isBase64Encoded'):
            try:
                if not isinstance(body_text, str):
                    raise ValueError('missing encoded body')
                body_text = base64.b64decode(body_text, validate=True).decode('utf-8')
            except (ValueError, UnicodeError, binascii.Error):
                raise InvalidInputError('body', 'request body must be valid base64-encoded UTF-8') from None
        config = get_config()
    except InvalidInputError as exc:
        status, body = _error(400, exc.code, exc.message, exc.field)
        _log(method, path, status, body, started)
        return _response(status, body)
    except Exception:
        status, body = _error(500, 'internal_error', 'internal error')
        _log(method, path, status, body, started, exception_trace=traceback.format_exc())
        return _response(status, body)
    status, body = handle_request(method, path, body_text, config)
    return _response(status, body)

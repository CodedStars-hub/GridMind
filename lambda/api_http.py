"""Strict JSON and an explicit, non-credentialed browser-origin allowlist."""

import json
import math
import os
from urllib.parse import urlsplit

from gridmind_engine.validate import InvalidInputError

# Existing API contract's decoded UTF-8 body limit.
MAX_BODY_BYTES = 2048


def _reject_constant(_):
    raise ValueError('non-finite JSON number')


def _float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('non-finite JSON number')
    return value


def _members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON member')
        result[key] = value
    return result


def parse_body(text):
    """Reject ambiguous or non-standard JSON before a scenario validator runs."""
    if not isinstance(text, str) or not text.strip():
        raise InvalidInputError('body', 'request body is required')
    try:
        encoded = text.encode('utf-8')
    except UnicodeError:
        raise InvalidInputError('body', 'request body must be valid UTF-8') from None
    if len(encoded) > MAX_BODY_BYTES:
        raise InvalidInputError('body', 'request body is too large')
    try:
        return json.loads(text, parse_constant=_reject_constant, parse_float=_float, object_pairs_hook=_members)
    except (ValueError, UnicodeError, RecursionError):
        raise InvalidInputError('body', 'request body must be valid JSON') from None


def allowed_origins():
    """Empty by default for same-origin access; never infer an approved origin."""
    try:
        origins = json.loads(os.environ.get('GRIDMIND_ALLOWED_ORIGINS', '[]'))
        if not isinstance(origins, list):
            raise ValueError()
        for origin in origins:
            if not isinstance(origin, str):
                raise ValueError()
            parsed = urlsplit(origin)
            if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.path
                    or parsed.query or parsed.fragment or parsed.username or parsed.password
                    or '*' in origin or any(c.isspace() or ord(c) < 32 for c in origin)):
                raise ValueError()
            parsed.port  # Also reject invalid port syntax/ranges.
        if len(set(origins)) != len(origins):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('GRIDMIND_ALLOWED_ORIGINS must be a JSON array of exact HTTP(S) origins') from None
    return origins


def cors_headers(headers):
    """Reflect only an approved origin, and do not enable credentialed requests."""
    origins = allowed_origins()
    if headers is None:
        headers = {}
    if not isinstance(headers, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()):
        raise InvalidInputError('event', 'headers must contain string names and values')
    headers = {k.lower(): v for k, v in headers.items()}
    result = {'Vary': 'Origin'} if origins else {}
    origin = headers.get('origin')
    if origin is not None:
        if origin not in origins:
            raise InvalidInputError('origin', 'origin is not allowed')
        result['Access-Control-Allow-Origin'] = origin
    if headers.get('access-control-request-method') not in (None, 'GET', 'POST'):
        raise InvalidInputError('method', 'preflight method is not allowed')
    requested = headers.get('access-control-request-headers', '')
    if any(v.strip().lower() != 'content-type' for v in requested.split(',') if v.strip()):
        raise InvalidInputError('headers', 'only Content-Type is allowed in preflight')
    return result

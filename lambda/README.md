# GridMind HTTP API adapter

`handler.lambda_handler` accepts API Gateway **HTTP API payload 2.0**, not REST API events. It invokes the unchanged shared Python engine. Versioned resources are GET `/v2/health`, `/v2/scenarios`, `/v2/network`, and POST `/v2/simulate`, `/v2/assess`, `/v2/impact`, `/v2/hosting`, `/v2/plan`. Unversioned resource names also work. One leading `/api` segment and trailing slashes are stripped. Dispatch and optimize remain unavailable.

The handler loads configuration once per process from `GRIDMIND_CONFIG_DIR`, otherwise `config/` beside the packaged handler (or the repository root locally). Package every engine module and all fourteen model/profile JSON files using `scripts/package_api.py`. There is no runtime S3 call, SDK dependency, result cache, or developer-specific path.

POST requests require strict JSON and are limited to 2048 decoded UTF-8 bytes. Unknown fields, unsupported scenarios and invalid allocations are rejected by existing engine validators. Errors use the contract's `{error:{code,message,field}}` shape: 400 invalid_input, 404 not_found, 405 method_not_allowed, 500 convergence_failed or internal_error. No 413/422 is introduced because the established mapping is retained. Versioned solver errors use a fixed safe message; unexpected failures always return `internal error`. The cause stays in a single structured log record, never in the response. Request bodies and headers are not logged.

`GRIDMIND_ALLOWED_ORIGINS` is a JSON list of exact approved origins; its default `[]` permits same-origin access only. No frontend origin is currently approved. OPTIONS on available resources returns 204, allowing GET/POST and Content-Type for approved origins; no credentials or wildcard CORS are enabled. Every response carries application/json and no-store headers. See contract section 13 for exact schemas and validation behaviour.

Local invocation (no AWS credentials required):

```bash
.venv/bin/python scripts/invoke_local.py lambda/events/simulate_default.json --summary
.venv/bin/python scripts/invoke_local.py lambda/events/v2_health.json --pretty
.venv/bin/python scripts/invoke_local.py lambda/events/v2_assess.json --pretty
.venv/bin/python scripts/package_api.py
```

Hosting and planning run bounded simulation searches, so local timings do not establish cloud latency. Deployment and cloud parity verification require separate approval; no deployed API URL is currently verified. Engineering outputs remain illustrative modeled estimates, not telemetry, measured appliance damage, upstream feeder approval or globally optimal placement.

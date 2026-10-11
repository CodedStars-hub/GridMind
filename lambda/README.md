# Local Lambda handler

`handler.py` adapts API Gateway HTTP API payload version 2.0 events to the shared Python engine. It implements `GET /scenarios` and `POST /simulate`; it contains no physics and imports no cloud SDK.

The handler reads `requestContext.http.method`, `rawPath`, `body`, and `isBase64Encoded`. It strips one leading `/api` segment and trailing slashes. Responses contain JSON with `Content-Type: application/json` and `Cache-Control: no-store`; decoded request bodies are limited to 2048 UTF-8 bytes.

Config loads once per process from `GRIDMIND_CONFIG_DIR`, or the repository's `config/` directory by default. Treat cached config as read-only; `reset_config_cache()` is available for tests. Scenarios assumptions include transformer, limits, costs, BESS and load-level parameters, including TBD values.

Invalid inputs return 400, unknown or unavailable routes 404, and wrong methods 405. Power-flow failures return 500 `convergence_failed`; unexpected errors return 500 `internal_error` with the fixed message `internal error`. BESS simulation requests return 400 until M8; `/optimize` and `/dispatch` return 404 until M9 and M11.

Each request emits one JSON log record containing routing, status, duration and error code. Validated simulation fields are included only after validation succeeds. Internal failures include the traceback in that same record; request bodies and headers are never logged.

From the repository root with `.venv` active:

```bash
python scripts/invoke_local.py lambda/events/get_scenarios.json --pretty
python scripts/invoke_local.py lambda/events/simulate_default.json --summary
```

The invoker reads only the supplied event file, inserts engine and Lambda paths locally, and exits 0 for HTTP 200 or 1 otherwise. This milestone is local only; deployment belongs to M5.

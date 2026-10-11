# GridMind

GridMind is a browser-based digital twin of one 250 kVA, 11 kV/415 V distribution transformer. A planner picks an EV hub size, rooftop solar size, day type and existing loading level, then runs a 24-hour simulation in 15-minute steps. It reports voltage, loading, hot-spot temperature and insulation aging, and later sizes a battery and exports a mock dispatch payload.

Planning-grade model of one transformer. Values marked TBD are not final.

## Repository map

**config/** holds every number the model uses (nameplate, limits, costs, battery settings, load presets) as JSON. Each parameter has a value, a unit and a source or assumption note. Physics constants, limits, costs and profile values belong in config, not code. `config/profiles/` will hold the 15-minute profile files later.

**engine/** is the Python package `gridmind_engine` (standard library only) plus its tests. For now every module is an empty placeholder with a docstring saying what it will do and when.

**lambda/** will hold the single AWS Lambda handler that routes requests to the engine. It is empty for now.

**scripts/** will hold deploy, precompute and smoke-test scripts. It is empty for now.

**frontend/** holds the M12 React + strict TypeScript + Vite + Tailwind application, including API integration, navigation, tests and setup documentation. **web/** is the original placeholder; the application lives in `frontend/` as specified for M12.

**infra/** will hold the AWS SAM template. It is empty for now.

**docs/** holds `api-contract.md` (the single source of truth for request and response shapes) and `assumptions.md` (a skeleton for modelling assumptions).

## Setup and tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
pytest engine/tests
```

No installation of the engine is needed: `pytest.ini` puts `engine/` on the Python path.

Current status: M12 frontend foundation complete; advanced interactive views remain upcoming.

Engine code must stay compatible with Python 3.12. Do not use syntax or standard-library features newer than 3.12.

## Run a simulation

Activate `.venv` first, then run from the repository root:
```bash
PYTHONPATH=engine python -m gridmind_engine.cli --ev 50 --pv 30 --day summer_weekday --load heavy --summary
```
Omit `--summary` for JSON; use `--pretty` for indented JSON or `--out FILE` to save output.

## Invoke the handler locally

With `.venv` active, run from the repository root:
```bash
python scripts/invoke_local.py lambda/events/simulate_default.json --summary
```
Use `get_scenarios.json --pretty` to inspect the choices and assumptions. This handler is local only.

## API v2

The existing handler exposes `/v2/health`, `/v2/scenarios`, `/v2/network`, `/v2/simulate`, `/v2/assess`, `/v2/impact`, `/v2/hosting` and `/v2/plan`; see [the API contract](docs/api-contract.md#13-m11-versioned-http-api-integration). The deployed Mumbai API base supplied for M12 is `https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com`; health and neighbourhood configuration were verified during frontend integration.

```bash
.venv/bin/python scripts/invoke_local.py lambda/events/v2_health.json --pretty
.venv/bin/python scripts/invoke_local.py lambda/events/v2_assess.json --pretty
.venv/bin/python scripts/package_api.py
```

Deployment requires separate approval; see [the infrastructure review](infra/README.md). Model results are illustrative, hosting excludes shared upstream constraints, and placement is a deterministic heuristic rather than a guaranteed optimum. No real-time telemetry is implemented.

## Run the frontend locally

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:5173`. The development proxy connects same-origin browser requests to the deployed API without changing AWS CORS. Direct browser access needs a separately approved origin allowlist update; see [frontend setup and architecture](frontend/README.md) for environment variables, CORS, tests and production builds.

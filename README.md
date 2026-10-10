# GridMind

GridMind is a browser-based digital twin of one 250 kVA, 11 kV/415 V distribution transformer. A planner picks an EV hub size, rooftop solar size, day type and existing loading level, then runs a 24-hour simulation in 15-minute steps. It reports voltage, loading, hot-spot temperature and insulation aging, and later sizes a battery and exports a mock dispatch payload.

Planning-grade model of one transformer. Values marked TBD are not final.

## Repository map

**config/** holds every number the model uses (nameplate, limits, costs, battery settings, load presets) as JSON. Each parameter has a value, a unit and a source or assumption note. Physics constants, limits, costs and profile values belong in config, not code. `config/profiles/` will hold the 15-minute profile files later.

**engine/** is the Python package `gridmind_engine` (standard library only) plus its tests. For now every module is an empty placeholder with a docstring saying what it will do and when.

**lambda/** will hold the single AWS Lambda handler that routes requests to the engine. It is empty for now.

**scripts/** will hold deploy, precompute and smoke-test scripts. It is empty for now.

**web/** will hold the Vite + React + TypeScript frontend. It is empty for now.

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

Current status: M0 to M3b complete

Engine code must stay compatible with Python 3.12. Do not use syntax or standard-library features newer than 3.12.

## Run a simulation

Activate `.venv` first, then run from the repository root:
```bash
PYTHONPATH=engine python -m gridmind_engine.cli --ev 50 --pv 30 --day summer_weekday --load heavy --summary
```
Omit `--summary` for JSON; use `--pretty` for indented JSON or `--out FILE` to save output.

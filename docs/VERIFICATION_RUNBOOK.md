# GridMind End-to-End Verification Runbook

Deterministic, reproducible runbook for testing and validating the GridMind digital twin across local engine, Lambda invoker, frontend, and cloud tiers.

---

## 1. Engine Verification (Python 3.12)

The engine requires zero package installations beyond `pytest` for running automated checks.

```bash
# 1. Activate virtual environment
source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1

# 2. Run all unit and golden fixture tests
python -m pytest engine/tests -v

# 3. Verify deterministic CLI simulation output
PYTHONPATH=engine python -m gridmind_engine.cli \
  --ev 50 \
  --pv 30 \
  --day summer_weekday \
  --load heavy \
  --summary
```

**Expected Results**:
- All tests pass with zero errors.
- Summary displays min voltage ~0.932 p.u. (at ~19:45) and peak hot-spot ~134.2°C (at ~20:15).

---

## 2. Serverless Lambda Local Invocation

Test the production Lambda entry point (`lambda/handler.py`) against realistic event JSON payloads:

```bash
# Health Check Event
python scripts/invoke_local.py lambda/events/v2_health.json --pretty

# Default Single-Transformer Simulation Event
python scripts/invoke_local.py lambda/events/simulate_default.json --summary

# Multi-Transformer Neighbourhood Assessment Event
python scripts/invoke_local.py lambda/events/v2_assess.json --pretty
```

**Expected Results**:
- Status code 200 returned across all valid events.
- Response payloads match schemas defined in [docs/api-contract.md](api-contract.md).

---

## 3. Frontend Quality Gates & Smoke Tests

Navigate to `frontend/`:

```bash
cd frontend

# 1. Run strict TypeScript type check
npm run typecheck

# 2. Run Vitest component & transport unit tests
npm test

# 3. Build production bundle (tests Vite compilation)
npm run build

# 4. Run automated proxy smoke test against live API
npm run smoke:api
```

---

## 4. Live Cloud Verification (AWS ap-south-1)

Test the live production deployment hosted in Mumbai:

```bash
# 1. Health Probe
curl -i https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/health

# 2. Scenario Metadata Probe
curl -i https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/scenarios

# 3. Live Simulation Invocation
curl -i -X POST https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/simulate \
  -H "Content-Type: application/json" \
  -d '{"ev_kw":50,"pv_kwp":30,"day_type":"summer_weekday","load_level":"heavy"}'
```

**Expected Results**:
- HTTP 200 with `Content-Type: application/json` and `Cache-Control: no-store`.
- Execution latency well under 100 ms warm.

# GridMind Operational & Automation Scripts

Comprehensive guide to GridMind's operational, testing, packaging, and precomputation scripts.

---

## Script Inventory

| Script | Purpose & Usage |
| :--- | :--- |
| [`package_api.py`](package_api.py) | Builds the deterministic production deployment package `out/gridmind-api.zip` containing the engine, handler, configuration, and profile datasets for AWS Lambda. |
| [`invoke_local.py`](invoke_local.py) | Simulates AWS Lambda execution locally without AWS credentials, accepting realistic event payloads (e.g. `lambda/events/simulate_default.json`). |
| [`precompute.py`](precompute.py) | Generates precomputed digital twin results across all 144 baseline parameter permutations for zero-downtime S3 edge fallback. Supports `--verify`. |
| [`serve_local_api.py`](serve_local_api.py) | Starts a lightweight local HTTP server exposing the API Gateway routes locally at `http://localhost:8000`. |
| [`check_release.py`](check_release.py) | Executes automated release verification across health, scenarios, simulation, and telemetry replays against local or live cloud endpoints. |
| [`generate_profiles.py`](generate_profiles.py) | Generates normalized 96-step (15-minute) profiles for base demand, EV charging hubs, rooftop solar PV, and ambient temperature. |

---

## Common Workflows

### 1. Build Production Lambda Package
```bash
python scripts/package_api.py
```
Outputs deterministic `out/gridmind-api.zip` ready for AWS SAM deployment.

### 2. Test Lambda Invocations Locally
```bash
# Test health check event
python scripts/invoke_local.py lambda/events/v2_health.json --pretty

# Test full digital twin simulation event
python scripts/invoke_local.py lambda/events/simulate_default.json --summary

# Test multi-transformer assessment
python scripts/invoke_local.py lambda/events/v2_assess.json --pretty
```

### 3. Generate Precomputed Edge Fallback Cache
```bash
python scripts/precompute.py --verify
```

### 4. Run Release Verification Suite
```bash
python scripts/check_release.py --battery-power 100 --battery-energy 500 --initial-soc 80
```

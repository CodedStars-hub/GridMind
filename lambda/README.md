# GridMind Serverless AWS Lambda Engine

Technical documentation for GridMind's production AWS Lambda handler and API Gateway integration.

---

## 1. Architecture & Payload Format

- **Handler Function**: `handler.lambda_handler`
- **Payload Format**: Amazon API Gateway **HTTP API Payload 2.0**
- **Runtime**: Python 3.12 (Standard Library Only)
- **Memory Allocation**: 2,048 MB
- **Execution Timeout**: 25 seconds

The Lambda handler serves as the single cloud entry point for the shared pure-Python engine. It validates incoming JSON requests, executes the coupled multi-physics solvers, formats responses according to the strict [API Contract v3](../docs/api-contract.md), and publishes dispatch events to AWS IoT Core.

---

## 2. API v2 Routing

The handler maps HTTP routes directly to engine operations:

| Method | Route | Engine Operation |
| :--- | :--- | :--- |
| `GET` | `/v2/health` | Runtime configuration and health verification |
| `GET` | `/v2/scenarios` | Enumerated parameter spaces and metadata citations |
| `GET` | `/v2/network` | 6-transformer neighbourhood topology and site inventories |
| `POST` | `/v2/simulate` | Single-transformer 24h digital twin simulation |
| `POST` | `/v2/assess` | Multi-transformer network assessment |
| `POST` | `/v2/impact` | Asset life loss and rupee depreciation valuation |
| `POST` | `/v2/hosting` | Discrete EV hosting capacity search |
| `POST` | `/v2/plan` | Footfall-ranked strategic placement and remedy optimization |

*Note: Paths accept an optional leading `/api` prefix (e.g. `/api/v2/simulate`) and optional trailing slashes.*

---

## 3. Security, Validation & CORS

- **Decoded Request Size Guard**: Strict 2,048-byte limit on incoming request bodies, rejecting oversized payloads with HTTP 400.
- **Strict JSON Parsing**: Malformed JSON or unknown request fields are rejected immediately with structured error envelopes: `{"error": {"code": "invalid_input", "message": "...", "field": "..."}}`.
- **CORS Handling**: Native OPTIONS preflight handling returning HTTP 204. Supported cross-origin callers are validated against the `GRIDMIND_ALLOWED_ORIGINS` environment variable.
- **Headers**: Every response carries `Content-Type: application/json` and `Cache-Control: no-store`.

---

## 4. Local Execution & Packaging

Invoke the production handler locally using pre-packaged realistic event files:

```bash
# Verify health check
python scripts/invoke_local.py lambda/events/v2_health.json --pretty

# Run 24h digital twin simulation
python scripts/invoke_local.py lambda/events/simulate_default.json --summary

# Run neighbourhood assessment
python scripts/invoke_local.py lambda/events/v2_assess.json --pretty

# Package production deployment zip
python scripts/package_api.py
```

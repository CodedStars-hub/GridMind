# GridMind System & Cloud Architecture

Authoritative technical specification of GridMind's serverless cloud architecture, data flows, edge resilience mechanisms, and security model.

---

## 1. Architectural Philosophy

GridMind is engineered as a **lean, deterministic, serverless system running natively on Amazon Web Services (AWS)**. It prioritizes:
1. **Single-Origin Simplicity**: CloudFront acts as a single HTTPS entrypoint, serving the static frontend from Amazon S3 and reverse-proxying API calls to API Gateway, eliminating cross-origin resource sharing (CORS) complexity and latency.
2. **Deterministic Sub-Second Compute**: A monolithic, zero-dependency Python 3.12 Lambda function executes all coupled AC power flow, thermal, and aging equations in under 40 milliseconds warm.
3. **Resilience by Precomputation**: Because the baseline single-transformer parameter space is finite (144 permutations), all baseline results are precomputed and published to S3, providing a zero-downtime client-side fallback if network or API failures occur.
4. **Standard Library Only**: Eliminates heavy binary layers (NumPy/SciPy), keeping Lambda deployment packages under 1 MB and cold starts strictly under 300 ms.

---

## 2. High-Level AWS Topology

```
                                      END USER / PLANNER BROWSER
                                                  │
                                                  │ HTTPS (Single Origin)
                                                  ▼
                         ┌──────────────────────────────────────────────────┐
                         │              AMAZON CLOUDFRONT CDN               │
                         │              (ap-south-1 Edge PoP)               │
                         └──────────────┬───────────────────┬───────────────┘
                                        │                   │
                     Route /* (Static Assets)       Route /api/* (API Proxy)
                                        │                   │
                                        ▼                   ▼
                         ┌──────────────────────┐  ┌────────────────────────┐
                         │   AMAZON S3 BUCKET   │  │   AMAZON API GATEWAY   │
                         │ (Vite React 19 SPA & │  │     (HTTP API v2)      │
                         │ precomputed/ JSON)   │  └───────────┬────────────┘
                         └──────────────────────┘              │
                                                               │ Payload Format 2.0
                                                               ▼
                                                   ┌────────────────────────┐
                                                   │    AWS LAMBDA ENGINE   │
                                                   │   (Python 3.12 Runtime │
                                                   │   2048 MB Memory)      │
                                                   └───────────┬────────────┘
                                                               │
                                       ┌───────────────────────┴───────────────────────┐
                                       │                                               │
                                       ▼                                               ▼
                        ┌──────────────────────────────┐                ┌──────────────────────────────┐
                        │    AMAZON S3 DATA BUCKET     │                │         AWS IOT CORE         │
                        │ (config/ immutable schemas   │                │ (MQTT Broker Topic:          │
                        │ & 15-min profile datasets)   │                │ gridmind/dt-250/dispatch)    │
                        └──────────────────────────────┘                └──────────────────────────────┘
                                       │                                               │
                                       └───────────────────────┬───────────────────────┘
                                                               │
                                                               ▼
                                                ┌──────────────────────────────┐
                                                │       AMAZON CLOUDWATCH      │
                                                │ (Structured JSON Logging,    │
                                                │ Metric Alarms, Cost Guards)  │
                                                └──────────────────────────────┘
```

---

## 3. Component Deep Dive

### 3.1 Amazon CloudFront (Edge Delivery Tier)
- **Role**: High-speed CDN providing TLS 1.3 termination, HTTP/2 delivery, and origin routing.
- **Behaviors**:
  - `DefaultCacheBehavior` (`/*`): Forwards to S3 Site Bucket with Origin Access Control (OAC). Gzip and Brotli compression enabled.
  - `ApiCacheBehavior` (`/api/*`): Forwards dynamically to Amazon API Gateway with `CachingDisabled` policy, preserving headers and query strings.

### 3.2 Amazon API Gateway (HTTP API v2)
- **Role**: Lightweight, low-latency API proxy.
- **Features**:
  - Uses modern HTTP API (Payload Version 2.0) for reduced pricing and sub-5 ms gateway overhead compared to REST APIs.
  - Native stage throttling: Default 1 request/second with burst capacity of 2 requests, preventing denial-of-service abuse.
  - Enforces strict 2,048-byte decoded body limit.

### 3.3 AWS Lambda Engine (`handler.lambda_handler`)
- **Runtime**: Python 3.12 (Standard Library Only).
- **Resource Allocation**: 2048 MB memory, 25-second execution timeout.
- **In-Memory Caching**: Configuration schemas (`transformer.json`, `limits.json`, etc.) and profile time-series are loaded on cold boot and cached in module-level global state, eliminating repeat S3 reads during warm executions.
- **CORS Handling**: Native OPTIONS preflight handling with strict origin allowlist validation (`AllowedOriginsJson`).

### 3.4 AWS IoT Core (Edge Dispatch Interface)
- **Role**: Industrial IoT telemetry broker.
- **Topic**: `gridmind/dt-250/dispatch`.
- **Behavior**: When a planner approves a mitigated battery schedule or smart-charging plan, Lambda serializes an OASIS-compliant **OpenADR 2.0b** JSON payload and publishes it directly to IoT Core, demonstrating end-to-end edge controller integration.

### 3.5 Amazon CloudWatch (Observability & Cost Protection)
- **Log Group**: `/aws/lambda/gridmind-api-v2` with strict 14-day log retention.
- **Structured Telemetry**: Every invocation outputs a single-line JSON log containing request method, path, execution time, and response status code.
- **Billing Alarms**: Automated CloudWatch billing alarm configured to guard free-tier limits.

---

## 4. Edge Fallback & High-Availability Model

To guarantee 100% demonstration reliability during hackathon evaluations, GridMind features an **autonomous precomputed fallback mechanism**:

1. **Local Precompute Pipeline**: Before production deployment, `scripts/precompute.py` executes the identical Python engine across all 144 baseline parameter permutations:
   $$\text{Combinations} = 4\ (\text{EV}) \times 4\ (\text{PV}) \times 3\ (\text{Day Types}) \times 3\ (\text{Load Levels}) = 144\text{ Scenarios}$$
2. **S3 Static Cache**: Output JSON files are stored in the S3 site bucket under `/precomputed/{key}.json`.
3. **Client-Side Failure Detection**:
   - The browser attempts live execution via `/api/v2/simulate`.
   - If an HTTP 5xx error, timeout, or network disconnect occurs, the client API layer automatically intercepts the error and requests `/precomputed/{key}.json`.
   - The UI renders the full multi-series charts seamlessly, displaying a subtle "Precomputed Fallback Active" badge.

---

## 5. Security Posture & Least Privilege

- **IAM Least Privilege**: The Lambda execution role has permissions restricted exclusively to:
  - Writing logs to its dedicated CloudWatch log group.
  - Publishing messages to the single ARN `arn:aws:iot:ap-south-1:*:topic/gridmind/dt-250/dispatch`.
- **No Ingestion of User Secrets**: GridMind requires zero user authentication, zero tokens, and stores zero personal data.
- **Private S3 Buckets**: Public access is completely blocked on all S3 buckets; access is granted only via CloudFront Origin Access Control (OAC) and Lambda IAM roles.

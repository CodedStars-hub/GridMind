# M11 API deployment review — not deployed

## Inspection findings

There is no existing infrastructure template, deployment script or SAM configuration in the repository. Older planning documents describe SAM, a single HTTP API/Lambda, and ap-south-1; they do not establish that an AWS stack exists. AWS CLI is available, but credentials and a configured region are unavailable. Account identity, deployed resources and an API URL are therefore unverified. Do not create a parallel stack without checking the target account first.

SAM CLI is not installed. The M11 prompt requires approval before introducing tooling not already used by the repository. Preparation of the documented SAM template is awaiting that separate decision; this document is a proposed review, **not an executable deployment procedure**. No tool installation, resource change or deployment has occurred. Deployment will require another explicit approval after the template and commands are concrete and reviewed.

## Reviewed local artifact

```bash
.venv/bin/python scripts/package_api.py
.venv/bin/python -m pytest engine/tests -v
git diff --check
```

`out/gridmind-api.zip` bundles the root handler and its two adapters, every engine Python module, seven top-level config JSON files and seven profiles. It excludes tests, Git, virtual environments, caches, credentials, event samples and documentation. Config beside the packaged handler is the default; no S3 runtime permission or SDK is needed. Isolated-package tests compare M7 results with the repository engine and verify byte-identical model files and reproducible packaging.

## Proposed infrastructure, subject to approval

- Region: documented ap-south-1; account and stack name require discovery/confirmation. There are no established resource names to preserve in source.
- One Python 3.12 Lambda, handler `handler.lambda_handler`, proposed 2048 MB memory and 25-second timeout, on-demand execution. No layers, VPC, result cache, queue or additional solver. Cloud performance remains unverified.
- One API Gateway **HTTP API**, Lambda proxy payload version 2.0, default stage. Existing short resource names and `/v2` aliases match contract section 13. A catch-all proxy must reach the handler so unknown paths and wrong methods retain structured JSON errors; API Gateway requires a scoped Lambda invoke permission for this API only.
- Proposed execution role permits only creating streams and writing events in this function's pre-created log group. No S3, IoT, wildcard service actions or customer data access. Proposed log retention: 14 days. Minimal request logging is included; dashboards/alarms remain M18.
- Proposed stage throttle: one request/second, burst two, to limit expensive search traffic. The application enforces the existing 2048-byte decoded body limit; HTTP API is not claimed to have that custom gateway body limit.
- `GRIDMIND_ALLOWED_ORIGINS=[]` until a frontend origin is explicitly approved. CORS is handled by Lambda so local and cloud responses agree; do not also configure a conflicting gateway CORS policy. Only exact allowlisted origins, GET/POST/OPTIONS and Content-Type; no credentials.
- No frontend bucket, CloudFront deployment, IoT, precompute infrastructure, authentication or public S3 writes are proposed in M11. Any SAM upload bucket would be deployment tooling only and must be disclosed before approval.

## Timing and payload observations

One local cold configuration load plus health completed in 0.0038 s. Representative sequential warm requests: simulate 0.0047 s / 9,524 response bytes; assess 0.0505 s / 58,686 bytes; impact 0.1076 s / 145,457 bytes; hosting 6.4305 s / 54,111 bytes; plan target 300: 8.6606 s / 240,639 bytes; plan target 450: 8.8741 s / 243,739 bytes. These are observations on the developer's machine, not Lambda benchmarks or guarantees. Import/startup overhead and sustained request load were not measured.

HTTP API has a [30-second maximum integration timeout](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html). Validate expensive operations on the selected memory/runtime after approval. If they cannot reliably complete, report the limitation rather than add asynchronous infrastructure. Python [zip packaging](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html) places the handler at the archive root; the reviewed local artifact follows that layout.

## Approval and verification still required

Before any deployment: discover the account and existing CloudFormation/HTTP API/Lambda resources, choose whether to update an existing stack, approve template/tooling preparation, and review the resulting exact deployment command and IAM diff. No deploy command is supplied as runnable while its template does not exist. Authentication must not expose access keys or credentials; resource creation requires separate approval.

Potential charges include Lambda request/compute time, HTTP API requests, CloudWatch logs and deployment-artifact storage if used. No spending is authorized, no fixed bill is predicted, and throttling is not a spending cap. Review current prices for the chosen account/region before approval.

For an existing stack update, preserve its previous reviewed template and artifact for rollback through the same infrastructure process. For a new stack, rollback/deletion must be reviewed separately and must not touch unrelated resources. After deployment approval: obtain the real endpoint from stack outputs; call health and every operation, compare representative cloud JSON with local outputs, test allowed/disallowed CORS, malformed/oversized bodies and error mappings, inspect Lambda logs, and record verified settings/URL. No live URL should appear in documentation before those checks pass.

## Frontend call examples (after a real URL is known)

Set `GRIDMIND_API_BASE` to the verified HTTPS API base URL; it is deliberately not assigned an invented URL here.

```bash
curl --fail-with-body "$GRIDMIND_API_BASE/v2/health"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"allocation":[]}' "$GRIDMIND_API_BASE/v2/assess"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"allocation":[]}' "$GRIDMIND_API_BASE/v2/impact"
curl --fail-with-body -H 'Content-Type: application/json' -d '{}' "$GRIDMIND_API_BASE/v2/hosting"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"target_kw":300}' "$GRIDMIND_API_BASE/v2/plan"
```

Outputs are modeled estimates, not telemetry or interconnection approval. Independent transformer hosting excludes shared upstream constraints. Placement is a deterministic heuristic, not a guaranteed global optimum; economic and household metrics are explicitly illustrative proxies.

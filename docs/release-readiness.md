# M18 release gate - local readiness, deployment requires approval

The Python 3.12 package includes M15 battery physics and M16 simulated telemetry/advisory dispatch. M17 artifacts are served by the frontend, not Lambda. The existing ANY root/greedy HTTP API routes forward every endpoint to the same handler with payload 2.0. Logs-only IAM, API-scoped invocation, exact-origin Lambda CORS, 1 request/second and burst 2 remain unchanged. No new cloud resource is needed.

## Local setup and gate

Use existing dependencies; install nothing for this release. From the repo root, in separate terminals:

```sh
.venv/bin/python scripts/serve_local_api.py
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --port 5174 --strictPort
```

The adapter explicitly allows localhost:5173/5174; direct browser API requests use that allowlist. Existing AWS development mode uses `/api` and the configured HTTPS Vite proxy target. Production has no such proxy: a build now rejects missing, relative or insecure API bases. Set the actual reviewed HTTPS endpoint explicitly:

```sh
.venv/bin/python -m pytest engine/tests -v
npm --prefix frontend test -- --reporter=verbose
npm --prefix frontend run typecheck
VITE_API_BASE_URL=https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com npm --prefix frontend run build
.venv/bin/python scripts/precompute.py --verify
.venv/bin/python scripts/package_api.py
sam validate --template-file infra/template.json --lint --region ap-south-1
sam build --template-file infra/template.json --build-dir out/sam-release-build
git diff --check
.venv/bin/python scripts/check_release.py --battery-power 100 --battery-energy 500 --initial-soc 80
```

The supplied AWS URL is from the project context, not proof that the current M15-M17 package is deployed. Rebuild with the deployed endpoint if it changes. VITE variables are public build-time settings, never secrets. The checked-in samconfig.toml is preserved; explicit commands below do not depend on its deployment defaults.

## Deployment (instructions only; explicit approval required)

Confirm the owned existing stack, private artifact bucket, approved frontend origin, account and region. These placeholders must be supplied by the reviewer; do not create replacement stacks or buckets implicitly. Run read-only discovery first:

```sh
export GRIDMIND_DEPLOY_REGION=ap-south-1
export GRIDMIND_STACK=YOUR_REVIEWED_EXISTING_STACK
export GRIDMIND_ARTIFACT_BUCKET=YOUR_APPROVED_EXISTING_PRIVATE_BUCKET
export GRIDMIND_FRONTEND_ORIGIN=https://YOUR_APPROVED_FRONTEND_HOST
aws sts get-caller-identity --query Account --output text
aws cloudformation describe-stacks --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION"
```

Before any approved update, save the current template, the non-secret origin parameter and old uploaded package objects. Do not export unrelated stacks or secrets:

```sh
aws cloudformation get-template --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --template-stage Original --output json > out/rollback-template-response.json
.venv/bin/python -c 'import json; from pathlib import Path; body=json.loads(Path("out/rollback-template-response.json").read_text())["TemplateBody"]; Path("out/rollback-template.yaml").write_text(body if isinstance(body,str) else json.dumps(body,indent=2))'
aws cloudformation describe-stacks --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --query 'Stacks[0].Parameters' --output json > out/rollback-parameters.json
```

After separate approval only, build/upload through the existing SAM template; this updates the reviewed API stack and requires IAM acknowledgement. Keep exact frontend origins, no wildcard and no API Gateway CORS override:

```sh
export GRIDMIND_ALLOWED_ORIGINS_JSON="[\"${GRIDMIND_FRONTEND_ORIGIN}\"]"
sam deploy --template-file infra/template.json --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --s3-bucket "$GRIDMIND_ARTIFACT_BUCKET" --capabilities CAPABILITY_IAM --parameter-overrides "AllowedOriginsJson=${GRIDMIND_ALLOWED_ORIGINS_JSON}" --confirm-changeset
export GRIDMIND_API_BASE=$(aws cloudformation describe-stacks --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue' --output text)
```

Review proposed changes before confirming; reject unexpected replacement/expansion. Deploy frontend `dist/` only using the already approved hosting process; this milestone does not introduce a hosting service or run an upload.

## Live verification and rate limits

Perform a single pass, spaced at least one second apart; health/network/scenarios can exhaust the small burst allowance. On 429 respect Retry-After or pause; do not loop, increase retries or disable throttling. Automatic retries are limited to metadata GETs; simulation/dispatch POSTs remain user-controlled. Inspect cold/warm latency before declaring hosting/planner requests reliable inside the 25-second Lambda/29-second integration limits.

```sh
.venv/bin/python scripts/check_release.py --base-url "$GRIDMIND_API_BASE" --origin "$GRIDMIND_FRONTEND_ORIGIN" --snapshots-url "${GRIDMIND_FRONTEND_ORIGIN}/precomputed/scenarios.json" --battery-power 100 --battery-energy 500 --initial-soc 80
aws logs tail "/aws/lambda/${GRIDMIND_STACK}-api" --since 10m --region "$GRIDMIND_DEPLOY_REGION"
```

The check verifies health, network, scenarios, no-battery and battery simulations, 96-step series, telemetry replay, advisory response, stale/invalid errors, OPTIONS/CORS and frontend snapshot provenance. It stops at the first unexpected status, including 429; it does not claim success for a partial run. It makes no deployment or hardware command. Client guards and existing tests additionally validate frontend response structures.

Manual browser gate: load Overview and Network; select a transformer (its metadata does not silently become the separate single-transformer assessment); navigate to Assessment, run a scenario, inspect chart samples/limits, pin it, enable BESS and compare, step simulated dispatch, inspect an explicitly selected precomputed scenario, and verify graceful errors with the local backend stopped. Snapshots have no current-backend threshold overlay or dispatch monitor and are never labelled live. No real IoT hardware is connected. Browser-only review must be recorded separately; automated HTTP tests do not establish visual/accessibility approval.

## Rollback (separate approval required)

Allow automatic CloudFormation rollback after a failed update and inspect its events. For a completed update needing reversal, retain old package objects and apply the reviewed original template/parameters:

```sh
aws cloudformation update-stack --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --template-body file://out/rollback-template.yaml --parameters file://out/rollback-parameters.json --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND
aws cloudformation wait stack-update-complete --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION"
```

Re-run paced endpoint checks. Restore the prior approved frontend build with its original API base using the existing hosting process. Do not delete the stack, retained logs or unrelated resources. Remaining release gates are human browser review, approved production CORS origin, AWS deployment approval, cloud cold-start/performance checks and comparison with identical local outputs. Modeling limitations remain unchanged.

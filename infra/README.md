# M11 SAM infrastructure — prepared locally, not deployed

## Scope and infrastructure

`template.json` is a JSON-form AWS SAM template. It defines one Python 3.12 Lambda (`handler.lambda_handler`), one HTTP API with payload version 2.0, a pre-created log group, a logs-only execution role, and a scoped API invocation permission. SAM expands these definitions into CloudFormation resources. No frontend, IoT, queue, cache, or runtime S3 access is introduced.

No existing stack, account, resource names or live endpoint have been verified. Older planning documents specify `ap-south-1`; use that region unless the human approves another. Names derive from the selected stack: `${stack}-api`, `${stack}-http`, and `/aws/lambda/${stack}-api`. Keep the stack name at most 60 characters so the Lambda name stays within its limit. Check existing resources before choosing a new stack.

Lambda has 2048 MB memory and a 25-second timeout. The HTTP integration timeout is 29 seconds; stage throttling is one request/second with burst two. These are initial operational settings, not measured cloud performance guarantees or a spending cap. Logs expire after 14 days; the log group is retained on stack deletion/replacement to preserve diagnostics. The role can only create streams and write events in that group. Invocation is restricted to the target account, API and default stage.

The API's [default proxy route](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-open-api.html) forwards all paths/methods to the existing handler. This preserves structured unknown-route and wrong-method errors, legacy aliases and optional `/api` prefixes. Supported v2 operations are GET `/v2/health`, `/v2/scenarios`, `/v2/network`; POST `/v2/simulate`, `/v2/assess`, `/v2/impact`, `/v2/hosting`, `/v2/plan`.

CORS is implemented by Lambda, including OPTIONS, with exact origins supplied through `AllowedOriginsJson`. Its default `[]` enables no cross-origin callers. Do not configure competing API Gateway CORS or wildcard credentialed access. The handler enforces the contract's 2048-byte decoded body limit, returning 400; this is not a custom gateway request-size limit.

## Local build and validation

Run from the repository root:

```bash
.venv/bin/python scripts/package_api.py
.venv/bin/python -m json.tool infra/template.json > /dev/null
.venv/bin/python -m pytest engine/tests -v
git diff --check
```

The deterministic `out/gridmind-api.zip` contains the handler/adapters, every engine module, all top-level config JSON and all profile JSON. It excludes environments, tests, caches, credentials, Git and documentation. `CodeUri` points to this pre-built ZIP relative to the template; no dependency installation, Docker or `sam build` is needed. SAM supports [local deployment artifacts](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-function.html) uploaded during deployment. Isolated-package tests verify model bytes, required files, health and CORS without repository import paths.

Infrastructure tests check resource references, dependency cycles, scoped permissions, runtime settings and proxy wiring. They do **not** run the SAM transform or substitute for full CloudFormation validation. SAM CLI, cfn-lint and cfn-guard are unavailable locally; no tools were installed. After separately approving installation, run:

```bash
sam validate --template-file infra/template.json --lint --region ap-south-1
```

Resolve validation errors before deployment approval. Cloud-side template validation and change-set review also remain pending.

## Deployment approval checkpoint

The commands below are instructions only. **Do not run deployment, packaging uploads, change-set creation, update or deletion before separate explicit approval.** Even a non-executed change set or artifact upload changes AWS state.

First confirm the target account, region and ownership of any existing stack using read-only commands:

```bash
aws sts get-caller-identity --query Account --output text
aws cloudformation describe-stacks --region ap-south-1 --query 'Stacks[].{Name:StackName,Status:StackStatus}'
aws apigatewayv2 get-apis --region ap-south-1 --query 'Items[].{Name:Name,Id:ApiId}'
aws lambda list-functions --region ap-south-1 --query 'Functions[].FunctionName'
```

Never print credentials. Account identity was unavailable during previous inspection; no account or endpoint is invented here. Set the reviewed stack and an **existing approved private artifact bucket** in the same region. The example stack name is a proposal, not a discovered resource:

```bash
export GRIDMIND_DEPLOY_REGION=ap-south-1
export GRIDMIND_STACK=gridmind-api-v2
export GRIDMIND_ARTIFACT_BUCKET=YOUR_APPROVED_EXISTING_PRIVATE_BUCKET
```

Replace the bucket placeholder; do not create a bucket implicitly with `--resolve-s3`. Review whether this updates an existing owned stack or creates a new one. Approve the template, execution-role permissions, origin list, upload location, resource settings and costs. Potential charges are Lambda compute/requests, HTTP API requests, logs and artifact storage; no fixed bill is predicted.

After tooling validation and **separate deployment approval**, build the ZIP with the local command above, then:

```bash
sam deploy --template-file infra/template.json \
  --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" \
  --s3-bucket "$GRIDMIND_ARTIFACT_BUCKET" --s3-prefix "$GRIDMIND_STACK" \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --parameter-overrides 'AllowedOriginsJson=[]' \
  --confirm-changeset --no-fail-on-empty-changeset
```

For an approved frontend origin, replace `[]` with its exact JSON list (for example `AllowedOriginsJson=["https://YOUR_APPROVED_ORIGIN"]`); the placeholder is not an approved origin. Review the change set before confirming it. Uploads happen before that confirmation. Never deploy into an unrelated stack, and stop if replacements or permissions differ from this review.

## Verification after an approved deployment

Obtain the actual endpoint from stack outputs:

```bash
export GRIDMIND_API_BASE="$(aws cloudformation describe-stacks --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --query 'Stacks[0].Outputs[?OutputKey==`ApiBaseUrl`].OutputValue | [0]' --output text)"
curl --fail-with-body "$GRIDMIND_API_BASE/v2/health"
curl --fail-with-body "$GRIDMIND_API_BASE/v2/scenarios"
curl --fail-with-body "$GRIDMIND_API_BASE/v2/network"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"ev_kw":50,"pv_kwp":30,"day_type":"summer_weekday","load_level":"heavy"}' "$GRIDMIND_API_BASE/v2/simulate"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"allocation":[]}' "$GRIDMIND_API_BASE/v2/assess"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"allocation":[]}' "$GRIDMIND_API_BASE/v2/impact"
curl --fail-with-body -H 'Content-Type: application/json' -d '{}' "$GRIDMIND_API_BASE/v2/hosting"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"target_kw":300}' "$GRIDMIND_API_BASE/v2/plan"
curl --fail-with-body -H 'Content-Type: application/json' -d '{"target_kw":450}' "$GRIDMIND_API_BASE/v2/plan"
curl -i "$GRIDMIND_API_BASE/v2/nothing"
curl -i "$GRIDMIND_API_BASE/v2/simulate"
curl -i -H 'Content-Type: application/json' -d '{' "$GRIDMIND_API_BASE/v2/simulate"
.venv/bin/python -c 'print("x" * 2049, end="")' | curl -i -H 'Content-Type: application/json' --data-binary @- "$GRIDMIND_API_BASE/v2/simulate"
aws logs tail "/aws/lambda/${GRIDMIND_STACK}-api" --since 10m --region "$GRIDMIND_DEPLOY_REGION"
```

Expected error statuses above: 404, 405, 400, 400. Verify error envelopes, JSON/no-store headers and absence of client traceback leakage. With an actually approved origin set in `GRIDMIND_FRONTEND_ORIGIN`, test preflight (204) and reflection; an unapproved origin must receive 400:

```bash
curl -i -X OPTIONS -H "Origin: $GRIDMIND_FRONTEND_ORIGIN" -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: Content-Type' "$GRIDMIND_API_BASE/v2/plan"
curl -i -H 'Origin: https://unapproved.invalid' "$GRIDMIND_API_BASE/v2/health"
```

Compare representative cloud and local results using identical configuration:

```bash
.venv/bin/python scripts/invoke_local.py lambda/events/simulate_default.json > out/local-response.json
curl --fail-with-body -H 'Content-Type: application/json' -d '{"ev_kw":50,"pv_kwp":30,"day_type":"summer_weekday","load_level":"heavy"}' "$GRIDMIND_API_BASE/v2/simulate" > out/cloud-result.json
.venv/bin/python -c 'import json; from pathlib import Path; local=json.loads(Path("out/local-response.json").read_text()); cloud=json.loads(Path("out/cloud-result.json").read_text()); assert json.loads(local["body"]) == cloud; print("local/cloud simulation equal")'
```

Validate the other responses against contract section 13 and record measured latency/payload sizes, especially hosting and both plan targets. Previous local warm observations were approximately 6.43 s for hosting and 8.66–8.87 s for planning; these are not Lambda guarantees. HTTP API's [maximum integration timeout is 30 seconds](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html). If cloud operations cannot reliably complete, report the limitation; do not add asynchronous infrastructure. Record a live URL only after all required smoke tests pass.

## Rollback (requires its own explicit approval)

Before an **existing owned API stack update**, save its original template and non-secret parameters, and retain previous artifact objects:

```bash
aws cloudformation get-template --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --template-stage Original --output json > out/rollback-template-response.json
.venv/bin/python -c 'import json; from pathlib import Path; body=json.loads(Path("out/rollback-template-response.json").read_text())["TemplateBody"]; Path("out/rollback-template.yaml").write_text(body if isinstance(body,str) else json.dumps(body,indent=2),encoding="utf-8")'
aws cloudformation describe-stacks --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --query 'Stacks[0].Parameters' --output json > out/rollback-parameters.json
```

This prepared template has only the non-secret origin parameter. Do not export parameters from unrelated stacks or stacks containing secrets. For a failed update, allow CloudFormation's normal automatic rollback and inspect events. If a completed update needs reversal, review the saved template and parameter file, then, only after approval:

```bash
aws cloudformation update-stack --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION" --template-body file://out/rollback-template.yaml --parameters file://out/rollback-parameters.json --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND
aws cloudformation wait stack-update-complete --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION"
```

The original deployed template references previous uploaded artifacts; do not remove those objects. Repeat health, operation and CORS verification after rollback. For a newly created stack that must be removed, approve deletion of **only that stack**:

```bash
aws cloudformation delete-stack --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION"
aws cloudformation wait stack-delete-complete --stack-name "$GRIDMIND_STACK" --region "$GRIDMIND_DEPLOY_REGION"
```

Retained logs and artifact objects remain, may incur storage charges, and need a separate reviewed cleanup decision. No deletion is performed automatically.

All engineering results remain modeled estimates, not telemetry, interconnection approvals or guaranteed optimal siting. Independent transformer capacity excludes shared upstream constraints. Infrastructure preparation does not change those model limitations.

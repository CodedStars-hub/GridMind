GridMind v2.0: minimum viable architecture
Design stance

The v2 PRD describes a small, deterministic computation: one transformer, 96 timesteps, and enumerated inputs only (144 base combinations, each with an optional BESS result). That shapes everything below.

One engine, three callers. A single pure-Python module does the physics. The Lambda, the precompute script, and the unit tests all import it, so cached and live results cannot diverge.
No ML, no database, no queue, no auth. The PRD excludes them, and nothing in the critical path needs them.
One origin. CloudFront serves the site and proxies /api/* to API Gateway. That removes CORS and the circular dependency between the API URL and the CloudFront domain.
Reliability is a design feature. Because the input space is finite, every result is precomputed and used as the fallback.
Six meaningful AWS services: S3, CloudFront, API Gateway, Lambda, IoT Core, CloudWatch. All are serverless and none needs a VPC.
System components
#	Component	Role
1	Web app (SPA)	Scenario inputs, charts, alerts, exports, fallback logic
2	CloudFront distribution	Single HTTPS origin: static site, precomputed JSON, /api/* proxy
3	API Gateway (HTTP API)	Public API surface with throttling
4	Engine Lambda (Python)	Power flow, thermal and aging, BESS sizing, cost, OpenADR builder, IoT publish
5	S3 (site bucket)	Frontend build and precomputed/ results
6	S3 (data bucket)	config/ JSON: transformer, profiles, limits, cost assumptions
7	IoT Core	MQTT topic that stands in for the edge controller
8	CloudWatch	Logs, alarms, small dashboard, billing alarm
9	Precompute script (local)	Runs the same engine over all combinations before deploy
The ten areas
1. Frontend
Responsibility: Enumerated dropdowns, Run and Find-minimum-BESS and Send-dispatch actions, four charts with limit lines, peak-value cards, alert list, before/after toggle, assumptions drawer, copy-JSON button, client-side CSV, and the fallback badge.
Why it exists: The no-install, first-click-works experience is what judges see in a video-only evaluation.
Alternatives: Plain HTML and JS (fastest start, but before/after state gets messy). Next.js (SSR adds nothing). Streamlit or Dash (quick, but weak UI control and a server to run).
Recommended: Vite, React, TypeScript, ECharts. Plain useState, no router, no state library, no component framework beyond light CSS.
Why it fits: It builds to static files for S3. ECharts has native threshold lines and shaded bands, which is what the voltage and hot-spot charts need. The fallback logic is simple: if the API call fails or times out, fetch /precomputed/<key>.json, render it, and show the badge.
2. Backend
Responsibility: Four routes: GET /scenarios, POST /simulate, POST /optimize, POST /dispatch. Internal modules: power flow, thermal, BESS, cost, OpenADR builder.
Why it exists: It keeps the physics in one trusted, testable place and means the core logic actually runs on AWS.
Alternatives: Run the engine in browser JS (nothing on AWS, and two copies of physics). FastAPI on ECS, EC2 or App Runner (servers to operate, no benefit here). Step Functions (nothing to orchestrate).
Recommended: One Lambda, Python 3.12, standard library only. Pre-allocate roughly 512-1024 MB. Cache the config in memory after the first read.
Why it fits: One simulation is 96 steps over two passes (periodic steady state). The BESS sweep is a small grid, a few dozen to a few hundred runs of the same simulator. That is well under a second, against a 3 s target. One monolithic Lambda is correct here. Skipping NumPy avoids packaging layers and cold-start cost.
3. Database
Responsibility: None.
Why: The PRD excludes persistence and scenario save/load. I also dropped v1’s optional run records, since CloudWatch logs cover debugging.
Alternatives: DynamoDB (only if save/load becomes a stretch goal; one table). RDS (never, for this).
Recommended: No database. Configuration and profiles are JSON in S3.
Why it fits: It removes a whole class of failure: IAM for tables, schema, connections.
4. AI/ML components
Responsibility: None in the system. The decision logic is physics, a threshold rule, and a bounded parameter sweep.
Why: The PRD excludes ML and LLM components, and there is no training data. Forecasting or generated text would add demo risk and no credibility.
Alternatives: SageMaker forecasting, Bedrock summaries. Both are excluded.
Recommended: Nothing. Call the product a physics-based digital twin, not AI-powered.
Why it fits: Judges can inspect and trust physics-backed numbers, and the thermal reference tests make them defensible.
5. External APIs
Responsibility: None at runtime. The only outbound calls are to AWS APIs.
Alternatives: Weather or grid-data APIs. They add keys, rate limits, and failure modes, and the PRD uses a fixed ambient profile.
Recommended: None.
6. File storage
Responsibility: The site bucket holds the frontend build and precomputed/ (all combinations plus BESS variants). The data bucket holds config/ (transformer parameters with source notes, profiles, limits, cost assumptions).
Why it exists: S3 is both the asset host and the data layer, so no database is needed. Keeping config as editable JSON satisfies “easy to swap for real data”.
Alternatives: One bucket (simpler, but mixes public and private paths). Bundling config in the Lambda zip (removes a read dependency, but makes data swaps a redeploy). EFS (unnecessary).
Recommended: Two private buckets. The site bucket is reached only via CloudFront Origin Access Control, and the data bucket is readable only by the Lambda. Block public access on both.
Why it fits: Cheap, durable, and the precomputed/ prefix is the safety net when the API misbehaves.
7. Authentication
Responsibility: None. The PRD says no login.
Alternatives: Cognito (a future-scope item).
Recommended: No auth, with compensating controls. Use API Gateway throttling and a small burst limit. Validate server-side that every field is an allowed enum and reject anything else. Use least-privilege IAM, with Lambda allowed to read config and publish to one IoT topic only. Set a billing alarm.
Why it fits: The endpoint accepts a handful of enums and does cheap work, so the abuse risk is low. Same-origin hosting means no CORS configuration.
8. Background processing
Responsibility: None at runtime. Simulation and the BESS sweep are synchronous.
Where precompute lives: It is a pre-deploy step, a local script that imports the engine, runs every combination (with BESS where violations exist), and writes JSON to precomputed/. It is not a Lambda or a scheduled job.
Alternatives: SQS plus a worker, Step Functions, EventBridge Scheduler. None is needed.
Recommended: None. A batch smoke test doubles as the precompute script, and any NaN fails the build.
Why it fits: It guarantees cached and live results come from the same code and removes an entire layer.
9. AWS services
Service	Role	Why it earns its place
S3	Site, precomputed results, config	Core storage and static hosting
CloudFront	HTTPS, caching, single origin with /api/* proxy	Safe S3 delivery and no CORS
API Gateway (HTTP API)	Public API, throttling	Cheaper and simpler than REST API
Lambda	The whole engine	Physics runs on AWS, not in the browser
IoT Core	MQTT topic gridmind/dt-250/dispatch	Gives the dispatch export a real destination
CloudWatch	Logs, alarms, dashboard, billing alarm	Debugging and demo-day confidence
IAM	Least-privilege roles	Required

IoT Core use: On Send dispatch, the Lambda builds the OpenADR-style payload, publishes it to the topic, and returns it for the copy button. In the video you show the same message arriving in the IoT test client, which acts as the simulated edge controller. It is a single publish call, with no browser MQTT, no identity pool, and no custom authorizer. The Lambda needs the account’s IoT data endpoint passed in as an environment variable.

Eligibility: The prize rules require either an AWS open-source tool or deployment on AWS. This design does both, since SAM CLI is AWS open source and the stack is deployed.

10. Deployment
Responsibility: One-command, repeatable deploy of everything.
Alternatives: Console click-ops (unrepeatable at hour 40). Terraform (more setup). CDK (more ceremony than SAM for this shape). Amplify Hosting (hides what you want to show judges).
Recommended: AWS SAM, one template, one stack, in ap-south-1. A single deploy script does the stack deploy, frontend build, s3 sync, and CloudFront invalidation. No CI/CD pipeline, one environment.
Why it fits: One template means a teammate or a fresh account can reproduce the stack in minutes. The template also makes a good architecture slide for the video. Deploy an empty skeleton in the first hours and a full rehearsal at least 12 hours before the deadline.
A. High-level architecture
                 Planner (browser)
                        │ HTTPS (one origin)
                        ▼
              ┌────────────────────┐
              │ CloudFront         │
              │  /*        ───────────▶ S3 site bucket (SPA, precomputed/)
              │  /api/*    ───────────┐
              └────────────────────┘  │
                                      ▼
                          ┌────────────────────┐
                          │ API Gateway (HTTP) │  throttling
                          └─────────┬──────────┘
                                    ▼
                  ┌──────────────────────────────────┐
                  │ Lambda: GridMind engine (Python) │
                  │  config loader · power flow ·    │
                  │  thermal + aging · BESS sizing · │
                  │  cost · OpenADR builder          │
                  └───────┬─────────────────┬────────┘
                          ▼                 ▼
                S3 data bucket          IoT Core topic
                (config/)               (mock edge controller)

        Logs, alarms, billing alarm ──▶ CloudWatch

   Offline: precompute script ──(same engine)──▶ S3 precomputed/
B. Data flow
The browser loads the SPA through CloudFront. It calls GET /api/scenarios, and the Lambda returns the allowed enum values and the assumption metadata from config/, cached in memory.
The user clicks Run simulation. The browser sends only enum values.
The Lambda validates every field, loads the matching profiles, and runs the 96-step loop twice, reporting day 2. Each step computes net load, solves voltage and loading, advances the thermal state, and computes the aging factor.
The Lambda returns one JSON result: time series, peaks, alert list, verdict, and insulation-life estimate.
On Find minimum BESS, POST /optimize runs the bounded sweep over power and energy with the same simulator. It returns the smallest feasible pair with the before/after series, or “no feasible size” with an upgrade recommendation, plus the cost comparison.
The browser renders charts, cards, and alerts. CSV is generated client-side from the same JSON.
On Send dispatch, POST /api/dispatch builds the payload, publishes it to IoT Core, and returns it for copying.
Failure path: on any API error or timeout, the browser loads /precomputed/<key>.json, renders it, and shows a “cached result” badge.
C. User flow
Open site (default scenario preloaded)
   └─▶ Run simulation  ── 1 click ──▶ Dashboard
          │
          ├─ No violations ──▶ Try a larger hub or different load level
          │
          └─ Violations ──▶ Find minimum BESS
                  ├─ Feasible ──▶ Before/after + BESS size + cost comparison
                  │                   └─▶ Send dispatch ──▶ JSON + IoT message
                  └─ Infeasible ──▶ "Upgrade recommended" verdict
D. AI/ML flow

There is no learned model. The decision pipeline is deterministic:

Enum inputs ─▶ validated ─▶ profiles from config
      │
      ▼
Net load per step (base + EV − PV ± BESS), fixed power factors
      │
      ├─▶ Power flow (fixed-point) ─▶ voltage, loading
      ├─▶ Thermal update (exponential) ─▶ top-oil, hot-spot
      └─▶ Aging factor ─▶ equivalent hours, insulation life
      │
      ▼
Violation check (voltage band, 110/140 °C, loading)
      │ violations?
      ▼
BESS rule (discharge on loading/voltage; charge on solar surplus/night)
      + bounded sweep over kW × kWh, efficiency and SOC limits,
        end SOC = start SOC
      │
      ▼
Feasible? ─ yes ─▶ cost comparison + OpenADR schedule
          └ no ──▶ "upgrade recommended"
E. Deployment architecture
Developer
  ├─▶ unit tests + precompute script (local, same engine)
  ├─▶ sam deploy ──────────▶ CloudFormation stack (ap-south-1)
  │        creates: S3 ×2, CloudFront, API Gateway, Lambda, IAM,
  │                 IoT permissions, CloudWatch alarms
  └─▶ build SPA ─▶ s3 sync (site + precomputed/) ─▶ CloudFront invalidation

Runtime
  Browser ─▶ CloudFront ─┬─▶ S3 site bucket
                         └─▶ API Gateway ─▶ Lambda ─┬─▶ S3 data bucket
                                                    └─▶ IoT Core
  Everything ─▶ CloudWatch

Backups: precomputed JSON in S3 · recorded demo video

No VPC, no servers, no pipeline, one stack, and one deploy script.

What I deliberately left out
Bedrock or SageMaker: the PRD excludes them and they add IAM and demo risk.
DynamoDB or Cognito: nothing in the MVP needs them.
Step Functions, SQS, EventBridge: nothing to coordinate or schedule.
NumPy and a Lambda layer: not needed at this size.
WAF and a custom domain: throttling and the default CloudFront domain are enough for a hackathon.
Run-record storage in S3: dropped from v1 to keep the system smaller.
Build order and reliability gates

This matches the PRD’s priority list, because the architecture only has value if the engine is right.

Engine module plus unit tests (thermal reference case, aging-factor values, power-flow sanity, BESS energy balance).
SAM skeleton deployed early (Lambda, API Gateway, CloudFront, S3), then the dashboard on top.
BESS sweep, then dispatch plus IoT publish.
Precompute script and fallback badge.
Cost comparison, CSV, and polish.
Demo video recording, then the blog post.

One decision for you: do you want to keep the config bucket separate, or bundle the config JSON into the Lambda package to drop one read dependency? I recommend the separate bucket, since it supports your “swap in real data later” story, but bundling is the lower-risk option if you are short on time.
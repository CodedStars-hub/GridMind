
Target repository layout
gridmind/
  config/            transformer.json, limits.json, costs.json, bess.json, profiles/*.json
  engine/gridmind_engine/   thermal, aging, powerflow, simulate, bess, cost, openadr, validate, keys, cli
  engine/tests/
  lambda/handler.py  thin routing and validation only
  scripts/           precompute, smoke_test, deploy
  web/               Vite + React + TypeScript
  infra/template.yaml
  docs/              api-contract.md, assumptions.md
M0: Scaffold, contract, config skeleton (~1.5 h)
Objective: Create a repo where every later piece has a defined place and a fixed interface.
Files/components: whole repo skeleton; docs/api-contract.md; docs/assumptions.md; config/*.json; engine/ package with empty modules; engine/tests/ with a passing placeholder test.
Dependencies: none.
Tasks:
Create the layout above, a README with one paragraph per folder, and a .gitignore.
Write api-contract.md defining the four routes (GET /scenarios, POST /simulate, POST /optimize, POST /dispatch), the request enums, and the response shape: meta (input echo, engine version, source flag), series (96-point arrays for time, voltage, loading, top-oil, hot-spot, aging factor, base/EV/PV/net load, BESS power and SOC), summary (min voltage and time, peak hot-spot, peak loading, peak and daily aging, insulation-life estimate), alerts (type, severity, start, end, peak value), verdict. Plus bess and cost blocks (nullable) and an error shape.
Create config files with parameter names and placeholder values. Every parameter has a source or assumption field. Include transformer nameplate and thermal parameters, limits, cost, BESS sweep grid and efficiency, and load-level presets (peak base load as a percentage of rating).
Define the precompute key format (for example ev{kw}_pv{kwp}_{day}_{load}_{bess}) in the contract.
Acceptance criteria: the folder tree exists; the contract covers every field the PRD’s Outputs section lists; pytest runs and passes; every config value has a note.
Commands: pytest engine/tests; JSON lint on config/ (for example python -m json.tool on each file).
Do NOT change/do: do not implement any physics yet, and do not choose final parameter values. Mark placeholders as "assumption": "TBD".
M1: Thermal model and aging factor (~2.5 h)
Objective: A tested, pure implementation of IEEE C57.91 top-oil and hot-spot temperatures and the aging acceleration factor.
Files/components: thermal.py, aging.py, config/transformer.json, engine/tests/test_thermal.py, test_aging.py.
Dependencies: M0.
Tasks:
Implement the steady-state top-oil rise and hot-spot rise as functions of load K (per unit) using the config’s rated rises, loss ratio, and exponents.
Implement the dynamic update using the exponential (analytic) step for both top-oil and hot-spot, so it is stable for a 15-minute step with a winding time constant of a few minutes. No forward Euler.
Implement the aging factor F_AA with the 110°C reference and equivalent-aging-hours helper (sum of F_AA times step length).
Implement the insulation-life helper (normal life from config, divided by daily equivalent aging).
Fill in transformer.json with typical ONAN values and a source note for each.
Acceptance criteria:
A constant rated load at the reference ambient converges to the nameplate hot-spot (about 110°C) within ±2°C.
F_AA is 1.0 at 110°C, about 0.6 at 105°C, about 11 at 135°C, about 17 at 140°C (within 2%).
Results are step-size independent (a 15-min step and a 1-min substep agree within a small tolerance).
A step load change relaxes monotonically toward the new steady state, with no oscillation.
Commands: pytest engine/tests/test_thermal.py engine/tests/test_aging.py -v.
Do NOT change: the contract, the file layout, or anything outside thermal.py, aging.py, transformer.json, and their tests. No power-flow code here.
M2: Power flow and transformer loading (~2 h)
Objective: A tested single-branch AC voltage solver giving voltage (p.u.) and transformer loading (%) from net P at a fixed power factor.
Files/components: powerflow.py, config/transformer.json and config/limits.json (feeder R/X, impedance voltage, source voltage, tap), engine/tests/test_powerflow.py.
Dependencies: M0 (M1 not required).
Tasks:
Model the HV source at 1.0 p.u., the transformer series impedance (from impedance voltage and load loss), and one lumped LV feeder impedance to the connection point.
Solve the voltage by fixed-point iteration with a tolerance and a maximum-iteration cap; return a clear failure (not NaN) on non-convergence.
Handle generation (negative net load) and reverse flow correctly (voltage rise).
Compute apparent power and loading K = S / S_rated, with the fixed power factors from config (base, EV, PV).
Document the topology and assumptions in docs/assumptions.md.
Acceptance criteria:
Zero load gives about 1.0 p.u.
Voltage drop grows monotonically with load.
A solved voltage reproduces a hand-calculated reference case in the tests.
Net export raises voltage above the no-load value.
Non-convergence is reported explicitly.
Commands: pytest engine/tests/test_powerflow.py -v.
Do NOT change: thermal and aging modules and their tests. Do not add reactive compensation, multi-node logic, or a general-purpose solver.
M3: Simulation orchestrator and CLI, the first runnable result (~3 h)
Objective: Run a full 24-hour scenario from enumerated inputs and print or write the contract-shaped JSON.
Files/components: validate.py, profiles.py (config loader), simulate.py, cli.py, config/profiles/*.json (base, EV, PV, ambient, per day type at 15 min), engine/tests/test_simulate.py.
Dependencies: M1, M2.
Tasks:
Validation: accept only the enums from the contract and reject anything else with the contract’s error shape.
Build the net load per step (base scaled by load-level preset, plus EV, minus PV) and select the day-type ambient profile.
Run the 96-step loop twice (periodic steady state), carrying thermal state across, and report day 2.
Build summary, alerts (merge consecutive violating steps into events with start, end, peak), and the one-line verdict.
Populate the profile files. Shapes should be plausible and documented; calibrate base load and feeder impedance to a documented plausible range, not to a target outcome.
CLI: python -m gridmind_engine.cli --ev 50 --pv 30 --day summer_weekday --load heavy writes JSON to stdout or a file.
Acceptance criteria:
The output validates against the contract (add a schema or key check in tests).
All arrays have 96 entries and contain no NaN or infinity.
Day 1 and day 2 start states are consistent (day-2 start close to day-1 end).
Increasing EV size never decreases peak loading or hot-spot.
Invalid enums are rejected.
Commands: pytest engine/tests -v; run the CLI for three different scenarios and inspect the summaries by eye.
Do NOT change: formulas in thermal.py, aging.py, powerflow.py (if a bug is found, report it rather than patching silently). No BESS, cost, or AWS code.
M4: Lambda handler for /scenarios and /simulate, local only (~1.5 h)
Objective: A thin HTTP-style handler around the engine, testable without AWS.
Files/components: lambda/handler.py, config loading with in-memory cache, engine/tests/test_handler.py.
Dependencies: M3.
Tasks:
Route by method and path; return JSON with correct status codes; map validation errors to 400 and unexpected errors to 500 with a safe message.
GET /scenarios returns the allowed enum values and assumption metadata from config.
POST /simulate calls the engine and returns the contract response.
Load config from a local directory by default and from S3 when an environment variable is set (implement the switch now, test S3 later in M5).
Structured log lines per request: route, inputs, duration, outcome.
Acceptance criteria: direct handler invocation with sample events returns 200 and contract-valid JSON; a bad payload returns 400; the second call uses the cached config.
Commands: pytest engine/tests/test_handler.py -v; invoke with a sample event JSON through a tiny local runner or sam local invoke if installed.
Do NOT change: engine modules, config schema, and the contract.
M5: Infrastructure skeleton deployed end to end (~3 h)
Objective: A public URL where the browser reaches CloudFront, S3, API Gateway, and the Lambda.
Files/components: infra/template.yaml, scripts/deploy.*, a minimal placeholder web/ page.
Dependencies: M4.
Tasks:
SAM template: two private S3 buckets (site, data), CloudFront with Origin Access Control, an HTTP API with a default throttle, one Lambda (Python 3.12, package the engine plus handler), IAM least privilege (read config/ in the data bucket, nothing else yet), CloudWatch log retention.
CloudFront behaviors: default to the site bucket; /api/* to the API Gateway origin (with the stage path handled and no caching); /precomputed/* served from the site bucket.
Upload config/ to the data bucket during deploy.
Deploy script: sam build, sam deploy (ap-south-1), sync the web build, invalidate CloudFront. Print the site URL.
Create a placeholder page that calls /api/scenarios and prints the result.
Acceptance criteria: the CloudFront URL loads the placeholder; /api/scenarios and /api/simulate work through CloudFront; both buckets block public access; a direct S3 URL is denied.
Commands: sam validate; sam build; sam deploy; curl the two API routes through the CloudFront URL; check CloudWatch logs for the request lines.
Do NOT change: engine code and the contract. Do not add IoT, extra buckets, a custom domain, WAF, or a pipeline yet.
M6: Frontend shell with live simulation, the first usable app (~3.5 h)
Objective: Pick inputs, click Run, and see the main charts from the deployed API.
Files/components: web/ (Vite, React, TypeScript, ECharts), typed API client that mirrors the contract, input panel, chart components.
Dependencies: M5.
Tasks:
Scaffold the app with only React and ECharts as extra dependencies. No router, no state library.
Fetch /api/scenarios to build the dropdowns, with defaults preselected so one click runs.
Run button calls /api/simulate and shows a loading state and an error state.
Charts: voltage with the 0.95/1.05 band, hot-spot with 110 and 140°C lines, loading with a 100% line. Axis labels with units and a time axis in hours.
Mark violations with icon and text, not colour alone, and use a colour-blind-safe palette.
Add a Vite dev proxy so local development can target either the deployed API or a local runner.
Acceptance criteria: the deployed site shows three charts for the default scenario within one click; changing any dropdown and rerunning updates the charts; an API failure shows a readable error (no blank screen, no NaN on charts).
Commands: npm run build and npm run typecheck; deploy with the script; manual walkthrough in Chrome.
Do NOT change: the backend, the contract, and infra (except the deploy script’s frontend step if needed).
M7: Dashboard completeness (~2.5 h)
Objective: Everything in PRD 8.1 and 8.5 that does not need BESS.
Files/components: web/ summary cards, alert list, assumptions drawer, timeline strip, CSV export, verdict banner.
Dependencies: M6.
Tasks:
Cards: min voltage and time, peak hot-spot, peak loading, peak and daily aging, insulation-life estimate.
Alert list with type, severity, start, end, and peak; verdict banner with icon and text.
Assumptions drawer that renders the /api/scenarios assumption metadata (parameter, value, source or assumption).
Timeline strip for EV and solar windows from the selected inputs.
Client-side CSV from the response series (the PRD’s columns plus aging).
A visible planning-grade disclaimer.
Acceptance criteria: every PRD output marked as non-BESS appears; CSV opens in a spreadsheet with 96 rows and correct headers; the drawer lists every config parameter that is shown to the user.
Commands: npm run build, npm run typecheck, manual check against the CLI output for one scenario (values match).
Do NOT change: the backend or the contract. No BESS UI yet.
M8: BESS engine, dispatch rule and simulation integration (~3 h)
Objective: Simulate with a given BESS size using the rule-based dispatch and correct energy accounting.
Files/components: bess.py, config/bess.json, an extension of simulate.py (BESS as an optional input), engine/tests/test_bess.py.
Dependencies: M3.
Tasks:
Dispatch rule: discharge when loading exceeds the configured threshold or voltage falls below the limit; charge from surplus solar or in the configured night window; otherwise idle. Thresholds come from config.
Respect power limit, energy capacity, SOC limits, and round-trip efficiency.
Enforce end-of-day SOC equal to start-of-day SOC (via a start-SOC choice or a day-2 convergence loop, documented).
Feed the BESS power into the net load and return the SOC series and dispatch schedule.
Keep the no-BESS path byte-identical to M3.
Acceptance criteria: with zero-size BESS the result equals no-BESS; the energy balance holds within tolerance; SOC stays within limits; end SOC matches start SOC; a sensibly sized BESS lowers peak loading.
Commands: pytest engine/tests -v (including all M1-M3 tests, which must still pass).
Do NOT change: the thermal, aging, and power-flow formulas. Do not add an optimizer yet.
M9: Sizing sweep, cost comparison, /optimize endpoint (~2.5 h)
Objective: Find the minimum feasible BESS or declare that none exists, and compare with a transformer upgrade.
Files/components: bess.py (sweep), cost.py, config/costs.json, handler route /optimize, tests.
Dependencies: M8, M4.
Tasks:
Sweep the config grid of power and energy; feasibility means zero voltage violations and hot-spot at or below the warning limit; choose the smallest by the configured cost metric.
If nothing is feasible, return bess: null with an upgrade-recommended verdict. This is a valid result.
Cost module: upgrade cost versus BESS cost (per kWh and per kW from config); the net difference may be negative; insulation life with and without BESS from the aging helper.
/optimize returns before and after results, the BESS size, the dispatch schedule, and the cost block per the contract.
Update the contract doc if any field changes.
Acceptance criteria: the sweep result is deterministic; a scenario with no violations reports that BESS is unnecessary; an infeasible scenario returns the upgrade verdict; the cost block can show a negative saving; the response stays within the time budget.
Commands: pytest engine/tests -v; a batch run of the sweep over the 144 combinations (log any errors, NaNs, and the run time); sam build and deploy, then curl /api/optimize.
Do NOT change: the no-BESS result and the existing routes’ behaviour.
M10: BESS user interface (~2.5 h)
Objective: Find minimum BESS, before/after view, SOC chart, and cost comparison in the app.
Files/components: web/ Find-minimum-BESS button and state, before/after toggle, SOC chart, cost panel.
Dependencies: M9, M7.
Tasks:
Show the button only when violations exist, and show a clear message when none exist.
Before/after toggle swapping the series on the same charts, with the BESS size shown.
SOC chart and the dispatch schedule summary.
Cost panel: upgrade, BESS, net difference (signed), insulation life before and after, and the assumption note.
Handle the infeasible result with an upgrade-recommended banner.
Acceptance criteria: the full unmitigated-to-mitigated flow works on the deployed site; the infeasible case renders without error; every number on screen traces to a response field.
Commands: npm run build, npm run typecheck, deploy, manual walkthrough of both cases.
Do NOT change: the backend and the dashboard from M7 beyond adding the BESS views.
M11: OpenADR-style payload, /dispatch, and IoT Core publish (~2.5 h)
Objective: A copyable payload that also arrives on an IoT topic.
Files/components: openadr.py, handler route /dispatch, infra/template.yaml (IoT permission and endpoint env var), web/ Send-dispatch button and payload view, tests.
Dependencies: M9, M10.
Tasks:
Build a payload modelled on OpenADR 2.0b: event ID, event start and end, interval list (start, duration, signal type, signed kW), baseline profile, and a clear mock label in the metadata.
Validate that the payload is syntactically valid JSON and has all fields (tested).
Add iot:Publish for the single topic ARN to the Lambda role, pass the IoT data endpoint through environment configuration, and publish on /dispatch.
If publishing fails, still return the payload with a flag that publishing failed. The copy button must never depend on IoT.
UI: button, formatted JSON view, copy button, and a published or failed indicator.
Acceptance criteria: the payload parses and passes the field check; the message appears in the IoT console test client subscribed to the topic; IoT failure degrades gracefully; the IAM policy covers only this topic.
Commands: pytest engine/tests -v; deploy; subscribe in the IoT test client and click the button; verify the message.
Do NOT change: existing routes, the BESS logic, and any other IAM permissions.
M12: Precomputed results and fallback (~2.5 h)
Objective: Every combination is cached, and the UI degrades to the cache automatically.
Files/components: scripts/precompute.*, web/ fallback logic and badge, deploy script (sync precomputed/), a batch smoke test.
Dependencies: M9, M10.
Tasks:
The precompute script runs the engine for all 144 combinations and the sweep where violations exist; writes files named by the key format; fails the run on any NaN, error, or schema violation.
The deploy script uploads precomputed/ to the site bucket.
The frontend wraps API calls with a timeout and retry once, then loads the matching cached file and shows a “cached result” badge. Dispatch has no cache fallback (the payload is regenerated client-side from the cached schedule only if you decide it is worth it; otherwise show an explicit unavailable message).
A smoke test that compares a cached file with a live response for sampled combinations and requires equality of the key fields.
Acceptance criteria: all files exist and validate; with the API forcibly broken (for example, a temporarily wrong route), the UI still shows results with the badge; cached and live summaries match.
Commands: python scripts/precompute...; pytest the parity test; deploy; break the API deliberately and reload.
Do NOT change: engine outputs or the contract, or engine behaviour to make parity pass (if they differ, find the bug).
M13: Hardening and observability (~2 h)
Objective: Safe to leave public and easy to debug.
Files/components: infra/template.yaml, the handler logging, web/ error handling.
Dependencies: M11, M12.
Tasks:
Tighten API throttling (rate and burst) and request body size limits.
CloudWatch alarms on Lambda errors and throttles, a small dashboard (invocations, errors, duration), and an AWS billing alarm.
Log retention, and ensure logs never contain more than the input enums and timings.
Confirm least-privilege IAM by review (list each permission and why).
Frontend: no unhandled promise rejections; every failure path shows a message.
Acceptance criteria: over-limit requests are throttled; alarms exist; the IAM review is written in docs/; a malformed request never produces a stack trace in the response.
Commands: sam validate, deploy, a short burst test with curl in a loop, view the dashboard.
Do NOT change: features or the contract. No new services.
M14: Release rehearsal and demo support (~3 h)
Objective: A clean deploy from scratch, a recorded demo, and the submission pieces.
Files/components: README, docs/architecture.md, docs/demo-script.md, repo cleanup.
Dependencies: all prior milestones.
Tasks:
Fresh-clone rehearsal: tests, precompute, deploy, and full walkthrough. Fix only breakages.
README with the architecture diagram, how to run locally, how to deploy, and the assumptions and limitations (planning-grade, single transformer, mock OpenADR).
Demo script following the PRD flow, with a rule that every number is read from the screen.
Capture the AWS evidence: IoT message arriving, the stack resources, and the dashboard.
Draft the AWS Builder Center blog outline: problem, stack, and what fought back.
Acceptance criteria: a teammate can deploy from the README alone; the recorded video is 3 minutes or less and shows the unmitigated, mitigated, and dispatch flow plus AWS; the repo has no secrets or stray files.
Commands: the complete test suite, the deploy script, a final manual run in a clean browser profile.
Do NOT change: any feature code. Stop all feature work before this milestone starts.
Cut line if time runs short

Keep M0-M7 as the minimum shippable product. Then add M8-M10 for the BESS story, M11 for the AWS IoT story, and M12 for reliability. M13 can shrink to throttling plus the billing alarm. M14 cannot be skipped, because the demo video is what judges see.
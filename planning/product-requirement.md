GridMind: Product Requirements Document (v2.0)
WeMakeDevs Environmental Hacks 2026 · Track: Waste and Energy · 9 Oct 2026 · Supersedes v1.0
1. Problem
Urban and peri-urban 11 kV/415 V distribution transformers (typically 100-630 kVA) were sized before DC fast charging and rooftop solar. A charging hub adds a concentrated evening load exactly when solar output has fallen to zero, and in Indian summers ambient temperature is already 40°C or more. Two constraints bind: (a) voltage at the connection point, and (b) winding hot-spot temperature, which drives insulation life loss exponentially (IEEE C57.91). Planners currently either approve an interconnection without a time-resolved check, or demand an upfront upgrade (assumed ₹5-7 lakh per transformer; configurable) that stalls EV and solar adoption.
Track fit: Waste and Energy (rooftop solar, EV nudges). The tool helps a planner say yes to clean load safely.
2. Target Users
• Primary: DISCOM planning and operations engineers evaluating EV or rooftop-solar interconnection requests.
• Secondary: EV hub developers and solar installers checking grid impact before applying; SERC reviewers.
• Demo persona: one planner, one transformer, one decision: approve, approve with a battery, or upgrade.
3. User Pain Points
• No lightweight, no-install tool for time-resolved what-if checks on a single transformer.
• Enterprise tools (ETAP and similar) need licences and specialist setup.
• Spreadsheet checks use peak-vs-nameplate rules and miss the solar-ramp-down plus EV-ramp-up interaction.
• Studies deliver a verdict, not a machine-readable dispatch signal.
• Approving blind carries liability; refusing blind carries a climate and customer cost.
4. Existing Alternatives
Alternative
Gap
ETAP, EcoStruxure and similar
Licensed, specialist-driven, not a quick planner sandbox
Peak-load vs nameplate rule of thumb
Static; ignores thermal inertia and ambient temperature
pandapower and academic scripts
Python expertise, no UI, no transformer thermal coupling by default
Utility-internal analytics
Not available to other DISCOMs or to developers
Spreadsheets
No coupled voltage plus hot-spot plus aging over 24 h
5. Unique Value Proposition
GridMind is a browser-based, physics-based digital twin of one distribution transformer. In a single run it couples AC voltage with an IEEE C57.91 hot-spot and aging model, sizes a battery (BESS) to clear violations, and emits an OpenADR-style dispatch payload.
• Coupled physics: voltage, loading, hot-spot, and loss-of-life from one simulation.
• Decision output: feasible / not feasible, minimum BESS size, and an honest comparison against a transformer upgrade.
• Actionable: dispatch schedule published to an AWS IoT Core topic standing in for an edge controller.
• Honest wording: this is a planning-grade tool. We do not claim to be the first, to be AI-driven, or to be connected to any vendor controller.
6. Core User Journey
1. Open the site (no login). A default scenario is preloaded, so one click on Run simulation gives a first result.
2. Optionally change: EV hub size, solar size, season/day type, existing transformer loading level.
3. Dashboard shows voltage, loading, hot-spot, aging factor, and alerts against limits.
4. If violations exist, click Find minimum BESS. The tool shows before/after and the BESS size, or reports that no feasible size exists within bounds.
5. Review the upgrade-vs-BESS cost comparison and insulation-life impact.
6. Click Send dispatch. The OpenADR-style JSON is shown, copyable, and published to IoT Core.
7. Primary Feature
24-hour time-series AC power flow with IEEE C57.91 thermal and aging model (single transformer, 96 steps at 15 min).
• Power flow: HV source at 1.0 p.u. (fixed tap), transformer series impedance, one lumped LV feeder impedance to the connection point. Loads at fixed power factor (base 0.95 lagging, EV 0.98, PV unity); no reactive compensation. For this single-branch radial topology a fixed-point iteration of the voltage equation is exact; no general solver is needed.
• Thermal: top-oil and hot-spot temperature per IEEE C57.91 (ambient, load K = S/S_rated, no-load and load losses, oil and winding time constants). State is advanced with the exponential (analytic) update, not forward Euler, because the winding time constant is shorter than a 15-min step.
• Initial condition: run the day twice and report day 2 (periodic steady state), so results do not depend on an arbitrary 00:00 start.
• Aging acceleration factor: F_AA = exp(15000/383 - 15000/(θ_H + 273)), where θ_H is hot-spot in °C (reference 110°C gives 1.0). Reference values: about 0.6 at 105°C, about 11 at 135°C, about 17 at 140°C. Report equivalent aging hours per day and implied insulation life (normal life 180,000 h at reference).
• Violations: voltage outside 0.95-1.05 p.u. (configurable); hot-spot above 110°C (warning) and 140°C (critical); loading above 100% (information).
This is the product. If only this ships, the project is still complete.
8. Secondary Features
• 8.1 Scenario builder: dropdowns for the enumerated inputs below; a timeline strip showing EV and solar windows; a Model and assumptions drawer listing every parameter with its source.
• 8.2 BESS sizing (rule-based plus bounded sweep): dispatch rule: discharge when loading exceeds a threshold or voltage drops below 0.95; charge from surplus solar or night off-peak. Sweep power (kW) and energy (kWh) over a small grid using the same simulator; pick the smallest feasible pair. Model round-trip efficiency (90%), SOC limits (10-90%), and end-of-day SOC equal to start-of-day SOC. If nothing in the grid is feasible, say so and recommend upgrade.
• 8.3 Dispatch export: OpenADR 2.0b-style JSON (event ID, interval start/end, baseline, charge/discharge signals); copy button; publish to an AWS IoT Core MQTT topic, shown arriving in the IoT test client. Labelled a mock payload, structurally modelled on OpenADR 2.0b.
• 8.4 Cost comparison: inputs are transformer upgrade cost, BESS cost per kWh and per kW (all editable, defaults documented as assumptions). Output is net difference, which may be negative, plus insulation life with and without BESS. The v1.0 payback-from-avoided-aging figure is dropped because it was ill-defined.
• 8.5 Results dashboard: four charts (voltage, hot-spot, loading, BESS SOC), peak-value cards, alert list with timestamps, before/after toggle, CSV export generated in the browser. Colour-blind-safe palette; severity shown by icon and label, not colour alone.
• 8.6 Cached-result fallback: every input combination is precomputed to S3; if the API call fails, the UI loads the cached result and shows a visible badge.
9. Features Explicitly Excluded from MVP
• Multi-node feeders, three-phase unbalanced flow, reactive power control
• Real SCADA or smart-meter integration; physical hardware or vendor controllers
• Authentication, accounts, database persistence, scenario save/load
• ML or LLM components in the critical path (no forecasting; no generated explanations)
• Custom profile upload; weather or grid-data APIs
• Mobile or responsive layout (desktop browser only)
• Full mathematical optimisation of BESS (the bounded sweep is the optimiser)
10. Inputs
User-selected (all enumerated, so the input space is finite):
Input
Values
EV hub (kW)
10, 30, 50, 100
Rooftop solar (kWp)
0, 10, 20, 30
Day type
Summer weekday, winter weekday, weekend
Existing transformer loading
Moderate, heavy, critical (preset base-load scaling)
BESS
Off, or auto-size
This gives 4 x 4 x 3 x 3 = 144 no-BESS combinations, each with one optional BESS result: all precomputable.
Preloaded config (JSON, each parameter carries a source/assumption note): transformer nameplate (250 kVA, impedance voltage, no-load and load loss, oil and winding time constants and exponents, rated rises); LV feeder R and X; 15-min base, EV, and PV profiles per day type; 24 h ambient profile; limits; cost assumptions; BESS efficiency and SOC limits.
Calibration rule: base-load levels and feeder impedance are chosen from a documented, plausible range for a loaded Indian distribution transformer. They are not tuned to produce a pre-chosen demo number.
11. Outputs
• Charts: voltage (p.u.), hot-spot (°C) with 110/140°C lines, loading (%), BESS SOC (%).
• Numbers: minimum voltage and time; peak hot-spot; peak loading; peak and daily-equivalent aging; estimated insulation life; required BESS kW and kWh; cost comparison.
• Verdict: one line, e.g. Safe / Safe with BESS of X kW and Y kWh / Upgrade recommended.
• Exports: OpenADR-style JSON; CSV of time series.
12. Success Metrics
Metrics are tests the system must pass, not outcomes chosen in advance. Demo figures come from model output.
Correctness (must pass before any UI polish):
• Reference test: constant rated load at the reference ambient converges to the nameplate hot-spot rise (about 110°C total) within ±2°C.
• F_AA test: 110°C gives 1.0; the 105/135/140°C values above reproduce within 2%.
• Energy sanity: BESS energy in and out balances with efficiency; end SOC equals start SOC.
• Voltage sanity: zero load gives about 1.0 p.u.; drop grows monotonically with load.
Performance and reliability:
• API response under 3 s warm (typically well under 1 s); cold start under 6 s.
• Any failed API call degrades to a cached result in under 2 s with a visible badge.
• All 144 combinations plus BESS variants run without error or NaN in a batch test.
Usability:
• A first-time user who is not on the team reaches a result with one click from the default and a BESS result with two more.
• Exported JSON parses with a standard JSON parser and contains all required fields.
Judging alignment (from the hackathon page): real problem and who benefits (idea and impact); AWS deployed (built on AWS); clear for a non-expert (design); every shown feature works (execution); 3-minute recorded video (demo).
13. Demo Flow (3-minute recorded video; there is no live demo)
• 0:00-0:25 Problem. One planner, one request for a 50 kW charging hub. Show the two limits (voltage band, hot-spot) in plain words.
• 0:25-1:10 Unmitigated. Default scenario, click Run. Walk through the charts and red alerts, reading the values from the screen. Show aging factor and insulation life.
• 1:10-2:00 Mitigated. Click Find minimum BESS. Show before/after, SOC chart, BESS size, and the upgrade-vs-BESS cost comparison, including an honest case where upgrade wins if one exists in the presets.
• 2:00-2:35 Actionable. Click Send dispatch. Show the JSON and the message arriving in the AWS IoT Core test client.
• 2:35-3:00 AWS and close. Show the architecture slide and the CloudFormation/SAM stack; one-line close on letting planners say yes to clean energy safely.
Record a clean take the day before submission; rehearse the exact click path.
14. Technical Requirements
• Frontend: Vite, React, TypeScript, ECharts; static build on S3 behind CloudFront.
• Backend: one Python Lambda behind an API Gateway HTTP API. Routes: GET /scenarios, POST /simulate, POST /optimize, POST /dispatch. Modules kept separate: power flow, thermal, BESS, cost, OpenADR builder.
• Data: config and profiles as JSON in S3 (loaded once, cached in Lambda memory); precomputed results under a precomputed/ prefix; no database.
• AWS services: S3, CloudFront, API Gateway, Lambda, IoT Core (publish only), CloudWatch, IAM. No VPC, no servers.
• Deployment: AWS SAM, single stack, ap-south-1, one deploy script (stack deploy, build, bucket sync, cache invalidation).
• Validation: enum-only input validation server-side; API throttling; CORS allow-list.
• Tests: unit tests for thermal reference case, aging factor, power-flow sanity, BESS energy balance; a batch smoke test over all combinations.
• Submission extras: public deployed URL, repository, 3-minute video, and an AWS Builder Center blog post (eligible for the blog prize).
15. Non-Functional Requirements
• Usability: no install, no login, Chrome/Edge/Firefox desktop; sensible defaults; every chart labelled with units and limits.
• Reliability: graceful errors for bad input; NaN or infinity never reaches a chart; cached fallback as above.
• Maintainability: modular code, config separate from logic, every parameter documented with a source or marked as an assumption.
• Security: no user data stored; least-privilege IAM (Lambda may read config, write runs, publish to one IoT topic only); bucket public access blocked, site served only via CloudFront.
• Transparency: a visible statement that results are planning-grade, valid only for the stated single-transformer configuration, and not a substitute for a utility's engineering study.
• Accessibility: colour-blind-safe palette, text and icon severity cues.
• Cost: within free-tier credits; billing alarm set.
16. Risks
Risk
Likelihood
Impact
Mitigation
Thermal model implementation error
Medium
High
Reference-case unit tests before UI work; show assumptions drawer
Unrealistic or hand-tuned sample data
Medium
High
Documented ranges with sources; no output targets; sensitivity presets
Demo numbers contradict the model
Medium
High
Read all figures from live output; no hardcoded narration numbers
BESS sweep finds no feasible size
Medium
Medium
Treat as a valid result: recommend upgrade
Overclaiming (first, AI, vendor integration)
Medium
Medium
Approved wording list in section 5; mock payload labelled as such
AWS deployment problem near deadline
Medium
High
Deploy a skeleton in the first hours; precomputed fallback; recorded video as a hard deliverable
Scope creep
High
High
Priority order below; feature freeze before final 12 hours
Time (about 2 days of the 4-day window remain)
High
High
Build order: engine and tests, then API plus dashboard, then BESS, then export and IoT, then polish, video, blog
Priority order (cut from the bottom): (1) engine plus tests, (2) deployed API plus dashboard, (3) BESS sizing, (4) dispatch export plus IoT publish, (5) precomputed fallback, (6) cost comparison, (7) CSV export, (8) blog post.
17. Future Scope
• Short term: multi-node feeders with coordinated dispatch; custom profile upload; scenario save/load (DynamoDB, Cognito); calibrating against real DISCOM load data.
• Medium term: three-phase unbalanced flow; reactive power and inverter VAR control; optimisation-based BESS sizing; load forecasting; real telemetry via an OpenADR VEN integration.
• Longer term: hosting-capacity maps per circle; V2G and shared community batteries; extreme-heat scenarios; pilot with a DISCOM.
Appendix: Changes from v1.0
Change
Reason
Aging model fixed to C57.91 Arrhenius (110°C reference)
v1.0 mixed two incompatible rules and quoted demo values matching neither
Success metrics rewritten as tests; demo numbers come from the model
Pre-set targets cannot be honestly defended
Added LV feeder impedance and fixed power factors
A single node has no voltage drop otherwise; kVA loading needs a power factor
Exponential thermal update and periodic steady-state start
Time constants versus step size; avoids start-up bias
Added existing-loading preset
Makes the stress case a documented input rather than hidden tuning
Payback replaced with insulation life and signed cost comparison
Original payback was undefined; BESS may cost more than an upgrade
Dispatch labelled mock OpenADR-style; no vendor claim; no 'first' claim
Accuracy
Added precomputed fallback, recorded-video-first demo plan, blog deliverable, priority order
Matches judging (video only, working beats broad) and the remaining time
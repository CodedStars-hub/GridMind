# GridMind frontend - M12 foundation and M13 network explorer

React + strict TypeScript + Vite + Tailwind. This workspace reads actual API configuration, shows backend health and runs supported single-transformer scenarios. It does not include the full interactive digital twin, maps, hosting UI, placement controls, batteries, dispatch, precomputation or telemetry. Backend planning endpoints exist; their interactive frontend is upcoming.

## Local setup

Use Node.js 22.12+ (or a newer supported LTS). From the repository root:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open **http://localhost:5173**. The port is fixed with `strictPort`; it will not silently change and invalidate the documented browser origin. Dependencies are local to frontend; nothing is installed globally. After an approved first installation creates the lockfile, `npm ci` reproduces it.

## API connection and CORS

The deployed URL supplied for this milestone is:

`https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com`

The browser base comes from `VITE_API_BASE_URL`. With the example file, it is `/api`: the browser calls `http://localhost:5173/api/v2/health`, `/api/v2/network`, `/api/v2/scenarios` and `/api/v2/simulate`. Vite's **development-only**, localhost-bound proxy removes `/api` and forwards to `GRIDMIND_API_PROXY_TARGET`, the deployed HTTPS origin. Certificate checks stay enabled. The trusted server-to-server hop omits Origin, Cookie and Authorization; browser requests remain same-origin. This does not change or redeploy AWS, and does not enable browser CORS on the backend.

`GRIDMIND_API_PROXY_TARGET` is server-only configuration, not a `VITE_` variable. Set it explicitly; there is no hardcoded fallback upstream. If it is missing, `/api` has no proxy and the UI reports an unavailable or invalid response. Never put secrets into `VITE_` variables: Vite embeds them in the public bundle.

For direct browser access, set:

```dotenv
VITE_API_BASE_URL=https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com
```

Direct requests will fail with the current backend `AllowedOriginsJson=[]`. The exact development allowlist value needed is **`["http://localhost:5173"]`**. `localhost` and `127.0.0.1` are distinct origins. A human must separately review and approve updating the existing stack's `AllowedOriginsJson` parameter; preserve its other parameters. Through the documented SAM workflow, the parameter argument is:

```bash
--parameter-overrides 'AllowedOriginsJson=["http://localhost:5173"]'
```

This is a deployment-command argument, **not permission to deploy**. Consult [infrastructure instructions](../infra/README.md) before any AWS update. No wildcard origin or credentialed CORS is needed. A production frontend needs its actual approved HTTPS origin in that list or an separately approved same-origin API reverse proxy. No production hosting is implemented here.

## Checks and builds

```bash
npm run typecheck
npm test
npm run build
npm run preview
```

`dist/` is ignored. Vite's development proxy is not included in the production bundle or configured for preview. A preview at `http://localhost:4173` therefore needs direct API configuration and separately approved CORS for that origin, or an external same-origin proxy. To build for direct API access without changing local development configuration:

```bash
VITE_API_BASE_URL=https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com npm run build
```

No preview/build command deploys anything. From the repository root, existing backend regression checks remain:

```bash
.venv/bin/python -m pytest engine/tests -v
git diff --check
```

## Architecture and interview notes

- `src/app/`: shared layout, hash navigation, error boundary and health/network state. Hash links work on a static host without server-side routing rules. Route changes update the title and move keyboard focus to main content.
- `src/pages/`: Overview, Network, Assessment, Planning and Not Found. Overview totals are **configured counts and nameplate ratings**, not measured demand, available headroom or live operating health. Customer connections include whatever counts the backend config defines; they are not automatically residential households.
- `src/components/`: reusable panels, metrics, table and loading/error/empty states. The system-font stack avoids external font requests. Restrained teal/slate tokens, focus indicators, table captions and responsive navigation support clear engineering presentation.
- `src/types/api.ts`: types for the four consumed operations derived from contract §§2-4 and 13. No unsupported endpoint or response fields. Neighborhood impact/hosting/planning types are deferred until their UI is implemented.
- `src/api/`: finite-value and shape checks at the untrusted response boundary, AbortController timeout/cancellation, structured server errors and no credentialed requests. The default request timeout is a transport setting, not a physics parameter. There are no automatic retries, caches or fabricated fallback results.
- Simulation inputs and defaults come from `/v2/scenarios`. Display values come from successful `/v2/simulate` responses; the browser performs no physics. Errors clear prior results. While editing a completed scenario, the result remains explicitly labeled with the last submitted inputs.
- `src/test/`: mocked transport and component/navigation tests. JSON fixtures were captured from the unchanged local backend (default simulation plus network/scenarios). They are **test-only** and are never imported by application pages or used as fallback data. Tests check failure states and cancellation as well as success.

A healthy health endpoint means the application loaded configuration; it is not proof every backend operation works or real telemetry exists. Network errors are reported separately. Aging and economic metrics are modeled estimates, not transformer failure dates or confirmed household damage. Neighbourhood before/after storytelling belongs to later milestones; no placeholder charts represent fake results.

## Interactive network explorer

The shared `DataProvider` fetches `/v2/network` through the existing typed API client. The Network page passes its validated response to `NetworkExplorer`; the explorer never fetches independently. Responsive inventory cards group charging sites under their configured transformer. The API supplies illustrative map coordinates and site associations, but no electrical feeder edges. We therefore show an inventory rather than inventing a connected grid or geographic map. Ratings and site power ceilings are configuration, not measured loading or available hosting capacity.

Selection is local to the Network page and stores only the equipment kind and stable ID. Initially the first transformer in API order is selected. A refresh preserves an ID that still exists and updates its details; removed equipment resets selection to the first remaining transformer, and an empty inventory clears it. Loading and error states hide stale details while retaining the selection for a successful retry. Native buttons provide keyboard activation, visible focus and pressed-state labels.

The details panel shows only response fields: transformer rating, archetype, load level, EV usage, connection count and associated sites; site details show its transformer, configured maximum kW and footfall score. Assessment and Planning links open existing workflows; they do not transfer the selected equipment or create an allocation. Equipment-specific assessment, placement controls and simulation overlays remain future work. Component tests cover real backend fixture rendering, selection, refresh, removal, missing topology and honest empty/error states.

## Mandatory frontend milestone gate

Do not finish a frontend milestone on unit tests alone. Start the development server from `frontend/` with `npm run dev` (explicitly loads `vite.config.ts`), then, in a second terminal, run:

```bash
cd frontend
npm run verify
```

This runs `npm test -- --reporter=verbose`, `npm run typecheck`, `npm run build`, the existing `.venv/bin/python -m pytest engine/tests -v` from the repository root, `git diff --check`, and `npm run smoke:api`. Nothing is deployed or installed. Every failed check exits nonzero; the smoke check is never silently skipped. For a separately started development port, use `npm run verify -- http://localhost:5174` or `npm run smoke:api -- http://localhost:5174`.

The integration tests start real local HTTP fixture and Vite servers using the application configuration. They check prefix rewriting, response fixtures, upstream errors, stripped credentials and compiled Tailwind. These are deterministic local tests, **not live AWS verification**. The smoke command checks the running proxy's health, network, scenarios and a real simulation using API-supplied defaults against the same guards used by the UI. Its JSON results come from the configured upstream, not test fixtures. A successful HTML fallback is a failure, even when HTTP status is 200.

Browser review remains explicitly manual: open Overview and confirm actual connectivity/configuration; inspect transformer/site selection on Network; open Assessment, submit a real simulation and verify returned values, loading and failure states; check sans-serif typography, focus and responsive layout. Inspect Network responses for JSON content type and `/api/v2/...` URLs. Do not claim browser review unless it was performed.

### Diagnosing an HTML fallback or serif typography

In the M13 incident, the existing server on 5173 returned Vite HTML for API GET requests, an empty 404 for simulation POST, and unprocessed `@theme` CSS. A fresh server using the checked-in configuration returned real AWS JSON and processed Tailwind. This establishes missing proxy/plugin configuration in the old running process; the historical reason it omitted that configuration is unknown. The client binding and environment file were intact, and the M13 changes did not alter the configured font stack.

Stop and restart your existing development server with `npm run dev` after configuration/environment changes; do not start a competing process on the same port. The config now resolves environment files relative to the frontend directory and rejects an absent proxy target when `/api` is selected. The root font includes a sans-serif fallback even if theme processing fails. Error messages distinguish HTML, invalid JSON, contract mismatch, HTTP errors, network failures, cancellation and timeouts without displaying response bodies or secrets. Unit tests and production builds cannot prove the already-running server has the intended proxy/plugins: run the smoke command and manual browser checks before completion.

## M14 simulation visualization

Assessment uses the existing `/v2/scenarios` and `/v2/simulate` calls; no endpoint, API client or backend calculation changed. The simulation contract supplies 96 actual modeled samples at 15-minute intervals for voltage (p.u.), loading (% of rated current), hot-spot/top-oil/ambient temperature (°C), aging acceleration (dimensionless), and base/EV/PV/net power (kW). These are planning-model outputs, not measured hourly telemetry. Alerts include severity and inclusive first/last step timestamps. BESS series remain null in this workflow.

`SimulationCharts` draws responsive SVG polylines directly from voltage, loading and hot-spot arrays. `simulationAnalysis.ts` computes plotting coordinates and signed comparison differences only, never physics or interpolated engineering readings. No charting dependency was added: three 96-point charts are small enough for standard SVG and React. Axes include units and returned time labels. Hover snaps to a returned sample; the shared native range control supports keyboard inspection, and a disclosed table provides all current samples plus aging. Temperatures are end-of-step values labelled by step start, matching the API.

Limit lines come from exact `/scenarios` assumption keys: voltage_min_pu, voltage_max_pu, loading_info_pct, hotspot_warning_c and hotspot_critical_c. Numeric finite limits are used; null/missing limits are explicitly unavailable. Thresholds are hidden when the scenarios engine version does not match the result. Comparisons are strict: equality is not a violation. Current violations are filled circles; pinned-scenario violations are outlined circles. Actual backend alert events and verdicts remain authoritative, including the distinction between informational loading events and warning/critical violations. A missing line never means a scenario is safe.

Click **Use as comparison A** on a successful response, change inputs and run again to obtain B. Both results are labelled with scenario inputs. The comparison table shows actual returned metrics and signed B-minus-A differences; loading changes are percentage points, not relative percentages. Overlays share a vertical scale per metric and require the same engine version and identical time labels. No history is persisted: only one pinned A and current B exist in local page state, and navigation discards them. Failed runs do not create B or retain stale current charts; the explicitly pinned successful A remains available for a later retry. Clear A to remove the comparison. The API does not expose a configuration hash, so aligned engine versions do not establish that assumptions stayed unchanged across backend deployments.

Run the mandatory gate (`npm run verify`) against a fresh running Vite server. It includes frontend unit/integration tests, TypeScript checking, build, Python regressions, diff checks and the real upstream API smoke test. Manual browser review must additionally inspect keyboard/hover values, threshold labels, two successful comparisons, responsive charts and an actual Assessment submission; mocked fixture tests do not count as live AWS or browser verification. Full neighbourhood before/after visualization, battery sizing and dispatch remain out of scope.


## M15 local battery simulation

The optional Battery Storage section accepts stored energy (kWh), grid-side power (kW), initial SOC, and optional SOC bounds/directional efficiencies. Enable it to send `bess_override`; disable it to send the original request unchanged. Defaults come from API assumptions/backend config, never invented UI results. SOC/dispatch charts use actual returned series. Pin a no-battery result as A and run a battery result as B for grid comparisons. Battery chart overlays are available only when both scenarios contain the relevant series.

The AWS deployment has not been updated for M15. To exercise the new feature end-to-end locally, from the repository root:

```bash
.venv/bin/python scripts/serve_local_api.py
```

In another terminal:

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

The local standard-library server binds to localhost and invokes the existing Lambda adapter, shared config and engine. Its explicit local CORS allowlist covers localhost:5173 and localhost:5174; it does not change AWS CORS or infrastructure. For another approved development origin, set GRIDMIND_ALLOWED_ORIGINS explicitly. Direct local requests bypass the AWS development proxy. Restart Vite to change environments. The original `npm run smoke:api` checks the configured proxy/older API and is **not evidence that deployed BESS works**.

Peak shaving is a fixed nominal real-power target derived from configured loading percentage, transformer rating and base power factor. Recharge is confined to the configured overnight window; finite energy and losses may leave constraints unresolved. Initial energy is a user assumption, final SOC need not equal it. The dispatch schedule is computed once, then replayed solely for the engine's thermal warmup convention. See the M15 contract section for the exact energy ledger and returned metrics. No sizing optimizer, financial comparison, neighbourhood placement remedies or M16 controls are implemented.


## M16 simulated Dispatch Monitoring

After a successful Assessment run, the Dispatch Monitoring panel can load an independent replay of that scenario. Enter an explicit UTC ISO timestamp, click **Load simulated replay**, then **Evaluate next sample**. The panel shows source/model identity, end-of-step timestamps, loading, voltage, hot-spot, battery SOC, engineering alert codes, reasons, advisory charge/discharge/idle and progress. Without battery or required data it idles; missing endpoints produce an honest error. Requests are cancelled on unmount; a mismatched dispatch-response timestamp is rejected. There is no automatic polling, hardware integration or publishing.

Use the M15 local HTTP adapter and direct local frontend API configuration for these new endpoints:

```bash
# Repository root
.venv/bin/python scripts/serve_local_api.py
# Another terminal
cd frontend
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

The existing typed API client adds only replay/evaluation methods and guards. The backend uses the same simulation and BESS functions, configured limits, SOC bounds, efficiency and freshness setting. UTC timestamps describe a simulated timeline; stale/future/out-of-order input is rejected relative to caller-supplied now/previous_timestamp. This stateless demonstration is not a secure real-device ingestion service. High voltage and critical hot-spot interlock to idle. Charging additionally passes a shared power-flow headroom check under documented modeled reactive-demand assumptions. One-step predictions are not guaranteed future grid/thermal compliance.

Replay advances manually and does not apply recommendations to future records. A depleted/missing battery never causes fabricated charge/discharge data. Frontend component tests use locally generated fixtures; local API tests verify real serialization. Keep the mandatory frontend gate and distinguish the older AWS smoke from local M16 checks. AWS deployment, broker/database services, real IoT commands and M17/M18 remain excluded.

### M17 resilience and explicit snapshots

Run from the repository root:

```sh
.venv/bin/python scripts/precompute.py
.venv/bin/python scripts/precompute.py --verify
# Deliberately refresh the timestamp when publishing a new generation:
.venv/bin/python scripts/precompute.py --generated-at 2026-10-11T00:00:00Z
```

The generator calls the shared engine, records source/config SHA-256 provenance, and keeps the previous generation timestamp unless explicitly replaced. Verification reruns all three scenarios and compares the entire artifact byte-for-byte. Vite serves the committed artifact at `/precomputed/scenarios.json`; it contains illustrative configured results, not measurements. Assessment offers explicit snapshot inspection even when scenarios or simulation services fail. Snapshot charts reuse the existing visualization, without assuming current backend thresholds. Dispatch monitoring remains a live/local workflow, not replayed automatically from a fallback snapshot.

Only exact full inputs plus matching engine and model/config fingerprint support equivalence lookup. Since AWS health does not expose the complete fingerprint, no deployed-model equivalence is claimed. New scenarios and battery overrides still require a live/local engine. No automatic result replacement occurs. Metadata GETs retry once for 429/5xx with a short bounded Retry-After wait and a single overall timeout; POST submissions never automatically retry. The synchronous submission guard prevents duplicate clicks. Existing mandatory frontend/Python/type/build/proxy checks remain applicable. Browser testing is still manual; snapshot availability requires the frontend static assets to be accessible, not a service worker or guaranteed offline application.

### M18 production release

Production builds require an explicit absolute HTTPS `VITE_API_BASE_URL`; `/api` is only the development proxy and is now rejected at build time. Example: `VITE_API_BASE_URL=https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com npm run build`. This existing public URL does not prove the latest battery/dispatch implementation is deployed. Rebuild after a reviewed endpoint change and configure the exact deployed frontend origin through Lambda's allowlist. No wildcard CORS or browser credentials are introduced. See [release commands, verification and rollback](../docs/release-readiness.md). `npm run verify` requires this production variable and a running, configured Vite server for its proxy smoke step. Human browser review and cloud deployment approval remain separate gates.

### Product workspace redesign

The interface uses one dark navy theme with teal/cyan for navigation and primary data, amber for constraint attention, and distinct A/B overlays. Typography uses the local system stack; no external font download, charting framework or dependency was added. Reduced-motion preferences disable nonessential transitions. All visible network/configuration metrics still come from the API. Overview's conceptual asset inventory links to the selected transformer; it does not draw feeder edges or geographical routes. Selecting equipment does not silently alter the separate single-transformer physics scenario.

Assessment is a guided demand → optional battery → simulation → exploration/comparison workflow. Core battery inputs stay visible while operating limits are disclosed on demand. Existing synchronized 96-step inspection and accessible sample tables remain; smaller screens scroll charts to preserve legible axes. Signed comparisons label direction without treating a voltage shift as automatically beneficial. Snapshot provenance and absence of deployed-model equivalence remain explicit. Advisory dispatch is visually separate from hardware control. The older AWS deployment may not provide battery/replay routes; use the local adapter to exercise the entire journey.

Planning now calls the already implemented `POST /v2/plan`; it does not reproduce scoring or electrical calculations. The frontend validates every displayed field, request-target correspondence and errors before showing recommendations. It distinguishes allocation feasibility from whole-neighbourhood compliance, displays actual site reasons, cost assumptions and existing-to-plan electrical comparisons, and labels the uncontrolled benchmark as modelled. The test plan fixture is a display-field projection of a result generated by the real engine, never a live fallback.

Local full-feature preview (two terminals from the repository root):

```sh
.venv/bin/python scripts/serve_local_api.py
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev -- --port 5174 --strictPort
```

Open `http://localhost:5174`. Production build still requires the explicit reviewed HTTPS API base. Run the established test/type/build/proxy gate and manually review Overview, Network, Assessment, Planning, mobile navigation, keyboard chart inspection, BESS, replay and explicit fallback before publishing. No deployment or API physics change is part of this redesign.

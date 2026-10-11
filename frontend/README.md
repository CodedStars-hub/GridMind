# GridMind frontend — M12 foundation

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
- `src/types/api.ts`: types for the four consumed operations derived from contract §§2–4 and 13. No unsupported endpoint or response fields. Neighborhood impact/hosting/planning types are deferred until their UI is implemented.
- `src/api/`: finite-value and shape checks at the untrusted response boundary, AbortController timeout/cancellation, structured server errors and no credentialed requests. The default request timeout is a transport setting, not a physics parameter. There are no automatic retries, caches or fabricated fallback results.
- Simulation inputs and defaults come from `/v2/scenarios`. Display values come from successful `/v2/simulate` responses; the browser performs no physics. Errors clear prior results. While editing a completed scenario, the result remains explicitly labeled with the last submitted inputs.
- `src/test/`: mocked transport and component/navigation tests. JSON fixtures were captured from the unchanged local backend (default simulation plus network/scenarios). They are **test-only** and are never imported by application pages or used as fallback data. Tests check failure states and cancellation as well as success.

A healthy health endpoint means the application loaded configuration; it is not proof every backend operation works or real telemetry exists. Network errors are reported separately. Aging and economic metrics are modeled estimates, not transformer failure dates or confirmed household damage. Advanced charts and before/after storytelling belong to later milestones; no placeholder charts represent fake results.

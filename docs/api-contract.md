# GridMind API Contract (v3)

Single source of truth for request and response shapes. Engine, Lambda and frontend must all match this file. If a field changes, change this file first.

> Planning-grade neighbourhood planning with the unchanged single-transformer model. Values marked TBD are not final.

## 1. Conventions

| Topic | Rule |
|---|---|
| Format | JSON, UTF-8 |
| Time axis | 96 strings `"HH:MM"`, from `"00:00"` to `"23:45"`, 15-minute steps. Index 0 = `"00:00"`, index 95 = `"23:45"` |
| Voltage | per unit (p.u.) |
| Temperature | degrees Celsius (°C) |
| Power | kW |
| Loading | percent of rated CURRENT (equal to kVA loading at rated voltage) |
| Money | INR, integers |
| Numbers | Never `NaN` or `Infinity` anywhere in any response |
| Nullable | A field marked "nullable" is present but may be `null`. No field is ever omitted |

## 2. Request enums (the finite input space)

| Field | Type | Unit | Nullable | Allowed values |
|---|---|---|---|---|
| `ev_kw` | integer | kW | no | `10`, `30`, `50`, `100` |
| `pv_kwp` | integer | kWp | no | `0`, `10`, `20`, `30` |
| `day_type` | string | enum | no | `"summer_weekday"`, `"winter_weekday"`, `"weekend"` |
| `load_level` | string | enum | no | `"moderate"`, `"heavy"`, `"critical"` |
| `bess` | string | enum | no | `"off"`, `"auto"` (used for legacy single-transformer keys) |
| `bess_override` | object or null | none | yes | Optional, `/simulate` only. `{ "power_kw": number, "energy_kwh": number }`. Default `null` |

The four scenario fields are required for `/simulate`; the shared validator defaults optional `bess` to `off` and `bess_override` to null. These enums describe the legacy single-transformer request only. New neighbourhood request shapes are defined in section 3; unknown request fields are rejected.

Any other value is rejected with `invalid_input` and the offending field name.

## 3. Routes

This is the v3 design contract; M5 adds data and documentation, not handlers. The existing M4 adapter still implements only GET /scenarios and POST /simulate. Other routes remain unavailable until their implementation milestones. POST /optimize is superseded by POST /plan; the v3 dispatch request replaces the legacy dispatch request.

All successful routes return HTTP 200. Paths accept one optional leading `/api` segment and a trailing slash. Responses use `Content-Type: application/json` and `Cache-Control: no-store`. The decoded UTF-8 body limit remains 2048 bytes. Error codes and HTTP statuses remain those in section 5; internal errors use the fixed public message `internal error`.

Single-transformer request validation remains unchanged: exact integer EV/PV choices (not bool or float), exact string choices from scenarios config, and finite positive override power/energy numbers (not bool), without upper bounds yet. Battery simulation returns 400 invalid_input with field bess until M8. `/scenarios` assumptions cover transformer, limits, costs, bess and load_levels parameters only, excluding scenarios and profiles.

The common legacy scenario is `{ "ev_kw": 50, "pv_kwp": 30, "day_type": "summer_weekday", "load_level": "heavy" }`. New request objects below are exact: required fields may not be omitted and unknown fields are rejected. Nullability applies to present fields; all numbers must be finite.

### 3.1 GET /scenarios

| Item | Value |
|---|---|
| Request body | none |
| Errors | `method_not_allowed`, `internal_error` |

Success response:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `engine_version` | string | no | e.g. `"0.1.0"` |
| `enums` | object | no | `ev_kw`, `pv_kwp`, `day_type`, `load_level`, `bess`: each a list of allowed values (section 2) |
| `defaults` | object | no | One default per scenario field: `ev_kw`, `pv_kwp`, `day_type`, `load_level`, `bess` |
| `assumptions` | list of objects | no | One entry per config parameter, see below |

`enums` contains the five keys in section 2, with arrays of their listed integer or string values. `defaults` contains those same keys with single values of the corresponding types. Both objects and all their members are non-null; units match section 2. Default values come from `config/scenarios.json`.

`assumptions[]` item:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `name` | string | no | EXACT config key, e.g. `voltage_min_pu`; the UI looks limits up by this name |
| `value` | number, string, boolean, object, list or null | yes | `null` means TBD |
| `unit` | string | no | Unit from the config parameter |
| `note` | string | no | Non-empty source and/or assumption text from config |

The `name` is the EXACT config key, not a display label. The frontend reads chart limit lines from this list by `name`. Limits are never hard-coded in the UI.

### 3.2 POST /simulate

| Item | Value |
|---|---|
| Request body | Scenario (above) plus optional `bess_override` (default `null`). `bess` is not sent; it is implied `"off"` |
| Success response | Simulation result object (section 4) |
| Errors | `invalid_input`, `method_not_allowed`, `convergence_failed`, `internal_error` |

The override members `power_kw` and `energy_kwh` are required, non-null finite positive numbers, in kW and kWh respectively. Override requests run live and bypass precomputed results because the key does not encode custom sizing.

With `bess_override = null`, `series.bess_*` are `null`, and `bess` and `cost` are `null`.

### 3.3 POST /optimize (superseded)

Superseded by POST /plan. No v3 request or success shape is assigned to /optimize; the current adapter returns 404 not_found, `route not available yet`. The legacy auto key format is retained in section 6.

### 3.4 GET /network

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `meta` | object | none | no | Neighbourhood route meta defined in section 3.5 |
| `neighbourhood` | object | none | no | Name and diagram dimensions |
| `neighbourhood.name` | string | none | no | neighbourhood_name from config |
| `neighbourhood.map` | object | none | no | Map coordinate extent |
| `neighbourhood.map.width` | integer | map units | no | 100 |
| `neighbourhood.map.height` | integer | map units | no | 100 |
| `transformers` | array of objects | none | no | Transformer entries below |
| `sites` | array of objects | none | no | Candidate site entries below |
| `defaults` | object | none | no | Planning defaults |
| `defaults.target_kw` | integer | kW | no | target_kw_default |
| `defaults.month` | object | none | no | Illustrative summer month |
| `defaults.month.weekday_count` | integer | days | no | month_weekday_count |
| `defaults.month.weekend_count` | integer | days | no | month_weekend_count |
| `enums` | object | none | no | Available targets |
| `enums.target_kw` | array of integers | kW | no | target_kw_options |
| `assumptions` | array of objects | none | no | Exact config keys with value/unit/note; item schema below |

Network transformer item

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `id` | string | identifier | no | Unique transformer id |
| `name` | string | none | no | Display name |
| `archetype` | string | enum | no | residential, commercial, mixed |
| `load_level` | string | enum | no | Load level from config/load_levels.json |
| `ev_usage` | string | enum | no | evening or daytime |
| `connections` | integer | customers | no | Existing customer connections |
| `rated_kva` | number | kVA | no | Shared transformer rated_kva |
| `x` | number | map units | no | Coordinate within 0..100 |
| `y` | number | map units | no | Coordinate within 0..100 |

Network site item

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `id` | string | identifier | no | Unique site id |
| `name` | string | none | no | Display name |
| `transformer_id` | string | identifier | no | Existing transformer id |
| `footfall_score` | integer | score | no | 1..10 |
| `max_kw` | integer | kW | no | Site rating ceiling |
| `x` | number | map units | no | Coordinate within 0..100 |
| `y` | number | map units | no | Coordinate within 0..100 |

Network assumption item

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `name` | string | config key | no | Exact unique config parameter name |
| `value` | JSON value | as indicated by unit | yes | Includes null for TBD |
| `unit` | string | none | no | Config unit |
| `note` | string | none | no | Non-empty source and/or assumption text |

Network assumptions cover neighbourhood, transformer, limits, costs, bess and load_levels parameters, without profile arrays or scenarios enums. This wider scope does not change GET /scenarios. GET /network has no request body.

### 3.5 Neighbourhood route meta

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `engine_version` | string | none | no | Engine package version; independent of contract v3 |
| `source` | string | enum | no | live or cached |
| `inputs` | object | none | no | Exact normalized request body; empty object for GET /network |

This meta belongs to /network, /assess, /plan and /dispatch. Nested single-transformer simulation meta remains exactly section 4. Neighbourhood charging totals need not match the legacy ev_kw enums; M7 nested simulation meta uses the same six input keys: ev_kw is the sum of allocated site ratings (not necessarily a legacy enum), pv_kwp is zero because the neighbourhood defines no PV installation, day_type and load_level identify the branch scenario, bess is off and bess_override is null. Managed charging is described by the outer meta.inputs.allocation; series.ev_kw is the actual served load. Legacy /simulate validation and echoes are unchanged.

### 3.6 Allocation

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `site_id` | string | identifier | no | Existing network site id |
| `kw` | integer | kW | no | Non-negative multiple of allocation_block_kw, no more than site max_kw |
| `managed` | boolean | none | no | Whether managed charging applies |
| `cap_fraction` | number | fraction | yes | Null when unmanaged; configured managed_cap_fractions entry when managed |

An allocation is an array of these objects, at most one per site. Omitted sites receive zero charging. Transformer EV load is the sum of the served site profiles attached to it. Empty allocation is valid. Battery and upgrade remedy effects belong to the planning assessment, not extra allocation fields.

### 3.7 POST /assess

M7 engine assessment implements both representative days and the unchanged simulation shape. `month` and `household` are null until M8; `hosting` is null until M9. Totals dependent on those features (`life_consumed_days_per_month`, `depreciation_inr_per_month`, `connections_affected`, `customer_hours_per_month`, `worst_min_voltage_v`) are present as null, never fabricated zeros. Their tables below describe later populated values. No HTTP handler is added in M7.

The current configuration explicitly assigns the shared transformer.json nameplate and electrical parameters to every branch; profiles, load levels, site loads and thermal states remain branch-specific. No individual equipment overrides are defined. Voltage profiles retain transformer_id association; these branches are not a coupled multi-node feeder.

Served peak and energy are computed from full-precision served site powers on aligned weekday steps, then rounded to four decimals. `served_kw_peak` is charging-only coincident peak, not total neighbourhood demand or a sum of separate transformer peaks. Aging is reported separately for every transformer/day and is not averaged. Managed allocations apply the supplied cap and redistribution only; M7 does not select caps or enforce a planner feasibility verdict.

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `request.allocation` | allocation array | none | no | Only required request member |
| `meta` | object | none | no | Neighbourhood route meta |
| `assessment` | object | none | no | Assessment below |
| `assessment.transformers` | array of T objects | none | no | One entry per neighbourhood transformer |
| `assessment.totals` | object | none | no | Totals below |

Transformer assessment T

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `transformer_id` | string | identifier | no | Network transformer id |
| `existing_peak_kw` | number | kW | no | Base peak from own archetype and load level |
| `new_charging_kw` | number | kW | no | Sum of allocated kW on its sites |
| `status` | string | enum | no | healthy, watch, overloaded |
| `simulation` | object | none | no | Full unchanged section 4 result for summer_weekday |
| `weekend_summary` | object | none | no | Exactly section 4.3 summary for weekend |
| `month` | object or null | none | yes | Monthly projection below |
| `household` | object or null | none | yes | Household indicators below |
| `hosting` | object or null | none | yes | Capacity estimates below |

Classify each day as overloaded if any hotspot_critical alert exists or peak_loading_pct exceeds the configured loading_info_pct (currently 100); otherwise watch if any other warning-severity alert exists; otherwise healthy. T.status is the worse of summer_weekday and weekend, ordered healthy < watch < overloaded. The simulation verdict is preserved and is distinct from this neighbourhood status.

Monthly projection

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `weekday_count` | integer | days | no | Configured weekday count |
| `weekend_count` | integer | days | no | Configured weekend count |
| `equivalent_aging_hours` | number | h/month | no | weekday_count × daily weekday aging + weekend_count × daily weekend aging |
| `life_consumed_days` | number | equivalent life days/month | no | equivalent_aging_hours / 24 |
| `calendar_days` | integer | days/month | no | weekday_count + weekend_count |
| `aging_ratio` | number | ratio | no | life_consumed_days / calendar_days |
| `life_consumed_years` | number | equivalent life years/month | no | equivalent_aging_hours / 8760 |
| `depreciation_inr` | integer | INR/month | no | transformer_upgrade_cost_inr × equivalent_aging_hours / normal_insulation_life_hours; rounded to INR |
| `life_expectancy_years` | number | years | no | Engine life estimate at monthly average daily equivalent aging, with configured cap |

A weekday is summer_weekday and a weekend uses the summer-weather weekend profiles. Project repeated representative days; do not interpret the month as a measured forecast. Depreciation is the share of transformer value consumed by modelled insulation aging, not a failure prediction.

Household indicators

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `connections` | integer | customers | no | Transformer customer count |
| `nominal_voltage_v` | number | V | no | nominal_home_voltage_v |
| `min_voltage_v` | number | V | no | simulation.summary.min_voltage_pu × nominal_voltage_v |
| `hours_below_limit` | number | h/weekday | no | Count of strict voltage-low steps × step_minutes / 60 |
| `customer_hours_per_day` | number | customer-h/weekday | no | connections × hours_below_limit |
| `customer_hours_per_month` | number | customer-h/month | no | connections × (weekday_count × weekday low-voltage hours + weekend_count × weekend low-voltage hours) |
| `heater_output_pct_at_min` | number | % of nominal output | no | 100 × V² |
| `motor_start_torque_pct_at_min` | number | % of nominal torque | no | 100 × V² |
| `motor_run_current_increase_pct_at_min` | number | % increase | no | 100 × (1/V − 1), constant-power motor |

V is the weekday minimum voltage in per unit. These three appliance indicators are indicative engineering rules of thumb, not measured appliance behaviour. A negative current increase indicates a modelled decrease above nominal voltage. Weekend voltage-low duration is calculated during assessment even though only its summary is returned.

Hosting capacity

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `unmanaged_kw` | integer | kW | no | Largest uncontrolled charging level healthy on both day types |
| `managed_kw` | integer | kW | no | Largest managed level healthy on both day types using the best configured cap fraction |

Search in allocation_block_kw steps, from zero through hosting_search_max_kw, using each transformer's own load level, base archetype and ev_usage profile. Hosting is additional charging against existing base load, not spare capacity after the submitted allocation. Return zero if no positive candidate is healthy; managed candidates must also retain the configured minimum served energy percentage. Choose the cap yielding largest healthy capacity, breaking ties by highest served energy then highest cap fraction.

Assessment totals

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `life_consumed_days_per_month` | number or null | equivalent life days/month | yes | Sum of transformer month.life_consumed_days |
| `depreciation_inr_per_month` | integer or null | INR/month | yes | Sum of transformer month.depreciation_inr |
| `transformers_in_violation` | integer | transformers | no | Count with status watch or overloaded |
| `connections_affected` | integer or null | customers | yes | Sum connections for transformers with any voltage_low alert on either day |
| `customer_hours_per_month` | number or null | customer-h/month | yes | Sum of household monthly exposures |
| `worst_min_voltage_v` | number or null | V | yes | Lowest minimum on either day across transformers, scaled to nominal household volts |
| `worst_hotspot_c` | number | °C | no | Highest hot-spot on either day across transformers |
| `served_kw_peak` | number | kW | no | Peak of the simultaneous served charging sum over sites on the representative weekday |
| `served_energy_kwh_per_day` | number | kWh/weekday | no | Sum of served site charging samples × step_minutes / 60 on summer_weekday |

### 3.8 POST /plan

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `request.target_kw` | integer | kW | no | Only required request member; from target_kw_options |
| `meta` | object | none | no | Neighbourhood route meta |
| `baseline` | object | none | no | Unplanned case below |
| `plan` | object | none | no | Planned allocation and remedies below |
| `comparison` | object | none | no | Comparison below |

Baseline

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `description` | string | none | no | Exact label: Unplanned installation (modelled) |
| `allocation` | allocation array | none | no | Fill sites by descending footfall_score, each up to max_kw until target is met; unmanaged with cap_fraction null |
| `assessment` | object | none | no | Full assessment as section 3.7 |

The baseline is MODELLED and every UI must label it **Unplanned installation (modelled)**. Equal footfall scores resolve by site_id ascending. Allocations obey block size and never exceed target.

Plan

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `allocation` | allocation array | none | no | Selected charging placements |
| `assessment` | object | none | no | Full assessment under the selected remedies |
| `remedies` | array of objects | none | no | Remedy items below |
| `unplaced_kw` | integer | kW | no | target_kw minus sum of selected allocation.kw |
| `cost` | object | none | no | Cost components below |

Remedy item

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `site_id` | string | identifier | no | Affected site |
| `transformer_id` | string | identifier | no | Attached transformer |
| `type` | string | enum | no | none, managed_charging, reallocate, battery, upgrade |
| `parameters` | object | none | no | Remedy settings; schema below |
| `cost_inr` | integer | INR | no | Cost charged to this remedy; zero for no action |
| `reason` | string | none | no | Plain-English rationale |
| `alternatives_considered` | array of objects | none | no | Alternatives below |

Remedy parameters by type

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `none` | empty object | none | no | No settings |
| `managed_charging` | object | none | no | cap_fraction: non-null number, fraction from config |
| `reallocate` | object | none | no | from_site_id and to_site_id: non-null strings; kw: non-null integer kW |
| `battery` | object | none | no | power_kw: non-null number kW; energy_kwh: non-null number kWh |
| `upgrade` | object | none | no | rated_kva: non-null positive number kVA; later milestone supplies engineering sizing |

Alternative considered

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `type` | string | enum | no | Same five remedy types |
| `feasible` | boolean | none | no | Healthy on both representative days and any required energy condition met |
| `cost_inr` | integer | INR | yes | Null if cost cannot be estimated yet |
| `reason` | string | none | no | Why accepted, rejected, or not evaluable |

Plan cost

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `controllers_inr` | integer | INR | no | Managed controller costs |
| `battery_inr` | integer | INR | no | Battery costs |
| `upgrade_inr` | integer | INR | no | Transformer upgrade costs |
| `connections_inr` | integer | INR | no | New connection costs; see TBD handling below |
| `total_inr` | integer | INR | no | Sum of the four components |

Shared transformer remedies are charged once, not once per attached site; repeated remedy entries carry zero incremental cost. Until new_connection_cost_inr_per_kw is supplied, connections_inr is an explicitly uncosted zero placeholder; reasons and UI must disclose exclusion, not imply a quoted free connection. An unpriced alternative has cost_inr null and cannot win the cheapest-feasible comparison.

Comparison

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `target_kw` | integer | kW | no | Requested target |
| `placed_kw_baseline` | integer | kW | no | Sum baseline allocation.kw |
| `placed_kw_plan` | integer | kW | no | Sum plan allocation.kw |
| `served_energy_kwh_per_day_baseline` | number | kWh/weekday | no | Baseline assessment total |
| `served_energy_kwh_per_day_plan` | number | kWh/weekday | no | Plan assessment total |
| `served_pct_of_baseline` | number | % | no | 100 × plan served energy / baseline served energy; zero if baseline energy is zero |
| `deltas` | object | mixed units | no | Plan minus baseline totals, defined below |
| `net` | object | none | no | Financial comparison below |

Comparison deltas (plan minus baseline)

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `life_consumed_days_per_month` | number | equivalent life days/month | no | Change in total modelled damage |
| `depreciation_inr_per_month` | integer | INR/month | no | Change in depreciation |
| `customer_hours_per_month` | number | customer-h/month | no | Change in exposure |
| `connections_affected` | integer | customers | no | Change in affected connections |
| `worst_min_voltage_v` | number | V | no | Change in worst minimum voltage; positive is improvement |
| `worst_hotspot_c` | number | °C | no | Change in worst temperature; negative is improvement |
| `transformers_in_violation` | integer | transformers | no | Change in violation count |

Comparison net

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `damage_avoided_inr_per_month` | integer | INR/month | no | Baseline depreciation minus plan depreciation; signed |
| `plan_cost_inr` | integer | INR | no | Plan total cost |
| `payback_months` | number | months | yes | plan_cost_inr / damage_avoided_inr_per_month; null if damage avoided is not positive |

Payback compares modelled depreciation avoided to the explicitly costed intervention; it is not guaranteed cash savings, avoided outages, or a failure prediction.

### 3.9 POST /dispatch (v3 replacement)

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `request.site_id` | string | identifier | no | Required existing site id; must occur in allocation |
| `request.allocation` | allocation array | none | no | Required site allocations |
| `meta` | object | none | no | Neighbourhood route meta |
| `payload` | object | none | no | Charger-cap event below |
| `published` | boolean | none | no | Whether publish succeeded |
| `publish_error` | string | none | yes | Null on success; failure reason otherwise |

Charger power-cap payload

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `event_id` | string | identifier | no | Unique event id |
| `mock` | boolean | none | no | Always true |
| `site_id` | string | identifier | no | Requested charging site |
| `event_start` | string | ISO 8601 timestamp | no | Offset-aware start |
| `event_end` | string | ISO 8601 timestamp | no | Exclusive end, one day later |
| `intervals` | array of objects | none | no | 96 ordered cap intervals |
| `baseline_kw` | array of numbers | kW | no | 96 uncontrolled samples: allocated kw × own ev_usage shape |
| `note` | string | none | no | Exact text: modelled on OpenADR 2.0b, not certified |

Dispatch interval

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `index` | integer | step | no | 0..95 |
| `start` | string | HH:MM | no | Step-start label |
| `duration_min` | integer | min | no | Configured step_minutes, currently 15 |
| `cap_kw` | number | kW | no | Non-negative charger power cap; no signed battery signal |

This replaces the old charge/discharge/idle battery event, not the simulation result object. Managed sites use the redistributed served profile as their cap schedule; unmanaged sites use baseline_kw. The site follows its transformer's ev_usage. A publish failure still returns the payload with published false and a non-null publish_error. Mock event date is chosen in the dispatch milestone.

### 3.10 Remedy ladder and managed charging

Try managed_charging first, then reallocate, then battery, then upgrade. Evaluate feasible candidates and select the cheapest known cost, using ladder order for equal-cost ties; the ladder does not mean accepting an expensive early candidate without comparing cheaper later candidates. Feasible means the transformer is healthy on BOTH summer_weekday and weekend; reallocation must keep source and destination healthy. Retain at least min_served_energy_pct_for_managed of each managed site's uncontrolled energy on each day type.

For each managed site, first cap its uncontrolled shape at cap_fraction × allocated kW. Redistribute excess energy into the overnight window from managed_offpeak_start_hour inclusive through midnight to managed_offpeak_end_hour exclusive, filling available room up to the same cap, earliest chronological daily step first. Never exceed the site cap or create extra energy. Energy that cannot fit is unserved. Sum served site profiles on each transformer. Evening uses ev_profile; daytime uses ev_daytime_profile. Residential uses base_load_profile, commercial uses base_load_commercial_profile, and mixed uses base_load_mixed_profile. Weekend uses summer PV and ambient weather. Existing limits, thermal equations, power factors and engine remain unchanged.

Battery and upgrade candidate sizing, bounds and costs need later engineering implementation; M5 supplies no new engineering values and no planner algorithm. Alternative reasons must state unpriced or unevaluable candidates honestly. Zero target shortfall does not imply full energy delivery: compare served energy as well as placed rating.

## 4. Simulation result object

All seven top-level fields are required: `meta`, `series`, `summary`, `alerts`, `verdict`, `bess`, and `cost`. Only `bess` and `cost` may be null; `alerts` is an array and all other fields are objects.

### 4.1 meta

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `inputs` | object | no | Normalized input echo: the four required scenario fields, resolved `bess` (`off` for simulate, `auto` for optimize, request value for dispatch), and `bess_override` (null unless supplied to simulate) |
| `engine_version` | string | no | |
| `source` | string | no | `"live"` or `"cached"` |

### 4.2 series (every array has exactly 96 entries)

M3b reports the second daily pass; series temperatures are at the end of each step, labelled by that step's start time. All output numbers are rounded to four decimals; summaries and alerts are derived from the rounded series.

| Field | Type | Unit | Nullable | Notes |
|---|---|---|---|---|
| `time` | list of string | `"HH:MM"` | no | |
| `ambient_c` | list of number | °C | no | |
| `base_kw` | list of number | kW | no | Existing load |
| `ev_kw` | list of number | kW | no | EV charging load |
| `pv_kw` | list of number | kW | no | PV generation (positive number) |
| `net_kw` | list of number | kW | no | Net load at the transformer after any BESS |
| `voltage_pu` | list of number | p.u. | no | |
| `loading_pct` | list of number | % | no | Percent of rated CURRENT: 100 times per-unit secondary current magnitude; equal to kVA loading at rated voltage |
| `top_oil_c` | list of number | °C | no | |
| `hotspot_c` | list of number | °C | no | |
| `aging_factor` | list of number | none | no | |
| `bess_kw` | list of number | kW | **yes** | `null` when no BESS. Positive = discharging, negative = charging |
| `bess_soc_pct` | list of number | % | **yes** | `null` when no BESS |

The UI builds the EV/solar timeline strip from `series.ev_kw` and `series.pv_kw`. Nullable BESS series are whole-array nulls without BESS; otherwise each contains 96 finite, non-null numbers. All other arrays contain 96 non-null entries.

### 4.3 summary

| Field | Type | Unit | Nullable |
|---|---|---|---|
| `min_voltage_pu` | number | p.u. | no |
| `min_voltage_time` | string `"HH:MM"` | | no |
| `peak_voltage_deviation_pu` | number | p.u. (largest absolute distance from 1.0) | no |
| `peak_hotspot_c` | number | °C | no |
| `peak_hotspot_time` | string `"HH:MM"` | | no |
| `peak_loading_pct` | number | % | no |
| `peak_loading_time` | string `"HH:MM"` | | no |
| `peak_aging_factor` | number | none | no |
| `daily_equivalent_aging_hours` | number | h per day | no |
| `insulation_life_years` | number | years | no (never null; capped at `insulation_life_cap_years` from limits config) |

Summary timestamps select the first occurrence when extrema tie.

### 4.4 alerts

Threshold crossings use strict comparisons; consecutive-step events never wrap across midnight. Hot-spot warning applies above its warning limit up to and including the critical limit; critical applies strictly above the critical limit, so crossings split events.

List (may be empty). Each item:

| Field | Type | Nullable | Allowed values / unit |
|---|---|---|---|
| `type` | string | no | `voltage_low`, `voltage_high`, `hotspot_warning`, `hotspot_critical`, `loading_over_100` |
| `severity` | string | no | `info`, `warning`, `critical` |
| `start` | string | no | `"HH:MM"` |
| `end` | string | no | `"HH:MM"` |
| `peak_value` | number | no | Worst value in the event |
| `unit` | string | no | `"p.u."`, `"°C"` or `"%"` |

Alert count = length of the list. `start` and `end` are inclusive first and last affected step labels; a one-step alert has identical labels. For voltage_low, peak_value is the lowest value; for other alert types it is the highest.

### 4.5 verdict

`violations_found` means warning or critical violations exist and no BESS analysis has been run; info alerts alone leave the M3b verdict `safe`.

| Field | Type | Nullable | Allowed values |
|---|---|---|---|
| `status` | string | no | `safe`, `violations_found`, `safe_with_bess`, `upgrade_recommended` |
| `message` | string | no | One human-readable line |

### 4.6 bess (nullable object)

`null` when there is no BESS. Otherwise:

| Field | Type | Unit | Nullable | Notes |
|---|---|---|---|---|
| `power_kw` | number | kW | no | Required battery power |
| `energy_kwh` | number | kWh | no | Required battery capacity |
| `feasible` | boolean | none | no | Whether constraints are satisfied |
| `schedule` | list | none | no | 96 items, defined below |

`schedule[]` item:

| Field | Type | Unit | Nullable | Notes |
|---|---|---|---|---|
| `index` | integer | none | no | 0-95 |
| `start` | string | HH:MM | no | Start on the time axis |
| `duration_min` | integer | min | no | 15 |
| `power_kw` | number | kW | no | Positive = discharge, negative = charge, zero = idle |

### 4.7 cost (nullable object)

`null` when there is no BESS. Otherwise:

| Field | Type | Unit | Nullable |
|---|---|---|---|
| `upgrade_cost_inr` | integer | INR | no |
| `bess_cost_inr` | integer | INR | no |
| `net_difference_inr` | integer | INR, signed. `upgrade_cost_inr - bess_cost_inr`, so negative means the BESS costs more | no |
| `insulation_life_years_before` | number | years | no |
| `insulation_life_years_after` | number | years | no |
| `note` | string | | no |

## 5. Error shape

```json
{ "error": { "code": "invalid_input", "message": "ev_kw must be one of 10, 30, 50, 100", "field": "ev_kw" } }
```

| Field | Type | Unit | Nullable | Notes |
|---|---|---|---|---|
| `error` | object | none | no | Contains the three fields below |
| `error.code` | string | enum | no | One code from the status table |
| `error.message` | string | none | no | Human-readable explanation |
| `error.field` | string | none | yes | Offending field; null for errors unrelated to one field |

| `code` | HTTP status |
|---|---|
| `invalid_input` | 400 |
| `not_found` | 404 |
| `method_not_allowed` | 405 |
| `convergence_failed` | 500 |
| `internal_error` | 500 |

## 6. Precompute key format

Key: `ev{ev_kw}_pv{pv_kwp}_{day_type}_{load_level}_{bess}` where `bess` is `off` or `auto`.

Worked examples:

- `ev50_pv30_summer_weekday_heavy_off`
- `ev100_pv0_winter_weekday_critical_auto`

Counts:

| Set | Count |
|---|---|
| No-BESS (`_off`) combinations: 4 x 4 x 3 x 3 | 144 |
| `_auto` entries | up to 144 more, only where violations exist |

S3 path pattern: `precomputed/<key>.json`

Route mapping: `/simulate` maps to `bess=off`. `/optimize` maps to `bess=auto`. Override simulations bypass this cache. Cached `auto` objects use the full `/optimize` response shape; cached `off` objects use the simulation result shape. If no violations exist, optimization may return `after=null`, `bess=null`, `cost=null`, and a `safe` verdict; no extra auto entry is required.

### 6.1 Neighbourhood cache artifacts

Retain the single-transformer key exactly: `ev{ev_kw}_pv{pv_kwp}_{day_type}_{load_level}_{bess}`. Its historical auto entries refer to the superseded optimizer, not /plan. Add `precomputed/network.json` for the full GET /network response and `precomputed/plan_target{target_kw}.json` for the full POST /plan response. The three target files are plan_target150.json, plan_target300.json and plan_target450.json; network.json is a separate fourth artifact. /assess and /dispatch do not share target-only cache keys. Changed neighbourhood assumptions require regenerating these artifacts; cached meta.source is cached. Error codes and the 2048-byte body limit are unchanged.

## 7. PRD output coverage

Legacy simulation outputs and v3 neighbourhood product outputs mapped to actual fields. Route-relative paths below use the /plan response unless another route is named.

| PRD output | Contract field(s) | Notes |
|---|---|---|
| Voltage chart | `series.time`, `series.voltage_pu` | Band lines from `/scenarios` `assumptions` (`voltage_min_pu`, `voltage_max_pu`) |
| Hot-spot chart | `series.time`, `series.hotspot_c` | 110/140 °C lines from `assumptions` (`hotspot_warning_c`, `hotspot_critical_c`) |
| Loading chart | `series.time`, `series.loading_pct` | 100 % line from `assumptions` (`loading_info_pct`) |
| BESS SOC chart | `series.time`, `series.bess_soc_pct` | `null` when no BESS |
| Alert panel: count | `alerts` (length of list) | Count is the list length |
| Alert panel: severity | `alerts[].severity` | Shown by icon and label, not colour alone |
| Alert panel: timestamps | `alerts[].start`, `alerts[].end` | Plus `type`, `peak_value`, `unit` |
| Peak voltage deviation | `summary.peak_voltage_deviation_pu` | Largest absolute distance from 1.0 p.u. |
| Min voltage and time | `summary.min_voltage_pu`, `summary.min_voltage_time` | Time is `"HH:MM"` |
| Peak hot-spot | `summary.peak_hotspot_c`, `summary.peak_hotspot_time` | In °C |
| Peak loading | `summary.peak_loading_pct`, `summary.peak_loading_time` | In % of rated kVA |
| Peak aging factor | `summary.peak_aging_factor` | Unitless |
| Daily aging and insulation life | `summary.daily_equivalent_aging_hours`, `summary.insulation_life_years` | Hours per day and years |
| Verdict line | `verdict.status`, `verdict.message` | One line for the banner |
| Required BESS kWh and kW | `bess.energy_kwh`, `bess.power_kw` | `null` block when no BESS |
| CapEx estimate | `cost.bess_cost_inr`, `cost.upgrade_cost_inr`, `cost.net_difference_inr` | INR integers; difference is signed |
| Insulation life with and without BESS | `cost.insulation_life_years_before`, `cost.insulation_life_years_after` | In years |
| EV and solar timeline strip | `series.ev_kw`, `series.pv_kw` | Windows are the non-zero steps |
| OpenADR JSON | `/dispatch` response `payload` | Mock payload, modelled on OpenADR 2.0b |
| CSV column: timestamp | `series.time` | `"HH:MM"` strings |
| CSV column: voltage | `series.voltage_pu` | In p.u. |
| CSV column: temperature | `series.hotspot_c` | Top-oil is also available as `series.top_oil_c` |
| CSV column: loading | `series.loading_pct` | In % of rated kVA |
| CSV column: BESS SOC | `series.bess_soc_pct` | `null` when no BESS |
| CSV column: aging (extra) | `series.aging_factor` | Extra column beyond the five PRD columns |
| Before/after damage | `baseline.assessment.totals.life_consumed_days_per_month; plan.assessment.totals.life_consumed_days_per_month` | Modelled equivalent life days |
| Life lost per month in days and years | `baseline.assessment.transformers[].month.life_consumed_days; plan.assessment.transformers[].month.life_consumed_years` | Both month fields exist on before and after T objects |
| Depreciation in rupees | `baseline.assessment.totals.depreciation_inr_per_month; plan.assessment.totals.depreciation_inr_per_month` | Share of transformer value consumed |
| Household volts | `plan.assessment.transformers[].household.nominal_voltage_v; plan.assessment.transformers[].household.min_voltage_v` | Nominal and minimum household volts |
| Household hours and customer-hours | `plan.assessment.transformers[].household.hours_below_limit; plan.assessment.transformers[].household.customer_hours_per_day; plan.assessment.transformers[].household.customer_hours_per_month` | Daily and monthly low-voltage exposure |
| Hosting capacity | `plan.assessment.transformers[].hosting.unmanaged_kw; plan.assessment.transformers[].hosting.managed_kw` | Healthy on both representative days |
| Remedies and reasons | `plan.remedies[].type; plan.remedies[].parameters; plan.remedies[].reason; plan.remedies[].alternatives_considered` | Costed intervention and rejected alternatives |
| 24h simulation series | `plan.assessment.transformers[].simulation.series` | Full unchanged section 4 series |
| Dispatch schedule | `POST /dispatch payload.intervals[].cap_kw; payload.baseline_kw` | 96 charger cap intervals |
| Neighbourhood map | `GET /network neighbourhood.map; transformers[].x; transformers[].y; sites[].x; sites[].y` | Diagram coordinates and dimensions |
| Allocation and unplaced target | `baseline.allocation; plan.allocation; plan.unplaced_kw` | Site ratings and remaining target |
| Served energy and percent | `comparison.served_energy_kwh_per_day_baseline; comparison.served_energy_kwh_per_day_plan; comparison.served_pct_of_baseline` | Representative weekday energy |
| Damage avoided and payback | `comparison.net.damage_avoided_inr_per_month; comparison.net.plan_cost_inr; comparison.net.payback_months` | Payback null when avoided damage is not positive |
| Appliance indicators | `plan.assessment.transformers[].household.heater_output_pct_at_min; plan.assessment.transformers[].household.motor_start_torque_pct_at_min; plan.assessment.transformers[].household.motor_run_current_increase_pct_at_min` | Indicative rules of thumb only |
| Affected connections and violation counts | `plan.assessment.totals.connections_affected; plan.assessment.totals.transformers_in_violation; comparison.deltas.connections_affected` | Counted customers and transformer statuses |

## 8. CSV export

One header row followed by 96 data rows, in this exact column order. A null SOC exports as an empty CSV cell.

| Column | Contract field | Type | Unit | Nullable |
|---|---|---|---|---|
| timestamp | `series.time` | string | HH:MM | no |
| voltage_pu | `series.voltage_pu` | number | p.u. | no |
| hotspot_c | `series.hotspot_c` | number | °C | no |
| loading_pct | `series.loading_pct` | number | % | no |
| bess_soc_pct | `series.bess_soc_pct` | number | % | yes |
| aging_factor | `series.aging_factor` | number | none | no |
## 9. Worked /plan JSON structure

Arrays are shortened to three values for readability; transformer assessment details are omitted here. Numeric values below illustrate types and nesting only and are not calculated outcomes. A production response includes all transformer assessments and full 96-step simulation arrays as specified above.

```json
{
  "meta": {"engine_version": "0.1.0", "source": "live", "inputs": {"target_kw": 300}},
  "baseline": {
    "description": "Unplanned installation (modelled)",
    "allocation": [
      {"site_id": "S1", "kw": 150, "managed": false, "cap_fraction": null},
      {"site_id": "S2", "kw": 120, "managed": false, "cap_fraction": null},
      {"site_id": "S4", "kw": 30, "managed": false, "cap_fraction": null}
    ],
    "assessment": {"transformers": [], "totals": {
      "life_consumed_days_per_month": 0, "depreciation_inr_per_month": 0,
      "transformers_in_violation": 0, "connections_affected": 0, "customer_hours_per_month": 0,
      "worst_min_voltage_v": 230, "worst_hotspot_c": 30, "served_kw_peak": 300, "served_energy_kwh_per_day": 300
    }}
  },
  "plan": {
    "allocation": [
      {"site_id": "S1", "kw": 150, "managed": true, "cap_fraction": 0.8},
      {"site_id": "S2", "kw": 120, "managed": false, "cap_fraction": null},
      {"site_id": "S4", "kw": 30, "managed": false, "cap_fraction": null}
    ],
    "assessment": {"transformers": [], "totals": {
      "life_consumed_days_per_month": 0, "depreciation_inr_per_month": 0,
      "transformers_in_violation": 0, "connections_affected": 0, "customer_hours_per_month": 0,
      "worst_min_voltage_v": 230, "worst_hotspot_c": 30, "served_kw_peak": 270, "served_energy_kwh_per_day": 300
    }},
    "remedies": [{"site_id": "S1", "transformer_id": "T4", "type": "managed_charging",
      "parameters": {"cap_fraction": 0.8}, "cost_inr": 50000,
      "reason": "Illustrative cap and redistribution; connection cost is uncosted until a quote is supplied.",
      "alternatives_considered": [
        {"type": "none", "feasible": false, "cost_inr": 0, "reason": "Illustrative rejected candidate."},
        {"type": "managed_charging", "feasible": true, "cost_inr": 50000, "reason": "Illustrative selected candidate."},
        {"type": "battery", "feasible": false, "cost_inr": null, "reason": "Sizing and full cost not evaluated in this structure example."}
      ]}],
    "unplaced_kw": 0,
    "cost": {"controllers_inr": 50000, "battery_inr": 0, "upgrade_inr": 0, "connections_inr": 0, "total_inr": 50000}
  },
  "comparison": {
    "target_kw": 300, "placed_kw_baseline": 300, "placed_kw_plan": 300,
    "served_energy_kwh_per_day_baseline": 300, "served_energy_kwh_per_day_plan": 300, "served_pct_of_baseline": 100,
    "deltas": {"life_consumed_days_per_month": 0, "depreciation_inr_per_month": 0,
      "customer_hours_per_month": 0, "connections_affected": 0, "worst_min_voltage_v": 0,
      "worst_hotspot_c": 0, "transformers_in_violation": 0},
    "net": {"damage_avoided_inr_per_month": 0, "plan_cost_inr": 50000, "payback_months": null}
  }
}
```

## 10. M8 engine impact comparison

`assess_impact(payload, config)` is an opt-in Python engine interface, not a new HTTP handler or route. Its request is exactly the section 3.7 allocation body. Existing `assess_network` and `/simulate` responses remain unchanged, including M7's null placeholders. M8 results live in the separate comparison below; hosting remains unimplemented.

Baseline means **existing neighbourhood demand without proposed EV charging**, represented by an empty allocation. EV means the submitted allocation, including its supplied managed caps. These are not the /plan “Unplanned installation (modelled)” baseline. Both scenarios use identical equipment, existing loads, weather, profiles, day weights and numerical settings. Baseline does not remove any separately modelled existing demand from the base load.

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `meta` | object | none | no | Section 3.5 meta; inputs is the submitted allocation body |
| `baseline` | object | none | no | Complete unchanged M7 response, with meta.inputs.allocation empty |
| `ev` | object | none | no | Complete unchanged M7 response for proposed allocation |
| `impact` | object | none | no | Comparison of unrounded records from those same engine runs |
| `impact.transformers` | array of objects | none | no | One impact item per configured transformer, in config order |
| `impact.totals` | object | mixed, below | no | Defined sums only; no sum of percentages or extrema |
| `assumptions` | array of objects | none | no | Section 3.1 name/value/unit/note items for reference life, calendar year, limits, valuation, day weights, nominal voltage, topology counts and timing |
| `limitations` | array of strings | none | no | Interpretation limits: modelled aging, illustrative valuation, connection-point proxy, unknown household counts and independent branches |

M8 integrates unrounded FAA and uses unrounded voltage/hot-spot values retained from the final daily pass. No physics is recomputed in an impact module. Existing chart-facing series, summaries and alerts still follow section 4 rounding. Small differences between impact exposure counts and legacy chart alerts can therefore occur near rounded thresholds. Impact values are rounded only at the response boundary: floating-point metrics to four decimals, INR to nearest integer using Python's ties-to-even rounding. Totals are calculated before rounding individual contributions, so rounded totals can differ slightly from sums of displayed values. Undefined percentage changes are null; signed additional values are never clamped.

Transformer impact item

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `transformer_id` | string | identifier | no | Same id in both scenarios and configured topology |
| `life` | object | none | no | Daily and monthly reference-equivalent aging comparison |
| `economic` | object | none | no | Illustrative monthly aging valuation |
| `household` | object | none | no | Potential exposure proxy, not appliance damage |

`life.days` has exactly summer_weekday and weekend keys, each with the following fields. `life.month` uses the monthly fields below.

| Daily field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `baseline_equivalent_aging_hours` | number | reference-equivalent h/day | no | Sum of baseline FAA × step_minutes / 60 |
| `ev_equivalent_aging_hours` | number | reference-equivalent h/day | no | Sum of EV FAA × step_minutes / 60 |
| `additional_equivalent_aging_hours` | number | reference-equivalent h/day, signed | no | EV minus baseline |
| `baseline_aging_ratio` | number | ratio | no | Baseline equivalent hours / simulated calendar hours |
| `ev_aging_ratio` | number | ratio | no | EV equivalent hours / simulated calendar hours |
| `aging_change_pct` | number | %, signed | yes | 100 × additional / baseline; null for zero baseline |
| `baseline_peak_hotspot_c` | number | °C | no | Maximum unrounded baseline hot-spot |
| `ev_peak_hotspot_c` | number | °C | no | Maximum unrounded EV hot-spot |
| `peak_hotspot_change_c` | number | °C, signed | no | EV peak minus baseline peak; no Celsius percentage ratio |

| Monthly field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `calendar_days` | integer | days/month | no | Configured weekday_count + weekend_count |
| `baseline_equivalent_aging_hours` | number | reference-equivalent h/month | no | Weekday count × baseline weekday hours + weekend count × baseline weekend hours |
| `ev_equivalent_aging_hours` | number | reference-equivalent h/month | no | Same weighting of EV results |
| `additional_equivalent_aging_hours` | number | reference-equivalent h/month, signed | no | EV minus baseline; repeated identical days reduce to daily difference × calendar_days |
| `baseline_reference_equivalent_years` | number | reference-equivalent years/month | no | Baseline equivalent hours / (calendar day hours × calendar_days_per_year) |
| `ev_reference_equivalent_years` | number | reference-equivalent years/month | no | Same conversion for EV |
| `additional_reference_equivalent_years` | number | reference-equivalent years/month, signed | no | Additional hours using that same conversion |
| `baseline_aging_ratio` | number | ratio | no | Baseline monthly equivalent hours / monthly calendar hours |
| `ev_aging_ratio` | number | ratio | no | EV monthly equivalent hours / monthly calendar hours |
| `aging_change_pct` | number | %, signed | yes | 100 × monthly additional hours / baseline hours; null for zero baseline |

Daily records must span a full calendar day. Calendar day duration follows configured step_minutes × steps_per_day; calendar_days_per_year is 365 in limits config, explicitly ignoring leap years. These are reference-equivalent aging quantities, not actual calendar service life lost, remaining life or failure dates.

Economic fields

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `replacement_value_inr` | integer | INR | no | Existing transformer_upgrade_cost_inr used as an explicit equipment valuation proxy, not a replacement quote |
| `reference_insulation_life_hours` | number | reference-equivalent h | no | normal_insulation_life_hours from limits config |
| `baseline_reference_life_fraction` | number | fraction | no | Baseline monthly equivalent hours / reference life |
| `ev_reference_life_fraction` | number | fraction | no | EV monthly equivalent hours / reference life |
| `additional_reference_life_fraction` | number | fraction, signed | no | Additional monthly equivalent hours / reference life |
| `baseline_aging_proxy_inr` | integer | INR/month | no | Baseline fraction × configured valuation |
| `ev_aging_proxy_inr` | integer | INR/month | no | EV fraction × configured valuation |
| `additional_aging_proxy_inr` | integer | INR/month, signed | no | Additional fraction × configured valuation |

Missing/null valuation or reference-life assumptions are rejected with ValueError naming the parameter; no monetary default is substituted. Values must be finite, valuation non-negative and reference life positive. Fractions are not capped at one. This proxy is not guaranteed replacement cost, maintenance spending, repair cost or real financial loss.

`household.baseline` and `household.ev` each contain summer_weekday and weekend exposure objects, plus a month object. Daily exposure objects:

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `min_voltage_pu` | number | p.u. | no | Modelled connection-point minimum |
| `min_voltage_v` | number | V | no | Minimum p.u. × configured nominal_home_voltage_v; household-voltage proxy |
| `violation_steps` | integer | samples | no | Strictly outside voltage_min_pu..voltage_max_pu |
| `violation_intervals` | integer | events | no | Runs of consecutive outside-limit samples; no midnight merging; adjacent low/high samples belong to one outside-limit run |
| `voltage_low_steps` | integer | samples | no | Voltage strictly below minimum |
| `voltage_high_steps` | integer | samples | no | Voltage strictly above maximum |
| `hours_outside_limits` | number | h/day | no | violation_steps × step_minutes / 60 |
| `hours_below_limit` | number | h/day | no | voltage_low_steps × step_minutes / 60 |
| `maximum_undervoltage_deviation_pu` | number | p.u. | no | Maximum shortfall below lower limit, or zero; not deviation from nominal |
| `outside_limits_pct` | number | % of simulated time | no | 100 × violation_steps / number of samples |
| `connections` | integer | customer connections | yes | Configured count; null if unavailable to pure comparison |
| `connections_potentially_exposed` | integer | customer connections | yes | Count once if this day has any outside-limit step; otherwise zero; null if count unknown |
| `connection_hours` | number | customer-h/day | yes | connections × hours_outside_limits; null if count unknown |
| `residential_connections_proxy` | integer | potential residential connections | yes | Customer count only for a residential archetype; not a measured household count |
| `residential_connections_potentially_exposed_proxy` | integer | potential residential connections | yes | Exposure count for residential archetypes; unknown for commercial/mixed or missing counts |
| `residential_connection_hours_proxy` | number | potential residential connection-h/day | yes | Exposure hours for residential archetypes; unknown otherwise |
| `proxy` | boolean | none | no | Always true; service drops and appliance susceptibility are not modelled |

Monthly exposure fields

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `hours_outside_limits` | number | h/month | no | Weighted weekday and weekend outside-limit hours |
| `connections_potentially_exposed` | integer | customer connections | yes | Count once if either representative day with nonzero monthly weight violates; never sum day counts |
| `connection_hours` | number | customer-h/month | yes | connections × monthly outside-limit hours |
| `residential_connections_potentially_exposed_proxy` | integer | potential residential connections | yes | Same count for residential archetypes only |
| `residential_connection_hours_proxy` | number | potential residential connection-h/month | yes | Same hours for residential archetypes only |

`household.additional_connection_hours_per_month` is number or null, unit customer-h/month, EV monthly connection-hours minus baseline; it is signed, and null if counts are unknown.

Counts represent disjoint transformer customer groups as an illustrative topology assumption. They are never multiplied by the number of charging sites, added once per violating interval, or counted separately for both day types. Residential proxy totals cover **residential archetypes only**, excluding unknown residential shares of commercial/mixed customers. Missing counts propagate null totals rather than partial sums. The pure comparison supports missing counts; the existing M7 simulation adapter still requires valid configured customer counts. Potential exposure establishes neither appliance damage nor failed households.

Neighbourhood impact totals

| Field | Type | Unit | Nullable | Meaning |
|---|---|---|---|---|
| `baseline_equivalent_aging_hours_per_month` | number | reference-equivalent transformer-h/month | no | Sum of individual asset aging hours |
| `ev_equivalent_aging_hours_per_month` | number | reference-equivalent transformer-h/month | no | Same sum for EV |
| `additional_equivalent_aging_hours_per_month` | number | reference-equivalent transformer-h/month, signed | no | Sum of individual additional hours |
| `baseline_reference_equivalent_years_per_month` | number | reference-equivalent transformer-years/month | no | Sum of individual baseline equivalents |
| `ev_reference_equivalent_years_per_month` | number | reference-equivalent transformer-years/month | no | Same sum for EV |
| `additional_reference_equivalent_years_per_month` | number | reference-equivalent transformer-years/month, signed | no | Sum of individual additional equivalents |
| `baseline_aging_proxy_inr_per_month` | integer | INR/month | no | Sum of unrounded baseline valuations, then round |
| `ev_aging_proxy_inr_per_month` | integer | INR/month | no | Same sum for EV |
| `additional_aging_proxy_inr_per_month` | integer | INR/month, signed | no | Sum of unrounded additional valuations, then round |
| `baseline_connections_potentially_exposed_per_month` | integer | customer connections | yes | Sum of unique transformer customer groups potentially exposed |
| `ev_connections_potentially_exposed_per_month` | integer | customer connections | yes | Same count for EV |
| `baseline_connection_hours_per_month` | number | customer-h/month | yes | Sum of baseline customer-hours |
| `ev_connection_hours_per_month` | number | customer-h/month | yes | Sum of EV customer-hours |
| `additional_connection_hours_per_month` | number | customer-h/month, signed | yes | EV minus baseline |
| `baseline_residential_connections_potentially_exposed_proxy_per_month` | integer | potential residential connections | yes | Residential-archetype subset only |
| `ev_residential_connections_potentially_exposed_proxy_per_month` | integer | potential residential connections | yes | Same subset for EV |
| `baseline_residential_connection_hours_proxy_per_month` | number | potential residential connection-h/month | yes | Residential-archetype subset only |
| `ev_residential_connection_hours_proxy_per_month` | number | potential residential connection-h/month | yes | Same subset for EV |

No aggregate percentage, averaged FAA, summed minimum voltage or predicted failure date is defined. Aggregate aging is explicitly a sum over separate assets, not the aging of one equivalent neighbourhood transformer. Invalid factors, timing, reference life, monetary assumptions, voltage limits, counts, identities or aligned series raise clear ValueError exceptions; allocation errors retain M7 InvalidInputError semantics.

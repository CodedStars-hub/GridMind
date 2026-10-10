# GridMind API Contract (v0.1.0)

Single source of truth for request and response shapes. Engine, Lambda and frontend must all match this file. If a field changes, change this file first.

> Planning-grade model of one transformer. Values marked TBD are not final.

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
| `bess` | string | enum | no | `"off"`, `"auto"` (used for precompute keys and `/dispatch`) |
| `bess_override` | object or null | none | yes | Optional, `/simulate` only. `{ "power_kw": number, "energy_kwh": number }`. Default `null` |

The four scenario fields are required; `bess` is required only on `/dispatch`. Only `bess_override` may be omitted, defaulting to null. Unknown request fields are rejected.

Any other value is rejected with `invalid_input` and the offending field name.

## 3. Routes

Common request body for the POST routes (the "scenario"):

```json
{ "ev_kw": 50, "pv_kwp": 30, "day_type": "summer_weekday", "load_level": "heavy" }
```

Successful routes return HTTP 200. All routes can return `not_found` for an unknown path, `method_not_allowed` for an unsupported method, or `internal_error` for an unexpected failure.

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

### 3.3 POST /optimize

| Item | Value |
|---|---|
| Request body | Scenario (above). `bess` is implied `"auto"` |
| Errors | `invalid_input`, `method_not_allowed`, `convergence_failed`, `internal_error` |

Success response:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `meta` | object | no | Same as simulation `meta` (section 4) |
| `before` | simulation result | no | No-BESS result |
| `after` | simulation result | yes | With-BESS result. `null` if no feasible BESS exists |
| `bess` | object | yes | Same shape as section 4 `bess`. `null` if none feasible |
| `cost` | object | yes | Same shape as section 4 `cost`. `null` if no BESS result |
| `verdict` | object | no | `{ status, message }`, same as section 4 `verdict` |

### 3.4 POST /dispatch

| Item | Value |
|---|---|
| Request body | Scenario (above) plus required `bess`: `"off"` or `"auto"`; no `bess_override` |
| Errors | `invalid_input`, `method_not_allowed`, `convergence_failed`, `internal_error` |

Success response:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `meta` | object | no | Same as simulation `meta` |
| `payload` | object | no | OpenADR-style payload (below) |
| `published` | boolean | no | `true` if the IoT publish succeeded |
| `publish_error` | string | yes | Reason if publish failed, else `null`. The payload is returned either way |

OpenADR-style payload:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `event_id` | string | no | Unique event id |
| `mock` | boolean | no | Always `true` |
| `event_start` | string | no | ISO 8601 timestamp |
| `event_end` | string | no | ISO 8601 timestamp; exclusive end |
| `intervals` | list | no | 96 items, see below |
| `baseline_kw` | list of 96 numbers | no | Net load without BESS, kW |
| `note` | string | no | States the payload is modelled on OpenADR 2.0b but is not certified |

`intervals[]` item:

| Field | Type | Unit | Nullable | Notes |
|---|---|---|---|---|
| `index` | integer | none | no | 0 to 95 |
| `start` | string | HH:MM | no | Start on the time axis |
| `duration_min` | integer | min | no | 15 |
| `signal_type` | string | enum | no | `charge`, `discharge`, `idle` |
| `power_kw` | number | kW | no | Positive = discharge, negative = charge, zero = idle |

Event timestamps include a UTC offset and span one 24-hour day. The mock calendar date is a design decision for M11. Dispatch with `bess=off` uses 96 idle intervals; `bess=auto` uses the optimized schedule, or idle intervals when no BESS is selected. Publish failures return HTTP 200 with `published=false` and a non-null `publish_error`; otherwise `publish_error=null`.

Unknown paths return `not_found` (404) from any route.

## 4. Simulation result object

All seven top-level fields are required: `meta`, `series`, `summary`, `alerts`, `verdict`, `bess`, and `cost`. Only `bess` and `cost` may be null; `alerts` is an array and all other fields are objects.

### 4.1 meta

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `inputs` | object | no | Normalized input echo: the four required scenario fields, resolved `bess` (`off` for simulate, `auto` for optimize, request value for dispatch), and `bess_override` (null unless supplied to simulate) |
| `engine_version` | string | no | |
| `source` | string | no | `"live"` or `"cached"` |

### 4.2 series (every array has exactly 96 entries)

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

| Field | Type | Nullable | Allowed values |
|---|---|---|---|
| `status` | string | no | `safe`, `safe_with_bess`, `upgrade_recommended` |
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

## 7. PRD output coverage

Every PRD v2.0 output (sections 8.5 and 11) mapped to a contract field.

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

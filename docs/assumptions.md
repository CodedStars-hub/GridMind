# Assumptions

> Planning-grade model of one transformer. Values marked TBD are not final.

## Topology
M2 uses one branch: ideal HV source at the configured fixed-tap voltage, then transformer series impedance, then one lumped LV feeder impedance, then ONE connection point for base load, the EV hub, solar and later battery. This balanced single-phase equivalent has no shunt branches; no-load loss does not enter its power-flow demand.

## Thermal model parameters
M1 uses these typical-value assumptions, not values from a specific nameplate:

| Parameter | Value | Unit | Basis |
|---|---|---|---|
| rated_top_oil_rise_c | 55 | degC | Typical-value assumption |
| rated_hotspot_rise_over_top_oil_c | 25 | degC | Typical-value assumption |
| loss_ratio | 5.0 | ratio | Typical-value assumption; rated load loss divided by no-load loss |
| oil_exponent | 0.8 | none | Typical-value assumption |
| winding_exponent | 0.8 | none | Typical-value assumption |
| oil_time_constant_min | 180 | min | Typical-value assumption |
| winding_time_constant_min | 5 | min | Typical-value assumption |
| reference_ambient_c | 30 | degC | Typical-value assumption |

Each value assumes a typical 65 C-rise ONAN distribution transformer: 80 C hot-spot rise plus 30 C ambient gives the 110 C reference. Verify against the nameplate or standard before real-world use; these values do not claim an IEEE citation.

Ultimate top-oil rise is the rated rise multiplied by the ratio of load-squared times loss ratio plus one to loss ratio plus one, raised to the oil exponent. Ultimate hot-spot rise over top-oil is the rated rise multiplied by per-unit load raised to twice the winding exponent. Each rise relaxes exactly toward its ultimate value: ultimate plus the old-minus-ultimate difference multiplied by the exponential of negative step duration divided by its time constant.

State stores only relative rises. Absolute top-oil is ambient plus oil rise; absolute hot-spot adds the winding rise. Time constants remain constant, and temperature-dependent oil viscosity is not modelled.

## Feeder impedance and voltage model
The per-unit base is the configured 250 kVA rating and 415 V LV voltage. Active kW and reactive kvar divide by rated kVA to give per-unit power. Transformer resistance is rated load loss divided by rated power in VA; impedance magnitude is short-circuit impedance percent divided by 100. Reactance is the square root of impedance magnitude squared minus resistance squared. An impedance smaller than resistance is invalid.

| Parameter | Value | Unit | Basis |
|---|---|---|---|
| impedance_voltage_pct | 4.5 | percent | Typical-value assumption; verify against nameplate |
| load_loss_w | 3000 | W | Typical-value assumption at rated current; verify against nameplate |
| no_load_loss_w | 600 | W | Typical-value assumption; load loss divided by no-load loss equals thermal loss_ratio 5.0 |
| feeder_resistance_pu | 0.024 | p.u. on a 250 kVA, 415 V base | Typical-value cable assumption |
| feeder_reactance_pu | 0.010 | p.u. on a 250 kVA, 415 V base | Typical-value cable assumption |
| powerflow_tolerance_pu | 1e-9 | p.u. | Numerical solver setting |
| powerflow_max_iterations | 50 | count | Numerical solver setting |

The feeder values assume roughly 100 m of 185 mm2 aluminium four-core LV cable using typical per-km values; replace with real feeder data. The supplied losses and impedance are typical-value assumptions, not a specific nameplate.

All connection-point powers are constant-power inputs. Active demand is base plus EV minus solar minus battery discharge; charging adds demand. Reactive demand comes from base and EV power factors. Starting at source voltage, fixed-point iteration calculates current as the conjugate of complex power divided by connection voltage, then subtracts total series impedance times current from source voltage. Convergence requires the voltage-change magnitude below the configured tolerance. Non-convergence, non-finite intermediates, or voltage below the named 0.1 p.u. numerical collapse guard raise a convergence failure.

Current is recomputed using the final voltage. Loading is 100 times secondary current magnitude in per unit: percent of rated CURRENT, equal to kVA loading at rated voltage. At a depressed voltage, constant apparent power draws higher current, so loading is not simply net kW divided by rated kVA.

## Power factors
M2 holds base load at 0.95 lagging, EV at 0.98 lagging, PV at 1.0 and battery at 1.0. These are typical-value, fixed design assumptions rather than measured values; verify for the installation. Only unity-power-factor PV is supported in the MVP. Base and EV reactive power is active power multiplied by the tangent of the arccosine of their power factor; PV and battery add no reactive power.

## Load profiles and calibration approach
M3a uses normalized base, EV and PV shapes, sampled every 15 minutes for 96 steps. The base and EV shapes peak at one. Base peaks are 55, 70 and 85 percent of rated kVA for moderate, heavy and critical, applied to real power in kW: for the 250 kVA unit these are 137.5, 175 and 212.5 kW. This is illustrative demo calibration of existing loading before the new EV hub, not measured feeder loading or a current-based loading result.

The EV profile is a stress-test case with full hub output during the evening window, including 18:00 through 21:00; the PRD describes a 6-10 PM peak. PV shapes include temperature, soiling and inverter derating, with maxima 0.80 in summer/weekend and 0.65 in winter. Their daylight span is roughly 7 AM to 6 PM, wider than the PRD 9 AM to 5 PM example.

Ambient is an illustrative Delhi day: summer 30-43 C within the PRD 30-45 C range, winter 7-21 C. Weekend uses summer PV and weather; weekday EV shapes are identical. All data are illustrative and replaceable by real feeder, charging, solar and weather measurements; calibration must use plausible inputs rather than target outcomes.

Regenerate the four profile JSON files with `python scripts/generate_profiles.py`. Only that standalone authoring tool holds the supplied anchor tables. It linearly interpolates the wrapping 0-to-24-hour anchors at quarter-hour samples, rounds to four decimals, and writes deterministic JSON; the engine reads only the JSON.

## Aging model
M1 computes aging acceleration as the exponential of the aging constant divided by reference kelvin, minus that constant divided by hot-spot Celsius plus 273. Config supplies the 15000 K constant and 383 K reference; the requested Celsius-to-kelvin convention uses 273. At the 110 C reference, the factor is one.

Equivalent aging hours sum each factor times the step duration in hours. Normal insulation life is 180000 h; divide by equivalent hours per day and then by 365 days per year to estimate years. The editable 100-year display cap comes from `insulation_life_cap_years` in limits config; zero or negative daily equivalent hours return the cap. This is a planning estimate, not a measured remaining-life prediction.

## BESS model
Will document dispatch rule, efficiency, SOC limits and sizing sweep. Filled in M8-M9.

## Cost assumptions
Will document the upgrade and battery cost assumptions and their editable ranges. Filled in M9.

## Known limitations
Will list what the model does not cover (single transformer, single phase equivalent, mock OpenADR). Filled in M14.
Engine code must stay compatible with Python 3.12. Do not use syntax or standard-library features newer than 3.12.

## Simulation procedure

M3b builds load series and parameters from loaded config. It solves the first step's power flow and initializes relative thermal rises at that current's steady state. It then carries thermal state through two full daily passes and reports only the second pass; the first pass warms up the state toward the repeating daily cycle. A separate three-pass test checks the residual drift rather than assuming exact periodic convergence.

Each step solves connection voltage and secondary current, uses current in per unit as thermal load K, advances relative rises with the exact thermal update, and computes aging from absolute hot-spot temperature. Load and ambient stay constant during the step. Reported temperatures are end-of-step values labelled by that step's start time.

Compute in full precision, round series to four decimals, then derive summaries and alerts from the rounded series. Summary extrema choose the first occurrence on ties. Daily equivalent aging is recomputed from rounded hot-spot temperatures; life is derived from that unrounded total before rounding both summary values.

Alert thresholds are strict: voltage below the minimum or above the maximum is warning; hot-spot above the warning threshold up to and including the critical threshold is warning; hot-spot above the critical threshold is critical; loading above its information threshold is info. Warning and critical hot-spot step sets are disjoint. Consecutive steps merge into inclusive events without crossing midnight, sorted by start step then type. Low-voltage events use their minimum voltage as peak; other events use their maximum.

Any warning or critical alert gives `violations_found`, meaning violations exist and no BESS analysis has been run. Otherwise the verdict is `safe`; info alerts alone do not change it. BESS is not simulated yet: automatic mode and overrides raise NotImplementedError until M8, and all BESS and cost result fields are null.

## Network assessment (M7)

Each configured transformer is assessed as an independent copy of the same single-branch electrical model, with separate thermal state. All six share the nameplate and feeder parameters explicitly assigned by neighbourhood.json; their archetype, load level, attached sites and charging usage select distinct input series. No shared upstream voltage interaction is modelled. No installed neighbourhood PV is specified, so its generation is zero; the legacy PV scenarios remain unchanged.

Assess summer_weekday and weekend, preserve the existing two-pass warm-up and four-decimal chart semantics, and classify the transformer by the worse day. Overloaded means critical hot-spot or loading above the configured rated-current information threshold; watch means another warning; otherwise healthy. Household exposure, monthly life/cost and hosting are not calculated in M7 and are explicitly null. Insulation aging is modelled acceleration, not measured remaining life; voltage alerts do not establish appliance damage.

Managed charging evaluates the requested configured cap: clip the site series, then fill off-peak headroom in chronological daily-index order. Any excess that cannot fit is unserved. It neither creates energy nor chooses an optimal cap. Peak served charging is the maximum simultaneous sum across sites, and energy integrates that sum using configured step duration.

## Life, economic and exposure comparison (M8)

The baseline is existing base demand with an empty proposed charging allocation; the EV scenario uses the supplied allocation. Equipment, day profiles and numerical procedure are identical. M8 retains unrounded final-pass series from the shared engine while preserving existing rounded simulation results. Monthly weighting uses neighbourhood month_weekday_count and month_weekend_count (currently 22 and 8).

Reference-equivalent aging integrates FAA × step-hours; aging ratio divides equivalent hours by calendar hours. Additional quantities are EV minus baseline, including negative differences. Reference-equivalent years divide hours by 24 calendar hours per day and the configured calendar_days_per_year (365, ignoring leap years). This is not measured calendar life lost or a failure-date forecast. Zero baseline makes percentage change unavailable, not zero percent.

The existing transformer_upgrade_cost_inr assumption (currently INR 550000) serves as an illustrative equipment valuation proxy, not a verified replacement quote. Economic aging proxy equals equivalent aging hours / normal_insulation_life_hours (currently 180000) × that value. No new cost coefficient, BESS comparison or real-loss claim is introduced. Totals sum unrounded asset contributions before presentation rounding.

Voltage is simulated at one connection point per transformer, not at individual homes. Potential customer exposure assumes the configured customer groups are disjoint and share that point's voltage as a proxy. Residential-archetype customer counts approximate residential connections only within that subset; commercial/mixed residential shares are unknown. Count a connection once across sites and representative days; weight exposure hours by day counts. Unknown counts remain unavailable in the pure comparison; M7 topology validation still rejects missing customer counts when running scenarios. There is no appliance damage, repair-cost or failure-count calculation.

## EV hosting capacity (M9)

Hosting evaluates additional proposed charging against existing demand, with no proposed EV in the baseline. It preserves each branch's archetype, load level, EV timing, ambient, fixed power factors, explicitly shared equipment and zero installed neighbourhood PV. An uncontrolled candidate in kW multiplies a normalized EV shape peaking at one, so it is the additional coincident peak, not daily kWh or transformer kVA. Site ceilings and installation placement are separate questions.

The configured 10 kW block and 300 kW bound define a discrete exhaustive search. The new hosting_max_evaluations setting is a numerical budget of 151 two-day candidate evaluations per transformer: one reused baseline plus 30 positive points for uncontrolled demand and for each of four managed caps. Increase that budget if changing the grid or cap list. No continuous maximum or global monotonicity is assumed; all grid points are inspected even after a failure.

Healthy hosting requires unrounded voltage within both configured limits, rated-current loading no higher than loading_info_pct and hot-spot no higher than hotspot_warning_c on summer_weekday and weekend. Equality is permitted. The higher critical hot-spot threshold adds diagnostics; there is no configured top-oil or aging operational threshold. Full-precision second-pass results drive feasibility; four-decimal displays may hide a tiny violation, so feasibility flags and violation keys are authoritative. The physics and thermal warm-up remain unchanged.

A violating baseline returns zero permissible additional capacity with explicit baseline violations and no feasible selected candidate. It requires remediation, not a claim that zero makes existing conditions safe. Failure to solve baseline propagates rather than fabricating compliance. A failed positive candidate is explicitly infeasible due to convergence_failed.

Managed searches evaluate only the existing configured cap fractions and M7 redistribution rule, retaining the configured minimum energy on each day. They do not choose sites, remedies or costs. The historical managed_kw field is the uncontrolled profile scale before capping; selected day additional_peak_kw exposes actual delivered peak. These quantities must not be interchanged. No new charger nameplate recommendation is made.

Independent transformer capacities can be summed only as independent branch headroom. That sum is not validated simultaneous network capacity: shared upstream feeder limits, transformer-to-transformer coupling, unbalance, household service drops and real interconnection requirements are outside this model. Capacities depend on illustrative scenario assumptions and require measured equipment/load data and a utility study before real-world approval.

## M10 placement and before/after assessment

Candidate sites and footfall are illustrative configuration, not measured traffic, land availability or permits. A missing requested demand defaults to the configured site max_kw; a missing eligibility flag means only that the site is a candidate. Demand attractiveness uses normalized footfall alone, with a configured positive relative weight and stable site-id ties. Commercial activity is represented by the transformer's load archetype, not an invented score.

The total target and individual requests are uncontrolled EV profile-scale kW. Managed sites cap and redistribute that profile using M7's existing night window; actual coincident power and delivered kWh are separate outputs. All sites on a transformer inherit its charging timing. Shared capacity is checked by summing their served time series, never assigning each site the transformer's entire M9 hosting capacity.

A bounded greedy search exhausts configured grid levels and managed modes for each site, keeping earlier placements fixed. Full-precision M9 limits must hold on both summer_weekday and weekend, and each managed site must retain the configured minimum energy on each day. Equality at an operating limit is allowed. Existing noncompliant branches receive no additional demand; their unchanged violations remain visible in the final network. This heuristic is deterministic, not globally optimal or an interconnection approval.

The existing-demand before case is separate from the contract's Unplanned installation (modelled) reference deployment. M8 computes existing-to-plan life and exposure impacts; reference-to-plan comparisons retain the established contract. Equivalent aging and its rupee valuation are illustrative proxies, not actual calendar life lost, appliance damage or guaranteed savings. Only configured controller costs and any supplied connection quote are included; missing connection costs remain explicitly excluded. Battery, upgrade, cross-site backtracking and financial-budget optimization are not implemented.

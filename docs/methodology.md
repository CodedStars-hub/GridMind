# GridMind methodology

Planning-grade model; this skeleton assigns the full explanations to M6.

## Overview

Explain the neighbourhood planning question, modelled baseline and shared single-transformer engine. Document in M6.

## Electrical model

Explain the existing M2 topology, per-unit bases, fixed power factors and current-based loading. Document in M6.

## Thermal model

Explain the existing M1 thermal assumptions, exact updates and daily warm-up procedure. Document in M6.

## Aging and life

Explain the existing M1 aging factor, normal insulation life and configurable display cap. Document in M6.

## Monthly projection

Explain representative weekday/weekend weighting, equivalent life consumed and depreciation. Document in M6.

## Household effects

Explain voltage exposure and indicative heater/motor rules, including their limits. Document in M6.

## Hosting capacity

M9 implements the configured discrete search and healthy-on-both-days criterion below. It does not calculate a continuous maximum or approve an interconnection.

## Placement and remedies

Explain the modelled footfall baseline, remedy ladder, feasibility and cost comparison. Document in M6; update as planner remedies are implemented.

## Data and assumptions

Explain illustrative topology, profile authoring, archetypes, charging usage and replacement with measured data. Document in M6.

## Limitations

Explain representative days, simplified equipment and appliance behaviour, missing quotes and uncertainty. Document in M6.

## References

List primary engineering references and distinguish supplied assumptions from verified sources. Document in M6.


## M7 assessment implementation

`assess_network(payload, config)` validates the allocation, selects residential/commercial/mixed base profiles and evening/daytime charging profiles, and aggregates site powers onto their configured transformer. Missing sites contribute zero charging. Configuration errors raise ValueError; malformed requests raise InvalidInputError naming the field; shared power-flow failures propagate without a partial assessment.

`simulate_load_series(loads, config, input_echo)` is the shared daily orchestration interface; `simulate_day` and `run_simulation` keep their existing public signatures and behaviour. The refactor changes no physics. Six full-result fixtures captured before the refactor preserve supported single-transformer outputs, including time series, metadata, rounding, alerts and verdicts. Both network representative days use that same routine.

Coincident charging peak and integrated daily energy use aligned full-precision served site powers, with final rounding only. Worst hot-spot is the maximum over every transformer and both days; status counts count each transformer once. Voltage stays associated with the branch's series and summary. No network-average insulation aging, monthly depreciation, household indicators or hosting search is introduced. These results remain illustrative planning calculations requiring site-specific calibration.

## M8 reference-equivalent life, value and exposure

`assess_impact(payload, config)` evaluates the submitted allocation and an empty-allocation baseline through the same M7 engine. Optional internal precision-returning functions expose the final-pass records before rounding, including weekend series previously omitted from the public response. They do not introduce another solver. Existing full-output golden fixtures and M7 response hashes protect public results.

For each complete representative day, equivalent reference aging hours are the sum of unrounded FAA times interval duration in hours. Monthly equivalent hours are weekday_count times weekday hours plus weekend_count times weekend hours. Additional hours are EV minus baseline and remain signed. For identical repeated days this reduces to daily difference times the configured month length. Divide by configured calendar_days_per_year times calendar-day hours for reference-equivalent years. Divide equivalent hours by the corresponding calendar hours for the aging ratio; percentage change uses the baseline as denominator and is null at zero. Peak hot-spot comparisons use absolute unrounded temperatures and Celsius differences, not temperature percentages.

The illustrative monthly economic proxy values the fraction of reference insulation life consumed: equivalent hours divided by normal_insulation_life_hours, multiplied by transformer_upgrade_cost_inr as an explicit equipment value proxy. Additional value uses additional hours directly. This neither predicts a replacement date nor guarantees spending or loss; upgrade pricing is not a site-specific replacement quote. Multiple reference-life equivalents are not clipped. INR results round to integers only at presentation; neighbourhood totals use unrounded asset values.

Strict voltage-limit comparisons count violating samples. Each sample spans step_minutes/60 hours, including the last sample; adjacent violating samples form one event and events never join across midnight. Potential connection-hours equal configured customers times violating hours. Monthly exposure weights the representative days, but customer counts are counted once if any day with nonzero monthly weight violates. Residential proxy totals include residential archetypes only; they are not a census of all neighbourhood households. Unknown counts propagate null rather than incomplete totals.

Impact metrics intentionally use unrounded voltages; near thresholds they may differ from the legacy chart alerts, which use rounded voltages. The one-point feeder model omits household service drops and appliance susceptibility, so exposure cannot establish appliance damage. Neighbourhood equivalent aging totals have units of transformer-hours or transformer-years across separate assets. Percentages and voltage extrema are not summed. Definitions and all response fields are in API contract section 10; no HTTP deployment is part of M8.

## M9 hosting search implementation

`assess_hosting(config)` obtains a zero-proposed-EV baseline through `assess_network_with_precision`. For each transformer, `candidate_load_series` calls M7's profile builder with one virtual aggregate charging entry associated with that branch. The aggregate is not a site allocation: it avoids falsely restricting electrical headroom to existing candidate-site ceilings. Residential/commercial/mixed demand and evening/daytime EV shapes remain branch-specific. The shared `simulate_load_series_with_precision` performs all electrical, thermal and aging calculations; hosting modules contain no duplicate equations.

At each grid candidate q, uncontrolled EV power is q times the normalized shape. Thus uncontrolled coincident peak is q. Managed power uses the same M7 clipping and overnight redistribution rule; the profile scale q, delivered peak and daily served kWh are returned separately. Managed feasibility retains the configured energy percentage on each day. The two representative days use summer weather but different configured demand profiles.

`check_operating_series` takes extrema of unrounded voltage, loading and hot-spot series and reports margins. A lower-bound margin is observed minimum minus configured minimum; an upper-bound margin is configured maximum minus observed maximum. Any negative margin is a violation. There is no numerical safety epsilon or decision rounding. Hot-spot warning and critical diagnostics can both violate; the lower warning threshold determines healthy hosting. Top-oil and FAA are calculated by the engine, but no operational thresholds for them are configured.

`grid_search` evaluates all positive multiples of allocation_block_kw through hosting_search_max_kw, after baseline evaluation. Exhaustive search tolerates non-monotonic feasibility; sampled monotonicity is not claimed as proof. It selects the highest evaluated feasible point and retains the next grid point's violations as limiting factors. At the upper bound, the true capacity may be greater. A compliant baseline with no feasible positive point selects zero; an already-violating baseline has no selected point and no positive search.

For managed capacity, repeat that grid for each configured fraction. Select the largest feasible scaling level, then the highest sum of representative-day served energy, then the highest fraction. This follows the existing hosting contract, not the later placement/remedy ladder. No cost, battery, reallocation or equipment upgrade is considered. The configured evaluation budget must cover every possible candidate before any simulations start; each candidate represents two daily simulations, except baseline reused from M7. Baseline convergence failure propagates; candidate convergence failure is an explicit infeasible result and does not terminate the exhaustive grid.

The response is opt-in and additive, defined in API contract section 11. M7/M8 consumers and golden outputs remain unchanged. Presentation rounds diagnostics only after feasibility and search; a negative margin close to zero may display as zero. Neighbourhood counts count each transformer once. Sum only independent uncontrolled kW, explicitly excluding any validation of shared upstream capacity or simultaneous network feasibility. The existing topology assigns identical equipment to all six branches; no unsupported per-equipment overrides are invented.

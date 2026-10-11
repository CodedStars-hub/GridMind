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

Explain bounded block-wise capacity searches and the healthy-on-both-days criterion. Document in M6.

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

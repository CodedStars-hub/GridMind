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

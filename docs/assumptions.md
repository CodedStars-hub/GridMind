# Assumptions

> Planning-grade model of one transformer. Values marked TBD are not final.

## Topology
Will describe the single-branch radial layout: HV source, transformer, one lumped LV feeder, one connection point. Filled in M2.

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
Will explain the feeder R and X choice and the voltage solution method. Filled in M2.

## Power factors
Will document the fixed power factors for base load, EV and PV. Filled in M2.

## Load profiles and calibration approach
Will describe profile shapes and the rule that calibration uses plausible ranges, not target outcomes. Filled in M3.

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

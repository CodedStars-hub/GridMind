# Assumptions

> Planning-grade model of one transformer. Values marked TBD are not final.

## Topology
Will describe the single-branch radial layout: HV source, transformer, one lumped LV feeder, one connection point. Filled in M2.

## Thermal model parameters
Will list the transformer thermal parameters and where each came from. Filled in M1.

## Feeder impedance and voltage model
Will explain the feeder R and X choice and the voltage solution method. Filled in M2.

## Power factors
Will document the fixed power factors for base load, EV and PV. Filled in M2.

## Load profiles and calibration approach
Will describe profile shapes and the rule that calibration uses plausible ranges, not target outcomes. Filled in M3.

## Aging model
Will document the aging acceleration factor and insulation-life calculation. Filled in M1.

## BESS model
Will document dispatch rule, efficiency, SOC limits and sizing sweep. Filled in M8-M9.

## Cost assumptions
Will document the upgrade and battery cost assumptions and their editable ranges. Filled in M9.

## Known limitations
Will list what the model does not cover (single transformer, single phase equivalent, mock OpenADR). Filled in M14.
Engine code must stay compatible with Python 3.12. Do not use syntax or standard-library features newer than 3.12.

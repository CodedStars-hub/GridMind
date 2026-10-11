# GridMind Modeling Assumptions & Parameter Citations

Comprehensive documentation of all physical constants, nameplate ratings, economic parameters, standards citations, and boundary assumptions used across the GridMind digital twin.

---

## 1. Network Topology & Per-Unit Basis

GridMind models a single 250 kVA distribution transformer serving a radial low-voltage (LV) feeder:
- **Topology Representation**: Balanced single-phase equivalent circuit with an ideal 1.0 p.u. High-Voltage (11 kV) source, transformer series impedance ($Z_{\text{tx}}$), lumped secondary cable impedance ($Z_{\text{feeder}}$), and a single lumped connection point for base load, EV charging, solar PV, and battery storage.
- **Per-Unit Bases**:
  - $S_{\text{base}} = 250\text{ kVA}$
  - $V_{\text{base,LV}} = 415\text{ V}$ (line-to-line)
  - $I_{\text{base}} = \frac{250000}{\sqrt{3} \times 415} \approx 347.8\text{ A}$
  - $Z_{\text{base}} = \frac{415^2}{250000} \approx 0.6889\ \Omega$

---

## 2. Transformer Thermal & Electrical Parameters

All parameters are configured in [`config/transformer.json`](../config/transformer.json) and follow standard distribution engineering specifications:

| Parameter | Value | Unit | Basis / Citation |
| :--- | :--- | :--- | :--- |
| `rated_kva` | 250 | kVA | Standard urban Indian distribution rating (PRD v2.0 §1) |
| `hv_voltage_kv` | 11.0 | kV | Standard primary distribution voltage (CEA Regulations) |
| `lv_voltage_v` | 415.0 | V | Standard 3-phase secondary nominal voltage (IS 2026) |
| `source_voltage_pu` | 1.0 | p.u. | Nominal fixed-tap substation HV bus assumption |
| `impedance_voltage_pct` | 4.5 | % | Typical short-circuit impedance for 250 kVA ONAN distribution units |
| `load_loss_w` | 3000 | W | Typical full-load copper losses at rated current (IS 1180 Level 2) |
| `no_load_loss_w` | 600 | W | Typical core losses ($P_{\text{load\_loss}} / P_{\text{no\_load\_loss}} = 5.0$) |
| `rated_top_oil_rise_c` | 55 | °C | IEEE C57.91 Table 1 / IS 2026 standard 65°C-rise ONAN unit |
| `rated_hotspot_rise_over_top_oil_c` | 25 | °C | IEEE C57.91 Table 1 ($55^\circ\text{C} + 25^\circ\text{C} = 80^\circ\text{C}$ rise; $+ 30^\circ\text{C} = 110^\circ\text{C}$ ref) |
| `loss_ratio` | 5.0 | ratio | $3000\text{ W} / 600\text{ W} = 5.0$ loss ratio |
| `oil_exponent` ($n$) | 0.8 | none | IEEE C57.91 standard exponent for ONAN natural oil circulation |
| `winding_exponent` ($m$) | 0.8 | none | IEEE C57.91 standard exponent for ONAN natural cooling |
| `oil_time_constant_min` ($\tau_{\text{TO}}$) | 180 | min | IEEE C57.91 typical thermal inertia of bulk transformer oil |
| `winding_time_constant_min` ($\tau_W$) | 5 | min | IEEE C57.91 typical thermal time constant of copper windings |
| `reference_ambient_c` | 30 | °C | Reference ambient temperature (IS 2026 / IEEE C57.91) |

---

## 3. Secondary Feeder Impedance & Power Flow

Configured in [`config/transformer.json`](../config/transformer.json):

| Parameter | Value | Unit | Basis / Citation |
| :--- | :--- | :--- | :--- |
| `feeder_resistance_pu` | 0.024 | p.u. | Approx. 100 m of 185 mm² 4-core aluminum XLPE cable |
| `feeder_reactance_pu` | 0.010 | p.u. | Typical inductive reactance for bundled underground LV cable |
| `powerflow_tolerance_pu` | 1e-9 | p.u. | Numerical fixed-point convergence tolerance |
| `powerflow_max_iterations` | 50 | count | Numerical iteration ceiling (typically converges in 3–5 iterations) |

**Power Factor Standards**:
- Base load: $\cos\phi = 0.95$ lagging (typical diversified residential/commercial power factor).
- EV charging hub: $\cos\phi = 0.98$ lagging (modern power-factor corrected DC fast charger rectification).
- Solar PV inverters: $\cos\phi = 1.00$ unity (standard grid-tied solar operating in active power export).
- Battery Energy Storage: $\cos\phi = 1.00$ unity (four-quadrant inverter set to real power dispatch).

---

## 4. Operational Limits & Alert Thresholds

Configured in [`config/limits.json`](../config/limits.json):

| Threshold | Value | Severity | Justification & Standard |
| :--- | :--- | :--- | :--- |
| `voltage_min_pu` | 0.95 | Warning | Lower statutory voltage limit (ANSI C84.1 Range A / CEA Grid Code) |
| `voltage_max_pu` | 1.05 | Warning | Upper statutory voltage limit (ANSI C84.1 Range A / CEA Grid Code) |
| `hotspot_warning_c` | 110.0 | Warning | Continuous operating hot-spot limit for normal insulation life (IEEE C57.91 §5.1) |
| `hotspot_critical_c` | 140.0 | Critical | Emergency hot-spot threshold for bubble formation risk (IEEE C57.91 §5.2) |
| `loading_info_pct` | 100.0 | Info | Rated current capacity benchmark |
| `insulation_life_cap_years` | 100.0 | Display Cap | Numerical display cap for negligible aging regimes |

---

## 5. Battery Energy Storage System (BESS) Sizing

Configured in [`config/bess.json`](../config/bess.json):

| Parameter | Value | Unit | Justification & Modeling Rule |
| :--- | :--- | :--- | :--- |
| `round_trip_efficiency` | 0.90 | ratio | 90% AC-to-AC round-trip efficiency for lithium iron phosphate (LFP) systems |
| `soc_min` | 0.10 | ratio | 10% lower depth-of-discharge buffer to protect battery health |
| `soc_max` | 0.90 | ratio | 90% upper SOC ceiling to prevent overcharging degradation |
| `initial_soc` | 0.50 | ratio | 50% midpoint starting state of charge |
| `sweep_power_kw_min` | 10 | kW | Lower bound for physical inverter power sweep |
| `sweep_power_kw_max` | 150 | kW | Upper bound for physical inverter power sweep |
| `sweep_power_kw_step` | 10 | kW | Inverter power granularity |
| `sweep_energy_kwh_min` | 20 | kWh | Lower bound for battery pack energy capacity |
| `sweep_energy_kwh_max` | 300 | kWh | Upper bound for battery pack energy capacity |
| `sweep_energy_kwh_step` | 20 | kWh | Battery pack capacity granularity |

**BESS Operational Conservation Rules**:
1. **Net-Zero Daily Energy Balance**: To ensure sustainable daily cyclical operation, the BESS simulation enforces $\text{SOC}_{\text{end}} = \text{SOC}_{\text{start}}$ across the 24-hour horizon.
2. **Dispatch Algorithm**:
   - Discharges automatically during intervals where loading exceeds 100% or secondary voltage drops below $0.95\text{ p.u.}$
   - Recharges during midday rooftop solar surplus (11:00–14:00) or midnight off-peak grid valleys (01:00–05:00).
3. **Bounded Sweep Optimization**: Evaluates all $(P_{\text{kW}}, E_{\text{kWh}})$ candidate pairs through the coupled multi-physics engine, selecting the minimal cost-effective pair that eliminates all voltage and thermal violations. If no pair succeeds, the engine recommends a transformer upgrade.

---

## 6. Economic Assumptions & Capex Benchmarks

Configured in [`config/costs.json`](../config/costs.json):

| Parameter | Value | Unit | Basis / Real-World Market Benchmark |
| :--- | :--- | :--- | :--- |
| `transformer_upgrade_cost_inr` | 5,50,000 | INR | Typical utility turnkey replacement cost for 250 kVA $\to$ 400/500 kVA (equipment, civil work, permits) |
| `bess_cost_per_kwh_inr` | 25,000 | INR/kWh | Commercial & industrial LFP battery pack capital expenditure (~$300/kWh) |
| `bess_cost_per_kw_inr` | 12,000 | INR/kW | Bi-directional grid-tied PCS inverter and balance-of-system cost (~$145/kW) |
| `smart_controller_fee_inr` | 35,000 | INR | One-time edge gateway controller hardware & commissioning charge |

**Economic Valuation Proxy**:
Insulation loss-of-life is monetized against the capital replacement value of the transformer:
$$\text{Economic Depreciation Proxy} = \left( \frac{L_{\text{EQ,hours}}}{180,000\text{ hours}} \right) \times \text{transformer\_upgrade\_cost\_inr}$$

---

## 7. Multi-Feeder Neighbourhood Archetypes

Configured in [`config/neighbourhood.json`](../config/neighbourhood.json):

GridMind models **Model Colony, Sector 14** as an illustrative 6-transformer distribution network:
- **T1 (Residential Block A)**: 180 connections, heavy baseline loading, evening EV charging profile.
- **T2 (Residential Block B)**: 140 connections, moderate baseline loading, evening EV charging profile.
- **T3 (Central Market)**: 90 connections, heavy baseline loading, daytime commercial EV profile.
- **T4 (Metro Station Plaza)**: 60 connections, moderate baseline loading, daytime commute EV profile.
- **T5 (Community Hospital)**: 75 connections, critical baseline loading, daytime mixed EV profile.
- **T6 (Mixed Commercial/Residential)**: 110 connections, moderate baseline loading, evening mixed profile.

---

## 8. Known Limitations & Model Boundaries

To maintain engineering transparency, the digital twin acknowledges the following intentional boundary assumptions:
1. **Lumped Secondary Representation**: Secondary feeders are aggregated into a single lumped impedance per transformer branch; internal house-by-house service drop variations are not modeled.
2. **Balanced Single-Phase Equivalent**: Three-phase unbalanced phase-loading is assumed balanced across the three phases.
3. **Planning-Grade Determinism**: The engine is designed for rapid interconnection screening and strategic mitigation planning; it does not replace site-specific utility transient fault studies.
4. **Mock OpenADR Payload**: While the emitted OpenADR 2.0b payload conforms strictly to the OASIS specification, the destination AWS IoT Core MQTT broker acts as a simulated edge telemetry interface.

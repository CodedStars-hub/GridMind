# GridMind Engineering Methodology

Authoritative mathematical derivations, physical formulations, and algorithmic specifications governing the GridMind digital twin.

---

## 1. Executive Summary & Core Objective

GridMind addresses the critical last-mile distribution planning challenge: **evaluating the operational and physical degradation impact of concentrated EV fast charging hubs and rooftop solar PV on urban 11 kV / 415 V distribution transformers.**

Distribution transformers (typically 100–630 kVA, nominal 250 kVA) are the most expensive and vulnerable assets in the low-voltage network. When high-power EV charging coincides with evening peak load and high ambient temperatures, transformers experience simultaneous statutory voltage collapse ($< 0.95\text{ p.u.}$) and rapid thermal degradation.

GridMind replaces static spreadsheets and licensed black-box software with a **deterministic, standard-library Python physics engine** that:
1. Solves radial AC power flow via exact fixed-point iteration.
2. Updates transformer thermal states using the **IEEE C57.91-1995/2011** analytical exponential model.
3. Quantifies cumulative insulation degradation via the **Arrhenius Aging Acceleration Factor ($F_{\text{AA}}$)**.
4. Auto-sizes Battery Energy Storage Systems (BESS) or evaluates dynamic smart-charging curtailment to remediate violations.
5. Emits standardized **OpenADR 2.0b** demand-response signals published to **AWS IoT Core** edge controllers.

---

## 2. Electrical Model & Radial Power Flow

### 2.1 Per-Unit System Formulation
The electrical network is modeled on a single-phase balanced equivalent basis using standard per-unit normalizations:
- **Base Power**: $S_{\text{base}} = 250\text{ kVA}$
- **Base Secondary Voltage**: $V_{\text{base,LV}} = 415\text{ V}$ (line-to-line) $\implies V_{\text{base,LN}} = \frac{415}{\sqrt{3}} \approx 239.6\text{ V}$
- **Base Secondary Current**: $I_{\text{base}} = \frac{S_{\text{base}}}{\sqrt{3} \cdot V_{\text{base,LV}}} \approx 347.8\text{ A}$
- **Base Impedance**: $Z_{\text{base}} = \frac{V_{\text{base,LV}}^2}{S_{\text{base}}} = \frac{415^2}{250000} \approx 0.6889\ \Omega$

### 2.2 Transformer & Feeder Impedance
The network series impedance $Z_{\text{series}} = R_{\text{total}} + jX_{\text{total}}$ consists of:
1. **Transformer Series Impedance**:
   - Short-circuit impedance magnitude: $z_{\text{tx}} = \frac{\text{impedance\_voltage\_pct}}{100} = 0.045\text{ p.u.}$
   - Transformer resistance: $r_{\text{tx}} = \frac{P_{\text{load\_loss,W}}}{S_{\text{base,VA}}} = \frac{3000}{250000} = 0.012\text{ p.u.}$
   - Transformer reactance: $x_{\text{tx}} = \sqrt{z_{\text{tx}}^2 - r_{\text{tx}}^2} = \sqrt{0.045^2 - 0.012^2} \approx 0.04337\text{ p.u.}$
2. **Lumped Secondary Feeder Impedance**:
   - Modelled on $100\text{ m}$ of $185\text{ mm}^2$ 4-core aluminum underground cable:
   - $r_{\text{feeder}} = 0.024\text{ p.u.}$
   - $x_{\text{feeder}} = 0.010\text{ p.u.}$
3. **Total Radial Branch Impedance**:
   $$R_{\text{total}} = r_{\text{tx}} + r_{\text{feeder}} = 0.012 + 0.024 = 0.036\text{ p.u.}$$
   $$X_{\text{total}} = x_{\text{tx}} + x_{\text{feeder}} = 0.04337 + 0.010 = 0.05337\text{ p.u.}$$

### 2.3 Net Load Aggregation & Power Factors
At each 15-minute time-step $t \in [0, 95]$:
- Base active demand: $P_{\text{base}}(t)$ with fixed power factor $\cos\phi_{\text{base}} = 0.95$ lagging.
- EV hub active demand: $P_{\text{EV}}(t)$ with fixed power factor $\cos\phi_{\text{EV}} = 0.98$ lagging.
- Solar PV generation: $P_{\text{PV}}(t)$ at unity power factor ($\cos\phi_{\text{PV}} = 1.0$).
- Battery net power: $P_{\text{BESS}}(t)$ (discharge $> 0$, charge $< 0$) at unity power factor.

$$\text{Net Active Power: } P_{\text{net}}(t) = P_{\text{base}}(t) + P_{\text{EV}}(t) - P_{\text{PV}}(t) - P_{\text{BESS,discharge}}(t) + P_{\text{BESS,charge}}(t)$$

$$\text{Net Reactive Power: } Q_{\text{net}}(t) = P_{\text{base}}(t) \tan(\arccos(0.95)) + P_{\text{EV}}(t) \tan(\arccos(0.98))$$

In per-unit notation:
$$s_{\text{net}}(t) = p_{\text{net}}(t) + j q_{\text{net}}(t) = \frac{P_{\text{net}}(t)}{S_{\text{base}}} + j \frac{Q_{\text{net}}(t)}{S_{\text{base}}}$$

### 2.4 Exact Fixed-Point Iterative Solution
Starting with $V^{(0)} = V_{\text{source}} = 1.0 + j0.0\text{ p.u.}$, the connection point voltage is iteratively solved:

$$I^{(k)} = \left( \frac{s_{\text{net}}}{V^{(k)}} \right)^*$$

$$V^{(k+1)} = V_{\text{source}} - Z_{\text{series}} \cdot I^{(k)}$$

The solver terminates when $|V^{(k+1)} - V^{(k)}| < 10^{-9}\text{ p.u.}$ (typically converges in 3–5 iterations). A numerical guard aborts if $|V| < 0.10\text{ p.u.}$ to prevent voltage collapse singularity.

### 2.5 Current-Based Loading Definition
At depressed operating voltages, constant apparent power draws higher current. GridMind measures loading as true secondary current magnitude:

$$K(t) = \frac{|I(t)|}{I_{\text{base}}} = |I(t)|\text{ (in p.u.)} \implies \text{Loading \%} = 100 \cdot K(t)$$

---

## 3. Thermal Dynamics: IEEE C57.91-1995/2011

### 3.1 Limitations of Forward Euler Discretization
Distribution transformer winding time constants ($\tau_W \approx 5\text{ minutes}$) are significantly shorter than the standard 15-minute simulation interval ($\Delta t = 15\text{ minutes}$). Explicit forward Euler approximation introduces numerical oscillation and overshoots. GridMind implements the **exact analytical exponential state update**.

### 3.2 State Equations & Analytic State Advance
Transformer thermal behavior is governed by two coupled first-order differential equations representing top-oil rise over ambient ($\Delta \theta_{\text{TO}}$) and winding hot-spot rise over top-oil ($\Delta \theta_H$):

$$\tau_{\text{TO}} \frac{d\Delta \theta_{\text{TO}}}{dt} + \Delta \theta_{\text{TO}} = \Delta \theta_{\text{TO},U}$$

$$\tau_W \frac{d\Delta \theta_H}{dt} + \Delta \theta_H = \Delta \theta_{H,U}$$

Given constant load $K(t)$ over interval $\Delta t = 15\text{ min}$, the exact analytical solutions are:

$$\Delta \theta_{\text{TO}}(t) = \Delta \theta_{\text{TO},U} - \left( \Delta \theta_{\text{TO},U} - \Delta \theta_{\text{TO}}(t - \Delta t) \right) e^{-\Delta t / \tau_{\text{TO}}}$$

$$\Delta \theta_H(t) = \Delta \theta_{H,U} - \left( \Delta \theta_{H,U} - \Delta \theta_H(t - \Delta t) \right) e^{-\Delta t / \tau_W}$$

Where ultimate steady-state rises are defined by:
- **Ultimate Top-Oil Rise**:
  $$\Delta \theta_{\text{TO},U} = \Delta \theta_{\text{TO,rated}} \left( \frac{K(t)^2 R_{\text{loss}} + 1}{R_{\text{loss}} + 1} \right)^n$$
- **Ultimate Hot-Spot Rise over Top-Oil**:
  $$\Delta \theta_{H,U} = \Delta \theta_{H,\text{rated}} \cdot K(t)^{2m}$$

Where:
- $\Delta \theta_{\text{TO,rated}} = 55^\circ\text{C}$ (rated top-oil rise for 65°C-rise ONAN unit)
- $\Delta \theta_{H,\text{rated}} = 25^\circ\text{C}$ (rated hot-spot rise over top-oil)
- $R_{\text{loss}} = \frac{P_{\text{load\_loss}}}{P_{\text{no\_load\_loss}}} = \frac{3000}{600} = 5.0$ (loss ratio)
- $n = 0.8$ (oil cooling exponent)
- $m = 0.8$ (winding cooling exponent)
- $\tau_{\text{TO}} = 180\text{ minutes}$ (oil thermal time constant)
- $\tau_W = 5\text{ minutes}$ (winding thermal time constant)

### 3.3 Absolute Temperatures & Warm-Up Procedure
Absolute temperatures are obtained by superimposing ambient temperature $\theta_A(t)$:
$$\theta_{\text{TO}}(t) = \theta_A(t) + \Delta \theta_{\text{TO}}(t)$$
$$\theta_H(t) = \theta_{\text{TO}}(t) + \Delta \theta_H(t) = \theta_A(t) + \Delta \theta_{\text{TO}}(t) + \Delta \theta_H(t)$$

**Dual-Pass Warm-Up**: To eliminate arbitrary initial condition bias at midnight (00:00), the 24-hour simulation is executed over two complete cycles. Pass 1 warms up the thermal mass toward periodic steady state; Pass 2 is reported to the user.

---

## 4. Insulation Aging & Life Consumption

### 4.1 Arrhenius Aging Acceleration Factor ($F_{\text{AA}}$)
The thermal degradation of cellulose insulation immersed in mineral oil follows the Arrhenius chemical reaction rate:

$$F_{\text{AA}}(t) = \exp\left( \frac{B}{T_{\text{ref}}} - \frac{B}{T_H(t)} \right) = \exp\left( \frac{15000}{383.15} - \frac{15000}{\theta_H(t) + 273.15} \right)$$

- At $\theta_H = 110^\circ\text{C}$: $F_{\text{AA}} = 1.0$ (baseline degradation rate)
- At $\theta_H = 105^\circ\text{C}$: $F_{\text{AA}} \approx 0.63$ (decelerated aging)
- At $\theta_H = 135^\circ\text{C}$: $F_{\text{AA}} \approx 10.9$ (1 hour consumes 11 hours of asset life)
- At $\theta_H = 140^\circ\text{C}$: $F_{\text{AA}} \approx 17.2$ (severe thermal runaway)

### 4.2 Equivalent Aging Hours & Expected Lifespan
Daily equivalent operating hours at reference temperature:
$$L_{\text{EQ}} = \sum_{i=0}^{95} F_{\text{AA}}(t_i) \cdot \Delta t_{\text{hours}} \quad (\text{where } \Delta t = 0.25\text{ hours})$$

Normal insulation life expectancy under reference conditions is $180,000\text{ hours}$ ($\approx 20.55\text{ years}$). Projected calendar lifespan under the simulated operating regime:
$$\text{Expected Life (Years)} = \min\left( \frac{180000}{L_{\text{EQ}} \times 365}, \text{insulation\_life\_cap\_years} \right)$$
(where the default display cap is 100 years).

---

## 5. Monthly Projection & Economic Valuation

### 5.1 Representative Day Weighting
To project annual and monthly performance without simulating all 365 days, GridMind uses representative weekday and weekend profiles:
$$\text{Days}_{\text{month}} = N_{\text{weekday}} + N_{\text{weekend}} = 22 + 8 = 30\text{ days}$$
$$L_{\text{EQ,month}} = N_{\text{weekday}} \cdot L_{\text{EQ,weekday}} + N_{\text{weekend}} \cdot L_{\text{EQ,weekend}}$$

### 5.2 Economic Asset Life Depreciation Proxy
GridMind values insulation life consumed against the capital cost of a transformer replacement:
$$\text{Asset Replacement Capex Proxy} = \text{₹}5,50,000 \text{ to ₹}6,00,000$$
$$\text{Monthly Economic Depreciation} = \frac{L_{\text{EQ,month}}}{180,000} \times \text{transformer\_upgrade\_cost\_inr}$$

$$\text{Additional Monthly Degradation (EV Impact)} = \frac{L_{\text{EQ,month}}^{\text{EV}} - L_{\text{EQ,month}}^{\text{baseline}}}{180,000} \times \text{transformer\_upgrade\_cost\_inr}$$

---

## 6. Household Exposure & Voltage Quality

### 6.1 Customer Exposure Metrics
Low-voltage violations ($V < 0.95\text{ p.u.}$) harm residential appliances (air conditioners, induction cooktops, water pumps):
$$\text{Violating Duration (Hours)} = \sum_{t \in \text{violations}} \Delta t_{\text{hours}}$$
$$\text{Customer-Hours of Poor Power Quality} = N_{\text{connections}} \times \text{Violating Duration}$$

---

## 7. Hosting Capacity Search Engine

### 7.1 Exhaustive Grid Search
Rather than relying on unproven monotonic assumptions, GridMind conducts a discrete exhaustive search over EV charging capacity:
- Increments: Multiples of $10\text{ kW}$ ($\Delta q = 10\text{ kW}$).
- Search Range: $q \in [10, 100]\text{ kW}$.
- Feasibility Criterion: Must satisfy operating margins on **both representative days**:
  $$\min V(t) \ge 0.95\text{ p.u.}$$
  $$\max V(t) \le 1.05\text{ p.u.}$$
  $$\max \theta_H(t) \le 110^\circ\text{C}$$
  $$\max K(t) \le 100\%$$

---

## 8. Strategic Placement & Remedy Ladder

### 8.1 Footfall-Ranked Placement Algorithm
When multiple candidate EV charging sites request grid interconnection, GridMind evaluates a 5-step deterministic greedy allocation:
1. **Candidate Attractiveness Scoring**:
   $$\text{Score}(s) = \frac{\text{footfall\_score}(s)}{\text{max\_footfall}} \cdot w_{\text{footfall}}$$
2. **Prioritization**: Ranks sites by descending score, breaking ties by stable site ID.
3. **Remedy Evaluation Ladder**: For each candidate site:
   - **Mode 1 (Unmanaged)**: Full requested capacity.
   - **Mode 2 (Managed Smart-Charging)**: Evaluates peak curtailment with overnight off-peak reallocation.
   - **Mode 3 (BESS Mitigation)**: Sizes local battery storage to absorb charging peaks.
4. **Acceptance**: Commits the highest feasible allocation meeting a minimum 70% energy retention guarantee.
5. **Final Network Verification**: Re-evaluates the entire 6-transformer network simultaneously to confirm no secondary violations.

---

## 9. M7–M11 Production Transport & Multi-Asset Assessment

### 9.1 Multi-Transformer Aggregation (M7)
`assess_network(payload, config)` maps candidate sites to configured transformers (T1–T6), builds archetype load profiles (residential, commercial, mixed), and aggregates power flows without inventing synthetic network edges.

### 9.2 Economic Valuation Engine (M8)
`assess_impact(payload, config)` compares proposed charging allocations against a zero-EV baseline, providing unrounded high-precision series for depreciation and customer exposure hours.

### 9.3 Hosting Headroom Search (M9)
`assess_hosting(config)` evaluates uncontrolled and managed hosting capacity across the transformer fleet, reporting exact limiting constraints (voltage lower bound, thermal hot-spot rise, or secondary current rating).

### 9.4 Strategic Planner (M10)
`plan_network(payload, config)` executes the deterministic greedy heuristic to distribute a target EV demand across candidate sites.

### 9.5 HTTP Transport Gateway (M11)
AWS Lambda handler exposes `/v2` endpoints with strict JSON deserialization, 2,048-byte request size enforcement, CORS origin validation, and sub-50 ms execution latency.

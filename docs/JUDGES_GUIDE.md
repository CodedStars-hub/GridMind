# GridMind - Hackathon Judge & Evaluator Guide

**WeMakeDevs Environmental Hacks 2026** · **Track: Waste & Energy**  
*Evaluating GridMind among 9,000+ Participants.*

<br />

> 🎬 **Official Video Demonstration**: Watch our project walkthrough explaining the engineering, physics, and live AWS architecture: **[Complete Video Demonstration on Google Drive](https://drive.google.com/file/d/10gruQFk1MFoZIFqSXgte1COrSRzSN2S-/view?usp=drive_link)**  
> ⚡ **Quick Evaluator Verification**: The serverless backend is live in `ap-south-1` (Mumbai).  
> Test live API health directly: **[`https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/health`](https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/health)**

---

## 1. Executive Summary for Judges

Across cities in India and developing nations, distribution utilities (DISCOMs) face a massive roadblock in clean energy adoption:
- **The Core Problem**: 11 kV / 415 V distribution transformers (250 kVA) are overloaded when evening EV fast-charging surges right as solar PV generation drops to zero.
- **The Dual Crisis**: Transformers experience statutory voltage collapse ($< 0.95\text{ p.u.}$) and rapid insulation thermal breakdown ($> 110^\circ\text{C} / 140^\circ\text{C}$), destroying millions in public assets.
- **Current Utility Inefficiency**: Utility engineers either reject EV charging applications blindly (stalling clean energy) or demand expensive ₹5-7 Lakh transformer replacements (wasting metric tons of copper, steel, and oil).
- **The GridMind Solution**: A browser-based digital twin that couples AC power-flow with IEEE C57.91 thermal physics, auto-sizes BESS, evaluates managed smart-charging, and emits OpenADR 2.0b dispatch instructions to AWS IoT Core edge controllers.

---

## 2. Rubric Alignment Matrix

| Hackathon Criterion | Weight | How GridMind Satisfies It | Verifiable Evidence |
| :--- | :--- | :--- | :--- |
| **Idea & Real-World Impact** | 30% | Targets physical waste of distribution assets and energy grid bottlenecks in developing nations. Unlocks rooftop solar & EV hosting capacity without ₹5-7L capital waste. | Detailed in [docs/ENVIRONMENTAL_IMPACT.md](ENVIRONMENTAL_IMPACT.md) and [PRD](../planning/product-requirement.md). |
| **Technical Rigor & Physics** | 25% | Standard-library Python engine solving exact radial AC power flow, IEEE C57.91 analytic exponential updates, and Arrhenius aging ($F_{\text{AA}}$). Zero hallucinations. | 100% reproducible tests in [engine/tests/](../engine/tests/); derivations in [docs/methodology.md](methodology.md). |
| **AWS Cloud Architecture** | 25% | AWS SAM stack deployed in `ap-south-1` (Mumbai). HTTP API Gateway v2, Lambda (Python 3.12, <40 ms warm), S3 edge fallback, and AWS IoT Core MQTT dispatch. | Live endpoint at `/v2/health`; CloudFormation template in [infra/template.json](../infra/template.json); complete cloud guide in [docs/AWS_ARCHITECTURE.md](AWS_ARCHITECTURE.md). |
| **Design, UX & Craft** | 20% | Executive engineering dashboard built with React 19, strict TypeScript, and Tailwind CSS v4. Interactive SVG network topology explorer and responsive charts. | Frontend code in [frontend/src/](../frontend/src/) and verified locally via `npm run dev`. |

---

## 3. Recommended Video Demo Flow

> 🎬 **Direct Video Link**: **[Watch the Complete Video Demonstration on Google Drive](https://drive.google.com/file/d/10gruQFk1MFoZIFqSXgte1COrSRzSN2S-/view?usp=drive_link)**

If evaluating our recorded video submission, here is the exact narrative structure:

```text
[0:00 - 0:35] Problem Definition:
  - Introduce one DISCOM planning engineer facing an interconnection request for a 50 kW EV charging hub on a 250 kVA transformer.
  - Explain the dual statutory constraints: Voltage band (0.95-1.05 p.u.) and Hot-spot temperature (110°C / 140°C).

[0:35 - 1:15] Unmitigated Baseline Simulation:
  - Open GridMind (default scenario preloaded, zero setup). Click "Run Simulation".
  - Show the 4 synchronized time-series charts (Voltage, Loading, Hot-Spot, SOC).
  - Highlight the red alerts: evening voltage sag to 0.932 p.u. and hot-spot spiking to 134°C.
  - Read the live numbers: 4.8 equivalent aging days consumed in a single 24-hour cycle!

[1:15 - 2:00] Mitigation & Remedy Optimization:
  - Click "Find Minimum BESS".
  - Show before-and-after overlay: battery discharges during the evening peak, restoring voltage above 0.95 p.u. and capping hot-spot below 110°C.
  - Review the autonomous BESS sizing verdict (e.g., 30 kW / 60 kWh) and the transparent Capex comparison against a ₹5.5 Lakh transformer replacement.

[2:00 - 2:30] Multi-Feeder Neighbourhood Explorer:
  - Navigate to "Network Explorer" showing transformers T1-T6 across Model Colony.
  - Demonstrate footfall-weighted candidate placement allocating charging capacity based on electrical headroom.

[2:30 - 3:00] Edge Dispatch & AWS Architecture:
  - Click "Send Dispatch". Show the structured OpenADR 2.0b payload.
  - Verify message publication to AWS IoT Core MQTT topic `gridmind/dt-250/dispatch`.
  - Close with the serverless architecture on AWS ap-south-1.
```

---

## 4. Evaluator Quick-Start Runbook

Judges can verify GridMind locally in under 60 seconds:

### Step 1: Verify Live Cloud Endpoint
```bash
# Query the live deployed health endpoint in Mumbai (ap-south-1)
curl https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/health

# Query live scenarios and assumptions
curl https://0qe4v48i38.execute-api.ap-south-1.amazonaws.com/v2/scenarios
```

### Step 2: Run a Local CLI Simulation
```bash
# Run simulation with 50 kW EV and 30 kWp solar under heavy load
PYTHONPATH=engine python -m gridmind_engine.cli \
  --ev 50 \
  --pv 30 \
  --day summer_weekday \
  --load heavy \
  --summary
```

### Step 3: Run Engine Physics Unit Tests
```bash
python -m pytest engine/tests -v
```

---

## 5. Frequently Asked Questions by Evaluators

### Q: Why didn't you use Machine Learning (LLMs / Neural Networks) for the core engine?
**A**: Distribution grid physics are deterministic and safety-critical. Predicting transformer burnouts or line voltages with black-box neural networks introduces hallucination risk that no licensed utility engineer can legally approve. GridMind uses standards-governed equations (**IEEE C57.91-1995/2011**) that are 100% mathematically defensible.

### Q: Why is the engine pure Python with zero external libraries?
**A**: Skipping heavy packages like NumPy and SciPy allows the AWS Lambda function to boot in **under 300 ms** with zero container layers, eliminating cold-start latency and minimizing cloud execution costs.

### Q: How does GridMind ensure 100% uptime during demonstrations?
**A**: GridMind implements an automated S3 precomputed fallback. All 144 baseline parameter permutations are pre-calculated. If any network timeout occurs, the frontend seamlessly renders the precomputed twin with a visible status badge.

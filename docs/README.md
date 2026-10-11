# GridMind Technical Documentation Directory

Authoritative engineering, mathematical, cloud architectural, and hackathon evaluation documentation for the GridMind digital twin.

---

## 1. Hackathon Evaluation & Impact
- 🏆 [**Judges & Evaluator Guide**](JUDGES_GUIDE.md): 3-minute video breakdown, rubric mapping (Waste & Energy track), and live cloud endpoint testing.
- 🌱 [**Environmental Impact Assessment**](ENVIRONMENTAL_IMPACT.md): Quantified asset waste reduction (avoided copper/steel/mineral oil scrap) and renewable hosting expansion.
- ❓ [**Frequently Asked Questions (FAQ)**](FAQ.md): Detailed engineering answers on standard-library Python, avoiding black-box ML, and thermal stability.
- 🧪 [**End-to-End Verification Runbook**](VERIFICATION_RUNBOOK.md): Step-by-step reproduction guide for local tests, Lambda invokers, frontend quality gates, and live AWS calls.

---

## 2. Core Physics & Engineering Specifications
- 📖 [**API Contract v3**](api-contract.md): Single source of truth for all request/response JSON schemas, enums, units, and error codes.
- 📐 [**Engineering Methodology**](methodology.md): Full mathematical derivations for radial AC power flow, IEEE C57.91 analytic exponential updates, and Arrhenius aging kinetics.
- 🔬 [**Assumptions & Parameters**](assumptions.md): Comprehensive citations and justifications for all transformer nameplate values, feeder impedances, and BESS settings.
- 📋 [**Release Readiness Checklist**](release-readiness.md): Release gates and production verification criteria.

---

## 3. Architecture & Cloud Infrastructure
- 🏗️ [**System & Cloud Architecture**](ARCHITECTURE.md): Single-origin CloudFront design, serverless Lambda execution, AWS IoT Core dispatch, and S3 edge fallback.
- 🔌 [**API v2 Reference Guide**](API_REFERENCE.md): Detailed specification of all 8 production `/v2` endpoints with example curl commands.
- ☁️ [**AWS Infrastructure Guide**](../infra/README.md): AWS SAM CloudFormation template review, IAM permissions, and deployment procedures.

---

## 4. Frontend & Planning
- 💻 [**Frontend Architecture & Setup**](../frontend/README.md): React 19, strict TypeScript, Vite 8 proxy configuration, and network explorer.
- 📋 [**Product Requirements Document (PRD v2)**](../planning/product-requirement.md): Problem definition, target personas, and MVP boundaries.
- 🗺️ [**Implementation Plan**](../planning/implementationplan.md): Milestone roadmap (M1–M13) from physics foundations to interactive views.

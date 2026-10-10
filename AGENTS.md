# GridMind: rules for the coding agent

GridMind is a browser-based digital twin of ONE 250 kVA distribution transformer.
It simulates 24 hours (96 steps of 15 min): voltage, loading, IEEE C57.91 thermal
model and aging, battery (BESS) sizing, cost comparison, and an OpenADR-style mock
dispatch. Stack: Python engine (standard library only), one AWS Lambda, API Gateway,
S3, CloudFront, IoT Core, Vite + React + TypeScript frontend.

## Working rules
1. Implement ONLY the milestone in the current prompt. Do not start or refactor other milestones.
2. The engine uses the Python standard library only. The only dev dependency is pytest.
   Do not add any dependency without asking.
3. Code must stay compatible with Python 3.12 (the Lambda runtime), even if the local Python is newer.
4. No physics constants, limits, costs or profile values in code. They live in config/*.json,
   and every parameter carries a "source" or "assumption" note.
5. docs/api-contract.md is the single source of truth for all JSON shapes. If a change is
   needed, update the doc in the same change and flag it.
6. One engine, used everywhere (Lambda, scripts, CLI, tests). Never reimplement physics elsewhere.
7. Do not make git commits. Do not install anything globally. Do not run cloud, deploy, npm
   or docker commands unless the prompt says so. Ask before installing anything.
8. The reviewer is a beginner learning as they go: small files, plain-English comments.
9. If the prompt is ambiguous, pick the simplest option and list it under "Decisions and ambiguities".
10. Never print, request, or store credentials or API keys.

## Finishing a milestone
Run the checks listed in the prompt and paste the REAL output (not summaries) into a
FINAL REPORT with these sections: "What was created", "Test and check results",
"Decisions and ambiguities", "Anything not done". Then stop and wait.
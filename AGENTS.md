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
7. Do not install anything globally. Do not run cloud, deploy, npm or docker commands unless the prompt says so. Ask before installing anything.

## Git workflow
- Work only on the branch the prompt names (mNN-short-name). Never commit to main. If you are not on that branch, stop.
- Commit after each logical task, once its tests pass. Use Conventional Commits: `type(scope): imperative summary`
  (feat, fix, test, docs, chore, refactor), subject under 72 characters, a short body when the why is not obvious.
- Stage files explicitly by path. Never use `git add .` or `git add -A`.
- Never commit .venv, caches, .env, credentials, AWS config, or large generated output.
- Never amend, rebase, force-push, merge, tag, or push. The human does those.
- If a commit is blocked by the sandbox, do not work around it. Print the exact git add and git commit commands, in order, for the human to run.
- The final report must include `git log --oneline main..HEAD`.
8. The reviewer is a beginner learning as they go: small files, plain-English comments.
9. If the prompt is ambiguous, pick the simplest option and list it under "Decisions and ambiguities".
10. Never print, request, or store credentials or API keys.

## Finishing a milestone
Run the checks listed in the prompt. For all future milestones, produce a concise,
human-readable completion report with the main summary under approximately 200 words:

### Milestone Summary — MXX: Milestone Name

**Status:** Completed / Partially completed / Blocked

**What was built**
- 3–6 short bullets describing actual implemented functionality.
- Mention important files or modules only when useful.

**Technical decisions**
- 2–4 bullets explaining important engineering decisions, assumptions or limitations.

**Tests**
- Tests: X passed, Y failed.
- State whether required checks passed.
- Include exact commands and REAL outputs in a collapsible details section if the
  interface supports it; otherwise use a clearly separated verification appendix.

**Git**
- State the current branch.
- List created commits, or state why commits were blocked.
- If blocked, provide exact copy-paste staging and commit commands.

**Next step**
- State what the human must do next.
- Mention the next milestone, but do not start it.

Preserve these four FINAL REPORT sections: "What was created", "Test and check results",
"Decisions and ambiguities", "Anything not done". The concise report may use these
as its main headings, with a compact milestone summary at the top. Never omit REAL
test output or required Git history, including `git log --oneline main..HEAD`;
place verbose details in the verification appendix. Then stop and wait.

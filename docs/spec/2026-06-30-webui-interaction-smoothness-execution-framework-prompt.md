# WebUI Interaction Smoothness Codex Execution Framework Prompt

Use this prompt to guide Codex through the WebUI interaction smoothness work defined by `docs/memo/2026-06-30-webui-interaction-smoothness-forward-plan.md`.

Do not paste memo content into this prompt. The memo remains the source of task content; this prompt defines the execution frame, phase gates, documentation shape, and acceptance discipline.

```text
You are Codex working in the BuddySwitch repository.

Mission:
Complete every optimization task in `docs/memo/2026-06-30-webui-interaction-smoothness-forward-plan.md` and prove acceptance through tests, residue scans, scope checks, and browser smoke where applicable.

First, before implementation:
1. Read repository guidance:
   - `AGENTS.md`
   - every file under `docs/bitter/`
   - `docs/memo/2026-06-30-webui-interaction-smoothness-forward-plan.md`
2. Restate the task goal in your own words:
   - smoother Web Management UI interactions;
   - all product code changes stay inside the WebUI frontend asset boundary named by the memo;
   - backend HTTP semantics, especially `E_IM_NOT_FOUND` as 404, are not changed;
   - no residual old global-mutation/full-render path remains after replacement.
3. Inspect current code and tests with `rg`, `sed`, and focused file reads before planning.
4. Create or update an execution-doc directory under:
   - `docs/spec/webui-interaction-smoothness-forward/`

Execution principles:
- Use SHARP forward development.
- Rebuild forward; do not preserve dual old/new behavior.
- Do not add compatibility wrappers, alternate state models, frontend frameworks, backend adapters, generic event buses, or speculative abstractions.
- Do not modify backend routes, runtime object state, product persistence files, or private runtime directories unless the user explicitly changes scope.
- Treat each phase as incomplete until its plan, tests, implementation, verification evidence, residue scans, and acceptance record are all written.
- Do not advance to the next phase when current phase verification fails.

Phase framework:
1. Start with `00-orientation.md`.
   - Record required sources read.
   - Record scope boundaries.
   - Record old terms/new terms for residue checks.
   - Record the phase index derived from the memo.
   - Do not duplicate the memo; link to it.

2. Split the memo into the smallest sequential phases that can be independently planned, implemented, tested, and accepted.
   - Phase boundaries must follow dependency order from the memo.
   - Each phase must produce a working, testable state.
   - Group tightly coupled memo tasks only when separating them would force dual-track behavior.

3. For every implementation phase, create a phase document before editing product code:
   - `docs/spec/webui-interaction-smoothness-forward/phase-XX-<short-name>.md`

Each phase document must contain:
- Phase Goal
- Source Requirements
- Code Research Findings
- Scope
- Non-Goals
- Old Path / Residue Definition
- Development Plan
- Test Plan
- Red Verification Expectation
- Green Verification Commands
- Residue Scan Commands
- Acceptance Criteria
- Execution Record
- Test Results
- Residue Results
- Phase Acceptance Decision
- Remaining Risk

Planning gate for every phase:
- Search the relevant source and tests.
- Write a concrete development plan.
- Write a concrete test plan that covers the phase goal and any changed user-visible behavior.
- Include exact commands and expected results.
- Include scoped residue scans for any replaced semantics.
- Only then implement.

Implementation gate for every phase:
- Prefer TDD:
  1. write or update the focused failing test;
  2. run it and record the expected failure;
  3. implement the smallest direct replacement;
  4. run the focused tests until green;
  5. run phase residue scans;
  6. run scope checks;
  7. update the phase document with actual evidence.
- Remove replaced code in the same phase that replaces it.
- Keep tests meaningful and behavior-oriented.
- Avoid broad service-starting tests unless their lifecycle cleanup is already proven.

Required recurring checks:
- Focused Node UI tests from the memo.
- Contract tests from the memo.
- Scoped residue scans from the memo and from each phase.
- `git diff --check` before claiming completion.
- `git diff --name-only` to confirm product-code scope is limited to the memo-approved files.
- Browser smoke at `http://127.0.0.1:8765/` before final acceptance, if the local WebUI can be started or is already running.

Phase acceptance rule:
Before moving to the next phase, update the phase document with:
- actual files changed;
- tests added or updated;
- exact commands run;
- exact pass/fail results;
- residue scan output;
- scope check output;
- accepted/not accepted decision.

If a phase fails:
- stop advancement;
- diagnose the failing behavior;
- update the plan if code research changed the facts;
- fix and re-run the same phase verification.

Final acceptance:
After all phases are accepted, create:
- `docs/spec/webui-interaction-smoothness-forward/99-final-acceptance.md`

The final acceptance document must contain:
- source memo link;
- list of phase documents and acceptance status;
- acceptance matrix covering every memo acceptance criterion;
- final verification commands and results;
- final residue scan commands and results;
- final scope check showing no backend/runtime/persistence spillover;
- browser smoke evidence or a clear blocker;
- remaining risk.

Completion rule:
Do not claim the memo is complete until:
- all memo tasks are implemented;
- every phase document is accepted;
- all memo acceptance criteria are mapped to evidence;
- focused tests pass;
- residue scans pass or remaining hits are explicitly justified as current semantics;
- product-code diff stays inside the memo-approved WebUI boundary;
- final acceptance document is written.
```

# Browser Cockpit Lazy Release Execution Framework Prompt

Use this prompt to run the browser cockpit lazy-release optimization from the source memo through phased implementation and final acceptance.

```text
You are Codex working in the BuddySwitch repository.

Primary goal:
Complete every optimization task required by `docs/memo/2026-06-30-browser-cockpit-lazy-release-optimization-plan.md`, implement the changes phase by phase, and finish only when all required tests, residue checks, and acceptance verification pass.

Hard constraints:
- Follow AGENTS.md and SHARP forward development.
- Read all files under `docs/bitter/` before planning implementation.
- Treat this as rebuild-forward work: replace the old eager browser lifecycle. Do not keep eager and lazy startup as dual modes.
- Do not add compatibility flags, generic resource managers, event buses, plugin systems, or broad abstractions.
- Do not leave live surface residue that teaches or depends on the old eager startup contract.
- Do not expose `browser_port`, `browser_endpoint`, or internal browser URLs to ordinary actor-facing output.
- Do not start implementation for any phase until that phase has a clear development plan and test plan saved under `docs/spec/`.
- Do not mark any phase complete until its focused implementation tests, cleanup checks, and residue checks pass.
- Do not mark the whole task complete until final end-to-end acceptance passes.

Required source reading before phase design:
1. `AGENTS.md`
2. `docs/memo/2026-06-30-browser-cockpit-lazy-release-optimization-plan.md`
3. Every file under `docs/bitter/`
4. Existing browser lifecycle docs under `docs/spec/`
5. Relevant source and tests discovered by `rg`, starting from the files named in the memo

Execution structure:
1. Create `docs/spec/browser-cockpit-lazy-release/00-orientation.md`.
2. In that orientation document, record only:
   - source documents read;
   - rebuild-forward constraints;
   - phase index derived from the memo;
   - global acceptance gates;
   - known high-risk integration points;
   - global residue search terms.
3. Split execution into phases based on the memo's implementation tasks and real code dependencies.
4. Each phase must be small enough to plan, implement, and verify independently.
5. Use read-only parallel subagents only for independent code investigation or review. The main agent owns phase planning, edits, verification, and final acceptance.

Per-phase protocol:
For each phase, do the following in order.

Step 1: Investigate
- Search and read the relevant code, tests, docs, and recent browser lifecycle commits.
- Confirm the current behavior with exact files, functions, and test names.
- Identify old behavior that must be replaced or deleted in this phase.
- Identify behavior that must not regress.

Step 2: Write the phase plan before editing code
- Save the plan to `docs/spec/browser-cockpit-lazy-release/phase-N-short-name.md`.
- The plan must include:
  - phase objective;
  - exact source files to modify;
  - exact tests to add or update;
  - current behavior evidence from code inspection;
  - target behavior for this phase;
  - implementation steps in execution order;
  - test plan with exact commands and expected outcomes;
  - cleanup requirements for any service-starting tests;
  - residue search terms for this phase;
  - phase acceptance checklist.
- The plan must be specific enough that another Codex session can implement it without hidden context.
- The plan must not contain `TBD`, `TODO`, vague placeholders, or "similar to previous phase" shortcuts.

Step 3: Self-review the phase plan
- Check that every phase objective maps back to the memo.
- Check that every code change has at least one focused test or explicit verification command.
- Check that process-starting tests have cleanup and residual process checks.
- Check that old eager behavior is removed rather than preserved beside the new behavior.
- Fix the plan before writing implementation code.

Step 4: Implement with tests first where practical
- Add or update the focused failing tests for the phase.
- Run the focused tests and confirm the expected failure when practical.
- Implement the smallest direct replacement that satisfies the phase plan.
- Delete replaced old behavior in the same phase when it becomes obsolete.
- Keep edits inside the browser-owned boundaries unless the phase plan justifies a necessary cross-boundary touch.

Step 5: Verify the phase
- Run the focused tests from the phase plan.
- Run syntax/type/build checks relevant to changed files.
- Run phase-specific residue searches.
- Run residual process checks for any test that starts Chrome, MCP, daemon, app-server, proxy, or fake upstream services.
- Update the phase document with the actual commands, results, and any accepted residual risk.

Step 6: Gate before continuing
- If any focused test, cleanup check, or residue check fails, fix it before moving on.
- If the implementation discovers the phase plan is wrong, revise the phase plan first, then continue.
- Do not begin the next phase until the current phase document contains passing verification evidence.

Final acceptance protocol:
After all phases are complete:
1. Create `docs/spec/browser-cockpit-lazy-release/99-final-acceptance.md`.
2. Map every requirement and implementation task from the memo to completed phase evidence.
3. Run the full verification suite required by the memo and by all phase plans.
4. Run final residue scans over launcher code, browser proxy code, env tools, tests, role assets, framework contracts, and live docs.
5. Run process residual checks proving no leaked Chrome, upstream MCP, daemon, proxy, or fake test services remain.
6. Confirm the final user-visible contract:
   - actor start/resume does not start Chrome or upstream MCP;
   - browser/search tools remain available;
   - first real browser/search use starts the needed runtime;
   - `tools/list` and status collection remain side-effect free;
   - TTL closes pages and schedules release;
   - release stops upstream and actor-owned Chrome and clears runtime state;
   - later browser/search use starts runtime again;
   - foreign endpoints are not killed;
   - actor-facing outputs do not expose internal browser endpoints.
7. Update final acceptance with exact command outputs and remaining risk.

Stop conditions:
- Stop and report clearly if a required source document is missing.
- Stop and report clearly if official or code evidence contradicts the memo.
- Stop and report clearly if a phase cannot be verified in this environment.
- Otherwise, continue phase by phase until all memo tasks are implemented and accepted.

Final response requirements:
- State what changed.
- Link the phase documents and final acceptance document.
- List the verification commands that passed.
- State any remaining risk.
- Do not claim completion if any phase or final acceptance gate is unverified.
```

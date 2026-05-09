# Runtime Command Contract Test Plan

**Goal:** Verify from product requirements that launcher-managed buddy instances use an executable runtime preflight contract and do not ask users for extra approval because the host tried to run a non-executable `scripts/turn_runtime.py prepare` command.

**Testing principle:** Tests must start from observable behavior and functional requirements. They should prove that the user-facing buddy path works, that active host-facing contracts are consistent, and that existing buddy boundaries remain intact. Do not write tests that merely match a private helper branch, a single implementation string, or a fixture chosen only to make the current code pass.

---

## Functional Requirements

FR1. A user may enter ordinary natural-language text in any buddy instance without adding runtime commands or permission hints.

FR2. Runtime preflight is an internal host step. It prepares context and must not execute the user's requested task.

FR3. The host-facing prepare invocation must be executable in the instance workspace without relying on file executable bits.

FR4. There is one canonical host-facing runtime command contract for prepare and persist.

FR5. Active buddy AGENTS remain short, framework-level runtime guidance. They must not contain business-specific examples or long payload recipes.

FR6. `prepare.runtime_context` or its equivalent runtime-returned surface is the source for executable command hints, capability boundaries, payload hints, and safe next actions.

FR7. Structured runtime errors and broker feedback must point to the canonical executable contract or a clear stop condition.

FR8. The fix must not introduce a compatibility wrapper, dual command contract, or approval workaround.

FR9. Dev buddy retains write access to `projects/app`; PM, Market, Design, and Test remain read-only against project source.

FR10. User text that starts with `switch ...` remains ordinary request text and must not change active buddy.

FR11. Launcher materialization must project the updated AGENTS/runtime guidance into product instances.

FR12. Historical notes may describe the old failure, but active host-facing surfaces must not instruct bare execution of `scripts/turn_runtime.py prepare` or `scripts/turn_runtime.py persist`.

FR13. The implementation must produce zero active residue of the old command contract: every old-command occurrence must be deleted, rewritten, or explicitly classified as historical-only retained.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
|---|---|---|
| FR1, FR2, FR3, FR4 | TG-01 Runtime Command Contract | Prepare command hint is executable and prepare does not perform task work |
| FR4, FR6, FR7 | TG-02 Runtime Context And Feedback | Runtime output and errors expose the canonical contract |
| FR5, FR12 | TG-03 AGENTS Host Instructions | Active AGENTS stay framework-level and avoid bare script execution |
| FR8, FR12, FR13 | TG-04 No Compatibility Drift | No wrapper, dual-path instruction, or active old-command residue is introduced |
| FR9, FR10 | TG-05 Existing Boundary Regression | Buddy capabilities and switch-prefixed text behavior remain unchanged |
| FR11 | TG-06 Launcher Instance Materialization | Product instances receive updated active instructions |
| FR1, FR3 | TG-07 Manual Main Path Probe | A representative ordinary request follows prepare without command-shape approval |

---

## TG-01 Runtime Command Contract

**Purpose:** Prove the public runtime contract provides an executable command path for host preflight and persist.

**Setup:**

- Run tests from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.
- Use product-mode-style environment fixtures already used by runtime tests.
- Use at least one representative buddy, then table-drive across all manifest buddies where cheap.

**Test cases:**

1. Prepare response exposes a canonical prepare command hint.
2. Prepare response exposes a canonical persist command hint.
3. The prepare command hint uses `python3 scripts/turn_runtime.py prepare`.
4. The persist command hint uses `python3 scripts/turn_runtime.py persist`.
5. Running `python3 scripts/turn_runtime.py --help` succeeds from the worktree.
6. Running prepare with ordinary text returns `ok=true` and preserves the original request text.
7. Prepare does not create or modify the user-requested project file for a request like "write manual acceptance".

**Assertions:**

- The command contract is present in runtime-returned data, not only in prose docs.
- The command is executable without relying on `scripts/turn_runtime.py` being mode `100755`.
- Prepare output contains context and run reservation data, but no evidence that the user task was performed.
- Persist command guidance points to `--context <context>` and `--result <result>` or the repo's equivalent canonical payload flow.

**Anti-cheat guard:**

- Do not test only a private constant. At least one assertion must inspect the public prepare JSON returned by the CLI or public runtime function.

## TG-02 Runtime Context And Structured Feedback

**Purpose:** Prove runtime context and errors guide the host with executable next steps or explicit stop conditions.

**Test cases:**

1. Normal prepare includes runtime command hints in `prepare.runtime_context` or the chosen public runtime surface.
2. Product-mode broker unavailable prepare failure returns `ok=false`.
3. Product-mode broker unavailable persist failure returns `ok=false`.
4. Market evidence broker unavailable failure returns `ok=false` if evidence tooling has command feedback.
5. Persist rejection for a disallowed buddy action returns a permission boundary and safe next action.

**Assertions:**

- Recoverable command hints use `python3 scripts/turn_runtime.py ...`.
- Non-recoverable product-mode broker failures include a stop condition such as "stop and report".
- Feedback does not tell the host to bypass the broker, write raw BuddySwitch state, or retry by granting sandbox approval.
- Existing error codes and permission boundary meanings remain stable unless the implementation deliberately updates the public contract.

**Anti-cheat guard:**

- The test should validate behavior through returned JSON shape and semantics. It must not pass solely because an exact long error string was copied into the implementation.

## TG-03 AGENTS Host Instructions

**Purpose:** Prove active buddy AGENTS remain concise framework-level instructions and no longer carry the broken bare command contract.

**Scope:**

- `tools/launcher/assets/buddies/pm/AGENTS.md`
- `tools/launcher/assets/buddies/market/AGENTS.md`
- `tools/launcher/assets/buddies/design/AGENTS.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tools/launcher/assets/buddies/test/AGENTS.md`

**Assertions:**

- Each AGENTS file identifies the locked active buddy behavior.
- Each AGENTS file says to run runtime preflight before skill work.
- Each AGENTS file points the host to runtime context and structured feedback.
- No AGENTS file contains active instruction text that runs bare `scripts/turn_runtime.py prepare`.
- No AGENTS file contains active instruction text that runs bare `scripts/turn_runtime.py persist`.
- No AGENTS file contains business-specific examples such as demo pages, landing pages, calendar apps, competitor scans, or request-specific payload recipes.
- Buddy-specific wording is limited to durable capability boundaries, such as Dev project write access or non-Dev read-only project access.

**Anti-cheat guard:**

- Do not assert a full-file snapshot. Assert the behavioral constraints so the AGENTS can stay concise while wording evolves.

## TG-04 No Compatibility Drift

**Purpose:** Prove the implementation replaced the broken contract instead of layering around it, and prove zero active residue of the old contract.

**Test cases:**

1. Search active host-facing surfaces for bare `scripts/turn_runtime.py prepare`.
2. Search active host-facing surfaces for bare `scripts/turn_runtime.py persist`.
3. Search launcher assets and runtime feedback for dual-path wording such as "use either".
4. Check the implementation did not add a new wrapper whose only purpose is to preserve the old bare command.
5. Build a residue inventory for every remaining old-command string found in searched scopes.
6. Classify each residue inventory row as `deleted`, `rewritten`, or `historical-only retained`.

**Assertions:**

- Active host-facing files do not instruct bare script execution.
- Canonical command guidance is singular and uses `python3 scripts/turn_runtime.py`.
- Historical memo text may mention the old command only as a past failure, not as current guidance.
- Tests do not require `chmod +x scripts/turn_runtime.py` as success criteria.
- No residue inventory row is classified as `active retained`, `compatibility retained`, or `dual path retained`.
- Historical-only retained rows are outside runtime execution, launcher materialization, validators, and current runbooks.

**Anti-cheat guard:**

- Do not make this a repo-wide ban on every historical string. Scope it to active host-facing surfaces so history can remain accurate.
- Do not satisfy this group by excluding broad directories without classification. The test must make active-surface scope explicit and review every old-command match in that scope.

## TG-05 Existing Boundary Regression

**Purpose:** Prove the command contract fix does not change buddy semantics.

**Test cases:**

1. Dev prepare context still reports writable project source boundary for `projects/app`.
2. PM prepare context still reports read-only project source boundary.
3. Market prepare context still reports read-only project source boundary and evidence requirements.
4. Design prepare context still reports read-only project source boundary and Dev handoff expectation for source changes.
5. Test prepare context still reports read-only project source boundary and Dev handoff expectation for source fixes.
6. `switch market: do competitor scan` entered in a Dev instance remains ordinary request text and active buddy remains Dev.
7. `switch dev: write file` entered in a PM instance remains ordinary request text and active buddy remains PM.

**Assertions:**

- Active buddy comes from launcher/product session metadata, not request text.
- Request text is preserved.
- Capability boundaries remain aligned with manifest/env profile.
- The command contract change does not widen project write access.

**Anti-cheat guard:**

- Use functional buddy scenarios and public prepare output. Do not validate only `_derive_track_id` or other private string cleanup helpers.

## TG-06 Launcher Instance Materialization

**Purpose:** Prove a newly opened product instance receives the updated active instructions.

**Flow:**

1. Start or materialize a test instance for at least Dev and one read-only buddy.
2. Inspect the instance workspace AGENTS content produced by launcher assets.
3. Confirm the runtime command contract visible to the host matches the canonical contract.
4. Confirm the instance does not carry a stale workspace `.codex/config.toml` that overrides launcher-managed config behavior.

**Assertions:**

- Materialized AGENTS do not instruct bare `scripts/turn_runtime.py prepare`.
- Materialized AGENTS point to runtime context and structured feedback.
- The launcher-managed instance path is used, not the main checkout.
- Existing config neutralization behavior remains intact.

**Anti-cheat guard:**

- Do not inspect only source templates. The test must prove materialized instance output when launcher behavior is touched.

## TG-07 Manual Main Path Probe

**Purpose:** Provide an observable end-to-end sanity check for the user-facing symptom when UI automation cannot directly assert the Codex approval popup.

**Probe request:**

```text
请在 projects/app/manual-acceptance-dev.md 写入 manual acceptance，然后读取确认
```

**Expected flow:**

1. Host runs canonical prepare preflight.
2. Prepare returns runtime context for Dev.
3. Host/skill performs the file write and readback.
4. Host persists the result through canonical persist.
5. Final response contains receipt and summary.

**Observable proof:**

- The prepare command shape is `python3 scripts/turn_runtime.py prepare ...`.
- No command-shape approval is needed for preflight.
- The file write occurs during skill execution, not during prepare.
- Persist succeeds or returns a structured runtime error unrelated to bare script execution.

**Anti-cheat guard:**

- This manual probe is not a substitute for automated tests. It is a final product-path confirmation for the approval-popup symptom.

---

## Required Verification Commands

Run the focused test suites affected by the contract:

```bash
python3 -m pytest tests/test_turn_runtime.py
python3 -m pytest tests/test_runtime_agents.py
python3 -m pytest tests/test_repo_consistency.py
```

Run launcher tests if materialization code or assets changed:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py
```

Run command proofs:

```bash
python3 scripts/turn_runtime.py --help
python3 scripts/turn_runtime.py prepare "simple ordinary request"
```

Run active-surface inspection:

```bash
rg '(^|[^a-zA-Z0-9_./-])scripts/turn_runtime\.py (prepare|persist)' tools framework scripts tests README.md docs/spec
```

Review any matches and classify them as active instruction, historical description, or test assertion. Active instructions must use the canonical executable contract.

Record the classification in a residue inventory:

| File | Occurrence | Classification | Required result |
|---|---|---|---|
| `path/to/file` | `scripts/turn_runtime.py prepare` | active instruction | deleted or rewritten |
| `path/to/memo` | `scripts/turn_runtime.py prepare` | historical-only | retained only if not consumed by active checks |

## Passing Criteria

- Public runtime output exposes canonical executable command guidance.
- Active AGENTS no longer instruct bare script execution.
- Structured feedback either gives canonical executable hints or clear stop conditions.
- Existing buddy permission boundaries and switch-prefixed text behavior remain intact.
- Launcher materialization reflects updated AGENTS/runtime guidance.
- Residue inventory has no active retained old-command contract.
- Tests are requirement-driven and cannot pass merely by matching one private helper or preserving a compatibility shim.

## Explicitly Invalid Test Designs

- A test that only checks `os.access("scripts/turn_runtime.py", X_OK)` or chmod behavior.
- A test that only asserts a private constant equals a hardcoded string.
- A snapshot test over full AGENTS files that makes prompt wording brittle without proving behavior.
- A test that passes because both old and new command forms are accepted.
- A test that embeds a business-specific prompt example as the core proof.
- A test that ignores product-mode materialization when launcher assets are changed.
- A test that treats a historical memo mention of the old command as an active contract failure.
- A test that hides old-command matches by excluding whole active directories instead of classifying the matches.

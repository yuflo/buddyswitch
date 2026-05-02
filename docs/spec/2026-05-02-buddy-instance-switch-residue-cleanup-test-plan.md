# Buddy Instance Switch Residue Cleanup Test Plan

## 1. Product Requirement Framing

This test plan starts from product behavior, not current implementation details.

The product requirement is:

> In a buddy instance, the user experiences a normal focused product turn. They do not need to know, type, copy, see, or benefit from any historical `switch <buddy>...:` wire syntax.

The runtime requirement is:

> Product turn state is prepared from launcher-bound instance metadata and ordinary `request_text`, then persisted through exactly one selected skill result. No historical parser or router participates in the product path.

## 2. Functional Requirements

| ID | Requirement | Product Meaning |
| --- | --- | --- |
| FR-01 | Ordinary user text starts a product turn | A user can type a normal request in a buddy instance and get a persisted result. |
| FR-02 | Active buddy comes from the instance | User text cannot change the active buddy, route to another buddy, or infer task/track from command syntax. |
| FR-03 | No user-facing historical wire | Active prompts, terminal guidance, docs, and Context Panel must not teach command-shaped routing. |
| FR-04 | No hidden product dependency on historical parser/router | Product prepare/persist still works when debug parser/router files are absent. |
| FR-05 | Command-shaped legacy input is not accepted as workflow | If a user pastes an old command-shaped input, the product fails closed before state mutation instead of routing or polluting task content. |
| FR-06 | Natural language containing "switch" remains valid | A normal request such as "Help users switch plans" must not be rejected. |
| FR-07 | Exactly one skill result is persisted per turn | Multi-skill orchestration or cross-buddy routing is not introduced. |
| FR-08 | Structured state drives summary and panel | Receipt, run audit, task, artifact, and panel data come from structured fields, not parsed command text. |
| FR-09 | Main checkout stays clean | Buddy instance runtime state must not write product run state into the source checkout. |

## 3. Coverage Matrix

| Requirement | Unit Tests | Integration Tests | Product Smoke | Static Guardrails |
| --- | --- | --- | --- | --- |
| FR-01 | UT-01, UT-02 | IT-01, IT-02 | PS-01 | SG-01 |
| FR-02 | UT-03, UT-04 | IT-03 | PS-02 | SG-02 |
| FR-03 | UT-08 | IT-05 | PS-01 | SG-03 |
| FR-04 | UT-07 | IT-04 | PS-01 | SG-04 |
| FR-05 | UT-05 | IT-03 | PS-02 | SG-01 |
| FR-06 | UT-06 | IT-02 | PS-03 | SG-01 |
| FR-07 | UT-09 | IT-06 | PS-01 | SG-05 |
| FR-08 | UT-10 | IT-07 | PS-04 | SG-06 |
| FR-09 | UT-11 | IT-08 | PS-05 | SG-07 |

## 4. Unit Test Design

### UT-01: Ordinary Request Prepares Turn Context

**Requirement:** FR-01, FR-02

Setup:

- Start test runtime with product-mode env for buddy `pm`.
- Instance metadata has no current task or track.
- Input: `Draft the MVP PRD for onboarding rewrite`.

Assertions:

- `ok=true`.
- `active_buddy=pm`.
- `request_text` equals the exact input.
- `current_task_id` is created.
- `run_envelope.status=reserved`.
- A task file exists in runtime state.
- A reservation file exists for the returned run id.

Anti-cheat rule:

- Do not mock the prepare function.
- Do not assert on a private helper name.

### UT-02: Existing Instance Binding Is Reused

**Requirement:** FR-01, FR-02

Setup:

- Product-mode env for buddy `pm`.
- Instance metadata already has `current_task_id` and `current_track_id`.
- Input: `Continue the onboarding PRD`.

Assertions:

- Returned context keeps the existing task and track.
- User text is not parsed for task or track identifiers.
- No new unrelated task is created.

### UT-03: User Text Cannot Change Buddy

**Requirement:** FR-02

Setup:

- Product-mode env locks buddy to `pm`.
- Input contains another buddy name in natural language, for example `Ask dev later to implement this after PRD approval`.

Assertions:

- `active_buddy` remains `pm`.
- No `dev` task is created.
- Persist accepts only a skill from the current `pm` context.

### UT-04: Command-Shaped Legacy Input Fails Closed

**Requirement:** FR-05

Inputs:

- `switch pm: Draft the PRD`
- `switch dev: Implement the PRD`
- `switch dev(task-a) -> track-a: Implement the PRD`

Assertions for each input:

- Command returns `ok=false`.
- Error is before mutation.
- No new task, artifact, run audit, or reservation is written.
- Active instance metadata is unchanged.

Anti-cheat rule:

- Do not only check the error message. Verify no side-effect files were created.

### UT-05: Natural Language Word "switch" Is Accepted

**Requirement:** FR-06

Input:

```text
Help users switch plans without losing draft data
```

Assertions:

- `ok=true`.
- `request_text` is preserved exactly.
- A normal task and reserved run are created.
- No command-syntax error appears.

### UT-06: Debug Parser Absence Does Not Break Product Prepare

**Requirement:** FR-04

Setup:

- Remove debug parser/router from import path or monkeypatch any attempted import to raise.
- Product-mode env is valid.
- Input is ordinary request text.

Assertions:

- Prepare succeeds.
- Test proves no debug parser/router was called.

Anti-cheat rule:

- The test should fail if product prepare imports or calls debug parser/router.

### UT-07: Persist Accepts Exactly One Skill

**Requirement:** FR-07

Setup:

- Prepare a valid turn context.
- Use one valid skill id from `turn_context.skills`.

Assertions:

- Missing `skill_id` fails with no writes.
- Array or multi-skill payload fails with no writes.
- Skill id outside current context fails with no writes.
- One valid skill id plus schema-valid result succeeds.

### UT-08: Persist Rejects Tampered Turn Identity

**Requirement:** FR-02, FR-08

Tamper cases:

- Change `active_buddy`.
- Change `current_task_id`.
- Change `run_envelope.run_id`.
- Change `request_text`.

Assertions:

- Persist rejects each tampered context.
- No artifact or run audit is written.

### UT-09: Structured Receipt Contract

**Requirement:** FR-08

Assertions after successful persist:

- Top-level response contains `ok`, `receipt`, and `refreshed_context`.
- `receipt` includes `task_id`, `run_id`, `skill_id`, `receipt_paths`, and `next_state`.
- `receipt_paths` files exist.
- No command-shaped follow-up field exists.

### UT-10: Context Panel Projection Uses Structured State

**Requirement:** FR-08

Setup:

- Create a task, artifact, and run audit through prepare/persist.
- Build workspace projection.

Assertions:

- Projection contains the task, artifact, and run audit.
- UI-facing next state comes from structured fields.
- There is no command-derived next step.

### UT-11: Runtime State Writes Stay In Instance/Shared State

**Requirement:** FR-09

Setup:

- Product-mode instance workspace points to shared runtime state.
- Main source checkout is separate.

Assertions:

- Product run state appears under the instance/shared runtime state.
- Main source checkout does not receive runtime task/artifact/run files.

## 5. Integration Test Design

### IT-01: Complete Product Turn Persists Result

Flow:

1. Prepare turn context from ordinary request.
2. Select one valid skill from returned context.
3. Produce schema-valid result.
4. Persist.

Assertions:

- `receipt.run_id` equals the prepared run id.
- Task contains that run id.
- Artifact `source_run_id` equals that run id.
- Run audit references task, artifact, active buddy, and skill id consistently.

### IT-02: Natural Language "switch" Full Path

Input:

```text
Help users switch plans without losing draft data
```

Assertions:

- Full prepare -> persist path succeeds.
- Final task title/content reflects the product request, not a command route.
- Context Panel projection includes the persisted result.

### IT-03: Legacy Command-Shaped Input Has No Side Effects

Input:

```text
switch dev: Draft onboarding PRD
```

Assertions:

- Prepare rejects before reservation.
- No task/artifact/run audit is created.
- Current instance buddy remains unchanged.
- A subsequent ordinary request still succeeds.

### IT-04: Product Path Works With Debug Files Deleted

Setup:

- Run after deleting `scripts/debug/parse_switch.py` and `scripts/debug/codex_router.py`.

Assertions:

- Prepare and persist still pass.
- Manifest loading still works.
- Skill selection still comes from buddy/skill definitions.

### IT-05: Generated Instance Prompt Is Clean

Flow:

1. Start a disposable `pm` instance.
2. Inspect generated root `AGENTS.md`.

Assertions:

- Prompt includes locked buddy, ordinary request, prepare, exactly-one-skill, persist, and `Receipt -> Summary`.
- Prompt does not include legacy wire syntax, parser names, router names, or command examples.

### IT-06: Multi-Skill Buddy Does Not Auto-Orchestrate

Setup:

- Use a buddy with multiple skills.
- User request contains multiple goals.

Assertions:

- Prepare returns multiple eligible skills.
- Persist requires exactly one selected skill.
- No automatic multi-skill sequence or cross-buddy dispatch occurs.

### IT-07: Context Panel Shows Persisted Result From Instance Workspace

Flow:

1. Complete a product turn in an instance workspace.
2. Start `python3 scripts/serve_context_panel.py` from that same instance workspace.
3. Read `/api/workspace`.

Assertions:

- API returns the new task, artifact, and run audit.
- Running the panel from the source worktree is not accepted as proof for instance data.

### IT-08: Main Worktree Isolation

Flow:

1. Complete product turn in runtime instance.
2. Check `git status --short` in `/Users/chen/Dev/buddyswitch`.
3. Check `git status --short` in `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.

Assertions:

- Main checkout is not polluted by runtime state.
- Development worktree only contains intentional source/doc changes.

## 6. Static Guardrail Tests

### SG-01: Active Product Paths Do Not Contain Legacy Wire Syntax

Scan active paths:

- `tools/launcher/assets`
- `scripts`
- `buddyswitch/manifest.toml`
- `README.md`
- `framework/docs`
- `framework/contracts`
- `framework/console`

Forbidden patterns:

- `switch <buddy>`
- `switch pm:`
- `switch dev:`
- `switch market:`
- `switch design:`
- `switch test:`
- `_parse_wire_switch`
- `_STRUCTURAL_SWITCH_PATTERN`
- `WIRE_SYNTAX`
- `parse_switch.py`
- `codex_router.py`
- `switch-grammar`

Allowed:

- The product name `BuddySwitch`.
- Historical dated plans under `docs/spec` when not used as active runtime guidance.

### SG-02: Manifest Has No Runtime Adapter For Legacy Router

Assertions:

- No `[[adapters]]` entry points to parser/router files.
- Skills and buddies remain valid.

### SG-03: Prompt Assets Do Not Teach Historical Commands

Assertions:

- Every buddy prompt starts with `# BuddySwitch Runtime Workspace`.
- Every buddy prompt states ordinary requests belong to the locked buddy.
- No buddy prompt contains legacy wire examples or parser/router names.

### SG-04: Runtime Code Does Not Import Debug Parser

Assertions:

- Product runtime and runtime kernel do not import `parse_switch`, `codex_router`, or debug router modules.
- Product runtime contains no structural wire regex.

### SG-05: Contract Files Are Turn-Oriented

Assertions:

- Active contracts refer to turn context and persist result.
- No active `switch-grammar.json` remains.

### SG-06: Console Does Not Parse Commands

Assertions:

- Console JS does not include command parsing regexes.
- Console display derives next state from structured projection fields.

### SG-07: Test Fixtures Do Not Smuggle Old Workflow Back

Assertions:

- Product-path tests use ordinary requests as normal fixtures.
- Legacy command-shaped inputs appear only in negative tests that assert rejection and no writes.

## 7. Manual Product Acceptance

### PS-01: Happy Path

1. Start a fresh instance:

```bash
./buddyswitch-codex instance start --buddy pm
```

2. Enter:

```text
Draft the MVP PRD for onboarding rewrite
```

Expected:

- No instruction tells the user to add structural syntax.
- One skill is selected.
- Result is persisted.
- Final output is `Receipt -> Summary`.

### PS-02: Legacy Input Rejection

Input:

```text
switch dev: Draft onboarding PRD
```

Expected:

- Rejected before state mutation.
- Message says to use an ordinary request in the current buddy instance.
- No cross-buddy routing occurs.

### PS-03: Natural Language "switch" Request

Input:

```text
Help users switch plans without losing draft data
```

Expected:

- Accepted as a normal request.
- Persisted under the current buddy.

### PS-04: Context Panel Acceptance

1. From the same instance workspace, run:

```bash
python3 scripts/serve_context_panel.py --port 8767
```

2. Open `/api/workspace` or refresh the panel.

Expected:

- The persisted task/artifact/run audit is visible.
- The panel does not display command-derived next steps.

### PS-05: Worktree Isolation

After manual smoke:

```bash
git status --short
```

Expected:

- Main checkout has no runtime pollution.
- `dev0210` contains only intended source/doc changes.

## 8. Required Test Commands

Focused tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_integration.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_parallel_contracts.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py -q
```

Active residue scan:

```bash
rg -n "\\bswitch\\s+<buddy>|\\bswitch\\s+[a-z][a-z0-9-]*\\s*:|_parse_wire_switch|_STRUCTURAL_SWITCH_PATTERN|WIRE_SYNTAX|switch-grammar|parse_switch\\.py|codex_router\\.py" \
  tools/launcher/assets scripts buddyswitch/manifest.toml README.md framework/docs framework/contracts framework/console tests \
  -S
```

Expected:

- Focused tests pass.
- Active residue scan has no matches except negative-test cases explicitly asserting rejection.

## 9. Completion Bar

The cleanup is accepted only when:

- Ordinary product turn works end-to-end.
- Legacy command-shaped input cannot route or mutate state.
- Natural-language "switch" requests still work.
- Active prompts/docs/runtime/manifest/console have no historical wire residue.
- Product runtime does not import or define historical parser/router logic.
- Context Panel shows structured persisted state from the instance workspace.
- Tests prove behavior through runtime outputs and state files, not private helper names.

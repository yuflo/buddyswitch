# No-Switch Buddy Instance Single-Turn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make buddy-locked product-mode instances accept ordinary conversation as the only user-facing task assignment path for a single turn, with no user-visible `switch` command.

**Architecture:** Product mode should resolve a user request from the launcher-bound buddy identity, not from user-authored `switch` syntax. Keep the canonical switch parser only as an internal/debug wire tool for non-product-mode commands. Hide existing switch-shaped recovery fields from product UX first; migrate/delete those internal fields in a later cleanup slice.

**Tech Stack:** Python runtime scripts and unittest/pytest tests, Bash launcher, static HTML/CSS/JS console, Markdown prompt/docs/skill assets.

---

## Target Outcome

A user can run:

```bash
./buddyswitch-codex instance start --buddy pm
```

Then, inside that buddy instance, the user assigns one task by ordinary conversation:

```text
Draft the MVP PRD for onboarding rewrite
```

The runtime must resolve that request as a `pm` task, reserve one run, expose eligible `pm` skills, and persist normally after the selected skill runs. The user must not type, copy, or see `switch pm:` as the product-mode task assignment mechanism.

## Current Bottleneck

Buddy instances already carry the active buddy in environment and instance state, but the codebase still treats `switch` as the product UI:

- `scripts/switch_runtime.py` adapts plain text by constructing a canonical `switch ...` string, and product mode still accepts same-buddy structural switches.
- `tools/launcher/assets/buddies/*/AGENTS.md`, `tools/launcher/assets/runtime-AGENTS.md`, README, framework docs, skill examples, and console UI still teach copyable `switch` commands.
- `reference_switches` and `recommended_switch` are still persisted and projected as command strings.

The first bottleneck is not parser capability. It is the product contract: buddy instance task assignment must be ordinary text only.

## Scope

### In This First Slice

- Product-mode ordinary text resolves one single-turn buddy task.
- Product mode rejects structural `switch <buddy>...:` input, including same-buddy input.
- Natural language containing the word `switch` remains valid when it is not structural command syntax.
- Product prompts/docs/console/final-output guidance stop presenting copyable `switch` commands.
- Existing internal persisted `switch`, `reference_switches`, and `recommended_switch` fields stay in place but are treated as debug/internal state, not user UX.
- Tests prove behavior through observable runtime outputs and state, not by asserting a private implementation rewrite string.

### Out Of Scope For This Slice

- Multi-turn natural-language continuation.
- Replacing `reference_switches` / `recommended_switch` schema fields with `next_task_ref` / `next_buddy_ref`.
- Deleting `parse_switch.py`, `switch-grammar.json`, or `codex_router.py`.
- Deleting `_legacy_resolve_switch` and packet-era run-instruction helpers.
- Redesigning track handoff semantics.

These are follow-up cleanup tasks after the single-turn no-switch path is proven.

## Non-Negotiable Test Principles

Tests must be written from product behavior, not from implementation tricks.

- Do not write tests that only check whether `_adapt_resolve_text_for_product_session()` builds a specific string.
- Do not mock `resolve_switch()` in the main no-switch acceptance tests.
- Do not make success depend on a private helper name or exact internal synthetic command format.
- Do assert externally meaningful effects: exit code, JSON response contract, created task object, reserved run, active buddy, demand preservation, and instance binding.
- Do assert absence of user-visible `switch` instructions in active product prompts/docs/console UI.
- Do preserve internal/debug parser tests separately so canonical wire tools remain available outside product mode.

## File Responsibility Map

- `scripts/switch_runtime.py`
  Product-mode input boundary. It should reject structural `switch` input in buddy instances and resolve ordinary text from active buddy session metadata.

- `tests/test_switch_runtime.py`
  Runtime behavior tests for product-mode plain request resolution, structural switch rejection, reservation creation, and invalid env fail-closed behavior.

- `tools/launcher/assets/buddies/*/AGENTS.md`
  Buddy-specific runtime prompts. They must state that ordinary requests belong to the locked buddy and must not say same-buddy `switch` commands are allowed.

- `tools/launcher/assets/runtime-AGENTS.md`
  Generic runtime prompt used outside buddy-specific product mode. It must describe `switch` only as internal/debug wire syntax, not product UI.

- `.codex/agents/router.toml`
  Development/debug router prompt. It must not present `switch` as product-mode user UX.

- `README.md`
  Main docs. Product-mode usage must show ordinary conversation inside a buddy instance; debug parser/router examples must be isolated under a debug section.

- `framework/docs/switch-spec.md`
  Rename/reframe as internal wire spec, or clearly mark as debug/internal. Product-mode plain request contract must be primary.

- `framework/docs/architecture-overview.md`
  Update architecture language so canonical wire is not the user-facing entrypoint.

- `framework/docs/skill-architecture-best-practices.md`
  Update skill guidance examples from `switch <buddy>:` to ordinary task requests scoped by active buddy instance.

- `buddyswitch/skills/**/SKILL.md`
  Replace examples that teach `switch pm:` / `switch dev:` / etc. with plain-language examples.

- `framework/console/index.html`
  Replace the “Next Commands” panel title and purpose.

- `framework/console/app.js`
  Remove copyable switch command rendering from user-facing UI. Render state-oriented next-step information instead.

- `tests/test_console_app_contract.py`
  Replace command-derivation tests with state-summary tests.

- `tests/test_repo_consistency.py`
  Add guardrails preventing product prompts/docs/console from reintroducing user-facing `switch` guidance.

## Implementation Tasks

### Task 1: Product-Mode Plain Request Contract

**Files:**
- Modify: `scripts/switch_runtime.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add behavior-first failing tests for product-mode ordinary requests**

Add tests that call `_cmd_resolve()` without mocking `resolve_switch()`. These tests may use `RuntimeWorkspaceTestMixin` because the functional contract includes runtime state writes. The tests must assert behavior, not private string rewriting.

Required tests:

```python
def test_product_mode_plain_text_creates_single_turn_task_and_reserved_run(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-pm-plain-real")
    env = self._product_env("pm", "inst-pm-plain-real", instance_json)

    with patch.dict(os.environ, env, clear=True):
        exit_code, payload = self._run_cmd_resolve("Draft the MVP PRD for onboarding rewrite")

    self.assertEqual(exit_code, 0)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["buddy"]["id"], "pm")
    self.assertEqual(payload["switch"]["buddy_id"], "pm")
    self.assertEqual(payload["switch"]["demand"], "Draft the MVP PRD for onboarding rewrite")
    self.assertIsInstance(payload["switch"]["task_id"], str)
    self.assertIsInstance(payload["run_envelope"]["run_id"], str)
    self.assertEqual(payload["run_envelope"]["status"], "reserved")

    task_path = self._runtime_path(f"buddyswitch/objects/tasks/{payload['switch']['task_id']}.json")
    reservation_path = switch_runtime._reserved_run_path(payload["run_envelope"]["run_id"])
    self.assertTrue(task_path.exists())
    self.assertTrue(reservation_path.exists())

    stored_instance = json.loads(instance_json.read_text(encoding="utf-8"))
    self.assertEqual(stored_instance["current_task_id"], payload["switch"]["task_id"])
```

```python
def test_product_mode_plain_text_with_word_switch_is_demand_not_command(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-pm-natural-switch")
    env = self._product_env("pm", "inst-pm-natural-switch", instance_json)

    with patch.dict(os.environ, env, clear=True):
        exit_code, payload = self._run_cmd_resolve("Help users switch plans without losing draft data")

    self.assertEqual(exit_code, 0)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["switch"]["buddy_id"], "pm")
    self.assertEqual(payload["switch"]["demand"], "Help users switch plans without losing draft data")
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests -q
```

Expected before implementation: at least the ordinary real-resolve test passes only if current behavior already works; structural rejection tests from Step 2 should fail until implementation.

- [ ] **Step 2: Replace same-buddy acceptance test with structural switch rejection tests**

Replace `test_cmd_resolve_product_mode_allows_canonical_switch_for_active_buddy` with behavior tests:

```python
def test_product_mode_rejects_structural_switch_for_active_buddy(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-pm-reject-same-buddy")
    env = self._product_env("pm", "inst-pm-reject-same-buddy", instance_json)

    with patch.dict(os.environ, env, clear=True):
        exit_code, payload = self._run_cmd_resolve("switch pm: Draft the PRD")

    self.assertEqual(exit_code, 1)
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["error"]["code"], "E_RUNTIME_RESOLVE")
    self.assertIn("ordinary request", payload["error"]["message"].lower())
    self.assertFalse(list(self._runtime_path("buddyswitch/objects/tasks").glob("*.json")))
```

```python
def test_product_mode_rejects_structural_switch_for_other_buddy_without_writes(self) -> None:
    instance_json = self._write_instance_json(instance_id="inst-pm-reject-other-buddy")
    env = self._product_env("pm", "inst-pm-reject-other-buddy", instance_json)

    with patch.dict(os.environ, env, clear=True):
        exit_code, payload = self._run_cmd_resolve("switch dev: Implement the PRD")

    self.assertEqual(exit_code, 1)
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["error"]["code"], "E_RUNTIME_RESOLVE")
    self.assertIn("locked buddy instance", payload["error"]["message"].lower())
    self.assertFalse(list(self._runtime_path("buddyswitch/objects/tasks").glob("*.json")))
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests -q
```

Expected before implementation: same-buddy structural rejection fails because current code allows it.

- [ ] **Step 3: Implement product-mode structural switch rejection**

Change `_adapt_resolve_text_for_product_session()` so structural switch input raises before calling `resolve_switch()`, regardless of requested buddy.

Implementation rule:

```python
structural_switch = _match_structural_switch(trimmed)
if structural_switch:
    requested_buddy = structural_switch.group(1).strip().lower()
    raise ValueError(
        "Locked buddy instance accepts ordinary requests only; "
        f"received structural switch command for '{requested_buddy}'. "
        f"Open the '{requested_buddy}' buddy instance instead when that is the intended owner."
    )
```

Keep `_build_plain_text_switch()` for this slice as an internal bridge to the existing resolve path. Do not expose it in docs or prompts.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests -q
```

Expected after implementation: all product-mode input tests pass.

### Task 2: Product Prompts And Final Output Contract

**Files:**
- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `.codex/agents/router.toml`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add repo-consistency tests for active product prompts**

Add tests that scan active product prompt assets and fail if they reintroduce product-mode switch UX.

Behavioral guardrails:

```python
def test_buddy_prompts_do_not_allow_user_facing_switch_commands(self) -> None:
    manifest = env_manifest.load_manifest(ROOT / "buddyswitch" / "manifest.toml")
    for buddy in manifest["buddies"]:
        buddy_id = buddy["id"]
        path = ROOT / "tools" / "launcher" / "assets" / "buddies" / buddy_id / "AGENTS.md"
        text = path.read_text(encoding="utf-8").lower()
        self.assertIn("ordinary user requests", text)
        self.assertNotIn("same-buddy canonical", text)
        self.assertNotIn("switch " + buddy_id, text)
        self.assertNotIn("receipt -> commands -> summary", text)
        self.assertIn("receipt -> summary", text)
```

```python
def test_runtime_prompt_does_not_present_switch_as_product_ui(self) -> None:
    text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(encoding="utf-8").lower()
    self.assertNotIn("canonical ui", text)
    self.assertNotIn("use the canonical directive", text)
    self.assertIn("internal/debug wire", text)
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompts_do_not_allow_user_facing_switch_commands tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_prompt_does_not_present_switch_as_product_ui -q
```

Expected before prompt edits: fail.

- [ ] **Step 2: Update buddy prompt assets**

For each `tools/launcher/assets/buddies/<buddy>/AGENTS.md`:

- State that ordinary user requests belong to the locked buddy.
- State that structural `switch <buddy>...:` commands are not product-mode input.
- Keep canonical loop commands as host/runtime tool calls: `scripts/switch_runtime.py resolve` and `scripts/switch_runtime.py persist`.
- Replace `Receipt -> Commands -> Summary` with `Receipt -> Summary`.
- Remove “Same-buddy canonical switches are allowed.”

Example target wording:

```markdown
Inside this session, ordinary user requests belong to `pm`. Do not ask the user to prefix product-mode requests with `switch pm:`. Structural `switch <buddy>...:` commands are not product-mode input; ask the user to use ordinary task language in this locked buddy instance.
```

Run the prompt consistency test from Step 1.

- [ ] **Step 3: Update generic runtime prompt and router prompt**

In `tools/launcher/assets/runtime-AGENTS.md`, demote canonical switch syntax to an internal/debug section. Product mode should lead with:

```markdown
## Product-Mode Input

In a launcher-managed buddy instance, ordinary user requests are the task assignment input. The active buddy comes from launcher session metadata, not from user-authored command syntax.
```

In `.codex/agents/router.toml`, remove product-mode command language and describe `switch` as debug/internal wire routing only.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist_for_every_manifest_buddy tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_prompt_does_not_present_switch_as_product_ui -q
```

Expected after edits: pass.

### Task 3: Console UI Removes Copyable Switch Commands

**Files:**
- Modify: `framework/console/index.html`
- Modify: `framework/console/app.js`
- Test: `tests/test_console_app_contract.py`

- [ ] **Step 1: Replace command derivation contract tests with state-oriented tests**

The console should not generate copyable `switch` commands. Replace command tests with state-summary tests that derive next-state labels from track/task/run data.

Example test intent:

```python
def test_track_next_step_summary_uses_state_not_switch_command(self) -> None:
    track_payload = {
        "id": "track-alpha",
        "current_buddy": "dev",
        "next_buddy": "market",
        "task_ids": ["task-dev"],
        "tasks": [{"id": "task-dev", "buddy": "dev", "artifact_ids": ["artifact-dev"], "run_ids": ["run-dev-1"]}],
    }
    workspace_payload = {
        "tracks": [track_payload],
        "tasks": track_payload["tasks"],
        "artifacts": [{"id": "artifact-dev", "buddy": "dev"}],
        "run_audits": [{"run_id": "run-dev-1", "track_id": "track-alpha", "task_id": "task-dev"}],
    }

    summary = self._derive_track_next_step_summary(workspace_payload, track_payload)

    self.assertEqual(summary["nextBuddy"], "market")
    self.assertEqual(summary["currentBuddy"], "dev")
    self.assertNotIn("switch", json.dumps(summary).lower())
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py -q
```

Expected before console edits: fail or require harness update because current console exposes command derivation.

- [ ] **Step 2: Replace “Next Commands” UI**

In `framework/console/index.html`, replace:

```html
<h3>Next Commands</h3>
<div id="switchCommands" class="command-list"></div>
```

with state-oriented UI:

```html
<h3>Next Step</h3>
<div id="nextStepState" class="state-list"></div>
```

In `framework/console/app.js`:

- Remove copy-button rendering for switch commands from the product panel.
- Replace `deriveSwitchCommandsForTrack()` / `deriveSwitchCommandsForTask()` product use with `deriveNextStepStateForTrack()` / `deriveNextStepStateForTask()`.
- Do not synthesize `switch test -> ...` or any other copyable command.
- Keep run audit fields readable in source details only if needed for debugging.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_console_app_contract.py tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_prompt_does_not_present_switch_as_product_ui -q
```

Expected after edits: pass.

### Task 4: Documentation And Skill Examples

**Files:**
- Modify: `README.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/architecture-overview.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `buddyswitch/manifest.toml`
- Modify: `buddyswitch/skills/**/SKILL.md`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add docs guardrail tests**

Add a repo consistency test that separates product docs from debug docs.

Behavioral guardrail:

```python
def test_product_docs_do_not_teach_switch_as_buddy_instance_input(self) -> None:
    product_paths = [
        ROOT / "README.md",
        ROOT / "framework" / "docs" / "architecture-overview.md",
        ROOT / "framework" / "docs" / "skill-architecture-best-practices.md",
    ]
    forbidden = [
        "`switch` is the canonical entry point",
        "Canonical UI",
        "Use the canonical directive",
        "switch pm:",
        "switch dev:",
        "switch market:",
        "switch test:",
        "switch design:",
    ]
    for path in product_paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            self.assertNotIn(token, text, msg=f"{token!r} leaked in {path.relative_to(ROOT)}")
```

Add a separate assertion that internal wire docs may still contain switch syntax only under explicit internal/debug wording:

```python
def test_switch_spec_is_marked_internal_debug_wire_contract(self) -> None:
    text = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
    self.assertIn("internal/debug wire", text)
    self.assertNotIn("product-mode users should type", text)
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_product_docs_do_not_teach_switch_as_buddy_instance_input tests/test_repo_consistency.py::RepoConsistencyTests::test_switch_spec_is_marked_internal_debug_wire_contract -q
```

Expected before docs edits: fail.

- [ ] **Step 2: Rewrite README product-mode usage**

Product-mode section should show:

```bash
./buddyswitch-codex instance start --buddy pm
```

Then ordinary task examples:

```text
Draft the MVP PRD for onboarding rewrite
Create a track for the onboarding rewrite and define P0 scope
```

Move parser/router examples into a clearly named debug section:

```markdown
## Internal Debug Wire Tools
```

- [ ] **Step 3: Rewrite switch spec as internal wire spec**

`framework/docs/switch-spec.md` should open with:

```markdown
# BuddySwitch Internal Wire Spec

Product-mode users do not type `switch` commands. In launcher-managed buddy instances, ordinary user requests are resolved using the active buddy from session metadata.
```

Keep grammar details under internal/debug use only.

- [ ] **Step 4: Replace skill examples with ordinary language**

For each `buddyswitch/skills/**/SKILL.md`, replace examples such as:

```markdown
- `switch dev: Implement the approved P0 creator profile flow in projects/app`
```

with:

```markdown
- `Implement the approved P0 creator profile flow in projects/app`
```

If an example refers to a different buddy, rewrite it as a handoff note instead of a command:

```markdown
- Handoff intent: ask the PM buddy to define MVP scope for creator profile.
```

Run the docs guardrail tests from Step 1.

### Task 5: First-Slice Integration Verification

**Files:**
- Modify only if failures expose missing test coverage or doc drift.

- [ ] **Step 1: Run focused runtime tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests -q
```

Expected: all tests pass, including ordinary request resolution and structural switch rejection.

- [ ] **Step 2: Run prompt/docs/console tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist_for_every_manifest_buddy tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompts_do_not_allow_user_facing_switch_commands tests/test_repo_consistency.py::RepoConsistencyTests::test_product_docs_do_not_teach_switch_as_buddy_instance_input tests/test_console_app_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run broader regression set**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_console_app_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q
```

Expected: all tests pass.

- [ ] **Step 4: Manual product-mode smoke test**

Start a real buddy instance:

```bash
./buddyswitch-codex instance start --buddy pm
```

Inside the launched Codex session, enter:

```text
Draft the MVP PRD for onboarding rewrite
```

Expected observable behavior:

- The session resolves under `pm`.
- It does not ask the user to type `switch pm:`.
- It does not render copyable `switch` commands in final output.
- Runtime state shows one task under `buddyswitch/objects/tasks/`.
- Runtime state has one reserved run before persist and one run audit after persist.

Then enter:

```text
switch pm: Draft the MVP PRD
```

Expected observable behavior:

- The product-mode instance rejects the structural command.
- The error tells the user to use ordinary request language in the locked buddy instance.
- No new task or reservation is created.

### Task 6: Follow-Up Cleanup Plan After First Slice

This task is not part of the first implementation slice. Create a follow-up plan only after Task 5 passes.

Planned cleanup:

- Add structured `next_task_ref` and `next_buddy_ref` fields alongside `reference_switches` / `recommended_switch`.
- Migrate projections and console to structured fields.
- Remove `reference_switches` / `recommended_switch` from product receipts and run audits after consumers stop reading them.
- Delete `_legacy_resolve_switch`.
- Remove packet-era `_build_run_instructions` guidance referencing `prepare-execution` / `selected_skill_packet`.
- Remove or rewrite stale evals that still mention nonexistent commands or retired markdown artifacts.

## Detailed Test Plan

### Functional Requirements Matrix

| Requirement | Test Type | Test Location | Must Prove | Anti-Cheat Constraint |
| --- | --- | --- | --- | --- |
| Ordinary text assigns one task to active buddy | Runtime integration | `tests/test_switch_runtime.py` | JSON response, task object, reserved run, instance binding | No mocking `resolve_switch`; assert state not private rewrite string |
| Natural word `switch` remains ordinary demand | Runtime integration | `tests/test_switch_runtime.py` | Demand preserved exactly and resolves under active buddy | Input is not structural command syntax |
| Structural same-buddy switch is rejected | Runtime integration | `tests/test_switch_runtime.py` | Non-zero exit, no task writes, actionable message | Must fail current same-buddy acceptance behavior |
| Structural cross-buddy switch is rejected | Runtime integration | `tests/test_switch_runtime.py` | Non-zero exit, no task writes, mentions locked instance | No writes despite valid buddy name |
| Non-product debug parser remains strict | Existing parser tests | `tests/test_switch_routing.py` | `parse_switch.py` still handles internal/debug wire syntax | Do not delete debug parser contract |
| Buddy prompts do not re-teach switch | Repo consistency | `tests/test_repo_consistency.py` | Active buddy prompts require ordinary requests | Scan active prompt assets, not stale docs only |
| Product docs do not teach switch as UI | Repo consistency | `tests/test_repo_consistency.py` | README/product docs show ordinary input | Internal/debug spec can still contain switch if labeled |
| Console does not produce copyable switch commands | JS contract | `tests/test_console_app_contract.py` | Next-step state contains buddy/task/track info, no command | Do not just hide CSS; derived data must not contain switch command |
| Product final output contract drops Commands | Repo consistency | `tests/test_repo_consistency.py` | Prompts say `Receipt -> Summary` | Must reject `Receipt -> Commands -> Summary` in active product prompts |

### Required Negative Tests

Negative tests are mandatory because the core goal is eliminating a user-facing command.

- `switch pm: Draft the PRD` in a `pm` instance must reject.
- `switch dev: Implement the PRD` in a `pm` instance must reject.
- `switch pm:` with empty demand must reject without creating task or reservation.
- Partial product env must reject before any runtime mutation.
- Invalid or mismatched instance JSON must reject before any runtime mutation.

### Required Positive Tests

- `Draft the MVP PRD for onboarding rewrite` in a `pm` instance must succeed.
- `Help users switch plans without losing draft data` in a `pm` instance must succeed.
- Non-product debug `python3 scripts/parse_switch.py "switch pm: debug"` must still work.

### Verification Commands

Baseline command already run in the `dev0210` worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_prompt_assets_exist_for_every_manifest_buddy -q
```

Observed baseline before changes:

```text
23 passed in 0.31s
```

Final focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests tests/test_console_app_contract.py -q
```

Final broader verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_console_app_contract.py -q
```

Launcher prompt verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q
```

## Stop Conditions

Stop and reassess if any of these occur:

- Ordinary product-mode request cannot resolve without depending on structural `switch` user input.
- Removing user-facing commands requires a schema migration before the first slice can pass.
- Console cannot show meaningful next-step state without `reference_switches`.
- Tests only pass by mocking the exact internal adapter rewrite.

## Done Definition

This first slice is done when:

- Product-mode ordinary request assignment passes behavior tests.
- Product-mode structural `switch` input rejects, including same-buddy.
- Active prompts, README product sections, skill examples, and console UI no longer teach user-facing `switch` commands.
- Existing internal debug parser/router tests still pass.
- Verification commands above pass in the `dev0210` worktree.


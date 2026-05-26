# Task Input Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the old private task tool surface with a current/propose/confirm task runtime, and compose a clear task-TUI into main launcher user input before Codex receives it.

**Architecture:** Keep BuddySwitch as the input boundary owner. Add one canonical task read model (`TaskSnapshot`), render it as an agent-readable task-TUI for main `instance input`, and expose the same snapshot through `task.current`. Mutating task state remains only inside `task.propose` and `task.confirm`; the launcher composer never writes taskbox state.

**Tech Stack:** Python env tool runtime, taskbox JSON/history files, Bash launcher wrappers, Codex app-server JSON-RPC helper, pytest/unittest tests, fake Codex app-server test harness.

---

## Scope

Implement the complete first version:

- Replace task env tool actions with:
  - `task.current`
  - `task.propose`
  - `task.confirm`
- Replace shared skill `task-tool` with `$task-management`.
- Add canonical `TaskSnapshot` reading from taskbox history first, then task doc JSON.
- Add task-TUI rendering from `TaskSnapshot`.
- Compose task-TUI before raw user input for main `buddyswitch-codex instance input`.
- Apply composition to both `turn/start` and `turn/steer`.
- Keep taskbox state under `taskbox/<buddy>/history.md` and `taskbox/<buddy>/tasks/*.json`.
- Preserve task detail `body` in task docs.

Do not implement:

- Stop hook or running-end reconciliation.
- Gate, signed gate, daemon phase authority, allowed-list, expiry, or turn validation.
- Independent long-lived task daemon process.
- Side conversation task-TUI composition.
- Generic confirmation framework.
- Old task action compatibility wrappers.
- `task.events`, `task.update`, `task.list`, `task.get`, `task.archive`, or `task.reopen`.
- Direct writes to `buddyswitch/objects/**` or old buddybox runtime paths.

## Forward Decisions

1. Replace the old task tool surface directly. Do not keep old task actions as aliases.
2. The first version's "daemon" role is implemented as a launcher input context composer, not as a separate process.
3. Task reading has one canonical implementation. `task.current` and task-TUI both consume the same `TaskSnapshot`.
4. Task-TUI is a presentation layer. It does not classify user intent, generate proposal payloads, or force tool calls.
5. `$task-management` is topic/workflow-oriented. It helps Codex judge task scenarios; it is not a schema mirror.
6. `task.propose(start)` is only for selecting a new task when there is no current task in `active` or `blocked` state. If a different task should replace active work, use `task.propose(switch)`.
7. `task.propose(switch)` creates pending confirmation. It does not change the current task until `task.confirm(accept)`.
8. `task.confirm` only accepts or rejects the one pending task switch confirmation.
9. `finish` and `block` are implemented as tool capabilities, but main input task-TUI does not actively drive them in version 1.

## Current Implementation Map

Read these files before implementation:

- `buddyswitch-codex`
  - `instance_input` binds the instance, validates app-server health, and calls `buddyswitch_app_server_input`.
  - The CLI output shape should remain unchanged.

- `tools/launcher/app_server.sh`
  - `buddyswitch_app_server_input` wraps `tools/launcher/app_server.py input`.
  - It can pass instance context from `BUDDYSWITCH_INSTANCE_JSON`.

- `tools/launcher/app_server.py`
  - `_command_input()` currently forwards raw text into `input_turn()`.
  - `input_turn()` handles both idle `turn/start` and active `turn/steer`.

- `scripts/env/repos/tasks.py`
  - Existing taskbox file helpers and history appending live here.
  - Current model lacks task `body` and active/pending replay.

- `scripts/env/domain/tasks.py`
  - Existing task payload validation lives here.

- `scripts/env/tools/task/tool.py`
  - Current tool definitions expose old actions.

- `scripts/env/tools/task/_impl.py`
  - Current action handlers implement old actions.

- `buddyswitch/manifest.toml`
  - Current skill id and permissions still refer to `task-tool`, `task.create`, `task.update`, and `task.archive`.

- `buddyswitch/skills/shared/task-tool/SKILL.md`
  - Replace with the new topic/workflow skill.

## File Structure

Create:

- `scripts/env/domain/task_management.py`
  - Owns the canonical task read/write service functions:
    - `current_snapshot(...)`
    - `propose_task(...)`
    - `confirm_task(...)`
  - Coordinates repo functions and domain validation.
  - Returns plain dictionaries suitable for tool responses and TUI rendering.

- `scripts/env/domain/task_tui.py`
  - Pure renderer:
    - `render_task_tui(snapshot: Mapping[str, object]) -> str`
  - No file reads and no task mutation.

- `tools/launcher/task_input_context.py`
  - Launcher-only composer:
    - loads instance payload from `--instance-json`;
    - calls `task_management.current_snapshot(...)`;
    - calls `task_tui.render_task_tui(...)`;
    - returns `task_tui + "\n\n[USER INPUT]\n" + raw_text`.

- `buddyswitch/skills/shared/task-management/SKILL.md`
  - New shared task skill.

Modify:

- `scripts/env/repos/tasks.py`
  - Add `body` to task validation and persistence.
  - Add parseable history event helpers for active/pending replay.
  - Add id generation helpers for `task-0001-short-slug` and `confirm-0001`.

- `scripts/env/domain/tasks.py`
  - Replace old create/update/archive validation with current/propose/confirm validation.

- `scripts/env/tools/task/tool.py`
  - Replace action definitions with `current`, `propose`, `confirm`.

- `scripts/env/tools/task/_impl.py`
  - Replace old action handlers with thin wrappers around `task_management`.

- `scripts/env/tool_runtime/context.py`
  - Update runtime source labels from old task actions to `task.current`.

- `scripts/env/tools/context/_impl.py`
  - Update task visible/semantic surfaces to the new actions.

- `tools/launcher/app_server.py`
  - Add `--instance-json` to the `input` subcommand.
  - Compose input before `input_turn()`.

- `tools/launcher/app_server.sh`
  - Pass `--instance-json "${BUDDYSWITCH_INSTANCE_JSON}"`.

- `buddyswitch/manifest.toml`
  - Replace shared skill id/path with `task-management`.
  - Replace task permissions with `task.read`, `task.propose`, `task.confirm`.

- Tests listed in the test plan.

Delete:

- `buddyswitch/skills/shared/task-tool/SKILL.md`

Remove or rewrite tests that assert old actions as public surface. Do not leave old-action compatibility expectations.

## Data Contracts

### Task Doc

Stored at:

```text
taskbox/<buddy>/tasks/<task-id>.json
```

Shape:

```json
{
  "id": "task-0001-clean-runtime-environment",
  "owner_buddy": "dev",
  "title": "Clean runtime environment",
  "summary": "Refine task input context.",
  "body": "Detailed task body.",
  "status": "active",
  "priority": "normal",
  "track_id": null,
  "refs": [],
  "created_at": "2026-05-27T10:00:00+08:00",
  "updated_at": "2026-05-27T10:00:00+08:00",
  "closed_at": null
}
```

`status` values:

```text
active
blocked
done
archived
```

`archived` remains an internal storage status value, but no public `task.archive` action is shipped in version 1.

### History Lines

Keep the current readable markdown-line style, but make replay fields parseable:

```text
- <iso-time> task.create <task-id> title="<json-string>" status="<json-string>" reason="<json-string>" evidence="<json-string>"
- <iso-time> task.switch.requested <current-task-id> confirmation_id="<json-string>" target="<json-object>" reason="<json-string>" evidence="<json-string>"
- <iso-time> task.switch.confirmed <new-current-task-id> confirmation_id="<json-string>" reason="<json-string>"
- <iso-time> task.switch.rejected <current-task-id> confirmation_id="<json-string>" reason="<json-string>"
- <iso-time> task.close <task-id> reason="<json-string>" evidence="<json-string>"
- <iso-time> task.block <task-id> reason="<json-string>" evidence="<json-string>"
```

Replay rules:

- `task.create` selects the created task as current.
- `task.switch.requested` creates pending confirmation and does not change current.
- `task.switch.confirmed` clears pending confirmation and selects the target task.
- `task.switch.rejected` clears pending confirmation and keeps current.
- `task.close` keeps the same current task id but changes task state to `done`.
- `task.block` keeps the same current task id but changes task state to `blocked`.

### TaskSnapshot

Canonical dictionary returned by `task_management.current_snapshot(...)`:

```json
{
  "owner_buddy": "dev",
  "task_state": "none | active | blocked | done",
  "current_task": null,
  "pending_confirmation": null,
  "recent_events": [],
  "last_event": null,
  "progress_summary": ""
}
```

When a current task exists:

```json
{
  "current_task": {
    "id": "task-0001-clean-runtime-environment",
    "title": "Clean runtime environment",
    "status": "active",
    "summary": "Refine task input context.",
    "body_excerpt": "Detailed task body.",
    "priority": "normal",
    "track_id": null,
    "refs": [],
    "updated_at": "2026-05-27T10:00:00+08:00"
  }
}
```

When a pending switch exists:

```json
{
  "pending_confirmation": {
    "confirmation_id": "confirm-0001",
    "type": "task.switch",
    "from_task_id": "task-0001-clean-runtime-environment",
    "target": {
      "mode": "existing | new",
      "task_id": "task-0002-next-task",
      "task": null
    },
    "reason": "User asked to switch tasks.",
    "evidence": "User-visible quote or summary."
  }
}
```

### Task-TUI

Renderer output:

```text
[TASK CONTEXT]
Current Task: task-0001-clean-runtime-environment
Title: Clean runtime environment
State: active
Progress: Refine task input context.
Last Event: task.create task-0001-clean-runtime-environment
Pending Confirmation: none
Recent Events:
- task.create task-0001-clean-runtime-environment

Task Handling Cue:
- Continue current task: no task state change.
- Clear new task with no active current task: use $task-management and task.propose(start).
- Clear switch away from current task: use $task-management and task.propose(switch).
- Pending switch answer: use task.confirm.
- Unclear: no task mutation.
```

Composer output:

```text
<task-TUI>

[USER INPUT]
<raw user input>
```

## Task Tool Contracts

### `task.current`

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [],
  "properties": {
    "history_limit": {
      "type": "integer",
      "minimum": 1,
      "default": 8,
      "description": "Maximum recent task history lines to return."
    }
  }
}
```

Response effect:

- reads taskbox history and current task doc;
- does not write;
- returns `snapshot`.

### `task.propose`

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "reason", "evidence"],
  "properties": {
    "type": {
      "type": "string",
      "enum": ["start", "switch", "finish", "block"],
      "description": "Task state proposal type."
    },
    "task_id": {
      "type": "string",
      "description": "Current task id for finish/block."
    },
    "task": {
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "body"],
      "properties": {
        "title": {"type": "string", "description": "Task title."},
        "summary": {"type": "string", "description": "Short task summary."},
        "body": {"type": "string", "description": "Detailed task body."},
        "priority": {"type": "string", "enum": ["high", "normal", "low"], "description": "Task priority."},
        "track_id": {"type": ["string", "null"], "description": "Optional linked track id for context only."},
        "refs": {"type": "array", "description": "Optional private references.", "items": {"type": "object"}}
      }
    },
    "target": {
      "type": "object",
      "additionalProperties": false,
      "required": ["mode"],
      "properties": {
        "mode": {"type": "string", "enum": ["existing", "new"], "description": "Switch target mode."},
        "task_id": {"type": "string", "description": "Existing target task id."},
        "task": {"type": "object", "description": "New target task body for mode=new."}
      }
    },
    "reason": {"type": "string", "description": "Why this task state change is appropriate."},
    "evidence": {"type": "string", "description": "User-visible evidence for the proposal."}
  }
}
```

Domain validation enforces type-specific required fields:

- `start` requires `task`, rejects when current task state is `active` or `blocked`.
- `switch` requires `target`, creates pending confirmation.
- `finish` requires `task_id` matching current task.
- `block` requires `task_id` matching current task.

### `task.confirm`

Input schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["confirmation_id", "decision"],
  "properties": {
    "confirmation_id": {"type": "string", "description": "Pending task switch confirmation id."},
    "decision": {"type": "string", "enum": ["accept", "reject"], "description": "Whether to accept or reject the pending switch."},
    "reason": {"type": "string", "description": "Optional reason for the decision."}
  }
}
```

Domain validation:

- rejects when no pending confirmation exists;
- rejects mismatched `confirmation_id`;
- supports only pending type `task.switch`;
- `accept` executes the switch and clears pending;
- `reject` keeps current task and clears pending.

## Implementation Tasks

### Task 1: Add Task Snapshot And TUI Tests

**Files:**

- Create: `tests/test_task_input_context.py`
- Test helper patterns: reuse `RuntimeWorkspaceTestMixin` from existing env tool tests.

- [ ] **Step 1: Write empty snapshot and empty TUI tests**

Add tests that create an instance taskbox with empty `history.md`, call `task_management.current_snapshot(...)`, and render `task_tui.render_task_tui(snapshot)`.

Expected assertions:

```python
self.assertEqual(snapshot["task_state"], "none")
self.assertIsNone(snapshot["current_task"])
self.assertIsNone(snapshot["pending_confirmation"])
self.assertIn("Current Task: none", tui)
self.assertIn("State: none", tui)
self.assertIn("Pending Confirmation: none", tui)
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
```

Expected: fails because `env.domain.task_management` and `env.domain.task_tui` do not exist.

- [ ] **Step 3: Write current-task and pending-confirmation tests**

Seed history and task docs. Assert the current task is chosen by history replay, not directory sorting. Assert pending switch data is rendered in the TUI.

- [ ] **Step 4: Run the focused test and confirm failure still points to missing implementation**

Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
```

Expected: fails on missing module/functions, not on test syntax.

### Task 2: Implement Canonical Task Snapshot Read Model

**Files:**

- Create: `scripts/env/domain/task_management.py`
- Modify: `scripts/env/repos/tasks.py`

- [ ] **Step 1: Add task doc body validation**

Update `scripts/env/repos/tasks.py::_validate_task` to include:

```python
body = task.get("body", "")
if not isinstance(body, str):
    raise ValueError("task.body must be a string")
```

Return `body` in the normalized task dict.

- [ ] **Step 2: Add history parsing helpers**

Add functions that parse current history lines into event dictionaries without changing the on-disk readable line format:

```python
def parse_history_line(line: str) -> dict[str, Any] | None:
    ...

def read_history_events(..., limit: int = 50) -> list[dict[str, Any]]:
    ...
```

The parser must support the event names listed in this plan and JSON-decoded `key=<json>` fields.

- [ ] **Step 3: Add id generation helpers**

Add:

```python
def next_task_id(title: str, *, active_buddy: str, instance_json: Path | str | None, instance_payload: Mapping[str, object] | None) -> str:
    ...

def next_confirmation_id(*, active_buddy: str, instance_json: Path | str | None, instance_payload: Mapping[str, object] | None) -> str:
    ...
```

`next_task_id` scans existing task files and returns `task-0001-short-slug` style ids.

- [ ] **Step 4: Implement `current_snapshot`**

In `scripts/env/domain/task_management.py`, implement:

```python
def current_snapshot(
    *,
    active_buddy: str,
    instance_json: Path | str | None,
    instance_payload: Mapping[str, object] | None,
    history_limit: int = 8,
) -> dict[str, Any]:
    ...
```

It must:

- read history events first;
- replay current task id and pending confirmation;
- load current task doc by id;
- return `task_state`, `current_task`, `pending_confirmation`, `recent_events`, `last_event`, and `progress_summary`;
- never write files.

- [ ] **Step 5: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
```

Expected: snapshot tests pass; TUI tests still fail until renderer exists.

### Task 3: Implement Task-TUI Renderer

**Files:**

- Create: `scripts/env/domain/task_tui.py`

- [ ] **Step 1: Implement pure renderer**

Add:

```python
def render_task_tui(snapshot: Mapping[str, object]) -> str:
    ...
```

It must:

- return a deterministic text panel starting with `[TASK CONTEXT]`;
- render none/current/pending states clearly;
- include recent events as short lines;
- include the fixed short task-handling cue;
- not include `[USER INPUT]`;
- not read or write files.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_task_input_context.py -q
```

Expected: pass.

### Task 4: Replace Task Env Tool Surface

**Files:**

- Modify: `scripts/env/domain/tasks.py`
- Modify: `scripts/env/tools/task/tool.py`
- Modify: `scripts/env/tools/task/_impl.py`
- Modify: `tests/test_task_env_tool.py`

- [ ] **Step 1: Rewrite task env tool tests for current/propose/confirm**

Replace old action tests with the cases from the test plan:

- `task.current` read-only snapshot;
- `task.propose(start)`;
- `task.propose(switch)`;
- `task.confirm(accept/reject)`;
- `task.propose(finish/block)`;
- invalid payloads do not mutate task docs or history.

- [ ] **Step 2: Run task env tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
```

Expected: fails because current tool definitions still expose old actions.

- [ ] **Step 3: Replace `scripts/env/tools/task/tool.py` actions**

Define exactly three `ActionDefinition` rows:

```text
current
propose
confirm
```

Use required permissions:

```text
task.read
task.propose
task.confirm
```

Set reads/writes/effects so operation semantics make state impact clear.

- [ ] **Step 4: Replace `_impl.py` handlers**

Implement thin handlers:

```python
def current_for_active_buddy(...):
    snapshot = task_management.current_snapshot(...)

def propose_for_active_buddy(...):
    result = task_management.propose_task(...)

def confirm_for_active_buddy(...):
    result = task_management.confirm_task(...)
```

Use `tool_results.success` and `tool_results.rejection` with precise `state_changed`, `durability`, `state_changes`, and `why_blocked`.

- [ ] **Step 5: Implement proposal and confirmation domain service**

In `scripts/env/domain/task_management.py`, add:

```python
def propose_task(..., args: Mapping[str, Any]) -> dict[str, Any]:
    ...

def confirm_task(..., args: Mapping[str, Any]) -> dict[str, Any]:
    ...
```

Use repository helpers for all file writes. Rejected calls must return before writing task docs or history.

- [ ] **Step 6: Run task env tests**

Run:

```bash
python3 -m pytest tests/test_task_env_tool.py -q
```

Expected: pass.

### Task 5: Update Tool Catalog, Context Surface, Manifest, And Skill

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Delete: `buddyswitch/skills/shared/task-tool/SKILL.md`
- Create: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_task_management_skill_architecture.py`

- [ ] **Step 1: Update tests for the new public surface**

Rewrite assertions to expect:

```text
task.current
task.propose
task.confirm
task-management
```

Remove old `task-tool` and old action expectations.

- [ ] **Step 2: Run contract tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_task_management_skill_architecture.py -q
```

Expected: fails on old manifest/skill/context references.

- [ ] **Step 3: Replace manifest skill and permissions**

Update the shared skill table:

```toml
[[skills]]
id = "task-management"
path = "buddyswitch/skills/shared/task-management"
```

Replace buddy skill entries `task-tool` with `task-management`.

Replace task permissions:

```text
task.read
task.propose
task.confirm
```

- [ ] **Step 4: Write `$task-management` skill**

Create `buddyswitch/skills/shared/task-management/SKILL.md` with topic/workflow sections:

```markdown
---
name: task-management
description: Use when current user input may continue, create, switch, confirm, finish, or block a persistent BuddySwitch task.
---

# task-management

## Principles

...

## Continue Current Task
...

## Create New Task
...

## Switch Task
...

## Confirm Pending Switch
...

## Mark Done / Blocked
...

## Tool Reference
...
```

Keep `Tool Reference` short; do not paste full JSON schemas.

- [ ] **Step 5: Update context surfaces**

Update `scripts/env/tool_runtime/context.py` and `scripts/env/tools/context/_impl.py` so host-visible runtime sources and summaries name `task.current`, `task.propose`, and `task.confirm`.

- [ ] **Step 6: Run contract tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_task_management_skill_architecture.py -q
```

Expected: pass.

### Task 6: Compose Task-TUI Into Main Launcher Input

**Files:**

- Create: `tools/launcher/task_input_context.py`
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add launcher tests for turn/start composition**

In `tests/test_buddyswitch_launcher.py`, extend the existing input-start test or add a new focused test that seeds instance taskbox and asserts fake Codex receives composed text in `turn/start`.

Assert order:

```text
[TASK CONTEXT]
...
[USER INPUT]
<raw user text>
```

- [ ] **Step 2: Add launcher tests for turn/steer composition**

Add a test for active-thread `turn/steer` with the same composition assertion.

- [ ] **Step 3: Add side non-composition regression**

Add a side create/send assertion that side text remains raw and contains no `[TASK CONTEXT]`.

- [ ] **Step 4: Run focused launcher tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "input_ or side_" -q
```

Expected: input composition tests fail because raw text is still sent.

- [ ] **Step 5: Implement `tools/launcher/task_input_context.py`**

Add:

```python
def compose_task_context_input(*, raw_text: str, instance_json: Path) -> str:
    ...
```

It must:

- load instance JSON;
- read `buddy` from the instance payload;
- call `task_management.current_snapshot(...)`;
- render the TUI;
- append `[USER INPUT]` and the raw text;
- raise a clear error for missing/invalid instance JSON.

- [ ] **Step 6: Wire composer into `app_server.py input`**

Add `--instance-json` to the input parser. In `_command_input`, compose before calling `input_turn`:

```python
text = args.text
if args.instance_json:
    text = compose_task_context_input(raw_text=args.text, instance_json=Path(args.instance_json))
payload = input_turn(Path(args.socket), args.thread_id, text, args.permissions)
```

- [ ] **Step 7: Pass instance JSON from shell wrapper**

Update `tools/launcher/app_server.sh::buddyswitch_app_server_input`:

```bash
--instance-json "${BUDDYSWITCH_INSTANCE_JSON}"
```

- [ ] **Step 8: Run focused launcher tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "input_ or side_" -q
```

Expected: pass.

### Task 7: Focused And Broad Verification

**Files:**

- No implementation files unless verification exposes a defect.

- [ ] **Step 1: Run focused task tests**

Run:

```bash
python3 -m pytest tests/test_task_input_context.py tests/test_task_env_tool.py -q
```

Expected: pass.

- [ ] **Step 2: Run focused launcher input tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "input_ or side_" -q
```

Expected: pass and no residual fake Codex/app-server processes from the focused run.

- [ ] **Step 3: Run tool and skill contract tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_task_management_skill_architecture.py -q
```

Expected: pass.

- [ ] **Step 4: Run repo consistency checks that mention skills or runtime surfaces**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: pass.

- [ ] **Step 5: Search for old public task surface**

Run:

```bash
rg -n "task-tool|Use task\\.(list|get|update|archive|history)|task\\.(list|get|update|archive|history)|required_permission=\"task\\.(create|update|archive)\"" buddyswitch scripts tests
```

Expected: no live public-contract references outside explicit negative tests. History event names such as `task.create` are allowed because they are persisted events, not public tool actions.

## Self-Review Checklist

Before handing off implementation:

- Every requirement in `docs/spec/2026-05-27-task-input-context-test-plan.md` maps to at least one implementation task above.
- No old task action remains as a supported public action.
- `task.current` and task-TUI share `task_management.current_snapshot`.
- Launcher input composition occurs before Codex `turn/start` or `turn/steer`.
- Side input is unchanged in version 1.
- `$task-management` is topic/workflow-oriented and does not duplicate full tool schemas.
- Rejected task mutations prove `state_changed=false` and unchanged taskbox files/history.
- Verification includes launcher lifecycle discipline because app-server tests start persistent processes.

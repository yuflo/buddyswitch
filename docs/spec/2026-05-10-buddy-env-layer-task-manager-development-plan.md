# Buddy Env Layer Task Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` before implementing this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first product-grade BuddySwitch buddy env layer slice by shipping `task-manager` as a normal shared skill backed by deterministic active-buddy-scoped task env tools.

**Architecture:** Keep user-facing capability in a concise shared skill, expose the deterministic operation surface through a broker-routed `env.task` tool, enforce permissions and buddy ownership in service code, and continue to use existing runtime state objects as the store. This first slice deliberately avoids a new manifest registry schema, workflow engine, or full track/artifact migration.

**Tech Stack:** Python stdlib, existing BuddySwitch manifest/env profile/runtime broker code, existing JSON object store in `scripts/env_store.py`, pytest/unittest test suites, Codex native skill packages.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`.

## Source Memo Review

Source: `docs/memo/2026-05-10-buddy-env-layer-task-manager-action-plan-memo.md`.

The memo defines one product goal: build a stronger BuddySwitch buddy env layer so buddies can operate task, track, artifact, context, and binding state through consistent runtime-owned tools.

The immediate bottleneck is task management, not a standalone task CLI. Today `scripts/env_tasks.py` is manual/debug oriented: it checks manifest permissions such as `task.read` and `task.update`, but it does not enforce product session identity or `task.buddy == active_buddy`. The current runtime can create or bind tasks during `prepare`, but buddies do not have a normal shared skill plus lower-level env tool path to create, inspect, update, archive, or switch current task safely.

The agreed direction is "more context, less prompt":

- `prepare.runtime_context` is the buddy-facing source for allowed actions, payload shapes, tool requirements, and current context.
- Runtime/tool rejection returns structured feedback such as `permission_boundary`, `allowed_next_actions`, `stop_condition`, `command_hint`, and payload hints.
- `AGENTS.md` and `SKILL.md` stay concise and do not become the permission source.
- Active buddy and instance identity come from launcher/runtime session context, not LLM-authored payload fields.
- Cross-buddy task management is forbidden in runtime/tool/service code.
- The old switch-era text routing model must not be revived.

## Confirmed Facts

- `buddyswitch/manifest.toml` already grants every buddy `task.read`, `task.create`, `task.update`, and `task.archive`; PM additionally owns track lifecycle permissions.
- The manifest currently has no shared skill registry. `scripts/runtime_skills.py` installs exactly the skill ids listed on the active buddy row.
- Existing skills live under `buddyswitch/skills/<buddy>/<skill>/`; there is no `buddyswitch/skills/shared/` package yet.
- `scripts/env_tasks.py` exposes `list`, `show`, `update`, and `archive` debug commands. It has no create operation, no product instance binding operation, and no active-buddy ownership check.
- `scripts/env_store.py` already owns JSON validation and low-level task/track/artifact reads and writes, including `create_task`, `list_tasks`, `get_task`, `update_task`, and track/task linkage helpers.
- `scripts/runtime_kernel/broker.py` currently dispatches only `prepare`, `persist`, and `issue_browser_evidence`.
- `scripts/runtime_kernel/client.py` already wraps broker transport and returns structured broker-unavailable feedback.
- `scripts/turn_runtime.py` already writes launcher instance binding through `_write_product_session_binding()` and builds `prepare.runtime_context`.
- `tools/launcher/workspace.sh` syncs runtime scripts into instance workspaces, but the current runtime surface list does not include a future `scripts/env/` directory.
- `framework/contracts/prepare-turn-context.json` requires `runtime_context.runtime_commands`, `capability_boundary`, `tool_requirements`, and related runtime context sections.

## Open Assumptions And Invalidators

- Assumption: The first implementation can register `task-manager` once in the manifest and add that skill id to each buddy's existing `skills` list. If the manifest must instead support inherited shared skills, stop and split that schema change into a separate plan.
- Assumption: A broker method namespace `env.task` is enough for this slice. If a broader `tool.call` envelope is required by another active runtime contract, stop and reconcile the contract before implementation.
- Assumption: The first slice can reuse `scripts/env_store.py` as the store layer and add service/tool modules above it. If implementation proves store-level coupling blocks active-buddy scoping, introduce the smallest `scripts/env/store/objects.py` facade needed for tasks only.
- Assumption: `task.archive` will be implemented as `status = "archived"` with a distinct action and clear response. It will not delete tasks.
- Invalidator: Any active product path requiring cross-buddy task reads or mutations must be escalated, because the memo consensus forbids that at tool/service layer.

## Scope

In scope:

- Add shared `task-manager` skill and make it available to every buddy.
- Add broker-routed task env tool operations: `create`, `list`, `get`, `get_current`, `set_current`, `update`, and `archive`.
- Enforce active-buddy ownership and manifest permissions in code.
- Synchronize launcher instance `current_task_id` and `current_track_id` on `set_current`.
- Add structured success and rejection payloads.
- Expose task env tool availability through `prepare.runtime_context`.
- Mark or thin-wrap old manual/debug task script so it no longer defines product behavior.

Non-goals:

- No task deletion.
- No cross-buddy task administration.
- No task-manager ownership of artifacts, runs, browser evidence, or track lifecycle creation.
- No user text routing or old switch syntax revival.
- No generic workflow engine, permission DSL, or new manifest inheritance system.
- No manual human admin UI.

## Target Operation Contract

All tool responses are JSON objects.

Success shape:

```json
{
  "ok": true,
  "action": "task.get",
  "active_buddy": "dev",
  "task_id": "task-dev-example",
  "task": {
    "id": "task-dev-example",
    "buddy": "dev",
    "title": "Example",
    "summary": "",
    "status": "active",
    "track_id": null,
    "latest_run_id": null,
    "updated_at": "2026-05-10T00:00:00+08:00"
  },
  "current_binding": {
    "instance_id": "inst-dev-example",
    "current_task_id": "task-dev-example",
    "current_track_id": null
  },
  "allowed_next_actions": [
    "Use task.update to change title, summary, or status.",
    "Use task.set_current to bind this task to the active instance."
  ]
}
```

Rejected cross-buddy shape:

```json
{
  "ok": false,
  "action": "task.set_current",
  "error": {
    "code": "E_TASK_BUDDY_SCOPE",
    "message": "task belongs to buddy 'pm', not active buddy 'dev'"
  },
  "permission_boundary": "task.buddy_scope",
  "active_buddy": "dev",
  "task_id": "task-pm-example",
  "allowed_next_actions": [
    "Choose a task owned by the active buddy.",
    "List active-buddy tasks before changing the current task.",
    "Use handoff or track context instead of cross-buddy task mutation."
  ]
}
```

CLI shape for skills:

```bash
python3 scripts/env/client.py task create --payload /tmp/task-create.json
python3 scripts/env/client.py task list
python3 scripts/env/client.py task get --task-id task-dev-example
python3 scripts/env/client.py task get-current
python3 scripts/env/client.py task set-current --task-id task-dev-example
python3 scripts/env/client.py task update --payload /tmp/task-update.json
python3 scripts/env/client.py task archive --task-id task-dev-example
```

The CLI prints the JSON tool response for both `ok=true` and `ok=false`. It exits nonzero only for invalid CLI usage or when it cannot print a structured response.

## File Map

Create:

- `buddyswitch/skills/shared/task-manager/SKILL.md`: concise native skill instructions, use cases, env tool invocation pattern, and feedback interpretation.
- `scripts/env/__init__.py`: package marker for env tool modules.
- `scripts/env/client.py`: skill-facing CLI that calls the runtime broker with `method="env.task"`.
- `scripts/env/services/__init__.py`: package marker.
- `scripts/env/services/tasks.py`: active-buddy task domain service, manifest permission checks, ownership checks, task summaries, response shaping, and instance binding writes.
- `scripts/env/tools/__init__.py`: package marker.
- `scripts/env/tools/task_manager.py`: request dispatcher from broker payload `{action, args}` to task service operations.
- `tests/test_task_manager_env_tool.py`: functional task-manager env tool coverage.

Modify:

- `buddyswitch/manifest.toml`: add one `task-manager` skill row pointing at `buddyswitch/skills/shared/task-manager`; add `"task-manager"` to every buddy's `skills` list.
- `scripts/runtime_kernel/broker.py`: dispatch `method == "env.task"` under the same active instance and runtime lock checks as other state-mutating runtime operations.
- `scripts/turn_runtime.py`: add task env tool hints to `prepare.runtime_context`.
- `framework/contracts/prepare-turn-context.json`: include the chosen runtime context section for env task tools.
- `framework/docs/turn-runtime-spec.md`: document task-manager as the first shared env tool skill and state that permissions live in env tool/service code.
- `tools/launcher/workspace.sh`: include `scripts/env` in runtime surface sync.
- `scripts/env_tasks.py`: reclassify as manual/debug-only and route through service only if doing so does not weaken product identity checks.
- `tests/test_runtime_skills.py`: prove shared task-manager is materialized for every buddy.
- `tests/test_runtime_broker.py`: prove broker accepts `env.task` only for active launcher instances and preserves identity checks.
- `tests/test_prepare_runtime_context.py` or `tests/test_turn_runtime.py`: prove runtime context exposes task tool capability and command hints.
- `tests/test_repo_consistency.py`: add guards for shared skill availability and no prompt-level permission recipes.
- `tests/test_buddyswitch_launcher.py`: prove runtime workspace sync includes `scripts/env` and task-manager materializes into launcher-managed instances.

## Implementation Tasks

### Task 1: Lock The Product Contract With Failing Tests

- [ ] Add `tests/test_task_manager_env_tool.py` with a runtime workspace fixture that creates two launcher instance records: one active `dev` instance and one `pm` task owned by a different buddy.
- [ ] Test `task.create` through broker dispatch with active buddy `dev`.
- [ ] Test `task.list` returns the created Dev task and excludes the PM task.
- [ ] Test `task.get`, `task.update`, and `task.archive` succeed for an active-buddy-owned task.
- [ ] Test `task.get`, `task.update`, `task.archive`, and `task.set_current` reject a foreign task with `ok=false`, `error.code=E_TASK_BUDDY_SCOPE`, `permission_boundary=task.buddy_scope`, `active_buddy`, `task_id`, and non-empty `allowed_next_actions`.
- [ ] Test `task.set_current` writes the instance record `current_task_id` and synchronizes `current_track_id` from the selected task.
- [ ] Test `task.get_current` returns the current binding and task summary when the active instance has a current task.
- [ ] Test missing or malformed payloads reject with `permission_boundary=request-payload` and do not mutate task objects or instance binding.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q`.
- [ ] Expected before implementation: tests fail because `env.task` and `scripts/env/` do not exist.

### Task 2: Add Shared Task Manager Skill To The Manifest

- [ ] Create `buddyswitch/skills/shared/task-manager/SKILL.md`.
- [ ] Keep the skill concise: purpose, when to use, operations, command shape, feedback interpretation, and guardrails.
- [ ] State that runtime/tool feedback is authoritative for permission and next action decisions.
- [ ] Do not duplicate cross-buddy permission recipes beyond the rule that the tool enforces active-buddy scope.
- [ ] Add `[[skills]] id = "task-manager"` with path `buddyswitch/skills/shared/task-manager` to `buddyswitch/manifest.toml`.
- [ ] Add `"task-manager"` to each buddy's skill list: market, pm, design, dev, and test.
- [ ] Update `tests/test_runtime_skills.py` so runtime skill installation for representative buddies includes `task-manager`.
- [ ] Add a repo consistency assertion that every manifest buddy includes `task-manager` exactly once.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q`.
- [ ] Expected after this task: skill materialization and manifest consistency pass; env tool operation tests still fail.

### Task 3: Build Active-Buddy Task Service

- [ ] Create `scripts/env/services/tasks.py`.
- [ ] Add a service context object or plain dict with `active_buddy`, `instance_id`, `instance_json`, `instance_payload`, and `manifest`.
- [ ] Implement permission checks with `env_manifest.buddy_permissions()`.
- [ ] Implement ownership checks by reading tasks with `env_store.get_task(task_id)` and requiring `task["buddy"] == active_buddy`.
- [ ] Implement task summary output with only stable public fields: `id`, `buddy`, `title`, `summary`, `status`, `track_id`, `latest_run_id`, and `updated_at`.
- [ ] Implement `create_task_for_active_buddy(args, context)`.
- [ ] Implement `list_tasks_for_active_buddy(args, context)`.
- [ ] Implement `get_task_for_active_buddy(args, context)`.
- [ ] Implement `get_current_task(args, context)`.
- [ ] Implement `set_current_task(args, context)` using `turn_runtime._write_product_session_binding()`.
- [ ] Implement `update_task_for_active_buddy(args, context)` allowing only `title`, `summary`, and `status`.
- [ ] Implement `archive_task_for_active_buddy(args, context)` as a distinct action that writes `status="archived"`.
- [ ] Ensure every success response includes `ok`, `action`, `active_buddy`, and relevant task or binding fields.
- [ ] Ensure every rejection response includes `ok=false`, `action`, `error.code`, `error.message`, `permission_boundary`, `active_buddy`, and `allowed_next_actions`.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q`.
- [ ] Expected after this task: service-level tests pass if they call the service directly; broker and CLI tests still fail until dispatch is wired.

### Task 4: Add Broker-Routed `env.task` Dispatch

- [ ] Create `scripts/env/tools/task_manager.py`.
- [ ] Accept broker payload shape `{"action": "<name>", "args": {...}}`.
- [ ] Normalize supported actions to `create`, `list`, `get`, `get_current`, `set_current`, `update`, and `archive`.
- [ ] Return structured `ok=false` for unknown action without throwing an unstructured exception.
- [ ] Modify `scripts/runtime_kernel/broker.py` to dispatch `method == "env.task"` inside `_runtime_server_env()`.
- [ ] Use the same protocol, instance id, active buddy, active status, and runtime lock checks already used for `prepare` and `persist`.
- [ ] Pass the locked instance record and manifest into the task manager dispatcher.
- [ ] Update broker allowed method feedback to mention `env.task`.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_task_manager_env_tool.py -q`.
- [ ] Expected after this task: broker-routed task operations pass for active instances and reject wrong instance, wrong buddy, inactive instance, and unsupported method cases.

### Task 5: Add Skill-Facing Env Client CLI

- [ ] Create `scripts/env/client.py`.
- [ ] Insert the parent `scripts/` directory into `sys.path` before importing `runtime_kernel.client`.
- [ ] Add a `task` subcommand with operations `create`, `list`, `get`, `get-current`, `set-current`, `update`, and `archive`.
- [ ] Support `--payload <json-file>` for create/update and `--task-id <id>` for get/set-current/archive.
- [ ] Convert CLI operation names to service action names: `get-current` to `get_current`, `set-current` to `set_current`.
- [ ] Print `json.dumps(response, ensure_ascii=True, indent=2)` plus a newline.
- [ ] Wrap `RuntimeBrokerError` as a structured `ok=false` JSON response using the error code, message, and feedback details from `runtime_kernel.client`.
- [ ] Return exit code 0 when a structured response is printed, even when `ok=false`.
- [ ] Return exit code 2 for invalid CLI usage or unreadable payload files.
- [ ] Add subprocess tests that run the CLI against a temporary broker or mock broker path and assert machine-readable output.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q`.
- [ ] Expected after this task: skill-facing command path works and prints decision-friendly JSON.

### Task 6: Expose Task Tool Hints Through Runtime Context

- [ ] Add a compact task tool section to `prepare.runtime_context`, named `env_tools` unless current contract review identifies a better existing section.
- [ ] Include `task_manager.command` with `python3 scripts/env/client.py task <operation>`.
- [ ] Include supported operations and required payload fields at a compact level.
- [ ] Include `scope` stating that operations are active-buddy scoped and runtime enforced.
- [ ] Update `framework/contracts/prepare-turn-context.json` so the new section is required.
- [ ] Update tests that validate prepare context key order or required sections.
- [ ] Update `framework/docs/turn-runtime-spec.md` to state that task-manager is the first shared env tool skill and that permissions are enforced by env tool/service code.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_prepare_runtime_context.py tests/test_repo_consistency.py -q` using only files that exist in the branch.
- [ ] Expected after this task: prepare output shows the tool path without expanding AGENTS or skill prompts into permission manuals.

### Task 7: Sync Runtime Surface Into Launcher Workspaces

- [ ] Modify `tools/launcher/workspace.sh` runtime surface list to include `scripts/env`.
- [ ] Update launcher tests so a materialized product instance contains `scripts/env/client.py`, task tool modules, and the shared `task-manager` skill under `.agents/skills/task-manager`.
- [ ] Confirm non-Dev and Dev instance materialization both receive the shared skill.
- [ ] Confirm the runtime workspace still neutralizes workspace `.codex/config.toml` as before.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q`.
- [ ] Expected after this task: launcher-managed instances have the executable env tool client and the shared skill without copying runtime-only state skeletons into the source checkout.

### Task 8: Reclassify Old Manual Task Script

- [ ] Update `scripts/env_tasks.py` docstring and argparse description to say it is a manual/debug helper, not the product buddy env tool path.
- [ ] If practical without broadening scope, route its read/update/archive internals through the new task service using an explicit debug context and keep actor-supplied behavior clearly separate from product active-buddy context.
- [ ] If routing would add confusing compatibility behavior, leave the script as debug/manual and add tests/docs that product tests do not call it as the env tool path.
- [ ] Add a repo consistency guard that `task-manager` product tests call `scripts/env/client.py`, broker `env.task`, or service functions, not `scripts/env_tasks.py`.
- [ ] Run `python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_task_manager_env_tool.py -q`.
- [ ] Expected after this task: old debug script is no longer ambiguous as the product permission source.

### Task 9: Final Verification And Scope Review

- [ ] Run focused tests:

```bash
python3 -m pytest -p no:cacheprovider tests/test_task_manager_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_runtime_tool_feedback.py -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

- [ ] Run launcher coverage if Task 7 changed workspace sync:

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

- [ ] Run import/compile proof:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py scripts/env/services/tasks.py scripts/env/tools/task_manager.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py
```

- [ ] Run active surface search:

```bash
rg -n "task-manager|env.task|scripts/env/client.py|scripts/env_tasks.py" buddyswitch scripts tests framework tools/launcher docs/spec
```

- [ ] Inspect `git diff --stat` and confirm the change set is limited to task-manager env layer work.
- [ ] Confirm the self-review rubric:
  - root cause is addressed by code-owned tool/service enforcement, not prompt wording;
  - active-buddy and instance identity are runtime injected;
  - no cross-buddy task read or mutation succeeds;
  - no generic workflow/permission framework was introduced;
  - old debug paths do not define product behavior;
  - verification proves own-buddy success, cross-buddy rejection, binding sync, skill materialization, and runtime context exposure.

## Acceptance Criteria

- `task-manager` exists as a normal shared skill package.
- Every buddy receives `task-manager` through normal runtime skill materialization.
- Task env tool operations exist behind the broker-routed lower-level env tool path.
- Task create/list/get/get-current/set-current/update/archive work for active-buddy-owned tasks.
- Cross-buddy task reads and mutations are rejected by code with structured feedback.
- `task.set_current` updates launcher instance `current_task_id` and synchronizes `current_track_id`.
- `prepare.runtime_context` exposes compact task env tool capability and command hints.
- `AGENTS.md` and `SKILL.md` remain concise and are not the permission source.
- `scripts/env_tasks.py` is clearly debug/manual residue or a thin wrapper, not the product task env path.
- Focused tests pass from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`.

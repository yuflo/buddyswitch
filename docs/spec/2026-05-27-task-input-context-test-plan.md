# Task Input Context Test Plan

Date: 2026-05-27

## Test Goal

Prove BuddySwitch can give Codex a clear current-task context before each main `instance input` turn, while keeping task state mutation inside the task env tool.

The first version covers only the user-input boundary:

```text
raw user input
-> launcher input context composer
-> task_management.current_snapshot() / TaskSnapshot
-> task-TUI + raw user input
-> Codex turn/start or turn/steer
-> Codex decides whether to use $task-management and task tools
```

The tests must start from product behavior. They must prove that Codex receives a readable task panel, that the task panel comes from the same snapshot source as `task.current`, and that the new task tools persist taskbox state and history correctly. They must not pass by asserting private helper calls while missing the persisted taskbox, tool response, or app-server input contract.

## Current Code Findings

- Current launcher input path is `buddyswitch-codex instance input` -> `tools/launcher/app_server.sh::buddyswitch_app_server_input` -> `tools/launcher/app_server.py::_command_input` -> `input_turn()` -> Codex `turn/start` or `turn/steer`.
- `input_turn()` currently sends the raw `--text` unchanged as a Codex text input.
- `app_server.py input` currently receives `--socket`, `--thread-id`, `--text`, and `--permissions`; it does not receive task context or instance context.
- `buddyswitch_env_bind_instance` already exports `BUDDYSWITCH_INSTANCE_JSON`, `BUDDYSWITCH_INSTANCE_ROOT`, and related instance paths before `instance input`.
- Current task env tool surface is the old `create/list/get/update/archive/history` set.
- Current task taskbox storage lives under `taskbox/<buddy>/tasks/*.json` and `taskbox/<buddy>/history.md`.
- Current task docs do not include a detail `body` field.
- Current shared task skill is `task-tool`; the new agreed skill surface is `$task-management`.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Main `instance input` sends Codex a composed text containing task-TUI followed by the original user input. |
| FR2 | Composition applies to both idle-thread `turn/start` and active-thread `turn/steer`. |
| FR3 | Composition does not apply to side conversation input in this version. |
| FR4 | Task-TUI is rendered from the same `TaskSnapshot` source used by `task.current`. |
| FR5 | Task-TUI clearly shows no-current-task state when taskbox history has no selected task. |
| FR6 | Task-TUI clearly shows current task id, title, status, progress summary, last event, pending confirmation, and recent history when present. |
| FR7 | Task-TUI includes a short task-handling cue and may mention `$task-management`, but does not copy the full skill text or force a tool call. |
| FR8 | `task.current` is read-only and returns the canonical `TaskSnapshot` with current task, pending confirmation, recent events, and task state. |
| FR9 | `task.propose(type=start)` creates a new task doc with `body`, selects it as current, and appends `task.create` history. |
| FR10 | `task.propose(type=switch)` creates a pending switch confirmation and appends `task.switch.requested` without changing the current task or creating a new target task doc. |
| FR11 | `task.confirm(decision=accept)` accepts a pending switch, updates the current task, creates the new target task only when the switch target is new, clears pending confirmation, and appends `task.switch.confirmed`. |
| FR12 | `task.confirm(decision=reject)` clears pending confirmation, keeps the current task unchanged, and appends `task.switch.rejected`. |
| FR13 | `task.propose(type=finish)` marks the current task done and appends `task.close`. |
| FR14 | `task.propose(type=block)` marks the current task blocked and appends `task.block`. |
| FR15 | Rejected task proposals and confirmations do not mutate taskbox task docs or history. |
| FR16 | The shipped task env tool actions are exactly `current`, `propose`, and `confirm`; old task actions are removed rather than kept as a compatibility path. |
| FR17 | The shared task skill is `$task-management`, topic/workflow-oriented, and not a JSON schema mirror. |
| FR18 | Manifest buddy permissions and skill lists use the new task action permissions and `task-management` skill id. |
| FR19 | Context catalog and runtime summaries point hosts to `task.current`, `task.propose`, and `task.confirm`, not old task actions. |
| FR20 | No direct writes occur under `buddyswitch/objects/**` or old buddybox runtime paths for task management. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | Launcher integration test captures fake Codex `turn/start` params and asserts composed text contains task-TUI before raw user input. |
| FR2 | Launcher integration test captures fake Codex `turn/steer` params and asserts the same composition behavior. |
| FR3 | Side conversation test asserts side `turn/start` still receives raw side text without task-TUI. |
| FR4 | Unit test renders TUI from a snapshot and compares key fields with `task.current` tool output for the same taskbox. |
| FR5 | TUI renderer unit test with empty history. |
| FR6 | TUI renderer unit test with active task, history tail, and pending switch confirmation. |
| FR7 | TUI renderer unit test asserts short cue exists and full topic text is absent. |
| FR8 | Env tool test calls `task.current` through broker and asserts `state_changed=false`, `durability=none`, and no file mutation. |
| FR9 | Env tool test calls `task.propose(start)` and inspects response, task doc JSON, and history. |
| FR10 | Env tool test calls `task.propose(switch)` and inspects pending confirmation plus unchanged current task. |
| FR11 | Env tool test accepts pending switch for existing and new targets. |
| FR12 | Env tool test rejects pending switch and asserts current task unchanged. |
| FR13 | Env tool test finishes current task and inspects status/history. |
| FR14 | Env tool test blocks current task and inspects status/history. |
| FR15 | Validation tests snapshot taskbox files/history before invalid calls and assert unchanged after rejection. |
| FR16 | Registry/schema tests assert supported task actions and reject old actions. |
| FR17 | Runtime skill tests inspect `buddyswitch/skills/shared/task-management/SKILL.md`. |
| FR18 | Manifest tests assert buddies reference `task-management` and new task permissions. |
| FR19 | Context tests assert decision surfaces and operation semantics name the new actions. |
| FR20 | Existing runtime boundary tests plus task tests assert no shared product object mutation. |

## Detailed Test Cases

### 1. Task Snapshot Empty State

File:

- Add or modify `tests/test_task_input_context.py`

Behavior:

- Create an instance with empty `taskbox/<buddy>/history.md` and no task docs.
- Call the shared snapshot reader.
- Assert:
  - `task_state == "none"`.
  - `current_task is None`.
  - `pending_confirmation is None`.
  - `recent_events == []`.
  - no files are created by the read.

### 2. Task Snapshot Reads History First And Loads Current Task

File:

- Add or modify `tests/test_task_input_context.py`

Behavior:

- Seed `history.md` with `task.create task-0001-alpha` and then `task.create task-0002-beta`.
- Seed both matching task docs.
- Call the shared snapshot reader.
- Assert:
  - current task is `task-0002-beta`.
  - the loaded current task includes title, status, summary, body excerpt, refs, and updated timestamp.
  - recent events preserve history order.
  - the test fails if snapshot selection comes only from directory sorting.

### 3. Task-TUI Empty State Rendering

File:

- Add or modify `tests/test_task_input_context.py`

Behavior:

- Render a TUI from an empty snapshot.
- Assert it contains:
  - `[TASK CONTEXT]`
  - `Current Task: none`
  - `State: none`
  - `Pending Confirmation: none`
  - `[USER INPUT]` is not part of the renderer output.

### 4. Task-TUI Current Task And Pending Confirmation Rendering

File:

- Add or modify `tests/test_task_input_context.py`

Behavior:

- Render a TUI from a snapshot with:
  - current active task;
  - progress summary from task summary/body;
  - `task.switch.requested` pending confirmation;
  - recent history tail.
- Assert it contains:
  - current task id/title/status;
  - pending confirmation id;
  - target task title or target task id;
  - a short cue mentioning `$task-management`;
  - no full skill section headings such as `Create New Task`, `Switch Task`, or `Tool Reference`.

### 5. `task.current` Tool Returns The Canonical Snapshot

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Seed taskbox history and docs.
- Dispatch `env.tool` with `tool=task`, `action=current`, `args={}`.
- Assert:
  - `ok=true`;
  - `action == "task.current"`;
  - `state_changed is False`;
  - `durability == "none"`;
  - `snapshot.current_task.id` matches the snapshot reader result;
  - no history line is appended by the read.

### 6. `task.propose(start)` Creates Current Task With Body

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Start from empty taskbox.
- Dispatch:

```json
{
  "type": "start",
  "task": {
    "title": "Clean runtime environment",
    "summary": "Refine task input context.",
    "body": "Detailed body for the task.",
    "priority": "normal",
    "refs": []
  },
  "reason": "User introduced a new task.",
  "evidence": "User asked to design task input context."
}
```

- Assert:
  - one task doc is created under `taskbox/<buddy>/tasks/`;
  - id follows `task-0001-clean-runtime-environment` style;
  - JSON includes `body`;
  - history includes `task.create`;
  - subsequent `task.current` returns that task.

### 7. `task.propose(start)` Rejects Unsafe Starts

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Seed a current active task.
- Dispatch `task.propose(type=start)`.
- Assert:
  - rejected with a correctable reason telling the host to use `task.propose(type=switch)` when replacing an active task;
  - no new task doc appears;
  - history is unchanged.

### 8. `task.propose(switch)` Creates Pending Confirmation

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Seed current active task.
- Dispatch switch to an existing target.
- Assert:
  - `pending_confirmation.confirmation_id` is returned;
  - current task remains unchanged;
  - history includes `task.switch.requested`;
  - subsequent `task.current` returns the pending confirmation.

Repeat for switch target mode `new` and assert no target task doc is created before confirmation.

### 9. `task.confirm` Accepts Or Rejects Pending Switch

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Seed a pending switch.
- Accept it:
  - existing target: current task changes to target task id;
  - new target: a new task doc is created then selected;
  - pending confirmation clears;
  - history includes `task.switch.confirmed`.
- Reject it:
  - current task remains the original task;
  - pending confirmation clears;
  - history includes `task.switch.rejected`.

### 10. `task.propose(finish)` And `task.propose(block)`

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Seed current active task.
- Finish it:
  - task status becomes `done`;
  - `closed_at` is set;
  - history includes `task.close`.
- Block it:
  - task status becomes `blocked`;
  - `closed_at` remains null;
  - history includes `task.block`.
- Reject both actions when `task_id` does not match the current task.

### 11. Invalid Payloads Do Not Mutate State

File:

- Replace current task env tool tests in `tests/test_task_env_tool.py`

Behavior:

- Snapshot task files and history before each invalid call.
- Invalid cases:
  - unknown `type`;
  - start missing task title;
  - start missing body;
  - switch missing target;
  - confirm with no pending confirmation;
  - confirmation id mismatch;
  - unsupported old publication-style fields such as `visibility`, `template`, or `source_refs`.
- Assert:
  - `ok=false`;
  - `state_changed=false`;
  - history and task files are unchanged.

### 12. Tool Catalog Replaces Old Task Actions

Files:

- Modify `tests/test_env_tool_schema_contract.py`
- Modify `tests/test_env_tool_router.py`
- Modify `tests/test_env_tool_semantic_contract.py`

Behavior:

- Assert supported task actions are exactly:

```text
current
propose
confirm
```

- Assert old actions `create`, `list`, `get`, `update`, `archive`, and `history` are unsupported.
- Assert operation semantics for:
  - `task.current` are read-only;
  - `task.propose` and `task.confirm` write only taskbox task/history state;
  - rejection guarantees no state mutation.

### 13. Launcher Input Composes Task-TUI Before Starting A Turn

File:

- Modify `tests/test_buddyswitch_launcher.py`

Behavior:

- Start a service instance with fake Codex app-server.
- Seed the instance taskbox with one current task and history.
- Run:

```bash
./buddyswitch-codex instance input <instance-id> --text "Continue the design"
```

- Read captured fake Codex `turn/start` params.
- Assert:
  - `params.input[0].text` starts with `[TASK CONTEXT]`;
  - task id/title/status appear before `[USER INPUT]`;
  - original text appears after `[USER INPUT]`;
  - permissions remain `buddyswitch-runtime`;
  - JSON/human launcher output remains unchanged.

### 14. Launcher Input Composes Task-TUI Before Steering A Turn

File:

- Modify `tests/test_buddyswitch_launcher.py`

Behavior:

- Start a service instance with fake Codex app-server in active-thread state.
- Seed the instance taskbox.
- Run `instance input`.
- Assert captured `turn/steer` params contain composed text in the same order and still include the expected turn id.

### 15. Side Input Is Not Composed In Version 1

File:

- Modify `tests/test_buddyswitch_launcher.py`

Behavior:

- Run side conversation create/send.
- Assert captured side `turn/start` or `turn/steer` input text equals the raw side text and does not contain `[TASK CONTEXT]`.

### 16. `$task-management` Skill Contract

Files:

- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_task_management_skill_architecture.py`

Behavior:

- Assert `buddyswitch/skills/shared/task-management/SKILL.md` exists.
- Assert manifest shared skill id is `task-management`, not `task-tool`.
- Assert buddy skill lists include `task-management`.
- Assert the skill contains topic/workflow sections:
  - `Continue Current Task`
  - `Create New Task`
  - `Switch Task`
  - `Confirm Pending Switch`
  - `Mark Done / Blocked`
  - `Tool Reference`
- Assert the skill does not duplicate full JSON schemas or old action names.

## Verification Commands

Focused verification after implementation:

```bash
python3 -m pytest tests/test_task_input_context.py tests/test_task_env_tool.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -k "input_ or side_" -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_task_management_skill_architecture.py -q
```

Broader verification before completion:

```bash
python3 -m pytest tests/test_task_input_context.py tests/test_task_env_tool.py tests/test_buddyswitch_launcher.py -k "input_ or side_" -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_task_management_skill_architecture.py -q
```

Because launcher tests start persistent services, follow the lifecycle rule from `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`: run focused launcher tests first and inspect residual fake Codex/app-server processes before expanding the launcher suite.

## Non-Goals For This Test Plan

- No Stop hook or running-end reconciliation.
- No gate, signed gate, daemon phase authority, allowed-list, or expiry.
- No independent persistent task daemon process.
- No automatic model behavior assertion; tests verify the context and tool contracts BuddySwitch controls.
- No frontend UI changes.
- No old task action compatibility path.

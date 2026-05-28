# Launcher Input Wrapper Boundary Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation and keep the red/green loop visible while executing this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reset `launcher input` to a raw-by-default base API, move Task TUI foreground composition behind an explicit `task-tui` wrapper, and remove all Task TUI knowledge from app-server transport without changing daemon STOP behavior.

**Architecture:** Keep wrapper selection launcher-owned. `buddyswitch-codex instance input` parses `--input-wrapper`, composes `final_text` through a small launcher wrapper selector, then passes only transport-level arguments into `app_server.input`. App-server transport remains pure JSON-RPC/thread/turn plumbing. Task TUI composition moves into a dedicated wrapper module outside app-server.

**Tech Stack:** Bash launcher entrypoint, Python launcher helpers, existing task snapshot/render domain modules, pytest/unittest integration tests, fake Codex RPC harness.

---

## Current Bottleneck

The current foreground input path is still architecturally coupled:

- launcher input does not expose wrapper intent;
- app-server transport composes Task TUI text internally;
- launcher default input is not raw;
- `--instance-json` leaks Task TUI-only context through transport arguments.

That shared path means ordinary launcher input changes and ordinary Task TUI changes still collide inside `app_server.py`. This plan removes that bottleneck directly. Do not keep the old implicit behavior behind fallback branches or aliases.

## Target File Structure

Create:

- `tools/launcher/input_wrapper.py`
  - launcher-owned wrapper selection contract;
  - wrapper composition entrypoint used by `instance input`;
  - no transport or daemon logic.

- `tools/launcher/input_wrappers/__init__.py`
  - small package marker only.

- `tools/launcher/input_wrappers/raw.py`
  - raw wrapper implementation.

- `tools/launcher/input_wrappers/task_tui.py`
  - explicit Task TUI foreground wrapper implementation.

- `tests/test_input_wrapper.py`
  - focused wrapper composition contract tests.

- `docs/spec/2026-05-28-launcher-input-wrapper-boundary-reset-test-plan.md`
  - requirements, test suites, verification commands.

- `docs/spec/2026-05-28-launcher-input-wrapper-boundary-reset-development-plan.md`
  - this implementation plan.

- `docs/spec/2026-05-28-launcher-input-wrapper-boundary-reset-execution-prompt.md`
  - clean Phase 2 execution prompt.

Modify:

- `buddyswitch-codex`
  - add `--input-wrapper raw|task-tui` to help and parsing;
  - default omitted wrapper to `raw`;
  - compose final text before calling app-server input.

- `tools/launcher/instance.sh`
  - update public usage text for `instance input`.

- `tools/launcher/app_server.sh`
  - stop forwarding `--instance-json` for input.

- `tools/launcher/app_server.py`
  - remove Task TUI import and compose logic from `_command_input`;
  - remove `input --instance-json` parser argument.

- `tests/test_app_server_client.py`
  - add transport-boundary parser/source assertions.

- `tests/test_buddyswitch_launcher.py`
  - switch default input expectations from implicit Task TUI to raw;
  - add explicit `task-tui` wrapper coverage;
  - add rejection and boundary regression checks.

Delete or replace:

- `tools/launcher/task_input_context.py`
  - its foreground composition logic moves into `tools/launcher/input_wrappers/task_tui.py`;
  - no lingering import path should remain in app-server transport.

Do not modify:

- daemon STOP checkout behavior in `tools/launcher/daemon_core.py` / `tools/launcher/task_checkout_handler.py`;
- task snapshot semantics in `scripts/env/domain/task_management.py`;
- Task TUI rendering contract in `scripts/env/domain/task_tui.py`.

## Public API Target

```bash
buddyswitch-codex instance input <instance-id> \
  --text <text> \
  [--input-wrapper raw|task-tui] \
  [--json]
```

Rules:

- default wrapper is `raw`;
- only `raw` and `task-tui` are valid;
- `task-ui` must be rejected;
- `--json` changes only launcher output format.

## Task 1: Write the Failing Boundary and Wrapper Tests

**Files:**

- Create: `tests/test_input_wrapper.py`
- Modify: `tests/test_app_server_client.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add focused wrapper tests**
  - Add unit tests for `raw`, `task-tui`, and unknown-wrapper rejection.
  - Use seeded taskbox data for `task-tui` so coverage follows the functional requirement instead of a fake string-only stub.

- [ ] **Step 2: Add app-server transport boundary tests**
  - Add parser/source assertions proving:
    - `input --instance-json` is rejected;
    - `app_server.py` source no longer references `task_input_context`, `compose_task_context_input`, or `TaskInputContextError`.

- [ ] **Step 3: Update launcher integration expectations to the new contract**
  - Change current default-input tests from implicit Task TUI assertions to raw assertions.
  - Add explicit `--input-wrapper task-tui` launcher integration coverage for idle start and active steer.
  - Add unknown-wrapper rejection coverage with zero RPC mutation.

- [ ] **Step 4: Run focused tests and confirm red**

```bash
python3 -m pytest tests/test_input_wrapper.py tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -q
```

Expected red result:

- missing `input_wrapper.py` / wrapper package;
- old default launcher behavior still sends Task TUI text;
- app-server parser still accepts `--instance-json`;
- source still contains Task TUI input coupling.

## Task 2: Add Launcher-Owned Wrapper Modules

**Files:**

- Create: `tools/launcher/input_wrapper.py`
- Create: `tools/launcher/input_wrappers/__init__.py`
- Create: `tools/launcher/input_wrappers/raw.py`
- Create: `tools/launcher/input_wrappers/task_tui.py`
- Delete: `tools/launcher/task_input_context.py`

- [ ] **Step 1: Implement explicit wrapper selection contract**
  - Add a small selector that accepts only `raw` and `task-tui`.
  - Unknown names must raise a wrapper selection error; no fallback/default aliasing inside the selector.

- [ ] **Step 2: Implement `raw` wrapper**
  - Return the original text unchanged.
  - Do not read instance state.

- [ ] **Step 3: Move Task TUI foreground composition into `task_tui.py`**
  - Reuse the current snapshot/render behavior from the old launcher input composition logic.
  - Keep wrapper-local error handling explicit for invalid/missing instance metadata.

- [ ] **Step 4: Add a small CLI entrypoint in `input_wrapper.py`**
  - Compose wrapper output for shell launcher use.
  - Exit `2` for wrapper-selection/argument errors and `1` for composition/runtime errors.

- [ ] **Step 5: Run focused wrapper tests and confirm green**

```bash
python3 -m pytest tests/test_input_wrapper.py -q
```

## Task 3: Move Wrapper Selection Into `instance input`

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/instance.sh`

- [ ] **Step 1: Extend public usage/help text**
  - Update both top-level help and instance help to show `[--input-wrapper raw|task-tui]`.

- [ ] **Step 2: Parse wrapper selection in `instance_input()`**
  - Default omitted wrapper to `raw`.
  - Reject unknown launcher options as before.

- [ ] **Step 3: Compose `final_text` before app-server transport**
  - Call `tools/launcher/input_wrapper.py`.
  - Pass the active instance record only to the launcher-owned wrapper composer.
  - Preserve existing thread-id, health, and steer-blocked behavior.

- [ ] **Step 4: Keep `--json` output-only**
  - Do not branch wrapper behavior on `json`.

- [ ] **Step 5: Run launcher input tests**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected after green:

- default launcher input sends raw text;
- explicit `task-tui` sends composed text;
- JSON output remains stable.

## Task 4: Strip Task TUI From App-Server Transport

**Files:**

- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tests/test_app_server_client.py`

- [ ] **Step 1: Remove Task TUI import and composition from `_command_input(...)`**
  - `input` should forward `args.text` unchanged into `input_turn(...)`.

- [ ] **Step 2: Remove `--instance-json` from the `input` parser and shell helper**
  - `app_server.py input` keeps only transport-level args:
    - `--socket`
    - `--thread-id`
    - `--text`
    - `--permissions`

- [ ] **Step 3: Re-run transport boundary tests**

```bash
python3 -m pytest tests/test_app_server_client.py -q
```

- [ ] **Step 4: Run source scan**

```bash
rg "compose_task_context_input|TaskInputContextError|--instance-json|task_input_context" tools/launcher/app_server.py tools/launcher/app_server.sh buddyswitch-codex
```

Expected result after cleanup:

- no hits in `app_server.py`;
- no `--instance-json` hit in `app_server.sh`;
- launcher hit only if it refers to wrapper-owned instance metadata outside transport, never to legacy Task TUI coupling names.

## Task 5: Run Regression Verification And Review

**Files:**

- No new product files unless verification reveals a real defect.

- [ ] **Step 1: Run focused wrapper + transport + launcher suite**

```bash
python3 -m pytest tests/test_input_wrapper.py tests/test_app_server_client.py tests/test_buddyswitch_launcher.py -q
```

- [ ] **Step 2: Run daemon STOP regression**

```bash
python3 -m pytest tests/test_task_checkout_handler.py tests/test_daemon_core.py -q
```

- [ ] **Step 3: Review against memo non-negotiables**
  - no implicit Task TUI default path;
  - no hidden fallback;
  - no `task-ui` alias;
  - no plugin/registry/workflow abstraction;
  - no daemon STOP behavior changes;
  - no app-server import of Task TUI;
  - no app-server `--instance-json` for input.

- [ ] **Step 4: Run `git status --short`**

```bash
git status --short
```

Expected result:

- only task-related files in this worktree are modified;
- no unintended main/worktree pollution.

## Review Checklist

Use this before declaring completion:

1. `instance input` defaults to raw in both idle and active-thread paths.
2. Explicit `task-tui` still produces current task context plus user input envelope.
3. Transport layer knows only socket/thread/text/permissions for input.
4. Old `task_input_context` transport coupling is removed rather than bypassed.
5. No alias or compatibility branch named `task-ui` exists.
6. daemon STOP tests remain green and unchanged in behavior.
7. Help text, launcher parsing, and wrapper selection all describe the same public API.

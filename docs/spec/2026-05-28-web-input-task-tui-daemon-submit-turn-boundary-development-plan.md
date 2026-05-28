# Web Input / Task TUI / Daemon Submit Turn Boundary Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation, then execute this plan task-by-task with focused verification after each block. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the current boundary cleanup so web input explicitly uses Task TUI, CLI input stays raw-by-default, and launcher-owned `submit_turn` becomes the shared send path for both foreground input and daemon checkout.

**Architecture:** Keep wrapper selection in launcher input. Add one launcher-owned `submit_turn` module that sends already-composed text through app-server transport. Make daemon task checkout request `actions.submit_turn(...)`, with daemon state updates still owned by `daemon_core.ActionGateway`.

**Tech Stack:** Bash launcher entrypoint, Python launcher helpers, app-server transport helper, existing Task TUI renderer, pytest/unittest, fake Codex integration harness.

---

## Current Bottleneck

The foreground wrapper split is already in place, but the broader boundary cleanup is incomplete:

- web input still bypasses explicit `task-tui`;
- daemon checkout still owns transport details through `ActionGateway.turn_start(...)`;
- task checkout handler still imports `app_server`.

That leaves two send paths with different ownership:

```text
web input -> launcher input -> app_server.input_turn
STOP checkout -> task_checkout_handler -> daemon ActionGateway direct turn/start
```

This plan removes that remaining split directly instead of layering a compatibility path around it.

## Target File Structure

Create:

- `tools/launcher/submit_turn.py`
  - launcher-owned shared send contract;
  - transport-level function and small CLI entrypoint;
  - no task snapshot reads;
  - no Task TUI wording;
  - no checkout semantics.

- `tests/test_submit_turn.py`
  - focused shared-send contract tests.

- `docs/spec/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary-test-plan.md`
  - requirements, coverage matrix, verification commands.

- `docs/spec/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary-development-plan.md`
  - this implementation plan.

- `docs/spec/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary-execution-prompt.md`
  - clean Phase 2 execution prompt.

Modify:

- `tools/launcher/web_management.py`
  - route web input through `instance input ... --input-wrapper task-tui --json`.

- `tests/test_web_management.py`
  - assert delegated launcher command includes `--input-wrapper task-tui`.

- `tools/launcher/daemon_core.py`
  - replace direct `turn/start` transport call with `ActionGateway.submit_turn(...)` delegating to launcher-owned `submit_turn`.

- `tools/launcher/task_checkout_handler.py`
  - drop `app_server` import;
  - request `actions.submit_turn(...)`;
  - catch launcher-owned submit-turn error instead of transport-layer errors directly.

- `tests/test_daemon_service_contract.py`
  - assert action gateway delegates to shared launcher submit layer;
  - keep handler-state observability assertions green.

- `tests/test_task_checkout_handler.py`
  - assert handler uses `submit_turn` and has no direct app-server import.

Keep unchanged unless tests expose a real defect:

- `buddyswitch-codex`
  - CLI default raw behavior already matches the memo and should stay that way.

- `tools/launcher/input_wrapper.py`
- `tools/launcher/input_wrappers/raw.py`
- `tools/launcher/input_wrappers/task_tui.py`
- `tools/launcher/app_server.py`
- `tools/launcher/app_server.sh`

## Public Behavior Target

### Web Input

```text
POST /api/instances/<id>/input
-> instance input <id> --text ... --input-wrapper task-tui --json
-> task-tui wrapper composes [TASK CONTEXT] + [USER INPUT]
-> launcher submit_turn
-> app-server transport
```

### CLI Input

```text
instance input <id> --text ...
-> raw
-> launcher submit_turn
-> app-server transport
```

Optional:

```text
instance input <id> --text ... --input-wrapper task-tui
-> task-tui wrapper
-> launcher submit_turn
-> app-server transport
```

### STOP Checkout

```text
turn/completed notification
-> task_checkout_handler
-> render [TASK CHECKOUT]
-> actions.submit_turn(...)
-> daemon ActionGateway delegates to launcher submit_turn
-> app-server transport
```

## Task 1: Write Current-Memo Failing Tests First

**Files:**

- Create: `tests/test_submit_turn.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_task_checkout_handler.py`

- [ ] **Step 1: Add failing web-input route assertions**
  - Update input-route tests so expected launcher command includes `--input-wrapper task-tui`.

- [ ] **Step 2: Add failing submit-turn unit tests**
  - Add direct delegation test for new `submit_turn.submit_turn(...)`.
  - Add source-scan test proving no task-domain coupling.

- [ ] **Step 3: Add failing daemon action-gateway delegation tests**
  - Replace direct `turn_start` expectations with `submit_turn`.
  - Assert action gateway delegates to launcher-owned `submit_turn`.

- [ ] **Step 4: Add failing handler boundary tests**
  - Assert `task_checkout_handler.py` has no `app_server` import.
  - Assert accepted notification uses `actions.submit_turn(...)`.

- [ ] **Step 5: Run focused tests and confirm red**

```bash
python3 -m pytest tests/test_submit_turn.py tests/test_web_management.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py -q
```

Expected red result:

- missing `submit_turn.py`;
- web input route still delegates without wrapper;
- daemon gateway/handler still use `turn_start` / direct app-server coupling.

## Task 2: Add Launcher-Owned Shared Submit Layer

**Files:**

- Create: `tools/launcher/submit_turn.py`
- Create: `tests/test_submit_turn.py`

- [ ] **Step 1: Implement pure shared function**
  - Add `submit_turn(socket_path, thread_id, text, permissions)` that delegates to `app_server.input_turn(...)` and returns its payload unchanged.

- [ ] **Step 2: Add launcher-owned error type**
  - Define `SubmitTurnError` for launcher/daemon callers that need a shared non-transport-specific failure type.
  - CLI entrypoint should normalize unexpected transport exceptions into exit `1` with stderr text.

- [ ] **Step 3: Add minimal CLI entrypoint**
  - Accept only transport-level arguments:
    - `--socket`
    - `--thread-id`
    - `--text`
    - `--permissions`
  - Emit JSON payload from `submit_turn(...)`.

- [ ] **Step 4: Run focused submit-turn tests**

```bash
python3 -m pytest tests/test_submit_turn.py -q
```

## Task 3: Route Web Input Through Explicit Task TUI

**Files:**

- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Update delegated launcher command**
  - Change `_run_input_command(...)` to append `--input-wrapper task-tui` before `--json`.

- [ ] **Step 2: Keep response parsing and busy-guard behavior unchanged**
  - Only the delegated command line changes; response JSON shape stays the same.

- [ ] **Step 3: Run focused web-management tests**

```bash
python3 -m pytest tests/test_web_management.py -q
```

Expected after green:

- web input explicitly requests `task-tui`;
- no bootstrap-marker leakage;
- web response shape remains stable.

## Task 4: Delegate Daemon Send Path To Launcher Submit Turn

**Files:**

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/task_checkout_handler.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_task_checkout_handler.py`

- [ ] **Step 1: Replace `ActionGateway.turn_start(...)` with `ActionGateway.submit_turn(...)`**
  - Delegate the actual send to launcher `submit_turn.submit_turn(...)`.
  - Keep daemon-origin tracking and handler-state recording in `daemon_core`.

- [ ] **Step 2: Normalize missing-turn-id failure at the action gateway boundary**
  - If shared submit-turn payload does not contain a `turn_id`, raise launcher-owned `SubmitTurnError`.
  - Do not record daemon-origin ids on failure.

- [ ] **Step 3: Remove task-checkout transport import**
  - Drop `app_server` import from `task_checkout_handler.py`.
  - Catch launcher-owned submit-turn error when `actions.submit_turn(...)` fails.

- [ ] **Step 4: Preserve STOP checkout prompt semantics**
  - `[TASK CHECKOUT]` render and handler-state fields must stay unchanged.

- [ ] **Step 5: Run focused daemon gateway / handler tests**

```bash
python3 -m pytest tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py -q
```

## Task 5: Run Regression Verification And Review

**Files:**

- No new product files unless verification reveals a real defect.

- [ ] **Step 1: Run focused current-memo suite**

```bash
python3 -m pytest tests/test_submit_turn.py tests/test_web_management.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py -q
```

- [ ] **Step 2: Run launcher and daemon regressions**

```bash
python3 -m pytest tests/test_input_wrapper.py tests/test_buddyswitch_launcher.py tests/test_daemon_core.py tests/test_daemon_core_decoupling.py -q
```

- [ ] **Step 3: Review against memo acceptance criteria**
  - web input uses `task-tui`;
  - CLI input default remains raw;
  - explicit CLI `task-tui` still works;
  - STOP checkout still sends `[TASK CHECKOUT]`;
  - daemon core stays task-agnostic;
  - task checkout handler has no `app_server` import;
  - daemon action gateway delegates to launcher submit-turn;
  - app-server stays transport-only.

- [ ] **Step 4: Run boundary scan**

```bash
rg "import app_server|task_tui|task_management|\\[TASK CONTEXT\\]|\\[TASK CHECKOUT\\]" tools/launcher/submit_turn.py tools/launcher/task_checkout_handler.py tools/launcher/app_server.py
```

- [ ] **Step 5: Run `git status --short`**

```bash
git status --short
```

Expected result:

- only files related to this memo are modified in this worktree;
- no `main` pollution or unrelated changes are introduced.

## Review Checklist

1. Web input explicitly opts into `task-tui` at the launcher boundary.
2. CLI default raw behavior remains unchanged.
3. Shared submit-turn module owns only transport-level send logic.
4. task checkout handler requests an action and does not import app-server.
5. daemon action gateway records origin/action/error observability fields exactly once.
6. STOP checkout behavior stays green in focused and fake-Codex regressions.
7. No alias, hidden fallback, plugin system, or central config hotspot is introduced.

# Web Input / Task TUI / Daemon Submit Turn Boundary Test Plan

Date: 2026-05-28

## Objective

Verify the boundary cleanup described in `docs/memo/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary.md`:

1. Web input automatically uses `task-tui`.
2. CLI `instance input` remains `raw` by default, with explicit `--input-wrapper task-tui`.
3. Web/CLI input and STOP checkout share a launcher-owned `submit_turn` send path.
4. daemon core stays task-agnostic.
5. task checkout handler stops knowing app-server transport.
6. existing STOP checkout behavior and observability remain intact.

This is a boundary cleanup task, not a compatibility layer task. The tests must prove the old transport coupling is removed rather than hidden behind aliases or fallback branches.

## Current Code Facts

- launcher foreground input already supports explicit wrappers and defaults to `raw`.
- `tools/launcher/web_management.py` still invokes `instance input` without `--input-wrapper task-tui`.
- no launcher-owned shared `submit_turn` module exists yet.
- `tools/launcher/daemon_core.py` `ActionGateway` still performs `turn/start` directly.
- `tools/launcher/task_checkout_handler.py` still imports `app_server` and catches transport errors directly.
- daemon STOP checkout behavior is already covered by daemon-core, task-checkout-handler, and fake-Codex integration tests.

## Functional Requirements

FR1. Web input must call launcher `instance input` with `--input-wrapper task-tui`.

FR2. CLI `instance input` without `--input-wrapper` must remain `raw`.

FR3. CLI `instance input --input-wrapper task-tui` must still send `[TASK CONTEXT]` plus `[USER INPUT]`.

FR4. A launcher-owned `submit_turn` contract must exist and be used by both launcher input and daemon checkout.

FR5. `submit_turn` must remain transport-level only:
- already-composed text in;
- app-server `input_turn(...)` out;
- no task snapshot read;
- no Task TUI wording;
- no checkout semantics.

FR6. `task_checkout_handler.py` must not import `app_server`.

FR7. task checkout handler must request `actions.submit_turn(...)` instead of directly knowing transport details.

FR8. daemon action gateway must delegate the actual send to launcher-owned `submit_turn`.

FR9. `daemon_core.py` must still not import `task_management` or `task_tui`.

FR10. STOP checkout behavior must remain unchanged:
- completed main-thread user turns trigger one `[TASK CHECKOUT]` send;
- daemon-origin turns are ignored;
- other-thread and malformed notifications are ignored;
- no handler means no checkout send.

FR11. daemon handler state must still preserve:
- `last_origin_turn_id`;
- `last_action_turn_id`;
- `last_result`;
- `last_error`.

FR12. app-server transport must remain Task-TUI-free and checkout-free.

## Required Automated Tests

### 1. Web Input Route Tests

File: `tests/test_web_management.py`

Cases:

- `test_input_route_delegates_with_task_tui_wrapper`
  - POST `/api/instances/<id>/input`.
  - Expected launcher command:
    `["instance", "input", "<id>", "--text", "...", "--input-wrapper", "task-tui", "--json"]`.

- `test_user_input_does_not_use_internal_bootstrap_marker`
  - Keep existing check, but assert the delegated launcher command still includes `--input-wrapper task-tui`.

- `test_input_route_reports_started_vs_steered_turn`
  - Keep current result-shape assertions and update expected delegated command to include `--input-wrapper task-tui`.

Purpose:
- proves the web path now opts into Task TUI explicitly;
- proves this is launcher-owned, not app-server-owned.

### 2. Launcher Submit-Turn Unit Tests

File: `tests/test_submit_turn.py`

Cases:

- `test_submit_turn_delegates_to_app_server_input_turn`
  - Patch `app_server.input_turn`.
  - Call `submit_turn.submit_turn(...)`.
  - Assert exact socket/thread/text/permissions delegation and unchanged payload return.

- `test_submit_turn_cli_emits_json_payload`
  - Invoke the helper parser/command with transport-level args only.
  - Assert stdout JSON includes `action` and `turn_id`/`expected_turn_id` as returned by the patched transport function.

- `test_submit_turn_has_no_task_tui_source_coupling`
  - Source-scan `tools/launcher/submit_turn.py`.
  - Assert no `task_tui`, `task_management`, `[TASK CONTEXT]`, `[TASK CHECKOUT]`, or `task_checkout` references.

Purpose:
- proves the shared send layer exists;
- proves it is launcher-owned and transport-level only.

### 3. Daemon Action Gateway And Handler Boundary Tests

Files:
- `tests/test_daemon_service_contract.py`
- `tests/test_task_checkout_handler.py`

Cases:

- `test_action_gateway_submit_turn_delegates_to_launcher_submit_turn`
  - Patch launcher `submit_turn.submit_turn`.
  - Call `ActionGateway.submit_turn(...)`.
  - Assert delegation uses main-thread id, daemon permissions, and composed text.

- `test_action_gateway_records_daemon_origin_and_handler_action_state_from_submit_turn`
  - Returned payload includes `action="start"` and `turn_id="turn-daemon-1"`.
  - Assert daemon-origin list and handler state fields are updated.

- `test_action_gateway_raises_launcher_submit_turn_error_when_no_turn_id_is_returned`
  - Returned payload lacks `turn_id`.
  - Assert gateway raises launcher-owned submit-turn error and does not record daemon-origin ids.

- `test_task_checkout_handler_source_has_no_app_server_import`
  - AST/source scan `task_checkout_handler.py`.
  - Assert no `import app_server`.

- `test_task_checkout_handler_uses_actions_submit_turn`
  - Fake actions object exposes `submit_turn`.
  - Accepted completion notification triggers one call to `submit_turn`.
  - Prompt still starts with `[TASK CHECKOUT]` and excludes `[TASK CONTEXT]` / `[USER INPUT]`.

- `test_submit_turn_failure_returns_failed_handler_result`
  - Fake actions raises launcher-owned submit-turn error.
  - Handler returns `HandlerResult.failed(...)`.

Purpose:
- proves handler no longer knows transport;
- proves daemon gateway delegates to the shared launcher submit layer.

### 4. Daemon Boundary Regression Tests

Files:
- `tests/test_daemon_core.py`
- `tests/test_daemon_core_decoupling.py`
- `tests/test_buddyswitch_launcher.py`

Keep or update these checks:

- daemon core still imports without task modules;
- no handler means no checkout send;
- daemon-origin turns do not loop;
- completed main-thread user turn still yields one `[TASK CHECKOUT]` send;
- handler state still records `last_origin_turn_id`, `last_action_turn_id`, `last_result`, `last_error`.

Purpose:
- proves the boundary change did not mutate daemon ownership or STOP behavior.

### 5. CLI Foreground Input Regression Tests

Files:
- `tests/test_input_wrapper.py`
- `tests/test_buddyswitch_launcher.py`

Keep these green:

- default CLI input remains raw;
- explicit `--input-wrapper task-tui` still composes Task TUI text;
- unknown wrapper rejection still prevents RPC mutation.

Purpose:
- proves web-path change did not regress launcher CLI input semantics.

### 6. Transport Boundary Scan Tests

Files:
- `tests/test_app_server_client.py`
- optionally `tests/test_submit_turn.py`

Checks:

- `tools/launcher/app_server.py` source still has no Task TUI foreground coupling.
- `tools/launcher/task_checkout_handler.py` source has no `app_server` import.
- `tools/launcher/submit_turn.py` contains only transport-level send logic.

Purpose:
- proves the transport boundary is still clean after the shared submit layer is introduced.

## Coverage Matrix

| Requirement | Test Groups |
| --- | --- |
| FR1 | 1 |
| FR2 | 5 |
| FR3 | 5 |
| FR4 | 2, 3 |
| FR5 | 2, 6 |
| FR6 | 3, 6 |
| FR7 | 3 |
| FR8 | 3 |
| FR9 | 4 |
| FR10 | 3, 4 |
| FR11 | 3, 4 |
| FR12 | 2, 6 |

## Verification Commands

Focused shared-send and handler checks:

```bash
python3 -m pytest tests/test_submit_turn.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py -q
```

Web input route checks:

```bash
python3 -m pytest tests/test_web_management.py -q
```

Launcher and daemon regression:

```bash
python3 -m pytest tests/test_input_wrapper.py tests/test_buddyswitch_launcher.py tests/test_daemon_core.py tests/test_daemon_core_decoupling.py -q
```

Boundary scan:

```bash
rg "import app_server|task_tui|task_management|\\[TASK CONTEXT\\]|\\[TASK CHECKOUT\\]" tools/launcher/submit_turn.py tools/launcher/task_checkout_handler.py tools/launcher/app_server.py
```

Expected boundary-scan result after completion:

- `submit_turn.py` has no task-domain or prompt-content coupling;
- `task_checkout_handler.py` has no `app_server` import;
- `app_server.py` remains free of Task TUI and checkout knowledge.

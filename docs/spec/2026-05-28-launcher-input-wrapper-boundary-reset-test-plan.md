# Launcher Input Wrapper Boundary Reset Test Plan

Date: 2026-05-28

## Objective

Verify the launcher/input boundary reset described in `docs/memo/2026-05-28-launcher-input-wrapper-boundary-reset.md`:

1. `launcher input` becomes a neutral base API again;
2. Task TUI becomes an explicit `task-tui` input wrapper;
3. app-server transport stops knowing Task TUI exists;
4. idle `turn/start` and active `turn/steer` behavior stays intact;
5. daemon STOP checkout behavior remains unchanged.

This is a boundary reset, not a compatibility migration. The tests must prove the old implicit Task TUI path is gone rather than renamed or hidden behind fallback logic.

## Current Code Facts

- `buddyswitch-codex instance input` currently accepts only `--text` and always forwards that text through `buddyswitch_app_server_input(...)`.
- `tools/launcher/app_server.sh` currently passes `--instance-json` into `tools/launcher/app_server.py input`.
- `tools/launcher/app_server.py` currently imports `task_input_context`, composes Task TUI text inside `_command_input(...)`, and exposes `input --instance-json`.
- `tools/launcher/task_input_context.py` currently owns Task TUI foreground input composition by reading the task snapshot and rendering `[TASK CONTEXT] ... [USER INPUT]`.
- `tests/test_buddyswitch_launcher.py` currently asserts the default `instance input` path sends Task TUI-wrapped text.
- daemon STOP behavior is already separately exercised through `task_checkout_handler.py` and fake Codex launcher integration tests.

## Functional Requirements

FR1. `buddyswitch-codex instance input <instance-id>` must accept `--input-wrapper raw|task-tui`.

FR2. Omitting `--input-wrapper` must behave exactly like `--input-wrapper raw`.

FR3. `raw` must send the original user text to `app_server.input_turn(...)` without reading task state and without injecting `[TASK CONTEXT]` or `[USER INPUT]`.

FR4. `task-tui` must explicitly read task state and send Task TUI-composed text that includes both `[TASK CONTEXT]` and `[USER INPUT]`.

FR5. Unknown wrapper values must be rejected. No RPC mutation may occur when wrapper validation fails.

FR6. `--json` must continue to change only launcher command output format. It must not change the actual text sent to Codex.

FR7. `tools/launcher/app_server.py` must not import Task TUI composition code, `task_input_context`, or any Task TUI-specific launcher wrapper helper.

FR8. `tools/launcher/app_server.py input` must no longer expose `--instance-json`.

FR9. `tools/launcher/app_server.sh` must no longer pass `--instance-json` into app-server input.

FR10. `input_turn(...)` behavior must stay transport-level only:

- idle thread => `turn/start`;
- active thread with in-progress turn => `turn/steer`;
- existing steer-blocked behavior stays unchanged.

FR11. No compatibility alias named `task-ui` may exist.

FR12. daemon STOP checkout behavior must remain unchanged and green.

## Required Automated Tests

### 1. Input Wrapper Unit Tests

File: `tests/test_input_wrapper.py`

Cases:

- `test_raw_wrapper_returns_raw_text_unchanged`
  - Compose wrapper text with `raw`.
  - Assert returned text is exactly the original user input.

- `test_task_tui_wrapper_renders_task_context_and_user_input`
  - Seed a current task in an instance taskbox.
  - Compose wrapper text with `task-tui`.
  - Assert result starts with `[TASK CONTEXT]`, includes current task fields, includes `[USER INPUT]`, and includes the raw user text after the envelope.

- `test_unknown_wrapper_name_is_rejected`
  - Call wrapper selection with `task-ui` and another unknown value.
  - Assert selection raises the wrapper selection error rather than silently falling back.

### 2. App-Server Transport Boundary Tests

File: `tests/test_app_server_client.py`

Cases:

- `test_input_command_requires_explicit_permissions_profile`
  - Keep existing coverage.

- `test_input_command_rejects_legacy_instance_json_argument`
  - Parse `app_server.py input --instance-json ...`.
  - Assert argparse exits with error.

- `test_app_server_source_has_no_task_tui_input_coupling`
  - Read `tools/launcher/app_server.py`.
  - Assert source does not contain `task_input_context`, `compose_task_context_input`, or `TaskInputContextError`.

### 3. Launcher Input Integration Tests

File: `tests/test_buddyswitch_launcher.py`

Cases:

- `test_input_starts_turn_when_thread_idle_defaults_to_raw`
  - Run `instance input --text "Draft brief"`.
  - Assert RPC methods include `thread/read` and `turn/start`, not `turn/steer`.
  - Assert the sent text is exactly `Draft brief`.
  - Assert the sent text does not contain `[TASK CONTEXT]` or `[USER INPUT]`.

- `test_input_json_starts_turn_when_thread_idle_without_changing_sent_text`
  - Run `instance input --text "Draft brief" --json`.
  - Assert JSON response shape remains valid.
  - Assert the RPC `turn/start` payload still sends exactly `Draft brief`.

- `test_input_steers_in_progress_turn_defaults_to_raw`
  - Seed active thread state.
  - Run `instance input --text "Steer current turn"`.
  - Assert RPC methods include `thread/read`, `thread/turns/list`, and `turn/steer`.
  - Assert sent text is exactly `Steer current turn`.

- `test_input_task_tui_wrapper_starts_turn_when_thread_idle`
  - Seed a current task.
  - Run `instance input --text "Draft brief" --input-wrapper task-tui`.
  - Assert sent text is Task TUI-composed and includes `[TASK CONTEXT]` plus `[USER INPUT]`.

- `test_input_task_tui_wrapper_steers_in_progress_turn`
  - Seed a current task and active thread state.
  - Run `instance input --text "Steer current turn" --input-wrapper task-tui`.
  - Assert `turn/steer` payload contains Task TUI-composed text.

- `test_input_rejects_unknown_wrapper_without_rpc_mutation`
  - Run `instance input --text "Draft brief" --input-wrapper task-ui`.
  - Assert nonzero exit.
  - Assert RPC call log has no new `turn/start` or `turn/steer`.

### 4. Boundary Scan Tests

File: `tests/test_buddyswitch_launcher.py` or `tests/test_app_server_client.py`

Cases:

- `test_launcher_input_source_mentions_only_raw_and_task_tui_wrapper_names`
  - Read launcher source involved in input wrapper parsing.
  - Assert `task-tui` is present if needed for help/validation.
  - Assert `task-ui` is absent.

- `test_app_server_shell_does_not_forward_instance_json_for_input`
  - Read `tools/launcher/app_server.sh`.
  - Assert the input helper invocation does not include `--instance-json`.

### 5. Daemon / STOP Regression Tests

Keep these suites green without behavior changes:

- `tests/test_task_checkout_handler.py`
- `tests/test_daemon_core.py`
- fake Codex STOP checkout integration coverage already in `tests/test_buddyswitch_launcher.py`

Purpose:

- proves foreground input refactor did not mutate daemon STOP ownership;
- proves STOP Task TUI still remains daemon-side only.

## Coverage Matrix

| Requirement | Test Groups |
| --- | --- |
| FR1 | 1, 3 |
| FR2 | 3 |
| FR3 | 1, 3 |
| FR4 | 1, 3 |
| FR5 | 1, 3 |
| FR6 | 3 |
| FR7 | 2 |
| FR8 | 2 |
| FR9 | 4 |
| FR10 | 3 |
| FR11 | 1, 4 |
| FR12 | 5 |

## Verification Commands

Focused wrapper and transport checks:

```bash
python3 -m pytest tests/test_input_wrapper.py tests/test_app_server_client.py -q
```

Launcher input regression:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Daemon / STOP regression:

```bash
python3 -m pytest tests/test_task_checkout_handler.py tests/test_daemon_core.py -q
```

Boundary scan:

```bash
rg "compose_task_context_input|TaskInputContextError|--instance-json|task_input_context" tools/launcher/app_server.py tools/launcher/app_server.sh buddyswitch-codex
```

Expected boundary-scan result after cleanup:

- no hits in `tools/launcher/app_server.py`;
- no `--instance-json` hit in `tools/launcher/app_server.sh`;
- no Task TUI coupling hit in `buddyswitch-codex` beyond explicit `task-tui` wrapper selection/help text.

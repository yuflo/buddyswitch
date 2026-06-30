# Phase 4: Minimal Structured Runtime Breadcrumb Logs

Date: 2026-06-30

## 1. Phase Goal

Write small structured JSONL breadcrumbs at daemon, app-server, runtime-broker, and Task Sys instruction boundaries so the daemon / handler / Task Sys path is diagnosable without reading raw session JSONL or product object records.

## 2. Current Code Investigation Results

- `runtime/daemon/daemon.log`, `runtime/app-server.log`, and `runtime/runtime-broker.log` already exist as service log files.
- `tools/launcher/daemon_core.py` starts/stops daemon processes and dispatches notifications to handlers, but it does not write structured lifecycle or handler-result events.
- `tools/launcher/app_server.py` starts and stops Codex app-server, but the log file only captures process stdout/stderr.
- `scripts/runtime_kernel/lifecycle.py` starts/stops runtime broker, but the log file only captures broker stdout/stderr.
- Task Sys instruction execution is reached through `scripts/env/tool_runtime/context.py::DaemonAccess.execute_task_sys_instruction(...)`; that boundary currently returns runtime executor results without a breadcrumb.

## 3. Owning Module And System Boundary

- `tools/launcher/runtime_event_log.py` owns append-only JSONL breadcrumb formatting.
- Lifecycle modules decide when a boundary event occurred and pass compact metadata to the helper.
- Breadcrumbs are observability only. They do not own task state, handler state, message state, or delivery state.

## 4. Explicit Non-Goals

- Do not create log levels, subscribers, trace ids, sampling, event buses, or a logging platform.
- Do not log raw IM message content, artifact bodies, browser page content, credentials, full prompts, or full tool payloads.
- Do not change status log metadata in this phase; Phase 5 owns compact log metadata in status.
- Do not modify prohibited parallel iMessage channel/API files.

## 5. Planned File Changes

- Create `tools/launcher/runtime_event_log.py`
  - Add `append_event(log_path, *, service, event, **fields)`.
- Modify `tools/launcher/daemon_core.py`
  - Write `daemon_started`, `daemon_ready`, `notification_received`, `handler_result`, `handler_failed`, and `daemon_stopped`.
- Modify `tools/launcher/app_server.py`
  - Write `app_server_start_requested`, `app_server_ready`, and `app_server_stop_requested`.
- Modify `scripts/runtime_kernel/lifecycle.py`
  - Write `runtime_broker_start_requested`, `runtime_broker_ready`, and `runtime_broker_stop_requested`.
- Modify `scripts/env/tool_runtime/context.py`
  - Write `task_sys_instruction_executed` after Task Sys runtime instruction execution.
- Modify focused tests in `tests/test_daemon_service_contract.py`, `tests/test_buddyswitch_launcher.py`, and `tests/test_runless_runtime_contract.py`.

## 6. Test Plan

Write these failing tests first:

- `tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_dispatch_writes_handler_result_breadcrumb_without_message_content`
  - Covers daemon dispatch breadcrumbs and content redaction.
  - Expected failure before implementation: no structured daemon breadcrumb helper/events exist.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_role_writes_daemon_and_app_server_breadcrumbs`
  - Covers service-start lifecycle breadcrumbs through the existing start flow.
  - Expected failure before implementation: logs do not contain JSONL lifecycle events.
- `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_runtime_broker_lifecycle_writes_breadcrumb_log`
  - Covers runtime broker start/ready/stop breadcrumbs.
  - Expected failure before implementation: broker log has no structured lifecycle events.

Focused RED command:

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_dispatch_writes_handler_result_breadcrumb_without_message_content tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_role_writes_daemon_and_app_server_breadcrumbs tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_runtime_broker_lifecycle_writes_breadcrumb_log
```

## 7. Implementation Steps

1. Add the failing breadcrumb tests.
2. Run the focused RED command and confirm failures match missing JSONL events.
3. Implement `runtime_event_log.append_event(...)`.
4. Add daemon lifecycle and dispatch event calls with compact fields only.
5. Add app-server lifecycle event calls.
6. Add runtime-broker lifecycle event calls.
7. Add Task Sys instruction execution breadcrumb in env tool runtime context.
8. Run the focused tests until green.
9. Run phase py_compile.
10. Run residue scans for prohibited content patterns and prohibited files.
11. Update this document with actual RED/GREEN verification output summary and residue results.

## 8. Verification Commands

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_dispatch_writes_handler_result_breadcrumb_without_message_content tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_role_writes_daemon_and_app_server_breadcrumbs tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_runtime_broker_lifecycle_writes_breadcrumb_log
python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py
```

## 9. Residue Scan Commands

```bash
rg -n "raw_message|message_content|artifact_body|full_prompt|credentials|tool_payload|event bus|trace id|sampling" tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py tests docs/spec -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected residue results:

- No breadcrumb code or tests log raw content or introduce a generic tracing/event system.
- The prohibited-file scan returns no output.

## 10. Exit Criteria

- Focused breadcrumb tests pass.
- Phase py_compile passes.
- Residue scans match expected output or every remaining hit is recorded as a valid negative assertion.
- `git diff --name-only` does not include prohibited parallel iMessage files.
- This document includes actual RED failure summary, final verification summary, residue summary, and any implementation deviations.

## 11. Actual Phase Result

RED verification:

- Command: `python3 -m pytest -q tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_dispatch_writes_handler_result_breadcrumb_without_message_content tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_role_writes_daemon_and_app_server_breadcrumbs tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_runtime_broker_lifecycle_writes_breadcrumb_log`
- Result before implementation: expected failures from missing structured daemon/app-server/runtime-broker breadcrumb events.
- After the first implementation pass, copied per-instance runtime broker startup exposed a real integration failure: `ModuleNotFoundError: No module named 'runtime_event_log'` from `scripts/runtime_kernel/lifecycle.py`.

Implementation summary:

- Added `tools/launcher/runtime_event_log.py` for launcher-owned JSONL breadcrumb writes.
- Added daemon lifecycle and handler dispatch breadcrumbs without logging raw notification/message content.
- Added app-server start/ready/stop breadcrumbs.
- Added runtime-broker start/ready/stop breadcrumbs with a local helper inside `scripts/runtime_kernel/lifecycle.py`, because that file is copied into sparse instance workspaces and must not import launcher-only helpers.
- Added best-effort Task Sys instruction execution breadcrumbs after runtime instruction execution.

Final verification:

- Focused Phase 4 command passed: 3 passed.
- `python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py` passed.
- `python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py` passed after Phase 5: 35 passed, 6 subtests passed.
- `python3 -m pytest -q tests/test_buddyswitch_launcher.py` passed after Phase 5: 202 passed, 40 subtests passed.

Residue summary:

- Live breadcrumb/status code has no `raw_message`, message-content, artifact-body, prompt, credential, tool-payload, tracing, sampling, or event-bus residue.
- Broad scans still report docs and negative assertions that intentionally name forbidden patterns.
- The prohibited-file scan returned no output.

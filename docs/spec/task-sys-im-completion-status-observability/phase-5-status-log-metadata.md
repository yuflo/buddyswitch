# Phase 5: Compact Status Log Metadata

Date: 2026-06-30

## 1. Phase Goal

Expose compact metadata for existing runtime service logs in `instance status --json` so operators can see whether the daemon, app-server, and runtime-broker logs exist and what their last structured breadcrumb event is.

## 2. Current Code Investigation Results

- `tools/launcher/daemon_core.py::daemon_status(...)` already returns the daemon `log_path`, but not a compact log object.
- `tools/launcher/app_server.py::app_server_status(...)` already returns `log_file`, but not a compact log object.
- `scripts/runtime_kernel/lifecycle.py::broker_status(...)` already returns `log_file`, but launcher status does not include runtime-broker status.
- Phase 4 added structured JSONL breadcrumbs to the service logs. Status must expose only the last structured event, not arbitrary log text.

## 3. Owning Module And System Boundary

- Each service status payload owns metadata for its own log path.
- `buddyswitch-codex instance status` composes daemon, app-server, and runtime-broker status payloads.
- Status log metadata is read-only observability. It must not mutate logs, task records, message records, or runtime process state.

## 4. Explicit Non-Goals

- Do not add log tails, raw stderr, prompt text, message bodies, artifact bodies, credentials, or tool payloads to status.
- Do not add tracing, sampling, subscriptions, or a generic event system.
- Do not use status as proof of external iMessage phone delivery.
- Do not modify prohibited parallel iMessage channel/API files.

## 5. Planned File Changes

- Modify `tools/launcher/daemon_core.py`
  - Add compact log metadata helper.
  - Include `daemon["log"]`.
- Modify `tools/launcher/app_server.py`
  - Add compact log metadata helper.
  - Include `app_server["log"]`.
- Modify `scripts/runtime_kernel/lifecycle.py`
  - Add compact log metadata helper.
  - Include `runtime_broker["log"]` in broker status.
- Modify `tools/launcher/runtime_broker.sh`
  - Add a status JSON helper for `buddyswitch-codex`.
- Modify `buddyswitch-codex`
  - Include `runtime_broker` in `instance status --json`.
- Modify `tests/test_buddyswitch_launcher.py`
  - Add `test_instance_status_json_reports_log_metadata`.

## 6. Test Plan

Write the failing test first:

- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata`
  - Starts a service instance through the existing fake launcher path.
  - Calls `instance status --json`.
  - Asserts daemon/app-server/runtime-broker each have `log.path`, `log.exists`, `log.size_bytes`, `log.mtime`, and `log.last_event`.
  - Asserts last events are compact JSON objects and do not include raw message/prompt/tool payload fields.

Focused RED command:

```bash
python3 -m pytest -q tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata
```

Expected RED result:

- Failure because status payloads do not include compact `log` metadata and launcher status does not include `runtime_broker`.

## 7. Implementation Steps

1. Add the failing launcher status test.
2. Run the focused RED command and confirm failure is missing log metadata.
3. Add compact log metadata helpers to daemon, app-server, and runtime-broker lifecycle status.
4. Add `buddyswitch_runtime_broker_status_json` and include it in `instance_status_json`.
5. Run focused test until green.
6. Run broader daemon/launcher/runless verification.
7. Run py_compile and residue scans.
8. Update this document with actual RED/GREEN verification output summary and residue results.

## 8. Verification Commands

```bash
python3 -m pytest -q tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py tests/test_buddyswitch_launcher.py
python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py
```

## 9. Residue Scan Commands

```bash
rg -n "raw_message|message_content|artifact_body|full_prompt|credentials|tool_payload|event bus|trace id|sampling" tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py tests docs/spec -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected residue results:

- No status metadata exposes raw log tails or sensitive content.
- The prohibited-file scan returns no output.

## 10. Exit Criteria

- Focused status log metadata test passes.
- Daemon, app-server, and runtime-broker status payloads expose compact log metadata.
- Status exposes only the last structured event, not raw stderr/text tails.
- Broader daemon/launcher/runless verification passes.
- This document includes actual RED failure summary, final verification summary, residue summary, and implementation deviations.

## 11. Actual Phase Result

RED verification:

- Command: `python3 -m pytest -q tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata`
- Result before implementation: failed with `KeyError: 'log'` at `payload["daemon"]["log"]`.
- The failure matched the expected missing status metadata; setup and service startup succeeded.

Implementation summary:

- Added `runtime_event_log.log_metadata(...)` for launcher-owned daemon/app-server log metadata.
- Added `daemon["log"]` and `app_server["log"]` status payloads.
- Added a local runtime-broker log metadata helper in `scripts/runtime_kernel/lifecycle.py` so copied sparse workspaces remain self-contained.
- Added `buddyswitch_runtime_broker_status_json` and included top-level `runtime_broker` in `buddyswitch-codex instance status --json`.
- Status metadata exposes `path`, `exists`, `size_bytes`, `mtime`, and `last_event`, and does not expose raw log tails.

Final verification:

- `python3 -m pytest -q tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata` passed: 1 passed.
- `python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py` passed.
- `bash -n buddyswitch-codex` passed.
- `bash -n tools/launcher/runtime_broker.sh` passed.
- `python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py` passed: 35 passed, 6 subtests passed.
- `python3 -m pytest -q tests/test_buddyswitch_launcher.py` passed: 202 passed, 40 subtests passed.
- `python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py tests/test_role_action_auth.py tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py` passed: 111 passed, 510 subtests passed.

Residue summary:

- Live status/logging code has no sensitive-content or generic tracing/event-system residue.
- Broad scans report only historical docs, current non-goal text, and tests that assert forbidden fields are absent.
- The prohibited-file scan returned no output.

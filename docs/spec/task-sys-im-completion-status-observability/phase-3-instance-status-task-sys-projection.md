# Phase 3: Instance Status Task Sys Residue Projection

Date: 2026-06-30

## 1. Phase Goal

Add a read-only Task Sys active-residue projection to daemon and instance status, and make human status clearly distinguish daemon handler dispatch health from external iMessage delivery.

## 2. Current Code Investigation Results

- `tools/launcher/daemon_core.py::daemon_status(...)` currently returns daemon liveness, runtime calls, schedules, handlers, and notify subscriptions.
- Handler items expose `last_result`, but there is no field that explains handler result scope.
- Active Task Sys records already live under the Task Sys domain object store and can be read with `env.domain.task_sys.active_tasks_for_actor(...)` when runtime roots are bound.
- `buddyswitch-codex instance status --json` embeds daemon status JSON directly under `payload["daemon"]`, so adding `daemon["task_sys"]` is enough for JSON status.
- Human `buddyswitch-codex instance status` prints app-server health, daemon health, handler names, thread id/status, browser port, workspace, and updated time. It does not print Task Sys active count, active statuses, or delivery-scope language.
- Existing launcher status tests start services; Phase 3 should add focused assertions to existing status tests rather than broad new service-starting flows.

## 3. Owning Module And System Boundary

- Task Sys domain owns task lifecycle state and active task semantics.
- Daemon status owns a read-only projection of active Task Sys residue for the active actor.
- Handler status remains handler-specific; it must not claim external iMessage delivery.
- Instance status is a presentation layer over daemon status JSON.

## 4. Explicit Non-Goals

- Do not mutate Task Sys records from status.
- Do not copy or reimplement the Task Sys state machine inside daemon status.
- Do not read Central IM message bodies or iMessage channel local state.
- Do not prove phone delivery in this branch.
- Do not modify prohibited parallel iMessage channel/API files.

## 5. Planned File Changes

- Modify `tools/launcher/daemon_core.py`
  - Add `_task_sys_status_payload(context)` that calls Task Sys read APIs and returns active count, counts by status, and compact active task summaries.
  - Add handler result scope metadata without changing handler lifecycle behavior.
  - Include `task_sys` in `daemon_status(...)`.
- Modify `buddyswitch-codex`
  - Print `Task Sys active: N`.
  - Print `Task Sys active statuses: status=count` when active tasks exist.
  - Print `Delivery scope: daemon handler status is trigger-dispatch only; external channel delivery is separate.`
- Modify `tests/test_daemon_service_contract.py`
  - Add focused daemon status projection and handler-scope tests.
- Modify `tests/test_buddyswitch_launcher.py`
  - Add JSON and human status assertions to existing service-starting status tests.

## 6. Test Plan

Write these failing tests first:

- `tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_daemon_status_includes_task_sys_active_projection`
  - Covers daemon read-only projection shape from real Task Sys records.
  - Expected failure before implementation: `daemon_status(...)` has no `task_sys` key.
- `tests/test_daemon_service_contract.py::DaemonServiceContractTests::test_handler_status_result_scope_does_not_claim_external_delivery`
  - Covers handler status scope metadata and ensures `im_message_created.last_result` remains dispatch-only.
  - Expected failure before implementation: handler item has no result-scope field.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary`
  - Covers JSON status pass-through under `daemon.task_sys`.
  - Expected failure before implementation: JSON status has no Task Sys active summary.
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_human_status_reports_task_sys_active_and_delivery_scope`
  - Covers human-readable active count/statuses and delivery-scope warning.
  - Expected failure before implementation: human status prints no Task Sys lines.

Focused RED command:

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_human_status_reports_task_sys_active_and_delivery_scope
```

## 7. Implementation Steps

1. Add the failing daemon status and launcher status tests.
2. Run the focused RED command and confirm failures match missing Task Sys projection and delivery-scope lines.
3. Implement `_task_sys_status_payload(context)` in `daemon_core.py` using Task Sys read APIs only.
4. Add `result_scope` or equivalent compact metadata to handler status items so `last_result` is explicit dispatch/handler status.
5. Include `task_sys` in `daemon_status(...)`.
6. Update human status printing in `buddyswitch-codex`.
7. Run the focused tests until green.
8. Run phase py_compile.
9. Run boundary/residue checks.
10. Update this document with actual RED/GREEN verification output summary and residue results.

## 8. Verification Commands

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_human_status_reports_task_sys_active_and_delivery_scope
python3 -m py_compile tools/launcher/daemon_core.py
```

## 9. Residue Scan Commands

```bash
delivery_claim_regex="$(printf '%s%s%s%s%s%s' 'external.*deliv' 'ered|phone.*deliv' 'ered|last_result.*deliv' 'ery|Central IM replied.*deliv' 'ered')"
rg -n "${delivery_claim_regex}" tools/launcher/daemon_core.py buddyswitch-codex tests docs/spec -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected residue results:

- No handler status text claims external phone delivery.
- The prohibited-file scan returns no output.

## 10. Exit Criteria

- Focused daemon/status tests pass.
- `tools/launcher/daemon_core.py` compiles.
- Residue scans match expected output or every remaining hit is recorded as a valid negative assertion.
- `git diff --name-only` does not include prohibited parallel iMessage files.
- This document includes actual RED failure summary, final verification summary, residue summary, and any implementation deviations.

## 11. Actual Phase Result

RED verification:

- Command: `python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_human_status_reports_task_sys_active_and_delivery_scope`
- Result before implementation: 4 failed, 21 passed.
- Expected failures were observed: daemon status had no `task_sys` projection, handler items had no result scope, JSON status had no Task Sys summary, and human status printed no Task Sys or delivery-scope lines.

Implementation summary:

- Added read-only daemon `task_sys` projection with active count, by-status counts, and compact active task summaries.
- Added handler `result_scope: trigger_dispatch` metadata.
- Updated human `instance status` output with Task Sys active count, active status counts, and delivery-scope language.
- Kept status read-only and did not inspect Central IM bodies or iMessage channel state.

Final verification:

- `python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_human_status_reports_task_sys_active_and_delivery_scope` passed: 25 passed.
- `python3 -m py_compile tools/launcher/daemon_core.py` passed.

Residue summary:

- Delivery-claim residue scan returned no live claims after splitting the scan literal in this doc.
- The prohibited-file scan returned no output.

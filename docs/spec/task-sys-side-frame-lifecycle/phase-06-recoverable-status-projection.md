# Phase 06 Recoverable Status Projection Plan

Date: 2026-06-30

## Current Problem And Evidence

Phase 01 added recoverable Task Sys statuses, but live status surfaces still project active tasks
only:

- `daemon_core._task_sys_status_payload()` filters records by `ACTIVE_TASK_STATUSES`.
- `web_management._actor_console()` calls `task_sys.active_tasks_for_actor()` only.
- Tests assert only `active_count`, `by_status`, and `active_tasks`.

Operators cannot see `runtime_failed`, `side_no_result`, or `side_timed_out` once those tasks leave
active processing.

## Target Behavior

Daemon and Web status project active and recoverable Task Sys work separately:

- `active_count`, `by_status`, `active_tasks`;
- `recoverable_count`, `recoverable_by_status`, `recoverable_tasks`.

Recoverable task summaries include:

- `task_id`;
- `source_type`;
- `source_ref`;
- `status`;
- `active_processor`;
- `failure_result` summary;
- `updated_at`.

Status remains a projection only; Task Sys domain still owns state semantics.

## Files

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_web_management.py`

## Old Path / Residue Definition

Old residue is any status surface where recoverable side failures disappear because only active
Task Sys tasks are shown.

## Implementation Steps

1. Add failing daemon status test with one active and one `runtime_failed` task.
2. Add failing launcher status test with active and recoverable task summaries.
3. Add failing Web actor console test for distinct active/recoverable counts.
4. Run focused tests and confirm recoverable fields are missing.
5. Extend daemon status projection.
6. Extend Web actor console projection using Task Sys domain active/recoverable queries.
7. Run focused tests, compile gate, and projection scan.

## Test Plan

Focused red/green command:

```bash
python -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_web_management.py::WebManagementTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection
```

Expected red before implementation:

- recoverable count/task fields are missing.

Focused green expectation:

- focused daemon, launcher, and web status tests pass.

Compile gate:

```bash
python -m py_compile tools/launcher/daemon_core.py tools/launcher/web_management.py
```

## Residue Scan Plan

```bash
rg -n "recoverable_count|recoverable_tasks|recoverable_by_status|RECOVERABLE_TASK_STATUSES|recoverable_tasks_for_actor" tools/launcher tools/launcher/web_management.py tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py tests/test_web_management.py -S
```

Expected:

- hits define or assert recoverable projection fields.

## Acceptance Criteria

- Daemon status shows active and recoverable Task Sys counts separately.
- Launcher `instance status --json` includes recoverable projection under `daemon.task_sys`.
- Web actor console includes recoverable task summaries.
- Failure metadata summary is visible without introducing daemon-owned state semantics.
- Focused tests and compile gate pass.

## Test Resource Lifecycle Requirements

Phase 06 uses existing unit/service test harnesses. It must not start additional live actors beyond
the existing focused launcher test helper. No broad live smoke is allowed in this phase.

## Actual Changes

- Extended daemon Task Sys status projection with `recoverable_count`, `recoverable_by_status`, and
  `recoverable_tasks`.
- Added recoverable failure summaries with `failure_result` in daemon status.
- Extended Web actor console Task Sys projection with `recoverable_count` and `recoverable_tasks`.
- Added daemon, launcher status, and Web console regression coverage for active/recoverable counts.

## Actual Verification

- Red check:
  - `python -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection`
  - Result: failed as expected because `recoverable_count` and related fields were missing.
- Focused green check:
  - `python -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection`
  - Result: `26 passed`.
- Compile gate:
  - `python -m py_compile tools/launcher/daemon_core.py tools/launcher/web_management.py`
  - Result: pass.
- Recoverable projection scan:
  - `rg -n "recoverable_count|recoverable_tasks|recoverable_by_status|RECOVERABLE_TASK_STATUSES|recoverable_tasks_for_actor" tools/launcher tools/launcher/web_management.py tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py tests/test_web_management.py -S`
  - Result: hits define or assert recoverable projection fields.

## Acceptance Status

Accepted for Phase 06. Daemon, launcher status, and Web console surfaces now distinguish active Task
Sys work from recoverable side lifecycle failures.

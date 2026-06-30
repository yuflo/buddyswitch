# Phase 08 End-To-End Acceptance And Resource-Gated Smoke Plan

Date: 2026-06-30

## Current Problem And Evidence

The implementation phases prove Task Sys side-frame lifecycle behavior at domain, runtime, tool,
daemon, and Web projection boundaries. The remaining proof is consumer-visible: one External IM
message must flow through wake, a fresh Task Sys side thread, exact reply, task close, event ack,
and clean runtime residue.

The previous exploratory acceptance run in
`docs/spec/task-sys-exploratory-acceptance/01-run-log.md` exposed stale side-thread reuse and active
`side_processing` residue. Phase 08 must prove that the new implementation fixes that path without
starting broad matrix testing.

## Target Contract

```text
External IM send -> IM wake -> Task Sys side frame -> fresh side thread -> exact reply/close -> status active_count=0 and no Task Sys side lease remains.
```

## Files

- Modify: `docs/spec/task-sys-exploratory-acceptance/00-test-plan.md`
- Modify: this Phase 08 acceptance record.

## Resource Lifecycle Requirements

- Run focused unit/integration tests and compile checks before live smoke.
- Record current actor/resource baseline before starting any test-owned actor.
- Prefer a fresh test-owned actor so pre-existing actors are not mutated.
- Use the Integration External IM API only; do not use iMessage or `/api/web/im/*`.
- Keep the External IM connection key only in process memory.
- Stop the test-owned actor after the smoke, regardless of pass/fail.
- After smoke, verify:
  - no test-owned actor is left running;
  - no test-owned `task_sys.side_frame` side lease remains;
  - no unexpected `side_processing` task remains;
  - any consumed External IM reply event is acked.

## Implementation Steps

1. Update `00-test-plan.md` with the focused lifecycle contract.
2. Run final focused automated tests.
3. Run compile and required residue scans.
4. Record live baseline: instance list, External IM health, actor list, and per-actor status for
   the test-owned actor.
5. Start one fresh test-owned actor only if the baseline is healthy.
6. Send one exact-reply External IM message.
7. Poll for one source-bound reply, fetch it, ack the reply event, and wait for Task Sys status to
   return to the active-count baseline.
8. Verify no task-bound Task Sys side lease remains for the actor.
9. Stop the test-owned actor and verify process/resource cleanup.
10. Stop immediately and record a blocker if any step leaves lifecycle residue.

## Test Plan

Automated gate:

```bash
python -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_side_thread_registry.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection
python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py scripts/env/tool_runtime/context.py tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py tools/launcher/daemon_core.py tools/launcher/web_management.py
```

Required residue scans:

```bash
rg -n "find_open_side_thread\(" tools/launcher/task_sys_runtime.py tests -S
rg -n "thread not loaded|ephemeral threads do not support thread/turns/list|side_processing.*residue|Task Sys.*reuse" tools tests scripts/env buddyswitch/skills docs/spec/task-sys-memo-optimization -S
```

Also run the memo's close-semantics residue scan and classify remaining historical doc hits.

Live gate:

```text
behavior passes + Task Sys residue count returns to baseline + host resources return to baseline
```

## Actual Changes

- Added the focused lifecycle acceptance gate to
  `docs/spec/task-sys-exploratory-acceptance/00-test-plan.md`.
- Added the post-fix focused lifecycle acceptance result to
  `docs/spec/task-sys-exploratory-acceptance/01-run-log.md`.

## Actual Verification

- Focused Task Sys/runtime/tool/status suite:
  - `python -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_runtime_executor.py tests/test_task_sys_side_processing.py tests/test_side_thread_registry.py tests/test_env_tool_response_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_web_management.py::WebManagementProductApiTests::test_actor_console_api_composes_runtime_task_sys_track_and_im_projection`
  - Result: `123 passed, 476 subtests passed`.
- Broad daemon/launcher/Web projection suite:
  - `python -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py tests/test_web_management.py`
  - Result: `289 passed, 83 subtests passed`.
- Compile gate:
  - `python -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/tool.py scripts/env/tools/task_sys/_impl.py scripts/env/tool_runtime/context.py tools/launcher/task_sys_runtime.py tools/launcher/side_thread_registry.py tools/launcher/daemon_core.py tools/launcher/web_management.py`
  - Result: passed.
- Whitespace gate:
  - `git diff --check`
  - Result: passed.
- Required residue scans:
  - `rg -n "find_open_side_thread\(" tools/launcher/task_sys_runtime.py tests -S`
    - Remaining hits are only `tests/test_side_thread_registry.py` manual side-conversation registry
      behavior tests.
  - `rg -n "thread not loaded|ephemeral threads do not support thread/turns/list|side_processing.*residue|Task Sys.*reuse" tools tests scripts/env buddyswitch/skills docs/spec/task-sys-memo-optimization -S`
    - Remaining hits are regression failure strings and the Phase 03 memo-optimization tech-stack
      note that mentions scoped residue scans.
  - Memo close-semantics scan:
    - Remaining hits are historical `task-sys-proactive-rebuild` docs and
      `task-sys-im-completion-status-observability` docs that already state `task_sys.close` is no
      longer side-only.
- Live smoke:
  - First harness attempt started `act-dev-9d8fe504d84a` but aborted before IM send because of a
    local Python readiness-predicate bug. The test-owned actor was stopped immediately and verified
    inactive with `task_sys.active_count == 0`, `task_sys.recoverable_count == 0`, and no Task Sys
    side leases.
  - Successful focused smoke used fresh test-owned actor `act-dev-ab502df2cc22`.
  - Source message id: `msg-724a7ec98e95`.
  - Reply message id: `msg-39b978de697e`.
  - Reply event id: `imev-25e8b96a95e5`.
  - Reply `reply_to`: `msg-724a7ec98e95`.
  - Reply content: `收到`.
  - Ack result: reply event acked and no longer visible on immediate post-ack poll.
  - Baseline and post-close Task Sys status: `active_count == 0`, `recoverable_count == 0`.
  - Side lease check: no `task_sys.side_frame` lease remained in the actor `instance.json`.
  - Cleanup: `act-dev-ab502df2cc22` stopped; app-server, daemon, and runtime broker not live.
  - Final External IM actor list returned to the two pre-existing active market actors.

## Acceptance Status

Accepted for Phase 08. The focused External IM lifecycle loop passed with source-bound exact reply,
acked reply event, clean Task Sys status, no Task Sys side lease residue, and stopped test-owned
actors.

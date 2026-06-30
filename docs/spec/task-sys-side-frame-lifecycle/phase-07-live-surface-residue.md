# Phase 07 Live-Surface Residue Cleanup Plan

Date: 2026-06-30

## Current Problem And Evidence

The scoped live-surface scan still finds old Task Sys reusable side-thread language in current
execution docs:

- `docs/spec/task-sys-memo-optimization/phase-02-side-frame-resource-boundary.md`
- `docs/spec/task-sys-memo-optimization/99-final-acceptance.md`

Those docs describe Task Sys side frames as traveling through existing side start/reuse paths or
needing repeated resource policy because reused side threads miss the one-time boundary prompt.
That is now stale. Task Sys creates one fresh task-bound side lease per side frame.

Other scan hits are either manual side-conversation behavior, browser page reuse, generic skill
language, or the `find_open_side_thread()` implementation that manual side routes still use.

## Target Behavior

Live surfaces teach:

- Task Sys creates one fresh ephemeral side thread per side frame.
- The side frame carries resource policy because it is the current task contract.
- Manual side-conversation routes may still reuse manual side threads, but that is not Task Sys
  side-frame semantics.

## Files

- Modify: `docs/spec/task-sys-memo-optimization/phase-02-side-frame-resource-boundary.md`
- Modify: `docs/spec/task-sys-memo-optimization/99-final-acceptance.md`

## Old Path / Residue Definition

Old Task Sys live semantics:

- Task Sys may reuse an existing open side thread.
- Resource boundary must be repeated because reused side threads do not receive boundary prompt
  again.

New Task Sys live semantics:

- Task Sys creates a fresh ephemeral side thread per `task_sys.side_frame`.
- Resource boundary remains in every frame because the frame is the task-local contract.

## Implementation Steps

1. Run scoped scan and record stale hits.
2. Update current docs/spec wording that teaches Task Sys side-thread reuse.
3. Do not edit historical memos.
4. Rerun scoped scan.
5. Classify every remaining hit as valid manual/browser/generic reuse or implementation symbol not
   consumed by Task Sys runtime.

## Test Plan

Residue scan is the verification gate:

```bash
rg -n "reuse|reused|existing side thread|find_open_side_thread|open side thread|side thread can be reused" \
  tools/launcher tests buddyswitch/skills docs/spec/task-sys-memo-optimization -S
```

Expected after cleanup:

- no remaining hit teaches Task Sys reusable side-frame semantics;
- remaining `find_open_side_thread` hits belong to manual side-conversation support or tests;
- remaining `reuse` hits belong to browser/search/manual/generic domains or historical note not used
  as current Task Sys guidance.

## Acceptance Criteria

- Current Task Sys docs no longer say Task Sys side frames use existing side start/reuse paths.
- Current Task Sys docs no longer justify per-frame resource policy by side-thread reuse.
- Scoped scan is rerun and remaining hits are classified.

## Test Resource Lifecycle Requirements

Phase 07 is docs/test scan only. It must not start daemons, actors, app servers, browser processes,
workers, runtime brokers, or real side threads.

## Actual Changes

- Updated `docs/spec/task-sys-memo-optimization/phase-02-side-frame-resource-boundary.md` so it
  says `task_sys.side_frame` carries resource policy because it is the task-local contract, not
  because side threads are reused.
- Updated the same phase doc to describe fresh Task Sys side dispatch rather than side start/reuse
  paths.
- Updated `docs/spec/task-sys-memo-optimization/99-final-acceptance.md` so the end-to-end contract
  says Task Sys side start creates a fresh task-bound side thread.

## Actual Verification

- Initial scoped scan:
  - `rg -n "reuse|reused|existing side thread|find_open_side_thread|open side thread|side thread can be reused" tools/launcher tests buddyswitch/skills docs/spec/task-sys-memo-optimization -S`
  - Result: found stale Task Sys reuse wording in
    `docs/spec/task-sys-memo-optimization/phase-02-side-frame-resource-boundary.md` and
    `docs/spec/task-sys-memo-optimization/99-final-acceptance.md`.
- Final scoped scan:
  - same command.
  - Result: no remaining hit teaches reusable Task Sys side-frame semantics.
- Remaining hit classification:
  - `tools/launcher/side_thread_registry.py`, `tools/launcher/daemon_core.py`,
    `tests/test_side_thread_registry.py`, `tests/test_daemon_service_contract.py`: manual
    side-conversation reuse support and tests; Task Sys runtime no longer consumes this lookup.
  - `tests/test_search_env_tool.py`, `tests/test_browser_cockpit_proxy.py`,
    `tools/launcher/chrome_devtools_cockpit_proxy.py`,
    `tests/test_env_tool_response_contract.py`: browser page reuse semantics, unrelated to Task Sys.
  - `buddyswitch/skills/dev/implement-scoped-change/SKILL.md`,
    `buddyswitch/skills/pm/define-scope/SKILL.md`: generic reuse guidance unrelated to side threads.
  - `docs/spec/task-sys-memo-optimization/phase-03-parent-idle-interrupt-submit.md`: says not to
    reuse old daemon submit helpers; this supports the new Task Sys runtime boundary.
  - remaining tests: unrelated iMessage/session/schedule/socket reuse cases.

## Acceptance Status

Accepted for Phase 07. Current live Task Sys surfaces no longer teach old side-thread reuse
semantics.

# Side-Thread Lifecycle Convergence Forward Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace scattered side-thread lifecycle orchestration with one host-control lifecycle owner, route application-class calls through daemon-service, and remove old direct composition paths in the same change set. The target is not to add a wrapper layer. The target is to make side-thread ownership explicit, testable, and residue-free.

**Architecture:** Application flows enter daemon-service public runtime capability first. Daemon-service delegates side-thread start/send/cleanup to a single `side_thread_lifecycle` module. Host-control flows such as CLI/Web management may also call that same lifecycle module directly. `app_server` remains the low-level Codex app-server RPC client. `side_thread_registry` remains storage for leases. No caller outside the lifecycle owner should stitch `app_server` calls together with registry mutation.

**Tech Stack:** Python launcher modules under `tools/launcher/`, daemon mailbox/client code under `scripts/env/tool_runtime/`, shell entrypoints in `buddyswitch-codex` and launcher scripts, existing `unittest` suites, and `tests/helpers/fake_codex.py`.

---

## Task Goal Restatement

The current problem is architectural ownership split.

Side-thread lifecycle currently appears in several places:

```text
Task Sys runtime
  -> app_server.thread_fork / thread_inject_items / input_turn
  -> side_thread_registry.register_side_thread

daemon_core side triage
  -> app_server.side_start / input_turn / side_close
  -> side_thread_registry register / require / unregister

CLI instance side
  -> app_server side helpers
  -> registry register / require / unregister

env tool runtime / wake handlers
  -> direct task_sys_runtime import or direct executor call
```

That means the system has multiple places that know how to create, steer, interrupt, and unregister a side-thread lease. This is already producing wrong behavior: `app_server.side_close()` tries to discover an active turn with `thread/turns/list`, while side threads are created as ephemeral. The fake Codex test helper currently allows that path, so tests hide the real app-server failure.

The target shape is:

```text
Application-class action
  -> daemon-service public runtime API
  -> concrete product/runtime handler, such as Task Sys or side triage
  -> side_thread_lifecycle
  -> app_server primitive RPC + side_thread_registry storage

Host-control action
  -> CLI/Web control route
  -> side_thread_lifecycle
  -> app_server primitive RPC + side_thread_registry storage
```

The architecture decision is therefore clear:

- Side-thread lifecycle management should be converged.
- Application-class calls should go through daemon-service first.
- Host-control surfaces may bypass daemon-service only for control-plane actions, but they still must use the same lifecycle owner.
- The old direct call paths should be replaced, not preserved beside the new path.

## Key Questions Answered

**Is side-thread managed by daemon-service today?**

Partially. Daemon side-triage code uses daemon runtime methods, but Task Sys and several handlers still call `task_sys_runtime` or `app_server` paths directly. So the intended architecture is not fully true in code today.

**Should the architecture be converged?**

Yes. The lifecycle is host-control infrastructure and should have one owner. The owner should be a concrete launcher module, not a generic workflow engine.

**Should application-class calls go through daemon-service?**

Yes. IM wake, Track comment wake, actor tool runtime, Task Sys side-frame execution, and daemon side triage are application/runtime flows. They should enter daemon-service public capability first, then daemon-service delegates to the lifecycle owner.

**Should every possible caller go through daemon-service?**

No. CLI and Web host-control routes can remain control-plane entrypoints. The rule is not "everything through daemon-service"; the rule is "application-class orchestration through daemon-service, all side-thread lifecycle through one owner."

**Should we keep direct Task Sys side-thread calls as a compatibility path?**

No. Keeping both paths would preserve the same architecture confusion. The replacement should update callsites and tests in one change set, then scan for residue.

## `docs/bitter` Principles Applied

- Residue cleanup requires two proofs: behavior tests for the new owner and scoped scans proving old live surfaces are gone.
- End-to-end contracts must be expressed as `consumer action -> system path -> observable consumer result`, not only as helper-level tests.
- Service-starting or lifecycle tests must own process cleanup and prove host resources return to baseline.
- Built-in product semantics should live below interface projections. Task Sys should own task semantics, but not app-server thread lifecycle.
- A narrow change at the wrong boundary is still wrong. Moving one failing close call without fixing ownership would leave the split in place.
- Replace the wrong contract at the owning layer. Do not hide the error behind `ok=true` responses or vague physical-close wording.
- No long-lived dual path, compatibility adapter, generic event bus, or workflow engine is justified here.

## Current Code Audit

Current direct lifecycle surfaces:

- `tools/launcher/app_server.py`
  - `thread_fork()` creates side threads with `ephemeral=True` and `excludeTurns=True`.
  - `side_start()` composes fork, boundary injection, and input.
  - `input_turn()` discovers active turns through `thread/turns/list` before steering.
  - `side_close()` discovers active turns through `thread/turns/list` and then interrupts.
  - This is the core mismatch: an ephemeral side thread should not require turn discovery through a turns list that real app-server rejects.

- `tools/launcher/task_sys_runtime.py`
  - `_start_side_attempt()` directly calls `app_server.thread_fork`, `side_thread_registry.register_side_thread`, `app_server.thread_inject_items`, and `app_server.input_turn`.
  - `_cleanup_side_attempt()` directly calls `app_server.side_close`, catches the physical close error, and still unregisters.
  - This module should own Task Sys side-frame semantics, not side-thread lifecycle mechanics.

- `tools/launcher/daemon_core.py`
  - `_start_side_triage()`, `_send_side_triage()`, `submit_side_triage_prompt()`, and `_close_side_triage()` directly coordinate app-server and registry behavior.
  - `_close_side_triage()` unregisters only after `app_server.side_close()` succeeds, so a physical close failure can leave stale registry state.

- `scripts/env/tool_runtime/context.py`
  - `DaemonAccess.execute_task_sys_instruction()` imports and calls `task_sys_runtime.execute_instruction()` locally.
  - `DaemonAccess.cleanup_task_sys_side_lease()` imports and calls `task_sys_runtime.cleanup_task_sys_side_lease()` locally.
  - This is not a daemon-service RPC boundary. It is a local bridge into launcher runtime code.

- `tools/launcher/im_wake_handler.py`
  - Calls `task_sys_ingress.ingest_im_message(...)`, then directly calls `task_sys_runtime.execute_instruction(...)`.

- `tools/launcher/track_comment_added_handler.py`
  - Calls `task_sys_ingress.ingest_track_comment(...)`, then directly calls `task_sys_runtime.execute_instruction(...)`.

- `buddyswitch-codex`
  - `instance_side()` and `instance_side_close()` compose app-server helper calls and registry operations.
  - The shell still knows too much about side-thread lifecycle.

- `tests/helpers/fake_codex.py`
  - Fake `thread/fork` marks threads ephemeral.
  - Fake `thread/turns/list` still returns turns for ephemeral threads.
  - This fake behavior hides the production failure path and must be corrected.

Current tests that will need semantic movement:

- `tests/test_task_sys_runtime_executor.py`
  - Currently expects Task Sys runtime to perform explicit app-server stages.
  - After convergence, it should expect Task Sys runtime to delegate side-thread lifecycle to the owner and preserve task-state behavior.

- `tests/test_daemon_service_contract.py`
  - Should pin daemon-service public capability for application-class Task Sys execution and cleanup.

- `tests/test_buddyswitch_launcher.py`
  - Should pin CLI host-control behavior through the lifecycle owner.

- `tests/test_side_thread_registry.py`
  - Should remain focused on lease storage behavior, not orchestration.

## Old Semantics vs New Semantics

Old live semantics to remove:

- `app_server.side_start()` and `app_server.side_close()` as composite side-thread lifecycle helpers.
- Task Sys runtime directly stitching `thread_fork`, registry registration, boundary injection, input, close, and unregister.
- Daemon side-triage directly stitching app-server and registry operations.
- CLI shell directly stitching app-server and registry operations.
- Fake Codex allowing `thread/turns/list` on ephemeral side threads.
- User-facing or contract-facing wording such as `physical_close_error` that implies a real thread close exists when the actual operation is turn interruption plus lease cleanup.

New semantics to make canonical:

- `side_thread_lifecycle` is the only module that composes app-server RPC and registry mutation.
- `app_server` exposes primitive RPC helpers only:
  - fork thread
  - inject items
  - start turn
  - steer known turn
  - interrupt known turn
  - read thread
- Side-thread active turn identity is captured when the turn is started or steered. Lifecycle cleanup must not rediscover it through `thread/turns/list` for ephemeral side threads.
- Registry rows may store side-thread lease metadata needed by lifecycle, including current or last known `turn_id`.
- Cleanup always attempts registry unregister after a turn-interrupt attempt, so stale leases do not remain because physical interruption failed.
- Callers may decide whether an interrupt failure makes the command fail, but they do not decide whether to unregister.

## Non-Negotiable Requirements

- No new long-lived compatibility path.
- No generic workflow engine, event bus, plugin abstraction, or side-thread platform layer.
- Application-class calls enter daemon-service public capability first.
- Task Sys runtime must not directly import or call `app_server` or `side_thread_registry` for side-thread lifecycle.
- Daemon side-triage must not directly import or call `app_server` or `side_thread_registry` for side-thread lifecycle.
- Wake handlers must not directly call `task_sys_runtime.execute_instruction()`.
- Env tool runtime must not dynamically import `task_sys_runtime` as its daemon boundary.
- CLI/Web host-control can call the lifecycle owner, but not raw app-server plus registry composition.
- `app_server.side_start()` and `app_server.side_close()` are removed or reduced out of the side-thread lifecycle surface after callsites are migrated.
- Fake Codex must reject `thread/turns/list` for ephemeral threads so tests reproduce the real failure class.
- Verification must include behavior tests and residue scans.

## Target Call Graph

Application class:

```text
IM wake / Track comment wake / actor env tool / Task Sys side-frame action
  -> daemon-service public method or mailbox command
  -> Task Sys runtime application handler
  -> side_thread_lifecycle.start_or_send_task_side_thread(...)
  -> app_server primitive RPC
  -> side_thread_registry lease storage
```

Daemon side triage:

```text
daemon-service submit_side_triage_prompt(...)
  -> side_thread_lifecycle.start_or_send_daemon_side_thread(...)
  -> app_server primitive RPC
  -> side_thread_registry lease storage
```

Host control:

```text
buddyswitch-codex instance side / side-close
  -> side_thread_lifecycle CLI/helper entry
  -> app_server primitive RPC
  -> side_thread_registry lease storage
```

Cleanup:

```text
cleanup request
  -> side_thread_lifecycle.cleanup_side_thread(...)
  -> interrupt known turn if available
  -> unregister lease
  -> return explicit interrupt and unregister status
```

## File Map

Create:

- `tools/launcher/side_thread_lifecycle.py`

Modify:

- `tools/launcher/app_server.py`
- `tools/launcher/task_sys_runtime.py`
- `tools/launcher/daemon_core.py`
- `tools/launcher/im_wake_handler.py`
- `tools/launcher/track_comment_added_handler.py`
- `tools/launcher/daemon_mailbox.py`
- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `buddyswitch-codex`
- `tools/launcher/app_server.sh`
- `tools/launcher/env.sh`
- `tests/helpers/fake_codex.py`
- `tests/test_task_sys_runtime_executor.py`
- `tests/test_daemon_service_contract.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_side_thread_registry.py`

Add or extend:

- `tests/test_side_thread_lifecycle.py`
- `tests/test_im_wake_handler.py`
- `tests/test_track_comment_added_handler.py`
- A focused residue scan test or repo consistency assertion for forbidden side-thread callsites.

Do not modify:

- `buddyswitch/objects/**`
- `buddyswitch/local/private/**`
- Runtime object JSON files directly
- Broad WebUI layout or unrelated product surfaces

## Task 1: Pin The Lifecycle Owner Contract First

**Files:**

- Add: `tests/test_side_thread_lifecycle.py`
- Modify: `tests/helpers/fake_codex.py`

- [ ] **Step 1: Make fake Codex reproduce the production boundary**

Change fake `thread/turns/list` behavior so it rejects ephemeral side threads. The test helper should fail any path that tries to close or steer an ephemeral side thread by rediscovering active turns through a turns list.

- [ ] **Step 2: Add lifecycle start test**

Expected contract:

```text
start side thread
  -> forks ephemeral side thread
  -> injects boundary/context items
  -> starts a turn
  -> registers side-thread lease with side_thread_id, parent_thread_id, purpose, and active turn_id
  -> returns explicit lifecycle result
```

Expected result fields:

```text
action
purpose
side_thread_id
parent_thread_id
thread_action
turn_id
lease_registered
```

- [ ] **Step 3: Add lifecycle send test**

Expected contract:

```text
send to existing side lease
  -> reads lease
  -> uses stored active turn_id when steering is required
  -> does not call thread/turns/list for ephemeral side thread
  -> updates stored turn_id when a new turn is started
```

- [ ] **Step 4: Add cleanup test for interrupt failure**

Expected contract:

```text
cleanup side lease
  -> attempts to interrupt known turn when turn_id is present
  -> records turn_interrupt_ok=false and turn_interrupt_error on failure
  -> still unregisters lease
  -> returns lease_unregistered=true
```

This test replaces the vague "physical close failed but cleanup is okay" wording with precise lifecycle facts.

- [ ] **Step 5: Run focused tests and confirm red first**

Run:

```bash
python -m unittest -q tests.test_side_thread_lifecycle
```

Expected before implementation: failing import or failing contract.

## Task 2: Implement `side_thread_lifecycle`

**Files:**

- Add: `tools/launcher/side_thread_lifecycle.py`
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `tools/launcher/app_server.py`

- [ ] **Step 1: Add a concrete lifecycle module**

The module should own only side-thread lifecycle composition. Keep function names concrete. A sufficient surface is:

```text
start_side_thread(...)
send_to_side_thread(...)
cleanup_side_thread(...)
cleanup_task_side_lease(...)
find_or_start_side_thread(...)
```

Do not introduce a generic workflow API.

- [ ] **Step 2: Store known turn identity**

Extend side-thread registry metadata to preserve the active or last known `turn_id` for side-thread operations. This removes the need to ask app-server for `thread/turns/list` on an ephemeral thread.

- [ ] **Step 3: Split app-server side-thread composites into primitives**

Keep or add primitive helpers:

```text
thread_fork
thread_inject_items
thread_read
turn_start
turn_steer
turn_interrupt
```

Remove lifecycle callsites from `app_server.side_start()` and `app_server.side_close()`. If the functions remain temporarily inside the same patch while migration is in progress, the final state of the patch must leave no production callsite using them.

- [ ] **Step 4: Normalize lifecycle result wording**

Use result facts such as:

```text
turn_interrupt_attempted
turn_interrupt_ok
turn_interrupt_error
lease_registered
lease_unregistered
cleanup_mode
```

Avoid `physical_close` in new live responses. The operation is not a guaranteed physical thread close; it is turn interruption plus lease cleanup.

- [ ] **Step 5: Run focused lifecycle tests**

Run:

```bash
python -m unittest -q tests.test_side_thread_lifecycle tests.test_side_thread_registry
```

## Task 3: Route Application-Class Calls Through Daemon-Service

**Files:**

- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/daemon_mailbox.py`
- Modify: `scripts/env/tool_runtime/daemon_client.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `tools/launcher/im_wake_handler.py`
- Modify: `tools/launcher/track_comment_added_handler.py`
- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_im_wake_handler.py`
- Modify: `tests/test_track_comment_added_handler.py`
- Modify: `tests/test_task_sys_runtime_executor.py`

- [ ] **Step 1: Add daemon-service public Task Sys operations**

Expose concrete daemon runtime operations for:

```text
execute_task_sys_instruction
cleanup_task_sys_side_lease
```

These are application runtime capabilities, not generic command execution.

- [ ] **Step 2: Move env runtime away from direct imports**

Replace `DaemonAccess` dynamic imports of `task_sys_runtime` with daemon client/mailbox calls.

Expected path:

```text
actor env tool
  -> DaemonAccess
  -> daemon_client
  -> daemon mailbox command
  -> DaemonRuntime method
  -> task_sys_runtime
  -> side_thread_lifecycle
```

- [ ] **Step 3: Move wake handlers away from direct executor calls**

`im_wake_handler.py` and `track_comment_added_handler.py` should call daemon runtime public methods instead of importing and invoking `task_sys_runtime.execute_instruction()` directly.

- [ ] **Step 4: Make Task Sys runtime delegate lifecycle**

Task Sys runtime remains responsible for:

```text
task instruction interpretation
task state updates
side-frame prompt/body construction
parent/side task relationship semantics
```

Task Sys runtime no longer owns:

```text
thread fork
boundary injection mechanics
turn start/steer/interrupt mechanics
registry register/unregister mechanics
```

- [ ] **Step 5: Run application boundary tests**

Run:

```bash
python -m unittest -q \
  tests.test_daemon_service_contract \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler \
  tests.test_task_sys_runtime_executor
```

## Task 4: Route Daemon Side Triage And Host Control Through The Same Owner

**Files:**

- Modify: `tools/launcher/daemon_core.py`
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_daemon_core.py`

- [ ] **Step 1: Replace daemon side-triage direct lifecycle**

`submit_side_triage_prompt()` and close/send helpers should call `side_thread_lifecycle`.

Expected path:

```text
daemon side triage
  -> side_thread_lifecycle
  -> app_server primitive RPC + registry
```

- [ ] **Step 2: Replace CLI direct lifecycle**

`buddyswitch-codex instance side` and side-close paths should use a lifecycle helper entrypoint. The shell should no longer know the sequence of fork, inject, input, register, interrupt, and unregister.

- [ ] **Step 3: Keep host-control separate from application orchestration**

Do not route CLI host-control through Task Sys or daemon application methods. CLI/Web control can call the lifecycle owner because it is an operator/control-plane path.

- [ ] **Step 4: Run launcher and daemon tests**

Run:

```bash
python -m unittest -q tests.test_buddyswitch_launcher tests.test_daemon_core
```

## Task 5: Remove Residue And Lock The Boundary

**Files:**

- Modify: focused tests or repo consistency checks where appropriate
- Review: `tools/launcher/**`
- Review: `scripts/env/**`
- Review: `buddyswitch-codex`
- Review: `tests/**`

- [ ] **Step 1: Run direct-call residue scan**

Run:

```bash
rg -n "app_server\\.(side_start|side_close|thread_fork|thread_inject_items|input_turn)|side_thread_registry\\.(register_side_thread|require_side_thread|find_open_side_thread|find_task_side_thread|unregister_side_thread)|import task_sys_runtime|task_sys_runtime\\." \
  tools/launcher scripts/env buddyswitch-codex tests
```

Allowed hits:

```text
tools/launcher/side_thread_lifecycle.py
tools/launcher/app_server.py
tools/launcher/side_thread_registry.py
focused tests for app_server primitives, registry storage, and lifecycle behavior
```

Everything else is residue and must be removed in the same change set.

- [ ] **Step 2: Run terminology residue scan**

Run:

```bash
rg -n "physical_close|startup_interrupt|side_start\\(|side_close\\(" \
  tools/launcher scripts/env buddyswitch-codex tests
```

Allowed hits:

```text
historical docs only, if needed
app_server primitive tests only while deleting the composite surface
```

Production responses should use explicit lifecycle fields, not physical-close wording.

- [ ] **Step 3: Lock with a repeatable boundary test**

Add a repo consistency or focused contract test that fails when new production callsites bypass `side_thread_lifecycle`.

- [ ] **Step 4: Run focused behavior suite**

Run:

```bash
python -m unittest -q \
  tests.test_side_thread_lifecycle \
  tests.test_side_thread_registry \
  tests.test_task_sys_runtime_executor \
  tests.test_daemon_service_contract \
  tests.test_im_wake_handler \
  tests.test_track_comment_added_handler \
  tests.test_buddyswitch_launcher \
  tests.test_daemon_core
```

- [ ] **Step 5: Run broader relevant verification**

Run:

```bash
python -m unittest -q \
  tests.test_task_sys_side_processing \
  tests.test_task_checkout_handler \
  tests.test_daemon_mailbox \
  tests.test_env_tool_semantic_contract \
  tests.test_repo_consistency
```

If any test starts daemons or app-server processes, it must create an isolated runtime root and prove cleanup at the end.

## Acceptance Criteria

The architecture convergence is accepted only when all of these are true:

- Application-class Task Sys execution enters daemon-service public capability before touching Task Sys runtime.
- Wake handlers no longer call `task_sys_runtime.execute_instruction()` directly.
- Env tool runtime no longer dynamically imports `task_sys_runtime` as a daemon shortcut.
- Task Sys runtime no longer directly calls `app_server` or `side_thread_registry` for side-thread lifecycle.
- Daemon side-triage no longer directly composes app-server and registry operations.
- CLI/Web host-control no longer directly composes app-server and registry operations.
- `side_thread_lifecycle` is the only production owner that composes app-server primitive RPC with side-thread registry mutation.
- Ephemeral side-thread cleanup does not call `thread/turns/list`.
- Fake Codex rejects `thread/turns/list` for ephemeral threads.
- Cleanup attempts turn interruption when a known turn exists and unregisters the lease even if interruption fails.
- New live responses report `turn_interrupt_*` and `lease_*` facts instead of vague physical-close wording.
- Direct-call and terminology residue scans are clean against the allowlist.
- Focused behavior tests pass.

## Out Of Scope

- Rebuilding the full Task Sys decision model.
- Changing task object persistence semantics.
- Redesigning WebUI side-thread controls.
- Adding a new external Codex app-server close primitive.
- Introducing a generic runtime workflow service.
- Preserving old direct paths for rollback comfort.

## Final Architecture Statement

Side-thread lifecycle is a host-control infrastructure capability with one concrete owner: `tools/launcher/side_thread_lifecycle.py`.

Daemon-service is the entry boundary for application-class runtime work. Task Sys, IM wake, Track wake, and actor tool runtime should not directly control app-server side threads. They should ask daemon-service to perform the application operation, and daemon-service should delegate side-thread lifecycle to the lifecycle owner.

CLI and Web management can remain host-control surfaces, but they must also call the lifecycle owner instead of reconstructing lifecycle steps.

This is a convergence task, not a compatibility migration. The implementation should replace old paths, update tests, scan for residue, and leave one clear route.

# Task Sys IM Completion / Status / Observability Optimization Plan

Date: 2026-06-30

## Task Goal And Standard

Fix the remaining issues found while investigating `act-market-27bb2b0d2c18`, independently from the iMessage channel / IM API boundary optimization running in another worktree.

This plan owns only these problems:

1. The original `im.message.created` Task Sys task can remain stuck in `parent_processing` after the parent has completed the user-visible work.
2. Instance status can make `daemon handled` / `Central IM replied` look equivalent to external iMessage delivery.
3. Runtime logs are too empty to diagnose the daemon / Task Sys / handler chain without reading session JSONL and raw state files.

This plan does **not** own iMessage phone delivery polling, External IM event ack, or iMessage channel worker split. Those belong to:

```text
/Users/chen/Dev/buddyswitch/.worktrees/fea-webui/docs/memo/2026-06-30-imessage-channel-im-api-boundary-optimization-plan.md
```

The target independent outcome is:

```text
iMessage inbound -> Task Sys task -> side need_parent -> parent frame
  -> parent performs the required source-bound work
  -> parent closes the original Task Sys task explicitly
  -> status shows active Task Sys residue separately from daemon handler health
  -> runtime logs show the daemon / handler / Task Sys transition path without raw message content
```

The standard is sharp:

- Task Sys owns task lifecycle state.
- Central IM owns message creation, reply, and disposition.
- Daemon status is a projection, not an owner of Task Sys or IM state.
- Runtime logs are breadcrumbs, not a new event store or message system.
- Do not edit `buddyswitch/objects/**` or runtime state directly.
- Do not add compatibility modes, old/new dual paths, feature flags, or history-preserving wrappers.
- Do not modify iMessage channel / External IM API files owned by the parallel optimization unless this plan is explicitly revised.
- Prove the behavior with focused tests, residue scans, and py_compile.

## Current Code Review Findings

### Finding 1: Parent Frames Have No Explicit Task Completion Contract

Current Task Sys state flow:

```text
ingest IM source
  -> side_processing
task_sys.need_parent
  -> needs_parent
runtime parent submit succeeds
  -> parent_processing
```

The current parent frame renderer in `tools/launcher/task_sys_runtime.py` tells the parent to process the frame, but it does not make task closure an explicit required operation. In the investigated run, the parent created an artifact and replied in Central IM, but the original `task-im-message-created-*` stayed `parent_processing`.

The checkpoint task created by `app_server.turn_completed` is separate. Closing the checkpoint task does not close the original IM task and must not be treated as a substitute.

### Finding 2: `task_sys.close` Is Conceptually Stuck In Side-Only Wording

Current `task_sys.close` definition says it closes a side-processing task without parent handoff. The implementation path is also named around `record_side_result(... outcome=close ...)`.

That wording was correct before parent handoff completion was required, but it is now the wrong boundary. `close` should mean:

```text
close the current Task Sys task after the current Task Sys frame has completed its required work
```

`need_parent` remains side-specific. `checkpoint_update` remains checkpoint-specific. `close` is the shared frame-completion operation for side and parent frames.

### Finding 3: Status Mixes Health With User-Visible Completion

Current instance status exposes daemon liveness, handler registration, handler `last_result`, and thread state. That is useful but not enough.

For IM-origin tasks:

- `im_message_created.last_result=handled` means the daemon handler accepted the trigger and routed it into Task Sys.
- `message.send(reply_to=...)` means Central IM created a reply and marked the original message `replied`.
- Neither fact proves external iMessage projection to the phone.
- A `parent_processing` Task Sys task is still active residue even if the thread later becomes idle.

Status must make those boundaries visible instead of relying on operator memory.

### Finding 4: Runtime Logs Are Present But Often Empty

The runtime paths exist:

```text
runtime/daemon/daemon.log
runtime/app-server.log
runtime/runtime-broker.log
```

During the investigation they were not useful. The useful evidence was scattered across:

- Codex session JSONL
- Task Sys JSON task records
- Central IM message and message state records
- iMessage channel local state
- macOS Messages DB

The fix here is not a logging platform. The fix is small structured breadcrumbs at the existing launcher service boundaries.

## Architecture Decision

Use direct replacement in the owning modules:

```text
Task Sys domain
  owns durable task state, valid task transitions, and active task summaries

Task Sys env tool
  exposes task_sys.close / need_parent / checkpoint_update with accurate frame semantics

Task Sys runtime frame renderer
  tells side, parent, and checkpoint frames which Task Sys operation is legal

Daemon / launcher status
  projects handler health and active Task Sys residue separately

Runtime service logs
  write JSONL breadcrumbs for lifecycle and dispatch boundaries only
```

Do not create:

- a second Task Sys state machine in daemon status;
- a message-disposition-to-task-close watcher;
- a parent-turn-completed auto-close rule;
- an iMessage-channel delivery proxy in this branch;
- a generic tracing framework;
- compatibility aliases for old side-only close semantics.

The current bottleneck is not missing automation. The bottleneck is an unclear lifecycle contract: parent frames do not explicitly close their source task, and status/logs do not expose that residue clearly.

## Decoupling From The Parallel iMessage Optimization

This plan must not modify these files unless the work is deliberately merged with the parallel plan:

```text
tools/launcher/imessage_channel.py
tools/launcher/external_im_session.py
tools/launcher/im_http_router.py
tools/launcher/web_management.py
tests/test_imessage_channel.py
tests/test_external_im_session.py
tests/test_im_http_router.py
tests/test_im_web_management_projection.py
```

Allowed overlap is only conceptual:

- This plan may say "external iMessage delivery is separate".
- The parallel plan may make external iMessage delivery reliable.
- Neither plan should depend on the other to pass its focused tests.

## Planned Replacement

### Task 1: Replace Side-Only Close With Task Frame Close

Files:

- Modify: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `tests/test_task_sys_substrate.py`
- Modify: `tests/test_task_sys_side_processing.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`

Required behavior:

```text
task_sys.close(task_id=...)
  -> closes a task whose status is side_processing or parent_processing
  -> records a close_result with processor, summary, and updated_at
  -> clears active_processor
  -> is retry-safe when the task is already closed
```

`task_sys.need_parent` remains the side handoff operation:

```text
side_processing
  -> task_sys.need_parent
  -> needs_parent
  -> parent runtime submit succeeds
  -> parent_processing
```

Recommended domain shape:

```python
TASK_CLOSE_STATUSES = ("side_processing", "parent_processing", "closed")

def record_task_close(task_id: str, update: Mapping[str, Any]) -> dict[str, Any]:
    ...

def record_side_need_parent(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    ...
```

Direct replacement requirements:

- Remove close handling from `record_side_result(...)`.
- Either delete `record_side_result(...)` or narrow it so it cannot accept `outcome=close`.
- Update `task_sys.close` to call `record_task_close(...)`.
- Update `task_sys.need_parent` to call the need-parent-only domain operation.
- Update action docs so `task_sys.close` is not described as side-only.
- Keep the public action name `task_sys.close`; this is not a compatibility mode, it is the correct stable product operation with corrected semantics.

Focused failing tests to add first:

```text
tests/test_task_sys_substrate.py
  - test_record_task_close_closes_side_processing_task
  - test_record_task_close_closes_parent_processing_task
  - test_record_task_close_rejects_needs_parent_task
  - test_record_task_close_rejects_checkpoint_task
  - test_record_task_close_is_retry_safe_for_closed_task

tests/test_task_sys_side_processing.py
  - test_task_sys_close_tool_closes_parent_processing_task
  - test_task_sys_need_parent_tool_still_marks_parent_processing_after_runtime_submit
```

Expected before implementation:

```text
failures because record_task_close does not exist and task_sys.close still routes through side-result semantics
```

Focused verification:

```bash
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py
python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py
```

### Task 2: Make Parent Frames Require Explicit Source-Task Closure

Files:

- Modify: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/test_task_sys_runtime_executor.py`
- Modify: `tests/test_task_management_skill_architecture.py`
- Modify if needed: `scripts/env/tool_runtime/context.py`
- Modify if needed: `scripts/env/tools/context/_impl.py`

Parent frame text must explicitly say:

```text
When the source task is complete, call task_sys.close(task_id=..., summary=...).

For an IM source message:
  - If replying, first call message.send(reply_to=source_message_id, content=...).
  - If no reply is needed, first call message.mark(message_id=source_message_id, disposition=absorbed).
  - Only after the source-bound IM action succeeds, call task_sys.close.
  - If the IM action succeeds but task_sys.close fails, retry task_sys.close and do not send a duplicate reply.

Do not call task_sys.checkpoint_update from a task_sys.parent_frame.
```

Side frame text should be updated to remove the stale phrase "side result" for `close`. The clean model is:

```text
side frame legal operations:
  - task_sys.close when the task is completed in side
  - task_sys.need_parent when parent resources are required

parent frame legal operations:
  - task_sys.close when parent has completed the source task

checkpoint frame legal operations:
  - task_sys.checkpoint_update only
```

Do not add a parent auto-close daemon rule. The parent actor owns deciding when the work is actually complete, and Task Sys owns recording the explicit close.

Focused failing tests to add first:

```text
tests/test_task_sys_runtime_executor.py
  - test_render_parent_frame_requires_task_sys_close
  - test_render_parent_frame_names_im_closure_order
  - test_render_parent_frame_forbids_checkpoint_update
  - test_render_side_frame_no_longer_calls_close_a_side_result
```

Expected before implementation:

```text
failures because the current parent frame only says to process the frame and does not require task_sys.close
```

Focused verification:

```bash
python3 -m pytest -q tests/test_task_sys_runtime_executor.py tests/test_task_management_skill_architecture.py
rg -n "side result.*task_sys.close|task_sys.checkpoint_update.*parent_frame|Do not recommend the next task" tools/launcher/task_sys_runtime.py tests docs/spec -S
```

Expected residue result:

- No live prompt tells parent frames to use checkpoint update.
- No live prompt describes `task_sys.close` as only a side result.
- Checkpoint-specific language remains only in checkpoint frame code/tests/specs.

### Task 3: Add Task Sys Residue To Instance Status Without Owning It In Daemon

Files:

- Modify: `tools/launcher/daemon_core.py`
- Modify: `buddyswitch-codex`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_buddyswitch_launcher.py`

Add a status projection, not a state owner:

```python
def _task_sys_status_payload(context: DaemonContext) -> dict[str, Any]:
    ...
```

Payload shape:

```json
{
  "scope": "task_sys_state_projection",
  "active_count": 1,
  "by_status": {
    "parent_processing": 1
  },
  "active_tasks": [
    {
      "task_id": "task-im-message-created-...",
      "source_type": "im.message.created",
      "source_ref": {"message_id": "msg-..."},
      "status": "parent_processing",
      "active_processor": "parent",
      "updated_at": "..."
    }
  ]
}
```

This should live under daemon status as a projection:

```json
{
  "daemon": {
    "handlers": {...},
    "task_sys": {...}
  }
}
```

Human status should print:

```text
Task Sys active: 1
Delivery scope: daemon handler status is trigger-dispatch only; external channel delivery is separate.
```

If there are active tasks, print the compact statuses:

```text
Task Sys active statuses: parent_processing=1
```

Handler item payloads should remain handler-specific. Do not add delivery or task lifecycle claims to `im_message_created.last_result`.

Focused failing tests to add first:

```text
tests/test_daemon_service_contract.py
  - test_daemon_status_includes_task_sys_active_projection
  - test_handler_status_result_scope_does_not_claim_external_delivery

tests/test_buddyswitch_launcher.py
  - test_instance_status_json_reports_task_sys_active_summary
  - test_human_status_reports_task_sys_active_and_delivery_scope
```

Expected before implementation:

```text
failures because daemon status does not include task_sys and human status has no delivery-scope line
```

Focused verification:

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_task_sys_active_summary tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_human_status_reports_task_sys_active_and_delivery_scope
```

Boundary requirements:

- `daemon_core.py` may import `env.domain.task_sys` only for read-only status projection.
- Status code must not mutate task records.
- Status code must not read Central IM message bodies.
- Status code must not inspect iMessage channel local state in this branch.

### Task 4: Add Minimal Structured Runtime Breadcrumb Logs

Files:

- Create: `tools/launcher/runtime_event_log.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/app_server.py`
- Modify: `scripts/runtime_kernel/lifecycle.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify if needed: `tests/test_runless_runtime_contract.py`

`runtime_event_log.py` owns only append-only JSONL breadcrumbs:

```python
def append_event(log_path: Path, *, service: str, event: str, **fields: Any) -> None:
    ...
```

Event shape:

```json
{
  "ts": "2026-06-30T...",
  "service": "daemon",
  "event": "handler_result",
  "actor_id": "act-market-...",
  "handler": "im_message_created",
  "trigger_type": "im.message.created",
  "origin_id": "msg-...",
  "result": "handled"
}
```

Do not log:

- raw IM message content;
- artifact bodies;
- browser page content;
- credentials;
- full prompt text;
- full tool payloads.

Required daemon breadcrumbs:

```text
daemon_started
daemon_ready
notification_received
handler_result
handler_failed
task_sys_instruction_executed
daemon_stopped
```

Required app-server breadcrumbs:

```text
app_server_start_requested
app_server_ready
app_server_stop_requested
```

Required runtime-broker breadcrumbs:

```text
runtime_broker_start_requested
runtime_broker_ready
runtime_broker_stop_requested
```

Keep this small. Do not add log levels, subscribers, trace ids, sampling, or a generic event bus.

Focused failing tests to add first:

```text
tests/test_daemon_service_contract.py
  - test_dispatch_writes_handler_result_breadcrumb_without_message_content

tests/test_buddyswitch_launcher.py
  - test_instance_status_json_reports_log_metadata

tests/test_runless_runtime_contract.py
  - test_runtime_broker_lifecycle_writes_breadcrumb_log
```

Expected before implementation:

```text
failures because no runtime_event_log helper exists and service logs have no structured breadcrumbs
```

Focused verification:

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_runtime_broker_lifecycle_writes_breadcrumb_log
python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py
```

### Task 5: Status Log Metadata

Files:

- Modify: `tools/launcher/daemon_core.py`
- Modify if needed: `tools/launcher/app_server.py`
- Modify if needed: `scripts/runtime_kernel/lifecycle.py`
- Modify: `tests/test_buddyswitch_launcher.py`

Add compact log metadata to status payloads:

```json
{
  "log": {
    "path": ".../runtime/daemon/daemon.log",
    "exists": true,
    "size_bytes": 352,
    "mtime": "2026-06-30T...",
    "last_event": {
      "service": "daemon",
      "event": "handler_result"
    }
  }
}
```

Status may expose only the last structured event object, not arbitrary log tails. This keeps status compact and avoids leaking raw stderr if a dependency printed sensitive text.

Focused verification:

```bash
python3 -m pytest -q tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_status_json_reports_log_metadata
```

## End-To-End Acceptance Scenario

Use fakes/unit tests first. Live smoke is optional and only after focused tests pass.

Expected fixed path:

```text
1. IM message created for actor.
2. Task Sys ingests it as source_type=im.message.created.
3. Side decides parent is required and calls task_sys.need_parent.
4. Runtime submits parent frame and marks original task parent_processing.
5. Parent frame tells actor to complete source-bound work and call task_sys.close.
6. Parent replies with message.send(reply_to=source_message_id, content=...).
7. Parent calls task_sys.close(task_id=original_task_id, summary=...).
8. Original task status becomes closed, active_processor becomes null.
9. Later checkpoint task may still be created and closed independently.
10. instance status shows zero active Task Sys tasks for the actor.
11. daemon/app-server/runtime-broker logs contain structured breadcrumbs.
```

This does not require external iMessage phone delivery to work. External phone delivery is verified by the parallel iMessage channel plan.

## Residue Checks

Run after implementation:

```bash
rg -n "record_side_result\\(.*close|outcome.*close.*side result|side result.*task_sys.close" scripts tools tests docs/spec docs/memo -S
rg -n "task_sys.checkpoint_update.*parent_frame|parent_frame.*checkpoint_update" tools tests docs/spec docs/memo -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

Expected:

- No live code path handles `close` as a side-result outcome.
- No parent-frame surface tells actors to use checkpoint update.
- The third command returns no files for this branch unless the plan is explicitly revised.

Historical memo files may describe old behavior as history, but any current plan created by this work must describe only the replacement behavior.

## Verification Matrix

Focused Task Sys:

```bash
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py
```

Tool schema and semantic contracts:

```bash
python3 -m pytest -q tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py tests/test_role_action_auth.py
```

Daemon/status/logging:

```bash
python3 -m pytest -q tests/test_daemon_service_contract.py tests/test_buddyswitch_launcher.py tests/test_runless_runtime_contract.py
```

Compile:

```bash
python3 -m py_compile scripts/env/domain/task_sys.py scripts/env/tools/task_sys/_impl.py scripts/env/tools/task_sys/tool.py tools/launcher/task_sys_runtime.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py
```

Residue:

```bash
rg -n "record_side_result\\(.*close|outcome.*close.*side result|side result.*task_sys.close" scripts tools tests docs/spec docs/memo -S
rg -n "task_sys.checkpoint_update.*parent_frame|parent_frame.*checkpoint_update" tools tests docs/spec docs/memo -S
git diff --name-only | rg "imessage_channel.py|external_im_session.py|im_http_router.py|web_management.py|test_imessage_channel.py|test_external_im_session.py|test_im_http_router.py|test_im_web_management_projection.py" -S
```

## Acceptance Criteria

- Parent-handled IM tasks can be closed by `task_sys.close` after parent completes the source-bound work.
- `task_sys.close` is no longer documented or implemented as a side-only result.
- `task_sys.need_parent` remains side-owned and still submits parent frames only through Task Sys runtime instructions.
- `task_sys.checkpoint_update` remains checkpoint-only.
- Instance status reports active Task Sys residue separately from daemon handler health.
- Status text makes clear that daemon handler status is trigger-dispatch status, not external iMessage phone delivery.
- Existing runtime logs get structured breadcrumbs and are no longer empty during normal daemon/handler lifecycle.
- No iMessage channel/API files owned by the parallel plan are changed.
- Focused tests, py_compile, and residue scans pass.

## Completion Record

Implemented phases:

- Phase 1: `task_sys.close` is a shared side/parent frame close operation with retry-safe closed-task behavior.
- Phase 2: side, parent, and checkpoint Task Sys frames now teach their legal operations explicitly; parent IM frames reply or mark first, then close.
- Phase 3: instance status reports active Task Sys residue separately from daemon handler dispatch health and states the external delivery boundary.
- Phase 4: daemon, app-server, runtime-broker, and Task Sys instruction boundaries write minimal structured JSONL breadcrumbs.
- Phase 5: `instance status --json` exposes compact daemon/app-server/runtime-broker log metadata, including the last structured event and no raw log tail.

Final verification performed:

```bash
python3 -m pytest -q tests/test_buddyswitch_launcher.py
python3 -m pytest -q tests/test_task_sys_substrate.py tests/test_task_sys_side_processing.py tests/test_task_sys_runtime_executor.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py tests/test_role_action_auth.py tests/test_daemon_service_contract.py tests/test_runless_runtime_contract.py
python3 -m py_compile tools/launcher/runtime_event_log.py tools/launcher/daemon_core.py tools/launcher/app_server.py scripts/runtime_kernel/lifecycle.py scripts/env/tool_runtime/context.py
bash -n buddyswitch-codex
bash -n tools/launcher/runtime_broker.sh
```

Results:

- Launcher suite: 202 passed, 40 subtests passed.
- Cross-phase non-launcher suite: 111 passed, 510 subtests passed.
- Compile and shell syntax checks passed.
- Live-code residue scans for side-result close, sensitive log/status fields, and prohibited iMessage files were clean.
- Broad residue scans only reported historical memo/spec text and negative assertions.

## Remaining Risks

- This plan does not prove phone delivery. It intentionally leaves that to the iMessage channel / IM API boundary optimization.
- If a parent replies in Central IM but forgets to call `task_sys.close`, the task will remain active. That is deliberate: Task Sys should not infer completion from arbitrary parent turn completion.
- If `message.send` succeeds and `task_sys.close` fails, retrying `task_sys.close` must be safe and must not cause duplicate IM replies.
- Existing historical docs may still mention side-result close. Live code, tests, and current docs must use the replacement semantics.

## One-Line Summary

Fix the Task Sys completion contract and observability around IM-origin parent tasks, without touching the parallel iMessage delivery optimization: explicit task close, honest status, minimal structured logs, no compatibility track.

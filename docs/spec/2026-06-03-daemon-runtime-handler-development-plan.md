# Daemon Runtime Handler Rebuild Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use TDD for behavior changes: write or rewrite the focused test first, run it and confirm it fails for the expected contract gap, then implement.

**Goal:** Rebuild the daemon as a business-neutral runtime coordinator using `DaemonTrigger`, registered handlers, and `DaemonRuntime`.

**Architecture:** Keep daemon core responsible for trigger normalization dispatch, handler lifecycle status, daemon state, and runtime helper injection. Keep task/message business behavior inside business handlers. Keep mailbox ingress generic and keep side-thread registry validation inside `DaemonRuntime`.

**Tech Stack:** Python daemon launcher modules and pytest/unittest tests.

---

## Task 1: Replace Daemon Core Contract Tests

**Files:**

- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_daemon_service_contract.py`
- Modify: `tests/test_daemon_trigger_router.py`

Steps:

- [ ] Rewrite existing old-vocabulary assertions from `actions`/`ActionGateway` to `runtime`/`DaemonRuntime`.
- [ ] Add assertions that `DaemonHandler` and `DaemonRuntime` exist and `ActionGateway` does not.
- [ ] Add assertions that missing state initializes runtime-call fields and excludes action fields.
- [ ] Add assertions that stale action fields are dropped during state load.
- [ ] Add assertions that status exposes `runtime` and excludes `actions`.
- [ ] Run `python3 -m pytest tests/test_daemon_core.py tests/test_daemon_service_contract.py tests/test_daemon_trigger_router.py -q` and confirm failures point to the old daemon contract.

## Task 2: Replace Daemon Core Runtime Implementation

**Files:**

- Modify: `tools/launcher/daemon_core.py`

Steps:

- [ ] Rename `MAX_DAEMON_ACTION_IDS` to `MAX_DAEMON_RUNTIME_CALL_IDS`.
- [ ] Add `DaemonHandler` as a `typing.Protocol` with `name`, `handles`, and `handle(context, state, runtime, trigger)`.
- [ ] Rename `ActionGateway` to `DaemonRuntime` without keeping an alias.
- [ ] Rename `record_daemon_action` to `record_runtime_call`.
- [ ] Rename runtime record fields from `action_id`/`action_type` to `runtime_call_id`/`runtime_method`.
- [ ] Use runtime statuses `succeeded` and `failed`.
- [ ] Rename state fields to `daemon_runtime_call_ids` and `daemon_runtime_calls`.
- [ ] Drop stale `daemon_action_ids`, `daemon_actions`, and handler `last_action_turn_id` during `DaemonState.load`.
- [ ] Rename handler state field `last_action_turn_id` to `last_runtime_turn_id`.
- [ ] Rename `_action_status_payload` to `_runtime_status_payload`.
- [ ] Make `daemon_status` return `runtime`, not `actions`.
- [ ] Rename dispatch parameters and call sites from `actions` to `runtime`.
- [ ] Make `dispatch_notification` and `start_daemon_mailbox` instantiate `DaemonRuntime`.
- [ ] Run the Task 1 command until green.

## Task 3: Generalize Mailbox Local Trigger

**Files:**

- Modify: `tests/test_daemon_mailbox.py`
- Modify: `tests/test_daemon_core_decoupling.py`
- Modify: `tools/launcher/daemon_mailbox.py`

Steps:

- [ ] Rewrite local trigger tests to use `example.attention_needed` with arbitrary payload and source context.
- [ ] Add rejection tests for wrong actor, empty/non-string type, non-object payload, non-object source context, empty optional `origin_id`, and empty optional `correlation_id`.
- [ ] Remove tests requiring `message_id`, `reason`, `parent_thread_id`, `side_thread_id`, or side ownership at mailbox ingress.
- [ ] Remove `actions_factory` from `DaemonMailboxServer.__init__`.
- [ ] Remove mailbox import/use of `side_thread_registry`.
- [ ] Rename `_validate_local_trigger_request` to `_normalize_local_trigger_request`.
- [ ] Validate only actor address, type, payload object, optional origin/correlation ids, and source context object.
- [ ] Default omitted `source_context` to `{}`.
- [ ] Dispatch normalized generic `DaemonTrigger`.
- [ ] Run `python3 -m pytest tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py -q` until green.

## Task 4: Update Business Handlers To Runtime Contract

**Files:**

- Modify: `tests/test_task_checkout_handler.py`
- Modify: `tests/test_message_available_handler.py`
- Modify: `tools/launcher/task_checkout_handler.py`
- Modify: `tools/launcher/message_available_handler.py`

Steps:

- [ ] Rename test fakes to `FakeDaemonRuntime`.
- [ ] Rename handler method parameters from `actions` to `runtime`.
- [ ] Update task checkout tests to assert `last_runtime_turn_id`.
- [ ] Update task checkout code to call `runtime.submit_parent_prompt`.
- [ ] Update message available code to call `runtime.parent_activity`, `runtime.submit_parent_prompt`, and `runtime.submit_side_triage_prompt`.
- [ ] Remove `message.parent_required` from message handler `handles`.
- [ ] Remove `_handle_message_parent_required` if no longer used.
- [ ] Rewrite side triage prompt text so it does not instruct use of daemon `mailbox.local_trigger(type="message.parent_required")`.
- [ ] Run `python3 -m pytest tests/test_task_checkout_handler.py tests/test_message_available_handler.py -q` until green.

## Task 5: Entrypoint And Boundary Regression

**Files:**

- Modify: `tests/test_instance_daemon_entrypoint.py` if needed.
- Verify: `tools/launcher/instance_daemon.py`
- Verify: `scripts/env/tool_runtime/daemon_client.py`
- Verify: `scripts/env/tools/message/_impl.py`
- Verify: `scripts/env/tools/message/tool.py`

Steps:

- [ ] Confirm default handlers remain statically registered.
- [ ] Confirm no plugin loader, subscription loader, or dynamic routing was added.
- [ ] Confirm message env tool still delivers generic `message.available` through `DaemonAccess`.
- [ ] Run `python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_central_daemon_service.py tests/test_message_env_tool.py tests/test_runtime_actor_profile.py -q`.

## Task 6: Source Audits And Broad Verification

**Files:**

- Verify: `tools/launcher`
- Verify: focused daemon tests

Steps:

- [ ] Run source audit for old daemon action vocabulary.
- [ ] Run source audit for mailbox `message.parent_required` and mailbox side validation residue.
- [ ] Run source audit for message handler prompt/test residue.
- [ ] Run all focused daemon and related tests listed in the test plan.
- [ ] Run `python3 -m pytest --collect-only -q tests`.
- [ ] Run `git diff --check`.
- [ ] Run `python3 -m pytest tests/test_buddyswitch_launcher.py -q` only after focused tests and audits pass, with resource lifecycle caution.
- [ ] Inspect for residual long-lived test processes if broad verification starts services.

## Self-Review

- Spec coverage: every memo module section is mapped to a task above.
- Placeholder scan: no task uses `TBD`, `TODO`, or vague "add tests" wording.
- Type consistency: the final names are `DaemonRuntime`, `DaemonHandler`, `runtime`, `record_runtime_call`, `runtime_call_id`, `runtime_method`, `daemon_runtime_call_ids`, `daemon_runtime_calls`, `last_runtime_turn_id`, and `status["runtime"]`.
- Scope guard: no plugin system, event bus, workflow engine, action system, compatibility alias, or old/new status dual output is allowed.


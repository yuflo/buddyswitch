# Needs Parent Interrupt Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Use `superpowers:test-driven-development`: write the focused regression first,
> confirm it fails against the current implementation, implement the smallest direct fix, and rerun
> focused and relevant broader checks.

**Goal:** Fix `message.mark(needs_parent)` so side-thread parent handoff works when the parent turn
has already ended, without adding actor journal, context redesign, or new workflow concepts.

**Architecture:** Keep the message module's existing prompt-before-disposition invariant. Change the
runtime submit policy used by `needs_parent` from "always interrupt before submit" to "ensure parent
is stopped or receivable, then submit". Keep the daemon as the owner of parent thread mechanics and
the message tool as the owner of message disposition semantics.

**Tech Stack:** Python launcher daemon runtime, app-server helper wrappers, env-tool message
implementation, JSON runtime state, unittest/pytest.

---

## Current Verified Failure

Observed with:

- `act-market-5d22c6ece3d2` receiving `msg-3c6b95974b02` from
  `act-market-0b1d776d48ab`.
- The receiver side thread attempted `message.mark(needs_parent)` after the parent turn had already
  completed or entered checkout.
- The daemon recorded three `message_mark` runtime calls with:

```text
runtime_method = parent_interrupt
status = failed
error = thread 019e9398-229f-75e0-a1c4-32defba62a4c has no active in-progress turn
```

Root cause:

```text
message.mark(needs_parent)
  -> DaemonAccess.request_parent_message_handling(...)
  -> DaemonRuntime.submit_parent_prompt(..., interrupt_policy="before_submit")
  -> app_server.interrupt_turn(...)
  -> fails when parent has no active in-progress turn
  -> parent prompt is never submitted
  -> message remains in previous disposition
```

The broken assumption is that parent-required handoff always means "interrupt an active parent
turn". The correct behavior is to submit a parent-required prompt after the parent is stopped or
otherwise able to receive a turn.

---

## Scope

In scope:

- Add a daemon runtime parent submit policy for `needs_parent` handoff.
- Switch `DaemonAccess.request_parent_message_handling(...)` to that policy.
- Update existing tests that still assert `before_submit` for `needs_parent`.
- Add focused regressions for the "no active in-progress turn" race.
- Preserve prompt-before-disposition ordering and failure guarantees.

Out of scope:

- No actor journal.
- No thread sync journal.
- No `context.summarize` or `message_cues` redesign.
- No innerTUI framework.
- No task/request/track behavior changes.
- No new message dispositions.
- No model-facing handoff or journal tool.

---

## Design Decision

Add one explicit interrupt policy:

```text
interrupt_policy="ensure_stopped"
```

Meaning:

```text
parent idle
  -> submit parent prompt directly

parent running with active in-progress turn
  -> interrupt parent
  -> wait for parent to become idle
  -> submit parent prompt

parent running but interrupt reports "no active in-progress turn"
  -> treat as parent already stopping/stopped
  -> wait for parent to become idle
  -> submit parent prompt

parent unavailable
  -> fail

parent does not become idle before bounded timeout
  -> fail
```

Why this belongs in `DaemonRuntime`:

- Parent activity, interrupt, wait, and submit are runtime mechanics.
- The message tool should not know app-server thread lifecycle details.
- `message.mark(needs_parent)` should only know whether parent prompt submission succeeded.

Do not change `interrupt_policy="before_submit"` in this fix. Keep it available for callers that
explicitly want the old "interrupt first or fail" behavior. Only `message.mark(needs_parent)` should
move to `ensure_stopped`.

---

## Required Invariants

- `message.mark(needs_parent)` submits the parent prompt before saving `needs_parent`.
- If parent prompt submission fails, the original message disposition remains unchanged.
- If parent prompt submission succeeds and saving `needs_parent` fails, the response must report
  that the parent prompt was submitted but the message disposition did not change.
- `message.mark` remains limited to `absorbed` and `needs_parent`.
- `message.available` routing stays unchanged:
  - parent idle -> parent prompt with `interrupt_policy="none"`;
  - parent running -> side triage prompt.
- Existing source-root broker fix remains intact.

---

## Files To Modify

- `tools/launcher/daemon_core.py`
  - Add `interrupt_policy="ensure_stopped"` support.
  - Add a small bounded wait helper for parent idle/readiness.
  - Treat `no active in-progress turn` during `ensure_stopped` interrupt as a race, not a final
    failure.

- `scripts/env/tool_runtime/context.py`
  - Change `DaemonAccess.request_parent_message_handling(...)` to call
    `submit_parent_prompt(..., interrupt_policy="ensure_stopped")`.

- daemon service runtime policy tests
  - Add focused daemon runtime policy tests.
  - Keep old `before_submit` tests for explicit callers.

- `tests/test_message_env_tool.py`
  - Update projected-runtime/fake-daemon expectations from `before_submit` to `ensure_stopped`.
  - Add or adjust message-level tests proving prompt submission still happens before saving
    `needs_parent`.

- `tests/test_runtime_broker.py`
  - Update live broker projected-manifest regression to expect `ensure_stopped`.

- env.tool response-contract coverage
  - Add or confirm response-contract coverage for parent prompt failure leaving the message
    unchanged.

---

## Test Plan

### 1. Daemon Runtime Policy Tests

Area: daemon service runtime policy tests

Add tests:

- `test_submit_parent_prompt_ensure_stopped_idle_submits_without_interrupt`
  - Patch parent activity/read helpers to report idle.
  - Patch submit helper to return `turn-daemon-1`.
  - Assert no interrupt call happened.
  - Assert one `parent_submit` runtime call succeeded.

- `test_submit_parent_prompt_ensure_stopped_running_interrupts_waits_then_submits`
  - Patch interrupt to return `turn-main-1`.
  - Patch parent activity/read sequence to move from running to idle.
  - Patch submit helper to return `turn-daemon-1`.
  - Assert runtime calls include `parent_interrupt` then `parent_submit`.
  - Assert result includes both `interrupted_turn_id` and `turn_id`.

- `test_submit_parent_prompt_ensure_stopped_no_active_turn_race_waits_then_submits`
  - Patch interrupt to raise:

    ```text
    thread thr-main has no active in-progress turn
    ```

  - Patch parent activity/read sequence to become idle.
  - Assert the prompt is submitted successfully.
  - Assert the failed interrupt is not the final result.
  - Assert the final result has `turn_id`.

- `test_submit_parent_prompt_ensure_stopped_timeout_fails_without_submit`
  - Patch parent activity/read sequence to never become idle.
  - Assert an explicit runtime error is raised.
  - Assert no `parent_submit` runtime call succeeded.

Keep existing tests:

- `test_submit_parent_prompt_before_submit_interrupts_then_submits_and_records_facts`
- `test_submit_parent_prompt_before_submit_records_submit_failure_after_successful_interrupt`

These prove the old explicit policy still works and is not accidentally redefined.

### 2. Runtime Access Tests

File:

```text
tests/test_message_env_tool.py
```

Update existing tests:

- `test_projected_runtime_context_uses_repo_root_for_parent_handoff_import`
  - Expected fake `submit_parent_prompt` payload:

    ```text
    interrupt_policy == "ensure_stopped"
    ```

- `test_message_mark_needs_parent_uses_source_repo_root_when_broker_manifest_is_projected`
  - Expected response parent request:

    ```text
    interrupt_policy == "ensure_stopped"
    ```

Keep existing prompt-first assertions:

- Parent request happens before saving `needs_parent`.
- Parent prompt failure leaves the original unchanged.
- Parent prompt success followed by save failure reports prompt submitted and unchanged message
  disposition.

### 3. Broker Regression Tests

File:

```text
tests/test_runtime_broker.py
```

Update:

- `test_live_broker_needs_parent_uses_repo_root_with_workspace_manifest`
  - Keep the projected-manifest/source-root setup.
  - Assert `message.mark(needs_parent)` succeeds.
  - Assert stored message disposition is `needs_parent`.
  - Change fake daemon parent request assertion to:

    ```text
    interrupt_policy == "ensure_stopped"
    ```

This protects both fixes together:

- projected runtime source root still works;
- `needs_parent` no longer uses blind `before_submit`.

### 4. Response Contract Tests

Area: env.tool response-contract coverage

Ensure coverage for:

- parent prompt submission failure returns `ok=false`;
- `code == "E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED"`;
- `state_changed == false`;
- `durability == "none"`;
- `parent_prompt_submitted == false`;
- `original_final_disposition` remains the previous disposition;
- allowed next action tells the host to inspect the original processable message.

If this is already covered, tighten the assertion so it would fail if a future implementation marks
`needs_parent` after a failed parent submit.

### 5. Source Audits

Run after implementation:

```bash
rg -n 'interrupt_policy="before_submit"|interrupt_policy\\": "before_submit"|interrupt_policy == "before_submit"' scripts tools tests
```

Expected:

- `before_submit` may remain in daemon runtime tests for the explicit old policy.
- `before_submit` should not remain in `DaemonAccess.request_parent_message_handling(...)`.
- Message `needs_parent` tests should expect `ensure_stopped`, not `before_submit`.

Run:

```bash
rg -n 'actor-journal|thread_sync|message_cues|context\\.summarize' scripts tools tests
```

Expected:

- No new actor journal, thread sync, or context-summary implementation changes in this fix.

---

## Implementation Tasks

### Task 1: Add Failing Daemon Runtime Tests

Files:

- Modify: daemon service runtime policy tests

Steps:

- [ ] Add the four `ensure_stopped` tests listed in "Daemon Runtime Policy Tests".
- [ ] Run:

```bash
python3 -m pytest tests -k "submit_parent_prompt and ensure_stopped" -q
```

Expected current failure:

- `submit_parent_prompt(..., interrupt_policy="ensure_stopped")` raises invalid policy.

### Task 2: Implement `ensure_stopped`

Files:

- Modify: `tools/launcher/daemon_core.py`

Steps:

- [ ] Add a bounded wait helper near `DaemonRuntime` using existing daemon poll constants.
- [ ] Accept `interrupt_policy="ensure_stopped"`.
- [ ] For `ensure_stopped`, inspect parent activity before interrupting.
- [ ] If parent is idle, submit directly.
- [ ] If parent is running, try interrupt.
- [ ] If interrupt succeeds, wait for idle before submitting.
- [ ] If interrupt fails with `has no active in-progress turn`, wait for idle before submitting.
- [ ] If parent never becomes idle, raise an explicit error and do not submit.
- [ ] Run:

```bash
python3 -m pytest tests -k "submit_parent_prompt and ensure_stopped" -q
```

Expected:

- New `ensure_stopped` tests pass.
- Existing `none` and `before_submit` tests still pass.

### Task 3: Switch Message Parent Handling To `ensure_stopped`

Files:

- Modify: `scripts/env/tool_runtime/context.py`

Steps:

- [ ] Change `DaemonAccess.request_parent_message_handling(...)` from:

```python
interrupt_policy="before_submit"
```

to:

```python
interrupt_policy="ensure_stopped"
```

- [ ] Do not change prompt rendering, handler name, origin id, or disposition save order.

### Task 4: Update Message-Level Protection Tests

Files:

- Modify: `tests/test_message_env_tool.py`

Steps:

- [ ] Update fake daemon expectations from `before_submit` to `ensure_stopped`.
- [ ] Keep assertions that parent prompt submission happens before saving `needs_parent`.
- [ ] Keep assertions that parent prompt failure leaves the original message unchanged.
- [ ] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
```

Expected:

- Message tests pass with `ensure_stopped`.

### Task 5: Update Broker Protection Tests

Files:

- Modify: `tests/test_runtime_broker.py`

Steps:

- [ ] Update projected-manifest live broker fake daemon expectation from `before_submit` to
  `ensure_stopped`.
- [ ] Keep assertions that the response succeeds and the stored message becomes `needs_parent`.
- [ ] Run:

```bash
python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_broker_needs_parent_uses_repo_root_with_workspace_manifest -q
```

Expected:

- The live broker regression still passes.

### Task 6: Tighten Response Contract Coverage

Files:

- Modify: env.tool response-contract coverage

Steps:

- [ ] Confirm or add coverage for `E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED`.
- [ ] Assert failed parent submit leaves the message in its previous disposition.
- [ ] Assert no response reports `parent_prompt_submitted=true` when parent submit failed.
- [ ] Run:

```bash
python3 -m pytest tests -k "E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED" -q
```

Expected:

- Contract tests pass.

### Task 7: Focused Verification And Source Audits

Files:

- Verify: daemon runtime, message tool, runtime broker, response contracts.

Steps:

- [ ] Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_runtime_broker.py tests -k "submit_parent_prompt or E_MESSAGE_PARENT_REQUIRED_SUBMIT_FAILED" -q
```

- [ ] Run:

```bash
rg -n 'interrupt_policy="before_submit"|interrupt_policy\\": "before_submit"|interrupt_policy == "before_submit"' scripts tools tests
```

- [ ] Confirm `before_submit` remains only for explicit daemon policy tests or non-message callers.
- [ ] Run:

```bash
rg -n 'actor-journal|thread_sync|message_cues|context\\.summarize' scripts tools tests
```

- [ ] Confirm this fix did not implement actor journal, thread sync, or context summary changes.
- [ ] Run:

```bash
git diff --check
```

Expected:

- Focused tests pass.
- Source audits match the expected scope.
- No whitespace errors.

---

## Definition Of Done

This fix is done only when:

- `message.mark(needs_parent)` uses `ensure_stopped` parent submission.
- The observed `no active in-progress turn` race is covered by a daemon runtime regression.
- Parent prompt submission still happens before saving `needs_parent`.
- Parent prompt failure still leaves the original message disposition unchanged.
- Projected runtime/source-root broker coverage still passes.
- No actor journal, thread sync, context summary redesign, or innerTUI framework work is included.
- Focused tests and source audits pass.

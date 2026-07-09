# WebUI Lifecycle Operation Queue And Protection Plan

Date: 2026-07-09
Worktree: `fea-webui`
Scope: Web Management lifecycle interaction only

## Task Objective

Rebuild the START, Stop, Resume, and Clear interaction model so WebUI immediately accepts safe lifecycle intent, clearly protects unsafe same-actor conflicts, and visualizes queued/running/terminal state while existing launcher/runtime commands remain the source of real lifecycle truth.

The target contract is:

```text
consumer clicks a lifecycle action
  -> Web Management accepts or protectively rejects the intent with explicit semantics
  -> WebUI immediately renders queued/running/protective feedback
  -> Web Management serializes actual launcher execution under the real runtime constraint
  -> WebUI polls operation status and reconciles final actor/runtime/thread facts
  -> terminal UI never flashes stale runtime state between pending and final states
```

## Core Product Goals

1. START must not feel blocked by an unrelated in-flight START. Repeated Start clicks are safe additive intent and should create separate queued/starting operation rows immediately.
2. Runtime serialization must be visible as a queue, not hidden behind disabled controls or unexplained waits.
3. Same-actor contradictory operations must be protected, not queued. If an actor is stopping, Resume/Clear/Delete/Stop should be unavailable with a clear reason such as `Resume available after Stop completes`.
4. Different actors should not block each other at the interface layer. If the runtime can only execute one command at a time, operations for other actors should be accepted and queued.
5. Terminal operation reconciliation must be clean. Stop should move from `stopping` directly to `inactive`; Resume should move from `resuming` directly to `active`; Clear should update the thread id directly. The UI must not expose stale actor runtime after removing the operation overlay.
6. Auto-refresh must track operation progress, not only actor roster results.

## Bitter Principles Applied

This plan follows `docs/bitter`:

- Fix the layer that owns the contract. WebUI owns presentation; Web Management owns operation acceptance, protection, and queue projection; launcher/runtime owns real lifecycle execution.
- Small is not enough if the boundary is wrong. Unlocking the button only in JavaScript would turn a real runtime queue into noisy BUSY errors.
- A semantic replacement is unfinished while live surfaces still teach old semantics. Remove global Start blocking, old `accepted` pseudo-running semantics, and stale `active` flashes from live behavior and tests.
- The end-to-end contract must be proven across click, operation acceptance, polling, execution, reconciliation, and rendered result.
- Do not add dual-track compatibility. Replace the current background-thread/busy-reject lifecycle path with one queue/protection path inside Web Management.

## Boundary

Allowed files:

- `tools/launcher/web_management.py`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/styles.css`
- `tests/test_web_management.py`
- `tests/web_management_ui_state.test.js`
- `tests/web_management_ui_contract.test.js`

Do not modify:

- `buddyswitch-codex`
- `tools/launcher/env.sh`
- `tools/launcher/runtime_lock.py`
- `tools/launcher/app_server.py`
- `tools/launcher/app_server.sh`
- `buddyswitch/objects/**`
- runtime instance JSON schema or persistent product objects

Rationale: the requested improvement is a Web Management operation projection and queue. Changing runtime lock semantics would be a separate architecture task.

## Interaction Model

Operation statuses:

```text
queued    accepted by Web Management but waiting for the lifecycle scheduler
running   launcher command is currently executing
succeeded launcher command completed and final instance data is available
failed    launcher command failed after operation acceptance
```

START:

- Button remains enabled when a role is selected.
- Clicking Start returns `202 + operation` and renders a disabled operation row immediately.
- Multiple start operations can coexist as queued/running rows.
- Rows display `queued` or `starting` instead of making the user infer a lock.
- On success, the operation row is replaced by the real actor after roster/console reconciliation.

Stop, Resume, Clear:

- A selected actor can have at most one active lifecycle operation.
- While an actor has an active lifecycle operation, contradictory same-actor actions are disabled with an explicit protective reason.
- Other actors and Start remain usable.
- On success, `operation.result.instance` is applied to the local actor projection before the operation overlay is removed, then normal roster/console refresh reconciles authority.

## Backend Design

Replace lifecycle busy rejection with a Web Management-local scheduler:

- Store every lifecycle operation in `_operations`.
- Maintain a FIFO queue of operation ids.
- Maintain one `_lifecycle_running_operation_id`.
- Accept operations as `queued`.
- Protect same-actor conflicts before enqueueing by checking existing active operations for the actor.
- Dispatch exactly one queued operation at a time.
- Update a dispatched operation to `running`.
- Run the existing command callback.
- On terminal state, dispatch the next queued operation.

This scheduler intentionally serializes all lifecycle commands because the current CLI uses a global runtime lock. The UI can still accept safe intent and show queue progress without pretending execution is parallel.

## Frontend Design

Replace global start blocking with operation-aware rendering:

- `operationIsActive()` returns true for `queued` and `running`.
- `computeCreateEnabled()` only depends on role selection.
- `Start` button text remains `Start`; active operations appear in rows, not on the button.
- Start operation rows show `queued` for queued operations and `starting` for running operations.
- Actor rows show `queued`, `stopping`, `resuming`, or `clearing` from the active operation.
- Action status copy explains protective disabled states for same-actor conflicts.
- Polling continues while any queued or running operation exists.
- Terminal reconciliation applies final `instance` data before active operation removal.

## Key Questions Resolved

- Should same-actor reverse actions queue? No. They are protective disabled states with explanation.
- Should repeated Start queue? Yes. It is safe additive intent.
- Should WebUI implement a fake queue while backend rejects BUSY? No. That would be a dual track and would violate the interface contract.
- Should launcher/runtime lock be changed? No. Not in this task.

## Implementation Plan

### Task 1: Backend Queue Contract

Files:

- Modify `tests/test_web_management.py`
- Modify `tools/launcher/web_management.py`

Steps:

1. Add a failing test proving two Start requests both return `202` while the first command is blocked, with one operation `running` and the second `queued`.
2. Add a failing test proving queued Start dispatches after the first operation succeeds.
3. Add a failing test proving same-actor Stop followed by Resume still returns `409 BUSY` with a protective message and does not enqueue Resume.
4. Replace `_start_lifecycle_operation()` busy acquire/release with queue enqueue and scheduler dispatch.
5. Keep `_run_busy()` unchanged for non-lifecycle interrupt/delete/side operations.
6. Run `python3 -m pytest tests/test_web_management.py -q`.

### Task 2: Frontend Queue And Protection Rendering

Files:

- Modify `tests/web_management_ui_state.test.js`
- Modify `tools/launcher/assets/web-management/app.js`

Steps:

1. Add a failing test proving `computeCreateEnabled()` remains true with an active start operation.
2. Add a failing test proving two Start clicks produce two operation rows and the Start button remains enabled.
3. Add a failing test proving queued Start rows show `queued` and running Start rows show `starting`.
4. Add a failing test proving same-actor lifecycle operation disables contradictory controls with action-specific protective copy.
5. Update frontend selectors, button rendering, row badges, and action status copy.
6. Run `node tests/web_management_ui_state.test.js`.

### Task 3: Terminal Reconciliation Without Stale Runtime Flash

Files:

- Modify `tests/web_management_ui_state.test.js`
- Modify `tools/launcher/assets/web-management/app.js`

Steps:

1. Add a failing test that records actor-list renders during Stop completion and fails if old `active healthy` appears after `stopping`.
2. Add a helper that converts `operation.result.instance` into the local actor row/runtime projection.
3. Apply that final instance projection before `forgetLifecycleOperation()` for Stop, Resume, and Clear.
4. Preserve authoritative roster and actor-console refresh after local projection.
5. Run `node tests/web_management_ui_state.test.js`.

### Task 4: Contract And Residue Cleanup

Files:

- Modify `tests/web_management_ui_contract.test.js` if visible contract expectations need updates.
- Modify WebUI assets only if stale text remains.

Steps:

1. Update contract tests to allow `queued` lifecycle operation status and queued visible copy.
2. Remove live references to old global start blocking semantics.
3. Run the scoped residue scan:

   ```bash
   rg -n "operation\\[\\\"status\\\"\\].*accepted|activeStartLifecycleOperation|isCreating|state\\.createPending|lifecyclePendingAction|Action completed\\.|clear running|confirming|Starting\\.\\.\\." tools/launcher/assets/web-management tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js tests/test_web_management.py
   ```

   Expected: no output.

### Task 5: Full Verification And Browser Acceptance

Commands:

```bash
python3 -m pytest tests/test_web_management.py -q
node --check tools/launcher/assets/web-management/app.js
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
git diff --check
```

Browser acceptance on `http://127.0.0.1:8766/`:

- Click Start while another Start is still active and confirm a second queued row appears immediately.
- Confirm Start remains available for safe additive intent.
- Confirm same-actor conflicting actions are disabled with protective explanation while one lifecycle operation is active.
- Confirm Stop does not visually regress from `stopping` to stale `active` before final `inactive`.
- Confirm final active/inactive/runtime facts reconcile after auto-refresh.

## Non-Goals

- No persistent operation store.
- No runtime lock redesign.
- No CLI lifecycle contract changes.
- No compatibility path for old `accepted` lifecycle semantics.
- No hidden fallback to old busy-reject behavior for Start.

## Completion Criteria

The task is complete only when:

- The new memo exists in this worktree and matches the implemented behavior.
- Backend accepts safe lifecycle operations into a visible queue.
- Same-actor contradictory operations are protectively blocked with explicit feedback.
- Frontend renders queued/running/terminal states without global Start blocking.
- Terminal operation reconciliation avoids stale runtime flashes.
- Automated tests and residue scans pass.
- Live browser acceptance proves the user-visible interaction loop.

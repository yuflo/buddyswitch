# Browser Child Lifecycle Convergence Implementation Plan

> Plan state: `REJECTED / CONSUMED — HISTORICAL ONLY`
> Replaced by:
> `S2-FINAL-F003-BROWSER-LIFECYCLE-R1-RESUME-PLAN.md`
>
> This plan's implementation shape was correct, but its Task 2 → Task 4
> ordering attempted GREEN after package-source mutation and before runtime
> reprovision. The activated runner correctly failed closed. Do not execute
> this plan again.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task by task.

**Goal:** Make Browser process-group termination and the manager's tracked
Python child state converge on every return path, so a terminal child cannot
remain in `_DETACHED_BROWSER_PROCESSES`.

**Architecture:** Keep `browser_runtime_manager._terminate_owned_record` as
the single termination owner. Replace branch-local child reaping with one
function-level finalization postcondition. Do not introduce a lifecycle
framework or change external Browser semantics.

**Tech Stack:** Python 3.13, `unittest.mock`, BuddySwitch's existing process
identity helpers, and the sole `./buddyswitch-test` entrypoint.

---

## 1. Acceptance sentence

> Given an attributable Browser child that becomes terminal at any point
> while `_terminate_owned_record` executes, every return path preserves the
> existing termination result and safety behavior while removing that
> terminal child from `_DETACHED_BROWSER_PROCESSES`; a still-live tracked
> child remains registered.

## 2. Why this is a boundary repair

Current `_terminate_owned_record` has multiple exits:

```text
already not running
getpgid lookup failure
same process group
identity disappears before signal
SIGTERM lookup/permission failure
group disappears during wait
SIGKILL lookup/permission failure
normal completion
```

Selected branches call `_reap_child_pid`; others return directly. Historical
commit `10a4c0110edb3f3f65503dee7c55299e02436c8e` added reaping to the
"group disappears during wait" branch. The next escaped branch proves that
the rule belongs at function exit, not inside individual branches.

## 3. Frozen scope

Modify exactly:

```text
src/buddyswitch/launcher/browser_runtime_manager.py
tests/integration/browser/test_runtime_manager.py
```

Do not modify:

- S2 Demand implementation or tests;
- `tests/process/services/test_app_browser_start_failure.py`;
- shared test infrastructure;
- master migration documents;
- S3 or any other component;
- public Browser contracts, timeouts or return payloads.

Do not stage, commit, push, switch branches or rebase.

## 4. Task 1 — Reproduce source and create deterministic RED

**Files:**

- Modify:
  `tests/integration/browser/test_runtime_manager.py`
- Read:
  `src/buddyswitch/launcher/browser_runtime_manager.py`

- [ ] Reproduce the Goal Packet's HEAD, non-memo patch, empty index,
  non-memo untracked count and exact two-file hashes.
- [ ] Confirm no external task changed either authorized file.
- [ ] Add one exact owner-contract method named:

```text
test_terminate_owned_record_reconciles_tracked_child_on_all_terminal_exits
```

- [ ] Inside that method, use `subTest` cases for exactly these terminal
  exits:

  1. the identity disappears between the first and second
     `process_identity.is_running` checks;
  2. `os.killpg(..., SIGTERM)` raises `ProcessLookupError`;
  3. the TERM wait does not complete and
     `os.killpg(..., SIGKILL)` raises `ProcessLookupError`.

Each terminal case must install one mock `Popen` with:

```python
proc.pid = 4242
proc.poll.return_value = 0
manager._DETACHED_BROWSER_PROCESSES[:] = [proc]
```

Use `addCleanup(manager._DETACHED_BROWSER_PROCESSES.clear)`. Drive the exact
branch with mocks for `process_identity.is_running`, `os.getpgid`,
`os.killpg`, `_wait_pgid_gone` and `_pgid_alive` as required. Assert both:

```python
self.assertEqual(
    manager._terminate_owned_record(record),
    expected_existing_return_value,
)
self.assertEqual(manager._DETACHED_BROWSER_PROCESSES, [])
```

Do not weaken the real lifecycle assertion in
`test_acquire_starts_chrome_records_port_and_pid_marker`.

- [ ] Add one protective `subTest` in the same method for a still-live child:
  use the same-process-group return, set `proc.poll.return_value = None`, and
  assert the existing `Popen` remains in `_DETACHED_BROWSER_PROCESSES`.
- [ ] Run only the new exact test node:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_terminate_owned_record_reconciles_tracked_child_on_all_terminal_exits
```

- [ ] Record a real RED showing at least one current early return leaves the
  terminal child registered.
- [ ] Remove the RED run root and prove no attributable process remains.

Stop if the new test passes before production change or fails for any reason
other than the stale tracked child.

## 5. Task 2 — Implement one exit postcondition

**Files:**

- Modify:
  `src/buddyswitch/launcher/browser_runtime_manager.py`
- Test:
  `tests/integration/browser/test_runtime_manager.py`

- [ ] Wrap the existing body of `_terminate_owned_record` in one
  function-level `try/finally`.
- [ ] In `finally`, call `_reap_child_pid(record.pid)` exactly once.
- [ ] Remove every branch-local `_reap_child_pid(record.pid)` from this
  function.
- [ ] Preserve the existing decision tree and every return value verbatim.
- [ ] Do not change `_reap_child_pid`, `_pid_alive`, public APIs, signal
  timing, timeouts or process-group safety checks.

The intended shape is:

```python
def _terminate_owned_record(record: process_identity.RecordedProcess) -> bool:
    try:
        # Existing identity, process-group and signal decision tree.
        # Preserve its return semantics; no branch-local reap calls.
        ...
    finally:
        _reap_child_pid(record.pid)
```

This is safe for the protected negative branch: `_reap_child_pid` returns
`False` and retains the entry when the tracked `Popen.poll()` is `None`.

- [ ] Run the exact new test node GREEN.
- [ ] Run the existing branch regression:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_terminate_owned_record_reaps_child_when_group_disappears_during_wait
```

- [ ] Run the real lifecycle regression:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_acquire_starts_chrome_records_port_and_pid_marker
```

- [ ] Prove all run roots and attributable Browser processes are absent.

## 6. Task 3 — Prove the owner boundary

- [ ] Run the complete owner file:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py
```

- [ ] Inspect the two-file diff. Reject branch-local duplicate cleanup,
  fallback behavior, weakened assertions or changes outside the acceptance
  sentence.
- [ ] Run `git diff --check`.
- [ ] Prove no process, socket, lock, run-root, instance or active Browser
  residue attributable to these checks.

Stop before broader proof if this task is not fully green and clean.

## 7. Task 4 — Rebuild runtime and prove affected tiers

The production source mutation makes the installed activation stale.

- [ ] Follow the existing S2 runtime reprovision rule in
  `S2-IMPLEMENTATION-PLAN.md` section 10: clean wheel, replaced
  checkout-local runtime venv, non-editable install, installed activation and
  exact source/distribution verification.
- [ ] Record package version, source digest and distribution digest.
- [ ] Run:

```bash
./buddyswitch-test focused tests/integration
```

- [ ] Then run:

```bash
./buddyswitch-test focused tests/process
```

- [ ] Prove tier run roots and attributable runtime resources are absent.

These tiers are mandatory because the defect escaped in Integration and the
Browser lifecycle has process-level consumers. Do not substitute a selected
group for either complete tier.

## 8. Task 5 — Freeze and run one FINAL

- [ ] Freeze HEAD, exact non-memo diff, index, untracked identity, authorized
  file hashes and activation identity.
- [ ] Confirm exactly the two authorized executable files changed during this
  prerequisite.
- [ ] Confirm every preceding proof is green and cleanup is clean.
- [ ] Run exactly once:

```bash
./buddyswitch-test full
```

- [ ] If FINAL passes, record all tier totals, duration and global cleanup.
- [ ] If FINAL fails, do not rerun it and do not repair another finding.
  Return the exact failure and stop.

## 9. Return boundary

Return the result format required by
`S2-FINAL-F003-BROWSER-LIFECYCLE-GOAL-PACKET.md`, propose `ACCEPTED` or
`REJECTED`, and stop. Only the coordinating hub may close the prerequisite,
accept S2, update master migration truth, commit or push.

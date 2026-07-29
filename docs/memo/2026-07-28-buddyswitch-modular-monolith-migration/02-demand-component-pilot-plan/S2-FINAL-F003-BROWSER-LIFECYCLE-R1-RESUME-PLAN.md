# Browser Lifecycle R1 Activation-First Resume Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to execute this plan task by task.
> Plan state: `ACCEPTED / CONSUMED`

This plan completed successfully and is closed by `S2-ACCEPTANCE.md`. It is
not an active resume surface.

**Goal:** Preserve the accepted RED and current two-file Browser lifecycle
repair, restore exact installed/source correspondence, then complete the
previously blocked GREEN-to-FINAL evidence chain without another source edit.

**Architecture:** The implementation remains one function-level reconciliation
postcondition in `_terminate_owned_record`. R1 changes no product or test
source. It corrects only the execution boundary: every coherent
`src/buddyswitch/**` mutation is followed immediately by runtime reprovision
before the public test runner is invoked.

**Tech Stack:** Python 3.13.5, PEP 517 wheel build, non-editable venv install,
BuddySwitch runtime activation and the sole `./buddyswitch-test` entrypoint.

---

## 1. Acceptance sentence

> On one frozen source and activated installed distribution, every terminal
> exit from `_terminate_owned_record` preserves its existing return and safety
> semantics while reconciling a terminal tracked Browser child, retaining a
> live tracked child, and leaving no process or runtime residue.

## 2. Accepted and reusable evidence

The previous packet reproduced the escaped defect before production repair:

```text
exact RED:
d871368dee4640acb8bd03e9f59aba51

target:
tests/integration/browser/test_runtime_manager.py::
BrowserRuntimeManagerTests::
test_terminate_owned_record_reconciles_tracked_child_on_all_terminal_exits

result:
three terminal early exits retained the stale tracked child;
the protected live-child case passed;
run root and attributable processes absent
```

The current implementation then made exactly the selected change:

- one function-level `try/finally`;
- one `_reap_child_pid(record.pid)` in `finally`;
- no branch-local reap calls;
- unchanged return values, identity checks, process-group guards and signal
  escalation.

Do not rerun RED and do not revert either authorized file. RED is valid
historical before/after evidence for the current regression test and repair.

## 3. Why the previous packet stopped

`./buddyswitch-test` always starts through the activated installed Python and
`tests.runner._preflight` publishes only a verified runtime identity. After
`browser_runtime_manager.py` changed, the installed distribution still
contained the preceding bytes. The runner therefore stopped before creating a
run:

```text
exit: 2
run ID: none
error: RUNTIME_MISMATCH
changed path: launcher/browser_runtime_manager.py
```

This is correct fail-closed behavior, not a failed Browser GREEN. The previous
packet was wrong to schedule reprovision after that GREEN.

### R1 build-path preflight

The coordinating hub executed the temporary-copy build path without touching
the checkout runtime:

```text
evidence:                  S2-F003-R1-BUILD-20260729-01
temporary source manifest: exact pyproject.toml and src/buddyswitch bytes
wheel result:              buddyswitch-0.1.0-py3-none-any.whl
wheel Browser manager:     94df61c368c4772c95279184ad4bd4764ad6d521539706f4a2e7c58b6360ee03
expected source hash:      94df61c368c4772c95279184ad4bd4764ad6d521539706f4a2e7c58b6360ee03
temporary root:            absent after proof
non-memo source identity:  unchanged
```

This proves the frozen source can produce the required wheel from an isolated
byte-identical copy without rewriting ignored build artifacts in the
worktree. It does not replace R1 installation, activation or test evidence.

## 4. Frozen R1 scope

Executable/test source is read-only in R1:

```text
src/buddyswitch/launcher/browser_runtime_manager.py
tests/integration/browser/test_runtime_manager.py
all other source and tests
```

R1 explicitly authorizes replacement of only the checkout-local generated
runtime:

```text
.buddyswitch-runtime/venv/**
.buddyswitch-runtime/activation.json
```

It also authorizes one isolated temporary build root created with `mktemp -d`.
That root contains a byte-identical copy of `pyproject.toml` and
`src/buddyswitch`, plus the wheel output. Building from this copy prevents
setuptools from rewriting ignored `build/` or `src/buddyswitch.egg-info/`
inside the frozen worktree.

Do not edit source, tests, package declarations, migration documents or the
test runner. Do not stage, commit, push, switch branches or rebase. If any
source edit appears necessary, stop and return to the coordinating hub.

## 5. Task 1 — Reproduce the frozen resume identity

- [ ] Reproduce the exact HEAD, non-memo patch, empty index, non-memo
  untracked identities and two authorized file hashes in the R1 Goal Packet.
- [ ] Record the complete read-only `docs/memo/**` identity at entry.
- [ ] Confirm no test root, attributable process or system lock remains.
- [ ] Confirm the old activation returns `RUNTIME_MISMATCH` only for the
  expected changed package source. Do not run a test before reprovision.
- [ ] Inspect the two-file diff and confirm it still matches section 2.

Stop if executable identity differs, the index is non-empty, another task
overlaps, or runtime mismatch reports any unexpected path.

## 6. Task 2 — Reprovision before GREEN

Use repository root
`/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`, system bootstrap Python
`/Users/chen/miniconda3/bin/python3.13`, one `mktemp -d` build root and
checkout runtime `.buddyswitch-runtime`.

- [ ] Create the temporary build root with `source/src` and `wheel`
  subdirectories. Copy only the frozen build inputs:

```bash
r1_build_root="$(mktemp -d)"
mkdir -p "${r1_build_root}/source/src" "${r1_build_root}/wheel"
cp pyproject.toml "${r1_build_root}/source/pyproject.toml"
cp -R src/buddyswitch "${r1_build_root}/source/src/buddyswitch"

cmp pyproject.toml "${r1_build_root}/source/pyproject.toml"
diff -qr src/buddyswitch "${r1_build_root}/source/src/buddyswitch"
```

- [ ] Prove `cmp` succeeds for `pyproject.toml` and `diff -qr` reports no
  difference between the original and copied `src/buddyswitch`.
- [ ] Build one clean wheel from the byte-identical temporary source:

```bash
/Users/chen/miniconda3/bin/python3.13 -m pip wheel \
  --no-deps \
  --no-build-isolation \
  --wheel-dir "${r1_build_root}/wheel" \
  "${r1_build_root}/source"
```

- [ ] Recreate the checkout-local venv in place:

```bash
/Users/chen/miniconda3/bin/python3.13 -m venv --clear \
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool/.buddyswitch-runtime/venv
```

- [ ] Install the frozen test dependencies:

```bash
.buddyswitch-runtime/venv/bin/python -m pip install \
  --requirement requirements-test.txt
```

- [ ] Install exactly the newly built wheel non-editably and without index:

```bash
.buddyswitch-runtime/venv/bin/python -m pip install \
  --no-deps \
  --no-index \
  --find-links "${r1_build_root}/wheel" \
  buddyswitch==0.1.0
```

- [ ] Activate and verify exact correspondence:

```bash
.buddyswitch-runtime/venv/bin/python -m \
  buddyswitch.application.entrypoints.runtime_activation \
  activate \
  --source-root /Users/chen/Dev/buddyswitch/.worktrees/fea-tool

.buddyswitch-runtime/venv/bin/python -m \
  buddyswitch.application.entrypoints.runtime_activation verify

.buddyswitch-runtime/venv/bin/python -m \
  buddyswitch.application.entrypoints.runtime_activation status
```

- [ ] Record package version, activation time, source digest, distribution
  digest, Python and installed package root.
- [ ] Remove only the exact temporary build root and prove it absent.
- [ ] Confirm no source, test or memo file changed during reprovision.

Stop if build, install, activate or verify fails. Do not repair packaging or
source in this packet.

## 7. Task 3 — Complete exact and owner proof

- [ ] Run the previously blocked exact GREEN:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_terminate_owned_record_reconciles_tracked_child_on_all_terminal_exits
```

- [ ] Run the existing historical branch regression:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_terminate_owned_record_reaps_child_when_group_disappears_during_wait
```

- [ ] Run the real acquire/release lifecycle:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_acquire_starts_chrome_records_port_and_pid_marker
```

- [ ] Run the complete Browser owner file:

```bash
./buddyswitch-test focused \
  tests/integration/browser/test_runtime_manager.py
```

- [ ] Record each run ID, result, duration and cleanup.

If any command fails, diagnose the signal but do not blind-rerun. Because R1
is source-read-only, return the evidence and stop if resolving it requires an
edit.

## 8. Task 4 — Complete affected tier proof

- [ ] Run the complete Integration tier:

```bash
./buddyswitch-test focused \
  tests/integration \
  src/buddyswitch/modules/demand/tests/integration
```

- [ ] Run the complete Process tier:

```bash
./buddyswitch-test focused tests/process
```

- [ ] Record run IDs, totals, duration and cleanup.
- [ ] Confirm runtime activation still verifies and source identity is
  unchanged.

Stop before FINAL on any failure, residue or identity drift.

## 9. Task 5 — Freeze and run one FINAL

- [ ] Freeze complete worktree identity, the current non-memo patch,
  untracked identities, two Browser file hashes and activation identity.
- [ ] Confirm all preceding proof is green and no source changed after
  activation.
- [ ] Run exactly once:

```bash
./buddyswitch-test full
```

- [ ] If FINAL fails, do not rerun it and do not create another repair.
  Return its exact evidence and stop.
- [ ] If FINAL passes, prove global run-root, process, socket, lock, instance
  and Browser cleanup, then return the R1 result packet.

Only the coordinating hub may accept S2, close findings, commit or push.

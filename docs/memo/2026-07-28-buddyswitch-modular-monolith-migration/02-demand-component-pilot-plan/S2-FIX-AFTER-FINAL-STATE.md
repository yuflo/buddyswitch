# S2 Acceptance Prerequisite State

> State: `ACCEPTED / CLOSED`
> Parent stage: `S2 Demand Component Pilot`
> Consumed packet: `BS-MM-S2-BROWSER-LIFECYCLE-R1-20260729-01`
> Closed finding: `S2-FINAL-F003`
> Updated: 2026-07-29

This record preserves the resolved S2 acceptance-prerequisite history.
R1 completed the activation-first proof chain and the coordinating hub closed
the finding in `S2-ACCEPTANCE.md`. This file is not resumable and authorizes
neither an S2 packet nor S3 implementation.

## 1. Current source identity

```text
HEAD:                              28ca25d93b84c0165fa4cd6f92744744c1df5d67
branch:                            fea-tool
current non-memo tracked patch:    ca73ae9facae7d4f7a53e628e0d10bf4cadf08c95efed9a5438764838c9859c5
index patch:                       e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-memo untracked paths:          41
non-memo untracked path-set:       84fceb226de1414d7a2de1a1638988d7e4040ff11a8d716d5c1c5176ce5b600a
non-memo untracked path/content:    2fcd56fca903b5f3054a0a825fff11813ca628b9ecda2679650d1d610707a3be
Browser manager file SHA-256:      94df61c368c4772c95279184ad4bd4764ad6d521539706f4a2e7c58b6360ee03
Browser integration file SHA-256:  0651a79d8a2dfdddfb627066aba913b9b6ac1f10f0cba2e6ef0f8bc8e7c0f469
```

Coordinating changes under `docs/memo/**` are deliberately excluded from the
non-memo executable patch identity. The executor must preserve all existing
dirty work and independently reproduce this identity. R1 authorizes no
repository source or test edit.

The S2 Demand implementation remains the candidate. No Demand source,
master migration truth, S3 work, commit, stage or push is authorized by this
prerequisite.

## 2. Accepted findings

`S2-FINAL-F001` is closed. The Browser not-ready process test now captures the
real fake-Chrome `Popen` synchronously at the parent launch boundary instead
of depending on a child-authored PID file.

```text
exact run: 23e5c28a819640c2affefde89682c61e
result:    1 passed; process and run root absent
```

`S2-FINAL-F002` is closed. The app-server early-exit process test now creates
the real child and identity under parent control before terminating it, so
the product observes a deterministic exit.

```text
exact run:   fff09b42c52e43ed8719af14d608dd2b
owner file:  b76105b9e1c94b8bb0ab6ff9fcec74b5
Process:     6f72e37b3a66442ca851869c08eed516
result:      1 passed; 2 passed; 262 passed plus 379 subtests
cleanup:     clean
```

These repairs are accepted and must not be reverted.

## 3. Original F003 rejecting evidence

The single frozen FINAL run
`4ca6ae44008d4387aedd13c2c265d566` produced:

```text
Unit:        430 passed, 1,124 subtests
JavaScript:  147 passed
Integration: 758 passed, 1 failed, 438 subtests
Process:     not entered
System:      not entered
```

The failing target was:

```text
tests/integration/browser/test_runtime_manager.py::
BrowserRuntimeManagerTests::
test_acquire_starts_chrome_records_port_and_pid_marker
```

`manager.release(...)` returned success and the real fake-Chrome child was
already reaped, but the same `Popen` remained in
`_DETACHED_BROWSER_PROCESSES`. The externally observed Browser process state
and the manager's in-memory child ownership state therefore contradicted each
other.

The independent executor correctly stopped. Its later two turns were no-op
audits required by the goal blocker threshold, not repeated FINAL runs or
new source mutations.

## 4. Root cause and architectural decision

`_terminate_owned_record` owns termination of an attributable Browser process
group, but cleanup of the tracked Python child is repeated in selected
branches. Several terminal early returns bypass `_reap_child_pid`.

Commit `10a4c0110edb3f3f65503dee7c55299e02436c8e` already repaired one such
branch, where the process group disappears during the wait. The current
failure demonstrates that adding another branch-local call would be
patch-on-patch at the same invariant.

The selected repair is one function-level postcondition:

> Whenever `_terminate_owned_record` returns, it attempts to reconcile and
> reap the recorded child exactly once. If the tracked child is still live,
> `_reap_child_pid` leaves it registered; if it is terminal, no stale tracked
> `Popen` remains.

The consumed prerequisite implemented this as one `try/finally` boundary
around the existing termination decision tree and removed branch-local reap
duplication. It preserved every existing return value, identity check,
same-process-group guard, permission failure and signal escalation behavior.

No lifecycle framework, new registry, new abstraction or Browser redesign is
authorized.

## 5. Accepted RED and current implementation

The deterministic RED is valid and reusable:

```text
run:     d871368dee4640acb8bd03e9f59aba51
result:  three terminal exits retained the stale child;
         the live-child case remained registered
cleanup: clean
```

Exactly the two authorized files then changed. The current non-memo patch and
file hashes are frozen in section 1.

## 6. Rejected packet and controller correction

The consumed packet
`BS-MM-S2-BROWSER-LIFECYCLE-20260729-01` scheduled:

```text
production source edit
-> exact GREEN
-> owner proof
-> runtime reprovision
```

That ordering contradicted the accepted runtime contract. Any
`src/buddyswitch/**` mutation makes the installed activation stale, and
`./buddyswitch-test` fails closed before creating a run until exact
source/distribution correspondence is restored.

The attempted GREEN therefore produced no run ID and exited `2` with
`RUNTIME_MISMATCH` on `launcher/browser_runtime_manager.py`. This is not a
failed Browser GREEN. It is a coordinating-packet defect.

The old packet and implementation plan are `REJECTED / CONSUMED`. R1 corrects
only the execution order:

```text
accepted RED and frozen implementation
-> runtime reprovision and verify
-> exact GREEN
-> owner proof
-> Integration and Process
-> one FINAL
```

## 7. R1 authorized scope

No executable, test or document file may change in R1. These files are
read-only:

```text
src/buddyswitch/launcher/browser_runtime_manager.py
tests/integration/browser/test_runtime_manager.py
```

R1 may replace only the checkout-local generated runtime and create/clean one
exact `mktemp` build root containing a byte-identical source copy and wheel:

```text
.buddyswitch-runtime/venv/**
.buddyswitch-runtime/activation.json
```

Stop and return to the hub if any repository edit is required.

## 8. Required proof ladder

The executor must:

1. reproduce current source and known stale activation;
2. rebuild, non-editably install, activate and verify the runtime;
3. run exact GREEN and both existing Browser regressions;
4. run the complete Browser runtime-manager integration file;
5. run root and module-local Integration;
6. run the complete Process tier;
7. freeze source, diff and activation identity;
8. run `./buddyswitch-test full` exactly once.

Stop before FINAL on any focused failure or attributable residue. If the
single FINAL fails, do not rerun it; return the evidence and stop.

## 9. Resume and return boundary

Resume only through
`S2-FINAL-F003-BROWSER-LIFECYCLE-R1-GOAL-PACKET.md`. Return:

- starting and exact final non-memo source identity;
- reused RED and exact GREEN evidence;
- runtime build/install/activation identity;
- Browser owner-file, Integration-tier, Process-tier and FINAL evidence;
- global process/socket/lock/run-root/instance/Browser cleanup;
- omitted checks and residual risk;
- proposed `ACCEPTED` or `REJECTED`.

Do not begin S3, update master migration truth, commit, stage or push.

## 10. Final closure

R1 returned against the exact frozen source and performed no repository edit.
After activation-first reprovision it passed the exact GREEN, both regressions,
the Browser owner file, complete Integration, complete Process and one frozen
FINAL:

```text
exact GREEN:      090399c8d6e74e888f7df159cd41b1b9
Browser file:     e669bde115ae4c67af2ebfb5674d9ad7
Integration:      5571fa5053b048e5b8b006a96e745a66
Process:          ac14e92bf10a46f1817bda50a2e07beb
FINAL:            865b88ce29d34c25aef70c122b41768c
FINAL result:     PASS
```

`S2-FINAL-F003` and S2 are closed by
`02-demand-component-pilot-plan/S2-ACCEPTANCE.md`. The R1 packet is consumed.

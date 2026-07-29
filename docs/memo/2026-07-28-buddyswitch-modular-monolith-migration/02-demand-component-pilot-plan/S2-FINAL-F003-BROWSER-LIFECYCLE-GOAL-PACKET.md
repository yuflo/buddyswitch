# S2 Browser Lifecycle Prerequisite Goal Packet

> Packet ID: `BS-MM-S2-BROWSER-LIFECYCLE-20260729-01`
> Packet state: `REJECTED / CONSUMED — DO NOT EXECUTE`
> Parent stage: `S2 Demand Component Pilot`
> Finding: `S2-FINAL-F003`
> Prepared by: coordinating hub
> Replacement packet:
> `BS-MM-S2-BROWSER-LIFECYCLE-R1-20260729-01`

This packet was consumed after its mandatory GREEN command was stopped by the
expected installed/source correspondence guard. Its ordering placed runtime
reprovision after GREEN while any `src/buddyswitch/**` edit makes GREEN
unrunnable before reprovision. Preserve it as failure evidence; do not edit,
resume or execute its command sequence.

## 1. Copy-paste independent task request

```text
Create and pursue the following goal in this existing independent S2 task:

Execute BuddySwitch packet BS-MM-S2-BROWSER-LIFECYCLE-20260729-01.
Repair the Browser child-termination ownership boundary so every return from
_terminate_owned_record performs one terminal-child reconciliation, without
changing its existing return values, safety guards or external Browser
behavior. Add deterministic owner-contract RED/GREEN coverage, prove the
complete Browser owner file, rebuild and verify the installed runtime, prove
the complete Integration and Process tiers, then run one frozen full
acceptance. Modify only the two authorized executable files. If any gate or
the single FINAL fails, do not rerun or widen scope: return exact evidence and
stop.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/02-demand-component-pilot-plan/S2-FINAL-F003-BROWSER-LIFECYCLE-GOAL-PACKET.md

Follow root AGENTS.md, $buddyswitch-testing,
superpowers:systematic-debugging, superpowers:test-driven-development,
superpowers:executing-plans and superpowers:verification-before-completion.
Do not edit coordinating-owned migration documents, touch Demand/S3, stage,
commit, push, switch branches or rebase. Return the required result packet
and stop. I will bring it to the coordinating task for acceptance.
```

## 2. Starting identity

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

branch:
fea-tool

HEAD:
28ca25d93b84c0165fa4cd6f92744744c1df5d67

non-memo tracked patch SHA-256:
b2ee7c7d99b93e4c897195d6e3f6883d5a98408fa5e300767593b1434ee7fb7c

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo untracked paths:
41

non-memo untracked sorted-NUL path-set SHA-256:
84fceb226de1414d7a2de1a1638988d7e4040ff11a8d716d5c1c5176ce5b600a

non-memo untracked length-framed path/content SHA-256:
2fcd56fca903b5f3054a0a825fff11813ca628b9ecda2679650d1d610707a3be

src/buddyswitch/launcher/browser_runtime_manager.py SHA-256:
f322d7c37ae1b5127d089807b2b3a873c78ef1eb3843eff2053ed6a629ff9918

tests/integration/browser/test_runtime_manager.py SHA-256:
fa09db023713a9f2d572b6efc6ad8970aa4d42b33dbea125bf35b633050b5a04
```

Compute the non-memo tracked patch with:

```bash
git diff --binary -- . ':(exclude)docs/memo/**' | shasum -a 256
```

For the 41 non-memo untracked files, sort the paths. The path-set hash consumes
each UTF-8 path followed by NUL. The path/content hash consumes, per path in
the same order:

```text
8-byte big-endian path length
8-byte big-endian content length
UTF-8 path bytes
raw content bytes
```

At entry, independently reproduce every identity above and record the full
current coordinating `docs/memo/**` identity. Stop before editing if HEAD,
branch, index, non-memo patch, either non-memo untracked identity or either
authorized file differs. Preserve all existing dirty work.

## 3. Goal and acceptance

Acceptance sentence:

> Given an attributable Browser child that becomes terminal at any point
> while `_terminate_owned_record` executes, every return path preserves the
> existing termination result and safety behavior while removing that
> terminal child from `_DETACHED_BROWSER_PROCESSES`; a still-live tracked
> child remains registered.

This prerequisite is complete only when the deterministic owner contract,
real Browser lifecycle, installed-runtime correspondence, complete
Integration and Process tiers, single FINAL and global cleanup all agree.

## 4. Read order

1. root `AGENTS.md`;
2. `.agents/skills/buddyswitch-testing/SKILL.md` and all required references;
3. the applicable Superpowers skills named in section 1;
4. `S2-FIX-AFTER-FINAL-STATE.md`;
5. `S2-FINAL-F003-BROWSER-LIFECYCLE-IMPLEMENTATION-PLAN.md`;
6. current authorized production and integration-test files;
7. historical commit
   `10a4c0110edb3f3f65503dee7c55299e02436c8e` for evidence of the prior
   branch-local repair.

The implementation plan is authoritative for the execution sequence.

## 5. Exact authority

Writable executable files:

```text
src/buddyswitch/launcher/browser_runtime_manager.py
tests/integration/browser/test_runtime_manager.py
```

Read-only evidence file:

```text
tests/process/services/test_app_browser_start_failure.py
```

Forbidden:

- any S2 Demand or S3 change;
- any test-runner, timeout or retry change;
- any public Browser contract or payload change;
- compatibility, fallback, suppression, skip or weakened assertion;
- another branch-local `_reap_child_pid` patch;
- any third executable or test file;
- master ledger/decision/residue/document edits;
- stage, commit, push, branch switch or rebase.

If another file or semantic change is necessary, return
`STOPPED / REPLANNING REQUIRED` with evidence.

## 6. Frozen repair shape

Implement one postcondition at the current semantic owner:

```python
def _terminate_owned_record(record: process_identity.RecordedProcess) -> bool:
    try:
        # Existing decision tree and return values.
        ...
    finally:
        _reap_child_pid(record.pid)
```

Remove branch-local reap calls from this function. Do not change
`_reap_child_pid`. The finally block is reconciliation, not unconditional
removal: a live tracked `Popen` remains registered because its `poll()` is
`None`.

## 7. Mandatory evidence sequence

Use only:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

Execute in order:

1. deterministic exact RED:
   `tests/integration/browser/test_runtime_manager.py::BrowserRuntimeManagerTests::test_terminate_owned_record_reconciles_tracked_child_on_all_terminal_exits`;
2. single-postcondition implementation;
3. the same exact GREEN;
4. existing group-disappears regression;
5. real acquire/release lifecycle regression;
6. complete
   `tests/integration/browser/test_runtime_manager.py`;
7. `git diff --check` and exact cleanup;
8. runtime reprovision and activation verification per the existing S2 rule;
9. complete `tests/integration`;
10. complete `tests/process`;
11. freeze source/diff/activation identity;
12. one `./buddyswitch-test full`.

Do not reuse the failed FINAL as GREEN. Do not run FINAL until every earlier
gate is green and clean. Do not rerun FINAL after failure.

## 8. Stop conditions

Stop immediately and return evidence if:

- entry identity differs;
- the deterministic test does not RED for the stale child;
- implementation requires more than the two authorized files;
- a return value, safety guard or public Browser behavior must change;
- any focused/tier check fails or leaves attributable residue;
- source changes after freeze;
- FINAL fails;
- another independent task changes the worktree.

Do not self-authorize another repair packet.

## 9. Required result packet

```text
Packet ID and status:
Starting HEAD / non-memo patch / index / untracked count, path-set and content identity:
Authorized starting file hashes:
Exact final non-memo diff and two changed files:
Root cause confirmed:
Deterministic RED node(s), run ID(s), result and cleanup:
Exact GREEN node(s), run ID(s), result and cleanup:
Browser owner-file run ID/result:
Runtime rebuild and activation identity:
Integration-tier run ID/result:
Process-tier run ID/result:
Frozen FINAL run ID and tier totals:
Consumer-observed lifecycle contract:
Global process/socket/lock/run-root/instance/Browser cleanup:
git diff --check:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```

Stop after returning this packet. The coordinating hub alone decides whether
to close `S2-FINAL-F003` and accept S2.

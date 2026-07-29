# S2 Browser Lifecycle R1 Resume Goal Packet

> Packet ID: `BS-MM-S2-BROWSER-LIFECYCLE-R1-20260729-01`
> Packet state: `ACCEPTED / CONSUMED`
> Parent stage: `S2 Demand Component Pilot`
> Finding: `S2-FINAL-F003`
> Prepared by: coordinating hub

This packet completed successfully and is closed by `S2-ACCEPTANCE.md`. It is
retained as execution history and must not be resumed.

## 1. Copy-paste independent task request

```text
Resume the previously blocked goal in this existing independent S2 task and
pursue the following replacement packet:

Execute BuddySwitch packet
BS-MM-S2-BROWSER-LIFECYCLE-R1-20260729-01. Preserve the accepted RED and the
current two-file Browser lifecycle repair. Make no source or test edits.
First rebuild, non-editably install, activate and verify the checkout runtime
against the current source; only then run the exact GREEN, existing Browser
regressions, complete Browser owner file, complete Integration and Process
tiers, and one frozen full acceptance. If any post-activation check fails,
diagnose without blind rerun; if resolution requires a source edit or FINAL
fails, return exact evidence and stop.

Work only in:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

Read and execute only:
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/02-demand-component-pilot-plan/S2-FINAL-F003-BROWSER-LIFECYCLE-R1-GOAL-PACKET.md

Follow root AGENTS.md, $buddyswitch-testing,
superpowers:systematic-debugging, superpowers:executing-plans and
superpowers:verification-before-completion. Do not execute the rejected
predecessor packet. Do not edit source, tests or coordinating documents; do
not touch Demand/S3, stage, commit, push, switch branches or rebase. Return
the required result packet and stop. I will bring it to the coordinating task
for acceptance.
```

## 2. Frozen entry identity

```text
worktree:
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool

branch:
fea-tool

HEAD:
28ca25d93b84c0165fa4cd6f92744744c1df5d67

non-memo tracked patch SHA-256:
ca73ae9facae7d4f7a53e628e0d10bf4cadf08c95efed9a5438764838c9859c5

index patch SHA-256:
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

non-memo untracked paths:
41

non-memo untracked sorted-NUL path-set SHA-256:
84fceb226de1414d7a2de1a1638988d7e4040ff11a8d716d5c1c5176ce5b600a

non-memo untracked length-framed path/content SHA-256:
2fcd56fca903b5f3054a0a825fff11813ca628b9ecda2679650d1d610707a3be

src/buddyswitch/launcher/browser_runtime_manager.py SHA-256:
94df61c368c4772c95279184ad4bd4764ad6d521539706f4a2e7c58b6360ee03

tests/integration/browser/test_runtime_manager.py SHA-256:
0651a79d8a2dfdddfb627066aba913b9b6ac1f10f0cba2e6ef0f8bc8e7c0f469

git diff --check:
clean
```

The old activation is intentionally stale:

```text
activated_at:        2026-07-29T06:51:18.139002Z
package_version:     0.1.0
source_digest:       fb207fe776118295bac83417b0d5db63862cccd397f1a4be8c273e067e27ced8
distribution_digest: b4786117c8d7629ce6f8b2b53282a9a08c4d061f58d326617f99935ac15837c1
verify:              RUNTIME_MISMATCH at launcher/browser_runtime_manager.py
```

That mismatch is the expected R1 entry condition and explicitly authorizes
Task 2 runtime reprovision. It is not a reason to rerun GREEN first.

At entry, reproduce every non-memo identity and record the current read-only
`docs/memo/**` identity. Stop before mutation if anything except the known
runtime activation differs.

## 3. Accepted evidence and current claim

Reuse without rerun:

```text
RED run: d871368dee4640acb8bd03e9f59aba51
RED claim: three terminal early returns retained a stale tracked child;
           the live-child case remained registered
cleanup: clean
```

Coordinating build-path preflight:

```text
evidence:              S2-F003-R1-BUILD-20260729-01
temporary copy:        exact pyproject.toml + src/buddyswitch bytes
wheel:                 buddyswitch-0.1.0-py3-none-any.whl
wheel/source manager:  matching SHA-256 94df61c368c4772c95279184ad4bd4764ad6d521539706f4a2e7c58b6360ee03
cleanup/source:        temporary root absent; non-memo identity unchanged
```

Current claim:

> On one frozen source and activated installed distribution, every terminal
> exit from `_terminate_owned_record` preserves its existing return and safety
> semantics while reconciling a terminal tracked Browser child, retaining a
> live tracked child, and leaving no process or runtime residue.

## 4. Authority and prohibitions

Authorized mutations:

```text
.buddyswitch-runtime/venv/**
.buddyswitch-runtime/activation.json
one mktemp-created byte-identical build root and its cleanup
```

All repository source, tests and documents are read-only. In particular:

```text
src/buddyswitch/launcher/browser_runtime_manager.py
tests/integration/browser/test_runtime_manager.py
```

Do not execute or edit the rejected predecessor Packet. Do not change
timeouts, runner behavior, package declarations, tests, Browser contracts,
Demand, S3 or master migration truth. Do not stage, commit, push, switch
branches or rebase.

## 5. Required sequence

Execute
`S2-FINAL-F003-BROWSER-LIFECYCLE-R1-RESUME-PLAN.md` in order:

1. reproduce frozen source and known stale activation;
2. build wheel, recreate venv, install test dependencies and wheel, activate
   and verify;
3. exact GREEN;
4. historical branch and real lifecycle regressions;
5. complete Browser owner file;
6. complete Integration tier;
7. complete Process tier;
8. freeze source and activation identity;
9. one `./buddyswitch-test full`;
10. global cleanup and return.

No public test command is authorized before step 2 completes.

## 6. Stop conditions

Stop and return evidence if:

- entry source/index/untracked identity differs;
- stale activation names an unexpected mismatch;
- build, install, activation or verification fails;
- runtime reprovision changes a repository source/test/document file;
- any post-activation test fails and resolution requires a source edit;
- any run leaves attributable residue;
- source or activation drifts after freeze;
- FINAL fails;
- another task changes the worktree.

Do not blind-rerun a failure and do not self-authorize another repair.

## 7. Required result packet

```text
Packet ID and status:
Starting HEAD / patch / index / untracked / memo identity:
Reused RED evidence:
Pre-reprovision RUNTIME_MISMATCH:
Wheel / venv / dependency / package install result:
New activation identity and verify/status result:
Exact GREEN run ID/result/cleanup:
Historical branch regression run ID/result:
Real lifecycle run ID/result:
Browser owner-file run ID/result:
Integration-tier run ID/result:
Process-tier run ID/result:
Frozen full source and activation identity:
FINAL run ID and tier totals:
Global process/socket/lock/run-root/instance/Browser cleanup:
Source preservation and git diff --check:
Omitted checks and residual risk:
Stop/replan discoveries:
Proposed ACCEPTED / REJECTED:
```

Stop after returning this packet. Only the coordinating hub may close
`S2-FINAL-F003`, accept S2, commit or push.

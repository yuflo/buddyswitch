# S5 C5B Daemon Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-DAEMON-R1-20260807-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-11
> Stage effect: C5B accepted; C6 source refresh and READY preparation unblocked

## Accepted outcome

Central and instance Daemon now have one direct owner at
`src/buddyswitch/foundation/daemon/**`. The shared JSONL process-event log has
one owner at `src/buddyswitch/foundation/process_runtime/event_log.py`.
Eleven retired Launcher Daemon modules are absent from source, installed
distribution and wheel without alias, re-export, fallback or parallel path.

Application composition at `src/buddyswitch/application/daemon.py` supplies
the complete module-inbound, Browser-inbound and contributed-handler sequence.
The narrow `src/buddyswitch/application/daemon_host.py` adapter supplies App
Server and Actor Session capabilities. Foundation receives only the completed
host contract, handlers, subscriptions and application-command factories; it
imports no Launcher, application, product module, Browser implementation,
Role or Runtime Broker semantic owner.

Central protocol, registry, reachability, mailbox, triggers, schedules,
handler dispatch, reconciliation, telemetry, failure isolation, parent
activity/input, lifecycle and cleanup behavior remain unchanged. The exact
current handler order is:

```text
track_comment_added
im_message_created
browser_page_expired
browser_cockpit_release
browser_failed_open_page_cleanup
demand_triage
task_goal
demand_orchestration
```

Only `track.comment.added` and `im.message.created` remain App Server
notification subscriptions. Browser registrations are application-composed
Daemon triggers and do not become App Server subscriptions.

## Frozen identity

```text
execution HEAD:                 715bc2dea4dd5da17f66e0e25e97b41bf892762e
tracked patch SHA-256:          9e7da89cd81c1d1e38d5d289abf99973fe7f2b9b7dedfadcefdabad8df76cc6c
index patch SHA-256:            e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
status entries:                 94
non-ignored untracked files:    16
untracked content SHA-256:      834da2587a9fea77a6af44385c4e65b4a6fb7cfa66e2e3ab4ca88ede4b9824f6
git diff --check:               clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-10T03:53:06.809085Z
source_digest:       3d6b5cace4d40afc7058bb72c49188d783248f40114e923399c86c0c35180f2b
distribution_digest: 3fdbec1ebc0169bb198cf3d5f0b03adc0344aff1603a63ddbf10636fc30414c8
wheel SHA-256:       5fa774be4c9f3aa788ac5d296b6420fa6b42ca1cc93c2fb3767158d697865f42
source/install:      334/334 files; zero missing, extra or differing
runtime.verify:      ok=true
```

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| ownership RED | focused `tests/unit/architecture/test_daemon_foundation_owner.py`; `3b6aa175f5364313b0231b7fbbc46165` | expected old-owner failure |
| bounded timeout RED/GREEN | focused process-support regression; `1fd4bca546f141c3aa0d0c0b790f027d` / `8c70159a8843439ba3b7fc3a8f59355c` | unbounded post-kill pipe drain reproduced and bounded |
| package/composition | `7babc416001b4955bdb8c253ba974f62` | 2 passed |
| central cleanup system path | `8e670b3e803142b6a70f4b49283d170d` | 1 passed |
| FIX_AFTER_FINAL exact nodes | `c729d4c4968d4cf0b91a728e420a00c5`, `150aa4c928d34ad8a976809bfab98ea2` | stale proof representations corrected |
| frozen repository acceptance | `./buddyswitch-test full`; `e91948e42eb0498bbc473714cd48e09d` | all tiers and shell/diff gates passed; exit 0 |

The final run passed 510 Unit tests with 1,196 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 258 Process tests with 374 subtests,
and 22 System tests. Its run root and evidence parent were removed after
terminal capture. The coordinating review reproduced the source identities,
inspected the direct-owner and application-host boundaries, found zero retired
imports or reverse dependencies, and reused the identity-valid FINAL without
an unnecessary rerun.

## Contrary signals and disposition

The first frozen FINAL `ea8d35ae1b6944098e48db3b38613827` failed only
two stale test representations of the new C5B topology. The bounded
FIX_AFTER_FINAL repair changed those proof owners, passed their exact targets
and was followed by the one accepted frozen FINAL above.

Interrupted run `f76427972a2d44659525a63998c39a87` exposed an unbounded
post-SIGKILL pipe drain in root test support. The exact regression first failed,
then passed after the drain gained a five-second bound; the same long product
flow later passed in the accepted FINAL. Wrong-node, duplicate-run and
diagnostic-command signals were not counted as product evidence and left no
resource residue. No unexplained failure, timeout, flake, contradictory
terminal result or cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-014 is closed. The C5B R1 packet is consumed and must not
resume.

The only unlocked action is:

```text
commit and push the C5B safe checkpoint
  -> refresh current C6 Actor/App/Web/CLI host source and consumers
    -> authorize C6 implementation only after its own source-bound READY review
```

C6 implementation, C7 and S6 remain unauthorized until their own gates pass.

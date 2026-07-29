# S2 Demand Component Pilot Acceptance

> Decision: `ACCEPTED`
> Parent packet: `BS-MM-S2-20260729-01`
> Final prerequisite packet: `BS-MM-S2-BROWSER-LIFECYCLE-R1-20260729-01`
> Authority: coordinating hub
> Acceptance date: 2026-07-29
> Next stage: S3 preparation only

## 1. Accepted outcome

The S2 acceptance sentence is true:

> Demand domain, state, adapters, assets, exported Skills and local tests live
> under one Demand root; the application selects Demand once; generic hosts
> and other components use typed contributions or Demand Public contracts and
> know no Demand-private detail.

The accepted path is:

```text
application composition
  -> one Demand assembly
    -> typed host contributions or Demand Public
      -> one Demand-private owner/state path
        -> unchanged consumer-observed behavior
```

S2 is a direct Forward cutover. No compatibility package, forwarding import,
fallback registration, old/new Demand state path or second Demand Tool remains.

## 2. Frozen candidate identity

The coordinating hub reproduced the executor return before writing this
acceptance record:

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

git diff --check:
clean
```

The final Browser prerequisite remained exactly the selected two-file change:

```text
src/buddyswitch/launcher/browser_runtime_manager.py:
94df61c368c4772c95279184ad4bd4764ad6d521539706f4a2e7c58b6360ee03

tests/integration/browser/test_runtime_manager.py:
0651a79d8a2dfdddfb627066aba913b9b6ac1f10f0cba2e6ef0f8bc8e7c0f469

owner reap calls:
1
```

Nothing was staged, committed, pushed, rebased or branch-switched during R1.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| Demand create/list/get/complete and inbound behavior is preserved | CLI/Tool/Daemon -> Demand contribution/Public -> Demand owner/state | S2 implementation focused evidence and frozen FINAL | PASS |
| Task/Goal consumers use the exact Demand Public edge | Task/Goal adapter -> Demand Public -> canonical Demand state | affected Integration/System evidence | PASS |
| Actor receives selected Demand Skills and no implementation | Role selection -> module Skill export -> Actor projection | package/Actor architecture and System evidence | PASS |
| cleanup remains safe and attributable | cleanup selection -> typed Demand cleanup contribution -> current state removal/result | cleanup Integration/Process evidence | PASS |
| failure and terminal truth remain coherent | invalid contribution or owner failure -> build/protocol result -> unchanged or terminal state | S2 direct contract and affected-tier evidence | PASS |

There was no current Demand Web route before S2, so a Demand Web contribution
is correctly inapplicable rather than represented by an empty abstraction.

## 4. Architecture proof

The accepted candidate has:

- one physical owner at `src/buddyswitch/modules/demand/**`;
- one application-level selection of the Demand assembly;
- one Demand Public contract for real cross-component callers;
- typed Tool, Daemon, CLI, Skill and cleanup contributions;
- no Demand-private import from generic hosts or another component;
- no product-specific branch added to generic composition infrastructure;
- explicit fail-closed registration instead of hidden Demand discovery;
- Demand-owned tests co-located with the module and included in test
  collection without entering the runtime distribution;
- one canonical Demand state and write path.

The module boundary is concrete and intentionally narrow. S2 does not add a
generic plugin engine, service split, dependency-injection container,
discovery bus or speculative component framework.

## 5. Replacement and residue proof

S2 closes `R-DEMAND-001` completely. The following shared rows remain open
for later components, but their Demand portions are closed:

```text
R-FND-001
R-FND-002
R-FND-003
R-FND-006
R-FND-008
R-FND-011
R-FND-012
R-ROLE-004
R-DOC-002
R-DOC-003
```

The retired live Demand paths are deleted:

```text
src/buddyswitch/env/domain/demand_read.py
src/buddyswitch/env/domain/demand_sys.py
src/buddyswitch/env/repos/demands.py
src/buddyswitch/env/tools/demand_sys/**
src/buddyswitch/launcher/demand_*handler.py
src/buddyswitch/launcher/demand_*runtime.py
src/buddyswitch/launcher/demand_sys_daemon_adapter.py
src/buddyswitch/skills/shared/demand-*/**
tests/unit/demand_sys/**
tests/integration/demand_sys/**
```

Current code, tests and architecture documents point to the new owner.
Historical migration memos and negative absence assertions may still name the
retired paths; they are not live compatibility.

## 6. Final prerequisite findings

`S2-FINAL-F001` is closed. The Browser not-ready test observes the real child
from its parent launch boundary instead of racing a child-authored PID file.

`S2-FINAL-F002` is closed. The app-server early-exit proof now places the real
child and identity under deterministic parent control.

`S2-FINAL-F003` is closed. `_terminate_owned_record` now owns one function-level
reconciliation postcondition:

```text
every terminal return
  -> exactly one tracked-child reconciliation attempt
    -> terminal child absent
    -> live child retained
```

The accepted RED was reused without rerun:

```text
d871368dee4640acb8bd03e9f59aba51
```

After activation-first reprovision, the current repair passed:

```text
exact GREEN:                  090399c8d6e74e888f7df159cd41b1b9
historical branch regression: 3b10c7a1e5fe41108e90f920cd1a0a5b
real lifecycle regression:    17dff892ecf54e7e8e3e3d35ce52f5dd
Browser owner file:           e669bde115ae4c67af2ebfb5674d9ad7
Integration tier:             5571fa5053b048e5b8b006a96e745a66
Process tier:                 ac14e92bf10a46f1817bda50a2e07beb
```

The predecessor packet's GREEN-before-reprovision ordering is rejected and
consumed. R1 proves the corrected invariant:

```text
package-source mutation
  -> rebuild/install/activate/verify
    -> public test runner
```

## 7. Frozen FINAL

```text
command:
./buddyswitch-test full

run:
865b88ce29d34c25aef70c122b41768c

exit:
0

Unit:
430 passed, 1,124 subtests

JavaScript:
147 passed

Integration:
760 passed, 442 subtests

Process:
262 passed, 379 subtests

System:
22 passed

shell syntax:
PASS

diff check:
PASS
```

FINAL ran exactly once against the frozen source and activated distribution.
The hub reused this identity-valid evidence rather than running a second
repository-wide suite.

## 8. Runtime identity and operations

```text
activated_at:
2026-07-29T11:44:27.023663Z

source_digest:
664dc704b9c76293761dd4c36e12f3c38403b73d183a1fceec365e22dcb9963a

distribution_digest:
9c9483635358ce4dd66cd3f9107969c2d11efd637bb575efe31c15d3ba88540b

package_version:
0.1.0

runtime.verify:
ok=true
```

The hub independently confirmed the installed Browser manager matches the
source hash, there are zero current instances, Browser state is inactive, no
test root or attributable process remains and no system-test lock is held.
The 23 historical ownerless mailbox sockets predate S2, are unopened and are
unchanged; they are not attributed to this candidate.

## 9. Acceptance and next boundary

All material Product, Contract, Architecture, Replacement and Operations
proof classes pass. No authorized check was omitted. The only residual risk
is the pre-existing ownerless socket inventory, which is outside S2 and did
not change.

S2 is therefore `ACCEPTED`. Its execution and repair packets are consumed and
must not be resumed. S3 remains unimplemented and receives no execution
authority from this record. The next legal action is:

```text
checkpoint accepted S2
  -> refresh S3 source/consumer/state/test facts
    -> prepare and READY-review a new S3 Goal Packet
```

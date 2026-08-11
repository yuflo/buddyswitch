# S5 C6B Actor Runtime Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-ACTOR-RUNTIME-R1-20260811-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-11
> Stage effect: C6B accepted; remaining C6 source refresh and READY preparation unblocked

## Accepted outcome

Actor capability persistence, Codex runtime descriptors, parent Actor Session,
side-thread start/lifecycle and side-thread registry now have one direct owner
at `src/buddyswitch/foundation/actor_runtime/**`. The package root is inert and
consumers import concrete modules directly.

Application Daemon host, Demand adapters, Host Control, CLI and shell consumers
use that owner mechanically. The six retired Launcher modules and their source,
installed, import, literal, fallback and re-export representations are absent.
Capability, Codex runtime and registry modules are byte-identical to their former
owners; Session, side-thread and lifecycle differ only by direct Foundation
imports and removal of unused source-path shims. Capability records, runtime
validation, input/attach behavior, thread and turn effects, lease transitions,
typed failures, interrupt and cleanup behavior are unchanged.

Actor Runtime depends only on its sibling modules, Foundation App Server,
Foundation Process Runtime and the standard library. Role selection, Actor
workspace construction, Host Control lifecycle, runtime locking, Web routing,
public CLI dispatch and cleanup orchestration were not redesigned.

## Frozen identity

```text
execution HEAD:                 6bc5235d68cc4a6578160d250a89c2f866422028
tracked patch SHA-256:          6548db0170ef4b1b3be2d3842567b1e4a6f58c46632803894c68560c6a425041
index patch SHA-256:            e3b0c44298fc1c149afbf4b8996fb92427ae41e4649b934ca495991b7852b855
status entries:                 42
non-ignored untracked files:    9
untracked manifest SHA-256:     9aff55d3b464677193a9e28c9e34ed746eafd18e93c1839c597bc0bd40754e67
git diff --check:               clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-11T10:48:40.567779Z
source_digest:       4b93731c8c435772b8de3475bd06e1f61f9bf21b2528c0ffd071d64c59cc2779
distribution_digest: 55fce04f0ccf319111611bbe9f3e7dcef795b37ba9697b7cf34c422f654c95df
wheel SHA-256:       cfa98867aad924fc9d929572117b55e944068dda6440ed5c82f5781bccba6e14
source/install:      336/336 files; zero missing, extra or differing
runtime.verify:      ok=true
```

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| direct Actor Runtime behavior | focused capability, Codex runtime, Session, side-thread lifecycle and registry targets; `60bf541659eb496f98ad600ae4a584b4` | 56 passed, 25 subtests |
| affected public consumers | focused Host Control, CLI, Daemon, Demand, Web and runtime targets; `aaefa823fe4b4fe3bf5e618f09a8ce14` | 110 passed, 174 subtests |
| architecture and package | focused architecture `29a31aaf72cd4f638f9b20cf2cfe961e`, final Actor proof `42ca8be796974c24ae2cb118e17317a9`, distribution `99eb72fd56da4698a8fdf91aaf2ae927` | 43 passed/59 subtests; 7 passed; 3 passed |
| real product loop | focused System `c666068cbbfe467c8e1b2ad925ffcda5` | 1 passed; cleanup clean |
| frozen repository acceptance | `./buddyswitch-test full`; `7678be695ad14ba1b3cfdf2780a9670a` | all tiers, shell and diff gates passed; exit 0 |

The FINAL passed 521 Unit tests with 1,196 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 258 Process tests with 374 subtests,
and 22 System tests. All run roots and attributable resources were absent at
terminal capture.

The coordinating review reproduced HEAD, tracked patch and all nine untracked
content identities; confirmed the three byte-identical owners and the three
import-only owner changes; inspected every consumer, package, architecture and
replacement proof; verified runtime identity/status and retired-path absence;
and found no unexplained dependency or cleanup signal. Review changed no
executable state, so identity-valid focused and FINAL evidence was reused.

## Contrary signals and disposition

One stale architecture assertion, one guessed no-collection System target,
test-only old-path constants, and replacement-proof false negatives were fixed
before the accepted FINAL and closed by exact focused evidence. Unsupported
public-CLI verification spelling and read-only shell/audit probe errors did not
mutate or interrupt the candidate. No product failure, timeout, flake,
contradictory terminal result or attributable cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-016 is closed. The C6B R1 packet is consumed and must not
resume.

The only unlocked action is:

```text
commit and push the C6B safe checkpoint
  -> refresh remaining C6 owners and consumers from that exact commit
    -> authorize one next owner cutover only after its own source-bound READY review
```

Remaining C6 implementation, C7 and S6 remain unauthorized until their own
gates pass.

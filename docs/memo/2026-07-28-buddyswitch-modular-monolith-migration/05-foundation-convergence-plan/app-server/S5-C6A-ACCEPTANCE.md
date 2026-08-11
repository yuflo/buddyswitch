# S5 C6A App Server Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-APP-SERVER-R1-20260811-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-11
> Stage effect: C6A accepted; remaining C6 source refresh and READY preparation unblocked

## Accepted outcome

App Server now has one direct owner at
`src/buddyswitch/foundation/app_server/**`. The Python runtime lives in
`runtime.py`, its package root is inert, and the live shell projection is
co-located at `shell/app_server.sh` with direct package-data ownership. The
stable process entrypoint remains
`buddyswitch.application.entrypoints.app_server`.

Every application, module, Actor, CLI/host-shell, test and support consumer now
uses the direct Foundation owner. The retired Launcher Python and shell owners
are absent from source and installed distribution without alias, re-export,
fallback or dual path. The new Python and shell files are byte-identical to
their retired counterparts, so protocol envelopes, typed failures,
thread/turn/Goal/input operations, permissions, environment, timeouts, socket
selection, process identity and cleanup behavior are unchanged.

The Foundation Python owner imports only standard-library modules and direct
Process Runtime primitives. The shell projection invokes the stable
application entrypoint; it does not copy composition rules. Actor, Web, CLI,
cleanup, Role and product owners were not redesigned.

## Frozen identity

```text
execution HEAD:                 c58b3993136ffb776e56ba8c6f81f74e4148857d
tracked patch SHA-256:          63f54a9258ce2796c56d9addf90dc902bc9cb1b1074daa80e74fd8b7ebb2b47e
index patch SHA-256:            e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
status entries:                 30
non-ignored untracked files:    5
untracked manifest SHA-256:     cc56ac5eec9fcbd8d82b49ff6f6c8949e4cd602e04c983313fb7aa0564774b28
git diff --check:               clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-11T08:50:39.546159Z
source_digest:       d7f838a2f2e2ea57936e99cc27ce83d0ddf722a6adbd6a27b7a1065aff5b5211
distribution_digest: 4a42c7328c768e3692d27e30c84ba64a3438c97c713a6f97d206fb25c6756e00
wheel SHA-256:       121bd41998eb53bc1239dfcebf14d81c6d221eecabae147318f98f48f9628ad5
source/install:      335/335 files; zero missing, extra or differing
runtime.verify:      ok=true
```

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| owner and direct consumers | focused App Server, process lifecycle, Actor, Daemon, Demand and Task targets; `622998aa54c742918697d9cd2744f1a2` | 107 passed, 30 subtests |
| host, package and architecture | focused CLI host, instance, distribution and boundary targets; `28c9b73167eb42dba116cc0cf9d72a43` | 84 passed, 107 subtests |
| review finding closure | focused App Server/package architecture targets; `d4d529b1c5ef42ad8be47f0cf89907d3` | 5 passed |
| frozen repository acceptance | `./buddyswitch-test full`; `2136e109979a470485151eb4b0c132e1` | all tiers, shell and diff gates passed; exit 0 |

The FINAL passed 514 Unit tests with 1,196 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 258 Process tests with 374 subtests,
and 22 System tests. All run roots and attributable resources were absent at
terminal capture.

The coordinating review reproduced HEAD, tracked patch and all five untracked
content identities; confirmed old/new owner byte equivalence; scanned current
source, tests, package and architecture guidance for retired imports and paths;
and independently verified the activated runtime identity plus installed
source/shell correspondence. Review changed no executable state, so the
identity-valid focused and FINAL evidence was reused rather than rerun.

## Contrary signals and disposition

Rejected patch/cleanup commands, one wrong local interpreter for a static AST
probe, one unsupported verification argument and one scan false positive were
all rejected or diagnosed before altering the frozen candidate. The two final
review corrections affected only the architecture proof and current
architecture wording; their exact focused proof passed before the accepted
FINAL. No unexplained failure, timeout, flake, no-collection event,
contradictory terminal result or attributable cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-015 is closed. The C6A R1 packet is consumed and must not
resume.

The only unlocked action is:

```text
commit and push the C6A safe checkpoint
  -> refresh the remaining C6 owners and consumers from that exact commit
    -> authorize one next owner cutover only after its own source-bound READY review
```

Remaining C6 implementation, C7 and S6 remain unauthorized until their own
gates pass.

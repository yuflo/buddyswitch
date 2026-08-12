# S5 C6D Host Control Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-HOST-CONTROL-R2-20260812-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-12
> Stage effect: C6D accepted; remaining Web/Cli host source refresh unblocked

## Accepted outcome

The private instance lifecycle and shared runtime lock now have one current
owner path. Product-neutral Host Control lives under
`foundation/host_control/**`, the global lifecycle lock lives under
`foundation/process_runtime/runtime_lock.py`, and application composition
supplies one typed Role projection plus the four exact executable module facts
needed by the preserved lifecycle.

Foundation owns operation validation, locking, lifecycle ordering, command
arguments, result/error interpretation and cleanup. It imports or embeds no
Application, Launcher, product-module, runtime-support or concrete-Role
implementation. CLI and Web receive the same assembled Host Control object.

The retired Launcher Host Control Python owner, runtime-lock owner and three
shell owners are absent from source and the installed distribution. No alias,
fallback, dual invocation, registry, locator, provider family, container or
generalized host framework was introduced.

## Frozen identity

```text
execution HEAD:                 9b1acbe6d9f60dc7a46f63b0a58a89042541dd74
tracked patch SHA-256:          646fcf40d0602773c93004f3e4cc84d4881562903f3b14a58dc0ebd42bbc19d0
index patch SHA-256:            e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked files:                14
untracked manifest SHA-256:     0ac6f050ef5d1246c20ada0e5a0b37011888a534225c394e50a2fca31c3ef9bb
git diff --check:               clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-12T06:52:11.796973Z
source_digest:       e3d9959edee4994c68c0aecf275fc7636e9af747d178541e0c4523d7ec919eda
distribution_digest: b821c30835c14729be6a6fb7bc709be1e11ad7d9c26f4c132d070182bfb91318
wheel SHA-256:       8cb09642737972df3768b0916ec5de3794527f226f708d7dab6950025bbbe42d
runtime.verify:      ok=true
```

The coordinating hub reproduced the tracked patch and untracked manifest,
verified every Foundation Host Control Python/shell representation, confirmed
the critical source/install files are byte-identical, and reproduced the
activated runtime identity. Review changed no executable state, so the
identity-bound execution evidence was reused.

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| escaped reverse dependency RED | focused architecture node; `e5d95b16be154689b5821d428ec2ae3b` | expected assertion failure on the concrete Daemon module path |
| missing executable-input RED | focused private runner node; `477cbde44dc5406798d322f0b52bee6b` | expected missing-input failure |
| exact R2 GREEN | same architecture/runner nodes; `385408942b6c45759513c87dd14d5b2a`, `605d230ab8954f218cd953159e45e939` | 1 passed each |
| direct Host Control boundary | focused architecture/process/error targets; `007e7bdef2234a929de0ee971063b6e3` | 38 passed, 107 subtests |
| Daemon command preservation | affected run plus exact stale-test disposition; `8ffbdbf8fa0945aba07f0987b91dafb4`, `6dc6ea7b21564777b3f40e1cff12bf42` | 35 passed with 2 diagnosed stale assertions; exact 2 passed after correction |
| package/runtime correspondence | focused package/activation; `69918e20a0cf41068e0eae78a4a41d01` | 14 passed |
| Broker/Web affected behavior | focused lifecycle/behavior/API; `74cbad8c56be45f3853b75180d7dcc14` | 33 passed, 5 subtests |
| recursive shell proof repair | exact and complete architecture file; `4b2e2e4e5dd842cfb1c94e0e11e25f0d`, `87d4b9b2f7154df8831592b2a60e7a5e` | 2 passed; 5 passed |
| frozen repository acceptance | `./buddyswitch-test full`; `374bde20002b48cfaa40b6585298d66f` | all tiers, shell and diff gates passed; exit 0 |

The FINAL passed 534 Unit tests with 1,197 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 257 Process tests with 374 subtests
and one skip, and 22 System tests. Parent-known process/socket identities, the
FINAL root and all attributable resources were absent at terminal capture.

## Contrary signals and disposition

The two initial failures were valid R2 REDs. Two later Daemon assertions still
required hard-coded module literals and were corrected to preserve the same
commands and arguments through the injected facts. Review then found that the
shell architecture proof used a non-recursive glob; the proof was repaired to
cover every helper shell before candidate freeze. No product failure, timeout,
flake, no-collection result, contradictory terminal status or cleanup residue
remains.

The reported tuple/list validation minor is pre-existing and unreachable from
the sole application assembly, which supplies a tuple. It is not a C6D
dependency, lifecycle, replacement or consumer defect and does not block this
checkpoint.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-018 is closed. C6D R1 and R2 are consumed and must not resume.

The only unlocked action is:

```text
commit and push the C6D safe checkpoint
  -> refresh current Web/Cli host owners and consumers from that exact commit
    -> choose the smallest coherent remaining C6 cutover after source-bound review
```

C7 and S6 remain unauthorized until their own gates pass.

# S5 C6F CLI Runtime Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-CLI-RUNTIME-R1-20260812-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-12
> Stage effect: C6F accepted; C7 source refresh and READY preparation unblocked

## Accepted outcome

The public CLI host, Codex configuration adapter and cooperating environment,
cleanup and Browser shell adapters now have one direct owner at
`foundation/cli_runtime/**`. Application supplies one frozen required input
containing the concrete executable modules, manifest, Role-profile resolver and
parent Tool projection. Foundation validates and projects those facts without
importing or embedding Application, Launcher, product-module, runtime-support
or concrete Role implementation paths.

The public CLI and Host-start paths assemble the same input. Public command,
help, machine-envelope, exit, Web-launch, config, MCP, Browser, cleanup, lock,
Host-start and resource effects are preserved. Parent-provided Role capability
state is removed unless the current Application explicitly supplies it.

The retired Launcher Python and shell owners and eight zero-production-consumer
helpers are absent. Launcher now contains only an inert package root and the
unchanged S6-owned Role assets. No alias, fallback, registry, locator, provider
family, container, generalized host abstraction or second execution path was
introduced.

## Frozen identity

```text
execution HEAD/upstream:         48891d32454003da3d8e0f076386a28e9c3d6c51
tracked patch SHA-256:           4676cf6de417e975eb1a4958411e80c1372753170ecc18fa1a494fc6c788b0b8
index patch SHA-256:             e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked files:                 8
returned manifest SHA-256:       f26ab75f4cca5313ce07a3a1b33e4f6422781da472ae3bcc1ab53a535355f3bc
git diff --check:                clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-12T11:41:10.065697Z
source_digest:       f94b873f95fb8b119fa7455b7772b0107fa6b3ecebf88c71cd392787ea5f8da3
distribution_digest: 1ee40273808d4aa5b6d3dc2b88d8fe0d2fd0183c458d5bea5d985ba7b4658335
wheel SHA-256:       fa0cc55ad7ded5c7edbead6dae6019b3c724268e1ca7d21cd282eef896802852
runtime.verify:      ok=true
```

The coordinating hub reproduced HEAD/upstream, the exact tracked patch, empty
index and the eight untracked paths; reviewed the required Application input,
public CLI/Host-start consumers, shell projections, package declaration,
retired-owner deletion and bounded architecture guard; and independently
verified Python syntax, Bash syntax, recursive forbidden executable roots,
Launcher final contents and source/installed byte correspondence. Review made
no executable change, so the source-bound focused, System and FINAL evidence
remains valid.

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| stale Role fact regression | `c2a5e68a64e0424eb032fce0bf22e405` | 1 passed |
| direct Unit/Architecture/Web | `ea94da2659854668ae893419a24fbcae` | 113 passed, 127 subtests |
| affected public CLI/config/Browser/env/Host-start/Integration | `11111bd23b91470aa2e28dd1de90996c` | 107 passed, 151 subtests |
| package/activation | `7a0ddfbc84704861b354503ff884091f` | 9 passed |
| real reset/lock/Browser/instance/Web loops | `d90a7ca7bcbc4c4691bc90f6d0fd2e9d` | 7 passed; parent-known process and run root absent |
| frozen repository acceptance | `./buddyswitch-test full`; `f9dea78e158e473db2a89081e60cb595` | all tiers, shell and diff gates passed; exit 0 |
| hub read-only correspondence review | exact patch/runtime/owner/install/residue probes | all assertions passed; no attributable residue |

The FINAL passed 553 Unit tests with 1,197 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 258 Process tests with 374 subtests,
and 22 System tests. The FINAL root, parent process group and attributable
runtime resources were absent at terminal capture.

## Contrary signals and disposition

The initial architecture run found one stale current-doc path and was repaired
before candidate freeze. Review then found a stale Role-capability value could
leak from the parent environment; the executor added an exact RED, repaired the
owner, reprovisioned and passed the exact GREEN and all affected evidence.
Shell-mode, shell-parser, cleanup-command and production-consistent activation
probe corrections were diagnosed and left no unexplained source or runtime
state. None was a product failure, timeout or flake on the frozen candidate.

No contradictory terminal result, unexplained scope drift or cleanup residue
remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-020 is closed. The C6F R1 packet is consumed and must not
resume.

The only unlocked action is C7 source refresh and READY preparation against the
committed C6F checkpoint. C7 must replace final current guidance, prove every
S5-owned residue absent and freeze one S5 acceptance candidate. S6 remains
unauthorized until C7 accepts the complete S5 claim.

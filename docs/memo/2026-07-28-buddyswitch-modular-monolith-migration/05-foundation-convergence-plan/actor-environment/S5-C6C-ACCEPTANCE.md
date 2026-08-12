# S5 C6C Actor Environment Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-ACTOR-ENVIRONMENT-R1-20260811-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-12
> Stage effect: C6C accepted; remaining C6 source refresh and READY preparation unblocked

## Accepted outcome

Product-neutral Actor workspace publication now has one direct owner at
`src/buddyswitch/foundation/actor_runtime/environment.py`. The current
application resolves the selected Role, Role guidance, Skill sources and base
Codex configuration exactly once into `ResolvedActorBootstrap`; Foundation
validates and materializes only that resolved input.

The stable `buddyswitch.application.entrypoints.actor_build` process boundary
and Host Control shell invocation remain current. Runtime-identity validation,
Git-free shared-project seed-once behavior, config/auth/AGENTS/Skill/project
projections, path and symlink rejection, atomic no-overwrite publication,
typed result/error behavior and failed-stage cleanup are preserved.

`runtime_support/runtime_skills.py` now resolves Skill sources only and no
longer owns workspace writes. The retired
`launcher/actor_environment.py` owner, import path and installed projection are
absent. No alias, fallback, dual builder, discovery layer, provider registry,
container or early RoleHost implementation was introduced.

Foundation Actor Runtime imports only standard-library modules and the direct
Process Runtime owner for this capability. Current central Role/Skill selection
remains application-side as the one explicit S6 input. Host Control lifecycle,
runtime locks, Codex config patching, Web, CLI and Role assets were not
redesigned.

## Frozen identity

```text
execution HEAD:                 d5e19609e6c34f1804e3a38bbb4cc3758e579fe2
tracked patch SHA-256:          3d651bce13307efb1967d0f4cde5e76e532a8e41ab87619bcb1e8f09eac2f401
index patch SHA-256:            e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
status SHA-256:                 74118bdb25452846ad1adcc0e76a507d887753e4ca7db1e450071f89c22fe7ca
untracked manifest SHA-256:     49e6e6101c6616dc2ab5627da3594b0ecb6c608cfe05f5a1a0a8580f2f50e3a6
git diff --check:               clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-12T03:17:24.134764Z
source_digest:       0f24fd6ce3ccb995d84213ca5b678a547963b706701c3152d04f88c628007e54
distribution_digest: b5deaa423e359f5358ba771ae3f94abb11e4bed8b59ad519fe693fc296430a0b
wheel SHA-256:       5defdfeb47d5c6f74b7a3b821b1d65b02a50310b9ab8ff921e7415992a168e7f
source/install:      336/336 files; zero missing, extra or differing
runtime.verify:      ok=true
```

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| direct owner and bootstrap behavior | focused direct plus strengthened owner target; `99723c3c3a3e49b5ac103840d60af477`, `3902d35aa42645d1b5b9c8cf57a7fec9` | 13 passed/5 subtests; 8 passed/5 subtests |
| affected consumers and architecture | focused Actor/architecture/Host targets; `838a1b2dc6ac43909084b6710e37141c` | 68 passed, 307 subtests |
| installed package replacement | distribution install; `c6e121186e8f41acaf0ee358538d4824` | 3 passed |
| real consumer loop | focused System; `efa982a0d1854898af51244396a6b4e5` | 1 passed; cleanup clean |
| frozen repository acceptance | `./buddyswitch-test full`; `c9211e36639740738eca7fe0cbda96ca` | all tiers, shell and diff gates passed; exit 0 |

The FINAL passed 527 Unit tests with 1,197 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 258 Process tests with 374 subtests,
and 22 System tests. The FINAL root and attributable resources were absent at
terminal capture.

The coordinating hub reproduced HEAD, tracked patch, index, status and all
three untracked content identities; reviewed the owner, application input,
runtime Skill, package, test and current-architecture changes; verified the
installed runtime against the same source/distribution digests; and found no
unresolved dependency, replacement or cleanup signal. Review changed no
executable state, so the source-bound focused and FINAL evidence was reused.

## Contrary signals and disposition

An earlier direct run lost its terminal result and was replaced before freeze
by the exact unchanged direct run. An intentionally added assertion incorrectly
classified live `configure_skill_exports` composition input as dead; repository
tracing disproved it and the test-only probe was reverted before the accepted
candidate froze. The initial manual correspondence probe included co-located
tests; the package-aware probe then proved exact 336/336 correspondence.

During hub review, the known unsupported spelling
`./buddyswitch-codex runtime verify` returned `UNKNOWN_COMMAND` without state
mutation. The hub immediately used the current
`buddyswitch.application.entrypoints.runtime_activation verify/status`
boundary, which returned `ok=true` and reproduced the frozen runtime identity.
No product failure, timeout, flake, no-collection result, contradictory
terminal status or attributable cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-017 is closed. The C6C R1 packet is consumed and must not
resume.

The only unlocked action is:

```text
commit and push the C6C safe checkpoint
  -> refresh remaining C6 owners and consumers from that exact commit
    -> authorize one next owner cutover only after its own source-bound READY review
```

Remaining C6 implementation, C7 and S6 remain unauthorized until their own
gates pass.

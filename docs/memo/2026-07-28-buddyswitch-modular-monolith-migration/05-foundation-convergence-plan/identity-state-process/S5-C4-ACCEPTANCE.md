# S5 C4 Foundation Primitives Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-FOUNDATION-PRIMITIVES-R1-20260806-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-07
> Stage effect: C4 accepted; C5 source refresh and READY preparation unblocked

## Accepted outcome

Identity payload/profile persistence, canonical runtime state and
Actor-private deletion safety, and exact process-start ownership now have
direct Foundation owners:

- `foundation/identity/**` owns identity models and profile persistence;
- `foundation/state/**` owns canonical locators, write guards, atomic JSON and
  the live Actor-private deletion boundary;
- `foundation/process_runtime/process_identity.py` owns exact PID/start
  identity records beside the already-final activation and invocation owners.

Every current product, Foundation, runtime-support, Runtime-Kernel and Launcher
consumer imports the direct owner. `src/buddyswitch/env/**` and
`runtime_kernel/process_identity.py` are physically absent. No alias,
package-root re-export, fallback, copied dead helper or replacement service
facade remains.

The cutover preserves identity payloads, profile paths, state roots and write
authority, Actor-private effect-time containment, process sidecars, stale-PID
refusal, lifecycle cleanup, runtime activation and installed-distribution
correspondence. C5 Broker/Daemon ownership and C6 host ownership did not move.

## Frozen identity

```text
execution HEAD:                 2e7151722e29fc4d79f7bcf8069a5daa54ee0fe0
tracked patch SHA-256:          6ff8fcd6653ff75662bd704c18e2f338332cde21602f9e991b1580f2e76fbd2c
index patch SHA-256:            e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
tracked changes:                130 files; 560 insertions; 1,585 deletions
non-ignored untracked files:    11
git diff --check:               clean
Python AST:                     479 files parsed
```

Installed runtime identity:

```text
activated_at:        2026-08-07T03:33:59.084334Z
source_digest:       ad12cb31082f05b17062421ef427f416688fe03d6e9a9fc86fa347109614535f
distribution_digest: e7b80ee5b9773393914bacf71b8dea86d42bc08ad5d3238ccf13ac1e96d2b75e
wheel SHA-256:       a197ed3fdb728ea7a00a8d375e33042ccbab5061b97b41e0152f2a51bf2290fa
package:             buddyswitch 0.1.0
runtime.verify:      ok=true
```

The hub reproduced the tracked patch and every new-file content identity,
inspected the owner/consumer/replacement boundaries and reran only the
non-mutating installed-runtime verify/status checks. Review changed no
executable or test state, so the executor's source-equivalent evidence remains
valid without a duplicate FINAL.

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| Foundation architecture and replacement | focused architecture runs ending at `9dcc3924fd344a27ae25d83b40ae6f04` | 6 passed |
| architecture/state affected group | `d201c36743234e518465a8398aeb01b3` | 42 passed, 10 subtests |
| identity/state/cleanup integration | `5e3f05baeebb42ae929cf7b6259a0ca9` | 24 passed |
| process lifecycle | `0415b2114caf4dc29b56a78513bb461a` | 6 passed |
| environment/replacement boundary | `98ca3f7e2c564c48af636c75af02f7e4` | 3 passed |
| package/runtime correspondence | `b498c7abd22549c29017622b15ed172f` | 3 passed |
| frozen repository acceptance | `./buddyswitch-test full`; `e306abb4f43d42ce8b9517f08e3a5450` | 499 Unit + 1,189 subtests; 147 JavaScript; 771 Integration + 458 subtests; 257 Process + 374 subtests; 22 System; shell syntax and diff check; exit 0 |

The FINAL parent owned the real session handle through numerical exit. Its run
root and all attributable instance, process, socket, lock and PID state were
absent afterward.

## Contrary evidence and disposition

- Preparatory missing-owner failures and the later `env_legacy_store` RED were
  valid construction/replacement signals and were closed by the final owner
  cutover.
- One guessed node ID collected no tests. The executor rediscovered the current
  target without changing source and did not treat no-collection as evidence.
- The first local wheel was contaminated by ignored stale `build/lib` and
  egg-info content and correctly failed activation with `RUNTIME_MISMATCH`.
  Those generated inputs were removed recoverably, the runtime was built from
  clean input, and package correspondence plus FINAL then passed. Later
  checkpoints must continue using isolated clean build inputs; this is a
  delivery input rule, not an unresolved C4 product defect.
- Shell-variable shadowing produced read-only diagnostics only; the corrected
  audit reproduced the unchanged candidate.

No unexplained failure, timeout, flake, contradictory terminal result or
cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. C4 is `ACCEPTED`; its R1 authority is consumed and must not resume.

The only unlocked action is:

```text
commit and push the C4 safe checkpoint
  -> refresh current C5 Runtime Broker and Daemon source/consumers/contracts
    -> authorize C5 implementation only after its own source-bound READY review
```

C5 implementation, C6–C7 and S6 remain unauthorized until their own gates
pass.

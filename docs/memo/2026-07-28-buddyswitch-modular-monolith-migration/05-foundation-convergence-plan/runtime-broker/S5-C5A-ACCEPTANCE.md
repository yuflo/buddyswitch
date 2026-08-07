# S5 C5A Runtime Broker Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-RUNTIME-BROKER-R1-20260807-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-07
> Stage effect: C5A accepted; C5B source refresh and READY preparation unblocked

## Accepted outcome

The launcher-managed Runtime Broker now has one earned direct owner at
`src/buddyswitch/foundation/runtime_broker/**`. Protocol v2, coordination,
dispatch, client/server and lifecycle remain one local service boundary. The
Broker-private advisory lock moved with its only production consumer.

The already-shared Content-Length JSON-object framing algorithm now has one
product-neutral owner at
`src/buddyswitch/foundation/process_runtime/json_framing.py`. Broker and
Daemon transports import it directly; Daemon does not depend on Broker
protocol or lifecycle. The hub's review found and removed Broker-specific
wording from the shared primitive's own diagnostics before acceptance.

Every live application, Tool, Browser, Evidence, Daemon transport, test,
package and current-guidance representation now names the direct owner.
`src/buddyswitch/runtime_kernel/**` and the installed
`buddyswitch.runtime_kernel` package are absent without alias, re-export,
fallback or parallel path.

Protocol envelopes, request identity, deadlines, Tool/Browser dispatch,
Actor/Role/active-instance validation, read/write locking, retry eligibility,
Unix-socket capacity, process identity, start/stop/status behavior and cleanup
remain unchanged. Zero-production-consumer helpers and the test-only
single-argument server fallback did not migrate.

## Frozen identity

```text
execution HEAD:                 f3fd6ab594c04b81bb866b6674be9a8127a6e61f
tracked patch SHA-256:          6eabfe2bc7b356fa8837e2492e234e747453f7e7f481fbd91563f4dacc8b5310
index patch SHA-256:            e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
tracked changes:                61 files; 316 insertions; 2,609 deletions
non-ignored untracked files:    11
git diff --check:               clean
Python AST:                     481 files parsed
```

Installed runtime identity after the hub's review repair:

```text
activated_at:        2026-08-07T09:28:53.511972Z
source_digest:       5d76ea13017b006b1b759a362270084b106cf458395deef1147e12b853a915ad
distribution_digest: 2f120c8a7a3de5fb9b7d87bce9188ccf14ac3fbfcb63c433385b0a20091f6736
wheel SHA-256:       7def3113d7e26b6e5ef99dd9ebe23724278bc009c5c13585223eb49523c4e758
package:             buddyswitch 0.1.0
runtime.verify:      ok=true
```

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| executor exact/affected candidate | focused runs ending at `d063591387524973807d1d3b504e50e9` | Broker, Daemon, package and consumer boundaries passed |
| executor frozen repository acceptance | `./buddyswitch-test full`; `1ddb747f61064f7780756a8cf17530a7` | all tiers passed; exit 0 |
| hub review RED | `db81260ae20f419292bced6c350ca1ee` | shared framing still contained Broker terminology; 1 expected failure |
| hub FIX_AFTER_FINAL exact/affected | `a0f40b5181e44add9ed210717b8d584e` | 98 passed, 23 subtests |
| final repository acceptance | `./buddyswitch-test full`; `0edb068adf19462a863ce3445e8aab0c` | 506 Unit + 1,196 subtests; 147 JavaScript; 771 Integration + 458 subtests; 257 Process + 374 subtests; 22 System; shell syntax and diff check; exit 0 |

The final run root, every public-run root, instance, attributable process,
socket, PID, runtime lock, wheel temporary root and repository build artifact
were absent afterward. Installed source/distribution correspondence remained
`ok=true` on the frozen candidate.

## Review finding and disposition

The executor's candidate was structurally and behaviorally complete, but the
new shared process-runtime primitive had mechanically retained error messages
such as “broker header” and “broker body”. That wording would have leaked
Broker semantics through current Daemon protocol errors and contradicted the
product-neutral owner claim.

The hub added one small owner-bound invariant, observed the exact RED, changed
only the primitive diagnostics plus the Broker client's matching classifier
and direct expectation, rebuilt and activated the installed runtime, passed
the exact/affected boundary and ran one new frozen FINAL. No C5B Daemon
semantics, handler order, trigger, mailbox, state or lifecycle changed.

Earlier no-collection, setup, socket-readiness and review findings in the
executor packet all have source-bound dispositions. No unexplained failure,
timeout, flake, contradictory terminal result or cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. C5A is `ACCEPTED`; its R1 authority is consumed and must not
resume.

The only unlocked action is:

```text
commit and push the C5A safe checkpoint
  -> refresh current C5B Daemon source/consumers/contracts
    -> authorize C5B implementation only after its own source-bound READY review
```

C5B implementation, C6–C7 and S6 remain unauthorized until their own gates
pass.

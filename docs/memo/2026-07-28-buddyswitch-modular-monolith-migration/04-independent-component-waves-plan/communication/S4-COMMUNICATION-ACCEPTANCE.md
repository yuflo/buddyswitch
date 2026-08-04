# S4 Communication Capability Lane Acceptance

> Decision: `ACCEPTED`
> Product packet: `BS-MM-S4-COMMUNICATION-R1-20260803-01`
> Cleanup repair: `BS-MM-S4-COMMUNICATION-R2-20260803-01`
> Execution-boundary repair: `BS-MM-S4-COMMUNICATION-R3-20260803-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-04
> Next boundary: Context source refresh and READY preparation only

## 1. Accepted outcome

The Communication acceptance sentence is true:

> Message state, Message Tool, actor delivery, IM inbound, external sessions,
> `/api/im/*`, Web identity, iMessage channel and their owning tests have one
> physical Communication root and one explicit application assembly. Generic
> hosts consume passive typed contributions and contain no Communication
> implementation, while cleanup discovery and execution produce safe,
> effect-accurate results.

The accepted product path is:

```text
application composition
  -> Communication ModuleAssembly
    -> Communication Private owner
    -> Communication Public operations
    -> Tool / inbound / Web route / optional worker / cleanup contributions

generic Tool, Daemon, Web and cleanup hosts
  -> typed registration or Public operation
  -> no Communication Private import or product branch
```

Demand consumes four narrow Communication Public operations and Communication
consumes one application-injected Demand enqueue callable. The graph remains
acyclic and no service locator, plugin discovery, component lifecycle
framework, compatibility path or duplicate Message owner exists.

## 2. Frozen candidate identity

Before writing this non-executable acceptance record, the coordinating hub
reproduced the executor's frozen non-memo candidate identity:

```text
worktree:
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch:
  fea-tool
HEAD and origin/fea-tool:
  b0e343c4e4b546a2a06cd3ff6e57dd4d06c052d5
HEAD tree:
  e5ce2557f2e702e2e4d0b2cc971d3de68db35dd0
non-memo tracked binary patch SHA-256:
  4ae3115e033ede7f955353f9baa246c4b76c13dfc39f5a2daa6dd64ca46978ba
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-memo untracked files:
  46
non-memo untracked sorted-NUL path-set SHA-256:
  6aaaf167a7e8d1ded6ff31e20d139cc7887ddf00b5ca1531b8395d221b608fdb
non-memo untracked sorted line-manifest SHA-256:
  811af50e28be58dfa05b2dc297acbeea83b7413bbfae88f43c91878bed77982f
git diff --check:
  clean
```

The R3 result packet, frozen FINAL, installed runtime and hub review refer to
this same executable/test identity. This acceptance record and its migration
truth projections do not mutate that candidate.

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| Message create/read/list/delivery behavior remains exact | Actor Tool -> generic registry -> Communication owner | R1 direct/affected proof; R3 FINAL | PASS |
| Inbound and external reply paths preserve identity, routing and terminal result | external event -> contributed inbound source -> Communication owner -> consumer | R1 direct/affected/process proof; R3 FINAL | PASS |
| `/api/im/*` and iMessage worker preserve current Web behavior and lifecycle | application-contributed route/worker -> generic WebHost | R1 Web/process proof; R3 FINAL | PASS |
| Demand collaboration uses only the frozen Public/input-port edge | Demand Private -> Communication Public; Communication -> injected Demand callable | architecture and affected proof; R3 FINAL | PASS |
| Role and all-data cleanup remove all owned Message and actor-private entries | component discovery -> generic cleanup planner/executor -> state effects | R2 exact/affected proof; R3 exact/affected proof | PASS |
| Cleanup reports only attributable effects | execution-time root/path authority -> deletion -> filtered paths/count/object IDs | R3 RED/GREEN and FINAL | PASS |

Successful mutations persist exactly once and report success through the
existing envelope. Invalid authority, transport, schema, stale path or unsafe
boundary produces the existing rejection/failure or an execution warning with
no undeclared destructive effect.

## 4. Architecture proof

The accepted candidate has:

- one physical owner at `src/buddyswitch/modules/communication/**`;
- one `COMMUNICATION` assembly selected once by application composition;
- one Tool contribution, inbound-source contribution, Web route contribution,
  optional Web worker contribution and cleanup contribution;
- four narrow Public operations consumed by Demand and Context-facing reads;
- one Demand enqueue input callable injected by application composition;
- no Communication implementation in shared Tool, Daemon, Web or cleanup hosts;
- generic WebHost lifecycle ownership: prepare routes, start contributed
  workers fail-soft, stop started workers before server close;
- generic cleanup execution ownership: validate roots and paths at effect time,
  delegate regular actor-private files to their repository owner, unlink leaf
  links safely and project only real deletion effects;
- root-owned cross-component/process/architecture proof and module-local
  Communication tests under the Communication root;
- one public test runner and one installed attributable runtime.

The accepted residual safety boundary is deliberate: cleanup is coordinated by
the runtime lock and active-instance gate with immediate execution-time
revalidation. It does not claim hostile-concurrency `openat`/directory-fd
atomic filesystem security.

## 5. Replacement and residue proof

`R-COMM-001` and `R-FND-005` are closed completely. Communication portions of
`R-FND-001`–`R-FND-004`, `R-FND-008`, `R-FND-009`, `R-FND-011`, `R-FND-012`,
`R-DOC-002` and `R-DOC-003` are closed.

Retired live implementation roots are absent, including:

```text
src/buddyswitch/env/repos/messages.py
src/buddyswitch/env/services/messages.py
src/buddyswitch/env/tool_runtime/im_actor_delivery.py
src/buddyswitch/env/tool_runtime/im_client.py
src/buddyswitch/env/tools/message/**
src/buddyswitch/launcher/external_im_session.py
src/buddyswitch/launcher/im_http_router.py
src/buddyswitch/launcher/im_wake_handler.py
src/buddyswitch/launcher/imessage_channel.py
src/buddyswitch/launcher/message_inbound.py
src/buddyswitch/launcher/web_im_identity.py
```

Retired Communication implementation tests are replaced by module-local and
root consumer tests. Historical memos and scoped negative guards may name old
paths only as history or absence proof.

## 6. Verification evidence

R3 exact defect RED:

```text
run:
  ed64341113c648798dc5e5d12a0a3c1e
result:
  7 failed, each attributable to the stale R2 execution boundary
cleanup:
  run root and attributable resources absent
```

R3 exact final GREEN:

```text
run:
  935615ad05c443fb9c730fc18430fca3
result:
  7 passed; exit 0
cleanup:
  run root and attributable resources absent
```

R3 cleanup/architecture affected GREEN:

```text
run:
  97e2ed6734e34e39b967e1ab7369a0db
result:
  32 passed, 4 subtests; exit 0
cleanup:
  run root absent
```

R3 CLI/package affected GREEN:

```text
run:
  9adbb959051643edb648678801b56d57
result:
  13 passed, 7 subtests; exit 0
cleanup:
  run root and attributable processes absent
```

Frozen replacement FINAL:

```text
command:
  ./buddyswitch-test full
run:
  ffefbc012a5d45fa887cd10c9520229c
result:
  Unit Python 473 passed, 1,118 subtests
  Unit JavaScript 147 passed
  Integration 769 passed, 442 subtests
  Process 264 passed, 375 subtests
  System 22 passed
  shell syntax PASS
  git diff --check PASS
  Python total 1,528 passed, 1,935 subtests
  exit 0
cleanup:
  run root, attributable processes and build residue absent
```

FINAL ran once on the frozen R3 candidate. No executable, test, fixture,
package or runtime mutation occurred afterward. The hub reproduced the frozen
identity and reused the source-equivalent evidence instead of rerunning the
repository-wide suite.

## 7. Contrary evidence disposition

| Signal | Owning diagnosis | Disposition | Resolved |
|---|---|---|---|
| R1 FINAL passed but recursive/non-JSON Message residue remained | cleanup discovery proved JSON-shaped records instead of the entire owned tree | R1 consumed; R2 made Communication Private own recursive, extension-independent discovery | YES |
| R2 FINAL passed but stale parent state could escape during execution | packet proved planner rejection, not executor-owned effect-time authority | R2 consumed; audit recorded coordinating-side proof failure and R3 moved safety/result truth to the executor | YES |
| R3 initial GREEN became stale | fresh-state process proof exposed missing state-root initialization | implementation narrowed initialization to the exact validated empty shared-state case; runtime reprovisioned and exact/affected proof repeated | YES |
| Pre-FINAL process run had one failure | fresh HOME legitimately had no initial `state/` directory | owner-correct in-scope repair plus finding-specific confirmation passed before freeze | YES |
| Twenty-three old mailbox sockets remain | pre-existing, ownerless, zero open handles and unchanged by Communication | excluded from attribution; no active resource or accepted-lane effect | YES |

There is no unresolved FINAL failure, timeout, flake, undeclared dependency,
hidden environment mutation or attributable cleanup residue.

## 8. Runtime and operations

```text
activated_at:
  2026-08-03T10:01:35.026309Z
source_digest:
  abfc94c8fb824a0be42884687423316f92f2e8311037f4eeb11a8e57c163ae0c
distribution_digest:
  754c20fb6d2d0b9b6b445807765422db0415727d918363ca32710d9721372499
package:
  buddyswitch 0.1.0
runtime.verify:
  ok=true
installed env_cleanup.py:
  byte-identical to source
```

Final review found no `bs-test-*` or `bs-review-*` roots, live attributable
BuddySwitch/test process, instance, Browser-ready state, build/egg-info/cache
residue or open mailbox handle.

## 9. Current documents

Executable truth is reflected in:

```text
docs/arch/communication-capability-architecture.md
docs/arch/web-interface-call-architecture.md
```

No current guidance teaches the retired Communication roots or a
component-specific Web/cleanup branch.

## 10. Omitted checks and residual risk

The hub did not rerun focused or full tests after read-only review because the
complete executable/untracked/runtime identities matched the returned R3
evidence. Non-executable acceptance and ledger projections do not invalidate
that evidence.

Residual risk is limited to the explicitly accepted non-hostile filesystem
coordination boundary described in section 4. S5 owns final Foundation-wide
host neutrality; this does not defer any Communication semantic owner work.

## 11. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof all pass,
and every contrary signal has an owning resolved disposition.

Communication is therefore `ACCEPTED`. R1, R2 and R3 are consumed permanently
and must not resume. This record authorizes only:

```text
checkpoint accepted Communication
  -> refresh Context source, consumers and projection ownership
    -> design and preflight the smallest complete Context boundary
      -> issue a new packet only after READY review
```

It does not authorize Context implementation, S5, S6 or S7.

# S5 C1 ToolHost Acceptance

> Decision: `ACCEPTED`
> Product packet: `BS-MM-S5-TOOLHOST-R2-20260804-01`
> Consumed predecessor: `BS-MM-S5-TOOLHOST-R1-20260804-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-04
> Stage effect: C1 accepted; C2 source refresh and READY preparation unblocked

## 1. Accepted outcome

The C1 acceptance sentence is true:

> Every current env Tool is selected exactly once by explicit application
> composition; Foundation ToolHost owns only generic contracts, catalog,
> dispatch, authorization invocation, feedback and earned host facts; Role
> policy is injected; retired discovery, old Tool roots, broad context bags and
> zero-consumer facades are absent.

The accepted consumer path is:

```text
Native MCP / admin env client / Runtime Broker
  -> application-selected Foundation ToolHost
    -> injected Role authorizer and active-Task probe
      -> one explicitly registered component Tool adapter
        -> canonical ToolResult and observable state effect or exact failure
```

C1 does not accept S5 as a whole and does not authorize C2 implementation.

## 2. Frozen candidate identity

Before this non-executable acceptance record was written, the hub reproduced
the executor's final candidate:

```text
worktree: /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
branch: fea-tool
HEAD: 8a6369222c702aea6ec430a41524cdad4a9aaf15
executable tracked patch SHA-256:
  23e7aab5e7e0c284df51bb580f2df05abca6c9fab4841bf62385e363bacc8e07
index patch SHA-256:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked source path-set SHA-256:
  26c5f086109dfa7fcc7543a36a03a3b635ce943c6c67c43a3af71560ea76bf36
untracked source path/content manifest SHA-256:
  3b5d61bcce2b8c0dbf5da38a18debd0caaa55382b227c2fff36109639860b5f0
git diff --check: clean
```

The executable patch excludes coordinating-owned `docs/memo/**` and
`AGENTS.md`; the complete dirty worktree was nevertheless present for every
public test command and remained partitioned.

Installed runtime identity reproduced by the hub:

```text
activated_at: 2026-08-04T09:56:44.746545Z
source_digest: 8a0bbe8f7607cad0e574b6ce17a0aac4a68cab13d907b21eeb11999f15682a64
distribution_digest: 4f68eb5a09accb22003d5089ec33947f6419a2ade1181d830c20e286d918812a
package: buddyswitch 0.1.0
runtime.verify: ok=true
```

## 3. Product and contract proof

| Material claim | Consumer path | Evidence | Result |
|---|---|---|---|
| eight current Tool IDs/actions remain exact | application composition -> ToolHost catalog -> Native MCP/Context projections | architecture GREEN `c3c2a6c43d044197ad09ee1a00bcdd9d`; FINAL | PASS |
| read, mutation, authorization and active-Task terminal semantics remain exact | Broker/CLI/MCP -> dispatch -> component adapter -> ToolResult/state | affected runs `b5033c61de0e415db1ae2060e16fd217`, `eabb70a77a8b4fb1b9b34b011d79a090`, `f4be3d4e2a4d4e2889e14834d3bfe91b`; FINAL | PASS |
| ToolContext retains only currently consumed facts and capabilities | ToolHost -> component Tool adapters | RED `5f73c79ce361482ca7b86a6beca1d078`; GREEN `c3c2a6c43d044197ad09ee1a00bcdd9d`; independent review `02c1baac1623489cbca363860b3650a2` | PASS |
| Role policy remains behaviorally exact while Foundation imports no Role implementation | application injection -> generic authorization contract -> rejection/allow result | Role RED `2ab995bd9057488a9b732dbdcb87db19`; GREEN `19599a531e504ddb87e241bbe7cf8151`; FINAL | PASS |
| Search default manifest resolution stays with the current profile owner | Search adapter -> `env_profiles` -> exact runtime profile | first FINAL signal plus exact GREEN `fe6e7364374342d1b0ed16c3b9f87349`; affected `460a18870bee46e8b14f67b1e602f1f1`; replacement FINAL | PASS |

No Tool action schema, canonical state path, current Role decision or product
mutation meaning changed.

## 4. Architecture and replacement proof

The accepted candidate has:

- application composition as the one Tool registration, Role authorizer and
  active-Task-probe owner;
- exactly eight unique Tool registrations with no package discovery;
- one Foundation ToolHost at
  `src/buddyswitch/foundation/tool_runtime/**`;
- one generic Daemon transport client at
  `src/buddyswitch/foundation/daemon/client.py`;
- Role policy outside Foundation at
  `src/buddyswitch/runtime_support/role_auth.py`;
- no Foundation import of a component or Role policy implementation;
- a ToolContext limited to earned identity, instance, manifest, invocation,
  Actor-directory, signal-delivery, Actor-private-root and clock facts;
- no `active_actor`, attribute-form `active_role`, `new_id()`, broad repo/domain
  bag, discovery error facade or ToolHost Broker re-export;
- no retired `src/buddyswitch/env/tool_runtime/**`,
  `src/buddyswitch/env/tools/**`, `src/buddyswitch/env/client.py` or
  `src/buddyswitch/launcher/env_tool_mcp_server.py` path.

`R-FND-002`, `R-FND-003` and `R-FND-010` are closed. The C1 portions of
`R-FND-001` and `R-FND-012` are closed; their remaining host-root work stays
owned by later S5 checkpoints.

## 5. Verification evidence

```text
architecture/public-surface GREEN:
  run: c3c2a6c43d044197ad09ee1a00bcdd9d
  result: 3 passed, 35 subtests

complete affected architecture:
  run: 5d0d14bc50c1403ea2c9c4b9fde061e6
  result: 68 passed, 596 subtests

complete affected integration:
  run: b5033c61de0e415db1ae2060e16fd217
  result: 54 passed, 170 subtests

complete affected CLI/MCP process boundary:
  run: eabb70a77a8b4fb1b9b34b011d79a090
  result: 21 passed, 127 subtests

replacement frozen FINAL:
  command: ./buddyswitch-test full
  run: 7841f5d5614141728a2db56a4612d8f4
  result:
    Unit Python 477 passed, 1,144 subtests
    Unit JavaScript 147 passed
    Integration 770 passed, 458 subtests
    Process 260 passed, 374 subtests
    System 22 passed
    shell syntax PASS
    runner diff-check PASS
    exit 0
  cleanup: run root and attributable resources absent
```

The hub performed a read-only review, reproduced source and runtime identity,
and reused the identity-valid executor evidence. It did not rerun FINAL merely
because the reviewer changed.

## 6. Contrary evidence and operations

Initial FINAL `68a461234385448687309022a30b1ff4` failed one Search boundary
assertion because Search imported the retired ToolContext default-manifest
facade. The executor diagnosed that exact owner error, repaired production
source, reprovisioned and activated a new candidate, passed exact and affected
proof, then ran one replacement FINAL. This is a resolved `FIX_AFTER_FINAL`,
not an unexplained rerun.

No failure, flake, timeout or cleanup residue remains unresolved. Final hub
inspection found no `bs-test-*` root, attributable process, checkout socket,
PID or held test lock. No relevant check was omitted.

## 7. Acceptance and next boundary

Product, Contract, Architecture, Replacement and Operations proof pass. C1 is
`ACCEPTED`; R1 and R2 are consumed and must never resume.

The only unlocked action is:

```text
commit and push the C1 safe checkpoint
  -> refresh current C2 WebHost/cleanup source, consumers and tests
    -> issue C2 execution authority only after its own READY review
```

C2–C7 implementation and S6 remain unauthorized until their own gates pass.

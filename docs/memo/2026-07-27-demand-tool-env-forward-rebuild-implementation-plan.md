# Demand Tool Env Forward REBUILD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` to execute this plan block by block. Use
> `superpowers:test-driven-development` for every executable change,
> `buddyswitch-testing` for target discovery and evidence, and
> `superpowers:verification-before-completion` before any completion claim.
> Steps use checkbox (`- [ ]`) syntax so execution can stop safely at every
> gate.

**Status:** implementation in progress; execution authorized by the user on
2026-07-27. Blocks must complete in A → D order, followed by a fresh real Dev
Actor/WebUI acceptance run.

**Source identity:** `c81d4e0eaa957c564d45b072b1f0de88f3c71114`
(`Refine demand triage semantic judgment`).

**Execution baseline:** isolated worktree
`/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`, branch `fea-daemon`, with
`HEAD=c81d4e0eaa957c564d45b072b1f0de88f3c71114`. Before implementation, the
only non-ignored untracked file was this plan; there were no tracked changes.

**Goal:** REBUILD Demand's Codex-visible tool boundary into one
`buddyswitch-env` projection with four current actions, make inbound triage the
only path that creates or changes a Demand, make Parent reconciliation the only
path that completes a Demand, and remove every live self-Demand, dedicated
triage MCP, special broker, and duplicate mutation path.

**Architecture:** Codex thread configuration selects which actions and Skills
are visible; the unified `demand_sys` adapter validates actual Actor, Thread,
one-shot side capability, Task evidence, and action authority; Demand Sys owns
one canonical aggregate and one transaction path. Product handlers coordinate
the flow. `daemon-service` remains product-neutral activation and
reconciliation infrastructure and receives no Demand semantics.

**Tech stack:** Python 3, Codex App Server per-thread configuration, native MCP
tool filtering, native Skills, BuddySwitch runtime broker and environment tool
registry, actor-scoped JSON aggregates, native Codex Goal, the public
`./buddyswitch-test` runner, BuddySwitch CLI/WebUI, and real Actor logs.

**Submission policy:** this plan remains uncommitted for review. Do not begin
implementation, stage the plan, or create implementation commits until the
user authorizes execution. After authorization, submit code, tests, current
architecture docs, this plan's checked state, and acceptance evidence only
after the real-Actor gate passes.

---

## 1. FRAME

### 1.1 Exact bottleneck

Demand behavior currently has one canonical aggregate but several
Codex-visible and transport-level mutation surfaces:

- Parent/Goal can see direct `create`, `revise`, and `cancel`, allowing Actor
  self-Demands and bypassing inbound triage;
- the isolated side commits through a second MCP server and a special
  `demand.ingress.resolve` broker method rather than the normal `env.tool`
  route;
- `resolve_ingress` and the direct Actor mutations converge on similar state
  changes through partially duplicated code;
- Parent completion accepts evidence references structurally but does not
  programmatically prove that a same-Actor, same-Demand Task actually completed;
- Parent and Side Skill intent is installed globally but not projected as one
  exact per-thread working surface;
- active code, tests, permissions, architecture guidance, and schemas still
  teach the six-action Actor API and Actor-create receipts.

This permits multiple products to express the same Demand transition and makes
tool visibility, authority, wire truth, and canonical state disagree.

### 1.2 Observable acceptance sentence

> From a fresh WebUI Actor, every inbound is resolved through
> `demand_sys__resolve_inbound` on an isolated side; only inbound triage can
> create, merge, revise, or cancel a Demand; Parent/Goal can only list, get, and
> complete; completion requires a completed same-Actor Task for that Demand;
> Task/Goal reconciliation selects later live work; native MCP tools, Skills,
> broker results, persisted Demand/Task state, Web-visible replies, logs, and
> resource cleanup all agree, with no retired mutation or transport path left
> live.

### 1.3 Protected contracts and scope

No external compatibility contract has been identified. This is Sharp mode:
cut over directly and rebuild fresh Actor state.

In scope:

- exact Demand tool actions, schemas, descriptions, permissions, and results;
- Parent versus side Codex tool and Skill projection;
- Parent `context.get` guidance projection, so it does not advertise the
  side-only resolver as an available Parent action;
- one-shot side capability and actual Thread/Actor authority;
- unified `env.tool` wire path for inbound resolution;
- one Demand aggregate schema and one mutation implementation;
- Task evidence validation before Demand completion;
- Demand triage and orchestration Skills;
- affected current architecture docs, tests, role guidance, and runtime
  cleanup;
- real Actor/WebUI acceptance.

Out of scope:

- changing Codex source under `/Users/chen/Dev/codex`;
- Control Thread or Work Thread redesign;
- multi-Task parallelism or dynamic Work Thread creation;
- changing native Goal execution semantics;
- adding a Demand dependency graph;
- adding semantic judgment to Python, the broker, or daemon-service;
- migrating or interpreting old Actor aggregate state;
- limiting unrelated side tools beyond the exact Demand-side projection;
- broad WebUI redesign.

The Task terminal-result schema currently records native Goal terminal status,
token, and time metadata but not a complete work-result/evidence record. This
REBUILD does not silently invent that separate Task schema change. It validates
the terminal Task identity/binding and continues to require exact durable
Message/artifact evidence at Demand completion. If real acceptance proves that
the missing Task result record prevents reliable reconciliation, that is a
reported blocker requiring an explicit follow-up design, not permission to add
an ad hoc transcript fetch or model-generated summary inside this work.

---

## 2. Frozen current architecture

### 2.1 One Codex-visible Demand tool

There is one MCP server and one Demand tool definition:

```text
Codex Thread
  ↓ native MCP tools/list + tools/call
buddyswitch-env
  ↓ env.tool
Tool Registry
  ↓ demand_sys adapter
Demand application boundary
  ↓
Demand Sys domain
  ↓ one actor-scoped transaction
canonical Demand aggregate
```

The complete action set is exactly:

```text
demand_sys__list
demand_sys__get
demand_sys__resolve_inbound
demand_sys__complete
```

There is no public or Actor-callable:

```text
demand_sys__create
demand_sys__revise
demand_sys__cancel
demand_triage.resolve
demand.ingress.resolve
```

The words above may remain only in historical memos or negative residue tests.

### 2.2 Thread projections

Installed files may be shared by the Actor workspace. Codex per-thread config
controls actual model-visible tools and selected Skills.

```text
Demand Triage Side
├─ Skill: demand-triage
├─ demand_sys__list
├─ demand_sys__get
├─ message__get
├─ message__conversation
└─ demand_sys__resolve_inbound

Parent/Main, including native Goal on that Parent Thread
├─ Skill: demand-orchestration
├─ demand_sys__list
├─ demand_sys__get
└─ demand_sys__complete
```

Required negative visibility:

- Side cannot see or call `demand_sys__complete` or select
  `$demand-orchestration`;
- Parent/Goal cannot see or call `demand_sys__resolve_inbound` or select
  `$demand-triage`;
- no thread can see direct Demand `create`, `revise`, or `cancel`;
- Goal is not a separate Thread. It inherits the Parent Thread's projection and
  receives no separate BuddySwitch tool-filter concept.

The Parent's informational `context.get.tool_catalog` must also omit the
side-only resolver. The Side does not receive `context.get`; it learns the
resolver from its actual MCP `tools/list` result and `$demand-triage`. This is a
narrow catalog projection of the same action definition, not a second schema or
permission engine.

Exposure and permission are separate:

- Codex config decides what the model sees;
- the adapter still rejects forged or misplaced calls using actual invocation
  identity;
- domain code validates business and lifecycle invariants.

### 2.3 Action semantics

`demand_sys__list`

- reads compact live, terminal, or all Demand summaries;
- never mutates state.

`demand_sys__get`

- reads one complete current Demand and its opaque `demand_ref`;
- never mutates state.

`demand_sys__resolve_inbound`

- is callable only from the isolated side bound to one claimed ingress receipt;
- model arguments remain:

```json
{
  "decision": "no_action_needed | handled | create | merge_intake | revise | cancel",
  "reason": "grounded classification reason",
  "demand_ref": "opaque live ref or null",
  "description": "complete post-resolution need or null",
  "detail": "complete post-resolution satisfaction contract or null",
  "reply_content": "complete source-local reply or null"
}
```

- the model does not provide Actor id, Thread id, source key, receipt attempt,
  capability token, storage path, or numeric revision;
- `no_action_needed` settles the receipt without a Demand mutation;
- `handled` sends and verifies the bound source reply, then settles the receipt;
- `create`, `merge_intake`, `revise`, and `cancel` atomically apply exactly one
  canonical Demand effect and settle the receipt;
- it creates no Task and controls no Goal.

`demand_sys__complete`

- is callable only from Parent/Main;
- requires one current opaque `demand_ref`, a concrete satisfaction summary,
  and durable evidence refs;
- at the application boundary, requires at least one `task_sys.task` ref whose
  Task:
  - exists;
  - belongs to the same Actor;
  - is `completed`, not merely terminal or canceled;
  - is bound to the same `demand_id`;
- Task status is necessary evidence, not sufficient semantic proof. The
  Parent Actor, guided by `$demand-orchestration`, must still judge the latest
  Demand outcome, delivery, constraints, and other evidence as satisfied;
- it mutates no Task or Goal.

### 2.4 One owner per rule

| Rule | Single owner |
|---|---|
| Which tools/Skills the model sees | Codex per-thread config assembled by the Actor/triage launcher |
| Actual Actor/Thread/capability authority | unified Demand tool application adapter |
| Inbound semantic classification | `$demand-triage` Skill + side model |
| Completion semantic judgment and next-work choice | `$demand-orchestration` Skill + Parent model |
| Demand shape, lifecycle, stale ref, receipt, and transaction invariants | Demand Sys domain |
| Aggregate locking and atomic replacement | Demand repository |
| Task identity, status, Actor, and Demand binding | Task Sys public/domain read contract |
| Generic activation, retry, checkpoint, and reconciliation | daemon-service |

The daemon must not inspect a Demand decision, select a Demand, validate a Task
as satisfying a Demand, or construct business prompts.

### 2.5 One bottom implementation

The Demand domain keeps private record-level primitives:

```text
create record
revise record
terminalize record
```

Both application actions reuse them:

```text
resolve_inbound
├─ no_action_needed / handled → settle receipt
├─ create                     → create record
├─ merge_intake / revise      → revise record + source provenance
└─ cancel                     → terminalize record as canceled + source provenance

complete
└─ terminalize record as completed after Task evidence validation
```

`resolve_inbound` is one composite application operation. It must not call
public `create`, `revise`, or `cancel` tools, chain Skills, or duplicate
terminalization logic.

The actor-scoped aggregate contains only:

```text
demands
demand_pool_revision
ingress_receipts
```

`actor_creation_receipts` is deleted from schema, repository validation,
domain access, fixtures, tests, and current documentation. Old aggregates are
not migrated; real acceptance uses a fresh Actor.

### 2.6 Side authority transport

The one-shot capability remains internal because Thread id alone is not a
sufficient security boundary for a process that can reach the runtime socket.

Target transport:

1. `DemandTriageHandler` mints a one-use capability and registers its hash on
   the side lease bound to Actor, main Thread, side Thread, purpose, source key,
   and receipt attempt.
2. The side's `buddyswitch-env` subprocess receives the raw capability in one
   private process environment variable.
3. `env_tool_mcp_server.py` attaches it to host invocation metadata when
   forwarding `demand_sys__resolve_inbound`.
4. The tool schema never exposes that token to the model.
5. The Demand application adapter validates the token hash and actual Codex
   `_meta.threadId` against the lease before any reply or Demand write.
6. A successful resolution consumes the capability exactly once. A stale
   target returns the receipt to retryable pending state without a partial
   effect.

Use one current environment-variable name. Do not retain the former dedicated
server name as an alias.

---

## 3. TRACE — current source and retirement map

| Current surface | Current fact | Required disposition |
|---|---|---|
| `scripts/env/tools/demand_sys/tool.py` | exposes six Actor actions | replace with exact four-action contract |
| `scripts/env/tools/demand_sys/_impl.py` | implements direct Actor mutations | keep reads, add unified resolver/completion adapters, remove direct mutation actions |
| `scripts/env/domain/demand_sys.py` | has public create/revise/cancel and ingress resolution; cancel resolution duplicates terminalization | refactor to private shared record operations and two current application paths |
| `scripts/env/repos/demands.py` | requires `actor_creation_receipts` | remove field with no fallback reader |
| `tools/launcher/demand_triage_mcp_server.py` | second MCP protocol and envelope | delete |
| `tools/launcher/demand_triage_runtime.py` | owns side lease/capability, handled reply, and composite application flow | retain as explicit application capability behind unified adapter; remove model-authored capability arg |
| `tools/launcher/demand_triage_handler.py` | attaches dedicated MCP plus partial env-tool allow-list | attach only unified env MCP filters, capability env, and side Skill config |
| `tools/launcher/env_tool_mcp_server.py` | unified MCP forwards actual Codex invocation metadata | add private resolver capability metadata without adding model args |
| `scripts/env/tool_runtime/context.py` | contains invocation fact and product-specific runtime accesses | add one narrow Demand ingress application access, not a generic service bus |
| `scripts/env/tool_runtime/registry.py` | constructs `ToolContext` and dispatches adapters | inject the explicit application capability |
| `scripts/runtime_kernel/dispatcher.py` | supports both `env.tool` and special `demand.ingress.resolve` | keep `env.tool`, delete special method and dispatch |
| `scripts/env/tool_runtime/role_auth.py` | authorizes six Demand actions | authorize exact four current actions; thread authority remains adapter-owned |
| `scripts/env/tools/context/_impl.py` | projects the global registry catalog and currently would advertise every Demand action to Parent | omit the side-only resolver from Parent guidance without copying its schema |
| `tools/launcher/actor_environment.py` / `codex_config.py` | install shared Skills but do not freeze Parent Demand projection | set Parent tool deny and Skill selection policy |
| `buddyswitch/skills/shared/demand-triage/SKILL.md` | calls dedicated resolver | call unified `demand_sys__resolve_inbound` |
| `buddyswitch/skills/shared/demand-orchestration/SKILL.md` | permits revise/cancel during reconciliation | complete or leave live only, then select at most one live Demand |
| role `AGENTS.md` files | may still permit Actor self-Demand language | remove self-create/revise/cancel guidance |
| `docs/arch/demand-sys-architecture.md` | teaches six Actor actions and dedicated MCP | replace with this current architecture |

Historical `docs/memo/**` files may retain past architecture as history. They
are never active policy and must not be copied into current code or guidance.

---

## 4. Efficient test strategy

### 4.1 Proof order

Use the shortest meaningful consumer boundary first:

```text
structured definition/config RED
  → application adapter + domain RED
  → full env.tool broker wire RED
  → automated Task/Goal product-flow RED
  → focused affected-boundary GREEN
  → real WebUI Actor acceptance
```

Do not start with a broad suite. Do not claim success from unit fields,
mock-only registration, `ok: true`, or eventual state convergence.

For each mutating action, one test must prove all four agree:

```text
persisted effect
protocol result
consumer-observed result
attributable error/log
```

Description tests should parse the structured tool definition and verify
meaningful action/schema/invariant fields. Do not snapshot exact prose or
claim semantic quality from string equality. Semantic classification is proved
by scenario behavior and real Actor acceptance.

### 4.2 Public commands only

All automated proof uses:

```bash
./buddyswitch-test focused <file-or-nodeid>...
./buddyswitch-test full
```

`full` is not an early debugging tool. Run it only after the candidate is
frozen for merge/release or if the user explicitly requests repository-wide
acceptance.

### 4.3 Evidence record

Every GREEN block records:

- source commit and dirty-state identity;
- exact public test command;
- run id;
- pass/fail count;
- relevant runtime or broker error, if any;
- cleanup state;
- residual risk and next gate.

---

## 5. BUILD sequence

The implementation has four coherent blocks. Do not start the next block until
the current block's exact GREEN and replacement gate pass.

### Block A — freeze the four-action public contract and thread projection

**Claim:** native Codex exposure is exact before mutation internals move.

**Modify:**

- `scripts/env/tools/demand_sys/tool.py`
- `scripts/env/tools/demand_sys/_impl.py`
- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tools/context/_impl.py`
- `tools/launcher/actor_environment.py`
- `tools/launcher/codex_config.py`
- `tools/launcher/demand_triage_handler.py`
- `buddyswitch/skills/shared/demand-triage/SKILL.md`
- `buddyswitch/skills/shared/demand-orchestration/SKILL.md`
- affected role `tools/launcher/assets/roles/*/AGENTS.md`

**Tests:**

- `tests/unit/env_tool/test_native_mcp_server.py`
- `tests/process/cli/test_env_native_mcp_projection.py`
- `tests/integration/env_tool/test_response_registry.py`
- `tests/unit/actor/test_role_action_auth.py`
- `tests/process/launcher/test_bootstrap_config.py`
- `tests/integration/app_server/test_client.py`
- `tests/integration/actor/test_side_thread_lifecycle.py`
- `tests/unit/architecture/test_task_management_skill.py`
- `tests/unit/architecture/test_demand_sys_boundaries.py`

- [x] Write RED assertions that the global native Demand action set is exactly
      `{list, get, resolve_inbound, complete}`.
- [x] Write RED Parent-config assertions:
      `demand_sys__resolve_inbound` is disabled and `demand-triage` is disabled;
      orchestration remains available.
- [x] Write a RED `context.get` assertion that Parent guidance contains
      `list/get/complete` but does not advertise `resolve_inbound`; verify the
      projection reuses the registry definition instead of maintaining copied
      action descriptions.
- [x] Write RED side-config assertions: only Demand reads, Message reads, and
      `resolve_inbound` are enabled; inherited Parent deny-list is explicitly
      overridden; `demand-triage` is enabled and `demand-orchestration` is
      disabled.
- [x] Write RED App Server projection proof using the real `thread/start.config`
      payload, not only a helper return value.
- [x] Write negative architecture assertions for direct public Demand mutation
      actions and Goal-specific filtering.
- [x] Run the RED target and record the expected contract mismatch:

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_native_mcp_server.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/integration/env_tool/test_response_registry.py \
  tests/unit/actor/test_role_action_auth.py \
  tests/process/launcher/test_bootstrap_config.py \
  tests/integration/app_server/test_client.py \
  tests/integration/actor/test_side_thread_lifecycle.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/unit/architecture/test_demand_sys_boundaries.py
```

- [x] Replace the ToolDefinition with the exact four actions and the frozen
      schemas in section 2.3.
- [x] Remove six-action language and direct Actor mutation permissions.
- [x] Apply Parent config and side config at their actual Codex `thread/start`
      boundaries.
- [x] Update the two Skills without duplicating their full SOP into prompts or
      tool descriptions.
- [x] Run the same focused command GREEN.
- [x] Inspect actual MCP `tools/list` projections in the App Server test:
      helper configuration alone is insufficient.

**Block A gate:**

- the model-visible action set is exact for both Thread types;
- forbidden actions are neither listed nor recommended by current Skills;
- domain/runtime behavior may remain temporarily RED only inside the active
  implementation block; no compatibility alias is introduced.

**Block A evidence (2026-07-27):**

- baseline: run `c0bb321ab51b4f68bedd2c3aab87eadb`, 104 passed and
  161 subtests passed;
- RED: run `fb20ab39f11840bebabe5a8e5044dd96`, 9 expected contract
  failures, 97 passed and 116 subtests passed;
- GREEN: run `55a468964d484f61884ea2a40fc4f0da`, 106 passed and
  149 subtests passed in 3.18s;
- intermediate run `d16bc59ee4524dc3adabad3ac04ff4b1` exposed one stale
  test assertion that still taught Parent cancel; the assertion was replaced
  with the current complete-only rule before the recorded GREEN;
- source: `HEAD=c81d4e0eaa957c564d45b072b1f0de88f3c71114` plus the
  current tracked Block A patch and this untracked plan;
- cleanup: runner exited cleanly; no residual run process or test root;
- residue gate: public native tools, Parent catalog, role permissions, Parent
  config, side `thread/start.config`, and current Skills expose only the
  intended projections. Dedicated transport and domain mutation internals are
  intentionally deferred to Blocks B and C; current architecture-doc cleanup
  remains Block D.

### Block B — route inbound resolution through unified `env.tool`

**Claim:** the side commits one truthful, capability-bound resolution through
the normal environment tool wire and no second MCP/broker route exists.

**Modify:**

- `tools/launcher/env_tool_mcp_server.py`
- `tools/launcher/demand_triage_runtime.py`
- `tools/launcher/demand_triage_handler.py`
- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tools/demand_sys/_impl.py`
- `scripts/runtime_kernel/dispatcher.py`
- `tools/launcher/side_thread_registry.py` only if an existing capability
  field must be narrowed, not redesigned

**Delete:**

- `tools/launcher/demand_triage_mcp_server.py`
- `tests/unit/demand_sys/test_triage_mcp_server.py`

**Replace/update tests:**

- `tests/integration/runtime_broker/test_broker.py`
- `tests/integration/demand_sys/test_side_triage_flow.py`
- `tests/integration/env_tool/test_response_demand.py`
- `tests/integration/app_server/test_client.py`
- `tests/integration/actor/test_side_thread_lifecycle.py`
- `tests/process/services/test_runtime_broker_behavior.py`
- `tests/unit/actor/test_side_thread_registry.py`

- [x] First replace the dedicated-server test with one unified native MCP
      schema and invocation RED; do not preserve a test for the retired server.
- [x] Write a full wire RED that calls `env.tool` with
      `tool=demand_sys`, `action=resolve_inbound` and proves:
  - success returns top-level `ok: true`;
  - the receipt and Demand effect commit exactly once;
  - actual Codex Thread id and private capability are not model args;
  - missing, wrong, consumed, wrong-purpose, wrong-Actor, or wrong-Thread
    authority fails before reply or Demand mutation;
  - stale `demand_ref` returns retryable pending without partial state;
  - `handled` sends one bound reply, verifies it, and reports the durable
    Message id.
- [x] Write a RED proving `demand.ingress.resolve` is unsupported.
- [x] Run the focused RED:

```bash
./buddyswitch-test focused \
  tests/integration/runtime_broker/test_broker.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/integration/app_server/test_client.py \
  tests/integration/actor/test_side_thread_lifecycle.py \
  tests/process/services/test_runtime_broker_behavior.py \
  tests/unit/actor/test_side_thread_registry.py
```

- [x] Move the private capability into the unified MCP subprocess environment
      and host invocation metadata.
- [x] Add one narrow Demand ingress application access to `ToolContext`,
      following existing product-access composition patterns. Do not create a
      generic handler registry, service locator, event bus, or daemon callback.
- [x] Invoke `demand_triage_runtime.resolve_request` through that explicit
      capability behind the unified adapter.
- [x] Ensure `resolve_request` receives host-owned capability separately from
      the model proposal and validates before `_ensure_handled_reply`.
- [x] Delete the special broker method and dedicated MCP server/config.
- [x] Preserve the existing one-shot side lease; do not add Codex source
      changes or a new resource service.
- [x] Run the same focused command GREEN.
- [x] Inspect broker logs and persisted aggregate for success/failure
      agreement, including the former “state succeeded, tool reported failed”
      class.

**Block B gate:**

- one server, one broker method, one resolver schema, one truthful envelope;
- no model-authored authority fields;
- no partial reply/Demand effect on authority or stale failures;
- side lease and capability consumption remain attributable and cleanup-safe.

**Block B evidence (2026-07-27):**

- RED: run `e4c4542412564ac4bfe999aba328b710`, 23 expected
  implementation failures, 114 passed and 44 subtests passed; the failures
  named the missing host injection, new runtime signature, unified adapter,
  and retired broker route;
- first GREEN candidate `4dc984a85c8d4f63ab4846b91494f528`
  exposed eager Demand runtime loading on unrelated env tools; the access was
  narrowed to a lazy, explicit application capability;
- focused wire supplement `77f1cf5709454d3fb2fb1de7cc92ebbf`
  passed 5 tests and 4 subtests and proves `handled` reports exactly one
  verified durable Message id and rejects consumed-capability replay;
- final GREEN: run `f58757a06dab4e6ba69c843fa153279e`,
  127 passed and 56 subtests passed in 4.66s;
- persisted-state checks compare the Demand aggregate, receipt state, Task
  snapshot, Message reply identity/count, and side lease consumption against
  the successful wire result; authority and stale paths prove no contradictory
  partial Demand/Message effect;
- process broker coverage ran inside the final command and its resource ledger
  exited cleanly; `/private/tmp/bs-test-f58757a0-qgml5ryk` was removed;
- residue search found the retired server/config/method only in scoped negative
  assertions and this implementation plan, never in live code or current
  Skills/architecture guidance; `git diff --check` passed.

### Block C — remove self-Demand residue and harden completion

**Claim:** inbound triage owns every create/change/cancel transition, while
Parent completion is admitted only with verified terminal Task evidence.

**Modify:**

- `scripts/env/domain/demand_sys.py`
- `scripts/env/repos/demands.py`
- `scripts/env/tools/demand_sys/_impl.py`
- `scripts/env/tool_runtime/context.py` if the Task read capability belongs
  there
- Task Sys public/domain read module identified during TRACE
- `buddyswitch/skills/shared/demand-orchestration/SKILL.md`

**Tests:**

- `tests/unit/demand_sys/test_ingress_resolution.py`
- `tests/unit/demand_sys/test_lifecycle.py`
- `tests/integration/demand_sys/test_repository_atomicity.py`
- `tests/process/launcher/test_demand_commands.py`
- `tests/integration/env_tool/test_response_demand.py`
- `tests/integration/goal_mode/test_demand_orchestration.py`
- `tests/integration/goal_mode/test_task_goal_reconciliation.py`
- `tests/integration/env_tool/test_response_task.py`

- [x] Replace direct-create test fixtures with real
      `claim_ingress → begin_ingress → resolve_inbound(create)` setup helpers.
      Tests must not keep retired Actor-create as a convenient seeding API.
- [x] Write repository RED proving the only valid top-level fields are
      `demands`, `demand_pool_revision`, and `ingress_receipts`.
- [x] Write shared-mutation RED proving resolve create/revise/cancel and Parent
      complete use the same record lifecycle primitives and increment the pool
      revision once per committed transaction.
- [x] Write completion RED cases:
  - no Task evidence;
  - missing Task;
  - other Actor's Task;
  - active Task;
  - canceled Task;
  - completed Task bound to another Demand;
  - completed same-Actor Task bound to the target Demand;
  - stale Demand ref after Task completion;
  - required delivery evidence absent even though Task completed.
- [x] Prove every rejected completion leaves Demand, Task, Goal, pool revision,
      and evidence unchanged.
- [x] Run the focused RED:

```bash
./buddyswitch-test focused \
  tests/unit/demand_sys/test_ingress_resolution.py \
  tests/unit/demand_sys/test_lifecycle.py \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/process/launcher/test_demand_commands.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/integration/goal_mode/test_demand_orchestration.py \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/integration/env_tool/test_response_task.py
```

- [x] Extract/retain private `_new_demand_record`, `_revise_record`, and one
      `_terminalize_record` operation; remove duplicate inline cancel
      transition logic.
- [x] Delete public direct Actor `create`, `revise`, and `cancel` application
      entrypoints and `actor_creation_key` handling.
- [x] Delete `actor_creation_receipts` with no alias, migration, default,
      fallback read, or dual schema.
- [x] Validate terminal Task evidence at the Demand tool application boundary
      through one Task Sys read contract. Do not make the Demand domain depend
      on Task adapter DTOs.
- [x] Keep semantic satisfaction in the Parent Skill: completed Task status
      alone never auto-completes a Demand.
- [x] Change orchestration behavior to exactly:

```text
terminal Task observed
  → reread latest Demand and durable evidence
  → satisfied: demand_sys__complete
  → not satisfied: leave Demand live
  → reread all live Demands
  → if no active Task, select at most one and create Task/Goal
```

- [x] Run the same focused command GREEN.

**Block C gate:**

- one aggregate schema and one write path;
- no Actor self-Demand lifecycle remains;
- no completion without a valid completed same-Demand Task;
- no automatic completion from Task status;
- an unsatisfied Demand remains live and can be selected for another Task.

**Block C evidence (2026-07-27):**

- RED: run `6285f7360fb8448394df16acdd260ebc`, 12 expected
  failures, 61 passed and 24 subtests passed; failures identify schema v4
  residue and every invalid completion class that previously terminalized a
  Demand;
- GREEN: run `79b0ae1a5eaf40cfabeea93e4fe76b4e`, 65 passed and
  32 subtests passed in 1.91s;
- adjacent consumer/architecture proof:
  `a66b591cd3b147438e58f8960dc338df`, 36 passed and 17
  subtests passed; this supersedes `12edf666d86e4397811d8b34b9551698`,
  which caught and removed one stale `demand_sys.create` schema test;
- repository schema is v5 and rejects the retired field without rewrite;
  source and tests contain no direct Demand create/revise/cancel application
  entrypoint or fixture;
- completion rejection snapshots compare the full Demand aggregate and every
  Task record after Task/Goal terminal setup; valid completion changes only
  the Demand and preserves Task state;
- Task status is admitted through
  `task_sys.require_completed_task_for_demand`; delivery evidence remains a
  Parent semantic judgment and must include a concrete artifact or verified
  IM reply ref beyond Task status;
- runner roots were removed, residue search is clean except the scoped
  repository negative guard, and `git diff --check` passed.

### Block D — prove the whole automated product path and remove live residue

**Claim:** the current architecture operates end to end and the retired model
is absent from every active surface.

**Modify:**

- `tests/system/goal_mode/test_product_flow.py`
- `tests/system/goal_mode/support.py` if the deterministic model controller
  needs the current tool names
- `tests/unit/architecture/test_demand_sys_boundaries.py`
- `tests/unit/architecture/test_task_management_skill.py`
- `docs/arch/demand-sys-architecture.md`
- `docs/arch/task-sys-architecture.md` only for the affected completion
  boundary
- `docs/arch/daemon-service-architecture.md` only to keep the generic boundary
  explicit; no new daemon business design

- [x] Update the deterministic system controller to call
      `mcp__buddyswitch_env` / `demand_sys__resolve_inbound`; do not add a
      translation alias for the former MCP name.
- [x] Add one automated vertical scenario:
  1. inbound A creates Demand A;
  2. a supplement merges into A;
  3. independent inbound B creates Demand B;
  4. ordinary conversation is handled/no-action and creates no Demand;
  5. inbound C creates then a later inbound cancels C;
  6. at most one active Task/native Goal exists;
  7. a terminal Task reconciles against its latest Demand;
  8. satisfied Demand completes with validated evidence or remains live
     without mutation;
  9. one later live Demand is selected into the next Task/Goal;
  10. Goal never self-creates, revises, or cancels a Demand.
- [x] Assert actual tools and selected Skill visible on each model request,
      not only final persisted state.
- [x] Assert all side leases, one-shot capabilities, subprocesses, sockets, and
      test Actor state are cleaned.
- [x] Run the system RED, then GREEN:

```bash
./buddyswitch-test focused \
  tests/system/goal_mode/test_product_flow.py \
  tests/system/goal_mode/test_native_goal_contract.py
```

- [x] Run the consolidated affected-boundary GREEN:

```bash
./buddyswitch-test focused \
  tests/unit/env_tool/test_native_mcp_server.py \
  tests/process/cli/test_env_native_mcp_projection.py \
  tests/integration/env_tool/test_response_registry.py \
  tests/integration/runtime_broker/test_broker.py \
  tests/integration/demand_sys/test_side_triage_flow.py \
  tests/integration/env_tool/test_response_demand.py \
  tests/unit/demand_sys/test_ingress_resolution.py \
  tests/unit/demand_sys/test_lifecycle.py \
  tests/integration/demand_sys/test_repository_atomicity.py \
  tests/integration/goal_mode/test_demand_orchestration.py \
  tests/integration/goal_mode/test_task_goal_reconciliation.py \
  tests/integration/actor/test_side_thread_lifecycle.py \
  tests/process/launcher/test_bootstrap_config.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_task_management_skill.py \
  tests/system/goal_mode/test_product_flow.py
```

- [x] Update current architecture docs from source facts after code is GREEN.
      Historical memos remain unchanged.
- [x] Run a residue audit over live surfaces:

```bash
rg -n \
  'demand_triage\\.resolve|buddyswitch-demand-triage|demand\\.ingress\\.resolve|demand_sys__(create|revise|cancel)|actor_creation_receipts' \
  scripts tools buddyswitch/skills docs/arch tests
```

- [x] Classify every remaining match. Only scoped negative absence assertions
      may remain. Remove old code, imports, permissions, fixtures, help,
      schemas, comments, prompts, Skill guidance, and positive tests.
- [x] Run `git diff --check` and inspect the full diff for duplicated rules,
      guessed shapes, fallback reads, alias names, and daemon business coupling.

**Block D gate:**

- automated product, contract, architecture, replacement, and operations proof
  is GREEN;
- all current docs teach one architecture;
- no retired live path exists;
- real Actor acceptance is the only remaining gate.

**Block D evidence (2026-07-27):**

- system RED: run `de2631662b2e40c4808e74a1ddec3ce2`, 1 failed and
  2 passed; the new Side request-surface assertion exposed that Code Mode
  presents native environment actions through the top-level `exec` tool;
- system GREEN: run `e9ef7adb4c08477995f861d237790267`, 3 passed in
  203.02s. The deterministic controller executed 36 real model stages across
  Web, App Server, daemon, broker, Side, Parent, Task, and native Goal. It
  proved Demand A create/merge/complete, independent Demand B selection,
  ordinary no-action, Demand C create/cancel, exact Skill/tool projections,
  durable reply evidence, one active Task, and owned resource cleanup;
- architecture RED: run `ac84b9336e8c4b60abad28c38a40a9e2`, 2 failed and
  16 passed; the failures identified the retired absolute phrases
  `select exactly one` and `one task per demand`;
- architecture GREEN: run `3c1b1b6d64cf40768cdf4fa126be7bc5`,
  18 passed. Current docs and structural guards now enforce the four-action
  surface, one-use Side authority, Task evidence boundary, and generic daemon
  ownership;
- consolidated affected-boundary GREEN:
  run `9ee81ca259f547dfb7b6b37b9c60ada3`, 167 passed and
  114 subtests passed in 206.74s. The prior run
  `12cfa2abadc34ae3ac2233a9a435c173` reached 166 passed and exposed one
  cross-tier test-import collision; the system/bootstrap harnesses now use the
  public runner's launcher-module path without changing product runtime
  architecture;
- completion-audit rerun after real Actor acceptance:
  run `c1ddc0418e954ab581fdb4523b24a12c`, 167 passed and
  114 subtests passed in 207.96s. It used the same consolidated public
  `./buddyswitch-test focused ...` command and exited 0 with runner cleanup;
- pre-publish verification:
  run `1c2618c69ebd4defb12302d6ca267fde`, 167 passed and
  114 subtests passed in 207.14s. It repeated the exact consolidated public
  focused command on the implementation candidate immediately before commit;
- completion static/resource audit: `git diff --check` returned no output;
  the exact retired-term search returned nine matches, all in scoped negative
  assertions that forbid the old actions, dedicated MCP config, or retired
  aggregate field; `instance list` returned an empty array; ports `51609` and
  `9222`, the accepted Actor id, its two lock paths, and recent
  `/private/tmp/bs-test-*` roots had no listener, process, open-file holder, or
  temporary test root. The worktree remained at the specified source commit
  with 47 changed/untracked paths and no commit or push.
- the exact residue query reports only scoped negative absence assertions:
  one rejected aggregate fixture, one retired Side-config absence check, two
  rejected special-broker-method checks, and four Parent/Goal tool-surface
  exclusions. Live code, config, Skills, and architecture docs contain no
  retired transport, mutation surface, schema, or fallback;
- `git diff --check` passed. Generic daemon modules contain no Demand import or
  Demand term, and the interrupted diagnostic run's owned processes, sockets,
  Actor root, and `/private/tmp/bs-test-1791639d-7k9b6mcu` were explicitly
  removed.

---

## 6. Real Actor/WebUI acceptance

Automated GREEN is necessary but not final acceptance. Use a fresh runtime and
one real Dev Actor. WebUI is the sole product writer; CLI and logs are
read-only observers except lifecycle setup/cleanup.

### 6.0 Acceptance attempt ledger

- attempt 1 RED used Web port `51606`, fresh Dev Actor
  `act-dev-41e6913d77ad`, main Thread
  `019fa20e-4199-75a2-8d06-c5c86028ed19`, and Side Thread
  `019fa20f-3978-7ce0-81c6-c3edbd1c721f`. Create-A Web Message
  `msg-ab93ab1ec163` produced source
  `im.message.created:msg-ab93ab1ec163`;
- the Side lease started, but the run stopped before message 2 under the
  mandatory RED rule. The ingress receipt remained `resolving`, the Demand
  aggregate stayed empty at pool revision 0, and no partial Demand mutation
  occurred;
- product RED: fresh-Actor Web Console and orchestration both failed because
  `task_sys.list_tasks(actor_target=...)` validated retired Task records owned
  by unrelated Actors before applying the requested Actor scope;
- owner regression RED:
  run `dc76f9d7d62b4947a539ec5e2220067e`, 1 failed. The minimal owner fix now
  routes only records with a strict, canonical foreign `actor_target` before
  full current-schema validation. Missing, malformed, current-Actor, and
  unscoped retired records still fail without translation;
- owner GREEN: run `eda38a8181994d65adc3d657ddb8dcdd`, 3 passed;
  affected Task Sys, Web projection, Demand orchestration, Task/Goal
  reconciliation, and architecture GREEN:
  run `3b191ba396204b4bb89b9edd5832d571`, 64 passed and 10 subtests passed.
  The owner helper refactor remained GREEN in
  `1b71652f8ca043fdaaea9c5ec4f98b8d`, 53 passed and 10 subtests passed;
- post-fix system product GREEN:
  run `6b9184cb15844cfbbac315269e927b78`, 1 passed in 201.34s. The full
  deterministic 36-stage multi-Demand flow passed again after the
  Actor-scoped Task fix;
- independent external RED: App Server calls returned `401 token_expired` and
  `refresh_token_reused`; the Side therefore ended `systemError`. No
  compatibility path or local credential workaround was added;
- the failed Actor was stopped and deleted through WebUI, WebUI was stopped,
  the Browser page was closed, port `51606` was released, and no related
  instance/process/listener remained. A later successful run must use another
  fresh Actor and repeat the full scenario from message 1.
- attempt 2 RED, after the owner and system reruns, used Web port `51607`,
  fresh Dev Actor `act-dev-b2cce62297eb`, and main Thread
  `019fa218-ab50-75d3-9f35-f8d716789e9d`. Initial Demand aggregate and
  Actor-scoped Task projection were empty;
- Create-A Web Message `msg-53b1026f1a7a` produced source
  `im.message.created:msg-53b1026f1a7a` and attempt
  `attempt-7c52383a46e6`. The strict current schema-5 aggregate remained at
  pool revision 0 with no Demands and no Actor Task while the receipt was
  `resolving`;
- App Server startup and Side execution again returned
  `401 token_expired` and `refresh_token_reused`. Local
  `codex login status` reported only that ChatGPT credentials existed, while
  the real model endpoint proved those credentials unusable. The run stopped
  before message 2 and did not patch or continue;
- Actor `act-dev-b2cce62297eb` was stopped and deleted through WebUI, the
  in-app Browser page and WebUI process were closed, port `51607` was
  released, the instance root was removed, `instance list` returned only the
  two pre-existing inactive Actors, and no Task was written for the failed
  Actor. Durable identity/IM/empty receipt records and the central-daemon
  offline registry entry remain in shared product state; they were not edited
  directly or misreported as process/socket residue.
- continuation preflight at `2026-07-27 13:46:48 CST` did not create a third
  Actor: `/Users/chen/.codex/auth.json` still had mtime
  `2026-07-27 10:37:10 CST`, before both failed real endpoint attempts.
  `codex login status` continued to report only local credential presence, and
  `git diff --check` remained clean. A new acceptance run is deferred until
  the local Codex ChatGPT login is actually renewed.
- the third consecutive blocker audit at `2026-07-27 13:47:20 CST` found the
  same unchanged auth mtime and local-only login-status result. `instance list`
  still contained only the two pre-existing inactive Actors and
  `git diff --check` stayed clean. Real acceptance is blocked on an external
  credential renewal; no third test Actor was created.
- authentication was renewed at `2026-07-27 14:15:25 CST`. Attempt 3 used
  Web port `51608`, fresh Dev Actor `act-dev-774ce1dd6120`, main Thread
  `019fa238-1707-7c92-ae88-268d2fcadb73`, and `codex-cli 0.145.0`;
- Create-A Message `msg-36937797d2aa` settled as `create` in
  `attempt-7821dc58cb74`, producing Demand `demand-95a794d3231e` and the
  single active Task `task-demand-1cc85dcfa153`. The Goal completed that Task,
  sent and re-read durable reply `msg-91337af71dd4`, and WebUI rendered the
  runnable-file and automated/browser-test evidence;
- the observer stopped the run before message 2 after initially interpreting
  the empty-draft disabled Send button as a busy-thread restriction. Source
  tracing disproved that diagnosis: `canSend` is independent of
  `threadBusy`; only Clear is blocked by `Thread running`, and filling the
  composer is the event that enables Send. Existing exact UI proof remained
  GREEN in run `ac179f25f2af402b86b7e5b455d069e2`, 28 passed. No product code
  was changed for the false diagnosis;
- Actor `act-dev-774ce1dd6120` was stopped and deleted through WebUI, the
  in-app Browser tab and WebUI process were closed, ports `51608` and `9222`
  were released, the Actor and test roots were removed, and `instance list`
  was empty. Because the full multi-message scenario was not executed,
  attempt 3 is informative evidence only and not acceptance.
- attempt 4 GREEN on `2026-07-27 CST` used source
  `c81d4e0eaa957c564d45b072b1f0de88f3c71114` plus the recorded dirty diff,
  official Web port `51609`, fresh Dev Actor `act-dev-eae23e2f704f`, main
  Thread `019fa241-5ee8-7b11-8cc4-b46756b4a4f0`,
  `codex-cli 0.145.0`, Parent `gpt-5.6-terra/high`, and Side
  `gpt-5.6-luna/xhigh`. No prior Actor, Web listener, or browser listener was
  reused;
- create-A Message `msg-c8ad22f528ed` resolved once through attempt
  `attempt-a1c294c30e09` and Side Thread
  `019fa241-bb35-7862-9449-acffdb4b0e6f` as `create`, producing Demand
  `demand-38ce3193ed6b` revision 1 and Task
  `task-demand-0e19c8ddb963` at basis revision 1;
- supplement-A Message `msg-eec1bfacbf1f` resolved once through attempt
  `attempt-094ef073d19e` and Side Thread
  `019fa243-67e2-7df0-b8c9-b8913fa868a0` as `merge_intake`. It revised the
  same Demand to revision 2 without duplicating it or rewriting the active
  revision-1 Task. Reconciliation later created and completed
  `task-demand-f401c3c67a8e` at basis revision 2, delivered durable reply
  `msg-4ec648917ebf`, and completed A at revision 3 with that exact
  same-Demand Task and reply evidence;
- independent-B Message `msg-fae30c79c60f` resolved once through attempt
  `attempt-1bf0b0c8df5c` and Side Thread
  `019fa244-28de-7e62-abbb-cfe8fdc30ad2` as `create`, producing Demand
  `demand-1fd693de83b7`. It remained queued while A owned the active slot,
  then completed through `task-demand-3d507d48e016` and durable reply
  `msg-7bec41b0c494`;
- progress Message `msg-0d6d3d126e66` resolved once through attempt
  `attempt-4796fd451617` and Side Thread
  `019fa244-df08-77c2-b1e5-4d611cf68818` as `handled` with
  `demand_changed=false`, durable reply `msg-183177f83208`, no pool revision
  change, and no Task. One read-only Side `exec` used an incorrect Skill path,
  was rejected without state effect, and the Side recovered through the
  native tools;
- create-C Message `msg-0b0895e3a472` resolved once through attempt
  `attempt-ff33700d7c34` and Side Thread
  `019fa246-3e9d-76a2-9220-3a9283a91175` as `create`, producing Demand
  `demand-b3eba9e97bb7`. Cancel-C Message `msg-9509780fe242` resolved once
  through attempt `attempt-f5c76a0e767c` and Side Thread
  `019fa247-31df-76b1-a625-8b685dac77ea` as `cancel`, leaving A and B
  unchanged;
- the final strict schema-5 aggregate was pool revision 7: A completed at
  revision 3, B completed at revision 2, C canceled at revision 2,
  `live_demand_count=0`, and every one of the six ingress receipts was settled
  with exactly one committed outcome and `last_failure=null`. Three Tasks
  completed and no more than one was active at any time; final orchestration
  status was `consumed_empty_pool`;
- App Server request logs and rollout records showed each ephemeral Side used
  only `tools.mcp__buddyswitch_env__...`, exactly one
  `demand_sys__resolve_inbound`, and the selected Demand triage Skill. No
  dedicated triage MCP process started. Parent rollouts selected Demand
  orchestration and used only `list`, `get`, and `complete`; its effective
  config disabled `resolve_inbound`. Both completion results reported
  top-level `ok=true` and matched persisted terminal Demand, Task, reply, and
  artifact evidence;
- WebUI rendered three recent completed Tasks and zero active Tasks. It exposed
  A's runnable `projects/app` delivery, launch instruction, three passing Node
  tests and browser behavior; the supplement's refresh-persistence behavior;
  B's separate README with launch and all three operations; the normal
  progress reply; and the final stopped state. The WebUI then showed
  `No actors available` after deletion;
- the Actor was stopped and deleted through WebUI. The Browser was finalized,
  WebUI stopped, `instance list` became empty, ports `51609` and `9222` were
  released, the Actor root and sockets disappeared, and no Actor process,
  side lease, open file, or recent `bs-test-*` directory remained. Shared
  durable identity, IM, Demand, Task, artifact, and offline registry evidence
  intentionally remains. Two zero-byte demand/task lock-path files remain in
  shared durable state with no `lsof` holder; they are not active locks and
  were not deleted by an observer.
- residual operational risk: scheduler snapshots recorded two ignored
  Parent-busy retry ticks as `failed` with the generic text
  `scheduled trigger had no matching handler`. Later retry delivery reconciled
  the pool and no Demand/Task mutation contradicted its tool result, but the
  generic scheduler wording is imprecise and remains outside this Demand
  REBUILD.

### 6.1 Setup

- [x] Record source commit, dirty diff, model configuration, current date, and
      allocated Web port.
- [x] Confirm no prior test Actor or listener will be reused.
- [x] Start WebUI through the official product command on an isolated free port:

```bash
./buddyswitch-codex web --host 127.0.0.1 --port <free-port>
```

- [x] In WebUI, create one fresh `dev` Actor. Do not migrate an old actor whose
      aggregate contains retired fields.
- [x] Record Actor id, main Thread id, daemon/app-server/broker log paths, and
      initial empty Demand/Task projections.

### 6.2 Conversation scenario

Send one message at a time. After each message, wait for the attributable side
turn, receipt, Demand transition, pool attention, Task/Goal transition, reply,
and cleanup before deciding whether to continue.

1. **Create A**

   > 创建一个极简的单页日程管理工具，支持新增、完成和删除日程；完成后把可运行文件和测试结果回复给我。

   Expected: one side `create`; one live Demand A; no direct Parent mutation;
   at most one Task/Goal starts.

2. **Merge into A while work is active**

   > 这是同一个日程工具交付的补充：增加本地持久化，刷新页面后日程仍然存在，纳入同一次最终验收。

   Expected: `merge_intake` into A, not duplicate Demand; running Task is not
   secretly rewritten. Latest Demand revision is canonical for later
   reconciliation.

3. **Create independent B**

   > 另外独立交付一份简短 README，说明启动方式和三个主要操作；它与工具代码分开验收。

   Expected: one independent live Demand B; it queues while one Task is active.

4. **Normal progress conversation**

   > 现在进展到哪里？只告诉我已确认的进展和下一步，不要改变现有交付范围。

   Expected: `handled` or `no_action_needed` according to the actual reply need;
   no new/revised/canceled Demand and no shadow Task.

5. **Create and cancel C**

   > 再独立准备一份发布前检查清单，单独验收。

   Wait for C creation, then send:

   > 发布前检查清单不再需要，请取消这个独立需求，其它需求保持不变。

   Expected: C is canceled through inbound resolution; Parent/Goal never calls
   cancel.

6. **Observe Task/Goal reconciliation**

   Wait without injecting completion commands.

   Expected:

   - if Task A evidence satisfies the latest merged Demand A, Parent completes
     A;
   - otherwise A stays live and may receive another Task;
   - after the active slot clears, Parent compares all live Demands and selects
     at most one current Demand;
   - B is eventually selected and completed, unless A legitimately needs
     another Task first;
   - no Goal turn creates, revises, or cancels a Demand;
   - final replies/files/test evidence are visible to the Web user.

### 6.3 Required observations

For every inbound, correlate:

```text
Web Message id
→ ingress source key + attempt
→ side Thread id + one-shot lease
→ model-visible tools + selected Skill
→ env.tool request id
→ resolve_inbound decision/result
→ receipt and Demand pool revision
→ orchestration attention
→ Task id + native Goal status
→ durable reply/artifact evidence
→ lease/process cleanup
```

Explicitly prove:

- the side uses only `buddyswitch-env`; no dedicated triage MCP starts;
- all successful broker results have truthful top-level success and matching
  state;
- all rejected calls have no partial effect;
- Parent/Goal request tools never contain resolver or direct Demand mutation;
- side request tools never contain completion;
- normal conversation creates no Demand;
- the Goal creates no self-Demand;
- no more than one active Task exists;
- completed Demand evidence cites a valid completed same-Demand Task and any
  required Message/artifact delivery;
- WebUI exposes the promised user result, not only artifact metadata;
- side leases disappear within the bounded cleanup/reconciliation window and
  no socket/process/test Actor residue remains.

### 6.4 Acceptance stop rules

Stop and report RED immediately if:

- a forbidden tool is visible or callable;
- a state write succeeds while the tool reports failure, or vice versa;
- one inbound produces more than one committed resolution;
- Parent/Goal self-creates, revises, or cancels a Demand;
- completion accepts missing, canceled, cross-Actor, or cross-Demand Task
  evidence;
- a normal progress question becomes a Demand;
- a Task/Goal result is not delivered to the Web user;
- side resources do not clean up within the documented bounded window;
- any observer mutates state outside WebUI scenario actions.

Do not patch during the acceptance run and then continue treating it as one
run. Preserve logs, return to the nearest automated RED, fix, rerun affected
GREEN, start a fresh Actor, and repeat acceptance from the beginning.

### 6.5 Cleanup

- [x] Stop and delete the Actor through WebUI.
- [x] Stop WebUI and release any Actor browser resource.
- [x] Confirm `instance list` contains no test Actor.
- [x] Confirm no Web listener, App Server, daemon, broker, side lease, socket,
      held lock, or temporary Actor state remains. Zero-byte unheld lock-path
      files associated with durable shared records are recorded above.
- [x] Write a source-bound acceptance memo with exact observations, failures,
      fixes, reruns, and residual risk.

---

## 7. ACCEPT gate

The REBUILD is complete only when all are true:

### Product

- [x] Web users can submit, supplement, separate, cancel, and discuss work;
      canonical Demand outcomes and delivered results are visible and correct.
- [x] Task/Goal completion reconciles the latest Demand and later live work is
      selected with at most one active Task.

### Contract

- [x] The native tool set is exactly four actions.
- [x] Side and Parent/Goal projections are exact.
- [x] Wire success, failure, state effects, and user-visible results agree.
- [x] Demand completion requires verified completed same-Demand Task evidence.

### Architecture

- [x] Demand semantics are owned once.
- [x] Thread visibility, adapter authority, domain lifecycle, repository
      atomicity, Task truth, and daemon infrastructure remain separate.
- [x] daemon-service contains no Demand business branch or prompt.

### Replacement

- [x] Dedicated triage MCP and special broker method are deleted.
- [x] Direct Actor create/revise/cancel and Actor-create receipts are deleted.
- [x] No alias, fallback, dual schema, dual write, old test fixture, help text,
      Skill, or current architecture doc preserves the retired model.

### Operations

- [x] Focused automated evidence is GREEN.
- [x] Real Actor/WebUI acceptance is GREEN from a fresh Actor.
- [x] Side leases, capabilities, processes, sockets, and test state are clean.
- [x] `./buddyswitch-test full` is run only if the candidate is frozen for
      merge/release or the user explicitly requests it.

### Final report

The final implementation report must name:

- changed behavior and files;
- exact test commands, run ids, and counts;
- real Actor id/scenario and Web-visible outcome;
- retired residue removed;
- omitted checks;
- remaining risk and next owner/action.

No Phase or architecture work beyond this plan begins before the user reviews
the implementation and real-Actor acceptance evidence.

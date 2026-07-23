# Demand Ingress and Goal-Mode Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild BuddySwitch into one live path where inbound facts are triaged concurrently into canonical Demands, at most one current Task is executed by the actor main thread through native Codex Goal, and Goal completion triggers a separate parent Demand reconciliation/selection turn.

**Architecture:** Demand Sys owns canonical Demands plus a private source-keyed ingress receipt; a triage side receives one thread-scoped resolver tool and commits directly through the Demand owner without `outputSchema` or terminal App Server notifications. The product-neutral instance daemon only delivers durable triggers and invokes optional handler reconciliation. Task Sys becomes a minimal Demand-to-Goal binding/result record; native Goal owns multi-turn execution completeness.

**Tech Stack:** Python 3, JSON file aggregates with `fcntl` locking and atomic replacement, Unix-socket runtime broker and daemon mailbox, Codex App Server JSON-RPC, thread-scoped stdio MCP, Markdown skills, BuddySwitch public test runner.

---

## 0. Plan status and authority

This is the active implementation plan for the forward rebuild discussed on 2026-07-22 and 2026-07-23.

### 2026-07-23 execution checkpoint

Phase 1 is implemented and has passed its real product gate. Phase 2 has not
started.

The acceptance run used the official CLI Web server with isolated shared root
`/private/tmp/buddyswitch-phase1-green.1eTmKD/.codex-buddyswitch` and Market
actor `act-market-6550f8f531a3`. The actor was created, stopped, and resumed
through Web UI; all inbound facts were sent through the Web conversation.

The real run found and fixed three defects that mocked tests had not exposed:

1. The triage MCP server omitted `default_tools_approval_mode = "approve"`, so
   the side waited forever on an approval the product session could not
   present.
2. The triage handler reconstructed the long instance-local runtime-broker
   socket instead of reading the broker lifecycle owner's marker-resolved short
   path, causing an AF_UNIX path-length transport failure.
3. After actor restart, an ephemeral triage thread was not loaded by the new
   App Server, while reconciliation ignored `thread not loaded` and left the
   receipt permanently `resolving`.

After the fixes, the same accepted in-flight receipt recovered across
stop/resume and settled. Web displayed the exact `PHASE1_HANDLED_OK` reply.
Further Web messages produced these durable outcomes:

| Scenario | Receipt decision | Canonical result |
|---|---|---|
| direct reply | `handled` | one verified Web reply; no Demand |
| FYI | `no_action_needed` | no Demand mutation |
| new research need | `create` | Demand revision 1 |
| same-need supplement | `merge_intake` | same Demand revision 2 |
| boundary change | `revise` | same Demand revision 3 |
| withdrawal | `cancel` | same Demand revision 4, terminal `canceled` |

The focused Phase 1 regression passed with `56 passed, 8 subtests passed`.
The isolated actor is stopped and the Web page remains available for
inspection. The run also reconfirmed the planned Phase 2 replacement need:
the retired Task engine continued and completed a Task bound to Demand
revision 1 after that Demand had been revised and canceled. That behavior was
observed but deliberately not changed inside the Phase 1 gate.

It supersedes the implementation direction in:

- `docs/memo/2026-07-23-demand-intake-rebuild-stage-1-implementation-plan.md`, which treats Intake as a first-class stored object and depends on strict turn output plus `item/completed` / `turn/completed`;
- the Stage 1 portion of `docs/memo/2026-07-22-demand-goal-mode-forward-architecture.html` where it conflicts with this plan.

Those files remain historical memos only. They are not live policy, compatibility requirements, or supported runtime paths.

The current architecture owners that must be rewritten during this plan are:

- `docs/arch/demand-sys-architecture.md`;
- `docs/arch/task-sys-architecture.md`;
- `docs/arch/daemon-service-architecture.md`.

No compatibility reader, dual writer, feature flag, old/new schema switch, fallback Task executor, or old skill alias is permitted. Development may proceed in coherent blocks on this branch, but the product cutover is accepted only after the retired runtime state is explicitly rebuilt.

## 1. Exact bottleneck and acceptance sentence

### Bottleneck

BuddySwitch currently has three overlapping lifecycle owners:

1. first-class Demand Intake owns pending triage state;
2. the Demand triage daemon handler owns side completion by observing App Server notifications;
3. Task Sys owns a second side/parent execution state machine and progress-check loop.

The overlap creates two classes of product failure:

- a side can finish or fail without the Demand owner learning the outcome;
- a Task turn can finish without the requested work being complete, so BuddySwitch must reconstruct execution completeness with frames and progress checks.

### One observable acceptance sentence

> With a clean rebuilt shared state, a user can send several inbound facts to an online actor; each fact is durably resolved exactly once into no Demand, a new Demand, or an atomic change to one current Demand; at most one Task/Goal runs on the actor main thread; the native Goal continues until complete or explicitly stopped; Goal completion records the Task result and starts a new parent Demand reconciliation/selection turn; the resulting work and user-facing delivery are readable from Web/CLI after daemon restart, with no Intake object, Task frame, progress-check, or legacy Task schema reachable.

## 2. Code and runtime audit

### 2.1 Current source facts

| Finding | Current source evidence | Consequence |
|---|---|---|
| Intake is a first-class aggregate object | `scripts/env/repos/demands.py` schema version 3 contains `intakes`; `scripts/env/domain/demand_sys.py` exposes `capture_intake`, `get_intake`, `begin_triage`, `record_triage_proposal`, `retry_triage`, and `apply_triage_proposal` | The intermediate state has its own identity, public-like lifecycle, proposal storage, and result storage even though the product only needs source deduplication and resolution recovery |
| Triage depends on strict final output | `tools/launcher/demand_triage_handler.py` passes `TRIAGE_OUTPUT_SCHEMA` to `actor_side_thread.start_actor_side_thread`; `tools/launcher/side_thread_lifecycle.py` passes it to `turn/start.outputSchema` | Model/provider schema validation can reject the turn before triage begins |
| Triage completion depends on ephemeral notifications | `DemandTriageHandler` listens for item and turn completion, records an agent message, then applies the proposal | A daemon outage or notification-shape change can leave the stored intake permanently `triaging` |
| daemon-service has no activation/reconciliation lifecycle | `tools/launcher/daemon_contracts.py::DaemonHandler` has only `handles` and `handle`; `tools/launcher/daemon_core.py::run_daemon` registers and enters `read_notification` / scheduled-trigger polling | Product handlers cannot reconcile durable owner state at startup or on periodic idle |
| Generic scheduled delivery is already durable | `tools/launcher/demand_sys_daemon_adapter.py::enqueue_inbound` writes a due-now schedule to daemon state; `sweep_due_scheduled_triggers` marks it delivered only after handler success | The source-delivery layer does not need a new product queue or event bus |
| Offline inbound is not admitted to Demand handling | `scripts/env/tool_runtime/im_actor_delivery.py` requires Central daemon reachability `online` and a successful mailbox response; otherwise Message returns `target_not_online` or `handling_failed` | The outage risk here is already-accepted in-flight work, not silently queuing new Demand work into a fully offline actor |
| Actor Demand API is already correctly narrowed | `scripts/env/tools/demand_sys/tool.py` declares exactly `list`, `get`, `create`, `revise`, `complete`, `cancel` and calls triage/idempotency host-owned | The rebuild must preserve these six intents and must not expose ingress internals as a seventh Demand action |
| Native MCP tools are globally listed today | `scripts/env/tool_runtime/native_mcp.py::list_native_tool_specs` lists all registered actions; `tools/launcher/env_tool_mcp_server.py::_handle_tools_list` returns the entire list | Registering `demand_sys.resolve` in the normal registry would expose it to the parent Actor and violate the six-intent boundary |
| Codex supports per-thread config | Codex `ThreadStartParams.config` is loaded as session overrides; BuddySwitch `tools/launcher/app_server.py::thread_start` does not currently pass arbitrary config overrides | A dedicated MCP server can be injected only into triage side threads without changing the parent tool catalog |
| Codex supports per-thread MCP tool filtering | MCP server config supports `enabled_tools` / `disabled_tools`, and request overrides accept dotted keys | The triage thread can see only Demand reads and required source-local tools instead of inheriting Demand/Task mutation tools |
| Codex supports thread-scoped dynamic tools, but callbacks are client-bound | Codex `ThreadStartParams.dynamic_tools` exists; `item/tool/call` is sent to subscribed App Server client connections | A dynamic tool handled by the instance daemon would still fail if that daemon disconnects; it does not by itself satisfy the outage claim |
| Runtime broker survives daemon-only stop | The live test kept App Server and runtime broker alive after stopping the instance daemon | A side-only stdio MCP server can persist through the runtime broker while the daemon is offline |
| Current Task Sys is a second execution engine | `scripts/env/domain/task_sys.py`, `tools/launcher/task_sys_runtime.py`, and `tools/launcher/task_sys_daemon_adapter.py` implement side/parent states, handoff, outcome frames, and Progress Check | Goal-mode must replace and delete these paths, not wrap or run beside them |
| Native Goal is already available and enabled | `tools/launcher/app_server.py` wraps `thread/goal/get`, `thread/goal/set`, and `thread/goal/clear`; the installed `codex-cli 0.144.6` reports `goals stable true`; Codex source marks `Feature::Goals` stable and enabled by default | BuddySwitch can delegate execution completeness to Codex without inventing another loop or adding a BuddySwitch feature flag |
| Goal terminal/recovery information is queryable | App Server emits global `thread/goal/updated`, and `thread/goal/get` returns objective, status, budgets, token/time usage, and timestamps | Goal notifications can accelerate reconciliation; `goal/get` must remain the recovery truth after daemon restart |
| Web Task projection aborts on old records | `scripts/env/domain/task_read.py::_external_demand_ref` requires `{demand_id,basis_revision,demand_ref}`; `tools/launcher/web_management.py::_actor_console` does not translate projection `ValueError` | Old shared-state records can break the actor-console API instead of returning an explicit rebuild-required error |

### 2.2 Live runtime findings that this plan must fix

The 2026-07-23 test used the official CLI and Web UI with an isolated shared root and created Market actor `act-market-3648b287ab4d`.

| Observation | Evidence from the run | Required correction |
|---|---|---|
| Real Codex rejected the triage schema | The side ended `systemError` with `invalid_json_schema`; the schema's conditional fields were not included in the strict top-level `required` set | Do not use `turn/start.outputSchema` for triage |
| Online failure also remained stuck | Codex 0.144.6 emitted `thread/status/changed`, while the handler expected item/turn terminal notifications; the intake stayed `triaging` | Demand owner must cover failure/retry independently of terminal notification names |
| daemon restart did not recover in-flight triage | The side registry remained open and the intake retained null proposal/result after daemon restart | Add product-neutral handler reconciliation and Demand-owned idempotent attempt recovery |
| A daemon-only outage occurs after accepted work | The inbound had already been accepted and its triage side had started before the daemon stopped | Preserve the side's ability to commit through App Server/runtime broker without daemon availability |
| Default shared state contains retired Task records | Seven Task JSON records under `/Users/chen/.codex-buddyswitch/state/buddyswitch/objects/task-sys/tasks/` contain only `demand_id` and `basis_revision` | Make the cutover require explicit state rebuild; reject any residue clearly and remove it before product acceptance |
| Market delivery did not reach the Web conversation | Track/Artifact metadata existed, but four Market deliveries were absent from the user message session and artifact inspection was not usable | Goal completion criteria and end-to-end tests must prove the requested result is actually delivered/readable, not only stored as metadata |
| The Dev actor's self-demand behavior was not reliably observable | Existing Task flow did not provide a clear, durable demonstration that the actor created and later selected its own new Demand | Preserve direct actor `demand_sys.create`, wake orchestration without converting it into Intake, and prove it while one Goal remains active |

The test actor was stopped. The isolated test root was retained for evidence. The user's default shared state was not mutated.

## 3. Re-evaluation of the proposed “two problems disappear” claim

The original statement was:

> No longer depend on strict output schema, so the current `invalid_json_schema` disappears.
>
> The side persists and commits through the Demand owner immediately after producing a proposal; even if the daemon is offline, the result does not wait for non-replayable `item_completed` / `turn_completed` notification.

### Verdict

The first sentence is correct for the reproduced failure only if triage stops using `turn/start.outputSchema` entirely. It does not mean “no schema can ever fail”: the dedicated MCP tool still needs one flat input schema, which must pass a real App Server/model contract test.

The second sentence is directionally correct but incomplete. It is accepted with these exact conditions:

1. The resolver is injected only into the isolated triage thread. It is not a normal `demand_sys` action and is not listed to the parent Actor.
2. The resolver is a dedicated stdio MCP server configured on that thread through `thread/start.config`.
3. Before starting the side, the host mints a one-side capability, places only its hash in the side lease, and injects the raw token into that side's MCP process.
4. The MCP server calls a runtime-broker application operation with that host-owned, non-model-authored token; the broker resolves and validates the exact actor, side purpose, source, and attempt before invoking the Demand owner transaction.
5. App Server and runtime broker remain alive. If the whole actor instance is offline, inbound is rejected and no side can run.
6. The daemon is not needed for the atomic Demand commit, but it is still needed later to clean the side lease and request parent orchestration.

### What this design really eliminates

- strict final-output schema validation;
- parsing the final assistant message as the authoritative proposal;
- dependency on `item/completed`, `turn/completed`, or `thread/status/changed` to commit the decision;
- loss of an already-issued resolution merely because the daemon was stopped;
- a seventh Actor-facing Demand action.

### What it does not eliminate

- the window after a source is claimed but before its side is started;
- a model turn that ends without calling the resolver;
- malformed future changes to the resolver's ordinary MCP input schema;
- App Server/runtime broker failure;
- automatic redelivery of a new Message whose actor mailbox submission was rejected during an offline/stale-reachability window;
- non-retriable invalid source data or authority failures;
- the need to wake parent orchestration after a Demand change.

The already-accepted ingress cases are handled by the generic daemon reconciliation hook and the Demand-owned receipt state. Therefore, the dedicated side resolver and daemon reconciliation are complementary; neither replaces the other.

The Message itself may already exist in Central IM when actor handling returns `target_not_online` or `handling_failed`; that is a visible rejected delivery, not a pending Demand ingress receipt. Automatic redelivery of rejected new inbound would be a separate Message delivery contract and is not smuggled into this Demand/Goal rebuild.

## 4. Target architecture

### 4.1 Full current-focus path

```text
Source product writes canonical fact
          │
          ├─ actor not online ───────────────> reject inbound; no actor work accepted
          │
          └─ actor online
                 │
                 v
       generic daemon mailbox delivery
                 │
                 v
       durable due-now generic schedule
                 │
                 v
       Demand owner claim(source_key, fact)
       private receipt; no Intake identity
                 │
                 v
       isolated demand-triage side
       + thread-only demand_triage.resolve MCP
       + host-minted one-side capability
       + filtered ordinary env MCP:
         Demand list/get + source Message reads only
                 │
                 v
       runtime broker validates:
       capability + actor + open side lease
       + purpose + source + attempt
                 │
                 v
       Demand owner atomic resolve
          ├─ no_action_needed ──> settle receipt only
          ├─ handled ───────────> verify source-local handling; settle receipt
          ├─ create ────────────> create one canonical Demand
          ├─ merge_intake ──────> merge fact into one live Demand
          ├─ revise ────────────> replace one live Demand's meaning
          └─ cancel ────────────> terminalize one live Demand
                 │
                 v
       canonical Demand mutation increments
       private demand_pool_revision
                 │
                 v
       handler reconcile compares durable revision/cursor
       and requests duplicate-safe parent attention
                 │
                 v
       parent demand-orchestration
       - reconcile terminal Task when present
       - compare all live Demands
       - if any live Demand exists, choose exactly one
                 │
                 v
       minimal Task binding + native Goal on main thread
                 │
                 v
       Codex Goal automatic multi-turn work
          ├─ active ────────────> continue automatically
          ├─ complete ──────────> Task complete
          ├─ blocked/limited ───> Task remains current; expose stopped condition
          └─ clear/cancel ──────> Task canceled
                 │
                 v
       new parent Demand reconciliation/selection turn
```

### 4.2 One owner per truth

| Truth or transition | Single owner | Other layers may do |
|---|---|---|
| Canonical Demand content and terminal state | `scripts/env/domain/demand_sys.py` | Tools, daemon handlers, and Web call/project it |
| Source deduplication and triage attempt state | Private source-keyed receipt inside the Demand aggregate | Handler starts/reconciles work; no Actor API |
| Triage decision application | One Demand owner transaction | Side submits intent once; runtime adapter validates authority |
| Idempotent source-local `handled` reply coordination | `tools/launcher/demand_triage_runtime.py` explicit application operation | Message owner finds/sends the reply; Demand owner only receives verified evidence |
| Durable notification that the canonical Demand pool changed | Private monotonic `demand_pool_revision` in the Demand aggregate | Product handler persists its observed revision cursor; daemon core only invokes reconciliation |
| Side thread identity, purpose, and resolver capability binding | `tools/launcher/side_thread_registry.py` | Demand handler creates/looks up a purpose-bound lease; only the capability hash is persisted |
| Durable trigger timing and handler lifecycle | daemon-service | No Demand or Task business branch in daemon core |
| Current work selection and Demand reconciliation judgment | Parent `$demand-orchestration` skill | Demand/Task tools provide exact operations |
| One Task's binding to one current Demand | minimal Task Sys owner | Web/CLI project it |
| Multi-turn execution completeness | native Codex Goal | BuddySwitch starts, observes, and reconciles it |
| User-facing research/tool delivery | Source product tools such as Message/Artifact/Track | Task objective requires and verifies the delivery |

## 5. Demand model and interfaces

### 5.1 Actor-facing Demand tools remain exactly six

| Actor tool | Actor intent | Host-owned inputs the Actor must not provide |
|---|---|---|
| `list` | Compare live or terminal Demands | storage cursor, read batch, aggregate revision |
| `get` | Read one complete Demand and current opaque ref | storage path, numeric expected revision |
| `create` | Declare a deliberate independent new need | source key, intake id, provenance, idempotency key |
| `revise` | Change the goal, boundary, or constraints | CAS number, receipt state |
| `complete` | Judge that the need itself is satisfied | Task state synchronization |
| `cancel` | Judge that the need was withdrawn or abandoned | terminal record structure |

`merge_intake` is not an Actor tool. It is an inbound-triage decision applied by the Demand owner.

`resolve_ingress` is not an Actor Demand tool. It is a side-only application operation exposed through a dedicated MCP server on one triage thread.

### 5.2 Private source-keyed receipt

The aggregate replaces `intakes` with a private map keyed by the exact source key. There is no `intake_id`, no Intake list/get operation, no Intake projection, and no separate Intake object directory.

Target shape:

```json
{
  "demand_pool_revision": 0,
  "ingress_receipts": {
    "im.message.created:msg-123": {
      "fingerprint": "sha256-of-normalized-source-fact",
      "fact": {
        "description": "compact inbound statement",
        "detail": "full inbound fact",
        "source_refs": [
          {
            "type": "im.message.created",
            "ref": {
              "message_id": "msg-123",
              "conversation_id": "conv-123",
              "event_id": "event-123"
            }
          }
        ]
      },
      "state": "pending",
      "attempt_id": null,
      "outcome": null,
      "last_failure": null,
      "created_at": "2026-07-23T00:00:00Z",
      "updated_at": "2026-07-23T00:00:00Z"
    }
  }
}
```

`demand_pool_revision` is private aggregate metadata, not a Demand field or Actor argument. The Demand owner increments it in the same locked transaction whenever canonical Demand state changes through `create`, `merge_intake`, `revise`, `complete`, or `cancel`. Receipt-only transitions, retries, `no_action_needed`, and `handled` do not increment it.

The Demand handler persists an observed revision cursor in its own daemon handler state. Reconciliation compares the two values:

- if no Task is active and the main thread is idle, it submits one purpose-keyed parent attention turn and advances the cursor only after App Server accepts that turn;
- it never submits a concurrent parent turn; a crash around `turn/start` may cause a later sequential duplicate, so every attention turn must re-read current Task/Demand truth before acting;
- if a Task is active, it records the revision as deferred; Task/Goal terminal reconciliation later re-reads the entire live pool;
- if the daemon was offline during the mutation, the higher aggregate revision remains discoverable at startup;
- duplicate attention is harmless because the parent always re-reads the one active Task invariant and current live Demands before selecting.

This is a durable change signal, not another queue, event bus, or business rule in daemon core.

Allowed receipt states:

- `pending`: accepted source fact needs a side attempt;
- `resolving`: exactly one current attempt owns resolution;
- `settled`: one business decision was atomically applied;
- `failed`: the source cannot be safely resolved without external correction.

Failure rules:

- model error, App Server error, missing resolver call, stale Demand ref, daemon interruption, and orphaned side lease are retriable; record `last_failure`, return to `pending`, and issue a new attempt later;
- source fingerprint collision, invalid authority, missing canonical source after validation, or permanently invalid source payload may become `failed`;
- `failed` is terminal for the receipt, not for any Demand;
- Demand lifecycle remains only live, completed, or canceled.

This gives failure a useful role: it stops silent infinite retry and makes the broken source visible to diagnostics. It does not create a “failed Demand.”

### 5.3 Internal Demand owner operations

These are Python application operations, not Actor tools:

```python
claim_ingress(actor_target, source_key, description, detail, source_refs)
get_ingress_receipt(actor_target, source_key)
list_unsettled_ingress(actor_target)
begin_ingress_resolution(actor_target, source_key)
resolve_ingress(actor_target, source_key, attempt_id, proposal, handled_verified)
fail_ingress_resolution(actor_target, source_key, attempt_id, failure, retriable)
```

`resolve_ingress` performs one locked aggregate transaction:

1. validate source key, fingerprint, state, and attempt;
2. validate the proposal's exact decision-dependent fields;
3. validate any opaque Demand ref against current revision and live state;
4. verify `handled` evidence when applicable;
5. apply no change, create, merge, revise, or cancel;
6. settle the receipt with a compact idempotent outcome;
7. increment `demand_pool_revision` if and only if canonical Demand state changed;
8. return the settled outcome and resulting pool revision.

No adapter may reimplement these rules.

### 5.4 Decision semantics

| Decision | Demand effect | Side may finish immediately? | Required evidence/context |
|---|---|---:|---|
| `no_action_needed` | none | yes | concrete reason the fact needs neither response nor durable Demand |
| `handled` | none | yes | reply content for the source IM message; runtime returns an existing matching reply or sends once through Message owner, then supplies verified evidence to Demand owner |
| `create` | one new independent Demand | yes | self-contained description/detail preserving response/deliverable obligations |
| `merge_intake` | merge source refs and updated meaning into one live Demand | yes | current opaque Demand ref and replacement canonical description/detail |
| `revise` | change the goal/boundary/constraints of one live Demand | yes | current opaque Demand ref and reason |
| `cancel` | cancel one live Demand | yes | current opaque Demand ref and reason tied to the inbound fact |

There is no `absorb`, `absorb_into`, `keep_independent`, or parent-judgment branch:

- a still-independent need uses `create`;
- a supplemental fact uses `merge_intake`;
- the triage side receives enough live-Demand context to decide;
- unsafe or stale decisions are rejected by the owner and retried, not escalated through a second parent decision path.

### 5.5 Actor-created Demand

An Actor calling `demand_sys.create` has already made the semantic decision that an independent durable need exists. Therefore:

- it bypasses source ingress and does not create an ingress receipt;
- host-derived thread/turn provenance and idempotency remain in `actor_creation_receipts`;
- it produces the same canonical Demand shape as inbound `create`;
- it increments the same durable `demand_pool_revision`; orchestration defers selection without creating a Task while another Task/Goal is active;
- it is a required acceptance path for the Dev actor self-demand scenario.

## 6. Side-only resolver design

### 6.1 Why not a normal env tool

Adding `resolve` to `scripts/env/tools/demand_sys/tool.py` would cause `native_mcp.list_native_tool_specs()` to list it to every parent and side. Authorization after the call is too late: the Actor would still see and reason about a low-level operation.

### 6.2 Why not App Server dynamic tools

Codex dynamic tools are thread-scoped, but `item/tool/call` is sent to subscribed App Server client connections. BuddySwitch currently opens short-lived helper connections for `thread/start` and `turn/start`. Keeping the instance daemon subscribed would make the resolver dependent on daemon liveness again.

Dynamic tools can remain available for other use cases, but they are not the accepted implementation for durable Demand triage.

### 6.3 Accepted resolver

Create a dedicated stdio MCP server:

```text
tools/launcher/demand_triage_mcp_server.py
```

It exposes one tool:

```text
demand_triage.resolve
```

The tool input deliberately avoids conditional JSON Schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "decision",
    "reason",
    "demand_ref",
    "description",
    "detail",
    "reply_content"
  ],
  "properties": {
    "decision": {
      "type": "string",
      "enum": [
        "no_action_needed",
        "handled",
        "create",
        "merge_intake",
        "revise",
        "cancel"
      ]
    },
    "reason": {"type": "string"},
    "demand_ref": {"type": ["string", "null"]},
    "description": {"type": ["string", "null"]},
    "detail": {"type": ["string", "null"]},
    "reply_content": {"type": ["string", "null"]}
  }
}
```

All fields are structurally required and non-applicable values are `null`; the Demand owner enforces the decision-dependent semantic rules. This is ordinary MCP tool input, not `turn/start.outputSchema`, and there is no final-message JSON parser.

The server is added only to the triage thread through a `thread/start.config` override such as:

```json
{
  "mcp_servers.buddyswitch-demand-triage": {
    "command": "/absolute/path/to/python",
    "args": [
      "/absolute/path/to/demand_triage_mcp_server.py",
      "--broker-socket",
      "/absolute/runtime/broker.sock"
    ],
    "env": {
      "BUDDYSWITCH_DEMAND_TRIAGE_CAPABILITY": "host-minted-random-token"
    }
  },
  "mcp_servers.buddyswitch-env.enabled_tools": [
    "demand_sys__list",
    "demand_sys__get",
    "message__get",
    "message__conversation"
  ]
}
```

The host mints the random capability before `thread/start`, stores only its hash with the side lease after `thread/start` returns, and registers that lease before `turn/start`. If thread creation or lease registration fails, the capability is discarded. These values are host-authored process configuration, not proposal fields the model may choose. This is an application-authority boundary consistent with BuddySwitch's existing local same-user runtime; it is not claimed as a hostile local-process security sandbox.

The MCP server forwards:

```text
method: demand.ingress.resolve
params:
  capability
  proposal
```

The runtime adapter validates:

1. the capability hashes to exactly one open side lease;
2. the lease belongs to the active instance and role;
3. lease parent equals the actor main thread;
4. lease purpose contains the exact Demand triage source key and attempt id;
5. that source receipt is still `resolving` under the same attempt;
6. the capability has not been revoked, replaced, or bound to another side.

Only then does it call `demand_sys.resolve_ingress`. After the owner commits, the runtime adapter marks the capability consumed in the side lease immediately; daemon cleanup of the side thread may happen later. A crash between those writes is safe: the next identical call receives the already-settled idempotent outcome and consumes the capability without another Demand mutation. MCP itself does not supply trustworthy thread/turn metadata, so the design does not pretend otherwise.

The ordinary `buddyswitch-env` server implementation remains unchanged. On the triage thread, Codex's thread config allow-lists only the two Demand reads and source Message reads shown above; no Demand mutation, Task tool, unrelated product tool, or raw `message__send` is visible there. On the parent Actor thread, the ordinary catalog still exposes exactly the six Demand intents.

For `handled`, the dedicated runtime owns the explicit cross-product operation:

1. validate the source is an IM message addressed to this actor;
2. search through the Message owner for an actor reply whose `reply_to` is the exact source message;
3. reuse that reply if one already exists; otherwise send the proposed reply content once through the Message owner;
4. verify message id, sender, recipient, conversation, and `reply_to`;
5. call the Demand owner with `handled_verified` evidence and settle the receipt;
6. on a crash after Message write but before Demand settle, retry finds and reuses the existing reply instead of sending another.

The Demand domain does not import Message storage or reproduce Message rules.

## 7. Product-neutral daemon capability

daemon-service must not know about Demand, Task, Intake, Goal, or source-specific business rules.

Add one optional handler lifecycle capability:

```python
class DaemonReconciler(Protocol):
    def reconcile(
        self,
        context: DaemonContext,
        state: Any,
        runtime: Any,
        reason: str,
    ) -> HandlerResult | dict[str, Any]:
        ...
```

The daemon core invokes it:

- once after App Server binding, mailbox start, and Central daemon registration;
- on the existing bounded timeout/heartbeat cycle;
- after a future real App Server reconnect if the daemon later gains an internal reconnect loop.

The current implementation does not have an App Server reconnect loop. This plan does not add one unless a failing test proves it is required. Process restart plus startup reconciliation is the current recovery boundary.

The core only:

- calls the optional method;
- records result/error metadata;
- keeps the call bounded;
- continues serving other handlers after one handler failure.

Product handlers decide what durable state needs repair.

Demand triage reconciliation performs:

- start a side for `pending`;
- restart `resolving` when no exact side lease exists;
- leave an active matching side alone;
- reset/retry when the side is idle, failed, missing, or ended without a settled receipt;
- clean a lease for `settled` or non-retriable `failed`;
- compare canonical `demand_pool_revision` with its persisted observed/deferred cursor and request purpose-keyed parent orchestration after a canonical Demand change;
- never parse an assistant final message.

Goal reconciliation later performs:

- `goal/get` for the actor main thread;
- restore a missing active Goal from one active Task binding;
- complete/cancel the Task from a matching terminal Goal snapshot;
- trigger parent Demand reconciliation after Task terminalization.

This hook has general daemon-service value because any durable product handler can repair its own interrupted work without daemon core importing product semantics.

## 8. Goal-mode Task model

### 8.1 Current scope

- many live Demands are supported;
- at most one active Task is supported;
- the active Task binds to exactly one Demand;
- at most one native Goal is active on the actor main thread;
- multi-Demand-to-one-Task and multi-thread parallel execution remain future work.

The one-Task/one-Demand constraint is a current product invariant, not a statement that Demand and Task completion are semantically coupled.

### 8.2 Completion remains decoupled

- Goal `complete` means the Task execution objective completed.
- Task `completed` records that Goal outcome.
- Demand remains live until the parent Actor judges its current need satisfied.
- One Task may complete while its Demand is revised or remains live.
- A later Task may be created for the same still-live Demand.

### 8.3 Selection invariant

- If one Task is active, select nothing else.
- If no Task is active and one or more live Demands exist, the parent orchestration turn must select exactly one and record why it won over the other candidates.
- If no live Demand exists, creating no Task is the only legal no-selection result and needs no separate journal.
- If selected work cannot currently progress, its native Goal becomes `blocked`; BuddySwitch does not add a parallel “deferred Demand” scheduler state.

This removes the current underspecified “choose at most one by judgment” branch without adding another orchestration tool or state owner.

### 8.4 Minimal Task record

Target record:

```json
{
  "schema_version": 1,
  "id": "task-123",
  "actor_target": {
    "actor_id": "act-market-123",
    "role_id": "market"
  },
  "demand_ref": {
    "demand_id": "demand-123",
    "basis_revision": 2,
    "demand_ref": "dref-opaque"
  },
  "objective": "self-contained Goal objective",
  "selection": {
    "reason": "why this Demand is current work",
    "selected_at": "2026-07-23T00:00:00Z"
  },
  "goal_binding": {
    "thread_id": "main-thread-id",
    "objective_hash": "sha256",
    "created_at": 1780000000
  },
  "status": "active",
  "result": null,
  "created_at": "2026-07-23T00:00:00Z",
  "updated_at": "2026-07-23T00:00:00Z"
}
```

Allowed Task statuses:

- `active`;
- `completed`;
- `canceled`.

There is no Task-side, awaiting-parent, parent-processing, progress-check-pending, recoverable-side-failure, handoff, frame, or outcome-frame state.

For a completed Task, `result` is host-authored terminal evidence only: the matching Goal status/snapshot, objective hash, completion time, and usage counters returned by `goal/get`. It is not an Actor-authored outcome frame and does not claim that the Demand is satisfied. User-visible Message/Artifact/Track references remain in their owning products; the new parent turn reads the main-thread history and those canonical products when judging the Demand.

The Task may be `active` before `goal_binding` is filled if the process stops between the Task write and `goal/set`. Startup reconciliation completes that binding. This is the only required cross-owner recovery window.

### 8.5 Goal status mapping

| Native Goal status/event | Task effect | Demand/selection effect |
|---|---|---|
| `active` | remain `active` | select no other Demand |
| `complete` | atomically record `completed` with Goal terminal snapshot | start a new parent Demand reconciliation/selection turn |
| `blocked` | remain `active`; project stopped condition | no new Task; wait for explicit resume/cancel or new user input |
| `usageLimited` | remain `active`; project stopped condition | no new Task |
| `budgetLimited` | remain `active`; project stopped condition | no new Task |
| `paused` | remain `active`; project stopped condition | no new Task |
| `thread/goal/cleared` | cancel the matching active Task unless cancellation already owns the clear | start parent reconciliation; Demand is not automatically canceled |

Only Goal `complete` completes a Task.

### 8.6 Goal objective

The parent orchestration turn creates one self-contained objective containing:

- Task id and selected Demand id/ref;
- the current Demand description, detail, source refs, and selection reason;
- exact deliverables and completion checks;
- the requirement to send requested user-facing results back through the source conversation before completion;
- the rule that the Goal must not decide Demand completion or select the next Demand;
- the rule to use native `update_goal(status="complete")` only when all Task work and delivery evidence are complete.

`thread/goal/set(status="active")` starts or resumes automatic Goal work. Codex Goal is the only continuation engine.

### 8.7 Task tools after cutover

The current Actor Task surface becomes:

- `task_sys.list`;
- `task_sys.get`;
- `task_sys.create` for `$demand-orchestration`;
- `task_sys.cancel`.

Remove:

- `task_sys.close`;
- `task_sys.need_parent`.

Task completion is host-owned from native Goal terminal state. The Actor does not manually close Task Sys.

## 9. Skill ownership after cutover

### `$demand-triage`

Runs only on an isolated triage side.

It:

- reads the exact inbound fact;
- compares all live Demands through only `demand_sys.list` and `demand_sys.get`;
- proposes source-local reply content through `handled` when appropriate; the dedicated runtime owns idempotent Message delivery;
- calls the thread-only `demand_triage.resolve`;
- does not create Task work or request parent judgment.

### `$demand-orchestration`

Runs only in the actor parent/main thread.

It:

1. reconciles a terminal Task with its latest Demand;
2. completes, cancels, revises, or leaves that Demand live;
3. checks for an active Task;
4. compares all live Demands when no Task is active;
5. selects exactly one when any live Demand exists, otherwise creates no Task;
6. rereads the selected Demand;
7. calls `task_sys.create` with a self-contained Goal objective and selection reason.

### `$task-management`

Delete it in Goal-mode cutover.

Native Goal instructions own continuation and completion discipline. Keeping `task-management` would teach the retired frame/progress-check path and create a product dual track.

## 10. Three implementation phases

The phases are validation boundaries, not compatibility releases. Each phase leaves one implementation in the branch. Phase 1 is not a merge/release candidate while old Task execution remains; Phase 2 deletes that executor before the branch can be accepted. The final shared-state cutover occurs once, after all phases pass.

### Phase 1 — Demand ingress owns triage truth

Outcome:

- no first-class Intake;
- no strict turn output schema;
- no terminal-notification dependency;
- side-only direct resolver;
- daemon handler reconciliation;
- six Actor Demand tools unchanged;
- existing Task execution may be used only until Phase 2 replaces it on the same branch.

### Phase 2 — native Goal owns Task execution

Outcome:

- one minimal Task binding;
- one active Goal on main thread;
- Goal completion records Task completion;
- new parent turn reconciles/selects;
- Task frames, side execution, progress checks, outcome frames, and `task-management` are deleted.

### Phase 3 — whole-product cutover and proof

Outcome:

- Web/CLI project the new Task/Demand truth;
- old runtime state is explicitly rebuilt;
- Market and Dev scenarios pass;
- daemon outage recovery passes;
- Market results are readable in the message/product surface;
- residue scans and final full suite pass.

## 11. Phase 1 implementation tasks

### Task 1: Replace Intake with the private ingress receipt

**Files:**

- Modify: `scripts/env/repos/demands.py`
- Modify: `scripts/env/domain/demand_sys.py`
- Rename/Delete: `tests/unit/demand_sys/test_intake_triage.py`
- Create: `tests/unit/demand_sys/test_ingress_resolution.py`
- Modify: `tests/integration/demand_sys/test_repository_atomicity.py`
- Modify: `tests/unit/architecture/test_demand_sys_boundaries.py`

- [ ] Write failing tests that assert a fresh aggregate contains `demand_pool_revision = 0` and `ingress_receipts`, and does not contain `intakes`.
- [ ] Write failing tests for idempotent `claim_ingress`: the same source key plus identical fingerprint returns the existing receipt; the same key plus different fact raises `E_DEMAND_INGRESS_CONFLICT`.
- [ ] Write failing tests for `pending -> resolving` with exactly one attempt id.
- [ ] Write one test for each decision: `no_action_needed`, `handled`, `create`, `merge_intake`, `revise`, `cancel`.
- [ ] Write tests proving `resolve_ingress` changes receipt and Demand in one aggregate write.
- [ ] Write tests proving every canonical Demand mutation increments `demand_pool_revision` in the same write, while receipt-only/no-action/handled transitions do not.
- [ ] Write tests proving a duplicate successful resolve returns the stored outcome without another Demand revision.
- [ ] Write tests proving a stale opaque Demand ref is rejected without partial Demand mutation and leaves the receipt retryable.
- [ ] Write tests for retriable failure returning to `pending` with `last_failure`.
- [ ] Write tests for non-retriable failure entering receipt `failed` without creating a Demand.
- [ ] Implement the new aggregate schema and internal operations.
- [ ] Delete `_INTAKE_FIELDS`, `_INTAKE_STATUSES`, `capture_intake`, `get_intake`, `begin_triage`, `record_triage_proposal`, `retry_triage`, `apply_triage_proposal`, and `intake-*` identity generation.
- [ ] Keep `normalize_triage_proposal` only as an internal ingress-resolution validator, renamed to match the new owner language.
- [ ] Run:

```bash
./buddyswitch-test focused tests/unit/demand_sys/test_ingress_resolution.py tests/integration/demand_sys/test_repository_atomicity.py tests/unit/architecture/test_demand_sys_boundaries.py
```

Expected: all selected tests pass; residue assertion proves `intakes` and `intake_id` are absent from the live aggregate and domain API.

### Task 2: Add the triage-thread-only resolver

**Files:**

- Create: `tools/launcher/demand_triage_mcp_server.py`
- Create: `tools/launcher/demand_triage_runtime.py`
- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/side_thread_lifecycle.py`
- Modify: `tools/launcher/actor_side_thread.py`
- Modify: `tools/launcher/side_thread_registry.py`
- Modify: `tools/launcher/demand_triage_handler.py`
- Create: `tests/unit/demand_sys/test_triage_mcp_server.py`
- Modify: `tests/integration/runtime_broker/test_broker.py`
- Modify: `tests/integration/app_server/test_client.py`
- Modify: `tests/integration/actor/test_side_thread_lifecycle.py`
- Modify: `tests/integration/demand_sys/test_side_triage_flow.py`
- Modify: `tests/unit/env_tool/test_native_mcp_server.py`
- Modify: `tests/process/cli/test_env_native_mcp_projection.py`

- [ ] Write a failing MCP protocol test proving the dedicated server lists exactly one `resolve` tool with the flat required/nullable schema above and no conditional keywords.
- [ ] Write a failing App Server client test for arbitrary thread config overrides.
- [ ] Write a failing side lifecycle test proving the Demand resolver MCP config is attached only to the triage side and augments rather than replaces the ordinary environment MCP server.
- [ ] Write a real tool-list test proving the triage thread sees only `demand_sys__list`, `demand_sys__get`, `message__get`, `message__conversation`, and the dedicated resolver; it must not see `message__send`, Demand mutations, Task tools, or unrelated product tools.
- [ ] Write failing runtime tests for missing/unknown/reused capability, wrong actor, parent thread, side thread, purpose, source key, and attempt id.
- [ ] Write a side lifecycle test proving the capability hash is registered before `turn/start`, the raw token is never persisted, and failed startup revokes/discards it.
- [ ] Write `handled` tests proving the runtime reuses an existing exact `reply_to` Message or sends one through the Message owner before passing verified evidence; forged evidence must be impossible for the side to supply.
- [ ] Write the crash-window test “Message reply persisted, Demand receipt not yet settled,” then prove retry reuses that reply and does not send a duplicate.
- [ ] Write a crash-window test proving an owner-settled receipt plus still-open capability returns the stored outcome, consumes the capability, and does not mutate the Demand twice.
- [ ] Write a failing integration test proving a valid side call reaches the Demand owner and settles the receipt.
- [ ] Write a real App Server/model contract test proving the resolver tool schema is accepted and callable while no `turn/start.outputSchema` is supplied.
- [ ] Write a negative tool-catalog test proving the parent `buddyswitch-env` catalog still exposes only the six Demand actions and never exposes `resolve_ingress` or `demand_triage.resolve`.
- [ ] Implement the dedicated MCP server and runtime adapter.
- [ ] Extend `app_server.thread_start` and side lifecycle with host-owned thread config overrides.
- [ ] Add a generic side-registry lookup by exact purpose; do not add Demand branches to `side_thread_registry.py`.
- [ ] Remove `TRIAGE_OUTPUT_SCHEMA` and stop passing `output_schema` from Demand triage.
- [ ] Change the prompt from “return JSON” to “call `demand_triage.resolve` before ending.”
- [ ] Run:

```bash
./buddyswitch-test focused tests/unit/demand_sys/test_triage_mcp_server.py tests/integration/runtime_broker/test_broker.py tests/integration/app_server/test_client.py tests/integration/actor/test_side_thread_lifecycle.py tests/integration/demand_sys/test_side_triage_flow.py tests/unit/env_tool/test_native_mcp_server.py tests/process/cli/test_env_native_mcp_projection.py
```

Expected: the side resolves through the owner, parent tool listing is unchanged, and no test supplies `turn/start.outputSchema`.

### Task 3: Add generic handler reconciliation and remove notification ownership

**Files:**

- Modify: `tools/launcher/daemon_contracts.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/daemon_state.py`
- Modify: `tools/launcher/demand_triage_handler.py`
- Modify: `tools/launcher/instance_daemon.py`
- Modify: `tests/unit/daemon/test_core.py`
- Modify: `tests/integration/daemon/test_core_runtime.py`
- Modify: `tests/unit/daemon/test_instance_entrypoint.py`
- Modify: `tests/integration/demand_sys/test_side_triage_flow.py`

- [ ] Write a failing daemon-core test proving `reconcile` is invoked after registration and during bounded timeout polling.
- [ ] Write a failing isolation test proving one handler reconciliation error is recorded and does not stop other handlers.
- [ ] Write a failing Demand flow test for process death after `begin_ingress_resolution` but before side registration.
- [ ] Write a failing test for an open side ending without resolver call.
- [ ] Write a failing test for a settled receipt with a higher `demand_pool_revision` while daemon is stopped, followed by cursor recovery, cleanup, and purpose-keyed parent attention after daemon restart.
- [ ] Write a failing duplicate-reconcile test proving the observed/deferred revision cursor does not produce concurrent parent turns and that a possible sequential repeat re-reads the one-active-Task invariant safely.
- [ ] Write a failing test for `systemError` side status becoming retriable without item/turn terminal notifications.
- [ ] Implement the optional generic reconciliation contract and result telemetry.
- [ ] Implement Demand reconciliation only in `DemandTriageHandler`.
- [ ] Remove item-completed and turn-completed handling, proposal-message parsing, and their constants/subscriptions from Demand triage.
- [ ] Keep generic durable scheduled-trigger sweeping unchanged.
- [ ] Run:

```bash
./buddyswitch-test focused tests/unit/daemon/test_core.py tests/integration/daemon/test_core_runtime.py tests/unit/daemon/test_instance_entrypoint.py tests/integration/demand_sys/test_side_triage_flow.py
```

Expected: recovery passes without replaying an App Server terminal notification.

### Task 4: Cut Phase 1 tools, skills, and architecture to one path

**Files:**

- Modify: `scripts/env/tools/demand_sys/tool.py`
- Modify: `scripts/env/tools/demand_sys/_impl.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `buddyswitch/skills/shared/demand-triage/SKILL.md`
- Modify: `buddyswitch/skills/shared/demand-orchestration/SKILL.md`
- Modify: `buddyswitch/manifest.toml`
- Modify: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `tests/integration/env_tool/test_response_demand.py`
- Modify: `tests/unit/actor/test_role_action_auth.py`
- Modify: `tests/unit/actor/test_runtime_skills.py`
- Modify: `tests/unit/architecture/test_tool_runtime_contract.py`

- [ ] Write/retain tests proving the Actor Demand action set is exactly `{list,get,create,revise,complete,cancel}`.
- [ ] Write a direct Actor `create` test proving no ingress receipt is created.
- [ ] Write an attention test proving Actor-created Demand increments `demand_pool_revision` and waits while one Task is active.
- [ ] Update `$demand-triage` to use the side-only resolver and remove final-JSON instructions.
- [ ] Update `$demand-orchestration` only enough to consume Phase 1 Demand attention; Phase 2 will replace its Task instructions.
- [ ] Rewrite current architecture docs to describe source-keyed receipt and generic reconciliation.
- [ ] Remove all live current-doc references to Intake as a product object.
- [ ] Run:

```bash
./buddyswitch-test focused tests/integration/env_tool/test_response_demand.py tests/unit/actor/test_role_action_auth.py tests/unit/actor/test_runtime_skills.py tests/unit/architecture/test_tool_runtime_contract.py
```

Expected: six Actor actions, direct self-demand, and no live guidance teaching first-class Intake.

## 12. Phase 2 implementation tasks

### Task 5: Prove the native Goal contract at the real boundary

**Files:**

- Modify: `tests/integration/app_server/test_client.py`
- Create: `tests/system/goal_mode/test_native_goal_contract.py`
- Modify if required by proof only: `tools/launcher/app_server.py`

- [ ] Write a protocol test for `goal_set`, `goal_get`, and `goal_clear` payload/response handling.
- [ ] Assert the repository-pinned/runtime-selected Codex reports Goals enabled; do not add a BuddySwitch feature flag or alternate executor.
- [ ] Write a real App Server test using the repository-pinned Codex binary proving `goal/set(status=active)` starts idle work on a persistent main thread.
- [ ] Prove an active Goal automatically starts another turn when the previous turn ends without Goal completion.
- [ ] Prove `update_goal(complete)` produces `thread/goal/updated` with status `complete`.
- [ ] Prove `goal/get` returns the complete snapshot after disconnect/reconnect of the observing client.
- [ ] Prove a turn error produces a non-complete stopped state and is recoverable through `goal/get`.
- [ ] Run:

```bash
./buddyswitch-test focused tests/integration/app_server/test_client.py tests/system/goal_mode/test_native_goal_contract.py
```

Expected: the installed Codex runtime, not a guessed mock contract, proves continuation, terminal notification, and query recovery.

Stop Phase 2 if this proof fails. Report the exact Codex/App Server capability gap before changing Task Sys. Current Codex source indicates the contract is supported, but runtime proof is the gate.

### Task 6: Replace Task frames with the minimal Goal binding

**Files:**

- Replace: `scripts/env/domain/task_sys.py`
- Modify: `scripts/env/domain/task_read.py`
- Modify: `scripts/env/tools/task_sys/tool.py`
- Modify: `scripts/env/tools/task_sys/_impl.py`
- Create: `tools/launcher/task_goal_runtime.py`
- Replace/Delete: `tests/integration/task_sys/test_actor_create.py`
- Delete/Replace: `tests/integration/task_sys/test_side_processing.py`
- Delete/Replace: `tests/integration/task_sys/test_progress_check.py`
- Replace: `tests/integration/task_sys/test_substrate.py`
- Replace: `tests/integration/env_tool/test_response_task.py`
- Modify: `tests/unit/architecture/test_task_sys_boundaries.py`
- Modify: `tests/unit/architecture/test_tool_runtime_contract.py`

- [ ] Write a new Task schema test with only `active`, `completed`, and `canceled`.
- [ ] Write a one-active-Task invariant test.
- [ ] Write a Task-create test requiring one current opaque Demand ref, a self-contained objective, and a selection reason.
- [ ] Write a recovery test for active Task written before `goal/set`.
- [ ] Write a Goal-complete-to-Task-completed test using exact objective hash and main thread.
- [ ] Write a result-shape test proving Task completion stores only the matching host-authored Goal terminal snapshot and never an Actor-authored outcome frame or automatic Demand disposition.
- [ ] Write tests proving blocked/paused/limited Goal states do not complete Task and do not permit another Task.
- [ ] Write a Task-cancel test that clears the matching Goal and leaves Demand unchanged.
- [ ] Implement the minimal Task owner and Goal runtime adapter.
- [ ] Reduce Actor Task tools to `list`, `get`, `create`, `cancel`.
- [ ] Delete close/need-parent operations and every side/parent execution field.
- [ ] Run:

```bash
./buddyswitch-test focused tests/integration/task_sys/test_actor_create.py tests/integration/task_sys/test_substrate.py tests/integration/env_tool/test_response_task.py tests/unit/architecture/test_task_sys_boundaries.py tests/unit/architecture/test_tool_runtime_contract.py
```

Expected: one active minimal Task starts one native Goal; no frame-state assertion remains.

### Task 7: Reconcile Goal terminal state and start a new parent turn

**Files:**

- Create: `tools/launcher/task_goal_handler.py`
- Modify: `tools/launcher/instance_daemon.py`
- Delete: `tools/launcher/task_sys_runtime.py`
- Delete: `tools/launcher/task_sys_daemon_adapter.py`
- Modify: `tools/launcher/daemon_core.py` only if the generic hook needs a proven correction
- Create: `tests/integration/goal_mode/test_task_goal_reconciliation.py`
- Modify: `tests/unit/daemon/test_instance_entrypoint.py`
- Delete/Replace: `tests/unit/task_sys/test_runtime_executor.py`

- [ ] Write a failing test for matching main-thread Goal `complete` recording Task result exactly once.
- [ ] Write a failing test proving the handler starts a new parent turn after Task completion, not in the completing Goal turn.
- [ ] Write a failing test proving Demand is not automatically completed.
- [ ] Write a failing test proving no next Demand is selected while Goal is active or stopped-but-not-complete.
- [ ] Write a startup reconciliation test where Goal completed while daemon was offline.
- [ ] Write a duplicate notification + startup reconciliation test proving only one Task terminal transition and one pending parent attention.
- [ ] Implement the Goal handler using notification as acceleration and `goal/get` as recovery truth.
- [ ] Delete Task application-command factories for side cleanup/progress check.
- [ ] Delete Task side-thread startup, parent handoff, outcome frame, and progress-check runtime.
- [ ] Run:

```bash
./buddyswitch-test focused tests/integration/goal_mode/test_task_goal_reconciliation.py tests/unit/daemon/test_instance_entrypoint.py
```

Expected: Goal completion yields Task completion plus one independent parent reconciliation turn; Task frames are absent.

### Task 8: Replace skills and current architecture guidance

**Files:**

- Modify: `buddyswitch/skills/shared/demand-orchestration/SKILL.md`
- Delete: `buddyswitch/skills/shared/task-management/SKILL.md`
- Modify: `buddyswitch/manifest.toml`
- Rewrite: `docs/arch/task-sys-architecture.md`
- Modify: `docs/arch/demand-sys-architecture.md`
- Modify: `docs/arch/daemon-service-architecture.md`
- Modify: `tests/unit/architecture/test_task_management_skill.py`
- Modify: `tests/unit/actor/test_runtime_skills.py`
- Modify: `tests/unit/architecture/test_task_sys_boundaries.py`

- [ ] Replace Task-management skill tests with negative residue assertions.
- [ ] Update `$demand-orchestration` to reconcile Task/Goal terminal state and select exactly one live Demand when the Task slot is empty and the pool is non-empty.
- [ ] Require every Task creation to record its selection reason and completion/delivery target.
- [ ] Teach that no-selection is legal only when no live Demand exists; blocked work belongs to the selected Goal.
- [ ] Delete `task-management` from manifest and runtime skill projections.
- [ ] Rewrite Task architecture around minimal binding and native Goal.
- [ ] Run:

```bash
./buddyswitch-test focused tests/unit/architecture/test_task_management_skill.py tests/unit/actor/test_runtime_skills.py tests/unit/architecture/test_task_sys_boundaries.py
```

Expected: active guidance contains no frame, Progress Check, `need_parent`, or `outcome_frame`.

## 13. Phase 3 implementation tasks

### Task 9: Harden Web/CLI projections and perform the explicit rebuild cutover

**Files:**

- Modify: `scripts/env/domain/task_read.py`
- Modify: `scripts/env/domain/demand_read.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/integration/im/test_external_query.py`
- Modify: `tests/integration/web/test_management_product_api.py`
- Modify: `tests/process/launcher/test_public_cli.py`
- Modify: `tests/process/cli/test_clean_runtime_environment.py`

- [ ] Write Web and CLI projection tests for the new minimal Task and Demand shapes.
- [ ] Write a malformed/retired Task record test proving Web returns one stable explicit `REBUILD_REQUIRED` product error rather than aborting the HTTP handler.
- [ ] Do not add a fallback parser for `{demand_id,basis_revision}`.
- [ ] Add a residue test proving the old Task shape is rejected.
- [ ] Use an isolated shared root to prove a clean product start creates only the new schemas.
- [ ] Freeze code changes before touching the user's default shared state.
- [ ] Stop all BuddySwitch actors and browser runtimes before cutover.
- [ ] Preview the existing public cleanup command for the chosen scope.
- [ ] Obtain explicit user authorization immediately before destructive cleanup of the default shared state.
- [ ] Execute the approved existing cleanup/rebuild operation; do not add a migration command or copy old records forward.
- [ ] Start fresh actors and prove no old Task or Intake record remains.
- [ ] Run:

```bash
./buddyswitch-test focused tests/integration/im/test_external_query.py tests/integration/web/test_management_product_api.py tests/process/launcher/test_public_cli.py tests/process/cli/test_clean_runtime_environment.py
```

Expected: current records project correctly, retired records fail clearly, and the rebuilt root contains one current schema only.

The exact cleanup scope is an operational choice made at execution time because it is destructive. The architectural requirement is fixed: no old records remain readable or writable after acceptance.

### Task 10: Prove the complete Market, Dev, and outage loops

**Files:**

- Create: `tests/system/demand_goal_mode/test_product_flow.py`
- Modify: `tests/integration/demand_sys/test_side_triage_flow.py`
- Modify: `tests/integration/goal_mode/test_task_goal_reconciliation.py`
- Modify only when a real defect is reproduced: the owning source file and nearest regression test

#### Market scenario

- [ ] Start Web through `./buddyswitch-codex web` on an isolated clean shared root.
- [ ] Create one Market actor through the Web API/UI.
- [ ] Send four AI-market research facts:
  - independent question A;
  - independent question B;
  - supplemental question A2 that must `merge_intake` into A;
  - supplemental question B2 that must `merge_intake` into B.
- [ ] Assert two canonical live Demands, each carrying both relevant source refs; assert no separate supplemental Demand and no relation-edge object.
- [ ] Assert only one active Task/Goal while the second Demand waits.
- [ ] Let Goal A complete and assert a new parent reconciliation turn selects B only after reconciling A.
- [ ] Assert the research result is returned to the originating Web message conversation.
- [ ] Assert any referenced Artifact is readable through the actual Web/CLI consumer surface, not only visible as metadata.

#### Dev scenario

- [ ] Create one Dev actor and request a simple schedule-management tool.
- [ ] During the active Goal, require the actor to identify at least one genuinely independent improvement and call `demand_sys.create` for itself.
- [ ] Assert the self-created Demand has actor thread/turn provenance and no ingress receipt.
- [ ] Assert it waits while the original Task/Goal remains active.
- [ ] Assert original Goal completion causes Demand reconciliation and selects exactly one waiting self-demand when it is the only live candidate.
- [ ] Exercise create/edit/delete schedule behavior in a browser and treat the delete confirmation as expected application behavior, not BuddySwitch task completion evidence.

#### daemon outage scenario

- [ ] Send an inbound fact and wait until the receipt is `resolving` with an exact side lease.
- [ ] Stop only the instance daemon; keep App Server and runtime broker alive.
- [ ] Let the side call `demand_triage.resolve`.
- [ ] Assert the receipt settles and canonical Demand state changes while the daemon is offline.
- [ ] Restart the daemon.
- [ ] Assert reconciliation cleans the side lease and starts no concurrent duplicate attention; any sequential replay must be a no-op after re-reading current Task/Demand truth.
- [ ] Repeat with a side that ends without resolver call and assert retry rather than permanent `resolving`.

#### Goal outage scenario

- [ ] Start one Task/Goal and stop only the daemon.
- [ ] Let native Goal reach `complete`.
- [ ] Restart the daemon.
- [ ] Assert `goal/get` recovers the terminal snapshot, completes Task once, and starts one parent reconciliation turn.

#### Verification and cleanup

- [ ] Run:

```bash
./buddyswitch-test focused tests/system/demand_goal_mode/test_product_flow.py tests/integration/demand_sys/test_side_triage_flow.py tests/integration/goal_mode/test_task_goal_reconciliation.py
```

- [ ] Inspect daemon, App Server, runtime broker, Message, Demand, Task, and Goal logs for matching actor/thread/source/task identities.
- [ ] Stop and delete isolated test actors.
- [ ] Prove no process, socket, side lease, scheduled trigger, or temporary root remains.
- [ ] Freeze the candidate and run:

```bash
./buddyswitch-test full
```

Expected: all product scenarios and the frozen repository suite pass with clean residual state.

## 14. Direct replacement matrix

| Retired live concept | Replacement | Required removal proof |
|---|---|---|
| Demand `intakes` map | private `ingress_receipts` keyed by source key | no aggregate/test/current doc contains `intakes` |
| `intake_id` | source key + attempt id | no API, prompt, state, or tool accepts `intake_id` |
| stored TriageProposal | resolver arguments applied atomically | no proposal field or record-proposal operation |
| `TRIAGE_OUTPUT_SCHEMA` | side-only MCP input schema | no Demand triage `outputSchema` |
| final assistant JSON parsing | direct owner operation | no `_agent_message_text` triage path |
| item/turn terminal handlers | receipt state + handler reconciliation | Demand handler ignores terminal notification names |
| parent triage judgment | complete side context + owner validation | no `needs_parent_judgment` branch |
| `absorb` / `absorb_into` | `merge_intake` | negative residue scan |
| Task side processing | main-thread native Goal | no Task side startup or side status |
| Task parent handoff | Goal continues on main thread | no handoff state or `need_parent` |
| Task Progress Check | Goal automatic continuation | no Progress Check prompt/handler/state |
| `task_sys.outcome_frame` | Goal handler starts a new parent reconciliation turn | no outcome frame renderer/prompt |
| `task-management` skill | native Goal built-in discipline | skill directory and manifest entry absent |
| old Task `source_ref` shape | new minimal Task `demand_ref` binding | old record rejected; rebuilt state contains none |
| Market metadata-only completion | delivered message/readable artifact | end-to-end consumer assertion |

## 15. Required residue scans

Run after implementation and before final full suite:

```bash
rg -n "capture_intake|get_intake|begin_triage|record_triage_proposal|retry_triage|apply_triage_proposal|TRIAGE_OUTPUT_SCHEMA|needs_parent_judgment|absorb_into|task_sys\\.outcome_frame|TASK PROGRESS CHECK|need_parent|side_processing|awaiting_parent|parent_processing" scripts tools buddyswitch tests docs/arch
```

Expected: no live implementation/guidance matches. Negative tests may name a retired term only to prove absence.

```bash
rg -n "\"intakes\"|\"intake_id\"|\"proposal\"" scripts/env tools/launcher buddyswitch/skills docs/arch
```

Expected: no Demand ingress state/API match. Unrelated English usage must be individually reviewed.

```bash
rg -n "task-management" buddyswitch tools scripts docs/arch tests
```

Expected: only a negative residue assertion may remain.

```bash
find "${BUDDYSWITCH_STATE_ROOT}" -path '*/task-sys/tasks/*.json' -type f -print
```

Expected after approved rebuild and fresh actors: every listed Task validates against the new schema; no old record is retained as fallback input.

## 16. Acceptance matrix

| Proof class | Claim | Nearest evidence |
|---|---|---|
| Product | Four Market facts become two canonical Demands, one Goal at a time, and readable user delivery | `tests/system/demand_goal_mode/test_product_flow.py` plus Web run |
| Product | Dev creates a direct self-demand while current Goal continues | same system test plus Demand aggregate observation |
| Contract | Triage side resolver is side-only and commits atomically | MCP, runtime broker, and Demand integration tests |
| Contract | Goal complete is the only Task-complete signal | Goal-mode Task tests |
| Architecture | Demand, daemon, Task, Goal, and skills each own one rule set | architecture boundary tests and current docs |
| Replacement | Intake, output schema, terminal notification parser, Task frames, and task-management are absent | residue scans and negative tests |
| Operations | daemon-only outage and restart recover without replay | system outage scenarios |
| Operations | Goal terminal during daemon outage is recovered by `goal/get` | Goal outage scenario |
| Operations | test actors/processes/sockets/leases are cleaned | resource-owning system test assertions |
| Data | retired Task records do not crash Web and are removed before acceptance | explicit error test plus approved rebuild |

## 17. Important implementation constraints

1. **No daemon business coupling.** daemon core may invoke handler reconciliation, record results, and manage timing. It must not import or branch on Demand, Task, Goal, Message, Track, or Browser business semantics.
2. **No seventh Demand tool.** The side resolver is not added to `demand_sys` ToolDefinition, role permissions, normal MCP listing, Context tool catalog, CLI Demand actions, or Web Demand actions.
3. **No first-class Intake under a new name.** The source-keyed receipt is private operational state. It has no generated id, list/get surface, selection role, Task role, or separate projection.
4. **No Goal/frame coexistence.** Once Phase 2 lands, delete the frame executor in the same coherent change.
5. **No automatic Demand completion.** Task/Goal completion only supplies evidence and attention.
6. **No automatic next Task on stopped Goal.** Blocked, paused, or limited Goal keeps the one Task slot occupied.
7. **No source-delivery reinvention.** Keep canonical Message/Track/Browser source records and generic daemon schedules; do not introduce another queue, bus, dispatcher registry, or workflow engine.
8. **No compatibility migration.** Old aggregates and Tasks are not translated. Cutover requires an explicit rebuild after user approval.
9. **No metadata-only success.** Artifact or Track existence does not satisfy a user request when the requested result is absent from the message/product surface.
10. **Preserve unrelated dirty work.** The worktree already contains broad user changes. Implementation must inspect and partition overlapping edits instead of reverting or restaging them.

## 18. Explicitly deferred work

The following are not part of this implementation:

- multiple simultaneously active Tasks;
- multi-thread Actor instance execution;
- multi-Demand-to-one-Task binding;
- remote cross-instance Task coordination;
- a general workflow engine, event bus, handler registry, or distributed scheduler;
- migration of historical Demand/Task runtime data;
- new Goal behavior inside the Codex repository.

Native Goal's App Server RPC and persisted thread ownership are compatible with a future remote/main-thread design. BuddySwitch should preserve the Task-to-thread binding so future Actor multi-thread execution can add another binding without changing Demand semantics. No parallel implementation is added now.

## 19. Final review checklist

- [ ] Every file path in this plan either exists now or is explicitly marked Create/Delete/Replace.
- [ ] All tests use only `./buddyswitch-test focused` or the final frozen `./buddyswitch-test full`.
- [ ] No task contains an unresolved product decision or placeholder.
- [ ] The six Actor Demand tools remain exact.
- [ ] Side resolver visibility is proven, not merely documented.
- [ ] daemon outage claim is worded with App Server/runtime broker liveness preconditions.
- [ ] In-flight pre-side and missing-resolver windows are covered by reconciliation.
- [ ] Task and Demand completion remain decoupled.
- [ ] Goal complete starts a separate parent reconciliation turn.
- [ ] Old state is rejected, explicitly rebuilt, and never read through a fallback.
- [ ] Market delivery and Dev self-demand findings are included in product acceptance.
- [ ] Final report names exact changed files, focused/full test evidence, rebuild action, cleanup evidence, and any remaining external risk.

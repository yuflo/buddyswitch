# Web Actor Start Recovery Design

Date: 2026-07-18

Status: Approved direction; awaiting written-spec review before implementation planning

## Acceptance

When a user starts an actor, the Team room shows exactly one row for that actor throughout the attempt: the row progresses from `Starting` to `Active`, or to `Start failed`; startup-only states do not request actor identity or conversation data; and a failed published actor offers only `Retry` and `Delete`.

Consumer path:

```text
Start teammate
  -> Host Control assigns the actor id
  -> Web lifecycle operation targets that actor id
  -> Web actor projection merges operation and instance facts
  -> one actor row shows Starting
  -> Active, or Start failed with Retry/Delete
```

Retry path:

```text
Retry failed actor
  -> Host Control validates startup failure and reads the role
  -> assign replacement actor id
  -> Delete(previous actor)
  -> Start(same role, replacement actor id)
  -> one row shows Retrying
  -> replacement Active, or replacement Start failed
```

## Problem

The current WebUI renders two independently sourced rows during one start attempt:

- an active `op-*` start operation whose actor id is initially empty;
- an `act-*` instance record published early with runtime status `inactive`.

The roster therefore presents one logical actor as both `Starting` and `Stopped`. Selecting the prematurely visible instance also starts actor-console and direct-conversation reads before the daemon has registered the actor identity profile, exposing `actor identity profile not found`.

Current evidence:

- `tools/launcher/host_control.sh::start_codex` generates the actor id inside the blocking start command;
- `tools/launcher/host_control.sh::start_locked_bootstrap` publishes the instance record before app-server, thread, and daemon startup complete;
- `tools/launcher/web_management.py::_run_lifecycle_operation_worker` patches the operation target with the actor id only after a successful command result;
- `tools/launcher/assets/web-management/app.js::renderActorRowsHtml` renders active start operations and roster actors as separate row families;
- `tools/launcher/assets/web-management/app.js::loadActorSelection` starts actor-console and conversation reads for every selected actor id.

This is a lifecycle identity and projection defect, not evidence that two actors were created.

## Product Decisions

### One logical actor, one row

An operation id is progress metadata, not a teammate identity. The roster never renders a start operation as an independent person row. The operation remains available for polling and diagnostics.

### User-facing lifecycle states

The browser consumes one explicit Web actor projection state:

| `lifecycle_state` | Meaning | Visible actions |
| --- | --- | --- |
| `starting` | Initial start attempt is queued or running | none |
| `active` | Start completed and actor services are ready | existing active actions |
| `stopped` | A previously usable actor was intentionally stopped | Resume, Delete |
| `start_failed` | A published initial or replacement attempt failed | Retry, Delete |
| `retrying` | A failed actor is being replaced | none |

`inactive` remains a Host Control runtime fact during this slice. It is not rendered directly as the user-facing lifecycle state. Web Management derives `stopped` versus `start_failed` from owner facts and returns the result once in the actor DTO; browser code does not reproduce the classifier.

### Retry means fresh replacement

Retry does not resume or repair the failed actor. It removes the failed attempt and runs the ordinary Start path for the same role with a new actor id, workspace, and thread.

Retry does not copy partial runtime state, identity, thread, workspace content, capabilities, or failure-phase artifacts into the replacement. The role is the only product input carried forward.

### Early unpublished failure

If Start fails before an instance record exists, no actor exists to delete. The provisional Starting row disappears, the Start panel retains the role and shows the failure, and its retry action runs an ordinary `Start(same role)`.

## Ownership And Contracts

### Private Host Control

Host Control remains the sole owner of lifecycle mechanics. It owns:

- actor id allocation for every start attempt;
- Start execution for a supplied owner-issued actor id;
- published-start failure recording and resource cleanup;
- failed-actor validation;
- Retry composition as Delete followed by ordinary Start;
- exact previous and replacement actor ids in Retry results.

Web and the public CLI must not generate actor ids independently. The exact callable split may be chosen in the implementation plan, but owner-issued actor identity must exist before Web enqueues the asynchronous operation.

Host Control status/list facts expose the nullable startup failure record currently persisted as `last_failure`. A present startup failure on an inactive instance authorizes Retry and distinguishes the instance from a normally stopped actor.

### Web Management

Web Management owns browser DTO composition and asynchronous operation presentation. It:

- creates Start operations with a non-empty owner-issued actor id;
- creates Retry operations with previous and replacement identity information;
- merges initial Start operations with Host Control instance rows by actor id and correlates Retry through its previous and replacement ids;
- emits one row per user-visible teammate lifecycle through `/api/actors`;
- computes the browser-facing `lifecycle_state` once;
- exposes one Retry route that delegates to Host Control;
- keeps `/api/operations/*` as the polling surface without rendering operations as teammates.

The intended Retry surface is:

```text
POST /api/instances/{failed_actor_id}/retry
```

The Retry operation target contains:

```text
actor_id                 # failed actor and conflict-protection target
replacement_actor_id     # preassigned fresh actor
role
```

The successful operation result contains:

```text
previous_actor_id
actor_id                 # replacement actor id
instance                 # replacement status after successful Start
```

On Retry failure, the operation error remains the failure result. Its target retains the failed and replacement ids, and `/api/actors` supplies any published replacement failure row; Web does not invent a successful result payload for a failed operation.

The route is a single browser action even though Host Control performs two ordered lifecycle mutations.

### Browser

The browser renders the supplied actor projection and does not infer lifecycle state from scattered combinations of `inactive`, health, thread, and operation labels.

It may create an immediate provisional row from a Start response because that response already contains the owner-issued actor id. A Retry response instead updates the selected failed row in place: the active operation correlates the previous and replacement ids, and the replacement id becomes the row's actor id when a replacement instance is published or Retry succeeds. Reconciliation never renders the operation, previous instance, and replacement instance as separate teammate rows.

## Start Attempt Identity

The actor id is allocated before the asynchronous command begins and is carried through every layer:

```text
role selection
  -> Host Control owner-issued actor id
  -> Web operation.target.actor_id
  -> Host Control Start input
  -> instance.json actor_id
  -> /api/actors actor_id
  -> operation result actor_id
```

The same actor id must appear at every boundary. A mismatch is a contract failure; it is not reconciled with an alias or fallback.

For Retry, the operation target carries both identities:

```text
actor_id = failed actor being removed and protected from conflicting actions
replacement_actor_id = replacement actor being started
```

The UI keeps one selected row during the identity replacement and displays the new id when the replacement becomes authoritative.

## Unified Actor Projection

Web Management joins current facts into one row per user-visible teammate lifecycle:

```text
Host Control instance row
        +
active Start/Retry operation for the actor
        +
startup failure fact
        -> browser actor DTO with lifecycle_state
```

Classifier precedence:

1. active Retry operation -> `retrying`;
2. active initial Start operation -> `starting`;
3. inactive instance with startup failure -> `start_failed`;
4. active instance after successful Start/Resume -> `active`;
5. inactive instance without startup failure -> `stopped`.

Starting and retrying rows do not display runtime health. Intermediate app-server health cannot override lifecycle state or imply actor readiness.

For an active Retry, the operation is the correlation owner between two actor ids. It supersedes the failed-actor row and any replacement-instance row, emitting exactly one `retrying` row. Before replacement publication, the row uses the failed actor id and also carries `replacement_actor_id`; after publication, it uses the replacement actor id and carries `previous_actor_id`. This is transient Web projection metadata, not a persisted actor alias.

When Retry becomes terminal, the correlation projection disappears: a successful or published-failure replacement remains under its own actor id, while an unpublished replacement failure returns to the Start panel. The browser transfers selection using the terminal operation's previous and replacement ids.

The projection permits multiple concurrent queued attempts, but each attempt has its own preassigned actor id and therefore its own single row. Existing lifecycle serialization remains unchanged.

## Failure Recording And Cleanup

Once an instance record has been published, every subsequent Start failure must pass through one common failure-cleanup owner. Required phases include:

- capability seeding;
- runtime-broker startup;
- Codex configuration patching;
- environment MCP startup;
- browser cockpit registration;
- app-server startup;
- thread start;
- thread bootstrap;
- daemon startup and identity registration.

For every published failure, the owner:

1. stops app-server, runtime broker, browser manager, and daemon resources when present;
2. clears pid, socket, browser-port, app-server, and thread fields that are not valid after cleanup;
3. records phase, message, timestamp, and relevant diagnostic identifiers;
4. leaves one inactive instance record carrying the startup failure fact;
5. returns a failed operation that remains correlatable to the actor id.

Cleanup is idempotent. Cleanup warnings do not replace the primary startup failure, but they remain visible in diagnostics.

No failure after instance publication may fall back to an indistinguishable plain inactive record.

## Readiness And Identity

Lifecycle completion, not intermediate health, gates actor interaction.

The browser loads actor console, capabilities, direct conversation, and messaging state only for:

- `active` actors;
- `stopped` actors that previously completed startup.

It does not call those surfaces for `starting`, `retrying`, or `start_failed`.

Host Control Start success means the daemon has completed actor identity profile registration. If identity registration fails, Start fails and common cleanup records the published failure. The UI therefore does not hide an unexpected identity error after Start success; it prevents requests only while the owner says the actor is not ready.

## Retry Execution And Failure Semantics

Retry runs as one asynchronous Web lifecycle operation and one Host Control lifecycle capability.

Ordered behavior:

1. validate that the target instance exists, is inactive, and carries a startup failure;
2. capture the role;
3. allocate the replacement actor id;
4. delete the failed actor through the existing Delete owner;
5. start the replacement through the existing Start owner;
6. return previous id, replacement id, and replacement instance.

Failure results are explicit:

| Failure point | Result |
| --- | --- |
| validation fails | no mutation; original row remains |
| Delete fails | Start is not attempted; original failed actor remains |
| Delete succeeds and Start fails before publication | original actor is gone; Start panel shows the retry failure and same role |
| Delete succeeds and replacement fails after publication | replacement appears once as `start_failed` |
| replacement succeeds | replacement appears once as `active` |

Retry is not transactionally atomic. No database, rollback layer, or attempt-restoration mechanism is introduced. The ordered effects above are the supported contract.

## UI Behavior

### Starting

- One row under `Starting` with the actor role and preassigned actor id.
- Selected detail explains that Start is in progress.
- No health badge, Resume, Delete, messaging composer, actor console, or conversation request.

### Active

- The same row moves to `Active`.
- Runtime health and existing actor actions become available.
- Actor console and conversation load only after terminal Start success.

### Start failed

- One row under `Needs attention` with `start failed`.
- Detail shows the external-safe failure phase and message.
- Only Retry and Delete are enabled.
- Resume is absent.
- Messaging and actor-console surfaces remain unavailable.

### Retrying

- The failed row becomes `Retrying`; no second Starting row is added.
- The detail states that the failed attempt is being replaced by a fresh actor of the same role.
- All lifecycle and messaging actions are disabled until Retry completes.
- On success, the row shows the replacement actor id and becomes Active.
- On published failure, the row shows the replacement actor id and becomes Start failed.

### Delete

The existing explicit Delete confirmation remains unchanged. Deleting a failed actor removes the row and does not start a replacement.

## Explicit Non-Goals

- repairing or continuing the failed actor in place;
- treating Retry as Resume;
- browser-side orchestration of separate Delete and Start requests;
- copying partial failed workspace, identity, thread, or runtime state;
- a new persistent lifecycle state machine, database, event bus, job engine, or recovery-phase engine;
- operation persistence across Web process restarts;
- changing unrelated Stop, Resume, Clear, Task, Track, IM, or capability semantics;
- compatibility rendering for the separate `op-*` teammate row.

## Proof Strategy

### Host Control contract

- owner-issued actor id is accepted by Start and appears unchanged in the instance record and result;
- status/list expose the startup failure fact;
- every post-publication failure phase records failure and leaves no process, socket, pid, lock, browser, or temporary runtime residue;
- successful Start implies daemon identity registration is ready;
- Retry rejects a normally stopped actor and a currently active actor;
- Retry calls Delete before Start, uses the same role, and returns a new actor id;
- Delete failure prevents Start;
- replacement failure produces the specified unpublished or published result.

### Web contract

- Start response operation has a non-empty actor id before the worker completes;
- Retry is one operation containing previous and replacement identities;
- `/api/actors` emits one row when an operation and instance record describe the same actor id;
- an active Retry emits one row across the failed and replacement ids, including if the replacement instance has already been published;
- lifecycle-state precedence is exact for Starting, Active, Stopped, Start failed, and Retrying;
- active operations remain pollable without becoming teammate rows.

### Browser behavior

- initial Start renders one row before, during, and after instance publication;
- no transient Stopped row or `inactive + healthy` combination appears during Start;
- Starting, Retrying, and Start failed issue no actor-console or conversation request;
- Start success selects the same logical row and enables normal interaction;
- Start failure exposes Retry/Delete and no Resume;
- Retry success replaces the id without a duplicate row;
- Retry published failure exposes the replacement once with Retry/Delete;
- early unpublished failure returns to the Start panel with the role preserved;
- Delete retains its existing confirmation behavior.

### Replacement assertions

The current tests and renderer paths that protect these retired behaviors are removed or replaced:

- blank actor id on a running Start operation;
- independent `op-*` teammate rows;
- operation identity as the selected teammate context;
- all inactive actors receiving Resume;
- selected startup actors triggering conversation loads;
- plain inactive records for published Start failures.

No compatibility alias, legacy renderer, fallback join, or second lifecycle classifier remains live.

## Implementation Boundaries

Expected affected areas:

- `tools/launcher/host_control.py`;
- `tools/launcher/host_control.sh`;
- `tools/launcher/env.sh` only where instance failure facts are owned;
- `tools/launcher/web_management.py`;
- `tools/launcher/assets/web-management/app.js`;
- existing Web styles only for the approved lifecycle states;
- claim-scoped Host Control, Web service, Web state, and instance lifecycle tests.

The change must remain one coherent vertical slice. Unrelated lifecycle renames, operation persistence, general job abstractions, UI redesign, and broad IM changes are out of scope.

# Web Interface Call Architecture

## Purpose

BuddySwitch external interfaces call the owner of requested behavior directly.
Web and the public CLI are peer adapters; neither is the other's internal API.

## Public CLI

The public CLI delegates:

- instance lifecycle and capabilities to private Host Control;
- instance input and attach to Actor Session;
- Demand, Task, and Track reads to their Public external-safe projections;
- Web startup to the Web process launcher.

Web does not run the CLI as a subprocess or parse CLI output. Open TUI is the
explicit user-visible exception: Web hands Terminal.app the same public
`buddyswitch-codex instance attach` command shown by Copy command.

## Web interface

Web owns browser routes and browser DTO composition. It may combine Host
Control facts with external-safe product reads, but it does not own lifecycle
mechanics, Actor input, Demand/Task mutation, or IM semantics.

`/api/actors/{id}/console` composes one Actor Console read model. The generic
Web host owns the surrounding Actor, runtime, IM, and capability DTO. It
invokes typed `ActorConsoleSectionRegistration` projectors selected by
application composition. Task contributes `task_sys`; Track contributes
`tracks` using Track Public external projections. Those projections preserve
their exact external-safe DTOs. Web imports neither Task-private nor
Track-private packages, contains no product lifecycle rule, has no raw
repository fallback, and exposes no product mutation subroute.

## Web Message

`/api/im/*` is the single browser-facing Message contract.
`ExternalImSession` projects external identity, Actor discovery, send, events,
reply, acknowledgement, and conversation calls onto Central IM. Central IM
owns immutable Messages, `reply_to` edges, identity-visible cursors, target
resolution, and delivery results.

Inbound Actor delivery may create Demand triage attention through the owning
IM delivery path. Web does not synthesize Demand or Task state and does not
infer completion from a Message response.

## Owners

### Private Host Control

Private Host Control owns role discovery, instance
start/list/status/clear/resume/stop/delete, interrupt, compact, capabilities,
and daemon/App Server coordination. It returns host facts, not product state.

### Actor Session

Actor Session owns direct parent-thread input and attach resolution. Direct
input is distinct from the Demand ingress pipeline and does not mutate Demand
or Task state.

### Product domains

- Demand Sys owns canonical needs and their external-safe reads.
- Task Sys owns minimal Demand-bound Task records.
- Codex App Server owns native Goal execution.
- Track owns Track state and projections.
- Artifact owns Artifact content, attachment state, and read policy.
- Central IM owns Message state and delivery results.

Actor runtime Task tools expose exactly `list`, `get`, `create`, and `cancel`.
Successful Task completion is recorded by Task's native-Goal adapter from the
matching native Goal, not by Web, CLI, or another external mutation.

External Task rows contain exactly:

```text
task_id
demand_ref
objective
selection
goal_binding
status
result
actor
updated_at
```

Web and CLI construct fresh DTOs and do not expose storage paths, internal
revisions, raw payloads, or handler checkpoints.

## Dependency rules

Valid paths:

```text
Browser -> Web -> private Host Control
Browser -> Web Open TUI -> Terminal -> public CLI attach -> Actor Session
Browser -> Web -> typed Actor Console section projectors
Browser -> Web -> IM API

Public CLI -> private Host Control
Public CLI -> Actor Session
Public CLI -> typed product command registrations

Actor tools -> product owners
Product owners -> repositories
```

Forbidden paths:

- Web to CLI subprocess execution as an internal product API;
- Web to raw product repository rows;
- generic Web host to Task private code or Task lifecycle rules;
- generic Web host to Track private code or Track lifecycle rules;
- Web to Actor runtime mutation tools for console reads;
- Web or CLI to native Goal mutation;
- Actor Session to Demand or Task mutation;
- lower owners to Web DTOs.

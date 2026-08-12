# Web Interface Call Architecture

## Purpose

BuddySwitch external interfaces call the owner of requested behavior directly.
Web and the public CLI are peer adapters; neither is the other's internal API.

## Public CLI

The public CLI delegates:

- instance lifecycle and capabilities to private Host Control;
- instance input and attach to the direct Foundation Actor Session owner;
- Demand, Task, and Track reads to their Public external-safe projections;
- Web startup to the Web process launcher.

Web does not run the CLI as a subprocess or parse CLI output. Open TUI is the
explicit user-visible exception: Web hands Terminal.app the same public
`buddyswitch-codex instance attach` command shown by Copy command.

## Web interface

The generic Web host owns its built-in browser routes, host DTO composition,
and product-neutral route matching. It does not own lifecycle mechanics, Actor
input, product read or mutation semantics, Communication routes, workers,
identities, delivery, or Message semantics.

Application composition selects passive `WebRouteRegistration` values exactly
once. Each registration declares one or more query-free exact paths and/or API
prefixes. Shared validation rejects malformed, duplicate, overlapping, and
host-reserved matchers before any factory runs. After preparation, the generic
host matches the parsed URL path and forwards the original path, query, body,
and headers to the selected product adapter. Track owns the exact
`/api/tracks` and prefix `/api/tracks/` read adapter; Communication owns the
prefix `/api/im/` adapter. The host contains no branch or import for either
product.

`/api/actors/{id}/console` composes one Actor Console read model. The generic
Web host owns the surrounding Actor, runtime, and capability DTO. It
invokes typed `ActorConsoleSectionRegistration` projectors selected by
application composition. Task contributes `task_sys`; Track contributes
`tracks` using Track Public external projections; Communication contributes
`im`. Those projections preserve their exact external-safe DTOs. Web imports
no component-private package, contains no product lifecycle rule, has no raw
repository fallback, and exposes no product mutation subroute.

## Web Message

`/api/im/*` is the single browser-facing Message contract. Communication owns
that prefix route and contributes it through one typed `WebRouteRegistration`.
Communication also contributes the optional iMessage channel through one
`WebWorkerRegistration`. Application composition selects both; the generic Web
host validates, instantiates, prepares, dispatches, starts, stops, and closes
them without importing Communication.

Communication's external session projection maps external identity, Actor
discovery, send, events, reply, acknowledgement, and conversation calls onto
its Message owner. Communication owns immutable Messages, `reply_to` edges,
identity-visible cursors, target resolution, and delivery results.

Inbound Actor delivery may create Demand triage attention through the owning
IM delivery path. Web does not synthesize Demand or Task state and does not
infer completion from a Message response.

## Owners

### Private Host Control

Foundation Host Control owns instance
start/list/status/clear/resume/stop/delete, interrupt, compact, capabilities,
and Daemon/App Server coordination. Application supplies the one current Role
catalog/validation/start input, and both generic Web and CLI receive the same
assembled capability. Host Control returns host facts, not product state.

### Actor Session

`src/buddyswitch/foundation/actor_runtime/session.py` owns direct parent-thread
input and attach resolution. Direct
input is distinct from the Demand ingress pipeline and does not mutate Demand
or Task state.

### Product domains

- Demand Sys owns canonical needs and their external-safe reads.
- Task Sys owns minimal Demand-bound Task records.
- Codex App Server owns native Goal execution.
- Track owns Track state and projections.
- Artifact owns Artifact content, attachment state, and read policy.
- Communication owns Message state, delivery results, its Web route, its
  iMessage worker, and the Actor Console `im` projection.

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
Browser -> generic Web host -> contributed Track read route -> Track Public
Browser -> generic Web host -> contributed Communication route

Public CLI -> private Host Control
Public CLI -> Foundation Actor Session
Public CLI -> typed product command registrations

Actor tools -> product owners
Product owners -> repositories
```

Forbidden paths:

- Web to CLI subprocess execution as an internal product API;
- Web to raw product repository rows;
- generic Web host to Task private code or Task lifecycle rules;
- generic Web host to Track private code or Track lifecycle rules;
- generic Web host to Communication private code or Message semantics;
- Web to Actor runtime mutation tools for console reads;
- Web or CLI to native Goal mutation;
- Actor Session to Demand or Task mutation;
- lower owners to Web DTOs.

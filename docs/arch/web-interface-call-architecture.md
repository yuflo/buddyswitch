# Web Interface Call Architecture

## Purpose

This document defines the stable call architecture for the BuddySwitch Web
interface. It is not an implementation plan.

The Web interface may present Actor as the primary interaction object, but that
does not make Actor the owner of every product domain. Task, Track, IM, runtime,
and persistence keep their own boundaries.

## Layers

1. Browser UI
   - Owns user interaction state and rendering.
   - Calls only Web-interface HTTP APIs.
   - Must not know runtime broker methods, daemon sockets, Task Sys storage paths, JSON
     file paths, or repository modules.

2. Web-interface API
   - Owns browser-facing HTTP routes and Web DTOs.
   - Translates product views into stable browser contracts.
   - May compose host-control facts with domain/service read models.
   - Internal helpers such as projection, resolver, and DTO shaping functions
     remain private implementation details, not architecture layers.

3. Host control lower API
   - Owns launcher, daemon, app-server, instance lifecycle, thread control, and
     runtime status facts.
   - Examples include `buddyswitch-codex instance ...`, app-server JSON-RPC,
     and daemon control.
   - Does not own product concepts such as Actor console, task panels, or track
     workspace views.

4. Actor runtime product API
   - Owns active actor capabilities and permission checks.
   - Runtime broker and native env MCP expose actor-bound actions such as
     `task_sys.list`, `task_sys.get`, `task_sys.close`, `task_sys.need_parent`,
     `track.open`, `context.summarize`, and `message.send`.
   - This layer is not the default Web query path because it is actor-bound and
     active-instance-gated.

5. Domain / service layer
   - Owns product semantics.
   - Examples: Task Sys frame semantics, track read semantics, message service,
     actor identity normalization.
   - Provides reusable behavior to Web-interface APIs and actor runtime tools.

6. Repo / persistence layer
   - Owns storage reads and writes.
   - Examples: Task Sys records, shared track JSON, track comments,
     IM message files.
   - Must not be used as a Browser-facing or UI-shaped API.

## Dependency Direction

Dependencies point downward. Lower layers must not depend on higher layers.

Valid paths:

```text
Browser UI
  -> Web-interface API
```

```text
Web-interface API
  -> Host control lower API
```

Use this for runtime and control-plane facts: instance list, instance status,
start, stop, resume, interrupt, thread status, attach/open behavior.

```text
Web-interface API
  -> Domain / service layer
  -> Repo / persistence layer
```

Use this for product read models: actor console, task state, track workspace,
track detail, direct conversations, and message disposition.

```text
Actor runtime product API
  -> Domain / service layer
  -> Repo / persistence layer
```

Use this for actor tool execution, actor-owned actions, and actor permission
boundaries.

The architecture is not a required linear chain. A request does not have to pass
through every layer. It must pass through the correct public boundary for the
kind of fact or behavior being requested.

## Forbidden Paths

- Browser UI -> Host control lower API
- Browser UI -> Actor runtime product API
- Browser UI -> Repo / persistence layer
- Web-interface API -> Repo / persistence layer for business-object semantics
- Web-interface API -> Actor runtime product API for general console reads
- Web-interface API -> actor tool handler modules as reusable service
  boundaries
- Domain / service layer -> Web-interface API
- Repo / persistence layer -> any higher layer

## Web-Interface API Families

Web-interface APIs should fall into one of these families:

1. Product view APIs
   - Browser-facing views such as actor console and track workspace.
   - Compose host-control facts and domain/service read models.
   - Return Web DTOs, not raw repo rows or tool results.

2. IM HTTP product APIs
   - `/api/im/*` is the single IM HTTP product contract for channel adapters,
     third-party callers, and the Web interface.
   - The Web interface differs only by server-owned auth context; it does not
     own a separate IM route family.
   - `ExternalImSession` owns external session and actor-directed IM
     application semantics: external identity, actor discovery, message send,
     events, replies, explicit ack, direct conversations, and disposition.

3. Control-plane APIs
   - Instance lifecycle and runtime operations.
   - Delegate to host control lower APIs.
   - Must remain visibly control-plane and should not become the primary product
     object model.

## Domain Ownership

Actor:

- Actor is the UI anchor for the console.
- Actor does not own task, track, or message semantics.
- Actor identity and address normalization belong below Web, in domain/runtime
  identity code.

Task:

- Actor-driving task state belongs to Task Sys.
- Web reads actor task state through Task Sys summary projections with resolved
  actor context.
- Web should not call actor env tools for general console reads.

Track:

- Track state belongs to track domain/service semantics and track repos.
- Web should depend on reusable track domain/service reads, not actor runtime
  tool handlers.
- Actor-track relation and participant derivation may remain inside Web DTO
  shaping while only Web needs it. Move it down only when non-Web callers need
  the same semantics.

IM:

- External session semantics belong to `External IM Session`.
- `/api/im/*` is the single IM HTTP product contract for local channel
  adapters, third-party callers, and the Web console.
- Web Management supplies a server-owned external IM session for browser calls,
  but message, event, ack, reply, conversation, and disposition semantics still
  flow through `ExternalImSession`.
- The Web console must not invent actor-owned message state or a separate IM
  route family.

Runtime:

- Runtime status and lifecycle facts belong to host control.
- Actor runtime tools express active actor capabilities, not global Web console
  queries.

Persistence:

- Repos store facts and validate stored shapes.
- Repos must not shape UI DTOs or enforce Web interaction semantics.

## Boundary Rule

When adding or changing Web behavior, classify the need first:

- If it is a browser contract or UI read model, put it in the Web-interface API.
- If it is lifecycle, status, thread, daemon, or app-server control, call host
  control lower APIs.
- If it is reusable product semantics, put it in the domain/service layer.
- If it is active actor capability or permission behavior, put it behind actor
  runtime product APIs.
- If it is storage mechanics, keep it in repos.

Do not add lower-layer APIs to satisfy page DTO shape alone. Do not call lower
private implementation modules because they happen to contain useful logic.
Extract reusable semantics to the domain/service layer when more than one public
surface needs them.

# Web Interface Call Architecture

## Purpose

This document defines the durable external control boundaries for BuddySwitch.
Each interface calls the owner of the requested behavior directly. Web and the
public CLI are peers; neither is a transport layer for the other.

## External Interfaces

### Public CLI

The public CLI is a peer adapter. It translates commands to machine-readable
results and delegates directly to the owning callable:

- instance lifecycle and capabilities go to private Host Control;
- instance input and attach go to Actor Session;
- Task and Track reads go to external-safe domain projections;
- Web startup launches the Web process.

The public CLI is not the Web interface's lower API. Web never shells through
`buddyswitch-codex`.

### Web Interface

The Web interface owns browser routes and browser DTO composition. It may
combine host-control facts with external-safe product reads, but it does not
own lifecycle mechanics, Actor input, Task/Track mutation, or IM semantics.

`/api/actors/{id}/console` is the actor console read model, with no Task subroute.
Instance routes delegate lifecycle work to private Host Control.
Open TUI delegates attach resolution to Actor Session.

### Web Message

Web Message belongs to the IM API. `/api/im/*` is the single HTTP product
contract for browser, local channel, and third-party message calls.
`ExternalImSession` owns external identity, actor discovery, send, events,
reply, acknowledgement, conversation, and disposition behavior. Web supplies
server-owned browser identity context and does not create another message
contract.

## Owners

### Private Host Control

Private Host Control is the sole host lifecycle owner. It owns role discovery,
instance start/list/status/clear/resume/stop/delete, interrupt, compact,
capabilities, daemon/app-server coordination, and host-control facts only.
It does not return Task or Track product state.

### Actor Session

Actor Session Input/Attach owns direct parent-thread input and Codex remote
attach resolution. These operations are outside Task Sys: they do not create a
Task frame, Task relation, handoff frame, or Side runtime state. The Web Open
TUI path and public CLI call the same Actor Session boundary.

### Product Domains

Task Sys remains the internal actor-runtime mutation and classification owner.
Internal runtime tools may use `actor_task_projection` and explicit mutations
such as `task_sys.update_task_analysis`.

External interfaces use external-safe Task/Track projections only:

- Task rows use the exact allowlist produced by `external_task_projection`;
- actor console classification uses `actor_external_task_projection`;
- Track lists and details use `track_read.list_external_tracks` and
  `track_read.get_external_track`;
- external Task/Track exact allowlist projections construct fresh DTOs and do
  not expose execution, events, runtime instructions, raw payloads, or repo
  paths.

Web and CLI must not mutate Task or Track state. Side/Goal mutations are not exposed
by any external interface. Actor-bound Task Sys actions, internal Side runtime
behavior, and internal Goal callables remain behind their owners.

## Dependency Rules

Valid direct paths are:

```text
Browser -> Web Interface -> private Host Control
Browser -> Web Interface -> Actor Session
Browser -> Web Interface -> external-safe Task/Track projections
Browser -> Web Interface -> IM API

Public CLI -> private Host Control
Public CLI -> Actor Session
Public CLI -> external-safe Task/Track projections

Actor runtime tools -> Task Sys / Track / Message domain owners
Domain owners -> repositories
```

Forbidden paths are:

- Web -> public CLI;
- Web -> raw repository rows for product semantics;
- Web -> actor runtime tools for console reads;
- Web or CLI -> external Side/Goal mutation routes;
- Actor Session -> Task Sys runtime framing;
- lower owners -> Web DTOs.

## Change Rule

Classify a change by owner before adding a call. Lifecycle belongs to private
Host Control, direct input/attach belongs to Actor Session, messages belong to
the IM API, external Task/Track reads belong to exact allowlist projections,
and actor-runtime mutations remain internal. Add a new external surface only
when none of these owners can express the required product behavior.

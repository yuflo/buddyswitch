# Track Capability Architecture

## Owner

`src/buddyswitch/modules/track/` is the single live Track owner. It owns Track
and Track-comment schemas and storage, relation and update state, Track Tool
behavior, external CLI/Web projections, the Actor Console section, comment
inbound handling, cleanup discovery, Skills, and owner tests.

Track state keeps the existing durable locations under
`buddyswitch/objects/tracks` and `buddyswitch/objects/track-comments`. The
module derives those locations from the generic runtime object root; generic
runtime files and cleanup do not own or discover Track paths.

## Public boundary

Track Public exposes immutable facts and consumer-earned reads:

- Track identity/archive scope for Artifact policy;
- Artifact relation and update-reference usage facts;
- external-safe list/get projections for CLI and Web;
- the active Track, update, and comment-thread snapshot used by Context.

Track Public does not expose repositories or mutable Track records.

## Artifact input ports

Track owns two narrow callable ports: publication candidate resolution and
reference metadata reading. Application composition injects the corresponding
Artifact Public callables when it builds Track. Track Private therefore has no
Artifact import and maps typed port failures at the Track Tool boundary.

The dependency path is:

```text
application composition
  -> Artifact Public callables
  -> Track-owned callable ports
  -> Track Private relation/update behavior
```

There is no capability locator, fallback repository, or shared relationship
service.

## Host contributions

Track contributes one Tool, one CLI command, two Skills, Track/comment cleanup
categories, one Actor Console section, one Web read route, and one
`track.comment.added` inbound source through `ModuleAssembly`. The Web route
declares exact `/api/tracks` and prefix `/api/tracks/` matchers and translates
list/detail reads through Track Public. Application composition selects Track
exactly once; the generic Web host validates and dispatches the passive route
without importing Track or branching on Track paths.

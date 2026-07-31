# Artifact Capability Architecture

## Owner

`src/buddyswitch/modules/artifact/` is the single live Artifact owner. It owns
Artifact and attachment schemas and storage, revision/source-reference rules,
read policy, relation/backlink projection, Tool behavior, Evidence target
facts, cleanup discovery, selection assets and entrypoint, its Skill, and
owner tests.

Artifact state keeps the existing durable locations under
`buddyswitch/objects/artifacts` and
`buddyswitch/objects/artifact-attachments`. The module derives those
locations from the generic runtime object root; generic runtime files and
cleanup do not own or discover Artifact paths.

## Public boundary

Artifact Public exposes immutable facts and Artifact-owned decisions:

- publication candidate identity/template through the Track port adapter;
- content-free reference metadata and attachment summaries;
- readable Artifact summaries for Context;
- Evidence target existence and active-author validation.

Artifact Public does not expose Artifact storage or mutable records.

## Track dependency

Artifact read policy consumes Track Public scope and usage facts. Artifact
Private never imports Track Private and never mutates Track. The reverse
relation-write need is supplied through Track-owned callable ports, with
application composition injecting Artifact's provider callables.

The source direction is:

```text
Artifact Private -> Track Public -> Track Private
application composition -> Artifact Public callables -> Track input ports
```

There is no Public cycle, cross-Private import, shared relationship module, or
generic product locator.

## Host contributions and packaging

Artifact contributes one Tool, one Skill, and Artifact record/attachment
cleanup categories through `ModuleAssembly`. Its selection command remains at
the stable application entrypoint and delegates directly to the module-owned
entrypoint. Selection JSON and the Skill are packaged from the Artifact
module. The application selects Artifact exactly once.

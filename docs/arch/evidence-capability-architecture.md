# Evidence Capability Architecture

## Purpose

Evidence issues transient, Artifact-scoped metadata for browser evidence and
explicit downgrade approvals. It does not persist product objects or own
Browser lifecycle.

The complete implementation owner is:

```text
src/buddyswitch/modules/evidence/
```

## Consumer path

```text
Actor or stable CLI
  -> Runtime Broker env.tool
    -> explicitly composed Evidence Tool
      -> Artifact Public scope decision
        -> transient result or rejection
```

The stable application entrypoint delegates to the Evidence-owned entrypoint.
Both consumers use the existing Runtime Broker protocol and Tool ID, actions,
schemas, authority, and result contract.

## Composition

Evidence contributes one passive Tool registration through `ModuleAssembly`.
The application composition root selects that assembly exactly once after
Track. Evidence contributes no daemon handler, CLI command registration,
Skill, cleanup category, actor-console section, or inbound source.

The generic Tool registry combines explicitly composed registrations with
remaining dynamically discovered packages. Evidence is composed and is not
dynamically discovered.

## Dependencies and state

Evidence Private may consume Artifact Public to resolve readable,
active-actor-authored Artifact targets. It may not consume Artifact Private,
Browser lifecycle, another component's Private package, or a broad host
service locator.

Evidence token metadata is transient. Artifact remains the sole owner of
durable Artifact data and target-scope meaning. Browser status remains a
generic host surface and contains no Evidence issuance or approval behavior.

There is no Evidence Public package because there is no current in-process
consumer contract to expose.

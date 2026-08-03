# S4 Independent Component Waves Charter

> Current state: COMMUNICATION READY
> Entry prerequisite: S3 ACCEPTED
> Execution authority: `BS-MM-S4-COMMUNICATION-R1-20260803-01`
> Merge unit: one accepted component lane at a time

## Acceptance sentence

> Track, Artifact, Communication, Search, Evidence and Context each have one
> physical owner, one assembly path and no private behavior in shared hosts.

## Lanes

| Lane | Owned behavior | Ordering constraint |
|---|---|---|
| Track | Track/comments/state/inbound/Skill/projections | ACCEPTED with two Artifact Public callables injected into Track-owned ports |
| Artifact | artifacts/relations/visibility/config/Skill | ACCEPTED with read-only Track Public dependency |
| Communication | Message/IM/delivery/external session/channel worker | READY; passive Web route/worker contributions and cleanup edge frozen |
| Search | bounded non-opening Actor search capability | existing Tool contribution; Browser remains foundation |
| Evidence | transient evidence/downgrade capability | ACCEPTED; one stateless module and canonical broker-backed command result |
| Context | application read projection and context Tool | last; consumes other Public reads |

Browser is not a product lane. It remains an Actor foundation capability.

Search, the atomic Track–Artifact pair and Evidence are accepted. See
`04-independent-component-waves-plan/search/S4-SEARCH-ACCEPTANCE.md` and
`04-independent-component-waves-plan/track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md`
and `04-independent-component-waves-plan/evidence/S4-EVIDENCE-ACCEPTANCE.md`.
Communication is READY through its own committed source snapshot, boundary
design and packet under `04-independent-component-waves-plan/communication/`.
Context remains last and may not begin until Communication is accepted.

## Lane protocol

Each lane receives its own current-source trace, implementation plan, branch,
residue rows and acceptance record:

```text
TRACE -> PROVE (RED or preservation baseline) -> BUILD
      -> consumer cutover -> old-path deletion -> VERIFY
```

## Parallelism

Allowed only when:

- host contribution contracts are frozen;
- write roots and state owners are disjoint;
- application root has one integration owner;
- root test ownership is assigned;
- no lane edits another component's Public/private surface.

## Lane proof

- owner-specific product/capability behavior;
- one Tool/Daemon/Web/CLI/Skill/cleanup path as applicable;
- private dependency isolation;
- package/runtime and Actor projection content;
- lifecycle/cleanup at affected breadth;
- old path/test/guidance absence.

## Wave exit

S4 accepts only after every lane accepts and the remaining S5 hotspot list is
exact. A vague “foundation cleanup later” is not an exit.

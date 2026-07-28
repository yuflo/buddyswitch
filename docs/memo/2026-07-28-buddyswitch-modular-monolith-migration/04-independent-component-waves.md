# S4 Independent Component Waves Charter

> Initial state: BLOCKED
> Blocked by: S3 acceptance
> Merge unit: one accepted component lane at a time

## Acceptance sentence

> Track, Artifact, Communication, Search, Evidence and Context each have one
> physical owner, one assembly path and no private behavior in shared hosts.

## Lanes

| Lane | Owned behavior | Ordering constraint |
|---|---|---|
| Track | Track/comments/state/inbound/Skill/projections | none after S3 |
| Artifact | artifacts/relations/visibility/config/Skill | none after S3 |
| Communication | Message/IM/delivery/external session/channel worker | Web worker contract frozen |
| Search | bounded Actor search capability | Browser host contract frozen |
| Evidence | transient evidence/downgrade capability | Artifact Public accepted |
| Context | application read projection and context Tool | last; consumes other Public reads |

Browser is not a product lane. It remains an Actor foundation capability.

## Lane protocol

Each lane receives its own current-source trace, implementation plan, branch,
residue rows and acceptance record:

```text
TRACE -> RED -> BUILD -> consumer cutover -> old-path deletion -> VERIFY
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

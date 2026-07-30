# S4 Independent Component Waves Charter

> Current state: READY — SEARCH LANE ONLY
> Entry prerequisite: S3 ACCEPTED
> Execution authority: `BS-MM-S4-SEARCH-20260730-01` only
> Merge unit: one accepted component lane at a time

## Acceptance sentence

> Track, Artifact, Communication, Search, Evidence and Context each have one
> physical owner, one assembly path and no private behavior in shared hosts.

## Lanes

| Lane | Owned behavior | Ordering constraint |
|---|---|---|
| Track | Track/comments/state/inbound/Skill/projections | exact Artifact Public/input-port direction not yet frozen |
| Artifact | artifacts/relations/visibility/config/Skill | exact Track Public/input-port direction not yet frozen |
| Communication | Message/IM/delivery/external session/channel worker | worker lifecycle contribution not yet frozen |
| Search | bounded non-opening Actor search capability | existing Tool contribution; Browser remains foundation |
| Evidence | transient evidence/downgrade capability | Artifact Public accepted |
| Context | application read projection and context Tool | last; consumes other Public reads |

Browser is not a product lane. It remains an Actor foundation capability.

Current source review has admitted Search only. See
`04-independent-component-waves-plan/README.md`. The other five lanes remain
preparation-only and may not reuse the Search packet.

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

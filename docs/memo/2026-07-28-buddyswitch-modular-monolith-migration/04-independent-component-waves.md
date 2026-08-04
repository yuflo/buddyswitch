# S4 Independent Component Waves Charter

> Current state: ACCEPTED
> Entry prerequisite: S3 ACCEPTED
> Execution authority: none; every S4 packet is consumed
> Merge unit: one accepted component lane at a time

## Acceptance sentence

> Track, Artifact, Communication, Search, Evidence and Context each have one
> physical owner, one assembly path and no private behavior in shared hosts.

## Lanes

| Lane | Owned behavior | Ordering constraint |
|---|---|---|
| Track | Track/comments/state/inbound/Skill/projections | ACCEPTED with two Artifact Public callables injected into Track-owned ports |
| Artifact | artifacts/relations/visibility/config/Skill | ACCEPTED with read-only Track Public dependency |
| Communication | Message/IM/delivery/external session/channel worker | ACCEPTED; passive Web route/worker contributions and effect-safe cleanup |
| Search | bounded non-opening Actor search capability | existing Tool contribution; Browser remains foundation |
| Evidence | transient evidence/downgrade capability | ACCEPTED; one stateless module and canonical broker-backed command result |
| Context | application read projection and context Tool | last; consumes other Public reads |

Browser is not a product lane. It remains an Actor foundation capability.

All six lanes are accepted. See
`04-independent-component-waves-plan/search/S4-SEARCH-ACCEPTANCE.md` and
`04-independent-component-waves-plan/track-artifact/S4-TRACK-ARTIFACT-ACCEPTANCE.md`
`04-independent-component-waves-plan/evidence/S4-EVIDENCE-ACCEPTANCE.md` and
`04-independent-component-waves-plan/communication/S4-COMMUNICATION-ACCEPTANCE.md`
and `04-independent-component-waves-plan/context/S4-CONTEXT-ACCEPTANCE.md`.
Context is selected once and last; no S4 packet remains executable.

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

Every lane is accepted and the remaining Foundation-wide scanner, host,
lifecycle, identity and technical-root targets are assigned to the fresh S5
trace. S4 is closed; a vague “foundation cleanup later” remains insufficient
for S5 READY.

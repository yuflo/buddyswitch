# S4 Wave Dependency and Host-Contract Audit

> Audit source: `e4fe342144febc023d1d635012e7e8a5e645138d`
> Initial audit result: Search executed first.
> 2026-07-31 refresh: Track–Artifact is accepted and Evidence is READY through
> the existing Tool contribution; Communication and Context remain
> preparation-only.

## 1. Why S4 is lane-sized

The current six capability/product surfaces have different reasons for being
scattered:

| Lane | Current source shape | Cross-owner input | Host contribution/lifecycle |
|---|---|---|---|
| Search | one stateless Tool package plus profile reads | runtime profile and generic instance facts | Tool only |
| Track | Tool, repo/domain, comments, inbound, Skill, UI projection | Artifact relations and identity | Tool, Daemon/inbound, Web, Skill, cleanup |
| Artifact | Tool, repo/domain, visibility/relations, selection, Skill | Track relation semantics | Tool, Skill, cleanup |
| Communication | Message Tool/repo plus IM routing/session/channel | identity, external session | Tool, inbound/Daemon, Web, worker lifecycle, cleanup |
| Evidence | Tool plus broker-backed stable command adapter | Artifact Public and generic Runtime Broker | Tool |
| Context | broad read projection in ToolContext and Context Tool | every accepted product Public read | Tool/application projection |

Therefore one shared move template would either omit real boundaries or invent
a speculative universal plugin/lifecycle framework. Both violate the accepted
architecture.

## 2. Dependency order

```text
Search

Track <-> Artifact
  requires an exact Public/input-port decision before either cutover

Communication
  requires one worker-lifecycle contribution contract

Artifact accepted
  -> Evidence

all preceding Public read surfaces accepted
  -> Context
```

Search is independent of that chain. It reads a profile and instance facts,
owns no canonical state, emits no Daemon/Web/CLI/Skill/cleanup contribution,
and performs no Browser action.

## 3. Search host-contract decision

The current passive `ModuleAssembly` already carries exactly the required
Search surface:

```text
ModuleAssembly.tools -> ToolRegistration(DEFINITION, invoke)
```

No `ModuleAssembly` field, registry contract, Browser contract, service
locator, plugin loader or discovery mechanism is needed.

Search behavior is intentionally narrower than Browser:

- `search.status` reports configured backend and Browser readiness metadata;
- `search.request` validates explicit backend/query/engine and returns a URL
  plan;
- `search.request` returns `page_opened=false`;
- actual page opening remains
  `chrome-devtools-cockpit.search_page` in the Browser foundation surface.

The unused `BrowserAccess.request(...)` method is not a valid Search contract.
It is a Search-specific placeholder in a generic host and must disappear with
the Search move. The later Evidence refresh proved the two Evidence-shaped
methods were unused placeholders and assigns their removal to Evidence R1;
`BrowserAccess.status` remains foundation truth.

## 4. Representative final-topology preflight

Hub probe `S4SEARCHP-20260730-02` constructed a passive Search assembly from
the current `DEFINITION` and `invoke`, then exercised the real application and
registry boundaries without editing the repository.

Observed:

```text
module order:
  demand, task, search

daemon order:
  demand_triage, task_goal, demand_orchestration

positive dispatch:
  search.status PASS

old plus new path:
  "tool 'search' is both explicitly registered and package-discovered"

duplicate Search module:
  "duplicate module: search"
```

This proves:

1. the existing Tool contribution is sufficient;
2. Search does not disturb Daemon order;
3. application activation can dispatch Search explicitly;
4. old package deletion and new contribution must be one atomic cutover;
5. current duplicate guards fail closed.

This Search preflight did not authorize another S4 lane. Evidence was admitted
later by its own committed-source trace, preservation evidence, boundary
decision, and `EVIDENCEP-20260731-01` topology preflight.

## 5. S4 sequencing rule

After Search returns, the hub accepts or rejects that exact candidate before
preparing another lane. Parallel execution remains possible only if a later
source refresh proves disjoint owners, frozen host contracts, disjoint write
sets and one application-root integration owner. That condition is not
currently established and is not implied by S4's name.

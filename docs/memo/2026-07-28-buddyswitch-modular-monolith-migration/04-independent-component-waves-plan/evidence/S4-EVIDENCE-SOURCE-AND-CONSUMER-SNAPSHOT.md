# S4 Evidence Source and Consumer Snapshot

> Snapshot date: 2026-07-31
> Snapshot HEAD/tree: `ba292e9781400ee55ecf75a0da0271bb79c87324` /
> `3bdb9a687fae8b8a28a253639c931844560b734e`
> Branch/worktree: `fea-tool` /
> `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`

## 1. Identity

At refresh, tracked, indexed, and untracked identities were all empty SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
`git diff --check` was clean.

The installed runtime verified:

```text
activated_at:        2026-07-30T12:30:57.935144Z
source_digest:       e36160bf6172d497827394eb687fe073082a60faa136a91965390c833f14fa1f
distribution_digest: 2d09c0a2e120ffa64a8868c221d58a1ece590a28a3f42ee1f069e9241a774b13
package_version:     0.1.0
runtime.verify:       ok=true
```

The preparation commit may advance HEAD through coordinating documents only.
Any executable source, test, fixture, package, or runtime-asset delta from this
snapshot invalidates READY.

## 2. Current owner and consumer map

### Evidence-owned implementation

```text
src/buddyswitch/env/tools/evidence/__init__.py
src/buddyswitch/env/tools/evidence/tool.py
src/buddyswitch/env/tools/evidence/_impl.py
src/buddyswitch/runtime_support/browser_evidence.py
```

### Stable consumer and composition surfaces

```text
src/buddyswitch/application/composition.py
src/buddyswitch/application/entrypoints/browser_evidence.py
src/buddyswitch/env/tool_runtime/context.py
src/buddyswitch/modules/artifact/public/**
```

The material source path/content digest covering the current Evidence package,
stable entrypoint, runtime helper, and host context is:

```text
1608421bcbc7979c46266d8099a5ef529f3cebe11268d09f2b18a2d8fe50fcf2
```

### Current tests and projections

The direct consumer proofs are:

```text
tests/integration/env_tool/test_evidence.py
tests/integration/browser/test_market_evidence.py
tests/integration/browser/market_evidence_harness.py
tests/process/browser/test_browser_evidence_cli.py
```

Cross-capability and representation proofs include Tool catalog/schema/
semantics, Runtime Broker, Native MCP, Context affordances, host decisions,
application composition, dynamic package discovery, package correspondence,
Role authority, and the Search host-boundary test. These remain root-owned
because they observe more than one module or a foundation/runtime boundary.

## 3. Current behavior

Evidence owns exactly two Tool actions:

- `evidence.issue_browser`;
- `evidence.approve_downgrade`.

Both require an active-actor-authored Artifact target resolved through
`buddyswitch.modules.artifact.public.resolve_evidence_target`. They return
transient token metadata with `durability=transient`,
`mutates_product_state=false`, and no durable Evidence object. Rejections
leave no token metadata or product-state change.

The stable command
`python -m buddyswitch.application.entrypoints.browser_evidence` sends an
`env.tool` request through Runtime Broker. Despite its historical filename,
the helper does not open, own, inspect, start, stop, or otherwise call Browser
lifecycle.

`BrowserAccess.issue_evidence_token` and
`BrowserAccess.approve_downgrade` have no current caller. Their real semantics
are independently implemented by the Evidence Tool, so they are unused
product-shaped host placeholders. `BrowserAccess.status` remains a current
Browser foundation fact.

## 4. Refactor-entry evidence

Direct Evidence preservation:

```text
run:    244e12758d9f41bebe4bd3754ab1f163
result: 9 passed
scope:  Evidence Tool, Market evidence, stable CLI
cleanup: run root absent
```

Affected representation and integration preservation:

```text
run:    158f68a5d618496eb8444310f621162a
result: 143 passed, 540 subtests passed
scope:  registry/catalog/schema, host decisions, Context, Runtime Broker,
        architecture, dynamic Tool paths, Native MCP, package distribution
cleanup: run root absent
```

Both runs are source/runtime-equivalent to the snapshot. This is a
behavior-preserving refactor entry; the executor must not manufacture a
behavioral RED.

## 5. Why Evidence is next

Evidence can complete through the existing `ModuleAssembly.tools`
contribution and the already accepted Artifact Public operation. It needs no
new host contract and no persisted-state migration.

Communication remains preparation-only because its iMessage channel worker is
started and stopped inside WebHost. `inbound_sources` covers event
subscription, not side-worker lifetime. Moving Communication now would leave
the executor to invent a new lifecycle contribution. Context remains last
because it composes accepted Public reads from all product/capability modules.

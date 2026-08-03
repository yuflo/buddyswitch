# S4 Communication Source and Consumer Snapshot

> Snapshot date: 2026-08-03
> Snapshot HEAD/tree: `0b2462beffaa775980b096b7504bef341fb907bd` /
> `1fa512c61fd4cdf3d5590381acbae55e08baf961`
> Branch/worktree: `fea-tool` /
> `/Users/chen/Dev/buddyswitch/.worktrees/fea-tool`

## 1. Source and runtime identity

Tracked, index and untracked state were clean. `git diff --check` passed and
no `/private/tmp/bs-test-*` root remained.

The 25-path material production snapshot has:

```text
path-set SHA-256:              eca3968ebc65d6013077eddfa83713472a1c79a698cbc18c0a47b251c5a28ec1
path/content manifest SHA-256: 6d8d3837f358bcedb8ce48f7d3fb8c6ee697e0745dca0c33526bfd381c52f8f8
```

Installed runtime verification:

```text
activated_at:        2026-07-31T09:22:16.244005Z
source_digest:       cf8909b292e0a31c0ba0d4819594185d2bb06d9a7c5e20031e69ea3464d0d5ca
distribution_digest: 682351bc4b12e19067e0c98f8dc0595dee7c23de81d33662d815b2e42dbb6aca
package_version:     0.1.0
runtime.verify:       ok=true
```

The preparation commit may advance HEAD through coordinating documents only.
Any executable source, test, fixture, package or runtime-asset delta from this
snapshot invalidates the packet.

## 2. Scattered current owner

Message state and semantics:

```text
src/buddyswitch/env/repos/messages.py
src/buddyswitch/env/services/messages.py
src/buddyswitch/env/tools/message/**
```

Actor-side adapters:

```text
src/buddyswitch/env/tool_runtime/im_client.py
src/buddyswitch/env/tool_runtime/im_actor_delivery.py
src/buddyswitch/launcher/message_inbound.py
src/buddyswitch/launcher/im_wake_handler.py
```

External/Web/channel adapters:

```text
src/buddyswitch/launcher/external_im_session.py
src/buddyswitch/launcher/im_http_router.py
src/buddyswitch/launcher/web_im_identity.py
src/buddyswitch/launcher/imessage_channel.py
```

Communication-specific behavior is also embedded in generic hosts:

- `launcher/web_management.py` imports every concrete IM Web/channel adapter,
  constructs the route/session/identity, hard-codes the Actor Console `im`
  section and owns the iMessage worker lifetime;
- `launcher/instance_daemon.py` imports `message_inbound` directly;
- `runtime_support/env_cleanup.py` parses Message schema, sender/recipient
  roles, records and retired Message paths;
- `env/tool_runtime/context.py` exposes Message repository and IM-delivery
  objects as generic host context.

## 3. Real cross-owner consumers

Demand's triage runtime calls four Message operations to verify and emit one
handled reply:

```text
get_im_message
list_im_replies
send_im_message
get_im_message (post-write verification)
```

Context reads identity-visible Message events to build `message_cues`.
These are real Public consumers and cannot be replaced by private imports or a
generic service locator.

Communication's IM inbound handler causes Demand attention. The current
private-to-private import of `modules.demand.public` from the scattered wake
handler would create a Public cycle once Demand imports Communication Public.
Application composition must therefore inject Demand's exact
`enqueue_inbound` callable into Communication.

## 4. Current behavior to preserve

- Tool ID `message` and actions `contacts`, `conversation`, `get`, `list`,
  `send` retain schemas, authority, ToolResult envelopes and effects.
- Messages remain immutable Central IM rows with identity visibility,
  conversation/reply edges and exact post-write delivery status.
- `im.message.created` remains one identity-targeted Daemon inbound source;
  successful handling enqueues exactly one Demand ingress fact.
- `/api/im/*`, Web's stable external identity and iMessage behavior remain
  unchanged.
- iMessage worker start failure remains fail-soft; only a started worker is
  stopped, and it stops before the Web server closes.
- role cleanup selects a Message when either sender or recipient belongs to
  the role; all-data cleanup removes all Message rows and retains the current
  plan/result projections and warnings.

## 5. Refactor-entry evidence

Direct product behavior:

```text
run:    81501321bd0845149719c13e7d941d8b
result: 164 passed, 69 subtests passed
scope:  tests/unit/im, tests/integration/im, Message Tool integration
```

Affected non-process behavior:

```text
run:    7d8932ce647640e39068872988848089
result: 241 passed, 793 subtests passed
scope:  Demand, Web, Daemon, cleanup, Context, Tool schema/catalog/contracts
```

Affected process/package behavior:

```text
run:    1872a4bf43f74d73bd16bd04a296e54a
result: 86 passed, 167 subtests passed
scope:  black-box Tool, package independence, Native MCP, public CLI,
        distribution/activation and Runtime Broker
```

All three roots were absent after completion. This is a behavior-preserving
refactor entry; do not manufacture a behavioral RED. Add RED only for the new
topology/host contracts and retired-residue assertions.

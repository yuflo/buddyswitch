# S5 Source Refresh and Cutover Blueprint

## 1. Observable stage outcome

> Foundation imports no concrete component or Role implementation and owns
> only product-neutral lifecycle, protocol, transport, identity, state and
> process behavior; product meaning enters through explicit application
> composition, typed contributions or Public operations.

The consumer path remains:

```text
consumer action
  -> application-selected host operation
  -> Foundation protocol/lifecycle
  -> explicitly selected component Public/adapter
  -> observable result, state effect or exact failure
```

S5 changes ownership and physical locality. It does not change accepted Demand,
Task, Search, Track, Artifact, Evidence, Communication or Context semantics.

## 2. Refreshed source facts

The current technical roots contain roughly 27,000 lines and combine unrelated
change reasons:

- explicit application composition already exists;
- `env/tool_runtime/**` still combines generic Tool protocol, package discovery,
  Role authorization, Daemon transport and broad host data bags;
- `launcher/web_management.py` still imports Track and owns two Track routes;
- cleanup still names product projection fields although components already
  contribute cleanup ownership;
- Browser lifecycle is spread across `env/**`, `launcher/**` and Broker calls;
- identity, locators, process lifecycle, Daemon, Broker, Actor and host entry
  code remain physically split across technical-history roots;
- current Role manifest/profile/Skill policy remains S6-owned and must not be
  redesigned inside S5.

There is no live checkout Python loader after S1. The remaining dynamic source
discovery is the Tool package scanner in `env/tool_runtime/registry.py`.

## 3. Target Foundation topology

```text
src/buddyswitch/
├── application/                 # sole explicit composition root
├── foundation/
│   ├── composition/             # typed module/contribution contracts
│   ├── identity/                # product-neutral Actor identity primitives
│   ├── state/                   # locators, atomic state and private-root safety
│   ├── actor_runtime/           # Actor lifecycle and projection host
│   ├── process_runtime/         # activation, invocation and process ownership
│   ├── app_server/              # app-server lifecycle
│   ├── daemon/                  # product-neutral Daemon transport/host
│   ├── runtime_broker/          # local Broker protocol/dispatch/lifecycle
│   ├── tool_runtime/            # explicit ToolHost protocol and dispatch
│   ├── browser_runtime/         # one Actor-scoped Browser lifecycle owner
│   ├── web_runtime/             # generic route/worker/console host
│   ├── cli_runtime/             # generic CLI host
│   └── role_host/               # S6-owned final Role selection host
├── modules/                     # accepted product modules
└── runtime_support/             # shrinks as owners converge; Role policy stays
                                 # here only until S6 replaces it
```

This is a modular monolith. It does not add a service mesh, event bus, generic
plugin loader, dependency-injection container or runtime module discovery.

## 4. Why S5 is checkpointed

One S5 packet would mix at least four distinct operational risks:

1. Tool catalog, authorization and terminal-result semantics;
2. HTTP routing, worker lifetime and destructive cleanup projection;
3. Browser child-process, lease and page-target lifetime;
4. Daemon/Broker/App/Actor process and identity lifecycle.

They do not share one shortest proof loop. Treating them as one change would
make failures hard to attribute and force one executor to keep a huge dirty
candidate alive. Checkpoints therefore follow semantic owners and dependency
order, not arbitrary file counts.

## 5. Ordered cutover units

### C1 — ToolHost

- replace package scanning with explicit-only registrations;
- move generic Tool runtime to `foundation/tool_runtime/**`;
- narrow ToolContext to used host facts and capabilities;
- move generic Daemon client to `foundation/daemon/client.py`;
- move current Role policy out of Foundation and inject authorization;
- remove old Tool runtime/package roots and update every consumer atomically.

### C2 — Web and cleanup

- Track contributes its external read routes;
- generic WebHost imports no concrete module and matches exact/prefixed routes;
- cleanup output/projection is derived from typed component contributions;
- CLI is re-proved product-neutral; no manufactured rewrite is required.

### C3 — Browser runtime

- one `foundation/browser_runtime/**` physical owner;
- public internal operations replace cross-owner private-method calls;
- Actor-scoped acquisition, readiness, lease, target and cleanup remain exact.

### C4 — Identity, state and process primitives

- converge identity and locator/state primitives under Foundation;
- preserve canonical state roots and one write path;
- converge process activation/invocation/lifecycle without product imports.

### C5A — Runtime Broker

- converge Broker protocol, dispatch, coordination, client/server and lifecycle
  into one earned `foundation/runtime_broker/**` owner;
- extract the already-shared Content-Length JSON socket framing into one direct
  process-runtime primitive used by Broker and Daemon;
- delete the retired `runtime_kernel/**` root after every live consumer moves;
- preserve Broker envelopes, locking, retries, identity checks, service
  lifecycle and Tool/Browser dispatch exactly.

### C5B — Daemon

- converge central and instance Daemon transport/host ownership;
- Daemon remains subscription/strategy plus registered handler execution;
- no central product handler switch or content interpretation enters the host.

### C6 — Actor, App, Web and CLI hosts

- converge remaining host and packaged asset ownership;
- keep interface ownership separate from product semantics;
- delete retired `env/**` and `launcher/**` roots only when
  every live consumer has moved.

### C7 — S5 acceptance

- replace current architecture guidance with final Foundation truth;
- close all S5-owned residue with source-bound absence proof;
- run exact/affected acceptance and one frozen full candidate;
- leave S6 one clean RoleHost input, not an S5 compatibility seam.

## 6. Dependency rule

Each checkpoint must leave one complete runnable product path. No checkpoint
may create old/new aliases, fallback imports, dual registration, a service
locator or an intermediate path that only a later checkpoint repairs.

Later work may consume a current contract created earlier, but it may not make
an earlier checkpoint semantically incomplete. If source refresh disproves this
property, the checkpoint is replanned before implementation.

## 7. Stage-wide protected contracts

- all accepted component Public operations and Tool actions;
- Daemon ordering and failure isolation;
- native MCP names/schema/result semantics;
- state paths, Actor-private safety and source/runtime identity;
- Web/CLI observable routes and commands;
- Browser Actor-scoped lifecycle and cleanup;
- Role authorization behavior until S6 intentionally replaces its owner.

Internal Python import paths and historical technical roots are not protected.

## 8. Stage-wide stop conditions

Stop and return `REPLANNING REQUIRED` if a checkpoint requires:

- changing accepted product semantics or component Public contracts outside its
  explicitly named mechanical contribution;
- Role package discovery or final RoleHost selection before S6;
- a compatibility alias, fallback, dual write or dual registry;
- a generic plugin framework, DI container, service split or event bus;
- changing canonical state paths or irreversible data;
- executing a later checkpoint to make the current candidate runnable.

An executor may repair owner-correct implementation and tests inside the
classified write set. It owns exact test-target discovery under the public
runner contract; mechanically stale command text is not a reason to preserve a
wrong target.

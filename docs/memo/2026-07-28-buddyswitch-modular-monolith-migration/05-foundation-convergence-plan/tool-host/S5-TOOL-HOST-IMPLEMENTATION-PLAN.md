# S5 C1 ToolHost Implementation Plan

## Status

`READY` for packet `BS-MM-S5-TOOLHOST-R1-20260804-01` only.

## FRAME

### Bottleneck

The application already selects every current Tool explicitly, but the live
ToolHost still scans a package tree, dynamically imports Tool code, owns Role
policy and exposes broad repository/domain/browser/private-file bags through
ToolContext. Adding or changing a module therefore still touches or depends on
historical central runtime surfaces.

### Acceptance sentence

> Every env Tool is selected exactly once by explicit application composition;
> Foundation ToolHost owns only generic schema, catalog, authorization
> invocation, feedback and host facts, imports no component or Role
> implementation, and no package scanner, old env Tool runtime path, broad
> repository/domain bag or unused ToolContext capability remains.

### Consumer-observable path

```text
native MCP / admin env client / Actor runtime Broker
  -> Foundation explicit ToolHost catalog and dispatch
  -> selected component Tool adapter
  -> unchanged result, state effect, authorization or terminal error
```

### Protected contracts

- Tool IDs, actions, payload schemas, native MCP names and catalog order;
- success/rejection result shapes and terminal-state truth;
- active-Task gate and selected implementation failure isolation;
- current Role authorization behavior and receipts;
- Actor directory and signal-delivery behavior;
- Actor-private path safety;
- runtime Broker protocol and installed-runtime attribution.

Internal Python paths, Tool package discovery and broad unused context fields
are not protected contracts.

## TRACE

Read the source snapshot and consumer manifest. Before editing, regenerate the
following representation classes against the executor's exact source:

1. direct and parent Python imports;
2. dynamic import strings;
3. literal source/package paths;
4. package/discovery assertions;
5. embedded subprocess scripts;
6. native MCP and CLI catalog enumerations;
7. installed-package projections;
8. current guidance.

Any live consumer not classifiable under the write set is a stop condition.
Do not silently omit it or add it after a failed final run.

## PROVE

This is a refactor/replacement entry, not a manufactured product RED. Preserve
the green ToolHost baseline and add the nearest final-topology assertions that
can detect:

- explicit catalog completeness and duplicate/invalid startup failure;
- absence of scanner/dynamic Tool imports and old package root;
- Foundation-to-component/Role import prohibition;
- narrow ToolContext shape and the two mechanical consumer replacements;
- old source/import/guidance absence;
- exact native MCP, Broker and terminal result behavior.

Run proof through `./buddyswitch-test focused ...`. The executor owns exact
target discovery and command construction under the repository runner contract.
Targets must be valid runner leaves/tiers; a stale planning example never
overrides the runner.

## BUILD — coherent block A: generic contracts and policy inversion

1. Create `foundation/tool_runtime/**` and `foundation/daemon/**` owners.
2. Define the generic authorization decision/callable contract in ToolHost.
3. Move current Role policy intact to `runtime_support/role_auth.py`; it may
   depend on the generic decision contract.
4. Configure the authorizer explicitly from application activation. Foundation
   must not import the Role policy implementation.
5. Preserve active-Task probe configuration without introducing a registry or
   container beyond the existing explicit application composition.

## BUILD — coherent block B: explicit-only registry

1. Move Tool schema, result, feedback, native MCP and Broker adapter code to the
   final owner.
2. Delete package discovery, dynamic Tool import, definition cache and load
   error state.
3. Derive supported Tools/actions/catalog only from validated explicit
   registrations.
4. Fail duplicate or invalid registrations during application build/activation.
5. Preserve consumer-required `tool_catalog_errors` projection as an empty
   current value if its output remains part of Context; do not retain discovery
   state to manufacture it.
6. Remove discovery-only reset APIs and rewrite tests around explicit
   application/registration setup.

## BUILD — coherent block C: narrow ToolContext

1. Retain only used identity/instance/manifest/invocation facts, time/ID helpers,
   Actor directory and signal delivery.
2. Add explicit `actor_private_root: Path`, resolved by the host using the
   current safe state locator.
3. Change Artifact to consume that fact.
4. Change Evidence to consume `context.now()`.
5. Delete `DomainAccess`, `RepoAccess`, `ActorPrivateAccess`, `BrowserAccess`
   and their context attributes.
6. Do not hide them behind a new `services`, `capabilities`, repository or
   dependency bag.

The underlying identity/state primitives may remain at their current C4-owned
physical paths during C1. C1 removes semantic breadth from ToolContext; it does
not pull C4 forward.

## BUILD — coherent block D: direct physical cutover

Perform direct moves with no old-path module:

```text
env/tool_runtime/__init__.py       -> foundation/tool_runtime/__init__.py
env/tool_runtime/auth_feedback.py  -> foundation/tool_runtime/auth_feedback.py
env/tool_runtime/broker_client.py  -> foundation/tool_runtime/broker_client.py
env/tool_runtime/context.py        -> foundation/tool_runtime/context.py
env/tool_runtime/definition.py     -> foundation/tool_runtime/definition.py
env/tool_runtime/native_mcp.py     -> foundation/tool_runtime/native_mcp.py
env/tool_runtime/registry.py       -> foundation/tool_runtime/registry.py
env/tool_runtime/results.py        -> foundation/tool_runtime/results.py
env/client.py                      -> foundation/tool_runtime/client.py
launcher/env_tool_mcp_server.py    -> foundation/tool_runtime/mcp_server.py
env/tool_runtime/daemon_client.py  -> foundation/daemon/client.py
env/tool_runtime/role_auth.py      -> runtime_support/role_auth.py
```

Update every production/test/guidance consumer in the same candidate. Delete
`env/tool_runtime/**`, tracked `env/tools/__init__.py` and empty retired roots.
Do not create aliases, compatibility imports or fallback reads.

## REPLACE

Replacement is complete only when:

- `buddyswitch.env.tool_runtime`, `buddyswitch.env.client` and
  `buddyswitch.launcher.env_tool_mcp_server` cannot be imported;
- no runtime scanner or dynamic Tool module loader remains;
- no live code or current guidance teaches `src/buddyswitch/env/tools` or the
  old ToolHost paths;
- old terms in tests are negative absence guards only;
- temporary discovered-package tests are replaced by explicit registration and
  selected-implementation isolation tests;
- all eight component Tools are selected once by application composition.

## VERIFY

### Proof classes

1. **Product:** representative read and mutating Tool operations traverse the
   real Broker and return exact terminal results.
2. **Contract:** catalog/schema/native MCP, authorization, active-Task gate,
   unknown Tool/action and unavailable transport remain exact.
3. **Architecture:** explicit completeness, invalid/duplicate startup failure,
   narrow context and dependency direction.
4. **Replacement:** old paths, scanner, discovery imports and broad bags absent.
5. **Operations:** installed source identity, runtime activation, process/root
   cleanup and selected implementation failure isolation.

### Candidate cycle

After the coherent C1 source mutation, activate/reprovision and verify the
installed source/distribution identity before any public-runner command. Then
run final-topology, direct behavior and affected consumer groups. If a failure
is attributable to the C1 candidate and within the classified write set,
repair the owner, reprovision the changed source before the next runner command,
rerun the affected proof, and continue. If it requires semantic/scope
expansion, stop.

When exact and affected proof are green and residual state is clean, freeze
that already verified source/runtime identity and run one
`./buddyswitch-test full` as the C1 acceptance candidate.

If the frozen full exposes an attributable in-scope defect, the candidate is no
longer frozen: repair it, reprovision and verify the changed runtime, repeat
exact/affected proof, then freeze a new identity and run one full for that new
candidate. Never rerun an unchanged failed identity merely to seek a pass. An
out-of-scope or ambiguous failure is `REPLANNING REQUIRED`.

This rule avoids both forbidden retry roulette and the earlier contradictory
state where a failed pre-run gate prohibited the reprovision needed to satisfy
that gate.

## ACCEPT

The return packet must contain:

- starting and final source, patch and untracked identities;
- exact changed/deleted path set;
- regenerated consumer representation inventory;
- final explicit Tool IDs and registration owner;
- final ToolContext public field/capability list;
- exact/affected/frozen-full run identities and results;
- runtime activation/source/distribution identity;
- negative old-path/scanner/import proof;
- cleanup proof and omitted checks;
- proposed residue closure, without editing master migration truth.

## Classified write set

Allowed:

- the exact source owners and consumers named in the snapshot/manifest;
- component Tool adapter imports and the two mechanical context replacements;
- directly affected unit/integration/process/architecture tests;
- current root README ToolHost owner lines;
- C1-local execution-state/result memo if needed.

Forbidden:

- component domain/state/Public semantics;
- Web/cleanup/Browser/Daemon-host/Broker-host redesign;
- Role manifest/profile/Skill/Role package design;
- canonical state paths or data migration;
- S5 master ledger, decision/residue truth, commits or pushes;
- unrelated cleanup.

## Stop conditions

Stop before expanding scope if:

- a current Tool genuinely requires dynamic discovery;
- explicit-only registration cannot preserve current catalog/native MCP output;
- Role behavior cannot be preserved by capability inversion alone;
- Browser, Web, cleanup, Broker-host or RoleHost semantics must change;
- a compatibility layer appears necessary;
- source/runtime identity cannot be made one-to-one;
- a failure is outside the classified write set or its cause is ambiguous.

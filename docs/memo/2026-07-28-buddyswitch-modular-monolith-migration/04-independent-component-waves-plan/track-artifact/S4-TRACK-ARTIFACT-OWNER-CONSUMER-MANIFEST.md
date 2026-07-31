# S4 Track–Artifact Owner and Consumer Manifest

> Packet: `BS-MM-S4-TRACK-ARTIFACT-R1-20260730-01`
> R2 correction: `BS-MM-S4-TRACK-ARTIFACT-R2-20260731-01`
> Rule: product writes stay inside the classes below; an unclassified semantic
> or shared-host change stops execution.

## 1. Final physical owners

The final roots are:

```text
src/buddyswitch/modules/track/**
src/buddyswitch/modules/artifact/**
```

Each root contains:

- one passive `module.py`;
- a small `public/` contract and operation surface;
- all of its own state, domain, read-model and adapter code under `private/`;
- its own Skills and runtime assets;
- its own unit/integration tests.

The approved design intentionally leaves Private file splitting to the
executor. A new shared Track–Artifact package, relationship service, generic
dependency map or registry is forbidden.

## 2. OWNER writes

### Track — create/move

Authorized:

```text
src/buddyswitch/modules/track/**
```

This owner absorbs:

```text
src/buddyswitch/env/repos/tracks.py
src/buddyswitch/env/repos/track_comments.py
src/buddyswitch/env/domain/track_comments.py
src/buddyswitch/env/domain/track_read.py
src/buddyswitch/env/domain/track_artifact_relations.py
src/buddyswitch/env/tools/track/**
src/buddyswitch/launcher/track_comment_inbound.py
src/buddyswitch/launcher/track_comment_added_handler.py
src/buddyswitch/skills/shared/track-tool/**
src/buddyswitch/skills/pm/triage-track/**
```

### Artifact — create/move

Authorized:

```text
src/buddyswitch/modules/artifact/**
```

This owner absorbs:

```text
src/buddyswitch/env/repos/artifacts.py
src/buddyswitch/env/domain/artifact_visibility.py
src/buddyswitch/env/domain/artifact_relations.py
src/buddyswitch/env/domain/source_refs.py
src/buddyswitch/env/tools/artifact/**
src/buddyswitch/runtime_support/artifact_selection.py
src/buddyswitch/config/artifact-selection-v1.json
src/buddyswitch/config/artifact-selection-v2.json
src/buddyswitch/skills/shared/artifact-tool/**
```

Every absorbed path is deleted in the same candidate. No forwarding import,
alias, wrapper, fallback read or duplicate asset remains.

## 3. COMPOSITION and host-contract writes

Authorized exact shared sources:

- `src/buddyswitch/foundation/composition/__init__.py`
  - add only `inbound_sources` to `ModuleAssembly`;
- `src/buddyswitch/application/build.py`
  - flatten and validate `inbound_sources`;
  - reject duplicate component event types;
  - retain existing duplicate checks and contribution semantics;
- `src/buddyswitch/application/composition.py`
  - construct Artifact;
  - inject the two approved Artifact Public callables into Track;
  - select Artifact and Track exactly once;
- `src/buddyswitch/application/entrypoints/instance_daemon.py`
  - pass the application inbound-source tuple to the generic Daemon;
- `src/buddyswitch/launcher/instance_daemon.py`
  - consume contributed Track inbound registration;
  - remove its Track import;
  - retain Message and Browser behavior until their own lanes;
- `src/buddyswitch/application/entrypoints/artifact_selection.py`
  - delegate to the Artifact-owned entrypoint without changing command
    behavior.

No second host field, bus, plugin loader, locator, DI container or dynamic
module discovery is authorized.

## 4. Product-neutral host cleanup

Authorized exact shared sources:

- `src/buddyswitch/env/tool_runtime/context.py`
  - remove Track, Track-comment and Artifact repositories/rules and unused
    runtime-object methods;
- `src/buddyswitch/env/repos/runtime_files.py`
  - remove Track/Artifact directory constants and eager creation;
  - preserve generic roots, file helpers, identity/time utilities and all
    unrelated product paths;
- `src/buddyswitch/runtime_support/env_cleanup.py`
  - remove Track/Artifact discovery and path ownership;
  - preserve cleanup contracts, orchestration and unrelated categories.

Track and Artifact calculate the same durable paths privately from generic
runtime roots. Storage names and record formats do not change.

## 5. Direct consumer edge changes

Authorized exact production consumers:

- `src/buddyswitch/env/tools/context/_impl.py`
  - replace Track/Artifact private access with approved Public projections;
  - do not migrate or redesign Context;
- `src/buddyswitch/env/tools/evidence/_impl.py`
  - replace Artifact repository access with
    `resolve_evidence_target`;
  - do not migrate or redesign Evidence;
- `src/buddyswitch/launcher/cli.py`
  - use Track Public external projections;
- `src/buddyswitch/launcher/web_management.py`
  - use Track Public external and Actor Console projections.

Only dependency edges change. Result schemas, route/command behavior,
permission decisions and effects remain exact.

## 6. Package, manifest and current-doc writes

Authorized:

- `pyproject.toml`
  - package Track/Artifact module Skills and Artifact assets;
- `src/buddyswitch/catalog/manifest.toml`
  - replace the three retired shared Skill paths with module-owned paths while
    preserving Skill IDs and role membership;
- `README.md`;
- `docs/arch/daemon-service-architecture.md`;
- `docs/arch/web-interface-call-architecture.md`;
- create `docs/arch/track-capability-architecture.md`;
- create `docs/arch/artifact-capability-architecture.md`.

Current docs name final owners and contracts only. Historical memos may retain
old paths as history or negative residue assertions.

## 7. Owning-test relocation and proof writes

Only tests whose behavior and fixtures stay inside one module move beneath that
module's test root. Cross-component tests remain in the root test tiers even
when one product capability dominates their name. Their assertions and
fixtures remain semantically equivalent while imports and literal owner paths
change.

Final module-local tests:

```text
src/buddyswitch/modules/track/tests/integration/test_track_comment.py
src/buddyswitch/modules/track/tests/unit/test_comments_repo.py
src/buddyswitch/modules/artifact/tests/unit/test_artifact_selection.py
```

Final root-owned cross-component tests:

```text
tests/integration/env_tool/_artifact_env_tool_case.py
tests/integration/env_tool/test_artifact_attachments.py
tests/integration/env_tool/test_artifact_listing.py
tests/integration/env_tool/test_artifact_publication.py
tests/integration/env_tool/test_artifact_relations.py
tests/integration/env_tool/test_artifact_validation.py
tests/integration/env_tool/test_response_artifact.py
tests/integration/env_tool/test_track.py
tests/integration/track/test_comment_added_handler.py
tests/integration/track/test_owner_actor_model.py
```

The classification rule is semantic:

- a module-local test may import that module's Private implementation;
- a module-local test may consume another module only through its Public
  contract;
- a test that needs another module's Private fixture or proves a multi-module
  consumer path belongs in the root test tiers;
- root Process, System and repository Architecture tests remain root-owned.

Authorized root proof edits include these known direct consumers:

```text
tests/support/object_builders.py
tests/integration/env_tool/_artifact_env_tool_case.py
tests/integration/env_tool/test_artifact_attachments.py
tests/integration/env_tool/test_artifact_listing.py
tests/integration/env_tool/test_artifact_publication.py
tests/integration/env_tool/test_artifact_relations.py
tests/integration/env_tool/test_artifact_validation.py
tests/integration/env_tool/test_response_artifact.py
tests/integration/env_tool/test_track.py
tests/integration/env_tool/test_cleanup.py
tests/integration/env_tool/test_context_binding.py
tests/integration/env_tool/test_evidence.py
tests/integration/env_tool/test_host_decision_surface.py
tests/integration/env_tool/test_layer_end_to_end.py
tests/integration/track/test_comment_added_handler.py
tests/integration/track/test_owner_actor_model.py
tests/integration/im/test_external_query.py
tests/integration/im/test_identity_product_ownership.py
tests/integration/runtime/test_runless_contract.py
tests/integration/runtime/test_tool_feedback.py
tests/integration/web/test_management_http.py
tests/integration/web/test_management_product_api.py
tests/process/cli/test_cleanup_cli.py
tests/process/cli/test_env_layer_boundaries.py
tests/process/cli/test_env_tool_package_independence.py
tests/process/cli/test_env_tool_router.py
tests/process/cli/test_black_box_tool_runtime.py
tests/process/cli/test_env_native_mcp_projection.py
tests/process/package/test_distribution_install.py
tests/unit/actor/test_runtime_skills.py
tests/unit/architecture/test_demand_sys_boundaries.py
tests/unit/architecture/test_external_control.py
tests/unit/architecture/test_package_contract.py
tests/unit/architecture/test_repo_contracts.py
tests/unit/daemon/test_communication_boundary.py
tests/unit/daemon/test_contracts.py
tests/unit/daemon/test_decoupling.py
tests/unit/daemon/test_instance_entrypoint.py
tests/unit/im/test_notification_center.py
tests/unit/env_tool/test_manifest.py
```

Create:

```text
tests/unit/architecture/test_track_component_boundaries.py
tests/unit/architecture/test_artifact_component_boundaries.py
tests/unit/architecture/test_component_inbound_sources.py
```

The executor may update another current test without stopping only when all
of these are true:

1. target discovery proves it directly imports or asserts a retired path,
   package location, Skill location, registration source or generic-host
   Track/Artifact field;
2. the edit is a mechanical projection to the approved final owner;
3. no assertion strength, product behavior or shared contract meaning changes;
4. the extra path and reason are recorded in the result packet.

Any semantic test change, assertion weakening or new production write remains
unclassified and stops execution.

## 8. Proof-only consumers

All unchanged direct consumers discovered from current symbols, Tool IDs,
schemas, routes, cleanup categories, package assets and durable paths are
proof-only. The executor owns target discovery and may run them without hub
pre-enumeration.

A test directory is never assumed to be a runner target. The runner decides
valid target tiers; the executor supplies current file/node/tier targets after
discovery.

## 9. Representation completeness

| Representation | Required disposition |
|---|---|
| production and module-local direct Python imports | final Public or same-module Private import |
| module-local tests | own Private or another module's Public only |
| cross-component tests | root tier; no false module-local ownership |
| relative imports | remain inside one final owner |
| literal old paths | absent outside history/negative guards |
| Tool ID/action/schema | unchanged; one explicit registration each |
| dynamic Tool discovery | no `env/tools/track` or `env/tools/artifact` |
| component selection | Artifact and Track each selected once |
| Public graph | acyclic; no cross-Private edge |
| Track inbound source | contributed once; generic Daemon has no Track import |
| Context/Evidence/Web/CLI | approved Public edges only |
| runtime directory names | unchanged on disk, privately owned in source |
| cleanup categories/results | unchanged externally, contributed by owners |
| Skill IDs/role membership | unchanged; module-owned package paths |
| selection command/config | stable command/result; Artifact-owned code/assets |
| installed distribution | both modules/assets present; module tests absent |
| current guidance | final owners only |

## 10. Forbidden scope

- Communication component migration or Message/IM ownership changes;
- Evidence or Context component migration;
- Browser, App Server, actor worker or lifecycle redesign;
- durable schema/path migration or data rewrite;
- Tool, CLI, Web, selection-command, Daemon or Skill ID change;
- another assembly field or generic contribution framework;
- compatibility, re-export, fallback, dual registration or alternate root;
- migration master truth, packet history, Git commit/push/rebase/branch work;
- any S5–S7 implementation.

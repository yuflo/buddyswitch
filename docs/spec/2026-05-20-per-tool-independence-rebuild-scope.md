# Per-Tool Independence Rebuild Scope

Date: 2026-05-20

Source inputs:

- `docs/memo/2026-05-19-worktree-independence-review-memo.md`
- `docs/spec/2026-05-19-tool-independence-repair-scope.md`
- `docs/spec/2026-05-19-tool-independence-repair-test-plan.md`
- `docs/spec/2026-05-19-tool-independence-repair-implementation-plan.md`
- Current env.tool runtime under `scripts/env/tools/**`, `scripts/env/services/**`, `scripts/env/client.py`, and existing env.tool tests.

## Goal

Rebuild env.tool so each tool can be developed independently: changing one tool's actions, payload fields, semantics, CLI arguments, handler mapping, and service code must be local to that tool package and its tests.

This is a direct forward rebuild, not a compatibility migration. The old central hand-maintained tables and branch maps are removed, not preserved behind shims.

## Current State After The First Repair

The current repair plan moves the runtime in the right direction:

- default `python3` compatibility is repaired;
- dispatch imports are selected-tool lazy instead of eager service imports;
- services validate payload fields from one registry-backed helper;
- stale ignored payload fields are rejected;
- comment payload fields and CLI status filtering are aligned.

That repair still keeps these shared tool-development edit points:

- `scripts/env/tools/contracts.py` owns all tool/action/payload registry rows.
- `scripts/env/tools/semantics.py` owns all tool/action semantic rows.
- `scripts/env/tools/dispatch.py` owns all handler specs.
- `scripts/env/client.py` owns all CLI parser branches and payload builders.
- `scripts/env/services/*.py` keeps service entrypoints outside the tool that owns them.

Those files are acceptable for a small monolith repair, but they are not enough for complete per-tool independent development.

## Definition Of Tool Independence

Per-tool independence means all tool-specific ownership lives under one tool package:

```text
scripts/env/tools/<tool>/
  __init__.py
  contract.py
  semantics.py
  cli.py
  handlers.py
  service.py
```

For the shipped tools, the required packages are:

- `scripts/env/tools/task/`
- `scripts/env/tools/track/`
- `scripts/env/tools/artifact/`
- `scripts/env/tools/buddybox/`
- `scripts/env/tools/context/`
- `scripts/env/tools/evidence/`
- `scripts/env/tools/message/`
- `scripts/env/tools/comment/`
- `scripts/env/tools/search/`

Adding or changing an action for a tool must require only:

- files under `scripts/env/tools/<tool>/`;
- that tool's focused tests;
- shared domain/repo files only when product behavior genuinely crosses object boundaries.

It must not require editing a central action table, central semantics table, central dispatch map, or central CLI dispatch branch.

## Target Runtime Shape

Shared env.tool modules remain, but they are generic infrastructure:

- `scripts/env/tools/model.py` defines shared typed shapes and mutation constants.
- `scripts/env/tools/discovery.py` discovers local tool packages under `scripts/env/tools/`.
- `scripts/env/tools/catalog.py` projects tool catalogs and operation semantics from per-tool packages.
- `scripts/env/tools/dispatch.py` loads only the selected tool handler.
- `scripts/env/tools/router.py` validates the env.tool envelope and delegates to generic dispatch.
- `scripts/env/tools/responses.py` remains the shared response helper module.
- `scripts/env/client.py` builds the top-level CLI and lets tool packages register their own CLI subcommands.

The discovery mechanism is repo-local package discovery only. It is not an external plugin system, not a marketplace, not entry-point loading, not config-driven extension, and not a workflow engine.

## Required Direct Replacements

Delete or replace these central ownership points:

- Delete `TOOL_REGISTRY` as a central hand-written list.
- Delete central `_CAPABILITIES` / action semantics ownership from `scripts/env/tools/semantics.py`.
- Delete `HANDLER_SPECS_BY_TOOL` as a central hand-written handler map.
- Delete `_dispatch_task`, `_dispatch_track`, `_dispatch_artifact`, `_dispatch_context`, `_dispatch_buddybox`, `_dispatch_evidence`, `_dispatch_search`, `_dispatch_message`, and `_dispatch_comment` from `scripts/env/client.py`.
- Delete the tool service entrypoint modules under `scripts/env/services/` after their code is moved into tool packages.
- Delete `env.tools.contracts` as the runtime API and update callers to `env.tools.catalog`.

Do not keep compatibility aliases, import shims, duplicate registries, fallback registries, or dual dispatch paths.

## Product Coupling Rules

Per-tool independence does not mean false product independence.

Allowed cross-object domains:

- `env.domain.publication` may coordinate track and artifact publication.
- `env.domain.comment_targets` may coordinate comment target readability.
- `env.domain.artifact_visibility` may coordinate artifact visibility.
- `env.domain.tasks` may perform read-only task domain validation, including track reference checks when required by product semantics.
- `env.domain.source_refs` may normalize artifact provenance metadata, including buddybox logical-name provenance rules.
- `env.domain.buddybox_workspace` may expose shared buddybox workspace descriptors used by both buddybox and context tools.

Forbidden coupling:

- A tool package must not import another tool package.
- A tool package must not depend on another tool's service module.
- Context may include catalog output for all tools, but it must get that through generic catalog projection, not direct imports of tool services.
- Artifact source refs may refer to buddybox logical names as provenance, but that must not create buddybox read grants or require importing the buddybox tool.

## Key Questions This Task Must Answer

1. Can a developer add or change a tool action without editing central action, semantics, dispatch, or CLI maps?
2. Can catalog and operation semantics be generated from per-tool packages without loading service code?
3. Can CLI affordances be registered by each tool without central per-tool branches?
4. Can dispatch load only the selected tool handler and selected tool service?
5. Can a broken selected tool return structured feedback without breaking unrelated tools?
6. Can a broken non-selected tool's service avoid affecting unrelated dispatch?
7. Can context catalog generation report tool metadata load problems without crashing unrelated runtime context discovery?
8. Are track/artifact/comment product couplings still explicit in domain modules instead of direct tool imports?
9. Are the current tool actions and runtime behavior preserved after ownership is moved?
10. Are old central ownership files removed instead of left as compatibility surfaces?

## Non-Goals

- Do not change the shipped tool set.
- Do not change action names or product behavior except where necessary to remove central ownership.
- Do not split env.tool into external processes.
- Do not introduce a generic plugin framework.
- Do not add config-driven tools.
- Do not preserve `env.tools.contracts` imports as a shim.
- Do not keep `scripts/env/services/*.py` service entrypoints as wrappers.
- Do not edit runtime state under `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Definition Of Done

The rebuild is complete only when all of these are true:

1. All tool-specific contract, semantics, CLI registration, handler specs, and service entrypoints live under `scripts/env/tools/<tool>/`.
2. Shared env.tool files contain no hand-written action, payload, handler, or per-tool CLI maps.
3. `scripts/env/tools/contracts.py` and central `scripts/env/tools/semantics.py` are removed or replaced by non-authoritative deleted paths; runtime callers use `env.tools.catalog`.
4. `scripts/env/services/*.py` tool entrypoint modules are removed after their code moves into tool packages.
5. Public catalog/router/client imports are service-light.
6. Dispatching one tool imports no other tool service.
7. Tool packages do not import sibling tool packages.
8. Adding a local test probe tool package is discovered without central source edits.
9. Runtime catalog and operation semantics match the merged per-tool specs.
10. CLI commands and broker-routed env.tool behavior remain green for every shipped tool.
11. Relevant architecture tests, focused env.tool suites, broker/CLI suites, boundary suites, skill/catalog consistency suites, and full `python3 -m pytest -q` pass.
12. `git diff --check` passes.

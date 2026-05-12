# Env Tool Layer Rebuild And Residue Removal Memo

Date: 2026-05-12
Scope: BuddySwitch env tool architecture, runtime context surface, skill-facing host surface, and residue cleanup after the host decision surface work.

## Core Question

The previous implementation moved active BuddySwitch env operations behind the broker-routed `env.tool` envelope, but it left an internal and user-facing naming burden around "managers".

The question for the next pass is:

Should BuddySwitch treat the remaining `*_manager.py`, `_ACTION_MAP`, `manager_name`, and `task_manager` / `track_manager` runtime context surfaces as acceptable thin implementation details, or should they be removed as old structure?

The answer for the next pass should be:

Remove them. Rebuild forward to one clear env tool layer.

## Current Confirmed State

The active external entry point is already unified:

- The runtime broker accepts `env.tool` for buddy env operations.
- The env CLI builds `{"tool": ..., "action": ..., "args": ...}` payloads and sends them through `env.tool`.
- `scripts/env/tools/contracts.py` is the static registry for tool ids, action names, payload field views, operation semantics, permissions, authorities, preconditions, and return fields.
- `scripts/env/tools/router.py` validates the env tool envelope and owns unknown tool/action rejection for host-provided payloads.

The remaining problem is internal and surface-level duplication:

- `scripts/env/tools/*_manager.py` still exists as the dispatch layer name.
- Each manager still carries a private `_ACTION_MAP`.
- Managers still contain `_router_contract_error`, which is no longer the host-facing unknown-action boundary.
- `contracts.py` still exposes `manager_name`.
- `prepare.runtime_context.env_tools` still uses keys such as `task_manager` and `track_manager`.
- Tests still assert manager modules and `_ACTION_MAP` as architecture facts.
- Buddy AGENTS, shared skills, and active docs still contain manager wording such as "Env manager actions".

This is not a broken runtime path. It is architecture residue that keeps two concepts alive: env tools as the product surface and managers as the internal/public naming surface.

## Adjusted Decision

The remaining `_ACTION_MAP` entries should no longer be treated as a minor future optimization.

They are part of the next rebuild target because they create a second action fact source beside the registry. Even when tests prove the maps currently match the registry, the shape still asks future maintainers to keep duplicate action lists in sync.

The next pass should treat these as one cleanup set:

- remove manager naming;
- remove manager-local action maps;
- remove manager-local unknown-action boundaries;
- make registry-backed dispatch the only action-to-handler binding path.

## Target Architecture

The desired path is:

```text
runtime broker
  -> env.tool
  -> router
  -> registry-backed dispatch
  -> service
```

Responsibilities:

- Broker: protocol entry, active instance identity, active buddy identity, runtime lock.
- Router: envelope validation for `tool`, `action`, and object-shaped `args`; single unknown tool/action boundary.
- Registry: single public contract source for tool/action names and operation semantics.
- Dispatch: bind already-valid `(tool, action)` pairs to service handlers.
- Service: business permission checks, state checks, reads, writes, response construction.

The dispatch layer may use local handler references, but it should not preserve per-manager private action maps as independent allowlists. Registry and dispatch consistency must be machine-checked.

## Runtime Context Surface

`prepare.runtime_context.env_tools` should use tool ids as keys:

```text
env_tools.task
env_tools.track
env_tools.artifact
env_tools.context
env_tools.binding
env_tools.handoff
env_tools.run
env_tools.evidence
```

It should not expose manager keys:

```text
env_tools.task_manager
env_tools.track_manager
env_tools.artifact_manager
```

The runtime context should describe env tool operations, not manager actions.

## Codex CLI Skill Boundary

This rebuild must not replace or wrap Codex CLI native skill discovery.

The current BuddySwitch mechanism is:

1. `buddyswitch/manifest.toml` declares skill ids and repo-relative package paths.
2. `scripts/runtime_skills.py install` materializes the active buddy's packages into `.agents/skills/<skill_id>/`.
3. Codex CLI discovers and executes skills from `.agents/skills/<skill_id>/SKILL.md` using its native mechanism.

That mechanism should remain intact.

If the manager naming is removed from skills, the skill ids may change, for example:

```text
task-manager     -> task-tool
track-manager    -> track-tool
artifact-manager -> artifact-tool
```

That is a naming surface change, not a Codex skill mechanism change.

If skill ids are renamed, the change must be complete and direct:

- update `buddyswitch/manifest.toml` skill entries;
- update every buddy `skills = [...]` list;
- rename source skill directories;
- update `SKILL.md` frontmatter `name`;
- update tests that expect materialized skill ids;
- update AGENTS and active docs that reference the old ids.

Do not keep old aliases such as both `track-manager` and `track-tool`. That would create an old/new dual path.

## Required Cleanup

Active code cleanup:

- Delete or replace `scripts/env/tools/*_manager.py`.
- Delete per-tool `_ACTION_MAP`.
- Delete manager-local `_router_contract_error`.
- Delete `manager_name` from the tool registry contract.
- Update `scripts/env/tools/router.py` to call the new registry-backed dispatch layer.
- Add or update a clear dispatch module, for example `scripts/env/tools/dispatch.py`.

Active surface cleanup:

- Replace "manager actions" with "env tool operations" in buddy AGENTS, shared skills, and active docs.
- Replace `task_manager`, `track_manager`, and similar runtime context keys with tool ids.
- Rename manager-themed skill packages if the rebuild chooses to remove manager wording from the host skill surface.

Residue scan targets:

- `env.task`
- `issue_browser_evidence`
- `handoff_inbox`
- `automatic router`
- `auto-routing`
- `workflow engine`
- `event bus`
- `DSL`
- `manager actions`
- `*_manager.py`
- `_ACTION_MAP`
- `manager_name`
- `task_manager`
- `track_manager`
- `artifact_manager`

Historical specs may remain as history only when they are clearly not active guidance. If a stale spec can mislead future implementation, mark it superseded or move it out of the active path.

## Explicit Non-Goals

Do not add:

- compatibility wrappers;
- import shims for removed `*_manager.py` modules;
- old/new skill aliases;
- a BuddySwitch-specific skill discovery layer;
- workflow engines;
- event buses;
- DSLs;
- automatic routing;
- handoff inboxes.

Do not preserve manager naming because old prompts or old skills might mention it. Update the prompts and skills instead.

## Test And Verification Requirements

The next implementation should start with failing tests and then rebuild forward.

Focused tests should prove:

- router is the single unknown tool/action boundary;
- registry and dispatch handler coverage are identical;
- active runtime context uses tool id keys, not manager keys;
- active skill materialization still installs Codex-native `.agents/skills/<skill_id>/SKILL.md` packages;
- renamed skills, if renamed, are installed under only the new ids;
- active docs, AGENTS, and shared skills do not advertise manager actions;
- residue checks catch removed broker methods and forbidden product concepts.

Required gates:

- focused env tool router and registry/dispatch tests;
- runtime context tests;
- runtime skill materialization tests;
- repo consistency / residue tests;
- full pytest;
- `py_compile` over changed Python paths or the whole project script surface;
- product-mode smoke that starts an instance, prepares context, uses env tool CLI, and confirms Codex skill materialization remains native.

## Acceptance Criteria

The rebuild is complete only when all of the following are true:

- Active env operations still enter through `env.tool`.
- There are no active env tool `*_manager.py` dispatch modules.
- There are no per-tool `_ACTION_MAP` allowlists.
- There is no manager-local unknown-action boundary.
- `contracts.py` no longer exposes `manager_name`.
- `prepare.runtime_context.env_tools` is keyed by tool id.
- Codex CLI skill discovery remains native through `.agents/skills/<skill_id>/SKILL.md`.
- If manager-named skills are renamed, old skill ids are gone rather than aliased.
- Active AGENTS, skills, and docs use env tool language rather than manager language.
- Verification proves behavior, residue cleanup, and product-mode operation.

## One-Line Definition

Rebuild the env tool layer so BuddySwitch keeps Codex-native skill discovery unchanged while exposing and implementing only one clear path:

```text
env.tool -> router -> registry-backed dispatch -> service
```

with manager naming, duplicate action maps, old tool methods, and stale host-facing residue removed.

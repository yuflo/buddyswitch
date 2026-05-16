# Runtime Workspace And Host Boundary Memo

Date: 2026-05-16
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: alignment memo only. This document records the target, current evidence, and implementation constraints. It is not an implementation patch.

## Background

The immediate trigger was a PM buddy instance handling a request for a PRD plus a rough prototype. The PM buddy correctly had only PM runtime skills under `.agents/skills`, but it used shell discovery over the full runtime workspace, found `buddyswitch/skills/design/shape-prototype/SKILL.md`, read a design-only skill from the repository source tree, and then attempted to write a preview file under `.sandbox/design/ai-schedule-landing/index.html`.

That exposed two separate boundary problems:

1. The per-instance execution workspace is currently a full Git worktree, so it contains source surfaces that are not part of the active buddy runtime.
2. The launcher-generated Codex permission profile currently restricts writes, but still grants broad read access, so the host can read source surfaces that should not drive runtime behavior.

The corrected direction is to make the instance environment narrow by construction and narrow by host policy:

- The instance checkout should be a minimal runtime checkout, not the full repository.
- The host should only read and write inside the intended BuddySwitch env surface.
- `.agents/skills` should be the only runtime skill surface.
- Source skill packages under `buddyswitch/skills/**` should not be visible to normal product-mode instances.

## Current Facts

### Project Workspace Is Already Sparse

The shared project workspace is already narrow:

- `tools/launcher/workspace.sh` defines the project sparse paths as only `projects/app/`.
- `buddyswitch_workspace_configure_project_sparse_checkout` runs `git sparse-checkout set --no-cone projects/app/`.
- `buddyswitch_workspace_project_worktree_has_sparse_boundary` rejects top-level entries such as `buddyswitch`, `tools`, `scripts`, `tests`, `framework`, `docs`, `AGENTS.md`, `README.md`, and `buddyswitch-codex`.

This means the product-source workspace is already conceptually right: it exposes `projects/app/` and avoids the rest of the repository.

### Execution Workspace Is Still Full

The per-instance execution workspace is not narrow today:

- `buddyswitch_workspace_force_rebuild_execution_worktree` uses `git worktree add --detach "${workspace_dir}" HEAD`.
- `buddyswitch_workspace_is_valid_execution_worktree` only checks that the workspace is a Git worktree backed by the same common Git directory.
- It does not check sparse checkout state.
- It does not check that disallowed source paths are absent.
- `buddyswitch_workspace_sync_runtime_surface` copies the intended runtime subset into the workspace, but because the workspace starts as a full checkout, copying the runtime subset does not remove extra checked-out content.

Result: `instances/<id>/workspace` can contain `buddyswitch/skills/design/**`, `buddyswitch/skills/market/**`, `tools/**`, `tests/**`, and other source-only paths. Those paths are not intended runtime inputs, but the host can discover them with ordinary shell commands.

### Runtime Skills Are Correct But Not Exclusive

The manifest correctly separates PM and design skills:

- PM skills: `write-prd`, `track-tool`, `artifact-tool`, `task-tool`, `handoff-tool`, `buddybox-tool`.
- Design skills: `shape-prototype`, `track-tool`, `artifact-tool`, `task-tool`, `handoff-tool`, `buddybox-tool`.

`scripts/runtime_skills.py` materializes only the active buddy's skills into `.agents/skills`. Existing launcher tests already assert that PM does not receive `.agents/skills/shape-prototype`, while design does receive it.

The problem is not the `.agents/skills` materialization. The problem is that the full source checkout exposes a second readable skill surface under `buddyswitch/skills/**`.

### Host Write Permissions Are Narrower Than Read Permissions

In profile mode, the launcher writes a named Codex permission profile:

```toml
default_permissions = "buddyswitch-runtime"

[permissions.buddyswitch-runtime.filesystem]
"/" = "read"
":project_roots" = { "." = "read" }
```

Write access is then granted only to selected paths:

- instance `HOME`;
- instance `CODEX_HOME`;
- instance `XDG_CONFIG_HOME`;
- active buddybox root under the instance workspace;
- safe temp roots such as `/tmp`;
- shared project workspace only when the active buddy's profile has `project.access = "write"`.

Current tests assert that PM does not get writable project workspace access and that dev does.

The write model is close to the target. The read model is not: `"/" = "read"` makes the full filesystem readable unless later denied by a more specific rule.

OpenAI's Codex config reference says named filesystem permission profiles support `"read"`, `"write"`, and `"none"` for absolute paths, special tokens, and project-root-relative paths. It also says `"none"` can deny reads for matching paths. Therefore the host boundary can be made stricter than write-only allowlisting.

Reference: <https://developers.openai.com/codex/config-reference>

## Target Outcome

After the change, launching a BuddySwitch product-mode instance should give Codex CLI an env-shaped runtime workspace, not a repository-shaped workspace.

For a PM instance, the host-visible workspace should look like this:

```text
AGENTS.md

.agents/skills/
  write-prd/
  track-tool/
  artifact-tool/
  task-tool/
  handoff-tool/
  buddybox-tool/

scripts/
  env/client.py
  env/**
  runtime_kernel/**
  turn_runtime.py
  env_store.py
  env_manifest.py
  env_profiles.py
  browser_evidence.py

buddyswitch/
  manifest.toml
  env-profiles/**
  objects/
    tracks -> shared state projection
    tasks -> shared state projection
    artifacts -> shared state projection
    handoffs -> shared state projection
  local/buddybox/pm/

framework/
  contracts/**

projects/app -> shared sparse project workspace
```

The host should not see these in the normal product-mode instance workspace:

```text
buddyswitch/skills/**
tools/**
tests/**
docs/**
README.md
buddyswitch-codex
tools/launcher/assets/buddies/**
non-runtime source memos, specs, fixtures, and tests
```

`tools/launcher/**` remains necessary for the host launcher itself, but it is not necessary for the buddy running inside the already-created Codex instance.

## Task 1: Host Permission Boundary

### Goal

Constrain Codex CLI read and write access to the BuddySwitch env runtime surface while preserving high-velocity operation for legitimate buddy work.

This is not only a write sandbox task. Reads must also be bounded, because the observed failure came from reading a non-runtime source skill.

### Current State

`tools/launcher/codex_config.py` currently:

- uses `default_permissions = "buddyswitch-runtime"` in profile mode;
- disables native web search;
- disables permission escalation requests through `request_permissions = false`;
- grants `"/" = "read"`;
- grants `":project_roots" = { "." = "read" }`;
- grants writes to instance env paths and active buddybox;
- grants writes to the project workspace only for buddies whose profile has `project.access = "write"`;
- allows broker Unix socket access when a broker socket is present.

This profile protects writes better than reads.

### Required Permission Model

Keep writable:

- instance `HOME`;
- instance `CODEX_HOME`;
- instance `XDG_CONFIG_HOME`;
- active buddybox root;
- runtime broker socket;
- safe temp roots;
- shared sparse `project/workspace` only for dev or other explicitly write-authorized buddies.

Keep readable:

- the execution runtime workspace surface listed in this memo;
- `.agents/skills/**`;
- `projects/app/**`;
- instance `HOME`, `CODEX_HOME`, and `XDG_CONFIG_HOME` paths required by Codex itself;
- runtime broker metadata required by `scripts/env/client.py` and `scripts/runtime_kernel/**`;
- safe temp roots when needed for payload files and generated scratch output.

Deny or remove from read access:

- `buddyswitch/skills/**` in the execution workspace;
- inactive buddy prompt templates and source-only launcher assets;
- tests, docs, and source memos in runtime instances;
- the full repository root when the instance is running in product mode;
- source checkout internals that are not needed by the active buddy runtime.

### Recommended Shape

Prefer a two-layer defense:

1. Sparse runtime workspace removes disallowed source paths from the instance.
2. Codex permission profile denies or avoids read access to disallowed source paths if they appear due to migration, stale state, or future regressions.

Do not rely only on prompt instructions or AGENTS guidance. AGENTS should remain a route map, not the enforcement mechanism.

Do not make the profile so tight that normal tool use requires approval prompts. BuddySwitch currently uses `request_permissions = false`, so all legitimate runtime reads and writes must be available up front.

### Important UX Constraint

The user experience should not degrade into constant permission failures.

The boundary should be narrow by category, not brittle by individual incidental file:

- allow the entire runtime tool layer rather than one file at a time;
- allow active `.agents/skills/**` rather than individual skill files;
- allow active buddybox rather than only predeclared filenames;
- allow safe temp roots for payload files and temporary exports;
- allow `projects/app/**` reads for all buddies, but writes only for write-authorized buddies.

### Verification Requirements

Add tests or focused checks proving:

- PM cannot read `buddyswitch/skills/design/shape-prototype/SKILL.md` from the instance workspace.
- PM can read `.agents/skills/write-prd/SKILL.md`.
- Design can read `.agents/skills/shape-prototype/SKILL.md`.
- PM cannot write `.sandbox/design/...`.
- PM cannot write `projects/app/**`.
- Dev can write the shared project workspace.
- `python3 scripts/env/client.py context summarize` works in a PM instance.
- `python3 scripts/turn_runtime.py status` works in a PM instance.
- `python3 scripts/env/client.py buddybox desc` works in a PM instance.
- Browser/search env tool commands still work where the active buddy has `search.use`.

## Task 2: Runtime Workspace Checkout Slimming

### Goal

Change `instances/<id>/workspace` from a full repository worktree into a sparse, runtime-only execution worktree.

The product-mode instance should expose only what the active buddy needs to operate through BuddySwitch env tools, runtime skills, project context, and private buddybox files.

### Current State

The existing two-workspace model should be preserved:

- `shared_root/project/workspace` is the product source workspace.
- `shared_root/instances/<id>/workspace` is the execution workspace for the active Codex instance.

The project workspace is already narrow and should remain a sparse checkout of `projects/app/`.

The execution workspace is the problem. It is a full worktree and should be narrowed.

### Runtime Files That Must Stay

The execution workspace still needs the runtime tool layer. Removing all scripts would break env tools.

Keep:

- `scripts/env/client.py`;
- `scripts/env/**`;
- `scripts/runtime_kernel/**`;
- `scripts/turn_runtime.py`;
- `scripts/env_store.py`;
- `scripts/env_manifest.py`;
- `scripts/env_profiles.py`;
- `scripts/browser_evidence.py`;
- `buddyswitch/manifest.toml`;
- `buddyswitch/env-profiles/**`;
- `framework/contracts/**`;
- runtime `AGENTS.md`;
- `.agents/skills/**` for the active buddy;
- `projects/app` projection to the shared sparse project workspace;
- `buddyswitch/objects/{tracks,tasks,artifacts,handoffs}` projections;
- `buddyswitch/local/buddybox/<active_buddy>/` real local directory;
- Git worktree metadata needed by launcher maintenance, local excludes, hooks, and cleanup.

Do not keep:

- `buddyswitch/skills/**`;
- `tools/**`;
- `tests/**`;
- `docs/**`;
- root `README.md`;
- root `buddyswitch-codex`;
- old runtime residue directories;
- source-only fixtures and implementation docs.

### Recommended Implementation Direction

Keep using Git worktrees. Do not replace the worktree model with ad hoc copying.

For the execution workspace:

1. Add a function analogous to `buddyswitch_workspace_project_sparse_paths`, but for execution runtime paths.
2. Add an execution sparse boundary check analogous to `buddyswitch_workspace_project_worktree_has_sparse_boundary`.
3. Change fresh execution workspace creation from:

```bash
git -C "${repo_root}" worktree add --detach "${workspace_dir}" HEAD
```

to:

```bash
git -C "${repo_root}" worktree add --detach --no-checkout "${workspace_dir}" HEAD
git -C "${workspace_dir}" sparse-checkout init --no-cone
git -C "${workspace_dir}" sparse-checkout set --no-cone <runtime paths>
git -C "${workspace_dir}" checkout HEAD
```

4. For existing full execution worktrees, either narrow in place when there are no unsafe local changes, or rebuild and restore runtime-managed outputs using the existing staging mechanism.
5. Keep `buddyswitch_workspace_sync_runtime_surface` or replace it with a simpler refresh step after the sparse checkout boundary is established.
6. Continue installing runtime AGENTS and runtime skills after checkout setup.
7. Continue installing state projections and the active buddybox local directory after checkout setup.
8. Continue installing local excludes for runtime-managed generated paths.

### Required Execution Workspace Shape

For PM, after start/open:

```text
workspace/
  AGENTS.md
  .agents/skills/write-prd/SKILL.md
  .agents/skills/track-tool/SKILL.md
  .agents/skills/artifact-tool/SKILL.md
  .agents/skills/task-tool/SKILL.md
  .agents/skills/handoff-tool/SKILL.md
  .agents/skills/buddybox-tool/SKILL.md
  scripts/env/client.py
  scripts/env/**
  scripts/runtime_kernel/**
  scripts/turn_runtime.py
  scripts/env_store.py
  scripts/env_manifest.py
  scripts/env_profiles.py
  scripts/browser_evidence.py
  buddyswitch/manifest.toml
  buddyswitch/env-profiles/**
  buddyswitch/objects/**
  buddyswitch/local/buddybox/pm/**
  framework/contracts/**
  projects/app -> shared sparse project workspace
```

For design, `.agents/skills/shape-prototype` should exist, but `buddyswitch/skills/design/shape-prototype` should still not exist in the execution workspace.

### Migration Notes

Existing instances may already have full worktrees. The implementation must handle `instance open`, not only new `instance start`.

The migration must not silently delete active buddybox files or runtime object projections. The current staging and restore helpers for runtime outputs should remain part of the migration path.

If an existing execution workspace has local changes outside the runtime-managed outputs, the launcher should either rebuild safely after staging only known runtime outputs, or fail with a clear message. Do not preserve arbitrary source edits in product-mode runtime instances.

### Verification Requirements

Add or update tests proving:

- new PM instance workspaces do not contain `buddyswitch/skills/**`;
- reopened existing full PM instance workspaces are narrowed or rebuilt so `buddyswitch/skills/**` disappears;
- PM `.agents/skills` contains only PM skills;
- design `.agents/skills` contains design skills;
- project workspace remains sparse to `projects/app/`;
- `projects/app` projection still resolves to the shared sparse project workspace;
- broker starts because `scripts/runtime_kernel/broker.py` and manifest are present;
- `context summarize`, `turn_runtime.py status`, and env tool calls work after narrowing;
- active buddybox files survive `instance open` when they are stored under the active instance workspace;
- local excludes still cover `.agents/skills/**`, runtime objects, and buddybox paths;
- no test relies on `tools/**`, `tests/**`, or `docs/**` being available inside the product-mode instance workspace.

## Host-Visible Env After Both Tasks

After both tasks, launching a PM instance should produce this effective host environment:

```text
cwd:
  <shared_root>/instances/<instance_id>/workspace

HOME:
  <shared_root>/instances/<instance_id>/home

CODEX_HOME:
  <shared_root>/instances/<instance_id>/codex-home

XDG_CONFIG_HOME:
  <shared_root>/instances/<instance_id>/xdg-config

BUDDYSWITCH_INSTANCE_ID:
  <instance_id>

BUDDYSWITCH_INSTANCE_JSON:
  <shared_root>/instances/<instance_id>/instance.json

BUDDYSWITCH_INSTANCE_ROOT:
  <shared_root>/instances/<instance_id>

BUDDYSWITCH_WORKSPACE_DIR:
  <shared_root>/instances/<instance_id>/workspace

BUDDYSWITCH_ACTIVE_BUDDY:
  pm

BUDDYSWITCH_RUNTIME_BROKER_SOCKET:
  <instance_root>/runtime/runtime-broker.sock
  or /tmp/buddyswitch-runtime-<digest>.sock when the default socket path is too long

BUDDYSWITCH_SHARED_ROOT:
  <shared_root>
```

From inside Codex CLI, the active buddy should have:

- read access to runtime files and project context;
- write access to private env paths, active buddybox, and safe temp;
- no read or write access to source-only skill trees;
- no write access to product source unless the active buddy profile explicitly allows it;
- env tool access through `python3 scripts/env/client.py ...`;
- runtime status access through `python3 scripts/turn_runtime.py status`;
- no need to inspect `tools/launcher/**` directly.

## Non-Goals

Do not build:

- a generic virtual filesystem framework;
- a rule engine for skill selection;
- compatibility layers that keep full source skill trees visible;
- cross-buddy buddybox visibility;
- source checkout mutation from PM/design/market/test;
- prompt-heavy AGENTS workarounds;
- a new tool invocation system replacing `scripts/env/client.py`;
- a new project workspace model replacing the already sparse `projects/app/` worktree.

Do not remove:

- the env tool runtime layer;
- the runtime broker;
- the `.agents/skills` materialization path;
- project workspace sparse checkout;
- active buddybox;
- runtime object projections.

## Main Risks

1. Missing runtime file breaks broker startup.
   - Mitigation: keep the runtime surface list explicit and test broker start/status.

2. Overly tight host read rules break Codex CLI internals or env tool calls.
   - Mitigation: start with sparse workspace plus targeted read deny, then tighten broad read only after real instance verification.

3. Existing full instances keep stale source paths.
   - Mitigation: handle `instance open` with sparse boundary repair, not only new `instance start`.

4. Runtime-managed untracked paths become noisy or are deleted incorrectly.
   - Mitigation: keep local excludes and staging/restore for state projections, `.agents/skills`, and buddybox.

5. Tool layer is accidentally removed because `tools/**` is excluded.
   - Mitigation: distinguish launcher tools from env tools. Keep `scripts/env/**` and `scripts/runtime_kernel/**`; remove `tools/**` from the instance workspace.

6. Design buddy loses its runtime prototype skill.
   - Mitigation: design should still receive `.agents/skills/shape-prototype`; only source path `buddyswitch/skills/design/shape-prototype` should disappear.

## Acceptance Criteria

The change is complete only when all of these are true:

- A PM instance cannot discover `shape-prototype` by scanning the workspace.
- A PM instance can still use `write-prd`, track/task/artifact/handoff/buddybox tools.
- A design instance can still use `.agents/skills/shape-prototype`.
- Product source remains available through `projects/app`.
- PM cannot write product source.
- Dev can write product source when its profile allows it.
- Env tools work through the broker.
- The launcher can start and reopen instances after the migration.
- Existing runtime state projections and active buddybox files are preserved across reopen.
- Relevant focused tests pass.

## Recommended Implementation Order

1. Add failing tests for execution workspace source-skill leakage.
2. Add failing tests for host read deny or absence of `buddyswitch/skills/**`.
3. Add execution sparse path list and boundary check.
4. Convert fresh execution worktree creation to sparse checkout.
5. Add repair/narrowing for existing execution worktrees on `instance open`.
6. Update Codex permission profile to remove or deny read access to disallowed source paths while preserving runtime reads.
7. Verify PM, design, and dev instance launches.
8. Run focused launcher, runtime skills, broker, and env boundary tests.

## Source References

Local source references checked while preparing this memo:

- `tools/launcher/workspace.sh`
- `tools/launcher/env.sh`
- `tools/launcher/runtime_broker.sh`
- `tools/launcher/codex_config.py`
- `scripts/env/client.py`
- `scripts/runtime_kernel/dispatcher.py`
- `scripts/runtime_kernel/server.py`
- `scripts/runtime_skills.py`
- `scripts/runtime_agents.py`
- `buddyswitch/manifest.toml`
- `tests/test_buddy_env_sandbox.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_runtime_skills.py`

External reference:

- OpenAI Codex Configuration Reference: <https://developers.openai.com/codex/config-reference>

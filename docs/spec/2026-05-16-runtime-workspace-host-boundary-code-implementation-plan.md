# Runtime Workspace Host Boundary Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use test-first changes for behavior, keep each phase runnable, and do not start from `main`.

**Goal:** Product-mode buddies run inside an env-shaped runtime workspace and a Codex permission profile that cannot use source-only repo surfaces as runtime inputs.

**Architecture:** Keep the current two-workspace model. `shared_root/project/workspace` remains the sparse product source checkout for `projects/app/`; `shared_root/instances/<id>/workspace` becomes a sparse runtime checkout plus launcher-managed runtime projections, active skills, and active buddybox. Host permissions move from broad filesystem read to explicit runtime/project/env access with deny rules for stale source-only paths.

**Tech Stack:** Bash launcher helpers, Git worktrees and sparse checkout, Python Codex config renderer, runtime broker/env tool Python modules, TOML/JSON contracts, pytest/unittest.

---

## 1. 任务目标

完成后，BuddySwitch product-mode instance 的 host-visible workspace 不再像完整仓库，而是只包含 active buddy 运行所需的 runtime tool layer、runtime skills、project context projection、shared object projections 和 active buddybox。当前核心瓶颈是 `instances/<id>/workspace` 仍由完整 Git worktree 创建，且 Codex profile 仍渲染 `"/" = "read"`；这会让 PM 等非设计 buddy 通过普通 shell 扫描读到 `buddyswitch/skills/design/**` 等 source-only surfaces，并让提示词/AGENTS 只能充当提醒而非边界。

最重要的问题是读边界，不只是写边界。观察到的失败来自 PM 读取 source skill 后按设计能力行动；因此最短可验证路径是先让 runtime workspace by construction 不含 source skills，再让 Codex filesystem profile by policy 不读 full repo 或 stale source-only paths。

## 2. 需求提取

- `REQ-001`：Product-mode execution workspace 必须是 runtime-only sparse checkout，不得是完整 repository checkout。
- `REQ-002`：现有两工作区模型保留：`shared_root/project/workspace` 是共享 product source workspace，`shared_root/instances/<id>/workspace` 是 active Codex execution workspace。
- `REQ-003`：Project workspace 必须继续 sparse 到 `projects/app/`，并继续被 runtime workspace 的 `projects/app` projection 指向。
- `REQ-004`：Execution workspace 必须保留 runtime tool layer：`scripts/env/client.py`、`scripts/env/**`、`scripts/runtime_kernel/**`、`scripts/turn_runtime.py`、`scripts/env_store.py`、`scripts/env_manifest.py`、`scripts/env_profiles.py`、`scripts/browser_evidence.py`。
- `REQ-005`：Execution workspace 必须保留 runtime data/config inputs：`buddyswitch/manifest.toml`、`buddyswitch/env-profiles/**`、`framework/contracts/**`、runtime `AGENTS.md`。
- `REQ-006`：Execution workspace 必须保留 active runtime surfaces：`.agents/skills/**`、`buddyswitch/objects/{tracks,tasks,artifacts,handoffs}` projections、`buddyswitch/local/buddybox/<active_buddy>/` real directory、Git worktree metadata、local excludes、guardrail hooks。
- `REQ-007`：Execution workspace must not expose `buddyswitch/skills/**`, `tools/**`, `tests/**`, `docs/**`, root `README.md`, root `buddyswitch-codex`, inactive buddy prompt templates, source memos/specs/fixtures, or old runtime residue dirs.
- `REQ-008`：`.agents/skills` 是唯一 runtime skill surface；PM has `write-prd` and shared tool skills but no `shape-prototype`; design has `.agents/skills/shape-prototype`; neither sees `buddyswitch/skills/design/shape-prototype`.
- `REQ-009`：Fresh execution worktree creation must use `git worktree add --detach --no-checkout`, `git sparse-checkout init --no-cone`, `git sparse-checkout set --no-cone <runtime paths>`, then `git checkout HEAD`.
- `REQ-010`：Existing full execution worktrees must be repaired on both `instance start` and `instance open`; clean full worktrees are narrowed in place, and worktrees with unmanaged local source-only changes fail with a clear message before deletion.
- `REQ-011`：Migration must not silently delete active buddybox files or runtime object projections; existing runtime output staging/restoration remains in the rebuild path.
- `REQ-012`：Runtime-managed generated paths must be excluded from local Git noise: `AGENTS.md`, `.agents/skills/**`, `projects/app`, `.runtime/**`, `buddyswitch/objects/**`, and `buddyswitch/local/buddybox/**`.
- `REQ-013`：`buddyswitch_workspace_sync_runtime_surface` must stop masking a full checkout by copying runtime files over it; runtime surface correctness must come from sparse checkout plus active runtime installation.
- `REQ-014`：Host permission profile must not grant broad read access through `"/" = "read"` or source repo root read in product mode.
- `REQ-015`：Host permission profile must keep reads for runtime workspace, active `.agents/skills/**`, shared `projects/app/**`, instance `HOME`, `CODEX_HOME`, `XDG_CONFIG_HOME`, runtime broker socket access, and safe temp roots.
- `REQ-016`：Host permission profile must keep writes for instance `HOME`, instance `CODEX_HOME`, instance `XDG_CONFIG_HOME`, active buddybox root, safe temp roots, and shared project workspace only for buddies whose env profile has `project.access = "write"`.
- `REQ-017`：PM/design/market/test must not receive write permission for `projects/app/**` or `.sandbox/design/**`; dev must receive project workspace write permission.
- `REQ-018`：Host permission profile must deny stale source-only paths if they exist in the runtime workspace: `buddyswitch/skills/**`, `tools/**`, `tests/**`, `docs/**`, root `README.md`, root `buddyswitch-codex`, and inactive launcher prompt assets.
- `REQ-019`：`request_permissions = false`, disabled native Codex web search, MCP approval hardening, and broker Unix socket allowlist behavior must remain intact.
- `REQ-020`：Normal runtime commands must not degrade into permission failures: `python3 scripts/env/client.py context summarize`, `python3 scripts/turn_runtime.py status`, `python3 scripts/env/client.py buddybox desc`, and search/browser env tool commands must still work where the active buddy has `search.use`.
- `REQ-021`：Do not rely on prompt instructions or AGENTS as enforcement; AGENTS remains route-map guidance.
- `REQ-022`：Do not replace Git worktrees with ad hoc copying, do not build a virtual filesystem, rule engine, skill selection engine, prompt workaround, generic permission framework, or new env tool invocation system.
- `REQ-023`：Do not remove env tools, runtime broker, `.agents/skills` materialization, project workspace sparse checkout, active buddybox, or runtime object projections.
- `REQ-024`：Verification must prove PM cannot discover/read `shape-prototype` by scanning the workspace, PM can read `.agents/skills/write-prd/SKILL.md`, design can read `.agents/skills/shape-prototype/SKILL.md`, PM cannot write project source, dev can write project source, runtime broker/env tool commands work, and reopen preserves active buddybox.
- `REQ-025`：The generated Codex config must follow official Codex custom permission profile semantics: `default_permissions` names a `[permissions.<name>]` profile; filesystem entries accept `"read"`, `"write"`, and `"none"`; Unix socket rules accept `allow` and `none`. References checked: <https://developers.openai.com/codex/config-advanced> and <https://developers.openai.com/codex/config-reference>.

## 3. 现状探索摘要

### 关键目录、文件、测试、命令

- `docs/memo/2026-05-16-runtime-workspace-host-boundary-memo.md`：需求源。
- `AGENTS.md`：SHARP forward、testing-bound、no verification no done、runtime state 不直接编辑。
- `README.md`：product-mode launcher and workspace layout summary。
- `tools/launcher/workspace.sh`
  - `buddyswitch_workspace_project_sparse_paths`
  - `buddyswitch_workspace_project_worktree_has_sparse_boundary`
  - `buddyswitch_workspace_configure_project_sparse_checkout`
  - `buddyswitch_workspace_force_rebuild_execution_worktree`
  - `buddyswitch_workspace_ensure_execution_worktree`
  - `buddyswitch_workspace_sync_runtime_surface`
  - `buddyswitch_workspace_install_runtime_agents`
  - `buddyswitch_workspace_install_runtime_skills`
  - `buddyswitch_workspace_install_state_projections`
  - `buddyswitch_workspace_install_local_excludes`
- `buddyswitch-codex`
  - `start_locked_bootstrap`
  - `instance_open_locked_bootstrap`
  - `buddyswitch_patch_codex_config` call flow through `tools/launcher/env.sh`
- `tools/launcher/codex_config.py`
  - `render_permission_profile_block`
  - `_build_profile_mode_roots`
  - `_build_profile_mode_unix_sockets`
  - `patched_config_text`
- `tools/launcher/env.sh`
  - `buddyswitch_patch_codex_config`
  - `buddyswitch_env_bind_instance`
  - `buddyswitch_run_codex`
- `tools/launcher/runtime_broker.sh`
  - `_buddyswitch_runtime_broker_manifest_path`
  - `_buddyswitch_runtime_broker_script_path`
  - `buddyswitch_runtime_broker_ensure`
- `scripts/runtime_skills.py`：materializes active buddy skills into `.agents/skills`.
- `scripts/runtime_agents.py`：validates runtime AGENTS templates.
- `scripts/env/client.py`：runtime CLI for `context`, `buddybox`, `search`, `evidence`.
- `scripts/runtime_kernel/dispatcher.py` and `scripts/runtime_kernel/broker.py`：broker status/env.tool gateway.
- `scripts/turn_runtime.py`：runless runtime status and env tool catalog.
- `buddyswitch/manifest.toml`：buddy skill sets and permissions.
- `buddyswitch/env-profiles/{pm,design,dev,market,test}.json`：project access and search/browser capabilities.
- `tests/test_buddyswitch_launcher.py`：launcher start/open, project workspace sparse, runtime skills, broker, project projection, buddybox preservation.
- `tests/test_buddy_env_sandbox.py` and `tests/test_env_layer_boundaries.py`：Codex config permissions.
- `tests/test_runtime_broker.py`：runtime broker status and workspace root behavior.
- `tests/test_runtime_skills.py` and `tests/test_runtime_agents.py`：skill and runtime AGENTS correctness.
- `tests/test_search_env_tool.py`：search env tool behavior.
- Exploration commands:
  - `git status --short --branch`
  - `rg -n "worktree add|sparse-checkout|sync_runtime_surface|buddyswitch-runtime|default_permissions|shape-prototype|\\.agents/skills" tools scripts tests buddyswitch-codex`
  - `python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_uses_shared_project_workspace_and_instance_workspace -q`
  - `python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q`
  - `python3 -m pytest tests/test_runtime_broker.py::RuntimeBrokerLiveStatusTests::test_live_status_reports_workspace_root_facts -q`

### 保留、替换、删除、迁移

- 保留：two-workspace model, project workspace sparse checkout, `projects/app` projection, runtime broker, env tool CLI, `.agents/skills` materialization, runtime AGENTS installation, active buddybox real directory, shared object projections, local excludes, guardrail hooks.
- 替换：execution worktree creation from full `git worktree add --detach "${workspace_dir}" HEAD` to sparse `--no-checkout` flow.
- 替换：execution worktree validity from "same common Git dir only" to "same common Git dir plus repairable runtime sparse boundary".
- 替换：runtime surface refresh from Python copy overlay to Git sparse checkout configuration and checkout refresh.
- 替换：Codex profile read model from `"/" = "read"` to explicit runtime/project/env reads plus stale-source denies.
- 删除 from runtime workspace: `buddyswitch/skills/**`, `tools/**`, `tests/**`, `docs/**`, root `README.md`, root `buddyswitch-codex`, source-only launcher assets, source memos/specs/fixtures.
- 迁移：existing clean full execution worktrees are narrowed in place on open/start; active buddybox files under `buddyswitch/local/buddybox/<active_buddy>` are staged/restored if rebuild is needed.
- 阻塞条件：an existing execution worktree with unmanaged local changes outside runtime-managed paths fails with a clear message, because preserving arbitrary source edits in a product-mode runtime instance would keep the boundary ambiguous.

## 4. 最终目标架构

### Runtime workspace shape

For a PM instance:

```text
workspace/
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
      tracks -> shared_root/state/buddyswitch/objects/tracks
      tasks -> shared_root/state/buddyswitch/objects/tasks
      artifacts -> shared_root/state/buddyswitch/objects/artifacts
      handoffs -> shared_root/state/buddyswitch/objects/handoffs
    local/buddybox/pm/
  framework/contracts/**
  projects/app -> shared_root/project/workspace/projects/app
```

For a design instance, `.agents/skills/shape-prototype/SKILL.md` exists and `buddyswitch/skills/design/shape-prototype/SKILL.md` does not exist.

### File responsibilities

- Modify `tools/launcher/workspace.sh`
  - Add `buddyswitch_workspace_execution_sparse_paths()`: emits the tracked runtime checkout paths.
  - Add `buddyswitch_workspace_execution_forbidden_entries()`: emits top-level/runtime-forbidden entries that must not be present.
  - Add `buddyswitch_workspace_execution_worktree_has_sparse_boundary(workspace_dir)`: validates sparse-checkout list and absence of forbidden entries.
  - Add `buddyswitch_workspace_execution_worktree_has_dirty_unmanaged_changes(workspace_dir)`: detects dirty or untracked changes outside runtime-managed paths.
  - Add `buddyswitch_workspace_report_dirty_unmanaged_execution_changes(workspace_dir)`: prints a concrete refusal message and `git status --short`.
  - Add `buddyswitch_workspace_configure_execution_sparse_checkout(workspace_dir, mode)`: initializes no-cone sparse checkout with runtime paths, checks out `HEAD`, and validates boundary.
  - Modify `buddyswitch_workspace_force_rebuild_execution_worktree()`: uses `git worktree add --detach --no-checkout`, then calls `buddyswitch_workspace_configure_execution_sparse_checkout "${workspace_dir}" fresh`.
  - Modify `buddyswitch_workspace_ensure_execution_worktree()`: if valid worktree and sparse boundary exists, refresh checkout; if valid but boundary missing and no unmanaged changes, configure sparse; if invalid, rebuild.
  - Modify `buddyswitch_workspace_sync_runtime_surface()`: stop copying runtime files from repo; make it call execution sparse configuration/checkout validation plus `buddyswitch_workspace_neutralize_project_codex_config`.
  - Modify `buddyswitch_workspace_install_local_excludes()`: add `AGENTS.md`, `projects/app`, `.runtime/**`, and `.codex/config.toml` alongside existing runtime output excludes.

- Modify `buddyswitch-codex`
  - In `instance_open_locked_bootstrap`, replace the current missing/invalid-only check plus direct sync with `buddyswitch_workspace_ensure_execution_worktree`.
  - Keep the existing live-instance checks, state skeleton install, runtime AGENTS/skills install, project workspace ensure, project projection repair, broker ensure, Codex config patch, and browser bootstrap order.

- Modify `tools/launcher/codex_config.py`
  - Replace `render_permission_profile_block(writable_paths, unix_sockets=None)` with a renderer that accepts `filesystem_entries: dict[str, object]` and `unix_sockets`.
  - Add `_profile_mode_workspace_deny_rules(workspace_dir) -> dict[str, str]` for project-root-relative denies:
    - `buddyswitch/skills/** = "none"`
    - `tools/** = "none"`
    - `tests/** = "none"`
    - `docs/** = "none"`
    - `README.md = "none"`
    - `buddyswitch-codex = "none"`
  - Add `_build_profile_mode_filesystem(args) -> dict[str, object]`:
    - `":project_roots"` maps `"."` to `"read"` and the deny rules above to `"none"`.
    - `project_workspace_dir` maps to `"read"` for all buddies, `"write"` for dev or any profile with `project.access = "write"`.
    - instance `home`, `codex_home`, `xdg_config_home`, active `buddybox_root`, and safe temp roots map to `"write"`.
    - no `"/" = "read"` entry is emitted in profile mode.
    - no source repo root, shared root, project root parent, state root, instance root, or workspace root absolute entry is emitted.
  - Keep `_safe_temp_roots`, `_build_profile_mode_unix_sockets`, MCP approval patching, native web search disabled, and `request_permissions = false`.
  - Keep `_build_local_mode_roots` and non-profile sandbox behavior unchanged.

- Modify tests
  - `tests/test_buddyswitch_launcher.py`: add sparse runtime workspace shape, migration, skills, local excludes, and runtime command smoke coverage.
  - `tests/test_buddy_env_sandbox.py`: update profile expectations from broad read to explicit read/deny/write entries.
  - `tests/test_env_layer_boundaries.py`: add config-level read/write boundary assertions for source skill denial and project workspace access.
  - `tests/test_runtime_broker.py`: keep broker status coverage; add or update sparse-workspace runtime surface assertions if broker helper assumes copied files.
  - `tests/test_runtime_skills.py`: keep active buddy skill materialization assertions; no source runtime visibility assertions belong here.

### Core data and call flow

`buddyswitch_workspace_execution_sparse_paths()` returns tracked paths only:

```text
scripts/env/
scripts/runtime_kernel/
scripts/turn_runtime.py
scripts/env_store.py
scripts/env_manifest.py
scripts/env_profiles.py
scripts/browser_evidence.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/
framework/contracts/
```

Runtime generated/projection paths are installed after sparse checkout:

```text
AGENTS.md
.agents/skills/**
projects/app
buddyswitch/objects/{tracks,tasks,artifacts,handoffs}
buddyswitch/local/buddybox/<active_buddy>
.runtime/**
.codex/config.toml
```

Start flow:

```text
start_locked_bootstrap
  -> buddyswitch_ensure_shared_env
  -> buddyswitch_workspace_prepare_execution_worktree
     -> buddyswitch_workspace_ensure_execution_worktree
        -> validate or configure execution sparse checkout
     -> install state projections and active buddybox
     -> install runtime AGENTS
     -> install runtime skills
     -> install local excludes
     -> install guardrail hooks
  -> buddyswitch_workspace_ensure_project_worktree
  -> buddyswitch_workspace_repair_runtime_projects_app_projection
  -> buddyswitch_runtime_broker_ensure
  -> buddyswitch_patch_codex_config
```

Open flow:

```text
instance_open_locked_bootstrap
  -> validate instance and buddy
  -> buddyswitch_workspace_ensure_execution_worktree
  -> check live instance markers
  -> install/refresh runtime projections, AGENTS, skills, excludes, hooks
  -> ensure project workspace and repair projects/app projection
  -> broker/config/browser bootstrap
```

Codex profile shape:

```toml
default_permissions = "buddyswitch-runtime"

[permissions.buddyswitch-runtime.filesystem]
":project_roots" = {
  "." = "read",
  "buddyswitch/skills/**" = "none",
  "tools/**" = "none",
  "tests/**" = "none",
  "docs/**" = "none",
  "README.md" = "none",
  "buddyswitch-codex" = "none"
}
"/.../shared/project/workspace" = "read"   # "write" for dev profile
"/.../instances/<id>/home" = "write"
"/.../instances/<id>/codex-home" = "write"
"/.../instances/<id>/xdg-config" = "write"
"/.../instances/<id>/workspace/buddyswitch/local/buddybox/<buddy>" = "write"
"/tmp" = "write"

[permissions.buddyswitch-runtime.network]
enabled = true
mode = "full"
unix_sockets = { "/.../runtime-broker.sock" = "allow" }
```

The renderer must not emit `"/" = "read"` in profile mode.

## 5. 分阶段实施计划

### 阶段 1：锁定 execution workspace leak 的失败测试

目标：用 tests 先证明当前 execution workspace 仍暴露 source-only surfaces，并证明目标 runtime shape、active skills、project projection、active buddybox preservation。

具体文件变更：

- Modify `tests/test_buddyswitch_launcher.py`

详细步骤：

1. Add helper inside `BuddySwitchLauncherTests`:
   - `_runtime_sparse_list(workspace_dir: Path) -> list[str]` runs `git -C <workspace_dir> sparse-checkout list`.
   - `_assert_runtime_workspace_excludes_source_surfaces(workspace_dir: Path)` asserts these do not exist: `buddyswitch/skills`, `tools`, `tests`, `docs`, `README.md`, `buddyswitch-codex`.
   - `_assert_pm_runtime_shape(workspace_dir: Path, shared_root: Path)` asserts required runtime files exist, `projects/app` resolves to `shared_root/project/workspace/projects/app`, state object dirs are symlinks to `shared_root/state`, active buddybox is a real directory, and `.agents/skills/write-prd/SKILL.md` exists.
2. Add `test_instance_start_execution_workspace_is_sparse_runtime_surface`.
   - Start PM with existing fake Codex/fake browser pattern from `test_start_execution_worktree_uses_runtime_workspace_agents_header`.
   - Assert `payload["cwd"] == shared_root/instances/<id>/workspace`.
   - Assert `git sparse-checkout list` equals:
     - `scripts/env/`
     - `scripts/runtime_kernel/`
     - `scripts/turn_runtime.py`
     - `scripts/env_store.py`
     - `scripts/env_manifest.py`
     - `scripts/env_profiles.py`
     - `scripts/browser_evidence.py`
     - `buddyswitch/manifest.toml`
     - `buddyswitch/env-profiles/`
     - `framework/contracts/`
   - Assert source surfaces are absent.
   - Assert `workspace/.agents/skills/write-prd/SKILL.md` exists and `workspace/.agents/skills/shape-prototype` does not exist.
   - Assert `workspace/buddyswitch/skills/design/shape-prototype/SKILL.md` does not exist.
3. Add `test_instance_start_design_runtime_skill_exists_without_source_skill_tree`.
   - Start design instance.
   - Assert `.agents/skills/shape-prototype/SKILL.md` exists.
   - Assert `buddyswitch/skills/design/shape-prototype` and `tools/launcher/assets/buddies/design` do not exist in the runtime workspace.
4. Add `test_instance_open_narrows_existing_full_execution_worktree_and_preserves_active_buddybox`.
   - Use `_write_instance_record` and `_add_test_worktree(workspace_dir)` to create an existing full worktree.
   - Before open, create `workspace/buddyswitch/local/buddybox/pm/reopen/probe.txt` with `survives\n`.
   - Assert `workspace/buddyswitch/skills/design/shape-prototype/SKILL.md` exists before open.
   - Open the instance.
   - Assert source skill path is gone, sparse list is expected, active buddybox probe still exists with the same content, and PM runtime skills were refreshed.
5. Add `test_instance_open_rejects_unmanaged_source_changes_before_sparse_narrowing`.
   - Create existing full worktree.
   - Write untracked or modified file under `workspace/tools/launcher/source-edit.txt`.
   - Open the instance.
   - Assert non-zero return code, stderr contains `execution workspace has local changes outside runtime-managed paths`, the file still exists, source paths still exist, and fake Codex capture file was not written.
6. Add `test_runtime_local_excludes_cover_generated_runtime_paths`.
   - Start PM.
   - Read `git -C <workspace> rev-parse --git-path info/exclude`.
   - Assert it contains exact lines: `AGENTS.md`, `.agents/skills/**`, `projects/app`, `.runtime/**`, `buddyswitch/objects/tracks/**`, `buddyswitch/objects/tasks/**`, `buddyswitch/objects/artifacts/**`, `buddyswitch/objects/handoffs/**`, `buddyswitch/local/buddybox/**`.

预期行为变化：这些 tests fail before implementation because execution workspace is full, sparse list is absent or broader than expected, and source skills/tools/docs are present.

对应需求编号：`REQ-001` to `REQ-013`, `REQ-024`.

验证命令：

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_execution_workspace_is_sparse_runtime_surface -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_design_runtime_skill_exists_without_source_skill_tree -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_narrows_existing_full_execution_worktree_and_preserves_active_buddybox -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_unmanaged_source_changes_before_sparse_narrowing -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_local_excludes_cover_generated_runtime_paths -q
```

阶段完成标准：all five tests fail for the expected boundary reasons before implementation, without failures caused by fixture setup or fake Codex/browser setup.

### 阶段 2：实现 execution sparse checkout 和 open/start 修复

目标：让 fresh and existing execution worktrees reach the runtime-only sparse boundary by construction, while keeping active buddybox and runtime projections safe.

具体文件变更：

- Modify `tools/launcher/workspace.sh`
- Modify `buddyswitch-codex`

详细步骤：

1. In `tools/launcher/workspace.sh`, add `buddyswitch_workspace_execution_sparse_paths()` after `buddyswitch_workspace_project_sparse_paths()`:
   - It prints the exact tracked runtime path list from 阶段 1.
2. Add `buddyswitch_workspace_execution_forbidden_entries()`:
   - It prints `buddyswitch/skills`, `tools`, `tests`, `docs`, `README.md`, `buddyswitch-codex`, `buddyswitch/content/buddybox`, `runs`, `buddyswitch/content/runs`.
3. Add `buddyswitch_workspace_runtime_managed_paths()`:
   - It prints `AGENTS.md`, `.agents/skills`, `.runtime`, `.codex`, `projects/app`, all object projection dirs, and `buddyswitch/local/buddybox/<active_buddy>` when active buddy is available.
4. Add `buddyswitch_workspace_execution_worktree_has_sparse_boundary(workspace_dir)`:
   - Verify `git -C "${workspace_dir}" rev-parse --is-inside-work-tree`.
   - Compare `git -C "${workspace_dir}" sparse-checkout list` to `buddyswitch_workspace_execution_sparse_paths`.
   - Loop over forbidden entries and return failure if any exists or is a symlink.
   - Assert required runtime tracked files exist: `scripts/env/client.py`, `scripts/runtime_kernel/broker.py`, `scripts/turn_runtime.py`, `buddyswitch/manifest.toml`, `framework/contracts/pm.md`.
5. Add `buddyswitch_workspace_execution_worktree_has_dirty_unmanaged_changes(workspace_dir)`:
   - Build a `git status --porcelain --untracked-files=all -- .` command excluding every path from `buddyswitch_workspace_runtime_managed_paths`.
   - Return true when output is non-empty.
6. Add `buddyswitch_workspace_report_dirty_unmanaged_execution_changes(workspace_dir)`:
   - Print `execution workspace has local changes outside runtime-managed paths; refusing to narrow sparse checkout`.
   - Print `execution workspace: <path>`.
   - Print the same excluded `git status --short --untracked-files=all` output.
7. Add `buddyswitch_workspace_configure_execution_sparse_checkout(workspace_dir, mode)`:
   - Accept `fresh` or `existing`.
   - For `existing`, call dirty unmanaged checker first and fail with code `3` after report if dirty.
   - Run:
     - `git -C "${workspace_dir}" sparse-checkout init --no-cone`
     - `git -C "${workspace_dir}" sparse-checkout set --no-cone $(buddyswitch_workspace_execution_sparse_paths)`
     - `git -C "${workspace_dir}" checkout HEAD`
   - Validate with `buddyswitch_workspace_execution_worktree_has_sparse_boundary`.
   - On validation failure, print `execution workspace sparse checkout did not reach expected runtime boundary`.
8. Modify `buddyswitch_workspace_force_rebuild_execution_worktree()`:
   - Keep staging setup and rollback behavior.
   - Replace full checkout worktree add with:
     - `git -C "${repo_root}" worktree add --detach --no-checkout "${workspace_dir}" HEAD`
     - `buddyswitch_workspace_configure_execution_sparse_checkout "${workspace_dir}" fresh`
   - Restore staged runtime outputs after sparse checkout succeeds.
9. Modify `buddyswitch_workspace_ensure_execution_worktree()`:
   - If `buddyswitch_workspace_is_valid_execution_worktree` fails, call `buddyswitch_workspace_force_rebuild_execution_worktree`.
   - If valid and `buddyswitch_workspace_execution_worktree_has_sparse_boundary` succeeds, call `buddyswitch_workspace_sync_runtime_surface`.
   - If valid but sparse boundary fails, call `buddyswitch_workspace_configure_execution_sparse_checkout "${BUDDYSWITCH_WORKSPACE_DIR}" existing`, then `buddyswitch_workspace_sync_runtime_surface`.
10. Replace `buddyswitch_workspace_sync_runtime_surface()` body:
    - Remove the embedded Python copy loop.
    - Call `buddyswitch_workspace_configure_execution_sparse_checkout "${workspace_dir}" existing` only when sparse boundary is missing; otherwise run `git -C "${workspace_dir}" checkout HEAD -- $(buddyswitch_workspace_execution_sparse_paths)` to reset tracked runtime files to the worktree HEAD.
    - Call `buddyswitch_workspace_neutralize_project_codex_config`.
11. Modify `buddyswitch_workspace_install_local_excludes()`:
    - Add exact patterns from 阶段 1.
12. Modify `buddyswitch-codex` `instance_open_locked_bootstrap`:
    - Replace the block that returns `Instance open blocked: workspace is missing or invalid...` for any invalid execution worktree with:
      - if `buddyswitch_workspace_is_valid_execution_worktree` fails, keep the existing block message and return `3`;
      - if valid, call `buddyswitch_workspace_ensure_execution_worktree`.
    - This preserves blocking for missing/non-worktree instance workspaces and allows valid full worktrees to be narrowed.

预期行为变化：new starts create sparse execution worktrees; existing clean full execution worktrees are narrowed on open; unmanaged source-only edits block migration; source skills/tools/docs disappear from product-mode runtime workspace.

对应需求编号：`REQ-001` to `REQ-013`, `REQ-021`, `REQ-022`, `REQ-024`.

验证命令：

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_execution_workspace_is_sparse_runtime_surface -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_design_runtime_skill_exists_without_source_skill_tree -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_narrows_existing_full_execution_worktree_and_preserves_active_buddybox -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_unmanaged_source_changes_before_sparse_narrowing -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_local_excludes_cover_generated_runtime_paths -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_uses_shared_project_workspace_and_instance_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_workspace_rebuild_preserves_active_buddybox_inside_instance_workspace -q
```

阶段完成标准：all listed tests pass; `git sparse-checkout list` inside a captured runtime workspace is the expected runtime path list; PM and design active runtime skills behave as required.

### 阶段 3：收窄 Codex host permission profile

目标：生成的 `buddyswitch-runtime` profile no longer grants full filesystem read, while preserving necessary runtime/project/env access and dev project write.

具体文件变更：

- Modify `tools/launcher/codex_config.py`
- Modify `tests/test_buddy_env_sandbox.py`
- Modify `tests/test_env_layer_boundaries.py`
- Modify `tests/test_buddyswitch_launcher.py` `_assert_codex_automation_config`

详细步骤：

1. In `tests/test_buddy_env_sandbox.py`, add helper `_profile_filesystem_entries(config_text) -> dict[str, object]` using existing TOML parser.
2. Update `test_non_dev_permission_profile_keeps_workspace_read_only_and_writes_only_safe_roots`:
   - Assert `"/"` is not in filesystem.
   - Assert `filesystem[":project_roots"]["."] == "read"`.
   - Assert deny rows for `buddyswitch/skills/**`, `tools/**`, `tests/**`, `docs/**`, `README.md`, `buddyswitch-codex` are `"none"`.
   - Assert project workspace absolute path is `"read"`, not `"write"`.
   - Assert home, codex-home, xdg-config, active buddybox, and `/tmp` are `"write"`.
   - Assert shared root, state root, instance root, workspace root, source repo root, and source Codex home are absent.
3. Update `test_dev_permission_profile_includes_project_workspace_but_keeps_state_read_only`:
   - Assert project workspace absolute path is `"write"`.
   - Assert no `"/"` entry and no source repo root entry.
4. Add `test_permission_profile_denies_stale_runtime_source_surfaces` to `tests/test_buddy_env_sandbox.py`:
   - Render PM config.
   - Assert `:project_roots` deny table covers source skill, tools, tests, docs, root README, and launcher executable.
   - Assert no deny row points to `.agents/skills/**`.
5. Add `test_permission_profile_does_not_grant_pm_project_or_design_sandbox_writes` to `tests/test_env_layer_boundaries.py`:
   - Render PM config.
   - Assert no write entry equals project workspace, workspace root, `workspace/.sandbox`, `workspace/.sandbox/design`, or shared root.
   - Assert active buddybox remains write.
6. Add `test_permission_profile_keeps_dev_project_write_and_runtime_reads` to `tests/test_env_layer_boundaries.py`:
   - Render dev config.
   - Assert project workspace is write.
   - Assert runtime project root table is present with `"." = "read"` and source denies.
7. Update `tests/test_buddyswitch_launcher.py::_assert_codex_automation_config`:
   - In profile mode, replace expectations for `"/" = "read"` with expectations that it is absent.
   - Keep expectations for `default_permissions`, network full mode, `request_permissions = false`, disabled web search, no source repo common dir, and broker socket allowlist.
8. In `tools/launcher/codex_config.py`, replace `render_permission_profile_block`:
   - Render filesystem entries from a dict preserving insertion order.
   - Render nested `:project_roots` inline table using existing `toml_string` for keys and string values.
   - Keep network block rendering and Unix socket allowlist.
9. Add `_profile_mode_workspace_deny_rules()` and `_build_profile_mode_filesystem(args)` as described in final architecture.
10. Change `patched_config_text` and `main`:
    - In profile mode call `_build_profile_mode_filesystem(args)` instead of `build_writable_roots(args)`.
    - In local mode keep `build_writable_roots(args)` and `render_sandbox_workspace_write_block`.
    - Keep `build_writable_roots` available for local mode tests.
11. Ensure `_safe_temp_roots` still rejects temp roots inside shared/project/state/instance/workspace boundaries.
12. Ensure `_build_profile_mode_unix_sockets` is unchanged and still canonicalizes broker socket.

预期行为变化：generated Codex product-mode config denies source-only reads by default category and no longer grants broad `"/"` read. Dev remains the only built-in buddy with project workspace write.

对应需求编号：`REQ-014` to `REQ-019`, `REQ-024`, `REQ-025`.

验证命令：

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py -q
python3 -m pytest tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

阶段完成标准：profile-mode TOML has no `"/"` filesystem grant, denies stale source runtime paths with `"none"`, grants project write only for dev, grants PM active buddybox write, and keeps broker socket/network/approval settings.

### 阶段 4：验证 runtime commands, broker, search/browser surfaces after narrowing

目标：prove the narrowed runtime surface still supports the main product-mode commands and search/browser affordances.

具体文件变更：

- Modify `tests/test_buddyswitch_launcher.py`
- Modify fake Codex helper `_write_fake_codex` inside `tests/test_buddyswitch_launcher.py`

详细步骤：

1. Extend `_write_fake_codex`:
   - If `BUDDYSWITCH_TEST_RUNTIME_COMMAND_SMOKE=1`, run these commands from `cwd`:
     - `python3 scripts/turn_runtime.py status`
     - `python3 scripts/env/client.py context summarize`
     - `python3 scripts/env/client.py buddybox desc`
     - `python3 scripts/env/client.py search status --query boundary-smoke`
   - Capture each command as `{name, returncode, stdout, stderr, json}` in payload key `runtime_command_smoke`.
   - JSON decode stdout when present and record decode errors without swallowing non-zero exit codes.
2. Add `test_pm_runtime_commands_work_after_sparse_execution_workspace`.
   - Start PM with `BUDDYSWITCH_TEST_RUNTIME_COMMAND_SMOKE=1`.
   - Assert all four commands return `0`.
   - Assert `turn_runtime.status` JSON has `ok=true` and env tools include `context`, `buddybox`, `search`.
   - Assert `context summarize` JSON has `ok=true` and `tool_affordances.buddybox.capability == "private_file_workspace"`.
   - Assert `buddybox desc` JSON has `ok=true` and `lifetime_scope == "active_instance_workspace"`.
   - Assert `search status` JSON has `ok=true` and native Codex web search is disabled in the response.
3. Add `test_runtime_broker_starts_from_sparse_workspace`.
   - Use existing `BUDDYSWITCH_TEST_BROKER_STATUS=1` fake Codex probe.
   - Assert status payload is healthy and `runtime_workspace` is true.
   - Assert `scripts/runtime_kernel/broker.py` and `buddyswitch/manifest.toml` exist in sparse workspace.
4. Add `test_no_runtime_test_depends_on_source_dirs_inside_instance_workspace`.
   - Start PM and assert runtime workspace lacks `tools`, `tests`, and `docs`.
   - Assert the fake Codex command smoke still passes, proving tests do not require those directories in the runtime workspace.

预期行为变化：runtime command paths continue to work from the narrow runtime workspace; failures identify missing sparse runtime files immediately.

对应需求编号：`REQ-004`, `REQ-005`, `REQ-020`, `REQ-023`, `REQ-024`.

验证命令：

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_pm_runtime_commands_work_after_sparse_execution_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_broker_starts_from_sparse_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_no_runtime_test_depends_on_source_dirs_inside_instance_workspace -q
python3 -m pytest tests/test_runtime_broker.py -q
python3 -m pytest tests/test_search_env_tool.py -q
```

阶段完成标准：broker, context, buddybox, turn runtime, and search status all pass from sparse runtime workspace; no product-mode launcher test requires `tools/**`, `tests/**`, or `docs/**` inside instance workspace.

### 阶段 5：broader regression and consistency cleanup

目标：remove stale assumptions, keep runtime docs/guidance as route maps, and run the broader verification set.

具体文件变更：

- Modify `tests/test_repo_consistency.py` only if a new grep gate is needed.
- Modify `README.md` only if existing workspace wording contradicts the new runtime shape.
- Do not add prose mirrors for runtime behavior; runtime contracts remain code, JSON contracts, role contracts, and tests.

详细步骤：

1. Add `test_product_mode_runtime_workspace_source_surfaces_are_not_required_by_guidance` to `tests/test_repo_consistency.py` if grep coverage is not already present:
   - Scan `tools/launcher/assets/buddies`, `buddyswitch/skills`, `framework/contracts`, `README.md`, and `AGENTS.md`.
   - Assert active guidance does not instruct runtime buddies to scan `buddyswitch/skills/**`, `tools/launcher/assets/buddies/**`, `docs/**`, or `tests/**` inside product-mode workspace.
   - Allow source maintenance docs under `docs/spec/**` and `docs/memo/**`.
2. Run focused launcher and sandbox suites from stages 1 to 4.
3. Run broader launcher/runtime suites listed below.
4. Run grep checks:
   - `rg -n '"/" = "read"|buddyswitch/skills/design/shape-prototype|tools/launcher/assets/buddies|workspace.*full repository|full repo' tools scripts tests README.md AGENTS.md framework buddyswitch`
   - Filter expected source definitions/tests only; no runtime guidance should instruct product-mode host to depend on those paths.
5. Confirm `git status --short` shows only intended implementation/test/doc changes.

预期行为变化：no stale source-surface guidance remains in active runtime docs; broad verification passes.

对应需求编号：all requirements, especially `REQ-021` to `REQ-025`.

验证命令：

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py tests/test_runtime_broker.py tests/test_runtime_skills.py tests/test_runtime_agents.py tests/test_search_env_tool.py -q
python3 -m pytest tests/test_runless_runtime_contract.py tests/test_host_decision_surface_product_mode.py tests/test_repo_consistency.py -q
rg -n '"/" = "read"|workspace.*full repository|full repo' tools scripts tests README.md AGENTS.md framework buddyswitch
git status --short
```

阶段完成标准：all focused and broader checks pass; grep output contains no active runtime-surface regression; final status contains only scoped changes.

## 6. 迁移 / 删除策略

- Delete from runtime visibility by sparse checkout, not by long-lived runtime filters:
  - `buddyswitch/skills/**`
  - `tools/**`
  - `tests/**`
  - `docs/**`
  - root `README.md`
  - root `buddyswitch-codex`
  - retired runtime residue dirs such as `runs/**` and `buddyswitch/content/runs/**`
- Replace full execution checkout creation with sparse creation. There is no compatibility mode that keeps full execution workspace visible.
- Existing clean full execution worktrees are narrowed in place on start/open.
- Existing execution worktrees with unmanaged source-only local changes fail with a concrete message and preserve the files. This is a short-term migration safety guard, not a dual runtime path; the exit condition is that the user deletes the instance or removes those unmanaged source edits.
- Active buddybox files under `buddyswitch/local/buddybox/<active_buddy>` remain workspace-local and survive rebuild through existing staging/restore.
- Shared object projections are recreated from `shared_root/state` and remain symlinks.
- `.agents/skills` and runtime `AGENTS.md` are regenerated every start/open and excluded from Git noise.
- Codex profile removes `"/" = "read"` in product mode. If a legitimate runtime command fails after this removal, the fix is to add a category-level runtime read/write grant, not to restore broad filesystem read.

## 7. 完成定义

The task is complete only when all conditions hold:

- New PM execution workspaces are sparse runtime worktrees and do not contain `buddyswitch/skills/**`, `tools/**`, `tests/**`, `docs/**`, root `README.md`, or root `buddyswitch-codex`.
- Existing clean full PM workspaces are narrowed on `instance open`; active buddybox files survive reopen.
- Existing workspaces with unmanaged source-only edits fail clearly before migration and are not silently deleted.
- PM `.agents/skills` contains PM skills and shared tool skills only; design `.agents/skills` contains `shape-prototype`; source skill trees are absent for both.
- `projects/app` in runtime workspace resolves to the shared sparse project workspace, and project workspace remains sparse to `projects/app/`.
- Generated Codex profile has no `"/" = "read"` product-mode grant, denies stale source runtime paths with `"none"`, keeps PM project workspace read-only, and keeps dev project workspace writable.
- `request_permissions = false`, disabled native web search, network mode, and broker Unix socket allowlist remain in generated config.
- `python3 scripts/turn_runtime.py status`, `python3 scripts/env/client.py context summarize`, `python3 scripts/env/client.py buddybox desc`, and `python3 scripts/env/client.py search status --query boundary-smoke` work from a PM sparse runtime workspace.
- Focused tests from every phase pass.
- Broader verification passes:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py tests/test_runtime_broker.py tests/test_runtime_skills.py tests/test_runtime_agents.py tests/test_search_env_tool.py tests/test_runless_runtime_contract.py tests/test_host_decision_surface_product_mode.py tests/test_repo_consistency.py -q
```

- No runtime guidance relies on prompt-only enforcement or instructs product-mode buddies to inspect source-only repo paths.

# Runtime Workspace Host Boundary Test Plan

## 1. 测试设计原则

- Tests start from the source memo's externally observable contracts: runtime workspace shape, absent source paths, active skill visibility, Codex config filesystem rules, project write authority, broker/env tool command behavior, migration safety, and persistence of active buddybox files.
- Tests must not be shaped around only the future helper implementation. Unit-level helper assertions are allowed for sparse path lists and config rendering, but completion depends on launcher-created filesystem state and generated TOML.
- Tests verify user-visible state and outputs: directory presence/absence, symlink targets, `git sparse-checkout list`, generated `config.toml`, CLI JSON output, launcher exit code/stderr, and persisted files.
- Negative tests are required for stale source paths, unmanaged local changes, PM project writes, PM `.sandbox/design` writes, and missing runtime files.
- No happy-path-only coverage. PM, design, and dev must all be represented because their skill and project-write boundaries differ.
- Tests must keep SHARP scope: no generic permission engine, no virtual filesystem, no prompt workaround, and no compatibility test that accepts full source checkout visibility.
- Actual Codex sandbox enforcement is external to the fake Codex binary used by launcher tests. Automated tests must prove the generated profile rules and workspace absence; one manual real-Codex smoke is the final enforcement check when credentials/local Codex are available.

## 2. 需求覆盖矩阵

| Requirement | Automated tests or verification |
| --- | --- |
| `REQ-001` | `RWH-SPARSE-001`, `RWH-SPARSE-004` |
| `REQ-002` | `RWH-SPARSE-006`, `RWH-RUNTIME-001` |
| `REQ-003` | `RWH-SPARSE-006`, `RWH-PROJECT-001` |
| `REQ-004` | `RWH-RUNTIME-001`, `RWH-RUNTIME-002`, `RWH-RUNTIME-003` |
| `REQ-005` | `RWH-SPARSE-001`, `RWH-RUNTIME-001` |
| `REQ-006` | `RWH-SPARSE-001`, `RWH-SPARSE-007` |
| `REQ-007` | `RWH-SPARSE-001`, `RWH-SPARSE-002`, `RWH-SPARSE-003`, `RWH-REGRESSION-001` |
| `REQ-008` | `RWH-SKILL-001`, `RWH-SKILL-002`, `RWH-SKILL-003` |
| `REQ-009` | `RWH-SPARSE-001`, `RWH-SPARSE-008` |
| `REQ-010` | `RWH-SPARSE-004`, `RWH-SPARSE-005` |
| `REQ-011` | `RWH-MIGRATION-001`, `RWH-MIGRATION-002` |
| `REQ-012` | `RWH-SPARSE-007` |
| `REQ-013` | `RWH-SPARSE-001`, `RWH-REGRESSION-001` |
| `REQ-014` | `RWH-PERM-001`, `RWH-PERM-004` |
| `REQ-015` | `RWH-PERM-001`, `RWH-RUNTIME-002`, `RWH-RUNTIME-003`, `RWH-RUNTIME-004` |
| `REQ-016` | `RWH-PERM-001`, `RWH-PERM-002`, `RWH-PERM-003` |
| `REQ-017` | `RWH-PERM-002`, `RWH-PERM-003`, `RWH-PROJECT-002` |
| `REQ-018` | `RWH-PERM-004`, `RWH-SPARSE-002`, `RWH-SPARSE-003` |
| `REQ-019` | `RWH-PERM-005`, existing broker socket tests |
| `REQ-020` | `RWH-RUNTIME-002`, `RWH-RUNTIME-003`, `RWH-RUNTIME-004`, `RWH-RUNTIME-005` |
| `REQ-021` | `RWH-REGRESSION-002` |
| `REQ-022` | `RWH-REGRESSION-003`, implementation review checklist |
| `REQ-023` | `RWH-RUNTIME-001`, `RWH-RUNTIME-002`, `RWH-MIGRATION-001` |
| `REQ-024` | `RWH-SPARSE-002`, `RWH-SKILL-001`, `RWH-SKILL-002`, `RWH-PERM-002`, `RWH-PERM-003`, `RWH-RUNTIME-002` |
| `REQ-025` | `RWH-PERM-001`, `RWH-PERM-004` |

All requirements have automated coverage except the real external Codex sandbox attempt to write or read denied paths. Automated tests verify generated policy and absent files; manual verification executes real Codex shell commands under the generated profile.

## 3. 测试分层

### 单元测试

Purpose: prove config rendering and sparse path helper outputs match the contract without launching Codex.

Coverage:

- `tools/launcher/codex_config.py` generated TOML.
- `tools/launcher/workspace.sh` sourced helper smoke through shell commands where helper output can be asserted.

Run:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
```

### 集成测试

Purpose: prove launcher start/open creates the correct filesystem state and migration behavior.

Coverage:

- `./buddyswitch-codex instance start --buddy pm`
- `./buddyswitch-codex instance start --buddy design`
- `./buddyswitch-codex instance open <instance-id>`
- Git worktree and sparse checkout state.
- Active buddybox preservation.

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

### CLI、API、UI 或主路径运行测试

Purpose: prove runtime CLI/API commands still work from sparse runtime workspace.

Coverage:

- `python3 scripts/turn_runtime.py status`
- `python3 scripts/env/client.py context summarize`
- `python3 scripts/env/client.py buddybox desc`
- `python3 scripts/env/client.py search status --query boundary-smoke`
- Runtime broker status and env.tool gateway.

Run:

```bash
python3 -m pytest tests/test_runtime_broker.py tests/test_search_env_tool.py tests/test_runless_runtime_contract.py -q
```

### 回归测试

Purpose: prove source-only surfaces and prompt-only enforcement assumptions do not return.

Coverage:

- Runtime skills and AGENTS validations.
- Repo consistency grep gates.
- Host decision surface.

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_runtime_agents.py tests/test_host_decision_surface_product_mode.py tests/test_repo_consistency.py -q
```

### 手动验证

Purpose: verify real Codex sandbox enforcement because fake launcher tests cannot enforce filesystem policy.

Steps:

1. Confirm worktree and branch:

   ```bash
   pwd
   git branch --show-current
   ```

   Expected: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` and `dev_buddy_mem`.

2. Start a PM instance:

   ```bash
   ./buddyswitch-codex instance start --buddy pm -- debug prompt-input "runtime boundary smoke"
   ```

3. In the launched runtime workspace, run:

   ```bash
   test ! -e buddyswitch/skills/design/shape-prototype/SKILL.md
   test -f .agents/skills/write-prd/SKILL.md
   python3 scripts/turn_runtime.py status
   python3 scripts/env/client.py context summarize
   python3 scripts/env/client.py buddybox desc
   ```

4. Ask Codex shell to attempt:

   ```bash
   cat buddyswitch/skills/design/shape-prototype/SKILL.md
   mkdir -p .sandbox/design && printf x > .sandbox/design/blocked.txt
   printf x > projects/app/pm-blocked.txt
   ```

   Expected: source skill file is absent; PM write attempts are denied by sandbox or fail due read-only profile; `projects/app/pm-blocked.txt` is not created.

5. Start a dev instance and verify project write is allowed:

   ```bash
   ./buddyswitch-codex instance start --buddy dev -- debug prompt-input "project write smoke"
   printf dev-smoke > projects/app/dev-write-smoke.txt
   test -f projects/app/dev-write-smoke.txt
   rm projects/app/dev-write-smoke.txt
   ```

Manual verification is supplemental. Completion still requires automated tests.

## 4. 详细测试用例

### `RWH-SPARSE-001`: PM instance starts with sparse runtime workspace

- 覆盖需求：`REQ-001`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-009`, `REQ-013`
- 用户 / 系统场景：PM starts a product-mode instance and receives only the runtime surface.
- 前置条件：Fake Codex and fake browser launcher fixture in `tests/test_buddyswitch_launcher.py`.
- 输入：`./buddyswitch-codex instance start --buddy pm debug prompt-input "Draft the onboarding PRD"`.
- 预期输出或状态变化：`workspace` is a valid Git worktree; `git sparse-checkout list` equals the runtime path list; required runtime scripts, manifest, env-profiles, contracts, `AGENTS.md`, active skills, object projections, buddybox, and `projects/app` projection exist.
- 断言重点：`buddyswitch/skills`, `tools`, `tests`, `docs`, `README.md`, and `buddyswitch-codex` are absent.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_execution_workspace_is_sparse_runtime_surface`

### `RWH-SPARSE-002`: PM cannot discover source design skill by workspace scan

- 覆盖需求：`REQ-007`, `REQ-008`, `REQ-018`, `REQ-024`
- 用户 / 系统场景：PM shell discovery scans the runtime workspace.
- 前置条件：PM instance from fake launcher start.
- 输入：Filesystem assertions for `workspace.rglob("shape-prototype")` and direct path checks.
- 预期输出或状态变化：`.agents/skills/shape-prototype` is absent; `buddyswitch/skills/design/shape-prototype/SKILL.md` is absent; `.agents/skills/write-prd/SKILL.md` exists.
- 断言重点：PM still has PM skills while source design skill tree is absent.
- 测试类型：Launcher integration regression.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_execution_workspace_is_sparse_runtime_surface`

### `RWH-SPARSE-003`: design keeps runtime shape-prototype without source skill tree

- 覆盖需求：`REQ-007`, `REQ-008`, `REQ-018`, `REQ-024`
- 用户 / 系统场景：Design buddy starts and receives its runtime prototype skill.
- 前置条件：Fake launcher environment.
- 输入：`./buddyswitch-codex instance start --buddy design debug prompt-input "Shape prototype"`.
- 预期输出或状态变化：`.agents/skills/shape-prototype/SKILL.md` exists; `buddyswitch/skills/design/shape-prototype` does not exist; `tools/launcher/assets/buddies/design` does not exist.
- 断言重点：Runtime skill materialization survives workspace slimming.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_design_runtime_skill_exists_without_source_skill_tree`

### `RWH-SPARSE-004`: existing full execution worktree is narrowed on open

- 覆盖需求：`REQ-001`, `REQ-010`, `REQ-011`
- 用户 / 系统场景：User reopens an old instance whose workspace was created as a full checkout.
- 前置条件：`_write_instance_record` creates inactive PM instance; `_add_test_worktree` creates full worktree.
- 输入：`./buddyswitch-codex instance open <instance-id> debug prompt-input "continue"`.
- 预期输出或状态变化：Open succeeds; source skill tree disappears; sparse list equals runtime path list.
- 断言重点：The launcher repairs open, not only new start.
- 测试类型：Migration integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_narrows_existing_full_execution_worktree_and_preserves_active_buddybox`

### `RWH-SPARSE-005`: unmanaged source-only changes block narrowing

- 覆盖需求：`REQ-010`, `REQ-022`
- 用户 / 系统场景：Old full workspace contains local source edits under `tools/**`.
- 前置条件：Existing full PM worktree with `workspace/tools/launcher/source-edit.txt`.
- 输入：`./buddyswitch-codex instance open <instance-id> debug prompt-input "continue"`.
- 预期输出或状态变化：Command fails before launching fake Codex; stderr names unmanaged execution workspace changes; file is still present.
- 断言重点：No silent deletion and no long-lived compatibility path.
- 测试类型：Negative migration integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_unmanaged_source_changes_before_sparse_narrowing`

### `RWH-SPARSE-006`: project workspace remains sparse and shared

- 覆盖需求：`REQ-002`, `REQ-003`
- 用户 / 系统场景：Runtime workspace exposes product source through `projects/app`.
- 前置条件：PM instance start.
- 输入：Check `workspace/projects/app.resolve()` and `git -C shared_root/project/workspace sparse-checkout list`.
- 预期输出或状态变化：Runtime `projects/app` resolves to `shared_root/project/workspace/projects/app`; project sparse list is `["projects/app/"]`; project workspace lacks source framework entries.
- 断言重点：Execution slimming does not replace the already-correct project workspace model.
- 测试类型：Launcher integration regression.
- 建议测试文件路径和测试名称：Existing `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_uses_shared_project_workspace_and_instance_workspace`

### `RWH-SPARSE-007`: local excludes cover generated runtime paths

- 覆盖需求：`REQ-006`, `REQ-012`
- 用户 / 系统场景：Launcher-managed generated files do not become noisy Git state.
- 前置条件：PM instance start.
- 输入：Read `git -C <workspace> rev-parse --git-path info/exclude`.
- 预期输出或状态变化：Exclude file contains `AGENTS.md`, `.agents/skills/**`, `projects/app`, `.runtime/**`, object dirs, and buddybox dirs.
- 断言重点：Generated runtime paths are explicitly ignored; tracked runtime source files remain managed by sparse checkout.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_local_excludes_cover_generated_runtime_paths`

### `RWH-SPARSE-008`: fresh execution worktree uses no-checkout sparse sequence

- 覆盖需求：`REQ-009`
- 用户 / 系统场景：New instance workspace is created through the runtime sparse helper.
- 前置条件：Use a fake `git` wrapper or inspect resulting worktree state in a temp shared root.
- 输入：PM instance start.
- 预期输出或状态变化：Worktree exists, sparse-checkout list is the runtime list, and forbidden tracked files were never present after bootstrap.
- 断言重点：Observable state is the primary assertion; command sequence is secondary and only used if fake git coverage already exists.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：covered by `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_execution_workspace_is_sparse_runtime_surface`

### `RWH-SKILL-001`: PM runtime skills are active-buddy-only

- 覆盖需求：`REQ-008`, `REQ-024`
- 用户 / 系统场景：PM gets PRD and shared tool skills only.
- 前置条件：PM instance start.
- 输入：List `workspace/.agents/skills`.
- 预期输出或状态变化：Installed skill IDs match PM manifest skill ids exactly; `shape-prototype` absent.
- 断言重点：Exact set equality prevents stale skill leakage.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：Existing `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`

### `RWH-SKILL-002`: design runtime skills include shape-prototype

- 覆盖需求：`REQ-008`, `REQ-024`
- 用户 / 系统场景：Design buddy can still shape prototypes.
- 前置条件：Design instance start.
- 输入：List `.agents/skills`.
- 预期输出或状态变化：`shape-prototype`, shared tool skills exist; `write-prd` absent.
- 断言重点：Only source skill tree is removed, not active runtime skill capability.
- 测试类型：Launcher integration.
- 建议测试文件路径和测试名称：Existing `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_design_workspace_has_design_runtime_skills`

### `RWH-SKILL-003`: runtime skill source copy matches manifest source

- 覆盖需求：`REQ-008`
- 用户 / 系统场景：Runtime `.agents/skills` receives current skill package content.
- 前置条件：Open existing instance with corrupted runtime skill file.
- 输入：`instance open`.
- 预期输出或状态变化：Runtime skill file is refreshed from source package into `.agents/skills`.
- 断言重点：Materialization remains active-buddy-only and refreshes stale generated output.
- 测试类型：Launcher regression.
- 建议测试文件路径和测试名称：Existing `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_refreshes_runtime_skills_and_removes_stale_skill`

### `RWH-PERM-001`: PM profile uses explicit runtime reads and no broad filesystem read

- 覆盖需求：`REQ-014`, `REQ-015`, `REQ-016`, `REQ-025`
- 用户 / 系统场景：Launcher patches PM `CODEX_HOME/config.toml`.
- 前置条件：Temp shared root and profile patch helper.
- 输入：Run `python3 tools/launcher/codex_config.py` with `--buddy pm`.
- 预期输出或状态变化：TOML has `default_permissions = "buddyswitch-runtime"`; `permissions.buddyswitch-runtime.filesystem` has no `"/"` key; `:project_roots["."] == "read"`; project workspace is `"read"`; instance home/codex/xdg, buddybox, temp are `"write"`.
- 断言重点：No source repo, shared root, state root, instance root, or workspace root absolute read/write grant.
- 测试类型：Config unit/integration.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_non_dev_permission_profile_keeps_workspace_read_only_and_writes_only_safe_roots`

### `RWH-PERM-002`: PM project workspace and `.sandbox/design` are not writable

- 覆盖需求：`REQ-017`, `REQ-024`
- 用户 / 系统场景：PM tries to write product source or design sandbox.
- 前置条件：Rendered PM config.
- 输入：Inspect filesystem entries.
- 预期输出或状态变化：No `"write"` entry for project workspace, workspace root, `workspace/.sandbox`, or `workspace/.sandbox/design`.
- 断言重点：Generated policy prevents PM write authority by category.
- 测试类型：Config boundary.
- 建议测试文件路径和测试名称：`tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_permission_profile_does_not_grant_pm_project_or_design_sandbox_writes`

### `RWH-PERM-003`: dev project workspace remains writable

- 覆盖需求：`REQ-016`, `REQ-017`, `REQ-024`
- 用户 / 系统场景：Dev instance implements approved product source changes.
- 前置条件：Rendered dev config.
- 输入：Inspect filesystem entries.
- 预期输出或状态变化：Project workspace absolute path is `"write"`; shared root/state/instance/workspace roots are not write entries.
- 断言重点：Boundary is buddy-profile-driven, not globally read-only.
- 测试类型：Config boundary.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_dev_permission_profile_includes_project_workspace_but_keeps_state_read_only`

### `RWH-PERM-004`: stale source paths are denied if present

- 覆盖需求：`REQ-014`, `REQ-018`, `REQ-025`
- 用户 / 系统场景：Migration or future regression leaves source-only dirs under runtime workspace.
- 前置条件：Rendered PM config.
- 输入：Inspect `filesystem[":project_roots"]`.
- 预期输出或状态变化：`buddyswitch/skills/**`, `tools/**`, `tests/**`, `docs/**`, `README.md`, and `buddyswitch-codex` map to `"none"`.
- 断言重点：Deny rules do not target `.agents/skills/**`.
- 测试类型：Config unit/integration.
- 建议测试文件路径和测试名称：`tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_permission_profile_denies_stale_runtime_source_surfaces`

### `RWH-PERM-005`: broker socket and approval hardening are preserved

- 覆盖需求：`REQ-019`
- 用户 / 系统场景：PM env tools call broker without permission prompts.
- 前置条件：Rendered PM config with `--broker-socket`.
- 输入：Inspect TOML.
- 预期输出或状态变化：`request_permissions = false`, web search disabled, network mode full, and `unix_sockets = { <socket> = "allow" }` exist.
- 断言重点：Read hardening does not break broker access or approval policy.
- 测试类型：Config regression.
- 建议测试文件路径和测试名称：Existing `tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_profile_mode_with_broker_socket_includes_unix_socket_allowlist`

### `RWH-RUNTIME-001`: broker starts from sparse workspace

- 覆盖需求：`REQ-002`, `REQ-004`, `REQ-005`, `REQ-023`
- 用户 / 系统场景：Launcher starts runtime broker after sparse checkout.
- 前置条件：PM instance start with fake Codex broker status probe.
- 输入：`BUDDYSWITCH_TEST_BROKER_STATUS=1`.
- 预期输出或状态变化：Broker status is healthy; `runtime_workspace` is true; broker script and manifest are present in workspace.
- 断言重点：Sparse path list includes every broker startup dependency.
- 测试类型：Launcher/runtime integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_broker_starts_from_sparse_workspace`

### `RWH-RUNTIME-002`: `turn_runtime.py status` works from sparse workspace

- 覆盖需求：`REQ-020`, `REQ-024`
- 用户 / 系统场景：Host inspects runtime status in a PM instance.
- 前置条件：PM start with runtime command smoke probe.
- 输入：`python3 scripts/turn_runtime.py status`.
- 预期输出或状态变化：Exit code 0; JSON `ok=true`; env tool catalog includes `context`, `buddybox`, and `search`.
- 断言重点：Runtime status does not import excluded source-only paths.
- 测试类型：CLI main-path.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_pm_runtime_commands_work_after_sparse_execution_workspace`

### `RWH-RUNTIME-003`: `context summarize` works from sparse workspace

- 覆盖需求：`REQ-020`, `REQ-024`
- 用户 / 系统场景：PM discovers context through broker-routed env tool.
- 前置条件：PM start with runtime command smoke probe and active broker socket.
- 输入：`python3 scripts/env/client.py context summarize`.
- 预期输出或状态变化：Exit code 0; JSON `ok=true`; response has `tool_affordances` and `buddybox_desc`.
- 断言重点：Client, broker, context service, manifest, contracts, and object projections are all available.
- 测试类型：CLI/API integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_pm_runtime_commands_work_after_sparse_execution_workspace`

### `RWH-RUNTIME-004`: `buddybox desc` works from sparse workspace

- 覆盖需求：`REQ-020`, `REQ-023`, `REQ-024`
- 用户 / 系统场景：PM inspects active private file capability.
- 前置条件：PM sparse runtime workspace with active buddybox directory.
- 输入：`python3 scripts/env/client.py buddybox desc`.
- 预期输出或状态变化：Exit code 0; JSON `ok=true`; `lifetime_scope == "active_instance_workspace"`; no product object mutation.
- 断言重点：Active buddybox directory remains real workspace-local storage.
- 测试类型：CLI/API integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_pm_runtime_commands_work_after_sparse_execution_workspace`

### `RWH-RUNTIME-005`: search status works for buddies with search capability

- 覆盖需求：`REQ-020`
- 用户 / 系统场景：PM or market checks search capability after read boundary hardening.
- 前置条件：PM sparse runtime workspace with active broker.
- 输入：`python3 scripts/env/client.py search status --query boundary-smoke`.
- 预期输出或状态变化：Exit code 0; JSON `ok=true`; native Codex web search remains disabled; allowed search backends reflect env profile.
- 断言重点：Search env tool does not require source-only dirs.
- 测试类型：CLI/API integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_pm_runtime_commands_work_after_sparse_execution_workspace` and existing `tests/test_search_env_tool.py`

### `RWH-MIGRATION-001`: active buddybox survives workspace rebuild/open

- 覆盖需求：`REQ-011`, `REQ-023`
- 用户 / 系统场景：PM private file exists before workspace repair.
- 前置条件：Existing PM instance with `workspace/buddyswitch/local/buddybox/pm/reopen/probe.txt`.
- 输入：`instance open`.
- 预期输出或状态变化：Probe exists after open with same content; no shared state buddybox directory is created.
- 断言重点：Runtime staging preserves active buddybox and does not sync it to shared state.
- 测试类型：Migration regression.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_narrows_existing_full_execution_worktree_and_preserves_active_buddybox`

### `RWH-MIGRATION-002`: runtime object projections remain shared state symlinks

- 覆盖需求：`REQ-006`, `REQ-011`
- 用户 / 系统场景：Runtime task/track/artifact/handoff state remains shared across instances.
- 前置条件：PM instance start.
- 输入：Inspect `workspace/buddyswitch/objects/{tracks,tasks,artifacts,handoffs}`.
- 预期输出或状态变化：Each path is a symlink to `shared_root/state/buddyswitch/objects/<kind>`.
- 断言重点：Execution workspace slimming does not move product objects into instance-local private storage.
- 测试类型：Launcher integration regression.
- 建议测试文件路径和测试名称：Existing `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header`

### `RWH-PROJECT-001`: project workspace sparse boundary survives runtime changes

- 覆盖需求：`REQ-003`
- 用户 / 系统场景：Product source remains available and narrow.
- 前置条件：PM instance start.
- 输入：Check shared project workspace top-level entries and sparse list.
- 预期输出或状态变化：Only `projects/app/` is checked out; framework/source dirs are absent.
- 断言重点：Do not regress the already-correct project workspace.
- 测试类型：Launcher regression.
- 建议测试文件路径和测试名称：Existing `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_uses_shared_project_workspace_and_instance_workspace`

### `RWH-PROJECT-002`: PM cannot write product source by policy while dev can

- 覆盖需求：`REQ-017`, `REQ-024`
- 用户 / 系统场景：PM attempts product source write; dev performs implementation write.
- 前置条件：Rendered PM and dev configs.
- 输入：Inspect filesystem entries for project workspace.
- 预期输出或状态变化：PM project workspace is `"read"`; dev project workspace is `"write"`.
- 断言重点：This is a config-level automated check; real Codex write attempt is manual verification.
- 测试类型：Config boundary.
- 建议测试文件路径和测试名称：`tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_dev_project_workspace_is_writable_and_non_dev_project_workspace_is_read_only`

### `RWH-REGRESSION-001`: runtime tests do not rely on source dirs inside instance workspace

- 覆盖需求：`REQ-007`, `REQ-013`
- 用户 / 系统场景：Product-mode instance no longer has `tools/**`, `tests/**`, or `docs/**`.
- 前置条件：PM sparse runtime workspace.
- 输入：Run runtime command smoke with those directories absent.
- 预期输出或状态变化：Runtime command smoke passes.
- 断言重点：Tests prove runtime functionality through runtime surface, not source tree leakage.
- 测试类型：Launcher/runtime regression.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_no_runtime_test_depends_on_source_dirs_inside_instance_workspace`

### `RWH-REGRESSION-002`: active guidance does not use prompt-only enforcement for source surfaces

- 覆盖需求：`REQ-021`
- 用户 / 系统场景：Runtime instructions remain route maps, not the security boundary.
- 前置条件：Local checkout.
- 输入：Grep active guidance files for instructions to scan source skills or launcher assets from product-mode runtime.
- 预期输出或状态变化：No active guidance tells runtime buddies to inspect `buddyswitch/skills/**`, `tools/launcher/assets/buddies/**`, `docs/**`, or `tests/**` in their runtime workspace.
- 断言重点：No prompt workaround replaces workspace/profile enforcement.
- 测试类型：Repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_runtime_workspace_source_surfaces_are_not_required_by_guidance`

### `RWH-REGRESSION-003`: no speculative infrastructure appears

- 覆盖需求：`REQ-022`
- 用户 / 系统场景：Implementation stays direct.
- 前置条件：Local checkout after implementation.
- 输入：Review diff and grep for new generic engines.
- 预期输出或状态变化：No new virtual filesystem, rule engine, workflow engine, plugin system, or permission framework modules are added.
- 断言重点：The change remains in launcher workspace setup and Codex config rendering.
- 测试类型：Implementation review plus grep.
- 建议测试文件路径和测试名称：No dedicated automated file unless new module names appear; final review command is required.

## 5. 负向与边界测试

- 缺失数据：`RWH-RUNTIME-001` covers missing sparse runtime file because broker status fails if `scripts/runtime_kernel/broker.py` or `buddyswitch/manifest.toml` is absent.
- 无效状态：`RWH-SPARSE-005` covers dirty unmanaged full worktree; existing invalid/missing worktree open tests keep blocking behavior for non-worktree paths.
- 重复操作：Opening the same repaired instance twice must keep sparse list unchanged and must not duplicate local excludes; extend `RWH-SPARSE-004` or add a second open assertion if local excludes duplicate.
- 并发或顺序敏感行为：Launcher tests use runtime lock path through existing start/open flows; `RWH-RUNTIME-001` proves broker starts after workspace preparation.
- 空输入、空集合、空记录：Existing `instance open missing record`, `unknown buddy`, and env profile validation tests remain in `tests/test_buddyswitch_launcher.py` and `tests/test_buddy_env_profiles.py`; this task does not change their product meaning.
- 权限异常：`RWH-PERM-001` to `RWH-PERM-005` cover missing broad read, stale source deny, PM project read-only, dev project write, broker socket allowlist, and temp-root filtering.
- 路径异常：`RWH-SPARSE-005` rejects unmanaged source edits; `RWH-PERM-004` denies stale source paths; existing workspace path safety tests cover workspace outside shared root and unsafe symlink reset/delete behavior.
- 外部依赖异常：Real Codex sandbox enforcement remains manual because fake Codex cannot enforce filesystem permissions; automated proof is generated config plus absent runtime files.

## 6. 作弊防护

- Workspace shape tests assert both positive and negative paths. An implementation cannot pass by only installing `.agents/skills`; it must also remove source skills, tools, tests, docs, root README, and launcher executable from the runtime workspace.
- Sparse tests assert `git sparse-checkout list` exact equality, not just absence of one leaked file.
- Skill tests use PM and design with different expected active skills, preventing hardcoded "remove all prototype skill" behavior.
- Permission tests parse TOML and assert exact read/write/none entries, not substrings in config text.
- Project access tests compare PM and dev profiles, preventing a blanket project read-only or blanket project write policy.
- Runtime command smoke runs real Python commands through the runtime broker/client from the runtime cwd, preventing tests that only inspect copied files.
- Migration tests create real existing full worktrees and real buddybox files, preventing a helper-only implementation that never repairs `instance open`.
- Negative unmanaged-change test asserts the source edit remains after failure, preventing silent deletion.
- Manual real Codex smoke attempts denied reads/writes after automated proof, covering the external sandbox layer that fake Codex cannot enforce.

## 7. 验证命令清单

Focused sparse workspace tests:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_execution_workspace_is_sparse_runtime_surface -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_design_runtime_skill_exists_without_source_skill_tree -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_narrows_existing_full_execution_worktree_and_preserves_active_buddybox -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_rejects_unmanaged_source_changes_before_sparse_narrowing -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_local_excludes_cover_generated_runtime_paths -q
```

Focused permission tests:

```bash
python3 -m pytest tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_non_dev_permission_profile_keeps_workspace_read_only_and_writes_only_safe_roots -q
python3 -m pytest tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_dev_permission_profile_includes_project_workspace_but_keeps_state_read_only -q
python3 -m pytest tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_permission_profile_denies_stale_runtime_source_surfaces -q
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_permission_profile_does_not_grant_pm_project_or_design_sandbox_writes -q
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_permission_profile_keeps_dev_project_write_and_runtime_reads -q
```

Focused runtime command tests:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_pm_runtime_commands_work_after_sparse_execution_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_broker_starts_from_sparse_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_no_runtime_test_depends_on_source_dirs_inside_instance_workspace -q
```

Broader verification:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py tests/test_runtime_broker.py tests/test_runtime_skills.py tests/test_runtime_agents.py tests/test_search_env_tool.py -q
python3 -m pytest tests/test_runless_runtime_contract.py tests/test_host_decision_surface_product_mode.py tests/test_repo_consistency.py -q
```

Final grep and status verification:

```bash
rg -n '"/" = "read"|workspace.*full repository|full repo' tools scripts tests README.md AGENTS.md framework buddyswitch
rg -n 'buddyswitch/skills/design/shape-prototype|tools/launcher/assets/buddies|docs/|tests/' tools/launcher/assets/buddies framework/contracts README.md AGENTS.md
git status --short --branch
```

Expected final grep handling:

- `"/" = "read"` must not appear in product-mode expected config assertions or generated profile renderer.
- Source skill paths may appear in manifest source definitions and runtime skill source-copy tests, but active runtime guidance must not tell buddies to inspect those paths inside product-mode workspace.

Final manual smoke command when local Codex credentials are available:

```bash
./buddyswitch-codex instance start --buddy pm -- debug prompt-input "runtime boundary smoke"
```

Inside the launched PM workspace, run the manual checks from section 3 and record denied write/read outcomes in the implementation summary.

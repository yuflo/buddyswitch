# Framework Docs Cleanup Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan phase-by-phase. This plan is scoped to `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`.

**Goal:** Remove `framework/docs/` from the active BuddySwitch documentation and test surface, move only still-actionable runtime rules into their canonical owners, and delete the stale prose-doc layer without compatibility remnants.

**Architecture:** The final system keeps runtime truth in code, JSON contracts, role contracts, active skills, root guidance, and tests. It does not create a replacement framework-doc hierarchy, redirect file, archive copy, or long-lived dual path.

**Tech Stack:** Python runtime services and tests, Markdown project guidance and skill packages, JSON framework contracts, pytest/unittest verification, ripgrep active-surface gates.

---

## 1. 任务目标

完成后，BuddySwitch 的 runtime、skill、README、AGENTS 和测试不再依赖 `framework/docs/` 作为活动契约层；`framework/docs/` 整个目录被删除，仍有效的运行规则留在更强的 owner 中。当前核心瓶颈是 `framework/docs/` 已成为第二套 prose contract，README、skill 文件和测试仍读取或链接它，导致 runtime 规则可能在代码、JSON contract、skill 文案和 prose docs 之间漂移。

## 2. 需求提取

- `REQ-001`：删除 `framework/docs/` 作为 active documentation layer。
- `REQ-002`：不保留 `framework/docs/README.md` redirect、空目录、archive copy、`legacy-docs/`、replacement framework-doc hierarchy 或 dual documentation path。
- `REQ-003`：只把仍 actionable 的规则移动到 owning source，不把旧长文档复制到新的 prose mirror。
- `REQ-004`：`README.md` 移除 `Architecture Docs` 中对 `framework/docs/*.md` 的链接，并改为指向 canonical runtime sources。
- `REQ-005`：root `AGENTS.md` 保持短规则，只在需要时增加 env-tool runtime state boundary 和 canonical contract owner 说明。
- `REQ-006`：active skills 删除对 `framework/docs/browser-cockpit.md` 和 `framework/docs/skill-runtime-shared-rules.md` 的引用。
- `REQ-007`：market skills 保留 browser-native research 行为：`search.open-browser` entry、`chrome-devtools-cockpit` executor、headed `instance-browser` profile、mandatory takeover、no silent degrade、no silent API/snippet/crawler fallback、artifact-scoped evidence。
- `REQ-008`：active skills 的 durable output 文案从 stale `task/artifact/run objects` 和 `current buddy run` 改为 runless `task/artifact/handoff` product objects 与 active buddy private buddybox files。
- `REQ-009`：`scripts/skill_creator_importer.py::_append_buddyswitch_rules()` 生成 current runless closing rules，不再生成 `current buddy run`、`Do not call persist`、`persist one buddy run commit` 语句。
- `REQ-010`：`tests/test_skill_creator_importer.py` 和 `tests/fixtures/community-skills/dev-summary/SKILL.md` 更新为 importer 的 current runless wording，并加入旧 wording 的负向断言。
- `REQ-011`：`tests/test_repo_consistency.py` 不再读取 `framework/docs/turn-runtime-spec.md` 或 `framework/docs/runtime-broker-v2-runbook.md`，改为验证 README canonical pointers 与 runtime broker code owners。
- `REQ-012`：`tests/test_parallel_contracts.py` 不再读取 `framework/docs/interface-spec.md`，改为验证 `framework/contracts/workspace-projection.json` 是 console projection source of truth，并由 README 指向该 contract。
- `REQ-013`：新增或更新 consistency gate，active surfaces 不再引用 `framework/docs` 或 11 个 retired doc 文件名；历史 `docs/memo/**` 和旧 `docs/spec/**` 不属于本次清理范围。
- `REQ-014`：如果测试需要写 retired token 作为负向断言，必须拆分字符串，例如 `"framework/" + "docs"` 或 `"buddy " + "run"`，保证最终 grep gate 不被测试自身污染。
- `REQ-015`：删除 `framework/docs/` 下 11 个文件：`architecture-overview.md`、`artifacts-runs-git-policy.md`、`browser-cockpit.md`、`buddyswitch-development-constitution.md`、`interface-spec.md`、`multi-codex-worktree-guide.md`、`runtime-broker-v2-runbook.md`、`skill-architecture-best-practices.md`、`skill-runtime-shared-rules.md`、`track-registry.md`、`turn-runtime-spec.md`。
- `REQ-016`：测试/runtime contract assertions 必须指向 code、JSON contracts、role contracts、README pointers 或 runtime behavior，不能依赖 deleted prose docs 中的词。
- `REQ-017`：最终 active-surface grep 对 doc path tokens 和 stale run/persist/buddy-run wording 无命中，排除 `docs/**` 历史档案。
- `REQ-018`：focused tests `tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py` 通过。
- `REQ-019`：full `python3 -m pytest -q` 通过。
- `REQ-020`：不 redesign runtime behavior、env tools、launcher behavior、JSON object shapes、workspace projection shapes 或 `framework/agent-registry.md`。
- `REQ-021`：market browser rules 的 role boundary 继续由 `framework/contracts/market.md` 承载；不为 browser cockpit 创建新的 shared prose doc。
- `REQ-022`：实施必须在 `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` 完成，不污染 main checkout。

## 3. 现状探索摘要

### 关键目录、文件、测试、运行命令

- `docs/memo/2026-05-15-framework-docs-cleanup-review-memo.md`：本任务需求来源，状态显示为已修改，实施时读取但不回退。
- `AGENTS.md`：SHARP、testing-bound、direct replacement over wrappers、no verification no done；当前列出 runtime state paths，但 root 层还缺少明确 “use env tools; do not edit runtime state directly” 短规则。
- `README.md`：`Architecture Docs` section 仍指向 `framework/docs/architecture-overview.md`、`turn-runtime-spec.md`、`skill-runtime-shared-rules.md`、`track-registry.md`、`interface-spec.md`。
- `framework/docs/`：存在 11 个 active prose docs，全部应删除。
- `buddyswitch/skills/market/{channel-discovery,customer-discovery,launch-prep,pmf-recon,positioning-copy,research-scan}/SKILL.md`：引用 `framework/docs/browser-cockpit.md` 和 `framework/docs/skill-runtime-shared-rules.md`，并包含 `task/artifact/run objects`、`current buddy run`。
- `buddyswitch/skills/{design/shape-prototype,dev/implement-task,dev/skill-creator-importer,pm/write-prd,test/smoke-test}/SKILL.md`：引用 `framework/docs/skill-runtime-shared-rules.md` 或包含 `current buddy run`。
- `scripts/skill_creator_importer.py::_append_buddyswitch_rules()`：追加旧 closing rules，包含 `current buddy run`、`Do not call persist`、`persist one buddy run commit`。
- `tests/fixtures/community-skills/dev-summary/SKILL.md`：fixture 包含旧 run/persist wording。
- `tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy`：断言 importer 生成旧 wording。
- `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_docs_teach_runless_flow`：读取 `framework/docs/turn-runtime-spec.md`。
- `tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_runbook_is_runless`：读取 `framework/docs/runtime-broker-v2-runbook.md`。
- `tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_docs_point_to_workspace_projection_contract`：读取 `framework/docs/interface-spec.md`。
- `framework/contracts/workspace-projection.json`：console projection 的 machine-checkable source of truth，当前已覆盖 buddies/tracks/tasks/artifacts/handoffs。
- `framework/contracts/{pm,design,dev,market,test}.md`：role-specific runtime boundaries；`market.md` 已包含 artifact-scoped evidence 和 browser-native entry。
- `scripts/env/tools/contracts.py::TOOL_REGISTRY`、`env_tools_description()`、`operation_semantics()`：env tool contract owner。
- `scripts/env/tools/semantics.py`：env tool semantics owner。
- `scripts/runtime_kernel/protocol.py::PROTOCOL`、`make_request()`、`validate_request()`、`success_response()`、`error_response()`：runtime broker protocol owner。
- `scripts/runtime_kernel/dispatcher.py::dispatch_runtime_request()`：broker method owner for `env.tool`、`ping`、`status`。
- `scripts/turn_runtime.py::_build_env_tools_desc()`、`_runtime_status_payload()`：runtime status exposes tool catalog from contracts。
- Baseline reference scan:

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

- Baseline stale wording scan:

```bash
rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

- Focused baseline verification from memo:

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
```

- Full baseline verification from memo:

```bash
python3 -m pytest -q
```

### 保留、替换、删除、迁移

- 保留：runless runtime model、broker methods `env.tool` / `ping` / `status`、env tool registry、runtime tool semantics、workspace projection JSON contract、role contracts。
- 保留：market browser-native behavior and `framework/contracts/market.md` role boundary。
- 保留：historical `docs/memo/**` 和旧 `docs/spec/**` references，不在本任务内改写。
- 替换：README `Architecture Docs` list 替换为 concise `Canonical Runtime Sources` list。
- 替换：tests that read prose docs 替换为 tests against README pointers, runtime code, JSON contracts, and active-surface scans。
- 替换：active skill shared runtime prose 从 framework-doc link + buddy-run wording 替换为 inline runless env-tool/output rules。
- 替换：importer-generated closing rules 从 buddy-run/persist wording 替换为 runless explicit durable-write wording。
- 删除：`framework/docs/` directory and its 11 files。
- 不迁移：不把旧 docs 移动到 archive path，不创建 replacement docs hierarchy，不保留 empty folder。

## 4. 最终目标架构

### 最终文件结构和职责

- Modify `README.md`
  - Remove `## Architecture Docs`.
  - Add `## Canonical Runtime Sources`.
  - List code owners: `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`, `scripts/runtime_kernel/protocol.py`, `scripts/runtime_kernel/dispatcher.py`.
  - List machine/role contract owners: `framework/contracts/prepare-turn-context.json`, `framework/contracts/workspace-projection.json`, `framework/contracts/{pm,design,dev,market,test}.md`.
  - Keep Quick Start, Product Runtime Loop, Workspace Layout, Context Panel, and Manage Instances concise.

- Modify `AGENTS.md`
  - Keep SHARP/testing-bound guidance intact.
  - Add one short runtime-state boundary under BuddySwitch Context or Verification-adjacent guidance: product-mode runtime state must be changed through env tools; do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
  - Add one short source-of-truth sentence: runtime contracts are owned by code, JSON contracts, role contracts, and tests; do not create prose mirrors.

- Modify `tests/test_repo_consistency.py`
  - Replace `test_active_docs_teach_runless_flow()` with `test_readme_points_to_canonical_runtime_sources()`.
  - Replace `test_runtime_broker_runbook_is_runless()` with `test_runtime_broker_methods_are_owned_by_runtime_code()`.
  - Add `test_active_surfaces_do_not_reference_retired_framework_docs()`.
  - Add `test_active_skill_runtime_wording_is_runless()`.
  - Use split retired strings for negative scans:
    - `_RETIRED_FRAMEWORK_DOCS = "framework/" + "docs"`
    - `_RETIRED_BUDDY_RUN = "buddy " + "run"`
    - `_RETIRED_CURRENT_BUDDY_RUN = "current buddy " + "run"`
    - `_RETIRED_PERSIST_ONE_BUDDY_RUN = "persist one buddy " + "run"`
  - Scan active scopes: `README.md`, `AGENTS.md`, `tests`, `scripts`, `buddyswitch`, `framework`, `tools`, with `-g '!docs/**'`.

- Modify `tests/test_parallel_contracts.py`
  - Replace `test_docs_point_to_workspace_projection_contract()` with `test_readme_points_to_workspace_projection_contract()`.
  - The test reads `README.md` and `framework/contracts/workspace-projection.json`, never `framework/docs/interface-spec.md`.

- Modify `tests/test_skill_creator_importer.py`
  - Update `test_imports_codex_skill_package_and_registers_target_buddy()` expected generated text:
    - includes `## BuddySwitch Runtime Closing Rules`
    - includes target buddy line
    - includes `Runtime execution uses env.tool through python3 scripts/env/client.py ...`
    - includes explicit durable writes to `task`, `artifact`, `handoff`, and active buddy private buddybox files
    - excludes split old strings for `current buddy run`, `Do not call persist`, `persist one buddy run commit`
  - Keep existing safety checks for rejected import writes and manifest registration.

- Modify `tests/fixtures/community-skills/dev-summary/SKILL.md`
  - Replace old fixture body with runless wording that does not contain `buddy run`, `persist`, or framework-doc links.

- Modify `scripts/skill_creator_importer.py`
  - Update `_append_buddyswitch_rules(skill_md: Path, *, buddy_id: str) -> None`.
  - Generated section remains `## BuddySwitch Runtime Closing Rules`.
  - Generated rules:
    - `Target BuddySwitch buddy: <buddy_id>.`
    - `Runtime execution uses env.tool through python3 scripts/env/client.py ... .`
    - `Product-readable durable state is written explicitly as task, artifact, or handoff objects.`
    - `Use buddyswitch/local/buddybox/<active-buddy>/** only for active buddy private local working files.`
    - `Return after required explicit durable writes are complete.`
  - Do not add new importer modes or compatibility flags.

- Modify market skill files:
  - `buddyswitch/skills/market/channel-discovery/SKILL.md`
  - `buddyswitch/skills/market/customer-discovery/SKILL.md`
  - `buddyswitch/skills/market/launch-prep/SKILL.md`
  - `buddyswitch/skills/market/pmf-recon/SKILL.md`
  - `buddyswitch/skills/market/positioning-copy/SKILL.md`
  - `buddyswitch/skills/market/research-scan/SKILL.md`
  - Each file keeps its skill-specific purpose, use cases, verification, output kind, and artifact content schema.
  - Each file removes framework-doc links and replaces stale output wording with runless product-object wording.
  - Each file keeps market browser runtime constraints inline, without creating a shared replacement doc.

- Modify non-market skill files:
  - `buddyswitch/skills/design/shape-prototype/SKILL.md`
  - `buddyswitch/skills/dev/implement-task/SKILL.md`
  - `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
  - `buddyswitch/skills/pm/write-prd/SKILL.md`
  - `buddyswitch/skills/test/smoke-test/SKILL.md`
  - Each file removes framework-doc links and replaces stale shared runtime wording with inline runless env-tool/output rules.

- Delete `framework/docs/architecture-overview.md`
- Delete `framework/docs/artifacts-runs-git-policy.md`
- Delete `framework/docs/browser-cockpit.md`
- Delete `framework/docs/buddyswitch-development-constitution.md`
- Delete `framework/docs/interface-spec.md`
- Delete `framework/docs/multi-codex-worktree-guide.md`
- Delete `framework/docs/runtime-broker-v2-runbook.md`
- Delete `framework/docs/skill-architecture-best-practices.md`
- Delete `framework/docs/skill-runtime-shared-rules.md`
- Delete `framework/docs/track-registry.md`
- Delete `framework/docs/turn-runtime-spec.md`

### 核心数据模型、接口、函数 / 类边界、调用流

- No new data model is introduced.
- Runtime tool catalog owner:
  - `scripts/env/tools/contracts.py::TOOL_REGISTRY`
  - `scripts/env/tools/contracts.py::env_tools_description()`
  - `scripts/env/tools/contracts.py::operation_semantics()`
  - `scripts/env/tools/semantics.py::capability_semantics()`
  - `scripts/env/tools/semantics.py::action_semantics()`
- Runtime broker owner:
  - `scripts/runtime_kernel/protocol.py::PROTOCOL`
  - `scripts/runtime_kernel/protocol.py::make_request()`
  - `scripts/runtime_kernel/protocol.py::validate_request()`
  - `scripts/runtime_kernel/dispatcher.py::dispatch_runtime_request()`
  - Supported methods remain `env.tool`, `ping`, `status`.
- Runtime status call flow:
  - `python3 scripts/turn_runtime.py status`
  - `scripts/turn_runtime.py::_runtime_status_payload()`
  - `scripts/turn_runtime.py::_build_env_tools_desc()`
  - `scripts/env/tools/contracts.py::env_tools_description()`
- Console projection call flow:
  - `python3 scripts/serve_context_panel.py`
  - `workspace_data.build_workspace_data()`
  - `scripts/runtime_store/projections.py::build_workspace_projection()`
  - `framework/contracts/workspace-projection.json` defines shape and invariants.
- Skill runtime guidance flow:
  - `buddyswitch/skills/**/SKILL.md` carries skill-specific runtime rules.
  - Skills call `python3 scripts/env/client.py ...` for durable operations.
  - Market skills start browser-native research through `python3 scripts/env/client.py search open-browser ...` and use `chrome-devtools-cockpit`.
- Imported skill flow:
  - `scripts/skill_creator_importer.py::import_skill()`
  - `_copy_source_package()`
  - `_append_buddyswitch_rules()`
  - manifest serialization through `_serialize_manifest()`.

### 旧路径和旧逻辑删除清单

- Delete `framework/docs/` and every file under it.
- Remove README active references to `framework/docs/*.md`.
- Remove active skill links to `framework/docs/browser-cockpit.md`.
- Remove active skill links to `framework/docs/skill-runtime-shared-rules.md`.
- Remove tests that read any `framework/docs/*.md` file.
- Remove generated and fixture wording that mentions a current buddy-run commit or skill-level persist behavior.

## 5. 分阶段实施计划

### 阶段 A：建立失败的 contract tests 和 active-surface gates

**目标**

把删除 `framework/docs/` 的期望先写入测试，使当前 repo 在还未修改 active surfaces 时暴露明确失败点。

**具体文件变更**

- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_parallel_contracts.py`
- Modify `tests/test_skill_creator_importer.py`
- Modify `tests/fixtures/community-skills/dev-summary/SKILL.md`

**详细步骤**

1. 在 `tests/test_repo_consistency.py` 顶部 retired constants 附近加入 split-string constants：
   - `_RETIRED_FRAMEWORK_DOCS = "framework/" + "docs"`
   - `_RETIRED_BUDDY_RUN = "buddy " + "run"`
   - `_RETIRED_CURRENT_BUDDY_RUN = "current buddy " + "run"`
   - `_RETIRED_PERSIST_ONE_BUDDY_RUN = "persist one buddy " + "run"`
   - `_RETIRED_DOC_FILENAMES = (...)`，包含 11 个 retired doc basenames，且每个 basename 都用 split strings 组成，例如 `"architecture-" + "overview.md"`、`"turn-runtime-" + "spec.md"`、`"browser-" + "cockpit.md"`，避免测试文件自身污染最终 grep gate。
2. 将 `test_active_docs_teach_runless_flow()` 改名并重写为 `test_readme_points_to_canonical_runtime_sources()`：
   - Read `README.md`.
   - Assert lowercased README includes `runless`, `env.tool`, `context discovery`.
   - Assert README includes canonical source paths:
     - `scripts/env/tools/contracts.py`
     - `scripts/env/tools/semantics.py`
     - `scripts/runtime_kernel/protocol.py`
     - `scripts/runtime_kernel/dispatcher.py`
     - `framework/contracts/prepare-turn-context.json`
     - `framework/contracts/workspace-projection.json`
     - `framework/contracts/{pm,design,dev,market,test}.md`
   - Assert README does not include `_RETIRED_FRAMEWORK_DOCS`.
   - Assert README does not include `Architecture Docs`.
3. 将 `test_runtime_broker_runbook_is_runless()` 改名并重写为 `test_runtime_broker_methods_are_owned_by_runtime_code()`：
   - Import or read `scripts/runtime_kernel/protocol.py` and `scripts/runtime_kernel/dispatcher.py`.
   - Assert `protocol.PROTOCOL == "buddyswitch-runtime-broker/v2"`.
   - Assert dispatcher source includes `if method == "env.tool"`, `if method == "ping"`, `if method == "status"`.
   - Assert dispatcher unsupported-method guidance includes `Use supported runtime methods: env.tool, ping, status.`
   - Assert neither file contains `prepare\`` or `persist\`` retry-policy prose.
4. Add `test_active_surfaces_do_not_reference_retired_framework_docs()`:
   - Build regex from split `framework/docs` and split retired filenames.
   - Run `rg -n <pattern> README.md AGENTS.md tests scripts buddyswitch framework tools -g !docs/**`.
   - Assert return code is `0` or `1`.
   - Assert no hits.
5. Add `test_active_skill_runtime_wording_is_runless()`:
   - Iterate all active skill files under `buddyswitch/skills/**/SKILL.md`.
   - Assert no skill text contains `_RETIRED_FRAMEWORK_DOCS`, `_RETIRED_CURRENT_BUDDY_RUN`, `_RETIRED_PERSIST_ONE_BUDDY_RUN`, `Do not call persist`, or `task/artifact/run objects`.
   - For non-shared active role skills listed in this plan, assert text contains `Write durable outputs explicitly via env tools`.
   - For market skills, assert text contains `chrome-devtools-cockpit`, `search.open_browser`, `mandatory takeover`, `no silent degrade`, and `artifact` evidence wording.
6. In `tests/test_parallel_contracts.py`, replace `test_docs_point_to_workspace_projection_contract()` with `test_readme_points_to_workspace_projection_contract()`:
   - Read `README.md`.
   - Load `framework/contracts/workspace-projection.json`.
   - Assert README includes `framework/contracts/workspace-projection.json`.
   - Assert contract `contract_id == "workspace-projection"`.
   - Assert contract top-level keys include `handoffs` and do not include `memories`, `run_audits`, or `content_root`.
7. In `tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy`, replace old positive assertions:
   - Assert generated skill text contains `Runtime execution uses env.tool through`.
   - Assert generated skill text contains `Product-readable durable state is written explicitly as task, artifact, or handoff objects`.
   - Assert generated skill text contains `active buddy private local working files`.
   - Assert generated skill text excludes split `_RETIRED_CURRENT_BUDDY_RUN`, `Do not call persist`, and split `_RETIRED_PERSIST_ONE_BUDDY_RUN`.
8. In `tests/fixtures/community-skills/dev-summary/SKILL.md`, replace stale body with:
   - `Summarize code changes, verification evidence, and handoff risks for runless BuddySwitch execution.`
   - `Durable summaries are written through explicit env tools when the importing buddy uses this skill.`

**预期行为变化**

- Focused tests fail before source migration because README, skills, importer, and existing docs still contain retired references.
- Failures point to exact active surfaces rather than deleted prose doc contents.

**对应需求编号**

`REQ-008`, `REQ-009`, `REQ-010`, `REQ-011`, `REQ-012`, `REQ-013`, `REQ-014`, `REQ-016`, `REQ-017`, `REQ-018`

**验证命令**

```bash
python3 -m pytest -q tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_points_to_canonical_runtime_sources tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_methods_are_owned_by_runtime_code tests/test_repo_consistency.py::RepoConsistencyTests::test_active_surfaces_do_not_reference_retired_framework_docs tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_runtime_wording_is_runless tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy
```

**阶段完成标准**

The new or rewritten tests run and fail only because current active surfaces still contain `framework/docs` links, prose-doc reads, or old run/persist wording. Syntax/import errors are fixed in this phase before moving on.

### 阶段 B：更新 README 和 root AGENTS canonical owner guidance

**目标**

把 top-level project guidance 指向 canonical owners，去掉 README 对 `framework/docs` 的 active links，并给 root AGENTS 增加短 runtime state boundary。

**具体文件变更**

- Modify `README.md`
- Modify `AGENTS.md`

**详细步骤**

1. In `README.md`, delete the `## Architecture Docs` section and its five `framework/docs/*.md` bullets.
2. Add `## Canonical Runtime Sources` after `## Manage Instances`.
3. In that section, add concise bullets:
   - `scripts/env/tools/contracts.py` for env tool registry, action payloads, and status/catalog projection.
   - `scripts/env/tools/semantics.py` for machine-readable operation semantics.
   - `scripts/runtime_kernel/protocol.py` for runtime broker protocol envelope.
   - `scripts/runtime_kernel/dispatcher.py` for supported broker methods: `env.tool`, `ping`, `status`.
   - `framework/contracts/prepare-turn-context.json` for context payload contract compatibility.
   - `framework/contracts/workspace-projection.json` for context panel workspace projection shape.
   - `framework/contracts/{pm,design,dev,market,test}.md` for role-specific runtime boundaries.
   - `tests/` for behavior and consistency gates.
4. Keep README concise; do not paste `architecture-overview.md`, `turn-runtime-spec.md`, `track-registry.md`, `interface-spec.md`, or constitution content into README.
5. In `AGENTS.md`, under `## BuddySwitch Context`, add:
   - `Use env tools for product-mode runtime state. Do not edit buddyswitch/objects/** or buddyswitch/local/buddybox/** directly.`
   - `Runtime contracts are owned by code, JSON contracts, role contracts, and tests; do not create prose mirrors for runtime behavior.`
6. Do not change runtime paths, commands, priority ordering, or Done definition in `AGENTS.md`.

**预期行为变化**

- New README tests pass.
- Root guidance no longer sends developers to retired docs.
- Runtime state mutation guidance is explicit at the root without bloating the root instruction file.

**对应需求编号**

`REQ-003`, `REQ-004`, `REQ-005`, `REQ-011`, `REQ-012`, `REQ-020`

**验证命令**

```bash
python3 -m pytest -q tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_points_to_canonical_runtime_sources tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract
```

**阶段完成标准**

Both tests pass, and this scan returns no README/AGENTS hits:

```bash
rg -n "framework/docs|architecture-overview\\.md|turn-runtime-spec\\.md|skill-runtime-shared-rules\\.md|track-registry\\.md|interface-spec\\.md" README.md AGENTS.md
```

### 阶段 C：迁移 active skill runtime wording 和 importer-generated rules

**目标**

让 active skills 和 imported skills carry only the runtime rules they actually need, without framework-doc links or stale buddy-run/persist language.

**具体文件变更**

- Modify `buddyswitch/skills/market/channel-discovery/SKILL.md`
- Modify `buddyswitch/skills/market/customer-discovery/SKILL.md`
- Modify `buddyswitch/skills/market/launch-prep/SKILL.md`
- Modify `buddyswitch/skills/market/pmf-recon/SKILL.md`
- Modify `buddyswitch/skills/market/positioning-copy/SKILL.md`
- Modify `buddyswitch/skills/market/research-scan/SKILL.md`
- Modify `buddyswitch/skills/design/shape-prototype/SKILL.md`
- Modify `buddyswitch/skills/dev/implement-task/SKILL.md`
- Modify `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- Modify `buddyswitch/skills/pm/write-prd/SKILL.md`
- Modify `buddyswitch/skills/test/smoke-test/SKILL.md`
- Modify `scripts/skill_creator_importer.py`

**详细步骤**

1. In every market skill listed above, edit `## Market Research Cockpit Runtime`:
   - Remove `This skill follows framework/docs/browser-cockpit.md`.
   - Keep `It uses chrome-devtools-cockpit as the browser executor.`
   - Keep headed instance cockpit profile wording.
   - Keep `Discovery starts with search.open_browser`.
   - Keep critical-source login mandatory takeover.
   - Keep no silent degrade and no silent API/snippet/crawler fallback.
   - Replace `canonical outputs remain BuddySwitch task/artifact/run objects` with `canonical outputs remain BuddySwitch task, artifact, or handoff objects; buddybox remains active-buddy private local workspace state.`
   - Add or keep artifact-scoped evidence wording: `Market evidence is target-scoped to artifact ids; do not invent evidence tokens.`
2. In every market skill, edit `## Shared Runtime Rules`:
   - Remove the `framework/docs/skill-runtime-shared-rules.md` line.
   - Replace `This native skill contributes content to the current buddy run.`
   - Keep `Do not rely on deprecated prepare/persist flows.`
   - Replace `The locked buddy session returns after explicit durable writes are complete.`
   - Final section must contain these four runless rules:
     - `Runtime execution uses env.tool through python3 scripts/env/client.py ... .`
     - `Product-readable durable state is written explicitly as task, artifact, or handoff objects.`
     - `Use buddyswitch/local/buddybox/<active-buddy>/** only for active buddy private local working files.`
     - `Return after required explicit durable writes are complete.`
3. In each non-market skill listed above, edit `## Shared Runtime Rules` to the same four runless rules and keep any skill-specific guardrail line already present, such as `Do not introduce transcript parsing...` in `dev/skill-creator-importer`.
4. Do not rewrite skill purpose/use-case/output schemas except for the stale runtime-contract wording. Preserve artifact kinds:
   - `channel-plan`
   - `customer-discovery`
   - `launch-prep`
   - `pmf-report`
   - `positioning-brief`
   - `market-scan`
   - `prototype-brief`
   - `implementation-report`
   - `skill-import-report`
   - `prd`
   - `test-report`
5. In `scripts/skill_creator_importer.py::_append_buddyswitch_rules()`, replace `addition` with the runless closing rules defined in the final architecture section.
6. Do not add importer options, migration flags, or dual generated text.

**预期行为变化**

- Active skill files are self-contained for current runtime rules.
- Market skills retain browser-native behavior without relying on `framework/docs/browser-cockpit.md`.
- Newly imported skills no longer reintroduce retired buddy-run/persist wording.

**对应需求编号**

`REQ-003`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `REQ-010`, `REQ-014`, `REQ-017`, `REQ-021`

**验证命令**

```bash
python3 -m pytest -q tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_runtime_wording_is_runless
```

**阶段完成标准**

The two tests pass, and this active skill/importer scan returns no hits:

```bash
rg -n "framework/docs|task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session" buddyswitch/skills scripts/skill_creator_importer.py tests/fixtures/community-skills/dev-summary/SKILL.md
```

### 阶段 D：替换 prose-doc tests 并删除 `framework/docs/`

**目标**

移除最后的 active test dependencies on prose docs，然后删除 `framework/docs/` 目录和 11 个文件，不留下 compatibility remnants。

**具体文件变更**

- Modify `tests/test_repo_consistency.py`
- Modify `tests/test_parallel_contracts.py`
- Delete `framework/docs/architecture-overview.md`
- Delete `framework/docs/artifacts-runs-git-policy.md`
- Delete `framework/docs/browser-cockpit.md`
- Delete `framework/docs/buddyswitch-development-constitution.md`
- Delete `framework/docs/interface-spec.md`
- Delete `framework/docs/multi-codex-worktree-guide.md`
- Delete `framework/docs/runtime-broker-v2-runbook.md`
- Delete `framework/docs/skill-architecture-best-practices.md`
- Delete `framework/docs/skill-runtime-shared-rules.md`
- Delete `framework/docs/track-registry.md`
- Delete `framework/docs/turn-runtime-spec.md`

**详细步骤**

1. Confirm `tests/test_repo_consistency.py` no longer reads any path under `ROOT / "framework" / "docs"`.
2. Confirm `tests/test_parallel_contracts.py` no longer reads any path under `ROOT / "framework" / "docs"`.
3. Confirm all retired tokens in those tests are built from split strings.
4. Delete the 11 `framework/docs/*.md` files.
5. Remove the now-empty `framework/docs/` directory from git if the filesystem still has it.
6. Do not create `framework/docs/README.md`, `.gitkeep`, archive copy, or replacement prose path.
7. Do not edit `docs/memo/**` or old `docs/spec/**` references.
8. Do not touch `framework/agent-registry.md`.

**预期行为变化**

- `framework/docs/` no longer exists in the active repo tree.
- Tests target canonical owners instead of deleted prose.
- Historical documents under `docs/` remain untouched.

**对应需求编号**

`REQ-001`, `REQ-002`, `REQ-011`, `REQ-012`, `REQ-013`, `REQ-014`, `REQ-015`, `REQ-016`, `REQ-020`

**验证命令**

```bash
python3 -m pytest -q tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_methods_are_owned_by_runtime_code tests/test_repo_consistency.py::RepoConsistencyTests::test_active_surfaces_do_not_reference_retired_framework_docs tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_contract_matches_runless_workspace_projection tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract
test ! -e framework/docs
```

**阶段完成标准**

The commands pass. `find framework/docs -maxdepth 1 -type f -print` is not runnable because `framework/docs` does not exist; `test ! -e framework/docs` succeeds.

### 阶段 E：最终 focused verification、full suite 和 grep gates

**目标**

证明完整 cleanup 完成，且未改变 runtime behavior、env tools、launcher behavior 或 JSON object shapes。

**具体文件变更**

- No additional source edits are expected in this phase. If verification fails, return to the responsible phase and fix the concrete owner.

**详细步骤**

1. Run focused tests:

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
```

2. Run full pytest:

```bash
python3 -m pytest -q
```

3. Run active framework-doc reference gate:

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

4. Run active stale wording gate:

```bash
rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

5. Confirm worktree scope:

```bash
pwd
git branch --show-current
git status --short
```

**预期行为变化**

- Focused and full tests pass.
- Both active grep gates return code `1` with no output.
- `git status --short` shows only intended files and deletion of `framework/docs` files.

**对应需求编号**

`REQ-001` through `REQ-022`

**验证命令**

Use the five commands in the detailed steps.

**阶段完成标准**

All tests pass, both grep gates have no active hits, `framework/docs` is absent, and changed paths match this plan.

## 6. 迁移 / 删除策略

- Delete `framework/docs/` only after active README, skill, importer, and test references are removed.
- No redirect file is created because source memo explicitly rejects compatibility retention.
- No archive path is created because historical `docs/memo/**` and `docs/spec/**` can remain as historical records without preserving `framework/docs` as an active surface.
- No dual path is preserved; canonical owners after cleanup are:
  - `README.md`
  - `AGENTS.md`
  - `buddyswitch/skills/**/SKILL.md`
  - `scripts/skill_creator_importer.py`
  - `framework/contracts/*.json`
  - `framework/contracts/{pm,design,dev,market,test}.md`
  - `scripts/env/tools/**`
  - `scripts/runtime_kernel/**`
  - `tests/**`
- Short-term compatibility is not required because there is no external API, irreversible data migration, user data, payment, security, or release-hotfix scope tied to `framework/docs`.
- Historical archive cleanup is explicitly out of scope for this change set.

## 7. 完成定义

The task is complete only when all conditions below are true:

- `framework/docs/` does not exist.
- `README.md`, `AGENTS.md`, active code, active tests, active skills, and launcher/tool surfaces do not reference `framework/docs` or retired framework-doc filenames.
- Active skills are self-contained for current runless runtime rules and market skills retain browser-native evidence constraints.
- `scripts/skill_creator_importer.py::_append_buddyswitch_rules()` generates current runless closing rules.
- `tests/test_repo_consistency.py`, `tests/test_parallel_contracts.py`, and `tests/test_skill_creator_importer.py` assert canonical owners and no active retired references.
- Focused verification passes:

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
```

- Full verification passes:

```bash
python3 -m pytest -q
```

- Active grep gates return no hits:

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

- `git status --short` shows intended modifications and deleted framework docs only; no main checkout paths are touched.

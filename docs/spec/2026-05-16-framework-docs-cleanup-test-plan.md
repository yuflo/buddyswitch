# Framework Docs Cleanup Test Plan

## 1. 测试设计原则

- 测试从源 memo 的功能需求、用户工作流、系统不变量和失败模式出发：active runtime guidance must not depend on `framework/docs/`; canonical owners must be README, AGENTS, active skills, importer rules, code, JSON contracts, role contracts, and tests.
- 测试验证外部可观察行为和 repo state：README pointers, AGENTS root rule, skill package text, importer-generated skill text, runtime broker method ownership, workspace projection contract ownership, directory deletion, grep gates, and pytest pass/fail results.
- 测试不根据即将写出的实现细节反推刚好能通过的断言；断言围绕 active surface absence, canonical source presence, generated output text, and deleted path state。
- 测试不保留 prose-doc assertions；任何 test that reads `framework/docs/*.md` is a failure after cleanup。
- 负向测试验证 no active references and no stale wording, not only happy-path README content。
- Retired tokens used in negative assertions are split in test code, including retired doc basenames such as `"turn-runtime-" + "spec.md"`, so grep gates can still detect real regressions in active surfaces。
- Manual checks only cover worktree isolation and command evidence; automated tests and grep gates are required completion gates。

## 2. 需求覆盖矩阵

| Requirement | Coverage |
| --- | --- |
| `REQ-001` | `FDC-DELETE-001`, `FDC-GREP-DOCS-001`, `FDC-FOCUSED-001` |
| `REQ-002` | `FDC-DELETE-001`, `FDC-GREP-DOCS-001` |
| `REQ-003` | `FDC-README-001`, `FDC-AGENTS-001`, `FDC-SKILL-001` |
| `REQ-004` | `FDC-README-001`, `FDC-GREP-DOCS-001` |
| `REQ-005` | `FDC-AGENTS-001` |
| `REQ-006` | `FDC-SKILL-001`, `FDC-GREP-DOCS-001` |
| `REQ-007` | `FDC-MARKET-001`, `FDC-MARKET-ROLE-001` |
| `REQ-008` | `FDC-SKILL-001`, `FDC-GREP-WORDS-001` |
| `REQ-009` | `FDC-IMPORTER-001`, `FDC-GREP-WORDS-001` |
| `REQ-010` | `FDC-IMPORTER-001`, `FDC-FIXTURE-001` |
| `REQ-011` | `FDC-README-001`, `FDC-BROKER-001` |
| `REQ-012` | `FDC-PROJECTION-001` |
| `REQ-013` | `FDC-GREP-DOCS-001` |
| `REQ-014` | `FDC-GREP-DOCS-001`, `FDC-GREP-WORDS-001`, `FDC-IMPORTER-001` |
| `REQ-015` | `FDC-DELETE-001` |
| `REQ-016` | `FDC-BROKER-001`, `FDC-PROJECTION-001`, `FDC-README-001` |
| `REQ-017` | `FDC-GREP-DOCS-001`, `FDC-GREP-WORDS-001` |
| `REQ-018` | `FDC-FOCUSED-001` |
| `REQ-019` | `FDC-FULL-001` |
| `REQ-020` | `FDC-BROKER-001`, `FDC-PROJECTION-001`, `FDC-FULL-001` |
| `REQ-021` | `FDC-MARKET-001`, `FDC-MARKET-ROLE-001` |
| `REQ-022` | `FDC-WORKTREE-001` |

All requirements are suitable for automated testing except `REQ-022`, which is a worktree execution constraint verified by command evidence before and after implementation. Manual launcher smoke is not required because this task changes active docs/tests/skills, not launcher runtime behavior.

## 3. 测试分层

### 单元测试

Purpose: prove source-of-truth assertions no longer depend on deleted prose files and importer-generated wording is current.

Coverage:

- `tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_points_to_canonical_runtime_sources`
- `tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_methods_are_owned_by_runtime_code`
- `tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract`
- `tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy`

Command:

```bash
python3 -m pytest -q tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_points_to_canonical_runtime_sources tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_methods_are_owned_by_runtime_code tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy
```

### 集成测试

Purpose: prove active repo surfaces and generated/imported skill packages remain coherent together.

Coverage:

- `tests/test_repo_consistency.py`
- `tests/test_parallel_contracts.py`
- `tests/test_skill_creator_importer.py`
- `scripts/skill_creator_importer.py`
- `buddyswitch/skills/**/SKILL.md`
- `README.md`
- `AGENTS.md`

Command:

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
```

### CLI、API、UI 或主路径运行测试

Purpose: verify repository-level command outputs and active-surface scans that a developer will run before completion.

Coverage:

- `test ! -e framework/docs`
- active `rg` gates
- full pytest
- worktree path and branch

Commands:

```bash
test ! -e framework/docs
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
pwd
git branch --show-current
git status --short
```

Expected for both `rg` gates: exit code `1` and empty stdout. Expected for `pwd`: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`. Expected for branch: `dev_buddy_mem`.

### 回归测试

Purpose: prove cleanup did not alter runtime behavior, env tool contracts, workspace projection shapes, launcher behavior, or unrelated tests.

Coverage:

- Full test suite.
- Existing env tool, runtime, launcher, context panel, projection, manifest, and skill importer tests.

Command:

```bash
python3 -m pytest -q
```

### 手动验证

Purpose: confirm execution location and review changed path scope.

Steps:

1. Run `pwd` and confirm `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`.
2. Run `git branch --show-current` and confirm `dev_buddy_mem`.
3. Run `git status --short` and confirm changed paths are limited to README/AGENTS/tests/active skills/importer/fixture and deleted `framework/docs` files.
4. Confirm no main checkout path is referenced in command output.

## 4. 详细测试用例

### `FDC-WORKTREE-001`: worktree execution guard

- 覆盖需求：`REQ-022`
- 用户 / 系统场景：Implementation must run in `dev_buddy_mem`, not main.
- 前置条件：Repository checkout exists.
- 输入：`pwd`, `git branch --show-current`, `git status --short`.
- 预期输出或状态变化：cwd is `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`; branch is `dev_buddy_mem`; status contains only intended cleanup paths.
- 断言重点：Command evidence proves execution did not occur in main checkout.
- 测试类型：manual command guard.
- 建议测试文件路径和测试名称：No automated file; required preflight and final command evidence.

### `FDC-README-001`: README points to canonical runtime sources

- 覆盖需求：`REQ-003`, `REQ-004`, `REQ-011`, `REQ-016`
- 用户 / 系统场景：A developer opens README and finds current owners instead of retired prose docs.
- 前置条件：`README.md` exists.
- 输入：Contents of `README.md`.
- 预期输出或状态变化：README contains `runless`, `env.tool`, `context discovery`, `scripts/env/tools/contracts.py`, `scripts/env/tools/semantics.py`, `scripts/runtime_kernel/protocol.py`, `scripts/runtime_kernel/dispatcher.py`, `framework/contracts/prepare-turn-context.json`, `framework/contracts/workspace-projection.json`, and `framework/contracts/{pm,design,dev,market,test}.md`; README excludes `Architecture Docs` and split `framework/docs`.
- 断言重点：Presence of canonical owners and absence of retired links.
- 测试类型：unit/source contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_points_to_canonical_runtime_sources`.

### `FDC-AGENTS-001`: root AGENTS keeps concise runtime-state boundary

- 覆盖需求：`REQ-003`, `REQ-005`
- 用户 / 系统场景：A coding agent reads root guidance and knows to use env tools for product-mode runtime state.
- 前置条件：`AGENTS.md` exists.
- 输入：Contents of `AGENTS.md`.
- 预期输出或状态变化：AGENTS includes `Use env tools for product-mode runtime state`, includes `Do not edit buddyswitch/objects/** or buddyswitch/local/buddybox/** directly`, includes source-of-truth wording for code/JSON contracts/role contracts/tests, and excludes split `framework/docs`.
- 断言重点：Root guidance stays short and executable; no copied long architecture doc.
- 测试类型：unit/source contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_root_agents_names_runtime_state_boundary`.

### `FDC-BROKER-001`: broker methods are code-owned

- 覆盖需求：`REQ-011`, `REQ-016`, `REQ-020`
- 用户 / 系统场景：Repo consistency verifies broker methods without reading `runtime-broker-v2-runbook.md`.
- 前置条件：`scripts/runtime_kernel/protocol.py` and `scripts/runtime_kernel/dispatcher.py` import successfully.
- 输入：`protocol.PROTOCOL`, dispatcher source or callable behavior for supported methods.
- 预期输出或状态变化：Protocol is `buddyswitch-runtime-broker/v2`; dispatcher supports `env.tool`, `ping`, and `status`; unsupported method guidance names those three methods.
- 断言重点：No `framework/docs` file is read; broker method owner is code.
- 测试类型：unit/source contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_methods_are_owned_by_runtime_code`.

### `FDC-PROJECTION-001`: workspace projection source of truth is JSON contract

- 覆盖需求：`REQ-012`, `REQ-016`, `REQ-020`
- 用户 / 系统场景：Context panel projection contract is discoverable without `interface-spec.md`.
- 前置条件：`framework/contracts/workspace-projection.json` exists.
- 输入：README text and JSON contract payload.
- 预期输出或状态变化：README references `framework/contracts/workspace-projection.json`; contract `contract_id` is `workspace-projection`; projection contract includes current runless top-level keys and excludes retired keys.
- 断言重点：Test reads JSON contract and README, not deleted prose doc.
- 测试类型：unit/source contract plus existing projection integration.
- 建议测试文件路径和测试名称：`tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract`.

### `FDC-SKILL-001`: active skills are self-contained and runless

- 覆盖需求：`REQ-003`, `REQ-006`, `REQ-008`, `REQ-017`
- 用户 / 系统场景：A buddy skill can be used without framework-doc links and without stale run/persist output semantics.
- 前置条件：Active skill files exist under `buddyswitch/skills/**/SKILL.md`.
- 输入：Contents of active role skill files.
- 预期输出或状态变化：No active skill contains split `framework/docs`, `task/artifact/run objects`, split `current buddy run`, split `persist one buddy run`, `Do not call persist`, or `locked buddy session`; role skills contain explicit env-tool durable output guidance.
- 断言重点：Scan covers all active skills, not a single sample file.
- 测试类型：source contract / regression.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_runtime_wording_is_runless`.

### `FDC-MARKET-001`: market skills preserve browser-native rules

- 覆盖需求：`REQ-007`, `REQ-021`
- 用户 / 系统场景：Market research skills still require browser-native execution after removing `browser-cockpit.md`.
- 前置条件：Six market skill files exist.
- 输入：Contents of:
  - `buddyswitch/skills/market/channel-discovery/SKILL.md`
  - `buddyswitch/skills/market/customer-discovery/SKILL.md`
  - `buddyswitch/skills/market/launch-prep/SKILL.md`
  - `buddyswitch/skills/market/pmf-recon/SKILL.md`
  - `buddyswitch/skills/market/positioning-copy/SKILL.md`
  - `buddyswitch/skills/market/research-scan/SKILL.md`
- 预期输出或状态变化：Each file contains `chrome-devtools-cockpit`, headed `instance-browser`, `search.open_browser`, mandatory takeover, no silent degrade, no silent API/snippet/crawler fallback, and artifact-scoped evidence guidance; each file excludes `framework/docs/browser-cockpit.md`.
- 断言重点：Preserves actual market behavior while removing stale shared doc dependency.
- 测试类型：source contract / regression.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_market_skills_inline_browser_runtime_rules`.

### `FDC-MARKET-ROLE-001`: market role contract remains the browser boundary owner

- 覆盖需求：`REQ-007`, `REQ-021`
- 用户 / 系统场景：Role contract continues to define market runtime boundary after deleting framework browser doc.
- 前置条件：`framework/contracts/market.md` exists.
- 输入：Contents of `framework/contracts/market.md`.
- 预期输出或状态变化：Contains `search open-browser`, `chrome-devtools-cockpit`, `target-scoped evidence`, and artifact/buddybox output boundary; excludes split `framework/docs`.
- 断言重点：Role boundary is retained in the established contract path.
- 测试类型：source contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_market_role_contract_owns_browser_boundary`.

### `FDC-IMPORTER-001`: imported skills receive current runless closing rules

- 覆盖需求：`REQ-009`, `REQ-010`, `REQ-014`
- 用户 / 系统场景：A Codex-native skill imported into BuddySwitch does not reintroduce retired buddy-run/persist wording.
- 前置条件：Temporary repo helper in `tests/test_skill_creator_importer.py` creates a source skill.
- 输入：`skill_creator_importer.import_skill(source=source_root, buddy_id="dev", skill_id="dev-summary", repo_root=repo_root)`.
- 预期输出或状态变化：Generated target `SKILL.md` contains `## BuddySwitch Runtime Closing Rules`, target buddy line, env-tool runtime line, explicit task/artifact/handoff durable output line, active buddy private buddybox line, and return-after-explicit-writes line; excludes split old strings.
- 断言重点：Checks generated artifact, not only `_append_buddyswitch_rules()` source text.
- 测试类型：unit/integration.
- 建议测试文件路径和测试名称：`tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy`.

### `FDC-FIXTURE-001`: community skill fixture does not carry stale run wording

- 覆盖需求：`REQ-010`
- 用户 / 系统场景：Fixture data used by importer tests does not keep retired runtime language.
- 前置条件：`tests/fixtures/community-skills/dev-summary/SKILL.md` exists.
- 输入：Fixture text.
- 预期输出或状态变化：Fixture describes runless BuddySwitch execution and explicit env-tool durable summaries; excludes split `buddy run`, `persist`, and `Do not call persist`.
- 断言重点：Fixture cannot hide stale wording by passing through importer unchanged.
- 测试类型：source fixture regression.
- 建议测试文件路径和测试名称：Covered by `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_surfaces_do_not_reference_retired_framework_docs` and `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_runtime_wording_is_runless` if `tests/fixtures` is included in scan.

### `FDC-GREP-DOCS-001`: active surfaces have no retired framework-doc references

- 覆盖需求：`REQ-001`, `REQ-002`, `REQ-004`, `REQ-006`, `REQ-013`, `REQ-014`, `REQ-017`
- 用户 / 系统场景：A stale link to deleted docs would be caught before completion.
- 前置条件：`rg` is available.
- 输入：Active-surface scan over `README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'`.
- 预期输出或状态变化：No hits for `framework/docs`, all 11 retired filenames, `browser-cockpit.md`, `skill-runtime-shared-rules.md`, `turn-runtime-spec.md`, `runtime-broker-v2-runbook.md`, or `interface-spec.md`.
- 断言重点：Detects stale links across active repo, while excluding historical docs. Any retired basename constants inside tests are split strings, not literal filenames.
- 测试类型：source regression / CLI gate.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_surfaces_do_not_reference_retired_framework_docs`.

### `FDC-GREP-WORDS-001`: active surfaces have no stale run/persist skill wording

- 覆盖需求：`REQ-008`, `REQ-009`, `REQ-014`, `REQ-017`
- 用户 / 系统场景：Old buddy-run/persist wording cannot remain in active skill, importer, README, tests, or tools.
- 前置条件：`rg` is available.
- 输入：Active-surface scan over `README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'`.
- 预期输出或状态变化：No hits for `task/artifact/run objects`, split `current buddy run`, split `buddy run`, split `persist one buddy run`, `Do not call persist`, `locked buddy session`, or split `framework/docs`.
- 断言重点：The scan fails if tests contain retired phrases literally; tests must split retired tokens.
- 测试类型：source regression / CLI gate.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_runtime_wording_is_runless` plus final command gate.

### `FDC-DELETE-001`: framework docs directory is absent

- 覆盖需求：`REQ-001`, `REQ-002`, `REQ-015`
- 用户 / 系统场景：The retired docs are actually deleted, not merely unlinked from README.
- 前置条件：Cleanup implementation has run.
- 输入：Filesystem check `test ! -e framework/docs`.
- 预期输出或状态变化：Command exits `0`; no `framework/docs` directory, redirect file, `.gitkeep`, or README remains.
- 断言重点：Catches empty-dir or redirect retention.
- 测试类型：filesystem regression / CLI gate.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_framework_docs_directory_is_removed`.

### `FDC-FOCUSED-001`: focused cleanup suite passes

- 覆盖需求：`REQ-018`
- 用户 / 系统场景：The exact area changed by the cleanup has passing tests.
- 前置条件：Implementation phases complete.
- 输入：`python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py`.
- 预期输出或状态变化：Command exits `0`.
- 断言重点：Focused suite proves docs/contract/importer cleanup before full suite.
- 测试类型：focused verification.
- 建议测试文件路径和测试名称：Command-level completion gate.

### `FDC-FULL-001`: full test suite passes

- 覆盖需求：`REQ-019`, `REQ-020`
- 用户 / 系统场景：Deleting docs and changing active guidance did not break runtime, env tools, launcher, projection, manifest, or importer behavior.
- 前置条件：Focused suite passes.
- 输入：`python3 -m pytest -q`.
- 预期输出或状态变化：Command exits `0`.
- 断言重点：Broad regression coverage for non-goals.
- 测试类型：full regression.
- 建议测试文件路径和测试名称：Command-level completion gate.

## 5. 负向与边界测试

- 缺失数据：`FDC-DELETE-001` asserts `framework/docs` is absent and no tests read missing prose docs.
- 无效状态：`FDC-GREP-DOCS-001` fails if any active file references deleted doc paths.
- 重复操作：Running `test ! -e framework/docs` repeatedly succeeds after deletion; no cleanup command recreates the directory.
- 顺序敏感行为：Phase A tests intentionally fail before README/skill/importer migration; Phase D deletes docs only after prose-doc tests are replaced.
- 空目录边界：`FDC-DELETE-001` rejects an empty `framework/docs` directory.
- 空配置边界：No new config is introduced; existing JSON and role contracts remain loadable through `FDC-PROJECTION-001` and full pytest.
- 权限 / 路径异常：`FDC-WORKTREE-001` verifies worktree path and branch; `FDC-GREP-DOCS-001` excludes only `docs/**` historical files and scans active `framework` paths.
- 外部依赖异常：No network or external browser session is required; market browser behavior is verified as active skill and role contract text, not by opening a browser.
- Old wording boundary：Tests split retired phrases in code so final grep gates stay meaningful.

## 6. 作弊防护

- Active-surface scans cover multiple directories: `README.md`, `AGENTS.md`, `tests`, `scripts`, `buddyswitch`, `framework`, `tools`.
- Tests assert both presence of canonical owners and absence of retired links, preventing implementation from only deleting files while leaving developers without source pointers.
- Market skill tests cover six files and multiple browser-native constraints, preventing a one-file hardcoded pass.
- Importer test reads generated target `SKILL.md`, preventing a pass that only changes constants without affecting output.
- Projection test loads `framework/contracts/workspace-projection.json`, preventing a pass that only changes README text.
- Retired token strings and retired doc basename strings are split in test code, so grep gates detect real literal regressions.
- Full pytest remains required, preventing docs cleanup from breaking runtime, env tool, launcher, or projection behavior unnoticed.
- Historical `docs/**` are excluded from grep gates by design; active surfaces are not allowed to hide stale references there.

## 7. 验证命令清单

### Focused test commands

```bash
python3 -m pytest -q tests/test_repo_consistency.py::RepoConsistencyTests::test_readme_points_to_canonical_runtime_sources tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_methods_are_owned_by_runtime_code tests/test_repo_consistency.py::RepoConsistencyTests::test_active_surfaces_do_not_reference_retired_framework_docs tests/test_repo_consistency.py::RepoConsistencyTests::test_active_skill_runtime_wording_is_runless tests/test_parallel_contracts.py::WorkspaceProjectionContractTests::test_readme_points_to_workspace_projection_contract tests/test_skill_creator_importer.py::SkillCreatorImporterTests::test_imports_codex_skill_package_and_registers_target_buddy
```

```bash
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
```

### Broader verification commands

```bash
python3 -m pytest -q
```

```bash
test ! -e framework/docs
```

```bash
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

```bash
rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

### Final verification commands before completion

```bash
pwd
git branch --show-current
git status --short
python3 -m pytest -q tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_skill_creator_importer.py
python3 -m pytest -q
test ! -e framework/docs
rg -n "framework/docs|browser-cockpit\\.md|skill-runtime-shared-rules\\.md|turn-runtime-spec\\.md|runtime-broker-v2-runbook\\.md|interface-spec\\.md|architecture-overview\\.md|track-registry\\.md|artifacts-runs-git-policy\\.md|skill-architecture-best-practices\\.md|multi-codex-worktree-guide\\.md|buddyswitch-development-constitution\\.md" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
rg -n "task/artifact/run objects|current buddy run|buddy run|persist one buddy run|Do not call persist|locked buddy session|framework/docs" README.md AGENTS.md tests scripts buddyswitch framework tools -g '!docs/**'
```

Expected final state:

- `pwd` prints `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`.
- `git branch --show-current` prints `dev_buddy_mem`.
- Both pytest commands exit `0`.
- `test ! -e framework/docs` exits `0`.
- Both grep commands return exit code `1` with empty stdout.

# Buddybox Tool Skill Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan phase-by-phase. Work only in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`; use test-driven development for behavior changes and verification-before-completion before claiming completion.

**Goal:** Add and verify a shared Codex-native `buddybox-tool` skill that teaches buddies how to operate the existing BuddySwitch buddybox env tool as an active-buddy private local workspace, without creating a second executor or hardcoded intent router.

**Architecture:** Keep BuddySwitch execution unchanged: runtime skills materialize under `.agents/skills`, Codex reads native `SKILL.md`, and file operations go through `python3 scripts/env/client.py buddybox <operation>` into broker method `env.tool`. The skill stays concise and points to `context.get`, `context.summarize`, `turn_runtime.py status`, and structured tool feedback for full semantics.

**Tech Stack:** Markdown Codex skills, TOML manifest, Python env tool registry/services, launcher AGENTS templates, framework contracts, pytest.

---

## 1. 任务目标

完成后，所有拥有 buddybox 权限的 buddy 都会在运行时获得共享 `buddybox-tool` skill，并能通过 Codex 原生 skill 层理解何时使用 active-buddy 私有本地 buddybox、何时改用 artifact 承载产品可读内容、以及如何调用现有 env tool。当前核心瓶颈是 buddybox 的底层服务和语义已经存在，但缺少与 `task-tool`、`track-tool`、`artifact-tool`、`handoff-tool` 对齐的共享操作 playbook；这会迫使 host 依赖 AGENTS 里的短提示、猜测 CLI payload，或走直接文件系统路径。

## 2. 需求提取

- `REQ-001`：新增共享 Codex-native skill package `buddyswitch/skills/shared/buddybox-tool/SKILL.md`。
- `REQ-002`：`buddybox-tool` 是 buddy-facing 操作 playbook，不是 executor，不读取和执行自己的引擎。
- `REQ-003`：BuddySwitch 继续只负责准备 buddy-specific runtime environment 并调用 Codex；runtime skill materialization 目标仍是 `.agents/skills/<skill-id>`。
- `REQ-004`：所有 buddybox 操作必须通过现有 broker-routed env tool：`python3 scripts/env/client.py buddybox <operation>`。
- `REQ-005`：不得新增 Codex-native function/tool named `buddybox`，不得绕过 runtime broker。
- `REQ-006`：不得把 `buddyswitch/local/buddybox/**` 或 `buddyswitch/objects/**` 作为正常 buddy 工作流的直接编辑目标。
- `REQ-007`：不得引入 phrase trigger，例如 “prototype means HTML” 或 “用户说 prototype 就写 buddybox”。
- `REQ-008`：不得在每次 buddybox write 后强制 artifact promotion；promotion 只在内容需要 product-readable 或 cross-buddy-readable 时发生。
- `REQ-009`：不得把完整 tool schema、长 payload 表、长 action semantics 复制到 skill；完整目录和语义由 `context.get`、`context.summarize`、`scripts/turn_runtime.py status` 和 tool response 提供。
- `REQ-010`：AGENTS.md 只保留短 route marker，不承载 buddybox 长文档。
- `REQ-011`：skill frontmatter 必须声明 `name: buddybox-tool`，description 必须覆盖 active buddy private workspace files、drafts/prototypes/exports/logs/reports/binary outputs、通过 BuddySwitch env tools 操作。
- `REQ-012`：skill 必须说明 buddybox 是 active-buddy private local workspace。
- `REQ-013`：skill 必须说明其他 buddy 不能 list/read/write/delete 这些文件。
- `REQ-014`：skill 必须说明 buddybox path 不是 cross-buddy payload authority。
- `REQ-015`：skill 必须说明 product-readable 或 cross-buddy-readable 内容必须通过 artifact 或其他明确可读对象承载。
- `REQ-016`：skill 必须说明何时使用 buddybox：private drafts、prototypes、exports、logs、reports、binary outputs、local generated files。
- `REQ-017`：skill 必须说明何时不使用 buddybox：product deliverables、shared source edits、handoff-readable payloads、cross-buddy transport。
- `REQ-018`：skill 必须给出 `desc`、`list`、`read`、`write`、`delete` 的 CLI command forms。
- `REQ-019`：skill 必须说明 path 规则：路径是相对路径，必须在 `<active_buddy>/...` 下，例如 `pm/prototypes/landing.html`。
- `REQ-020`：skill 必须说明 text vs base64 payload：`content` 用于 UTF-8 text，`content_base64` 用于 binary 或 non-UTF-8，二者互斥，`content_type` 是 MIME hint。
- `REQ-021`：skill 必须说明 response fields to inspect：`ok`、`state_changed`、`durability`、`read_scope`、`allowed_next_actions`、`allowed_next_action_options`、created/updated/deleted path fields。
- `REQ-022`：skill 必须包含 runtime closing rules：最终输出总结写入的 private buddybox files、artifact/handoff 状态、blocked reason 和 next action；不要求 prepare/persist 生命周期。
- `REQ-023`：skill 必须包含 concise common flows：write/update、list/read、search-or-inspect、delete cleanup、promotion、rejection recovery。
- `REQ-024`：search flow 必须保持条件化：当前任务不新增 `buddybox.search`；只有 `context.get.tool_catalog` 或 `turn_runtime.py status` 暴露 `buddybox.search` 时才可使用；否则用 `list` 选择 exact path 后 `read`，不得把 shell search 作为正常 buddy workflow。
- `REQ-025`：`buddybox.read` 是 exact-file read，不得被描述为 search；`buddybox.list` 只枚举 summaries，不返回 bodies。
- `REQ-026`：若未来因具体 host failure 新增 `buddybox.search`，必须作为 broker-routed env tool action 实现，保持 active-buddy-private、read-only、bounded、text/snippet-oriented，并覆盖 literal、regex、invalid regex、binary skip、foreign path rejection、no full body 等测试；本任务不实现该 action。
- `REQ-027`：`buddyswitch/manifest.toml` 必须注册 `buddybox-tool` skill row。
- `REQ-028`：每个拥有 `buddybox.read`、`buddybox.write`、`buddybox.delete` 权限的 buddy 必须包含 `buddybox-tool` skill；当前目标 buddy 是 `market`、`pm`、`design`、`dev`、`test`。
- `REQ-029`：runtime materialization 必须为这些 buddy 安装 `.agents/skills/buddybox-tool`。
- `REQ-030`：现有 Codex-native skill materialization 行为必须保持，其他 shared skills 不得回退或缺失。
- `REQ-031`：tests 必须验证 skill teaches env tool usage，而不是 direct filesystem mutation。
- `REQ-032`：tests 必须验证 skill 和 active runtime guidance 不重新引入 `prepare`、`persist`、`run-tool`、retired prepare context wording。
- `REQ-033`：tests 必须验证 shared runtime tool skill expectations include `buddybox-tool`。
- `REQ-034`：tests 必须验证 AGENTS.md 保持短 route marker，不嵌入 buddybox schema 或长操作手册。
- `REQ-035`：tests 必须验证 no hardcoded PM-specific prototype behavior or global trigger rule。
- `REQ-036`：如果测试发现 tool catalog、context summary 或 buddybox response 缺少让 skill 可用的真实 feedback gap，只能补 env tool/semantic surface 的确定性边界，不得让 buddy 绕过 BuddySwitch。

## 3. 现状探索摘要

### 需要查看的关键目录和文件

- `docs/memo/2026-05-15-buddybox-tool-skill-task-memo.md`：需求源，包含最终设计、scope、acceptance criteria、search decision 和 addendum。
- `AGENTS.md`：仓库级 SHARP/testing-bound 规则，要求最短可验证路径、测试先行、无验证不完成。
- `README.md`：runless runtime loop、env tool 命令形态、runtime workspace layout。
- `framework/docs/skill-runtime-shared-rules.md`：native skills 的 runless contribution rules。
- `framework/docs/skill-architecture-best-practices.md`：skill registry 和 `.agents/skills` materialization contract。
- `buddyswitch/manifest.toml`：skill registry source of truth；需要注册 `buddybox-tool` 并分配给 buddy。
- `buddyswitch/skills/shared/{task-tool,track-tool,artifact-tool,handoff-tool}/SKILL.md`：共享 tool skill 的短文档风格参照。
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`：新增或强化目标 skill。
- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`：runtime buddy route marker，必须保持短。
- `framework/contracts/{market,pm,design,dev,test}.md`：role-specific buddybox/artifact boundary 文本。
- `scripts/env/client.py`：skill-facing CLI；当前 buddybox commands 为 `desc/list/read/write/delete`。
- `scripts/env/tools/contracts.py`：env tool action registry；验证 buddybox 当前 operations，不在本任务新增 `search`。
- `scripts/env/tools/semantics.py`：capability/action semantics 和 compact affordances。
- `scripts/env/services/context.py`：`context.get` full tool catalog 与 `context.summarize.tool_affordances`。
- `scripts/env/services/buddybox.py`：active-buddy private path enforcement、text/base64 read/write、structured response feedback。
- `scripts/env/tools/router.py`：unsupported tool/action/args rejection guidance，不得指向 retired prepare surfaces。
- `scripts/env/tools/dispatch.py`：broker-routed handler map；不得新增第二条 buddybox execution path。

### 需要查看或扩展的测试

- `tests/test_runtime_skills.py`：shared skill existence、content contract、runless wording。
- `tests/test_buddyswitch_launcher.py`：runtime `.agents/skills` materialization per buddy。
- `tests/test_env_manifest_v2.py`：manifest skill row and buddy permission/skill relationship。
- `tests/test_repo_consistency.py`：active surface grep gates、AGENTS/skills/role contracts residue checks。
- `tests/test_runless_runtime_contract.py`：`turn_runtime.py status` full env tool catalog and runless exclusions。
- `tests/test_context_binding_env_tool.py`：context summary/get semantic split。
- `tests/test_env_tool_semantic_contract.py`：tool registry semantics quality and buddybox/artifact affordance boundary。
- `tests/test_env_tool_response_contract.py`：response contract fields and next-action options。
- `tests/test_buddybox_env_tool.py`：buddybox path privacy, text/binary lifecycle, invalid payloads, repeat delete。
- `tests/test_env_tool_router.py`：unsupported env tool/action feedback and current discovery surfaces。
- `tests/test_host_decision_surface_product_mode.py`：PM prototype semantic decision surface without phrase routing。

### 运行命令

```bash
git status --short --branch
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_context_binding_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_buddybox_env_tool.py -q
python3 scripts/turn_runtime.py status
```

### 保留、替换、删除或迁移

- 保留：`scripts/env/client.py buddybox desc/list/read/write/delete` CLI surface。
- 保留：broker method `env.tool` 和 `scripts/env/tools/dispatch.py` handler route。
- 保留：buddybox storage root `buddyswitch/local/buddybox/<active_buddy>/**` 和 active-buddy privacy enforcement。
- 保留：`context.get.tool_catalog`、`context.get.operation_semantics`、`scripts/turn_runtime.py status` 作为 full semantic catalog。
- 保留：`context.summarize.tool_affordances` 作为 compact default decision surface。
- 替换：如果 `buddybox-tool/SKILL.md` 仍缺少 required frontmatter、common flows、path/payload/response/promotion/search-condition wording，直接改成 concise complete playbook。
- 替换：如果 manifest buddy skill lists 用静态假设而不是权限关系覆盖，改成 tests 通过权限集合验证。
- 替换：任何 active guidance 中的 `prepare.runtime_context.env_tools`、`prepare`、`persist`、`run-tool` retry wording。
- 删除：skill 或 AGENTS 中任何直接编辑 `buddyswitch/local/buddybox/**`、直接编辑 `buddyswitch/objects/**`、hardcoded phrase trigger、mandatory artifact promotion wording。
- 不迁移：不改 buddybox storage semantics，不迁移现有 buddybox files，不引入 compatibility dual path。

## 4. 最终目标架构

### 最终文件结构与职责

- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
  - 共享 Codex-native skill package。
  - 负责短操作 playbook：使用场景、不使用场景、CLI command forms、path rules、payload rules、response checks、promotion rule、runtime closing、common flows。
  - 不承载完整 schema；指向 `context.get`、`context.summarize`、`scripts/turn_runtime.py status` 和 tool response。

- `buddyswitch/manifest.toml`
  - 仍是 skill registry source of truth。
  - `[[skills]]` 注册 `id = "buddybox-tool"` 和 `path = "buddyswitch/skills/shared/buddybox-tool"`。
  - `market`、`pm`、`design`、`dev`、`test` 的 `skills` 包含 `buddybox-tool`，因为这些 buddy 拥有 buddybox read/write/delete permissions。

- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - 保留短 runtime route markers。
  - 不复制 buddybox payload details。
  - 继续声明 active buddy、context start command、full catalog inspection command、buddybox privacy boundary、artifact read boundary、direct-edit 禁止规则。

- `framework/contracts/{market,pm,design,dev,test}.md`
  - 角色级边界短句：各角色可用 buddybox 的私有本地文件类型，以及何时必须使用 artifact。
  - 不复制 full tool schema 或 skill common flows。

- `scripts/env/client.py`
  - 继续是 skill-facing CLI。
  - Buddybox subcommands 保持 `desc`、`list`、`read`、`write`、`delete`。
  - 本任务不新增 `buddybox search` parser。

- `scripts/env/tools/contracts.py`
  - 继续注册 buddybox action set：`desc/list/read/write/delete`。
  - `env_tools_description()` 和 `operation_semantics()` 继续为 full inspect layer。
  - 如果本文件缺少 `compact_tool_affordances()`，新增该函数委托到 `scripts/env/tools/semantics.py`；如果已存在，只保留并测试。

- `scripts/env/tools/semantics.py`
  - 继续承载 buddybox capability/action semantics。
  - `compact_tool_affordances()` 返回 buddybox/artifact 的 compact decision hints。
  - Buddybox semantics 明确 private local、not collaborative、not product object、artifact promotion conditional。

- `scripts/env/services/context.py`
  - `context.summarize` 返回 compact `tool_affordances`。
  - `context.get` 返回 full `tool_catalog` 和 `operation_semantics`。

- `scripts/env/services/buddybox.py`
  - 继续承载 active-buddy path normalization、symlink escape 防护、text/base64 read/write、state impact response。
  - 如果 tests 发现 response feedback gap，使用 existing `tool_responses.next_action_option()` 增加结构化 `allowed_next_action_options`；不得通过 skill 指导 buddy 直接改文件。

- `scripts/env/tools/router.py`
  - Unsupported tool/action/args feedback 指向 `context.get.tool_catalog`、`context.summarize.tool_affordances`、`python3 scripts/turn_runtime.py status`。
  - 不指向 retired prepare context。

- Tests:
  - `tests/test_runtime_skills.py`：skill package content and runless wording。
  - `tests/test_buddyswitch_launcher.py`：runtime materialization。
  - `tests/test_env_manifest_v2.py`：manifest permission-to-skill relationship。
  - `tests/test_repo_consistency.py`：active surface residue and concise AGENTS/role contracts。
  - `tests/test_context_binding_env_tool.py`、`tests/test_env_tool_semantic_contract.py`、`tests/test_env_tool_response_contract.py`、`tests/test_buddybox_env_tool.py`、`tests/test_env_tool_router.py`、`tests/test_host_decision_surface_product_mode.py`：semantic split and feedback integration.

### 核心数据模型与接口边界

Skill package frontmatter:

```yaml
---
name: buddybox-tool
description: Use when the active buddy needs private local workspace files such as drafts, prototypes, exports, logs, reports, or binary outputs, and needs to operate buddybox through BuddySwitch env tools.
---
```

Buddybox write payload example in skill:

```json
{
  "path": "pm/prototypes/landing.html",
  "content": "<!doctype html>...",
  "content_type": "text/html"
}
```

Buddybox binary write payload example in skill:

```json
{
  "path": "pm/assets/snapshot.png",
  "content_base64": "<base64>",
  "content_type": "image/png"
}
```

Skill command forms:

```bash
python3 scripts/env/client.py buddybox desc
python3 scripts/env/client.py buddybox list --path pm/prototypes --recursive
python3 scripts/env/client.py buddybox read --path pm/prototypes/landing.html
python3 scripts/env/client.py buddybox write --payload /tmp/buddybox-write.json
python3 scripts/env/client.py buddybox delete --path pm/tmp/obsolete.txt
```

Runtime call flow:

1. Host starts from `python3 scripts/env/client.py context summarize`.
2. Host uses `tool_affordances` and `buddybox-tool` to choose buddybox vs artifact.
3. Host inspects full payload details through `python3 scripts/env/client.py context get` or `python3 scripts/turn_runtime.py status` when needed.
4. Host calls `python3 scripts/env/client.py buddybox <operation>`.
5. `scripts/env/client.py` sends broker request `{tool:"buddybox", action:"<operation>", args:{...}}`.
6. Runtime broker dispatches method `env.tool` through `scripts/env/tools/router.py`.
7. `scripts/env/tools/dispatch.py` calls the corresponding `scripts/env/services/buddybox.py` service function.
8. Service returns structured response with `ok`, `state_changed`, `durability`, `read_scope`, file metadata or rejection feedback.
9. Host follows `allowed_next_actions` and `allowed_next_action_options`; artifact promotion occurs only when product-readable content is required.

Search boundary:

- Current final action set is `desc/list/read/write/delete`.
- `buddybox.read` remains exact path only.
- `buddybox.list` remains summary only.
- `buddybox-tool` may mention search only as conditional catalog-driven behavior: use `buddybox.search` only if the runtime catalog exposes it; otherwise list candidate paths and read exact files.
- No shell search over `buddyswitch/local/buddybox/**` appears in buddy-facing workflow text.

## 5. 分阶段实施计划

### 阶段 1：锁定 manifest、skill package、runtime materialization 的失败测试

**目标**

先用 tests 定义完整 skill registration/materialization contract，防止只新增文件而漏掉 buddy membership 或运行时复制。

**具体文件变更**

- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/test_env_manifest_v2.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. In `tests/test_runtime_skills.py`, add `RuntimeSkillsTests.test_buddybox_tool_skill_exists_with_required_frontmatter_and_sections`.
   - Read `buddyswitch/skills/shared/buddybox-tool/SKILL.md`.
   - Assert frontmatter contains `name: buddybox-tool`.
   - Assert description contains these lower-case tokens: `active buddy`, `private local workspace`, `drafts`, `prototypes`, `exports`, `logs`, `reports`, `binary outputs`, `buddySwitch env tools` normalized to lower-case.
   - Assert headings or body tokens cover: `what buddybox is`, `when to use`, `when not to use`, `commands`, `path`, `payload`, `response`, `promotion`, `runtime closing`, `common flows`.

2. In `tests/test_runtime_skills.py`, add `RuntimeSkillsTests.test_buddybox_tool_teaches_env_tool_not_direct_filesystem`.
   - Assert skill includes `python3 scripts/env/client.py buddybox`.
   - Assert skill includes all command operation tokens: `desc`, `list`, `read`, `write`, `delete`.
   - Assert skill includes `content`, `content_base64`, `content_type`, `allowed_next_actions`, `allowed_next_action_options`, `artifact.create_revision`.
   - Assert skill does not include direct write command patterns: `cat > buddyswitch/local/buddybox`, `tee buddyswitch/local/buddybox`, `open("buddyswitch/local/buddybox`, `Path("buddyswitch/local/buddybox`.
   - Assert skill does not include `prepare`, `persist`, `run-tool`, `prototype means`, `always create artifact`.

3. In `tests/test_runtime_skills.py`, add `RuntimeSkillsTests.test_buddybox_tool_search_flow_is_conditional_and_does_not_shell_search`.
   - Assert skill text contains `search`.
   - Assert same paragraph or section contains `when available` or `if tool catalog exposes`.
   - Assert skill text contains `context.get` or `scripts/turn_runtime.py status`.
   - Assert skill text contains `do not shell-search` or `do not use shell search`.
   - Assert skill text does not contain normal workflow command snippets with `rg buddyswitch/local/buddybox`, `grep -R buddyswitch/local/buddybox`, or `find buddyswitch/local/buddybox`.

4. In `tests/test_env_manifest_v2.py`, add `EnvManifestV2Tests.test_buddybox_capable_buddies_include_buddybox_tool`.
   - Load manifest.
   - For every buddy where permissions include any of `buddybox.read`, `buddybox.write`, `buddybox.delete`, assert `buddybox-tool` is in `skills`.
   - Assert the set of such buddy ids is exactly `{"market", "pm", "design", "dev", "test"}`.

5. In `tests/test_env_manifest_v2.py`, add `EnvManifestV2Tests.test_buddybox_tool_skill_row_points_to_shared_package`.
   - Assert one and only one `[[skills]]` row has `id == "buddybox-tool"`.
   - Assert row keys are exactly `{"id", "path"}`.
   - Assert `path == "buddyswitch/skills/shared/buddybox-tool"`.
   - Assert `ROOT / path / "SKILL.md"` exists.

6. In `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`, keep the existing expected skill equality assertion and add a permission-derived assertion:
   - For every buddy with any buddybox permission, assert `.agents/skills/buddybox-tool/SKILL.md` exists in `runtime_skills`.
   - Keep byte-for-byte directory equality from manifest source to runtime target.

7. In `tests/test_repo_consistency.py`, add or strengthen `RepoConsistencyTests.test_shared_skills_are_runless` to include `buddyswitch/skills/shared/buddybox-tool/SKILL.md`.
   - Assert no shared skill contains `prepare.runtime_context`, `turn_runtime.py persist`, `buddy-run commit`, `run-tool`.
   - Assert each shared skill contains `env.tool`.

**预期行为变化**

The test suite now fails when `buddybox-tool` is absent, unregistered, not installed at runtime, too vague, too large in the wrong place, or teaches direct filesystem mutation.

**对应需求编号**

`REQ-001` through `REQ-011`, `REQ-018`, `REQ-020` through `REQ-033`, `REQ-035`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

Expected before implementation: failures identify missing or incomplete `buddybox-tool` content, manifest row, buddy membership, or materialization assertion.

**阶段完成标准**

The focused tests fail for the intended missing contract only, not because of syntax errors, collection errors, or unrelated launcher setup failures.

### 阶段 2：新增或强化 `buddybox-tool` skill 并注册到 manifest

**目标**

Create the concise shared skill package and wire it to every buddy with buddybox permissions.

**具体文件变更**

- Create or modify `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- Modify `buddyswitch/manifest.toml`

**详细步骤**

1. Create directory `buddyswitch/skills/shared/buddybox-tool/` when absent.

2. Write `buddyswitch/skills/shared/buddybox-tool/SKILL.md` with exact frontmatter:

```yaml
---
name: buddybox-tool
description: Use when the active buddy needs private local workspace files such as drafts, prototypes, exports, logs, reports, or binary outputs, and needs to operate buddybox through BuddySwitch env tools.
---
```

3. In the skill body, use these section headings and bounded content:
   - `## What Buddybox Is`: state active-buddy private local workspace, other buddies cannot read it, paths are not cross-buddy authority.
   - `## Use It When`: list private drafts, prototypes, exports, logs, reports, generated files, binary outputs.
   - `## Do Not Use It When`: list product-readable deliverables, cross-buddy payloads, shared source edits, direct object mutation.
   - `## Commands`: include exactly the five command forms for `desc/list/read/write/delete`.
   - `## Path Rules`: paths under `<active_buddy>/...`; no absolute paths, traversal, foreign buddy prefix, direct root edits.
   - `## Payload Rules`: one short text payload example and one short binary payload example; explain `content`, `content_base64`, `content_type`, `read --encoding`.
   - `## Response Checks`: inspect `ok`, `state_changed`, `durability`, `read_scope`, `allowed_next_actions`, `allowed_next_action_options`; trust structured rejection feedback.
   - `## Promotion Rule`: use `artifact.create_revision` only when readable content must become product-readable or cross-buddy-readable.
   - `## Runtime Closing`: summarize private buddybox files written and artifact/handoff status; include blockers and next action when a tool rejects.
   - `## Common Flows`: write/update, list/read, search-or-inspect, delete cleanup, promotion, rejection recovery.

4. Keep skill concise:
   - Do not include large HTML templates.
   - Do not include full `tool_catalog`.
   - Do not include complete action schemas.
   - Do not include phrase triggers or PM-specific prototype routing.

5. In the `search-or-inspect` common flow:
   - Write that `buddybox.read` is exact-file read.
   - Write that `buddybox.list` returns summaries only.
   - Write that `buddybox.search` may be used only when `context.get.tool_catalog['buddybox']` or `python3 scripts/turn_runtime.py status` shows a registered `search` operation.
   - Write that when no `buddybox.search` operation is exposed, the normal path is `list` to identify candidate paths and `read` exact files.
   - Write that shell search over `buddyswitch/local/buddybox/**` is not a normal buddy workflow.

6. In `buddyswitch/manifest.toml`, add one skill row if absent:

```toml
[[skills]]
id = "buddybox-tool"
path = "buddyswitch/skills/shared/buddybox-tool"
```

7. In each `[[buddies]]` row for `market`, `pm`, `design`, `dev`, and `test`, add `"buddybox-tool"` to `skills` exactly once.

**预期行为变化**

Codex runtime workspaces can load `buddybox-tool` like other shared tool skills. The skill gives operational memory without changing the buddybox execution path or storage semantics.

**对应需求编号**

`REQ-001` through `REQ-025`, `REQ-027` through `REQ-035`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless -q
```

**阶段完成标准**

Focused tests pass. Manifest contains exactly one `buddybox-tool` row. Each buddy with buddybox permissions has the skill. The skill has concise required sections and contains no direct filesystem mutation instruction or retired lifecycle wording.

### 阶段 3：确认 layered semantic surfaces 支撑 skill，不把 schema 塞进 skill

**目标**

Make sure host-facing surfaces provide the details that the concise skill intentionally omits: compact affordances in summary, full catalog in get/status, and clear buddybox/artifact boundaries.

**具体文件变更**

- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_runless_runtime_contract.py`
- Modify `scripts/env/tools/semantics.py` only if compact affordance or buddybox boundary tokens are missing.
- Modify `scripts/env/tools/contracts.py` only if `compact_tool_affordances()` is missing.
- Modify `scripts/env/services/context.py` only if `context.summarize` does not return `tool_affordances`.

**详细步骤**

1. In `tests/test_context_binding_env_tool.py`, keep or add `ContextBindingEnvToolTests.test_context_summarize_exposes_compact_tool_affordances`.
   - Assert `summary["tool_affordances"]` has keys exactly `{"buddybox", "artifact"}`.
   - Assert `buddybox.use_for` contains `private local`, `drafts`, `lightweight prototypes`, `exports`, `reports`, `logs`, `generated files`, `binary outputs`.
   - Assert `buddybox.not_for` contains `cross-buddy readable` and `product objects`.
   - Assert `buddybox.promote_with` contains `artifact.create_revision`.
   - Assert `artifact.use_for` contains `product-readable deliverables`.

2. In `tests/test_context_binding_env_tool.py`, keep or add `ContextBindingEnvToolTests.test_context_summarize_tool_affordances_stay_compact`.
   - Assert `context.summarize` response does not include `tool_catalog` or `operation_semantics`.
   - Assert each affordance row omits `payload_fields`, `action_semantics`, `content`, `content_base64`, `files`.

3. In `tests/test_context_binding_env_tool.py`, keep or add `ContextBindingEnvToolTests.test_context_get_exposes_full_tool_catalog_for_inspection`.
   - Assert `context.get` includes `tool_catalog["buddybox"]["action_semantics"]`.
   - Assert `context.get` includes `operation_semantics["buddybox.write"]`.
   - Assert `tool_catalog["buddybox"]["payload_fields"]["write"]` contains `path`, `content`, `content_base64`, `content_type`.

4. In `tests/test_env_tool_semantic_contract.py`, keep or add `EnvToolSemanticContractTests.test_buddybox_semantics_explain_private_local_workspace_boundary`.
   - Assert capability text contains `active buddy`, `private`, `local workspace`, `not collaborative`, `not visible to other buddies`, `not product object`, `artifact`.

5. In `tests/test_env_tool_semantic_contract.py`, keep or add `EnvToolSemanticContractTests.test_buddybox_semantics_cover_file_output_affordances_and_output_meanings`.
   - Assert buddybox capability use cases include drafts/prototypes/exports/reports/logs/generated/binary.
   - Assert `desc` writes no files and returns summary only.
   - Assert `list` is summary-only and no bodies.
   - Assert `read` explains one exact path and `encoding`.
   - Assert `write` explains creates/overwrites and no product objects.
   - Assert `delete` explains absent repeat behavior.
   - Assert artifact promotion language contains `when` and does not contain `must`.

6. In `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests.test_status_exposes_env_tools_catalog`, assert `scripts/turn_runtime.py status` includes `env_tools["buddybox"]["action_semantics"]["write"]["inputs_explained"]`.

7. If `scripts/env/tools/semantics.py` lacks compact affordances, add function:
   - `compact_tool_affordances() -> dict[str, dict[str, str]]`
   - Return exactly two top-level keys: `buddybox`, `artifact`.
   - `buddybox` fields: `use_for`, `not_for`, `promote_with`, `inspect_with`.
   - `artifact` fields: `use_for`, `not_for`, `inspect_with`.

8. If `scripts/env/tools/contracts.py` lacks `compact_tool_affordances()`, add:
   - `def compact_tool_affordances() -> dict[str, dict[str, str]]: return semantics.compact_tool_affordances()`

9. If `scripts/env/services/context.py` lacks summary affordances, modify `summarize_context()` so `summary` includes `"tool_affordances": tool_contracts.compact_tool_affordances()`.

**预期行为变化**

The skill can stay short because the host can inspect compact tool choice guidance through `context.summarize`, then full payload/action semantics through `context.get` or `turn_runtime.py status`.

**对应需求编号**

`REQ-009`, `REQ-016`, `REQ-017`, `REQ-020` through `REQ-026`, `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog -q
```

**阶段完成标准**

`context.summarize` is compact; `context.get` and `turn_runtime.py status` expose full catalog; semantic tests prove buddybox vs artifact boundaries without adding a phrase router.

### 阶段 4：验证 buddybox response feedback 和 rejection recovery 可支撑 skill 流程

**目标**

Ensure tool responses give enough structured feedback for the skill’s verification and recovery loops, so buddies do not need direct filesystem bypasses.

**具体文件变更**

- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_env_tool_router.py`
- Modify `scripts/env/services/buddybox.py` only if structured next-action feedback is missing.
- Modify `scripts/env/tools/router.py` only if retired prepare wording remains.

**详细步骤**

1. In `tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests.test_buddybox_desc_returns_private_local_workspace_summary`, assert:
   - Response has `ok == True`, `action == "buddybox.desc"`, `state_changed == False`.
   - Response includes `logical_root`, `privacy_boundary`, `state_summary`, `allowed_next_actions`, `allowed_next_action_options`.
   - Response omits `files`, `content`, `content_base64`.
   - Options include `("buddybox", "list")` and `("buddybox", "write")`.

2. In `tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests.test_buddybox_text_and_binary_lifecycle_uses_local_root`, assert:
   - Text write creates `buddyswitch/local/buddybox/pm/prototypes/hero.html`.
   - Binary write/read returns base64 when needed.
   - List rows include `private_to_buddy` and omit `content` and `content_base64`.
   - Write/read options include conditional `artifact.create_revision`; option reason contains `when` and does not contain `must`.

3. In `tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests.test_pm_cannot_read_list_write_or_delete_foreign_private_paths`, assert each rejection:
   - `ok == False`
   - error code `E_BUDDYBOX_SCOPE`
   - `state_changed == False`
   - includes `permission_boundary`, `why_blocked`, `retryable`, `allowed_next_actions`, `allowed_next_action_options`
   - options include `buddybox.desc` and retry same buddybox action under active buddy path.

4. In `tests/test_buddybox_env_tool.py`, keep or add invalid path/payload coverage:
   - Empty path, absolute path, `../`, `pm/../x`, missing content, both `content` and `content_base64`, invalid read encoding.
   - Assert each rejected payload leaves state unchanged.

5. In `tests/test_env_tool_response_contract.py::EnvToolResponseContractTests.test_success_responses_cover_read_write_and_target_scoped_evidence`, assert buddybox write response options have `tool`, `action`, `mutates`, `reason`, `source_refs`.

6. In `tests/test_env_tool_router.py`, add or keep tests for unsupported tool/action/args:
   - Rejection `retry_guidance` and `allowed_next_actions` mention `context.get.tool_catalog`, `context.summarize.tool_affordances`, or `python3 scripts/turn_runtime.py status`.
   - Rejection text does not mention `prepare.runtime_context.env_tools`.

7. If `scripts/env/services/buddybox.py` lacks options, add helper functions:
   - `_next_option(tool: str, action: str, option_id: str, reason: str, preconditions: list[str] | None = None) -> dict[str, Any]`
   - `_desc_options()`, `_list_options()`, `_read_options()`, `_write_options()`, `_delete_options()`, `_rejection_options(action: str)`
   - Each helper calls `tool_responses.next_action_option()` and uses source refs `context.get.tool_catalog['<tool>']` and `context.get.operation_semantics['<tool>.<action>']`.

8. If `scripts/env/tools/router.py` still has retired wording, replace it:
   - Unsupported tool retry guidance: `Inspect context.get.tool_catalog, context.summarize.tool_affordances, or python3 scripts/turn_runtime.py status, then retry with a supported tool.`
   - Unsupported action retry guidance: `Inspect context.get.operation_semantics and python3 scripts/turn_runtime.py status, then retry with a supported action.`
   - Args shape guidance: `Use context.get.tool_catalog['<tool>'].payload_fields to shape args.`

**预期行为变化**

Buddybox responses become sufficient for skill-driven verification and recovery. Rejections guide hosts back to active-buddy private paths and current discovery surfaces, never to retired lifecycle or direct filesystem bypasses.

**对应需求编号**

`REQ-004` through `REQ-006`, `REQ-021` through `REQ-026`, `REQ-031`, `REQ-032`, `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddybox_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_router.py -q
```

**阶段完成标准**

All buddybox lifecycle and rejection tests pass. No response suggests direct buddybox root mutation. Unsupported tool/action feedback points to current runless discovery surfaces.

### 阶段 5：保持 AGENTS 和 role contracts 短而清晰

**目标**

Prevent guidance bloat: AGENTS remains a route map, role contracts stay role-specific, and `buddybox-tool` owns repeated operational guidance.

**具体文件变更**

- Modify `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md` only if required route marker is missing.
- Modify `framework/contracts/{market,pm,design,dev,test}.md` only if role-specific buddybox/artifact boundary is missing or stale.
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. In each buddy AGENTS file, ensure these short bullets exist:
   - `Start with python3 scripts/env/client.py context summarize.`
   - `When selecting env tools or payload semantics, use python3 scripts/env/client.py context get or python3 scripts/turn_runtime.py status for the full tool catalog.`
   - `Buddybox is the active buddy private local working directory: buddyswitch/local/buddybox/<buddy>/.`
   - `Other buddies cannot list/read/write/delete these local files; use artifact when content must become product-readable.`
   - `Do not edit buddyswitch/objects/** or buddyswitch/local/buddybox/** directly.`

2. In each buddy AGENTS file, keep out:
   - Buddybox JSON payload examples.
   - Full operation schema.
   - Hardcoded prototype or PM trigger rules.
   - Mandatory artifact promotion.

3. In `framework/contracts/pm.md`, ensure PM boundary sentence says:
   - `Use buddybox for PM-owned private local drafts, lightweight prototypes, exports, or supporting files; use artifact when content must become product-readable.`

4. In `framework/contracts/design.md`, ensure design boundary sentence says:
   - `Use buddybox for private local prototypes or exports; use artifact for design handoffs or prototype briefs another buddy must read.`

5. In `framework/contracts/dev.md`, ensure dev boundary sentence says:
   - `Use buddybox for private logs, generated files, binary outputs, or local reports; use artifact for implementation reports and technical conclusions the product workflow must read.`

6. In `framework/contracts/test.md`, ensure test boundary sentence says:
   - `Use buddybox for private logs, raw evidence files, or local reports; use artifact for pass/fail reports the product workflow must read.`

7. In `framework/contracts/market.md`, ensure market boundary sentence says:
   - `Use buddybox for private research exports, logs, or local reports; use artifact for market deliverables PM, Design, or Dev must read.`

8. In `tests/test_repo_consistency.py`, keep or add:
   - `RepoConsistencyTests.test_role_contracts_keep_buddybox_guidance_short_and_role_specific`
   - `RepoConsistencyTests.test_buddy_agents_contain_direct_id_artifact_read_boundary`
   - `RepoConsistencyTests.test_no_hardcoded_intent_to_buddybox_phrase_routing`
   - Each grep test scans active source/guidance excluding `docs/memo/**`, `docs/spec/**`, and `tests/**` where historical plans or negative assertions may mention forbidden phrases.

**预期行为变化**

Runtime prompts stay concise; repeated buddybox workflow knowledge lives in the skill; role-specific contracts clarify private-local vs artifact boundary without becoming manuals.

**对应需求编号**

`REQ-007` through `REQ-010`, `REQ-014` through `REQ-017`, `REQ-034`, `REQ-035`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_role_contracts_keep_buddybox_guidance_short_and_role_specific \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_agents_contain_direct_id_artifact_read_boundary \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_no_hardcoded_intent_to_buddybox_phrase_routing -q
```

**阶段完成标准**

AGENTS files contain route markers and boundary rules only. Role contracts contain short role-specific buddybox/artifact boundaries. Active surfaces contain no hardcoded trigger phrases.

### 阶段 6：关闭 search decision，不新增未证明需要的 env action

**目标**

Resolve the source memo’s search discussion with a concrete implementation boundary: do not add `buddybox.search` in this task; keep `read` exact, `list` summary-only, and skill search guidance conditional.

**具体文件变更**

- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_runless_runtime_contract.py`
- Modify `buddyswitch/skills/shared/buddybox-tool/SKILL.md` if search flow wording is absent or misleading.

**详细步骤**

1. In `tests/test_runtime_skills.py::RuntimeSkillsTests.test_buddybox_tool_search_flow_is_conditional_and_does_not_shell_search`, assert the skill:
   - Mentions search as catalog-dependent.
   - Mentions `list` and exact `read` as current fallback.
   - Rejects shell search over buddybox roots.

2. In `tests/test_env_tool_semantic_contract.py`, add `EnvToolSemanticContractTests.test_buddybox_current_operations_do_not_conflate_read_list_and_search`.
   - Assert `contracts.supported_actions("buddybox") == {"desc", "list", "read", "write", "delete"}`.
   - Assert buddybox `read` semantic text contains `one` and `exact` or `path`.
   - Assert buddybox `list` semantic text contains `summary` and does not contain `body` as an output promise.
   - Assert no registered buddybox action named `search`.

3. In `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests.test_status_exposes_env_tools_catalog`, assert `search` is not in `payload["env_tools"]["buddybox"]["operations"]`.

4. If skill wording promises `buddybox.search` as currently available, change it to:
   - `For keyword or regex search, first inspect context.get.tool_catalog['buddybox'] or python3 scripts/turn_runtime.py status. Use buddybox.search only if the runtime exposes that operation. In the current runless catalog, use buddybox.list to find candidate paths and buddybox.read for exact files. Do not shell-search buddybox roots as the normal buddy workflow.`

**预期行为变化**

The implementation does not add speculative search machinery. The host gets a safe conditional flow and cannot confuse `read` with search.

**对应需求编号**

`REQ-024` through `REQ-026`, `REQ-035`, `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_search_flow_is_conditional_and_does_not_shell_search \
  tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_current_operations_do_not_conflate_read_list_and_search \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog -q
```

**阶段完成标准**

No `buddybox.search` parser, registry action, dispatch handler, or service function is added. Skill wording is conditional and safe. Tests prove current read/list/search boundaries.

### 阶段 7：最终集成验证

**目标**

Prove the complete task across skill package, manifest, runtime materialization, context/semantic surfaces, response recovery, AGENTS/role guidance, and runless residue scans.

**具体文件变更**

- No source changes in this phase unless a focused test failure identifies an exact missing requirement from earlier phases.

**详细步骤**

1. Run focused skill and manifest tests.
2. Run launcher materialization test.
3. Run semantic/context/response tests.
4. Run repo consistency and runless contract tests.
5. Run active grep gates for retired lifecycle and hardcoded trigger phrases.
6. Inspect `git status --short` and verify changes are scoped to planned files.

**预期行为变化**

All required behavior is verified. The worktree contains one clear implementation path with no direct buddybox filesystem workflow, no duplicate executor, no old prepare/persist wording, and no speculative search action.

**对应需求编号**

All requirements `REQ-001` through `REQ-036`.

**验证命令**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py \
  tests/test_runless_runtime_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_buddybox_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_host_decision_surface_product_mode.py -q

rg -n "prepare\\.runtime_context\\.env_tools|prototype means|quickly build means|route prototype to buddybox|always create artifact" \
  README.md AGENTS.md scripts framework buddyswitch tools \
  -g '!docs/memo/**' -g '!docs/spec/**'

git status --short --branch
```

For the `rg` command, expected result is exit code `1` with no matches on active surfaces (excluding `tests` where negative assertions intentionally include forbidden literals).

**阶段完成标准**

All pytest commands pass. Active grep gates return no matches. `git status` shows only the intended implementation/test/docs files in `dev_buddy_mem`.

## 6. 迁移 / 删除策略

- No data migration is required because buddybox storage semantics stay under `buddyswitch/local/buddybox/<active_buddy>/**`.
- No compatibility dual path is kept. The only normal operation path is `python3 scripts/env/client.py buddybox <operation>` through broker method `env.tool`.
- Remove any active guidance that tells buddies to write directly to `buddyswitch/local/buddybox/**` or `buddyswitch/objects/**`.
- Remove any active wording that points hosts to retired `prepare.runtime_context.env_tools`, `prepare`, `persist`, or `run-tool` flows.
- Do not add `buddybox.search` in this task. If a later concrete host failure proves deterministic search is required, it must be implemented as a separate broker-routed env tool action with the semantics and tests listed in `REQ-026`.
- Do not split `buddybox-tool` into sub-skills. The source memo says multiple concise common workflows belong in this skill until a workflow has independent triggerability, inputs/outputs, and verification pattern.

## 7. 完成定义

The task is complete only when all of the following are true:

- `buddyswitch/skills/shared/buddybox-tool/SKILL.md` exists with required frontmatter and concise operational guidance.
- `buddyswitch/manifest.toml` registers `buddybox-tool` exactly once.
- `market`, `pm`, `design`, `dev`, and `test` include `buddybox-tool` because they have buddybox permissions.
- Launcher materialization installs `.agents/skills/buddybox-tool` for every buddybox-capable buddy and preserves other native skills.
- AGENTS files remain short route maps and do not embed buddybox schemas.
- Skill and active guidance teach env tool usage, not direct filesystem mutation.
- Skill and active guidance contain no retired prepare/persist/run-tool flow and no hardcoded prototype trigger rule.
- `context.summarize`, `context.get`, `turn_runtime.py status`, and buddybox responses provide enough host-facing semantics for the concise skill to work.
- `buddybox.read` remains exact-file read; `buddybox.list` remains summary-only; no speculative `buddybox.search` action is introduced in this task.
- Focused and broader verification commands in 阶段 7 pass in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`.

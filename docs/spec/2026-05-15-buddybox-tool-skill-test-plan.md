# Buddybox Tool Skill Test Plan

## 1. 测试设计原则

- Tests start from the source memo’s external contract: a Codex host should learn buddybox workflow through a native shared skill and current env tool semantics, not through hardcoded trigger phrases or direct filesystem writes.
- Tests verify observable behavior and surfaces: manifest data, installed `.agents/skills`, skill text, context output, tool catalog output, CLI/status output, env.tool responses, rejection feedback, AGENTS guidance, role contracts, and persisted private local file state.
- Tests must not be shaped around a single implementation shortcut. A passing implementation must satisfy several independent surfaces: manifest, runtime materialization, skill content, context/catalog semantics, buddybox service behavior, and active guidance residue scans.
- Tests must verify state and output, not only helper calls. For buddybox writes, assert actual file path under `buddyswitch/local/buddybox/<active_buddy>/**`; for list/desc, assert no bodies; for rejections, assert state did not change.
- Tests must include negative and boundary cases: missing payload, invalid paths, foreign buddy prefixes, repeated delete, unsupported env tool/action/args, retired wording, hardcoded trigger phrases, and conditional search guidance.
- Tests should cover all five buddybox-capable buddies where membership or runtime materialization matters: `market`, `pm`, `design`, `dev`, `test`.
- Manual verification may supplement launcher confidence, but repeatable behavior must be covered by automated tests.

## 2. 需求覆盖矩阵

| Requirement | Test coverage |
| --- | --- |
| `REQ-001` | `BBTS-SKILL-001`, `BBTS-MAN-001` |
| `REQ-002` | `BBTS-SKILL-002`, `BBTS-RUNLESS-001` |
| `REQ-003` | `BBTS-MAT-001`, `BBTS-CLI-001` |
| `REQ-004` | `BBTS-SKILL-002`, `BBTS-RESP-001`, `BBTS-CLI-001` |
| `REQ-005` | `BBTS-RUNLESS-001`, `BBTS-GREP-001` |
| `REQ-006` | `BBTS-SKILL-002`, `BBTS-RESP-002`, `BBTS-GREP-001` |
| `REQ-007` | `BBTS-GREP-001`, `BBTS-PM-001` |
| `REQ-008` | `BBTS-SKILL-001`, `BBTS-RESP-001`, `BBTS-PM-001` |
| `REQ-009` | `BBTS-SEM-001`, `BBTS-SKILL-001` |
| `REQ-010` | `BBTS-AGENTS-001` |
| `REQ-011` | `BBTS-SKILL-001` |
| `REQ-012` | `BBTS-SKILL-001`, `BBTS-SEM-002` |
| `REQ-013` | `BBTS-SKILL-001`, `BBTS-RESP-002` |
| `REQ-014` | `BBTS-SKILL-001`, `BBTS-SEM-002` |
| `REQ-015` | `BBTS-SKILL-001`, `BBTS-PM-001` |
| `REQ-016` | `BBTS-SKILL-001`, `BBTS-SEM-001`, `BBTS-ROLE-001` |
| `REQ-017` | `BBTS-SKILL-001`, `BBTS-SEM-001`, `BBTS-ROLE-001` |
| `REQ-018` | `BBTS-SKILL-001`, `BBTS-CLI-001` |
| `REQ-019` | `BBTS-SKILL-001`, `BBTS-NEG-001` |
| `REQ-020` | `BBTS-SKILL-001`, `BBTS-RESP-001`, `BBTS-NEG-001` |
| `REQ-021` | `BBTS-SKILL-001`, `BBTS-RESP-001`, `BBTS-RESP-002` |
| `REQ-022` | `BBTS-SKILL-001`, `BBTS-AGENTS-001` |
| `REQ-023` | `BBTS-SKILL-001` |
| `REQ-024` | `BBTS-SEARCH-001` |
| `REQ-025` | `BBTS-SEARCH-001`, `BBTS-RESP-001` |
| `REQ-026` | `BBTS-SEARCH-001`, `BBTS-CLI-001` |
| `REQ-027` | `BBTS-MAN-001` |
| `REQ-028` | `BBTS-MAN-002` |
| `REQ-029` | `BBTS-MAT-001` |
| `REQ-030` | `BBTS-MAT-001`, `BBTS-REG-001` |
| `REQ-031` | `BBTS-SKILL-002`, `BBTS-GREP-001` |
| `REQ-032` | `BBTS-RUNLESS-001`, `BBTS-GREP-001` |
| `REQ-033` | `BBTS-SKILL-003` |
| `REQ-034` | `BBTS-AGENTS-001` |
| `REQ-035` | `BBTS-GREP-001`, `BBTS-PM-001` |
| `REQ-036` | `BBTS-SEM-001`, `BBTS-RESP-002`, `BBTS-ROUTER-001` |

All requirements are suitable for automated coverage. The conditional future `buddybox.search` behavior in `REQ-026` is tested as a current non-addition boundary: current registry/status must not expose search, and skill text must only mention it as catalog-dependent.

## 3. 测试分层

### 单元测试

Purpose: validate manifest/skill text/contracts without launching runtime processes.

Coverage:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- `framework/contracts/{market,pm,design,dev,test}.md`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/semantics.py`
- active guidance grep gates

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_repo_consistency.py -q
```

### 集成测试

Purpose: prove broker-routed env tool behavior and host-facing semantic surfaces.

Coverage:

- `runtime_kernel.broker.dispatch_runtime_request`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/services/context.py`
- `scripts/env/services/buddybox.py`

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_router.py \
  tests/test_host_decision_surface_product_mode.py -q
```

### CLI、API、UI 或主路径运行测试

Purpose: validate public command surfaces and runtime materialization.

Coverage:

- `python3 scripts/env/client.py buddybox --help`
- `python3 scripts/env/client.py context summarize --help`
- `python3 scripts/env/client.py context get --help`
- `python3 scripts/turn_runtime.py status`
- `./buddyswitch-codex instance start --buddy <buddy>` through fake Codex launcher tests

Run:

```bash
python3 scripts/env/client.py buddybox --help
python3 scripts/env/client.py context summarize --help
python3 scripts/env/client.py context get --help
python3 scripts/turn_runtime.py status
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runless_runtime_contract.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

### 回归测试

Purpose: protect existing runless architecture, buddybox privacy, artifact/handoff boundaries, launcher skill copying, and no-retired-wording constraints.

Run:

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
  tests/test_host_decision_surface_product_mode.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py -q
```

### 手动验证

Purpose: confirm the real launcher workspace exposes the same surfaces as automated tests.

Steps:

1. Run `pwd` and confirm `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`.
2. Run `git branch --show-current` and confirm `dev_buddy_mem`.
3. Run `./buddyswitch-codex instance start --buddy pm`.
4. In the PM runtime workspace, confirm `.agents/skills/buddybox-tool/SKILL.md` exists.
5. Run `python3 scripts/env/client.py context summarize` and confirm `tool_affordances.buddybox.use_for` mentions private local prototypes and generated/binary outputs.
6. Run `python3 scripts/env/client.py context get` and confirm `tool_catalog.buddybox.payload_fields.write` includes `path`, `content`, `content_base64`, `content_type`.
7. Run `python3 scripts/env/client.py buddybox desc` and confirm it returns summary fields without file bodies.

## 4. 详细测试用例

### `BBTS-WT-001`: worktree isolation guard

- 测试 ID：`BBTS-WT-001`
- 覆盖需求：repository execution constraint from user request
- 用户 / 系统场景：Implementation must run in `dev_buddy_mem`, not main.
- 前置条件：Repository has Git worktrees.
- 输入：current checkout path and branch.
- 预期输出或状态变化：current path contains `.worktrees/dev_buddy_mem`; branch is `dev_buddy_mem`; primary checkout is a different worktree.
- 断言重点：test fails if work starts on main or detached checkout.
- 测试类型：unit/repo guard.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_worktree_isolated_for_dev_worktree`.

### `BBTS-MAN-001`: manifest registers shared buddybox skill row

- 测试 ID：`BBTS-MAN-001`
- 覆盖需求：`REQ-001`, `REQ-027`
- 用户 / 系统场景：Runtime skill source of truth is manifest.
- 前置条件：`buddyswitch/manifest.toml` exists.
- 输入：manifest parsed with `env_manifest.load_manifest`.
- 预期输出或状态变化：exactly one skill row has `id == "buddybox-tool"` and `path == "buddyswitch/skills/shared/buddybox-tool"`.
- 断言重点：row keys are exactly `id` and `path`; package contains `SKILL.md`.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_buddybox_tool_skill_row_points_to_shared_package`.

### `BBTS-MAN-002`: buddybox-capable buddies include the skill

- 测试 ID：`BBTS-MAN-002`
- 覆盖需求：`REQ-028`
- 用户 / 系统场景：Every buddy with buddybox permissions receives the operating playbook.
- 前置条件：manifest loaded.
- 输入：each `[[buddies]]` row.
- 预期输出或状态变化：buddies with any of `buddybox.read`, `buddybox.write`, `buddybox.delete` are exactly `market`, `pm`, `design`, `dev`, `test`; each includes `buddybox-tool`.
- 断言重点：permission-derived check prevents missing future buddybox-capable buddies.
- 测试类型：unit.
- 建议测试文件路径和测试名称：`tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_buddybox_capable_buddies_include_buddybox_tool`.

### `BBTS-MAT-001`: launcher materializes buddybox-tool for every capable buddy

- 测试 ID：`BBTS-MAT-001`
- 覆盖需求：`REQ-003`, `REQ-029`, `REQ-030`
- 用户 / 系统场景：A launched buddy runtime gets native Codex skills under `.agents/skills`.
- 前置条件：fake Codex launcher test can start each buddy.
- 输入：`./buddyswitch-codex instance start --buddy <buddy> -- debug prompt-input manifest-skill-check-<buddy>`.
- 预期输出或状态变化：runtime `.agents/skills` directories exactly equal manifest buddy skill ids; buddybox-capable buddies include `buddybox-tool/SKILL.md`; skill bytes match source directory.
- 断言重点：no stale manager skills; existing shared and buddy-specific skills remain intact.
- 测试类型：launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`.

### `BBTS-SKILL-001`: skill content covers required playbook

- 测试 ID：`BBTS-SKILL-001`
- 覆盖需求：`REQ-011` through `REQ-023`
- 用户 / 系统场景：Codex reads `buddybox-tool` and has enough operational guidance.
- 前置条件：`buddyswitch/skills/shared/buddybox-tool/SKILL.md` exists.
- 输入：skill markdown text.
- 预期输出或状态变化：frontmatter and body include required description, active-buddy privacy, when-to-use, when-not-to-use, command forms, path rules, payload rules, response checks, promotion rule, runtime closing, common flows.
- 断言重点：required tokens are present but full schemas and huge examples are absent.
- 测试类型：unit text contract.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_skill_exists_with_required_frontmatter_and_sections`.

### `BBTS-SKILL-002`: skill teaches env tool usage, not direct filesystem mutation

- 测试 ID：`BBTS-SKILL-002`
- 覆盖需求：`REQ-002`, `REQ-004`, `REQ-006`, `REQ-031`, `REQ-032`
- 用户 / 系统场景：Buddy follows the skill and calls the env tool instead of editing local roots.
- 前置条件：skill markdown text loaded.
- 输入：skill markdown text lower-cased.
- 预期输出或状态变化：text includes `python3 scripts/env/client.py buddybox` and `env.tool`; text excludes direct write command patterns under `buddyswitch/local/buddybox/**`; text excludes retired lifecycle words.
- 断言重点：not enough to mention buddybox path; the normal mutation command must be env tool CLI.
- 测试类型：unit text contract.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_teaches_env_tool_not_direct_filesystem`.

### `BBTS-SKILL-003`: shared skills include buddybox-tool in runless expectations

- 测试 ID：`BBTS-SKILL-003`
- 覆盖需求：`REQ-033`
- 用户 / 系统场景：Shared tool skill expectations match current runtime tools.
- 前置条件：shared skills exist.
- 输入：manifest and shared skill files.
- 预期输出或状态变化：required shared skill set includes `track-tool`, `artifact-tool`, `task-tool`, `handoff-tool`, `buddybox-tool`; no shared skill references prepare/persist.
- 断言重点：prevents future removal of buddybox-tool from required shared tool set.
- 测试类型：unit text/manifest contract.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_each_buddy_keeps_runless_shared_tool_skills` and `tests/test_repo_consistency.py::RepoConsistencyTests::test_shared_skills_are_runless`.

### `BBTS-SEARCH-001`: search guidance is conditional and not shell-based

- 测试 ID：`BBTS-SEARCH-001`
- 覆盖需求：`REQ-024`, `REQ-025`, `REQ-026`
- 用户 / 系统场景：Buddy needs to find private content but current runtime has no `buddybox.search`.
- 前置条件：skill text and tool registry loaded.
- 输入：skill markdown, `contracts.supported_actions("buddybox")`, `turn_runtime.py status` payload.
- 预期输出或状态变化：skill search flow says use `buddybox.search` only when catalog exposes it; current action set is `{"desc", "list", "read", "write", "delete"}`; status does not expose `buddybox.search`; skill rejects shell search as normal workflow.
- 断言重点：`read` remains exact-file read; `list` remains summary-only; no speculative action appears.
- 测试类型：unit plus CLI contract.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_search_flow_is_conditional_and_does_not_shell_search`, `tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_current_operations_do_not_conflate_read_list_and_search`, `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog`.

### `BBTS-SEM-001`: context summary stays compact while get/status expose full catalog

- 测试 ID：`BBTS-SEM-001`
- 覆盖需求：`REQ-009`, `REQ-016`, `REQ-017`, `REQ-036`
- 用户 / 系统场景：Host starts with compact orientation, then inspects full semantics only when needed.
- 前置条件：runtime broker can dispatch context actions.
- 输入：`context.summarize` and `context.get` env.tool requests.
- 预期输出或状态变化：summary includes compact `tool_affordances` for buddybox/artifact but omits `tool_catalog` and `operation_semantics`; get includes full catalog and operation semantics.
- 断言重点：prevents schema duplication in default summary and skill.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_compact_tool_affordances`, `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_tool_affordances_stay_compact`, `tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_exposes_full_tool_catalog_for_inspection`.

### `BBTS-SEM-002`: buddybox and artifact semantics express the boundary

- 测试 ID：`BBTS-SEM-002`
- 覆盖需求：`REQ-012` through `REQ-017`, `REQ-020`, `REQ-021`, `REQ-025`
- 用户 / 系统场景：Host decides whether content is private local or product-readable.
- 前置条件：`contracts.env_tools_description()` available.
- 输入：`desc["buddybox"]`, `desc["artifact"]`.
- 预期输出或状态变化：buddybox text covers active buddy private local workspace, non-collaborative boundary, not product object, file-output affordances, and conditional artifact promotion; artifact text covers product-readable deliverables.
- 断言重点：promotion wording contains conditional language and does not become mandatory.
- 测试类型：unit semantic contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_explain_private_local_workspace_boundary`, `tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_cover_file_output_affordances_and_output_meanings`.

### `BBTS-RESP-001`: buddybox happy path responses support verification loops

- 测试 ID：`BBTS-RESP-001`
- 覆盖需求：`REQ-004`, `REQ-008`, `REQ-020`, `REQ-021`, `REQ-025`
- 用户 / 系统场景：PM writes, reads, lists, and deletes private local text and binary files.
- 前置条件：runtime workspace test root and PM instance JSON.
- 输入：broker-routed buddybox `desc`, `write`, `read`, `list`, `delete` actions.
- 预期输出或状态变化：text write creates file under `buddyswitch/local/buddybox/pm`; binary write/read returns base64; list returns summaries without bodies; delete reports deleted; responses include state/durability/options.
- 断言重点：no product object is created by buddybox write; artifact promotion option is conditional.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_desc_returns_private_local_workspace_summary`, `tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_text_and_binary_lifecycle_uses_local_root`.

### `BBTS-RESP-002`: rejection feedback keeps buddies inside active scope

- 测试 ID：`BBTS-RESP-002`
- 覆盖需求：`REQ-006`, `REQ-013`, `REQ-021`, `REQ-031`, `REQ-036`
- 用户 / 系统场景：PM tries foreign buddy paths, traversal, bad payloads, and invalid read encoding.
- 前置条件：runtime workspace contains a dev private file and PM instance JSON.
- 输入：buddybox `list/read/write/delete` with foreign `dev/...`, absolute/traversal paths, missing/both payload bodies, invalid encoding.
- 预期输出或状态变化：responses reject with `ok == False`; state unchanged; error codes distinguish scope and payload; options include boundary review and active-path retry; foreign file content remains unchanged.
- 断言重点：structured feedback gives recovery route and does not leak foreign content.
- 测试类型：integration negative.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_pm_cannot_read_list_write_or_delete_foreign_private_paths`, `tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejects_invalid_paths_and_payloads`.

### `BBTS-ROUTER-001`: unsupported env tool feedback points to current discovery surfaces

- 测试 ID：`BBTS-ROUTER-001`
- 覆盖需求：`REQ-032`, `REQ-036`
- 用户 / 系统场景：Host sends unsupported tool, unsupported action, or args with wrong shape.
- 前置条件：router imported.
- 输入：env.tool payloads with unknown `tool`, unknown `action`, non-object `args`.
- 预期输出或状态变化：rejections mention `context.get.tool_catalog`, `context.summarize.tool_affordances`, or `python3 scripts/turn_runtime.py status`; no rejection mentions `prepare.runtime_context.env_tools`.
- 断言重点：retired prepare path cannot return through error recovery.
- 测试类型：unit/integration.
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_unsupported_tool_feedback_points_to_current_tool_discovery_surfaces`, `tests/test_repo_consistency.py::RepoConsistencyTests::test_active_runtime_feedback_points_to_current_tool_discovery_surfaces`.

### `BBTS-AGENTS-001`: runtime AGENTS remain short route maps

- 测试 ID：`BBTS-AGENTS-001`
- 覆盖需求：`REQ-010`, `REQ-022`, `REQ-034`
- 用户 / 系统场景：Buddy runtime prompt orients host without becoming a buddybox manual.
- 前置条件：launcher buddy AGENTS files exist.
- 输入：`tools/launcher/assets/buddies/*/AGENTS.md`.
- 预期输出或状态变化：each file includes context summarize, full catalog inspect command, buddybox private boundary, artifact-read boundary, direct-edit prohibition; each file omits JSON payload examples, `content_base64`, full action schemas, trigger phrases.
- 断言重点：AGENTS stays route marker, skill owns repeated workflow.
- 测试类型：unit text contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_buddy_agents_contain_direct_id_artifact_read_boundary`.

### `BBTS-ROLE-001`: role contracts keep role-specific boundary wording

- 测试 ID：`BBTS-ROLE-001`
- 覆盖需求：`REQ-016`, `REQ-017`
- 用户 / 系统场景：Role contracts distinguish each buddy’s private local file use from artifacts.
- 前置条件：framework role contracts exist.
- 输入：`framework/contracts/{market,pm,design,dev,test}.md`.
- 预期输出或状态变化：PM mentions private drafts/prototypes; design mentions private prototypes/exports; dev mentions logs/generated/binary; test mentions logs/raw evidence/local reports; market mentions research exports/logs/local reports; all mention artifact for readable deliverables.
- 断言重点：contracts do not include payload schemas or mandatory promotion language.
- 测试类型：unit text contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_role_contracts_keep_buddybox_guidance_short_and_role_specific`.

### `BBTS-PM-001`: PM prototype decision uses semantics, not phrase routing

- 测试 ID：`BBTS-PM-001`
- 覆盖需求：`REQ-007`, `REQ-008`, `REQ-015`, `REQ-035`
- 用户 / 系统场景：PM has read-only shared source and needs a quick page prototype.
- 前置条件：PM runtime context and manifest loaded.
- 输入：`context.summarize`, `context.get`, and `buddybox.write` for `pm/prototypes/simple-page.html`.
- 预期输出或状态变化：semantic surfaces show buddybox for private lightweight prototypes and artifact for product-readable deliverables; no text contains `prototype means`; buddybox write creates private file and no product object; allowed next actions include read/list and conditional artifact promotion.
- 断言重点：test asserts semantic inputs, not a hardcoded phrase rule.
- 测试类型：integration host decision surface.
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_private_buddybox_without_phrase_rule`.

### `BBTS-RUNLESS-001`: no retired prepare/persist/run-tool wording returns

- 测试 ID：`BBTS-RUNLESS-001`
- 覆盖需求：`REQ-002`, `REQ-005`, `REQ-032`
- 用户 / 系统场景：Runless runtime should not revive old run lifecycle.
- 前置条件：active source/guidance files exist.
- 输入：repo scans and shared skill text.
- 预期输出或状态变化：no active hits for `prepare.runtime_context.env_tools`, `turn_runtime.py persist`, `buddy-run commit`, `run-tool` under active scopes.
- 断言重点：old flow cannot be reintroduced through skill or router feedback.
- 测试类型：regression.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runless_architecture_residue_scan`, `tests/test_runtime_skills.py::RuntimeSkillsTests::test_shared_tool_skills_teach_env_tool_not_prepare_persist`.

### `BBTS-CLI-001`: CLI and status expose current action surfaces

- 测试 ID：`BBTS-CLI-001`
- 覆盖需求：`REQ-003`, `REQ-018`, `REQ-026`
- 用户 / 系统场景：A skill-following host checks the actual runtime command surface.
- 前置条件：local scripts are runnable.
- 输入：`python3 scripts/env/client.py buddybox --help`, `python3 scripts/turn_runtime.py status`.
- 预期输出或状态变化：buddybox help lists `desc`, `list`, `read`, `write`, `delete`; status shows `env_tools.buddybox.operations` with the same action set and no `search`.
- 断言重点：skill guidance matches executable runtime.
- 测试类型：CLI/main path.
- 建议测试文件路径和测试名称：`tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog`.

### `BBTS-GREP-001`: active surfaces exclude direct-bypass and trigger phrases

- 测试 ID：`BBTS-GREP-001`
- 覆盖需求：`REQ-005`, `REQ-006`, `REQ-007`, `REQ-031`, `REQ-035`
- 用户 / 系统场景：Future edits must not smuggle trigger routing or direct buddybox root mutation into active guidance.
- 前置条件：repo active scopes exist.
- 输入：`README.md`, `AGENTS.md`, `scripts`, `framework`, `buddyswitch`, `tools` (active surfaces only; exclude `tests` to avoid negative-assert literal noise), excluding `docs/memo/**` and `docs/spec/**`.
- 预期输出或状态变化：no active hit for hardcoded trigger phrases; no active guidance says to bypass env tools for buddybox writes.
- 断言重点：grep gate protects from regression outside the focused tests.
- 测试类型：regression scan.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_no_hardcoded_intent_to_buddybox_phrase_routing`.

### `BBTS-REG-001`: existing native skill behavior remains intact

- 测试 ID：`BBTS-REG-001`
- 覆盖需求：`REQ-030`
- 用户 / 系统场景：Adding buddybox-tool should not break existing shared and buddy-specific skills.
- 前置条件：manifest has existing skills and launcher fake Codex path.
- 输入：runtime start for every buddy.
- 预期输出或状态变化：installed skills equal manifest `skills` list for each buddy; `track-tool`, `artifact-tool`, `task-tool`, `handoff-tool` still exist where expected; removed manager/run tools remain absent.
- 断言重点：new shared skill is additive to native skill materialization, not a replacement engine.
- 测试类型：launcher regression.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`.

## 5. 负向与边界测试

- 缺失数据：`buddybox.write` without `content` or `content_base64` rejects with `E_BUDDYBOX_PAYLOAD`; no file is created.
- 无效状态：foreign prefix `dev/...` from active `pm` rejects with `E_BUDDYBOX_SCOPE`; existing foreign file remains unchanged and content is not leaked.
- 重复操作：second write to same file reports `overwrote == True`; second delete reports `deleted == False` and `state_changed == False`.
- 顺序敏感行为：write then read confirms exact path; list returns summary rows only; delete then read rejects missing file.
- 空输入：empty path rejects; empty list path defaults to active buddy prefix; empty buddybox workspace desc returns `file_count == 0`.
- 路径异常：absolute path, traversal `../x`, internal traversal `pm/../x`, symlink escape, and directory delete reject without state mutation.
- 配置异常：manifest missing `buddybox-tool` row or buddy membership fails manifest tests; runtime materialization missing directory fails launcher test.
- 运行状态异常：unsupported env tool/action/args shape returns current discovery guidance and no retired prepare wording.
- 外部依赖异常：no browser/search external dependency is required for this task; `buddybox.search` is not added and no network access is part of verification.

## 6. 作弊防护

- Manifest tests compute buddybox-capable buddies from permissions, so adding a future buddy with buddybox permissions but no skill fails.
- Launcher tests compare installed runtime skill directories exactly to manifest skill ids and byte-compare source/target directories, so a fake marker directory cannot pass.
- Skill tests check both required positive guidance and forbidden negative patterns, preventing a file that only contains keywords from passing while teaching bypasses.
- Context tests assert compact summary and full get/status surfaces separately, preventing schema duplication in the wrong surface.
- Buddybox integration tests assert actual filesystem state under the runtime root, not just response strings.
- Rejection tests seed foreign private files and assert they remain unchanged and unreadable, preventing implementations that only fake error codes.
- PM decision test checks semantic signals and output state, not a fixed phrase router.
- Search tests assert current action set and conditional skill wording, preventing speculative `buddybox.search` registration without full service/tests.
- Grep gates scan active source/guidance excluding memo/spec history, preventing hardcoded trigger phrases and retired lifecycle wording from reappearing.
- Tests cover text and binary payloads, multiple buddies, success and rejection paths, and repeated operations; a hardcoded happy-path response cannot satisfy the suite.

## 7. 验证命令清单

Focused skill/manifest verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

Focused semantic/response verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_buddybox_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_host_decision_surface_product_mode.py -q
```

Broader regression verification:

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
  tests/test_host_decision_surface_product_mode.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py -q
```

Active surface residue scan:

```bash
rg -n "prepare\\.runtime_context\\.env_tools|prototype means|quickly build means|route prototype to buddybox|always create artifact" \
  README.md AGENTS.md scripts framework buddyswitch tools \
  -g '!docs/memo/**' -g '!docs/spec/**'
```

Expected residue scan result: no matches and `rg` exit code `1` on active surfaces (excluding `tests` where negative assertions intentionally include forbidden literals).

Final verification before completion:

```bash
git status --short --branch
python3 scripts/env/client.py buddybox --help
python3 scripts/turn_runtime.py status
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
  tests/test_host_decision_surface_product_mode.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py -q
```

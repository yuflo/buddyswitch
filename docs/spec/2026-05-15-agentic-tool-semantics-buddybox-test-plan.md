# Agentic Tool Semantics And Buddybox Test Plan

## 1. 测试设计原则

- Tests start from the memo's externally observable contract: host-facing semantics must let the host distinguish private active-buddy local files from product-readable deliverables without phrase routing.
- Tests verify visible surfaces: `context.summarize`, `context.get`, `scripts/turn_runtime.py status`, env.tool responses, runtime AGENTS text, shared skill materialization, role contracts, router feedback, persisted local file state.
- Tests assert behavior and state, not internal call counts. A passing implementation must expose the right semantic signals, keep summaries compact, write private buddybox files only under the active buddy root, and preserve artifact promotion as conditional.
- Tests must not be reverse-engineered from implementation shortcuts. They use several surfaces together so hardcoding one string in one file cannot satisfy the suite.
- Tests cover negative and boundary behavior: unsupported router payloads, foreign buddy paths, content-free desc/list responses, empty context summary, duplicate delete, missing/invalid payloads, and stale retired wording.
- Tests use multiple buddies (`pm`, `dev`, `design`, `market`, `test`) so behavior cannot be hardcoded to PM.
- Tests preserve SHARP scope: no generic routing engine, no phrase matcher, no new compatibility path, and no broad refactor beyond semantic surfaces.

## 2. 需求覆盖矩阵

All requirements are suitable for automated testing. Manual verification is supplemental for launched product-mode confidence and does not replace automated proof.

| Requirement | Automated coverage |
| --- | --- |
| `REQ-001` | `ATS-SEM-001`, `ATS-PM-001`, `ATS-GREP-001` |
| `REQ-002` | `ATS-AGENTS-001`, `ATS-SKILL-001` |
| `REQ-003` | `ATS-AGENTS-001`, `ATS-GREP-001` |
| `REQ-004` | `ATS-CTX-001`, `ATS-COMPACT-NEG-001`, `ATS-PM-001` |
| `REQ-005` | `ATS-CTX-001`, `ATS-PM-001` |
| `REQ-006` | `ATS-CTX-001`, `ATS-PM-001` |
| `REQ-007` | `ATS-CTX-001` |
| `REQ-008` | `ATS-COMPACT-NEG-001` |
| `REQ-009` | `ATS-CLI-001`, `ATS-CTX-001` |
| `REQ-010` | `ATS-CLI-001` |
| `REQ-011` | `ATS-SEM-001` |
| `REQ-012` | `ATS-SEM-001` |
| `REQ-013` | `ATS-SEM-001`, `ATS-RESP-001` |
| `REQ-014` | `ATS-SEM-002` |
| `REQ-015` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-016` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-017` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-018` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-019` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-020` | `ATS-SEM-002`, `ATS-RESP-002` |
| `REQ-021` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-022` | `ATS-SEM-002`, `ATS-RESP-001` |
| `REQ-023` | `ATS-COMPACT-NEG-001`, `ATS-RESP-001` |
| `REQ-024` | `ATS-RESP-001`, `ATS-PM-001` |
| `REQ-025` | `ATS-RESP-002`, `ATS-GREP-001` |
| `REQ-026` | `ATS-RESP-001`, `ATS-RESP-002` |
| `REQ-027` | `ATS-RESP-001`, `ATS-RESP-002` |
| `REQ-028` | `ATS-RESP-001`, `ATS-PM-001` |
| `REQ-029` | `ATS-SEM-001`, `ATS-RESP-001`, `ATS-PM-001` |
| `REQ-030` | `ATS-RESP-002` |
| `REQ-031` | `ATS-SKILL-001` |
| `REQ-032` | `ATS-SKILL-001` |
| `REQ-033` | `ATS-SKILL-002` |
| `REQ-034` | `ATS-ROLE-001` |
| `REQ-035` | `ATS-ROLE-001` |
| `REQ-036` | `ATS-ROUTER-001`, `ATS-GREP-001` |
| `REQ-037` | `ATS-PM-001` |
| `REQ-038` | `ATS-HANDOFF-001`, `ATS-PM-001` |
| `REQ-039` | `ATS-PM-001`, `ATS-GREP-001` |
| `REQ-040` | `ATS-GREP-001`, `ATS-SEM-001` |
| `REQ-041` | `ATS-FINAL-001` |
| `REQ-042` | `ATS-WORKTREE-001` |

## 3. 测试分层

### 单元测试

Purpose: prove semantic registry quality, compact affordance data shape, manifest/shared skill contracts, role contract text, and grep-level active surface constraints without launching a broker.

Coverage:

- `scripts/env/tools/semantics.py`
- `scripts/env/tools/contracts.py`
- `buddyswitch/manifest.toml`
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- `framework/contracts/{pm,design,dev,test,market}.md`
- active source/doc residue scans in `tests/test_repo_consistency.py`

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py -q
```

### 集成测试

Purpose: prove broker-routed runtime behavior exposes the semantic surfaces and response contracts as the host sees them.

Coverage:

- `runtime_kernel.broker.dispatch_runtime_request`
- `scripts/env/tools/router.py`
- `scripts/env/services/context.py`
- `scripts/env/services/buddybox.py`
- `tests/runtime_root_test_helper.py`

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

Purpose: verify public commands and launcher-visible runtime packages.

Coverage:

- `python3 scripts/env/client.py context summarize`
- `python3 scripts/env/client.py context get`
- `python3 scripts/turn_runtime.py status`
- `python3 scripts/runtime_agents.py validate-all`
- launcher skill materialization for every buddy

Run:

```bash
python3 scripts/runtime_agents.py validate-all
python3 scripts/turn_runtime.py status
python3 scripts/env/client.py context summarize --help
python3 scripts/env/client.py context get --help
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_agents.py \
  tests/test_runless_runtime_contract.py \
  tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

### 回归测试

Purpose: prove the semantic upgrade does not regress runless product tools, buddybox privacy, handoff boundary, artifact provenance, launcher profile behavior, or repo-wide active-surface constraints.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_memory_removal_contract.py \
  tests/test_env_tool_router.py \
  tests/test_runless_runtime_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py \
  tests/test_handoff_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy \
  tests/test_repo_consistency.py -q
```

### 手动验证

Purpose: confirm a real launcher-managed PM workspace exposes the intended route map and semantic flow.

Steps:

1. Run `pwd` and confirm `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`.
2. Run `git branch --show-current` and confirm `dev_buddy_mem`.
3. Run `./buddyswitch-codex instance start --buddy pm`.
4. In the launched workspace, run `python3 scripts/env/client.py context summarize`.
5. Confirm `tool_affordances.buddybox.use_for` mentions private local prototypes and `tool_affordances.buddybox.promote_with` mentions `artifact.create_revision`.
6. Run `python3 scripts/env/client.py context get` and confirm `tool_catalog.buddybox.action_semantics.write.inputs_explained` explains `content`, `content_base64`, and `content_type`.
7. Run `python3 scripts/env/client.py buddybox desc`.
8. Confirm desc/list responses do not include file bodies and write responses include structured `allowed_next_action_options`.

## 4. 详细测试用例

### `ATS-WORKTREE-001`: worktree isolation guard

- 测试 ID：`ATS-WORKTREE-001`
- 覆盖需求：`REQ-042`
- 用户 / 系统场景：Implementation must run in the requested worktree and must not touch main.
- 前置条件：Repository is checked out with Git worktrees.
- 输入：`pwd`, `git branch --show-current`, `git worktree list --porcelain`.
- 预期输出或状态变化：cwd is `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`; branch is `dev_buddy_mem`; current root is not the primary checkout.
- 断言重点：Execution location and branch match user request.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_worktree_isolated_for_dev_worktree`.

### `ATS-CTX-001`: summarize exposes compact tool affordances

- 测试 ID：`ATS-CTX-001`
- 覆盖需求：`REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `REQ-037`
- 用户 / 系统场景：Host starts a turn with compact context and needs to decide whether to inspect buddybox or artifact.
- 前置条件：Runtime instance active buddy is `dev`.
- 输入：Broker `env.tool` request `{"tool":"context","action":"summarize","args":{}}`.
- 预期输出或状态变化：Response has `tool_affordances.buddybox` and `tool_affordances.artifact`; buddybox row mentions private local drafts/prototypes/exports/reports/logs/generated/binary outputs; artifact row mentions product-readable deliverables; no state changes.
- 断言重点：Compact summary has enough semantic signal without full schema bloat.
- 测试类型：integration.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_compact_tool_affordances`.

### `ATS-COMPACT-NEG-001`: summarize avoids full catalog and file bodies

- 测试 ID：`ATS-COMPACT-NEG-001`
- 覆盖需求：`REQ-008`, `REQ-023`
- 用户 / 系统场景：Host reads default summary in a workspace with buddybox files.
- 前置条件：Active buddy `dev`; file exists under `buddyswitch/local/buddybox/dev/notes/context.txt`.
- 输入：Broker `context.summarize`.
- 预期输出或状态变化：Response includes `buddybox_desc` and `tool_affordances`; response does not include `payload_fields`, `action_semantics`, `content`, `content_base64`, or `files`.
- 断言重点：Default summary stays high-signal and does not become a file browser or tool encyclopedia.
- 测试类型：integration and negative.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_tool_affordances_stay_compact`.

### `ATS-CLI-001`: full inspect surfaces remain available

- 测试 ID：`ATS-CLI-001`
- 覆盖需求：`REQ-009`, `REQ-010`
- 用户 / 系统场景：Host needs full payload/action semantics after compact summary.
- 前置条件：Repo root with Python available.
- 输入：`context.get` broker request and `python3 scripts/turn_runtime.py status`.
- 预期输出或状态变化：`context.get` includes `tool_catalog` and `operation_semantics`; `turn_runtime.py status` JSON includes `env_tools.buddybox.action_semantics.write.inputs_explained`.
- 断言重点：Layered discovery keeps inspect layer intact.
- 测试类型：integration and CLI.
- 建议测试文件路径和测试名称：`tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_exposes_full_tool_catalog_for_inspection`, `tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_status_exposes_env_tools_catalog`.

### `ATS-SEM-001`: buddybox capability semantics cover generalized file outputs

- 测试 ID：`ATS-SEM-001`
- 覆盖需求：`REQ-001`, `REQ-011`, `REQ-012`, `REQ-013`, `REQ-029`, `REQ-039`, `REQ-040`
- 用户 / 系统场景：Host reads full tool catalog to decide whether buddybox fits private file output.
- 前置条件：Import `env.tools.contracts`.
- 输入：`contracts.env_tools_description()["buddybox"]`.
- 预期输出或状态变化：Capability text contains active buddy, private, local workspace, drafts, lightweight prototypes, exports, reports, logs, generated files, binary outputs, not collaborative, not visible to other buddies, not product object, product-readable artifact promotion.
- 断言重点：Semantics describe capability meaning and reject phrase routing.
- 测试类型：unit semantic contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_cover_file_output_affordances_and_output_meanings`.

### `ATS-SEM-002`: buddybox action semantics explain inputs and output meanings

- 测试 ID：`ATS-SEM-002`
- 覆盖需求：`REQ-014`, `REQ-015`, `REQ-016`, `REQ-017`, `REQ-018`, `REQ-019`, `REQ-020`, `REQ-021`, `REQ-022`
- 用户 / 系统场景：Host inspects action-level semantics before forming payloads.
- 前置条件：Import `env.tools.contracts`.
- 输入：`contracts.env_tools_description()["buddybox"]["action_semantics"]`.
- 预期输出或状态变化：Each action has action-specific `inputs_explained`, `side_effects`, `risk_hints`, `success_means`, and `common_failures`; path/content/content_base64/content_type/encoding meanings are explicit.
- 断言重点：A host can form valid calls from semantics alone.
- 测试类型：unit semantic contract.
- 建议测试文件路径和测试名称：`tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_action_semantics_explain_input_formats_and_output_fields`.

### `ATS-RESP-001`: buddybox success responses expose structured next actions

- 测试 ID：`ATS-RESP-001`
- 覆盖需求：`REQ-013`, `REQ-015`, `REQ-016`, `REQ-017`, `REQ-018`, `REQ-019`, `REQ-023`, `REQ-024`, `REQ-026`, `REQ-027`, `REQ-028`, `REQ-029`
- 用户 / 系统场景：PM writes and reads a private page prototype.
- 前置条件：Active buddy `pm`; empty local buddybox root.
- 输入：`buddybox.write path="pm/prototypes/simple.html"`, `buddybox.read`, `buddybox.list`, `buddybox.desc`, `buddybox.delete`.
- 预期输出或状态变化：Write creates file under local pm root; desc/list return no file body; write/read responses contain structured options for private iteration and conditional artifact promotion; delete reports actual state transition.
- 断言重点：Options are machine-readable and promotion is conditional.
- 测试类型：broker integration.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_text_and_binary_lifecycle_uses_local_root`, `tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_success_responses_cover_read_write_and_target_scoped_evidence`.

### `ATS-RESP-002`: buddybox rejections guide safe retry without state change

- 测试 ID：`ATS-RESP-002`
- 覆盖需求：`REQ-020`, `REQ-025`, `REQ-026`, `REQ-027`, `REQ-030`
- 用户 / 系统场景：PM attempts to read/list/write/delete Dev's private buddybox path.
- 前置条件：`buddyswitch/local/buddybox/dev/reports/report.txt` exists; active buddy is `pm`.
- 输入：`buddybox.list path="dev"`, `buddybox.read path="dev/reports/report.txt"`, `buddybox.write path="dev/reports/new.txt"`, `buddybox.delete path="dev/reports/report.txt"`.
- 预期输出或状态变化：All responses are rejected with `state_changed=false`; structured options include `buddybox.desc` and retry of original action under active buddy root; Dev file remains unchanged.
- 断言重点：Rejections steer through runtime semantics and never direct filesystem bypass.
- 测试类型：broker integration and negative.
- 建议测试文件路径和测试名称：`tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_pm_cannot_read_list_write_or_delete_foreign_private_paths`.

### `ATS-SKILL-001`: shared buddybox-tool skill content is exact and runless

- 测试 ID：`ATS-SKILL-001`
- 覆盖需求：`REQ-002`, `REQ-003`, `REQ-031`, `REQ-032`
- 用户 / 系统场景：Runtime skill package teaches buddybox operations without bloating AGENTS.
- 前置条件：`buddyswitch/manifest.toml` and skill files exist.
- 输入：Read manifest and `buddyswitch/skills/shared/buddybox-tool/SKILL.md`.
- 预期输出或状态变化：Skill row exists; skill text teaches CLI, operations, active buddy path, content/base64/content_type/encoding, artifact promotion, response fields; text excludes prepare/persist and phrase triggers.
- 断言重点：Tool knowledge lives in skill, not runtime AGENTS.
- 测试类型：unit manifest/skill contract.
- 建议测试文件路径和测试名称：`tests/test_runtime_skills.py::RuntimeSkillsTests::test_buddybox_tool_skill_teaches_private_local_file_workflow`.

### `ATS-SKILL-002`: buddybox-tool materializes for every buddybox-capable buddy

- 测试 ID：`ATS-SKILL-002`
- 覆盖需求：`REQ-032`, `REQ-033`
- 用户 / 系统场景：Launcher starts each buddy workspace and installs runtime skills from manifest.
- 前置条件：Fake Codex/browser launcher test harness.
- 输入：`./buddyswitch-codex instance start --buddy <buddy> -- debug prompt-input ...` for every manifest buddy.
- 预期输出或状态变化：Runtime `.agents/skills` contains exactly manifest skill ids and includes `buddybox-tool` for each buddy with buddybox permissions.
- 断言重点：Skill registration reaches product runtime.
- 测试类型：launcher integration.
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`.

### `ATS-AGENTS-001`: runtime AGENTS stay short and route to discovery surfaces

- 测试 ID：`ATS-AGENTS-001`
- 覆盖需求：`REQ-002`, `REQ-003`
- 用户 / 系统场景：Host reads runtime AGENTS at session start.
- 前置条件：Five buddy AGENTS templates exist.
- 输入：Read `tools/launcher/assets/buddies/*/AGENTS.md`; run `python3 scripts/runtime_agents.py validate-all`.
- 预期输出或状态变化：Each file contains `context summarize` and either `context get` or `turn_runtime.py status` for full tool catalog; each file excludes payload schemas, action semantics dumps, and phrase triggers.
- 断言重点：AGENTS is a route map, not a tool encyclopedia.
- 测试类型：unit text contract and CLI.
- 建议测试文件路径和测试名称：`tests/test_runtime_agents.py::RuntimeAgentsValidationTests::test_runtime_agents_point_to_runless_context_discovery`.

### `ATS-ROLE-001`: role contracts contain short role-specific boundary sentences

- 测试 ID：`ATS-ROLE-001`
- 覆盖需求：`REQ-034`, `REQ-035`
- 用户 / 系统场景：Framework role contract tells each buddy how to use buddybox without duplicating tool docs.
- 前置条件：Role contract Markdown files exist.
- 输入：Read `framework/contracts/{pm,design,dev,test,market}.md`.
- 预期输出或状态变化：PM contains PM-owned private local drafts/lightweight prototypes and artifact product-readable boundary; other roles contain role-specific private file types and artifact deliverable boundary; no full schemas.
- 断言重点：Contracts are concise and role-specific.
- 测试类型：repo consistency text contract.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_role_contracts_keep_buddybox_guidance_short_and_role_specific`.

### `ATS-ROUTER-001`: router feedback points to current discovery surfaces

- 测试 ID：`ATS-ROUTER-001`
- 覆盖需求：`REQ-036`
- 用户 / 系统场景：Host sends malformed env.tool payload and needs recovery guidance.
- 前置条件：Runtime instance active buddy `dev`.
- 输入：Missing tool, unsupported tool, missing action, unsupported action, non-object args.
- 预期输出或状态变化：Responses reject without state mutation; retry guidance mentions `context.get.tool_catalog`, `context.summarize.tool_affordances`, or `python3 scripts/turn_runtime.py status`; no response mentions `prepare.runtime_context.env_tools`.
- 断言重点：Runtime feedback has current runless discovery references.
- 测试类型：router integration and negative.
- 建议测试文件路径和测试名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_rejects_malformed_envelope_without_state_mutation`.

### `ATS-PM-001`: PM prototype scenario is supported by semantics, not phrase routing

- 测试 ID：`ATS-PM-001`
- 覆盖需求：`REQ-001`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-024`, `REQ-028`, `REQ-029`, `REQ-037`, `REQ-038`, `REQ-039`, `REQ-040`
- 用户 / 系统场景：PM buddy receives a user request to quickly build a simple page prototype first.
- 前置条件：Active buddy `pm`; PM project access is read-only.
- 输入：Read PM AGENTS/profile signals, dispatch `context.summarize`, dispatch `context.get`, then call `buddybox.write` with `pm/prototypes/simple-page.html`.
- 预期输出或状态变化：Semantic surfaces identify buddybox as private local prototype/file output and artifact as product-readable path; write creates local file; response options include `buddybox.read`, `buddybox.list`, and conditional `artifact.create_revision`.
- 断言重点：No production code or docs contain hardcoded phrase-routing rules.
- 测试类型：product-mode decision surface integration.
- 建议测试文件路径和测试名称：`tests/test_host_decision_surface_product_mode.py::HostDecisionSurfaceProductModeTests::test_pm_page_prototype_decision_surface_prefers_private_buddybox_without_phrase_rule`.

### `ATS-HANDOFF-001`: private buddybox paths remain non-readable handoff payloads

- 测试 ID：`ATS-HANDOFF-001`
- 覆盖需求：`REQ-038`
- 用户 / 系统场景：Host tries to hand off a private buddybox path as if target buddy could read it.
- 前置条件：Existing handoff and source_ref privacy boundary tests.
- 输入：`handoff.validate` or `handoff.create` with `source_refs=[{"type":"buddybox","path":"design/handoff/handoff.txt"}]`.
- 预期输出或状态变化：Request rejects with `E_SOURCE_REFS`; message explains buddybox private provenance is not read authority; no handoff is created.
- 断言重点：Semantic upgrade does not weaken cross-buddy read boundary.
- 测试类型：integration regression.
- 建议测试文件路径和测试名称：`tests/test_handoff_env_tool.py::HandoffEnvToolTests::test_handoff_rejects_retired_private_path_list_and_buddybox_source_refs`.

### `ATS-GREP-001`: active surfaces reject stale and hardcoded routing wording

- 测试 ID：`ATS-GREP-001`
- 覆盖需求：`REQ-001`, `REQ-003`, `REQ-025`, `REQ-036`, `REQ-039`, `REQ-040`
- 用户 / 系统场景：Repository active surfaces should not teach retired runtime context or phrase triggers.
- 前置条件：Repo root.
- 输入：`rg` scans over `scripts`, `tools`, `framework`, `buddyswitch`, `README.md`, `AGENTS.md`, excluding `docs/memo/**` and `docs/spec/**`.
- 预期输出或状态变化：No active hit for `prepare.runtime_context.env_tools`, `prototype means`, `quickly build means`, `route prototype to buddybox`, `always create artifact`, or direct filesystem bypass wording.
- 断言重点：No hidden prompt or code shortcut replaces semantic discovery.
- 测试类型：repo consistency.
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_active_runtime_feedback_points_to_current_tool_discovery_surfaces`, `tests/test_repo_consistency.py::RepoConsistencyTests::test_no_hardcoded_intent_to_buddybox_phrase_routing`.

### `ATS-FINAL-001`: focused and broader verification gates

- 测试 ID：`ATS-FINAL-001`
- 覆盖需求：`REQ-041`
- 用户 / 系统场景：Implementation is ready to report completion.
- 前置条件：All code/doc changes applied in `dev_buddy_mem`.
- 输入：Focused and broader pytest commands from section 7.
- 预期输出或状态变化：All selected tests pass with exit code 0; no skipped failing check is used as completion evidence.
- 断言重点：Completion claim is backed by fresh command output.
- 测试类型：verification gate.
- 建议测试文件路径和测试名称：shell command gate, no new test file.

## 5. 负向与边界测试

- Missing data: `context.summarize` in an empty runtime still returns `tool_affordances`; `buddybox.desc` with empty root reports zero files and no content.
- Invalid state: unsupported env.tool `tool`, unsupported `action`, missing action, and non-object `args` reject without state mutation and point to current discovery surfaces.
- Duplicate operations: repeated `buddybox.delete` reports already absent and `state_changed=false`; repeated write reports `overwrote=true`.
- Concurrent or order-sensitive behavior: write then read then list then delete validates response options and state transitions in sequence; stale options cannot pass because assertions inspect actual filesystem state and response fields after each operation.
- Empty input and empty collection: empty buddybox root, absent candidate tracks, empty `args`, and empty optional filters still produce deterministic summary and desc payloads.
- Path and permission exceptions: absolute paths, traversal, foreign buddy prefixes, symlink escape, invalid base64, invalid read encoding, and directory delete reject with no state change.
- Configuration exceptions: manifest must register `buddybox-tool`; every buddy with buddybox permissions must materialize it; runtime AGENTS validation rejects missing full-catalog route wording.
- External dependency exceptions: browser/search is not required for these tests; launcher skill materialization uses existing fake Codex/browser harness.

## 6. 作弊防护

- Compact affordance tests assert several independent strings across `context.summarize`, `context.get`, and PM scenario flow, so hardcoding one response string cannot satisfy all behavior.
- PM scenario writes an actual file and asserts filesystem state plus response options, so semantic text alone cannot pass.
- Structured option tests validate `tool`, `action`, `mutates`, `reason`, `source_refs`, and `preconditions`, not just field existence.
- Grep guards reject phrase-routing shortcuts and retired discovery references across active source and docs.
- Tests use multiple buddies and foreign-path rejections so PM cannot be treated as a special cross-buddy reader.
- Tests verify desc/list omit file bodies and read returns content/base64 only for one requested file.
- Tests assert artifact promotion is conditional by checking option reason text does not contain mandatory language.
- Tests do not only cover happy path; they include malformed router payloads, invalid buddybox payloads, old/foreign path boundaries, empty roots, and repeated operations.
- Assertions must not be weakened to match implementation; the expected behavior is the memo contract.

## 7. 验证命令清单

Focused semantic/context/response loop:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_host_decision_surface_product_mode.py -q
```

Focused guidance/skill/router loop:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_env_tool_router.py \
  tests/test_repo_consistency.py -q
```

CLI and launcher-visible checks:

```bash
python3 scripts/runtime_agents.py validate-all
python3 scripts/turn_runtime.py status
python3 scripts/env/client.py context summarize --help
python3 scripts/env/client.py context get --help
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

Broader relevant verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_memory_removal_contract.py \
  tests/test_env_tool_router.py \
  tests/test_runless_runtime_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py \
  tests/test_handoff_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy \
  tests/test_repo_consistency.py -q
```

Final completion gate:

```bash
pwd
git branch --show-current
git status --short
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_memory_removal_contract.py \
  tests/test_env_tool_router.py \
  tests/test_runless_runtime_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py \
  tests/test_handoff_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_buddyswitch_launcher.py::BuddyswitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy \
  tests/test_repo_consistency.py -q
```

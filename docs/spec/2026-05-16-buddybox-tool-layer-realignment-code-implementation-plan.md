# Buddybox Tool Layer Realignment Code Implementation Plan

> **For agentic workers:** Implement this plan in `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem` on branch `dev_buddy_mem`. Use test-first changes for behavior, keep each phase runnable, and do not preserve the old `path` or shared-state buddybox contract.

**Goal:** Rebuild buddybox as an active-instance-local, tool-owned private file capability addressed by logical names, with context and responses exposing capability semantics instead of filesystem contracts.

**Architecture:** Product objects remain shared runtime state through existing object projections. Buddybox files move to the active instance workspace as real local directories, and the service resolves `logical_name` under the active buddy root internally. Host discovery uses capability metadata, structured affordances, and structured rejection fields rather than path roots, symlink targets, or fixed workflow prose.

**Tech Stack:** Python env services and broker dispatch, shell launcher workspace setup, Python CLI, TOML/JSON runtime contracts, Markdown runtime guidance and skills, pytest/unittest.

---

## 1. 任务目标

完成后，`buddybox` 是 active buddy 的工具层私有文件能力：host 只提供 `logical_name`，工具负责把它解析到当前实例工作区内的 active buddy 私有目录，并通过结构化响应说明可见性、生命周期、产品状态影响和可选后续能力。当前核心瓶颈是 buddybox 仍被暴露成路径契约和共享状态投影，host 必须理解 active buddy 前缀、workspace 路径或 shared state 形态；这是最重要的问题，因为它会让私有文件、产品可读 artifact、handoff 协作状态三者的边界继续混淆。

本计划采用直接 breaking replacement：删除 host-facing `path` 输入和 active buddy 前缀要求，改为 `logical_name`。源 memo 已说明该方向符合 SHARP forward，当前仓库没有外部 API 或真实数据迁移承诺要求保留双路径。

## 2. 需求提取

- `REQ-001`：`buddybox` 必须被定义为 active buddy 的 tool-backed private file capability，不是 host-visible filesystem contract、共享产品状态、handoff payload 或 artifact-readable path。
- `REQ-002`：active buddybox storage 必须位于 active instance workspace 内，生命周期为 `active_instance_workspace`，不再派生自 `${BUDDYSWITCH_SHARED_ROOT}/state`。
- `REQ-003`：launcher 创建 `<instance workspace>/buddyswitch/local/buddybox/<active_buddy>/` 时必须创建真实目录，不得创建指向 shared state 的 symlink。
- `REQ-004`：shared state 下已有 `buddyswitch/local/buddybox/**` 或旧 `buddyswitch/content/buddybox/**` 只作为 legacy unmanaged state；本任务不迁移、不兼容读取、不自动清理。
- `REQ-005`：workspace rebuild 可以在同一实例内保留 workspace-local buddybox 文件，但不得把它们放入 shared state 或跨实例同步。
- `REQ-006`：host-facing buddybox payload 使用 `logical_name`，不使用 `path`，也不要求或接受 `pm/`、`dev/`、`design/`、`market/`、`test/` 等 buddy 前缀。
- `REQ-007`：工具内部负责 active buddy namespace resolution：`logical_name` 解析到 active buddy 私有目录内，response 中不暴露 absolute path、workspace root、shared root 或 symlink target。
- `REQ-008`：`logical_name` 必须拒绝空值、非字符串、绝对路径、`..` traversal、解析出 active buddy 根以外的目标、以及以任一 buddy id 作为第一段的 legacy buddy prefix。
- `REQ-009`：如果 active buddy 私有目录内存在 symlink，read/list/write/delete 必须拒绝或跳过会逃逸 active buddy 私有根的目标，且 rejection 不泄露目标文件内容。
- `REQ-010`：`buddybox.write` 支持 `content` UTF-8 text 与 `content_base64` binary，两者必须互斥，写入时创建父目录并返回 `created` 与 `overwrote`。
- `REQ-011`：`buddybox.read` 只读取一个 exact private file，按 `encoding=auto|utf-8|base64` 返回 `content` 或 `content_base64`。
- `REQ-012`：`buddybox.list` 只返回 active buddy 私有文件 summary rows，不返回 content body；可用 `logical_name` 作为可选 prefix filter。
- `REQ-013`：`buddybox.delete` 只删除一个 exact private file；重复 delete 显式返回 `deleted=false` 和 `state_changed=false`。
- `REQ-014`：所有 buddybox 操作不得创建、更新或删除 `track`、`task`、`artifact`、`handoff`、`context`、`evidence` 等产品或协作对象。
- `REQ-015`：buddybox success response 必须包含 `tool`、`action`、`active_buddy`、`object_kind`、`logical_name` 或 capability summary、`visibility`、`owner_scope`、`lifetime_scope`、`durability`、`product_readable`、`cross_buddy_readable`、`mutates_product_state`、`mutated_product_objects`、`state_changed`。
- `REQ-016`：buddybox success response 必须用 structured affordances 描述可选能力，例如 private read/list/write/delete 和条件式 `artifact.create_revision`，不得用命令式 prose 规定固定流程。
- `REQ-017`：buddybox rejection response 必须包含 machine-readable `error.code`、`error.class`、`boundary`、`state_changed=false`、`mutates_product_state=false`、`retryable`、`correctable_fields`、`why_blocked`、`impact`、`alternative_capabilities`。
- `REQ-018`：rejection guidance 不得建议 host 使用 `<active_buddy>/...` 路径、直接编辑 `buddyswitch/local/buddybox/**`、检查 shared runtime state、或把 buddybox name 当成 cross-buddy readable reference。
- `REQ-019`：`context.get`、`context.summarize`、`context.list_sources`、tool catalog 与 `operation_semantics` 必须把 buddybox 描述为 capability，包含 `capability`、`owner_scope`、`lifetime_scope`、`visibility`、`product_readable`、`cross_buddy_readable`、`mutates_product_state`、`supports`。
- `REQ-020`：context 和 semantics 不得暴露 `source_of_truth="buddyswitch/local/buddybox/<active_buddy>/**"`、`logical_root`、absolute path、shared root 或 workspace root。
- `REQ-021`：operation semantics 必须解释 `logical_name` 的含义、payload 字段、side effects、success meaning、common failures、risk hints，并且不得要求 `<active_buddy>/...`。
- `REQ-022`：`context.summarize.tool_affordances` 必须足够让 host 区分 private buddybox files、product-readable artifacts、handoff collaboration state、project source writes；不得编码 phrase-to-tool SOP。
- `REQ-023`：artifact 是内容需要 product-readable 或 cross-buddy-readable 时的显式 carrier；artifact 可保存 buddybox private provenance，但必须使用 `logical_name`、`private_to_buddy=<active_buddy>`、`read_grant=false`。
- `REQ-024`：handoff 不得接受 buddybox private file 作为 target buddy readable payload；`handoff.validate` 与 `handoff.create` 必须拒绝 `source_refs.type="buddybox"`。
- `REQ-025`：不增加 generic permission framework、rule engine、phrase-to-tool router、workflow engine、MCP adapter layer 或长期兼容 wrapper。
- `REQ-026`：AGENTS、README、role contracts 和 runtime skills 只能作为 route map；不得编码 buddybox filesystem roots、完整 schemas、固定 SOP 或 artifact promotion 强制流程。
- `REQ-027`：保持已有 runless env tool model：`env.tool`、`ping`、`status`、explicit ids、product objects via env tools。
- `REQ-028`：所有 buddy 的 buddybox permission surface 保持一致，不新增 PM 或 buddy-type 特例读取权。
- `REQ-029`：测试必须覆盖 launcher/storage boundary、service behavior、context/semantics、rejection recovery、host decision surface、guidance grep gates 和 main path regression。

## 3. 现状探索摘要

### 必须查看的关键路径

- `docs/memo/2026-05-16-buddybox-tool-layer-realignment-memo.md`：本任务需求源。
- `AGENTS.md`：SHARP forward、testing-bound、no verification no done、runtime state 不直接编辑。
- `README.md`：当前仍提到 active buddy private buddybox path。
- `scripts/env_store.py`：`STATE_ROOT` 负责 product objects，当前 `BUDDYBOX_LOCAL_DIR = LOCAL_ROOT / "buddybox"` 仍随 `STATE_ROOT` 派生。
- `scripts/runtime_kernel/dispatcher.py`：`_runtime_server_env()` 当前设置 `BUDDYSWITCH_STATE_ROOT=<shared_root>/state`，需要明确 workspace-local buddybox root。
- `scripts/env/services/buddybox.py`：当前已有 `desc/list/read/write/delete`、path safety、base64、symlink escape checks，但 payload、response、semantics 仍使用 `path` 与 active buddy prefix。
- `scripts/env/services/context.py`：`context_sources_desc()["buddybox"]` 仍返回 `source_of_truth` path，`buddybox_desc` 仍含 `logical_root`。
- `scripts/env/tools/contracts.py`：buddybox payload fields 仍是 `path`；returns 仍提到 path。
- `scripts/env/tools/semantics.py`：buddybox input semantics、side effects 与 common failures 仍围绕 `<active_buddy>/...` path。
- `scripts/env/client.py`：CLI 仍提供 `--path` for buddybox list/read/delete，write payload 仍读取 `path`。
- `scripts/env/tools/responses.py`：canonical response helper 当前支持 structured `allowed_next_action_options`，但 `error.class`、`correctable_fields`、`alternative_capabilities`、buddybox affordance shape 需要补齐。
- `scripts/env/services/source_refs.py` 与 `scripts/env_store.py`：buddybox provenance 仍使用 `path` 和 active buddy prefix。
- `scripts/env/services/artifacts.py`：artifact source_refs normalization 会接受 buddybox path provenance。
- `scripts/env/services/handoffs.py`：handoff 已拒绝 buddybox source_refs，需要保持并改用 `logical_name` error wording。
- `tools/launcher/workspace.sh`：`buddyswitch_workspace_install_active_buddybox_root()` 当前创建 shared state dir 并 symlink 到 workspace。
- `tools/launcher/codex_config.py` 与 `buddyswitch/env-profiles/*.json`：sandbox writable root 使用 `buddyswitch/local/buddybox/<buddy>` profile root，最终应指向 workspace real dir。
- `tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md`：当前编码 buddybox filesystem root。
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`：当前 CLI examples、payloads、rules 使用 `--path` 和 `<active_buddy>/...`。
- `buddyswitch/skills/{pm,design,dev,market,test}/**/SKILL.md`：多处编码 `buddyswitch/local/buddybox/<active-buddy>/**`。
- `framework/contracts/{pm,design,dev,market,test}.md`：当前列出 role-specific buddybox filesystem path。
- `tests/test_buddyswitch_launcher.py`：当前断言 workspace buddybox projection 是 shared state symlink。
- `tests/test_buddybox_env_tool.py`：当前 buddybox service tests 使用 `path` 与 active buddy prefix。
- `tests/test_context_binding_env_tool.py` 与 `tests/test_env_tool_identity.py`：当前断言 context source exposes buddybox source path。
- `tests/test_env_tool_semantic_contract.py`：当前断言 buddybox input semantics contains `path` and `prefix`。
- `tests/test_env_tool_response_contract.py`：当前 buddybox success response tests 使用 `path` 与 `durability="durable"`。
- `tests/test_artifact_env_tool.py` 与 `tests/test_handoff_env_tool.py`：source_refs boundary tests 使用 buddybox `path`。
- `tests/test_buddy_env_sandbox.py`：sandbox tests ensure only active buddy workspace path is writable.
- `tests/runtime_root_test_helper.py`：test sandbox patches `env_store.BUDDYBOX_LOCAL_DIR` and must follow the new workspace-root helper.

### 需要运行的探索和验证命令

- `git status --short --branch`
- `rg -n "buddybox|BUDDYBOX|logical_root|source_of_truth|allowed_next_actions|logical_name|--path|<active_buddy>" scripts tests tools framework buddyswitch README.md AGENTS.md`
- `python3 -m pytest tests/test_buddybox_env_tool.py -q`
- `python3 -m pytest tests/test_buddyswitch_launcher.py -q`
- `python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py -q`
- `python3 -m pytest tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_buddy_env_sandbox.py -q`

### 保留、替换、删除、迁移

- 保留：`buddybox.desc/list/read/write/delete` action set。
- 保留：UTF-8 text write/read、base64 binary write/read、exact file delete、summary-only list。
- 保留：active buddy privacy checks、symlink escape checks、no product object mutation。
- 保留：product object dirs under `buddyswitch/objects/**` as shared runtime state projections.
- 替换：`path` payload field with `logical_name` in service, CLI, contracts, semantics, tests, source_refs.
- 替换：active buddy prefix validation with tool-owned namespace resolution under active buddy root.
- 替换：buddybox root derivation from `STATE_ROOT` with instance workspace root derivation.
- 替换：buddybox shared state symlink creation with workspace-local real directory creation.
- 替换：`logical_root` and `source_of_truth` context fields with capability metadata.
- 替换：command-like buddybox `allowed_next_actions` strings with structured affordance objects and conditional alternatives.
- 删除：host-facing active buddy prefix examples such as `pm/prototypes/hero.html`.
- 删除：shared-state active buddybox symlink logic and tests that assert live symlink behavior.
- 删除：buddybox `path` source_refs in artifact provenance payloads.
- 不迁移：existing shared-state buddybox files and retired `buddyswitch/content/buddybox/**`.
- 不保留双路径：no `path` alias, no active-prefix compatibility parser, no hidden fallback to shared state.

## 4. 最终目标架构

### 最终文件结构与职责

- Modify `scripts/env_store.py`
  - Keep `STATE_ROOT`, `OBJECTS_ROOT`, `TRACKS_DIR`, `TASKS_DIR`, `ARTIFACT_OBJECTS_DIR`, `HANDOFF_OBJECTS_DIR` for product objects.
  - Add `runtime_workspace_root(instance_payload: dict[str, Any] | None = None) -> Path`.
  - Add `buddybox_local_dir(instance_payload: dict[str, Any] | None = None) -> Path`.
  - `runtime_workspace_root()` resolution order: `instance_payload["workspace_dir"]`, `BUDDYSWITCH_WORKSPACE_DIR`, `BUDDYSWITCH_RUNTIME_WORKSPACE_ROOT`, then `ROOT`.
  - Stop using `STATE_ROOT` to derive active buddybox storage.
  - Keep legacy constants only when used by tests as patched compatibility inside the test process; no production code path should call a `STATE_ROOT`-derived buddybox constant.
  - Update persisted object validation for buddybox source refs to use `logical_name`, `private_to_buddy`, `read_grant=false`.

- Modify `scripts/runtime_kernel/dispatcher.py`
  - `_runtime_server_env()` adds `BUDDYSWITCH_WORKSPACE_DIR` from instance record `workspace_dir` when present.
  - `_env_tool_dispatch()` passes `instance_payload` unchanged to services so `env_store.buddybox_local_dir(context["instance_payload"])` can resolve the active instance workspace even in direct dispatch tests.

- Modify `tools/launcher/workspace.sh`
  - `buddyswitch_workspace_runtime_output_paths()` keeps `buddyswitch/local/buddybox/<active_buddy>` as workspace-local output for same-instance rebuild staging.
  - `buddyswitch_workspace_projected_state_paths()` remains product object dirs only.
  - `buddyswitch_workspace_install_active_buddybox_root()` becomes `buddyswitch_workspace_ensure_active_buddybox_root()` and creates `${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/local/buddybox/${BUDDYSWITCH_ACTIVE_BUDDY}` as a real directory.
  - The helper must not create `${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/local/buddybox/${buddy}` and must remove a stale symlink at the workspace buddybox path before creating the real directory.
  - `buddyswitch_workspace_install_state_projections()` calls the new real-directory helper after object projections.

- Modify `scripts/env/services/buddybox.py`
  - Replace `_LIST_FIELDS`, `_READ_FIELDS`, `_WRITE_FIELDS`, `_DELETE_FIELDS` with `logical_name` variants.
  - Add `KNOWN_BUDDY_IDS` derivation from `context["manifest"]["buddies"]`.
  - Add `normalize_logical_name(value: Any, *, active_buddy: str, buddy_ids: set[str]) -> str`.
  - Add `normalize_logical_prefix(value: Any, *, active_buddy: str, buddy_ids: set[str]) -> str | None`.
  - Add `buddybox_root(context: BuddyboxServiceContext) -> Path` returning `env_store.buddybox_local_dir(context["instance_payload"]) / active_buddy`.
  - Add `buddybox_base_dir(context: BuddyboxServiceContext) -> Path` returning `env_store.buddybox_local_dir(context["instance_payload"])`.
  - `_resolve_path(logical_name, context)` joins active root with the normalized logical name.
  - `_file_summary()` returns `logical_name`, `size_bytes`, `updated_at`, `content_type`, `visibility`, `private_to_buddy`; it must not return `path` or `source_ref`.
  - `build_buddybox_desc(active_buddy, instance_payload=None)` returns capability metadata without `logical_root`.
  - Success extras for file actions use `logical_name` and add `object_kind="private_file"`, `visibility="active_buddy_private"`, `owner_scope="active_buddy"`, `lifetime_scope="active_instance_workspace"`, `product_readable=false`, `cross_buddy_readable=false`, `mutates_product_state=false`, `mutated_product_objects=[]`.
  - Write success returns `created`, `overwrote`, `size_bytes`, `content_type`.
  - Read success returns `encoding`, `content` or `content_base64`, and never both.
  - List success returns `files` summary rows and no content body fields.
  - Delete success returns `deleted` and `logical_name`.
  - Rejections use `_reject_logical_name()`, `_reject_payload()`, `_reject_boundary()`, `_reject_not_found()` with codes `E_BUDDYBOX_LOGICAL_NAME`, `E_BUDDYBOX_PAYLOAD`, `E_BUDDYBOX_BOUNDARY`, `E_BUDDYBOX_NOT_FOUND`.
  - Buddybox-specific responses include `available_affordances` structured objects and avoid action-command prose in `allowed_next_actions`.

- Modify `scripts/env/tools/responses.py`
  - Extend `rejection()` with optional `error_class: str | None`, `boundary: str | None`, `correctable_fields: list[str] | None`, `alternative_capabilities: list[dict[str, Any]] | None`, `mutates_product_state: bool | None`.
  - Add `tool_affordance(tool, action, effect, condition, risk=None, mutates_product_state=False) -> dict[str, Any]` for Buddybox structured affordance rows.
  - Keep existing `next_action_option()` for other tools and existing response contract compatibility.

- Modify `scripts/env/tools/contracts.py`
  - Buddybox action payload fields become:
    - `desc`: `[]`
    - `list`: `["logical_name", "recursive", "limit"]`
    - `read`: `["logical_name", "encoding"]`
    - `write`: `["logical_name", "content", "content_base64", "content_type"]`
    - `delete`: `["logical_name"]`
  - Buddybox returns use `logical_name`, `private_file`, `capability_metadata`, `available_affordances`.
  - Context returns include capability-level `buddybox_desc` and `tool_affordances`.

- Modify `scripts/env/tools/semantics.py`
  - Buddybox capability text says "logical names resolved by the tool for the active buddy private file capability".
  - `inputs_explained` uses `logical_name`; it states names are relative within the active buddy private file capability and must not include buddy id prefixes.
  - `side_effects.writes` for buddybox write/delete uses `"active_buddy_private_file_workspace"` instead of filesystem roots.
  - `does_not_write` includes product objects and cross-buddy collaboration state.
  - `risk_hints` keeps desc/list/read read-only, write private-file mutation, delete destructive private-file mutation.
  - `common_failures` includes empty logical name, absolute name, traversal, buddy prefix, symlink escape, missing file, invalid base64, invalid encoding, directory delete, and attempts to use buddybox as cross-buddy readable content.
  - `compact_tool_affordances()["buddybox"]` returns capability metadata fields from `REQ-019`.

- Modify `scripts/env/client.py`
  - Replace `--path` arguments with `--logical-name` for `buddybox list/read/delete`.
  - `buddybox write --payload` requires payload key `logical_name`.
  - `_dispatch_buddybox()` emits `logical_name` only.

- Modify `scripts/env/services/context.py`
  - Pass `context["instance_payload"]` into `buddybox_service.build_buddybox_desc()`.
  - `context_sources_desc()["buddybox"]` removes `source_of_truth` and returns capability metadata.
  - `context.get` and `context.summarize` do not include `logical_root`, physical roots, shared roots, or workspace roots.

- Modify `scripts/env/services/source_refs.py`
  - Rename `validate_buddybox_ref_path()` to `validate_buddybox_ref_logical_name()`.
  - Accept `{"type":"buddybox","logical_name":"provenance/notes.md"}` only when `allow_buddybox=True`.
  - Reject `{"type":"buddybox","path":...}` with `ValueError("source_refs.buddybox.logical_name is required; path is retired")`.
  - Normalize to `{"type":"buddybox","logical_name":..., "private_to_buddy": active_buddy, "read_grant": false}`.
  - `source_ref_summary()` emits `logical_name` for buddybox refs.

- Modify `scripts/env_store.py` source_ref validation
  - Persisted artifact validation accepts normalized buddybox source refs with `logical_name`, `private_to_buddy`, `read_grant=false`.
  - Persisted handoff validation still rejects buddybox source refs.
  - Retired `path` source refs in existing JSON fail validation when active mutation reads them; this is acceptable because the task explicitly removes the old contract.

- Modify `scripts/env/services/artifacts.py`
  - Error messages and tests use `source_refs.buddybox.logical_name`.
  - Artifact content remains the product-readable carrier; buddybox source_ref remains private provenance.

- Modify `scripts/env/services/handoffs.py`
  - Rejection wording says buddybox logical names are active buddy private provenance and not target-readable payloads.

- Modify `tests/runtime_root_test_helper.py`
  - Patch `env_store.runtime_workspace_root()` or patch any module-level workspace root used by the new helper.
  - Existing test sandboxes continue writing under `self.runtime_root/buddyswitch/local/buddybox`.

- Modify guidance and docs
  - `README.md`: replace "active buddy private buddybox path" with "active buddy private buddybox logical names".
  - `AGENTS.md`: remove buddybox filesystem root from key runtime state list; keep env-tool and no-direct-edit rule at route-map level.
  - `tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md`: remove root paths and say to use `buddybox` env tool with logical names.
  - `buddyswitch/skills/shared/buddybox-tool/SKILL.md`: replace `--path` examples with `--logical-name`; payload examples use `logical_name`; path rules become logical name rules.
  - `buddyswitch/skills/{pm,design,dev,market,test}/**/SKILL.md`: replace `buddyswitch/local/buddybox/<active-buddy>/**` instructions with tool-level logical-name guidance.
  - `framework/contracts/{pm,design,dev,market,test}.md`: remove buddybox filesystem root bullets and keep role-specific buddybox/artifact boundary sentence.

### 核心数据模型

`buddybox.desc` and context capability row:

```json
{
  "capability": "private_file_workspace",
  "owner_scope": "active_buddy",
  "lifetime_scope": "active_instance_workspace",
  "visibility": "active_buddy_private",
  "product_readable": false,
  "cross_buddy_readable": false,
  "mutates_product_state": false,
  "supports": [
    "describe_capability",
    "list_private_file_summaries",
    "read_private_file",
    "write_private_text",
    "write_private_binary",
    "delete_private_file"
  ],
  "state_summary": {
    "file_count": 0,
    "total_bytes": 0,
    "latest_update_at": null
  }
}
```

`buddybox.write` request:

```json
{
  "logical_name": "prototypes/hero.html",
  "content": "<html>hero</html>",
  "content_type": "text/html"
}
```

`buddybox.write` success:

```json
{
  "ok": true,
  "tool": "buddybox",
  "action": "buddybox.write",
  "active_buddy": "pm",
  "object_kind": "private_file",
  "logical_name": "prototypes/hero.html",
  "visibility": "active_buddy_private",
  "owner_scope": "active_buddy",
  "lifetime_scope": "active_instance_workspace",
  "durability": "active_instance_local",
  "product_readable": false,
  "cross_buddy_readable": false,
  "mutates_product_state": false,
  "mutated_product_objects": [],
  "state_changed": true,
  "content_type": "text/html",
  "size_bytes": 17,
  "created": true,
  "overwrote": false
}
```

`available_affordances` row shape:

```json
{
  "tool": "artifact",
  "action": "create_revision",
  "effect": "create product-readable content",
  "condition": "host decides another buddy or product workflow must read this content",
  "risk": "creates or updates product deliverable state",
  "mutates_product_state": true
}
```

`buddybox` invalid logical name rejection:

```json
{
  "ok": false,
  "tool": "buddybox",
  "action": "buddybox.write",
  "error": {
    "code": "E_BUDDYBOX_LOGICAL_NAME",
    "class": "invalid_input"
  },
  "boundary": "active_buddy_private_file_capability",
  "state_changed": false,
  "mutates_product_state": false,
  "retryable": true,
  "correctable_fields": ["logical_name"],
  "why_blocked": "logical_name must be relative to the active buddy private file capability and must not include a buddy prefix",
  "alternative_capabilities": [
    {
      "tool": "artifact",
      "condition": "use when content must be product-readable"
    }
  ]
}
```

### 调用流

1. Host calls `python3 scripts/env/client.py context summarize`.
2. `context.summarize` returns `tool_affordances.buddybox` with capability metadata, not a filesystem root.
3. Host calls `python3 scripts/env/client.py buddybox write --payload /tmp/payload.json` where payload contains `logical_name`.
4. `scripts/env/client.py::_dispatch_buddybox()` sends broker params `{"tool":"buddybox","action":"write","args":{"logical_name":"..."}}`.
5. Broker routes through `scripts/env/tools/dispatch.py` to `scripts/env/services/buddybox.py::write_buddybox_for_active_buddy()`.
6. `write_buddybox_for_active_buddy()` calls `normalize_logical_name()`, resolves under `env_store.buddybox_local_dir(context["instance_payload"]) / active_buddy`, verifies parent symlink safety, writes atomically, and returns private-file response fields.
7. If host decides content must be readable beyond active buddy privacy, host creates or updates an artifact with readable content. Buddybox logical name may appear only as private provenance in artifact `source_refs`, with `read_grant=false`.

## 5. 分阶段实施计划

### 阶段 1：实例本地 storage boundary

**目标**

Make active buddybox files live in the active instance workspace as real local directories, while product object dirs remain shared runtime state projections.

**具体文件变更**

- Modify `tests/test_buddyswitch_launcher.py`
- Modify `tests/runtime_root_test_helper.py`
- Modify `scripts/env_store.py`
- Modify `scripts/runtime_kernel/dispatcher.py`
- Modify `tools/launcher/workspace.sh`

**详细步骤**

1. In `tests/test_buddyswitch_launcher.py`, replace the current buddybox entry in the state projection assertion with a new assertion in `test_instance_start_creates_instance_specific_runtime_workspace`:
   - `workspace_dir / "buddyswitch/local/buddybox/pm"` exists.
   - It is a directory.
   - It is not a symlink.
   - `shared_root / "state/buddyswitch/local/buddybox/pm"` does not exist after start.
   - A file written into the workspace buddybox dir is not visible under shared state.
   - Product object dirs still remain symlinks to shared state.
2. Add `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_workspace_rebuild_preserves_active_buddybox_inside_instance_workspace`:
   - Start PM instance.
   - Write `workspace_dir/buddyswitch/local/buddybox/pm/rebuild/probe.txt`.
   - Trigger the launcher path that rebuilds or reopens the same instance workspace.
   - Assert the file remains under the same instance workspace and no shared state buddybox dir is created.
3. In `tests/runtime_root_test_helper.py`, update `RuntimeWorkspaceSandbox.start()` so any patch follows `env_store.runtime_workspace_root()` and `env_store.buddybox_local_dir()` rather than a `STATE_ROOT`-derived constant.
4. In `scripts/env_store.py`, add:
   - `def runtime_workspace_root(instance_payload: dict[str, Any] | None = None) -> Path`
   - `def buddybox_local_dir(instance_payload: dict[str, Any] | None = None) -> Path`
   - The helper must prefer `instance_payload["workspace_dir"]` and must never use `STATE_ROOT`.
5. In `scripts/runtime_kernel/dispatcher.py`, set `BUDDYSWITCH_WORKSPACE_DIR` inside `_runtime_server_env()` using `instance_record["workspace_dir"]`; update call sites to pass `instance_record`.
6. In `tools/launcher/workspace.sh`, replace `buddyswitch_workspace_install_active_buddybox_root()` symlink logic with real directory creation:
   - Remove stale symlink or file at the target.
   - Create parent `buddyswitch/local/buddybox`.
   - Create active buddy dir with `mkdir -p`.
   - Do not touch shared state buddybox path.
7. Keep `buddyswitch_workspace_runtime_output_paths()` including active buddybox so rebuild staging preserves workspace-local private files.

**预期行为变化**

- Starting a buddy instance creates a real local buddybox directory inside that instance workspace.
- Buddybox files do not appear under `${BUDDYSWITCH_SHARED_ROOT}/state`.
- Object dirs continue to use shared state projections.
- Existing shared-state buddybox data is ignored.

**对应需求编号**

`REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-027`, `REQ-029`

**验证命令**

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_creates_instance_specific_runtime_workspace -q
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_workspace_rebuild_preserves_active_buddybox_inside_instance_workspace -q
python3 -m pytest tests/test_buddy_env_sandbox.py -q
```

**阶段完成标准**

- The new launcher tests fail before implementation because buddybox is a symlink to shared state.
- The tests pass after implementation.
- No code path creates `${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/local/buddybox/<buddy>` for active storage.

### 阶段 2：`path` 直接替换为 `logical_name`

**目标**

Remove host-facing filesystem-ish path input and active buddy prefix semantics from buddybox operations and buddybox provenance.

**具体文件变更**

- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_artifact_env_tool.py`
- Modify `tests/test_handoff_env_tool.py`
- Modify `scripts/env/services/buddybox.py`
- Modify `scripts/env/client.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/semantics.py`
- Modify `scripts/env/services/source_refs.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/handoffs.py`
- Modify `scripts/env_store.py`

**详细步骤**

1. In `tests/test_buddybox_env_tool.py`, change lifecycle tests to call:
   - `buddybox.write args={"logical_name":"prototypes/hero.html","content":"<html>hero</html>"}`
   - `buddybox.read args={"logical_name":"prototypes/hero.html"}`
   - `buddybox.list args={"recursive": True}`
   - `buddybox.delete args={"logical_name":"prototypes/hero.html"}`
2. Add `test_buddybox_rejects_legacy_path_payload_field`:
   - `buddybox.write args={"path":"pm/prototypes/hero.html","content":"x"}` returns `E_BUDDYBOX_PAYLOAD`.
   - Response has `correctable_fields=["logical_name"]` or includes `path` only as a retired field in `why_blocked`, not as retry guidance.
3. Add `test_buddybox_rejects_buddy_prefixed_logical_names`:
   - Active PM rejects `logical_name="pm/prototypes/hero.html"`.
   - Active PM rejects `logical_name="dev/reports/report.txt"`.
   - Both return `E_BUDDYBOX_LOGICAL_NAME`, `state_changed=false`, and no file is written.
4. Add `test_buddybox_logical_name_text_binary_lifecycle`:
   - Text write/read/list/delete uses `logical_name`.
   - Binary write/read uses `content_base64` and returns base64 for non-UTF-8 bytes.
   - List rows contain `logical_name` and never contain `path`, `content`, `content_base64`, `source_ref`.
5. Add `test_buddybox_logical_name_boundaries_and_symlink_escape`:
   - Reject `""`, `"/tmp/x"`, `"../x"`, `"notes/../../x"`.
   - Reject symlink read escape and parent symlink write escape without leaking target content.
6. In `scripts/env/services/buddybox.py`, rename normalizers and all call sites from path to logical name:
   - `_LIST_FIELDS = {"logical_name","recursive","limit"}`
   - `_READ_FIELDS = {"logical_name","encoding"}`
   - `_WRITE_FIELDS = {"logical_name","content","content_base64","content_type"}`
   - `_DELETE_FIELDS = {"logical_name"}`
   - `normalize_logical_name()` rejects buddy prefixes using manifest buddy ids.
   - `_resolve_path()` joins active root plus logical name.
7. In `scripts/env/services/buddybox.py`, update return payloads:
   - All action payloads use `logical_name`.
   - No buddybox response includes `path`, `logical_root`, `source_of_truth`, absolute paths, or workspace roots.
8. In `scripts/env/client.py`, replace CLI flags:
   - `buddybox list --logical-name <prefix>`
   - `buddybox read --logical-name <name>`
   - `buddybox delete --logical-name <name>`
   - Remove `--path` from buddybox CLI parser.
9. In `scripts/env/tools/contracts.py`, replace buddybox payload fields and returns as specified in the final architecture.
10. In `scripts/env/tools/semantics.py`, replace every buddybox `path` input explanation with `logical_name`, and remove `prefix under <active_buddy>/...`.
11. In `scripts/env/services/source_refs.py`, switch buddybox source_refs to `logical_name` and reject `path`.
12. In `scripts/env_store.py`, update persisted artifact validation and source_ref summary behavior to preserve `logical_name`, `private_to_buddy`, `read_grant=false`.
13. In `scripts/env/services/artifacts.py`, propagate the new source_ref validation errors unchanged through `E_SOURCE_REFS`.
14. In `scripts/env/services/handoffs.py`, keep `allow_buddybox=False` and ensure rejections mention private logical names are not readable payloads.

**预期行为变化**

- Host can no longer call buddybox with `path`.
- Host can no longer include active or foreign buddy prefix.
- Artifact private provenance uses `source_refs[].logical_name`.
- Handoff still rejects buddybox provenance as target-readable content.

**对应需求编号**

`REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `REQ-010`, `REQ-011`, `REQ-012`, `REQ-013`, `REQ-014`, `REQ-021`, `REQ-023`, `REQ-024`, `REQ-028`, `REQ-029`

**验证命令**

```bash
python3 -m pytest tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_success_responses_cover_read_write_and_target_scoped_evidence -q
python3 -m pytest tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_artifact_buddybox_source_ref_is_private_provenance -q
python3 -m pytest tests/test_handoff_env_tool.py::HandoffEnvToolTests::test_handoff_rejects_retired_private_path_list_and_buddybox_source_refs -q
```

**阶段完成标准**

- Focused buddybox lifecycle tests pass with `logical_name`.
- Tests prove `path` is rejected and old active prefix input no longer works.
- Artifact provenance and handoff rejection tests use `logical_name`.

### 阶段 3：structured response and rejection signals

**目标**

Make buddybox responses and rejections self-describing enough for host recovery without path knowledge or command-like SOP prose.

**具体文件变更**

- Modify `tests/test_buddybox_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`
- Modify `scripts/env/tools/responses.py`
- Modify `scripts/env/services/buddybox.py`

**详细步骤**

1. In `tests/test_buddybox_env_tool.py`, add `test_buddybox_success_responses_expose_private_file_state_model`:
   - Assert write/read/list/delete responses include `visibility="active_buddy_private"`, `owner_scope="active_buddy"`, `lifetime_scope="active_instance_workspace"`, `product_readable=false`, `cross_buddy_readable=false`, `mutates_product_state=false`, `mutated_product_objects=[]`.
   - Assert write response has `durability="active_instance_local"`.
2. Add `test_buddybox_success_affordances_are_structured_and_conditional`:
   - Assert `available_affordances` is a list of objects.
   - Each row has `tool`, `action`, `effect`, `condition`, `mutates_product_state`.
   - Artifact affordance includes condition text equivalent to "host decides content must become product-readable".
   - No buddybox `allowed_next_actions` string contains `retry with`, `<active_buddy>`, `edit`, `shared state`, `always`, or `must create artifact`.
3. Add `test_buddybox_rejections_are_self_correcting_without_path_guidance`:
   - Invalid `logical_name` returns `error.code="E_BUDDYBOX_LOGICAL_NAME"`, `error.class="invalid_input"`, `boundary="active_buddy_private_file_capability"`, `state_changed=false`, `mutates_product_state=false`, `retryable=true`, `correctable_fields=["logical_name"]`.
   - Rejection includes `alternative_capabilities` with conditional artifact row.
   - Rejection text does not include `<active_buddy>/`, `buddyswitch/local/buddybox`, `shared state`, or `directly edit`.
4. In `scripts/env/tools/responses.py`, extend `rejection()` optional fields and add `tool_affordance()`.
5. In `scripts/env/services/buddybox.py`, add local helpers:
   - `_private_file_state_fields(logical_name: str | None = None) -> dict[str, Any]`
   - `_available_affordances(action: str, *, include_artifact: bool) -> list[dict[str, Any]]`
   - `_alternative_capabilities() -> list[dict[str, Any]]`
6. In `scripts/env/services/buddybox.py`, set buddybox write/delete canonical `durability` to `active_instance_local` when state changes and `none` when no state changes.
7. Keep existing `allowed_next_action_options` only as structured machine options; set buddybox `allowed_next_actions` to an empty list or non-command summary strings that do not prescribe commands.

**预期行为变化**

- Tool results contain explicit privacy, lifetime, readability, product mutation, and affordance fields.
- Invalid inputs are recoverable from structured fields.
- Rejections stop teaching filesystem paths.

**对应需求编号**

`REQ-015`, `REQ-016`, `REQ-017`, `REQ-018`, `REQ-022`, `REQ-025`, `REQ-029`

**验证命令**

```bash
python3 -m pytest tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_success_responses_expose_private_file_state_model -q
python3 -m pytest tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_rejections_are_self_correcting_without_path_guidance -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_runtime_tool_feedback.py -q
```

**阶段完成标准**

- Response tests fail before signal implementation and pass after.
- Every buddybox rejection includes correction fields.
- No buddybox rejection suggests direct filesystem access or buddy prefix retry.

### 阶段 4：context、catalog、semantics capability realignment

**目标**

Make discovery surfaces describe buddybox as a capability, not as a path source.

**具体文件变更**

- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_identity.py`
- Modify `tests/test_env_tool_semantic_contract.py`
- Modify `tests/test_host_decision_surface_product_mode.py`
- Modify `scripts/env/services/context.py`
- Modify `scripts/env/tools/contracts.py`
- Modify `scripts/env/tools/semantics.py`

**详细步骤**

1. In `tests/test_context_binding_env_tool.py`, update `test_context_uses_buddybox_desc_not_file_projection`:
   - Assert `buddybox_desc` has `capability="private_file_workspace"`, `owner_scope`, `lifetime_scope`, `visibility`, `product_readable=false`, `cross_buddy_readable=false`, `mutates_product_state=false`, `supports`.
   - Assert `logical_root` is absent.
2. In `tests/test_context_binding_env_tool.py`, update `test_context_list_sources_excludes_memory_and_includes_buddybox`:
   - Assert buddybox source row has capability metadata.
   - Assert `source_of_truth` is absent.
   - Assert no stringified source row contains `buddyswitch/local/buddybox`, `workspace`, or `shared`.
3. In `tests/test_env_tool_identity.py`, update `test_runtime_surface_has_no_run_or_binding_identity_tools` with the same no-path assertions.
4. In `tests/test_env_tool_semantic_contract.py`, update `test_buddybox_action_semantics_explain_input_formats_and_output_fields`:
   - Assert list/read/write/delete input fields include `logical_name`.
   - Assert no buddybox action has payload field `path`.
   - Assert input text says no buddy prefix.
5. Add `tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_buddybox_semantics_do_not_expose_filesystem_roots`:
   - JSON dump of `contracts.env_tools_description()["buddybox"]` and `contracts.operation_semantics()["buddybox.write"]` must not contain `buddyswitch/local/buddybox`, `<active_buddy>`, `logical_root`, `source_of_truth`, `shared root`, `workspace root`.
6. In `tests/test_host_decision_surface_product_mode.py`, add or update host-decision scenario:
   - Context summary lets host distinguish private buddybox logical files from product-readable artifact and handoff state.
   - Test asserts no phrase-to-tool trigger such as "prototype means buddybox".
7. In `scripts/env/services/context.py`, remove `logical_root` from `buddybox_desc` and `source_of_truth` from `context_sources_desc()["buddybox"]`.
8. In `scripts/env/tools/contracts.py`, ensure tool catalog payload fields and returns use logical names and capability metadata.
9. In `scripts/env/tools/semantics.py`, update all buddybox semantics and `compact_tool_affordances()` to match `REQ-019` through `REQ-022`.

**预期行为变化**

- Default and full context discovery surfaces no longer reveal buddybox file roots.
- Tool catalog describes how to use `logical_name`.
- Host can distinguish private file state from artifact and handoff state without SOP rules.

**对应需求编号**

`REQ-019`, `REQ-020`, `REQ-021`, `REQ-022`, `REQ-025`, `REQ-029`

**验证命令**

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_identity.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_host_decision_surface_product_mode.py -q
```

**阶段完成标准**

- Context tests prove no buddybox path roots are exposed.
- Semantic contract tests prove `logical_name` is the only buddybox file selector.
- Host decision tests prove artifact remains the product-readable carrier.

### 阶段 5：route-map docs、skills、contracts cleanup

**目标**

Remove prompt-layer filesystem contracts while keeping concise route maps for tool discovery and env-tool usage.

**具体文件变更**

- Modify `README.md`
- Modify `AGENTS.md`
- Modify `tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md`
- Modify `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- Modify `buddyswitch/skills/pm/write-prd/SKILL.md`
- Modify `buddyswitch/skills/design/shape-prototype/SKILL.md`
- Modify `buddyswitch/skills/dev/implement-task/SKILL.md`
- Modify `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- Modify `buddyswitch/skills/market/{channel-discovery,customer-discovery,launch-prep,pmf-recon,positioning-copy,research-scan}/SKILL.md`
- Modify `buddyswitch/skills/test/smoke-test/SKILL.md`
- Modify `framework/contracts/{pm,design,dev,market,test}.md`
- Modify `scripts/runtime_agents.py`
- Modify `tests/test_runtime_agents.py`
- Modify `tests/test_runtime_skills.py`
- Modify `tests/test_repo_consistency.py`

**详细步骤**

1. In `README.md`, update Product Runtime Loop:
   - "Pick explicit target ids or buddybox logical names" instead of "active buddy private buddybox path".
   - Workspace layout says buddybox files are active-instance-local tool-managed private files and not product-readable state.
2. In `AGENTS.md`, remove buddybox filesystem root from runtime state path list; keep "Use env tools for product-mode runtime state. Do not edit runtime-managed object or buddybox files directly."
3. In all runtime buddy AGENTS templates, replace:
   - `Buddybox is the active buddy private local working directory: buddyswitch/local/buddybox/<buddy>/`
   - with `Buddybox is the active buddy private file capability; use buddybox env tool logical names and context/tool feedback.`
4. In `buddyswitch/skills/shared/buddybox-tool/SKILL.md`, update commands:
   - `python3 scripts/env/client.py buddybox list --logical-name prototypes --recursive`
   - `python3 scripts/env/client.py buddybox read --logical-name prototypes/landing.html`
   - `python3 scripts/env/client.py buddybox delete --logical-name tmp/obsolete.txt`
   - Payload examples use `logical_name`.
   - Replace "Path Rules" with "Logical Name Rules".
5. In role-specific skills, replace root-path instructions with "Use buddybox env tool logical names for active buddy private working files."
6. In role contracts, remove buddybox path bullets and keep the role-specific private-file/artifact boundary sentence.
7. In `scripts/runtime_agents.py`, update validation tokens so templates must mention logical names and must not include `buddyswitch/local/buddybox/<buddy>`.
8. In `tests/test_repo_consistency.py`, add grep-style assertions over active docs, templates, contracts, and skills:
   - No `--path` buddybox CLI examples.
   - No `<active_buddy>/...` buddybox retry instructions.
   - No `buddyswitch/local/buddybox/<active-buddy>` guidance in route-map text.
   - No "prototype means buddybox", "always create artifact", or "must create artifact after buddybox".

**预期行为变化**

- Prompt and skill surfaces direct hosts to tool discovery and logical names, not directories.
- Runtime guidance remains short and does not mirror full schemas.
- No prompt text becomes the enforcement layer for buddybox behavior.

**对应需求编号**

`REQ-018`, `REQ-021`, `REQ-022`, `REQ-025`, `REQ-026`, `REQ-029`

**验证命令**

```bash
python3 -m pytest tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
rg -n "buddybox.*--path|buddyswitch/local/buddybox/<|buddyswitch/local/buddybox/pm|buddyswitch/local/buddybox/dev|buddyswitch/local/buddybox/design|buddyswitch/local/buddybox/market|buddyswitch/local/buddybox/test|prototype means buddybox|always create artifact|must create artifact after buddybox" README.md AGENTS.md tools/launcher/assets/buddies buddyswitch/skills framework/contracts scripts tests -g '!docs/memo/**' -g '!docs/spec/**'
```

The `rg` command should return no matches except test strings that assert retired wording is absent.

**阶段完成标准**

- Guidance tests pass.
- Runtime skill materialization still installs the same skills.
- Active route-map text contains no buddybox filesystem contract.

### 阶段 6：main-path integration and regression pass

**目标**

Verify the complete realignment across launcher, broker, CLI, service, context, artifact/handoff boundary, and guidance.

**具体文件变更**

- Modify `tests/test_env_layer_end_to_end.py`
- Modify `tests/test_run_env_tool.py`
- Modify `tests/test_runtime_broker.py`
- Modify any failing tests touched by the previous phases without expanding scope.

**详细步骤**

1. In `tests/test_env_layer_end_to_end.py`, add `test_private_buddybox_logical_file_can_be_promoted_by_artifact_content_only`:
   - PM creates a task.
   - PM writes buddybox `logical_name="drafts/prd.html"`.
   - PM reads it and creates artifact content from the file body with `source_refs=[{"type":"buddybox","logical_name":"drafts/prd.html"}]`.
   - Dev can read artifact according to artifact rules.
   - Dev cannot read PM buddybox logical file.
2. In `tests/test_run_env_tool.py`, update any buddybox file creation or path assertion to logical names and active instance workspace root.
3. In `tests/test_runtime_broker.py`, ensure broker status still reports runtime workspace health and env tool dispatch works after `BUDDYSWITCH_WORKSPACE_DIR` env handling.
4. Run all focused phase commands again.
5. Run broader verification commands listed below.

**预期行为变化**

- Main path still works after the breaking input replacement.
- Product-readable collaboration still goes through artifact content.
- Buddybox remains active-buddy-private and instance-local.

**对应需求编号**

`REQ-001` through `REQ-029`

**验证命令**

```bash
python3 -m pytest tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_private_buddybox_logical_file_can_be_promoted_by_artifact_content_only -q
python3 -m pytest tests/test_run_env_tool.py tests/test_runtime_broker.py -q
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_buddy_env_sandbox.py -q
```

**阶段完成标准**

- End-to-end test proves artifact is the readable carrier and buddybox is not.
- Broker and CLI tests prove runtime invocation remains healthy.
- No phase-specific regression remains.

## 6. 迁移 / 删除策略

- Delete shared-state buddybox symlink creation in `tools/launcher/workspace.sh`.
- Delete host-facing `path` payload field from buddybox service, CLI, contracts, semantics, tests, and docs.
- Delete active buddy prefix requirement and foreign prefix special handling as a host contract.
- Delete context fields `logical_root` and buddybox `source_of_truth`.
- Delete buddybox source_ref `path` acceptance for artifact provenance; use `logical_name`.
- Do not migrate existing files under `${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/local/buddybox/**`.
- Do not migrate retired files under `buddyswitch/content/buddybox/**`.
- Do not keep a transition period that accepts both `path` and `logical_name`; the old path contract is the current bottleneck.
- If a stale workspace symlink exists at active buddybox dir, launcher removes that symlink and creates a real directory. It does not copy the old symlink target contents.
- Compatibility is retained only for persisted product objects whose validation is unrelated to buddybox. Buddybox legacy source refs with `path` fail validation when mutated because they encode the retired contract.

## 7. 完成定义

The task is complete when all of the following are true:

- Starting an instance creates a real active buddybox directory inside the instance workspace and no shared-state buddybox dir for active files.
- Buddybox service, CLI, contracts, semantics, tests, docs, and source_refs use `logical_name`; `path` is rejected for buddybox host-facing payloads.
- Buddybox responses expose visibility, owner scope, lifetime scope, durability, product readability, cross-buddy readability, product mutation state, and structured affordances.
- Buddybox rejections expose error class, boundary, correction fields, retryability, state impact, and conditional alternative capabilities without path retry guidance.
- Context and semantics expose buddybox as a capability and do not expose filesystem roots or `source_of_truth` for buddybox.
- Artifact remains the explicit product-readable content carrier; handoff rejects buddybox private logical names as target-readable payloads.
- AGENTS, README, role contracts, and skills stay route-map level and contain no buddybox filesystem root contract.
- Focused tests for each phase pass.
- Final broader verification passes:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_response_contract.py tests/test_artifact_env_tool.py tests/test_handoff_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_env_layer_end_to_end.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_runtime_agents.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
rg -n "buddybox.*--path|source_of_truth.*buddybox|logical_root|<active_buddy>|buddyswitch/local/buddybox/<|buddyswitch/local/buddybox/pm|buddyswitch/local/buddybox/dev|buddyswitch/local/buddybox/design|buddyswitch/local/buddybox/market|buddyswitch/local/buddybox/test|prototype means buddybox|always create artifact|must create artifact after buddybox" README.md AGENTS.md scripts tools framework buddyswitch tests -g '!docs/memo/**' -g '!docs/spec/**'
```

The `rg` command must have no unexpected matches; tests that assert retired wording is absent may contain the retired strings.

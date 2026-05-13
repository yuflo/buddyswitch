# Tool-Visible Search Layer Code Implementation Plan

## 1. 任务目标

完成后，BuddySwitch product-mode session 中的 search/research 入口收敛到 BuddySwitch 管理的 `env.tool search` 表面：Codex 原生 `web_search` 不再作为可见旁路存在，buddy 可以通过 runtime context 看见 search 能力、权限边界、backend 状态和下一步动作，并通过 broker-routed env tool 获得结构化反馈。

当前核心瓶颈是 BuddySwitch 已经把 task、track、artifact、context、evidence、handoff、run 收敛到 `env.tool`，但 search 仍可能由 Codex host-native `web_search` 直接暴露，绕过 BuddySwitch 的 profile、broker、tool feedback 和 browser cockpit 约束。它最重要，因为 Market research 的主路径依赖 browser-native 证据，而 search 旁路会让模型在行动前看见两套互相竞争的工具面。

## 2. 需求提取

- `REQ-001`：BuddySwitch-launched product sessions 必须把 Codex config 中的 `web_search` 设置为 `"disabled"`。
- `REQ-002`：product sessions 必须阻止明显原生 search 启动逃逸，包括 `--search`、`--search=...`、`-c web_search=...`、`-cweb_search=...`、`--config web_search=...` 和 `--config=web_search=...`。
- `REQ-003`：原生 search 被阻止时，用户可见错误必须指出 BuddySwitch search 工具路径，而不是只返回“blocked”。
- `REQ-004`：非 product-mode 的普通 `codex` 启动不得被 BuddySwitch search 规则限制。
- `REQ-005`：新增 `search` 作为 broker-routed `env.tool` tool id；当前代码库不得重新引入 `*_manager.py`、`*_manager` runtime context key 或 manager-named public surface。
- `REQ-006`：`search` 必须支持 `status`、`request`、`open_browser` 三个 action；CLI 操作为 `python3 scripts/env/client.py search status`、`search request`、`search open-browser`。
- `REQ-007`：`search.request` 不得使用隐式 `auto` backend；缺失或未知 backend 必须拒绝，并返回允许值、`permission_boundary`、`allowed_next_actions` 和 `command_hint`。
- `REQ-008`：`search.status` 必须返回 `native_codex_web_search`、`active_buddy`、`available_backends`、`backend_status.browser`、`backend_status.search_api`、`capability_boundary`、`permission_boundary`、`allowed_next_actions` 和 `command_hint`。
- `REQ-009`：`search.status` 不得编码 Market workflow default；它只报告 runtime facts 和 profile boundaries。
- `REQ-010`：`search.request` 使用 `backend="browser"` 时必须返回可执行的 browser instruction payload，包括 `target_url`、`browser_endpoint`、`required_cockpit_tool`、`page_opened=false` 和 browser traversal next action。
- `REQ-011`：`search.request` 使用 `backend="search_api"` 时，在真实 BuddySwitch-managed provider 存在前必须返回结构化 unavailable 或 approval-required feedback。
- `REQ-012`：`search.open_browser` 必须根据 `query` 和 `engine` 构造 search URL，使用 instance-bound browser endpoint，尝试通过 Chrome DevTools `/json/new?<target_url>` 打开页面，并返回 `target_url`、`browser_endpoint`、`page_opened`、`next_action`。
- `REQ-013`：`search.open_browser` 在 browser endpoint 缺失、端口无效、不可达或 page open 失败时必须返回结构化拒绝或降级反馈，包含恢复命令。
- `REQ-014`：支持的 engine 集合固定为 `google`、`web`、`reddit`、`x`；空 query、空 engine、未知 engine 必须被明确拒绝。
- `REQ-015`：所有 buddy env profiles 都必须暴露 coherent search capability boundary；Market 为 browser cockpit required 和 search API user-approved-only，非 Market buddy 共享同一 tool 且 browser/search boundary 更宽松。
- `REQ-016`：env profile 只表达 machine-readable static boundaries，不表达 workflow default 或 Market 研究步骤。
- `REQ-017`：`prepare.runtime_context.env_tools` 必须包含 `search`，并描述 envelope、operations、payload fields、backend model、feedback source 和 authoritative response fields。
- `REQ-018`：`prepare.runtime_context.tool_requirements` 和 `capability_boundary` 必须投影 search capability facts，使 host 可以在行动前看见 native search disabled、browser cockpit boundary 和 search API boundary。
- `REQ-019`：instance `AGENTS.md` templates 必须说明 native Codex `web_search` 在 BuddySwitch product sessions 中不可用，search 通过 `env.tool search` 进行；这只是投影，不是唯一 enforcement point。
- `REQ-020`：Market research skills 必须直接选择 browser-native search action，即先调用 `search.open_browser`，再继续 `chrome-devtools-cockpit` 页面遍历；不能只靠 profile prose 暗示默认选择。
- `REQ-021`：search tool 不得替代 browser evidence gate；Market artifact-producing persist 仍需要 broker-issued `tool_evidence`。
- `REQ-022`：不得新增 persist-time provenance audit、hidden governance loop、prompt-only constraint、Market-only patch、search-specific workflow router、broad policy engine、workflow engine、event bus、rule framework 或 plugin framework。
- `REQ-023`：现有 env tool response contracts 必须保持一致；search success/rejection 也必须使用 canonical machine-readable fields。
- `REQ-024`：所有实现和验证在 `dev2258` worktree 中完成，不改 main，不混入 runtime broker v2 refactor。

## 3. 现状探索摘要

### 需要查看的关键目录和文件

- `docs/memo/2026-05-13-tool-visible-search-layer-memo.md`：本任务需求来源。
- `AGENTS.md`：仓库级 SHARP guidance，要求最短可验证路径、直接替换旧逻辑、无验证不完成。
- `README.md`：确认 product runtime loop 和 broker-routed `env.tool` 是 runtime CLI 主路径。
- `tools/launcher/codex_config.py`：launcher-managed Codex config patcher；当前写 sandbox、permission profile、MCP approval，未写 `web_search = "disabled"`。
- `tools/launcher/env.sh`：`buddyswitch_run_codex()` 统一设置 product CODEX_HOME 并执行 `codex "$@"`，是拦截 `--search` 和 `-c web_search=...` 的最短入口。
- `buddyswitch-codex`：`instance start` 和 `instance open` 把用户透传 Codex args 交给 `buddyswitch_run_codex()`；不需要在多个 command parser 中复制过滤逻辑。
- `scripts/env/tools/contracts.py`：现有 env tool registry，是新增 `search` tool/action contract 的单一公共事实源。
- `scripts/env/tools/router.py`：统一 envelope validation；新增 search 后应由 registry 自动纳入 `_TOOL_ACTIONS`。
- `scripts/env/tools/dispatch.py`：registry-backed handler binding；新增 `search` handlers 并让 `dispatch_handler_actions()` 与 registry 一致。
- `scripts/env/tools/responses.py`：canonical success/rejection/next-action helpers；search service 应使用这些 helper。
- `scripts/env/client.py`：skill-facing CLI；需新增 `search` parser、arg normalization 和 dispatch。
- `scripts/env/services/evidence.py`：browser endpoint readiness 和 structured feedback 的既有模式；search service 可复用同类 endpoint validation style，但不能写 evidence token。
- `scripts/turn_runtime.py`：`_build_env_tools_desc()`、`_build_runtime_context()`、`tool_requirements` 和 `capability_boundary` 投影位置。
- `scripts/env_profiles.py`：profile contract validation；需校验 nested search capability。
- `framework/contracts/buddy-env-profile.json`：profile schema vocabulary；需加入 `tool_capability.search.*` enums。
- `buddyswitch/env-profiles/{market,pm,design,dev,test}.json`：每个 buddy 的 static capability boundary。
- `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`：instance host projection templates。
- `buddyswitch/skills/market/{research-scan,pmf-recon,customer-discovery,positioning-copy,channel-discovery,launch-prep}/SKILL.md`：Market research skill workflow wording。
- `framework/docs/browser-cockpit.md`：browser-native research contract；需把 discovery start 指向 `env.tool search.open_browser`。
- `tests/test_buddyswitch_launcher.py`：fake Codex launcher tests 和 config patch assertions。
- `tests/test_buddy_env_sandbox.py`：Codex config and permission profile tests。
- `tests/test_env_tool_router.py`：registry/router/dispatch coverage 和 manager residue guard。
- `tests/test_env_tool_response_contract.py`：env tool success/rejection response contract。
- `tests/test_prepare_runtime_context.py`：runtime context projection tests。
- `tests/test_buddy_env_profiles.py`：profile matrix tests。
- `tests/test_market_browser_evidence.py`：browser evidence gate regression coverage。
- `tests/test_repo_consistency.py`：active surface residue scans and env tool surface consistency。

### 现有结构中保留、替换、删除或迁移

- 保留：`runtime broker -> env.tool -> router -> registry-backed dispatch -> service` 主路径。
- 保留：`contracts.py` 作为 tool/action names、payload fields、semantics、returns 的公共 registry。
- 保留：browser cockpit bootstrap、MCP server setup、browser evidence gate 和 Market persist `tool_evidence` validation。
- 保留：现有 `tool_capability.browser_cockpit`、`market_research_evidence`、`ordinary_web_fallback` 字段，因为 evidence gate 和已有 tests 依赖它们。
- 替换：Codex config patcher 对 native search 的默认继承行为，改成 managed top-level `web_search = "disabled"` 且清理旧 `web_search` assignments。
- 替换：`buddyswitch_run_codex()` 对 product-mode Codex args 的无条件透传，改成 product-mode args 先经过 search escape guard。
- 新增：`scripts/env/services/search.py`，作为 search business service。
- 新增：`search` registry entry、dispatch binding、CLI parser、profile nested search boundary、runtime context projection。
- 修改：Market skill wording，从“在可见 browser 里 search”升级为“先通过 `env.tool search.open_browser` 打开 browser-native search，再用 `chrome-devtools-cockpit` 遍历结果页”。
- 删除：无旧 search service 需要删除；必须避免新增 `scripts/env/tools/search_manager.py` 或 `env_tools.search_manager`，因为当前 active architecture 已经删除 manager surface。
- 迁移：无需迁移 canonical state；profile JSON 是静态配置更新，launcher-managed Codex config 在下一次 `instance start/open` 或 config patch 时重写。

### 需要运行的探索和验证命令

- `rg -n "web_search|--search|search_manager|env_tools|tool_capability|browser_cockpit|ordinary_web_fallback" tools scripts tests buddyswitch framework`
- `python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_codex_config_patch_removes_prior_misnested_managed_settings_idempotently -q`
- `python3 -m pytest -p no:cacheprovider tests/test_buddy_env_profiles.py tests/test_prepare_runtime_context.py -q`
- `python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_response_contract.py -q`

## 4. 最终目标架构

### 文件结构和职责

- 修改 `tools/launcher/codex_config.py`
  - `strip_managed_sections()` 删除旧 top-level 或 `[features]` 内的 `web_search` assignment。
  - `render_managed_top_level_block()` 和 `render_managed_permission_top_level_block()` 写入 `web_search = "disabled"`。
  - `patched_config_text()` 产出的 config 中只保留一个 BuddySwitch-managed `web_search` setting。

- 修改 `tools/launcher/env.sh`
  - 新增 `buddyswitch_reject_native_search_args()`。
  - `buddyswitch_run_codex()` 在存在 `BUDDYSWITCH_ACTIVE_BUDDY` 或 `BUDDYSWITCH_INSTANCE_ID` 时调用 guard；非 product-mode 不调用 guard。
  - guard 拒绝 `--search`、`--search=*`、`-c web_search=*`、`-cweb_search=*`、`--config web_search=*`、`--config=web_search=*`，stderr 包含 `python3 scripts/env/client.py search status` 和 `python3 scripts/env/client.py search open-browser`。

- 修改 `framework/contracts/buddy-env-profile.json`
  - `tool_capability.search.native_codex_web_search` enum: `["disabled"]`。
  - `tool_capability.search.browser_cockpit` enum: `["required", "available", "unavailable"]`。
  - `tool_capability.search.search_api` enum: `["available", "user-approved-only", "unavailable"]`。

- 修改 `buddyswitch/env-profiles/market.json`
  - 在 `tool_capability` 中新增:
    ```json
    "search": {
      "native_codex_web_search": "disabled",
      "browser_cockpit": "required",
      "search_api": "user-approved-only"
    }
    ```

- 修改 `buddyswitch/env-profiles/{pm,design,dev,test}.json`
  - 在 `tool_capability` 中新增:
    ```json
    "search": {
      "native_codex_web_search": "disabled",
      "browser_cockpit": "available",
      "search_api": "available"
    }
    ```

- 修改 `scripts/env_profiles.py`
  - `validate_env_profile()` 读取 `tool_capability.search` object。
  - 校验 `native_codex_web_search == "disabled"` 对所有 buddy 成立。
  - 校验 nested `browser_cockpit` 与现有 `tool_capability.browser_cockpit` 一致。
  - 校验 Market `search_api == "user-approved-only"`，非 Market `search_api == "available"`。

- 新增 `scripts/env/services/search.py`
  - 定义 `SearchServiceContext` TypedDict：`active_buddy`、`instance_id`、`instance_json`、`instance_payload`、`manifest`、`manifest_path`。
  - 定义 constants:
    - `ALLOWED_BACKENDS = ("browser", "search_api")`
    - `ALLOWED_ENGINES = ("google", "web", "reddit", "x")`
    - `SEARCH_API_PROVIDER_AVAILABLE = False`
    - `REQUIRED_COCKPIT_TOOL = "chrome-devtools-cockpit"`
  - 定义 `_load_search_boundary(context) -> dict[str, Any]`：读取 active buddy env profile nested search object。
  - 定义 `_browser_endpoint(instance_payload) -> tuple[str | None, str | None]`：从 `browser_port` 生成 `http://127.0.0.1:<port>`，无端口或非法端口返回 reason。
  - 定义 `_normalize_query(args) -> str | None`：要求 non-empty string。
  - 定义 `_normalize_engine(args) -> str`：默认 `google`，拒绝未知 engine。
  - 定义 `_build_search_url(query: str, engine: str) -> str`：
    - `google`: `https://www.google.com/search?q=<urlencoded query>`
    - `web`: `https://www.google.com/search?q=<urlencoded query>`
    - `reddit`: `https://www.reddit.com/search/?q=<urlencoded query>`
    - `x`: `https://x.com/search?q=<urlencoded query>&src=typed_query`
  - 定义 `_open_browser_page(browser_endpoint: str, target_url: str) -> tuple[bool, str | None]`：`PUT <browser_endpoint>/json/new?<percent-encoded target_url>`，HTTP 2xx 为 opened。
  - 定义 `status_for_active_instance(args, context)`。
  - 定义 `request_for_active_instance(args, context)`。
  - 定义 `open_browser_for_active_instance(args, context)`。

- 修改 `scripts/env/tools/contracts.py`
  - 在 `TOOL_REGISTRY` 中新增 `search`：
    - `cli_resource`: `"search"`
    - `command`: `"python3 scripts/env/client.py search <operation>"`
    - `scope`: `"runtime-visible search capability boundary and browser/search backend feedback"`
    - `actions`: `status`、`request`、`open_browser`
    - `payload_fields.status`: `[]`
    - `payload_fields.request`: `["query", "backend", "engine"]`
    - `payload_fields.open_browser`: `["query", "engine"]`
    - `mutates.status`: `MUTATES_NONE`
    - `mutates.request`: `MUTATES_NONE`
    - `mutates.open_browser`: 新增 `MUTATES_BROWSER_SESSION = "browser_session"`，使 browser session mutation 显式化。
    - `required_permission`: `"none"`
    - `authority`: `"env profile search boundary + instance browser endpoint"`
    - `returns`: status/backend/url/feedback fields。
  - Extend `env_tools_description()` to pass through optional `backend_model` when present in the registry entry.

- 修改 `scripts/env/tools/dispatch.py`
  - Import `env.services.search as search_service`。
  - Add:
    ```python
    "search": {
        "status": search_service.status_for_active_instance,
        "request": search_service.request_for_active_instance,
        "open_browser": search_service.open_browser_for_active_instance,
    }
    ```
  - `_service_context()` includes `manifest_path` for `search` because service needs env profile lookup.
  - RuntimeFeedbackError special handling remains limited to tools that raise it; search service should return structured payloads directly.

- 修改 `scripts/env/client.py`
  - `_parse_args()` 新增 `search` resource 和三个 operations:
    - `status`
    - `request --query <query> --backend <browser|search_api> [--engine <google|web|reddit|x>]`
    - `open-browser --query <query> [--engine <google|web|reddit|x>]`
  - 新增 `_search_args_from_cli(args) -> dict[str, Any]`。
  - 新增 `_dispatch_search(args)` 并在 `main()` 分支调用。
  - CLI validation 对空 query、空 backend、未知 engine 直接返回 exit 2；env.tool payload validation 仍在 service 层覆盖 broker/API caller。

- 修改 `scripts/turn_runtime.py`
  - `_build_runtime_context()` 在 `tool_requirements` 中新增:
    ```python
    "search": {
        "native_codex_web_search": "disabled",
        "browser_cockpit": <profile tool_capability.search.browser_cockpit>,
        "search_api": <profile tool_capability.search.search_api>
    }
    ```
  - `capability_boundary` 新增 `search` object，字段同上，并加 `env_tool_source = "runtime_context.env_tools.search"`。
  - `_build_env_tools_desc()` 继续返回 `tool_contracts.env_tools_description()`，不用特殊 case。

- 修改 `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`
  - 在 Runtime Boundary 中加入一条：
    `Native Codex web_search is unavailable in BuddySwitch product sessions; use python3 scripts/env/client.py search status|request|open-browser through env.tool.`
  - Market template 增加：
    `Market browser-native discovery starts with search open-browser, then continues in chrome-devtools-cockpit.`

- 修改 `buddyswitch/skills/market/{research-scan,pmf-recon,customer-discovery,positioning-copy,channel-discovery,launch-prep}/SKILL.md`
  - Execution Order 第一步改为显式调用 `python3 scripts/env/client.py search open-browser --query "<query>" --engine <google|reddit|x|web>`。
  - Market Research Cockpit Runtime 中说明 `search.open_browser` 只打开 browser-native discovery 起点，实际证据仍来自 `chrome-devtools-cockpit` result-page traversal。
  - 保留 no silent search API/snippet/crawler fallback 和 evidence gate wording。

- 修改 `framework/docs/browser-cockpit.md`
  - Runtime Rules 中把 discovery start 明确为 `env.tool search.open_browser`，而不是裸 browser-external search 或 host-native search。
  - Source Of Truth Boundary 中声明 search tool 不写 canonical state。

- 修改 `tests` 下的 focused tests，具体用例在测试计划文档中列出。

### 核心数据模型

`search.status` success payload:

```json
{
  "ok": true,
  "tool": "search",
  "action": "search.status",
  "active_buddy": "market",
  "native_codex_web_search": "disabled",
  "available_backends": ["browser"],
  "backend_status": {
    "browser": {
      "available": true,
      "browser_url": "http://127.0.0.1:9222",
      "required_cockpit_tool": "chrome-devtools-cockpit"
    },
    "search_api": {
      "available": false,
      "permission": "user-approved-only",
      "reason": "No BuddySwitch-managed search API provider is configured."
    }
  },
  "capability_boundary": {
    "native_codex_web_search": "disabled",
    "browser_cockpit": "required",
    "search_api": "user-approved-only"
  },
  "permission_boundary": "search.profile",
  "allowed_next_actions": [
    "Use search.open_browser with backend browser for browser-native discovery."
  ],
  "command_hint": "python3 scripts/env/client.py search open-browser --query '<query>' --engine google"
}
```

`search.request` browser success payload:

```json
{
  "ok": true,
  "tool": "search",
  "action": "search.request",
  "active_buddy": "market",
  "backend": "browser",
  "engine": "reddit",
  "query": "creator analytics pain",
  "target_url": "https://www.reddit.com/search/?q=creator+analytics+pain",
  "browser_endpoint": "http://127.0.0.1:9222",
  "required_cockpit_tool": "chrome-devtools-cockpit",
  "page_opened": false,
  "permission_boundary": "search.browser",
  "allowed_next_actions": [
    "Call search.open_browser to open the target in the instance browser, then traverse result pages in chrome-devtools-cockpit."
  ],
  "command_hint": "python3 scripts/env/client.py search open-browser --query 'creator analytics pain' --engine reddit"
}
```

`search.open_browser` success payload:

```json
{
  "ok": true,
  "tool": "search",
  "action": "search.open_browser",
  "active_buddy": "market",
  "engine": "google",
  "query": "creator analytics pain",
  "target_url": "https://www.google.com/search?q=creator+analytics+pain",
  "browser_endpoint": "http://127.0.0.1:9222",
  "page_opened": true,
  "permission_boundary": "search.browser",
  "allowed_next_actions": [
    "Use chrome-devtools-cockpit to select the opened page, inspect result pages, and capture evidence."
  ],
  "command_hint": "Use the chrome-devtools-cockpit MCP page tools against the opened search page."
}
```

`search_api` rejection payload:

```json
{
  "ok": false,
  "tool": "search",
  "action": "search.request",
  "active_buddy": "market",
  "error": {
    "code": "E_SEARCH_BACKEND_APPROVAL_REQUIRED",
    "message": "search_api requires explicit user approval and no BuddySwitch-managed search API provider is configured"
  },
  "permission_boundary": "search.search_api.user_approved_only",
  "allowed_next_actions": [
    "Use search.open_browser for browser-native discovery.",
    "Ask the user for explicit one-off approval before requesting a non-browser downgrade."
  ],
  "command_hint": "python3 scripts/env/client.py search open-browser --query '<query>' --engine google"
}
```

### 调用流

```text
Buddy skill or host
  -> python3 scripts/env/client.py search open-browser --query ... --engine ...
  -> runtime_kernel.client request_runtime_broker("env.tool", {"tool":"search","action":"open_browser","args":...})
  -> runtime broker active instance / active buddy boundary
  -> env.tools.router dispatch_env_tool_request()
  -> env.tools.dispatch HANDLERS_BY_TOOL["search"]["open_browser"]
  -> env.services.search.open_browser_for_active_instance()
  -> instance browser endpoint /json/new?<target_url>
  -> structured env.tool response
```

## 5. 分阶段实施计划

### 阶段一：关闭 Codex native search 旁路

**目标**

让 BuddySwitch product sessions 无法通过 managed config 或 startup args 暴露 Codex native `web_search`，同时保留非 product-mode 的普通 Codex 行为。

**具体文件变更**

- 修改 `tests/test_buddy_env_sandbox.py`
- 修改 `tests/test_buddyswitch_launcher.py`
- 修改 `tools/launcher/codex_config.py`
- 修改 `tools/launcher/env.sh`

**详细步骤**

1. 在 `tests/test_buddy_env_sandbox.py` 新增 `test_patch_forces_web_search_disabled_and_removes_existing_web_search_settings`。
   - 构造 config 同时包含 top-level `web_search = "live"` 和 `[features] web_search = "cached"`。
   - 调用 `tools/launcher/codex_config.py`。
   - 断言输出 top-level 只出现一次 `web_search = "disabled"`，且没有 `"live"` 或 `"cached"`。

2. 在 `tests/test_buddyswitch_launcher.py` 新增 `test_product_instance_start_rejects_native_search_args_before_codex_launch`。
   - 使用 `_write_fake_codex()`。
   - 分别运行：
     - `./buddyswitch-codex instance start --buddy pm -- --search`
     - `./buddyswitch-codex instance start --buddy pm -- -c web_search=live`
     - `./buddyswitch-codex instance start --buddy pm -- -cweb_search=cached`
     - `./buddyswitch-codex instance start --buddy pm -- --config web_search=live`
     - `./buddyswitch-codex instance start --buddy pm -- --config=web_search=cached`
   - 断言 return code 为 2，stderr 包含 `Native Codex web_search is disabled`、`scripts/env/client.py search status`、`scripts/env/client.py search open-browser`。
   - 断言 fake Codex capture file 不存在。

3. 在 `tests/test_buddyswitch_launcher.py` 新增 `test_local_non_buddy_start_allows_codex_search_args`。
   - 运行 `./buddyswitch-codex instance start -- --search`。
   - 断言 fake Codex capture 中 `argv == ["--search"]`。

4. 修改 `tools/launcher/codex_config.py`。
   - 新增 constant `WEB_SEARCH_KEY = "web_search"`。
   - `strip_managed_sections()` 在 `current_section in (None, "features")` 时删除 `web_search` assignment。
   - `render_managed_top_level_block()` 和 `render_managed_permission_top_level_block()` 在 managed comment 后写 `web_search = "disabled"`。

5. 修改 `tools/launcher/env.sh`。
   - 新增 `buddyswitch_reject_native_search_args()`，遍历 `"$@"`。
   - 当发现 native search args 时输出三行 stderr：
     - `Native Codex web_search is disabled in BuddySwitch product sessions.`
     - `Use: python3 scripts/env/client.py search status`
     - `Use: python3 scripts/env/client.py search open-browser --query '<query>' --engine google`
   - 返回 2。
   - `buddyswitch_run_codex()` 在 product-mode env 存在时调用该 guard；guard 通过后再设置 HOME/CODEX_HOME/XDG_CONFIG_HOME 并执行 `codex "$@"`。

**预期行为变化**

- Instance `codex-home/config.toml` 中由 BuddySwitch 管理 `web_search = "disabled"`。
- Product-mode `--search` 和 `web_search` config override 在 Codex 启动前失败。
- 非 buddy local launch 仍可透传用户 args。

**对应需求编号**

`REQ-001`、`REQ-002`、`REQ-003`、`REQ-004`、`REQ-024`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_patch_forces_web_search_disabled_and_removes_existing_web_search_settings -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_instance_start_rejects_native_search_args_before_codex_launch -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_local_non_buddy_start_allows_codex_search_args -q
```

**阶段完成标准**

- 三个 focused tests 通过。
- `rg -n "web_search = \"(live|cached)\"" tools scripts tests buddyswitch framework` 无 active expected-value 之外的命中。
- `tools/launcher/env.sh` 没有在 `buddyswitch-codex` command parser 中复制 search arg parsing。

### 阶段二：加入 search capability profile 和 runtime projection

**目标**

让所有 buddy 的 search capability boundary 成为 machine-readable profile fact，并在 prepare runtime context 中可见。

**具体文件变更**

- 修改 `framework/contracts/buddy-env-profile.json`
- 修改 `buddyswitch/env-profiles/market.json`
- 修改 `buddyswitch/env-profiles/pm.json`
- 修改 `buddyswitch/env-profiles/design.json`
- 修改 `buddyswitch/env-profiles/dev.json`
- 修改 `buddyswitch/env-profiles/test.json`
- 修改 `scripts/env_profiles.py`
- 修改 `scripts/turn_runtime.py`
- 修改 `tests/test_buddy_env_profiles.py`
- 修改 `tests/test_prepare_runtime_context.py`

**详细步骤**

1. 在 `tests/test_buddy_env_profiles.py` 扩展 `test_profiles_validate_with_matrix_rules`。
   - 对每个 buddy 断言 `profile["tool_capability"]["search"]["native_codex_web_search"] == "disabled"`。
   - 对 Market 断言 `browser_cockpit == "required"`、`search_api == "user-approved-only"`。
   - 对非 Market 断言 `browser_cockpit == "available"`、`search_api == "available"`。
   - 断言 nested `search.browser_cockpit` 等于 existing `tool_capability.browser_cockpit`。

2. 在 `tests/test_prepare_runtime_context.py` 新增 `test_prepare_projects_search_capability_boundary_for_each_buddy`。
   - prepare 每个 buddy。
   - 断言 `runtime_context["tool_requirements"]["search"]` 与 profile nested search object 一致。
   - 断言 `runtime_context["capability_boundary"]["search"]["env_tool_source"] == "runtime_context.env_tools.search"`。
   - 断言 boundary 不包含 workflow wording，例如 `default_engine`、`market_workflow`、`preferred_backend`。

3. 修改 `framework/contracts/buddy-env-profile.json` enums，加入 nested search keys。

4. 修改五个 profile JSON，保持 key order 不变，只在 `tool_capability` object 内加入 `search`。

5. 修改 `scripts/env_profiles.py`。
   - 新增 `_require_search_capability(tool_capability, enums, buddy_id)` local helper。
   - 在 `validate_env_profile()` 中调用 helper。
   - helper 返回 normalized search dict 并执行 Market/non-Market matrix checks。

6. 修改 `scripts/turn_runtime.py`。
   - 在 `_build_runtime_context()` 读取 `search_capability = tool_capability.get("search")`。
   - `tool_requirements["search"] = dict(search_capability)`。
   - `capability_boundary["search"] = {**search_capability, "env_tool_source": "runtime_context.env_tools.search"}`。

**预期行为变化**

- `python3 scripts/env_profiles.py validate-all` 校验 search capability boundary。
- prepare context 对所有 buddy 暴露相同 shape 的 search facts。
- Profile 仍不表达具体 workflow default。

**对应需求编号**

`REQ-015`、`REQ-016`、`REQ-018`、`REQ-019`、`REQ-024`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_profiles_validate_with_matrix_rules -q
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_validate_all_cli -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_search_capability_boundary_for_each_buddy -q
```

**阶段完成标准**

- Focused profile and prepare tests 通过。
- `python3 scripts/env_profiles.py validate-all` 输出五个 buddy `ok`。
- `prepare.runtime_context.capability_boundary.search` 不包含 workflow default 字段。

### 阶段三：实现 `env.tool search` registry、service、dispatch 和 CLI

**目标**

通过现有 `env.tool` path 暴露 search status、backend request 和 browser opening，使 host 不需要选择 host-native search。

**具体文件变更**

- 新增 `scripts/env/services/search.py`
- 修改 `scripts/env/tools/contracts.py`
- 修改 `scripts/env/tools/dispatch.py`
- 修改 `scripts/env/client.py`
- 修改 `tests/test_env_tool_router.py`
- 修改 `tests/test_env_tool_response_contract.py`
- 新增 `tests/test_search_env_tool.py`

**详细步骤**

1. 新增 `tests/test_search_env_tool.py`，使用 `RuntimeWorkspaceTestMixin` 构造 instance JSON。
   - `test_search_status_reports_profile_backend_and_native_search_boundary`
   - `test_search_request_browser_returns_actionable_instruction_without_opening_page`
   - `test_search_request_rejects_missing_or_unknown_backend`
   - `test_search_request_search_api_returns_market_approval_required`
   - `test_search_request_search_api_returns_non_market_provider_unavailable`
   - `test_search_open_browser_opens_cdp_page_with_encoded_target_url`
   - `test_search_open_browser_returns_recovery_feedback_when_browser_missing`
   - `test_search_rejects_empty_query_and_unknown_engine`

2. 修改 `tests/test_env_tool_router.py::test_dispatch_handler_coverage_matches_registry_actions` expected behavior 不需要硬编码 search；registry 加入后 test 应自然要求 dispatch coverage。若 test 当前 expected tool set 由 registry 生成，无需额外修改。

3. 修改 `tests/test_env_tool_response_contract.py`。
   - 在 success cases 加入 `("search", "status", {}, dev_instance, dev_instance_id, "dev")`。
   - 在 rejection cases 加入 `("search", "request", {"query": "x"}, dev_instance, dev_instance_id, "dev")` 验证 missing backend。
   - `_assert_success_contract()` 对 `search.status` 允许并要求 `permission_boundary` 存在，因为 status 是 capability feedback。

4. 修改 `scripts/env/tools/contracts.py`。
   - 新增 `MUTATES_BROWSER_SESSION = "browser_session"`。
   - 在 `TOOL_REGISTRY` 末尾加入 `search` spec。
   - Search spec 增加:
     ```python
     "backend_model": {
         "allowed_backends": ["browser", "search_api"],
         "allowed_engines": ["google", "web", "reddit", "x"],
         "native_codex_web_search": "disabled",
         "search_api_provider": "not-configured"
     }
     ```
   - `env_tools_description()` 若 `backend_model` 存在则复制到 desc。

5. 新增 `scripts/env/services/search.py`。
   - 用 `tool_responses.success()` 和 `tool_responses.rejection()` 构造所有 payload。
   - `status_for_active_instance()` 忽略 args 内容，返回 runtime facts。
   - `request_for_active_instance()`：
     - backend missing/unknown 返回 `E_SEARCH_BACKEND`。
     - query empty 返回 `E_SEARCH_QUERY`。
     - engine unknown 返回 `E_SEARCH_ENGINE`。
     - backend browser 返回 ok true instruction payload，`page_opened=false`。
     - backend search_api 对 Market 返回 `E_SEARCH_BACKEND_APPROVAL_REQUIRED`，对非 Market 返回 `E_SEARCH_BACKEND_UNAVAILABLE`。
   - `open_browser_for_active_instance()`：
     - query/engine validation 同 request。
     - browser boundary unavailable 返回 `E_SEARCH_BROWSER_UNAVAILABLE`。
     - browser endpoint missing/invalid 返回 `E_SEARCH_BROWSER_UNAVAILABLE`，`command_hint = "./buddyswitch-codex env browser ensure --instance <instance_id>"`。
     - CDP open 失败返回 `E_SEARCH_BROWSER_OPEN_FAILED`，payload 包含 `target_url` 和 `browser_endpoint`。
     - CDP open success 返回 ok true，`page_opened=true`。

6. 修改 `scripts/env/tools/dispatch.py`。
   - Import search service。
   - Add search handlers。
   - `_service_context()` 对 `tool in {"run", "evidence", "search"}` 设置 `manifest_path`。

7. 修改 `scripts/env/client.py`。
   - `_parse_args()` 加 search subparser。
   - 新增 `_search_args_from_cli()`：
     - status 返回 `{}`。
     - request 返回 `{"query": ..., "backend": ..., "engine": ...}`。
     - open-browser 返回 `{"query": ..., "engine": ...}`。
   - 新增 `_dispatch_search()` 并在 `main()` 分支接入。

**预期行为变化**

- `env.tool` router 接受 `tool="search"`。
- `prepare.runtime_context.env_tools.search` 自动出现。
- CLI 可以调用 search status/request/open-browser。
- Browser backend 有 actionable feedback；search API backend 明确不可静默使用。

**对应需求编号**

`REQ-005`、`REQ-006`、`REQ-007`、`REQ-008`、`REQ-009`、`REQ-010`、`REQ-011`、`REQ-012`、`REQ-013`、`REQ-014`、`REQ-017`、`REQ-023`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_search_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_success_response_with_canonical_machine_readable_fields -q
python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_rejection_response_with_canonical_machine_readable_fields -q
```

**阶段完成标准**

- `tests/test_search_env_tool.py` 全部通过。
- `dispatch_handler_actions()` 与 registry 完全一致。
- `python3 scripts/env/client.py search --help` 显示三个 operations。
- 没有新增 `scripts/env/tools/search_manager.py`。

### 阶段四：更新 host projection、Market skills 和 browser cockpit contract

**目标**

让 host 在自然执行路径中先看见并使用 BuddySwitch search tool，而不是靠提示文本禁止 host-native search。

**具体文件变更**

- 修改 `tools/launcher/assets/buddies/market/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/pm/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/design/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/dev/AGENTS.md`
- 修改 `tools/launcher/assets/buddies/test/AGENTS.md`
- 修改 `buddyswitch/skills/market/research-scan/SKILL.md`
- 修改 `buddyswitch/skills/market/pmf-recon/SKILL.md`
- 修改 `buddyswitch/skills/market/customer-discovery/SKILL.md`
- 修改 `buddyswitch/skills/market/positioning-copy/SKILL.md`
- 修改 `buddyswitch/skills/market/channel-discovery/SKILL.md`
- 修改 `buddyswitch/skills/market/launch-prep/SKILL.md`
- 修改 `framework/docs/browser-cockpit.md`
- 修改 `tests/test_buddyswitch_launcher.py`
- 修改 `tests/test_repo_consistency.py`

**详细步骤**

1. 在 `tests/test_buddyswitch_launcher.py` 的 runtime AGENTS projection test 中增加断言：
   - copied `AGENTS.md` 包含 `env_tools.search`。
   - copied `AGENTS.md` 包含 `Native Codex web_search is unavailable`。
   - copied `AGENTS.md` 包含 `scripts/env/client.py search status`。

2. 在 `tests/test_repo_consistency.py` 新增 `test_search_tool_visible_surface_is_projected_without_native_web_search_bypass`。
   - 扫描 `tools/launcher/assets/buddies/*.md`，断言每个 template 包含 `env_tools.search` 和 `scripts/env/client.py search status`。
   - 扫描六个 Market skills，断言每个包含 `scripts/env/client.py search open-browser` 和 `chrome-devtools-cockpit`。
   - 断言 Market skills 不包含 `web_search`、`search API/snippet/crawler fallback` 的允许性 wording；保留 negative wording `Do not use silent search API/snippet/crawler fallback`。

3. 修改五个 `tools/launcher/assets/buddies/*/AGENTS.md`。
   - Runtime Boundary 添加 search tool line。
   - Market template 添加 browser-native discovery line。

4. 修改六个 Market skill `SKILL.md`。
   - Execution Order 第一步改成：
     `Before any market research, call python3 scripts/env/client.py search open-browser --query "<initial query>" --engine <google|reddit|x|web>, then continue in chrome-devtools-cockpit and keep the workflow browser-native.`
   - Market Research Cockpit Runtime 中加入：
     `The search tool opens the browser-native discovery start page; evidence still comes from page-level traversal, not snippets.`

5. 修改 `framework/docs/browser-cockpit.md`。
   - Runtime Rules 第 1 点增加 `env.tool search.open_browser`。
   - Runtime Rules 第 3 点明确 host-native `web_search` is outside BuddySwitch product-mode surface。

**预期行为变化**

- 新 runtime instance 的 `AGENTS.md` 直接指向 `env.tool search`。
- Market skills 选择 concrete browser-native search action。
- Browser cockpit doc 与 tool layer 关系清楚：search opens start page，browser cockpit executes traversal，evidence gate proves browser work。

**对应需求编号**

`REQ-019`、`REQ-020`、`REQ-021`、`REQ-022`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_design_buddy_prompt_contract -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_search_tool_visible_surface_is_projected_without_native_web_search_bypass -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q
```

**阶段完成标准**

- Runtime AGENTS projection includes search tool guidance for every buddy.
- Every Market research skill names `search open-browser`.
- No active doc or skill suggests using host-native `web_search` inside BuddySwitch product sessions.

### 阶段五：端到端验证、residue guard 和 broad gates

**目标**

证明 search layer 没有破坏现有 env tool contracts、browser evidence、runtime skill materialization 或 launcher product-mode main path。

**具体文件变更**

- 修改 `tests/test_repo_consistency.py`
- 修改 `tests/test_env_layer_end_to_end.py` 或新增 focused product-mode search smoke in existing end-to-end file

**详细步骤**

1. 在 `tests/test_repo_consistency.py` 扩展 `test_phase8_active_surfaces_agree_on_env_tool_contract`。
   - expected tool set 加入 `"search": "search"`。
   - 断言 `env_tools["search"]["backend_model"]["allowed_backends"] == ["browser", "search_api"]`。
   - 断言没有 env tool key 以 `_manager` 结尾。

2. 在 `tests/test_repo_consistency.py` 新增 `test_native_search_bypass_is_not_active_in_product_surface`。
   - 扫描 `tools/launcher`, `scripts`, `buddyswitch/skills`, `framework/docs`, `tools/launcher/assets`。
   - 允许 `web_search = "disabled"` 和 negative text `Native Codex web_search is unavailable`。
   - 禁止 `web_search = "live"`、`web_search = "cached"`、`--search` 在 product guidance 中作为 allowed command 出现。

3. 在 `tests/test_env_layer_end_to_end.py` 新增 product-mode broker routed search status smoke。
   - 启动 live broker test fixture。
   - 调用 `python3 scripts/env/client.py search status`。
   - 断言 stdout JSON `ok == true`、`tool == "search"`、`native_codex_web_search == "disabled"`、`backend_status` shape complete。

4. 运行 py_compile。

5. 运行 focused test set and broader verification。

**预期行为变化**

- Search 成为 env tool active surface 的一员。
- Existing response contracts remain green。
- Product-mode CLI main path 可调用 search status，不触碰 host-native search。

**对应需求编号**

`REQ-001` 到 `REQ-024`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_phase8_active_surfaces_agree_on_env_tool_contract -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_native_search_bypass_is_not_active_in_product_surface -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_product_mode_env_tool_search_status_smoke -q
python3 -m py_compile tools/launcher/codex_config.py scripts/env/client.py scripts/env/tools/contracts.py scripts/env/tools/dispatch.py scripts/env/tools/router.py scripts/env/tools/responses.py scripts/env/services/search.py scripts/env_profiles.py scripts/turn_runtime.py
python3 -m pytest -p no:cacheprovider tests/test_search_env_tool.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_prepare_runtime_context.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_market_browser_evidence.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

**阶段完成标准**

- Focused tests、py_compile 和 listed broader tests 全部通过。
- `git status --short` 只显示本任务预期文件和既有 unrelated dirty files；不包含 main worktree edits。
- `rg -n "search_manager|scripts/env/tools/search_manager.py|web_search = \"live\"|web_search = \"cached\"" .` 不出现 active implementation 命中。

## 6. 迁移 / 删除策略

- Codex config migration：不迁移旧 user config；`codex_config.py` 每次 patch 时删除 top-level 和 `[features]` 中旧 `web_search` assignment，并写入单一 managed `web_search = "disabled"`。
- Startup args migration：不提供兼容转换；product-mode 原生 search args 直接失败并给出 BuddySwitch search tool command。非 product-mode 不受影响。
- Env profile migration：五个 profile JSON 同步增加 nested `tool_capability.search`；不保留 profile shape alias。
- Tool surface migration：不创建 `search_manager` alias，不创建 `scripts/env/tools/search_manager.py`，不创建 `runtime_context.env_tools.search_manager`。
- Browser path migration：`search.open_browser` 只打开 search start page；browser traversal 和 evidence capture 继续由 `chrome-devtools-cockpit` 与 evidence env tool 承担。
- Search API migration：本任务不接入真实 provider；`search_api` backend 保持 structured unavailable/approval-required feedback。退出条件是有明确 BuddySwitch-managed provider spec、credential boundary、privacy/security review 和 tests；在此之前不得添加 silent provider fallback。
- Runtime broker v2：本任务不修改 runtime broker v2 architecture；如果当前 worktree 已有 broker v2 dirty files，实现时只在必要接口上兼容，不重构 broker。

## 7. 完成定义

整个任务完成必须同时满足：

- Product-mode Codex config 包含单一 `web_search = "disabled"`。
- Product-mode `--search` 和 `web_search` config override 在 Codex 启动前被拒绝，stderr 指向 `env.tool search`。
- `prepare.runtime_context.env_tools.search` 存在，且不出现 `search_manager` key。
- `env.tool` router 接受 `tool="search"`，支持 `status`、`request`、`open_browser`。
- `search.status` 返回完整 backend/capability facts。
- `search.request` 对 browser/search_api/missing/unknown backend 给出符合需求的结构化反馈。
- `search.open_browser` 对 supported engines 构造正确 URL，browser endpoint 可用时打开页面，不可用时返回恢复命令。
- 所有 buddy profiles 暴露 coherent search boundary，且 profile 中没有 workflow default。
- Market research skills 显式使用 `search open-browser` 作为 discovery start，并保留 browser evidence gate。
- AGENTS templates 明确 native Codex `web_search` 不可用且 search 通过 BuddySwitch `env.tool`。
- Existing env tool response contracts、router/dispatch coverage、profile validation、runtime context tests、browser evidence tests 继续通过。
- `python3 -m py_compile` 覆盖 changed Python files。
- Broader verification 命令通过，若受本地环境阻塞，阻塞原因和未验证风险在执行报告中列明。

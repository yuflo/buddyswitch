# Tool-Visible Search Layer Test Plan

## 1. 测试设计原则

- 测试从 memo 的用户可见行为出发：BuddySwitch product session 不能看见 Codex native `web_search` 旁路，host 能看见并调用 `env.tool search`，tool response 给出机器可读的 backend、权限和下一步动作。
- 测试验证外部可观察行为和状态：launcher stderr、fake Codex capture、patched config text、runtime context JSON、env.tool response JSON、CLI help/exit code、AGENTS/skill 文本投影。
- 测试不根据内部实现细节硬编码通过条件：registry/dispatch coverage 由 `TOOL_REGISTRY` 推导，profile matrix 遍历所有 buddies，search URL 断言覆盖多个 engine 和 query 组合。
- 所有失败模式都要有断言：缺失 backend、未知 backend、空 query、未知 engine、browser endpoint 缺失、browser endpoint 不可达、search API 未配置、Market approval gate。
- Browser evidence gate 继续由现有 tests 证明，search tests 只证明 search tool 打开 discovery 起点，不把 search 伪装成 evidence provider。
- 手动验证只作为补充；本任务涉及的 launcher、profile、runtime context、CLI、router、response contract、repo consistency 都可自动化。

## 2. 需求覆盖矩阵

| Requirement | Automated coverage |
| --- | --- |
| `REQ-001` | `TS-LAUNCH-001`, `TS-REG-002`, `TS-E2E-001` |
| `REQ-002` | `TS-LAUNCH-002`, `TS-REG-002` |
| `REQ-003` | `TS-LAUNCH-002` |
| `REQ-004` | `TS-LAUNCH-003` |
| `REQ-005` | `TS-CONTRACT-001`, `TS-PREPARE-001`, `TS-REG-001` |
| `REQ-006` | `TS-CONTRACT-001`, `TS-CLI-001`, `TS-E2E-001` |
| `REQ-007` | `TS-REQUEST-002`, `TS-CLI-002`, `TS-NEG-001` |
| `REQ-008` | `TS-STATUS-001`, `TS-STATUS-002`, `TS-E2E-001` |
| `REQ-009` | `TS-STATUS-002`, `TS-PROFILE-001`, `TS-REG-003` |
| `REQ-010` | `TS-REQUEST-001`, `TS-REQUEST-004` |
| `REQ-011` | `TS-REQUEST-003`, `TS-REQUEST-005` |
| `REQ-012` | `TS-OPEN-001`, `TS-OPEN-002` |
| `REQ-013` | `TS-OPEN-003`, `TS-OPEN-004`, `TS-NEG-002` |
| `REQ-014` | `TS-REQUEST-004`, `TS-OPEN-002`, `TS-NEG-003` |
| `REQ-015` | `TS-PROFILE-001`, `TS-PROFILE-002`, `TS-STATUS-001`, `TS-STATUS-002` |
| `REQ-016` | `TS-PROFILE-001`, `TS-PREPARE-001`, `TS-REG-003` |
| `REQ-017` | `TS-PREPARE-001`, `TS-CONTRACT-001` |
| `REQ-018` | `TS-PREPARE-001` |
| `REQ-019` | `TS-PROJECTION-001`, `TS-E2E-002` |
| `REQ-020` | `TS-SKILL-001` |
| `REQ-021` | `TS-EVIDENCE-001`, `TS-SKILL-001` |
| `REQ-022` | `TS-REG-003`, `TS-REG-004` |
| `REQ-023` | `TS-RESPONSE-001`, `TS-RESPONSE-002`, `TS-CONTRACT-001` |
| `REQ-024` | `TS-WORKTREE-001` |

不需要纯手动覆盖的需求；所有 acceptance criteria 均可用自动化或命令级验证证明。可选手动验证只用于实际浏览器页面打开体验。

## 3. 测试分层

### 单元测试

目的：证明 config patch、profile validation、search service normalization、URL building、response contract 在无真实 Codex 和无真实 browser 的条件下稳定。

覆盖范围：

- `tools/launcher/codex_config.py`
- `scripts/env_profiles.py`
- `scripts/env/services/search.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/dispatch.py`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_sandbox.py tests/test_buddy_env_profiles.py tests/test_search_env_tool.py tests/test_env_tool_response_contract.py -q
```

### 集成测试

目的：证明 launcher、prepare runtime context、router/dispatch、broker-routed env tool 主路径连起来后行为一致。

覆盖范围：

- `./buddyswitch-codex instance start`
- `scripts/turn_runtime.py`
- `scripts/env/client.py`
- `scripts/env/tools/router.py`
- `scripts/env/tools/dispatch.py`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_prepare_runtime_context.py tests/test_env_tool_router.py tests/test_env_layer_end_to_end.py -q
```

### CLI、API、UI 或主路径运行测试

目的：证明 skill-facing CLI 能稳定产生 broker envelope，并能从 stdout/stderr、exit code 和 JSON payload 观察结果。

覆盖范围：

- `python3 scripts/env/client.py search status`
- `python3 scripts/env/client.py search request`
- `python3 scripts/env/client.py search open-browser`
- `./buddyswitch-codex instance start --buddy <buddy> -- <codex args>`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_instance_start_rejects_native_search_args_before_codex_launch -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_product_mode_env_tool_search_status_smoke -q
python3 scripts/env/client.py search --help
```

### 回归测试

目的：防止本任务破坏已有 env tool contracts、Market browser evidence gate、runtime skill materialization 和 active surface consistency。

覆盖范围：

- Existing env tool response contract
- Existing router/dispatch contract
- Market browser evidence tests
- Runtime skill repo consistency checks
- Anti-manager and native-search residue scans

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_market_browser_evidence.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

### 手动验证

目的：补充确认实际 Chrome DevTools endpoint 打开页面后的可操作体验。

手动步骤：

1. 在 dev2258 启动一个 Market instance：`./buddyswitch-codex instance start --buddy market`。
2. 在同一 instance 环境调用：`python3 scripts/env/client.py search open-browser --query "creator analytics pain" --engine google`。
3. 观察 JSON 中 `page_opened == true`、`target_url` 是 Google search URL、`command_hint` 指向 `chrome-devtools-cockpit`。
4. 用 `chrome-devtools-cockpit` 选择打开的 page，确认 page title 或 URL 与 `target_url` 对应。

## 4. 详细测试用例

### `TS-LAUNCH-001`: config patch disables native web_search

- 覆盖需求：`REQ-001`
- 场景：已有 Codex config 明确打开 native web search，BuddySwitch patch 后必须关闭。
- 前置条件：临时 config 包含 top-level `web_search = "live"` 和 `[features] web_search = "cached"`。
- 输入：调用 `tools/launcher/codex_config.py` patch helper 或现有 launcher config patch test fixture。
- 预期输出或状态变化：patched config 只包含一个 BuddySwitch-managed `web_search = "disabled"`；不包含 `"live"` 或 `"cached"`。
- 断言重点：top-level disabled 唯一性、旧值清理、重复 patch 后 idempotent。
- 测试类型：单元测试。
- 建议测试文件和名称：`tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_patch_forces_web_search_disabled_and_removes_existing_web_search_settings`。

### `TS-LAUNCH-002`: product launcher rejects native search escapes

- 覆盖需求：`REQ-002`, `REQ-003`
- 场景：用户在 BuddySwitch product session 启动时传入 Codex native search args。
- 前置条件：fake Codex binary 写 capture file；`instance start --buddy pm` 进入 product mode。
- 输入：分别传入 `--search`、`--search=live`、`-c web_search=live`、`-cweb_search=cached`、`--config web_search=live`、`--config=web_search=cached`。
- 预期输出或状态变化：return code 为 2；stderr 包含 `Native Codex web_search is disabled`、`scripts/env/client.py search status`、`scripts/env/client.py search open-browser`；fake Codex capture file 不存在。
- 断言重点：所有 escape 变体都在 Codex 进程启动前被拒绝，错误信息指向 BuddySwitch search tool。
- 测试类型：CLI 集成测试。
- 建议测试文件和名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_instance_start_rejects_native_search_args_before_codex_launch`。

### `TS-LAUNCH-003`: non-product launch keeps user args

- 覆盖需求：`REQ-004`
- 场景：用户不选择 buddy 的普通 local launch 仍可透传 Codex args。
- 前置条件：fake Codex binary 可记录 argv。
- 输入：`./buddyswitch-codex instance start -- --search`。
- 预期输出或状态变化：fake Codex 被执行；capture 中 `argv == ["--search"]`。
- 断言重点：guard 只作用于 BuddySwitch product mode，不污染普通 Codex use case。
- 测试类型：CLI 集成测试。
- 建议测试文件和名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_local_non_buddy_start_allows_codex_search_args`。

### `TS-PROFILE-001`: all profiles expose coherent search boundary

- 覆盖需求：`REQ-009`, `REQ-015`, `REQ-016`
- 场景：每个 buddy profile 都有同形状的 `tool_capability.search`。
- 前置条件：读取 `buddyswitch/env-profiles/{market,pm,design,dev,test}.json`。
- 输入：调用 `scripts/env_profiles.py` validation helpers 或现有 profile fixture。
- 预期输出或状态变化：Market search boundary 为 `disabled/required/user-approved-only`；非 Market 为 `disabled/available/available`；nested browser cockpit 与 legacy `tool_capability.browser_cockpit` 一致。
- 断言重点：profile 只出现 capability fields，不出现 `preferred_backend`、`default_engine`、`market_workflow`。
- 测试类型：单元测试。
- 建议测试文件和名称：`tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_profiles_validate_with_matrix_rules`。

### `TS-PROFILE-002`: validate-all rejects malformed search boundary

- 覆盖需求：`REQ-015`
- 场景：profile 缺少 search boundary 或 search enums 非法。
- 前置条件：使用临时 profile copy，移除 `tool_capability.search` 或设置 `search_api = "silent-fallback"`。
- 输入：调用 `validate_env_profile()`。
- 预期输出或状态变化：validation 返回明确错误，指出 buddy id 和非法 search field。
- 断言重点：缺字段、非法 enum、Market/non-Market matrix 不匹配都失败。
- 测试类型：单元负向测试。
- 建议测试文件和名称：`tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_search_capability_boundary_is_required_and_validated`。

### `TS-PREPARE-001`: prepare projects search runtime context

- 覆盖需求：`REQ-005`, `REQ-017`, `REQ-018`
- 场景：host 在行动前通过 runtime context 看见 search tool 和 boundary。
- 前置条件：对每个 buddy 运行 prepare fixture。
- 输入：读取 `runtime_context.env_tools`、`runtime_context.tool_requirements`、`runtime_context.capability_boundary`。
- 预期输出或状态变化：`env_tools.search` 存在；`env_tools.search.actions` 包含 `status`、`request`、`open_browser`；`tool_requirements.search` 等于 profile search boundary；`capability_boundary.search.env_tool_source == "runtime_context.env_tools.search"`。
- 断言重点：没有 `env_tools.search_manager`；没有 `_manager` suffix key；runtime context 不含 workflow default 字段。
- 测试类型：集成测试。
- 建议测试文件和名称：`tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_search_capability_boundary_for_each_buddy`。

### `TS-CONTRACT-001`: registry, router, dispatch agree on search actions

- 覆盖需求：`REQ-005`, `REQ-006`, `REQ-017`, `REQ-023`
- 场景：新增 search 后 env tool active surface 仍由 registry 驱动。
- 前置条件：`TOOL_REGISTRY` 中包含 `search`。
- 输入：调用 `tool_contracts.tool_actions()`、`router.tool_actions()`、`dispatch.dispatch_handler_actions()`。
- 预期输出或状态变化：三个来源对 `search` action set 一致，且 set 为 `{"status", "request", "open_browser"}`。
- 断言重点：registry entry 包含 `backend_model.allowed_backends == ["browser", "search_api"]` 和 `allowed_engines == ["google", "web", "reddit", "x"]`。
- 测试类型：单元/contract 测试。
- 建议测试文件和名称：`tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions`。

### `TS-CLI-001`: search CLI exposes three operations

- 覆盖需求：`REQ-006`
- 场景：skill-facing CLI 可以调用 search status、request、open-browser。
- 前置条件：仓库根目录为 dev2258。
- 输入：`python3 scripts/env/client.py search --help`。
- 预期输出或状态变化：stdout 包含 `status`、`request`、`open-browser`、`--query`、`--backend`、`--engine`。
- 断言重点：CLI operation 名称为 `open-browser`，broker action payload 为 `open_browser`。
- 测试类型：CLI 测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_cli_help_exposes_status_request_and_open_browser`。

### `TS-CLI-002`: CLI rejects invalid request arguments before broker call

- 覆盖需求：`REQ-007`, `REQ-014`
- 场景：CLI 用户提供缺失 backend 或非法 engine。
- 前置条件：无 broker 运行。
- 输入：`python3 scripts/env/client.py search request --query "x"` 和 `python3 scripts/env/client.py search open-browser --query "x" --engine unknown`。
- 预期输出或状态变化：exit code 为 2；stderr 来自 argparse 并指出缺失 `--backend` 或 invalid choice。
- 断言重点：CLI 层阻止明显无效输入，service 层仍有 broker payload validation 覆盖。
- 测试类型：CLI 负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_cli_rejects_missing_backend_and_unknown_engine`。

### `TS-STATUS-001`: market status reports browser path and approval boundary

- 覆盖需求：`REQ-008`, `REQ-009`, `REQ-015`, `REQ-023`
- 场景：Market buddy 查询当前可用 search path。
- 前置条件：active buddy 为 `market`，instance payload 有 `browser_port = 9222`。
- 输入：env.tool envelope `{"tool":"search","action":"status","args":{}}`。
- 预期输出或状态变化：`ok == true`；`native_codex_web_search == "disabled"`；`available_backends == ["browser"]`；browser available true；search_api available false 且 permission 为 `user-approved-only`。
- 断言重点：payload 包含 `permission_boundary`、`allowed_next_actions`、`command_hint`；不包含 Market workflow default。
- 测试类型：单元/服务测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_status_reports_market_profile_backend_and_native_search_boundary`。

### `TS-STATUS-002`: non-market status shares tool without Market default

- 覆盖需求：`REQ-008`, `REQ-009`, `REQ-015`
- 场景：Dev buddy 使用同一个 search tool，但 profile boundary 更宽松。
- 前置条件：active buddy 为 `dev`，instance payload 有 browser port。
- 输入：env.tool `search.status`。
- 预期输出或状态变化：`capability_boundary.search_api == "available"`；`capability_boundary.browser_cockpit == "available"`；status 不包含 `market_workflow`、`browser_native_required_by_market`、`preferred_backend`。
- 断言重点：tool 是 shared surface，不是 Market-only policy。
- 测试类型：单元/服务测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_status_reports_non_market_boundary_without_market_workflow_default`。

### `TS-REQUEST-001`: browser request returns actionable instruction

- 覆盖需求：`REQ-010`, `REQ-023`
- 场景：host 显式选择 browser backend，但只请求 instruction，不打开页面。
- 前置条件：active buddy 为 `market`，browser endpoint 可从 instance payload 构造。
- 输入：`{"query":"creator analytics pain","backend":"browser","engine":"reddit"}`。
- 预期输出或状态变化：`ok == true`；`backend == "browser"`；`target_url == "https://www.reddit.com/search/?q=creator+analytics+pain"`；`page_opened == false`；`required_cockpit_tool == "chrome-devtools-cockpit"`。
- 断言重点：`allowed_next_actions` 指向 `search.open_browser` 和 browser traversal；不生成 evidence token。
- 测试类型：单元/服务测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_browser_returns_actionable_instruction_without_opening_page`。

### `TS-REQUEST-002`: missing or unknown backend is rejected

- 覆盖需求：`REQ-007`, `REQ-023`
- 场景：broker/API caller 绕过 CLI，payload 没有 backend 或 backend 非法。
- 前置条件：active instance 存在。
- 输入：`{"query":"x"}` 和 `{"query":"x","backend":"auto"}`。
- 预期输出或状态变化：`ok == false`；error code 为 `E_SEARCH_BACKEND`；payload 包含 allowed values `["browser", "search_api"]`、`permission_boundary`、`allowed_next_actions`、`command_hint`。
- 断言重点：没有隐式 `auto`；错误是机器可读的 canonical rejection。
- 测试类型：单元负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_rejects_missing_or_unknown_backend`。

### `TS-REQUEST-003`: Market search_api requires approval

- 覆盖需求：`REQ-011`, `REQ-015`, `REQ-023`
- 场景：Market 请求 `search_api` backend。
- 前置条件：active buddy 为 `market`，`SEARCH_API_PROVIDER_AVAILABLE == False`。
- 输入：`{"query":"creator analytics pain","backend":"search_api","engine":"web"}`。
- 预期输出或状态变化：`ok == false`；error code 为 `E_SEARCH_BACKEND_APPROVAL_REQUIRED`；`permission_boundary == "search.search_api.user_approved_only"`；`command_hint` 指向 browser-native command。
- 断言重点：不会静默 downgrade 到 search API，也不会自动改用 browser 后装作成功。
- 测试类型：单元负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_search_api_returns_market_approval_required`。

### `TS-REQUEST-004`: browser request builds URLs for all supported engines

- 覆盖需求：`REQ-010`, `REQ-014`
- 场景：同一 query 使用四个 supported engines。
- 前置条件：active instance 有 browser endpoint。
- 输入：`engine` 分别为 `google`、`web`、`reddit`、`x`，query 为 `creator analytics pain`。
- 预期输出或状态变化：Google 和 web 使用 `https://www.google.com/search?q=creator+analytics+pain`；Reddit 使用 `https://www.reddit.com/search/?q=creator+analytics+pain`；X 使用 `https://x.com/search?q=creator+analytics+pain&src=typed_query`。
- 断言重点：query URL encoding 稳定；supported engines 固定。
- 测试类型：参数化单元测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_browser_builds_expected_url_for_supported_engines`。

### `TS-REQUEST-005`: non-market search_api reports provider unavailable

- 覆盖需求：`REQ-011`, `REQ-015`
- 场景：Dev buddy profile 允许 search_api，但没有真实 provider。
- 前置条件：active buddy 为 `dev`，`SEARCH_API_PROVIDER_AVAILABLE == False`。
- 输入：`{"query":"release notes","backend":"search_api","engine":"web"}`。
- 预期输出或状态变化：`ok == false`；error code 为 `E_SEARCH_BACKEND_UNAVAILABLE`；reason 指出 no BuddySwitch-managed search API provider configured。
- 断言重点：profile permission 与 provider availability 分开表达。
- 测试类型：单元负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_search_api_returns_non_market_provider_unavailable`。

### `TS-OPEN-001`: open_browser opens page through CDP endpoint

- 覆盖需求：`REQ-012`, `REQ-023`
- 场景：browser endpoint 可用时，tool 用 CDP `/json/new?<target_url>` 打开 search page。
- 前置条件：本地 test HTTP server 监听 fake CDP endpoint，记录 request method 和 path；instance payload `browser_port` 指向该 server。
- 输入：`{"query":"creator analytics pain","engine":"google"}`。
- 预期输出或状态变化：server 收到 `PUT /json/new?<encoded target_url>`；response `ok == true`；`page_opened == true`；`target_url` 是 Google search URL。
- 断言重点：target URL 被 percent-encoded 放入 CDP request；response 包含 browser endpoint 和 cockpit next action。
- 测试类型：集成式服务测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_open_browser_opens_cdp_page_with_encoded_target_url`。

### `TS-OPEN-002`: open_browser supports all engines and special query chars

- 覆盖需求：`REQ-012`, `REQ-014`
- 场景：query 包含空格、`+`、`&`、非 ASCII 文本时 URL encoding 正确。
- 前置条件：fake CDP endpoint 可记录 path。
- 输入：query 分别为 `creator analytics pain`、`a+b & c`、`用户 访谈`，engine 覆盖 `google`、`reddit`、`x`。
- 预期输出或状态变化：`target_url` query component 经标准 URL encoding；CDP path 中 target URL 再经过 percent-encoding。
- 断言重点：不是简单字符串拼接；多个输入组合防止硬编码。
- 测试类型：参数化集成式服务测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_open_browser_encodes_queries_for_supported_engines`。

### `TS-OPEN-003`: missing browser endpoint returns recovery feedback

- 覆盖需求：`REQ-013`, `REQ-023`
- 场景：instance 没有 browser port。
- 前置条件：instance payload 中无 `browser_port`。
- 输入：`{"query":"creator analytics pain","engine":"google"}`。
- 预期输出或状态变化：`ok == false`；error code 为 `E_SEARCH_BROWSER_UNAVAILABLE`；payload 包含 `command_hint = "./buddyswitch-codex env browser ensure --instance <instance_id>"`。
- 断言重点：返回可恢复 feedback，不崩溃、不静默成功。
- 测试类型：单元负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_open_browser_returns_recovery_feedback_when_browser_missing`。

### `TS-OPEN-004`: unreachable browser endpoint reports open failure

- 覆盖需求：`REQ-013`
- 场景：instance 有 browser port，但端口不可连接或 CDP 返回非 2xx。
- 前置条件：使用一个未监听端口，或 fake server 返回 HTTP 500。
- 输入：`{"query":"creator analytics pain","engine":"google"}`。
- 预期输出或状态变化：`ok == false`；error code 为 `E_SEARCH_BROWSER_OPEN_FAILED`；payload 包含 `target_url`、`browser_endpoint`、`allowed_next_actions`、`command_hint`。
- 断言重点：保留 target URL，便于 host 继续手动恢复。
- 测试类型：集成式负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_open_browser_reports_cdp_open_failure_with_target_url`。

### `TS-NEG-001`: broker payload backend validation is independent of CLI

- 覆盖需求：`REQ-007`
- 场景：API caller 直接发送 `backend=""`、`backend=null`、`backend=[]`。
- 前置条件：active instance 存在。
- 输入：三个 payload 通过 router dispatch。
- 预期输出或状态变化：全部返回 `E_SEARCH_BACKEND`，并带 allowed backend values。
- 断言重点：不能只依赖 argparse validation。
- 测试类型：单元负向测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_request_rejects_empty_null_and_non_string_backend`。

### `TS-NEG-002`: invalid browser port is rejected

- 覆盖需求：`REQ-013`
- 场景：instance payload 中 `browser_port` 不是有效 TCP port。
- 前置条件：browser_port 分别为 `"abc"`、`0`、`70000`。
- 输入：`search.open_browser` payload。
- 预期输出或状态变化：`E_SEARCH_BROWSER_UNAVAILABLE`，reason 指出 invalid browser port。
- 断言重点：不会构造非法 endpoint 或向错误地址发请求。
- 测试类型：单元边界测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_open_browser_rejects_invalid_browser_port`。

### `TS-NEG-003`: empty query and unknown engine are rejected

- 覆盖需求：`REQ-014`, `REQ-023`
- 场景：broker/API caller 传空 query 或未知 engine。
- 前置条件：active instance 存在。
- 输入：`query=""`、`query="   "`、`query=[]`、`engine=""`、`engine="bing"`。
- 预期输出或状态变化：query failures 返回 `E_SEARCH_QUERY`；engine failures 返回 `E_SEARCH_ENGINE`；payload 包含 supported engine list。
- 断言重点：错误码区分 query 和 engine；response contract 字段完整。
- 测试类型：单元负向/边界测试。
- 建议测试文件和名称：`tests/test_search_env_tool.py::SearchEnvToolTests::test_search_rejects_empty_query_and_unknown_engine`。

### `TS-RESPONSE-001`: search success responses use canonical fields

- 覆盖需求：`REQ-023`
- 场景：response contract suite 遍历 env tool success cases。
- 前置条件：添加 `("search", "status", {})` success fixture。
- 输入：调用 response contract helper。
- 预期输出或状态变化：success payload 包含 `ok == true`、`tool`、`action`、`permission_boundary`、`allowed_next_actions`、`command_hint`。
- 断言重点：search 不绕过 canonical response shape。
- 测试类型：contract 测试。
- 建议测试文件和名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_success_response_with_canonical_machine_readable_fields`。

### `TS-RESPONSE-002`: search rejection responses use canonical fields

- 覆盖需求：`REQ-023`
- 场景：response contract suite 遍历 env tool rejection cases。
- 前置条件：添加 `("search", "request", {"query":"x"})` rejection fixture。
- 输入：调用 response contract helper。
- 预期输出或状态变化：rejection payload 包含 `ok == false`、`tool`、`action`、`error.code`、`error.message`、`permission_boundary`、`allowed_next_actions`、`command_hint`。
- 断言重点：rejection 不只是字符串错误。
- 测试类型：contract 测试。
- 建议测试文件和名称：`tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_rejection_response_with_canonical_machine_readable_fields`。

### `TS-PROJECTION-001`: AGENTS templates project search surface

- 覆盖需求：`REQ-019`
- 场景：每个 buddy runtime prompt 都指向 BuddySwitch search tool。
- 前置条件：读取 `tools/launcher/assets/buddies/{market,pm,design,dev,test}/AGENTS.md`。
- 输入：repo consistency scan。
- 预期输出或状态变化：每个 template 包含 `env_tools.search`、`Native Codex web_search is unavailable`、`scripts/env/client.py search status`。
- 断言重点：AGENTS projection 指向 env.tool，但不作为唯一 enforcement。
- 测试类型：repo consistency 测试。
- 建议测试文件和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_search_tool_visible_surface_is_projected_without_native_web_search_bypass`。

### `TS-SKILL-001`: Market skills choose browser-native search action

- 覆盖需求：`REQ-020`, `REQ-021`
- 场景：Market research skills 的 discovery start 明确调用 BuddySwitch search tool。
- 前置条件：读取六个 Market `SKILL.md`。
- 输入：repo consistency scan。
- 预期输出或状态变化：每个 skill 包含 `python3 scripts/env/client.py search open-browser` 和 `chrome-devtools-cockpit`；保留 evidence gate wording；没有允许 host-native `web_search` 的文本。
- 断言重点：skill 选择 workflow，env profile 不承载 workflow default。
- 测试类型：repo consistency 回归测试。
- 建议测试文件和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_market_skills_start_research_with_search_open_browser_and_keep_evidence_gate`。

### `TS-EVIDENCE-001`: browser evidence gate remains required

- 覆盖需求：`REQ-021`
- 场景：Market artifact-producing persist 没有 browser evidence token 时仍失败。
- 前置条件：使用现有 Market browser evidence fixture。
- 输入：artifact persist payload 缺少 broker-issued `tool_evidence`，同时存在 search response payload。
- 预期输出或状态变化：persist 拒绝；error 指向 browser evidence requirement。
- 断言重点：search response 不能替代 page-level browser evidence。
- 测试类型：回归测试。
- 建议测试文件和名称：`tests/test_market_browser_evidence.py::MarketBrowserEvidenceTests::test_search_tool_response_does_not_satisfy_market_browser_evidence_gate`。

### `TS-REG-001`: active surfaces contain search and no manager alias

- 覆盖需求：`REQ-005`, `REQ-017`
- 场景：active env tool surface 与 contract registry 一致。
- 前置条件：读取 `scripts/env/tools/contracts.py` 和 runtime context desc。
- 输入：repo consistency active surface check。
- 预期输出或状态变化：`search` 是 env tool key；没有 `search_manager` key；没有任何 env tool key 以 `_manager` 结尾。
- 断言重点：不为了兼容 memo wording 重新引入 manager surface。
- 测试类型：repo consistency 测试。
- 建议测试文件和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_phase8_active_surfaces_agree_on_env_tool_contract`。

### `TS-REG-002`: native search bypass is absent from product surface

- 覆盖需求：`REQ-001`, `REQ-002`
- 场景：代码、docs、skills、templates 不能重新提供 native search allowed path。
- 前置条件：扫描 `tools/launcher`、`scripts`、`buddyswitch/skills`、`framework/docs`、`tools/launcher/assets`。
- 输入：repo consistency scan。
- 预期输出或状态变化：允许 `web_search = "disabled"` 和 `Native Codex web_search is unavailable`；禁止 active guidance 中出现 `web_search = "live"`、`web_search = "cached"`、把 `--search` 作为 product-mode allowed command。
- 断言重点：防止 prompt/doc 层重新暴露旁路。
- 测试类型：repo consistency 回归测试。
- 建议测试文件和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_native_search_bypass_is_not_active_in_product_surface`。

### `TS-REG-003`: profiles and docs do not encode workflow routing

- 覆盖需求：`REQ-009`, `REQ-016`, `REQ-022`
- 场景：static profile 和 runtime status 只表达 capability facts。
- 前置条件：读取 env profiles、runtime context、`search.status` payload。
- 输入：scan forbidden keys and phrases。
- 预期输出或状态变化：不出现 `default_engine`、`preferred_backend`、`market_workflow`、`route_research`、`auto_backend`。
- 断言重点：不把 hidden routing rules 放进 profile 或 status。
- 测试类型：repo consistency/contract 测试。
- 建议测试文件和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_search_capability_boundaries_do_not_encode_workflow_defaults`。

### `TS-REG-004`: no governance or framework drift

- 覆盖需求：`REQ-022`
- 场景：本任务没有引入 hidden P2 governance loop 或 broad policy engine。
- 前置条件：扫描 changed search-related files。
- 输入：repo consistency scan。
- 预期输出或状态变化：没有新增 `search_policy.py`、`governance`、`workflow_router`、`rule_engine`、`provenance_audit`、`plugin` naming in search path。
- 断言重点：架构保持 env tool visible surface，不变成 policy framework。
- 测试类型：repo consistency 测试。
- 建议测试文件和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_search_layer_does_not_add_hidden_governance_or_policy_engine`。

### `TS-E2E-001`: product-mode env tool search status smoke

- 覆盖需求：`REQ-001`, `REQ-006`, `REQ-008`
- 场景：实际 product-mode runtime main path 可以调用 search status。
- 前置条件：使用现有 broker end-to-end fixture 启动 product-mode test instance。
- 输入：`python3 scripts/env/client.py search status`。
- 预期输出或状态变化：stdout JSON `ok == true`、`tool == "search"`、`native_codex_web_search == "disabled"`、`backend_status.browser` 和 `backend_status.search_api` shape complete。
- 断言重点：CLI 通过 runtime broker，而不是直接调用 service shortcut。
- 测试类型：端到端 smoke。
- 建议测试文件和名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_product_mode_env_tool_search_status_smoke`。

### `TS-E2E-002`: runtime AGENTS copy contains search projection

- 覆盖需求：`REQ-019`
- 场景：instance start 后工作区中的 `AGENTS.md` 包含 search guidance。
- 前置条件：fake Codex launcher 不真正启动 interactive session。
- 输入：`./buddyswitch-codex instance start --buddy design -- --version` 或现有 launcher prompt contract fixture。
- 预期输出或状态变化：copied runtime `AGENTS.md` 包含 `env_tools.search`、`Native Codex web_search is unavailable`、`scripts/env/client.py search status`。
- 断言重点：template text 实际进入 instance workspace。
- 测试类型：launcher 集成测试。
- 建议测试文件和名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_design_buddy_prompt_contract`。

### `TS-WORKTREE-001`: changes stay in dev2258

- 覆盖需求：`REQ-024`
- 场景：实现完成前确认没有 main worktree 写入。
- 前置条件：当前 shell `pwd` 为 `/Users/chen/Dev/buddyswitch/.worktrees/dev2258`。
- 输入：`pwd`、`git rev-parse --show-toplevel`、`git status --short`。
- 预期输出或状态变化：top-level 为 dev2258 worktree；status 只包含本任务文件和已知 unrelated dirty files。
- 断言重点：不混入 runtime broker v2 refactor，不修改 `/Users/chen/Dev/buddyswitch` main checkout。
- 测试类型：命令级验证。
- 建议测试文件和名称：自动化测试不写入仓库；执行报告中记录命令输出摘要。

## 5. 负向与边界测试

- 缺失数据：`search.request` 缺 `backend` 返回 `E_SEARCH_BACKEND`；`search.open_browser` 缺 `query` 返回 `E_SEARCH_QUERY`；profile 缺 `tool_capability.search` 使 validation fail。
- 无效状态：browser endpoint 缺失、browser port 非法、browser port 不可达、CDP 返回 500，分别返回 `E_SEARCH_BROWSER_UNAVAILABLE` 或 `E_SEARCH_BROWSER_OPEN_FAILED`。
- 重复操作：两次 config patch 仍只有一个 `web_search = "disabled"`；两次 `search.status` 不改变 canonical state；两次 `search.request backend=browser` 都 `page_opened=false`。
- 并发或顺序敏感行为：`search.open_browser` 使用 request-local query/engine 构造 target URL，不读取或写入 shared canonical object；fake CDP test 记录每次 request path，证明两个不同 query 不串值。
- 空输入：`query=""`、`query="   "`、`engine=""`、`backend=""` 都返回明确 error code。
- 空集合：profile matrix 遍历实际 buddies，如果没有任何 profile 被发现，test 显式失败并提示 env profile glob returned empty。
- 空记录：instance payload 缺 `browser_port` 时返回 recovery command，不假定 browser 已存在。
- 权限异常：Market `search_api` 返回 approval required；non-Market `search_api` 在 provider 缺失时返回 unavailable；两者都不静默执行外部 search。
- 路径异常：repo consistency 扫描防止新增 `scripts/env/tools/search_manager.py`、`search_policy.py`、`workflow_router.py`。
- 配置异常：product startup args 中 `-cweb_search=cached` 和 `--config=web_search=live` 被拒绝，避免只处理带空格的常见形式。
- 外部依赖异常：CDP endpoint unreachable 和 HTTP 500 都有 deterministic fake server 覆盖，不依赖真实浏览器稳定性。

## 6. 作弊防护

- 多输入组合：native search escape tests 覆盖六种 arg spelling；engine tests 覆盖四个 supported engines 和多个 query 字符组合；profile tests 遍历五个 buddies。
- 行为和状态双断言：launcher tests 同时断言 exit code、stderr 和 fake Codex 未执行；CDP tests 同时断言 response payload 和 fake server request path。
- Registry-driven assertions：router/dispatch tests 从 `TOOL_REGISTRY` 派生 action set，防止只在 CLI 层硬编码 search 而没有 env.tool coverage。
- No-manager residue scan：repo consistency 检查 `search_manager` public key 和 file path，防止实现用 alias 迎合 memo wording。
- No-auto backend assertion：missing/unknown backend tests 断言 `ok == false` 和 allowed values，防止实现默默选择 browser。
- Evidence separation：Market evidence regression 用 search response 作为非 evidence 输入，证明 search tool 没有绕过 browser evidence gate。
- Provider separation：Market 和 non-Market search_api 分别断言 approval required 与 provider unavailable，防止统一硬编码一个错误码。
- Contract field assertions：success 和 rejection tests 验证 canonical fields，不接受只返回 human-readable string。
- Product/non-product split：同一 `--search` arg 在 product mode 被拒绝、在 non-product mode 被透传，防止全局禁用误伤普通 Codex。
- Repo consistency guard：扫描 active docs、skills、templates，防止代码通过但指导文本继续建议 host-native `web_search`。

## 7. 验证命令清单

### Focused test 命令

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_sandbox.py::BuddyEnvSandboxTests::test_patch_forces_web_search_disabled_and_removes_existing_web_search_settings -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_product_instance_start_rejects_native_search_args_before_codex_launch -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_local_non_buddy_start_allows_codex_search_args -q
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_profiles.py::BuddyEnvProfilesTests::test_profiles_validate_with_matrix_rules -q
python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_projects_search_capability_boundary_for_each_buddy -q
python3 -m pytest -p no:cacheprovider tests/test_search_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_tool_router.py::EnvToolRouterTests::test_dispatch_handler_coverage_matches_registry_actions -q
python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_success_response_with_canonical_machine_readable_fields -q
python3 -m pytest -p no:cacheprovider tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_each_env_tool_has_rejection_response_with_canonical_machine_readable_fields -q
```

### Broader verification 命令

```bash
python3 scripts/env_profiles.py validate-all
python3 scripts/env/client.py search --help
python3 -m pytest -p no:cacheprovider tests/test_buddy_env_profiles.py tests/test_prepare_runtime_context.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_market_browser_evidence.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
python3 -m py_compile tools/launcher/codex_config.py scripts/env/client.py scripts/env/tools/contracts.py scripts/env/tools/dispatch.py scripts/env/tools/router.py scripts/env/tools/responses.py scripts/env/services/search.py scripts/env_profiles.py scripts/turn_runtime.py
```

### 任务完成前必须运行的最终验证命令

```bash
pwd
git rev-parse --show-toplevel
git status --short
rg -n "search_manager|scripts/env/tools/search_manager.py|web_search = \"live\"|web_search = \"cached\"" tools scripts tests buddyswitch framework
python3 -m pytest -p no:cacheprovider tests/test_search_env_tool.py tests/test_env_tool_router.py tests/test_env_tool_response_contract.py tests/test_prepare_runtime_context.py tests/test_buddy_env_profiles.py tests/test_buddy_env_sandbox.py tests/test_buddyswitch_launcher.py tests/test_market_browser_evidence.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
python3 -m py_compile tools/launcher/codex_config.py scripts/env/client.py scripts/env/tools/contracts.py scripts/env/tools/dispatch.py scripts/env/tools/router.py scripts/env/tools/responses.py scripts/env/services/search.py scripts/env_profiles.py scripts/turn_runtime.py
```

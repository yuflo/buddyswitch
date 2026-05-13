# Runtime Broker V2 Root Fix Test Plan

Superseded on 2026-05-12 by the env tool layer rebuild residue removal work.

## 1. 测试设计原则

测试从源 memo 的功能需求、产品主路径、不变量和失败模式出发。核心验证面是外部可观察行为：launcher 命令返回码、fake Codex cwd 与 stdout、Unix socket broker 请求、`broker.py status` JSON、runtime state 文件、stale pid/socket/marker 文件变化、产品 client 的 structured error。

测试不得根据实现细节写成只验证某个 helper 被调用。helper mock 只用于制造边界条件；最终断言必须落在状态、输出、错误 payload、文件系统和 retry 次数上。

测试必须覆盖非 happy path：source-root startup、stale broker、missing broker、transport reset、mutating request retry、invalid runtime workspace marker、failed startup cleanup。

## 2. 需求覆盖矩阵

| 需求 | 覆盖测试 |
| --- | --- |
| `REQ-001` | `TC-001` |
| `REQ-002` | `TC-001`, `TC-002` |
| `REQ-003` | `TC-001`, `TC-006`, `TC-007` |
| `REQ-004` | `TC-001`, `TC-004`, `TC-006` |
| `REQ-005` | `TC-002` |
| `REQ-006` | `TC-006` |
| `REQ-007` | `TC-007` |
| `REQ-008` | `TC-007`, `TC-008` |
| `REQ-009` | `TC-005`, `TC-006`, `TC-007` |
| `REQ-010` | `TC-006`, `TC-007` |
| `REQ-011` | `TC-009` |
| `REQ-012` | `TC-009` |
| `REQ-013` | `TC-003`, `TC-004`, `TC-005` |
| `REQ-014` | `TC-004`, `TC-005` |
| `REQ-015` | `TC-010` |
| `REQ-016` | `TC-011`, `TC-012` |
| `REQ-017` | `TC-013`, `TC-014` |
| `REQ-018` | `TC-015`, `TC-016` |
| `REQ-019` | `TC-015` |
| `REQ-020` | `TC-001`, `TC-016` |
| `REQ-021` | `TC-006` |
| `REQ-022` | `TC-003`, `TC-006` |
| `REQ-023` | `TC-007` |
| `REQ-024` | `TC-001` |
| `REQ-025` | `TC-017` |
| `REQ-026` | `TC-006`, `TC-007`, `TC-015`, `TC-016` |
| `REQ-027` | `TC-018` |

所有需求均适合自动化测试。手动验证仅作为最终 smoke 补充：在真实工作区运行 `./buddyswitch-codex instance start --buddy market` 后，在产品会话中执行 `python3 scripts/turn_runtime.py prepare "smoke prepare"`，用于确认真实 Codex profile 与人工环境没有偏离自动化覆盖。

## 3. 测试分层

### 单元测试

目的：验证 retry decision、status root 校验、stale cleanup、错误 payload shape。

覆盖范围：

- `scripts/runtime_kernel/client.py`
- `scripts/runtime_kernel/lifecycle.py`
- `scripts/runtime_kernel/dispatcher.py`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests -q
```

### 集成测试

目的：验证真实 broker process、Unix socket、workspace cwd、`env_store.ROOT`、status CLI。

覆盖范围：

- `python3 scripts/runtime_kernel/broker.py ensure`
- `python3 scripts/runtime_kernel/broker.py status`
- `runtime_kernel.server` socket transport
- runtime workspace marker `AGENTS.md`

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_status_reports_workspace_root_facts -q
```

### CLI / 主路径运行测试

目的：验证 launcher start/open 到 fake Codex first prepare 的真实主路径。

覆盖范围：

- `./buddyswitch-codex instance start --buddy pm ...`
- `./buddyswitch-codex instance open <instance-id> ...`
- fake Codex cwd 内执行 `python3 scripts/turn_runtime.py prepare "smoke prepare"`
- runtime workspace visible state

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_first_prepare_runs_through_workspace_broker -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_repairs_stale_broker_before_first_prepare -q
```

### 回归测试

目的：阻断本次事故复发，并保留 broker v2 已有行为。

覆盖范围：

- source-root startup static scan
- product client self-ensure static scan
- previous v2 protocol, coordinator, idempotency, structured error tests

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_lifecycle_uses_workspace_root_not_source_root -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_product_runtime_client_does_not_self_ensure_broker -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_repo_consistency.py -q
```

### 手动验证

目的：补充真实 Codex CLI profile 行为，不替代自动化测试。

命令：

```bash
./buddyswitch-codex instance start --buddy market
python3 scripts/turn_runtime.py prepare "smoke prepare"
```

预期：prepare 返回顶层 `ok: true` 的业务 payload；没有 broker envelope；不出现 sandbox approval 修复 broker 文件的提示。

## 4. 详细测试用例

### `TC-001` - 静态阻断 source-root broker lifecycle

- 覆盖需求：`REQ-001`、`REQ-002`、`REQ-003`、`REQ-004`、`REQ-020`、`REQ-024`
- 用户 / 系统场景：开发者误把 launcher shell 的 source checkout 当成 broker Python 执行根。
- 前置条件：仓库存在 `tools/launcher/runtime_broker.sh`。
- 输入：读取 shell 文件文本。
- 预期输出或状态变化：文本包含 `BUDDYSWITCH_WORKSPACE_DIR`；不包含 source broker script path；lifecycle 函数体不进入 source cwd；manifest 默认来自 workspace。
- 断言重点：阻断 `${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_kernel/broker.py`、`cd "${BUDDYSWITCH_REPO_ROOT}"`、source default manifest。
- 测试类型：回归静态测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_lifecycle_uses_workspace_root_not_source_root`

### `TC-002` - runtime surface 缺失时 launcher 在 Codex 前失败

- 覆盖需求：`REQ-002`、`REQ-005`
- 用户 / 系统场景：实例 workspace 未同步 broker.py 或 manifest。
- 前置条件：临时 HOME、fake Codex capture；创建 instance workspace 后删除 `workspace/scripts/runtime_kernel/broker.py` 或 `workspace/buddyswitch/manifest.toml`。
- 输入：运行 `./buddyswitch-codex instance open <instance-id> debug prompt-input continue`。
- 预期输出或状态变化：launcher 返回非零；stderr 包含缺失的 workspace path；fake Codex capture 文件不存在。
- 断言重点：失败发生在 Codex 启动前；没有 fallback 到 source checkout。
- 测试类型：CLI 负向测试。
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_fails_before_codex_when_runtime_broker_surface_missing`

### `TC-003` - live broker status 暴露 workspace root facts

- 覆盖需求：`REQ-013`、`REQ-022`
- 用户 / 系统场景：诊断 broker 是否运行在 runtime workspace。
- 前置条件：临时 runtime workspace，`AGENTS.md` 第一行为 `# BuddySwitch Runtime Workspace`，workspace 内有 runtime surface copy。
- 输入：从 workspace cwd 运行 `python3 scripts/runtime_kernel/broker.py ensure ...`，再运行 `status`。
- 预期输出或状态变化：status JSON `healthy: true`，包含 `runtime_root`、`cwd`、`env_store_root`、`runtime_workspace: true`。
- 断言重点：`env_store_root == workspace_dir`；`cwd == workspace_dir`；`socket_path` 与 marker 一致；ping 字段也包含 root facts。
- 测试类型：集成测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_status_reports_workspace_root_facts`

### `TC-004` - status 拒绝 source-root ping

- 覆盖需求：`REQ-004`、`REQ-013`、`REQ-014`
- 用户 / 系统场景：broker 进程活着，但导入根是 source checkout。
- 前置条件：pid file 指向当前进程，marker 指向 socket，patch socket 为 Unix socket，patch ping 返回 source root facts。
- 输入：调用 `lifecycle.broker_status(..., expected_workspace_root=<workspace>)`。
- 预期输出或状态变化：`healthy: false`。
- 断言重点：错误 code 为 stale/root permission 类错误；message 指明 runtime root mismatch 或 runtime workspace marker invalid；status 顶层保留 ping facts 便于诊断。
- 测试类型：单元负向测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_status_rejects_ping_from_source_checkout_root`

### `TC-005` - health 需要 ping 而不是 socket 文件

- 覆盖需求：`REQ-009`、`REQ-013`、`REQ-014`
- 用户 / 系统场景：socket 文件存在但 broker 没有响应正确 ping。
- 前置条件：pid live，marker/socket 一致，patch `_socket_is_unix` 返回 true，patch `ping_broker` 返回 unavailable。
- 输入：调用 `broker_status()`。
- 预期输出或状态变化：`healthy: false`。
- 断言重点：不会因为 socket 存在直接 healthy；error 来自 ping failure。
- 测试类型：单元回归测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_status_requires_successful_ping_before_healthy`

### `TC-006` - instance start 后 first prepare 通过 workspace broker

- 覆盖需求：`REQ-006`、`REQ-009`、`REQ-010`、`REQ-021`、`REQ-022`、`REQ-026`
- 用户 / 系统场景：用户启动 pm 实例后，产品会话第一条 prepare 命令立即可用。
- 前置条件：临时 HOME、source `.codex/auth.json`、fake browser、fake Codex 执行 `python3 scripts/turn_runtime.py prepare "smoke prepare"`。
- 输入：`./buddyswitch-codex instance start --buddy pm debug prompt-input continue`。
- 预期输出或状态变化：launcher exit code 0；fake Codex prepare exit code 0；stdout JSON 顶层 `ok: true`；无 `protocol`、`request_id` broker envelope；run reservation 在 `workspace/buddyswitch/content/runs/<run_id>.json` 可见。
- 断言重点：fake Codex `cwd == workspace_dir`；`BUDDYSWITCH_RUNTIME_BROKER_SOCKET` 非空；broker status `env_store_root == workspace_dir`、`runtime_workspace is True`。
- 测试类型：CLI 主路径集成测试。
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_first_prepare_runs_through_workspace_broker`

### `TC-007` - instance open 修复 stale broker 并 first prepare 成功

- 覆盖需求：`REQ-007`、`REQ-008`、`REQ-009`、`REQ-010`、`REQ-023`、`REQ-026`
- 用户 / 系统场景：inactive instance 留有 stale pid/socket/marker，用户 open 后继续工作。
- 前置条件：已有 inactive instance workspace；`runtime-broker.pid` 为不存在 pid；`runtime-broker.socket` 指向 stale socket；stale socket path 是普通文件或关闭后的 socket；fake Codex 执行 prepare。
- 输入：`./buddyswitch-codex instance open <instance-id> debug prompt-input continue`。
- 预期输出或状态变化：open exit code 0；prepare exit code 0；old stale files 被 live pid、live socket marker 替换；status healthy。
- 断言重点：marker 内容等于 status socket；pid file pid 与 status ping pid 一致；prepare payload 是业务 payload。
- 测试类型：CLI stale recovery 集成测试。
- 建议测试文件路径和测试名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_repairs_stale_broker_before_first_prepare`

### `TC-008` - ensure 清理 stale pid/socket/marker 后启动

- 覆盖需求：`REQ-008`
- 用户 / 系统场景：launcher ensure 遇到过期 broker runtime files。
- 前置条件：临时 runtime 目录内 pid 为 `999999`，marker 指向 stale socket，socket path 是普通文件。
- 输入：调用 `ensure_broker()`，patch start 和 ping 成功。
- 预期输出或状态变化：start 前 stale pid、socket、marker 已删除；ensure 后 marker 写入 live socket。
- 断言重点：事件顺序为 cleanup 后 start，再 ping，再 healthy status。
- 测试类型：单元测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_ensure_cleans_stale_pid_marker_and_socket_before_start`

### `TC-009` - ensure 超时返回 log path 并清理 stale marker

- 覆盖需求：`REQ-011`、`REQ-012`
- 用户 / 系统场景：broker process 启动后未在期限内健康。
- 前置条件：stale pid/socket/marker 存在；patch start 成功；patch ping 持续 unavailable。
- 输入：`ensure_broker(..., startup_timeout_seconds=0.05)`。
- 预期输出或状态变化：result `ok: false`；错误包含 `broker_status.log_file`、`socket_path`、`pid_file`；marker 和 stale socket 不存在。
- 断言重点：失败 payload 可诊断；下一次 ensure 不会读到 stale marker。
- 测试类型：单元负向测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_ensure_timeout_removes_stale_marker`

### `TC-010` - prepare transport reset 不自动 retry

- 覆盖需求：`REQ-015`
- 用户 / 系统场景：prepare request 发送后连接断开，不能重复副作用。
- 前置条件：fake Unix socket server 接收一次 request 后关闭，不写 response。
- 输入：`request_runtime_broker("prepare", {"text": "x"})`。
- 预期输出或状态变化：抛 `RuntimeBrokerError`；server 只收到一条 request。
- 断言重点：没有第二次 request；错误 retriable detail 不导致 retry。
- 测试类型：client 单元/ socket 测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_does_not_retry_prepare_after_transport_reset`

### `TC-011` - persist 有 idempotency key 时 transport reset retry 一次

- 覆盖需求：`REQ-016`
- 用户 / 系统场景：persist request 可通过 idempotency key 安全 retry。
- 前置条件：fake socket server 第一次断开，第二次返回 success。
- 输入：`request_runtime_broker("persist", params, idempotency_key="persist:run-1:abc")`。
- 预期输出或状态变化：返回 success；server 收到两条 request。
- 断言重点：两次 request id 不同；idempotency key 相同；无 product-side ensure subprocess。
- 测试类型：client socket 测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_retries_persist_once_after_transport_reset_when_key_present`

### `TC-012` - persist 缺 idempotency key 不 retry

- 覆盖需求：`REQ-016`
- 用户 / 系统场景：persist 没有 idempotency key 时 retry 会重复提交。
- 前置条件：patch `_request_once` 抛 transport reset。
- 输入：`request_runtime_broker("persist", {"context": {}, "result": {}})`。
- 预期输出或状态变化：抛 `RuntimeBrokerError`；`_request_once` 只调用一次。
- 断言重点：错误不被吞掉；没有 retry；没有 subprocess。
- 测试类型：client 单元负向测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_does_not_retry_persist_without_idempotency_key`

### `TC-013` - read-only env.tool retry 一次且不 self-ensure

- 覆盖需求：`REQ-017`
- 用户 / 系统场景：读取任务列表的 env tool 遇到一次 transport reset。
- 前置条件：patch `_request_once` 第一次抛 `E_RUNTIME_BROKER_CLIENT_DISCONNECTED`，第二次返回 `{"ok": true, "items": []}`；env tool contract 中 `task.list` 是 read-only。
- 输入：`request_runtime_broker("env.tool", {"tool": "task", "action": "list", "args": {}})`。
- 预期输出或状态变化：返回 success；`_request_once` 调用两次。
- 断言重点：无 subprocess；不写 broker lifecycle files。
- 测试类型：client 单元测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_retries_read_only_env_tool_once_without_ensure`

### `TC-014` - mutating env.tool 不 retry

- 覆盖需求：`REQ-017`
- 用户 / 系统场景：创建 task 的 env tool 发送后连接断开。
- 前置条件：patch `_request_once` 抛 transport reset。
- 输入：`request_runtime_broker("env.tool", {"tool": "task", "action": "create", "args": {"title": "x"}})`。
- 预期输出或状态变化：抛 `RuntimeBrokerError`；`_request_once` 只调用一次。
- 断言重点：不会重复 mutation；不会 self-ensure。
- 测试类型：client 单元负向测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_does_not_retry_mutating_env_tool_after_transport_reset`

### `TC-015` - stale/missing broker 返回 launcher reopen feedback

- 覆盖需求：`REQ-018`、`REQ-019`、`REQ-026`
- 用户 / 系统场景：产品会话 socket 缺失或 stale。
- 前置条件：env 中有 instance id、active buddy、missing socket path；patch `client.subprocess.run`。
- 输入：`request_runtime_broker("prepare", {"text": "x"})`。
- 预期输出或状态变化：抛 `RuntimeBrokerError`。
- 断言重点：details 包含 `permission_boundary: product-mode-runtime-broker`、`stop_condition: stop_and_report_do_not_bypass_broker`、`command_hint: ./buddyswitch-codex instance open inst-pm-example`、`socket_path`；`subprocess.run` 未调用。
- 测试类型：client 负向测试。
- 建议测试文件路径和测试名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_stale_socket_reports_launcher_reopen_without_self_ensure`

### `TC-016` - 静态阻断 product client self-ensure

- 覆盖需求：`REQ-018`、`REQ-020`、`REQ-026`
- 用户 / 系统场景：后续维护者重新加入产品态 broker lifecycle mutation。
- 前置条件：仓库存在 `scripts/runtime_kernel/client.py`。
- 输入：读取 client 文件文本。
- 预期输出或状态变化：文本不包含 `_ensure_runtime_broker`、broker lifecycle 文件名、`broker.py ensure` subprocess 路径。
- 断言重点：产品态 client 不拥有 pid/socket/marker/log repair 代码。
- 测试类型：回归静态测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_product_runtime_client_does_not_self_ensure_broker`

### `TC-017` - 不新增 workflow/supervisor 类复杂系统

- 覆盖需求：`REQ-025`
- 用户 / 系统场景：root fix 被扩大成通用 daemon manager 或 workflow engine。
- 前置条件：仓库存在 `scripts/runtime_kernel`。
- 输入：扫描 runtime kernel 文件名和 imports。
- 预期输出或状态变化：没有 workflow、rule_engine、plugin、supervisor、daemon_manager、queue_manager 文件或 import。
- 断言重点：保持本地 Unix socket broker，不引入 grpc/http/sqlite。
- 测试类型：回归静态测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_does_not_add_workflow_or_rule_engine`

### `TC-018` - runbook 记录 root fix 边界

- 覆盖需求：`REQ-027`
- 用户 / 系统场景：未来维护者需要理解健康标准和 repair owner。
- 前置条件：`framework/docs/runtime-broker-v2-runbook.md` 存在。
- 输入：读取 runbook。
- 预期输出或状态变化：包含 `runtime workspace`、`env_store.ROOT`、`launcher-owned ensure`、`prepare does not auto-retry`、`instance open <instance-id>`。
- 断言重点：文档覆盖 health criteria、ensure flow、retry policy、error codes。
- 测试类型：文档回归测试。
- 建议测试文件路径和测试名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_v2_runbook_documents_root_fix_boundary`

## 5. 负向与边界测试

- 缺失数据：`TC-002` 覆盖缺失 workspace broker.py 或 manifest；`TC-015` 覆盖缺失 socket。
- 无效状态：`TC-004` 覆盖 broker root mismatch；`TC-005` 覆盖 socket 存在但 ping 不健康。
- 重复操作：`TC-011` 验证 persist retry 依赖 idempotency key；`TC-012` 验证缺 key 不重复提交。
- 并发或顺序敏感行为：`TC-008` 验证 cleanup 必须发生在 start 前；`TC-009` 验证 failed startup 清理影响下一次 ensure。
- 空输入、空集合、空记录、空配置：`TC-002` 覆盖缺 runtime surface；现有 `RuntimeBrokerTests` 保留 request params 和 identity invalid cases；本任务不新增空业务 payload 语义。
- 权限、路径、配置、运行状态、外部依赖异常：`TC-001`、`TC-002`、`TC-004`、`TC-015`、`TC-016` 覆盖 source-root path、workspace path、product permission boundary、broker lifecycle ownership。

## 6. 作弊防护

- `TC-006` 和 `TC-007` 通过 fake Codex 从真实 launcher workspace cwd 执行 `python3 scripts/turn_runtime.py prepare`，防止只 patch `dispatch_runtime_request()` 或只检查 env var。
- `TC-003` 启动真实 broker process 并调用 CLI status，防止只在 direct dispatcher path 伪造 root facts。
- `TC-004` 使用与 pid/socket/identity 都一致但 root facts 错误的 ping，防止 health 只验证进程存活。
- `TC-006` 断言 stdout 不是 broker envelope，防止 launcher 返回内部 protocol envelope 冒充业务 payload。
- `TC-006` 和 `TC-007` 验证 run reservation 文件状态，防止实现只打印 `ok: true`。
- `TC-011`、`TC-012`、`TC-013`、`TC-014` 覆盖四种不同 retry 组合，防止硬编码所有 transport reset 都 retry 或都不 retry。
- `TC-015` 和 `TC-016` 同时用行为测试和静态扫描阻断 product client self-ensure，防止实现绕过 mock 改用另一条 subprocess 路径。
- 测试数据覆盖 `pm`、`market` 可运行 buddy 中的至少 `pm` 主路径，instance id 使用不同值 `inst-pm-root`、`inst-pm-example`、launcher 生成 id，防止按固定字符串硬编码通过。

## 7. 验证命令清单

Focused test 命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_lifecycle_uses_workspace_root_not_source_root -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_status_reports_workspace_root_facts -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_first_prepare_runs_through_workspace_broker -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_repairs_stale_broker_before_first_prepare -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_stale_socket_reports_launcher_reopen_without_self_ensure -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_product_runtime_client_does_not_self_ensure_broker -q
```

Broader verification 命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_task_manager_env_tool.py -q
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
```

任务完成前必须运行的最终验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests -q
```

# Runtime Broker V2 Root Fix Implementation Plan

Superseded on 2026-05-12 by the env tool layer rebuild residue removal work.

## 1. 任务目标

完成后，BuddySwitch 产品态实例必须通过 launcher 启动并维护 runtime broker，broker 进程从实例 runtime workspace 导入代码并写入 runtime workspace 可见状态，产品 Codex 会话只通过 `BUDDYSWITCH_RUNTIME_BROKER_SOCKET` 发请求。当前核心瓶颈是 broker v2 的生命周期根目录混淆：launcher shell 在 source checkout 中启动 broker，导致 `env_store.ROOT` 指向源码目录，并且产品态 client 仍试图修复 broker 文件；这是最重要问题，因为它会让 `instance start/open -> prepare` 这个主路径在普通产品请求开始前失败。

## 2. 需求提取

- `REQ-001`：`tools/launcher/runtime_broker.sh` 的 broker script 必须来自 `${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py`。
- `REQ-002`：`tools/launcher/runtime_broker.sh` 的 manifest 默认路径必须是 `${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml`，仅在 `BUDDYSWITCH_MANIFEST_PATH` 明确设置时使用该覆盖值。
- `REQ-003`：broker lifecycle 命令 `status|ensure|stop` 的 cwd 必须是 `${BUDDYSWITCH_WORKSPACE_DIR}`。
- `REQ-004`：source checkout 只能拥有 launcher 代码和 source files，不能作为产品态 broker Python 执行根。
- `REQ-005`：若 runtime surface 缺少 `scripts/runtime_kernel/broker.py` 或 `buddyswitch/manifest.toml`，launcher 必须在 Codex 启动前失败，并输出缺失路径。
- `REQ-006`：`instance start` 必须在启动 Codex 前由 launcher 执行 broker ensure。
- `REQ-007`：`instance open` 必须在启动 Codex 前由 launcher 执行 broker ensure。
- `REQ-008`：launcher-owned ensure 必须读取当前 status，识别 stale pid/socket/marker 状态，清理 stale `runtime-broker.pid`、`runtime-broker.sock`、`runtime-broker.socket`，再启动 broker。
- `REQ-009`：ensure 必须等待真实 ping 成功，不能只靠 socket 文件存在判断健康。
- `REQ-010`：ensure 成功返回给 shell 的 socket path 只能在 broker health 已验证后导出为 `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`。
- `REQ-011`：ensure 失败必须返回包含 `runtime-broker.log` 路径、socket path、pid file 的结构化错误。
- `REQ-012`：ensure 启动失败或超时后不能留下会误导下一次启动的 stale marker 文件。
- `REQ-013`：broker `ping` 或 `status` 必须暴露 protocol、pid、socket path、instance id、active buddy、broker cwd 或 resolved runtime root、`env_store.ROOT`、`env_store.is_runtime_workspace()`。
- `REQ-014`：healthy status 必须同时验证 pid live、socket 是 Unix socket、marker 指向同一 socket、ping instance/buddy 符合预期、ping pid 与 pid file 一致、ping socket 与 marker/socket 一致、`env_store.ROOT` 等于 instance workspace 或解析在其中、runtime workspace marker 有效。
- `REQ-015`：产品态 client 对 `prepare` 不能在 transport reset、stale socket、missing socket 后自动 retry，因为 `prepare` 有状态副作用。
- `REQ-016`：产品态 client 对 `persist` 只能在存在 idempotency key 时 retry 一次。
- `REQ-017`：产品态 client 对 read-only `env.tool` 可 retry 一次；mutating `env.tool` 不能自动 retry。
- `REQ-018`：产品态 client 不能通过 `broker.py ensure`、`subprocess.run(...)` 或写 pid/socket/marker/log 文件来修复 broker 生命周期。
- `REQ-019`：产品态 client 在 stale/missing/unavailable broker 时必须返回结构化 feedback，包含 permission boundary、stop condition、socket path、command hint `./buddyswitch-codex instance open <instance-id>`。
- `REQ-020`：不能保留 source-root broker startup fallback；旧的 source-root lifecycle path 必须删除或由测试阻断。
- `REQ-021`：`instance start` 后 fake Codex 从 runtime workspace 运行 `python3 scripts/turn_runtime.py prepare "smoke prepare"` 必须成功，stdout 是业务 payload，顶层 `ok: true`，不是 broker envelope。
- `REQ-022`：`instance start` 的 prepare 必须在 runtime workspace 可见路径产生 run reservation，且 broker status 报告 `env_store.ROOT` 为该 workspace。
- `REQ-023`：`instance open` 必须能修复 inactive instance 中 stale broker pid/socket/marker，并在 Codex 启动后让 first prepare 成功。
- `REQ-024`：静态测试必须阻断 `${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_kernel/broker.py` 作为 lifecycle broker script，阻断 lifecycle 前 `cd "${BUDDYSWITCH_REPO_ROOT}"`，并要求出现 `BUDDYSWITCH_WORKSPACE_DIR`。
- `REQ-025`：不得新增 generic supervisor、daemon manager、queue、workflow engine、rule engine、plugin system、长期双路径兼容层。
- `REQ-026`：不扩大产品 Codex 对 instance `runtime/` 目录的写权限，不把手动 sandbox approval 当成正常修复路径。
- `REQ-027`：更新 `framework/docs/runtime-broker-v2-runbook.md`，记录 runtime workspace startup、health root facts、launcher-only repair、product client retry policy。

## 3. 现状探索摘要

关键文档：

- `AGENTS.md`：要求 sharp-forward、测试约束、最短验证路径、不要保留无意义兼容。
- `README.md`：定义产品态 runtime loop、`python3 scripts/turn_runtime.py prepare`、实例 workspace 路径。
- `docs/memo/2026-05-13-runtime-broker-v2-root-fix-memo.md`：本任务源需求。
- `docs/spec/2026-05-12-runtime-broker-v2-implementation-plan.md` 与 `docs/spec/2026-05-12-runtime-broker-v2-test-plan.md`：上一版 broker v2 设计和测试边界。

关键代码路径：

- `tools/launcher/runtime_broker.sh`：当前 `_buddyswitch_runtime_broker_script_path()` 使用 `BUDDYSWITCH_REPO_ROOT`，`_buddyswitch_runtime_broker_manifest_path()` 默认使用 source manifest，`_buddyswitch_runtime_broker_lifecycle_json()` 进入 source cwd；这些必须替换。
- `buddyswitch-codex`：`start_codex()`、`instance_start_locked_bootstrap()`、`instance_open()`、`instance_open_locked_bootstrap()` 负责 Codex 启动和 broker ensure 调用；结构保留，验证点加强。
- `tools/launcher/env.sh`：`buddyswitch_env_bind_instance()` 设置 `BUDDYSWITCH_INSTANCE_ROOT` 和 `BUDDYSWITCH_WORKSPACE_DIR`；保留。
- `tools/launcher/workspace.sh`：`buddyswitch_workspace_sync_runtime_surface()` 同步 runtime broker 代码到 workspace；保留，并作为 broker script 存在性前置条件。
- `scripts/runtime_kernel/lifecycle.py`：`broker_status()`、`ensure_broker()`、`cleanup_stale_broker_state()`、`start_broker_process()` 是 stale recovery 和 health 判定主体；保留文件，扩展 root facts，清理失败残留。
- `scripts/runtime_kernel/dispatcher.py`：`_ping_dispatch()`、`_status_dispatch()` 目前只报告 pid/socket/identity；扩展 runtime root facts。
- `scripts/runtime_kernel/client.py`：`_ensure_runtime_broker()` 和 `_retry_decision(... ensure_before_retry ...)` 是产品态自修复路径；删除或改为不可调用路径，保留 conservative retry。
- `scripts/runtime_kernel/broker.py`：CLI `status|ensure|stop|ping|serve` 保留；输出 payload 因 health facts 增强而变化。
- `scripts/env_store.py`：`ROOT` 和 `is_runtime_workspace()` 是判定 broker 运行根的关键数据源；不改写 store 语义，仅让 broker status 暴露它。
- `scripts/turn_runtime.py`：`_cmd_prepare()`、`_cmd_persist()` 已经通过 runtime broker；保留，验收从 CLI 触发。

关键测试路径：

- `tests/test_repo_consistency.py`：新增 source-root startup forbidden 静态测试。
- `tests/test_runtime_broker.py`：扩展 lifecycle/status/client tests，替换旧的 product client stale socket ensure 测试。
- `tests/test_buddyswitch_launcher.py`：新增 `instance start` first prepare 与 `instance open` stale recovery 集成测试，复用 fake Codex 和 `_cleanup_runtime_broker()`。
- `tests/runtime_root_test_helper.py`：现有直接 patch module root 的 helper 保留，但不能替代 launcher/socket/cwd 端到端验收。

探索和验证命令：

```bash
rg -n "BUDDYSWITCH_REPO_ROOT|BUDDYSWITCH_WORKSPACE_DIR|_ensure_runtime_broker|runtime-broker" tools scripts tests -S
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_launcher_health_delegates_to_python_lifecycle -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

保留、替换、删除、迁移：

- 保留 `buddyswitch-codex` 中 start/open 的 locked bootstrap 结构，因为它已经是 launcher-owned 生命周期入口。
- 保留 `scripts/runtime_kernel/lifecycle.py` 的 ensure/status/stop 职责，但补齐 root facts 和失败清理。
- 保留 `scripts/runtime_kernel/server.py`、`protocol.py`、`coordinator.py` 的 v2 socket/protocol/coordination 边界。
- 替换 `tools/launcher/runtime_broker.sh` 的 source-root broker script、manifest、cwd 解析。
- 替换 `tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_stale_socket_retry_ensures_once`，新测试断言产品态不 self-ensure。
- 删除 `scripts/runtime_kernel/client.py::_ensure_runtime_broker()` 或移除所有 product-mode recovery 调用点并用静态测试阻断 `broker.py ensure` subprocess。
- 不迁移用户数据；runtime state 继续通过 workspace symlink 和 shared state 存储。

## 4. 最终目标架构

最终文件结构：

- `tools/launcher/runtime_broker.sh`
  - 负责 shell 层 broker pid/socket/log path、effective socket、lifecycle JSON 调用、导出 `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`。
  - `_buddyswitch_runtime_broker_manifest_path()` 默认返回 `${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml`。
  - `_buddyswitch_runtime_broker_script_path()` 返回 `${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py` 并在缺失时失败。
  - `_buddyswitch_runtime_broker_lifecycle_json()` 在 `${BUDDYSWITCH_WORKSPACE_DIR}` cwd 运行 `python3 "${broker_script}"`.

- `scripts/runtime_kernel/dispatcher.py`
  - `RuntimeBrokerSession` 继续携带 `instance_json_path`、`manifest_path`、`socket_path`、`pid_file`。
  - `_ping_dispatch(session, instance_record)` 返回 root facts：`runtime_root`、`cwd`、`env_store_root`、`runtime_workspace`。
  - `_status_dispatch(session, instance_record)` 复用 `_ping_dispatch()` 并补充 `healthy: true` 和 pid file。

- `scripts/runtime_kernel/lifecycle.py`
  - `ping_broker()` 校验 ping result 的 identity、pid、socket、root facts shape。
  - `broker_status()` 将 root facts 提升到 status 顶层，并按 `REQ-014` 计算 `healthy`。
  - `ensure_broker()` 在任何非健康状态下先调用 `cleanup_stale_broker_state()`；启动失败或超时后再次移除 marker/socket/pid 中会误导下一次 status 的 stale 文件。
  - `start_broker_process()` 继续以 runtime copy 中的 `broker.py` 启动，cwd 由 `broker_script.parents[2]` 得出；当 shell 已从 workspace 调用 broker 时，该 cwd 为 workspace。

- `scripts/runtime_kernel/client.py`
  - `request_runtime_broker()` 保留一次 retry budget。
  - `_retry_decision()` 输出 `BrokerRetryDecision(should_retry, reason)` 或等价简化结构，不再返回 `ensure_before_retry`。
  - 删除 `_ensure_runtime_broker()`；transport/stale/missing socket 只生成 `RuntimeBrokerError` 与 `broker_unavailable_feedback()`。
  - `prepare` 任何 transport 后失败都不 retry；`persist` 仅在 idempotency key 存在时 retry 一次；read-only `env.tool` retry 一次；mutating `env.tool` 不 retry。

- `scripts/runtime_kernel/broker.py`
  - CLI shape 保留；`status` 输出的 JSON 因 lifecycle root facts 增强而包含 `runtime_root`、`cwd`、`env_store_root`、`runtime_workspace`。

- `tests/test_repo_consistency.py`
  - 新增 `test_runtime_broker_lifecycle_uses_workspace_root_not_source_root`。
  - 增强 `test_runtime_broker_launcher_health_delegates_to_python_lifecycle` 保持 health delegated。
  - 新增静态阻断 product client self-ensure subprocess 的测试。

- `tests/test_runtime_broker.py`
  - 新增 `RuntimeBrokerLifecycleTests::test_live_status_reports_workspace_root_facts`。
  - 新增 `RuntimeBrokerLifecycleTests::test_status_rejects_ping_from_source_checkout_root`。
  - 新增 `RuntimeBrokerLifecycleTests::test_ensure_timeout_removes_stale_marker`。
  - 替换 client stale ensure 测试为 `RuntimeBrokerClientV2Tests::test_client_stale_socket_reports_launcher_reopen_without_self_ensure`。
  - 新增 `RuntimeBrokerClientV2Tests::test_client_retries_read_only_env_tool_once_without_ensure` 和 `test_client_does_not_retry_mutating_env_tool_after_transport_reset`。

- `tests/test_buddyswitch_launcher.py`
  - 新增 `BuddySwitchLauncherTests::test_instance_start_first_prepare_runs_through_workspace_broker`。
  - 新增 `BuddySwitchLauncherTests::test_instance_open_repairs_stale_broker_before_first_prepare`。

- `framework/docs/runtime-broker-v2-runbook.md`
  - 更新 Health Criteria、Ensure Flow、Retry Policy、Error Codes，记录 workspace-root startup 和 launcher-only repair。

核心数据模型：

`broker.py status` 顶层 payload：

```json
{
  "ok": true,
  "protocol": "buddyswitch-runtime-broker/v2",
  "pid": 12345,
  "pid_live": true,
  "socket_path": "<instance>/runtime/runtime-broker.sock",
  "marker_path": "<instance>/runtime/runtime-broker.socket",
  "marker_value": "<instance>/runtime/runtime-broker.sock",
  "log_file": "<instance>/runtime/runtime-broker.log",
  "healthy": true,
  "instance_id": "inst-pm-abc",
  "active_buddy": "pm",
  "runtime_root": "<instance>/workspace",
  "cwd": "<instance>/workspace",
  "env_store_root": "<instance>/workspace",
  "runtime_workspace": true,
  "ping": {
    "protocol": "buddyswitch-runtime-broker/v2",
    "instance_id": "inst-pm-abc",
    "active_buddy": "pm",
    "pid": 12345,
    "socket_path": "<instance>/runtime/runtime-broker.sock",
    "runtime_root": "<instance>/workspace",
    "cwd": "<instance>/workspace",
    "env_store_root": "<instance>/workspace",
    "runtime_workspace": true
  }
}
```

错误处理规则：

- Missing runtime broker script：shell 打印 `Runtime broker script missing in workspace: <path>` 并返回非零，Codex 不启动。
- Missing manifest：shell 打印 `Runtime broker manifest missing in workspace: <path>` 并返回非零，Codex 不启动。
- Status root mismatch：`broker_status()` 返回 `healthy: false`、`error.code: E_RUNTIME_BROKER_STALE_SOCKET`、message 包含 `runtime root mismatch`。
- Runtime workspace marker invalid：`broker_status()` 返回 `healthy: false`、`error.code: E_RUNTIME_BROKER_PERMISSION`、message 包含 `runtime workspace marker is invalid`。
- Product client stale broker：抛出 `RuntimeBrokerError`，`details.permission_boundary == "product-mode-runtime-broker"`，`details.command_hint == "./buddyswitch-codex instance open <instance-id>"`，不执行 subprocess。

调用流：

```text
./buddyswitch-codex instance start/open
  -> bind instance env: BUDDYSWITCH_INSTANCE_ROOT, BUDDYSWITCH_WORKSPACE_DIR
  -> sync runtime surface into BUDDYSWITCH_WORKSPACE_DIR
  -> buddyswitch_runtime_broker_ensure
    -> cd BUDDYSWITCH_WORKSPACE_DIR
    -> python3 BUDDYSWITCH_WORKSPACE_DIR/scripts/runtime_kernel/broker.py ensure
      -> lifecycle.broker_status
      -> lifecycle.cleanup_stale_broker_state when unhealthy
      -> lifecycle.start_broker_process using workspace broker.py
      -> lifecycle.ping_broker
      -> lifecycle.broker_status with root facts
  -> export BUDDYSWITCH_RUNTIME_BROKER_SOCKET only after healthy
  -> buddyswitch_run_codex from BUDDYSWITCH_WORKSPACE_DIR
  -> python3 scripts/turn_runtime.py prepare "smoke prepare"
    -> runtime_kernel.client.request_runtime_broker("prepare", ...)
    -> Unix socket request to launcher-owned broker
    -> broker dispatcher writes runtime state through workspace-root env_store
```

旧路径或旧逻辑删除：

- 删除 source-root broker script path `${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_kernel/broker.py` 在 lifecycle execution 中的使用。
- 删除 lifecycle 前 `cd "${BUDDYSWITCH_REPO_ROOT}"`。
- 删除 product client `_ensure_runtime_broker()` 或删除所有调用并增加静态测试禁止恢复。
- 删除旧测试 `test_client_stale_socket_retry_ensures_once` 的语义，替换为 launcher reopen feedback 测试。

## 5. 分阶段实施计划

### 阶段一：用静态测试锁住 workspace-root broker lifecycle

目标：先让当前错误路径可见，阻断 source-root startup fallback。

具体文件变更：

- 修改 `tests/test_repo_consistency.py`。
- 后续实现阶段修改 `tools/launcher/runtime_broker.sh`。

详细步骤：

1. 在 `RepoConsistencyTests` 新增 `test_runtime_broker_lifecycle_uses_workspace_root_not_source_root`。
2. 测试读取 `tools/launcher/runtime_broker.sh` 文本，断言包含 `BUDDYSWITCH_WORKSPACE_DIR`。
3. 断言不包含 `broker_script="${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_kernel/broker.py"`。
4. 断言不包含 `printf '%s/buddyswitch/manifest.toml\n' "${BUDDYSWITCH_REPO_ROOT}"`。
5. 断言 `_buddyswitch_runtime_broker_lifecycle_json` 函数体不包含 `cd "${BUDDYSWITCH_REPO_ROOT}"`。
6. 运行 focused test，确认当前 `dev2258` 失败。
7. 修改 `tools/launcher/runtime_broker.sh`：
   - `_buddyswitch_runtime_broker_manifest_path()` 在没有 `BUDDYSWITCH_MANIFEST_PATH` 时返回 `${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/manifest.toml`。
   - 若 manifest 文件不存在，输出 `Runtime broker manifest missing in workspace: ${manifest_path}` 并返回 1。
   - `_buddyswitch_runtime_broker_script_path()` 返回 `${BUDDYSWITCH_WORKSPACE_DIR}/scripts/runtime_kernel/broker.py`。
   - 若 broker script 不存在，输出 `Runtime broker script missing in workspace: ${broker_script}` 并返回 1。
   - `_buddyswitch_runtime_broker_lifecycle_json()` 进入 `cd "${BUDDYSWITCH_WORKSPACE_DIR}"` 后执行 Python。
8. 运行 focused test，确认通过。

预期行为变化：

- launcher 仍可从 source checkout 运行 shell，但 broker Python lifecycle 只从 runtime workspace 执行。
- runtime surface 缺失时，失败发生在 Codex 启动前。

对应需求编号：`REQ-001`、`REQ-002`、`REQ-003`、`REQ-004`、`REQ-005`、`REQ-020`、`REQ-024`、`REQ-025`。

验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_lifecycle_uses_workspace_root_not_source_root -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_launcher_health_delegates_to_python_lifecycle -q
```

阶段完成标准：

- 新静态测试能在旧实现上失败，在修改后通过。
- `rg -n 'BUDDYSWITCH_REPO_ROOT.*/scripts/runtime_kernel/broker.py|cd "\$\{BUDDYSWITCH_REPO_ROOT\}"' tools/launcher/runtime_broker.sh` 无输出。

### 阶段二：让 broker status 证明 runtime workspace root

目标：health 不只证明 broker 活着，还证明 broker 活在正确 workspace root。

具体文件变更：

- 修改 `scripts/runtime_kernel/dispatcher.py`。
- 修改 `scripts/runtime_kernel/lifecycle.py`。
- 修改 `scripts/runtime_kernel/broker.py` 仅在 CLI 输出需要字段透传时调整。
- 修改 `tests/test_runtime_broker.py`。

详细步骤：

1. 在 `RuntimeBrokerLifecycleTests` 新增 `test_live_status_reports_workspace_root_facts`：
   - 用 `tempfile.TemporaryDirectory()` 创建 workspace。
   - 写入 `AGENTS.md` 第一行为 `# BuddySwitch Runtime Workspace`。
   - 写入 `instance.json`，字段 `instance_id: "inst-pm-root"`, `buddy: "pm"`, `status: "active"`, `workspace_dir: <workspace>`。
   - 从 workspace cwd 启动真实 broker：`python3 <workspace>/scripts/runtime_kernel/broker.py ensure ...`，测试 setup 需要先把 source runtime surface 复制到 workspace，至少包括 `scripts/runtime_kernel`、`scripts/env_store.py`、`scripts/env`、`scripts/turn_runtime.py`、`buddyswitch/manifest.toml`。
   - 调用 `python3 <workspace>/scripts/runtime_kernel/broker.py status ...`。
   - 断言 JSON 顶层 `healthy is True`、`runtime_workspace is True`、`env_store_root == str(workspace)`、`runtime_root == str(workspace)`、`cwd == str(workspace)`。
2. 在 `RuntimeBrokerLifecycleTests` 新增 `test_status_rejects_ping_from_source_checkout_root`：
   - 构造 `paths.pid_file` 指向当前进程 pid，marker 指向 socket。
   - patch `_socket_is_unix` 返回 `True`。
   - patch `ping_broker` 返回 `ok: True`，result 中 `pid` 与 pid file 一致，`socket_path` 一致，`instance_id` 和 `active_buddy` 一致，但 `env_store_root` 为 `str(ROOT)`、`runtime_workspace` 为 `False`、`runtime_root` 为 `str(ROOT)`。
   - 调用 `broker_status(..., expected_workspace_root=<workspace>)` 或等价参数，断言 `healthy is False`、错误 code 为 `E_RUNTIME_BROKER_STALE_SOCKET` 或 `E_RUNTIME_BROKER_PERMISSION`，message 包含 root mismatch 或 invalid runtime workspace。
3. 修改 `dispatcher.py`：
   - import `env_store`。
   - `_ping_dispatch()` 计算 `runtime_root = Path.cwd().resolve(strict=False)`。
   - 返回 `cwd`、`runtime_root`、`env_store_root = str(env_store.ROOT.resolve(strict=False))`、`runtime_workspace = env_store.is_runtime_workspace(env_store.ROOT)`。
4. 修改 `lifecycle.py`：
   - `ping_broker()` 保持 identity 校验，并允许 result 携带新增字段。
   - `broker_status()` 从 `instance_json_path` 或新增 `expected_workspace_root` 参数获得 expected workspace root。推荐把 `broker_status()` 签名扩展为 `broker_status(paths, *, expected_instance_id, expected_active_buddy, expected_workspace_root: Path | None = None)`，CLI 由 `broker.py` 从 instance record `workspace_dir` 传入。
   - health 成功前校验 `runtime_workspace is True`。
   - 校验 `env_store_root` 字符串解析后等于 expected workspace root，或在 expected workspace root 内。
   - 将 `runtime_root`、`cwd`、`env_store_root`、`runtime_workspace` 写入 status 顶层。
5. 修改 `broker.py`：
   - `_expected_identity()` 扩展为 `_expected_runtime_context()`，返回 `(instance_id, active_buddy, workspace_root)`。
   - `status|ping|ensure` 调用 lifecycle 时传入 `expected_workspace_root`。
6. 运行 focused tests。

预期行为变化：

- `broker.py status` 能诊断 broker 是从 source checkout 还是 runtime workspace 启动。
- root mismatch 的 broker 不会被视为 healthy。

对应需求编号：`REQ-013`、`REQ-014`、`REQ-022`。

验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_live_status_reports_workspace_root_facts -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_status_rejects_ping_from_source_checkout_root -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests -q
```

阶段完成标准：

- status payload 包含 root facts。
- healthy status 对 source-root broker 返回 false。
- lifecycle 现有 stale pid、marker mismatch、missing socket 测试保持通过。

### 阶段三：用 launcher start first prepare 验证端到端主路径

目标：证明 `instance start` 创建的 workspace broker 能让 first prepare 通过真实 socket 写入 runtime state。

具体文件变更：

- 修改 `tests/test_buddyswitch_launcher.py`。
- 根据测试反馈修改 `tools/launcher/runtime_broker.sh`、`scripts/runtime_kernel/lifecycle.py`。

详细步骤：

1. 新增 fake Codex writer `_write_fake_codex_that_runs_prepare(path)` 或在测试内写入专用 fake `codex`：
   - 记录 `cwd`、`BUDDYSWITCH_RUNTIME_BROKER_SOCKET`、`BUDDYSWITCH_INSTANCE_JSON` 到 capture。
   - 执行 `python3 scripts/turn_runtime.py prepare "smoke prepare"`，cwd 使用 launcher 传入的当前目录。
   - 将 prepare stdout、stderr、exit code 写入 `BUDDYSWITCH_TEST_PREPARE_CAPTURE`。
   - fake Codex 以 prepare exit code 退出。
2. 新增 `BuddySwitchLauncherTests::test_instance_start_first_prepare_runs_through_workspace_broker`：
   - 使用临时 HOME、source `.codex/auth.json`、fake `codex`、fake browser。
   - 运行 `./buddyswitch-codex instance start --buddy pm debug prompt-input continue`。
   - 断言 launcher exit code 为 0。
   - 读取 prepare capture，断言 exit code 为 0。
   - JSON 解析 prepare stdout，断言顶层 `ok is True`，且不存在 broker envelope 字段 `protocol`、`request_id`。
   - 从 payload 取得 `run_envelope.turn_identity.run_id` 或当前 prepare payload 实际 run id 字段，断言 `workspace_dir/buddyswitch/content/runs/<run_id>.json` 存在。
   - 运行 workspace broker status CLI，使用 instance runtime 中的 pid/socket/marker/log/instance-json/manifest，断言 `healthy is True`、`env_store_root == workspace_dir`、`runtime_workspace is True`。
3. 若测试失败于 prepare 写入 source root，确认阶段一 shell change 和阶段二 root status 已生效；修复缺口。
4. 若测试失败于 runtime surface 不完整，修改 `tools/launcher/workspace.sh::buddyswitch_workspace_sync_runtime_surface()` 只补齐 broker 所需已存在 runtime files，不添加新抽象。
5. 运行 focused test。

预期行为变化：

- 产品实例第一次业务命令不再因为 `env_store.require_runtime_workspace_write_root()` 把 source checkout 识别成写根而失败。
- first prepare 通过 Unix socket 调用 launcher-owned broker，stdout 是业务 payload。

对应需求编号：`REQ-006`、`REQ-009`、`REQ-010`、`REQ-021`、`REQ-022`、`REQ-026`。

验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_first_prepare_runs_through_workspace_broker -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_wires_instance_env_and_lifecycle -q
```

阶段完成标准：

- `instance start` fake Codex 从 workspace cwd 运行 prepare 成功。
- run reservation 在 workspace 可见状态目录存在。
- broker status 证明 workspace root。

### 阶段四：补齐 stale broker recovery 与失败清理

目标：`instance open` 在 Codex 启动前由 launcher 修复 stale broker 文件，并且 failed startup 不留下误导 marker。

具体文件变更：

- 修改 `tests/test_buddyswitch_launcher.py`。
- 修改 `tests/test_runtime_broker.py`。
- 修改 `scripts/runtime_kernel/lifecycle.py`。

详细步骤：

1. 新增 `RuntimeBrokerLifecycleTests::test_ensure_timeout_removes_stale_marker`：
   - 创建 `runtime-broker.pid`，内容为不存在 pid。
   - 创建 `runtime-broker.socket`，内容为 `paths.socket_path`。
   - 创建普通文件 `runtime-broker.sock`。
   - patch `start_broker_process` 返回 `{"ok": True, "pid": os.getpid()}`。
   - patch `ping_broker` 持续返回 unavailable。
   - 调用 `ensure_broker(..., startup_timeout_seconds=0.05)`。
   - 断言 result `ok is False`，`error.broker_status.log_file` 等于 log path，`paths.marker_file.exists() is False`，`paths.socket_path.exists() is False`。
2. 修改 `ensure_broker()`：
   - 在初始 status 非 healthy 后调用 `cleanup_stale_broker_state(paths)`。
   - 在 `start_broker_process()` 返回非 ok 时调用 `cleanup_stale_broker_state(paths)` 后返回结构化错误。
   - 在 startup timeout 前后记录 `latest_status`；timeout 后调用 `cleanup_stale_broker_state(paths)`，但不要删除正在运行且后续可由 stop 管理的 live process pid file，若无法确认 live broker health，则删除 marker 和 socket，pid cleanup 按当前 stale cleanup 规则执行。
3. 新增 `BuddySwitchLauncherTests::test_instance_open_repairs_stale_broker_before_first_prepare`：
   - 先创建 inactive instance record 和 workspace，可通过一次 `instance start` fake Codex 退出后留下 inactive record，或直接复用 launcher helper 创建 instance record 与 runtime workspace。
   - 在 `instance_root/runtime` 写入 stale `runtime-broker.pid` 为 `999999`。
   - 写入 `runtime-broker.socket` 为 stale socket path。
   - 创建 stale socket path 普通文件或用临时 Unix socket 后关闭。
   - 使用会运行 prepare 的 fake Codex。
   - 执行 `./buddyswitch-codex instance open <instance-id> debug prompt-input continue`。
   - 断言 open exit code 为 0，prepare exit code 为 0。
   - 断言 stale pid 被替换为 live pid，marker 内容等于 live socket，status `healthy is True`。
4. 运行 focused tests。

预期行为变化：

- stale pid/socket/marker 不再把产品会话困在需要 sandbox approval 的 repair 状态。
- failed ensure 不留下下一次 status 会误判的 marker。

对应需求编号：`REQ-007`、`REQ-008`、`REQ-009`、`REQ-010`、`REQ-011`、`REQ-012`、`REQ-023`、`REQ-026`.

验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_ensure_timeout_removes_stale_marker -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_open_repairs_stale_broker_before_first_prepare -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests -q
```

阶段完成标准：

- open stale recovery 测试通过。
- lifecycle timeout cleanup 测试通过。
- stale marker 不会在失败 ensure 后保留。

### 阶段五：移除 product client self-ensure 并固定 conservative retry

目标：产品态 client 不再越权修复 broker 生命周期，同时保留安全 retry 规则。

具体文件变更：

- 修改 `scripts/runtime_kernel/client.py`。
- 修改 `tests/test_runtime_broker.py`。
- 修改 `tests/test_repo_consistency.py`。

详细步骤：

1. 删除或替换 `RuntimeBrokerClientV2Tests::test_client_stale_socket_retry_ensures_once`。
2. 新增 `RuntimeBrokerClientV2Tests::test_client_stale_socket_reports_launcher_reopen_without_self_ensure`：
   - patch env：`BUDDYSWITCH_INSTANCE_ID=inst-pm-example`、`BUDDYSWITCH_ACTIVE_BUDDY=pm`、`BUDDYSWITCH_RUNTIME_BROKER_SOCKET=/tmp/missing.sock`。
   - patch `client.subprocess.run`，测试结束断言未调用。
   - 调用 `request_runtime_broker("prepare", {"text": "x"})`。
   - 断言抛出 `RuntimeBrokerError`，code 为 `E_RUNTIME_BROKER_STALE_SOCKET` 或 `E_RUNTIME_BROKER_UNAVAILABLE`，details 包含 `permission_boundary: product-mode-runtime-broker`、`command_hint: ./buddyswitch-codex instance open inst-pm-example`、`socket_path: /tmp/missing.sock`。
3. 新增 `RuntimeBrokerClientV2Tests::test_client_retries_persist_once_after_transport_reset_when_key_present` 保留现有语义，断言没有调用 subprocess。
4. 新增 `RuntimeBrokerClientV2Tests::test_client_retries_read_only_env_tool_once_without_ensure`：
   - 使用 fake socket server 或 patch `_request_once` 第一次抛 `E_RUNTIME_BROKER_CLIENT_DISCONNECTED` 且 `retriable: True`，第二次返回 success。
   - params 使用 `{"tool": "task", "action": "list", "args": {}}`。
   - 断言 `_request_once` 调用两次，subprocess 未调用。
5. 新增 `RuntimeBrokerClientV2Tests::test_client_does_not_retry_mutating_env_tool_after_transport_reset`：
   - method `env.tool`，params `{"tool": "task", "action": "create", "args": {"title": "x"}}`。
   - `_request_once` 抛 transport reset。
   - 断言 `_request_once` 只调用一次。
6. 在 `RepoConsistencyTests` 新增 `test_product_runtime_client_does_not_self_ensure_broker`：
   - 读取 `scripts/runtime_kernel/client.py`。
   - 断言不包含 `_ensure_runtime_broker`。
   - 断言不包含 `"broker.py"` 与 `"ensure"` 组合的 subprocess command 字面量。
   - 断言不包含 `runtime-broker.pid`、`runtime-broker.socket`、`runtime-broker.log`。
7. 修改 `client.py`：
   - 删除 `import subprocess`。
   - 删除 `_ensure_runtime_broker()`。
   - 将 `BrokerRetryDecision` 改为仅包含 `should_retry`、`reason`，或保留字段但永远不设置 lifecycle mutation；推荐删除 `ensure_before_retry` 以避免双路径。
   - `_retry_decision()` 对 stale socket 返回：prepare false，persist with idempotency true，read-only env tool true，mutating false。
   - `request_runtime_broker()` retry 分支不再调用 ensure。
8. 运行 focused tests。

预期行为变化：

- 产品态 client 对 stale broker 只报告 launcher reopen hint。
- retry 不再伴随 lifecycle mutation。

对应需求编号：`REQ-015`、`REQ-016`、`REQ-017`、`REQ-018`、`REQ-019`、`REQ-026`。

验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_stale_socket_reports_launcher_reopen_without_self_ensure -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_retries_read_only_env_tool_once_without_ensure -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_does_not_retry_mutating_env_tool_after_transport_reset -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_product_runtime_client_does_not_self_ensure_broker -q
```

阶段完成标准：

- `rg -n "_ensure_runtime_broker|runtime-broker.pid|runtime-broker.socket|runtime-broker.log|broker.py.*ensure" scripts/runtime_kernel/client.py` 无输出。
- client retry tests 覆盖 prepare、persist、read-only env tool、mutating env tool。

### 阶段六：更新运行手册并跑完整验证

目标：把新的 broker root boundary 固化到 durable docs，并证明完整任务完成。

具体文件变更：

- 修改 `framework/docs/runtime-broker-v2-runbook.md`。

详细步骤：

1. 更新 `Health Criteria`：
   - healthy 需要 pid live、Unix socket、marker/socket 一致、ping identity 一致、ping pid/socket 一致、`env_store.ROOT` 为 runtime workspace、`runtime_workspace: true`。
2. 更新 `Ensure Flow`：
   - launcher start/open 调用 ensure。
   - lifecycle cwd 和 broker script 均来自 `${BUDDYSWITCH_WORKSPACE_DIR}`。
   - stale pid/socket/marker 由 launcher 清理。
   - failed startup 输出 log path，并清理 stale marker。
3. 更新 `Retry Policy`：
   - prepare 不自动 retry。
   - persist 仅 idempotency key 存在时 retry 一次。
   - read-only env tool retry 一次。
   - product client 不执行 broker ensure。
4. 更新 `Error Codes`：
   - 记录 stale/unavailable feedback 的 `permission_boundary` 和 reopen command hint。
5. 运行 focused 和 broader verification。

预期行为变化：

- 文档与代码行为一致，未来改动能通过静态测试和 runbook 测试维持边界。

对应需求编号：`REQ-025`、`REQ-027`。

验证命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_v2_runbook_documents_health_retry_and_errors -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
```

阶段完成标准：

- runbook 测试通过。
- runtime broker、launcher、repo consistency focused suites 通过。
- py_compile 通过。

## 6. 迁移 / 删除策略

要移除的旧实现：

- `tools/launcher/runtime_broker.sh` 中 source-root lifecycle execution：
  - `${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_kernel/broker.py`
  - `${BUDDYSWITCH_REPO_ROOT}/buddyswitch/manifest.toml` 默认 manifest
  - lifecycle command 前的 `cd "${BUDDYSWITCH_REPO_ROOT}"`
- `scripts/runtime_kernel/client.py::_ensure_runtime_broker()` 和它的 subprocess ensure command。
- `RuntimeBrokerClientV2Tests::test_client_stale_socket_retry_ensures_once` 的产品态自修复断言。

短期兼容：

- `BUDDYSWITCH_MANIFEST_PATH` 可继续作为显式测试和诊断覆盖路径保留，真实原因是现有 CLI lifecycle tests 和开发诊断会传入 manifest；退出条件是所有 launcher/runtime tests 都能从 workspace manifest 自动运行且没有手动 manifest 覆盖用例。
- 不保留 source-root broker script fallback。runtime surface 缺失时直接失败，退出码非零，Codex 不启动。

数据迁移：

- 无用户数据迁移。
- runtime state 路径保持 `buddyswitch/objects/*`、`buddyswitch/content/runs/*`、`runs/raw/*`。
- `instance_root/runtime/runtime-broker.*` stale 文件由 launcher ensure 清理；不转换为新格式。

## 7. 完成定义

整个任务完成必须同时满足：

- `tools/launcher/runtime_broker.sh` lifecycle script、manifest、cwd 均使用 runtime workspace。
- source-root broker startup 被静态测试阻断。
- `instance start` 后 fake Codex first prepare 通过真实 socket 成功，stdout 是业务 payload，run reservation 在 workspace 可见状态路径存在。
- `instance open` 能修复 stale pid/socket/marker，并在 Codex 启动后 first prepare 成功。
- `broker.py status` 输出 runtime root facts，healthy 判定要求 `env_store.ROOT` 为 runtime workspace 且 workspace marker 有效。
- 产品态 client 不写 broker lifecycle 文件，不运行 `broker.py ensure`，stale/missing broker 返回 launcher reopen feedback。
- retry policy 覆盖 prepare、persist、read-only env tool、mutating env tool。
- `framework/docs/runtime-broker-v2-runbook.md` 记录新边界。
- 以下最终验证通过：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_task_manager_env_tool.py -q
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
python3 -m pytest -p no:cacheprovider tests -q
```

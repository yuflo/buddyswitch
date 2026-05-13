# Runtime Broker V2 Implementation Plan

## 1. 任务目标

完成后，BuddySwitch product-mode 运行时通过一个可恢复、可观测、有结构化协议的本地 Unix socket broker 访问状态：`prepare`、`persist`、`env.tool` 仍由 broker 统一守住 active instance、active buddy、runtime lock 和写入边界，但 client timeout、broker 请求处理、生命周期恢复和 `persist` 重试语义不再互相冲突。

当前核心瓶颈是 broker 的同步单请求循环、EOF JSON framing、3 秒全包超时、pid/socket 健康判断和缺失的写入幂等性共同把一次普通 runtime lock 等待放大成 broker 进程退出与后续状态无法持久化。这个问题最重要，因为 product-mode 的所有状态访问都被设计为 broker-owned；broker 不可靠时，buddy 既不能安全写入，也不能被允许绕过 broker。

## 2. 需求提取

- `REQ-001`：保留本地 Unix socket broker 作为 product-mode state access gateway。
- `REQ-002`：替换当前脆弱同步循环，目标形态是小型本地 RPC gateway，不引入 gRPC、HTTP daemon、外部队列、systemd 依赖或数据库平台层。
- `REQ-003`：协议必须是显式 request/response，使用 `Content-Length` framing 和 UTF-8 JSON payload，不再使用“读到 EOF”判断单条消息结束。
- `REQ-004`：请求必须包含 `protocol`、`request_id`、`method`、`params`、`deadline_ms`；写方法必须带 `idempotency_key`。
- `REQ-005`：成功响应必须包含 `protocol`、`request_id`、`ok: true`、`result`，并把现有 product-mode payload 放在 `result` 下。
- `REQ-006`：失败响应必须包含 `protocol`、`request_id`、`ok: false`、`error`，其中 `error` 至少包含稳定 `code`、短 `message`、`retriable`，可包含 `retry_after_ms`、`permission_boundary`、`allowed_next_actions`、`broker_status`。
- `REQ-007`：不能长期保留 v1/v2 双 broker 栈；broker 和 client 在同一聚焦 change set 内切到 v2，公共 CLI 行为由测试保证。
- `REQ-008`：server 必须提供 bounded per-request isolation；一个慢请求、malformed request、client disconnect、`BrokenPipeError`、`ConnectionResetError` 或 handler exception 不得终止 broker 主进程。
- `REQ-009`：server 默认并发容量小而明确，`max_workers` 为 4；容量耗尽时返回 `E_RUNTIME_BROKER_BUSY`，且 `retriable: true`、`retry_after_ms: 250`。
- `REQ-010`：client timeout 必须拆分为 `connect_timeout`、`request_deadline`、`response_timeout`，不再用 3 秒覆盖 connect/send/处理/读取。
- `REQ-011`：默认 `connect_timeout` 为 0.75 秒，默认 `request_deadline` 为 35000 ms，`response_timeout` 与 request deadline 对齐。
- `REQ-012`：runtime lock timeout 不得大于 request deadline 减去响应余量；broker 在无法及时获取 runtime lock 时返回结构化 busy/deadline 错误，而不是让 client 误判 broker dead。
- `REQ-013`：client 生成 request id，贯穿 request、response、raised `RuntimeBrokerError` 和 CLI/API 输出。
- `REQ-014`：client 对 missing/stale broker 只执行一次受控 `ensure` 后重试；不能循环重试，不能要求 agent 运行 `ps` 等诊断作为正常恢复路径。
- `REQ-015`：retry 策略必须保守：`ping`、`status` 和 read-only `env.tool` 可自动重试一次；`prepare` 不盲目重试；`persist` 仅在有 idempotency key 时可重试； malformed request、active buddy mismatch、active instance mismatch、permission boundary error 不可重试。
- `REQ-016`：`persist` 幂等 key 为 `persist:<run_id>:<result_hash>`。
- `REQ-017`：同一 `persist` key 和同一 payload 重复提交必须返回原始 receipt。
- `REQ-018`：同一 run id 但不同 result hash 必须返回 `E_RUNTIME_PERSIST_CONFLICT`，并且不写入新状态。
- `REQ-019`：缺失 idempotency key 的 `persist` 必须在写入前返回 `E_RUNTIME_IDEMPOTENCY_REQUIRED`，`retriable: false`。
- `REQ-020`：dispatcher 必须继续拥有 method dispatch 和 product-mode checks，核心方法为 `prepare`、`persist`、`env.tool`，并保留 active instance、active buddy、instance status 校验。
- `REQ-021`：coordinator 必须显式拥有 runtime coordination policy：`prepare` 和 `persist` 为 write lock；`env.tool` 根据 action 声明 read/write；未知 env tool action 默认 write；`ping/status` 不持 runtime state write lock。
- `REQ-022`：第一版 coordination 继续使用现有 file lock primitive，不引入 SQLite、外部队列或通用事务引擎。
- `REQ-023`：lifecycle health 不能只看 pid file 或 socket path，必须校验 pid 是活进程、socket path 是 Unix socket、`ping` 返回预期 protocol/instance id/active buddy、pid file/socket marker/socket path 三者一致。
- `REQ-024`：`ensure` 必须执行健康检查；健康时返回 socket path；stale 时清理 pid file、marker file、socket path；启动 broker 后等待 `ping` 成功；启动失败时返回带 broker log path 的结构化失败。
- `REQ-025`：launcher shell 不再重复实现 pid/socket-only 健康逻辑；生命周期判断收敛到 Python `lifecycle.py`，shell 只负责传参和导出环境变量。
- `REQ-026`：错误不能再把 transport、timeout、permission、stale socket 全部折叠为 `E_RUNTIME_BROKER_UNAVAILABLE`。
- `REQ-027`：必须支持并使用重要错误码：`E_RUNTIME_BROKER_BUSY`、`E_RUNTIME_BROKER_DEADLINE_EXCEEDED`、`E_RUNTIME_BROKER_CLIENT_DISCONNECTED`、`E_RUNTIME_BROKER_STALE_SOCKET`、`E_RUNTIME_BROKER_PROTOCOL`、`E_RUNTIME_BROKER_PERMISSION`、`E_RUNTIME_PERSIST_CONFLICT`、`E_RUNTIME_IDEMPOTENCY_REQUIRED`。
- `REQ-028`：client disconnect 后 broker 可以记录 disconnect 并继续服务后续请求。
- `REQ-029`：product-mode `prepare` 和 `persist` 仍不得绕过 broker；broker server mode 内部调用仍是唯一例外。
- `REQ-030`：broker 只做本地 runtime gateway，不拥有 workflow policy、隐藏 routing、通用 orchestration、插件框架或规则框架。
- `REQ-031`：broker-issued evidence 和 controlled env tools 继续通过 broker boundary 执行。
- `REQ-032`：清理 obsolete broker loop code 和可删 shell lifecycle duplication。
- `REQ-033`：补齐 operational runbook 与 error meanings 文档。
- `REQ-034`：验收必须证明慢 handler 超过 client response timeout 不杀 broker。
- `REQ-035`：验收必须证明 client response 前断开不杀 broker，后续 `ping` 成功。
- `REQ-036`：验收必须证明 runtime lock contention 不再造成 3 秒 false broker-dead report。
- `REQ-037`：验收必须证明 missing socket 加 stale pid 可由 `ensure` 清理并恢复。
- `REQ-038`：验收必须证明 healthy broker status 由 `ping` 验证，而不是只由 pid/socket file 验证。
- `REQ-039`：验收必须证明 duplicate `persist` 同 key 同 payload 返回同一 receipt。
- `REQ-040`：验收必须证明 duplicate `persist` 同 run id 不同 result hash 返回 conflict 且无新写入。
- `REQ-041`：验收必须证明 active buddy 和 active instance mismatch 仍是结构化、不可重试错误。

## 3. 现状探索摘要

### 关键目录和文件

- `docs/memo/2026-05-12-runtime-broker-v2-redesign-memo.md`：本任务需求来源。
- `AGENTS.md`：要求 shortest tested path、直接替换旧逻辑、无验证不完成。
- `README.md`：确认 product runtime loop、broker-routed `env.tool`、launcher lifecycle 命令。
- `framework/docs/architecture-overview.md`：确认 runtime broker 是唯一 product-mode state writer。
- `framework/docs/turn-runtime-spec.md`：确认 public CLI 名称保持 `python3 scripts/turn_runtime.py prepare` 和 `persist`，product mode 不允许 direct host state-write fallback。
- `scripts/runtime_kernel/broker.py`：当前同步 broker，包含 `_serve`、`dispatch_runtime_request`、identity checks、business dispatch、runtime lock 包裹逻辑。
- `scripts/runtime_kernel/client.py`：当前 v1 client，`PROTOCOL = "buddyswitch-runtime-broker/v1"`，`request_runtime_broker()` 用 3 秒 socket timeout、裸 JSON、EOF framing。
- `scripts/runtime_kernel/persist.py`：broker persist entrypoint，当前只转发 `persist_buddy_run_request(context, result, manifest_path)`。
- `scripts/runtime_kernel/resolve.py`：broker prepare entrypoint，当前只转发 `prepare_turn_context_request(text, manifest_path)`。
- `scripts/turn_runtime.py`：product-mode CLI 在 `_cmd_prepare()`、`_cmd_persist()` 中调用 `request_runtime_broker()`；`_hold_product_runtime_lock()` 当前只支持 exclusive lock 和 env timeout。
- `scripts/env/client.py`：skill-facing env tool CLI，通过 `request_runtime_broker("env.tool", payload)` 进入 broker。
- `scripts/browser_evidence.py`：evidence wrapper，通过 `request_runtime_broker("env.tool", {"tool": "evidence", ...})` 进入 broker。
- `scripts/env/tools/contracts.py`：已有 `operation_semantics()`、`kind`、`mutates`，可直接作为 `env.tool` read/write classification 的数据源。
- `scripts/env/tools/router.py`、`scripts/env/tools/dispatch.py`：现有 env tool envelope validation 和 dispatch，要保留为 business path。
- `scripts/env/services/runs.py`：run commit service，需增加 broker persist 幂等字段读取/写入。
- `tools/launcher/runtime_broker.sh`：当前 shell 实现 socket path、pid file、log file、pid/socket-only active check、start wait、stop。
- `tools/launcher/workspace.sh`：`buddyswitch_workspace_sync_runtime_surface()` 已复制整个 `scripts/runtime_kernel` 目录，新增 runtime_kernel 模块会自动进入 product workspace。
- `buddyswitch-codex`：`start_locked_bootstrap()` 和 `instance_open_locked_bootstrap()` 调用 `buddyswitch_runtime_broker_ensure()`，`instance_set_inactive_locked()` 调用 `buddyswitch_runtime_broker_stop()`。
- `tests/test_runtime_broker.py`：当前 broker routing 和 identity checks 单测，会扩展为 protocol、server、client、coordinator、idempotency 覆盖。
- `tests/test_buddyswitch_launcher.py`：launcher 生命周期、runtime broker export、failure cleanup 测试，会增加 lifecycle ensure/status 覆盖。
- `tests/test_env_layer_end_to_end.py`：product-mode env.tool collaboration loop，用于证明 v2 不破坏 prepare/persist/env.tool 主路径。

### 需要运行的命令

- `python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q`
- `python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q`
- `python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py -q`
- `python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py`
- `python3 -m pytest -p no:cacheprovider tests -q`

### 保留、替换、删除、迁移

- 保留：Unix socket transport、`prepare`/`persist`/`env.tool` 方法、active instance/buddy/status 校验、broker server mode 内部例外、`env.tool` envelope 和服务层。
- 保留：`scripts/runtime_kernel/resolve.py` 和 `scripts/runtime_kernel/persist.py` 作为 prepare/persist runtime-kernel entrypoint；`persist.py` 需要扩展 idempotency 参数。
- 保留：`scripts/env/tools/contracts.py` 的 action semantics；新增 coordinator 直接读取 `get_action_spec()` 或 `operation_semantics()`。
- 替换：`scripts/runtime_kernel/broker.py` 中 `_serve()` 的同步 accept/read-dispatch-send loop，改成 thin CLI 调用 `lifecycle.py` 和 `server.py`。
- 替换：`scripts/runtime_kernel/client.py` 的 v1 裸 JSON/EOF/3 秒 timeout，改成 v2 framing、request id、deadline、structured error 和受控 ensure retry。
- 替换：`dispatch_runtime_request()` 的 v1 request shape，改为 `dispatcher.dispatch_runtime_request(BrokerRequest, RuntimeBrokerSession)` 使用 `params`/`result`。
- 替换：runtime lock policy 从 broker.py 中 method 分支内联 `with turn_runtime._hold_product_runtime_lock(...)` 移到 `scripts/runtime_kernel/coordinator.py`。
- 替换：`tools/launcher/runtime_broker.sh` 的 health/ensure 判断，改成调用 `python3 scripts/runtime_kernel/broker.py ensure|stop|status`。
- 删除：broker.py 内长期存在的 v1 protocol constant import、EOF framing、process-wide dispatch lock、未隔离 `conn.sendall()`。
- 删除：shell 中 `buddyswitch_runtime_broker_is_active()` 的 pid-only 决策；保留函数名时也必须改成 Python lifecycle status 的薄 wrapper。
- 迁移：run audit 新增 `idempotency_key` 和 `result_hash` 字段；历史 run audit 无这两个字段时只影响旧 run 的 duplicate retry，旧 run 继续可读。
- 不迁移：现有 task/track/artifact/run canonical object schema 不做批量迁移。

## 4. 最终目标架构

### 最终文件结构和职责

- 新增 `scripts/runtime_kernel/protocol.py`
  - 定义 `PROTOCOL = "buddyswitch-runtime-broker/v2"`。
  - 定义 `BrokerProtocolError`，字段为 `code`、`message`、`request_id`。
  - 定义 `make_request()`, `validate_request()`, `success_response()`, `error_response()`, `read_message()`, `write_message()`。
  - 负责 `Content-Length: <bytes>\r\n\r\n` framing、UTF-8 JSON decode、request envelope validation、response envelope construction。

- 新增 `scripts/runtime_kernel/server.py`
  - 定义 `RuntimeBrokerConfig` dataclass：`socket_path`、`pid_file`、`instance_json_path`、`manifest_path`、`max_workers=4`、`request_body_limit_bytes=1048576`、`response_margin_ms=1000`。
  - 定义 `RuntimeBrokerServer`，方法为 `serve_forever()`、`close()`、`_accept_loop()`、`_handle_connection()`。
  - 负责 Unix socket bind/listen/chmod、bounded request execution、handler exception isolation、client disconnect containment、capacity busy response。

- 新增 `scripts/runtime_kernel/dispatcher.py`
  - 定义 `RuntimeBrokerSession` dataclass：`instance_json_path`、`manifest_path`。
  - 定义 `dispatch_runtime_request(request: dict[str, Any], session: RuntimeBrokerSession) -> dict[str, Any]`。
  - 移入当前 broker.py 的 `_load_instance_record()`、`_runtime_server_env()`、`_product_session()`、`_prepare_dispatch()`、`_persist_dispatch()`、`_env_tool_dispatch()`、identity/status checks。
  - 继续调用 `prepare_turn_context_request()`、`persist_buddy_run_request()`、`dispatch_env_tool_request()`，并把业务 payload 放入 v2 `result`。

- 新增 `scripts/runtime_kernel/coordinator.py`
  - 定义 `class LockMode(str, Enum)`，值为 `NONE`、`READ`、`WRITE`。
  - 定义 `class RequestDeadline`，字段为 `request_id`、`started_monotonic`、`deadline_ms`、`response_margin_ms`，方法 `remaining_seconds()`、`lock_timeout_seconds()`、`expired()`。
  - 定义 `lock_mode_for_request(method: str, params: dict[str, Any]) -> LockMode`。
  - 定义 `dispatch_with_coordination(request, session, dispatch_fn) -> dict[str, Any]`。
  - 负责 lock policy：`prepare`/`persist` 写锁；`env.tool` 读取 `params.tool`/`params.action` 并查询 `env.tools.contracts.get_action_spec()`，`mutates == "none"` 为读锁，其他为写锁，未知 action 为写锁；`ping`/`status` 无 runtime state lock。

- 新增 `scripts/runtime_kernel/lifecycle.py`
  - 定义 `BrokerPaths` dataclass：`socket_path`、`pid_file`、`marker_file`、`log_file`。
  - 定义 `resolve_socket_path(instance_id, instance_root, marker_file)`, `read_pid()`, `pid_is_live()`, `ping_broker()`, `broker_status()`, `cleanup_stale_broker_state()`, `start_broker_process()`, `ensure_broker()`, `stop_broker()`。
  - 负责 pid/socket/marker consistency、ping-based health、stale cleanup、startup readiness wait、structured lifecycle failure。

- 修改 `scripts/runtime_kernel/client.py`
  - 更新 `PROTOCOL` 为 v2。
  - 新增 `RuntimeBrokerTimeouts` dataclass，默认 `connect_timeout_seconds=0.75`、`request_deadline_ms=35000`、`response_margin_ms=1000`。
  - 新增 `BrokerRetryDecision` dataclass 或等价字典，字段为 `should_retry`、`reason`、`ensure_before_retry`。
  - 修改 `request_runtime_broker(method, payload, *, deadline_ms=None, idempotency_key=None) -> dict[str, Any]`：生成 request id，写 v2 envelope，读 v2 response，成功返回 `result`，失败抛 `RuntimeBrokerError` 或返回 error payload 由调用方处理。
  - 新增 `make_persist_idempotency_key(context, result) -> str` 和 `canonical_result_hash(result) -> str`。
  - 对 missing/stale socket 执行一次 `ensure` 后重试，ensure 通过 `python3 scripts/runtime_kernel/broker.py ensure ...` 的 Python lifecycle CLI 完成，使用现有 product-mode env 定位 instance。

- 修改 `scripts/runtime_kernel/broker.py`
  - 保留为 thin CLI entrypoint。
  - CLI 子命令：`serve`、`ping`、`status`、`ensure`、`stop`。
  - `serve` 构造 `RuntimeBrokerConfig` 并调用 `RuntimeBrokerServer.serve_forever()`。
  - `ping/status/ensure/stop` 调用 `lifecycle.py`，输出 JSON；shell wrapper 根据 exit code 和 JSON 设置 env。

- 修改 `scripts/runtime_kernel/persist.py`
  - `persist_buddy_run_request(context, *, result, manifest_path=None, idempotency_key=None, result_hash=None)`。
  - 调用 `env.services.runs.commit_buddy_run(..., idempotency_key=idempotency_key, result_hash=result_hash)`。

- 修改 `scripts/turn_runtime.py`
  - `_hold_product_runtime_lock(product_session, *, mode="write", timeout_seconds=None)` 支持 `mode="read"` 时 `fcntl.LOCK_SH`，`mode="write"` 时 `fcntl.LOCK_EX`。
  - `_cmd_prepare()` 读取 broker v2 result，保持 stdout 的 prepare payload shape 不变。
  - `_cmd_persist()` 调用 client 生成 `persist` idempotency key，读取 broker v2 result，保持 stdout 的 persist payload shape 不变。
  - product-mode broker unavailable 时输出结构化 error，不提供 direct write fallback。

- 修改 `scripts/env/client.py`
  - `_dispatch_env_tool()` 读取 broker v2 result。
  - 当 `tool == "run"` 且 `action == "commit"` 时，根据 `args.context` 和 `args.result` 传入 idempotency key。
  - 非 idempotent write env.tool 在 transport reset 后不自动重试。

- 修改 `scripts/browser_evidence.py`
  - `_dispatch_issue()` 读取 broker v2 result。
  - 保持 stdout payload shape 为 `{"ok": true, "tool_evidence": ..., "feedback": ...}`。

- 修改 `scripts/env/services/runs.py`
  - 新增 `canonical_result_hash(result)` 或接收 client 计算结果并在 service 内复算验证。
  - `commit_buddy_run(context, *, result, manifest_path=DEFAULT_MANIFEST, idempotency_key=None, result_hash=None)`。
  - 成功 run audit 写入 `idempotency_key`、`result_hash`。
  - run content 已存在时，如果 stored `idempotency_key` 和 `result_hash` 与请求一致，返回由已存 audit 重建的 receipt；如果 run id 一致但 hash 不一致，返回/抛结构化 `E_RUNTIME_PERSIST_CONFLICT`。

- 修改 `tools/launcher/runtime_broker.sh`
  - `buddyswitch_runtime_broker_ensure()` 调用 `python3 "${broker_script}" ensure --socket ... --pid-file ... --marker-file ... --log-file ... --instance-json ... --manifest ...`。
  - `buddyswitch_runtime_broker_stop()` 调用 `python3 "${broker_script}" stop ...`。
  - `buddyswitch_runtime_broker_socket()` 仍读取 marker file，但 marker 写入由 Python lifecycle 完成。

- 修改 `framework/docs/turn-runtime-spec.md`
  - 更新 product-mode routing：v2 protocol、request id、structured errors、idempotent persist、ping-based lifecycle health。

- 修改 `framework/docs/architecture-overview.md`
  - 更新 runtime broker 描述为 local RPC gateway，声明不是 workflow engine。

- 新增 `framework/docs/runtime-broker-v2-runbook.md`
  - 记录 health criteria、ensure 行为、error code meanings、retry policy、常用验证命令。

### 核心数据模型

Broker request:

```json
{
  "protocol": "buddyswitch-runtime-broker/v2",
  "request_id": "req-<uuid-hex>",
  "method": "persist",
  "params": {
    "context": {},
    "result": {}
  },
  "deadline_ms": 35000,
  "idempotency_key": "persist:<run-id>:<sha256-result-hash>"
}
```

Broker success response:

```json
{
  "protocol": "buddyswitch-runtime-broker/v2",
  "request_id": "req-<uuid-hex>",
  "ok": true,
  "result": {
    "ok": true,
    "receipt": {},
    "refreshed_context": {}
  }
}
```

Broker error response:

```json
{
  "protocol": "buddyswitch-runtime-broker/v2",
  "request_id": "req-<uuid-hex>",
  "ok": false,
  "error": {
    "code": "E_RUNTIME_BROKER_BUSY",
    "message": "runtime broker is at request capacity",
    "retriable": true,
    "retry_after_ms": 250,
    "permission_boundary": "product-mode-runtime-broker"
  }
}
```

Broker status result:

```json
{
  "ok": true,
  "protocol": "buddyswitch-runtime-broker/v2",
  "instance_id": "<active-instance>",
  "active_buddy": "<active-buddy>",
  "pid": 12345,
  "socket_path": "/path/to/runtime-broker.sock",
  "marker_path": "/path/to/runtime-broker.socket",
  "healthy": true
}
```

Persist idempotency fields in run audit:

```json
{
  "run_id": "<run-id>",
  "idempotency_key": "persist:<run-id>:<sha256-result-hash>",
  "result_hash": "<sha256-result-hash>",
  "receipt_paths": {},
  "next_state": {}
}
```

### 调用流

1. Product host runs `python3 scripts/turn_runtime.py prepare "<request>"`.
2. `_cmd_prepare()` detects product mode and calls `request_runtime_broker("prepare", {"text": args.text})`.
3. `client.py` builds v2 envelope with request id and 35000 ms deadline, writes framed JSON to Unix socket, then waits until response deadline.
4. `server.py` accepts connection, reads one framed message, validates protocol envelope, and runs the request in bounded worker capacity.
5. `coordinator.py` classifies `prepare` as write lock, computes lock timeout from request deadline, acquires runtime lock, and calls `dispatcher.py`.
6. `dispatcher.py` validates active instance/buddy/status, sets broker server env, calls `prepare_turn_context_request()`, and returns the existing prepare payload under `result`.
7. `protocol.py` writes framed success response; if client disconnected, `server.py` catches transport write failure and keeps serving.
8. Product host runs `python3 scripts/turn_runtime.py persist --context ... --result ...`.
9. `_cmd_persist()` computes `persist:<run_id>:<result_hash>`, calls broker with idempotency key, and prints broker `result`.
10. `dispatcher.py` rejects missing idempotency key before service writes, passes valid key/hash into `persist_buddy_run_request()`, and returns duplicate same-key receipts from persisted audit when retried.

## 5. 分阶段实施计划

### PHASE-001：协议 framing 与结构化错误边界

**目标**

建立 v2 wire protocol 的唯一实现，先用单元测试证明 `Content-Length` framing、request validation、success/error envelope 和 malformed input 行为。此阶段不改 launcher，也不改变 product CLI 行为。

**具体文件变更**

- 新增 `scripts/runtime_kernel/protocol.py`
- 新增/修改 `tests/test_runtime_broker.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerProtocolTests`。
2. 增加 `test_protocol_round_trips_content_length_framed_json`：用 `socket.socketpair()` 或 `io.BytesIO` 写入两个连续 framed messages，断言 `read_message()` 分别读出两个 dict，且不会把第二条吞掉。
3. 增加 `test_protocol_rejects_missing_content_length`：输入 `b"{}\n"`，断言抛 `BrokerProtocolError`，`code == "E_RUNTIME_BROKER_PROTOCOL"`。
4. 增加 `test_protocol_rejects_invalid_json_body`：输入合法 header 加非法 JSON body，断言 error code 为 `E_RUNTIME_BROKER_PROTOCOL` 且 message 包含 `invalid JSON`。
5. 增加 `test_validate_request_requires_v2_protocol_request_id_method_params_deadline`：分别缺少 `protocol`、`request_id`、`method`、`params`、`deadline_ms`，断言 `validate_request()` 失败。
6. 增加 `test_write_methods_require_idempotency_key`：对 `method="persist"` 且无 `idempotency_key` 的请求断言 `validate_request()` 返回/抛 `E_RUNTIME_IDEMPOTENCY_REQUIRED`，并且没有调用业务 dispatch。
7. 实现 `protocol.py` 的 `PROTOCOL`、`BrokerProtocolError`、`read_message()`、`write_message()`、`validate_request()`、`success_response()`、`error_response()`。
8. `write_message()` 必须按 `Content-Length: <len>\r\n\r\n<body>` 输出；body 使用 `json.dumps(..., ensure_ascii=True, separators=(",", ":")).encode("utf-8")`。
9. `read_message()` 必须限制 header 最大 8192 bytes、body 最大 1048576 bytes；超过限制抛 `E_RUNTIME_BROKER_PROTOCOL`。
10. `error_response()` 在 request id 未知时使用 `"request_id": null`，在已知时原样回传。

**预期行为变化**

- 新增 v2 protocol 工具模块，但旧 broker/client 还未切换。
- malformed protocol 在模块级可以被归类为 structured broker protocol error。

**对应需求编号**

`REQ-003`、`REQ-004`、`REQ-005`、`REQ-006`、`REQ-019`、`REQ-027`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerProtocolTests -q
python3 -m py_compile scripts/runtime_kernel/protocol.py
```

**阶段完成标准**

- `RuntimeBrokerProtocolTests` 全部通过。
- `protocol.py` py_compile 通过。
- `rg -n "buddyswitch-runtime-broker/v2|Content-Length" scripts/runtime_kernel/protocol.py tests/test_runtime_broker.py` 能看到协议常量和 framing 测试。

### PHASE-002：server 请求隔离与 bounded capacity

**目标**

把 socket accept/read/write 与业务 dispatch 分离到 `server.py`，证明慢 handler、client disconnect、malformed request、BrokenPipe 不会杀 broker，并且超过 worker 容量时返回 structured busy。

**具体文件变更**

- 新增 `scripts/runtime_kernel/server.py`
- 修改 `scripts/runtime_kernel/broker.py`
- 修改 `tests/test_runtime_broker.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerServerIsolationTests`。
2. 增加测试 helper `start_test_broker_server(dispatch_fn, max_workers=1)`，使用临时 Unix socket、临时 pid file、`RuntimeBrokerServer` 后台线程，并在 cleanup 调用 `close()`。
3. 增加 `test_client_disconnect_before_response_does_not_stop_server`：dispatch 函数等待 event；client 发送 framed `ping` 后立即 close；释放 event 后再发第二个 `ping`，断言第二次返回 `ok: true`。
4. 增加 `test_broken_pipe_during_response_write_does_not_stop_server`：让 client 在 server 开始写 response 前 close；随后发送 `ping`，断言 broker 仍响应。
5. 增加 `test_malformed_request_returns_protocol_error_and_next_ping_succeeds`：发送 malformed frame，断言收到 `E_RUNTIME_BROKER_PROTOCOL` 或连接关闭后 broker 仍能处理下一次 `ping`。
6. 增加 `test_capacity_limit_returns_busy_without_killing_server`：`max_workers=1`，第一个请求阻塞，第二个请求收到 `E_RUNTIME_BROKER_BUSY`、`retriable: true`、`retry_after_ms: 250`，释放第一个后第三个 `ping` 成功。
7. 实现 `RuntimeBrokerConfig` 和 `RuntimeBrokerServer`。
8. `RuntimeBrokerServer.serve_forever()` 必须在启动时写 pid file，在 finally 中 unlink socket path；`broker.py` 不再直接实现 accept loop。
9. `_handle_connection()` 必须 catch `BrokerProtocolError` 并尝试写 structured error；catch `BrokenPipeError`、`ConnectionResetError`、`TimeoutError`、`OSError` 并记录到 stderr，不向 accept loop 抛出。
10. worker capacity 使用 `threading.BoundedSemaphore(max_workers)`；获取失败立即写 `E_RUNTIME_BROKER_BUSY`。
11. 修改 `broker.py serve`：解析原有 `--socket`、`--pid-file`、`--instance-json`、`--manifest`，构造 `RuntimeBrokerConfig`，传入 dispatcher stub 或现有 dispatch adapter。

**预期行为变化**

- broker socket serving 有请求级隔离。
- 单个连接异常不再终止 broker。
- 容量被占满时，client 得到可重试 busy error。

**对应需求编号**

`REQ-008`、`REQ-009`、`REQ-028`、`REQ-034`、`REQ-035`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests -q
python3 -m py_compile scripts/runtime_kernel/server.py scripts/runtime_kernel/broker.py
```

**阶段完成标准**

- server isolation tests 全部通过。
- 手动运行测试 broker 后，前一个 client 断开不会影响下一次 `ping`。
- `scripts/runtime_kernel/broker.py` 中不再包含旧 `_serve()` 的同步 `while True: conn, _ = server.accept()` 业务 dispatch 代码。

### PHASE-003：dispatcher 与 coordinator 边界

**目标**

把 business dispatch 和 runtime lock policy 从 broker.py 拆出去，保留现有 product behavior，同时让 `prepare`/`persist`/`env.tool` 的 read/write coordination 显式可测。

**具体文件变更**

- 新增 `scripts/runtime_kernel/dispatcher.py`
- 新增 `scripts/runtime_kernel/coordinator.py`
- 修改 `scripts/runtime_kernel/broker.py`
- 修改 `scripts/turn_runtime.py`
- 修改 `tests/test_runtime_broker.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerCoordinatorTests`。
2. 增加 `test_lock_mode_for_prepare_and_persist_is_write`：断言 `lock_mode_for_request("prepare", {"text": "x"}) == LockMode.WRITE`，`persist` 同理。
3. 增加 `test_lock_mode_for_read_only_env_tool_is_read`：输入 `{"tool": "task", "action": "list", "args": {}}` 和 `{"tool": "context", "action": "summarize", "args": {}}`，断言 `LockMode.READ`。
4. 增加 `test_lock_mode_for_mutating_env_tool_is_write`：输入 `task.create`、`track.attach_task`、`run.commit`、`evidence.issue_browser`，断言 `LockMode.WRITE`。
5. 增加 `test_unknown_env_tool_action_defaults_to_write`：输入 `{"tool": "task", "action": "unknown", "args": {}}`，断言 `LockMode.WRITE`。
6. 增加 `test_ping_and_status_do_not_acquire_runtime_lock`：patch `turn_runtime._hold_product_runtime_lock`，调用 `dispatch_with_coordination()` 的 `ping/status`，断言 lock helper 未被调用。
7. 将 `broker.py` 中 `_load_instance_record()`、`_instance_shared_root()`、`_runtime_server_env()`、`_product_session()`、`_prepare_dispatch()`、`_persist_dispatch()`、`_env_tool_dispatch()`、`dispatch_runtime_request()` 移到 `dispatcher.py`。
8. `dispatcher.dispatch_runtime_request()` 输入 v2 request，读取 `method` 和 `params`，保留 active instance/buddy/status error 的 `permission_boundary`，并把 `request_id` 传入 error response。
9. 在 `coordinator.py` 实现 `RequestDeadline.lock_timeout_seconds()`：`max(0.0, remaining_seconds() - response_margin_ms / 1000)`。
10. 修改 `turn_runtime._hold_product_runtime_lock(product_session, *, mode="write", timeout_seconds=None)`：`mode="read"` 使用 `fcntl.LOCK_SH | fcntl.LOCK_NB`，`mode="write"` 使用 `fcntl.LOCK_EX | fcntl.LOCK_NB`；`timeout_seconds is None` 时继续读取 `BUDDYSWITCH_RUNTIME_LOCK_TIMEOUT_SECONDS`。
11. 在 `coordinator.dispatch_with_coordination()` 内按 `LockMode` 获取 read/write lock；`TimeoutError` 转为 `E_RUNTIME_BROKER_DEADLINE_EXCEEDED`，`retriable: true`，`retry_after_ms: 250`。
12. 修改 `server.py` 调用 `coordinator.dispatch_with_coordination()`，而不是直接调用 dispatcher。
13. 保留 tests 中原有 `RuntimeBrokerTests.test_prepare_and_persist_enter_shared_runtime_lock`，更新 patch 断言包含 `mode="write"`。

**预期行为变化**

- 外部 CLI 输出仍与当前 product payload 兼容。
- runtime lock mode 由 coordinator 明确决定。
- read-only env.tool 可使用 shared read lock；写操作和未知操作使用 exclusive write lock。

**对应需求编号**

`REQ-020`、`REQ-021`、`REQ-022`、`REQ-029`、`REQ-030`、`REQ-031`、`REQ-036`、`REQ-041`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests tests/test_runtime_broker.py::RuntimeBrokerTests -q
python3 -m py_compile scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/turn_runtime.py
```

**阶段完成标准**

- coordinator tests 通过。
- 现有 broker routing 和 identity checks 仍通过。
- `rg -n "_hold_product_runtime_lock" scripts/runtime_kernel/broker.py` 无结果，lock policy 不再内联在 broker.py。

### PHASE-004：client deadline、request id 和 v2 response 适配

**目标**

切换 client 到 v2 协议，拆分 timeout，贯穿 request id，并让 `turn_runtime.py`、`scripts/env/client.py`、`scripts/browser_evidence.py` 读取 `result` 而不是旧 `payload`。

**具体文件变更**

- 修改 `scripts/runtime_kernel/client.py`
- 修改 `scripts/turn_runtime.py`
- 修改 `scripts/env/client.py`
- 修改 `scripts/browser_evidence.py`
- 修改 `tests/test_runtime_broker.py`
- 修改 `tests/test_env_layer_end_to_end.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerClientV2Tests`。
2. 增加 `test_client_sends_v2_request_id_deadline_and_reads_result`：测试 server 捕获 request，断言 `protocol` v2、`request_id` 非空、`deadline_ms == 35000`、`method`/`params` 正确；server 返回 `result={"ok": true, "value": 1}`，client 返回该 result。
3. 增加 `test_client_preserves_structured_error_fields`：server 返回 `E_RUNTIME_BROKER_PERMISSION`、`retriable: false`、`permission_boundary: "active-buddy"`，断言 `RuntimeBrokerError` 包含同一 code、request_id、details。
4. 增加 `test_client_connect_timeout_is_separate_from_response_deadline`：连接到不存在 socket 时错误发生在 connect timeout；连接成功但 response 延迟时不在 3 秒失败，测试使用小 deadline 200 ms 断言错误 code 为 `E_RUNTIME_BROKER_DEADLINE_EXCEEDED`。
5. 增加 `test_persist_request_includes_idempotency_key`：调用 `_cmd_persist()` 或 client helper，断言 outgoing request 带 `persist:<run_id>:<hash>`。
6. 实现 `RuntimeBrokerTimeouts`、`canonical_result_hash()`、`make_persist_idempotency_key()`。
7. `request_runtime_broker()` 构造 `params` 而不是 `payload`，用 `protocol.write_message()`，用 `protocol.read_message()`，成功时返回 response `result`。
8. `request_runtime_broker()` 对 response protocol mismatch、request_id mismatch、missing `ok` 返回 `RuntimeBrokerError("E_RUNTIME_BROKER_PROTOCOL", ...)`。
9. 修改 `_cmd_prepare()`：`broker_result = request_runtime_broker("prepare", {"text": args.text})`，直接把 `broker_result` 当 prepare payload 校验和打印。
10. 修改 `_cmd_persist()`：读取 context/result 后调用 `request_runtime_broker("persist", {"context": context, "result": result}, idempotency_key=make_persist_idempotency_key(context, result))`，直接把 broker result 当 persist payload 校验和打印。
11. 修改 `scripts/env/client.py` `_dispatch_env_tool()`：client 返回值已经是 v2 `result`；原有 invalid envelope error 保持。
12. 修改 `scripts/env/client.py` `_dispatch_run()`：当 operation 是 `commit` 时传 `idempotency_key=make_persist_idempotency_key(context, result)`。
13. 修改 `scripts/browser_evidence.py` `_dispatch_issue()`：按 result 校验 `tool_evidence` 和 `feedback`。
14. 更新 `tests/test_env_layer_end_to_end.py` 的 `PROTOCOL` 常量为 v2，并把 request shape 从 `payload` 改为 `params`。

**预期行为变化**

- product CLI stdout 仍打印原 prepare/persist payload。
- broker wire response 从 `{ok,payload}` 切换为 v2 `{ok,result}`，但调用者看到的是 `result`。
- `RuntimeBrokerError` 能暴露 request id 和 structured error details。

**对应需求编号**

`REQ-004`、`REQ-005`、`REQ-006`、`REQ-010`、`REQ-011`、`REQ-013`、`REQ-015`、`REQ-026`、`REQ-029`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests tests/test_env_layer_end_to_end.py -q
python3 -m py_compile scripts/runtime_kernel/client.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
```

**阶段完成标准**

- client v2 tests 通过。
- env layer end-to-end tests 通过。
- `rg -n "buddyswitch-runtime-broker/v1|request\\[\"payload\"\\]|get\\(\"payload\"\\)" scripts/runtime_kernel scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py` 无 v1 runtime broker 依赖。

### PHASE-005：lifecycle health、ensure、launcher integration

**目标**

把 broker health 和 ensure 收敛到 Python lifecycle，launcher shell 停止依赖 pid/socket-only 判断；missing socket + stale pid 能自动清理、重启并通过 `ping` 验证。

**具体文件变更**

- 新增 `scripts/runtime_kernel/lifecycle.py`
- 修改 `scripts/runtime_kernel/broker.py`
- 修改 `tools/launcher/runtime_broker.sh`
- 修改 `tests/test_runtime_broker.py`
- 修改 `tests/test_buddyswitch_launcher.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerLifecycleTests`。
2. 增加 `test_status_reports_unhealthy_when_pid_live_but_socket_missing`：创建 live pid file 指向当前进程、删除 socket，断言 `broker_status()["healthy"] is False`，`error.code == "E_RUNTIME_BROKER_STALE_SOCKET"`。
3. 增加 `test_status_reports_unhealthy_when_marker_disagrees_with_socket`：marker 指向 A，actual socket 参数是 B，断言 unhealthy 且 broker_status 包含 marker/socket mismatch。
4. 增加 `test_ensure_cleans_stale_pid_marker_and_socket_before_start`：创建 stale pid file、marker file、regular file socket path；patch `start_broker_process()` 和 `ping_broker()`，断言 stale 文件被清理，marker 写入新 socket。
5. 增加 `test_ensure_waits_for_ping_not_socket_existence`：让 socket 文件先出现但 `ping_broker()` 前两次失败、第三次成功，断言 ensure 成功发生在 ping 成功后。
6. 增加 `test_ensure_failure_returns_log_path`：`start_broker_process()` 后 ping 一直失败，断言 JSON error 包含 `broker_status.log_file`。
7. 实现 `BrokerPaths`、`resolve_socket_path()`，保留当前长 socket fallback：当 default socket path 长度大于等于 100，使用 `/tmp/buddyswitch-runtime-<sha1(instance_id)[:12]>.sock`。
8. 实现 `ping_broker()`：通过 client/protocol 发送 `method="ping"`、`params={}`，验证 result 中 `protocol`、`instance_id`、`active_buddy`。
9. 在 `dispatcher.py` 支持 `ping` 和 `status` 方法：`ping` 返回 broker protocol、instance id、active buddy、pid、socket path；`status` 返回更完整 lifecycle health 字段。
10. 实现 `ensure_broker()`：先 `broker_status()`；healthy 返回 socket path；unhealthy 调用 `cleanup_stale_broker_state()`；`start_broker_process()` 后循环 ping，最多 3 秒，每 100 ms 一次。
11. 修改 `broker.py` CLI 添加 `ping`、`status`、`ensure`、`stop` 子命令，所有子命令 stdout 输出 JSON。
12. 修改 `tools/launcher/runtime_broker.sh`：`buddyswitch_runtime_broker_ensure()` 使用 Python `ensure` 的 JSON 输出读取 socket path 并 export `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`；失败时 stderr 打印 JSON message 和 log path。
13. 修改 `tools/launcher/runtime_broker.sh`：`buddyswitch_runtime_broker_stop()` 调 Python `stop` 并清理 fallback socket、pid、marker。
14. 在 `tests/test_buddyswitch_launcher.py` 增加 `test_runtime_broker_ensure_recovers_stale_pid_and_missing_socket_before_codex_launch`：构造 instance runtime stale pid/marker，运行 `instance open` fake codex，断言 fake codex 收到非空 `runtime_broker_socket` 且 marker 指向存在 Unix socket。
15. 在 `tests/test_buddyswitch_launcher.py` 更新现有 browser bootstrap failure cleanup 断言，保留 pid/socket/marker 都不存在。

**预期行为变化**

- instance start/open 的 broker readiness 由 `ping` 决定。
- stale pid/socket/marker 自动清理。
- broker startup failure 给出 log path，不要求 agent 执行进程诊断。

**对应需求编号**

`REQ-014`、`REQ-023`、`REQ-024`、`REQ-025`、`REQ-032`、`REQ-037`、`REQ-038`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests tests/test_buddyswitch_launcher.py -q
python3 -m py_compile scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/broker.py
```

**阶段完成标准**

- lifecycle tests 和 launcher tests 通过。
- `tools/launcher/runtime_broker.sh` 中没有直接 `kill -0` 决定健康的路径；健康判断来自 `broker.py status|ensure`。
- `instance start` 和 `instance open` fake-codex 测试仍能导出 `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`。

### PHASE-006：persist 幂等性与 retry budget

**目标**

让 `persist` 在 transport timeout/reset 后可安全重试一次：同 key 同 payload 返回原 receipt，同 run id 不同 payload 返回 conflict，缺 key 在写入前拒绝。

**具体文件变更**

- 修改 `scripts/runtime_kernel/client.py`
- 修改 `scripts/runtime_kernel/dispatcher.py`
- 修改 `scripts/runtime_kernel/persist.py`
- 修改 `scripts/env/services/runs.py`
- 修改 `tests/test_runtime_broker.py`
- 修改 `tests/test_run_env_tool.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerPersistIdempotencyTests`。
2. 增加 `test_persist_without_idempotency_key_is_rejected_before_commit`：patch `persist_buddy_run_request`，发送 v2 `persist` 无 key，断言 response `E_RUNTIME_IDEMPOTENCY_REQUIRED`，patch 未被调用。
3. 增加 `test_duplicate_persist_same_key_same_payload_returns_original_receipt`：使用真实 prepare context 和 result 第一次 persist 成功；第二次用相同 key 和 result 调用，断言返回 receipt 完全相同，run content 文件数量不增加。
4. 增加 `test_duplicate_persist_same_run_different_result_hash_conflicts_without_write`：第一次 persist 成功；第二次同 context 不同 `execution_summary` 和不同 key/hash，断言 `E_RUNTIME_PERSIST_CONFLICT`，run audit 内容保持第一次结果。
5. 增加 `test_client_retries_persist_once_after_transport_reset_when_key_present`：test server 第一次接受 request 后 close 不回包，第二次返回 success；断言 server 收到两次相同 `idempotency_key` 和 `request_id` 不同。
6. 增加 `test_client_does_not_retry_prepare_after_transport_reset`：test server 第一次 reset，断言 `prepare` 只发送一次，错误 retriable details 说明未自动重试。
7. 修改 `dispatcher._persist_dispatch()`：读取 `request["idempotency_key"]`，缺失时返回 `E_RUNTIME_IDEMPOTENCY_REQUIRED`，`retriable: false`；存在时计算/接收 `result_hash` 并传入 `persist_buddy_run_request()`。
8. 修改 `persist_buddy_run_request()` signature，传递 idempotency。
9. 修改 `runs.commit_buddy_run()`：在 `_normalize_commit()` 前后检查 run id 是否已有 audit；已有 audit 且 key/hash 一致时返回 `{"ok": true, "receipt": existing_receipt, "refreshed_context": ...}`；已有 audit 且 hash 不一致时抛 `RuntimeFeedbackError` 或返回 structured error code `E_RUNTIME_PERSIST_CONFLICT`。
10. 修改 `runs.commit_buddy_run()`：首次成功写 audit 时写入 `idempotency_key` 和 `result_hash`。
11. 修改 `runs.get_run_receipt()`：不需要暴露 idempotency fields；receipt shape 不变。
12. 修改 `client.request_runtime_broker()` retry decision：missing/stale socket、transport reset、`E_RUNTIME_BROKER_BUSY` 可按 method 规则重试；`persist` 只有 idempotency key 才重试一次；`prepare` 不自动重试；read-only env.tool 重试一次；其他 writes 不自动重试。
13. 修改 `scripts/env/client.py` run commit path，确认 `run.commit` 也带同一 persist idempotency key。

**预期行为变化**

- `persist` 可以安全应对“client timeout 但 broker 已提交”的 hard case。
- 不同 result 不能覆盖已提交 run。
- 缺失 idempotency key 的 side-effecting persist 不会写状态。

**对应需求编号**

`REQ-015`、`REQ-016`、`REQ-017`、`REQ-018`、`REQ-019`、`REQ-039`、`REQ-040`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerPersistIdempotencyTests tests/test_run_env_tool.py -q
python3 -m py_compile scripts/runtime_kernel/client.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/persist.py scripts/env/services/runs.py
```

**阶段完成标准**

- idempotency tests 全部通过。
- run audit 中包含 `idempotency_key` 和 `result_hash`。
- duplicate same-key persist 不创建新 run audit、不改变原 audit。
- conflict response 包含 `E_RUNTIME_PERSIST_CONFLICT`、`retriable: false`。

### PHASE-007：清理旧路径、文档和端到端验收

**目标**

移除 v1 broker loop 和重复 lifecycle 逻辑，更新 runbook，并用 product-mode 主路径测试证明 Runtime Broker V2 完整替换旧路径。

**具体文件变更**

- 修改 `scripts/runtime_kernel/broker.py`
- 修改 `tools/launcher/runtime_broker.sh`
- 修改 `framework/docs/turn-runtime-spec.md`
- 修改 `framework/docs/architecture-overview.md`
- 新增 `framework/docs/runtime-broker-v2-runbook.md`
- 修改 `tests/test_runtime_broker.py`
- 修改 `tests/test_env_layer_end_to_end.py`
- 修改 `tests/test_buddyswitch_launcher.py`
- 修改 `tests/test_repo_consistency.py`

**详细步骤**

1. 在 `tests/test_runtime_broker.py` 增加 `RuntimeBrokerV2AcceptanceTests`，把 memo acceptance tests 汇总为 end-state assertions。
2. 增加 `test_slow_handler_exceeding_client_response_timeout_does_not_terminate_broker`：client 使用 200 ms deadline 调慢 handler，收到 deadline error；随后 `ping` 成功。
3. 增加 `test_runtime_lock_contention_returns_deadline_not_unavailable`：占住 runtime lock，发送 `prepare` 小 deadline，断言 `E_RUNTIME_BROKER_DEADLINE_EXCEEDED` 或 `E_RUNTIME_BROKER_BUSY`，不出现 `E_RUNTIME_BROKER_UNAVAILABLE`。
4. 增加 `test_active_identity_mismatch_errors_are_structured_non_retriable`：wrong instance 和 wrong buddy 都返回 `retriable: false`、对应 `permission_boundary`。
5. 修改 `tests/test_repo_consistency.py` 增加 static scan：`scripts/runtime_kernel/client.py`、`broker.py`、`tests/test_runtime_broker.py` 不再出现 `buddyswitch-runtime-broker/v1`；`broker.py` 不再出现 `sock.shutdown(socket.SHUT_WR)` 作为 broker framing 依赖；`tools/launcher/runtime_broker.sh` 不再出现 `kill -0` 作为 health success path。
6. 更新 `framework/docs/turn-runtime-spec.md` Product-Mode Routing 段落，写明 v2 request/response、deadline、idempotent persist、structured broker errors。
7. 更新 `framework/docs/architecture-overview.md` Runtime Boundaries 段落，写明 broker 是 local RPC gateway，不是 workflow engine。
8. 新增 `framework/docs/runtime-broker-v2-runbook.md`，包含 health criteria、`ensure` 步骤、error code table、retry policy、manual commands：`python3 scripts/runtime_kernel/broker.py status ...`、`ping`、`ensure`、`stop`。
9. 运行 focused tests，修复因 v2 result envelope 导致的 tests 断言。
10. 运行 broader verification。

**预期行为变化**

- v1 protocol 和 old serve loop 从 runtime path 消失。
- docs 明确 broker V2 的操作边界、错误和恢复方式。
- product-mode main path 通过 v2 完整运行。

**对应需求编号**

`REQ-001`、`REQ-002`、`REQ-007`、`REQ-026`、`REQ-027`、`REQ-032`、`REQ-033`、`REQ-034`、`REQ-035`、`REQ-036`、`REQ-037`、`REQ-038`、`REQ-041`

**验证命令**

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerV2AcceptanceTests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py tests/test_env_layer_end_to_end.py tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py -q
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
```

**阶段完成标准**

- acceptance tests 通过。
- repo consistency static scans 通过。
- `framework/docs/runtime-broker-v2-runbook.md` 存在并覆盖 health、ensure、retry、error meanings。
- `rg -n "buddyswitch-runtime-broker/v1|read until EOF|E_RUNTIME_BROKER_UNAVAILABLE.*active_buddy|E_RUNTIME_BROKER_UNAVAILABLE.*permission" scripts/runtime_kernel framework/docs tests` 没有旧协议或错误折叠证据。

## 6. 迁移 / 删除策略

- 删除旧 v1 runtime broker protocol：`PROTOCOL = "buddyswitch-runtime-broker/v1"` 不保留兼容分支，因为 product-mode runtime surface 由 launcher 同步，client 和 server 同仓库同版本运行。
- 删除旧 EOF framing：不保留 read-until-EOF fallback，避免双协议路径让 transport bugs 继续存在。
- 删除 broker.py 同步 serve loop：`broker.py` 只保留 CLI entrypoint，server 行为在 `server.py`。
- 删除 broker.py process-local dispatch lock：runtime state coordination 由 `coordinator.py` 和 file lock primitive 表达，server capacity 由 bounded workers 表达。
- 删除 shell pid/socket-only health 成功路径：`runtime_broker.sh` 可以保留函数名，但健康判断必须委托 `broker.py status|ensure`。
- 不删除 `turn_runtime._hold_product_runtime_lock()`：它保留为 runtime file lock primitive，并新增 read/write mode；lock policy 不再写在 broker.py。
- 不迁移历史 run audit：新增 `idempotency_key`、`result_hash` 只用于新 V2 persist。旧 run 继续由 `get_run_receipt()` 可读；旧 run 不参与 duplicate persist retry，因为旧 run 没有对应 prepared retry 上下文。
- 短期兼容仅限 public CLI stdout shape：`prepare` 和 `persist` 仍打印原 payload，不暴露 broker envelope；这是真实用户/skill contract，不是 v1 broker stack 兼容。退出条件不存在，因为 CLI payload shape 是稳定外部使用面。

## 7. 完成定义

整个任务完成必须同时满足：

- `scripts/runtime_kernel/protocol.py`、`server.py`、`dispatcher.py`、`coordinator.py`、`lifecycle.py` 存在并承担上述职责。
- `scripts/runtime_kernel/broker.py` 不再包含旧同步 accept/read-dispatch-send loop。
- `scripts/runtime_kernel/client.py` 使用 v2 protocol、Content-Length framing、request id、分离 timeout 和 conservative retry。
- `tools/launcher/runtime_broker.sh` 的 ensure/status/stop 通过 Python lifecycle 执行，broker readiness 由 `ping` 验证。
- product-mode `prepare`、`persist`、`env.tool` CLI 输出 shape 保持可用，状态写入仍不能绕过 broker。
- `persist` 同 key 同 payload 重试返回原 receipt，同 run id 不同 payload 返回 `E_RUNTIME_PERSIST_CONFLICT`，缺 key 写入前返回 `E_RUNTIME_IDEMPOTENCY_REQUIRED`。
- structured errors 保留 request id，并区分 busy、deadline、stale socket、protocol、permission、persist conflict、idempotency required。
- 文档 `framework/docs/runtime-broker-v2-runbook.md`、`framework/docs/turn-runtime-spec.md`、`framework/docs/architecture-overview.md` 已更新。
- focused verification 通过：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py -q
```

- final verification 通过：

```bash
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
python3 -m pytest -p no:cacheprovider tests -q
```

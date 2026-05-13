# Runtime Broker V2 Test Plan

## 1. 测试设计原则

- 测试从 runtime broker 的外部可观察行为出发：Unix socket wire protocol、CLI stdout payload、structured error、pid/socket/marker state、run audit 持久化、launcher export 的 broker socket。
- 测试覆盖用户工作流：product-mode `prepare`、host execution 后 `persist`、skill-facing `env.tool`、browser evidence issuance、instance start/open lifecycle recovery。
- 测试覆盖系统不变量：product-mode state writes 只能经过 broker；active instance/buddy/status mismatch 不可重试；runtime lock contention 不等于 broker dead；重复 `persist` 不得重复写入或覆盖原 run。
- 测试覆盖失败模式：malformed frame、invalid request envelope、client disconnect、BrokenPipe、capacity busy、deadline exceeded、missing socket、stale pid、marker mismatch、transport reset、duplicate persist conflict。
- 测试不根据实现细节反推断言；断言 wire response、CLI output、filesystem state、run audit state、error fields 和 broker survivability。
- 每个阶段先写 focused failing tests，再实现最小直接变更，阶段内运行 focused tests，完成前运行 broader verification。

## 2. 需求覆盖矩阵

| Requirement | 覆盖测试 |
| --- | --- |
| `REQ-001` | `ACCEPT-001`, `E2E-001`, `CLI-001` |
| `REQ-002` | `STATIC-001`, `ACCEPT-001` |
| `REQ-003` | `UNIT-001`, `UNIT-002`, `STATIC-001` |
| `REQ-004` | `UNIT-004`, `CLIENT-001`, `IDEMP-001` |
| `REQ-005` | `UNIT-005`, `CLIENT-001`, `E2E-001` |
| `REQ-006` | `UNIT-006`, `CLIENT-002`, `COORD-005`, `ACCEPT-004` |
| `REQ-007` | `STATIC-001`, `E2E-001` |
| `REQ-008` | `SERVER-001`, `SERVER-002`, `SERVER-003`, `ACCEPT-002` |
| `REQ-009` | `SERVER-004` |
| `REQ-010` | `CLIENT-003`, `ACCEPT-003` |
| `REQ-011` | `CLIENT-001`, `CLIENT-003` |
| `REQ-012` | `COORD-006`, `ACCEPT-003` |
| `REQ-013` | `CLIENT-001`, `CLIENT-002` |
| `REQ-014` | `LIFE-003`, `CLIENT-004`, `CLI-002` |
| `REQ-015` | `CLIENT-005`, `CLIENT-006`, `IDEMP-004`, `COORD-005` |
| `REQ-016` | `IDEMP-002`, `IDEMP-003`, `RUN-001` |
| `REQ-017` | `IDEMP-002`, `RUN-001` |
| `REQ-018` | `IDEMP-003`, `RUN-002` |
| `REQ-019` | `IDEMP-001` |
| `REQ-020` | `DISP-001`, `DISP-002`, `DISP-003`, `E2E-001` |
| `REQ-021` | `COORD-001`, `COORD-002`, `COORD-003`, `COORD-004`, `COORD-005` |
| `REQ-022` | `COORD-006`, `STATIC-002` |
| `REQ-023` | `LIFE-001`, `LIFE-002`, `LIFE-004` |
| `REQ-024` | `LIFE-003`, `LIFE-004`, `CLI-002` |
| `REQ-025` | `STATIC-003`, `CLI-002` |
| `REQ-026` | `CLIENT-002`, `ACCEPT-003`, `ACCEPT-004`, `STATIC-004` |
| `REQ-027` | `UNIT-006`, `SERVER-004`, `IDEMP-001`, `IDEMP-003`, `ACCEPT-003` |
| `REQ-028` | `SERVER-001`, `SERVER-002`, `ACCEPT-002` |
| `REQ-029` | `CLI-001`, `E2E-001`, `STATIC-005` |
| `REQ-030` | `STATIC-006`, documentation review in `DOC-001` |
| `REQ-031` | `E2E-002`, `E2E-003` |
| `REQ-032` | `STATIC-001`, `STATIC-003` |
| `REQ-033` | `DOC-001` |
| `REQ-034` | `ACCEPT-002` |
| `REQ-035` | `SERVER-001`, `ACCEPT-002` |
| `REQ-036` | `ACCEPT-003` |
| `REQ-037` | `LIFE-003`, `CLI-002` |
| `REQ-038` | `LIFE-004`, `CLI-002` |
| `REQ-039` | `IDEMP-002`, `RUN-001` |
| `REQ-040` | `IDEMP-003`, `RUN-002` |
| `REQ-041` | `DISP-002`, `DISP-003`, `ACCEPT-004` |

所有需求都适合自动化覆盖。`DOC-001` 是文档内容检查，用 static assertions 验证关键 heading 和 error code table 存在；不依赖人工目测。

## 3. 测试分层

### 单元测试

目的：验证 protocol、deadline、lock classification、idempotency helper、lifecycle state interpretation 等纯逻辑。

覆盖范围：

- `scripts/runtime_kernel/protocol.py`
- `scripts/runtime_kernel/coordinator.py`
- `scripts/runtime_kernel/client.py` helper
- `scripts/runtime_kernel/lifecycle.py` status/cleanup helper
- `scripts/env/services/runs.py` duplicate run audit behavior

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerProtocolTests tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests -q
python3 -m pytest -p no:cacheprovider tests/test_run_env_tool.py -q
```

### 集成测试

目的：验证真实 Unix socket server/client、bounded worker、dispatcher、coordinator、run service 组合行为。

覆盖范围：

- server isolation
- client v2 request/response
- product-mode identity checks
- deadline 和 lock contention
- duplicate persist

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q
```

### CLI、API、UI 或主路径运行测试

目的：验证 user-facing CLI output 和 launcher lifecycle。

覆盖范围：

- `python3 scripts/turn_runtime.py prepare`
- `python3 scripts/turn_runtime.py persist`
- `python3 scripts/env/client.py ...`
- `python3 scripts/browser_evidence.py ...`
- `./buddyswitch-codex instance start/open` fake codex lifecycle

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_evidence_env_tool.py -q
```

### 回归测试

目的：防止旧 v1 protocol、EOF framing、pid/socket-only health 和 broker bypass 回流。

覆盖范围：

- static scans in `tests/test_repo_consistency.py`
- existing runtime broker identity checks
- existing env tool response contract
- existing launcher cleanup tests

运行命令：

```bash
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_runtime_broker.py tests/test_env_tool_response_contract.py tests/test_buddyswitch_launcher.py -q
```

### 手动验证

手动验证只用于开发者本地观察，不作为完成替代：

```bash
./buddyswitch-codex instance start --buddy pm
python3 scripts/runtime_kernel/broker.py status --socket <socket> --pid-file <pid> --marker-file <marker> --instance-json <instance.json> --manifest buddyswitch/manifest.toml
```

完成判断仍以自动化测试和 py_compile 为准。

## 4. 详细测试用例

### UNIT-001

- 覆盖需求：`REQ-003`
- 场景：protocol 可以从同一个 stream 读取两条连续 Content-Length framed JSON。
- 前置条件：构造两个 v2 request dict。
- 输入：`write_message(sock, first)` 后 `write_message(sock, second)`。
- 预期输出或状态变化：两次 `read_message()` 分别返回 first 和 second。
- 断言重点：第一条 body 长度精确；第二条未被第一条读取吞掉。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerProtocolTests::test_protocol_round_trips_content_length_framed_json`

### UNIT-002

- 覆盖需求：`REQ-003`, `REQ-027`
- 场景：缺失 Content-Length header 的输入被识别为 protocol error。
- 前置条件：无。
- 输入：`b"{}\n"`。
- 预期输出或状态变化：抛 `BrokerProtocolError`。
- 断言重点：`code == "E_RUNTIME_BROKER_PROTOCOL"`，message 包含 `Content-Length`。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerProtocolTests::test_protocol_rejects_missing_content_length`

### UNIT-003

- 覆盖需求：`REQ-003`, `REQ-027`
- 场景：合法 header 携带非法 JSON body。
- 前置条件：无。
- 输入：`Content-Length: 1\r\n\r\n{`。
- 预期输出或状态变化：抛 `BrokerProtocolError`。
- 断言重点：`code == "E_RUNTIME_BROKER_PROTOCOL"`，message 包含 `invalid JSON`。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerProtocolTests::test_protocol_rejects_invalid_json_body`

### UNIT-004

- 覆盖需求：`REQ-004`
- 场景：v2 request envelope 缺任一必填字段。
- 前置条件：构造合法 request，然后分别删除字段。
- 输入：缺 `protocol`、`request_id`、`method`、`params`、`deadline_ms` 的 request。
- 预期输出或状态变化：每个 request validation 失败。
- 断言重点：error code 为 `E_RUNTIME_BROKER_PROTOCOL`；`request_id` 已知时被保留。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerProtocolTests::test_validate_request_requires_v2_protocol_request_id_method_params_deadline`

### UNIT-005

- 覆盖需求：`REQ-005`, `REQ-006`
- 场景：success/error response envelope shape。
- 前置条件：request id 为 `req-test`。
- 输入：`success_response("req-test", {"ok": true})` 和 `error_response("req-test", {...})`。
- 预期输出或状态变化：response 均包含 v2 protocol 和 request id。
- 断言重点：success 只有 `result` 承载业务 payload；error 只有 `error` 承载错误对象。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerProtocolTests::test_response_envelopes_use_result_or_error`

### UNIT-006

- 覆盖需求：`REQ-006`, `REQ-027`
- 场景：error helper 为缺少 retriable 的 error 自动填入 `retriable: false`。
- 前置条件：构造 error dict 只含 code/message。
- 输入：`error_response("req", {"code": "E_RUNTIME_BROKER_PERMISSION", "message": "denied"})`。
- 预期输出或状态变化：error object 完整。
- 断言重点：`retriable is False`，`request_id == "req"`。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerProtocolTests::test_error_response_defaults_non_retriable`

### SERVER-001

- 覆盖需求：`REQ-008`, `REQ-028`, `REQ-035`
- 场景：client 在 response 前断开，broker 继续服务。
- 前置条件：启动 test broker，dispatch 等待 event。
- 输入：第一个 client 发送 framed `ping` 后立即 close；第二个 client 发送 `ping`。
- 预期输出或状态变化：第二个 client 收到 success response。
- 断言重点：broker thread alive；第二次 response `ok: true`。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests::test_client_disconnect_before_response_does_not_stop_server`

### SERVER-002

- 覆盖需求：`REQ-008`, `REQ-028`
- 场景：server 写 response 时遭遇 BrokenPipe。
- 前置条件：启动 test broker，dispatch 返回较大 payload 或受控延迟。
- 输入：client 发送 request 后 close。
- 预期输出或状态变化：server 捕获 write failure。
- 断言重点：随后 `ping` 成功。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests::test_broken_pipe_during_response_write_does_not_stop_server`

### SERVER-003

- 覆盖需求：`REQ-008`
- 场景：malformed request 不杀 broker。
- 前置条件：启动 test broker。
- 输入：发送 malformed frame，然后发送 valid `ping`。
- 预期输出或状态变化：malformed 得到 protocol error 或连接关闭；valid ping 成功。
- 断言重点：error code 不为 `E_RUNTIME_BROKER_UNAVAILABLE`；broker still alive。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests::test_malformed_request_returns_protocol_error_and_next_ping_succeeds`

### SERVER-004

- 覆盖需求：`REQ-009`, `REQ-027`
- 场景：bounded worker 容量耗尽。
- 前置条件：`max_workers=1`，第一个 request 阻塞。
- 输入：第二个 request。
- 预期输出或状态变化：第二个 request 收到 busy error。
- 断言重点：`error.code == "E_RUNTIME_BROKER_BUSY"`，`retriable is True`，`retry_after_ms == 250`。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests::test_capacity_limit_returns_busy_without_killing_server`

### DISP-001

- 覆盖需求：`REQ-020`
- 场景：matching identity 的 `prepare` 和 `persist` 仍成功。
- 前置条件：临时 runtime root、active PM instance json。
- 输入：v2 `prepare` request，随后 v2 `persist` request。
- 预期输出或状态变化：prepare result `ok: true`；persist result `ok: true`；run audit 写入。
- 断言重点：业务 payload 在 `result` 下；instance json 不被 dispatch 误改。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerTests::test_prepare_and_persist_succeed_with_matching_identity`

### DISP-002

- 覆盖需求：`REQ-020`, `REQ-041`
- 场景：wrong instance id 被结构化拒绝。
- 前置条件：active instance json 为 `inst-pm-example`。
- 输入：request `instance_id="inst-other"`。
- 预期输出或状态变化：response `ok: false`。
- 断言重点：`permission_boundary == "active-instance"`，`error.retriable is False`，`error.code` 不使用 unavailable。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerTests::test_rejects_wrong_instance_id_with_non_retriable_structured_error`

### DISP-003

- 覆盖需求：`REQ-020`, `REQ-041`
- 场景：wrong active buddy 被结构化拒绝。
- 前置条件：active instance buddy 为 `pm`。
- 输入：request `active_buddy="market"`。
- 预期输出或状态变化：response `ok: false`。
- 断言重点：`permission_boundary == "active-buddy"`，`error.retriable is False`。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerTests::test_rejects_wrong_active_buddy_with_non_retriable_structured_error`

### COORD-001

- 覆盖需求：`REQ-021`
- 场景：prepare/persist 都需要 write lock。
- 前置条件：无。
- 输入：`lock_mode_for_request("prepare", {"text": "x"})` 和 `persist`。
- 预期输出或状态变化：返回 `LockMode.WRITE`。
- 断言重点：两个 method 都不是 read/none。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_lock_mode_for_prepare_and_persist_is_write`

### COORD-002

- 覆盖需求：`REQ-021`
- 场景：read-only env.tool 用 read lock。
- 前置条件：`scripts/env/tools/contracts.py` 中 `task.list`、`context.summarize` 为 `mutates: none`。
- 输入：env.tool params。
- 预期输出或状态变化：返回 `LockMode.READ`。
- 断言重点：classification 来自 contract，不是硬编码 method-only。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_lock_mode_for_read_only_env_tool_is_read`

### COORD-003

- 覆盖需求：`REQ-021`
- 场景：mutating env.tool 用 write lock。
- 前置条件：contracts 中存在 mutating actions。
- 输入：`task.create`、`track.attach_task`、`run.commit`、`evidence.issue_browser`。
- 预期输出或状态变化：均返回 `LockMode.WRITE`。
- 断言重点：`mutates != "none"` 都是 write。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_lock_mode_for_mutating_env_tool_is_write`

### COORD-004

- 覆盖需求：`REQ-021`
- 场景：未知 env.tool action 保守使用 write lock。
- 前置条件：无。
- 输入：`{"tool": "task", "action": "merge", "args": {}}`。
- 预期输出或状态变化：返回 `LockMode.WRITE`。
- 断言重点：未知不是 read/none。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_unknown_env_tool_action_defaults_to_write`

### COORD-005

- 覆盖需求：`REQ-021`, `REQ-006`
- 场景：ping/status 不持 runtime state lock。
- 前置条件：patch `turn_runtime._hold_product_runtime_lock`。
- 输入：v2 `ping` 和 `status` request。
- 预期输出或状态变化：返回 success。
- 断言重点：lock helper 未调用。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_ping_and_status_do_not_acquire_runtime_lock`

### COORD-006

- 覆盖需求：`REQ-012`, `REQ-022`
- 场景：runtime lock contention 在 deadline 内无法获取。
- 前置条件：占用 runtime lock；request deadline 设置为 200 ms。
- 输入：`prepare` request。
- 预期输出或状态变化：broker 返回 deadline/busy structured error。
- 断言重点：error code 是 `E_RUNTIME_BROKER_DEADLINE_EXCEEDED` 或 `E_RUNTIME_BROKER_BUSY`；不出现 unavailable。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests::test_lock_contention_returns_structured_deadline_error`

### CLIENT-001

- 覆盖需求：`REQ-004`, `REQ-005`, `REQ-011`, `REQ-013`
- 场景：client 发送 v2 request 并读取 result。
- 前置条件：test socket server 捕获 raw request。
- 输入：`request_runtime_broker("prepare", {"text": "Draft PRD"})`。
- 预期输出或状态变化：client 返回 server 的 `result`。
- 断言重点：outgoing request 含 v2 protocol、request_id、deadline_ms、params；response result 被解包。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_sends_v2_request_id_deadline_and_reads_result`

### CLIENT-002

- 覆盖需求：`REQ-006`, `REQ-013`, `REQ-026`
- 场景：client 保留 structured error details。
- 前置条件：test server 返回 permission error。
- 输入：`request_runtime_broker("env.tool", {...})`。
- 预期输出或状态变化：抛 `RuntimeBrokerError`。
- 断言重点：exception 有 code、message、request_id、permission_boundary、retriable false。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_preserves_structured_error_fields`

### CLIENT-003

- 覆盖需求：`REQ-010`, `REQ-011`
- 场景：connect timeout 与 response deadline 独立。
- 前置条件：不存在 socket path；另一个 test server 接受连接但延迟响应。
- 输入：client timeouts 使用默认 connect 和小 request deadline。
- 预期输出或状态变化：不存在 socket 报 stale/unavailable transport；延迟响应报 deadline exceeded。
- 断言重点：延迟响应不再固定 3 秒才失败；错误分类不同。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_connect_timeout_is_separate_from_response_deadline`

### CLIENT-004

- 覆盖需求：`REQ-014`
- 场景：missing socket 触发一次 ensure 后重试。
- 前置条件：env 指向 missing socket；patch lifecycle ensure 成功创建 test server。
- 输入：`request_runtime_broker("ping", {})`。
- 预期输出或状态变化：client 第一次失败后调用 ensure 一次，第二次成功。
- 断言重点：ensure call count 为 1；没有无限循环。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_runs_one_controlled_ensure_for_missing_socket`

### CLIENT-005

- 覆盖需求：`REQ-015`
- 场景：persist transport reset 且有 idempotency key 时自动重试一次。
- 前置条件：test server 第一次 close，第二次 success。
- 输入：`request_runtime_broker("persist", params, idempotency_key=key)`。
- 预期输出或状态变化：client 成功返回 result。
- 断言重点：两个 request id 不同，idempotency key 相同，发送次数为 2。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_retries_persist_once_after_transport_reset_when_key_present`

### CLIENT-006

- 覆盖需求：`REQ-015`
- 场景：prepare transport reset 不盲目重试。
- 前置条件：test server 第一次 close。
- 输入：`request_runtime_broker("prepare", {"text": "x"})`。
- 预期输出或状态变化：client 抛 transport error。
- 断言重点：server 收到 request 次数为 1。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_client_does_not_retry_prepare_after_transport_reset`

### LIFE-001

- 覆盖需求：`REQ-023`
- 场景：pid live 但 socket missing。
- 前置条件：pid file 写当前 pid；socket path 不存在。
- 输入：`broker_status(paths, expected_instance_id, expected_active_buddy)`。
- 预期输出或状态变化：status unhealthy。
- 断言重点：`error.code == "E_RUNTIME_BROKER_STALE_SOCKET"`。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_status_reports_unhealthy_when_pid_live_but_socket_missing`

### LIFE-002

- 覆盖需求：`REQ-023`
- 场景：marker path 与 socket path 不一致。
- 前置条件：marker file 内容为 A，expected socket 为 B。
- 输入：`broker_status(...)`。
- 预期输出或状态变化：status unhealthy。
- 断言重点：broker_status 包含 marker path 和 socket path，`healthy is False`。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_status_reports_unhealthy_when_marker_disagrees_with_socket`

### LIFE-003

- 覆盖需求：`REQ-014`, `REQ-024`, `REQ-037`
- 场景：ensure 清理 stale pid/marker/socket 并启动。
- 前置条件：stale pid file、marker file、regular file at socket path；patch start 和 ping。
- 输入：`ensure_broker(paths, ...)`。
- 预期输出或状态变化：旧文件被移除，marker 写入新 socket path。
- 断言重点：cleanup 发生在 start 前；ensure 返回 `ok: true` 和 socket path。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_ensure_cleans_stale_pid_marker_and_socket_before_start`

### LIFE-004

- 覆盖需求：`REQ-023`, `REQ-024`, `REQ-038`
- 场景：ensure 等待 ping 成功，而不是只看 socket 存在。
- 前置条件：start 后 socket 出现；ping 前两次失败第三次成功。
- 输入：`ensure_broker(...)`。
- 预期输出或状态变化：ensure 成功。
- 断言重点：ping call count 为 3；返回状态来自 ping payload。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_ensure_waits_for_ping_not_socket_existence`

### LIFE-005

- 覆盖需求：`REQ-024`
- 场景：broker startup failure 返回 log path。
- 前置条件：start 返回 pid，但 ping 一直失败。
- 输入：`ensure_broker(...)`。
- 预期输出或状态变化：ensure 返回 `ok: false`。
- 断言重点：error 包含 `broker_status.log_file`。
- 测试类型：单元测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests::test_ensure_failure_returns_log_path`

### IDEMP-001

- 覆盖需求：`REQ-004`, `REQ-019`, `REQ-027`
- 场景：persist 缺 idempotency key。
- 前置条件：patch `persist_buddy_run_request`。
- 输入：v2 `persist` request 无 `idempotency_key`。
- 预期输出或状态变化：response error。
- 断言重点：`E_RUNTIME_IDEMPOTENCY_REQUIRED`，`retriable false`，persist service 未调用。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerPersistIdempotencyTests::test_persist_without_idempotency_key_is_rejected_before_commit`

### IDEMP-002

- 覆盖需求：`REQ-016`, `REQ-017`, `REQ-039`
- 场景：duplicate persist 同 key 同 payload。
- 前置条件：临时 runtime root；prepare 成功；result 固定。
- 输入：同 context/result/key 调用 persist 两次。
- 预期输出或状态变化：两次 receipt 相同。
- 断言重点：run content 文件数量不增加；第二次不清空或改写 audit。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerPersistIdempotencyTests::test_duplicate_persist_same_key_same_payload_returns_original_receipt`

### IDEMP-003

- 覆盖需求：`REQ-018`, `REQ-027`, `REQ-040`
- 场景：duplicate persist 同 run id 不同 result hash。
- 前置条件：第一次 persist 已成功。
- 输入：同 context，result 改 `execution_summary`。
- 预期输出或状态变化：第二次返回 conflict。
- 断言重点：`E_RUNTIME_PERSIST_CONFLICT`，`retriable false`，run audit 仍是第一次内容。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerPersistIdempotencyTests::test_duplicate_persist_same_run_different_result_hash_conflicts_without_write`

### IDEMP-004

- 覆盖需求：`REQ-015`
- 场景：read-only env.tool 可 retry，mutating env.tool 不自动 retry。
- 前置条件：test server 对第一次 request reset。
- 输入：`task.list` 和 `task.create` env.tool。
- 预期输出或状态变化：`task.list` 发送两次，`task.create` 发送一次并报错。
- 断言重点：retry policy 按 read/write classification。
- 测试类型：集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests::test_retry_policy_distinguishes_read_and_write_env_tool`

### RUN-001

- 覆盖需求：`REQ-016`, `REQ-017`, `REQ-039`
- 场景：run service 从已存 audit 重建 receipt。
- 前置条件：已有 run audit 含 idempotency key/hash。
- 输入：`commit_buddy_run()` 同 context/result/key/hash。
- 预期输出或状态变化：返回 receipt。
- 断言重点：receipt 不包含 idempotency fields；audit mtime 或内容不变。
- 测试类型：单元/集成测试。
- 建议路径和名称：`tests/test_run_env_tool.py::RunEnvToolTests::test_duplicate_run_commit_returns_existing_receipt_for_same_idempotency_key`

### RUN-002

- 覆盖需求：`REQ-018`, `REQ-040`
- 场景：run service 对同 run id 不同 hash 拒绝。
- 前置条件：已有 run audit 含 hash A。
- 输入：`commit_buddy_run()` 同 context，result hash B。
- 预期输出或状态变化：structured conflict。
- 断言重点：run audit content 未变化。
- 测试类型：单元/集成测试。
- 建议路径和名称：`tests/test_run_env_tool.py::RunEnvToolTests::test_duplicate_run_commit_conflicts_for_different_result_hash`

### CLI-001

- 覆盖需求：`REQ-001`, `REQ-029`
- 场景：product-mode prepare/persist CLI 通过 broker，但 stdout payload shape 保持。
- 前置条件：临时 product env、live v2 broker。
- 输入：`python3 scripts/turn_runtime.py prepare "Draft onboarding PRD"`，随后 persist。
- 预期输出或状态变化：stdout JSON 是 prepare/persist payload，不是 broker envelope。
- 断言重点：stdout top-level 有业务 `ok`；没有 top-level `protocol`。
- 测试类型：CLI 主路径测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerV2AcceptanceTests::test_product_cli_prepare_and_persist_print_business_payload_not_broker_envelope`

### CLI-002

- 覆盖需求：`REQ-014`, `REQ-024`, `REQ-025`, `REQ-037`, `REQ-038`
- 场景：launcher instance open 遇到 stale broker state 自动恢复。
- 前置条件：instance runtime 目录有 stale pid/marker，fake codex 捕获 env。
- 输入：`./buddyswitch-codex instance open <instance-id> debug prompt-input continue`。
- 预期输出或状态变化：fake codex 启动，收到 `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`。
- 断言重点：marker 指向 socket；status/ping healthy；stale pid 已替换。
- 测试类型：CLI/launcher 集成测试。
- 建议路径和名称：`tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_runtime_broker_ensure_recovers_stale_pid_and_missing_socket_before_codex_launch`

### E2E-001

- 覆盖需求：`REQ-001`, `REQ-005`, `REQ-007`, `REQ-020`, `REQ-029`
- 场景：完整 env layer collaboration loop 仍能通过 v2 broker。
- 前置条件：`tests/test_env_layer_end_to_end.py` 临时 runtime root。
- 输入：PM prepare、task/track/artifact env tools、persist。
- 预期输出或状态变化：所有 env.tool 成功，run audit 和 artifacts/tracks 状态正确。
- 断言重点：request protocol v2；业务状态与旧主路径一致。
- 测试类型：端到端测试。
- 建议路径和名称：`tests/test_env_layer_end_to_end.py::EnvLayerEndToEndTests::test_full_buddy_loop_uses_env_tool_and_persists_state`

### E2E-002

- 覆盖需求：`REQ-031`
- 场景：browser evidence wrapper 通过 v2 env.tool issuance。
- 前置条件：Market context 和 fake browser readiness。
- 输入：`python3 scripts/browser_evidence.py issue --context <context> --mode browser-cockpit-preflight`。
- 预期输出或状态变化：stdout 含 `tool_evidence` 和 `feedback`。
- 断言重点：wrapper 解包 v2 result 后仍输出原业务 shape。
- 测试类型：CLI/集成测试。
- 建议路径和名称：`tests/test_evidence_env_tool.py::EvidenceEnvToolTests::test_live_broker_evidence_cli_uses_env_tool_and_returns_structured_rejection`

### E2E-003

- 覆盖需求：`REQ-031`
- 场景：skill-facing env client 通过 v2 broker 调用 controlled env tool。
- 前置条件：active runtime broker env。
- 输入：`python3 scripts/env/client.py task list`。
- 预期输出或状态变化：stdout JSON 为 env.tool business payload。
- 断言重点：没有 broker envelope 泄漏；错误时 structured feedback 保留。
- 测试类型：CLI/集成测试。
- 建议路径和名称：`tests/test_task_env_tool.py::TaskEnvToolTests::test_live_broker_task_cli_uses_env_tool_and_returns_structured_rejection`

### ACCEPT-001

- 覆盖需求：`REQ-001`, `REQ-002`
- 场景：Runtime Broker V2 是 local RPC gateway，不是外部服务平台。
- 前置条件：代码完成。
- 输入：static scan。
- 预期输出或状态变化：没有新增 gRPC/HTTP daemon/external queue 依赖。
- 断言重点：`scripts/runtime_kernel` 不导入 `grpc`、`http.server`、`sqlite3`；broker transport 仍是 `AF_UNIX`。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_v2_stays_local_unix_socket_gateway`

### ACCEPT-002

- 覆盖需求：`REQ-034`, `REQ-035`
- 场景：慢 handler 超过 client response timeout 或 client disconnect 后 broker 不退出。
- 前置条件：test broker running。
- 输入：小 deadline slow request，disconnect request，后续 ping。
- 预期输出或状态变化：slow request 返回 deadline；disconnect 无响应；后续 ping 成功。
- 断言重点：broker process/thread alive。
- 测试类型：验收集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerV2AcceptanceTests::test_slow_handler_and_disconnect_do_not_terminate_broker`

### ACCEPT-003

- 覆盖需求：`REQ-010`, `REQ-012`, `REQ-026`, `REQ-036`
- 场景：runtime lock contention 不再导致 false broker-dead report。
- 前置条件：占用 runtime lock。
- 输入：发送 `prepare` request。
- 预期输出或状态变化：structured deadline/busy error。
- 断言重点：error code 不等于 `E_RUNTIME_BROKER_UNAVAILABLE`；subsequent ping success。
- 测试类型：验收集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerV2AcceptanceTests::test_runtime_lock_contention_returns_deadline_not_unavailable`

### ACCEPT-004

- 覆盖需求：`REQ-006`, `REQ-026`, `REQ-041`
- 场景：active identity mismatch 是不可重试结构化错误。
- 前置条件：active instance json。
- 输入：wrong instance request、wrong buddy request。
- 预期输出或状态变化：两个 response `ok: false`。
- 断言重点：`retriable false`；permission boundary 分别是 `active-instance`、`active-buddy`；request id present。
- 测试类型：验收集成测试。
- 建议路径和名称：`tests/test_runtime_broker.py::RuntimeBrokerV2AcceptanceTests::test_active_identity_mismatch_errors_are_structured_non_retriable`

### STATIC-001

- 覆盖需求：`REQ-003`, `REQ-007`, `REQ-032`
- 场景：v1 protocol 和 EOF framing 不回流。
- 前置条件：代码完成。
- 输入：static scan runtime files。
- 预期输出或状态变化：scan 通过。
- 断言重点：没有 `buddyswitch-runtime-broker/v1`；broker server 不依赖 `shutdown(socket.SHUT_WR)` 作为 framing。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_v1_protocol_and_eof_framing_are_removed`

### STATIC-002

- 覆盖需求：`REQ-022`
- 场景：coordination 未引入 SQLite/queue/transaction engine。
- 前置条件：代码完成。
- 输入：static scan `scripts/runtime_kernel`。
- 预期输出或状态变化：scan 通过。
- 断言重点：没有 `sqlite3`、`queue.Queue` 用作 durable queue、`grpc`、HTTP server imports。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_coordination_keeps_file_lock_primitive`

### STATIC-003

- 覆盖需求：`REQ-025`, `REQ-032`
- 场景：launcher 不再用 pid/socket-only 判断 healthy。
- 前置条件：代码完成。
- 输入：static scan `tools/launcher/runtime_broker.sh`。
- 预期输出或状态变化：scan 通过。
- 断言重点：health success path 调 `broker.py status|ensure`；没有 `kill -0` 直接返回 healthy。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_launcher_health_delegates_to_python_lifecycle`

### STATIC-004

- 覆盖需求：`REQ-026`, `REQ-027`
- 场景：错误未继续全部折叠到 unavailable。
- 前置条件：代码完成。
- 输入：static scan 和 structured error tests。
- 预期输出或状态变化：scan 通过。
- 断言重点：listed error codes 出现在 tests；permission mismatch tests 不断言 unavailable。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_structured_error_codes_are_covered`

### STATIC-005

- 覆盖需求：`REQ-029`
- 场景：product-mode prepare/persist 不出现 direct fallback。
- 前置条件：代码完成。
- 输入：static scan `scripts/turn_runtime.py`。
- 预期输出或状态变化：scan 通过。
- 断言重点：broker exception path 输出 runtime error；不调用 direct `prepare_turn_context`/`persist_buddy_run` fallback。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_product_mode_prepare_persist_do_not_bypass_runtime_broker`

### STATIC-006

- 覆盖需求：`REQ-030`
- 场景：broker 没有演变成 workflow/rules/plugin engine。
- 前置条件：代码完成。
- 输入：static scan `scripts/runtime_kernel`。
- 预期输出或状态变化：scan 通过。
- 断言重点：没有 `workflow`, `rule_engine`, `plugin`, `router_policy` 等新 runtime ownership 模块名；dispatcher 只包含 broker method dispatch。
- 测试类型：回归/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_does_not_add_workflow_or_rule_engine`

### DOC-001

- 覆盖需求：`REQ-033`
- 场景：runbook 覆盖 operational behavior。
- 前置条件：`framework/docs/runtime-broker-v2-runbook.md` 存在。
- 输入：读取文档。
- 预期输出或状态变化：文档包含 required sections。
- 断言重点：包含 `Health Criteria`、`Ensure Flow`、`Retry Policy`、`Error Codes`，并列出 `E_RUNTIME_BROKER_BUSY`、`E_RUNTIME_BROKER_DEADLINE_EXCEEDED`、`E_RUNTIME_PERSIST_CONFLICT`、`E_RUNTIME_IDEMPOTENCY_REQUIRED`。
- 测试类型：文档/static。
- 建议路径和名称：`tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_broker_v2_runbook_documents_health_retry_and_errors`

## 5. 负向与边界测试

- 缺失数据：`UNIT-004` 覆盖 request 必填字段缺失；`IDEMP-001` 覆盖 `persist` 缺 idempotency key；`CLIENT-002` 覆盖 structured error field preservation。
- 无效状态：`LIFE-001` 覆盖 pid live/socket missing；`LIFE-002` 覆盖 marker mismatch；`DISP-002`/`DISP-003` 覆盖 active identity mismatch；现有 inactive instance test 继续覆盖 instance status invalid。
- 重复操作：`IDEMP-002` 覆盖 duplicate same payload；`IDEMP-003` 覆盖 duplicate different payload；`RUN-001`/`RUN-002` 在 service 层防止绕过 broker tests。
- 并发或顺序敏感行为：`SERVER-004` 覆盖 capacity；`COORD-006` 和 `ACCEPT-003` 覆盖 runtime lock contention；`SERVER-001`/`SERVER-002` 覆盖 disconnect/write race。
- 空输入、空集合、空记录、空配置：`UNIT-004` 覆盖空/missing request envelope；现有 env.tool router tests 继续覆盖 missing tool/action/args；新增 coordinator unknown action 默认 write。
- 权限、路径、配置、运行状态、外部依赖异常：`DISP-002`、`DISP-003`、inactive instance existing test 覆盖 permission/status；`LIFE-003` 覆盖 stale filesystem state；`LIFE-005` 覆盖 startup failure 和 log path；`CLIENT-004` 覆盖 missing socket recovery。

## 6. 作弊防护

- Protocol tests 使用连续两条 framed messages，防止实现只用 `json.loads(sock.recv())` 硬编码通过单条 request。
- Server tests 使用真实 Unix socket 和 client close/BrokenPipe 场景，断言后续 `ping` 成功，防止只 catch exception 但 server 已停止。
- Capacity test 使用阻塞 handler 和第二个并发 request，防止实现忽略 `max_workers` 或只在单线程下返回 busy。
- Coordinator tests 覆盖 read、write、unknown action 多组合，并从 `scripts/env/tools/contracts.py` 读取 action semantics，防止硬编码 `task.list` 一个 case。
- Client retry tests 断言发送次数、request id 变化和 idempotency key 保持，防止无限重试或对 `prepare` 盲目重试。
- Idempotency tests 同时检查 response receipt 和 filesystem run audit 数量/内容，防止只返回固定成功 payload 而重复写状态。
- Lifecycle tests 同时检查 pid/socket/marker 文件状态和 ping call count，防止只看 socket 存在就宣称 healthy。
- Static scans 防止 v1 protocol、EOF framing、pid/socket-only health、broker bypass 和平台化依赖回流。
- E2E tests 保持多 buddy/env tool/product CLI 路径覆盖，防止实现只服务 `ping` 和单个 happy path。

## 7. 验证命令清单

### Focused test commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerProtocolTests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerServerIsolationTests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerCoordinatorTests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerClientV2Tests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerLifecycleTests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerPersistIdempotencyTests -q
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py::RuntimeBrokerV2AcceptanceTests -q
```

### Broader verification commands

```bash
python3 -m pytest -p no:cacheprovider tests/test_runtime_broker.py -q
python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_evidence_env_tool.py tests/test_task_env_tool.py -q
python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_env_tool_response_contract.py -q
```

### Final verification commands

```bash
python3 -m py_compile scripts/runtime_kernel/protocol.py scripts/runtime_kernel/server.py scripts/runtime_kernel/dispatcher.py scripts/runtime_kernel/coordinator.py scripts/runtime_kernel/lifecycle.py scripts/runtime_kernel/client.py scripts/runtime_kernel/broker.py scripts/turn_runtime.py scripts/env/client.py scripts/browser_evidence.py
python3 -m pytest -p no:cacheprovider tests -q
```

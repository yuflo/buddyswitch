# Codex Runtime Provenance Forward Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 Actor 创建与 attach 对 ambient `PATH` 的双重 Codex 选择，使每个 Actor 使用一个明确、可验证、可追溯的 Codex runtime，同时彻底阻止 fake Codex 测试污染真实 `~/.codex-buddyswitch`。

**Architecture:** 新增具体的 `CodexRuntime` owner，只负责解析、记录和校验 Codex executable/version。Host Control 在创建 Actor 时唯一选择并写入 runtime descriptor；App Server、Actor Session 和 actor-scoped Codex helper 只消费该 descriptor，不再自行查询 PATH。测试 fake Codex 必须运行在系统临时 shared root；stop/delete 继续只依赖 Host Control 的 PID/socket/filesystem 清理能力。

**Tech Stack:** Python 3、Bash launcher、JSON instance record、`subprocess`、`unittest`/`pytest`、现有 Host Control/App Server/Actor Session。

---

## 1. 当前问题

本次故障包含两个独立问题：

1. 测试隔离泄漏：fake Codex 位于临时 PATH，但 `BUDDYSWITCH_SHARED_ROOT` 指向真实 `~/.codex-buddyswitch`，因此测试创建了真实目录和长驻 fake App Server。
2. Runtime 身份不一致：Actor 创建时 `app_server.py` 通过裸 `codex` 使用当时 PATH；attach 又通过当前 PATH/BUDDYSWITCH_CODEX_BIN 选择 TUI；`instance.json` 没有 executable/version，系统无法在连接前识别不匹配。

直接表现为：真实 `codex-cli 0.144.1` TUI 连接 fake App Server 后，`account/read` 响应缺少 `requiresOpenaiAuth`，在 TUI bootstrap 阶段解码失败。

## 2. 目标与不变量

### 2.1 Runtime descriptor

新 Actor 的 `instance.json` 必须包含：

```json
{
  "codex_runtime": {
    "executable": "/absolute/canonical/path/to/codex",
    "version": "codex-cli 0.144.1"
  }
}
```

不变量：

- `executable` 必须是 canonical absolute executable path。
- `version` 必须来自该 executable 的 `--version`，不能为空。
- descriptor 在 Actor 创建时确定，在 Actor 生命周期内固定。
- App Server start/resume、MCP 配置命令和 attach TUI 使用同一 executable。
- attach/input 在任何 App Server RPC 前验证 descriptor。
- 当前 PATH 或 attach-only 环境变量不能改变已有 Actor runtime。

### 2.2 清理边界

`status`、`stop`、`delete` 必须能处理 runtime 缺失、路径失效或版本不匹配的 Actor：

- status 原样投影 descriptor，并将进程健康状态保持为独立字段，不伪造 runtime 有效性。
- stop 依据已记录 PID/socket 终止进程。
- delete 清理实例目录和注册状态。
- stop/delete 不执行 Codex，不调用 `account/read`，不要求 runtime descriptor 有效。

这是异常资源清理能力，不是旧 runtime 兼容路径。

### 2.3 无兼容 rebuild

- 不回填旧 `instance.json`。
- 不从 PATH 为旧 Actor lazy seed runtime。
- 不保留 Actor Session constructor `codex_bin` 参数。
- 不保留 CLI attach-only `BUDDYSWITCH_CODEX_BIN` 分支。
- 不保留 `app_server.py` 的 `codex_bin="codex"` 默认值。
- 不保留 `env.sh` 的裸 `codex "$@"`。
- 不做新旧 schema 双读后继续运行；缺 descriptor 的 Actor 只能 status/stop/delete，然后重新创建。

## 3. 模块边界

### `tools/launcher/codex_runtime.py`

唯一责任：

- 解析显式候选或 `shutil.which("codex")`。
- canonicalize executable。
- 执行 `--version`。
- 从 instance payload 构造 descriptor。
- 校验路径、可执行性和版本一致性。

禁止责任：进程生命周期、CODEX_HOME/auth、Actor 状态、通用 runtime plugin。

### Host Control

- `start` 是 runtime descriptor 的唯一选择与写入入口。
- 将 descriptor 通过 private Host Control 参数传入 shell owner。
- `resume` 读取已有 descriptor，不重新查询 PATH。
- `status` 投影 descriptor 与 runtime state。
- stop/delete 不验证 runtime。

### App Server

- 只接受显式 absolute `--codex-bin`。
- 不解析 PATH，不读取 runtime record，不选择版本。

### Actor Session

- 从 instance record 读取并验证 runtime。
- input/attach 共用验证后的 Actor context。
- attach descriptor 的 `argv[0]` 必须是 recorded executable。

### Fake Codex

- `--version` 返回稳定测试版本。
- 除 `--version` 外，shared root 与测试 process registry 必须同时位于系统临时根，否则立即拒绝运行。
- 测试结束由既有 cleanup/process registry 负责终止进程。

## 4. 文件范围

Create:

- `tools/launcher/codex_runtime.py`
- `tests/test_codex_runtime.py`
- `tests/test_fake_codex.py`

Modify:

- `tools/launcher/host_control.py`
- `tools/launcher/host_control.sh`
- `tools/launcher/env.sh`
- `tools/launcher/app_server.py`
- `tools/launcher/app_server.sh`
- `tools/launcher/actor_session.py`
- `tools/launcher/cli.py`
- `tools/launcher/cli_contract.py`
- `tools/launcher/web_management.py`
- `tests/helpers/fake_codex.py`
- `tests/test_host_control.py`
- `tests/test_actor_session.py`
- `tests/test_app_server_client.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_web_management.py`
- `tests/test_runless_runtime_contract.py`

Review as architecture gates, unchanged when no failure is found:

- `tests/test_repo_consistency.py`
- `tests/test_external_control_architecture.py`

不修改 Task Sys、Message、IM、Actor Tool Env、Track/Task projection 或 Workspace 结构。

## 5. Focused Test 命令

所有 Python 测试统一使用：

```bash
bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest <targets> -q'
```

本任务不运行 `pytest tests -q`。最终验证仅覆盖直接相关测试和架构门禁。

## 6. 实施任务

### Task 1: 建立 CodexRuntime owner

**Files:**
- Create: `tools/launcher/codex_runtime.py`
- Create: `tests/test_codex_runtime.py`

- [x] **Step 1: 写 RED tests**

覆盖：显式绝对 executable、PATH resolution、版本读取、record round-trip、缺字段、相对路径、不可执行文件、版本变化。

目标 API：

```python
@dataclass(frozen=True)
class CodexRuntime:
    executable: Path
    version: str

    def to_record(self) -> dict[str, str]: ...

class CodexRuntimeError(RuntimeError):
    code: str

def resolve_codex_runtime(candidate: str | None = None) -> CodexRuntime: ...
def runtime_from_instance(payload: Mapping[str, object]) -> CodexRuntime: ...
def validate_codex_runtime(runtime: CodexRuntime) -> CodexRuntime: ...
```

- [x] **Step 2: 验证 RED**

```bash
bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_codex_runtime.py -q'
```

Expected: import/file missing failure。

- [x] **Step 3: 实现最小 owner**

错误代码固定为：

- `RUNTIME_UNAVAILABLE`：找不到、不可执行或无法读取版本。
- `RUNTIME_MISMATCH`：record 路径当前版本与记录版本不同。
- `INVALID_RUNTIME_RECORD`：record schema 非法。

- [x] **Step 4: 验证 GREEN**

Expected: `tests/test_codex_runtime.py` PASS。

### Task 2: Host Control 唯一选择并持久化 runtime

**Files:**
- Modify: `tools/launcher/host_control.py`
- Modify: `tools/launcher/host_control.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_host_control.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_runless_runtime_contract.py`

- [x] **Step 1: 写 RED tests**

断言：

- `HostControl.start("pm")` 只调用一次 resolver。
- private start args 包含 role、absolute executable、version。
- 新 instance record 包含 exact descriptor。
- resume 使用 record descriptor；当前 PATH/BUDDYSWITCH_CODEX_BIN 改变不影响它。
- 缺 descriptor 的 resume 返回 `RUNTIME_MISMATCH`，不启动 Codex。
- stop/delete 对缺 descriptor 的旧/损坏 record 仍成功。

- [x] **Step 2: 验证 RED**

```bash
bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_host_control.py tests/test_buddyswitch_launcher.py -q -k "runtime or start or resume or stop or delete"'
```

Expected: descriptor/runner assertions fail。

- [x] **Step 3: 实现单轨 Host flow**

- `HostControl` 注入具体 resolver，start 解析后调用 private owner。
- private `start` 接受 `<role> <executable> <version>`。
- lock subprocess 通过明确环境传递 descriptor。
- `buddyswitch_instance_activate` 原子写入 `codex_runtime`。
- resume 从 record 读取并验证 descriptor，然后绑定内部 `BUDDYSWITCH_CODEX_BIN`。
- `buddyswitch_run_codex` 必须执行 `"${BUDDYSWITCH_CODEX_BIN}"`，缺失时失败。
- status 输出 `codex_runtime`，但不因 invalid runtime 阻止 status。

- [x] **Step 4: 验证 GREEN**

运行上述 focused tests，Expected: PASS。

### Task 3: App Server 与 Actor Session 只消费 recorded runtime

**Files:**
- Modify: `tools/launcher/app_server.py`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tools/launcher/actor_session.py`
- Modify: `tools/launcher/cli.py`
- Modify: `tools/launcher/cli_contract.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_app_server_client.py`
- Modify: `tests/test_actor_session.py`
- Modify: `tests/test_web_management.py`

- [x] **Step 1: 写 RED tests**

断言：

- App Server ensure 缺 `--codex-bin` 失败。
- `ensure_app_server()` 使用传入 absolute executable。
- Actor Session constructor 不再接受 `codex_bin`。
- `_context()` 在 input/attach RPC 前校验 runtime。
- attach `argv[0]` 等于 record executable。
- 当前 PATH 与 `BUDDYSWITCH_CODEX_BIN` 指向其它 binary 时 attach 仍使用 record。
- missing/version mismatch 返回结构化 `RUNTIME_MISMATCH`，且不调用 `thread/resume`。
- Web Open TUI 映射同一 runtime error。

- [x] **Step 2: 验证 RED**

```bash
bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_app_server_client.py tests/test_actor_session.py tests/test_web_management.py -q -k "runtime or attach or ensure_app_server or open_tui"'
```

Expected: constructor/argv/error assertions fail。

- [x] **Step 3: 实现单轨 consumer**

- 删除 App Server 默认 binary。
- `app_server.sh` 明确传递 `--codex-bin`。
- Actor context 增加 validated `CodexRuntime`。
- attach 从 context 构造 argv。
- CLI 增加 `RUNTIME_MISMATCH -> exit 5`。
- Web 将 runtime mismatch 映射为稳定的 409/`RUNTIME_MISMATCH`。

- [x] **Step 4: 验证 GREEN**

运行上述 focused tests，Expected: PASS。

### Task 4: Fake Codex 测试隔离门禁

**Files:**
- Modify: `tests/helpers/fake_codex.py`
- Create: `tests/test_fake_codex.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tools/launcher/actor_session.py`
- Modify: `tests/test_actor_session.py`

- [x] **Step 1: 写 RED tests**

增加两个 subprocess tests：

1. fake `--version` 在无 CODEX_HOME 时返回 `codex-cli fake-test`。
2. fake 非 version 命令在真实样式 shared root 下拒绝运行，在系统临时 shared root 下允许。

增加 attach 环境断言：fake 只能在 descriptor 明确携带的临时 shared root 下运行。

- [x] **Step 2: 验证 RED**

```bash
bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests/test_fake_codex.py -q'
```

Expected: fake 当前不支持 version/隔离 guard。

- [x] **Step 3: 实现 test-only guard**

- `--version` 在读取 CODEX_HOME 前处理。
- 其它命令要求 resolved shared root 与测试 process registry 同时位于系统临时根。
- 拒绝时 stderr 输出稳定错误并 exit 2。
- 所有真正 start 的测试显式使用临时 HOME/shared root 和 fake absolute path。
- attach descriptor 显式传递实例的 `BUDDYSWITCH_SHARED_ROOT`。

- [x] **Step 4: 验证 GREEN**

运行上述 focused tests，Expected: PASS，用户目录样式 shared root 被直接拒绝。

### Task 5: 删除残留并完成 focused 验收

**Files:**
- Review: `tests/test_repo_consistency.py`
- Review: `tests/test_external_control_architecture.py`
- Modify only source files required by failed focused checks

- [x] **Step 1: 写 architecture RED gates**

门禁要求：

- `app_server.py` 无 `codex_bin: str = "codex"`。
- `actor_session.py` 无 constructor `codex_bin`。
- `cli.py` 无 attach-time `BUDDYSWITCH_CODEX_BIN`。
- `env.sh` 无裸 `codex "$@"`。
- App Server launch 的 argv[0] 来自 explicit descriptor。
- fake app-server 有 temporary shared-root guard。

- [x] **Step 2: 运行 residue scans**

```bash
rg -n 'codex_bin: str = "codex"|codex_bin="codex"|codex \"\$@\"|os\.environ\.get\("BUDDYSWITCH_CODEX_BIN", "codex"\)' tools/launcher
rg -n 'codex_runtime' tools/launcher/host_control.py tools/launcher/host_control.sh tools/launcher/actor_session.py tools/launcher/env.sh
```

Expected: 第一条无命中；第二条只命中 owner/writer/consumer 预期位置。

- [x] **Step 3: 运行 focused verification**

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/app_server.sh tools/launcher/host_control.sh

bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_codex_runtime.py \
  tests/test_fake_codex.py \
  tests/test_host_control.py \
  tests/test_actor_session.py \
  tests/test_cli_contract.py \
  tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_instance_record_contains_execution_identity_only \
  tests/test_external_control_architecture.py -q'

bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_app_server_client.py tests/test_web_management.py -q \
  -k "ensure_command_requires_explicit_absolute_codex_runtime or open_tui or map_host_control_failure"'

bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_buddyswitch_launcher.py -q \
  -k "start_with_role_wires_instance_env_and_lifecycle or env_mcp_reconciles_stale_interpreter_path_with_resolved_python or instance_resume_json_restarts_stopped_instance_with_original_thread or instance_resume_active_instance_is_idempotent or attach_preflights_thread_resume_then_invokes_remote_resume_tui or stop_json_marks_instance_inactive_after_cleanup or instance_delete_json_removes_only_target_instance_without_shared_state or run_codex_uses_explicit_runtime_instead_of_path"'

bash -c 'source tools/launcher/env.sh && buddyswitch_env_init && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_repo_consistency.py -q \
  -k "python_runtime_has_one_non_docs_entrypoint or public_launcher_is_minimal_bootstrap_to_python_cli_adapter or public_cli_adapter_delegates_to_concrete_owners_without_repository_writes"'

git diff --check
```

Expected: 全部 PASS，无无关全量测试。

## 7. 验收矩阵

| ID | 验收项 | 证据 |
|---|---|---|
| R01 | 新 Actor 记录 absolute executable/version | launcher integration test |
| R02 | Host Control 是 runtime descriptor 唯一写入者 | host control + architecture tests |
| R03 | App Server 无 PATH runtime resolution | app server tests + residue scan |
| R04 | Attach 使用 record executable | actor session test |
| R05 | PATH/env 改变不影响已有 Actor | actor session/resume tests |
| R06 | 缺失/版本不符在 RPC 前失败 | actor session tests |
| R07 | stop/delete 不依赖 runtime | host control integration tests |
| R08 | fake 支持稳定 `--version` | fake subprocess test |
| R09 | fake 不能运行在真实 shared root | fake isolation test |
| R10 | focused suite 和 shell syntax 全绿 | Task 5 verification |
| R11 | 无旧默认、fallback、双读残留 | architecture gates + rg |

## 8. 注意事项

- 当前污染 Actor `act-pm-f47bfc605028` 不自动迁移；实施后仍通过 stop/delete 清理。
- 不把真实 Codex 模型调用加入 focused suite。真实 attach 兼容性由独立 manual smoke 使用新建真实 Actor 验证。
- fake 只证明 BuddySwitch 编排，不证明 Codex TUI 内部协议完整性。
- runtime version probe 必须有短超时并捕获 stderr，避免 start 无限等待。
- descriptor 写入必须发生在 App Server 启动前并处于现有 runtime lock 内。
- 任何失败只修复新单轨实现，不恢复 PATH fallback 或旧 schema 运行路径。

## 9. 完成定义

任务完成必须同时满足：

1. 本计划文档存在且无占位项。
2. R01-R11 均有自动化或明确 manual smoke 证据。
3. 新 Actor 的 App Server 与 attach TUI 使用同一 runtime descriptor。
4. fake 测试无法修改真实 shared root。
5. 旧 Actor 只允许观察、停止、删除，不允许 lazy migration。
6. focused tests、shell syntax、residue scans、`git diff --check` 全部通过。

## 10. 实施与验收记录

完成日期：2026-07-14。

- Runtime/Host/Actor/CLI/架构组：`61 passed, 186 subtests passed`。
- App Server/Web Open TUI 组：`13 passed, 15 subtests passed`。
- Launcher 端到端组：`8 passed, 28 subtests passed`。
- Python 入口与 public launcher consistency：`3 passed`。
- Shell syntax：`buddyswitch-codex`、`env.sh`、`app_server.sh`、`host_control.sh` 全部通过 `bash -n`。
- Residue scan：无 App Server 默认 Codex、Actor Session runtime override、CLI attach-time runtime override 或裸 `codex "$@"`。
- `git diff --check`：通过。

未执行全量测试；按本计划只运行直接相关的 focused tests。未调用真实模型；真实 Codex TUI 协议仍由新建真实 Actor 的独立 smoke 验证。

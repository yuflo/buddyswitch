# BuddySwitch Phase 3 Implementation Handoff

## 1. 目标与范围（本轮已执行）

本轮实现已经按「前进式迭代，不做兼容层」执行，目标是把运行时切到 task-centric：

- `run` 必须归属 `task`
- `task` 可独立于 `track`
- `track` 串联 `task`（不再直接串 `artifact`）
- `artifact` 作为 run 的核心产物对象，归属 `task`

## 2. 本轮落地内容

### 2.1 Switch 语法与解析

已升级 parser/router/runtime 输入模型，支持：

1. `switch buddy -> track-id: demand`
2. `switch buddy(task-id): demand`
3. `switch buddy: demand`
4. `switch buddy(task-id) -> track-id: demand`

关键点：

- 冒号后字段统一命名为 `demand`（不再使用 `task`）
- 输出 payload 统一携带 `buddy/task_id/track_id/demand`

涉及文件：

- `scripts/parse_switch.py`
- `scripts/codex_router.py`
- `scripts/switch_runtime.py`

### 2.2 Object 模型迁移为 task-first

- 新增 `task` canonical object：
  - `buddyswitch/objects/tasks/<task-id>.json`
- `track` 从 `artifact_ids` 改为 `task_ids`
- `artifact` 从 `track_id` 改为：
  - `task_id`
  - `source_run_id`
- run audit 增加 task-centric receipt 字段：
  - `resolved_task_id`
  - `effective_track_id`
  - `artifact_ids`
  - `switch.demand`

涉及文件：

- `scripts/env_store.py`
- `scripts/switch_runtime.py`
- `scripts/workspace_data.py`
- `framework/console/app.js`

### 2.3 Debug / Cleanup 能力更新

- `env_artifacts.py` 参数更新：
  - `create` 需要 `--task-id`、`--source-run-id`
  - 移除旧 `--track-id` 语义
- 新增 task debug API：
  - `scripts/env_tasks.py`（`list/show/update/archive`）
- cleanup 已切到 task-centric：
  - 支持 task object 清理
  - `agent` 清理时会做 task/track、artifact/task 关系剥离
  - all-storage 会恢复 `buddyswitch/objects/tasks/.gitkeep`

涉及文件：

- `scripts/env_artifacts.py`
- `scripts/env_tasks.py`（新增）
- `scripts/env_cleanup.py`

### 2.4 Manifest/Schema 与计划文档

- manifest 权限扩展包含 `task.*`（各 buddy）
- track-manager schema 已去掉 attach/detach artifact 形态
- Phase 3 详细执行计划文档已新增

涉及文件：

- `buddyswitch/manifest.toml`
- `framework/schemas/pm/track-manager.json`
- `docs/reviews/buddyswitch-control-layer/10-phase-3-task-centric-runtime-plan.md`

## 3. Python 3.9 兼容处理

运行环境是 Python 3.9（无 `tomllib`）。为保证脚本可运行：

- `scripts/env_manifest.py` 增加 `_load_toml` 回退解析
- 支持 root-level key（`schema_version = 1`）
- `scripts/env_cleanup.py` 在无法导入 `env_manifest` 时可回退到最小 manifest 解析（仅提取 `[[buddies]].id`），保证 shell 集成场景可执行

注意：

- 这个最小解析只用于 cleanup 的 buddy 白名单，不承担完整 manifest 语义校验。

## 4. 验证结果（当前工作区）

已通过：

- `PYTHONPYCACHEPREFIX=/tmp/buddyswitch-pycache python3 -m unittest discover -s tests`
- 共 `49` 个测试，全通过。

核心覆盖：

- `tests/test_switch_routing.py`
- `tests/test_switch_runtime.py`
- `tests/test_switch_integration.py`
- `tests/test_cleanup_system.py`
- `tests/test_debug_apis.py`

## 5. 交接后的首要注意点

1. **不要回退到旧模型字段**

- 不要新写 `artifact.track_id`
- 不要新写 `track.artifact_ids`
- switch 输入语义不要再把 `:` 后文本叫 `task`

2. **继续保持 run→task 强绑定**

- persist 路径里 run 必须落到 task（显式 task 或自动新建 task）

3. **处理文档/规范一致性**

- 当前实现已切到新语法与 task-centric；后续若做规范统一，优先检查：
  - `README.md`
  - `AGENTS.md`
  - `framework/docs/*`

4. **cleanup 脚本可独立执行是硬要求**

- shell 集成测试依赖 `scripts/env_cleanup.py` 单文件复制后仍可运行
- 后续改 `env_cleanup.py` 时不要重新引入硬依赖导致 `ModuleNotFoundError`

## 6. 下一位 codex-cli 建议启动顺序

1. 先读：
   - `docs/reviews/buddyswitch-control-layer/10-phase-3-task-centric-runtime-plan.md`
   - 本文件
2. 再看主要改动面：
   - `scripts/switch_runtime.py`
   - `scripts/env_store.py`
   - `scripts/parse_switch.py`
   - `scripts/env_cleanup.py`
3. 本地验证：
   - `PYTHONPYCACHEPREFIX=/tmp/buddyswitch-pycache python3 -m unittest discover -s tests`
4. 若继续推进规范一致性，再统一文档入口（README/AGENTS/framework docs）。

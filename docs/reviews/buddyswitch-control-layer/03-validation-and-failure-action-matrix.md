# 03. 校验与失败动作矩阵

注：本文件中涉及 `track_mode` gate 的条目属于 Phase 2 历史审查语境。当前 Phase 3 runtime 已移除该 gate，并将 `track_mode` 作为 retired field 处理。

## 1. 使用说明

本矩阵只记录控制层里当前可见的显式校验，不评价业务质量。

每条校验都按以下字段记录：

- 位置：脚本 / 函数
- 当前规则
- 当前失败动作
- 保护对象
- 审查判断
- 后续建议

审查判断统一使用：

- `保留`
- `降级`
- `删除候选`
- `重定义`

## 2. `parse_switch.py`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `parse_switch` | 输入为空时报 `E_EMPTY_INPUT` | `reject` | 避免空输入继续流转 | 保留 | 合理的入口硬校验 |
| `parse_switch` | 输入必须以 `switch` 开头 | `reject` | 避免把普通聊天误当 framework directive | 保留 | 这是最小入口识别门槛 |
| `parse_switch` | 用正则抽取 `buddy/task_id/track_id/demand`（容忍 minor spacing 变体） | `reject` | 结构提取 | 重定义 | 应从“文本格式正确”转为“能否稳定抽出结构” |
| `parse_switch` | `buddy` 必须存在于 manifest | `reject` | 防止误路由 | 保留 | 合理的路由级硬校验 |
| `parse_switch` | `demand` 不能为空 | `reject` | 避免进入空需求工作流 | 保留 | 合理的入口硬校验 |

### 结论

- parser 中真正应保留的硬校验只有：`switch` 识别、`buddy` 存在、`demand` 非空。
- 正则层面的“格式感”不应继续扩大职责。

## 3. `codex_router.py`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `route_switch` | 复用 `parse_switch` 失败即返回错误 | `reject` | 路由前置结构正确性 | 保留 | 与 parser 同步即可 |
| `route_switch` | 读取 manifest 并 `require_buddy` | `reject` | manifest 一致性 | 保留 | 但和 parser 存在轻微重复校验 |

### 结论

- router 当前没有明显的过度校验问题。
- 它的主要问题不在“校验太多”，而在“结构暴露不足、职责表达不够清晰”。

## 4. `env_manifest.py`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `_load_skill_package` | `skill.toml` 必填，`SKILL.md` 不能包含 frontmatter，metadata 统一放入 `skill.toml` | `reject` | skill package 结构一致性 | 保留 | 这是当前唯一支持的 skill 加载形态 |
| `load_manifest` | skill 路径必须指向 package 目录而不是单文件 | `reject` | 防止 legacy file-based skill 路径回流 | 保留 | package-only 作为唯一支持路径 |
| `_parse_skill_guidance` | 要求 `Purpose/Use when/.../Gotchas` 全部存在 | `reject` | skill docs 完整性 | 降级 | 更像文档质量门槛，适合 lint 或 review，不必总是 runtime 级强校验 |
| `load_manifest` | `schema_version` 必须为 1 | `reject` | manifest 版本一致性 | 保留 | 合理 |
| `load_manifest` | `env/adapters/skills/buddies` 都必须存在且类型正确 | `reject` | manifest 可消费性 | 保留 | 合理 |
| `load_manifest` | skill/buddy id 不可重复 | `reject` | 路由唯一性 | 保留 | 合理 |
| `load_manifest` | `permissions` 必须形如 `<object>.<action>` | `reject` | 权限元数据结构 | 保留 | 作为 metadata 结构校验合理 |
| `load_manifest` | buddy-skill / skill-buddy 交叉引用必须一致 | `reject` | manifest 拓扑一致性 | 保留 | 合理 |

### 结论

- manifest 层的大部分强校验是合理的，因为它们保护的是“配置是否可被系统消费”。
- 旧的单文件/frontmatter skill runtime contract 已不再是生产接口；当前应以 package 目录 + `skill.toml` 为唯一加载入口。

## 5. `switch_runtime.py resolve`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `_extract_task_hints` | 用户给的 artifact/summary path 必须通过 normalize | `reject` | 路径安全 | 保留 | 路径越界必须阻断 |
| `_resolve_track_context` | 显式引用的 track 不存在时报错 | `reject` | 状态引用安全 | 保留 | 合理 |
| `_resolve_track_context` | （历史）`track_mode=forbidden` gate 已删除 | 无 | 历史语境 | 删除候选 | Phase 3 已移除 |
| `_resolve_track_context` | （历史）`track_mode=required` gate 已删除 | 无 | 历史语境 | 删除候选 | Phase 3 已移除 |
| `_resolve_track_context` | `optional` 且多个 active track 时不自动绑定 | `warn/continue` 风格，通过 `reason` 表达 | 防止误绑定 | 保留 | 是较好的非阻断设计 |
| `_evaluate_runtime_requirements` | 缺少 `required_env` / `required_tools` 会让 skill 变为 rejected | `reject` | 运行环境准备度 | 删除候选 | 如果失败后没有明确补救协议，这更像复杂度而不是必要保护 |
| `resolve_switch` | 没有 eligible skills 时整体失败 | `reject` | 避免 host 运行无效技能 | 保留 | 合理，但 rejected reason 应更清晰地面向 host |
| `resolve_switch` | `implicit_skill_id` 仅在单 skill buddy 下提供 | `continue` | 降低 host 决策复杂度 | 保留 | 合理 |

### 结论

- `track_mode` 相关 gate 已在 Phase 3 退役，当前以显式 task/track 引用与绑定一致性作为最小门槛。
- `required_env` / `required_tools` 已降级为 advisory metadata，不再作为 `resolve` 的阻断 gate。

## 6. `switch_runtime.py persist`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `_read_json_input` | 输入必须是 JSON object | `reject` | persist 输入可消费性 | 保留 | 合理 |
| `_pick_skill_id` | 多 skill buddy 未显式传 `skill_id` 会失败 | `reject` | 避免错误持久化到错误 skill | 保留 | 合理 |
| `persist_switch` | `resolved.ok` 必须为真 | `reject` | 运行链一致性 | 保留 | 合理 |
| `persist_switch` | `skill_id` 必须属于 `eligible_skills` | `reject` | 防误持久化 | 保留 | 合理 |
| `persist_switch` | `skill_id` 必须属于 buddy 声明的 skills | `reject` | 防误持久化 | 保留 | 与上一条有重复，但属于安全冗余 |
| `persist_switch` | result 必须满足 schema | `reject` | 最小结构一致性 | 保留 | 核心硬校验 |
| `persist_switch` | `track-manager` 必须有 summary defaults | `reject` | 输出路径可执行性 | 保留 | 合理 |
| `_persist_track_manager` | `track_operation.action` 必须合法 | `reject` | track state 变更安全 | 保留 | 合理 |
| `_persist_track_manager` | create/update/advance 中的 buddy/status 值必须合法 | `reject` | track state 一致性 | 保留 | 合理 |
| `_persist_track_manager` | attach/detach artifact 操作已退役，不再接受该 action | `reject` | 避免回退旧对象关系 | 保留 | 与 task-centric 模型一致 |
| `_persist_track_manager` | update/advance patch 不能为空 | `reject` | 避免空写 | 保留 | 合理 |
| `_persist_artifact_skill` | 根据 resolved task hints / track context 推导 artifact defaults | `reject` | 持久化可执行性 | 保留 | 合理 |

### 结论

- `persist` 当前总体上仍是“技术门槛”，没有明显滑向业务质量审查。
- 但返回结果里没有显式解释“失败后下一步该做什么”，这会让一些合理的 `reject` 也显得像黑盒。

## 7. `env_store.py`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `require_id` | 所有 id 必须匹配正则 | `reject` | 文件命名、对象唯一键安全 | 保留 | 底层硬约束 |
| `normalize_*_path` | 限制 repo-relative、禁止 `..`、限定根目录和后缀 | `reject` | 路径安全、存储布局稳定 | 保留 | 核心安全约束 |
| `validate_track` | track 各字段类型与值域合法 | `reject` | track 对象结构安全 | 保留 | 核心安全约束 |
| `validate_artifact` | artifact 各字段类型与值域合法 | `reject` | artifact 对象结构安全 | 保留 | 核心安全约束 |
| `create_track` | track 已存在则失败 | `reject` | 唯一性 | 保留 | 合理 |
| `update_track` | patch 字段必须在 allowlist 内 | `reject` | 避免隐式扩展状态 | 保留 | 合理 |
| `advance_track` | 空 patch 不允许 | `reject` | 避免空操作 | 保留 | 合理 |
| `add_artifact_to_task` / `remove_artifact_from_task` | task 必须存在 | `reject` | task-artifact 关系安全 | 保留 | 合理 |
| `create_artifact` | artifact id 不可重复；`task_id` 必须存在且 `artifact.buddy` 必须匹配 task owner | `reject` | artifact state 安全 | 保留 | 合理 |
| `update_artifact` | patch 字段白名单；`task_id` 必须存在且 `artifact.buddy` 必须匹配 task owner | `reject` | artifact state 安全 | 保留 | 合理 |
| `delete_artifact` | artifact 不存在时报错 | `reject` | 删除语义明确性 | 保留 | 合理 |

### 结论

- `env_store` 的大多数校验都属于“最底层状态安全”，应保留。
- 这里不是当前复杂度的主源头。

## 8. `env_tracks.py` / `env_artifacts.py`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `require_permission` | actor 必须具备相应 permission | `reject` | manual/debug API 权限边界 | 保留 | 作为 debug API 的显式门槛合理 |
| `cmd_update` / `cmd_advance` / `cmd_update_artifact` | 空 patch 不允许 | `reject` | 避免空写 | 保留 | 合理 |
| `cleanup-buddy` / `cleanup-all` | 当前无 permission gate | `continue` | 管理脚本便利性 | 重定义 | 属于审查出的边界不一致项，应在 backlog 中明确是否保留为管理员入口 |

### 结论

- manual/debug API 明确使用 `permissions` 进行 actor gate。
- 这与 `switch_runtime` 并未显式 enforce `permissions` 的现状形成了双轨控制模型，需要在后续架构中重新定义。

## 9. `output_schema.py`

| 位置 | 当前规则 | 当前失败动作 | 保护对象 | 审查判断 | 后续建议 |
|---|---|---|---|---|---|
| `normalize_schema_path` | schema 路径必须在 `framework/schemas/**` 下 | `reject` | schema 来源边界 | 保留 | 合理 |
| `load_output_schema` | schema 文件必须存在且为 JSON object | `reject` | persist 可执行性 | 保留 | 合理 |
| `_validate_node` | type / enum / required / properties / additionalProperties / items / minItems | `reject`（收集后统一失败） | result payload 最小结构一致性 | 保留 | 合理 |

### 结论

- `output_schema.py` 属于明确的状态安全工具，不是复杂度主源头。
- 风险点不在“校验多”，而在“schema 是否承担了不该承担的业务约束”，这应由调用方规范决定。

## 10. 总体判断

### 10.1 应保留的硬校验

- 入口识别：是否为 `switch`
- 路由安全：`buddy` 是否存在
- 持久化结构安全：`skill_id`、schema、track/artifact 引用、路径、id
- 对象结构安全：`env_store` 层约束

### 10.2 应优先重新定义的校验

- parser 中的格式感规则
- `required_env` / `required_tools` 的 runtime gate
- `permissions` 在不同入口层中的语义不一致

### 10.3 当前最重要的收敛原则

后续任何新增校验，都必须先回答：

1. 保护对象是什么？
2. 失败后动作是什么？
3. 如果删掉，会不会误路由或写坏状态？

如果三个问题不能回答清楚，就不应进入实现。

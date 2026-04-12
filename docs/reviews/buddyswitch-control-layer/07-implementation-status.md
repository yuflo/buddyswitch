# 07. 当前实施状态

## 1. 目的

这份文档把审查包结论与当前实现状态对应起来，避免后续迭代继续依赖口头共识。

它回答 4 个问题：

- 审查包里哪些项已经落地
- 哪些项被明确降级为 metadata / 提示语义
- 哪些项当前不做
- 当前控制层边界到底是什么

## 2. 已完成

### 2.1 `switch` 入口已收敛为 canonical but tolerant

当前实现已经满足：

- `switch <buddy>: <task>` 是 canonical form
- parser/router 可以容忍 minor CLI spacing variation
- parser/router 返回显式 invocation 结构
- host/session 消费的是结构化结果，而不是再猜字符串细节

对应实现：

- `scripts/parse_switch.py`
- `scripts/codex_router.py`
- `scripts/switch_runtime.py resolve`

### 2.2 `resolve/persist` 已收敛为最小技术 gate

当前实现已经满足：

- `resolve` 不写 BuddySwitch state
- `resolve` 只做成功派发需要的最小确定性判断
- `persist` 只做 skill identity、schema shape、state/reference safety
- `persist` 明确返回 receipt，说明本次写了什么

这意味着 runtime 不再承担：

- 研究质量审查
- 渠道覆盖审查
- 文本质量审查
- “工作做得够不够好”的 review 责任

### 2.3 `required_tools` / `required_env` 已降级为 advisory metadata

当前实现已经满足：

- 这两个字段仍然出现在 skill metadata 中
- 它们不会再导致 `resolve` 拒绝 skill candidate
- runtime 明确把它们作为 host-facing advisory metadata 暴露给 `skill_cards`

### 2.4 `permissions` 语义已拆分

当前实现已经满足：

- `buddy -> skills` 是 runtime 主 routing authority
- `permissions` 是 object-authority metadata
- manual/debug APIs 继续 enforce 对象级 mutation 权限
- runtime 主链路不扩成第二套 permission engine

### 2.5 debug/manual APIs 已补最小状态安全边界

当前实现已经满足：

- debug/manual APIs 保留 actor permission gate
- cleanup/admin helper 继续按管理能力建模
- track/artifact debug APIs 会阻止写入 manifest 中不存在的 buddy 引用
- 对象字段的最终合法性尽量统一下沉到 store 校验

### 2.6 cleanup 已适配 run audit content handling

当前实现已经满足：

- `scripts/cleanup_buddyswitch.sh` 不再停留在旧的 markdown/raw/object 白名单模型
- cleanup 会覆盖 run audit `buddyswitch/content/runs/*.json`
- `--agent` / `--all-agents` / `--all-storage` 都会处理命中范围内的 run content
- cleanup 主逻辑集中在单一 backend，而不是 bash、object helper、store 各维护一套删除规则

## 3. 已明确降级或不做

### 3.1 不做空格/标点洁癖式 parser gate

以下内容不再作为产品层 reject 理由：

- `switch market : task`
- `switch market:task`
- minor CLI whitespace variation

只要 `switch`、`buddy`、`task` 仍能明确提取，就按 `normalize` 处理。

### 3.2 不做 runtime 业务质量 gate

以下内容不属于当前 runtime 主链路职责：

- research quality
- 渠道数量要求
- 结论是否足够深入
- landing page 文案是否足够好
- skill workflow 是否“做得完整”

这些问题应交给：

- skill description
- host prompt / execution guidance
- 人工 review
- 评测用例

### 3.3 不把 `output_schema.py` 扩成 review 层

`output_schema.py` 当前只负责结构一致性：

- type
- required
- enum
- properties
- items
- minItems
- additionalProperties

它不应该承担：

- 业务语义判断
- 流程质量判断
- 结果价值判断

### 3.4 不扩统一 permission system

当前明确不做的事情：

- 让 runtime 主链路再次全面 enforce buddy object permissions
- 给 `permissions` 增加更细颗粒度 DSL
- 构建第三套“看起来很完整”的 control policy

## 4. 当前控制层最终边界

### 4.1 `parse`

负责：

- 识别 `switch`
- 提取 `buddy`
- 提取 `task`
- 做最小 normalize

不负责：

- 工作质量判断
- skill 选择
- 权限审查

### 4.2 `resolve`

负责：

- 读取 buddy/skill metadata
- 计算可选 skill
- 解析 track context
- 提供 defaults / schema / next actions

不负责：

- 写状态
- env/tool readiness gate
- 业务质量 review

### 4.3 `persist`

负责：

- 验证 skill identity
- 验证结构化 payload 与 schema 一致
- 阻止 unsafe state/reference writes
- 写 artifact object canonical content、track object 与 run audit content

不负责：

- 审查工作质量
- 代替 host 做流程判断

### 4.4 manual/debug APIs

负责：

- 显式对象 mutation
- actor permission gate
- 对象引用安全

不负责：

- 智能路由
- buddy 选择
- skill orchestration

## 5. 尚未完成

当前仍未完全闭环的只有两类：

- 失败动作词表尚未在所有控制层说明中完全统一引用
- 审查包与实现状态的对应关系还需要在后续迭代中持续更新

这两项都不应推动新的 runtime gate 增长。

兼容包袱清理与二阶段备忘见 [08-compatibility-debt-cleanup-plan.md](./08-compatibility-debt-cleanup-plan.md)。

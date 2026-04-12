# 05. 测试与规范缺口审查

## 1. 本文目标

本文检查三者是否一致：

- 文档怎么说
- 测试怎么测
- 系统真实怎么做

如果这三者长期不一致，团队会不断在“想象中的系统”和“实际系统”之间切换，导致控制层复杂度持续上升。

注：本文含 Phase 2 审查期术语（`switch <buddy>: <task>`）。当前 Phase 3 canonical 语法为 `switch <buddy>(<task-id>) -> <track-id>: <demand>`（支持简化形态）。

## 2. 当前测试覆盖现状

### 2.1 `tests/test_switch_runtime.py`

当前重点覆盖：

- skill runtime metadata 的必填项与 guidance 读取
- `resolve` 的单 skill / 多 skill 基本行为
- `persist` 的：
  - invalid skill id 拒绝
  - schema invalid 拒绝
  - artifact skill 持久化成功
  - track-manager 创建 track 成功

### 2.2 `tests/test_repo_consistency.py`

当前重点覆盖：

- 仓库中不再启用旧 `.agents/skills` 路径
- 文本中没有重新激活 legacy native skill 机制

### 2.3 当前未明显覆盖的部分

- `parse_switch.py` 没有独立测试文件
- `env_store.py` 没有系统性单测
- `env_tracks.py` / `env_artifacts.py` 的 permission gate 没有单测
- `output_schema.py` 没有独立单测
- `cleanup` 入口没有策略性测试

## 3. 当前规范表达现状

### 3.1 现行规范来源

当前控制层规范主要散落在：

- `README.md`
- `AGENTS.md`
- `framework/docs/switch-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/track-registry.md`

### 3.2 历史文档心智影响已移除

旧的 `docs/buddyswitch/` 产品规划包已移除，当前控制层以 `framework/docs/`、`README.md`、`AGENTS.md` 与本审查包为准。

## 4. 主要缺口

### 4.1 文档对“strict syntax”的强调强于系统所需

当前规范文档在早期版本多处强调：

- `switch <buddy>: <task>` 的 canonical form（旧术语）
- “Parse with strict syntax only”
- malformed syntax 要求用户重发

但当前 parser 的实际行为并不是“极严格格式器”。
这说明当前文档语言偏强，而系统真实能力与产品期望之间没有完全校准。

### 4.2 文档对 `permissions / authority` 的表达强于 runtime 主链路

文档中多次提到：

- object permissions
- lightweight authority consistency
- `pm` 管理 track lifecycle

但实际主链路中，最实在的 enforce 是：

- manifest 中的 `buddy -> skills`
- `persist` 的 skill + schema gate

`permissions` 本身主要在 manual/debug APIs 中被显式使用。

这意味着：

- 文档叙事更像统一 authority 模型
- 真实实现更像多层局部约束

### 4.3 测试没有覆盖“文档中最强的叙事点”

例如：

- strict syntax
- permissions 统一生效
- authority/context consistency 的具体边界
- `required_env` / `required_tools` 的行为预期

这些地方要么测试没有覆盖，要么测试只覆盖了局部。

### 4.4 一些 metadata 字段被测试保护，但其产品意义并不清晰

例如：

- `required_tools`
- `required_env`

当前测试会校验这些字段可以被正确读取。
但并没有形成一套稳定的“如果它们缺失/失败，系统应该怎么动作”的完整规范。

这说明：

- 数据结构已存在
- 但其运行时语义和产品边界仍然模糊

## 5. 三向映射

| 主题 | 文档叙事 | 当前实现 | 当前测试 | 结论 |
|---|---|---|---|---|
| `switch` 入口 | 强调 canonical/strict syntax | parser 通过正则做文本提取并校验 buddy/task | 未直接独立覆盖 parser | 需要统一“canonical form”和“强阻断”之间的边界 |
| skill 选择 | host 选择 skill；单 skill 可 implicit | `resolve` 返回 `eligible_skills` 与 `implicit_skill_id` | 已覆盖 | 一致性较好 |
| persist 边界 | 文档说是 lightweight technical gate | 实现主要做 skill + schema + state safety | 已部分覆盖 | 总体一致，但失败动作说明不足 |
| permissions/authority | 文档表达较强 | 主链路未系统 enforce；debug APIs enforce | 无系统性测试 | 存在明显理解差 |
| output schema | 文档强调结构化结果 | 实现通过 `output_schema.py` 强校验 | 已通过 `persist` 间接覆盖 | 一致性较好 |
| `required_env/tools` | 文档和 metadata 可表达 | resolve 会用它们拒绝 skill | 仅 metadata 读取被测试 | 运行时意义需要重新定义 |

## 6. 审查结论

### 6.1 当前最需要补的，不是更多测试，而是更清楚的规范边界

在文档没有先讲清以下问题前，继续补测试容易把复杂度固化：

- `switch` 到底是 canonical protocol 还是硬语法约束
- `permissions` 到底是 metadata 还是统一权限系统
- `required_env/tools` 到底是 warning 还是 reject

### 6.2 测试应服务于收敛后的边界，而不是放大当前模糊区

后续若进入实现阶段，优先新增的测试应围绕：

- 最小入口识别边界
- 最小状态安全边界
- failure action 是否明确

而不是先为模糊规则补更多回归测试。

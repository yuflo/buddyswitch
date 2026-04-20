# Design Buddy Legacy Skill Cleanup Review

## 背景

这份 memo 记录本轮对 `design` buddy 清理状态的客观检查结论。

目标边界不是删除 `design` buddy 本身，而是：

- 清除旧的 `design` skill 体系
- 保留 `design` 作为 BuddySwitch 中的角色壳
- 为后续新版 `design` 重构留出干净起点

## 本轮检查范围

本次 review 只看下面几类内容：

- runtime 与 manifest
- 活的 skill 文档与输入输出约束
- 测试与 eval 基线
- 对象与 run 中是否还有真实 `design` 调度残留

本次不处理历史 whiteboard、历史计划文档、历史 memo 的全面清扫。

## 当前状态结论

### 1. `design` buddy 已恢复为保留壳

当前 `design` 已重新存在于 `buddyswitch/manifest.toml` 中，但暂时没有注册任何 skill：

```text
id = "design"
skills = []
```

这表示：

- `design` 仍然是一个合法 buddy id
- 旧 skill 体系不会继续参与路由
- 新版 design 重构时可以直接在这个壳上接入

### 2. 旧 design skill 体系本体已清除

以下旧体系已删除：

- `buddyswitch/skills/design/**`
- `framework/contracts/design.md`
- `framework/templates/design-spec.md`
- `framework/schemas/design/**`

这意味着旧的：

- `product-design-spec`
- `experience-shaping`
- `activation-and-first-value`
- `initiative-and-intervention`
- `execution-boundaries`
- `memory-and-context`
- `conversation-and-clarity`
- `recovery-and-escalation`
- `design-critique`

都已退出当前运行面。

### 3. runtime 已允许“buddy 存在但暂无 skill”

为了支持 `design` 作为重构前的空壳，manifest 解析和 runtime resolve 已做最小调整：

- buddy 的 `skills` 现在可以为空列表
- 当用户执行 `switch design: ...` 时，系统会明确返回：

```text
Buddy 'design' currently has no registered skills.
```

这不是异常脏状态，而是当前刻意允许的过渡状态。

### 4. `dev` 不再硬依赖旧 `design-spec`

`implement-task` 之前把 `design-spec` 作为输入槽位的一部分。

当前已调整为：

- `input_slots = ["prd", "task"]`

这表示旧 design-spec handoff 已不再是 runtime 前提。

### 5. 旧 design eval case 已退出基线

原来直接要求 `switch design` 跑旧 `design-spec` 的 eval case 已删除，相关 rubric 也同步移除。

这使当前测试基线不再依赖已经被清掉的旧 design 体系。

## 额外核查结果

### 1. 对象层没有真实 design 调度残留

本轮检查了：

- `buddyswitch/objects/**`
- `buddyswitch/content/runs/**`

没有发现现存对象仍把：

- `current_buddy = "design"`
- `next_buddy = "design"`
- `buddy = "design"`

作为真实执行链路的一部分。

这意味着当前不会出现已有 track/task 被空壳 `design` 卡死的情况。

### 2. 活的 skill 文档已去掉直接指向 `switch design` 的示例

本轮也清掉了当前仍会误导用户去执行 `switch design` 的活文档示例，避免在 design 尚未重构完成前产生错误预期。

## 当前状态的客观评估

### 优点

- 旧 design skill 体系已经退出运行面
- `design` buddy 角色仍保留
- runtime、测试、eval 基线已经和这个新边界对齐
- 后续可以直接围绕 `.sandbox/design/ + guided intake + visible prototype` 接新方案

### 当前仍成立的限制

- `design` 目前不可执行
- `switch design: ...` 会明确失败
- 当前系统只是保留了 `design` 的壳，还没有接入任何新能力

这意味着当前状态更准确地说是：

```text
design buddy preserved
legacy design skills retired
new design runtime not installed yet
```

## 建议的后续原则

进入新版 `design` 重构时，建议继续保持下面这个边界：

1. 不再恢复旧 design-spec / activation-spec 这一类文档型 skill。
2. 新版 design 应围绕可见原型回路，而不是先围绕设计文档。
3. `design` sandbox 应放在 repo-level `.sandbox/design/`。
4. artifact 继续承担 buddy handoff，而不是让 sandbox 变成 canonical state。

## 验证记录

本轮最后执行了：

```bash
python3 -m unittest tests.test_env_manifest_v2 tests.test_switch_runtime tests.test_artifact_selection tests.test_repo_consistency
```

结果：

```text
Ran 102 tests ... OK
```

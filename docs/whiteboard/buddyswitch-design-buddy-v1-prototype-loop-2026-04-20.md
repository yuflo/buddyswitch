# BuddySwitch Design Buddy V1 Prototype Loop

## 版本信息

- Document: BuddySwitch Design Buddy V1 Prototype Loop
- Date: 2026-04-20
- Status: Draft
- Scope: `design` buddy 重构方向讨论，不含具体 skill/schema 实现

## 1. 文档目的

本文档记录本轮讨论已经收敛的核心结论，方便后续重启 Codex CLI 后继续推进。

本文档聚焦回答下面几个问题：

1. 新版 `design` buddy 的主目标是什么。
2. 它和旧版 design skill 体系的根本差异是什么。
3. 用户侧交互回路应该长什么样。
4. BuddySwitch 的 sandbox / artifact / buddy handoff 应如何分工。
5. v1 原型默认应该收敛成什么形态。

本文档不是最终实现方案，也不是 skill 清单本身。

## 2. 当前共识

### 2.1 旧 design 体系已经撤场

旧的 `design` skill 包已经删除，相关 manifest 注册、旧 contract/schema/template 路径和直接绑定这套体系的测试引用也已同步清理。

当前仓库处于：

```text
旧 design skill 系统已下线
等待基于新目标重建
```

### 2.2 新 design buddy 的目标不是“写设计文档”

新的 `design` buddy 不应再以“写一份结构化设计文档”为中心。

它更应该是：

```text
用少量引导问题，把用户的非专业表达收敛成可见的 UI / UX 原型，
并把结果打包成可供其他 buddies 消费的 artifact。
```

也就是说：

- 用户侧主界面是可视化原型
- artifact 是 buddy 协作和 handoff 的媒介
- design buddy 自身是一个控制层，而不是单纯的文档生成器

## 3. 用户问题模型

本轮讨论确认了一个非常关键的前提：

BuddySwitch 面向的很多用户不是专业 designer。

他们更常见的表达不是：

- “请给我一个 recovery-and-escalation spec”
- “请定义 information architecture”
- “请做一个 activation-spec”

而是：

- “这个整体有点乱”
- “我想做一个这样的产品”
- “用户会不会不知道下一步去哪”
- “这个流程感觉不顺”
- “帮我把这个界面想清楚”

所以新版 `design` buddy 的目标不是让用户学习设计术语，而是让系统把这些自然语言表达翻译成可迭代的原型收敛过程。

## 4. 目标交互回路

本轮已经明确希望贴近的体验，不是重型设计工具，而是更接近：

- Claude 的 “针对性技能 + 视觉迭代”
- Stitch 的 “更看重整体结构感和页面关系，而不是先做一个完整 demo”

因此，期望的核心回路是：

```text
非专业表达
-> 少量引导式收敛
-> 产出可视化原型
-> 用户对看到的内容反馈
-> 修正原型
-> 再次反馈
-> 形成 buddy handoff artifact
```

用户不需要先给出专业设计决策。

用户主要通过：

- 对整体结构的判断
- 对页面关系的反馈
- 对“我在哪里 / 能去哪里 / 下一步是什么”的感受

来推进收敛。

## 5. V1 必须同时成立的四个条件

本轮已经确认，v1 不是只做其中一个点，而是这四件事必须同时成立：

### 5.1 Managed Sandbox

设计原型必须运行在一个独立、受管理的 sandbox 中。

原因：

- 高频试错和覆盖是常态
- 不应污染 `projects/app`
- 不应把原型直接等同于正式产品代码
- 不能完全依赖 `/tmp` 这类难管理的临时目录

当前已确认的 v1 方向是：

```text
使用 repo-level 的 `.sandbox/design/` 作为 design buddy 的原型工作区
```

### 5.2 Artifact Handoff

虽然用户主要面对的是原型，但 buddies 之间的协作仍然必须通过 artifact 进行。

artifact 负责承载：

- 本轮原型摘要
- 当前页面结构和主流程
- 已收敛的关键决策
- 反馈结论
- sandbox 预览入口或引用
- 给 `pm / dev / test` 的交接信息

### 5.3 Guided Intake

默认入口不应是“用户先说清楚完整设计需求”。

更合理的默认是：

- 用户先自然语言表达
- 系统补 `1-3` 个高杠杆问题
- 问题只用产品语言，不用内部 skill 语言

### 5.4 Visible Iteration

用户反馈的对象不应主要是文档，而应主要是可见原型。

用户说的应当是：

- “这里入口不对”
- “我不知道自己现在在哪”
- “这一页不应该先出现”
- “这两个层级混在一起了”

而不是：

- “请调整某个 spec section”

## 6. 原型重心：先保信息架构，不先做高保真 demo

本轮一个关键判断是：

对于非 designer 用户来说，直接从“单个流程原型”切入，可能会让用户感知到割裂和局部化。

用户通常感知的是：

```text
这个整体像不像一个合理的产品结构
```

而不是：

```text
这个单一流程是否被专业地建模
```

因此，v1 更应该优先保证：

- 信息架构
- 页面关系
- 主流程承接

而不是：

- 高保真视觉 polish
- 非常像真实产品的 demo 感

换句话说，v1 的价值感应更接近 Stitch：

```text
帮助用户快速看懂整体结构和去向
```

而不是：

```text
先做一个看起来很完整的 demo 产品
```

## 7. V1 默认原型形态

本轮已经明确选择：

```text
页面地图 + 关键页面 + 少量关键跳转
```

也就是前面讨论里的 `B` 方案。

### 7.1 为什么不是完全自由画布

如果做一个真正 Stitch 式自由画布，成本会明显更高：

- 要管理空间关系
- 要支持局部编辑而不破坏全局
- 要引入更重的状态模型
- 很容易把 BuddySwitch 拖向“小型设计工具”

这不符合 v1 的轻量目标。

### 7.2 为什么也不是只做单页原型

如果只做单页或单组件：

- 用户可以快速反馈视觉和局部交互
- 但很难感知整体结构
- 不足以支撑“我在哪 / 我能去哪 / 主流程是什么”的判断

### 7.3 选 B 的含义

`B` 是一个中间但非常实用的选择：

- 能表现整体结构
- 能承载一个主流程
- 不要求做完整 demo
- 用户认知负担仍然可控

因此 v1 默认原型应当是：

- 有页面地图
- 有若干关键页面
- 有少量关键跳转关系
- 强化整体结构感
- 降低对高保真和完整可操作性的要求

## 8. 默认入口方式

本轮已经确认，v1 默认入口是：

```text
自然语言表达
-> 系统补 1-3 个引导问题
-> 开始原型收敛
```

也就是前面讨论里的 `B`。

### 8.1 为什么不是完全自由输入后立即生成

完全不做 intake，虽然速度快，但很容易让第一次原型发散或方向偏掉。

### 8.2 为什么不是先给技能菜单或复杂选项

因为这会把系统内部结构暴露给用户，增加学习负担。

### 8.3 所以 v1 intake 的要求是

- 问题数少：`1-3`
- 只问高杠杆问题
- 只用产品语言
- 够用就执行，不把 intake 做成仪式

## 9. BuddySwitch 内部应如何理解新 design buddy

内部上，新版 `design` buddy 更像这几个阶段能力的组合，而不是一个总 design prompt：

- `intake / framing`
- `ia / flow shaping`
- `prototype composition`
- `feedback-based revision`
- `handoff packaging`

这些底层能力是否拆成多少个 skill，后续还需要单独设计。

但用户侧不应直接感知这些 skill。

用户始终面对的是一个连续的对话式设计收敛过程。

## 10. Sandbox 与预览边界

本轮已经确认：

```text
design buddy 需要自己的受管理原型工作区
```

不应默认写入：

- `projects/app`
- 正式产品代码目录

### 10.1 为什么不是 `/tmp`

虽然设计原型天然是临时性的，但完全放到 `/tmp` 不利于管理：

- 生命周期不清晰
- 调试和排查不方便
- 不利于后续形成统一清理策略
- 容易让“临时”变成“不可追踪”

因此 v1 更合理的方式是：

```text
repo-level `.sandbox/design/`
```

也就是：

- 仍然是 sandbox
- 仍然是非 canonical 内容
- 但放在仓库受管目录下
- 方便后续约束、清理和演进

### 10.2 更合适的边界是

- sandbox：承载临时网页原型
- preview：作为 sandbox 的内置能力存在
- artifact：承载可传递结论
- `projects/app`：只有在进入实现阶段时，才由 `dev` buddy 消化 artifact 并落正式代码

这符合 BuddySwitch 的“前进式开发”原则：

- 快速验证
- 快速反馈
- 快速迭代
- 不把实验性产物过早混入正式工程

### 10.3 为什么 v1 不单独保留 `visual companion`

本轮后期已经进一步收敛：

```text
v1 不单独保留 `visual companion` 这一层概念
```

原因不是它做不到，而是没必要先把概念做重。

真正需要的是：

- design buddy 的引导式收敛
- sandbox 内的原型组织
- artifact handoff
- 一个足够轻的预览能力

也就是说，v1 更合理的理解应当是：

```text
preview 只是 `.sandbox/design/` 内的一项薄能力
而不是一套单独的产品层或工作区概念
```

此前查看 `/Users/chen/Dev/superpowers` 中的 visual companion 实现后，也进一步确认了一点：

- 这类预览层技术实现本身不重
- 主要是本地服务、HTML 展示、自动刷新、少量事件收集
- 后续如果需要，可以借鉴其“薄预览壳”思路
- 但当前阶段没有必要专门“学习或复制”它

因此，新的优先级很清楚：

```text
先把 design loop 和 sandbox 跑顺
预览只做够用的最小能力
```

## 11. 当前最稳定的一句话定义

到目前为止，可以把新版 `design` buddy 的 v1 方向总结成：

```text
新版 design buddy 是一个对话式原型收敛控制层：
它通过少量 guided intake，把非专业表达转成可见的结构化 UI / UX 原型，
在 `.sandbox/design/` 中迭代，并通过 artifact 把已收敛结果交给其他 buddies。
```

## 12. 下一步建议

如果后续继续推进，实现层面最应该先讨论的是下面三个问题：

1. 底层 design skills 先拆成几个，粗粒度还是阶段型。
2. `.sandbox/design/` 的最小目录结构是什么，以及 preview 入口如何附着其上。
3. v1 artifact 需要哪些字段，才能既服务 buddy handoff，又不过度变成“设计文档系统”。

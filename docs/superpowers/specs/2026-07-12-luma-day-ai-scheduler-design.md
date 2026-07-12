# Luma Day AI 日程管理 MVP 设计规格

日期：2026-07-12
状态：待用户评审
角色内路径：`projects/app/`
权威产品源：`/Users/chen/.codex-buddyswitch/project/workspace/projects/app`

当前框架 worktree 中的 `projects/app/README.md` 仅说明挂载约定，不是本产品的写入目标。Dev/Test 角色必须在各自工作区的 `projects/app` 中操作；该路径映射到上述权威产品源。

## 1. 目标

为日程密集的个人知识工作者提供一个简洁、可信的 AI 日程管理体验：用户用一句话描述待办，系统提取可编辑约束，结合单日忙碌信息生成一个可解释的时间块建议，用户确认后加入应用内 TodayPlan。

产品不替用户决定优先级，不后台自动重排，不写入外部日历。第一版用确定性、可测试的本地规划器实现真实交互闭环，并把能力边界在产品和 landing page 中说清楚。

首个成功时刻：用户不需要自己寻找空档，就能理解并确认一个满足约束的建议时间块。

## 2. 研究与决策记录

BuddySwitch 已通过 8766 Team room 完成独立研究与交叉复核：

- Market Track：`track-ai-calendar-mvp-20260712`
- Market Artifact：`art-894027cd15`
- PM Track：`track-ai-calendar-mvp-framing-20260712`
- PM 初版 Artifact：`art-69d6c15ba5`
- PM 交叉复核 Artifact：`art-ec86e50c95`
- Design 方向对比 Artifact：`art-5f4dae2c58`
- Design v2 对齐 Artifact：`art-b3e087d53c`

竞品对照结论：

| 产品/路线 | 可借鉴 | 不采用 |
| --- | --- | --- |
| Reclaim / Motion | 自动发现时间、减少手动排程 | 多规则、后台重排和信任成本 |
| Sunsama | 主动规划、围绕“今天”做决策 | 每天复杂的规划仪式 |
| Akiflow | 自然语言快速捕获、任务与日历并置 | 过载时仍需大量手动处理 |
| Notion Calendar | 轻量、熟悉、直接编辑 | 仅做传统日历，缺少可解释建议 |

产品路线比较：

| 路线 | 核心价值 | 主要问题 | 决策 |
| --- | --- | --- | --- |
| A 对话收件箱 | 快速捕获意图 | 只解决“记下来”，不解决“今天何时做” | 不选 |
| B 可解释的提议—确认 | 在真实忙碌信息中给出一个可理解的时间块 | 需要清楚显示约束、理由和数据新鲜度 | 选择并收紧 |
| C 自主排程代理 | 自动化感最强 | 优先级、估时、集成和错误成本过高 | 暂缓 |

最终路线：Today Decision View 中的一个可解释下一步时间块。

独立视觉探索结论：

| 方向 | 优势 | 主要风险 | 决策 |
| --- | --- | --- | --- |
| 静谧专注画布 | 安静、任务和时间轴扫描性好 | 理由与确认边界容易成为次要信息 | 保留为整体气质 |
| 理由优先计划台 | 约束、理由和用户控制最清晰，实现复杂度最低 | 需要避免变成表单或审计面板 | 选择为决策面板结构 |
| 动势时间流 | 时间变化和 AI 感强、差异化高 | 动效复杂，易削弱稳定感与无障碍 | 不选 |

最终视觉组合：使用 Today Focus 的安静三栏外壳，右栏采用“理由优先计划台”的信息顺序和控制边界。

## 3. 用户与核心场景

主要用户：会议、深度工作和零散待办交织的个人知识工作者。

核心场景：

1. 用户看到今天的会议、空档和未安排任务。
2. 用户输入“下午 4 点前安排 90 分钟准备发布 brief”。
3. 系统提取时长、截止时间、时间窗和可移动性；缺失项显式标记。
4. 用户确认或修改约束。
5. 系统生成一个建议时间块，附最多三条可追溯理由。
6. 用户确认、换时段、编辑约束或跳过。
7. 确认仅写入应用内 TodayPlan，并提供撤销。

## 4. 产品范围

### 包含

- 单日 Today Decision View。
- 一个本地示例日历的只读忙碌信息。
- 未安排任务列表。
- 中英文自然语言中的基础时长、截止/时间窗解析。
- 约束 chips，可直接编辑。
- 确定性空档计算和排序。
- 一个建议时间块及最多三条理由。
- 确认、换时段、编辑、跳过和撤销。
- 应用内 TodayPlan 与 `localStorage` 持久化。
- 完整空态、加载态、过期态、缺字段、无时段、错误、成功和撤销状态。
- 响应式桌面和移动端布局。
- 独立 landing page，CTA 进入可用产品演示。

### 不包含

- 真实 Google/Apple/Outlook OAuth 或双向同步。
- 外部日历写入。
- 后台持续重排。
- AI 自主决定优先级或估时。
- 多人协调、团队资源分配、项目管理、文档或会议转录。
- 付费、账户、服务器数据库或生产级隐私合规。

## 5. 信息架构

### Landing page：`index.html`

1. 顶部导航：品牌、工作方式、产品预览、FAQ、主 CTA。
2. Hero：核心承诺、反承诺、CTA、真实产品 mockup。
3. Trust strip：只读忙碌信息、确认后生效、不后台重排。
4. 三步流程：说出意图、理解建议、确认今天。
5. 产品细节：任务、时间轴、理由卡的组合。
6. 差异化：与全自动排程和纯聊天的对照。
7. 场景卡：深度工作、临时变更、碎片任务。
8. FAQ：数据边界、AI 边界、同步方式、演示状态。
9. 底部 CTA：进入本地演示。

核心文案：

- 主标题：“把一句安排，变成你看得懂、愿意确认的日程。”
- 补充：“Luma Day 读取今天的忙碌信息，为下一件重要任务找到一个合理时间块。它解释原因，等你确认，不会偷偷重排整周。”
- 主 CTA：“用一句话生成我的日程方案”
- 次 CTA：“看看它如何决定”

### 产品：`app.html`

桌面三栏：

- 左栏 Tasks：快速录入、未安排任务、约束摘要。
- 中栏 Today：单日时间轴、会议、空档、TodayPlan。
- 右栏 Suggestion：唯一建议、理由、数据时间戳和决策操作。

移动端：

- 顶部 Today 概览。
- 时间轴为主内容。
- Tasks 收拢为可展开列表。
- Suggestion 作为底部固定决策面板；展开后显示理由和约束。

## 6. 视觉设计

选择方向：Today Focus 外壳 + 理由优先计划台决策面板。

视觉原则：

- 安静、编辑感、非 SaaS 仪表盘堆叠。
- 使用暖纸色背景、深墨色文字、森林绿主色和酸橙色确认强调。
- AI 不使用魔法渐变或机器人拟人；建议通过结构、理由和数据状态建立信任。
- 页面只允许一个高强调主动作。
- 时间轴与任务内容优先于装饰。

Design tokens：

```css
:root {
  --paper: #f4f1e8;
  --surface: #fffdfa;
  --surface-muted: #ece9df;
  --ink: #1c2421;
  --ink-muted: #686c66;
  --forest: #164c43;
  --forest-soft: #dcebe4;
  --signal: #d8ff98;
  --clay: #c97b63;
  --line: #d8d4ca;
  --danger: #b4493f;
  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 24px;
  --shadow-soft: 0 18px 52px rgba(31, 39, 35, 0.08);
  --font-sans: "Avenir Next", "Segoe UI", sans-serif;
  --font-serif: Georgia, "Times New Roman", serif;
}
```

排版：

- Landing hero 使用 serif 标题制造编辑感。
- 产品 UI 使用 sans-serif 提高扫描性。
- 大标题紧凑，正文行高 1.5–1.65。
- 数字时间使用 tabular numerals。

动效：

- 150–220ms 的透明度、位移和尺寸过渡。
- 生成建议时使用三段骨架进度，不使用无限旋转等待。
- 确认后时间块从建议卡映射到时间轴，并立即显示撤销 toast。
- 尊重 `prefers-reduced-motion`。

## 7. 状态模型与数据流

### 数据模型

```text
BusyBlock
  id, title, startMinute, endMinute, source, updatedAt

Task
  id, title, durationMinutes, deadlineMinute?, windowStart?,
  windowEnd?, movable, status

PlanSuggestion
  id, taskId, startMinute, endMinute, constraintSnapshot,
  reasons[], confidence, sourceUpdatedAt, status

TodayPlanItem
  id, taskId, startMinute, endMinute, createdFromSuggestionId

AppState
  calendarStatus, busyBlocks[], tasks[], activeTaskId,
  suggestion?, todayPlan[], lastAction?
```

### 数据流

```text
一句话输入
  -> parseIntent(text)
  -> 约束草稿
  -> 用户确认/编辑
  -> findCandidateSlots(task, busyBlocks, todayPlan)
  -> rankCandidates(candidates, task)
  -> explainCandidate(bestCandidate, constraints)
  -> PlanSuggestion
  -> 用户确认
  -> TodayPlanItem + localStorage
  -> 撤销可恢复上一步
```

### 排程规则

1. 以 15 分钟为最小粒度。
2. 默认工作时间 09:00–18:00。
3. 忙碌时段、已确认 TodayPlan 和截止时间是硬约束。
4. 时间偏好、连续时长、会议前后缓冲是软约束。
5. 只返回排名第一的候选，同时保留“换时段”所需的后续候选。
6. 无候选时不伪造建议，明确说明冲突约束并提供可修改项。
7. 忙碌数据过期时禁止声称空闲，先要求刷新示例日历。

## 8. 技术架构

采用无构建工具的静态 Web 应用：

```text
projects/app/
  index.html                 landing page
  app.html                   product app
  assets/
    styles.css               shared tokens and layouts
  src/
    planner.js               parser, slot search, ranking, explanations
    state.js                 state transitions and localStorage
    app.js                   DOM rendering and interactions
    sample-data.js           deterministic demo calendar/tasks
  tests/
    planner.test.mjs         rule and boundary tests
    state.test.mjs           state transition and persistence tests
  README.md                  run and verification commands
```

运行方式：

```bash
# 在 BuddySwitch 角色工作区中
python3 -m http.server 4173 --directory projects/app

# 从 fea-webui 框架 worktree 验收共享产品源时
python3 -m http.server 4173 \
  --directory /Users/chen/.codex-buddyswitch/project/workspace/projects/app
```

技术取舍：

- 不引入框架和打包器，降低启动成本和依赖风险。
- 规划器和状态模块为纯 ESM，可用 Node 内置测试运行。
- DOM 渲染保持小组件边界，但不创建通用组件系统。
- 所有演示数据本地生成，不请求外部服务。

## 9. 组件边界

### Landing

- `SiteHeader`：导航和 CTA。
- `Hero`：价值承诺、边界说明、产品 mockup。
- `TrustStrip`：三条信任声明。
- `HowItWorks`：三步流程。
- `ProductStory`：Today Focus 结构。
- `Comparison`：可解释建议 vs 全自动 vs 纯聊天。
- `FAQ`：能力和数据边界。
- `FinalCTA`：进入 `app.html`。

### Product

- `AppHeader`：日期、示例日历状态、返回 landing。
- `TaskInbox`：录入、任务选择、约束 chips。
- `Timeline`：BusyBlock、空档、TodayPlanItem。
- `SuggestionPanel`：生成状态、建议、理由、操作。
- `ConstraintEditor`：时长、截止/时间窗、可移动性。
- `Toast`：确认反馈和撤销。

每个组件仅通过 `AppState` 和显式事件协作，不直接读取其他组件 DOM。

## 10. 错误与关键状态

| 状态 | 用户界面行为 |
| --- | --- |
| 未连接 | 说明本地演示，提供“使用示例日历”按钮 |
| 加载中 | 三段可见进度：理解约束、检查空档、准备理由 |
| 数据过期 | 显示最后更新时间，阻止生成并提供刷新 |
| 字段缺失 | 高亮缺失约束，保留原始输入，不静默猜测 |
| 无候选 | 列出冲突约束，提供修改时长/截止/时间窗 |
| 生成失败 | 保留任务和约束，允许重试，不清空输入 |
| 建议就绪 | 显示一个时间块、最多三条理由和数据时间戳 |
| 确认成功 | 立即进入 TodayPlan 和时间轴，显示撤销 |
| 撤销成功 | 移除 TodayPlanItem，恢复建议可决策状态 |

## 11. 无障碍与响应式

- 语义化 landmark、标题层级、label 和按钮文本。
- 所有操作可键盘完成，焦点环清晰。
- 色彩对比达到 WCAG AA；状态不只依赖颜色。
- `aria-live` 宣告生成、确认和撤销结果。
- 触控目标至少 44px。
- 320px 宽度下无水平滚动；建议面板不遮挡时间轴关键内容。

## 12. 测试与验收

### 自动化

规划器测试：

1. 解析 90 分钟、截止时间和时间偏好。
2. 不与 BusyBlock 或 TodayPlan 重叠。
3. 遵守工作时间和截止时间。
4. 无候选时返回明确冲突，不返回虚假建议。
5. 候选排序稳定、理由与实际约束一致。
6. 换时段返回不同的有效候选。

状态测试：

1. 未连接不能生成建议。
2. 过期数据阻止生成。
3. 确认产生 TodayPlanItem 并持久化。
4. 撤销恢复上一状态并更新持久化。
5. 重新载入恢复 tasks 和 TodayPlan。

静态检查：

- `node --test projects/app/tests/*.test.mjs`
- `node --check` 检查所有 JavaScript。
- HTML 链接、必需 landmark、表单 label 和 CTA 合约检查。
- `git diff --check`。

### 浏览器验收

必须通过真实浏览器验证：

1. Landing hero CTA 进入产品。
2. 使用示例日历后看到忙碌时段、任务和空档。
3. 输入“下午 4 点前安排 90 分钟准备发布 brief”。
4. 看到正确约束和一个有效建议。
5. 理由可追溯到时长、截止和相邻会议。
6. 确认后时间块立即出现在 TodayPlan 和时间轴。
7. 撤销后完整恢复。
8. 无时段、过期数据和字段缺失均有清晰恢复路径。
9. 桌面与移动视图均无溢出，主要操作清晰。
10. 控制台无未处理错误。

## 13. Marketing 验收

- Landing page 不声称真实外部日历同步或后台 AI 代理。
- 首屏在一个视口内同时回答“做什么、为什么可信、下一步是什么”。
- 产品 mockup 与实际 app 保持同一结构和视觉 tokens。
- CTA 文案具体，不使用泛化“Get started”。
- FAQ 明确这是本地演示、数据保存在浏览器、外部日历不被修改。

## 14. 完成定义

- Product 和 landing page 均可从静态服务器运行。
- 核心排程与状态测试通过。
- 真实浏览器完成主路径、恢复路径、桌面和移动验收。
- 比较记录、设计选择和技术边界可从本规格及 BuddySwitch Track/Artifact 回顾。
- 产品与营销表述一致，不夸大 AI 或同步能力。

# BuddySwitch SKILL Architecture Review And Evolution Notes

## 版本信息

- Document: BuddySwitch SKILL Architecture Review And Evolution Notes
- Date: 2026-04-14
- Status: Draft
- Scope:
  - `buddyswitch/manifest.toml`
  - `buddyswitch/skills/**/SKILL.md`
  - `scripts/env_manifest.py`
  - `scripts/switch_runtime.py`
  - `framework/schemas/**`
  - `tests/test_switch_runtime.py`
  - `tests/test_switch_integration.py`
  - `tests/test_repo_consistency.py`

## 1. 文档目的

本文档整理本轮针对 BuddySwitch SKILL 体系的系统性 review，目的是回答下面几个问题：

1. BuddySwitch 当前的 SKILL 设计，整体上是否符合社区最佳实践。
2. 当前实现有哪些地方已经比较稳，可以继续保留。
3. 当前实现有哪些地方还停留在 MVP 阶段，一旦每个 buddy 下引入大量新 SKILL，会迅速暴露问题。
4. 后续应该优先演进什么，避免在 skill 数量增长后出现路由混乱、上下文膨胀、artifact 堆积和维护成本失控。

本文不是单纯复述外部调研报告，而是把：

- 外部最佳实践
- BuddySwitch 当前代码与对象结构
- 已落盘的真实 runs/tasks/artifacts
- 本轮 review 的分析判断

放到一个统一的判断框架里，方便后续重启 Codex CLI 后继续推进。

## 2. 结论先行

整体判断：

```text
BuddySwitch 当前的 SKILL 体系“部分符合社区最佳实践”，
但它更像是一个质量较好的 MVP / 早期收敛版本，
还不是一个面向“大量新 skills 持续扩张”的长期稳态结构。
```

更具体地说：

- 好的部分：
  - 已经有明确的 buddy authority。
  - 已经有 resolve / persist 分层。
  - 已经有 output schema 和结构化 artifact persistence。
  - 已经有基础测试，避免 runtime contract 退化。

- 不足的部分：
  - skill contract 仍然几乎完全绑在单个 `SKILL.md` 上。
  - supporting files、模板、示例、脚本这些资源还没有成为一等结构。
  - skill 粒度已经开始出现漂移。
  - artifact 生命周期还是“不断新建同类 artifact”，没有明确版本语义。
  - runtime 已经具备确定性 command 推荐，但 skill 输出里仍保留自由生成的下一步命令，形成双重权威。
  - 当前测试覆盖的是“单文件 contract 可以跑通”，不是“后续 skill catalog 大规模扩张仍然稳定”。

因此，这一轮 review 的核心结论不是“当前设计错了”，而是：

```text
当前设计适合少量人工维护的 skills，
不适合直接无改造地承接每个 buddy 下大量新增 SKILL 的阶段。
```

## 3. 外部最佳实践基线

本轮判断主要参考了以下外部材料，并结合仓库现状做对照：

- Claude Code Skills 文档
- Claude Code Hooks 文档
- Claude Code Plugins Reference
- OpenAI 关于 multi-agent workflows / hand-offs / guardrails 的官方文档
- Google ADK 关于 workflow agents 的官方文档

### 3.1 Claude / Anthropic 侧的关键共识

Claude Code 官方文档已经明确支持“轻量 `SKILL.md` + supporting files”的结构。

它强调：

- `SKILL.md` 是主入口。
- 复杂 skill 可以拆 supporting files。
- supporting files 可以包含：
  - reference docs
  - examples
  - templates
  - scripts
- supporting files 应在 `SKILL.md` 中被显式导航。
- `description` 直接影响 skill 是否会被选中，而且 description 在 skill listing 中有长度截断约束。

这说明社区主流不是“所有东西都塞进一个大 `SKILL.md`”，而是：

```text
SKILL.md 做入口和导航；
复杂细节按需拆到附属文件。
```

### 3.2 Hooks / Workflow / Tools 的职责边界

Claude Hooks 文档强调：hooks 提供 deterministic control，用于“某些动作必须发生”的场景，而不是把这类强制规则只靠 skill 提示。

Google ADK 文档则明确区分：

- LLM agents：负责动态判断
- workflow agents：负责 predefined logic / deterministic orchestration

OpenAI 关于 multi-agent workflow 的文档也强调：

- hand-offs
- guardrails
- deterministic and reviewable workflows
- modular design

这些材料和本轮仓库分析共同指向同一个架构原则：

```text
知识与能力单元放 skill；
确定性规则放 hook / workflow / runtime；
外部能力放 tool / MCP；
不要让 skill 承担一切职责。
```

## 4. BuddySwitch 当前结构现状

## 4.1 当前技能目录很轻

当前 `buddyswitch/skills/` 下只有 6 个 skills：

- `market/research-scan`
- `pm/write-prd`
- `pm/track-manager`
- `design/ia-spec`
- `dev/implement-task`
- `test/smoke-test`

当前每个 skill 都只有一个 `SKILL.md`，没有：

- `references/`
- `examples/`
- `scripts/`
- `assets/`
- `evals/`

这说明当前仍处于单文件 skill 阶段。

## 4.2 当前 runtime 已经不是纯 markdown 驱动

这点很重要。

BuddySwitch 并不是简单“读一段 markdown 然后交给模型自由发挥”。

它已经具备以下结构化能力：

- manifest 里有 `buddy -> skills` 映射。
- `env_manifest.py` 会校验 skill frontmatter。
- `env_manifest.py` 会强制要求固定 guidance sections。
- `switch_runtime.py resolve` 会返回：
  - `eligible_skills`
  - `skill_cards`
  - `required_output_schema_by_skill`
  - `implicit_skill_id`
- `switch_runtime.py persist` 会用 schema 校验结果结构。

这意味着 BuddySwitch 已经有一个明确的 skill contract。

但这个 contract 的主要问题是：

```text
它几乎全部建立在单个 SKILL.md 之上，
还没有把 supporting files / templates / examples / scripts
纳入正式 contract。
```

## 4.3 当前 skill 解析方式的边界

`scripts/env_manifest.py` 当前只把这些 headings 识别为 guidance：

- `Purpose`
- `Use when`
- `Do not use when`
- `Inputs`
- `Outputs`
- `Verification`
- `Examples`
- `Counterexamples`
- `Gotchas`

这带来两个直接结果：

1. 现在的 skills 已经比较规范。
2. 但 runtime 对更丰富的 skill package 结构还没有原生认识。

换句话说，BuddySwitch 现在有“skill 文档 contract”，还没有“skill package contract”。

## 5. 当前做得比较好的地方

这一部分是本轮 review 里需要保留的内容，不应该因为要升级结构就误伤。

### 5.1 buddy authority 比较清楚

`buddyswitch/manifest.toml` 里：

- buddy scope 明确
- buddy -> skills 映射明确
- PM 拥有 track lifecycle authority
- 其他 buddies 主要通过 task/artifact 工作

这部分设计是清楚的，符合“显式路由 + 显式 authority”的思路。

### 5.2 resolve / persist 分层合理

当前流程：

```text
parse -> resolve -> host run -> persist
```

这里比较稳的地方是：

- resolve 不写状态
- persist 做结构化技术校验
- business quality 不塞进 persist

这与社区里“确定性 gate 放 runtime，生成质量由 host/session 负责”的方向一致。

### 5.3 output schema 已经是强约束

每个 skill 都绑定 schema。

这使得 skill 输出不是完全自由文本，而是结构化 artifact payload。

这对后续：

- handoff
- artifact selection
- UI 展示
- 自动验证

都非常关键，应该继续保留并加强。

### 5.4 当前 skills 的基本文档质量不差

现有 `SKILL.md` 普遍已经包含：

- purpose
- use when
- do not use when
- outputs
- verification
- examples / counterexamples
- guardrails

它们并不是“随手写几句 prompt”。

所以当前问题不在于 skill 文案过于粗糙，而在于：

```text
这套单文件结构不够支撑下一阶段的大规模增长。
```

## 6. 核心 Findings

## 6.1 Finding A: 当前 skill contract 仍然是单文件 contract，不是 skill package contract

这是本轮最核心的结构性判断。

现状：

- manifest 指向 `SKILL.md`
- runtime 只读取 `SKILL.md`
- guidance 也只从 `SKILL.md` 抽取

当前没有正式建模这些内容：

- reference docs
- examples
- templates
- helper scripts
- test/eval materials

这意味着：

- 现在可以靠少量 skill 人工维护来保持质量。
- 一旦 skill 数量上来，就会把本来该分散在 supporting files 的内容继续挤进 `SKILL.md`。

这个问题已经有前兆：

- 多个 skill 文案里都写了“use the template”
- 但仓库里没有真正对应的 template 资源目录
- `SKILL.md` 也没有 resource navigation

这说明当前结构已经开始承受超出它设计容量的职责。

### 判断

这一点和社区最佳实践不一致。

BuddySwitch 应该升级为：

```text
skill directory
  - SKILL.md
  - references/
  - examples/
  - scripts/
  - assets/
```

## 6.2 Finding B: skill 粒度总体还行，但已经出现边界漂移

从大方向看，现有 skills 基本还是围绕“自然工作单元”组织的：

- research
- prd
- track management
- design spec
- implementation
- smoke test

这比把 skill 切成很多微碎片要好。

但是已经出现一个危险信号：

`implement-task` 本应表示“在项目代码中实现 scoped changes”，
但真实 run 里它也被用于“确认 PM / design handoff，但不进行开发”。

这说明该 skill 已经同时承接：

- readiness check
- context confirmation
- actual implementation

这会带来两个问题：

1. skill name 和真实行为不再稳定对应。
2. 下游依赖 `skill_id` 或 artifact kind 理解上下文时，语义会变模糊。

如果后面继续沿这条路走，典型结果会是：

- `write-prd` 同时承担 scope refinement / decision closure / artifact confirmation
- `implement-task` 同时承担 implementation / implementation-readiness / no-op confirmation
- `smoke-test` 同时承担 smoke / exploratory QA / regression triage

到那时，skill 名字虽然没变，但每个 skill 的内部行为会越来越像“大杂烩阶段集合”。

### 判断

当前 skill 粒度尚未失控，但已经出现漂移前兆。

### 方向

应该尽快明确：

- 哪些是独立自然任务单元，应该拆 skill。
- 哪些是固定阶段编排，应该上提为 workflow。
- 哪些只是当前 skill 的内部可选步骤，不需要拆 skill。

## 6.3 Finding C: artifact 生命周期会比 skill 文档问题更早成为扩张瓶颈

这是本轮 review 里另一个非常重要的结论。

当前 `persist` 对 artifact skill 的处理是：

- 每次运行都派生新 `artifact_id`
- 创建新 artifact
- 挂到 task 下
- `latest_artifact_id` 指向最新那个

结果已经在真实数据里出现：

- 同一个 PM task 下有 3 个 PRD artifact
- 同一个 dev task 下有 2 个 implementation report

这在当前样本量下还勉强可控，但后续 skill 数量增加、迭代次数增加后，会迅速产生几个问题：

1. artifact selection 成本升高。
2. task 下堆积大量同类 artifact，`latest` 虽然能用，但历史语义不清。
3. “这一版是 refinement 还是 full replacement” 没有一等表达。
4. 下游很难判断哪些 artifacts 应继续读，哪些只属于历史留档。

### 判断

如果不尽快给 artifact 建立更清晰的版本语义，skill catalog 增长后最先出问题的不是文档，而是：

```text
上下文装载与 handoff 成本。
```

### 方向

至少应明确以下语义之一：

- current artifact vs historical revisions
- replace vs revise vs append
- canonical current artifact pointer

否则 skill 越多，artifact 选择越重。

## 6.4 Finding D: 当前路由机制适合少量 skills，不适合大量相邻 skills

当前 resolve 逻辑会：

- 读取某个 buddy 下的所有 skills
- 全部作为 `eligible_skills`
- 单 skill buddy 给 `implicit_skill_id`
- 多 skill buddy 交给 host session 选择

这对当前 skill 数量是成立的。

但当某个 buddy 下出现 5 到 12 个相邻技能时，会有明显问题：

1. 多个 skill description 容易高度相似。
2. 目前没有更细的 activation metadata。
3. runtime 没有对“这个 demand 更可能属于哪个 skill”做结构化过滤。

而 Claude 原生 skill 体系已经支持一些很有价值的 activation/frontmatter 能力，比如：

- `description`
- `paths`
- `disable-model-invocation`
- `allowed-tools`
- `hooks`

BuddySwitch 当前 frontmatter 只覆盖了其中一部分“运行描述”，还没有把这些更接近实际激活控制的字段吸纳进自身 model。

### 判断

现有路由机制是一个合理的 MVP，但不是未来多-skill buddy 的终局。

### 方向

后续需要补一层更强的 skill catalog metadata，而不是继续只靠 description 文案区分。

## 6.5 Finding E: runtime 已经有确定性 handoff 命令，但 schema 还允许 skill 自由生成 suggested_next_switch

当前 runtime 已经能确定性生成：

- `reference_switches`
- `recommended_switch`

而 schema 里仍然允许 skill 返回：

- `suggested_next_switch`

这会造成双重权威。

更关键的是，真实 run 已经出现错误：

- 某次 dev “确认不开发”的 run 里，`suggested_next_switch` 写出了一个错误 task id 的命令

这说明这类字段一旦交给模型自由生成，就会发生漂移。

### 判断

这不是文案小问题，而是明确的 control-plane 设计味道：

```text
runtime 已经能 deterministic 生成的东西，
不应该继续允许 skill 自由生成一个并列版本。
```

### 方向

应考虑：

- 删除 `suggested_next_switch`
- 或把它退化为纯附加建议文本，不再承载 command authority

## 6.6 Finding F: 当前测试覆盖的是“单文件 contract 可用”，不是“未来大规模扩张可维护”

当前测试基线是健康的。

本轮实际运行：

```text
python3 -m unittest tests.test_switch_runtime tests.test_switch_integration tests.test_repo_consistency
```

结果：

```text
Ran 26 tests in 0.082s
OK
```

这说明：

- 当前 runtime contract 没坏
- 当前 manifest/skill parsing 没坏
- 当前 repo consistency 规则没坏

但要注意：

当前测试主要覆盖的是：

- frontmatter requirement
- guidance section requirement
- persist wiring
- summary semantics

没有覆盖这些未来更关键的问题：

- supporting files 是否存在且可发现
- skill 所引用 template/example/script 是否真的存在
- skill description 冲突如何检测
- artifact revision policy 是否符合预期
- 多-skill buddy 在相邻任务上的路由稳定性
- golden outputs / evals

### 判断

测试质量不差，但测试边界仍停留在当前阶段。

## 7. 当前哪些地方已经出现“落后实践”的前兆

下面这些不是“未来也许会发生”，而是已经在仓库里出现的前兆。

### 7.1 “使用模板”已经写进 skill，但模板文件并不存在

多个技能都写了类似表述：

- “Write the PRD using the PRD template”
- “Write the design artifact using the design template”
- “Write the final report using the research template”
- “Write the report using the test template”

但当前 skill 目录没有对应模板文件。

这说明：

- skill 已经有模板化需求
- 但结构还没有升级去承接这件事

### 7.2 同一个 task 的产物已经开始多版本堆积

真实对象里已经能看到：

- `prd`
- `prd-2`
- `prd-3`

以及：

- `implementation-report`
- `implementation-report-2`

这不是数据错误，但它说明 artifact 生命周期设计已经进入下一阶段需求。

### 7.3 skill 名称和 skill 实际行为开始不完全一致

最明显的例子就是：

- `implement-task`

实际既承接：

- 真正开发
- 纯确认 handoff、不做开发

这说明 skill 粒度的内部边界已经开始松动。

### 7.4 “下一步命令”已经出现双重生成

当前既有：

- runtime 的 `recommended_switch`
- skill result 的 `suggested_next_switch`

而且后者已出现错误 task id。

这说明 deterministic control 和 model-generated suggestions 的职责边界已经重叠。

## 8. 对 BuddySwitch 的演进建议

## 8.1 第一优先级：升级 skill package 结构

建议把“标准 skill 目录结构”确认为正式规范，即使初期允许某些目录为空。

推荐默认结构：

```text
skill-name/
  SKILL.md
  references/
  examples/
  scripts/
  assets/
```

职责建议：

- `SKILL.md`
  - purpose
  - when to use
  - high-level workflow
  - output contract
  - resource navigation

- `references/`
  - 领域规则
  - 详细说明
  - 复杂边界条件

- `examples/`
  - 输入示例
  - 输出示例
  - 正反案例

- `scripts/`
  - 校验器
  - 辅助提取器
  - 重复性命令

- `assets/`
  - 模板
  - 产物骨架
  - 静态资源

## 8.2 第二优先级：把 deterministic next-step authority 收回 runtime

建议把 `suggested_next_switch` 从 output schema 中移除，或者至少降权。

推荐目标：

- runtime 负责唯一 authoritative switch command
- skill 只负责：
  - summary
  - open questions
  - additional notes

这样可以避免：

- task id 漂移
- 命令格式飘掉
- runtime 与 skill 给出相互冲突的下一步

## 8.3 第三优先级：定义 artifact revision policy

这件事非常关键。

建议尽快引入明确语义，例如：

- `current`
- `revision_of`
- `supersedes`
- `artifact_slot`

哪怕第一版只做很轻的版本策略，也比纯 suffix 累加更稳。

要点不是立即做很复杂的版本系统，而是先回答：

```text
同一 task 下多次 write-prd / implement-task / ia-spec，
到底是“同一种产物的新版本”，
还是“新的并列产物”？
```

只要这个问题不明确，skill 越多，artifact 越难选。

## 8.4 第四优先级：把“阶段性流程”从 skill 中提出来

建议逐步区分：

- 自然工作单元 skill
- 固定阶段 workflow

例如：

- “实现前确认最新 PM / design handoff”
- “读取 track_artifact_index 并选择输入 artifacts”
- “PM 确认 open questions 已清零并可 handoff dev”

这类动作不一定都要拆成新 skill。

很多更适合作为：

- workflow step
- runtime fixed flow
- hook
- explicit helper command

而不是塞进现有产物型 skill 里。

## 8.5 第五优先级：为 skill 扩张补测试

建议新增几类测试：

### A. skill package consistency tests

验证：

- `SKILL.md` 中引用的 template/example/reference/script 是否真实存在
- skill 目录结构是否符合规范

### B. routing disambiguation tests

针对未来某个 buddy 下多个相邻 skills，验证：

- 相似 demand 是否能稳定落到预期 skill

### C. artifact revision tests

验证：

- 第二次、第三次运行是否符合 revision policy

### D. golden output / evals

针对关键 skills，建立：

- 输入样例
- 期望输出结构
- quality rubric

## 9. 推荐的 v2 目标形态

如果要为“大量新增 SKILL”做准备，我建议把 BuddySwitch v2 的目标形态定义为：

```text
1. BuddySwitch 仍保留 buddy authority + resolve/persist control plane
2. skill 从单文件升级为 package
3. deterministic rules 继续放 runtime / hook / workflow
4. artifact 建立 revision semantics
5. runtime command authority 收敛为单一来源
6. 测试从 runtime correctness 扩展到 skill package scalability
```

这条路径是渐进式的，不需要一次性大重构。

## 10. 一个现实的分阶段改造顺序

为了降低改造风险，建议按下面顺序做，而不是一起动。

### Phase 1

- 定义 skill package 目录规范
- 给现有 6 个 skills 建空目录：
  - `references/`
  - `examples/`
  - `scripts/`
  - `assets/`
- 把现有 `SKILL.md` 里提到的 template 明确落文件
- 增加 repo consistency tests，检查引用资源存在性

### Phase 2

- 移除或降权 `suggested_next_switch`
- 让 runtime 成为唯一 command authority
- 清理相应 schema 和 docs

### Phase 3

- 明确 artifact revision policy
- 更新 `env_store` / `switch_runtime` / `artifact_selection`
- 更新 UI/selection 逻辑

### Phase 4

- 审视每个 buddy 下的 skill catalog
- 把阶段性逻辑从现有 skill 中拆出或上提 workflow
- 为多-skill buddies 建路由稳定性测试

## 11. 当前文档的最终判断

最终判断可以压缩成三句话：

1. BuddySwitch 当前的 SKILL 体系并不差，已经具备比较扎实的 runtime 与 persistence 基线。
2. 但它当前仍然是“单文件 skill + 少量技能”的质量较高版本，不是面向大量技能扩张的长期最佳实践形态。
3. 后续如果不尽快升级 skill package 结构、artifact revision 语义和 deterministic workflow 边界，大量新 SKILL 会先从上下文组织和对象管理层面拖垮系统。

## 12. 本轮运行与验证记录

本轮本地验证执行了：

```bash
python3 -m unittest tests.test_switch_runtime tests.test_switch_integration tests.test_repo_consistency
```

结果：

```text
Ran 26 tests in 0.082s
OK
```

说明当前代码基线是健康的，本轮结论主要针对“架构准备度”，而不是“当前实现已损坏”。

## 13. 可直接承接的后续工作

重启 Codex CLI 后，建议优先从以下三个方向中选一个继续：

1. 写一版 `BuddySwitch SKILL v2` 规范文档。
2. 先做 skill package 目录规范和资源存在性校验测试。
3. 先设计 artifact revision policy，再回头调整 skill/handoff 机制。

如果优先级只选一个，我建议先做：

```text
skill package 目录规范 + 资源存在性测试
```

因为这是最小成本、最高收益、对现有行为冲击最小的一步。

## 14. 参考资料

外部资料：

- Claude Code Skills: <https://code.claude.com/docs/en/skills>
- Claude Code Hooks: <https://code.claude.com/docs/en/hooks-guide>
- Claude Code Plugins Reference: <https://code.claude.com/docs/en/plugins-reference>
- Claude Code Plugin Discovery / Marketplace: <https://code.claude.com/docs/en/discover-plugins>
- OpenAI Codex Agents SDK Guide: <https://developers.openai.com/codex/guides/agents-sdk#creating-multi-agent-workflows>
- Google ADK Workflow Agents: <https://adk.dev/agents/workflow-agents/>

仓库内关键证据：

- `buddyswitch/manifest.toml`
- `scripts/env_manifest.py`
- `scripts/switch_runtime.py`
- `framework/schemas/**`
- `buddyswitch/skills/**/SKILL.md`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/content/runs/*.json`

# PMF-Recon Execution Fidelity Memo

## Bottom Line

`pmf-recon` 在 BuddySwitch 下看起来像“打折执行”，主要风险不在模型能力，而在执行保真度。

- 真正执行 skill 的仍然是宿主 Codex 会话，不是第二个更弱的 backend。
- 真正容易掉质量的地方，是 host 有没有把被选中的 skill 包完整用起来。

## What Actually Runs

以 `switch market: ...` 且最终选中 `pmf-recon` 为例，实际链路是：

1. BuddySwitch `resolve` 返回 `eligible_skills`、`skill_cards`、`required_output_schema_by_skill`、`run_instructions`
2. host 选中 `pmf-recon`
3. host 读取 `buddyswitch/skills/market/pmf-recon/SKILL.md`
4. host 按需要继续读取 `references/*` 和 `assets/*`
5. host 执行研究
6. BuddySwitch `persist` 做结构校验和状态写入

这意味着：

- 不是把整个 skill 目录一次性塞进 context
- 也不是 BuddySwitch 自己“代替” Codex 执行
- 本质上仍然是同一个 Codex 读说明、读引用文件、调用工具、完成任务

## Highest-Risk Failure Modes

### 1. 只看 `skill_cards`，没读完整 `SKILL.md`

这是最容易造成“像缩水版执行”的地方。

- `resolve` 暴露的是 compact guidance，不是完整 workflow
- `pmf-recon` 的研究默认项、source strategy、blocking rules、steps、verification、guardrails 都在 `SKILL.md`

典型症状：

- 输出像泛泛的市场分析
- PMF 视角不够尖锐
- strongest ICP / strongest pain / next validation move 不够清楚

### 2. 读了 `SKILL.md`，但没继续读关键 `references/*`

`pmf-recon` 明确要求按需读取：

- `references/source-map.md`
- `references/evidence-rubric.md`
- `references/interview-prompts.md`

如果 host 停在 `SKILL.md`，常见后果是：

- 证据采集口径不稳
- source mix 不够好
- evidence traceability 弱
- interview angles 变得泛

### 3. 选 skill 选错了

`market` 现在是 multi-skill buddy。

- 宽泛品类扫描更适合 `research-scan`
- PMF / ICP / pain / alternatives / next validation move 才适合 `pmf-recon`

如果一个本该走 `research-scan` 的请求被硬塞给 `pmf-recon`，结果也会“看起来不对”，但这不是执行打折，而是路由前就错了。

### 4. 把 schema 当成目标，而不是最低结构约束

`persist` 只做结构校验，不做质量评审。

风险在于 host 可能为了尽快填满必填字段，产出一份“字段齐全但研究很浅”的结果。

典型症状：

- 看起来很完整
- 但证据密度不够
- inference 和 evidence 分得不清
- 结论像 checklist，不像研究判断

### 5. 过早为 `persist` 压缩结果

正确顺序应该是：

1. 先按 skill 做完整研究
2. 再整理成 schema-valid result

如果反过来，host 一开始就按最终 JSON 形状思考，常见问题是：

- 研究过程被压扁
- 中间证据没积累够
- 最终 artifact 看起来“能交差”，但洞察不够深

## What Is Not The Main Problem

下面这些通常不是核心问题：

- 不是因为 BuddySwitch 调了一个更弱的模型
- 不是因为 BuddySwitch 先做了语义路由，替 host 做差了判断
- 不是因为 skill 只能被当作一段短 prompt 执行

对 `pmf-recon` 来说，真正的风险是：

- host 是否真的读了完整 skill package
- host 是否真的按 skill workflow 执行
- host 是否把 references 用起来

## Compared With Native Codex Skills

如果先不讨论 discovery，只讨论“skill 已经确定被执行”这一刻：

- BuddySwitch 版本：host 读 `SKILL.md`，再按需读 `references/*`、`assets/*`
- Native Codex skill 版本：Codex 也是读被触发的 `SKILL.md`，再按需读 `references/*`、`scripts/*`、`assets/*`

所以执行层面两者是接近的。

真正差异主要在执行前后：

- BuddySwitch 多了一层 `resolve`
- BuddySwitch 用 `skill.toml` 和 schema / persist 协议
- Native Codex skill 用自己的原生 skill metadata / loading semantics

结论：

- 能力本身不应打折
- 真正会打折的是 orchestration fidelity

## Practical Rule

如果要避免 `pmf-recon` 在 BuddySwitch 下“看起来像打折执行”，最低要求是：

1. 先确认 `pmf-recon` 选对了
2. 不要只停在 `skill_cards`
3. 必须读完整 `SKILL.md`
4. 需要时继续读 `references/*`
5. 先完成研究，再整理成 schema-valid result

一句话总结：

BuddySwitch 对 `pmf-recon` 的主要风险不是“换了个弱执行器”，而是“host 没有把这个 skill 包完整执行到位”。

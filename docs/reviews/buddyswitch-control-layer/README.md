# BuddySwitch 控制层架构审查包

## 1. 目的

这是一套面向后续迭代优化的控制层审查文档。

本审查包关注 BuddySwitch 当前最核心的控制链路：

- `switch` 入口唤起
- parser / router / runtime / persist
- manifest / skill metadata / output schema
- object store 与 manual debug APIs
- 相关规范文档与测试

本审查包不直接修改实现代码。
它的目标是把当前系统中的控制逻辑、校验逻辑、失败动作和复杂度来源讲清楚，供后续重构和收敛时直接使用。

## 2. 本审查包与现有文档的关系

- 历史 `docs/buddyswitch/` 产品规划包已移除，不再作为当前控制层依据。
- `framework/docs/`：当前规范与实现说明，是本审查包的重要证据来源。
- `README.md` / `AGENTS.md`：当前使用入口说明，是本审查包重点核对对象。

本审查包是一个独立的“架构审查层”，不替代上述文档。

## 3. 阅读顺序

1. [01-audit-charter.md](./01-audit-charter.md)
2. [02-switch-invocation-and-router-review.md](./02-switch-invocation-and-router-review.md)
3. [03-validation-and-failure-action-matrix.md](./03-validation-and-failure-action-matrix.md)
4. [04-state-safety-and-authority-review.md](./04-state-safety-and-authority-review.md)
5. [05-tests-and-spec-gap-review.md](./05-tests-and-spec-gap-review.md)
6. [06-optimization-backlog.md](./06-optimization-backlog.md)
7. [07-implementation-status.md](./07-implementation-status.md)
8. [08-compatibility-debt-cleanup-plan.md](./08-compatibility-debt-cleanup-plan.md)

## 4. 核心结论摘要

### 4.1 当前控制层已经形成两套不同倾向

- 一套倾向是 LLM-native：
  - 用户通过 `switch <buddy>: <task>` 明确表达意图
  - host Codex session 负责阅读 skill、执行工作流、生成结构化结果
- 另一套倾向是 rule-heavy：
  - parser、runtime、manifest、store 中存在较多显式校验与 eligibility gate
  - 一部分校验承担了状态安全职责
  - 另一部分校验更像“先验规则堆积”，失败后动作并不清晰

### 4.2 当前最需要明确的，不是“继续加规则”，而是“明确每种校验的失败动作”

本审查包统一采用 4 种失败动作分类：

- `normalize`
- `warn`
- `ask`
- `reject`

凡是不能明确归入其中之一的校验，默认视为复杂度风险项。

### 4.3 当前控制层里真正合理的硬校验，主要集中在两类

- 防止误路由
- 防止写坏状态

这两类以外的很多限制，更适合下沉为：

- schema 描述
- host 提示与执行说明
- 审查/评测规则
- warning 级提示

而不是 runtime gate。

### 4.4 审查包现在已经有对应的实施状态页

- [07-implementation-status.md](./07-implementation-status.md) 记录了哪些结论已经落地、哪些被降级为 metadata、哪些明确不做
- [08-compatibility-debt-cleanup-plan.md](./08-compatibility-debt-cleanup-plan.md) 记录兼容包袱清理的收口状态与与 09 的关系
- 后续迭代应先看这份状态页，再决定是否继续修改控制层

## 5. 审查对象清单

本审查包覆盖以下实现对象：

- `scripts/parse_switch.py`
- `scripts/codex_router.py`
- `scripts/switch_runtime.py`
- `scripts/env_manifest.py`
- `scripts/output_schema.py`
- `scripts/env_store.py`
- `scripts/env_tracks.py`
- `scripts/env_artifacts.py`
- `tests/test_switch_runtime.py`
- `tests/test_repo_consistency.py`
- `README.md`
- `AGENTS.md`
- `framework/docs/switch-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/track-registry.md`

## 6. 推荐使用方式

后续每次要调整控制层逻辑时，建议先做两步：

1. 在 [03-validation-and-failure-action-matrix.md](./03-validation-and-failure-action-matrix.md) 找到对应校验项，确认它属于 `normalize / warn / ask / reject` 中哪一种。
2. 在 [06-optimization-backlog.md](./06-optimization-backlog.md) 查看该问题是否已被列为 `P0 / P1 / P2`，避免重复设计或重新引入已识别的复杂度。

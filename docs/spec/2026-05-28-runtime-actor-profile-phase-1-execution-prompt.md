# Runtime Actor Profile Phase 1 Execution Prompt

在 worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-inst` 执行，禁止污染 main 或其它 worktree。

任务目标：完整执行 Runtime Actor Profile Phase 1，按以下文档推进：

- `docs/memo/2026-05-28-runtime-actor-profile-phase-1-task.md`
- `docs/spec/2026-05-28-runtime-actor-profile-phase-1-test-plan.md`
- `docs/spec/2026-05-28-runtime-actor-profile-phase-1-development-plan.md`

执行要求：

1. 先重新阅读 memo、测试计划、开发计划和当前代码实现。
2. 严格按测试驱动循环执行：写测试 -> 运行确认红灯 -> 实现 -> focused 测试 -> 修复 -> 更大范围回归。
3. 遵循 forward 原则：不做过渡方案，不保留 raw active-role auth 兼容入口，不引入 per-instance auth、delegation、elevation、permission DSL、workflow engine、plugin system。
4. `actor_profile` 只负责运行时 actor identity normalization。
5. `role_auth` 只负责 `required_permission + AuthSubject` 的 role-action policy decision。
6. `auth_feedback` 只负责标准 `E_TOOL_ROLE_AUTH` pre-dispatch denial feedback。
7. `registry` 只做编排：加载 action definition、读取 `required_permission`、调用 role auth、路由 denied feedback、构建 `ToolContext`、调用 tool service。
8. `ToolContext` 继续作为 tool-facing execution contract；tool package 不得 import 或 inspect `RuntimeActorProfile`。
9. 产品行为不得改变；现有 role auth、router、context、semantic、message 测试必须继续通过。
10. 完成后必须进行一次 review 验收：检查模块边界、依赖方向、身份来源、auth 输入、feedback ownership、ToolContext surface、tool package imports、测试覆盖、无 main 污染。
11. 如遇到会改变产品语义、计划冲突、测试无法合理通过、或需要扩大范围的问题，暂停并向用户确认。

最终完成标准：

- 测试计划覆盖点全部落实；
- 开发计划中的任务全部完成；
- focused tests 全 pass；
- 相关 runtime/auth/context/message 回归测试全 pass；
- search 验证显示旧的 inline auth feedback 和 raw-role auth 入口已移除；
- review 验收通过；
- `git status --short` 只显示 `fea-inst` 本任务相关变更。

最终回复需要简洁说明：

- 改了什么；
- 测试跑了哪些，结果如何；
- review 验收结论；
- 是否有剩余风险或需要用户确认的问题。

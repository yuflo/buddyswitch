# Daemon Service MVP Step 2 Execution Prompt

在 worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon` 执行，禁止污染 main 或其它 worktree。

任务目标：完整执行 Daemon Service MVP 第二步，按以下文档推进：

- `docs/memo/2026-05-28-daemon-service-mvp-step-2.md`
- `docs/spec/2026-05-28-daemon-service-mvp-step-2-test-plan.md`
- `docs/spec/2026-05-28-daemon-service-mvp-step-2-development-plan.md`

执行要求：

1. 先重新阅读 memo、测试计划、开发计划和当前代码实现。
2. 严格按测试计划和开发计划循环执行：写/迁移测试 -> 运行确认红灯 -> 实现 -> focused 测试 -> 修复 -> 更大范围回归。
3. 遵循 forward 原则：不做过渡方案，不保留旧 handler `bool`/raw client 兼容路径，不引入 plugin system / event bus / workflow engine / message handler。
4. daemon service 必须提供明确 Handler Contract、Action Gateway、handler state namespace、handler failure isolation、handler observability。
5. Task Checkout Handler 必须作为标准 handler 接入，只能通过 Action Gateway 发起 daemon-side action。
6. launcher thread bootstrap / 空 rollout 仍由 launcher 原生处理，不外溢到 daemon。
7. input Task TUI 不迁入 daemon。
8. 所有相关测试必须通过才算完成。
9. 完成后必须进行一次 review 验收：检查架构边界、依赖方向、状态归属、handler 接入面、failure isolation、status observability、测试覆盖、无 main 污染。
10. 如遇到会改变产品语义、计划冲突、测试无法合理通过、或需要扩大范围的问题，暂停并向用户确认。

最终完成标准：

- 开发计划中的任务全部完成；
- 测试计划覆盖点全部落实；
- focused tests 全 pass；
- 相关 launcher / app-server / task input 回归测试全 pass；
- review 验收通过；
- `git status --short` 只显示 `fea-daemon` 本任务相关变更。

最终回复需要简洁说明：

- 改了什么；
- 测试跑了哪些，结果如何；
- review 验收结论；
- 是否有剩余风险或需要用户确认的问题。

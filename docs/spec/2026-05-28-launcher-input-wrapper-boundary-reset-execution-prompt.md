# Launcher Input Wrapper Boundary Reset Execution Prompt

在 worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-tui` 执行，禁止污染 `main` 或其它 worktree。

任务目标：完整执行 launcher input / Task TUI foreground boundary reset，按以下文档推进：

- `docs/memo/2026-05-28-launcher-input-wrapper-boundary-reset.md`
- `docs/spec/2026-05-28-launcher-input-wrapper-boundary-reset-test-plan.md`
- `docs/spec/2026-05-28-launcher-input-wrapper-boundary-reset-development-plan.md`

执行要求：

1. 先重新阅读 memo、测试计划、开发计划和当前代码实现，再动手。
2. 严格执行 TDD：先写/更新测试，运行确认红灯，再写最小实现，回到 focused tests，最后做更大范围回归。
3. 遵循 forward 原则：不做过渡方案，不保留旧默认 Task TUI 路径，不保留 hidden fallback，不保留 `task-ui` alias。
4. `launcher input` 必须恢复为 raw-by-default 的基础 API；Task TUI 只能通过显式 `--input-wrapper task-tui` 进入。
5. wrapper 选择权属于 launcher；`app_server.py` / `app_server.sh` 只能保留 transport-level input 参数，不得继续感知 Task TUI 或 `--instance-json`。
6. 不引入 plugin system、generic registry、workflow engine、额外中间层。
7. 不修改 daemon STOP 路径，不把 foreground Task TUI 输入逻辑迁入 daemon。
8. 所有相关测试必须通过才算完成，包括：
   - wrapper focused tests；
   - app-server transport boundary tests；
   - launcher input regression；
   - daemon STOP regression。
9. 完成后必须做一次 review 验收，逐条检查 memo 里的 non-negotiables、public API、boundary scan、依赖方向、以及无 main 污染。
10. 如遇到会改变产品语义、计划与代码现实冲突、测试无法合理通过、或需要扩大范围的问题，暂停并向用户确认。

最终完成标准：

- `instance input` 默认 raw；
- `task-tui` 显式可用；
- app-server transport 不再知道 Task TUI；
- 旧隐式耦合已删除，不是隐藏兼容；
- 相关 focused tests / regression tests 全 pass；
- review 验收通过；
- `git status --short` 只显示本任务相关变更。

最终回复需要简洁说明：

- 改了什么；
- 跑了哪些测试，结果如何；
- review 验收结论；
- 是否还有剩余风险或需要用户确认的问题。

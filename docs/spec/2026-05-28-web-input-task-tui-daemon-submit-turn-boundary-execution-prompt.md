# Web Input / Task TUI / Daemon Submit Turn Boundary Execution Prompt

在 worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-tui` 执行，禁止污染 `main` 或其它 worktree。

任务目标：完整执行 `docs/memo/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary.md`，按以下文档推进：

- `docs/memo/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary.md`
- `docs/spec/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary-test-plan.md`
- `docs/spec/2026-05-28-web-input-task-tui-daemon-submit-turn-boundary-development-plan.md`

执行要求：

1. 先重新阅读 memo、测试计划、开发计划和当前代码实现，再动手。
2. 严格执行 TDD：先写/更新测试，运行确认红灯，再写最小实现，回到 focused tests，最后做更大范围回归。
3. 遵循 forward 原则：不做过渡方案，不保留双路径兼容，不加 plugin system / event bus / generic registry / central handler config。
4. Web input 必须显式通过 launcher `instance input --input-wrapper task-tui` 发送。
5. CLI `instance input` 默认必须继续保持 `raw`；显式 `--input-wrapper task-tui` 仍然可用。
6. 必须新增 launcher-owned `submit_turn` 共享发送层，并让 foreground input 与 daemon checkout 共用它。
7. `submit_turn` 只能拥有 transport-level send 责任：已经组合好的文本输入、thread/socket/permissions、调用 app-server、返回 action/turn id。
8. `daemon_core.py` 不能感知 task snapshot / Task TUI；`task_checkout_handler.py` 不能再 import `app_server`。
9. STOP checkout 必须继续发送 `[TASK CHECKOUT]`，并保持现有 handler state observability：`last_origin_turn_id`、`last_action_turn_id`、`last_result`、`last_error`。
10. 所有相关测试必须通过才算完成，包括：
    - `tests/test_submit_turn.py`
    - `tests/test_web_management.py`
    - daemon service boundary tests
    - `tests/test_task_checkout_handler.py`
    - 相关 launcher / daemon regression tests
11. 完成后必须做一次 review 验收，逐条检查 memo acceptance criteria、boundary scan、依赖方向、以及 worktree 干净度。
12. 如遇到会改变产品语义、计划与代码现实冲突、测试无法合理通过、或需要扩大范围的问题，暂停并向用户确认。

最终完成标准：

- Web input 默认带 `task-tui`；
- CLI input 默认 raw，显式 `task-tui` 正常；
- launcher-owned `submit_turn` 已接管 launcher input 与 daemon checkout send path；
- `task_checkout_handler.py` 不再 import `app_server`；
- daemon STOP 行为和 observability 不回退；
- focused tests 与相关回归 tests 全 pass；
- review 验收通过；
- `git status --short` 只显示本任务相关变更。

最终回复需要简洁说明：

- 改了什么；
- 跑了哪些测试，结果如何；
- review 验收结论；
- 是否还有剩余风险或需要用户确认的问题。

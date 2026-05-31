# Web Open TUI macOS Execution Prompt

在 worktree `/Users/chen/Dev/buddyswitch/.worktrees/fea-webui` 执行，禁止污染 `main` 或其它 worktree。

任务目标：完整执行 `docs/memo/2026-05-29-web-open-tui-macos-task.md`，按以下文档推进：

- `docs/memo/2026-05-29-web-open-tui-macos-task.md`
- `docs/spec/2026-05-29-web-open-tui-macos-test-plan.md`
- `docs/spec/2026-05-29-web-open-tui-macos-development-plan.md`

执行要求：

1. 先重新阅读 memo、测试计划、开发计划和当前代码实现，再动手。
2. 严格执行 TDD：先写/更新测试，运行确认红灯，再写最小实现，回到 focused tests，最后做更大范围回归。
3. 遵循 SHARP forward 原则：不做过渡方案，不保留双路径兼容，不加 launcher `attach-open`，不加 terminal selector / plugin system / generic opener registry。
4. 这个能力必须完全属于 Web Management：
   - `web_management.py` owns `POST /api/instances/<id>/open-tui`;
   - `web_management.py` owns macOS-only Terminal.app opener;
   - launcher 继续只 owns `instance attach <id>`.
5. 自动化测试禁止打开真实 Terminal，必须使用 fake terminal opener。
6. API route 必须：
   - validate instance id before status lookup/opener;
   - require `POST`;
   - require `Content-Type: application/json`;
   - require `X-BuddySwitch-Web: 1`;
   - check local Host/Origin where present;
   - reject arbitrary request body fields;
   - block inactive, unhealthy, missing-thread, unsupported-OS states before opener;
   - construct command server-side from repo root and validated instance id.
7. macOS opener 必须使用 Terminal.app + `osascript`，不得使用 `System Events`、keystroke simulation、iTerm、Linux/Windows support。
8. Frontend 必须：
   - 在 selected instance action area 增加简洁 `Open TUI` CTA；
   - active + healthy + thread present 时启用；
   - inactive 显示 `Resume this instance first.`;
   - unhealthy 显示 `Instance is unhealthy.`;
   - missing thread 显示 `No thread to attach.`;
   - 点击后显示 `Opening...`;
   - 成功显示 `Terminal opened.`;
   - 失败显示 `Could not open Terminal.` 并暴露 `Copy command`.
9. UI 保持当前 Notion-like local control console 风格，不做新页面、wizard、复杂 modal、重视觉效果或营销式说明。
10. 所有相关测试必须通过才算完成，包括：
    - `tests/test_web_management.py`
    - `tests/web_management_ui_state.test.js`
    - `tests/web_management_ui_contract.test.js`
    - 最终 full Python regression `tests`
11. 完成后必须做一次 review 验收，逐条检查 memo Definition of Done、security boundary、launcher surface、fake-opener coverage、frontend state gating、worktree scope。
12. 如遇到会改变产品语义、需要扩大到 launcher/daemon/runtime、测试无法合理通过、或 macOS manual verification 无法执行的问题，暂停并向用户说明具体阻塞证据。

建议执行顺序：

```bash
sed -n '1,260p' docs/memo/2026-05-29-web-open-tui-macos-task.md
sed -n '1,260p' docs/spec/2026-05-29-web-open-tui-macos-test-plan.md
sed -n '1,320p' docs/spec/2026-05-29-web-open-tui-macos-development-plan.md
sed -n '1,260p' tools/launcher/web_management.py
sed -n '1,260p' tools/launcher/assets/web-management/app.js
```

Focused verification loop:

```bash
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
```

Final verification:

```bash
node tests/web_management_ui_state.test.js
node tests/web_management_ui_contract.test.js
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
PATH=/Users/chen/miniconda3/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
git status --short
```

最终完成标准：

- Web Management exposes a minimal `Open TUI` CTA for selected instance.
- The CTA launches macOS Terminal.app through Web API only.
- Terminal runs the existing `./buddyswitch-codex instance attach <instance-id>` path.
- Launcher public command surface remains unchanged.
- Invalid states are blocked before opening Terminal.
- Failure gives a clear message and copy-command fallback.
- Automated tests cover API routing, state gating, and no-real-terminal behavior.
- Manual macOS verification is either passed and recorded, or an explicit environment blocker is reported.
- Focused tests and full Python regression pass.
- Review验收通过.

最终回复需要简洁说明：

- 改了什么；
- 跑了哪些测试，结果如何；
- review 验收结论；
- manual macOS verification 结果或阻塞；
- 是否还有剩余风险。

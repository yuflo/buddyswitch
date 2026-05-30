# Message Actor Signal Send Upgrade Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Objective: execute the message actor signal send upgrade until focused tests, full tests, and review all pass.

Required inputs:

- Memo: `docs/memo/2026-05-30-message-actor-signal-send-upgrade-task.md`
- Test plan: `docs/spec/2026-05-30-message-actor-signal-send-upgrade-test-plan.md`
- Development plan: `docs/spec/2026-05-30-message-actor-signal-send-upgrade-development-plan.md`
- Resource lifecycle lesson: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Execution rules:

1. Work only in `fea-daemon`; do not touch `main`.
2. Use TDD for behavior changes:
   - write or update the failing behavior test;
   - run it and confirm the intended failure;
   - implement the smallest direct change;
   - rerun the focused test.
3. Replace the old `to_buddy` message send path with `target_actor_address`; do not preserve a dual main path.
4. Keep daemon presence, registry, mailbox endpoint, and signal routing details outside message code.
5. Do not introduce an offline queue, workflow engine, subscription engine, plugin system, broadcast path, or fuzzy target selection.
6. Do not edit `buddyswitch/objects/**` or old buddybox runtime paths directly; tests must use runtime workspace overrides.
7. Be strict about resource lifecycle:
   - message tests should use daemon client fakes or in-process service objects;
   - do not start broad service suites until focused tests are green;
   - inspect residual daemon processes after broad verification.

Implementation loop:

1. Read the development plan.
2. Execute Task 1 through Task 10 in order.
3. If a test failure exposes a wrong plan assumption, update the plan and implementation together.
4. Before declaring completion, run:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
python3 -m pytest tests/test_env_tool_schema_*.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_context_binding_env_tool.py tests/test_env_tool_response_*.py tests/test_env_tool_schema_*.py -q
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py tests/test_central_daemon_service.py -q
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

Completion standard:

- all focused tests pass;
- full test suite passes;
- residual process check is clean for test-owned daemon processes;
- review confirms message durable data no longer stores `from_buddy` or `to_buddy`;
- review confirms `message.send` success requires delivered signal;
- review confirms delivery failure cleanup and indeterminate failure contracts are explicit;
- review confirms message code does not parse target instance JSON, daemon registry files, or daemon endpoint details.

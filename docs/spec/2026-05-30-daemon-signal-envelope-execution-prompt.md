# Daemon Signal Envelope Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Objective: execute the daemon signal envelope plan until tests pass and review accepts the result.

Required inputs:

- Memo: `docs/memo/2026-05-30-daemon-signal-communication-iteration-task.md`
- Test plan: `docs/spec/2026-05-30-daemon-signal-envelope-test-plan.md`
- Development plan: `docs/spec/2026-05-30-daemon-signal-envelope-development-plan.md`
- Resource lifecycle lesson: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Execution rules:

1. Work only in `fea-daemon`; do not touch `main`.
2. Use TDD for behavior changes:
   - write the failing test;
   - run it and confirm the intended failure;
   - implement the direct change;
   - rerun the focused test.
3. Replace the message-specific mailbox event shape with generic `DaemonSignalEnvelope`.
4. Do not preserve a message-shaped daemon delivery path as compatibility.
5. Keep Task TUI on local runtime notifications; do not convert it to daemon signal.
6. Do not implement message durable object rewrite, offline signal queue, subscription engine, workflow engine, plugin system, or broadcast path.
7. Be strict about service resource lifecycle:
   - lifecycle tests use fake process start/stop where possible;
   - socket tests start in-process servers with explicit close and join;
   - broad suite runs only after focused lifecycle tests pass.

Implementation loop:

1. Read the development plan.
2. Execute Task 1 through Task 7 in order.
3. If a test failure exposes a wrong plan assumption, fix the plan and implementation together.
4. Before declaring completion, run:

```bash
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_central_daemon_service.py -q
python3 -m pytest tests/test_runtime_actor_profile.py -q
python3 -m pytest tests/test_daemon_communication_boundary.py -q
python3 -m pytest tests/test_daemon_*.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_runtime_broker.py -q
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

Completion standard:

- all focused tests pass;
- full test suite passes;
- residual process check is clean for test-owned daemon processes;
- review confirms daemon base code no longer understands `message_id`, `message.available`, `from_actor_address`, or `to_actor_address` as mailbox event fields;
- review confirms `MessageAvailableHandler` owns `payload.message_id` validation and target-side read prompt behavior.

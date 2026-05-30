# New Daemon Communication Upgrade Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Objective: execute the daemon communication upgrade plan until tests pass and review accepts the result.

Required inputs:

- Architecture memo: `docs/memo/2026-05-29-new-daemon-communication-architecture.html`
- Test plan: `docs/spec/2026-05-30-new-daemon-communication-upgrade-test-plan.md`
- Development plan: `docs/spec/2026-05-30-new-daemon-communication-upgrade-development-plan.md`
- Resource lifecycle lesson: `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Execution rules:

1. Work only in `fea-daemon`; do not touch `main`.
2. Use TDD for behavior changes:
   - write the failing test;
   - run it and confirm the intended failure;
   - implement the direct change;
   - rerun the focused test.
3. Do not preserve the old daemon notification path as compatibility.
4. The final daemon path must use:
   - central daemon independent process;
   - actor_profile `RuntimeActorAddress`;
   - central daemon registry as single writer;
   - explicit actor-address reachability;
   - mailbox socket delivery;
   - `message.available` reference-only event;
   - target instance ActionGateway trigger.
5. Do not implement the full message tool business rewrite in this daemon task.
6. Be strict about service resource lifecycle:
   - lifecycle tests use fake process start/stop where possible;
   - socket tests start in-process servers with explicit close and join;
   - broad test suite runs only after focused service lifecycle tests pass.
7. Keep the implementation simple and concrete. Do not add plugin systems, workflow engines, or generic event-bus abstractions.

Implementation loop:

1. Read the development plan.
2. Execute Task 1 through Task 9 in order.
3. Keep the checklist current in the development plan if you edit it during execution.
4. If a test failure exposes a wrong plan assumption, fix the plan and the implementation together.
5. Before declaring completion, run:

```bash
python3 -m pytest tests/test_central_daemon_service.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py tests/test_daemon_communication_boundary.py -q
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_core_decoupling.py tests/test_daemon_service_contract.py tests/test_task_checkout_handler.py tests/test_instance_daemon_entrypoint.py -q
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_message_env_tool.py tests/test_runtime_broker.py -q
git diff --check
python3 -m pytest tests -q
pgrep -fl "central_daemon.py|instance_daemon.py" || true
```

Completion standard:

- all focused tests pass;
- full test suite passes;
- residual process check is clean for test-owned daemon processes;
- review confirms no old direct file append, fuzzy `to_buddy` daemon delivery, or `ambiguous_online_actor` daemon status remains.

# Phase 2 Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Implement the daemon runtime handler rebuild from:

- `docs/memo/2026-06-03-daemon-runtime-handler-rebuild-task.md`
- `docs/spec/2026-06-03-daemon-runtime-handler-test-plan.md`
- `docs/spec/2026-06-03-daemon-runtime-handler-development-plan.md`

Rules:

1. Stay on branch/worktree `fea-daemon`; do not touch main.
2. Use the shortest verified forward path; do not keep compatibility aliases or dual old/new daemon paths.
3. Use TDD for behavior changes: update/write the focused test, run it to see the expected failure, implement the smallest direct change, then rerun it green.
4. Be careful with resource lifecycle. Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`; do focused in-process tests before broad service-starting tests.
5. Do not add plugin loading, workflow engines, subscription systems, event buses, or generic action systems.
6. Completion requires all focused tests, source audits, `git diff --check`, collection, and broader launcher validation to pass, followed by a review of the final diff against the memo done criteria.

Primary loop:

```bash
python3 -m pytest tests/test_daemon_core.py tests/test_daemon_service_contract.py tests/test_daemon_trigger_router.py -q
python3 -m pytest tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py -q
python3 -m pytest tests/test_task_checkout_handler.py tests/test_message_available_handler.py -q
python3 -m pytest tests/test_instance_daemon_entrypoint.py tests/test_central_daemon_service.py tests/test_message_env_tool.py tests/test_runtime_actor_profile.py -q
rg -n 'ActionGateway|FakeActionGateway|actions_factory|record_daemon_action|daemon_actions|daemon_action_ids|last_action_turn_id|_action_status_payload' tools/launcher tests/test_daemon*.py tests/test_task_checkout_handler.py tests/test_message_available_handler.py
rg -n 'message\.parent_required|require_side_thread' tools/launcher/daemon_mailbox.py tests/test_daemon_mailbox.py tests/test_daemon_core_decoupling.py
rg -n 'mailbox\.local_trigger\(type="message\.parent_required"|FakeActionGateway' tools/launcher/message_available_handler.py tests/test_message_available_handler.py
python3 -m pytest --collect-only -q tests
git diff --check
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Final review:

- Re-read the memo done criteria.
- Check every explicit removal has no daemon-layer residue.
- Check every dependent module listed in the memo was either updated or verified unaffected.
- Confirm no old status/actions fallback remains.
- Confirm verification commands passed with fresh output.


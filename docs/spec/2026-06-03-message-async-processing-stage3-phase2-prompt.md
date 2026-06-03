# Phase 2 Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Implement Message Async Processing Stage 3 from:

- `docs/memo/2026-06-03-message-async-processing-stage3-task.md`
- `docs/spec/2026-06-03-message-async-processing-stage3-test-plan.md`
- `docs/spec/2026-06-03-message-async-processing-stage3-development-plan.md`

Rules:

1. Stay on branch/worktree `fea-daemon`; do not touch main.
2. Use the shortest verified forward path; do not keep compatibility aliases, role-selector conversation, or old/new dual paths.
3. Use TDD for behavior changes: update/write the focused test, run it to see the expected failure, implement the smallest direct change, then rerun it green.
4. Be careful with resource lifecycle. Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`; run focused in-process tests before broad service-starting tests.
5. Do not add plugin loading, workflow engines, subscription systems, event buses, generic action systems, model-facing parent-handoff tools, or daemon mailbox `message.parent_required`.
6. Completion requires focused tests, source audits, `git diff --check`, collection, broader relevant validation, and final diff review against the memo.

Primary loop:

```bash
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_message_env_tool.py -q
rg -n 'message\\.parent_required|mailbox\\.local_trigger|parent_thread_id|side_thread_id|message__list' tools/launcher/message_available_handler.py tests/test_message_available_handler.py
rg -n 'target_role|\"role\".*conversation|conversation.*role selector|message_conversation_role_selector' scripts/env/domain/messages.py scripts/env/tools/message tests/test_message_env_tool.py buddyswitch/skills/shared/message-tool/SKILL.md
rg -n 'message\\.get|message\\.mark|message__get|message__mark' scripts/env tools tests buddyswitch/skills/shared/message-tool/SKILL.md
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_context_binding_env_tool.py tests/test_env_native_mcp_projection.py -q
python3 -m pytest --collect-only -q tests
git diff --check
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Final review:

- Re-read the Stage 3 memo done criteria.
- Check every required tool addition, tool removal, prompt path, disposition transition, and parent-required runtime entry.
- Check every explicit removal has no residue: no `seen`, no `message.conversation(role=...)`, no `message.parent_required`, no handler-owned prompt business text, and no daemon mailbox handoff path.
- Confirm every focused and broad verification command passed with fresh output.

# Phase 2 Execution Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`

Implement the Message Stage 3 findings follow-up from:

- `docs/memo/2026-06-03-message-stage3-findings-followup-task.md`
- `docs/spec/2026-06-03-message-stage3-findings-followup-test-plan.md`
- `docs/spec/2026-06-03-message-stage3-findings-followup-development-plan.md`

Rules:

1. Stay in worktree branch `fea-daemon`; do not touch main.
2. Use SHARP: shortest verified path, no compatibility aliases, no transition framework, no generic
   retry framework.
3. Use TDD for behavior changes: write or update the focused test, run it and see the expected
   failure, implement the smallest direct change, then rerun it green.
4. Keep tests resource-safe. Follow
   `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`; patch retry sleep in focused
   tests and run service-starting tests only after focused tests pass.
5. Preserve the public `message.mark` disposition boundary: only `absorbed` and `needs_parent`.
   `replied` remains owned by `message.send(reply_to=...)`.
6. Completion requires focused tests, source audits, collection, `git diff --check`, launcher
   regression, and final review against the memo.

Primary loop:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
rg -n 'target_actor\.actor_id == source_actor_address\.actor_id|actor_address\["actor_id"\] == active_actor_address\.actor_id|message was marked needs_parent, but parent prompt submission failed' scripts/env/domain/messages.py scripts/env/tools/message/_impl.py
rg -n 'partial|indeterminate|outbox|workflow engine|transaction framework' scripts/env/domain/messages.py scripts/env/tools/message/_impl.py scripts/env/tools/message/tool.py
python3 -m pytest --collect-only -q tests
git diff --check
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Final review:

- Re-read the memo done criteria.
- Check full `ActorAddress` equality is used for self-send, self-conversation, and contacts
  sendability.
- Check reply success and failure responses state durable reply effects and original final
  disposition.
- Check `needs_parent` submits the parent prompt before saving disposition and reports both failure
  modes accurately.
- Check tool descriptions are host-decidable without reading AGENTS prose or implementation code.
- Confirm every focused and broad verification command passed with fresh output.

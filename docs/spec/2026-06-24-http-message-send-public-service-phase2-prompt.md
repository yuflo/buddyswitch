# Phase 2 Prompt: HTTP Message Send Public Service

Work in `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.

Read first:

- `AGENTS.md`
- `docs/memo/2026-06-24-http-message-send-public-service.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/spec/2026-06-24-http-message-send-public-service-test-plan.md`
- `docs/spec/2026-06-24-http-message-send-public-service-development-plan.md`

Execute the development plan with SHARP:

1. Use TDD. Add the focused failing test for each behavior before implementation.
2. Keep the change direct: create `scripts/env/services/messages.py` as the public send service and remove the old web HTTP send surface instead of wrapping it.
3. Do not add compatibility for `POST /api/instances/<actor_id>/messages`.
4. Do not add daemon, central-daemon, mailbox, or daemon-client web-user special cases.
5. Prefer fake daemon reachability/delivery tests. Do not run broad service-starting suites until focused tests and lifecycle cleanup are clean.
6. After each meaningful change block, run the focused test named in the plan.
7. If a test fails unexpectedly, stop and investigate root cause before changing code.
8. Completion requires all focused tests, UI contract tests, boundary scans, and final review to pass.

Final verification commands:

```bash
python -m pytest tests/test_message_service.py -q
python -m pytest tests/test_message_env_tool.py -q
python -m pytest tests/test_web_user_actor.py -q
python -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js
node --test tests/web_management_ui_state.test.js
python -m pytest tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py -q
rg "act-user-local|web_user|web-user|send_web_message|role_id.*user" tools/launcher/daemon_core.py tools/launcher/daemon_mailbox.py tools/launcher/daemon_triggers.py tools/launcher/central_daemon_core.py scripts/env/tool_runtime/daemon_client.py
rg "env\\.repos\\.messages|create_message|save_message|delete_message|message\\.available|signal_id|daemon_client\\.deliver_signal" tools/launcher/web_management.py
rg "/api/instances/.*/messages|/messages'|/messages\"" tools/launcher/assets/web-management tools/launcher/web_management.py README.md
rg "from env\\.tools\\.message import _impl|message_impl\\.send_message_from_actor" tools scripts tests
```

Review acceptance:

- public message service owns send semantics;
- `message.send` uses the service;
- web-user send uses the service;
- HTTP accepts only `actor_id + content`;
- HTTP sender is always `act-user-local`;
- old instance message route is removed;
- web UI calls `/api/messages/send`;
- target actor receives normal `message.available`;
- actor replies to `act-user-local` remain deliverable to the sink;
- daemon infrastructure remains generic;
- tests and scans pass without resource residue.

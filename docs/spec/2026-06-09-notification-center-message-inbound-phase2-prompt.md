# Notification Center Message Inbound Phase 2 Prompt

Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/nc`

Implement NC plus message inbound integration from:

- `docs/spec/2026-06-09-notification-center-message-inbound-test-plan.md`
- `docs/spec/2026-06-09-notification-center-message-inbound-development-plan.md`
- `docs/memo/2026-06-09-notification-center-message-inbound-tasks.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

Rules:

1. Stay in the `nc` worktree; do not touch main.
2. Follow sharp-forward: add the shortest clear NC registration path. Do not add an actor-facing
   notification inbox, notification lifecycle tools, compatibility wrappers, a plugin framework, or
   an `nc.notification` wrapper event.
3. Use tests first. Add focused NC and daemon wiring tests, run them, and verify they fail before
   implementation.
4. Keep message source-owned: `message.available`, `message_id`, `MessageAvailableHandler`,
   parent/side routing, prompt text, `message.get`, `message.send`, `message.mark`, `absorbed`,
   `replied`, and `needs_parent` semantics stay in message code.
5. NC may own only registration validation, handler construction, subscription listing, and daemon
   notify plumbing metadata.
6. Do not redesign Track, Comment, Artifact, or future source integrations.
7. Keep verification focused. Do not run broad daemon/app-server/browser suites unless resource
   lifecycle cleanup is proven per the bitter lesson document.
8. Completion requires focused tests, compile checks, residue scans, and final review to pass.

Required implementation loop:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_notification_center -v
```

First expected result: fail because NC/message inbound modules do not exist yet.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  -v
```

First expected result: fail because daemon entrypoint and core have not been wired through NC yet.

Final focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  tests.test_notification_center \
  tests.test_instance_daemon_entrypoint \
  tests.test_daemon_core_decoupling \
  tests.test_daemon_communication_boundary \
  tests.test_message_available_handler \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox \
  tests.test_env_tool_schema_contract \
  tests.test_env_native_mcp_projection \
  tests.test_message_env_tool \
  -v
```

Compile check:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  tools/launcher/notification_center.py \
  tools/launcher/message_inbound.py \
  tools/launcher/instance_daemon.py \
  tools/launcher/daemon_core.py
```

Residue scan:

```bash
rg -n "notification\\.mark|notification\\.archive|notification\\.needs_parent|notification__mark|notification__archive|notification__needs_parent|nc\\.notification" \
  tools scripts tests buddyswitch docs/spec/2026-06-09-notification-center-message-inbound-*.md
```

Expected for the residue scan: no production hits. Hits in the spec files or negative assertions are
acceptable only when they are explicitly testing forbidden behavior.

Final review:

- Confirm NC is registration/subscription/handler-construction infrastructure only.
- Confirm `message.available` is registered through message-owned inbound code.
- Confirm `MessageAvailableHandler` remains the handler that owns execution.
- Confirm actor-visible message behavior did not change.
- Confirm no actor-facing `notification.*` tools and no `nc.notification` wrapper exist.
- Confirm NC imports no message repo/domain internals.
- Confirm no broad service-starting suite was run without lifecycle proof.

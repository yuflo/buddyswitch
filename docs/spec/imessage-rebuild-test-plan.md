# iMessage Rebuild Test Plan

Date: 2026-06-28

## Baseline Commands

Current focused baseline:

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Observed result on 2026-06-28:

```text
82 passed, 51 subtests passed in 126.11s (0:02:06)
```

Current browser/Web UI baseline:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Observed result on 2026-06-28:

```text
all checks passed
```

## Stage 0: Fact Baseline And Entry Freeze

### New Tests

None. This stage is read-only documentation and current-state verification.

### Adjusted Tests

None.

### End-To-End Contract Tests To Keep

- `tests/test_im_external_reply_loop.py::ImExternalReplyLoopTests::test_external_send_actor_reply_to_external_visible_once_without_cursor`

### Residue Scan

Run to prove the current Stage 1 problem exists:

```bash
rg -n "send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition|create_external_connection|authenticate_external_connection_key" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Expected before Stage 1 implementation: hits in all three files.

### Verification Commands

```bash
command -v imsg
imsg --help
imsg status
imsg chats --help
imsg history --help
imsg send --help
imsg watch --help
python -m pytest tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

### Passing Standard

- `imsg` is installed.
- `imsg status` reports basic send/receive/history available.
- Help exposes `chats`, `history`, `send`, and `watch`.
- Baseline Python and Node tests pass.
- Residue scan has the expected current hits.

## Stage 1: Rebuild External IM Session

### New Tests

Add `tests/test_external_im_session.py`:

- `test_session_create_auth_send_event_conversation_and_disposition_flow`
  exercises the new session boundary without HTTP.
- `test_session_list_actors_returns_identity_projection`
  verifies actor list mapping and invalid actor rows are ignored.
- `test_session_rejects_missing_or_unreachable_actor_identity`
  verifies target resolution errors stay at the session boundary.
- `test_session_reads_actor_reply_once_without_client_cursor`
  verifies connection event cursor semantics remain server-owned.

Add a residue test, either in `tests/test_im_web_management_projection.py` or
`tests/test_external_im_session.py`:

```text
HTTP/Web projection files must not import env.services.messages or call the
Central IM external-session methods directly.
```

This test must fail before implementation because current files call those
methods directly.

### Adjusted Tests

- Update `tests/test_im_http_router.py` only for constructor/session wiring.
  Public `/api/im/*` assertions should remain the same.
- Update `tests/test_web_management.py` only for constructor/session wiring.
  Public `/api/web/im/*` assertions should remain the same.
- Update `tests/test_im_external_reply_loop.py` only if `ImHttpRouter`
  construction changes.

### End-To-End Contract Tests To Keep

- `tests/test_im_external_reply_loop.py::ImExternalReplyLoopTests::test_external_send_actor_reply_to_external_visible_once_without_cursor`
- `tests/test_im_external_reply_loop.py::ImExternalReplyLoopTests::test_wake_bridge_reaches_real_mailbox_socket_and_im_handler`

### Residue Scan

Before implementation, this must fail with hits:

```bash
rg -n "message_service\\.(create_external_connection|authenticate_external_connection_key|send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition)" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

After implementation, it must return no hits.

Also scan imports:

```bash
rg -n "from env\\.services import messages|import messages as message_service" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Expected after implementation: no hits in these projection files.

### Verification Commands

Focused Python:

```bash
python -m pytest tests/test_external_im_session.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Web UI:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

### Passing Standard

- New red test or residue check was observed failing before production code
  changes.
- Focused Python tests pass.
- Node Web UI tests pass.
- Residue scans return no hits.

## Stage 2: Projection Contract Tightening

### New Tests

Create or extend `tests/test_external_im_projection_contract.py` with tests
that use fake session objects where useful:

- Integration router maps missing auth to HTTP 401 without invoking session
  product methods.
- Integration router maps request body/query values to session calls and maps
  session payloads to HTTP status.
- Web BFF owns browser session response and never returns `connection_key`.
- Web BFF rejects browser `cursor`.
- Web BFF requires actor `identity_id` for events and direct conversation.
- Web BFF hydrates browser event DTOs with messages through the session
  boundary.

### Adjusted Tests

- Keep existing behavior tests in `tests/test_im_http_router.py` and
  `tests/test_web_management.py`.
- Move source-boundary assertions into one focused projection contract test if
  duplication grows.

### End-To-End Contract Tests To Keep

- Keep the external reply-loop acceptance test. Projection tests cannot replace
  it.

### Residue Scan

Automate or run:

```bash
rg -n "message_service\\.(create_external_connection|authenticate_external_connection_key|send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition)" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
rg -n "/api/messages/send|/api/im/external-participants|/api/im" tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js
```

Expected:

- no direct Central IM external-session calls in HTTP/Web projection files;
- browser JS has no `/api/im` calls;
- old routes appear only in negative assertions if present.

### Verification Commands

```bash
python -m pytest tests/test_external_im_projection_contract.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py -q
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

### Passing Standard

- Projection contract tests pass.
- Existing route behavior tests still pass.
- Residue scans are no-hit except explicit negative assertions.

## Stage 3: iMessage Channel Adapter MVP

### New Tests

Create `tests/test_imessage_bridge.py`:

- `test_bridge_fails_fast_when_target_actor_is_not_reachable`
- `test_inbound_ignores_messages_from_me`
- `test_inbound_rejects_sender_not_in_allowlist`
- `test_inbound_dedupes_by_rowid_or_guid`
- `test_inbound_posts_allowlisted_text_to_api_im_messages`
- `test_outbound_sends_actor_reply_once_and_records_event_id`
- `test_restart_does_not_resend_recorded_outbound_event`
- `test_bridge_source_does_not_import_central_im_internals`

Modify `tests/test_buddyswitch_launcher.py`:

- Add command dispatch coverage for `buddyswitch-codex imessage bridge`.
- Add unknown subcommand and missing option errors if the launcher test style
  already supports similar cases.

### Adjusted Tests

None in Central IM Core unless source scans reveal iMessage leakage.

### End-To-End Contract Tests To Keep

- Keep the existing external reply-loop test.
- Add a bridge-level fake-HTTP/fake-imsg integration test that proves:

```text
fake imsg inbound row -> bridge POST /api/im/messages
fake /api/im/events actor reply -> bridge imsg send to same chat/sender
```

### Residue Scan

Adapter isolation:

```bash
rg -n "env\\.services\\.messages|env\\.repos\\.messages|send_im_message|send_external_connection_message|read_external_connection_events" tools/launcher/imessage_bridge.py
```

Expected: no hits.

Central core iMessage pollution:

```bash
rg -n "iMessage|imessage|imsg|chat_id|chat_identifier|chat_guid|rowid|guid|allowlist|is_from_me" scripts/env/services/messages.py scripts/env/repos/messages.py scripts/env/tool_runtime/im_client.py scripts/env/tools/message/_impl.py tools/launcher/im_wake_handler.py
```

Expected: no hits, except generic words if explicitly justified by code context.

### Verification Commands

```bash
python -m pytest tests/test_imessage_bridge.py tests/test_buddyswitch_launcher.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

### Passing Standard

- Bridge tests pass.
- Launcher dispatch tests pass.
- Adapter isolation scans pass.
- Existing Central IM and integration route tests pass.

## Stage 4: End-To-End Smoke

### New Tests

No new unit tests required if Stage 3 bridge integration tests cover fake
inbound/outbound flow. Add a smoke script only if it improves repeatability
without pretending to be a real iMessage run.

### Adjusted Tests

None.

### End-To-End Contract Tests To Keep

Run:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_imessage_bridge.py -q
```

Manual smoke contract:

```text
allowlisted iPhone sender sends text
  -> Mac imsg watch sees inbound row
  -> bridge POSTs to /api/im/messages
  -> actor wakes and replies
  -> bridge reads /api/im/events and sends through imsg
  -> iPhone sees reply in same chat
```

### Residue Scan

Same adapter isolation and Central IM pollution scans from Stage 3.

### Verification Commands

```bash
./buddyswitch-codex web --port 8765
./buddyswitch-codex imessage bridge --server http://127.0.0.1:8765 --target-identity-id <actor_identity_id> --allow-sender <sender>
```

Then send one real text from the allowlisted iPhone sender.

### Passing Standard

- Real smoke succeeds and is recorded, or an external macOS/Apple/imsg blocker
  is recorded with enough detail to distinguish it from BuddySwitch code
  failure.
- Automated acceptance tests still pass.

## Stage 5: Residue Cleanup And Documentation Closeout

### New Tests

Add or extend a source-scan test for live surface wording if not already covered:

- no live surface describes `/api/im/*` and `/api/web/im/*` as separate product
  implementations;
- no live surface tells iMessage to call Central IM Core directly;
- no live surface suggests a generic channel plugin framework for this MVP.

### Adjusted Tests

- Update docs/source assertions in `tests/test_im_web_management_projection.py`
  or a new closeout test.

### End-To-End Contract Tests To Keep

Run the final relevant set:

```bash
python -m pytest tests/test_external_im_session.py tests/test_external_im_projection_contract.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py tests/test_imessage_bridge.py tests/test_buddyswitch_launcher.py -q
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

### Residue Scan

Memo-required live surfaces:

```bash
rg -n "two IM product implementations|separate IM product|Web IM routes should delegate to the message service|iMessage.*Central IM Core|Central IM.*iMessage|channel plugin|plugin framework|external-participants|/api/messages/send" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py tools/launcher/assets/web-management/app.js tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/web_management_ui_contract.test.js docs/arch/web-interface-call-architecture.md
```

Expected: no hits, except negative assertions explicitly checking retired
routes.

### Passing Standard

- Full relevant Python and Node verification passes.
- Scoped residue scan passes.
- `docs/arch/web-interface-call-architecture.md` names `External IM Session` as
  the shared semantic layer.
- Stage acceptance file lists completed stages, changed files, deleted old
  paths, tests, commands, and remaining risks.


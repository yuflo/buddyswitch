# iMessage Rebuild Context Audit

Date: 2026-06-28

## Goal

This audit records the current state before implementation of
`docs/memo/2026-06-28-imessage-rebuild-forward-plan.md`. It is intentionally
read-only for business code.

The current bottleneck is that `/api/im/*` and `/api/web/im/*` both still own
External IM product semantics directly. The next implementation phase must
replace that dual path with one `External IM Session` application boundary.

## Sources Read

- `AGENTS.md`
- `docs/memo/2026-06-28-imessage-rebuild-forward-plan.md`
- `docs/memo/2026-06-28-imessage-interface-brief.html`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- Current IM/Web code and tests listed below.

## Governing Constraints

- Product semantics must sit below interface projections.
- HTTP, Web, CLI, and channel adapters are projections, not product owners.
- A semantic replacement is incomplete while live surfaces still teach the old
  model.
- Residue scans must be scoped to live surfaces and stale phrases, not broad
  repository searches.
- The end-to-end contract remains:

```text
iPhone user sends iMessage
  -> local Mac bridge posts to BuddySwitch
  -> target actor wakes and replies through Central IM
  -> bridge sends the reply back to the same iMessage sender/chat
```

## Current iMessage Tooling Evidence

Current local `imsg` state:

- `command -v imsg` returned `/opt/homebrew/bin/imsg`.
- `imsg --help` reported `imsg 0.11.1`.
- `imsg status` reported `Basic features (send, receive, history): Available`.
- `imsg chats --help`, `imsg history --help`, `imsg send --help`, and
  `imsg watch --help` all exposed the required command surfaces.

This audit did not send a real iMessage or run a blocking watch. Real send/watch
validation belongs to the Stage 4 smoke gate with an allowlisted sender.

The older feasibility brief says the local machine did not have `imsg`
installed. That is stale relative to the current command evidence above; keep
the brief as feasibility context, not as current-state truth.

## Current Process Surface

- `./buddyswitch-codex web --port 8765` already exists and runs
  `tools/launcher/web_management.py` after ensuring the central daemon.
- There is no `./buddyswitch-codex imessage bridge` command yet.
- The MVP user-visible process target is therefore:
  - existing Web server command;
  - new iMessage bridge command in a later phase.

## Current Live IM Surfaces

Integration External IM HTTP API:

- `tools/launcher/im_http_router.py`
- Routes:
  - `POST /api/im/connections`
  - `GET /api/im/actors`
  - `POST /api/im/messages`
  - `GET /api/im/events`
  - `GET /api/im/conversations/direct`
  - `GET /api/im/messages/{id}`
  - `GET /api/im/messages/{id}/replies`
  - `PATCH /api/im/messages/{id}/disposition`

Web Console IM BFF:

- `tools/launcher/web_management.py`
- `tools/launcher/web_im_identity.py`
- `tools/launcher/assets/web-management/app.js`
- Routes:
  - `GET /api/web/im/session`
  - `POST /api/web/im/messages`
  - `GET /api/web/im/events`
  - `GET /api/web/im/conversations/direct`

Central IM Core and actor runtime surfaces:

- `scripts/env/services/messages.py`
- `scripts/env/repos/messages.py`
- `scripts/env/tool_runtime/im_client.py`
- `scripts/env/tools/message/_impl.py`
- `tools/launcher/im_wake_handler.py`
- `tools/launcher/message_inbound.py`

Architecture documentation live surface:

- `docs/arch/web-interface-call-architecture.md`

## Current Central IM Ownership

`scripts/env/services/messages.py` currently owns Central IM model behavior:

- `create_external_connection`
- `authenticate_external_connection_key`
- `send_im_message`
- `send_external_connection_message`
- `read_external_connection_events`
- `get_im_message`
- `list_im_replies`
- `get_im_direct_conversation`
- `update_im_disposition`

`scripts/env/repos/messages.py` owns persisted IM objects under runtime state:

- participants
- connections
- conversations
- messages
- events
- message states

Actor wake stays in Central IM/runtime territory:

- `send_im_message` creates `im.message.created` wake payloads.
- `tools/launcher/im_wake_handler.py` converts that payload into actor runtime
  prompts using message ids only.

This is the layer the new `External IM Session` boundary should call. HTTP and
Web projections should not call these Central IM external-session methods
directly after Stage 1.

## Current Dual-Track Problem

Current direct-call residue scan:

```bash
rg -n "send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition|create_external_connection|authenticate_external_connection_key" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Current hits:

- `tools/launcher/im_http_router.py` directly calls:
  - `message_service.create_external_connection`
  - `message_service.authenticate_external_connection_key`
  - `message_service.send_external_connection_message`
  - `message_service.read_external_connection_events`
  - `message_service.get_im_direct_conversation`
  - `message_service.list_im_replies`
  - `message_service.update_im_disposition`
  - `message_service.get_im_message`
- `tools/launcher/web_management.py` directly calls:
  - `message_service.send_external_connection_message`
  - `message_service.read_external_connection_events`
  - `message_service.get_im_message`
  - `message_service.get_im_direct_conversation`
- `tools/launcher/web_im_identity.py` directly calls:
  - `message_service.create_external_connection`
  - `message_service.authenticate_external_connection_key`

Conclusion: the target `External IM Session` layer does not exist yet. Both
HTTP route families still hold product semantics.

## Current Web BFF Shape

`tools/launcher/web_management.py` already owns browser-only behavior that
should remain in the Web BFF:

- it hides `connection_key` from browser responses;
- it owns the `/api/web/im/session` browser session response;
- it rejects browser-supplied event cursors;
- it requires `identity_id` for browser event/conversation scope;
- it turns a missing direct conversation into an empty browser payload.

It also currently owns behavior that should move to `External IM Session`:

- external connection send;
- external connection event read;
- direct conversation read;
- actor identity to Central IM target resolution;
- message fetch used to hydrate event DTOs.

After Stage 1, Web should keep only browser session ownership, query/body
mapping, and DTO shaping.

## Current Test Coverage

Focused baseline command:

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Result:

```text
82 passed, 51 subtests passed in 126.11s (0:02:06)
```

Focused Web UI command:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
all checks passed
```

Important existing tests:

- `tests/test_im_product_core.py` covers Central IM persistence, direct
  conversation, replies, disposition, external connection event cursors, and
  reply visibility.
- `tests/test_im_http_router.py` covers the `/api/im/*` integration surface.
- `tests/test_web_management.py` covers the `/api/web/im/*` Web BFF surface and
  browser token hiding.
- `tests/test_im_web_management_projection.py` covers old route removal and
  Web not exposing lower `/api/im/*` routes.
- `tests/test_im_external_reply_loop.py` covers external HTTP sender -> actor
  reply -> external event visibility, plus wake bridge behavior.
- `tests/web_management_ui_contract.test.js` verifies the browser JS uses only
  `/api/web/im/*`, not `/api/im/*`.

## Existing End-To-End Contract Coverage

`tests/test_im_external_reply_loop.py::ImExternalReplyLoopTests::test_external_send_actor_reply_to_external_visible_once_without_cursor`
already proves this internal contract:

```text
external HTTP client sends to actor
  -> Central IM wakes target actor
  -> actor replies with message.send(reply_to)
  -> external HTTP client reads reply event exactly once
```

This is necessary but not sufficient for the final iMessage MVP. Stage 4 still
needs a real Mac `imsg` smoke path or a recorded environment-specific blocker.

## Live Documentation Residue

`docs/arch/web-interface-call-architecture.md` currently says Web IM should
delegate to the message service. That describes the current code but not the
target architecture. Stage 5 must update it to name `External IM Session` as the
shared semantic boundary while keeping `/api/web/im/*` as a browser projection.

## Current Bottleneck

The immediate bottleneck is Stage 1:

```text
HTTP/Web projection files directly own External IM product semantics.
```

The shortest validated path is:

1. Add a scoped residue/contract test that fails on direct `message_service`
   external-session calls from the HTTP/Web projection files.
2. Add `External IM Session` as one concrete application boundary.
3. Move actor target resolution, connection authentication, send, events,
   conversation, message fetch, replies, and disposition behind that boundary.
4. Keep `/api/im/*` and `/api/web/im/*` response contracts green.
5. Run the focused tests and no-hit residue scan.


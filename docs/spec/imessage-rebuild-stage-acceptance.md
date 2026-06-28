# iMessage Rebuild Stage Acceptance

Date: 2026-06-28

## Stage 0: Fact Baseline And Entry Freeze

Status: accepted.

### Actual Changes

- Created `docs/spec/imessage-rebuild-context-audit.md`.
- Created `docs/spec/imessage-rebuild-development-plan.md`.
- Created `docs/spec/imessage-rebuild-test-plan.md`.
- Created this acceptance record.

No business code was changed.

### Verification Commands And Results

Command:

```bash
command -v imsg
```

Result:

```text
/opt/homebrew/bin/imsg
```

Command:

```bash
imsg --help
```

Result:

```text
imsg 0.11.1
Commands include chats, history, watch, send, status, and rpc.
```

Command:

```bash
imsg status
```

Result:

```text
Basic features (send, receive, history): Available
Advanced features (typing, read receipts): Not available
```

Command:

```bash
imsg chats --help
imsg history --help
imsg send --help
imsg watch --help
```

Result:

```text
All four commands exposed usable help and JSON-capable or stream-capable command surfaces.
```

Command:

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Result:

```text
82 passed, 51 subtests passed in 126.11s (0:02:06)
```

Command:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
all checks passed
```

Command:

```bash
rg -n "send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition|create_external_connection|authenticate_external_connection_key" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Result:

```text
Expected Stage 1 red residue exists.
Hits were found in tools/launcher/im_http_router.py, tools/launcher/web_management.py, and tools/launcher/web_im_identity.py.
```

### Live Surfaces Locked

- Integration External IM HTTP API: `tools/launcher/im_http_router.py`
- Web Console IM BFF: `tools/launcher/web_management.py`
- Web server-owned IM session: `tools/launcher/web_im_identity.py`
- Browser UI client: `tools/launcher/assets/web-management/app.js`
- Actor message tool: `scripts/env/tools/message/_impl.py`
- Actor IM client: `scripts/env/tool_runtime/im_client.py`
- Wake handler: `tools/launcher/im_wake_handler.py`
- Current architecture doc: `docs/arch/web-interface-call-architecture.md`

### Acceptance Decision

Stage 0 acceptance criteria are met:

- `docs/memo/2026-06-28-imessage-interface-brief.html` remains as feasibility
  evidence.
- `#1` is the Integration External IM HTTP API, `/api/im/*`.
- `#2` is the Web Console IM BFF, `/api/web/im/*`.
- Current relation is recorded: both are intended projections, but current code
  still implements product semantics in both route families.
- User-visible startup target is recorded as Web server plus iMessage bridge.
- iMessage adapter code has not been started.

### Remaining Risk

`imsg` basic features are available, but no real send/watch smoke was run in
Stage 0. That belongs to Stage 4 with an allowlisted sender and a running
bridge.

## Stage 1: Rebuild External IM Session

Status: accepted.

### Red Gate

Added:

- `tests/test_im_web_management_projection.py::ImWebManagementProjectionTests::test_http_and_web_projections_do_not_own_external_im_session_semantics`
- `tests/test_external_im_session.py`

Red command:

```bash
python -m pytest tests/test_im_web_management_projection.py::ImWebManagementProjectionTests::test_http_and_web_projections_do_not_own_external_im_session_semantics -q
```

Red result:

```text
20 failed, 1 passed, 10 subtests passed
```

The failures were expected direct-call hits in:

- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tools/launcher/web_im_identity.py`

Red session-boundary command:

```bash
python -m pytest tests/test_external_im_session.py -q
```

Red result:

```text
ImportError: cannot import name 'external_im_session' from 'env.services'
```

### Actual Changes

Created:

- `scripts/env/services/external_im_session.py`
- `tests/test_external_im_session.py`

Modified:

- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tools/launcher/web_im_identity.py`
- `tests/test_im_web_management_projection.py`

### Deleted Or Replaced Old Paths

Replaced direct Central IM external-session calls from HTTP/Web projection files:

- `message_service.create_external_connection`
- `message_service.authenticate_external_connection_key`
- `message_service.send_external_connection_message`
- `message_service.read_external_connection_events`
- `message_service.get_im_direct_conversation`
- `message_service.get_im_message`
- `message_service.list_im_replies`
- `message_service.update_im_disposition`

No route family was deleted. `/api/im/*` and `/api/web/im/*` remain as consumer
surfaces.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_external_im_session.py -q
```

Result:

```text
4 passed
```

Command:

```bash
python -m pytest tests/test_external_im_session.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Result:

```text
87 passed, 81 subtests passed in 126.15s (0:02:06)
```

Command:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
all checks passed
```

Command:

```bash
rg -n "message_service\\.(create_external_connection|authenticate_external_connection_key|send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition)" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Result:

```text
no hits
```

Command:

```bash
rg -n "from env\\.services import messages|import messages as message_service" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Result:

```text
no hits
```

Command:

```bash
python -m pytest tests/test_im_web_management_projection.py::ImWebManagementProjectionTests::test_http_and_web_projections_do_not_own_external_im_session_semantics -q
```

Result:

```text
1 passed, 30 subtests passed
```

### Acceptance Decision

Stage 1 acceptance criteria are met:

- `ExternalImSession` is now the only HTTP/Web path that calls Central IM
  external-session methods.
- `/api/im/*` behavior tests pass.
- `/api/web/im/*` behavior tests pass.
- Web UI contract/state tests pass.
- Scoped residue scans return no hits in HTTP/Web projection files.

### Remaining Risk

`ExternalImSession` is now concrete and tested, but Stage 2 still needs tighter
projection-contract tests so future route changes do not grow product semantics
back into HTTP/Web files.

## Stage 2: Projection Contract Tightening

Status: accepted.

### Red Gate

Added:

- `tests/test_external_im_projection_contract.py`

Red command:

```bash
python -m pytest tests/test_external_im_projection_contract.py -q
```

Red result:

```text
2 failed, 2 passed
TypeError: ImHttpRouter.__init__() got an unexpected keyword argument 'im_session'
```

This was expected. The Integration router could not yet be tested as a pure
HTTP projection with a fake session boundary.

### Actual Changes

Created:

- `tests/test_external_im_projection_contract.py`

Modified:

- `tools/launcher/im_http_router.py`

### Deleted Or Replaced Old Paths

No additional route or helper paths were deleted. Stage 2 added a test-only
session injection point to the Integration router so projection mapping can be
tested without calling Central IM internals.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_external_im_projection_contract.py -q
```

Result:

```text
4 passed
```

Command:

```bash
python -m pytest tests/test_external_im_projection_contract.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py -q
```

Result:

```text
83 passed, 76 subtests passed in 126.21s (0:02:06)
```

Command:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
all checks passed
```

Command:

```bash
rg -n "message_service\\.(create_external_connection|authenticate_external_connection_key|send_external_connection_message|read_external_connection_events|get_im_direct_conversation|get_im_message|list_im_replies|update_im_disposition)" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Result:

```text
no hits
```

Command:

```bash
rg -n "/api/im" tools/launcher/assets/web-management/app.js
```

Result:

```text
no hits
```

### Acceptance Decision

Stage 2 acceptance criteria are met:

- Integration router has projection tests for auth gating and request-to-session
  field mapping.
- Web BFF has projection tests for browser cursor rejection, event DTO shaping,
  and empty direct conversation shaping around the session boundary.
- Existing behavior tests still pass.
- Browser JS still avoids `/api/im/*`.
- Scoped direct-call residue scans remain no-hit.

### Remaining Risk

The projection tests intentionally use fake sessions for HTTP/Web mapping. They
do not replace the Stage 1 session behavior tests or the external reply-loop
acceptance test, both of which remain part of the verification set.

## Stage 3: iMessage Channel Adapter MVP

Status: accepted.

### Red Gate

Added:

- `tests/test_imessage_bridge.py`
- `tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_imessage_bridge_command_dispatches_to_bridge_parser`

Red command:

```bash
python -m pytest tests/test_imessage_bridge.py -q
```

Red result:

```text
ImportError: cannot import name 'imessage_bridge' from 'tools.launcher'
```

Red launcher command:

```bash
python -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_imessage_bridge_command_dispatches_to_bridge_parser -q
```

Red result:

```text
AssertionError: 'Unknown top-level command: imessage' unexpectedly found in stderr
```

### Actual Changes

Created:

- `tools/launcher/imessage_bridge.py`
- `tests/test_imessage_bridge.py`

Modified:

- `buddyswitch-codex`
- `tests/test_buddyswitch_launcher.py`

### Adapter Boundary

The bridge owns:

- `imsg status`;
- local JSON state with `0600` chmod best effort;
- `/api/im/connections` connection creation;
- `/api/im/actors` target validation;
- inbound `is_from_me` filtering;
- allowlist filtering;
- inbound row/guid dedupe;
- inbound `POST /api/im/messages`;
- outbound `GET /api/im/events`;
- outbound `GET /api/im/messages/{id}`;
- outbound `imsg send`;
- outbound event-id send-once tracking.

The bridge does not import Central IM service or repo internals.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_imessage_bridge.py -q
```

Result:

```text
8 passed
```

Command:

```bash
python -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_imessage_bridge_command_dispatches_to_bridge_parser -q
```

Result:

```text
1 passed
```

Command:

```bash
./buddyswitch-codex imessage bridge
```

Result:

```text
argparse reached the bridge parser and reported missing --server and --target-identity-id.
```

Command:

```bash
python -m pytest tests/test_imessage_bridge.py tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_imessage_bridge_command_dispatches_to_bridge_parser tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Result:

```text
25 passed, 5 subtests passed
```

Command:

```bash
python -m py_compile tools/launcher/imessage_bridge.py scripts/env/services/external_im_session.py tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py
```

Result:

```text
passed
```

Command:

```bash
rg -n "env\\.services\\.messages|env\\.repos\\.messages|send_im_message|send_external_connection_message|read_external_connection_events" tools/launcher/imessage_bridge.py
```

Result:

```text
no hits
```

Command:

```bash
rg -n "\\b(iMessage|imessage|imsg|chat_id|chat_identifier|chat_guid|rowid|guid|allowlist|is_from_me)\\b" scripts/env/services/messages.py scripts/env/repos/messages.py scripts/env/tool_runtime/im_client.py scripts/env/tools/message/_impl.py tools/launcher/im_wake_handler.py
```

Result:

```text
no hits
```

The unbounded version of this scan hit `retry_guidance`, which is not an
iMessage field. The word-boundary scan is the accepted Stage 3 evidence.

### Acceptance Decision

Stage 3 acceptance criteria are met:

- Bridge tests cover fail-fast target validation, self-message filtering,
  allowlist rejection, inbound dedupe, inbound post, outbound send-once, restart
  send-once, and source isolation.
- The root launcher dispatches `imessage bridge` to the bridge parser.
- Adapter source scan proves no Central IM service/repo imports.
- Central IM source scan proves no iMessage-specific adapter fields in core.

### Remaining Risk

The bridge has fake-client coverage and command dispatch coverage. It has not
yet been run against real Messages.app/iPhone traffic; that is Stage 4.

## Stage 4: End-To-End Smoke

Status: accepted.

### Actual Changes

Created:

- `docs/spec/imessage-bridge-smoke-runbook.md`

Fixed during real smoke:

- Exposed the existing `/api/im/*` integration router through the real Web
  management service, because the bridge consumes that public HTTP surface.
- Made the bridge API client bypass environment HTTP proxies for local
  BuddySwitch Web requests.
- Made the long-running bridge wait for asynchronous actor replies after an
  inbound iMessage before polling `/api/im/events`, with an HTTP timeout margin
  beyond the long-poll window.

### Automated Verification Commands And Results

Command:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_imessage_bridge.py -q
```

Result:

```text
13 passed
```

Command:

```bash
python -m pytest tests/test_imessage_bridge.py tests/test_im_web_management_projection.py tests/test_external_im_projection_contract.py tests/test_im_http_router.py -q
```

Result after real-smoke fixes:

```text
22 passed, 30 subtests passed
```

Command:

```bash
imsg status
```

Result:

```text
imsg 0.11.1
Basic features (send, receive, history): Available
Advanced features (typing, read receipts): Not available
```

Command:

```bash
imsg chats --limit 1 --json
```

Result:

```text
Returned one 1:1 iMessage chat. Handles/account identifiers are intentionally redacted from this acceptance note.
```

Command:

```bash
imsg history --chat-id <redacted_chat_id> --limit 1 --json
```

Result:

```text
Returned one redacted history row for the 1:1 iMessage chat.
```

Command:

```bash
imsg watch --json
```

Result with a 2 second non-mutating timeout:

```text
watch_started=true; no stderr; no live message arrived during the timeout.
```

### Acceptance Decision

Stage 4 is accepted.

Machine-side real smoke passed, and the user confirmed the iPhone saw the
reply in the same iMessage chat.

Machine-side evidence from the real smoke:

- `target_identity_id`: `act-market-89316cc41041`.
- allowlisted sender: redacted `yuflo2024@...` iMessage identity.
- first live inbound row:
  - `chat_id`: redacted one-to-one iMessage chat.
  - `guid`: `27B823CF-5E1C-44F6-ADF4-41FAF755038D`.
  - `is_from_me=false`.
  - content: `Buddyswitch smoke test 2026-06-28`.
- first BuddySwitch message: `msg-b1549d078a93`.
- first actor handling: message fetched and marked `absorbed`, no reply.
- second live inbound row:
  - `chat_id`: same redacted one-to-one iMessage chat.
  - `guid`: `7653DB45-805C-4056-8773-256F58898952`.
  - `is_from_me=false`.
  - content: `Please reply exactly: Buddyswitch smoke ack 2026-06-28`.
- second BuddySwitch message: `msg-a91192cbfcca`.
- actor reply message: `msg-360dbc552871`.
- outbound event consumed by bridge: `imev-48739eadd35b`.
- local Messages history shows same-chat outbound row with `is_from_me=true`
  and content `Buddyswitch smoke ack 2026-06-28`.
- iPhone observation: user confirmed the same-chat reply was visible.

### Required Next Evidence

Stage 5 is now unblocked.

### Repeated Blocker Audit

Checked again at `2026-06-28T08:03:07Z`.

Command:

```bash
imsg chats --limit 3 --json
```

Result:

```text
latest visible 1:1 iMessage last_message_at: 2026-06-28T06:54:35.580Z
```

Command:

```bash
imsg watch --json
```

Result with a 3 second non-mutating timeout:

```text
watch_started=true; no stderr; no live message rows arrived during the timeout.
```

Command:

```bash
python -m pytest tests/test_im_external_reply_loop.py tests/test_imessage_bridge.py -q
```

Result:

```text
13 passed
```

Conclusion: this blocker audit was superseded by the later live smoke above.
Stage 4 is now accepted and Stage 5 is no longer gated.

## Stage 5: Residue Cleanup And Documentation Closeout

Status: accepted.

### Actual Changes

Updated:

- `docs/arch/web-interface-call-architecture.md`
- `tests/test_im_web_management_projection.py`
- `tests/test_buddyswitch_launcher.py`
- `buddyswitch-codex`

Closeout changes:

- `docs/arch/web-interface-call-architecture.md` now names
  `External IM Session` as the shared semantic boundary for both `/api/im/*`
  and `/api/web/im/*`.
- Added a live-surface source scan test that rejects retired IM architecture
  wording in the memo-required surfaces.
- Bound `BUDDYSWITCH_STATE_ROOT` for `buddyswitch-codex imessage bridge` so
  adapter state lands under the shared runtime state root instead of the source
  checkout.
- Removed the generated local bridge state file from the worktree after smoke.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_external_im_session.py tests/test_external_im_projection_contract.py tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py tests/test_imessage_bridge.py tests/test_buddyswitch_launcher.py -q
```

Result:

```text
302 passed, 116 subtests passed
```

Command:

```bash
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
passed
```

Command:

```bash
rg -n "two IM product implementations|separate IM product|Web IM routes should delegate to the message service|iMessage.*Central IM Core|Central IM.*iMessage|channel plugin|plugin framework|external-participants|/api/messages/send" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py tools/launcher/assets/web-management/app.js tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py tests/web_management_ui_contract.test.js docs/arch/web-interface-call-architecture.md | rg -v "assertExcludes"
```

Result:

```text
no hits
```

### Acceptance Decision

Stage 5 is accepted.

The live surfaces no longer describe Web IM and Integration IM as separate
product implementations, no live surface tells iMessage to call Central IM Core
directly, no live surface suggests a generic channel plugin framework for this
MVP, and the documented startup path matches the real commands.

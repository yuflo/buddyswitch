# iMessage Channel Product Logic Rebuild Acceptance Record

Date: 2026-06-28

## Phase 0: Plan Reset And Current-State Gate

Status: accepted.

### Actual Changes

- Replaced `docs/spec/imessage-rebuild-development-plan.md` with the source-memo-driven phase plan.
- Replaced `docs/spec/imessage-rebuild-test-plan.md` with the source-memo-driven test plan.
- Replaced `docs/spec/imessage-rebuild-context-audit.md` with current-state audit facts.
- Replaced this acceptance record.
- Removed the stale standalone bridge smoke runbook from live `docs/spec` guidance.

No production code was changed in Phase 0.

### Source Memo Coverage

- Complete development plan exists before implementation.
- Complete test plan exists before implementation.
- Current code facts and old live-surface residue are recorded.
- Next phase is blocked on test-first channel implementation.

### Verification Commands And Results

Command:

```bash
git status --short
```

Result:

```text
Only docs/spec planning changes and the untracked source memo are present at this gate.
```

Command: scaffold-token scan over the development plan and test plan.

Result:

```text
no hits
```

Command: docs-only stale-token scan over the new development plan and test plan.

Result:

```text
no hits
```

### Current Residue To Remove In Later Phases

- Root launcher still exposes the retired standalone iMessage command.
- Retired bridge source and tests still exist.
- Web management still lacks iMessage worker lifecycle ownership.
- Channel state schema version 2 and sender-scoped controller behavior do not exist yet.

### Acceptance Decision

Phase 0 is accepted. Phase 1 may begin.

## Phase 1: Channel State And Controller

Status: accepted.

### Red Gate

Added `tests/test_imessage_channel.py` before production code.

Command:

```bash
python -m pytest tests/test_imessage_channel.py -q
```

Red result:

```text
ImportError: cannot import name 'imessage_channel' from 'tools.launcher'
```

The failure was expected because the channel module did not exist yet.

### Actual Changes

- Added `tools/launcher/imessage_channel.py`.
- Added `tests/test_imessage_channel.py`.
- Implemented sender-scoped schema version 2 state under the channel state path.
- Implemented `/actors`, numeric selection, ordinary message delivery, per-contact route storage, per-contact outbound dedupe, and prefixed reply projection.
- Implemented a concrete `/api/im/*` client and `imsg` client in the channel module.
- Kept channel product semantics out of Web, HTTP router, `ExternalImSession`, and Central IM.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_imessage_channel.py -q
```

Result:

```text
13 passed
```

Command:

```bash
python -m py_compile tools/launcher/imessage_channel.py
```

Result:

```text
passed
```

Command:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core -q
```

Result:

```text
3 passed
```

### Acceptance Decision

Phase 1 is accepted. Phase 2 may begin.

## Phase 2: Web Lifecycle And Public Entry Replacement

Status: accepted.

### Red Gate

Added launcher and Web lifecycle tests before implementation.

Launcher red result:

```text
The new test expected the iMessage top-level command to be unknown, but the launcher still dispatched into the retired parser.
```

Web lifecycle red result:

```text
AttributeError: module 'buddyswitch_web_management' has no attribute 'serve_with_imessage_worker'
```

### Actual Changes

- Removed the retired public iMessage dispatch and help entry from `buddyswitch-codex`.
- Deleted the retired bridge source and tests.
- Added Web lifecycle helpers that start an iMessage worker, keep Web serving if worker startup fails, and stop the worker on shutdown.
- Wired Web `main` to create the channel worker using the actual bound Web server URL.
- Added background `start()` behavior to `ImessageChannelWorker`.
- Added launcher help and unknown-command tests.
- Added Web lifecycle and Web boundary tests.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_imessage_command_is_not_public tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow -q
```

Result:

```text
2 passed
```

Command:

```bash
python -m pytest tests/test_web_management.py -k imessage -q
```

Result:

```text
3 passed, 63 deselected
```

Command:

```bash
rg retired-iMessage-surface-live-token-set buddyswitch-codex tools/launcher tests docs/spec
```

Result:

```text
no hits
```

### Acceptance Decision

Phase 2 is accepted. Phase 3 may begin.

## Phase 3: Cross-Layer Contract And Reachability Alignment

Status: accepted.

### Red Gate

Added:

- `tests/test_external_im_session.py::ExternalImSessionTests::test_session_list_and_send_reject_offline_actor_rows`

Red result:

```text
The actor list still returned an offline actor row.
```

### Actual Changes

- Updated `ExternalImSession.list_actors` to omit blocked actor statuses.
- Updated `ExternalImSession` target resolution so sends reject the same blocked statuses.
- This keeps displayed actor choices and message delivery reachability aligned.

### Verification Commands And Results

Command:

```bash
python -m pytest tests/test_external_im_session.py::ExternalImSessionTests::test_session_list_and_send_reject_offline_actor_rows -q
```

Result:

```text
1 passed
```

Command:

```bash
python -m pytest tests/test_imessage_channel.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_external_im_projection_contract.py -q
```

Result:

```text
30 passed
```

Command:

```bash
python -m pytest tests/test_imessage_channel.py tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_external_im_projection_contract.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
```

Result:

```text
302 passed, 86 subtests passed in 561.49s (0:09:21)
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
python -m py_compile tools/launcher/imessage_channel.py tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services/external_im_session.py
```

Result:

```text
passed
```

Command:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals -q
```

Result:

```text
3 passed
```

### Residue Classification

- Retired command, option, state-directory, helper, source, and test surfaces: no live hits in launcher, tools, tests, or `docs/spec`.
- `target_identity_id` remains in channel code/tests only as the existing `/api/im/messages` payload field required by the Integration External IM HTTP API.

### Acceptance Decision

Phase 3 is accepted. Phase 4 may begin.

## Phase 4: Live Smoke And Final Acceptance

Status: accepted.

### Phase 4 Supplement: Outbound Send Status Confirmation

Review finding:

```text
imsg send --json can return {"status":"sent"} even when the Messages.app database records:
  error=22
  is_sent=0
  is_delivered=0
  is_finished=1
```

Architecture decision:

- Treat `imsg send` return code as command-submission evidence only.
- Keep send-state interpretation inside `CommandImsgClient`, the boundary that owns `imsg` and Messages.app integration.
- Do not move this state into Web, `/api/im/*`, `ExternalImSession`, or Central IM.
- On a confirmed bottom-level failure, raise `ChannelError` so existing controller flow does not mark the outbound event as sent.
- Do not require `is_delivered == 1` as the initial gate because delivery status can lag; require a route-scoped row with no send error and `is_sent == 1`.

Required verification before final Phase 4 acceptance:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails tests/test_imessage_channel.py::CommandImsgClientSendStatusTests -q
python -m pytest tests/test_imessage_channel.py -q
python -m py_compile tools/launcher/imessage_channel.py
```

Red gate:

```text
The controller regression initially failed because the fake send client failed too early during setup; the fixture was corrected to fail only on the actor-reply outbound send.
The send-status tests then failed with:
  TypeError: CommandImsgClient.__init__() got an unexpected keyword argument 'messages_db_path'
```

Green evidence:

```text
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails tests/test_imessage_channel.py::CommandImsgClientSendStatusTests -q
-> 3 passed

python -m pytest tests/test_imessage_channel.py -q
-> 16 passed

python -m py_compile tools/launcher/imessage_channel.py
-> passed

python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals -q
-> 3 passed

python -m pytest tests/test_imessage_channel.py tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_external_im_projection_contract.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
-> 305 passed, 86 subtests passed in 547.28s (0:09:07)
```

Follow-up live finding:

```text
row 26750 briefly appeared as error=0,is_sent=0,is_delivered=0,is_finished=1,
then updated to error=0,is_sent=1,is_delivered=1,is_finished=1.
```

Follow-up fix:

- Added `test_send_keeps_polling_transient_finished_unsent_row_without_error`.
- Kept polling no-error unsent rows until success or timeout.
- Kept immediate failure only for `error != 0`.

Follow-up verification:

```text
python -m pytest tests/test_imessage_channel.py::CommandImsgClientSendStatusTests -q
-> 3 passed

python -m pytest tests/test_imessage_channel.py -q
-> 17 passed

python -m py_compile tools/launcher/imessage_channel.py
-> passed

python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals -q
-> 3 passed
```

### Live Apple ID A Smoke Evidence

Command:

```bash
./buddyswitch-codex instance resume act-market-d627587226e7 --json
./buddyswitch-codex web --port 8765
```

Result:

```text
Actor act-market-d627587226e7 resumed as active.
Web Management listened on http://127.0.0.1:8765.
Web-owned imsg watch process was running.
/api/health returned {"ok": true}.
/api/im/actors returned act-market-d627587226e7 as the active selectable actor.
```

Manual iMessage flow from Apple ID A, redacted `y***@126.com`:

```text
/actors
-> [1] market act-market-d627587226e7

1
-> act-market-d627587226e7

Please reply exactly: BuddySwitch channel smoke ack 2026-06-29
-> [Message From act-market-d627587226e7]

   BuddySwitch channel smoke ack 2026-06-29
```

Runtime evidence:

```text
Inbound iMessage GUID: 246638FB-F337-42D8-93E0-5EC226B9154C
Central IM inbound message: msg-630b82bd3b33
Central IM reply message: msg-cd2e190c3d70
Outbound reply event: imev-c9eb5a77e666
Inbound disposition after actor processing: replied
Channel route: msg-630b82bd3b33 -> chat_id 3211
Channel outbound dedupe: imev-c9eb5a77e666
```

Source memo coverage proven by this smoke:

- `./buddyswitch-codex web` owns the iMessage worker lifecycle.
- `/actors` stays in the iMessage channel and returns `[n] role_id actor_id`.
- Numeric selection updates iMessage private active actor state.
- Ordinary iMessage content is delivered to the selected actor through `/api/im/messages`.
- Actor reply returns through `/api/im/events`.
- iMessage outbound projection wraps the reply with `[Message From act-...]`.
- The reply returns to the same iMessage chat route.

### Remaining Live Smoke Gap

Resolved. Apple ID B live isolation passed at the Messages.app boundary.

Earlier same-iPhone email-alias attempts did not satisfy B isolation because macOS exposed them as the existing redacted `y***@126.com` sender in chat `3211`.
The accepted B sender was exposed by macOS as redacted `h***@126.com` in chat `3213`.

Live channel state proved separate:

- A sender key: `sender:yuflo2024@126.com`.
- B sender key: `sender:hblouis@126.com`.
- A and B have different connection keys.
- A and B have separate active actor state.
- A and B have separate route storage.
- A and B have separate seen inbound keys.
- A and B have separate outbound event ids.

### Actual Changes

- Added `docs/spec/imessage-channel-smoke-runbook.md`.
- Removed the stale standalone smoke runbook.

### Current Evidence

Automated channel, Web lifecycle, External IM, reply-loop, product-core, Node UI, compile, and residue gates pass.

Manual Apple ID A smoke passed in this session and is recorded above.

Manual Apple ID B smoke passed in this session and is recorded below.

Smoke-readiness checks on 2026-06-29:

- `imsg` is installed at `/opt/homebrew/bin/imsg`.
- `imsg status` reports basic send, receive, and history available.
- `imsg chats --limit 1 --json` can read a 1:1 iMessage chat.
- `./buddyswitch-codex web --port 18765` starts and serves `/api/health`.
- `/api/im/connections` works through the Web-managed service.
- With a temporary market actor running, `/api/im/actors` returned one active actor.
- The temporary actor and Web server were stopped after the readiness check.

### Live Apple ID B Smoke Evidence

Web lifecycle:

```text
Web Management listened on http://127.0.0.1:8765.
Web-owned imsg watch process was running.
/api/health returned {"ok": true}.
Actor act-market-d627587226e7 was active and idle.
```

Manual iMessage flow from Apple ID B, redacted `h***@126.com`, chat `3213`:

```text
helo
-> Send /actors to choose an actor.

/actors
-> [1] market act-market-d627587226e7

1
-> act-market-d627587226e7

Please reply exactly: Buddyswitch B route smoke ack 2026-06-29
-> [Message From act-market-d627587226e7]

   Buddyswitch B route smoke ack 2026-06-29
```

Runtime evidence:

```text
B inbound ordinary iMessage GUID: 40CDB621-CCAC-4CEE-8202-EF2D1400DB66
B Central IM inbound message: msg-ddb94d601124
B outbound reply event: imev-99ac12f48856
B route: msg-ddb94d601124 -> chat_id 3213
B outbound iMessage row: 26760, error=0,is_sent=1,is_delivered=1,is_finished=1
B outbound dedupe: imev-99ac12f48856
```

Source memo coverage additionally proven by B smoke:

- A second live sender created a distinct contact and connection.
- The second live sender used its own actor selection state.
- The second live sender's ordinary message routed to the selected actor.
- The actor reply returned to the second sender's original iMessage chat.
- A and B state did not cross at the Messages.app boundary.

### Acceptance Decision

Final post-smoke verification:

```text
python -m pytest tests/test_imessage_channel.py tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_external_im_projection_contract.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
-> 306 passed, 86 subtests passed in 550.50s (0:09:10)

node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
-> passed

python -m py_compile tools/launcher/imessage_channel.py tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services/external_im_session.py
-> passed

python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals -q
-> 3 passed
```

Cleanup evidence:

```text
./buddyswitch-codex instance stop act-market-d627587226e7 --json
-> {"actor_id": "act-market-d627587226e7", "status": "inactive"}

ps scan for "buddyswitch-codex web --port 8765", "web_management.py --port 8765", and "imsg watch --json"
-> no hits

lsof -nP -iTCP:8765 -sTCP:LISTEN
-> no listener

./buddyswitch-codex instance status act-market-d627587226e7 --json
-> status inactive; app_server healthy false; daemon live false
```

Phase 4 is accepted. The source memo target is proven end to end.

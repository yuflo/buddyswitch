# iMessage Channel Product Logic Rebuild Test Plan

Date: 2026-06-28

## Test Strategy

Use test-first replacement. Phase 1 and Phase 2 must each add tests that fail against the current bridge implementation before production code changes. Unit tests cover channel state and controller behavior; lifecycle tests cover Web-owned worker start/stop; integration-style tests cover the `/api/im/*` handoff. Residue scans are part of the acceptance gate because the source memo requires no live old surface.

## Phase 0: Plan Reset And Current-State Gate

### Source Memo Behavior Contracts Covered

- Development plan exists before implementation.
- Test plan exists before implementation.
- Old live bridge surface is identified as residue.

### Focused Test Cases

None. Phase 0 is documentation and current-state audit only.

### Integration Or Lifecycle Tests

None.

### Negative Cases

- Current scan is expected to find old bridge command, params, state, tests, and docs before replacement.

### Residue Checks

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
```

Expected before implementation: hits in launcher, bridge code, bridge tests, and stale docs.

### Commands And Pass Criteria

```bash
git status --short
```

Pass criteria: only intended source memo/docs changes are present.

## Phase 1: iMessage Channel State And Controller

### Source Memo Behavior Contracts Covered

- Sender-scoped state schema version 2.
- Per-sender connection creation and reuse.
- Per-sender active actor, pending choices, dedupe, outbound event ids, and route isolation.
- `/actors` list formatting and snapshot storage.
- Numeric selection changes only sender-local active actor.
- Ordinary messages require active actor and deliver original content.
- Actor replies are prefixed and routed to original iMessage route.
- iMessage module isolation from Central IM internals.

### Focused Test Cases

Create `tests/test_imessage_channel.py` with these failing tests before implementation:

- `test_default_state_path_uses_imessage_channel_schema_v2`
- `test_first_sender_message_creates_connection_and_reuses_it`
- `test_two_senders_keep_connections_choices_routes_and_dedupe_isolated`
- `test_actors_control_message_lists_online_actors_and_stores_snapshot`
- `test_numeric_selection_uses_pending_snapshot_without_posting_message`
- `test_numeric_without_pending_choices_is_ordinary_message_and_prompts_when_no_active_actor`
- `test_ordinary_message_without_active_actor_sends_minimal_actors_prompt`
- `test_ordinary_message_posts_to_active_actor_with_original_content`
- `test_actor_reply_is_prefixed_and_sent_to_recorded_route_once`
- `test_channel_source_does_not_import_central_im_internals`

### Integration Or Lifecycle Tests

- A fake `BuddySwitchImApi` records create/list/send/read/get calls.
- A fake `imsg` records outbound route/text calls.
- No real process or HTTP server is required in Phase 1.

### Negative Cases

- Offline/unreachable actor rows are not displayed by `/actors`.
- A numeric message with no pending choices is not treated as selection.
- An invalid pending number does not select an actor.
- Duplicate inbound keys do not resend messages.
- Duplicate outbound event ids do not resend iMessages.

### Residue Checks

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals -q
```

Pass criteria: no hits after Phase 1, except any deleted file paths absent from the tree.

### Commands And Pass Criteria

Red gate:

```bash
python -m pytest tests/test_imessage_channel.py -q
```

Expected before implementation: import failures or assertion failures caused by missing channel semantics.

Green gate:

```bash
python -m pytest tests/test_imessage_channel.py -q
python -m py_compile tools/launcher/imessage_channel.py
```

Expected after implementation: all pass.

## Phase 2: Web-Owned Worker Lifecycle And Public Entry Removal

### Source Memo Behavior Contracts Covered

- `./buddyswitch-codex web` is the only user startup entry.
- Root launcher no longer exposes the retired standalone iMessage command.
- Web starts and stops the iMessage worker.
- Worker local environment failure does not crash Web.
- Web does not own iMessage control semantics.

### Focused Test Cases

Modify `tests/test_buddyswitch_launcher.py`:

- Replace old bridge dispatch test with `test_imessage_command_is_not_public`.
- Add or update help test to assert the retired standalone command and its old options are absent.

Modify `tests/test_web_management.py`:

- `test_web_main_starts_and_stops_imessage_worker`
- `test_web_main_keeps_health_available_when_imessage_worker_start_fails`
- `test_web_management_source_does_not_parse_imessage_control_messages`

Modify `tests/test_imessage_channel.py`:

- `test_worker_stop_terminates_watch_client`

### Integration Or Lifecycle Tests

- Use fake worker factories and a short-lived Web server instance.
- Tests must cleanly stop the server and worker in `finally`.
- Add residual checks for fake worker stop calls; do not start real `imsg watch`.

### Negative Cases

- The retired standalone command returns unknown top-level command.
- `buddyswitch-codex help` does not advertise old command or params.
- Web worker startup errors are observable through a health/status field or logs but do not prevent `/api/health`.

### Residue Checks

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
```

Pass criteria: no hits in live surfaces after Phase 2.

### Commands And Pass Criteria

Red gate:

```bash
python -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_imessage_command_is_not_public -q
python -m pytest tests/test_web_management.py -k imessage -q
```

Expected before implementation: old command is still live and Web has no worker lifecycle.

Green gate:

```bash
python -m pytest tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_imessage_channel.py -q
python -m py_compile tools/launcher/web_management.py tools/launcher/imessage_channel.py
```

Expected after implementation: all pass and no worker/process residue remains.

## Phase 3: Cross-Layer Contract And Actor List Alignment

### Source Memo Behavior Contracts Covered

- `/actors` does not call `POST /api/im/messages`.
- Numeric selection does not call `POST /api/im/messages` or wake actors.
- Ordinary message posts to `/api/im/messages` with active actor.
- Event polling is per sender connection.
- Reply prefix actor id comes from event/message metadata.
- Actor list source aligns with wake reachability.

### Focused Test Cases

Add or extend:

- `test_control_messages_do_not_create_central_im_messages`
- `test_two_sender_full_fake_loop_keeps_connection_and_reply_routes_isolated`
- `test_reply_prefix_uses_message_or_event_sender_identity_not_content`
- `test_actor_list_display_uses_same_reachability_source_as_message_delivery`

### Integration Or Lifecycle Tests

Run existing External IM tests with new channel tests:

```bash
python -m pytest tests/test_imessage_channel.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py -q
```

### Negative Cases

- If `/actors` or numeric selection accidentally posts to `/api/im/messages`, fake API call counts must fail.
- If actor list/wake reachability diverges, the alignment test must fail.

### Residue Checks

```bash
rg -n "/actors|pending_actor_choices|active_actor_id|\\[Message From" tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services scripts/env/repos
rg -n "\\b(iMessage|imessage|imsg|chat_id|chat_identifier|chat_guid|rowid|guid|pending_actor_choices|active_actor_id)\\b" scripts/env/services/messages.py scripts/env/repos/messages.py scripts/env/tool_runtime/im_client.py scripts/env/tools/message/_impl.py tools/launcher/im_wake_handler.py
```

Pass criteria: no channel-specific semantics outside `tools/launcher/imessage_channel.py` and its tests.

### Commands And Pass Criteria

```bash
python -m pytest tests/test_imessage_channel.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py -q
```

Expected: all pass.

## Phase 4: Live Docs, Smoke Runbook, And Final Acceptance

### Source Memo Behavior Contracts Covered

- Live docs describe only Web startup for iMessage.
- Smoke runbook follows the channel control flow.
- Final acceptance proves the source memo end to end.
- Outbound iMessage replies are not accepted as sent solely because `imsg send` returned success.

### Focused Test Cases

- Add source-scan tests if residue checks are not already automated.
- Keep existing Web UI and External IM tests green.
- Add `test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails` to prove a failed outbound iMessage send does not update per-contact outbound dedupe state.
- Add `CommandImsgClientSendStatusTests::test_send_accepts_route_scoped_successful_message_row` using a temporary `chat.db` fixture to prove command success plus `error=0` and `is_sent=1` is accepted.
- Add `CommandImsgClientSendStatusTests::test_send_rejects_failed_message_row_after_successful_command` using a temporary `chat.db` fixture to prove command success plus `error!=0` or `is_sent=0` raises `ChannelError`.
- Add `CommandImsgClientSendStatusTests::test_send_keeps_polling_transient_finished_unsent_row_without_error` to prove `error=0,is_sent=0,is_finished=1` is not treated as final failure before the timeout.

### Integration Or Lifecycle Tests

Automated:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails tests/test_imessage_channel.py::CommandImsgClientSendStatusTests -q
python -m pytest tests/test_imessage_channel.py tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_external_im_projection_contract.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Manual smoke if environment permits:

```text
1. Start ./buddyswitch-codex web.
2. Send /actors from Apple ID A.
3. Select an actor by number.
4. Send a normal message and observe a prefixed actor reply in the same chat.
5. Repeat with Apple ID B and verify independent selection/reply routing.
```

### Negative Cases

- If local `imsg` or macOS permissions block smoke, record the exact external blocker and keep automated acceptance separate.
- Do not accept a fake run as manual smoke.
- If `imsg send` returns zero but the Messages.app row has `error=22`, `is_sent=0`, and `is_finished=1`, `CommandImsgClient.send()` must raise `ChannelError`.
- If a Messages.app row has `error=0,is_sent=0,is_finished=1`, `CommandImsgClient.send()` must continue polling until success or timeout because this state was observed as transient during live smoke.
- If status confirmation raises during outbound event polling, the event id must remain absent from `sent_outbound_event_ids` so the channel does not silently dedupe a failed reply.
- Do not require `is_delivered == 1` for initial acceptance because delivery status can lag; assert only the local send failure gate needed for this iteration.

### Residue Checks

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core -q
```

Pass criteria: old-surface hits are absent from live surfaces; any source memo or historical memo hits are classified explicitly in acceptance.

### Commands And Pass Criteria

```bash
python -m py_compile tools/launcher/imessage_channel.py tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services/external_im_session.py
```

Expected: compilation passes. Final acceptance maps each source memo requirement to evidence.

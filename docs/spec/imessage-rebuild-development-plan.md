# iMessage Channel Product Logic Rebuild Development Plan

Date: 2026-06-28

## Goal

Execute the source memo at `docs/memo/2026-06-28-imessage-channel-product-logic-rebuild.md` through staged, verified replacement of the old iMessage bridge path.

## Architecture

Target dependency direction:

```text
Messages.app / imsg
  -> tools/launcher/imessage_channel.py
  -> /api/im/*
  -> ExternalImSession
  -> Central IM Core
  -> actor runtime
```

`./buddyswitch-codex web` owns process lifecycle. The iMessage module owns sender-scoped channel state and iMessage control-message behavior. Web, `/api/im/*`, `ExternalImSession`, and Central IM must not learn iMessage control semantics.

## Current Code Facts

- `buddyswitch-codex` still exposes the retired standalone iMessage command and help text.
- The retired bridge module still uses fixed actor targeting, sender allow-listing, schema version 1, and the retired bridge state directory.
- The retired bridge tests still cover the fixed-target allowlist bridge.
- `tools/launcher/web_management.py` exposes `/api/im/*` but does not start or stop an iMessage worker.
- `ExternalImSession.list_actors` and `ExternalImSession.send_message` both use the injected actor lister, so the channel can filter current actor rows without importing Central IM internals.
- Existing `docs/spec` iMessage documents describe the old bridge MVP and must be replaced as live planning surfaces.

## Phase 0: Plan Reset And Current-State Gate

### Phase Objective

Replace stale `docs/spec` planning surfaces with this source-memo-driven plan and prove the old bridge surface is still live.

### Source Memo Requirements Covered

- Complete development plan before implementation.
- Complete test plan before implementation.
- No phase completion claim without verification.
- Live docs must not continue to teach the old bridge path.

### Files Expected To Change

- Modify: `docs/spec/imessage-rebuild-development-plan.md`
- Modify: `docs/spec/imessage-rebuild-test-plan.md`
- Modify: `docs/spec/imessage-rebuild-context-audit.md`
- Modify: `docs/spec/imessage-rebuild-stage-acceptance.md`
- Delete or replace: the retired standalone iMessage smoke runbook in `docs/spec`.

### Boundaries That Must Not Be Crossed

- No production code changes in Phase 0.
- Do not rewrite the source memo.
- Do not preserve old bridge runbooks as current execution guidance.

### Implementation Steps

1. Read source memo, `AGENTS.md`, and `docs/bitter/*`.
2. Inspect current iMessage code, launcher help, Web lifecycle, and tests.
3. Replace stale development and test plans with source-memo-aligned phase plans.
4. Replace the context audit and acceptance record with current evidence.
5. Remove the old bridge smoke runbook from live `docs/spec` guidance.

### Deletion / Replacement Points

- Replace old bridge MVP plan content in `docs/spec`.
- Remove the old smoke runbook that starts the retired standalone command.

### Verification Commands

```bash
git status --short
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
```

### Residue Scan Commands

Phase 0 expects current live hits outside historical/source memo context:

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
```

### Phase Done Criteria

- `docs/spec` contains this updated plan, an updated test plan, a current context audit, and Phase 0 acceptance evidence.
- Old bridge smoke runbook is removed or replaced.
- Current old-surface residue is recorded as the Phase 1/2 target.
- No production code has changed.

## Phase 1: iMessage Channel State And Controller

### Phase Objective

Replace fixed-target bridge semantics with sender-scoped iMessage channel product logic behind test-first controller and state-store coverage.

### Source Memo Requirements Covered

- State path is `runtime_files.LOCAL_ROOT / "imessage-channel" / "state.json"`.
- Schema version is 2 with per-sender `contacts`.
- First message from a sender creates a distinct `/api/im/connections` connection.
- Same sender reuses its connection.
- Different senders do not share connection key, active actor, pending choices, dedupe, outbound event ids, or routes.
- `/actors` lists online actors as `[n] role_id actor_id` and stores the sender's pending choice snapshot.
- Numeric selection only uses the pending snapshot and only updates sender-local active actor.
- Ordinary messages require an active actor and otherwise only send the minimal `/actors` prompt.
- Ordinary messages send original content to `/api/im/messages` using the sender's active actor.
- Actor replies are sent back through the stored iMessage route and wrapped by the channel.
- The iMessage module does not import Central IM repo/service internals.

### Code Facts Discovered

- Existing `BuddySwitchImApi` is usable as the `/api/im/*` client but must drop bridge-specific naming.
- Existing `CommandImsgClient` already encapsulates `imsg status/watch/send` and can be carried forward.
- Existing bridge state shape is global and must not be migrated or dual-read.

### Files Expected To Change

- Create: `tools/launcher/imessage_channel.py`
- Create: `tests/test_imessage_channel.py`
- Delete or stop importing the retired bridge module.
- Delete or replace the retired bridge tests.

### Boundaries That Must Not Be Crossed

- No `/actors` or numeric-selection parsing in Web, HTTP router, `ExternalImSession`, or Central IM.
- No Central IM imports from the iMessage channel module.
- No old schema dual-read or migration path.
- No generic channel framework.

### Implementation Steps

1. Write failing tests for schema path/version and sender-isolated connection creation/reuse.
2. Write failing tests for `/actors` formatting, online filtering, and pending snapshot storage.
3. Write failing tests for numeric selection with and without pending choices.
4. Write failing tests for ordinary message delivery to active actor and no-active prompt.
5. Write failing tests for reply route lookup, reply prefix wrapping, and per-contact outbound dedupe.
6. Write failing source-boundary tests that reject Central IM imports and old bridge state names.
7. Implement `ImessageChannelStateStore`, `BuddySwitchImApi`, `CommandImsgClient`, and `ImessageChannelController` in one concrete module.
8. Implement worker shell only as needed for controller-level tests; lifecycle belongs to Phase 2.
9. Delete the old bridge test file after replacement tests cover the new behavior.

### Deletion / Replacement Points

- Replace the retired bridge configuration, bridge runner, state store, and global bridge state with channel-specific classes.
- Delete fixed actor targeting, sender allow-list state, and schema version 1 from iMessage channel code and tests.

### Verification Commands

```bash
python -m pytest tests/test_imessage_channel.py -q
python -m py_compile tools/launcher/imessage_channel.py
```

### Residue Scan Commands

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_source_does_not_import_central_im_internals -q
```

### Phase Done Criteria

- New channel tests pass after observed RED failures.
- Old bridge source/test files are deleted or no longer live.
- Channel state is sender-scoped and schema version 2.
- Scoped residue scans pass for channel code and tests.

## Phase 2: Web-Owned Worker Lifecycle And Public Entry Removal

### Phase Objective

Make `./buddyswitch-codex web` the only user startup path and have Web start/stop the iMessage worker lifecycle without owning channel semantics.

### Source Memo Requirements Covered

- Root launcher no longer exposes the retired standalone iMessage command.
- User starts only `./buddyswitch-codex web`.
- Web starts/stops the iMessage channel worker lifecycle.
- Web passes lifecycle dependencies only.
- Worker failure due to local `imsg` availability or permissions must not crash the Web service.
- Web shutdown stops the worker and `imsg watch`.

### Code Facts Discovered

- `web_main` already ensures and idles the central daemon.
- `tools/launcher/web_management.py` currently creates the HTTP server directly and has no worker lifecycle hook.
- Launcher help currently advertises the old command.

### Files Expected To Change

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_imessage_channel.py`

### Boundaries That Must Not Be Crossed

- Web must not parse `/actors`, numeric choices, sender keys, active actors, pending choices, or outbound text wrapping.
- Root launcher must not keep old command aliases or deprecated params.
- Web service must remain available if iMessage worker startup reports a local environment problem.

### Implementation Steps

1. Write failing launcher tests showing help omits the retired standalone iMessage command and that its top-level dispatch is unknown.
2. Write failing Web lifecycle tests with a fake worker factory proving `start()` on Web startup and `stop()` on shutdown.
3. Write failing lifecycle test proving worker startup failure is captured without preventing `/api/health`.
4. Add explicit Web server lifecycle helpers that start the worker after server construction and stop it in `finally`.
5. Wire `ImessageChannelWorker` with base URL, state path, logger, and stop signal only.
6. Remove the retired standalone iMessage helper and dispatch from the root launcher.

### Deletion / Replacement Points

- Delete root launcher `imessage` top-level dispatch.
- Delete old bridge help line and helper constant.
- Replace old launcher tests that expected bridge dispatch.

### Verification Commands

```bash
python -m pytest tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_imessage_channel.py -q
python -m py_compile tools/launcher/web_management.py tools/launcher/imessage_channel.py
```

### Residue Scan Commands

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
```

### Phase Done Criteria

- Launcher no longer exposes or dispatches the old command.
- Web lifecycle tests prove start/stop behavior and failure isolation.
- Web source contains no channel product semantics.
- Residue scan passes except explicitly historical/source memo context.

## Phase 3: Cross-Layer Contract And Actor List Alignment

### Phase Objective

Prove the channel uses `/api/im/*` end to end with per-sender connections and an actor list that matches the existing reachability path.

### Source Memo Requirements Covered

- `/actors` uses `/api/im/actors` and does not create Central IM messages.
- Numeric selection does not call `/api/im/messages` or wake an actor.
- Ordinary messages post through `/api/im/messages`.
- Event polling is per contact/connection.
- Actor id for reply prefix comes from message/event metadata, not from reply content.
- Actor list source cannot diverge from wake reachability.

### Code Facts Discovered

- `ExternalImSession.list_actors` and `_actor_participant_for_identity` use the same actor lister injection.
- `ImHttpRouter` continues to own `/api/im/*` HTTP request mapping and session authentication.

### Files Expected To Change

- Modify: `tests/test_imessage_channel.py`
- Modify if needed: `scripts/env/services/external_im_session.py`
- Modify if needed: `tests/test_external_im_session.py`
- Modify if needed: `tests/test_im_http_router.py`

### Boundaries That Must Not Be Crossed

- Do not add iMessage control routes to `/api/im/*`.
- Do not move active actor state into Central IM.
- Do not add actor-list special cases in Web for iMessage.

### Implementation Steps

1. Add integration-style fake HTTP/API tests for `/actors -> numeric selection -> ordinary message -> prefixed reply`.
2. Add tests proving two senders get isolated connection keys and event polling.
3. Add a test proving displayed actor rows are filtered from the same actor list shape used by message delivery.
4. Adjust `ExternalImSession` only if current actor list/wake reachability evidence is inconsistent.

### Deletion / Replacement Points

- Remove any leftover bridge-level target validation tests.
- Remove tests that assert allowlist rejection or fixed target delivery.

### Verification Commands

```bash
python -m pytest tests/test_imessage_channel.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py -q
```

### Residue Scan Commands

```bash
rg -n "/actors|pending_actor_choices|active_actor_id|\\[Message From" tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services scripts/env/repos
rg -n "\\b(iMessage|imessage|imsg|chat_id|chat_identifier|chat_guid|rowid|guid|sender handle|pending_actor_choices|active_actor_id)\\b" scripts/env/services/messages.py scripts/env/repos/messages.py scripts/env/tool_runtime/im_client.py scripts/env/tools/message/_impl.py tools/launcher/im_wake_handler.py
```

### Phase Done Criteria

- Cross-layer fake path proves the memo's main channel loop without real Messages.app dependency.
- Boundary scans show channel-specific semantics are only in the iMessage module.
- Existing External IM HTTP and reply-loop tests still pass.

## Phase 4: Live Docs, Smoke Runbook, And Final Acceptance

### Phase Objective

Make every live execution surface teach the new Web-started channel path and record final automated plus manual smoke evidence or a precise external blocker.

Phase 4 also owns one live-smoke reliability supplement discovered during testing: `imsg send` can return command-level success while the Messages.app database records a failed outbound message. Final acceptance must not treat command submission as proof that an iMessage reply reached the user.

### Source Memo Requirements Covered

- Live docs only describe `./buddyswitch-codex web` for iMessage startup.
- Smoke runbook uses `/actors -> numeric selection -> ordinary message -> prefixed reply`.
- Old bridge command appears only in historical/superseded source material, not current execution guidance.
- Final acceptance proves the source memo target end to end.
- Outbound iMessage smoke evidence distinguishes command submission from the underlying Messages.app send state.

### Files Expected To Change

- Replace the retired standalone iMessage smoke runbook with channel smoke guidance or delete it if the final acceptance record fully covers smoke instructions.
- Modify: `docs/spec/imessage-rebuild-stage-acceptance.md`
- Modify: any live docs found by residue scan.
- Modify: `tools/launcher/imessage_channel.py`
- Modify: `tests/test_imessage_channel.py`

### Boundaries That Must Not Be Crossed

- Do not edit historical memos only to satisfy scans.
- Do not call fake tests a manual iMessage smoke.
- Do not mark final complete without requirement-by-requirement evidence.
- Do not move iMessage send-state interpretation into Web, `/api/im/*`, `ExternalImSession`, or Central IM.
- Do not require `is_delivered == 1` as the only success signal; delivery can lag after local send. The first gate is command success plus a route-scoped Messages.app row with no error and `is_sent == 1`.

### Code Facts Discovered During Phase 4

- A direct `imsg send --json` to `yuflo2024@126.com` returned `{"status":"sent"}`.
- The matching `chat.db.message` row later showed `error=22`, `is_sent=0`, `is_delivered=0`, and `is_finished=1`.
- Successful nearby outbound rows showed `error=0`, `is_sent=1`, and `is_delivered=1`.
- Current `CommandImsgClient.send()` only checks the `imsg send` subprocess return code, so `poll_outbound_once()` can mark an outbound event as sent even when Messages.app recorded a failed send.
- `imsg history --json` does not expose the status fields needed for this distinction; the local Messages.app SQLite database does.
- A successful outbound can be temporarily visible as `error=0,is_sent=0,is_delivered=0,is_finished=1` before Messages.app updates the same row to `is_sent=1,is_delivered=1`. This transient no-error unsent state must keep polling; only `error!=0` is an immediate bottom-level failure.

### Implementation Steps

1. Update smoke runbook to use `./buddyswitch-codex web` and the channel control flow.
2. Add a failing regression test proving command-level `imsg send` success with a failed Messages.app row raises `ChannelError`.
3. Add a failing controller regression test proving outbound events are not added to `sent_outbound_event_ids` when `imsg.send()` raises.
4. Add a failing regression test proving a no-error transient unsent row is polled until it becomes sent.
5. Implement the minimal route-scoped Messages.app status confirmation inside `CommandImsgClient`.
6. Keep product processing unchanged: failed send status should surface as `ChannelError`, and existing controller flow must avoid outbound dedupe when send fails.
7. Run focused, broader, and residue verification.
8. Run manual smoke if local iMessage conditions permit; otherwise record exact external blocker.
9. Write phase/final acceptance mapping each source memo requirement to evidence.

### Verification Commands

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_poll_outbound_does_not_mark_event_sent_when_imessage_send_fails tests/test_imessage_channel.py::CommandImsgClientSendStatusTests -q
python -m pytest tests/test_imessage_channel.py tests/test_buddyswitch_launcher.py tests/test_web_management.py tests/test_external_im_projection_contract.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_im_product_core.py -q
node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
python -m py_compile tools/launcher/imessage_channel.py tools/launcher/web_management.py tools/launcher/im_http_router.py scripts/env/services/external_im_session.py
```

### Residue Scan Commands

```bash
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_no_retired_imessage_surface -q
python -m pytest tests/test_imessage_channel.py::ImessageChannelResidueTests::test_channel_semantics_stay_out_of_web_http_and_core -q
```

### Phase Done Criteria

- All planned automated verification passes.
- Residue scans pass or remaining source memo/historical hits are explicitly classified.
- Command-level send success with bottom-level Messages.app failure is detected before an outbound event is deduped as sent.
- Manual smoke succeeds or a precise external blocker is recorded.
- Final acceptance record proves every source memo requirement.

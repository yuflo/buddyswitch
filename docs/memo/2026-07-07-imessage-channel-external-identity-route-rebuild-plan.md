# iMessage Channel External Identity Route Rebuild Plan

Date: 2026-07-07

## 1. Task Goal

Rebuild the iMessage channel outbound routing model so every iMessage delivery from BuddySwitch is driven by the external session / external identity route owned by the iMessage channel.

The final architecture must be:

```text
Actor
-> message.send(target_identity_id=ext-imessage-user)
   or message.send(reply_to=source_message_id)
-> IM core resolves target_identity=ext-imessage-user
-> IM core writes message/event

iMessage channel
-> poll /api/im/events with its external_session_key
-> fetch message by message_id
-> use the contact route bound to that external session / ext identity
-> imsg.send(route, content)
-> ack event after successful iMessage send
```

The final architecture must not be:

```text
reply_to/source message id -> iMessage route
```

`reply_to` remains valid IM metadata for reply/thread/state semantics. It must not participate in iMessage delivery routing.

## 2. Forward Development Requirements

This task is a rebuild, not a compatibility patch.

Non-negotiable requirements:

- No dual route model.
- No fallback from external identity route to `reply_to` route.
- No `message_id -> iMessage route` map in live channel state.
- No channel route fields in IM API, IM core, actor payloads, Web UI, or daemon runtime.
- No iMessage imports of IM core or repository internals.
- No runtime code that remembers retired iMessage route schema unless a real migration requirement is explicitly approved.

The implementation must delete the old route shape from active code rather than guard against it.

## 3. Bitter Lessons Applied

Read before this plan:

- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`

Rules this task must follow:

- Fix the layer that owns the wrong contract. The wrong contract is inside iMessage channel state and outbound routing, not inside IM core.
- Keep the shared API boundary stable and boring. Do not add iMessage-specific fields to `/api/im/*`.
- Prove both behavior and live surface cleanup. Passing behavior tests alone is not enough.
- Avoid guarded residue. Do not keep old route schema names in active runtime code just to reject them.
- Keep the end-to-end promise alive: actor sends to an external identity, and the iMessage user receives it through the channel.

## 4. Current State Confirmed In Code

Current core/API state is already sufficient:

- `scripts/env/services/messages.py` creates external sessions and returns both `external_session_key` and `identity`.
- `tools/launcher/im_http_router.py` exposes `/api/im/external-sessions`, `/api/im/messages`, `/api/im/events`, `/api/im/events/ack`, and message fetch routes.
- `tools/launcher/external_im_session.py` keeps send/reply semantics inside `ExternalImSession`.
- `scripts/env/services/messages.py` already normalizes `reply_to` through `send_im_reply` into `target_identity`, then writes through `send_im_message`.

Current iMessage channel state is not sufficient:

- `tools/launcher/imessage_channel.py` stores only `external_session_key` when creating an external session.
- It discards the returned external identity.
- It stores per-message route state after inbound delivery.
- It routes outbound events by reading `reply_to` and looking up a per-message route.
- It treats missing reply route as an unrouteable event and acks it away.

This means actor reply works only because it still carries a `reply_to` that points back to an inbound source message. Actor proactive send to `ext-*` has no route under the current channel state model.

## 5. Desired System Boundary

### IM API Boundary

`/api/im/*` is a black-box product boundary for channels.

iMessage may use:

```text
POST /api/im/external-sessions
GET  /api/im/actors
POST /api/im/messages
GET  /api/im/events
POST /api/im/events/ack
GET  /api/im/messages/{id}
```

iMessage must not use:

```text
resolve_im_send_target
send_im_message
send_im_reply
message repositories
identity repositories
actor reachability internals
daemon delivery internals
```

### iMessage Channel Boundary

iMessage channel owns:

```text
iMessage sender/chat route
external_session_key
external_identity_id
selected actor identity for inbound messages
inbound dedupe state
outbound event id send/ack state
```

iMessage channel does not own:

```text
IM message target resolution
IM conversation storage
IM event visibility rules
actor delivery
Web UI session behavior
```

## 6. Target iMessage Contact State

Replace the contact state shape with one current schema.

Target contact shape:

```json
{
  "external_session_key": "imsk-example",
  "external_identity_id": "ext-imessage-user",
  "route": {
    "sender": "user@example.com",
    "chat_id": "9"
  },
  "active_identity_id": "act-market-selected",
  "pending_actor_choices": {
    "1": "act-market-selected"
  },
  "seen_inbound_keys": [
    "guid:inbound-example"
  ],
  "sent_outbound_event_ids": [
    "imev-outbound-example"
  ]
}
```

There must be no per-message route map in the current schema.

Recommended schema handling:

- Bump `SCHEMA_VERSION` from `2` to `3`.
- Missing state file returns the new empty schema.
- Existing file with a non-current `schema_version` raises `ChannelError` with a reset-oriented message.
- Existing contact payloads are normalized only through the current allowlisted fields.
- Active code does not name or migrate the retired per-message route map.

Rationale: this is local channel adapter state, not an external API contract or irreversible product data. Keeping a runtime migration for the retired shape would preserve the wrong model inside the live path.

## 7. Target Data Flow

### Inbound iMessage To Actor

```text
iMessage row
-> sender + route extracted by channel
-> contact loaded by sender key
-> external session created or reused
-> external_identity_id saved from session creation response
-> contact.route refreshed from current iMessage row
-> /actors and numeric selection stay channel-local
-> ordinary text posts /api/im/messages(target_identity_id=active actor)
```

The inbound flow no longer records `message_id -> route`.

### Actor Reply To iMessage User

```text
actor message.send(reply_to=source_message_id)
-> IM core resolves target_identity=ext-imessage-user
-> IM core writes outbound event visible to external session
-> iMessage channel polls that external session
-> channel fetches message
-> channel uses contact.route
-> imsg.send(route, content)
-> ack event after send succeeds
```

The channel does not inspect `reply_to` for delivery routing.

### Actor Proactive Send To iMessage User

```text
actor message.send(target_identity_id=ext-imessage-user)
-> IM core writes outbound event visible to external session
-> iMessage channel polls that external session
-> channel fetches message
-> channel uses contact.route
-> imsg.send(route, content)
-> ack event after send succeeds
```

This is the same channel outbound path as actor reply.

## 8. Implementation Plan

Implementation must be test-first and scoped to iMessage channel files.

### Task 1: Update Fake API And State Expectations

Files:

- Modify `tests/test_imessage_channel.py`

Steps:

1. Update `_FakeBuddySwitchImApi.create_external_session` to return:

   ```python
   {
       "ok": True,
       "external_session_key": external_session_key,
       "identity": {"id": f"ext-fake-{len(self.created) + 1}", "type": "external"},
   }
   ```

2. Replace state assertions that expect per-message route maps with assertions that expect:

   ```python
   contact["external_session_key"] == "imsk-1"
   contact["external_identity_id"] == "ext-fake-1"
   contact["route"] == {"chat_id": "1", "sender": "a@example.com"}
   "routes" not in contact
   ```

3. Add a focused state test:

   ```python
   def test_inbound_sender_binds_external_identity_session_and_current_route(self) -> None:
       with tempfile.TemporaryDirectory() as temp_root:
           controller, api, _imsg = _controller(Path(temp_root))

           result = controller.handle_inbound_message(
               _row(sender="a@example.com", text="/actors", guid="guid-bind", chat_id="7")
           )
           state = controller.state_store.load()

       self.assertEqual(result["status"], "actors_listed")
       self.assertEqual(api.created[0]["external_session_key"], "imsk-1")
       contact = state["contacts"]["sender:a@example.com"]
       self.assertEqual(contact["external_session_key"], "imsk-1")
       self.assertEqual(contact["external_identity_id"], "ext-fake-1")
       self.assertEqual(contact["route"], {"chat_id": "7", "sender": "a@example.com"})
       self.assertNotIn("routes", contact)
   ```

Expected red state before implementation:

- `external_identity_id` is missing.
- `route` is missing.
- per-message route map still exists.

### Task 2: Replace Contact Schema

Files:

- Modify `tools/launcher/imessage_channel.py`
- Modify `tests/test_imessage_channel.py`

Steps:

1. Change `SCHEMA_VERSION` to `3`.
2. Change `_default_contact()` to include:

   ```python
   {
       "pending_actor_choices": {},
       "seen_inbound_keys": [],
       "sent_outbound_event_ids": [],
   }
   ```

   Do not include per-message route storage.

3. Add helpers:

   ```python
   def _contact_route(contact: dict[str, Any]) -> dict[str, Any] | None:
       value = contact.get("route")
       return dict(value) if isinstance(value, dict) and _valid_route(value) else None
   ```

   ```python
   def _set_contact_route(contact: dict[str, Any], route: dict[str, Any]) -> None:
       if not _valid_route(route):
           raise ChannelError("iMessage contact route is missing chat or sender")
       contact["route"] = dict(route)
   ```

   ```python
   def _valid_route(route: dict[str, Any]) -> bool:
       return any(route.get(field) for field in ("chat_id", "chat_identifier", "chat_guid", "sender"))
   ```

4. Make `ImessageChannelStateStore.load()` enforce current schema for existing state:

   ```python
   if payload.get("schema_version") != SCHEMA_VERSION:
       raise ChannelError("iMessage channel state schema is retired; reset the channel state file")
   ```

5. Make `_normalize_contact` allow only current fields:

   ```text
   external_session_key
   external_identity_id
   route
   active_identity_id
   pending_actor_choices
   seen_inbound_keys
   sent_outbound_event_ids
   ```

6. Remove `_contact_routes`.

Expected red/green checks:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_imessage_channel.py::ImessageChannelTests::test_default_state_path_uses_imessage_channel_schema_v2 -q
```

This test should be renamed to schema v3 and pass after implementation.

### Task 3: Bind External Identity And Route On Inbound

Files:

- Modify `tools/launcher/imessage_channel.py`
- Modify `tests/test_imessage_channel.py`

Steps:

1. Replace `_external_session_key(contact)` with a helper that ensures both session and identity:

   ```python
   def _external_session_binding(self, contact: dict[str, Any]) -> tuple[str, str]:
       existing_key = _contact_external_session_key(contact)
       existing_identity = _contact_external_identity_id(contact)
       if existing_key and existing_identity:
           return existing_key, existing_identity
       created = self.api.create_external_session(display_name=self.config.display_name)
       if created.get("ok") is not True:
           raise ChannelError(str((created.get("error") or {}).get("message") or "external session creation failed"))
       external_session_key = str(created.get("external_session_key") or "").strip()
       identity = created.get("identity")
       external_identity_id = str(identity.get("id") or "").strip() if isinstance(identity, dict) else ""
       identity_type = str(identity.get("type") or "").strip() if isinstance(identity, dict) else ""
       if not external_session_key:
           raise ChannelError("external session creation did not return external_session_key")
       if not external_identity_id or identity_type != "external":
           raise ChannelError("external session creation did not return external identity")
       contact["external_session_key"] = external_session_key
       contact["external_identity_id"] = external_identity_id
       return external_session_key, external_identity_id
   ```

2. Validate the API response identity:

   ```text
   identity must be an object
   identity.id must be a non-empty string
   identity.type must equal external
   ```

3. In `handle_inbound_message`, compute `route` and immediately store it on the contact:

   ```python
   route = _route_from_row(row, sender=sender)
   _set_contact_route(contact, route)
   external_session_key, _external_identity_id = self._external_session_binding(contact)
   ```

4. Keep `/actors`, numeric selection, and ordinary message behavior otherwise unchanged.

5. Remove the line that stores inbound `message_id` into per-message route state.

Expected result:

- Any inbound iMessage refreshes the current route for that sender/contact.
- The route exists before any outbound event for that external session is sent.

### Task 4: Rebuild Outbound Poll Routing

Files:

- Modify `tools/launcher/imessage_channel.py`
- Modify `tests/test_imessage_channel.py`

Steps:

1. Build poll targets from contacts that have:

   ```text
   external_session_key
   external_identity_id
   route
   ```

2. For each event:

   ```text
   read event
   skip already sent ids by ack retry path
   fetch message
   require content
   require sender_identity.id for display prefix
   send to contact.route
   record sent_outbound_event_ids after successful imsg.send
   ack after successful send
   ```

3. Remove outbound code that reads `reply_to` for route lookup.

4. Keep `reply_to` in fetched message/event untouched as IM metadata. Do not use it for route selection.

5. Do not ack if:

   ```text
   message fetch fails
   contact route is missing
   iMessage send fails
   required message fields are missing
   ```

6. Ack only after successful iMessage send, or when retrying ack for an event already marked sent.

Expected behavior tests:

- Actor reply event with `reply_to` sends through contact route.
- Actor proactive event with `reply_to=None` sends through the same contact route.
- Event with unrelated `reply_to` still sends through contact route.
- Message fetch failure does not ack.
- iMessage send failure does not mark sent and does not ack.
- Ack failure does not duplicate iMessage send on retry.

### Task 5: Replace Tests That Teach Old Routing

Files:

- Modify `tests/test_imessage_channel.py`

Tests to replace:

- Replace `test_actor_reply_is_prefixed_and_sent_to_recorded_route_once` with a test named:

  ```python
  def test_actor_reply_uses_contact_route_not_reply_to_route(self) -> None:
      with tempfile.TemporaryDirectory() as temp_root:
          controller, api, imsg = _controller(Path(temp_root))
          controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
          controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
          controller.handle_inbound_message(_row(text="ping", guid="guid-message", chat_id="9"))
          api.events_by_key["imsk-1"] = [
              {"event_id": "imev-reply-1", "message_id": "msg-reply-1", "reply_to": "unrelated-reply-id", **_actor_reply_identity()}
          ]
          api.messages["msg-reply-1"] = {
              "id": "msg-reply-1",
              "content": "pong",
              "reply_to": "unrelated-reply-id",
              **_actor_reply_identity(),
          }

          result = controller.poll_outbound_once(wait_ms=0)

      self.assertEqual(result["sent"], 1)
      self.assertEqual(
          imsg.sent[-1],
          {"route": {"chat_id": "9", "sender": "user-a@example.com"}, "text": "[Message From act-market-demo]\n\npong"},
      )
  ```

- Add:

  ```python
  def test_actor_proactive_external_message_uses_contact_route_without_reply_to(self) -> None:
      with tempfile.TemporaryDirectory() as temp_root:
          controller, api, imsg = _controller(Path(temp_root))
          controller.handle_inbound_message(_row(text="/actors", guid="guid-actors", chat_id="9"))
          controller.handle_inbound_message(_row(text="1", guid="guid-select", chat_id="9"))
          api.events_by_key["imsk-1"] = [
              {"event_id": "imev-proactive-1", "message_id": "msg-proactive-1", "reply_to": None, **_actor_reply_identity()}
          ]
          api.messages["msg-proactive-1"] = {
              "id": "msg-proactive-1",
              "content": "proactive hello",
              "reply_to": None,
              **_actor_reply_identity(),
          }

          result = controller.poll_outbound_once(wait_ms=0)

      self.assertEqual(result["sent"], 1)
      self.assertEqual(
          imsg.sent[-1],
          {"route": {"chat_id": "9", "sender": "user-a@example.com"}, "text": "[Message From act-market-demo]\n\nproactive hello"},
      )
  ```

- Replace `test_poll_outbound_acks_unrouteable_event_after_fetch` with:

  ```python
  def test_outbound_event_without_contact_route_is_not_acked(self) -> None:
      with tempfile.TemporaryDirectory() as temp_root:
          controller, api, imsg = _controller(Path(temp_root))
          controller.state_store.save(
              {
                  "schema_version": imessage_channel.SCHEMA_VERSION,
                  "contacts": {
                      "sender:user-a@example.com": {
                          "external_session_key": "imsk-1",
                          "external_identity_id": "ext-fake-1",
                          "pending_actor_choices": {},
                          "seen_inbound_keys": [],
                          "sent_outbound_event_ids": [],
                      }
                  },
              }
          )
          api.events_by_key["imsk-1"] = [
              {"event_id": "imev-no-route", "message_id": "msg-no-route", "reply_to": None, **_actor_reply_identity()}
          ]
          api.messages["msg-no-route"] = {
              "id": "msg-no-route",
              "content": "cannot route",
              "reply_to": None,
              **_actor_reply_identity(),
          }

          result = controller.poll_outbound_once(wait_ms=0)

      self.assertEqual(result["sent"], 0)
      self.assertEqual(imsg.sent, [])
      self.assertEqual(api.ack_calls, [])
  ```

  The setup should create an invalid current-schema state with an external session and identity but no route, then assert no send and no ack.

- Update worker tests so late outbound delivery does not depend on `reply_to`.

Expected tests after replacement:

- Tests describe external session route delivery, not source message route delivery.
- Tests no longer encode the old per-message route model.

### Task 6: Add Residue Checks

Files:

- Modify `tests/test_imessage_channel.py`

Add or extend residue tests over `tools/launcher/imessage_channel.py` only.

Required source checks:

```text
_contact_routes is absent
contact["routes"] is absent
message_id route storage is absent
route lookup from reply_to is absent
outbound code does not call message.get("reply_to") for route selection
```

Use narrow source checks and avoid broad terms like `route`, because `route` is still valid current channel state.

Keep existing boundary checks:

```text
iMessage channel does not import env.services.messages
iMessage channel does not import env.repos.messages
iMessage channel does not call send_im_message
iMessage channel does not call send_external_session_message
```

### Task 7: Focused Verification

Run focused iMessage tests:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_imessage_channel.py -q
```

Expected:

```text
all tests pass
```

Run projection and API boundary tests:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_im_web_management_projection.py tests/test_im_http_router.py tests/test_external_im_session.py -q
```

Expected:

```text
all tests pass
```

Run IM core regression tests that prove reply remains a wrapper:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_im_product_core.py::ImProductCoreTests::test_send_im_reply_normalizes_original_sender_to_target_identity_and_marks_replied \
  tests/test_im_product_core.py::ImProductCoreTests::test_send_im_message_returns_final_target_identity_for_explicit_and_reply_to_targets \
  -q
```

Expected:

```text
all tests pass
```

Run repo consistency checks:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py -q
```

Expected:

```text
all tests pass
```

## 9. Acceptance Contract

The implementation is accepted only when these sentences are true and tested:

1. An iMessage inbound sender creates or reuses one external session, stores the returned external identity id, and stores the current iMessage route on the contact.
2. An actor reply to that external identity is delivered by the iMessage channel using the contact route, not `reply_to`.
3. An actor proactive message to that external identity is delivered by the same iMessage channel path without `reply_to`.
4. An event is acked only after successful iMessage send, or during ack retry for an event already recorded as sent.
5. The iMessage channel source does not contain the old per-message route map or `reply_to` route lookup.
6. IM API and IM core are unchanged in business semantics and remain black boxes from the channel point of view.

## 10. Explicit Non-Goals

Do not implement:

- General outbound channel framework.
- New delivery queue.
- New IM API fields for channel route.
- Web UI changes.
- Actor tool changes.
- IM core target resolver changes.
- State migration for retired iMessage per-message route maps.
- Compatibility fallback for old state shape.

## 11. Risk And Handling

Risk: Existing local iMessage channel state with schema version 2 stops loading.

Handling: This is expected under forward rebuild. The operator should reset the local iMessage channel state file before running the rebuilt channel. Do not preserve the old schema in active code.

Risk: A contact has an external session but no route.

Handling: Treat this as invalid current channel state. Do not ack outbound events without a route, because acking would lose a deliverable message.

Risk: Tests accidentally keep teaching old semantics.

Handling: Replace old tests rather than adding new tests beside them. Add narrow residue checks for the old route model in `imessage_channel.py`.

## 12. Completion Checklist

- [ ] `docs/spec` development and test plan written before implementation.
- [ ] Failing tests created for external identity route delivery.
- [ ] iMessage channel state schema rebuilt to current shape only.
- [ ] Inbound stores external identity and current route.
- [ ] Outbound uses contact route for reply and proactive actor messages.
- [ ] `reply_to` route lookup removed.
- [ ] Per-message route map removed.
- [ ] iMessage source residue checks added.
- [ ] Focused tests pass.
- [ ] Projection/API boundary tests pass.
- [ ] IM core reply-wrapper tests pass.
- [ ] Repo consistency checks pass.

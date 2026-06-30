# Phase 03: Web Frontend Uses `/api/im/*`

Date: 2026-06-30

## Phase Goal

Move the Web Management frontend from the retired `/api/web/im/*` route family to the unified `/api/im/*` contract, and make browser event processing explicit:

```text
GET /api/im/events
GET /api/im/messages/<message_id>
POST /api/im/events/ack
```

The browser must not send Authorization headers or store `connection_key`.

## Code Research Findings

- `tools/launcher/assets/web-management/app.js` still builds:
  - `/api/web/im/events?identity_id=...`
  - `/api/web/im/conversations/direct?identity_id=...`
- `ensureWebImSession()` still calls `/api/web/im/session`.
- `sendImDraft()` still posts to `/api/web/im/messages`.
- `pollImEventsOnce()` expects the server events response to include `messages` and calls `applyImEventsPayload()`.
- `applyImEventsPayload()` records `payload.messages`; this encodes the old Web BFF behavior.
- `refreshSelectedActorConversation()` calls `buildWebImConversationUrl()`.
- `tests/web_management_ui_contract.test.js` currently asserts the old routes are present and `/api/im` is absent.
- `tests/web_management_ui_state.test.js` currently expects old event/conversation URLs.

## Involved Files

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/web_management_ui_state.test.js`

## Development Plan

1. Update Node contract tests:
   - require `/api/im/session`, `/api/im/messages`, `/api/im/events`, `/api/im/events/ack`, and `/api/im/conversations/direct`;
   - forbid `/api/web/im`;
   - forbid browser `Authorization`;
   - forbid browser `connection_key`.
2. Update state tests:
   - `buildImEventsUrl(15000)` returns `/api/im/events?wait_ms=15000`;
   - `buildImConversationUrl("act-market demo", 20)` returns `/api/im/conversations/direct?identity_id=act-market%20demo&limit=20`;
   - add coverage for `buildImMessageUrl("msg-1")`;
   - add coverage for `buildImAckPayload("imev-1")`.
3. Rename frontend concepts:
   - `buildWebImConversationUrl` -> `buildImConversationUrl`;
   - `ensureWebImSession` -> `ensureImSession`.
4. Change fetch URLs:
   - `/api/web/im/session` -> `/api/im/session`;
   - `/api/web/im/messages` -> `/api/im/messages`;
   - `/api/web/im/events` -> `/api/im/events`;
   - `/api/web/im/conversations/direct` -> `/api/im/conversations/direct`.
5. Replace BFF event payload handling:
   - remove reliance on `payload.messages` from event reads;
   - for each event with `message_id`, fetch `/api/im/messages/<message_id>`;
   - record the fetched message when it belongs to the selected or known actor conversation;
   - ack with `POST /api/im/events/ack` only after message fetch succeeds;
   - refresh the selected actor console/conversation if any selected actor message was processed.
6. Keep browser request headers limited to JSON `Content-Type` where needed.
7. Export renamed builders used by tests.

## Test Plan

Focused red command before implementation:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected before implementation: tests fail because the frontend still contains `/api/web/im/*`, excludes `/api/im`, and lacks the ack/message URL helpers.

Focused green command after implementation:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected after implementation: all selected Node tests pass.

## Acceptance Criteria

- Active frontend source contains no `/api/web/im`.
- Frontend calls `/api/im/session`, `/api/im/messages`, `/api/im/events`, `/api/im/messages/<id>`, `/api/im/events/ack`, and `/api/im/conversations/direct`.
- `buildImEventsUrl(15000)` does not include `identity_id`.
- Browser code does not contain `Authorization`.
- Browser code does not contain `connection_key`.
- Event polling no longer expects event reads to include message bodies or implicit ack.
- Ack payload shape is exactly `{"event_id":"..."}`.

## Risks

- Event processing now performs multiple requests per poll; errors must stop before ack so failed fetches remain visible on later polls.
- Filtering by selected actor moves client-side; a wrong filter could hide valid messages until direct conversation refresh.
- Node state tests are not a full browser runtime, so Phase 06 still needs an end-to-end contract slice at the Python service level.

## Execution Record

- Updated UI contract tests to require `/api/im/session`, `/api/im/messages`, `/api/im/events`, `/api/im/events/ack`, and `/api/im/conversations/direct`.
- Updated UI contract tests to forbid `/api/web/im`, browser `Authorization`, and `connection_key`.
- Updated UI state tests for:
  - `buildImEventsUrl(15000)`;
  - `buildImConversationUrl("act-market demo", 20)`;
  - `buildImMessageUrl("msg demo/1")`;
  - `buildImAckPayload("imev-1")`.
- Replaced the old embedded event `messages` state test with fetched-message recording coverage.
- Renamed frontend helpers:
  - `buildWebImConversationUrl` -> `buildImConversationUrl`;
  - `ensureWebImSession` -> `ensureImSession`.
- Changed frontend fetch URLs to `/api/im/*`.
- Removed `applyImEventsPayload()` because it encoded the retired server-shaped Web BFF event payload.
- Updated event polling to:
  - read `/api/im/events`;
  - fetch each message through `/api/im/messages/<message_id>`;
  - record fetched messages that touch a known or selected actor conversation;
  - ack each event through `/api/im/events/ack` after message fetch succeeds;
  - refresh the selected actor console and direct conversation when a selected actor message is processed.

## Test Results

Red command:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result before implementation:

```text
2 failing test files
```

Expected failures:

- frontend bundle did not include `/api/im/session`;
- `buildImEventsUrl(15000)` still returned `/api/web/im/events?...`.

Green command:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result after implementation:

```text
2 test files passed; 0 failed
```

## Residue Scan Result

Command:

```bash
rg -n "/api/web/im|buildWebImConversationUrl|ensureWebImSession|applyImEventsPayload|Authorization|connection_key|participant_token|event_cursor|cursor=" tools/launcher/assets/web-management/app.js tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js -S
```

Result:

```text
tests/web_management_ui_contract.test.js:148: negative assertion excluding /api/web/im
tests/web_management_ui_contract.test.js:150: negative assertion excluding connection_key
tests/web_management_ui_contract.test.js:152: negative assertion excluding participant_token
tests/web_management_ui_contract.test.js:153: negative assertion excluding event_cursor
tests/web_management_ui_contract.test.js:155: negative assertion excluding cursor=
tests/web_management_ui_contract.test.js:156: negative assertion excluding Authorization
```

No active frontend source references the retired Web IM route family, browser Authorization, or raw credential state.

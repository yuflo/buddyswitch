# Unified IM API Rebuild-Forward Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Web and external IM entrypoints onto one `/api/im/*` contract, delete the `/api/web/im/*` live route family, and remove the Web BFF message/event/conversation fork without changing the identity foundation.

**Architecture:** `/api/im/*` becomes the only live HTTP IM product contract. `ImHttpRouter` resolves either Bearer `connection_key` auth or the Web Management server-owned IM connection, then delegates all IM semantics to `ExternalImSession`. `WebManagementService` owns Web identity provisioning only; it does not own message send, event read, event ack, message fetch, conversation, or disposition semantics.

**Tech Stack:** Python launcher HTTP service, `ExternalImSession`, `scripts/env/services/messages.py` Central IM service, Web Management vanilla JavaScript frontend, Python `pytest`, Node UI contract/state tests.

---

## Task Objective Restatement

Work in `worktrees/fea-im`.

The requested upgrade is a rebuild-forward cleanup of the IM HTTP architecture:

- Make `/api/im/*` the standard API for external users, local channel adapters, and Web interface.
- Delete `/api/web/im/*` as a live product surface instead of preserving a compatibility branch.
- Use the current identity system as the lower-level foundation; do not redesign `IdentityRef`, `ActorAddress`, external identity ids, connection records, or participant storage.
- Move Web interface behavior onto the same IM contract as every other caller.
- Delete duplicated Web BFF IM semantics and shrink `web_management.py`.
- Keep the end-to-end user loop covered: browser send -> `/api/im/*` -> Task Sys wake -> actor reply -> `/api/im/*` event/message/ack -> browser-visible conversation.
- Verify both behavior and live-surface residue. Tests passing without residue scans is not enough; residue scans without behavior tests are not enough.

## Bitter Principles Applied

From `docs/bitter/2026-06-25-built-in-product-interface-principles.md`:

- IM is the product capability.
- HTTP routes and Web UI are projections.
- Product semantics must live behind `ExternalImSession` and message service, not inside Web route helpers.

From `docs/bitter/2026-06-02-residue-cleanup-principles.md`:

- A semantic replacement is unfinished while any live source, test, UI asset, or runtime discovery path still teaches `/api/web/im/*`.
- Historical memos are evidence, not cleanup targets. The residue gate must scan live surfaces, not old planning notes.

From `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`:

- Local unit coverage is insufficient.
- The final verification must include a browser/Web Management path that crosses send, wake, reply, event read, message fetch, ack, and conversation display semantics.

From `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`:

- A small `/api/web/im/*` special case is still the wrong boundary if future Web IM work keeps adding sibling behavior there.
- The stable shared boundary is `/api/im/*`; Web variation belongs in auth context resolution only.

From `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`:

- `web_management.py` is already a large shared surface. Removing IM product semantics from it reduces future conflict pressure.

From `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

- The implementation plan should rely first on focused in-process contract tests and UI state tests.
- Runtime smoke tests are useful after focused tests, but any service-starting verification must own cleanup.

## Current-State Evidence

Recent relevant branch history in `fea-im`:

- `3d55b81 Optimize iMessage IM API boundary`
- `b46ce12 Complete task sys IM observability`
- `85017e0 docs: record fea webui daemon merge verification`

Current implementation facts:

- `tools/launcher/im_http_router.py` owns `/api/im/*`, but protected routes only authenticate through Bearer `connection_key`.
- `tools/launcher/web_management.py` constructs both `ExternalImSession` and `ImHttpRouter`, then handles `/api/web/im/*` before `/api/im/*`.
- `tools/launcher/web_management.py` still owns Web-specific IM send/events/conversation helpers:
  - `ensure_web_im_identity`
  - `_handle_web_im`
  - `_web_im_connection`
  - `_web_im_send_message`
  - `_web_im_events`
  - `_web_im_direct_conversation`
  - `_actor_identity_id_from_query`
  - `_actor_identity_id`
  - `_im_event_targets_identity`
- `tools/launcher/assets/web-management/app.js` calls:
  - `/api/web/im/session`
  - `/api/web/im/messages`
  - `/api/web/im/events`
  - `/api/web/im/conversations/direct`
- `tests/web_management_ui_contract.test.js` currently asserts that the frontend excludes `/api/im`, which directly contradicts the target architecture.
- `tests/test_external_im_projection_contract.py` currently treats Web BFF event shaping as a first-class projection contract.
- `docs/arch/web-interface-call-architecture.md` currently documents two IM projection route families.

Current size pressure:

```text
1122 tools/launcher/web_management.py
 204 tools/launcher/im_http_router.py
 181 tools/launcher/external_im_session.py
 140 tools/launcher/web_im_identity.py
1194 tools/launcher/assets/web-management/app.js
2030 tests/test_web_management.py
```

The cleanup should reduce Web Management IM-specific code, not merely move it behind another route alias.

## Target Architecture

```text
External adapter / iMessage channel
  -> /api/im/* with Authorization: Bearer <connection_key>
  -> ImHttpRouter
  -> ExternalImSession
  -> scripts/env/services/messages.py

Web browser
  -> /api/im/* without raw connection_key exposure
  -> WebManagementService-hosted ImHttpRouter
  -> Web server-owned IM connection provider
  -> ExternalImSession
  -> scripts/env/services/messages.py
```

Only auth context differs:

- External caller auth: Bearer `connection_key`.
- Web caller auth: server-side `WebImIdentityProvider.ensure()` returns the Web Management external connection.

Message semantics do not differ:

- actor discovery
- send
- event read
- event ack
- message fetch
- replies
- direct conversation
- disposition

## Non-Negotiable Design Rules

- Do not keep `/api/web/im/*` as a compatibility route, alias, redirect, or thin proxy.
- Do not create a second Web message service.
- Do not let `WebManagementService` call `ExternalImSession.send_message`, `read_events`, `get_message`, `ack_event`, or `get_direct_conversation` directly.
- Do not expose `connection_key` to browser JavaScript or Web API responses.
- Do not change the identity model or persisted Central IM data model.
- Do not rewrite historical memos to hide past architecture. Historical `docs/memo` and old `docs/spec` files can remain as history.
- Do update live architecture docs and live tests so they teach only the new route family.

## API Contract Decisions

### `GET /api/im/session`

Add a Web-safe session/introspection route under `/api/im/*`.

Behavior:

- With Bearer auth, returns the authenticated external identity.
- With Web Management server auth, creates or reuses the server-owned Web IM identity and returns that identity.
- Response never contains `connection_key`, `participant_token`, `event_cursor`, or raw repo state.

Expected response:

```json
{
  "ok": true,
  "identity": { "id": "ext-...", "type": "external" },
  "client_kind": "web-management",
  "display_name": "BuddySwitch Web"
}
```

For Bearer callers, `client_kind` and `display_name` may be absent unless they are already available through authenticated connection metadata. The browser must not depend on those optional fields.

### `POST /api/im/connections`

Keep current external connection creation.

This remains the only route that returns a raw `connection_key`. Web UI must not call it.

### Protected `/api/im/*` Routes

These routes use the resolved connection from either Bearer auth or Web server auth:

- `GET /api/im/actors`
- `POST /api/im/messages`
- `GET /api/im/events`
- `POST /api/im/events/ack`
- `GET /api/im/messages/<message_id>`
- `GET /api/im/messages/<message_id>/replies`
- `PATCH /api/im/messages/<message_id>/disposition`
- `GET /api/im/conversations/direct?identity_id=...`

### Event Semantics

`GET /api/im/events` is a connection-wide event stream.

- It rejects caller-supplied cursor.
- It does not fetch message bodies.
- It does not ack events.
- It does not filter by `identity_id`.

Every consumer, including Web UI, follows the same sequence:

```text
GET /api/im/events
GET /api/im/messages/<message_id>
POST /api/im/events/ack
GET /api/im/conversations/direct?identity_id=<selected actor> when full history is needed
```

This deliberately deletes the current hidden Web BFF behavior:

```text
read connection-wide events -> fetch message -> auto ack -> filter by selected actor
```

That behavior is convenient but structurally wrong because it makes the server consume events under a per-conversation-looking Web route.

## Implementation Plan

### Task 1: Add Unified Auth Context To `ImHttpRouter`

**Files:**

- Modify: `tools/launcher/im_http_router.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_external_im_projection_contract.py` or replace it with focused unified projection tests

- [ ] Add a failing router test proving no-provider behavior remains strict:

  ```text
  GET /api/im/events without Authorization and without a web auth provider -> 401
  ```

- [ ] Add a failing router test proving Web auth provider behavior:

  ```text
  ImHttpRouter(web_connection_provider=fake_provider)
    GET /api/im/session without Authorization -> 200, identity returned, no connection_key
    POST /api/im/messages without Authorization -> delegates to ExternalImSession.send_message with fake provider connection
    GET /api/im/events without Authorization -> delegates to ExternalImSession.read_events with fake provider connection
    POST /api/im/events/ack without Authorization -> delegates to ExternalImSession.ack_event with fake provider connection
  ```

- [ ] Implement a minimal auth resolver in `ImHttpRouter`.

  Required shape:

  ```text
  Authorization Bearer present -> authenticate via ExternalImSession.authenticate
  Authorization missing and web provider present -> provider returns identity + connection
  Authorization missing and no provider -> E_IM_AUTH
  malformed Authorization -> E_IM_AUTH
  ```

- [ ] Add `GET /api/im/session`.

  It must resolve auth through the same path and return sanitized identity/session metadata.

- [ ] Keep `POST /api/im/connections` behavior unchanged.

- [ ] Run focused tests:

  ```bash
  python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_projection_contract.py
  ```

  Expected: all selected tests pass.

### Task 2: Rewire `WebManagementService` To Host Only Web IM Auth

**Files:**

- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_web_management_projection.py`

- [ ] Add a failing test proving `/api/web/im/session`, `/api/web/im/messages`, `/api/web/im/events`, and `/api/web/im/conversations/direct` are not live routes.

  Expected behavior: `404 NOT_FOUND`.

- [ ] Add a failing Web Management test for the new Web-authenticated `/api/im/session`.

  Assertions:

  - stable Web identity is reused across service instances
  - response contains `identity`
  - response excludes `connection_key`
  - persisted local Web identity record may contain `connection_key` with file permission protection

- [ ] Rewrite the existing Web send/history test to use unified `/api/im/*`:

  ```text
  GET /api/im/session
  POST /api/im/messages
  actor sends reply through message_service
  GET /api/im/events
  GET /api/im/messages/<reply_id>
  POST /api/im/events/ack
  GET /api/im/conversations/direct?identity_id=<actor>&limit=20
  ```

  Assertions:

  - send still wakes actor
  - browser response does not expose `connection_key`
  - event read does not auto-ack
  - explicit ack removes the event from later reads
  - direct conversation includes sent and reply messages

- [ ] Delete `_handle_web_im`, `_web_im_send_message`, `_web_im_events`, and `_web_im_direct_conversation`.

- [ ] Keep a small `ensure_web_im_identity` or equivalent provider method only for auth context.

- [ ] Remove `_im_event_targets_identity` if no longer used.

- [ ] Reduce `WebManagementService.__init__` so it passes the Web connection provider into `ImHttpRouter`.

- [ ] Run focused tests:

  ```bash
  python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_web_management_projection.py
  ```

  Expected: all selected tests pass.

### Task 3: Move Web Frontend To `/api/im/*`

**Files:**

- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tests/web_management_ui_contract.test.js`
- Modify: `tests/web_management_ui_state.test.js`

- [ ] Rename frontend helper concepts from Web IM route language to IM route language:

  - `buildWebImConversationUrl` -> `buildImConversationUrl`
  - `ensureWebImSession` -> `ensureImSession`

- [ ] Change URLs:

  ```text
  /api/web/im/session              -> /api/im/session
  /api/web/im/messages             -> /api/im/messages
  /api/web/im/events               -> /api/im/events
  /api/web/im/conversations/direct -> /api/im/conversations/direct
  ```

- [ ] Add frontend event processing steps:

  ```text
  read events from /api/im/events
  for each event with message_id:
    fetch /api/im/messages/<message_id>
    merge message into UI state if it belongs to a known or selected actor conversation
    ack through /api/im/events/ack after message fetch succeeds
  refresh selected actor console/conversation when a selected actor message was processed
  ```

- [ ] Do not add browser Authorization headers.

- [ ] Do not put `connection_key` in JS state.

- [ ] Update UI contract tests so they include `/api/im/*` and exclude `/api/web/im`.

- [ ] Update UI state tests to expect:

  ```text
  app.buildImEventsUrl(15000) -> /api/im/events?wait_ms=15000
  app.buildImConversationUrl("act-market demo", 20) -> /api/im/conversations/direct?identity_id=act-market%20demo&limit=20
  ```

- [ ] Add UI state coverage for ack payload:

  ```text
  POST /api/im/events/ack with {"event_id": "..."}
  ```

- [ ] Run Node tests:

  ```bash
  node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
  ```

  Expected: all selected tests pass.

### Task 4: Delete Web IM Projection Contract Residue

**Files:**

- Modify or delete: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `docs/arch/web-interface-call-architecture.md`

- [ ] Remove tests that describe Web BFF event shaping as a product contract.

- [ ] Replace them with tests that prove:

  ```text
  WebManagementService exposes /api/im/* through the shared ImHttpRouter
  WebManagementService does not expose /api/web/im/*
  WebManagementService does not call message_service directly for IM semantics
  ```

- [ ] Update architecture docs:

  New wording:

  ```text
  /api/im/* is the single IM HTTP product contract for channel adapters, third-party callers, and Web interface.
  Web interface differs only by server-owned auth context; it does not own a separate IM route family.
  ExternalImSession owns external participant and actor-directed IM application semantics.
  ```

- [ ] Remove live doc wording that describes `/api/web/im/*` as a browser-facing IM projection.

- [ ] Run focused tests:

  ```bash
  python3 -m pytest -q tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py
  ```

  Expected: all selected tests pass, or deleted tests are no longer collected and equivalent replacement tests pass.

### Task 5: Add Live-Surface Residue Gates

**Files:**

- Modify: `tests/test_im_web_management_projection.py` or create a focused residue test under `tests/`
- Modify: `tests/web_management_ui_contract.test.js`

- [ ] Add a scoped Python residue test over live server surfaces:

  ```text
  tools/launcher/web_management.py
  tools/launcher/im_http_router.py
  tools/launcher/external_im_session.py
  tools/launcher/web_im_identity.py
  tools/launcher/assets/web-management/app.js
  tests/test_web_management.py
  tests/test_im_http_router.py
  tests/test_im_web_management_projection.py
  tests/test_external_im_projection_contract.py
  tests/web_management_ui_contract.test.js
  tests/web_management_ui_state.test.js
  docs/arch/web-interface-call-architecture.md
  ```

- [ ] The residue test must fail on live positive references to:

  ```text
  /api/web/im
  _handle_web_im
  _web_im_send_message
  _web_im_events
  _web_im_direct_conversation
  _im_event_targets_identity
  assertExcludes(appJs, '/api/im')
  ```

- [ ] Allow negative assertions only when they enforce absence of the old route family.

- [ ] Add the equivalent Node contract assertion:

  ```text
  app.js includes /api/im/session, /api/im/messages, /api/im/events, /api/im/events/ack, /api/im/conversations/direct
  app.js excludes /api/web/im
  app.js excludes Authorization
  app.js excludes connection_key
  ```

- [ ] Run residue scans manually after tests:

  ```bash
  rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|assertExcludes\\(appJs, '/api/im'\\)" tools/launcher tests docs/arch -S
  ```

  Expected: no hits except negative assertions that explicitly enforce absence.

### Task 6: Focused End-To-End Contract Slice

**Files:**

- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_external_reply_loop.py` only if the existing loop does not cover explicit ack through Web-authenticated `/api/im/*`

- [ ] Add or update one contract test with this sentence:

  ```text
  Browser-style Web request sends actor-directed IM through /api/im/messages, actor reply becomes visible through /api/im/events, browser fetches the reply through /api/im/messages/<id>, browser acks through /api/im/events/ack, and direct conversation shows both messages without exposing connection_key.
  ```

- [ ] Keep iMessage channel adapter tests on Bearer `/api/im/*`.

- [ ] Run:

  ```bash
  python3 -m pytest -q tests/test_im_http_router.py tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
  ```

  Expected: all selected tests pass.

### Task 7: Broader Verification

Run focused contract and UI checks first:

```bash
python3 -m py_compile tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/external_im_session.py tools/launcher/web_im_identity.py
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_session.py tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Then run residue scan:

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|assertExcludes\\(appJs, '/api/im'\\)" tools/launcher tests docs/arch -S
```

Expected:

- Compile exits 0.
- Python tests exit 0.
- Node tests exit 0.
- Residue scan has no live positive hits.

If a broader suite is needed, run it only after focused checks pass. Avoid service-starting broad verification until lifecycle ownership is clear.

## Files Expected To Shrink Or Simplify

`tools/launcher/web_management.py` should lose:

- `_handle_web_im`
- `_web_im_send_message`
- `_web_im_events`
- `_web_im_direct_conversation`
- `_actor_identity_id_from_query`
- `_actor_identity_id` if no other route uses it
- `_im_event_targets_identity`

`tools/launcher/assets/web-management/app.js` may grow slightly in client event handling because explicit ack moves out of the server BFF, but this is acceptable because the product semantics become visible and unified.

`tests/test_web_management.py` should stop treating `/api/web/im/*` as a product route family.

`docs/arch/web-interface-call-architecture.md` should stop describing two IM route families.

## Out Of Scope

- Redesigning identity ids, actor identity, external identity, `ActorAddress`, participant refs, or Central IM persistence.
- Rewriting historical `docs/memo` or old `docs/spec` records.
- Changing iMessage channel behavior except to ensure it still passes against the unified `/api/im/*` contract.
- Adding a generic auth framework or permission system.
- Adding Web-only IM convenience endpoints outside `/api/im/*`.

## Acceptance Checklist

- [ ] Active Web frontend source contains no `/api/web/im`.
- [ ] Active Python launcher source contains no `/api/web/im` route handler.
- [ ] `/api/web/im/*` returns 404 in Web Management tests.
- [ ] Browser/Web Management send path uses `POST /api/im/messages`.
- [ ] Browser/Web Management event path uses `GET /api/im/events`, `GET /api/im/messages/<id>`, and `POST /api/im/events/ack`.
- [ ] `GET /api/im/events` does not auto-ack.
- [ ] Browser responses and JS state do not expose `connection_key`.
- [ ] External adapter Bearer flow still works.
- [ ] Web server-owned identity is stable and remains server-side.
- [ ] `web_management.py` no longer owns IM message/event/conversation semantics.
- [ ] Live architecture docs describe one `/api/im/*` contract.
- [ ] Scoped residue scan over `tools/launcher`, `tests`, and `docs/arch` has no stale positive hits.
- [ ] Focused Python and Node verification commands pass.

## Final Definition Of Done

The rebuild is complete only when both statements are proven:

```text
External caller or iMessage adapter -> /api/im/* with Bearer key -> actor-directed IM conversation works with explicit event ack.
```

```text
Web browser -> /api/im/* with server-owned Web identity -> actor-directed IM conversation works with explicit event ack and no connection_key exposure.
```

The implementation must not leave `/api/web/im/*` as a live compatibility path.

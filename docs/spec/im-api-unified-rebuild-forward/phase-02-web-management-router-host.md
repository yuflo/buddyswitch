# Phase 02: Web Management Hosts Only Web IM Auth

Date: 2026-06-30

## Phase Goal

Rewire `WebManagementService` so Web browser calls use `/api/im/*` through the shared `ImHttpRouter`. Web Management may provision the server-owned Web IM identity, but it must no longer own message send, event read, event ack, direct conversation, or Web-specific IM route semantics.

## Code Research Findings

- `WebManagementService.__init__` creates both `ExternalImSession` and `ImHttpRouter`, but does not pass a Web auth provider into the router.
- `handle_api()` checks `/api/web/im/*` before `/api/im/*`, so the old Web route family remains live.
- `WebManagementService` still defines IM product helpers:
  - `ensure_web_im_identity`
  - `_handle_web_im`
  - `_web_im_connection`
  - `_web_im_send_message`
  - `_web_im_events`
  - `_web_im_direct_conversation`
  - `_actor_identity_id_from_query`
  - `_actor_identity_id`
  - `_im_event_targets_identity`
- `tests/test_web_management.py` encodes the old BFF behavior:
  - `/api/web/im/session`
  - `/api/web/im/messages`
  - `/api/web/im/events?identity_id=...`
  - `/api/web/im/conversations/direct`
  - hidden message fetch and event ack inside the Web events route.
- `tests/test_im_web_management_projection.py` proves Web Management exposes Bearer `/api/im/*`, but does not yet prove browser-style unauthenticated `/api/im/*`.
- Phase 01 added `ImHttpRouter(web_connection_provider=...)` and `GET /api/im/session`, so this phase can remove Web-specific semantics without adding a compatibility alias.

## Involved Files

- Modify: `tools/launcher/web_management.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_web_management_projection.py`
- Read-only in this phase: `tools/launcher/im_http_router.py`
- Read-only in this phase: `tools/launcher/web_im_identity.py`

## Development Plan

1. Add/replace tests in `tests/test_web_management.py`:
   - `/api/web/im/session`, `/api/web/im/messages`, `/api/web/im/events`, and `/api/web/im/conversations/direct` return `404 NOT_FOUND`.
   - stable Web identity is available at `GET /api/im/session`, reused across service instances, and does not expose raw credentials.
   - invalid persisted Web identity is replaced via `GET /api/im/session`.
   - browser-style send/reply/read/fetch/ack/history loop uses only `/api/im/*`.
2. Rewrite the current Web send/history test to prove:
   - `GET /api/im/session`;
   - `POST /api/im/messages`;
   - actor reply through `message_service`;
   - `GET /api/im/events` returns the reply event and does not auto-ack;
   - `GET /api/im/messages/<reply_id>` fetches the reply body;
   - `POST /api/im/events/ack` removes the event from later reads;
   - `GET /api/im/conversations/direct?identity_id=<actor>&limit=20` returns sent and reply messages;
   - responses do not expose `connection_key`.
3. Replace the old actor-scoped Web event test with a unified route test:
   - `/api/im/events` is connection-wide and does not require `identity_id`;
   - the browser, not the server BFF, decides which fetched messages belong to a selected conversation.
4. Add or adjust `tests/test_im_web_management_projection.py` coverage:
   - Web Management delegates browser-style `/api/im/*` to `ImHttpRouter`;
   - live `/api/web/im/*` routes are absent.
5. Implement `WebManagementService` changes:
   - pass `web_connection_provider=self.ensure_web_im_identity` to `ImHttpRouter`;
   - remove the `/api/web/im/*` dispatch branch;
   - delete `_handle_web_im`, `_web_im_connection`, `_web_im_send_message`, `_web_im_events`, `_web_im_direct_conversation`, `_actor_identity_id_from_query`, `_actor_identity_id`, and `_im_event_targets_identity` if unused.
6. Keep `ensure_web_im_identity()` as the only Web IM method in Web Management.

## Test Plan

Focused red command before implementation:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_web_management_projection.py
```

Expected before implementation: new tests fail because `/api/im/session` is not Web-authenticated through Web Management and old `/api/web/im/*` routes still return live responses.

Focused green command after implementation:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_web_management_projection.py
```

Expected after implementation: all selected tests pass.

## Acceptance Criteria

- `WebManagementService` exposes browser-style Web IM through `/api/im/*` without browser Authorization headers.
- `/api/web/im/*` is not a live API family and returns `404 NOT_FOUND`.
- Web session responses do not expose `connection_key`, `participant`, `participant_token`, `event_cursor`, or raw `connection`.
- The persisted private Web identity may contain `connection_key` and remains file-protected.
- Event reads do not implicitly ack.
- Explicit ack removes the event from later reads.
- `web_management.py` no longer calls `ExternalImSession.send_message`, `read_events`, `get_message`, `ack_event`, or `get_direct_conversation` directly for Web IM semantics.

## Risks

- Tests that still expect `/api/web/im/*` may hide live compatibility residue if not replaced in the same phase.
- Moving hidden event fetch/ack out of the server changes frontend responsibilities; Phase 03 must update the browser code before final acceptance.
- Directly returning provider records through the router would expose the private `connection_key`; Phase 01 session sanitization must remain intact.

## Execution Record

- Replaced stable Web IM identity tests to use `GET /api/im/session`.
- Added explicit 404 tests for the retired `/api/web/im/*` family.
- Rewrote the Web send/reply/read path to use:
  - `GET /api/im/session`
  - `POST /api/im/messages`
  - `GET /api/im/events`
  - `GET /api/im/messages/<message_id>`
  - `POST /api/im/events/ack`
  - `GET /api/im/conversations/direct`
- Replaced actor-scoped Web events coverage with connection-wide `/api/im/events` coverage.
- Updated projection tests so browser-style `/api/im/*` goes through `ImHttpRouter`.
- Added source guard against `web_management.py` directly calling `self._im_session.send_message`, `read_events`, `get_message`, `ack_event`, or `get_direct_conversation`.
- Passed `web_connection_provider=self.ensure_web_im_identity` into `ImHttpRouter`.
- Removed the `/api/web/im/*` dispatch branch from `WebManagementService.handle_api()`.
- Deleted `_handle_web_im`, `_web_im_connection`, `_web_im_send_message`, `_web_im_events`, `_web_im_direct_conversation`, `_actor_identity_id_from_query`, `_actor_identity_id`, and `_im_event_targets_identity`.
- Updated remaining positive Python test calls from `/api/web/im/*` to `/api/im/*`.

## Test Results

Red command:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_web_management_projection.py
```

Result before implementation:

```text
19 failed, 7 passed, 40 subtests passed
```

Expected failures:

- Browser-style `/api/im/session` returned `401`.
- `/api/web/im/*` routes were still live.
- `web_management.py` still contained direct `self._im_session.*` Web IM semantic calls.

Green command:

```bash
python3 -m py_compile tools/launcher/web_management.py && python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_web_management_projection.py
```

Result after implementation:

```text
13 passed, 53 subtests passed in 0.09s
```

## Residue Scan Result

Command:

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|self\\._im_session\\.(send_message|read_events|get_message|ack_event|get_direct_conversation)" tools/launcher/web_management.py tests/test_web_management.py tests/test_im_web_management_projection.py -S
```

Result after implementation:

```text
tests/test_im_web_management_projection.py:179: negative 404 assertion for /api/web/im/session
tests/test_im_web_management_projection.py:180: negative 404 assertion for /api/web/im/messages
tests/test_im_web_management_projection.py:181: negative 404 assertion for /api/web/im/events
tests/test_im_web_management_projection.py:182: negative 404 assertion for /api/web/im/conversations/direct
tests/test_web_management.py:1122: negative 404 assertion for /api/web/im/session
tests/test_web_management.py:1123: negative 404 assertion for /api/web/im/messages
tests/test_web_management.py:1124: negative 404 assertion for /api/web/im/events
tests/test_web_management.py:1125: negative 404 assertion for /api/web/im/conversations/direct
```

No Python live route handler or direct Web IM session semantic call remains. Frontend and architecture-doc residue remain expected for Phases 03-05.

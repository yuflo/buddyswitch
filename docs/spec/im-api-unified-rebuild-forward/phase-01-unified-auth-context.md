# Phase 01: Unified IM Auth Context

Date: 2026-06-30

## Phase Goal

Make `tools/launcher/im_http_router.py` resolve one authenticated IM connection context for both callers:

- external callers with `Authorization: Bearer <connection_key>`;
- Web Management callers without browser-visible credentials, via a server-owned Web IM connection provider.

This phase also adds `GET /api/im/session` as the sanitized session introspection route. It does not remove `/api/web/im/*`; that belongs to Phase 02 after the shared router can serve Web callers.

## Code Research Findings

- `ImHttpRouter` currently authenticates protected routes only through `Authorization: Bearer ...`.
- Missing or malformed auth currently returns `E_IM_AUTH`, which must remain strict when no Web provider is installed.
- `POST /api/im/connections` already returns a raw `connection_key`; this remains external-only and unchanged.
- `ExternalImSession` already exposes the message/event/ack/conversation methods this phase needs.
- `WebImIdentityProvider.ensure()` already returns a record with `identity` and `connection`; the raw `connection_key` is present in the private record and must not be returned by `/api/im/session`.
- `WebManagementService` constructs `ImHttpRouter` but does not pass a Web auth provider yet.
- Live residue search still finds `/api/web/im/*` in `web_management.py`, frontend JS, UI tests, Web tests, projection tests, and architecture docs. Those are later-phase cleanup targets.

## Involved Files

- Modify: `tools/launcher/im_http_router.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_external_im_projection_contract.py`
- Read-only in this phase: `tools/launcher/web_im_identity.py`
- Read-only in this phase: `tools/launcher/web_management.py`

## Development Plan

1. Add router tests for strict no-provider behavior:
   - `GET /api/im/events` without Authorization and without Web provider returns `401 E_IM_AUTH`.
2. Add router tests for Web provider behavior:
   - `GET /api/im/session` without Authorization returns `identity`, `client_kind`, `display_name`, and excludes `connection_key`, `participant_token`, and `event_cursor`.
   - `POST /api/im/messages`, `GET /api/im/events`, and `POST /api/im/events/ack` without Authorization delegate to `ExternalImSession` with the provider connection.
3. Add a Bearer session test:
   - `GET /api/im/session` with Bearer auth returns the authenticated external identity and excludes raw credentials.
4. Implement `ImHttpRouter(web_connection_provider=...)`.
5. Implement one auth resolver:
   - Bearer present: authenticate through `ExternalImSession.authenticate`.
   - Authorization missing and provider present: call provider once and use its `identity` and `connection`.
   - Authorization missing and no provider: return `E_IM_AUTH`.
   - Malformed Authorization: return `E_IM_AUTH` even when a provider exists.
6. Add `GET /api/im/session` to the authenticated route set.
7. Keep `POST /api/im/connections` unchanged.

## Test Plan

Focused red command before implementation:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_projection_contract.py
```

Expected before implementation: new Web-provider/session tests fail because `ImHttpRouter` has no `web_connection_provider` parameter and no `/api/im/session` route.

Focused green command after implementation:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_projection_contract.py
```

Expected after implementation: all selected tests pass.

## Acceptance Criteria

- Missing Authorization remains `401 E_IM_AUTH` when no Web provider exists.
- Missing Authorization uses the Web provider only when the router was configured with one.
- Malformed Authorization is not silently treated as Web auth.
- `GET /api/im/session` works through both Bearer auth and Web-provider auth.
- `/api/im/session` response never exposes `connection_key`, `participant_token`, `event_cursor`, raw `connection`, or raw `participant`.
- Web-provider message send, event read, and event ack share the same router code path as Bearer callers.
- `POST /api/im/connections` behavior is unchanged.

## Risks

- If provider records are passed through directly, `connection_key` could leak to the browser.
- If malformed Authorization falls back to Web auth, an invalid client header could accidentally get Web Management privileges.
- If provider auth bypasses the same resolver, later route additions could drift into a second auth path.

## Execution Record

- Added Bearer `/api/im/session` coverage to `tests/test_im_http_router.py`.
- Added Web-provider router coverage to `tests/test_external_im_projection_contract.py`.
- Verified red state before implementation:
  - `GET /api/im/session` returned `404`.
  - `ImHttpRouter(web_connection_provider=...)` raised `TypeError`.
- Implemented `web_connection_provider` support in `ImHttpRouter`.
- Added one resolver path for Bearer auth, Web provider auth, missing auth, and malformed auth.
- Added sanitized `GET /api/im/session` response.
- Kept `POST /api/im/connections` unchanged.

## Test Results

Red command:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_projection_contract.py
```

Result before implementation:

```text
3 failed, 6 passed
```

Expected failures:

- `GET /api/im/session` returned `404`.
- `ImHttpRouter.__init__()` did not accept `web_connection_provider`.

Green command:

```bash
python3 -m py_compile tools/launcher/im_http_router.py && python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_projection_contract.py
```

Result after implementation:

```text
9 passed in 0.05s
```

## Residue Scan Result

Not run for Phase 01. Live `/api/web/im/*` residue is expected until Phases 02-05.

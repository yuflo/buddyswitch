# Phase 4: Web / External Identity

## Goal

Make web and external HTTP IM contracts consume identity ids. The Web IM session resolves to an external `IdentityRef`; browser sends use `target_identity_id`; direct conversation/event reads use `identity_id`. `connection_key` remains authentication only, and external identity never gets role, actor runtime, or daemon route semantics.

## Code Audit

- `tools/launcher/im_http_router.py` exposes actor contacts as `participant` objects, accepts `to` participant objects on `/api/im/messages`, and reads conversations through `kind=actor&role_id=...&actor_id=...`.
- `tools/launcher/web_im_identity.py` persists `participant` in `im-session.json` and returns it from `ensure()`.
- `tools/launcher/web_management.py` returns `participant` from `/api/web/im/session`, accepts `to` participant objects for `/api/web/im/messages`, and scopes web events/conversations with `role_id + actor_id`.
- `tools/launcher/assets/web-management/app.js` builds web IM URLs with `role_id + actor_id` and sends actor participant objects.
- `tests/test_im_http_router.py` and `tests/test_web_management.py` lock the old participant-shaped HTTP contract.

## Plan

1. Add failing tests for external/web session identity projection, `target_identity_id` sends, and `identity_id` direct conversation/event reads.
2. Add small resolver helpers at HTTP/web boundaries:
   - actor identity id -> actor participant using the current actor list / selected actor console data.
   - web session connection -> external identity projection.
3. Replace HTTP response bodies and request payloads with identity ids while keeping hydrated display/reachability data as projection.
4. Persist web IM session with `identity`, not public `participant`; keep `connection_key` only in the server-owned file.
5. Update browser JS to send/route by identity id.
6. Run focused web/external tests and residue scans.

## Test Plan

Focused command:

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py -q
```

Add red tests before implementation for:

- `/api/im/actors` returns actor identity rows, not participant objects.
- `/api/im/messages` accepts `target_identity_id`.
- `/api/im/conversations/direct?identity_id=...` reads conversation.
- `/api/web/im/session` returns `identity`, not `participant`.
- `/api/web/im/messages` accepts `target_identity_id`.
- `/api/web/im/conversations/direct?identity_id=...` and `/api/web/im/events?identity_id=...` scope by identity id.

## Implementation

- `tools/launcher/im_http_router.py`
  - `/api/im/actors` now returns actor identity rows with `identity`, `identity_id`, `role_id`, and reachability projection; it no longer returns actor participant objects.
  - `/api/im/messages` now accepts `target_identity_id`.
  - `/api/im/conversations/direct` now accepts `identity_id`.
  - Actor identity is resolved to an actor participant only inside the router before calling Central IM services.
- `tools/launcher/web_im_identity.py`
  - Web Management session records now persist `identity: { id, type: "external" }`.
  - `connection_key` remains only in the server-owned session file.
  - Old persisted `participant` is removed from refreshed records.
- `tools/launcher/web_management.py`
  - `/api/web/im/session` returns external `identity`, not `participant`.
  - `/api/web/im/messages` accepts `target_identity_id`.
  - `/api/web/im/events` and `/api/web/im/conversations/direct` accept `identity_id`.
  - Actor identity is projected to a daemon/IM route only inside the server boundary.
  - Actor console IM target now exposes identity projection, not `actor_address`.
- `tools/launcher/assets/web-management/app.js`
  - Browser calls web IM send/event/conversation APIs with identity ids.
  - Browser message projection reads `from_identity_id`/`to_identity_id`.

## Verification

Focused red checks before implementation included:

```text
KeyError: 'identity'
AssertionError: 'target_identity_id' not found in 'to must be an object'
AssertionError: '/api/web/im/events?role_id=...' == '/api/web/im/events?identity_id=...'
```

Focused phase command:

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py -q && node tests/web_management_ui_state.test.js && node tests/web_management_ui_contract.test.js
```

Result:

```text
65 passed, 41 subtests passed in 127.30s (0:02:07)
```

JS result:

```text
tests/web_management_ui_state.test.js: all checks ok
tests/web_management_ui_contract.test.js: all checks ok
```

Residue checks:

```bash
rg -n "api/web/im/(events|conversations/direct).*role_id|api/web/im/(events|conversations/direct).*actor_id|api/im/conversations/direct.*role_id|api/im/conversations/direct.*actor_id|kind=actor|external-participants|participant_token" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py tools/launcher/assets/web-management/app.js tests/test_im_http_router.py tests/test_web_management.py tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js -S
rg -n "\\bparticipant\\b|actor_address|target_actor_address" tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/web_im_identity.py tools/launcher/assets/web-management/app.js -S
```

Results:

- Public role/actor query contract scan: no implementation hits; remaining hits are negative assertions and identity-id URLs in tests.
- Participant/actor-address scan: remaining implementation hits are internal Central IM service projections and route resolution boundaries only.

## Gate

Complete.

- Phase test command passed.
- Web/external HTTP contracts use `identity`, `target_identity_id`, and `identity_id`.
- `connection_key` remains authentication-only and is not returned to the browser session response.
- External identity has no `role_id`, daemon route, or actor runtime.
- Remaining participant/actor-address usage is internal projection to existing Central IM/daemon service boundaries.
- README updated to set `phase-05-product-ownership` as current.

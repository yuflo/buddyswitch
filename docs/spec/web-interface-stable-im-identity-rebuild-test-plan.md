# Web Interface Stable IM Identity Rebuild Test Plan

## Purpose

Verify the rebuild target directly: Web Management has one stable server-owned IM identity per shared runtime, Browser UI does not register or hold tokens, and the WebUI API has no `/api/im/*` compatibility path.

## Required Coverage

### Web-interface Identity

- `WebImIdentityProvider.ensure()` creates `im-session.json` on first use.
- A second provider/service in the same runtime authenticates and reuses the same `external_id` and token.
- A corrupted or invalid token record is replaced once.
- The identity file contains credential metadata only: schema version, client kind, display name, participant ref, token, timestamps.
- The identity file does not contain messages, conversations, actor history, or WebUI render cache.

### Web Management API Surface

- `GET /api/web/im/session` returns `ok`, participant metadata, and cursor/session state without `participant_token`.
- `POST /api/web/im/messages` sends from the server-owned Web participant to the selected actor address.
- `GET /api/web/im/conversations/direct?role_id=...&actor_id=...&limit=...` returns the IM direct conversation for that stable participant.
- `GET /api/web/im/events?role_id=...&actor_id=...&cursor=...&wait_ms=...` returns only that actor direct conversation's visible event/message projection while advancing the Web participant cursor.
- `POST /api/im/external-participants` through `WebManagementService.handle_api` returns 404.
- Any `/api/im/*` path through Web Management returns 404.

### Browser UI Contract

- `app.js` includes `/api/web/im/session`, `/api/web/im/messages`, `/api/web/im/events`, and `/api/web/im/conversations/direct`.
- `app.js` excludes `/api/im`, `external-participants`, `participant_token`, `imParticipantToken`, and `Authorization`.
- `buildImEventsUrl("market", "act-market demo", "imev-abc 123", 15000)` returns `/api/web/im/events?role_id=market&actor_id=act-market%20demo&cursor=imev-abc%20123&wait_ms=15000`.
- Direct conversation payloads populate `state.imConversation`.
- Event payloads append scoped direct-conversation messages and dedupe already-rendered message ids.
- Sending a draft posts to `/api/web/im/messages` without token headers.

### Lower IM Contract

- `tests/test_im_http_router.py` stays green to prove external `/api/im/*` remains valid outside Web Management Browser surface.
- `tests/test_im_external_reply_loop.py` stays green to prove actor reply loop still works.

### Boundary Checks

- No new `actor.web_messages`, `web_interface_messages`, or actor message history API.
- No new message history persistence under Web-interface local state.
- No Web-interface direct repo write to IM messages/conversations/events.
- No Browser-held long-lived IM token.

## Verification Commands

Run:

```bash
python -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py -q
```

Run:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Run:

```bash
python -m pytest tests/test_im_http_router.py tests/test_im_external_reply_loop.py -q
```

Run:

```bash
python -m pytest tests/test_env_layer_boundaries.py -q
```

Run:

```bash
rg -n "/api/im|external-participants|imParticipantToken|participant_token|Authorization: 'Bearer|Authorization\\\": \\\"Bearer|web_interface_messages|actor\\.web_messages" tools/launcher/assets/web-management tools/launcher/web_management.py tools/launcher/web_im_identity.py tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js tests/test_web_management.py tests/test_im_web_management_projection.py
```

Expected: no result for Browser/Web Management implementation files except intentional negative assertions in tests.

Run:

```bash
git diff --check -- docs/spec tools/launcher tests
```

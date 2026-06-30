# Unified IM API Rebuild-Forward Final Acceptance

Date: 2026-06-30

## Completion Summary

The unified IM API rebuild is complete in this worktree.

Final contract now proven:

```text
External caller or iMessage adapter -> /api/im/* with Bearer key -> actor-directed IM conversation works with explicit event ack.
```

```text
Web browser -> /api/im/* with server-owned Web identity -> actor-directed IM conversation works with explicit event ack and no connection_key exposure.
```

No `/api/web/im/*` live compatibility route remains.

## Phase Documents

- `docs/spec/im-api-unified-rebuild-forward/phase-01-unified-auth-context.md`
- `docs/spec/im-api-unified-rebuild-forward/phase-02-web-management-router-host.md`
- `docs/spec/im-api-unified-rebuild-forward/phase-03-web-frontend-unified-im.md`
- `docs/spec/im-api-unified-rebuild-forward/phase-04-projection-doc-residue.md`
- `docs/spec/im-api-unified-rebuild-forward/phase-05-live-surface-residue-gates.md`
- `docs/spec/im-api-unified-rebuild-forward/phase-06-focused-e2e-contract-slice.md`
- `docs/spec/im-api-unified-rebuild-forward/phase-07-broader-verification.md`

## Acceptance Matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Web frontend source contains no `/api/web/im` | Complete | `tests/web_management_ui_contract.test.js`; Phase 07 residue scan no matches |
| Active Python launcher source contains no `/api/web/im` route handler | Complete | `tests/test_im_web_management_projection.py::test_live_surfaces_have_no_retired_web_im_route_or_helper_residue`; Phase 07 residue scan no matches |
| `/api/web/im/*` is not live | Complete | `tests/test_web_management.py::WebManagementStableImIdentityTests::test_retired_web_im_routes_are_not_live`; `tests/test_im_web_management_projection.py::test_web_management_does_not_expose_retired_web_im_route_family` |
| Browser/Web Management send path uses `POST /api/im/messages` | Complete | `tests/test_web_management.py::WebManagementStableImIdentityTests::test_browser_style_im_routes_send_read_fetch_ack_and_restore_history_without_browser_token`; UI contract tests |
| Browser/Web Management event path uses read, fetch, explicit ack | Complete | Same Web contract test; `app.js` polling implementation; UI state tests for message URL and ack payload |
| `GET /api/im/events` does not auto-ack | Complete | Web contract test repeated read before ack; external/session/router tests; projection test proving event read does not fetch or ack |
| Explicit ack works | Complete | Web contract test; `tests/test_im_http_router.py`; `tests/test_external_im_session.py`; iMessage channel ack tests |
| Browser responses and JS state do not expose `connection_key` | Complete | Web session/send/event/history assertions; Node contract exclusion; Phase 07 residue scan |
| External adapter Bearer flow still works | Complete | `tests/test_im_external_reply_loop.py`; `tests/test_im_http_router.py`; iMessage channel tests |
| Web server-owned identity is stable and server-side | Complete | `tests/test_web_management.py::WebManagementStableImIdentityTests::test_im_session_creates_one_stable_web_identity_per_runtime` |
| `web_management.py` no longer owns IM message/event/conversation semantics | Complete | Source guard in `tests/test_im_web_management_projection.py`; deleted Web BFF helpers |
| Live architecture docs describe one `/api/im/*` contract | Complete | `docs/arch/web-interface-call-architecture.md`; Phase 04 residue scan |
| Scoped residue scan over `tools/launcher`, `tests`, and `docs/arch` has no stale positive hits | Complete | Phase 07 residue scan no matches |
| Focused Python and Node verification commands pass | Complete | Phase 07 results below |

## Verification

Compile:

```bash
python3 -m py_compile tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/external_im_session.py tools/launcher/web_im_identity.py
```

Result: passed.

Python:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_session.py tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
```

Result:

```text
115 passed, 176 subtests passed in 111.65s (0:01:51)
```

Node:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result:

```text
2 test files passed; 0 failed
```

Residue:

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|assertExcludes\\(appJs, '/api/im'\\)" tools/launcher tests docs/arch -S
```

Result:

```text
no matches
```

## Live Smoke

Not run. The final pass used focused in-process Python and Node contract tests. No long-lived Web server or live macOS iMessage smoke was started.

## Remaining Risk

- Browser polling now performs explicit event fetch and ack in JavaScript. Automated Node tests cover URLs and ack payload shape; Python Web Management tests cover the server-side contract. A live browser smoke can still add confidence in UI timing and rendering.
- Live iMessage behavior still depends on local macOS Messages.app and `imsg` state. Automated iMessage channel tests cover the adapter contract without starting long-lived processes.

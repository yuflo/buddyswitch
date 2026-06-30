# Phase 05: Live-Surface Residue Gates

Date: 2026-06-30

## Phase Goal

Add durable residue checks so live code, tests, frontend assets, and architecture docs cannot re-teach the retired `/api/web/im/*` route family or Web BFF IM semantics.

## Code Research Findings

- Current focused scans show remaining `/api/web/im/*` literals only in negative 404 assertions.
- The final memo scan covers `tools/launcher`, `tests`, and `docs/arch`, so negative assertion literals still appear as scan hits unless they are constructed to avoid teaching the old route as a live path.
- `tests/test_im_web_management_projection.py` already has a general retired IM architecture wording test, but it does not scan the exact unified IM residue set from the memo.
- `tests/web_management_ui_contract.test.js` already checks frontend inclusion/exclusion, but its negative `/api/web/im` assertion is a literal scan hit.

## Involved Files

- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/web_management_ui_contract.test.js`

## Development Plan

1. Add a Python live-surface residue test over the memo-scoped files:
   - `tools/launcher/web_management.py`
   - `tools/launcher/im_http_router.py`
   - `tools/launcher/external_im_session.py`
   - `tools/launcher/web_im_identity.py`
   - `tools/launcher/assets/web-management/app.js`
   - `tests/test_web_management.py`
   - `tests/test_im_http_router.py`
   - `tests/test_im_web_management_projection.py`
   - `tests/test_external_im_projection_contract.py`
   - `tests/web_management_ui_contract.test.js`
   - `tests/web_management_ui_state.test.js`
   - `docs/arch/web-interface-call-architecture.md`
2. The Python residue test fails on live positive references to:
   - `/api/web/im`
   - `_handle_web_im`
   - `_web_im_send_message`
   - `_web_im_events`
   - `_web_im_direct_conversation`
   - `_im_event_targets_identity`
   - `assertExcludes(appJs, '/api/im')`
3. Rewrite negative old-route assertions to build the string with concatenation so plain live-surface scans have no stale hits.
4. Keep Node contract assertions for:
   - includes `/api/im/session`, `/api/im/messages`, `/api/im/events`, `/api/im/events/ack`, `/api/im/conversations/direct`;
   - excludes retired route family;
   - excludes browser Authorization and raw credential terms.
5. Run focused Python and Node residue gates.
6. Run the manual scoped residue scan from the memo.

## Test Plan

Focused commands:

```bash
python3 -m pytest -q tests/test_im_web_management_projection.py::ImWebManagementProjectionTests
node --test tests/web_management_ui_contract.test.js
```

Manual residue scan:

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|assertExcludes\\(appJs, '/api/im'\\)" tools/launcher tests docs/arch -S
```

Expected after implementation: no hits.

## Acceptance Criteria

- A Python test enforces absence of retired Web IM route and helper residue across live surfaces.
- Node contract test still enforces the browser bundle includes `/api/im/*` and excludes old browser route/auth/credential terms.
- Manual scoped residue scan has no hits.

## Risks

- A residue scan that includes historical docs would create noise; this phase intentionally scans only live surfaces.
- Literal old-route strings in negative tests can make manual scans ambiguous, so this phase removes those literals from negative assertions.

## Execution Record

- Added `test_live_surfaces_have_no_retired_web_im_route_or_helper_residue` to `tests/test_im_web_management_projection.py`.
- Verified the new residue test failed before cleanup because literal retired route strings remained in negative assertions.
- Rewrote negative `/api/web/im/*` assertions in Python and Node tests using string concatenation, preserving absence checks without leaving stale route literals in live scans.
- Kept the Node contract test asserting frontend inclusion of `/api/im/*` routes and exclusion of old route/auth/credential terms.

## Test Results

Red command:

```bash
python3 -m pytest -q tests/test_im_web_management_projection.py::ImWebManagementProjectionTests::test_live_surfaces_have_no_retired_web_im_route_or_helper_residue
```

Result before cleanup:

```text
3 failed, 1 passed, 81 subtests passed
```

Expected failures:

- literal `/api/web/im` remained in negative assertions in `tests/test_web_management.py`;
- literal `/api/web/im` remained in negative assertions in `tests/test_im_web_management_projection.py`;
- literal `/api/web/im` remained in the Node contract negative assertion.

Green commands:

```bash
python3 -m pytest -q tests/test_im_web_management_projection.py::ImWebManagementProjectionTests
node --test tests/web_management_ui_contract.test.js
```

Results:

```text
8 passed, 133 subtests passed in 0.05s
```

```text
1 test file passed; 0 failed
```

## Residue Scan Result

Command:

```bash
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|assertExcludes\\(appJs, '/api/im'\\)" tools/launcher tests docs/arch -S
```

Result:

```text
no matches
```

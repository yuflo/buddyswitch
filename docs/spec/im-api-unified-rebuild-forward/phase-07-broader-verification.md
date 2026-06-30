# Phase 07: Broader Verification

Date: 2026-06-30

## Phase Goal

Run the broader verification set from the memo and record final evidence that the unified `/api/im/*` rebuild is complete across Python launcher code, Web frontend code, external adapter flow, iMessage adapter flow, architecture docs, and live-surface residue gates.

## Code Research Findings

- Phases 01-06 have already moved the router, Web Management service, frontend, projection tests, docs, residue gates, and end-to-end contract slice.
- The final verification must still prove the combined current state, not rely on phase-local test runs.
- Broad service-starting live smoke is intentionally out of scope unless lifecycle ownership is clear; the memo allows focused contract and UI checks first.

## Involved Files

- Verify: `tools/launcher/im_http_router.py`
- Verify: `tools/launcher/web_management.py`
- Verify: `tools/launcher/external_im_session.py`
- Verify: `tools/launcher/web_im_identity.py`
- Verify: `tests/test_im_http_router.py`
- Verify: `tests/test_external_im_session.py`
- Verify: `tests/test_external_im_projection_contract.py`
- Verify: `tests/test_im_web_management_projection.py`
- Verify: `tests/test_web_management.py`
- Verify: `tests/test_im_external_reply_loop.py`
- Verify: `tests/test_imessage_channel.py`
- Verify: `tests/web_management_ui_contract.test.js`
- Verify: `tests/web_management_ui_state.test.js`
- Verify: `docs/arch/web-interface-call-architecture.md`

## Development Plan

No production changes are planned in this phase unless verification exposes a defect. If any command fails, fix the smallest root cause under the relevant phase constraint, then rerun the failed command and its dependent broader gate.

## Test Plan

Run:

```bash
python3 -m py_compile tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/external_im_session.py tools/launcher/web_im_identity.py
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_session.py tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
rg -n "/api/web/im|_handle_web_im|_web_im_send_message|_web_im_events|_web_im_direct_conversation|_im_event_targets_identity|assertExcludes\\(appJs, '/api/im'\\)" tools/launcher tests docs/arch -S
```

Expected:

- compile exits 0;
- Python tests exit 0;
- Node tests exit 0;
- residue scan has no matches.

## Acceptance Criteria

- Web and external adapter paths use `/api/im/*`.
- `/api/web/im/*` is not a live surface.
- Web JS does not expose `connection_key` or browser Authorization.
- Event read does not implicitly ack.
- Explicit event ack works.
- Architecture docs teach one IM HTTP product contract.
- Live-surface residue scan has no old positive hits.

## Risks

- `tests/test_web_management.py` is broader than the modified Web IM class and may expose unrelated Web Management expectations.
- No live macOS/iMessage smoke is run in this phase; automated in-process iMessage channel tests cover the adapter contract.

## Execution Record

- Ran final compile verification for the launcher IM modules.
- Ran broader Python verification across router, session, projection, Web Management, external reply loop, and iMessage channel suites.
- Ran Node UI contract/state verification.
- Ran final scoped live-surface residue scan.

## Test Results

Compile command:

```bash
python3 -m py_compile tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/external_im_session.py tools/launcher/web_im_identity.py
```

Result:

```text
passed
```

Python command:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_external_im_session.py tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
```

Result:

```text
115 passed, 176 subtests passed in 111.65s (0:01:51)
```

Node command:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Result:

```text
2 test files passed; 0 failed
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

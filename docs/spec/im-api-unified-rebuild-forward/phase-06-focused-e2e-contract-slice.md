# Phase 06: Focused End-To-End Contract Slice

Date: 2026-06-30

## Phase Goal

Prove the original user-visible IM loop across Web Management and external adapter paths:

```text
Browser-style Web request sends actor-directed IM through /api/im/messages, actor reply becomes visible through /api/im/events, browser fetches the reply through /api/im/messages/<id>, browser acks through /api/im/events/ack, and direct conversation shows both messages without exposing connection_key.
```

This phase does not add a new product path; it makes the acceptance slice explicit and verifies it with the relevant Python suites.

## Code Research Findings

- `tests/test_web_management.py::WebManagementStableImIdentityTests::test_browser_style_im_routes_send_read_fetch_ack_and_restore_history_without_browser_token` already covers the browser-style Web loop through `/api/im/*`.
- `tests/test_im_external_reply_loop.py` covers the external Bearer reply loop through `/api/im/*`.
- `tests/test_imessage_channel.py` covers iMessage adapter use of `/api/im/*` with explicit event ack.
- `tests/test_im_http_router.py` covers the raw HTTP router contract for Bearer and event ack.
- The Web test needs the exact contract sentence from the memo so future reviewers can map it directly to the final acceptance promise.

## Involved Files

- Modify: `tests/test_web_management.py`
- Read-only verification: `tests/test_im_http_router.py`
- Read-only verification: `tests/test_im_external_reply_loop.py`
- Read-only verification: `tests/test_imessage_channel.py`

## Development Plan

1. Add the exact memo contract sentence as the docstring for the browser-style Web IM test.
2. Keep iMessage channel adapter tests on Bearer `/api/im/*`.
3. Run the Phase 06 focused command.

## Test Plan

Focused red command before implementation:

```bash
python3 -m pytest -q tests/test_web_management.py::WebManagementStableImIdentityTests::test_browser_style_im_routes_send_read_fetch_ack_and_restore_history_without_browser_token
```

Expected before implementation: no behavior failure is required here because the test already exists; the missing artifact is the explicit contract sentence. This is a documentation-in-test acceptance update.

Focused verification after implementation:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
```

Expected: all selected tests pass.

## Acceptance Criteria

- The Web end-to-end contract sentence is present in the owning test.
- Browser-style Web path uses `/api/im/messages`, `/api/im/events`, `/api/im/messages/<id>`, `/api/im/events/ack`, and `/api/im/conversations/direct`.
- External Bearer and iMessage adapter flows still pass.

## Risks

- This is an automated in-process contract slice, not a live browser smoke. The broader final phase must still run the full focused verification and residue scan.

## Execution Record

- Added the exact memo contract sentence as the docstring for `tests/test_web_management.py::WebManagementStableImIdentityTests::test_browser_style_im_routes_send_read_fetch_ack_and_restore_history_without_browser_token`.
- Kept external Bearer and iMessage adapter tests unchanged on `/api/im/*`.

## Test Results

Focused verification command:

```bash
python3 -m pytest -q tests/test_im_http_router.py tests/test_web_management.py::WebManagementStableImIdentityTests tests/test_im_external_reply_loop.py tests/test_imessage_channel.py
```

Result:

```text
40 passed, 4 subtests passed in 0.46s
```

## Residue Scan Result

Not applicable for this phase; Phase 05 owns residue gates.

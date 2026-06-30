# Phase 04: Delete Web IM Projection Contract Residue

Date: 2026-06-30

## Phase Goal

Remove live tests and architecture docs that still describe `/api/web/im/*` or Web BFF event shaping as a valid IM contract. Replace them with tests and docs that teach one `/api/im/*` product surface with Web-only auth context resolution.

## Code Research Findings

- `tests/test_external_im_projection_contract.py` still has:
  - `test_web_bff_rejects_cursor_before_session_read`;
  - `test_web_bff_shapes_events_and_empty_direct_conversation_around_session`.
- Those tests call `/api/web/im/events` and `/api/web/im/conversations/direct`, and they expect the server to fetch message bodies and ack events inside the Web events route.
- `tests/test_im_web_management_projection.py` already has negative 404 assertions for `/api/web/im/*` and source guards for direct Web IM session calls.
- `docs/arch/web-interface-call-architecture.md` still documents:
  - `/api/im/*` as integration-only;
  - `/api/web/im/*` as browser-facing;
  - two IM projection route families.

## Involved Files

- Modify: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `docs/arch/web-interface-call-architecture.md`

## Development Plan

1. Remove old Web BFF tests from `tests/test_external_im_projection_contract.py`.
2. Add replacement projection tests proving:
   - Web Management exposes browser-style `/api/im/*` through the shared router;
   - `/api/web/im/*` is absent;
   - Web Management does not call `ExternalImSession` directly for Web IM semantics.
3. Keep negative `/api/web/im/*` assertions in `tests/test_im_web_management_projection.py` as the live absence proof.
4. Update architecture docs:
   - `/api/im/*` is the single IM HTTP product contract for channel adapters, third-party callers, and Web interface;
   - Web interface differs only by server-owned auth context;
   - `ExternalImSession` owns external participant and actor-directed IM application semantics.
5. Remove live doc wording that presents `/api/web/im/*` as a browser-facing projection.

## Test Plan

Focused red command before implementation:

```bash
python3 -m pytest -q tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py
```

Expected before implementation: old Web BFF tests fail because `/api/web/im/*` is no longer live.

Focused green command after implementation:

```bash
python3 -m pytest -q tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py
```

Expected after implementation: all selected tests pass.

Residue scan:

```bash
rg -n "/api/web/im|Web BFF|browser-facing projection|integration projection for local channel adapters|buildWebIm|applyImEventsPayload|web_bff" tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py docs/arch/web-interface-call-architecture.md -S
```

Expected after implementation: no positive live hits; negative 404 assertions in `tests/test_im_web_management_projection.py` may remain.

## Acceptance Criteria

- `tests/test_external_im_projection_contract.py` no longer describes Web BFF event shaping.
- Projection tests prove shared `/api/im/*` behavior and `/api/web/im/*` absence.
- Live architecture docs describe one `/api/im/*` IM HTTP product contract.
- Live architecture docs no longer describe `/api/web/im/*` as browser-facing.

## Risks

- Removing old tests without replacement would weaken router/Web Management boundary proof.
- Doc updates must avoid implying Web owns IM semantics directly; Web owns auth context and UI DTOs only.

## Execution Record

- Ran focused projection tests before replacing old tests; the two Web BFF tests failed because `/api/web/im/*` now returns `404`.
- Removed tests that expected Web BFF cursor handling, hidden message fetch, auto-ack, and Web-shaped empty direct conversation responses.
- Added replacement coverage in `tests/test_external_im_projection_contract.py` proving:
  - Web Management browser IM uses `/api/im/events`;
  - event read does not include `messages`;
  - event read does not fetch or ack;
  - message fetch, event ack, and direct conversation are explicit `/api/im/*` calls through the shared router.
- Kept `/api/web/im/*` negative route-family assertions in `tests/test_im_web_management_projection.py`.
- Updated `docs/arch/web-interface-call-architecture.md` so `/api/im/*` is the single IM HTTP product contract and Web differs only by server-owned auth context.

## Test Results

Red command:

```bash
python3 -m pytest -q tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py
```

Result before implementation:

```text
2 failed, 11 passed, 49 subtests passed
```

Expected failures:

- `test_web_bff_rejects_cursor_before_session_read` expected `400`, but the retired route returned `404`.
- `test_web_bff_shapes_events_and_empty_direct_conversation_around_session` called retired `/api/web/im/*` routes.

Green command:

```bash
python3 -m pytest -q tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py
```

Result after implementation:

```text
12 passed, 49 subtests passed in 0.04s
```

## Residue Scan Result

Command:

```bash
rg -n "/api/web/im|Web BFF|browser-facing projection|integration projection for local channel adapters|buildWebIm|applyImEventsPayload|web_bff" tests/test_external_im_projection_contract.py tests/test_im_web_management_projection.py docs/arch/web-interface-call-architecture.md -S
```

Result:

```text
tests/test_im_web_management_projection.py:179: negative 404 assertion for /api/web/im/session
tests/test_im_web_management_projection.py:180: negative 404 assertion for /api/web/im/messages
tests/test_im_web_management_projection.py:181: negative 404 assertion for /api/web/im/events
tests/test_im_web_management_projection.py:182: negative 404 assertion for /api/web/im/conversations/direct
```

No positive Web BFF projection tests or architecture-doc references remain in this phase scope.

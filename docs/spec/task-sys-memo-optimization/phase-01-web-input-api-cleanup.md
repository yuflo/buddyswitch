# Phase 01 Web Input API Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the stale Web management `/api/instances/<actor-id>/input` API while preserving WebUI IM message sending and CLI `instance input`.

**Architecture:** Web management should project the IM product surface through `/api/web/im/messages`; actor input remains a CLI/product ingress outside this Web backend. The phase deletes the Web route and helper chain instead of keeping a compatibility branch.

**Tech Stack:** `tools/launcher/web_management.py`, `tests/test_web_management.py`, `tests/web_management_ui_contract.test.js`, pytest, Node test runner, scoped residue scans.

---

## 1. Background And Goal

This phase resolves `docs/memo/2026-06-29-web-management-input-residue-cleanup.md`.

Current bottleneck:

- The visible WebUI composer already calls `sendImDraft()` and posts to `/api/web/im/messages`.
- The backend still parses and executes `POST /api/instances/<actor-id>/input`.
- Python tests still validate the old Web input API success and error paths.

Observable behavior change:

- `POST /api/instances/<actor-id>/input` returns `404 NOT_FOUND`.
- WebUI message send remains backed by `/api/web/im/messages`.
- The backend no longer runs `./buddyswitch-codex instance input` from Web management.

## 2. Code Current-State Investigation

Relevant files:

- `tools/launcher/web_management.py`
  - `handle_api()` currently dispatches `method == "POST" and action == "input"` to `_send_input()`.
  - `_parse_instance_action_path()` maps `/api/instances/<actor-id>/input` to action `"input"`.
  - `_send_input()`, `_send_input_under_lock()`, and `_run_input_command()` execute the old Web API.
  - `/api/web/im/messages` is handled separately in `_handle_web_im()` and `_web_im_send_message()`.
- `tools/launcher/assets/web-management/app.js`
  - `sendImDraft()` posts to `/api/web/im/messages`.
  - Current UI contract excludes `"selectedActorId) + '/input'"`.
- `tests/test_web_management.py`
  - Old input tests at current lines around 1041, 1053, 1921, and 1929 cover empty text, delegated success, bootstrap residue, and malformed launcher JSON.
  - Web IM tests around current lines 1283, 1353, and 1635 cover `/api/web/im/messages`.
- `tests/web_management_ui_contract.test.js`
  - Confirms `/api/web/im/messages` is a real frontend API surface and excludes the old `/input` frontend route.

Old path or residue path:

- `POST /api/instances/<actor-id>/input`
- action string `"input"` inside Web management path parsing and dispatch
- `_send_input*` helper chain
- `_run_input_command()`
- Web tests that expect Web API input success or launcher JSON errors

Existing coverage and gaps:

- Existing coverage proves the stale route works; after this phase it should prove the route is gone.
- Existing UI contract already proves the frontend does not use `/input`; keep that test green.
- Existing IM tests prove `/api/web/im/messages`; keep them green.

## 3. Solution Design

Minimal direct change:

1. Change `tests/test_web_management.py` first:
   - Replace `test_input_route_rejects_empty_text` with `test_input_route_returns_404_without_launcher_call`.
   - Delete `test_input_route_delegates_and_reports_task_sys_task`.
   - Delete `test_web_management_input_route_does_not_submit_bootstrap_text` if present by that name.
   - Delete `test_input_route_returns_structured_error_for_malformed_launcher_json`.
   - Keep Web IM tests unchanged.
2. Run the focused old-route test and observe failure while production code still returns 400/200/502.
3. Edit `tools/launcher/web_management.py`:
   - Remove the `input` dispatch branch.
   - Remove the `/input` parser branch.
   - Remove `_send_input()`.
   - Remove `_send_input_under_lock()`.
   - Remove `_run_input_command()`.
4. Run focused and broader tests.
5. Run scoped residue scan.

No compatibility or abstraction:

- Do not keep a 410 compatibility response; existing unknown action handling already returns 404.
- Do not proxy old Web input to `/api/web/im/messages`.
- Do not modify CLI `instance input`.
- Do not add a generic route registry.

Boundary with other memo phases:

- This phase does not change Task Sys prompt rendering or parent handoff runtime.
- This phase does not change IM message domain, `im_message_created` wake, or Task Sys ingest.

## 4. Test Plan

### Red Tests

- Modify `tests/test_web_management.py` so `POST /api/instances/act-pm-demo/input` expects `404` with error code `NOT_FOUND` and no runner calls.
- Run:

```bash
python -m pytest -q tests/test_web_management.py -k input_route
```

Expected red result before production edit:

- The route returns the old status (`400`, `200`, or `502`) instead of `404`, or calls the launcher.

### Focused Tests

After implementation:

```bash
python -m pytest -q tests/test_web_management.py -k "input_route or web_im"
```

Expected:

- Input route removal test passes.
- Web IM send/read tests still pass.

### Integration / End-To-End Contract Tests

```bash
python -m pytest -q tests/test_web_management.py
node --test tests/web_management_ui_contract.test.js
```

Expected:

- Python Web management suite passes.
- Node UI contract passes and continues to include `/api/web/im/messages` while excluding frontend `/input` usage.

### Residue Scans

```bash
rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|instance input for" tools/launcher tests -S
```

Expected:

- No hits in `tools/launcher/web_management.py`.
- No Web API input success-path hits in `tests/test_web_management.py`.
- CLI `instance input` may still appear outside Web management scope if searched more broadly.

### Compile / Diff Checks

```bash
python -m py_compile tools/launcher/web_management.py
git diff --check
```

Expected:

- Both pass.

## 5. Acceptance Criteria

Behavior acceptance:

- `WebManagementService.handle_api("POST", "/api/instances/act-pm-demo/input", ...)` raises/returns the standard 404 API error envelope.
- No command runner call is made for the old Web input route.
- `/api/web/im/messages` tests still pass.

State acceptance:

- No runtime object files under `buddyswitch/objects/**` are edited.
- No direct IM state files are edited by this phase.

UI / CLI / WebUI observable acceptance:

- Frontend contract still includes `/api/web/im/messages`.
- Frontend contract still excludes the old selected actor `/input` route.
- CLI `instance input` remains available in launcher code and tests outside Web management.

Live surface no-residue acceptance:

- `web_management.py` contains no `action == "input"`, `_send_input`, or `_run_input_command`.
- `tests/test_web_management.py` no longer proves Web input route success or malformed launcher JSON handling.

Actual Verification:

- Red checks before production edits:
  - `python -m pytest -q tests/test_web_management.py -k input_route`
  - Result: failed because the old backend route still dispatched to `instance input`, and the fake runner raised `unexpected command: ['instance', 'input', 'act-pm-demo', '--text', 'Advance the brief', '--json']`.
  - `python -m pytest -q tests/test_web_management.py::WebManagementHTTPTests::test_web_management_does_not_write_message_rows_or_construct_signals`
  - Result: failed for forbidden source string `Instance input blocked:` before the stale mapper branch was removed.
- Focused green checks:
  - `python -m pytest -q tests/test_web_management.py -k "input_route or web_im"`
  - Result: `9 passed, 54 deselected`.
  - `python -m pytest -q tests/test_web_management.py::WebManagementHTTPTests::test_input_route_returns_404_without_launcher_call tests/test_web_management.py::WebManagementHTTPTests::test_web_management_does_not_write_message_rows_or_construct_signals tests/test_web_management.py::WebManagementUnitTests::test_map_command_failure_uses_required_status_codes`
  - Result: `3 passed, 12 subtests passed`.
- Final phase verification:
  - `python -m pytest -q tests/test_web_management.py`
  - Result: `63 passed, 39 subtests passed in 112.39s`.
  - `node --test tests/web_management_ui_contract.test.js`
  - Result: pass, `7` UI contract checks reported by the test file and Node reported `pass 1`.
  - `python -m py_compile tools/launcher/web_management.py`
  - Result: pass.
  - `rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|instance input for|Instance input blocked" tools/launcher tests -S`
  - Result: no hits.

## Actual Changes

- Removed Web management dispatch for `POST /api/instances/<actor-id>/input`.
- Removed `/input` parsing from `_parse_instance_action_path()`.
- Removed `_send_input()`, `_send_input_under_lock()`, and `_run_input_command()`.
- Removed the obsolete Web command failure mapper for `Instance input blocked:`.
- Replaced old Web input success/error tests with `test_input_route_returns_404_without_launcher_call`.
- Added source-residue coverage so `tools/launcher/web_management.py` cannot retain the stale `Instance input blocked:` Web-only mapper.
- Kept Web IM route tests and UI contract tests green.

## Acceptance Status

Accepted for Phase 01. Web management no longer exposes or exercises the old actor input API; the WebUI IM path remains verified; CLI `instance input` remains outside this Web backend cleanup.

## 6. Appendix

Search commands used during investigation:

```bash
rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|api/web/im/messages|sendImDraft" tools/launcher tests -S
rg -n "def test_.*input_route|/api/instances/act-pm-demo/input|/api/web/im/messages" tests/test_web_management.py -S
```

Key code references:

- `tools/launcher/web_management.py` route dispatch and `_parse_instance_action_path()`
- `tools/launcher/web_management.py` old `_send_input*` helper chain
- `tests/test_web_management.py` old input route tests
- `tests/web_management_ui_contract.test.js` production frontend API surface test

Decision record:

- Use 404 rather than 410 because the phase goal is to remove the Web API surface, not publish a compatibility deprecation endpoint.
- Keep CLI input untouched because the memo explicitly preserves CLI `instance input` as a Task Sys `user.input` product ingress.

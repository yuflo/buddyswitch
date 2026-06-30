# Task Sys Memo Optimization Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before implementation changes and keep each phase document current. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the three memo optimizations with verified product behavior: Web management has no live input API residue, side frames carry resource-boundary guidance, and `interrupt_submit_parent` submits parent frames when the parent thread is idle.

**Architecture:** Keep the existing Task Sys rebuild boundary: inbound creates Task Sys tasks, side frames decide `close` versus `need_parent`, and parent work is submitted only through Task Sys runtime instructions. This work edits the smallest live surfaces that own the defects instead of adding compatibility paths.

**Tech Stack:** Python launcher/runtime modules, Python pytest/unittest tests, Node UI contract tests, scoped `rg` residue scans, `py_compile`, and `git diff --check`.

---

## Source Requirements

Required source documents were read before planning:

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/memo/2026-06-29-web-management-input-residue-cleanup.md`
- `docs/memo/2026-06-29-task-sys-interrupt-submit-parent-idle-bug.md`
- `docs/memo/2026-06-30-task-sys-side-thread-resource-boundary-prompt.md`
- Existing Task Sys rebuild records under `docs/spec/task-sys-proactive-rebuild/`, especially phases 03 and 04 and final acceptance.

## Extracted Task Checklist

### Web Management Input Residue Cleanup

- [ ] Remove backend route handling for `POST /api/instances/<actor-id>/input` from `tools/launcher/web_management.py`.
- [ ] Remove `_send_input`, `_send_input_under_lock`, and `_run_input_command` from Web management.
- [ ] Replace successful input-route tests with a route-removal test proving `POST /api/instances/<actor-id>/input` returns 404 and does not call the launcher.
- [ ] Keep `/api/web/im/messages` behavior and UI contract coverage intact.
- [ ] Prove frontend assets still send via IM and do not reference `/input`.
- [ ] Prove CLI `./buddyswitch-codex instance input` remains out of scope and not deleted.

### Side Thread Resource Boundary Prompt

- [ ] Replace the compact `render_side_frame()` body in `tools/launcher/task_sys_runtime.py` with resource-boundary rules from the memo.
- [ ] Keep dynamic fields in every side frame: `task_id`, `source`, `context`, and allowed result actions.
- [ ] Do not edit `SIDE_BOUNDARY_PROMPT` or `SIDE_DEVELOPER_INSTRUCTIONS`.
- [ ] Do not add tool-layer hard resource isolation in this phase.
- [ ] Add prompt-rendering tests that assert allowed side resources, forbidden parent resources, IM exact reply/absorbed closure, Track comment restriction, browser/web/research restriction, artifact/evidence/workspace restriction, checkpoint restriction, and the two legal outcomes.
- [ ] Prove no old triage prompt or side interrupt outcome appears in the side frame.

### `interrupt_submit_parent` Idle Parent Bug

- [ ] Add a runtime executor regression test for `interrupt_submit_parent` where `app_server.interrupt_turn` raises `AppServerUnavailableError("thread thr-main has no active in-progress turn")`; `submit_turn` must still run and return a parent turn id.
- [ ] Keep existing running-parent interrupt behavior: interrupt first, then submit, and return `interrupted_turn_id`.
- [ ] Cover the no-active-turn race message (`active but no in-progress turn was found`) as no-op interrupt plus submit.
- [ ] Add or extend a Task Sys side-processing/tool test so `task_sys.need_parent(params.interrupt=true)` returns a parent runtime turn id when the parent is idle.
- [ ] Avoid restoring old raw inbound-to-parent prompt paths.
- [ ] Document whether status advancement remains pre-submit or is corrected in this work; if corrected, add a failure recovery test so runtime failures do not silently leave `parent_processing` without a submitted parent turn.

## Phase Order And Dependencies

1. **Phase 01 - Web input API cleanup**
   - Dependency: none. This is isolated from Task Sys runtime behavior because WebUI already sends through `/api/web/im/messages`.
   - Reason to do first: removes a live stale surface and reduces noise before Task Sys prompt/runtime changes.

2. **Phase 02 - Side frame resource boundary prompt**
   - Dependency: none on phase 01, but should land before or alongside parent handoff validation because it reduces unnecessary `interrupt=true` handoffs from simple IM closures.
   - Reason to do second: prompt-only plus tests, no runtime actuation risk.

3. **Phase 03 - Parent idle interrupt submit fix**
   - Dependency: uses current Task Sys parent handoff implementation from the proactive rebuild. It is logically independent of phase 02 but easier to verify after side prompt tests clarify when parent is required.
   - Reason to do third: highest runtime risk, so execute after isolated cleanup and prompt contracts are stable.

4. **Final acceptance**
   - Dependency: all phase docs have Actual Changes and Actual Verification filled in.
   - Output: `docs/spec/task-sys-memo-optimization/99-final-acceptance.md`.

## Phase Matrix

| Phase | Memo | Objective | Code Scope | Test Scope |
| --- | --- | --- | --- | --- |
| 01 | Web management input residue cleanup | Delete Web backend input API and tests while preserving IM WebUI send | `tools/launcher/web_management.py`, `tests/test_web_management.py`, UI contract scan | `python -m pytest -q tests/test_web_management.py`, `node --test tests/web_management_ui_contract.test.js`, residue scan |
| 02 | Side thread resource boundary prompt | Put resource model into every `task_sys.side_frame` | `tools/launcher/task_sys_runtime.py`, `tests/test_task_sys_runtime_executor.py` | focused prompt tests, `py_compile`, residue scan |
| 03 | interrupt_submit_parent idle parent bug | Treat idle/no-active-turn interrupt as no-op and still submit parent frame | `tools/launcher/task_sys_runtime.py`, `tests/test_task_sys_runtime_executor.py`, `tests/test_task_sys_side_processing.py` if tool-level coverage is needed | focused runtime/tool tests, `py_compile`, no old prompt path scan |

## End-To-End Acceptance Contract

- WebUI message composer action -> `POST /api/web/im/messages` -> IM message is created and routed to actor wake/Task Sys; no Web backend `/api/instances/<actor>/input` path exists.
- Side task frame submission -> rendered `task_sys.side_frame` includes resource-boundary rules -> side has deterministic guidance to either close simple current-source IM work or call `task_sys.need_parent` for parent resources.
- Side calls `task_sys.need_parent(params.interrupt=true)` while parent is idle -> Task Sys runtime executes `interrupt_submit_parent` -> interrupt no-ops for idle/no-active-turn -> parent frame is submitted and a parent `turn_id` is returned.
- Side calls `task_sys.need_parent(params.interrupt=true)` while parent is running -> Task Sys runtime interrupts the active turn, then submits the parent frame and returns both `interrupted_turn_id` and parent `turn_id`.

## Residue Cleanup Strategy

- Search live source/test surfaces only; historical memos and accepted phase records are evidence, not cleanup targets.
- Phase 01 scan:
  - `rg -n "/api/instances/.*/input|action == \"input\"|_send_input|_run_input_command|instance input for" tools/launcher tests -S`
  - Expected after cleanup: no Web management route/helper/test success-path hits. CLI `instance input` hits outside Web management are allowed when they are CLI surfaces.
- Phase 02 scan:
  - `rg -n "\\[IM MESSAGE TRIAGE|\\[TRACK COMMENT TRIAGE|side_interrupt|Do not use any other side outcome|Core policy: decide by required resources" tools/launcher/task_sys_runtime.py tests/test_task_sys_runtime_executor.py -S`
  - Expected after prompt update: resource-boundary terms exist; old triage and `side_interrupt` do not appear in the rendered frame or positive expectations.
- Phase 03 scan:
  - `rg -n "request_parent_message_handling|\\[MESSAGE NEEDS PARENT\\]|message\\.mark\\(needs_parent\\)|parent_prompt_submitted" tools scripts tests -S`
  - Expected: no restored old raw parent prompt path; remaining hits must be negative assertions or historical tests.

## Risks And Non-Goals

- Do not edit `buddyswitch/objects/**` or runtime state directly.
- Do not remove CLI `instance input`; only Web management API residue is in phase 01.
- Do not implement tool-layer hard isolation for side resource policy in phase 02.
- Do not replace the generic Task Sys runtime with `DaemonRuntime.submit_parent_prompt`; phase 03 should fix the new runtime boundary directly.
- Do not mix unrelated UI redesign, Track comment side write support, artifact/evidence policy, browser policy enforcement, or checkpoint behavior into these phases.
- Service-starting product smoke is optional and must only run after confirming lifecycle cleanup. Focused unit/contract tests are the primary verification loop for this optimization set.

## Progress Log

- [x] Required docs and three memos read.
- [x] Current live surfaces searched for Web input route, side frame prompt, and parent handoff runtime.
- [ ] Phase 01 plan created.
- [x] Phase 01 implemented and verified.
- [x] Phase 02 planned, implemented, and verified.
- [x] Phase 03 planned, implemented, and verified.
- [x] Final acceptance completed.

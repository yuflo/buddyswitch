# Web Interface Actor Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development while implementing this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first actor-centered Web console with an independent Track workspace while preserving the phase two call architecture.

**Architecture:** Browser code calls only Web-interface HTTP APIs. Web-interface APIs own browser DTOs and may compose host-control facts with reusable domain/service read models. Track read semantics are extracted only as small domain functions when needed to avoid importing actor tool handlers or duplicating Track business rules.

**Tech Stack:** Python `unittest`/`pytest`, local launcher HTTP service, vanilla HTML/CSS/JavaScript, Node `node --test` contract/state tests.

---

## Expected Outcome

The Web UI moves from an instance-centered control room to an actor-centered console:

- Actor is the default selected product object.
- Instance lifecycle remains available, but it is shown as runtime control for the selected actor.
- Track has an independent workspace section.
- Browser-facing APIs are Web-interface APIs, not actor runtime tools or repo-shaped APIs.
- Phase two exclusions remain excluded in the first cut: no `/api/actors/{actor_id}/tasks`, no `/api/actors/{actor_id}/tracks`, no `/api/tracks/{track_id}/comments`, no lower `actor.tasks`, no lower `track.workspace`.

## File Map

- Create `docs/spec/web-interface-actor-console-implementation-plan.md`
  - This plan.
- Create `docs/spec/web-interface-actor-console-test-plan.md`
  - Target-effect verification plan.
- Create `docs/spec/web-interface-actor-console-api-dto.md`
  - Browser DTO and route appendix.
- Create or modify `scripts/env/domain/track_read.py`
  - Minimal pure Track read helpers if Web otherwise needs to duplicate Track summary/detail/comment-thread semantics.
- Modify `tools/launcher/web_management.py`
  - Add Web product routes and private DTO composition helpers.
- Modify `tools/launcher/assets/web-management/index.html`
  - Reframe UI as actor console plus Track workspace.
- Modify `tools/launcher/assets/web-management/app.js`
  - Move state model from selected instance to selected actor and selected workspace section.
- Modify `tools/launcher/assets/web-management/styles.css`
  - Support professional console layout, responsive behavior, empty/loading/error states.
- Modify `tests/test_web_management.py`
  - API contract tests and boundary regression tests.
- Modify `tests/test_env_layer_boundaries.py` only if a new domain file needs an explicit boundary assertion.
- Modify `tests/web_management_ui_contract.test.js`
  - Static production asset contract.
- Modify `tests/web_management_ui_state.test.js`
  - JavaScript state and pure-rendering behavior.

## Task 1: Lock The Plan Artifacts

- [ ] Add this implementation plan under `docs/spec`.
- [ ] Add the matching test plan under `docs/spec`.
- [ ] Add the API/DTO appendix under `docs/spec`.
- [ ] Run `rg -n "TB[D]|TO[DO]|may[be]|probab[ly]" docs/spec/web-interface-actor-console-*`.
- [ ] Run `git diff --check -- docs/spec/web-interface-actor-console-*`.

## Task 2: Add Web API Red Tests

Files:

- Modify `tests/test_web_management.py`.

Test behaviors:

- `GET /api/actors` returns active/inactive actor roster rows derived from instance list data, with role, runtime status, health, thread id, browser port, updated time, and workspace path.
- `GET /api/actors/{actor_id}/console` returns one actor console DTO with runtime facts, task view, direct IM target metadata, and Track summary area.
- `GET /api/tracks` returns a Web DTO list of non-archived Track summaries.
- `GET /api/tracks/{track_id}` returns detail DTO including materials, proofs, updates, and comments/thread summary inside the detail response.
- Invalid actor ids return the existing `INVALID_REQUEST` style.
- Unknown Track ids return `404`.
- Web route code does not import `env.tools.track._impl`.
- No `env.services.tracks` file is introduced.
- No new first-cut routes for `/api/actors/{actor_id}/tasks`, `/api/actors/{actor_id}/tracks`, or `/api/tracks/{track_id}/comments`.

Commands:

```bash
python -m pytest tests/test_web_management.py -q
```

Expected red state before implementation:

- New route tests fail with `NOT_FOUND`.
- Boundary tests fail if forbidden imports or route strings are introduced.

## Task 3: Implement Minimal Track Read Domain If Needed

Files:

- Create `scripts/env/domain/track_read.py` only if Web cannot stay clean without it.
- Add focused tests in `tests/test_web_management.py` or a small domain test if needed.

Allowed functions:

- `track_summary(track)`
- `track_detail(track, comments)`
- `comment_threads(comments, active_actor=None)`

Rules:

- Keep the module pure and read-only.
- It may shape reusable Track semantics such as non-archived filtering, materials/proofs classification, update normalization, and comment thread grouping.
- It must not use UI terms such as workspace, panel, card, sidebar, tab, badge, selected row, or actor-console section.
- It must not create a service class or a broad Track service.

Focused command:

```bash
python -m pytest tests/test_web_management.py tests/test_env_layer_boundaries.py -q
```

## Task 4: Implement Web Product APIs

Files:

- Modify `tools/launcher/web_management.py`.

Implementation notes:

- Add route dispatch before instance action parsing:
  - `GET /api/actors`
  - `GET /api/actors/{actor_id}/console`
  - `GET /api/tracks`
  - `GET /api/tracks/{track_id}`
- Reuse `_list_instances()` and `_get_instance_status(actor_id)` for host-control facts.
- Use `task_management.current_view(...)` for task read state when the selected actor has enough instance context.
- Use the minimal Track read domain helper if needed.
- Keep composition helpers private to `WebManagementService`.
- Do not call runtime broker or `env.tool` for general console reads.
- Do not import actor tool handler modules.

Focused command:

```bash
python -m pytest tests/test_web_management.py -q
```

## Task 5: Add Frontend Red Tests

Files:

- Modify `tests/web_management_ui_contract.test.js`.
- Modify `tests/web_management_ui_state.test.js`.

Test behaviors:

- Production HTML contains Actor Console and Tracks navigation targets.
- Production JavaScript calls `/api/actors`, `/api/actors/{id}/console`, `/api/tracks`, and `/api/tracks/{id}`.
- Production JavaScript does not call first-cut excluded APIs.
- State initializes with `selectedSection: "actors"` and `selectedActorId`, not only `selectedInstanceId`.
- Actor roster selection updates console target and clears per-actor transient feedback.
- Track workspace selection loads detail and keeps comments inside Track detail state.
- Instance lifecycle controls are computed from selected actor runtime facts.
- Empty actor roster and empty Track workspace states are represented explicitly.

Focused command:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected red state before frontend implementation:

- Asset tests fail because existing UI is still instance-first.
- State tests fail because actor/track state helpers do not exist yet.

## Task 6: Implement Actor-Centered Frontend

Files:

- Modify `tools/launcher/assets/web-management/index.html`.
- Modify `tools/launcher/assets/web-management/app.js`.
- Modify `tools/launcher/assets/web-management/styles.css`.

Implementation notes:

- Left navigation has two primary sections: `Actors` and `Tracks`.
- Main default section is Actor Console.
- Actor console includes:
  - actor roster;
  - selected actor runtime summary;
  - task summary;
  - message composer and compact direct conversation feed;
  - lifecycle/TUI controls as runtime actions.
- Track workspace includes:
  - non-archived Track list;
  - selected Track detail;
  - materials, proofs, updates, and comment threads within the detail panel.
- Preserve existing IM send/poll behavior through `/api/im/*`.
- Preserve existing instance lifecycle actions through `/api/instances/*`.
- Add loading, empty, and error states without decorative UI copy.
- Keep the UI dense, calm, scan-oriented, and responsive.

Focused command:

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

## Task 7: Run Integration Verification

Commands:

```bash
python -m pytest tests/test_web_management.py tests/test_env_layer_boundaries.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git diff --check -- docs/spec tools/launcher scripts/env tests
rg -n "env\\.tools\\.track\\._impl|env\\.services\\.tracks|/api/actors/[^\"']+/tasks|/api/actors/[^\"']+/tracks|/api/tracks/[^\"']+/comments|track_workspace|actor\\.tasks|track\\.workspace" tools scripts tests docs/spec
```

Expected:

- Python and Node tests pass.
- `git diff --check` exits zero.
- Boundary search returns no active code or plan violations.

## Task 8: Manual UI Smoke

Command:

```bash
./buddyswitch-codex web --port 8765
```

Manual checks:

- Browser opens the actor-centered console.
- `Actors` is the default active section.
- Actor roster renders from existing instances.
- Selecting an actor updates the runtime, task, and message areas.
- Lifecycle buttons preserve previous enable/disable semantics.
- `Tracks` section renders list/detail and does not require opening an actor tool.
- Layout does not overlap at desktop width and at a narrow mobile viewport.

Stop the server after the smoke check.

## Self-Review

- The plan keeps Actor as the first product object without making Actor own Task, Track, or IM semantics.
- Track gets an independent Web workspace without introducing a lower `track.workspace` API.
- The plan avoids new service entities unless a pure domain read helper is needed.
- Tests are required before production code and cover behavior, architecture boundaries, and UI state.

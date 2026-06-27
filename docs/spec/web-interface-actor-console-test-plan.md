# Web Interface Actor Console Test Plan

Status: Phase two/three implementation test plan.

## Target Effect

The release is valid only if the user-visible Web surface becomes an actor-centered console with an independent Track workspace and the implementation preserves the confirmed call architecture.

The test plan must prove these outcomes:

- Browser code consumes Web-interface APIs only.
- Actor is the primary selected object.
- Track is an independent workspace section.
- Instance control remains available as runtime control, not as the top-level product model.
- Task, Track, IM, runtime, and persistence boundaries stay clean.
- First-cut excluded APIs are still absent.

## Focused Test Commands

Run these during development:

```bash
python -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Run this before acceptance:

```bash
python -m pytest tests/test_web_management.py tests/test_env_layer_boundaries.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
git diff --check -- docs/spec tools/launcher scripts/env tests
```

Run this boundary search before acceptance:

```bash
rg -n "env\\.tools\\.track\\._impl|env\\.services\\.tracks|/api/actors/[^\"']+/tasks|/api/actors/[^\"']+/tracks|/api/tracks/[^\"']+/comments|track_workspace|actor\\.tasks|track\\.workspace" tools scripts tests docs/spec
```

Expected:

- Tests exit zero.
- `git diff --check` exits zero.
- Boundary search has no active implementation hits. If it finds this test plan or implementation plan because the forbidden strings are listed as forbidden examples, that is acceptable only when the hit is in a negative assertion or documented forbidden list.

## Backend API Coverage

### Actor Roster

Test: `tests/test_web_management.py`

Coverage:

- `GET /api/actors` returns `ok: true`.
- Response includes `actors`.
- Each actor row has:
  - `actor_id`
  - `role`
  - `status`
  - `app_server_health`
  - `thread_id`
  - `browser_port`
  - `updated_at`
  - `workspace_dir`
  - `runtime`
- Rows derive from host-control instance list.
- No repo reads are needed for roster.

Anti-cheat:

- The test uses a fake command runner and asserts the exact `instance list --json` call.
- The returned DTO must preserve at least two actors with different roles/statuses.

### Actor Console

Test: `tests/test_web_management.py`

Coverage:

- `GET /api/actors/{actor_id}/console` returns one selected actor DTO.
- Response contains:
  - `actor`
  - `runtime`
  - `task`
  - `tracks`
  - `im`
- Runtime facts come from `instance status`.
- Task facts come from a domain read model, not an actor runtime tool.
- Track information is a summary inside the console, not a separate `/api/actors/{actor_id}/tracks` route.

Anti-cheat:

- The test patches the task domain reader and asserts it is called with resolved actor context.
- The test asserts no command resembling `env.tool` or runtime broker dispatch is called.

### Track List

Test: `tests/test_web_management.py`

Coverage:

- `GET /api/tracks` returns non-archived Track summaries.
- Archived rows are excluded.
- Summary fields are stable and browser-facing.
- No actor tool handler is imported.

Anti-cheat:

- Fixture includes one active Track and one archived Track.
- The archived Track id must be absent from the response.

### Track Detail

Test: `tests/test_web_management.py`

Coverage:

- `GET /api/tracks/{track_id}` returns:
  - base Track fields;
  - `materials`;
  - `proofs`;
  - `updates`;
  - `comment_threads`;
  - `comment_summary`.
- Comments are included in the detail DTO.
- There is no separate `/api/tracks/{track_id}/comments` route in phase two/three.

Anti-cheat:

- Fixture includes at least two comments in one thread and one comment in another thread.
- The test asserts thread grouping, open/resolved counts, and latest comment preview.

### Error Behavior

Test: `tests/test_web_management.py`

Coverage:

- Invalid actor id returns `400 INVALID_REQUEST`.
- Unknown actor returns existing command-failure mapping or `404` only if status resolution is changed intentionally.
- Unknown Track returns `404 NOT_FOUND`.
- Archived Track detail returns `404 NOT_FOUND` to avoid exposing archived pages.

## Architecture Boundary Coverage

Test: `tests/test_web_management.py` and `tests/test_env_layer_boundaries.py`

Coverage:

- Web management source does not import `env.tools.track._impl`.
- No `scripts/env/services/tracks.py` exists.
- Browser assets do not contain runtime broker, `env.tool`, repo module names, taskbox paths, or JSON object paths.
- New Web APIs do not add first-cut excluded route strings.

Anti-cheat:

- Source scans are exact and fail on forbidden active strings.
- Tests allow forbidden strings only inside test assertions that are explicitly checking absence.

## Frontend Contract Coverage

Test: `tests/web_management_ui_contract.test.js`

Coverage:

- HTML includes:
  - `actor-nav-button`
  - `tracks-nav-button`
  - `actors-list`
  - `actor-console`
  - `tracks-list`
  - `track-detail`
  - existing controls needed for create, message, lifecycle, and TUI actions.
- JavaScript includes:
  - `/api/actors`
  - `/api/actors/`
  - `/console`
  - `/api/tracks`
  - `/api/im/*`
  - `/api/instances/*` only for control-plane actions.
- JavaScript excludes:
  - `/api/actors/{id}/tasks`
  - `/api/actors/{id}/tracks`
  - `/api/tracks/{id}/comments`
  - `env.tool`
  - `env.repos`
  - `env.tools.track._impl`

Anti-cheat:

- Static contract checks both required and forbidden strings.
- Contract checks section ids, not only visible labels.

## Frontend State Coverage

Test: `tests/web_management_ui_state.test.js`

Coverage:

- Initial state uses `selectedSection: "actors"`.
- Actor roster refresh chooses the first actor if none is selected.
- Changing selected actor clears TUI feedback and points IM send target at the new actor.
- Track list refresh chooses the first Track if none is selected.
- Track detail state stores comment threads inside the selected Track detail object.
- Existing lifecycle button enablement behavior still works from actor runtime facts.
- Empty actor roster and empty Track list have explicit render states.

Anti-cheat:

- Pure helper tests inspect returned state transitions and rendered HTML snippets.
- Tests do not rely on browser snapshots alone.

## Manual UI Smoke

Run after focused tests pass:

```bash
./buddyswitch-codex web --port 8765
```

Manual checks:

- Desktop: Actor console opens as the primary view.
- Desktop: Track workspace can be opened from the sidebar.
- Desktop: no text overlaps in actor roster, runtime details, action controls, or Track detail.
- Mobile/narrow viewport: sidebar collapses above content and all controls remain reachable.
- Message composer still sends through IM APIs.
- Lifecycle buttons still call instance control APIs.

## Acceptance Criteria

The task is accepted when:

- Plan docs exist under `docs/spec`.
- Python focused tests pass.
- Node frontend tests pass.
- Whitespace diff check passes.
- Boundary search shows no active violations.
- Manual smoke does not reveal a blank page, broken primary navigation, or overlapped controls.
- Final summary states changed files, verification commands, and any remaining risk.

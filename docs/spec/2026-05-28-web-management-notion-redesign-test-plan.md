# Web Management Notion Redesign Test Plan

Date: 2026-05-28

## Objective

Verify that the BuddySwitch Web Management UI is rebuilt into a cleaner Notion-like local control console while preserving the current product behavior exactly.

This task is a first-version UI redesign, not a feature expansion. The implementation must improve layout, visual hierarchy, selected state, disabled state, danger action treatment, long-value handling, and responsive behavior without adding new controls or changing API behavior.

## Current Bottleneck

The current Web Management UI is visually blunt and operationally awkward:

- create controls, instance list, details, and actions are arranged as flat cards with weak hierarchy
- selected instance state is easy to miss
- action grouping does not communicate runtime vs lifecycle intent
- disabled and danger states are visually under-specified
- long instance ids, thread ids, and workspace paths can dominate the layout
- mobile layout only stacks sections, but does not create a coherent control flow

The backend and action semantics are not the bottleneck. The current Bootstrap-thread work already removed the old Web initialize workaround, so the redesign must not reintroduce it.

## Design Read

Reading this as: local operational control panel for BuddySwitch maintainers, with a restrained Notion-like workspace language, leaning toward native HTML/CSS/JS with dense admin-console hierarchy.

Design dials:

- `DESIGN_VARIANCE: 3`
- `MOTION_INTENSITY: 1`
- `VISUAL_DENSITY: 8`

## Scope

### In Scope

- Rebuild `tools/launcher/assets/web-management/index.html`
- Rebuild `tools/launcher/assets/web-management/styles.css`
- Adjust the render layer in `tools/launcher/assets/web-management/app.js`
- Add focused UI contract tests if useful
- Preserve current Web API, route names, payloads, state transitions, and action enablement rules
- Use `tmp/buddyswitch-web-rebuild-notion/` only as a visual reference for:
  - sidebar/workspace framing
  - white document-like panels
  - subtle warm background
  - thin dividers
  - compact controls
  - selected row and status badge treatment
  - responsive layout mechanics

### Out Of Scope

- Status strip or metric summary
- Search or filtering
- Activity feed
- Side thread UI
- Mode tabs
- Threads, Artifacts, or Runtime logs navigation
- Any Initialize or Retry Initialize UI
- New backend routes
- New JavaScript package dependencies
- New build chain
- Feature flags or old/new UI compatibility toggle

## Functional Requirements

FR1. The page still loads `/static/styles.css` and `/static/app.js` from `tools/launcher/assets/web-management`.

FR2. Initial refresh still calls:

- `GET /api/health`
- `GET /api/buddies`
- `GET /api/instances`
- `GET /api/instances/<selected>/status` when an instance is selected

FR3. Create still posts exactly to `POST /api/instances` with body `{"buddy": "<selected buddy id>"}`.

FR4. Instance selection still refreshes selected status through `GET /api/instances/<instance_id>/status`.

FR5. Existing actions still call the same endpoints:

- `POST /api/instances/<id>/input`
- `POST /api/instances/<id>/interrupt`
- `POST /api/instances/<id>/stop`
- `POST /api/instances/<id>/clear`
- `POST /api/instances/<id>/resume`
- `DELETE /api/instances/<id>`

FR6. Action enablement remains exactly defined by `computeInstanceActionState`:

- no selection disables all instance actions
- mutation busy disables all instance actions
- active healthy idle instance allows send when draft text is non-empty, stop, and clear
- active healthy busy instance allows send, interrupt, and stop, but not clear
- inactive instance allows resume and delete only

FR7. Create enablement remains exactly defined by `computeCreateEnabled`:

- no selected buddy disables create
- create busy disables create
- selected buddy with no create busy state enables create

FR8. Web initialize must remain removed:

- no `Retry Initialize` visible text
- no `initialize-button`
- no `canInitialize`
- no `/initialize` fetch path
- no fixed init prompt

FR9. First-version UI must not expose side conversations:

- no `Side` tab
- no `side-draft`
- no `sideThreads`
- no visible side-thread count or side-thread action controls

FR10. First-version UI must not expose mock-only enhancements:

- no status strip or `metric-*` elements
- no `search-input`
- no `data-view` filters
- no `data-mode` tabs
- no `activity-list`
- no `Refresh mock` or `Mock data` copy

FR11. The redesign must keep all real current controls discoverable on the first page:

- buddy select
- create button
- server/API status
- refresh button
- instance list
- selected instance detail
- instruction textarea
- send button
- interrupt button
- clear button
- stop button
- resume button
- delete button
- message banner

FR12. Long values must not break the layout:

- instance ids
- thread ids
- workspace paths
- timestamps
- browser port values
- server error messages

FR13. The selected instance must be visually obvious in the instance list and reflected in the detail panel.

FR14. Disabled buttons must be visually distinct and still non-clickable.

FR15. Delete must be visually separated as a dangerous action without changing its endpoint or enablement rule.

FR16. The mobile viewport must present a single-column operational flow:

1. header/status
2. create controls
3. instance list
4. selected instance details
5. actions

FR17. No new dependency or build step is introduced. Opening the served HTML through `tools/launcher/web_management.py` remains enough.

## Test Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | `tests/test_web_management.py::test_static_assets_are_served` |
| FR2 | Existing Web API tests plus manual network inspection during browser run |
| FR3 | `tests/test_web_management.py::test_create_instance_delegates_to_launcher_start_without_initialize_input` |
| FR4 | Existing selection path in browser verification |
| FR5 | `tests/test_web_management.py` action route tests |
| FR6 | `tests/web_management_ui_state.test.js` |
| FR7 | `tests/web_management_ui_state.test.js` |
| FR8 | New static UI contract test and static `rg` scan |
| FR9 | New static UI contract test and static `rg` scan |
| FR10 | New static UI contract test and static `rg` scan |
| FR11 | New static UI contract test |
| FR12 | Browser screenshot and layout-bound checks |
| FR13 | Browser screenshot and DOM class check after row selection |
| FR14 | Browser screenshot and DOM disabled-state check |
| FR15 | Static class check plus screenshot |
| FR16 | Mobile screenshot at 390x844 |
| FR17 | Dependency/package check plus static serving test |

## Automated Test Plan

### 1. Preserve Action-State Unit Tests

File: `tests/web_management_ui_state.test.js`

Run:

```bash
node tests/web_management_ui_state.test.js
```

Expected:

- all current tests pass
- expected action-state objects still have exactly these keys:
  - `canSend`
  - `canInterrupt`
  - `canStop`
  - `canDelete`
  - `canClear`
  - `canResume`
- no `canInitialize` key returns

### 2. Add Static UI Contract Test

File: `tests/web_management_ui_contract.test.js`

Purpose:

- enforce first-version functional equivalence
- prevent mock-only controls from leaking into production UI
- verify all required real controls remain present

The test should read:

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/assets/web-management/styles.css`

Assertions:

- required element ids exist in `index.html`:
  - `server-status`
  - `refresh-button`
  - `buddy-select`
  - `create-button`
  - `instances-body`
  - `instance-detail`
  - `instruction-input`
  - `send-button`
  - `interrupt-button`
  - `stop-button`
  - `clear-button`
  - `resume-button`
  - `delete-button`
  - `message-banner`
- required real API strings exist in `app.js`:
  - `/api/health`
  - `/api/buddies`
  - `/api/instances`
  - `/status`
  - `/input`
  - `/interrupt`
  - `/stop`
  - `/clear`
  - `/resume`
- forbidden strings are absent from production Web UI assets:
  - `Retry Initialize`
  - `retry-init`
  - `canInitialize`
  - `initialize-button`
  - `/initialize`
  - `Refresh mock`
  - `Mock data`
  - `sideThreads`
  - `side-draft`
  - `metric-active`
  - `metric-busy`
  - `metric-attention`
  - `metric-side`
  - `status-strip`
  - `search-input`
  - `activity-list`
  - `data-mode`
  - `data-view`
  - `Runtime logs`
  - `Artifacts`
  - `Threads`

Run:

```bash
node tests/web_management_ui_contract.test.js
```

Expected:

- PASS

### 3. Preserve Web API Behavior Tests

File: `tests/test_web_management.py`

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_web_management.py -q
```

Expected:

- all tests pass
- `test_initialize_route_is_removed` still returns 404
- create and clear tests still prove no fixed init prompt is sent
- side route tests still pass even though first-version UI does not expose side controls
- static asset serving test still passes

### 4. Static Forbidden-Feature Scan

Run:

```bash
rg -n 'Retry Initialize|retry-init|canInitialize|initialize-button|/initialize|Refresh mock|Mock data|sideThreads|side-draft|metric-active|metric-busy|metric-attention|metric-side|status-strip|search-input|activity-list|data-mode|data-view|Runtime logs|Artifacts|Threads' tools/launcher/assets/web-management
```

Expected:

- no matches

### 5. JavaScript Syntax Check

Run:

```bash
node --check tools/launcher/assets/web-management/app.js
```

Expected:

- no syntax errors

### 6. Dependency Boundary Check

Run:

```bash
git diff -- package.json package-lock.json pnpm-lock.yaml yarn.lock
```

Expected:

- no output

### 7. Browser Verification

Run the Web Management server with a test-safe local port, then inspect in a browser.

Suggested command:

```bash
python3 tools/launcher/web_management.py --host 127.0.0.1 --port 8765
```

Expected browser checks at desktop viewport `1440x980`:

- page renders without console errors caused by missing DOM ids
- sidebar is visible and contains create controls
- header contains API status and refresh
- instances panel is the primary left content
- detail/actions panel is the primary right content
- selected row is visibly distinct
- instruction textarea is in the action panel
- delete action is visually danger-styled
- disabled actions are visibly disabled
- long ids and workspace paths do not overlap adjacent panels

Expected browser checks at mobile viewport `390x844`:

- layout is single-column
- no horizontal page overflow
- table may scroll horizontally inside its own panel if needed
- controls remain reachable without overlapping text
- message banner remains visible below actions

### 8. Screenshot Artifacts

Capture screenshots for review:

- desktop: `tmp/web-management-notion-redesign-desktop.png`
- mobile: `tmp/web-management-notion-redesign-mobile.png`

Expected:

- screenshots show functional equivalence with a Notion-like visual language
- no status strip, activity feed, search/filter, side tab, or initialize UI appears

## Review Checklist

- The plan tests behavior from product requirements, not implementation convenience.
- Existing backend and API tests remain the behavioral source of truth.
- New UI contract tests guard the first-version boundary.
- Screenshot checks cover the visual and responsive risks that unit tests cannot prove.
- No test requires adding a new frontend dependency or build chain.

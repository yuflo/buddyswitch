# Phase 02: Focused Render Functions

## Phase Goal

Split the full-page render path into focused render functions and add dynamic section title/summary rendering without yet deleting the compatibility render wrapper.

## Source Requirements

- Memo Task 2.
- The page title and summary derive from `state.selectedSection`.
- `renderComposer()` updates composer controls without rewriting actor rows.

## Code Research Findings

- `index.html` currently has static `<h1>` and `.page-summary` without ids.
- `render()` currently owns shell, lists, details, composer, Open TUI, IM conversation, and row listener installation.
- State-test render stubs lack `pageTitle`, `pageSummary`, and `refreshButton`.

## Scope

- Modify `tests/web_management_ui_state.test.js`.
- Modify `tools/launcher/assets/web-management/app.js`.
- Modify `tools/launcher/assets/web-management/index.html`.

## Non-Goals

- Do not delete the `render()` wrapper in this phase.
- Do not move event delegation in this phase.

## Old Path / Residue Definition

- Old: one full `render()` function doing every DOM write.
- New: `sectionCopy()`, `renderShell()`, `renderRoleSelect()`, `renderActorList()`, `renderActorDetail()`, `renderTrackList()`, `renderTrackDetail()`, `renderComposer()`, `renderOpenTui()`, `renderAll()`.

## Development Plan

1. Add `page-title` and `page-summary` ids in `index.html`.
2. Extend state-test render stubs.
3. Add `sectionCopy()` tests.
4. Add `renderComposer()` non-list-write test.
5. Run focused state test and record expected red failure.
6. Add `sectionCopy()` and focused render functions.
7. Keep `render()` as a temporary wrapper to `renderAll()`.
8. Export `renderComposer` and `sectionCopy`.
9. Run focused state test and record green result.

## Test Plan

Focused command:

```bash
node tests/web_management_ui_state.test.js
```

Expected red result:

- Fails before implementation because `sectionCopy` and `renderComposer` are not exported.

Expected green result:

- All state tests pass.

## Red Verification Expectation

New focused-render tests fail before implementation for missing exports/functions.

## Green Verification Commands

```bash
node tests/web_management_ui_state.test.js
```

## Residue Scan Commands

Compatibility `render()` residue is still expected until Phase 06:

```bash
rg -n "function render\(|render\(state, elements\)" tools/launcher/assets/web-management/app.js -S
```

## Acceptance Criteria

- Static title/summary nodes have stable ids.
- `sectionCopy('actors')` and `sectionCopy('tracks')` return expected copy.
- `renderComposer()` updates composer controls without rewriting actor rows.
- Focused state test passes.

## Execution Record

- Added `page-title` and `page-summary` ids to `index.html`.
- Added `pageTitle`, `pageSummary`, and `refreshButton` stubs to the state-test render element factory.
- Added `sectionCopy()` state test for actor and Track workspace copy.
- Added `renderComposer()` focused render test proving actor rows are not rewritten.
- Added `sectionCopy()`, focused render functions, `renderAll()`, and a temporary `render()` wrapper.
- Added `pageTitle` and `pageSummary` bootstrap element references.
- Exported `renderComposer` and `sectionCopy`.

## Test Results

Red:

```text
$ node tests/web_management_ui_state.test.js
not ok - section copy follows selected workspace
TypeError: app.sectionCopy is not a function
exit 1
```

Green:

```text
$ node tests/web_management_ui_state.test.js
ok - create button requires selected role and no start busy state
...
ok - polling connection-wide events acks off-selected actor message without rendering it
exit 0
```

## Residue Results

Expected compatibility wrapper and full-render call sites remain for later phases:

```text
$ rg -n "function render\(|render\(state, elements\)" tools/launcher/assets/web-management/app.js -S
772:  function render(state, elements) {
779:          render(state, elements);
787:          render(state, elements);
813:    render(state, elements);
...
1294:      render(state, elements);
```

## Phase Acceptance Decision

Accepted. Focused render helpers and section copy are implemented; temporary render residue is queued for Phase 06.

## Remaining Risk

Most runtime event handlers still call the temporary full render path until later phases convert them.

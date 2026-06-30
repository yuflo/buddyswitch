# Phase 07: CSS Feedback And Mobile Priority

## Phase Goal

Add pending/loading visual feedback classes and place the Actions column before deep runtime detail on narrow screens.

## Source Requirements

- Memo Task 7.
- Stylesheet must support `.is-loading`, `.button.is-pending`, `.selectable-row.is-loading`, `.inline-loading`, `.im-row.pending`, `.im-row.failed`.
- Narrow screens prioritize Actions before deep runtime detail.

## Code Research Findings

- `styles.css` currently has disabled button styling but not memo-required pending/loading classes.
- Existing media queries include `@media (max-width: 960px)` and `@media (max-width: 1180px)`.

## Scope

- Modify `tools/launcher/assets/web-management/styles.css`.
- Modify `tests/web_management_ui_contract.test.js`.

## Non-Goals

- Do not redesign the WebUI.
- Do not add images, frameworks, or visual systems.

## Old Path / Residue Definition

- Old: pending feedback is only disabled opacity or text.
- New: explicit loading/pending classes and mobile column priority.

## Development Plan

1. Add CSS contract marker test.
2. Run contract test and record expected red failure.
3. Add feedback CSS after `.button[disabled]`.
4. Add `.runtime-column { order: -1; }` inside `@media (max-width: 960px)`.
5. Run contract test and record green result.

## Test Plan

Focused command:

```bash
node tests/web_management_ui_contract.test.js
```

Expected red result:

- Fails before CSS implementation because required markers are missing.

Expected green result:

- Contract test passes.

## Red Verification Expectation

CSS marker contract test fails before the new classes exist.

## Green Verification Commands

```bash
node tests/web_management_ui_contract.test.js
```

## Residue Scan Commands

No old residue unique to this phase.

## Acceptance Criteria

- Contract test confirms pending/loading CSS markers.
- Narrow viewport CSS prioritizes `.runtime-column`.
- Contract test passes.

## Execution Record

- Added a stylesheet contract test for pending/loading feedback markers.
- Added `.is-loading`, `.button.is-pending`, `.selectable-row.is-loading`, `.inline-loading`, `.im-row.pending`, and `.im-row.failed` styles.
- Added `.runtime-column { order: -1; }` inside the `@media (max-width: 960px)` block.
- Phase 08 mobile smoke found the Send button only partially visible at `390x844`; added a mobile-only `#instruction-input` height of `96px` so the textarea and Send button are fully visible before runtime metadata.

## Test Results

Red:

```text
$ node tests/web_management_ui_contract.test.js
not ok - production stylesheet supports pending and loading feedback states
AssertionError: Expected asset content to include: .is-loading
exit 1
```

Green:

```text
$ node tests/web_management_ui_contract.test.js
ok - production html keeps all real control ids used by the web UI
...
ok - first version does not ship mock-only controls
exit 0
```

Post-smoke mobile CSS adjustment check:

```text
$ node tests/web_management_ui_contract.test.js
ok - production html keeps all real control ids used by the web UI
...
ok - first version does not ship mock-only controls
exit 0
```

## Residue Results

No old residue unique to this phase.

## Phase Acceptance Decision

Accepted.

## Remaining Risk

Final focused verification, scope checks, and browser smoke remain.

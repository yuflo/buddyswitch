# Web Task Panel B2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active/recoverable-only WebUI Task summary with the approved compact B2 ledger so a selected teammate's completed or canceled work remains visible after the current task disappears.

**Architecture:** Keep Task Sys as the only lifecycle owner. Extend its existing external-safe Task Read projection with a terminal group, let Web Console cap and forward that group, and replace the browser renderer in place. The browser formats and discloses already-classified rows; it does not reproduce lifecycle rules or add a second data path.

**Tech Stack:** Python domain projection and Web service adapter; dependency-free JavaScript and CSS WebUI; `unittest` integration tests and Node `node:test` UI tests through `./buddyswitch-test focused`; in-app browser acceptance against the real service at `http://127.0.0.1:8765/`.

---

## Acceptance Sentence

When a user selects a teammate in the real WebUI, the 300px right-rail Task card shows the highest-priority current task and two most-recent terminal tasks at no more than 220px default height, keeps terminal history visible when no task is active, expands to at most five recent tasks, and exposes one keyboard-accessible row detail at a time without horizontal or internal-card overflow.

Consumer path:

```text
select teammate -> Task Read external projection -> Web Console bounded response -> B2 Task card -> current and terminal work stays observable
```

Protected contracts: none. This is a coordinated internal cutover; no legacy response fallback or old renderer remains.

## Scope And Ownership

- `scripts/env/domain/task_sys.py` remains unchanged and owns persistence, lifecycle constants, and transitions.
- `scripts/env/domain/task_read.py` owns actor filtering, terminal classification, sorting, counts, and the existing external row allowlist.
- `tools/launcher/web_management.py` owns the Web Console response and caps terminal rows at five without filtering or reordering them.
- `tools/launcher/assets/web-management/app.js` owns compact rendering and native disclosure semantics only.
- `tools/launcher/assets/web-management/styles.css` owns B2 geometry and visual states; the right rail continues to own vertical scrolling.
- No Task mutation, pagination, search, concurrent-active browser, execution detail, failure detail, new endpoint, or storage change is in scope.

## Resumable State

- Current state: FRAME and TRACE complete; PROVE begins at Task 1.
- Approved design: `docs/superpowers/specs/2026-07-17-web-task-panel-b2-design.md`.
- Frozen visual baseline: `docs/memo/2026-07-17-web-task-panel-b2-implementation-baseline.html`.
- Test entry: only `./buddyswitch-test focused <file-or-nodeid>...`.
- Runtime acceptance target: real service `http://127.0.0.1:8765/`; use environment/launcher interfaces, never edit `buddyswitch/objects/**` directly.

## Task 1: Extend The External Task Read Contract

**Files:**

- Modify: `tests/integration/im/test_external_query.py:53-216`
- Modify: `scripts/env/domain/task_read.py:126-158`

- [x] Add a `status` parameter to the test record helper and extend `test_task_external_actor_projection_filters_sorts_and_allowlists_exact_keys` with completed, canceled, active, and other-actor records.
- [x] Assert `terminal_tasks` contains only completed/canceled rows in descending `updated_at` order, `terminal_count` is the full terminal count, active groups retain existing behavior, and every terminal row has exactly `TASK_KEYS` with no sensitive fields.
- [x] Run the exact RED proof:

  ```bash
  ./buddyswitch-test focused tests/integration/im/test_external_query.py
  ```

  Expected: failure because `terminal_tasks`/`terminal_count` are absent.

- [x] Implement `_is_terminal_task(record)` using only `task_sys.COMPLETED` and `task_sys.CANCELED`; build the terminal group from the already sorted, actor-filtered `classified` records; return the group and exact count.
- [x] Run the same focused command and expect GREEN.
- [x] Inspect the diff to confirm the external row allowlist is unchanged and Task Read is the sole new classifier.

## Task 2: Forward A Bounded Terminal Projection Through Web Console

**Files:**

- Modify: `tests/integration/web/test_management_product_api.py:387-476`
- Modify: `tools/launcher/web_management.py:715-742`

- [x] Seed six terminal records for the selected actor using Task Sys public transitions, plus the existing active and recoverable records.
- [x] Assert the Console response reports the full `terminal_count`, forwards only five `terminal_tasks`, preserves newest-first order, and exposes exactly the external-safe row keys.
- [x] Add negative assertions that the adapter contains no terminal lifecycle classifier and no sensitive Task fields reach the response.
- [x] Run the exact RED proof:

  ```bash
  ./buddyswitch-test focused tests/integration/web/test_management_product_api.py
  ```

  Expected: failure because the Web Console omits terminal fields.

- [x] Add `terminal_count` and `terminal_tasks[:5]` to `_actor_console`; do not filter, sort, or translate rows in the adapter.
- [x] Run the same focused command and expect GREEN.

## Task 3: Replace The Task Summary With The B2 Ledger

**Files:**

- Replace tests in: `tests/unit/web/ui_state_task.test.js:1-73`
- Modify: `tools/launcher/assets/web-management/app.js:1369-1392`
- Modify: `tools/launcher/assets/web-management/styles.css:322-421,920-942`
- Modify: `tools/launcher/assets/web-management/index.html:146-149`

- [x] Replace the legacy summary test with fixtures and assertions for all required states:
  - active uses the first active row and teal current styling;
  - recoverable takes priority and uses amber `Needs attention` copy;
  - no-active keeps terminal rows visible;
  - no current and no terminal rows renders `No tasks yet`;
  - header reports `N active · M recent` and collapsed output contains exactly two of five terminal rows.
- [x] Add interaction-contract assertions on the generated markup:
  - `Recent` is a native disclosure with accurate collapsed text and `aria` semantics;
  - expanded content can expose all five server-supplied rows without a second fetch;
  - current and terminal rows are keyboard-operable native controls;
  - row details share one native exclusive-disclosure name and contain only full `task_id` plus full `updated_at`;
  - legacy `Active`/`Recoverable` summary-line markup and sensitive/mutation fields are absent.
- [x] Run the exact RED proof:

  ```bash
  ./buddyswitch-test focused tests/unit/web/ui_state_task.test.js
  ```

  Expected: failure against the legacy summary renderer.

- [x] Replace `renderTaskSummaryHtml` with one direct B2 renderer. Require `active_tasks`, `recoverable_tasks`, `terminal_tasks`, `active_count`, and `terminal_count`; choose `recoverable_tasks[0] || active_tasks[0]`; use native `<details>` for Recent and row detail, with a shared `name` for exclusive row details.
- [x] Add deterministic short local-time formatting while preserving the original ISO value in detail. Escape every external value before insertion.
- [x] Add narrowly prefixed `.task-ledger-*` styles that achieve:
  - 276px card fit within the existing 300px rail;
  - default B2 body at no more than 220px including the existing card heading;
  - teal current, amber attention, 36px idle, two compact terminal rows;
  - no internal scrollbar and visible keyboard focus.
- [x] Run the same focused command and expect GREEN.

## Task 4: Prove Affected Boundaries And Replacement

**Files:**

- Verify: `tests/integration/im/test_external_query.py`
- Verify: `tests/integration/web/test_management_product_api.py`
- Verify: `tests/unit/web/ui_state_task.test.js`
- Verify affected asset/architecture tests discovered from repository references.

- [x] Run one frozen focused proof set:

  ```bash
  ./buddyswitch-test focused \
    tests/integration/im/test_external_query.py \
    tests/integration/web/test_management_product_api.py \
    tests/unit/web/ui_state_task.test.js \
    tests/unit/web/asset_contract_html.test.js \
    tests/unit/architecture/test_external_control.py
  ```

- [x] Run residue checks:

  ```bash
  rg -n "<span>Active</span>|<span>Recoverable</span>|task_sys\.actor_task_projection" \
    tools/launcher/web_management.py tools/launcher/assets/web-management \
    tests/unit/web/ui_state_task.test.js
  rg -n "terminal_tasks|terminal_count" \
    scripts/env/domain/task_read.py tools/launcher/web_management.py \
    tools/launcher/assets/web-management/app.js tests
  ```

  Expected: the first command finds no live legacy Web renderer or retired Web projection path; the second shows one classification owner and direct projections/consumer assertions. Other current internal Task tools continue to use Task Sys' richer internal projection and are not Web compatibility residue.

- [x] Inspect `git diff --check` and the scoped diff. Confirm no unrelated files, fallback shape, duplicate classifier, Task mutation, or internal card scrolling were introduced.

## Task 5: Accept Through The Real 8765 Product Path

**Files:**

- Runtime only; do not edit runtime projection files directly.
- Evidence screenshots may be saved under ignored `tmp/iterations/task-panel-b2-acceptance/`.

- [x] Resolve the exact process and launcher command serving port 8765. Restart only that known process if static assets are not hot-reloaded; preserve the separate docs preview on 8777.
- [x] Use the real launcher/WebUI path to ensure a teammate exists, submit a real task/message, observe the current task, and wait until its completed projection remains in Recent after current clears.
- [x] In the in-app browser at `http://127.0.0.1:8765/`, verify:
  - Task card width is 276px within the 300px rail;
  - active and no-active default states are at most 220px;
  - attention markup/geometry is covered by the exact production renderer fixture and its browser-equivalent style measurements if a safe real failure cannot be induced;
  - collapsed Recent shows two rows and expanded Recent shows up to five, then contracts;
  - opening another row detail closes the previous row; full ID/time are shown; keyboard activation and focus indicators work;
  - Task card and a 390px viewport have no horizontal overflow and the card has no internal scrollbar;
  - no main-path console errors occur.
- [x] Clean up any acceptance-only actor/process through the same public launcher interface and confirm no process, socket, or temporary runtime-state residue remains. Keep screenshots only as ignored evidence. The acceptance used the already-running dev actor, so no actor was created or deleted; the current-worktree 8765 server remains intentionally available for user inspection.

Runtime evidence: a real `im.message.created` task was observed as active and then as completed in Recent; eight real terminal tasks remain externally visible while the Web Console serves the newest five. At 1280px the rail/card measured 300px/276px, idle+five measured 201.8px, active+five measured 207.8px, and neither the card nor page overflowed. At a 390px emulated viewport, document client and scroll widths both measured 375px. Recent and row-detail state survived an automatic refresh, exclusive detail count stayed one, keyboard focus was visible with accurate `aria-expanded`, and browser logs were empty. A safe real runtime failure was not induced; attention semantics are covered by the exact production renderer fixture and use the already measured current-row geometry with only its approved amber presentation/copy variant.

## Task 6: Final Acceptance And Commit

- [x] Review the implementation against Product, Contract, Architecture, Replacement, and Operations proof classes.
- [x] Re-run the frozen focused proof if browser acceptance caused any source change.
- [x] Run `git status --short`, `git diff --check`, and inspect the final diff against the acceptance sentence.
- [x] Commit the coherent implementation and plan with a focused message such as:

  ```bash
  git add docs/memo/2026-07-17-web-task-panel-b2-implementation-plan.md \
    scripts/env/domain/task_read.py \
    tools/launcher/web_management.py \
    tools/launcher/assets/web-management/app.js \
    tools/launcher/assets/web-management/styles.css \
    tests/integration/im/test_external_query.py \
    tests/integration/web/test_management_product_api.py \
    tests/unit/web/ui_state_task.test.js
  git commit -m "feat(web): keep recent tasks visible"
  ```

- [x] Final report must name changed behavior/files, exact automated verification, real 8765 browser evidence, omitted checks, residual risk, cleanup result, and the commit ID.

## Acceptance Matrix

| Proof class | Claim | Evidence |
|---|---|---|
| Product | A completed task remains visible after current clears; two recent rows expand to five | Real 8765 interaction plus UI test |
| Contract | Terminal means only completed/canceled, sorted newest-first, full count, unchanged row allowlist | Task Read focused integration test |
| Architecture | Lifecycle classification exists once in Task Read; Web Console only caps; browser only presents | Source inspection, adapter test, residue search |
| Replacement | Legacy active/recoverable-only summary and retired projection path are absent | Negative UI assertions and `rg` residue check |
| Operations | Real service reloads cleanly; no console/overflow/internal-scroll errors; acceptance resources cleaned | Browser inspection, process checks, cleanup record |

Full repository testing is intentionally omitted unless focused evidence exposes broader risk: this is not a merge/release freeze, and the repository contract reserves `./buddyswitch-test full` for that boundary.

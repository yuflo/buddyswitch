# WebUI Team Room Visual Restoration Plan

## Goal

Restore the production WebUI visual structure toward `tmp/webui-teamwork-prototypes.html` without changing backend contracts or inventing unsupported teammate facts.

## Cause Backtrace

The current mismatch is a plan omission, not an implementation drift.

Evidence:

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` required Team room / Tracks copy, route boundaries, old-shell residue removal, read-only Track Studio behavior, and browser smoke.
- The plan did not require matching the prototype's visual artboard structure: integrated room shell, section-tinted rails, center conversation canvas, attached composer, right teammate rail, Track document canvas, or Track comment rail.
- Stage specs focused on semantic names, route residue, fake-data prevention, and responsive safety. Stage 8 explicitly asked for a restrained product-tool CSS pass and banned fake visual markers, but it still did not define prototype fidelity checks.
- Current production assets therefore satisfy the semantic forward redesign while still looking like a generic app shell: fixed sidebar, page header, and separate card panels.

Conclusion: the visual restoration requirement was absent from the previous acceptance contract. The next slice should add explicit visual contract tests before changing production CSS/HTML.

## Visual Restoration Scope

Restore from the prototype:

- Team Room uses one integrated workspace surface rather than unrelated floating cards.
- Desktop Team Room is a three-column room: left roster rail, center conversation/thread, right teammate rail.
- The left rail includes the BuddySwitch mark, primary room navigation, teammate roster, and the compact start-teammate control.
- The center column uses a room header, scrollable thread area, and attached composer band.
- The right column reads as a teammate rail with runtime/detail sections and lifecycle/TUI controls.
- Tracks uses a Track Studio shell: left Track list rail, center document page, right read-only comments/context rail.
- Backgrounds, borders, spacing, and shadows follow the prototype's calm off-white room materials.
- Mobile stacks explicitly without horizontal overflow.

Do not restore from the prototype:

- Fake avatars, fake capacity/load bars, fake unread counts, fake collaborator counts, fake proof ages, or any fact not available from current DTOs.
- Track write UI, Track comment composer, side-thread UI, alternate legacy views, or new routes.

## Files

Modify:

- `tools/launcher/assets/web-management/index.html`
- `tools/launcher/assets/web-management/styles.css`
- `tools/launcher/assets/web-management/app.js` only if render markup needs class hooks for Track Studio sections
- `tests/web_management_ui_contract.test.js`
- `tests/web_management_ui_state.test.js` only if render markup hooks need behavioral coverage
- `tests/test_web_management.py` only for static asset assertions

Do not modify:

- Backend/router/runtime files
- `buddyswitch/objects/**`
- `buddyswitch/local/private/**`

## Implementation Plan

1. Add failing visual contract tests.
   - Require Team Room prototype hooks: `.room-sidebar`, `.room-main`, `.room-header`, `.room-thread`, `.composer`, `.person-panel`, `.person-card`.
   - Require Track Studio prototype hooks: `.studio-side`, `.studio-doc`, `.doc-page`, `.studio-rail`, `.comment-thread`.
   - Require CSS grid proportions and material colors close to the prototype: `260px minmax(0, 1fr) 320px` for Team Room, `250px minmax(0, 1fr) 320px` for Track Studio, rail backgrounds, center white/off-white surfaces.
   - Keep existing negative tests for fake facts and forbidden routes.

2. Replace static shell classes and structure.
   - Convert `team-room-grid` into the integrated `proto-shell team-room` surface.
   - Rename the left roster panel to use `room-sidebar` while keeping all current IDs.
   - Convert the center conversation panel into `room-main` with `room-header`, `room-thread`, and `composer`.
   - Convert the right teammate card into `person-panel` with `person-card` sections.
   - Preserve all existing control IDs.

3. Restore Track Studio visual shell.
   - Convert `track-studio-grid` into `proto-shell track-studio`.
   - Use `studio-side` for the Track list.
   - Use `studio-doc` and `doc-page` around `#track-detail`.
   - Add a `studio-rail` containing read-only comment/context summaries from existing rendered Track detail, without composer or write routes.

4. Adjust render markup only where needed.
   - Add stable class hooks to `renderTrackDetailHtml()` for document sections and read-only comment blocks.
   - Keep roster rendering supported-data-only: role label, actor id, status, and health.

5. Run focused verification after each change block.
   - `node tests/web_management_ui_contract.test.js`
   - `node tests/web_management_ui_state.test.js`
   - `python3 -m pytest -q tests/test_web_management.py::WebManagementProductApiTests tests/test_web_management.py::WebManagementHTTPActionTests::test_static_assets_are_served`
   - Browser smoke at desktop and mobile against `./buddyswitch-codex web`.

## Acceptance

- The production desktop Team Room visually uses the prototype's three-part room shell.
- The production desktop Tracks page visually uses the prototype's Track Studio shell with a document page and right read-only rail.
- Existing API routes and control IDs remain intact.
- No fake teammate facts or forbidden UI/routes are reintroduced.
- Desktop and mobile browser smoke show no horizontal overflow or incoherent overlap.
- Focused Node and Python checks pass.

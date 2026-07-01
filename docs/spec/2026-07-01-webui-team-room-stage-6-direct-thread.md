# WebUI Team Room Stage 6 Direct Thread Placement

## Stage Goal

Verify and lock the direct conversation placement: direct IM stays in the center conversation column, while runtime facts, TUI controls, lifecycle controls, and status feedback stay in the right teammate card. Stage 6 covers memo Task 6.

## Associated Memo Tasks

- `docs/memo/2026-07-01-webui-team-room-forward-implementation-plan.md` Task 6: Move Direct Conversation To The Center And Keep Actions In The Teammate Card.

## Read And Confirmed Code Locations

- `tools/launcher/assets/web-management/index.html`: Stage 2 already moved `im-conversation`, `instruction-input`, `send-button`, and `interrupt-button` into `.conversation-column`.
- `tools/launcher/assets/web-management/index.html`: `actor-runtime-detail`, task/Track summaries, TUI controls, lifecycle buttons, status, and banner live in `aside#actor-console.teammate-card`.
- `tools/launcher/assets/web-management/app.js`: `sendImDraft()` posts to `/api/im/messages` with `target_identity_id`, `content`, and `reply_to: null`.
- `tests/web_management_ui_contract.test.js`: current route contract already excludes old actor input routes and `/api/web/im`.

## Current Problems And Residue Points

- The desired production DOM already exists because memo Task 2's shell snippet included the center conversation column.
- The placement is not yet explicitly locked by a scoped contract test.
- Without a DOM-placement guard, a future edit could put the composer back into the teammate card while keeping ids intact.

## Development Change Scope

Modify:

- `tests/web_management_ui_contract.test.js`

No production code change is expected for this stage unless the placement test exposes a gap.

## Explicit Non-Scope

- No backend, route, DTO, service, env tool, object-store, or runtime changes.
- No app behavior changes to `sendImDraft()`.
- No Track Studio rendering changes.
- No CSS polish beyond existing Stage 2 layout.

## TDD And Test Plan

1. Add a contract test that extracts `.conversation-column` from `index.html`.
2. Assert the conversation column contains `im-conversation`, `instruction-input`, `send-button`, `interrupt-button`, `Message`, and `Message the selected teammate.`
3. Assert the conversation column does not contain TUI or lifecycle controls.
4. Extract `aside#actor-console.teammate-card`.
5. Assert the teammate card contains runtime/task/Track summaries, TUI controls, lifecycle controls, status, and banner.
6. Assert the teammate card does not contain `instruction-input` or `send-button`.
7. Run focused contract and state tests.

## Expected Test Result

Because Stage 2 already applied memo Task 6's static markup, the new placement contract is expected to pass immediately. This stage is still necessary as a regression lock for the direct-thread layout boundary.

Command:

```bash
node tests/web_management_ui_contract.test.js
```

Expected result:

- Pass.

## Implementation Steps

1. Add `Team room keeps direct thread centered and actions in the teammate card` to `tests/web_management_ui_contract.test.js`.
2. Run the focused contract test.
3. Run the focused state test to confirm existing send/IM behavior remains green.
4. Record results.

## Acceptance Commands

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Expected result:

- Both commands exit `0`.
- The placement contract proves direct IM ids are in `.conversation-column` and lifecycle/TUI controls are in `.teammate-card`.

## Residue Scan Command

```bash
rg -n "instruction-input|send-button|interrupt-button|open-tui-button|clear-button|stop-button|resume-button|delete-button|/api/im/messages|/api/web/im|/api/actors/.*/input" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js
```

Expected after Stage 6:

- Production hits show direct thread ids and `/api/im/messages`.
- No `/api/web/im` or actor input route appears in production assets.

## Stage Completion Standard

- Stage 6 spec exists.
- Direct-thread placement contract exists and passes.
- Focused contract and state tests pass.
- No production code change is required unless the contract exposes a real gap.

## Stage 6 Result

Implemented test change:

- Added `Team room keeps direct thread centered and actions in the teammate card` to `tests/web_management_ui_contract.test.js`.

Verification:

```bash
node tests/web_management_ui_contract.test.js
node tests/web_management_ui_state.test.js
```

Result: both pass.

Residue and route scan:

```bash
rg -n "instruction-input|send-button|interrupt-button|open-tui-button|clear-button|stop-button|resume-button|delete-button|/api/im/messages|/api/web/im|/api/actors/.*/input" tools/launcher/assets/web-management tests/web_management_ui_contract.test.js
```

Result: expected direct-thread and lifecycle control ids are present, `/api/im/messages` is present, and no production `/api/web/im` or actor input route appears.

## Risks And Boundary Checks

- Risk: id-only tests can pass while layout regresses. The placement test must scope assertions to the actual column/card HTML.
- Risk: duplicating controls would satisfy id checks but break UX. The placement test should also exclude direct controls from the teammate card.

Boundary check:

```bash
git diff --name-only | rg -v '^(tools/launcher/assets/web-management/(index\.html|styles\.css|app\.js)|tests/(web_management_ui_contract\.test\.js|web_management_ui_state\.test\.js)|docs/spec/2026-07-01-webui-team-room-stage-[123456].*\.md)$'
```

Expected during Stage 6: no output, ignoring pre-existing untracked memo files.

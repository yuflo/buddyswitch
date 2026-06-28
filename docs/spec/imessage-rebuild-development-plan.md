# iMessage Rebuild Development Plan

Date: 2026-06-28

## Goal

Rebuild BuddySwitch IM forward so there is one `External IM Session` application
semantic boundary, two HTTP projections of it, and one local iMessage Channel
Adapter that consumes only `/api/im/*`.

## Architecture

Target dependency direction:

```text
iMessage bridge -> /api/im/* -> External IM Session -> Central IM Core -> repo
Browser UI -> /api/web/im/* -> External IM Session -> Central IM Core -> repo
Actor runtime message tool -> Central IM Core -> repo
```

`/api/im/*` and `/api/web/im/*` stay as separate consumer surfaces. They must
not stay as separate business implementations.

## Stage 0: Fact Baseline And Entry Freeze

### Stage Goal

Lock the current facts before implementation and prove the Stage 1 problem is
real.

### Current Problem

The memo and feasibility brief are planning inputs, but implementation must use
current code and command output. The brief's old local `imsg` note is stale.

### Planned Files

- Create: `docs/spec/imessage-rebuild-context-audit.md`
- Create: `docs/spec/imessage-rebuild-development-plan.md`
- Create: `docs/spec/imessage-rebuild-test-plan.md`
- Create/update: `docs/spec/imessage-rebuild-stage-acceptance.md`

### New Files

Documentation files only.

### Deleted Or Replaced Old Paths

None.

### Forbidden Compatibility Paths

- Do not start iMessage adapter implementation in Stage 0.
- Do not change business code in Stage 0.
- Do not treat stale memo text as stronger than current command evidence.

### Executable Tasks

1. Read the memo, the feasibility brief, AGENTS guidance, and the four relevant
   `docs/bitter` principle notes.
2. Search current IM code and tests for `/api/im/*`, `/api/web/im/*`, direct
   message service calls, actor wake paths, and browser IM calls.
3. Run focused baseline verification.
4. Run the scoped direct-call residue scan and record its current failing hits.
5. Record Stage 0 acceptance in
   `docs/spec/imessage-rebuild-stage-acceptance.md`.

### Stage Acceptance

- Current `imsg` capability surface is recorded.
- Current IM/Web test baseline is recorded.
- Current live surfaces are named.
- The Stage 1 residue problem is proven by current hits.
- No business code has changed.

### Regression Risk

Low. Documentation-only stage. Risk is inaccurate audit, mitigated by command
output and exact file paths.

## Stage 1: Rebuild External IM Session

### Stage Goal

Create the only External IM application semantic layer and make both HTTP route
families delegate to it.

### Current Problem

`tools/launcher/im_http_router.py`, `tools/launcher/web_management.py`, and
`tools/launcher/web_im_identity.py` call Central IM external-session service
methods directly. That is the dual-track semantic split.

### Planned Files

- Create: `scripts/env/services/external_im_session.py`
- Create: `tests/test_external_im_session.py`
- Modify: `tools/launcher/im_http_router.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tools/launcher/web_im_identity.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: `tests/test_im_external_reply_loop.py` only if constructor wiring
  changes require it.
- Update: `docs/spec/imessage-rebuild-stage-acceptance.md`

### New Files

`scripts/env/services/external_im_session.py` owns:

- `ExternalImSession.create_connection(display_name)`
- `ExternalImSession.authenticate(connection_key)`
- `ExternalImSession.list_actors(role_id)`
- `ExternalImSession.send_message(connection, target_identity_id, content, reply_to)`
- `ExternalImSession.read_events(connection, limit, wait_ms)`
- `ExternalImSession.get_direct_conversation(connection, identity_id, limit)`
- `ExternalImSession.get_message(connection, message_id)`
- `ExternalImSession.list_replies(connection, message_id)`
- `ExternalImSession.update_disposition(connection, message_id, disposition, reason)`

### Deleted Or Replaced Old Paths

Replace these direct calls in projection files:

- `message_service.create_external_connection`
- `message_service.authenticate_external_connection_key`
- `message_service.send_external_connection_message`
- `message_service.read_external_connection_events`
- `message_service.get_im_direct_conversation`
- `message_service.get_im_message`
- `message_service.list_im_replies`
- `message_service.update_im_disposition`

No route family is deleted in this stage.

### Forbidden Compatibility Paths

- No compatibility wrapper that lets HTTP/Web choose between old direct calls
  and new session calls.
- No duplicate actor target resolver in both route files.
- No browser exposure of `connection_key`.
- No change to `/api/im/*` or `/api/web/im/*` public response contracts beyond
  implementation routing.

### Executable Tasks

1. Re-read this Stage 1 plan and the Stage 1 section of
   `docs/spec/imessage-rebuild-test-plan.md`.
2. Add a residue/contract test that fails while projection files call Central IM
   external-session methods directly.
3. Add `scripts/env/services/external_im_session.py` with the concrete methods
   listed above.
4. Move actor identity resolution into `ExternalImSession`.
5. Change `ImHttpRouter` to parse HTTP, authenticate header, call
   `ExternalImSession`, and map status codes.
6. Change `WebManagementService` to keep browser-specific session/query/body/DTO
   work and call `ExternalImSession` for IM semantics.
7. Change `WebImIdentityProvider` to use `ExternalImSession` for
   create/authenticate while still owning only server-side persistence.
8. Run the focused tests and residue scan.
9. Record exact commands, results, changed files, and remaining risk in
   `docs/spec/imessage-rebuild-stage-acceptance.md`.

### Stage Acceptance

- Only `ExternalImSession` calls Central IM external-session methods from the
  HTTP/Web path.
- `/api/im/*` contract tests still pass.
- `/api/web/im/*` contract tests still pass.
- Web UI JS contract tests still pass.
- Scoped residue scan returns no hits in HTTP/Web projection files.

### Regression Risk

Medium. Contract shape must stay stable while moving implementation. The main
risk is advancing the external event cursor before Web DTO filtering finishes;
keep existing behavior tests green and add session tests around event reads.

## Stage 2: Projection Contract Tightening

### Stage Goal

Prevent the two route families from growing product semantics again.

### Current Problem

Existing tests prove behavior but not enough of the projection boundary. A
future edit could reintroduce direct Central IM calls while keeping route
behavior green.

### Planned Files

- Create or extend: `tests/test_external_im_projection_contract.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_web_management.py`
- Modify: `tests/test_im_web_management_projection.py`
- Update: `docs/spec/imessage-rebuild-stage-acceptance.md`

### New Files

Optional new focused test file:

- `tests/test_external_im_projection_contract.py`

### Deleted Or Replaced Old Paths

None beyond removing any old projection tests that teach direct service
ownership.

### Forbidden Compatibility Paths

- No resurrection of `/api/messages/send`.
- No resurrection of `/api/im/external-participants`.
- Browser JS must not call `/api/im/*`.
- Route tests must not assert that Web/HTTP files call `message_service`
  directly.

### Executable Tasks

1. Add projection contract tests using a fake session where practical.
2. Add a scoped source scan test for direct Central IM external-session calls in
   HTTP/Web projection files.
3. Keep Web-specific tests limited to browser session ownership, actor scope
   requirement, and DTO shaping.
4. Run focused Python and Node verification.
5. Record acceptance.

### Stage Acceptance

- Integration API tests distinguish auth/body/query/status mapping from session
  semantics.
- Web BFF tests distinguish browser session/DTO behavior from session
  semantics.
- Residue scan is part of the automated suite.
- Naming for Integration External IM HTTP API, Web Console IM BFF, and External
  IM Session is consistent in tests.

### Regression Risk

Low to medium. Main risk is over-mocking the session and weakening behavior
coverage. Keep existing end-to-end route tests alongside projection tests.

## Stage 3: iMessage Channel Adapter MVP

### Stage Goal

Add a local iMessage bridge that is only a headless consumer of `/api/im/*`.

### Current Problem

No `imessage bridge` command exists. Central IM and Web code must not gain
iMessage-specific state.

### Planned Files

- Create: `tools/launcher/imessage_bridge.py`
- Modify: `buddyswitch-codex`
- Create: `tests/test_imessage_bridge.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Update: `docs/spec/imessage-rebuild-stage-acceptance.md`

### New Files

`tools/launcher/imessage_bridge.py` owns:

- CLI parsing for `bridge`;
- `imsg status` health check;
- connection creation or restore through `/api/im/connections`;
- target validation through `/api/im/actors`;
- inbound `imsg watch` processing;
- `is_from_me` filtering;
- allowlist filtering;
- rowid/guid dedupe;
- outbound `/api/im/events` polling;
- message fetch through `/api/im/messages/{id}`;
- send back through `imsg send`;
- local adapter state under `runtime_files.LOCAL_ROOT / "imessage-bridge"`.

### Deleted Or Replaced Old Paths

None expected. This stage adds the first adapter path.

### Forbidden Compatibility Paths

- iMessage adapter must not import `env.services.messages`.
- iMessage adapter must not import `env.repos.messages`.
- Central IM Core must not contain Apple ID, chat id, rowid, guid, sender
  allowlist, or `imsg` process lifecycle fields.
- No generic channel plugin framework.
- No Web UI dependency.

### Executable Tasks

1. Add failing bridge tests for fail-fast actor validation, allowlist rejection,
   `is_from_me` filtering, rowid/guid dedupe, and outbound event exactly-once.
2. Add `buddyswitch-codex imessage bridge` command dispatch.
3. Implement a small HTTP client for `/api/im/*` using the standard library.
4. Implement local JSON state load/save with 0600 permissions.
5. Implement inbound mapping and dedupe.
6. Implement outbound polling and send-once tracking.
7. Add source scans proving adapter isolation from Central IM internals.
8. Run focused tests and record acceptance.

### Stage Acceptance

- Bridge tests cover all MVP adapter rules named in the memo.
- Source scan proves no Central IM service/repo imports in adapter code.
- Central IM source scan proves no iMessage-specific fields in core.
- `./buddyswitch-codex imessage bridge --server ... --target-identity-id ... --allow-sender ...`
  is the documented command shape.

### Regression Risk

Medium to high. The adapter crosses local process, HTTP, and filesystem state.
Keep implementation concrete and adapter-local; defer real Messages.app effects
to Stage 4 smoke.

## Stage 4: End-To-End Smoke

### Stage Goal

Prove the MVP user-visible iMessage loop or record the exact external blocker.

### Current Problem

Module tests cannot prove a real iPhone-to-Mac-to-BuddySwitch-to-iPhone loop.

### Planned Files

- Create: `docs/spec/imessage-bridge-smoke-runbook.md`
- Update: `docs/spec/imessage-rebuild-stage-acceptance.md`
- Modify tests only if the automated acceptance slice needs a stable command
  wrapper.

### New Files

`docs/spec/imessage-bridge-smoke-runbook.md` records:

- prerequisites;
- commands;
- allowlisted sender used;
- target actor identity used;
- observed bridge logs;
- observed iPhone result;
- failure classification if blocked.

### Deleted Or Replaced Old Paths

None.

### Forbidden Compatibility Paths

- Do not call a mocked bridge smoke "real smoke".
- Do not mark Stage 4 complete if Apple/Messages permissions block the run
  without recording the blocker and separating it from BuddySwitch adapter
  behavior.

### Executable Tasks

1. Keep or run the automated external reply-loop acceptance test.
2. Start `./buddyswitch-codex web --port 8765`.
3. Start `./buddyswitch-codex imessage bridge ...`.
4. Send one text from the allowlisted iPhone identity.
5. Confirm the actor receives and replies.
6. Confirm the reply lands in the same iMessage chat.
7. Record command output and observations.

### Stage Acceptance

- Automated external reply-loop acceptance still passes.
- Real smoke is recorded, or a precise external environment blocker is recorded.
- The smoke validates one-to-one text, one allowlisted sender, one target actor,
  and same-chat reply.

### Regression Risk

High because macOS permissions and Apple account state are outside the repo.
Bridge startup must produce actionable errors.

## Stage 5: Residue Cleanup And Documentation Closeout

### Stage Goal

Make live surfaces teach the final architecture and not the old dual-track
semantics.

### Current Problem

Current architecture docs still say Web IM delegates to the message service.
Tests and docs may also retain old route or direct-core wording after
implementation.

### Planned Files

- Modify: `docs/arch/web-interface-call-architecture.md`
- Modify: `tests/test_im_web_management_projection.py`
- Modify: any live tests that still teach old names.
- Update: `docs/spec/imessage-rebuild-stage-acceptance.md`

### New Files

Only add a short principle doc if a durable rule emerges that is not already
covered by `docs/bitter`.

### Deleted Or Replaced Old Paths

- Remove old helper names or docs that describe `/api/im/*` and
  `/api/web/im/*` as separate product implementations.
- Remove any live-surface instruction suggesting iMessage should call Central IM
  Core directly.

### Forbidden Compatibility Paths

- Do not edit historical memos just to make scans pass.
- Do not add broad repo-wide scans over common terms.
- Do not preserve old wording in live architecture docs.

### Executable Tasks

1. Update `docs/arch/web-interface-call-architecture.md` to name
   `External IM Session` as the shared semantic layer.
2. Run scoped scans over the memo-named live surfaces.
3. Remove or justify every hit.
4. Run full relevant verification.
5. Record final acceptance and remaining risk.

### Stage Acceptance

- No live surface teaches `/api/im/*` and `/api/web/im/*` as separate IM
  product implementations.
- No live surface suggests iMessage directly imports Central IM Core.
- No live surface suggests an iMessage-specific Central IM branch.
- Startup docs match actual commands.

### Regression Risk

Low to medium. Main risk is over-editing docs outside live surfaces. Keep scans
scoped.


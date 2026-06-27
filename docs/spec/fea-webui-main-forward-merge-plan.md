# fea-webui Worktree Forward Merge Plan

Date: 2026-06-27

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` for behavior changes and `superpowers:verification-before-completion` before declaring completion.

**Goal:** Merge the actual dirty `fea-webui` worktree into `main` while preserving the latest `main` message contract and browser lifecycle fixes.

**Architecture:** `fea-webui` owns the newest Web Interface feature: an actor-centered Web Management console, independent Track workspace, server-owned Web IM identity, and browser route cleanup. `main` owns newer post-`fea-webui` upgrades: the external IM connection-key contract and browser page TTL lifecycle fix. The merge must forward-port WebUI onto those latest contracts, not keep old token/cursor compatibility paths.

**Tech Stack:** Python launcher/runtime code, `pytest`/`unittest`, vanilla Web Management HTML/CSS/JavaScript, Node `--test`.

---

## Latest Feature Assessment

Authoritative state:

- `main` is at `16b19b4` (`docs: remove superseded merge plans`).
- `fea-webui` branch ref is at `3b0b70f` and is already an ancestor of `main`.
- `.worktrees/fea-webui` contains the real uncommitted feature work.

The latest feature to merge is not the stale branch tip. It is the dirty Web Interface phase-two rebuild in `.worktrees/fea-webui`:

- Actor-centered Web Management console replaces the instance-first primary workspace.
- Track workspace is a first-party Web section with Track list/detail DTOs.
- Web Management owns a stable server-side IM identity for browser messaging.
- Browser assets call Web-interface routes only and do not call lower actor tools or repo paths.
- Browser-facing `/api/im/*` passthrough is removed from Web Management.

Newer `main` work that must win during the merge:

- `3607cf1` replaces external IM registration/token/cursor behavior with `connection_key`.
- `3af4ea4` fixes browser page TTL lifecycle handling.
- `16b19b4` removes superseded merge plans.

Current drift:

- Dirty `fea-webui` code still names the persisted Web IM secret `participant_token` and calls the old `register_external_participant` / `authenticate_im_token` service API.
- Current `main` exposes `create_external_connection`, `authenticate_external_connection_key`, `send_external_connection_message`, and `read_external_connection_events`.
- Final merged code must use `connection_key` only. Do not reintroduce participant-token browser or Web Management compatibility.

## Forward-Only Rules

- Do not restore `/api/im/*` as a Browser-facing Web Management route.
- Do not reintroduce `/api/im/external-participants`.
- Do not preserve `participant_token`, Browser-held authorization headers, client-supplied IM event cursors, or `imParticipantToken`.
- Do not add dual code paths for old WebUI IM identity files.
- Do not add `env.tools.track._impl`, `env.services.tracks`, runtime broker dispatch, or actor tool handlers to Web Management reads.
- Do not add first-cut subpanel routes: `/api/actors/{actor_id}/tasks`, `/api/actors/{actor_id}/tracks`, or `/api/tracks/{track_id}/comments`.
- Keep implementation concrete in Web Management, `web_im_identity.py`, and the small read-only `track_read.py` domain helper.

## Implementation Plan

### Task 1: Preserve the dirty WebUI feature as a feature commit

Run in `.worktrees/fea-webui`.

- Verify dirty files:

```bash
git status --short --branch
git diff --stat
```

- Run the feature baseline:

```bash
python -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

- Commit the dirty WebUI feature after baseline is green:

```bash
git add docs/arch docs/memo docs/spec scripts/env/domain/track_read.py tools/launcher/web_im_identity.py tests/test_im_web_management_projection.py tests/test_web_management.py tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js tools/launcher/assets/web-management/app.js tools/launcher/assets/web-management/index.html tools/launcher/assets/web-management/styles.css tools/launcher/web_management.py
git commit -m "feat: rebuild web management actor console"
```

Expected: commit records only the Web Interface feature files and docs.

### Task 2: Bring latest `main` into `fea-webui`

Run in `.worktrees/fea-webui`.

```bash
git fetch --all --prune
git merge main
```

Expected:

- Merge surfaces WebUI conflicts against latest `main` IM changes if any.
- Browser TTL lifecycle files from `main` remain unchanged unless directly relevant.
- Superseded docs removed on `main` stay removed unless they are current WebUI docs.

### Task 3: Red test the connection-key forward-port

Before changing production code, update focused tests to require the current contract:

- `tests/test_web_management.py`
  - Web IM identity file stores `connection_key`, not `participant_token`.
  - `GET /api/web/im/session` returns participant metadata without `connection_key`.
  - Invalid persisted `connection_key` is replaced once and then reused.
  - Web IM send/events use the server-owned connection state.

- `tests/web_management_ui_contract.test.js`
  - Browser assets exclude `participant_token`, `imParticipantToken`, and Browser `Authorization` headers.
  - Browser assets include `/api/web/im/session`, `/api/web/im/messages`, `/api/web/im/events`, and `/api/web/im/conversations/direct`.

Run:

```bash
python -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected red state:

- Tests fail because `web_im_identity.py` still uses the old participant-token service API or persisted field names.

### Task 4: Forward-port Web IM identity to connection keys

Modify:

- `tools/launcher/web_im_identity.py`
- `tools/launcher/web_management.py`
- `tools/launcher/assets/web-management/app.js` only if route payload shape requires adjustment.

Required final behavior:

- Identity provider calls `message_service.create_external_connection(display_name="BuddySwitch Web")`.
- Identity provider stores `connection_key` in `im-session.json` with mode `0600`.
- Identity provider authenticates with `message_service.authenticate_external_connection_key(connection_key)`.
- Internal Web Management APIs derive participant and connection server-side.
- Browser responses never include `connection_key`.
- Browser JavaScript never sends authorization headers for IM.
- Actor-scoped Web events use the latest connection state and do not accept client-supplied lower IM cursor as the source of truth.

Focused green command:

```bash
python -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

### Task 5: Merge forward into `main`

After focused tests pass in `.worktrees/fea-webui`, run in the main checkout:

```bash
git status --short --branch
git merge --no-ff --no-edit fea-webui
```

Expected:

- `main` contains the Web Interface feature commit and forward-port fixes.
- `main` keeps `3607cf1`, `3af4ea4`, and `16b19b4` behavior.
- No conflict markers remain.

### Task 6: Remove stale residue

Run in the merged main tree:

```bash
rg -n "participant_token|imParticipantToken|external-participants|register_external_participant|authenticate_im_token" tools/launcher scripts/env tests docs/spec
rg -n "env\\.tools\\.track\\._impl|env\\.services\\.tracks|/api/actors/[^\"']+/tasks|/api/actors/[^\"']+/tracks|/api/tracks/[^\"']+/comments|track_workspace|actor\\.tasks|track\\.workspace" tools scripts tests docs/spec
```

Expected:

- No active implementation hits for old IM token/register APIs.
- Any remaining hits are negative assertions or historical docs that still matter; remove superseded WebUI docs if they contradict the final contract.

## Test Plan

### Focused WebUI gate

```bash
python -m pytest tests/test_web_management.py tests/test_im_web_management_projection.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Proves:

- Actor console and Track workspace API/asset contracts are green.
- Web Management rejects lower `/api/im/*` Browser-facing routes.
- Stable Web IM identity is server-owned and connection-key based.

### Lower IM regression gate

```bash
python -m pytest tests/test_im_product_core.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py tests/test_message_tool_im_client.py -q
```

Proves:

- Latest connection-key external IM contract still works.
- Actor external reply loop remains green.
- Message tool IM client behavior remains compatible with latest product contract.

### Browser lifecycle regression gate

```bash
python -m pytest tests/test_browser_page_expired_handler.py tests/test_cdp_browser_session.py tests/test_daemon_trigger_router.py -q
```

Proves:

- New WebUI merge did not regress the latest browser page TTL lifecycle fix.

### Architecture and hygiene gate

```bash
python -m pytest tests/test_env_layer_boundaries.py -q
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- .
git diff --check -- docs/spec tools/launcher scripts/env tests
```

Expected:

- Boundary tests pass.
- Conflict marker scan has no output.
- Whitespace check exits zero.

### Optional manual smoke

Run only after automated gates pass:

```bash
./buddyswitch-codex web --port 8765
```

Check:

- Actor console is the default view.
- Tracks section opens and renders list/detail.
- Selecting an actor refreshes runtime, task, track summary, and IM target.
- Message composer sends without browser-held credentials.
- Lifecycle and TUI controls remain available for the selected actor runtime.

## Acceptance Evidence

The merge is complete only when:

- `fea-webui` is no longer behind `main`.
- `main` contains the WebUI feature and latest message/browser lifecycle fixes.
- Old WebUI IM token/register residue is removed from active implementation.
- Focused WebUI, lower IM, browser lifecycle, boundary, conflict-marker, and whitespace gates pass.
- Final review compares explicit requirements in this plan against current files and command output.

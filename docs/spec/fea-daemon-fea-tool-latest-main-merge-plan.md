# fea-daemon and fea-tool Latest Main Merge Plan

Date: 2026-06-27

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the current latest `fea-daemon` and `fea-tool` feature tips into local `main` through one forward-only path, with stale merge plans removed and behavior verified by focused and broad tests.

**Architecture:** `fea-daemon` owns the latest external Central IM connection-key contract. `fea-tool` owns the latest browser page lifecycle expiry fix. The branches touch separate product surfaces, so the merge should preserve both feature tips directly instead of adding compatibility branches or old-path fallbacks.

**Tech Stack:** Python stdlib launcher/runtime code and `unittest`/`pytest` tests under `scripts/`, `tools/`, and `tests/`; Node `--test` JavaScript asset contract tests under `tests/`.

---

## Current Bottleneck

`main` is current with `origin/main` at `3b0b70f` (`Merge branch 'fea-tool'`), but it is not the latest integrated product state. After `git fetch --all --prune`, both feature branches still contain one unmerged tip commit:

- `fea-daemon` / `origin/fea-daemon`: `3607cf1` dated `2026-06-27 10:36:09 +0800`, `feat: replace external im contract with connection key`
- `fea-tool` / `origin/fea-tool`: `3af4ea4` dated `2026-06-26 18:53:00 +0800`, `fix browser page ttl lifecycle`

Evidence commands:

```bash
git log --format='%h %ci %s' main..fea-daemon
git log --format='%h %ci %s' main..fea-tool
git diff --name-status main..fea-daemon
git diff --name-status main..fea-tool
```

Expected before merge:

- `main..fea-daemon` prints only `3607cf1`.
- `main..fea-tool` prints only `3af4ea4`.
- `fea-daemon` changes IM service/repository/router/WebManagement tests and assets.
- `fea-tool` changes browser page lifecycle, daemon sweep, and related tests.

Dry-run merge checks already passed in both orders in throwaway worktrees:

- `main -> fea-daemon -> fea-tool`
- `main -> fea-tool -> fea-daemon`

No content conflicts were reported.

## Forward-Only Merge Rules

- Merge the latest branch tips, not older commits mentioned by stale planning docs.
- Do not add compatibility routes for old external IM fields or routes.
- Do not preserve `external_id`, `participant_token`, `event_cursor`, `imEventCursor`, or client-supplied external IM cursor behavior.
- Do not restore `/api/im/external-participants` as a compatible route.
- Do not add browser lifecycle compatibility for old TTL response fields, `touch_page_idle`, or delivered-after-refresh schedule behavior.
- Delete superseded merge-plan docs that describe older refs or earlier repair-only scopes.
- Keep implementation concrete in the owning modules; no new plugin engines, rule engines, adapters, or dual paths.

## Implementation Plan

### Task 1: Commit This Current Merge Plan

**Files:**

- Create: `docs/spec/fea-daemon-fea-tool-latest-main-merge-plan.md`

- [ ] **Step 1: Verify working tree is clean except this plan**

Run:

```bash
git status --short --branch
```

Expected:

- Branch is `main`.
- Only `docs/spec/fea-daemon-fea-tool-latest-main-merge-plan.md` is untracked or staged.

- [ ] **Step 2: Commit the plan**

Run:

```bash
git add docs/spec/fea-daemon-fea-tool-latest-main-merge-plan.md
git commit -m "docs: plan latest daemon and tool merge"
```

Expected: a docs-only commit on `main`.

### Task 2: Merge Latest Feature Tips

**Files:**

- Merge from: `fea-daemon`
- Merge from: `fea-tool`

- [ ] **Step 1: Reconfirm latest refs**

Run:

```bash
git fetch --all --prune
git rev-parse main origin/main fea-daemon origin/fea-daemon fea-tool origin/fea-tool
git log --format='%h %ci %s' main..fea-daemon
git log --format='%h %ci %s' main..fea-tool
```

Expected:

- `origin/main` still points to the pre-merge remote main unless it was updated externally.
- Local and remote feature branch refs match.
- Each `main..feature` range contains the latest intended feature tip.

- [ ] **Step 2: Merge `fea-daemon`**

Run:

```bash
git merge --no-ff --no-edit fea-daemon
```

Expected:

- Merge exits `0`.
- `3607cf1` is reachable from `main`.
- No conflict markers exist.

- [ ] **Step 3: Merge `fea-tool`**

Run:

```bash
git merge --no-ff --no-edit fea-tool
```

Expected:

- Merge exits `0`.
- `3af4ea4` is reachable from `main`.
- No conflict markers exist.

### Task 3: Remove Superseded Merge-Plan Residue

**Files:**

- Delete: `docs/spec/fea-tool-main-merge-implementation-plan.md`
- Delete: `docs/spec/fea-tool-main-merge-test-plan.md`
- Delete: `docs/spec/buddyswitch-im-merge-readiness-test-and-implementation-plan.md`
- Delete: `docs/superpowers/plans/2026-06-26-im-connection-key.md`

- [ ] **Step 1: Delete stale docs**

Run:

```bash
git rm docs/spec/fea-tool-main-merge-implementation-plan.md
git rm docs/spec/fea-tool-main-merge-test-plan.md
git rm docs/spec/buddyswitch-im-merge-readiness-test-and-implementation-plan.md
git rm docs/superpowers/plans/2026-06-26-im-connection-key.md
```

Expected:

- The combined plan in `docs/spec/fea-daemon-fea-tool-latest-main-merge-plan.md` is the active merge plan.
- The browser TTL lifecycle fix plan added by `fea-tool` remains because it documents the latest browser lifecycle repair, not an older merge state.

- [ ] **Step 2: Commit residue removal if needed**

Run:

```bash
git status --short
git commit -am "docs: remove superseded merge plans"
```

Expected: only stale planning files are deleted.

### Task 4: Run Merge Hygiene Checks

- [ ] **Step 1: Conflict marker scan**

Run:

```bash
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- .
```

Expected: no output and exit code `1`.

- [ ] **Step 2: Latest feature reachability**

Run:

```bash
git merge-base --is-ancestor 3607cf166ea078026fbd607704f808aaa4ed3c7e main
git merge-base --is-ancestor 3af4ea48669bb7848307f324c4e787815c747512 main
```

Expected: both commands exit `0`.

- [ ] **Step 3: Active docs check**

Run:

```bash
find docs/spec -maxdepth 1 -type f -name 'fea-tool-main-merge-*' -print
find docs/spec -maxdepth 1 -type f -name 'buddyswitch-im-merge-readiness-test-and-implementation-plan.md' -print
find docs/superpowers/plans -maxdepth 1 -type f -name '2026-06-26-im-connection-key.md' -print
```

Expected: no output.

## Test Plan

Run verification in the shortest meaningful loop first, then broaden.

### Focused Python Gate

Run:

```bash
python -m unittest \
  tests.test_im_product_core \
  tests.test_im_http_router \
  tests.test_im_external_reply_loop \
  tests.test_im_web_management_projection \
  tests.test_web_management \
  tests.test_message_tool_im_client \
  tests.test_browser_page_expired_handler \
  tests.test_cdp_browser_session \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox
```

Expected:

- Exit code `0`.
- `OK` from `unittest`.
- Proves both latest feature surfaces pass together after merge.

### Focused Node Gate

Run:

```bash
node --test tests/web_management_ui_state.test.js tests/web_management_ui_contract.test.js
```

Expected:

- Exit code `0`.
- WebManagement asset contract passes with the new IM connection-key client surface.

### Forward-Only Residue Gate

Run:

```bash
rg -n 'external-participants|participant_token|event_cursor|imEventCursor' \
  tools/launcher/im_http_router.py \
  tools/launcher/assets/web-management/app.js \
  tmp/im_reply_console.py \
  tests
```

Expected:

- No live HTTP/Web/terminal compatibility path for the old external IM contract.
- Any remaining hits must be explicit negative contract assertions, not active compatibility behavior.

Run:

```bash
rg -n 'register_browser_page_ttl|BROWSER_PAGE_TTL_SECONDS|ttl_seconds|ttl_registered|expiry_policy|Browser page TTL|touch_page_idle' scripts tools tests
```

Expected:

- No active code or tests depend on old browser TTL contract names or `touch_page_idle`.

### Broad Repository Gate

Run:

```bash
python -m unittest discover tests
```

Expected:

- Exit code `0`.
- `OK` from `unittest`.

Run:

```bash
python -m pytest tests -q
```

Expected:

- Exit code `0`.
- Confirms pytest-collected tests also pass.

### Syntax and Residual Process Check

Run:

```bash
python -m py_compile tmp/im_reply_console.py
```

Expected: exit code `0`.

Run:

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch|fake_codex|chrome-devtools|runtime_broker|app_server' || true
```

Expected:

- No unexplained test-created process remains.
- Any existing user/runtime process is identified as pre-existing or outside this merge verification.

## Acceptance Checklist

- [ ] Local `main` contains both latest feature tips: `3607cf1` and `3af4ea4`.
- [ ] `main..fea-daemon` and `main..fea-tool` are empty or contain only commits intentionally created after the merge plan.
- [ ] External IM live contract exposes one client credential: `connection_key`.
- [ ] Browser page lifecycle keeps refreshed pending schedules pending, ignores stale due triggers, and locks page idle state mutations.
- [ ] Superseded merge docs are removed; this file is the active merge/test plan.
- [ ] Focused Python and Node gates pass.
- [ ] Broad Python verification passes.
- [ ] No conflict markers, old compatibility paths, or unexplained residual test processes remain.
- [ ] Worktree status is clean after final commits.

## Self-Review

- Spec coverage: identifies latest feature refs, plans the merge, removes stale merge docs, and defines focused plus broad verification.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation steps remain.
- Forward-only check: plan rejects old IM and browser lifecycle compatibility paths instead of preserving dual behavior.

# Merge fea-daemon and fea-tool Into Main Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion before claiming merge completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `fea-daemon` and `fea-tool` into `main` with the shortest verified path and without running unrelated full-suite tests.

**Architecture:** Keep the merge direct on `main` after confirming clean branch state. Preserve `main`'s removal of the task TUI input wrapper, take `fea-daemon`'s message service boundary, and take `fea-tool`'s browser page limit reduction. Fix only merge-result hygiene that would block focused verification.

**Tech Stack:** Git merge, Python `unittest`, Node contract test, `git diff --check`.

---

## Branch State

- `main`: `98c832557a7ee6e61bd34891d64f3bf16302b530`
- `fea-daemon`: `40d2f18e355c9479df813a4fee1066fddf1436a7`
- `fea-tool`: `e29fb0d19ea101375de5606d68e30f50a439d1cd`
- Both feature branches share base `fe3ad4dc8f50af7d334aa50228ccf8f723b693f3`.
- Prior merge preflight showed no text conflicts for `main <- fea-daemon`, `main <- fea-tool`, or `fea-daemon <-> fea-tool`.

## Files Expected to Change

- Modify: `docs/memo/2026-06-23-browser-tool-page-limit.md`
- Modify: `docs/spec/2026-06-23-browser-tool-page-limit-development-plan.md`
- Modify: `docs/spec/2026-06-23-browser-tool-page-limit-test-plan.md`
- Add: `docs/memo/2026-06-24-http-message-send-public-service.md`
- Add: `docs/spec/2026-06-24-http-message-send-public-service-development-plan.md`
- Add: `docs/spec/2026-06-24-http-message-send-public-service-phase2-prompt.md`
- Add: `docs/spec/2026-06-24-http-message-send-public-service-test-plan.md`
- Modify: `scripts/env/cdp_browser_session.py`
- Add: `scripts/env/services/__init__.py`
- Add: `scripts/env/services/messages.py`
- Modify: `scripts/env/tools/message/_impl.py`
- Modify/Add focused tests under `tests/` for message service, web management, web user actor, browser cockpit proxy, and search env tool.
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/web_management.py`
- Modify: `tools/launcher/web_user_actor.py`

## Risk Controls

- Do not reintroduce `tools/launcher/input_wrapper.py`, `tools/launcher/input_wrappers/`, or `tests/test_input_wrapper.py`; `main` intentionally removed them.
- Do not run full test discovery for this merge. Run the targeted tests that cover the touched message, web management, web user, search/browser page-gate, and UI contract surfaces.
- Use `git diff --check` against the merged result because `fea-daemon` currently introduces an extra blank line at EOF in `scripts/env/services/__init__.py`.

## Tasks

### Task 0: Commit This Plan

**Files:**
- Add: `docs/spec/2026-06-24-merge-fea-daemon-fea-tool-into-main-plan.md`

- [ ] **Step 1: Commit the plan before merging**

Run:

```bash
git add docs/spec/2026-06-24-merge-fea-daemon-fea-tool-into-main-plan.md
git commit -m "docs: plan daemon and tool branch merge"
```

Expected: `main` gains one documentation commit before any merge commits.

### Task 1: Reconfirm Merge Inputs

**Files:** none

- [ ] **Step 1: Confirm clean main**

Run: `git status --short --branch`

Expected: `main` may be ahead of `origin/main` by the plan commit, with no changed files.

- [ ] **Step 2: Confirm merge preflight**

Run:

```bash
git merge-tree --write-tree main fea-daemon
git merge-tree --write-tree main fea-tool
git merge-tree --write-tree fea-daemon fea-tool
```

Expected: each command exits `0` and prints a tree hash, with no conflict entries.

### Task 2: Merge Feature Branches

**Files:** merge result across the files listed above

- [ ] **Step 1: Merge `fea-daemon` into `main`**

Run: `git merge --no-edit fea-daemon`

Expected: merge exits `0`, adds the public message send service files, and does not create conflict markers.

- [ ] **Step 2: Merge `fea-tool` into `main`**

Run: `git merge --no-edit fea-tool`

Expected: merge exits `0`, updates browser page-limit files, and does not create conflict markers.

- [ ] **Step 3: Confirm final merge status**

Run: `git status --short --branch`

Expected: `main` is ahead of `origin/main` with no unstaged or staged changes after any hygiene fix is committed.

### Task 3: Fix Required Merge Hygiene

**Files:**
- Modify if needed: `scripts/env/services/__init__.py`

- [ ] **Step 1: Run whitespace gate**

Run: `git diff --check origin/main..HEAD`

Expected before fix may include: `scripts/env/services/__init__.py:2: new blank line at EOF.`

- [ ] **Step 2: Remove only the trailing blank line if present**

Expected final file content:

```python
"""Public runtime service boundaries."""
```

- [ ] **Step 3: Commit the hygiene fix if the file changed after merges**

Run:

```bash
git add scripts/env/services/__init__.py
git commit -m "Fix service package whitespace"
```

Expected: a small commit that only changes `scripts/env/services/__init__.py`.

### Task 4: Focused Verification

**Files under test:**
- `scripts/env/services/messages.py`
- `scripts/env/tools/message/_impl.py`
- `tools/launcher/web_management.py`
- `tools/launcher/web_user_actor.py`
- `scripts/env/cdp_browser_session.py`
- `tools/launcher/assets/web-management/app.js`

- [ ] **Step 1: Run targeted Python tests**

Run:

```bash
python3 -m unittest \
  tests.test_message_service \
  tests.test_message_env_tool \
  tests.test_web_management \
  tests.test_web_user_actor \
  tests.test_browser_cockpit_proxy \
  tests.test_search_env_tool
```

Expected: all selected tests pass. Resource warnings from socket cleanup are acceptable only if exit code is `0` and the summary is `OK`.

- [ ] **Step 2: Run targeted UI contract test**

Run: `node tests/web_management_ui_contract.test.js`

Expected: all contract assertions print `ok`.

- [ ] **Step 3: Re-run whitespace gate**

Run: `git diff --check origin/main..HEAD`

Expected: no output and exit code `0`.

- [ ] **Step 4: Confirm no input wrapper resurrection**

Run:

```bash
git diff --name-status origin/main..HEAD | rg '(^A|^M).*input_wrapper|input_wrappers|test_input_wrapper' || true
```

Expected: no matching added or modified input-wrapper files.

### Task 5: Acceptance Summary

**Files:** none

- [ ] **Step 1: Capture final commit graph**

Run: `git log --oneline --decorate --max-count=8`

Expected: `main` contains merge commits for `fea-daemon` and `fea-tool`, plus any minimal hygiene commit if needed.

- [ ] **Step 2: Report to the user**

Include:
- merge commits created
- focused tests run and result
- whitespace gate result
- remaining risk, if any

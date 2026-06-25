# fea-tool Main Merge Implementation Plan

Date: 2026-06-26

## Goal

Merge `fea-tool` into `main` and deliver browser page lifecycle stabilization without preserving old TTL, idle-refresh rollback, or stale spec paths.

## Assessment Result

- `main` is at `e2c21be` and includes the IM/daemon work from `fea-daemon`.
- `fea-tool` is at `6f6a2c1` and implements browser page lifecycle stabilization.
- A dry merge reports one content conflict in `tests/test_buddyswitch_launcher.py`.
- The conflict is test-harness-only: `main` keeps the `bash -lc` launcher test path with explicit fake-bin PATH injection, while `fea-tool` changed the same subprocess invocation.
- No source-code merge conflicts are reported.
- `fea-tool` focused verification passes before integration:

```bash
python -m unittest \
  tests.test_browser_cockpit_launcher \
  tests.test_buddyswitch_launcher \
  tests.test_browser_cockpit_proxy \
  tests.test_search_env_tool \
  tests.test_cdp_browser_session \
  tests.test_browser_page_expired_handler \
  tests.test_daemon_core \
  tests.test_daemon_trigger_router \
  tests.test_daemon_mailbox
```

Expected result: `Ran 349 tests ... OK`.

## Implementation Tasks

### Task 1: Merge Branch State Into Main

- [ ] Start from clean `main`.
- [ ] Fetch remotes and confirm `main` and `origin/main` match.
- [ ] Merge `fea-tool` with no auto-commit.
- [ ] Resolve `tests/test_buddyswitch_launcher.py` by preserving `main`'s fake-bin PATH injection and `fea-tool`'s browser lifecycle registration assertions.
- [ ] Stage the resolved merge.

Validation:

```bash
git status --short
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- tests/test_buddyswitch_launcher.py
```

Expected result: no conflict-marker hits.

### Task 2: Keep Browser Lifecycle Work Single-Path

- [ ] Keep the deleted `docs/spec/browser-page-idle-lifecycle-*` files deleted from active specs.
- [ ] Keep `docs/spec/browser-page-lifecycle-systemic-stabilization-plan.md` as the browser lifecycle feature plan.
- [ ] Do not add compatibility wrappers for `touch_page_idle`, old TTL terms, or old success-with-warning behavior.
- [ ] Confirm active code and tests have no old lifecycle terms.

Validation:

```bash
find docs/spec -maxdepth 1 -type f -name 'browser-page-idle-lifecycle-*' -print
rg -n 'register_browser_page_ttl|BROWSER_PAGE_TTL_SECONDS|ttl_seconds|ttl_registered|expiry_policy|Browser page TTL|touch_page_idle' scripts tools tests
```

Expected result: both commands print nothing.

### Task 3: Verify Focused Product Behavior

- [ ] Run the focused browser lifecycle and daemon tests listed in `docs/spec/fea-tool-main-merge-test-plan.md`.
- [ ] If a focused failure appears, add or adjust the smallest regression test first unless the failure is purely from merge conflict resolution.
- [ ] Fix root cause directly in the owning module.
- [ ] Re-run the focused test until green.

Expected result: focused unittest command exits `0`.

### Task 4: Verify Repository Acceptance Surface

- [ ] Run broad Python verification.
- [ ] Run JavaScript UI contract verification.
- [ ] Run syntax/merge hygiene checks.
- [ ] Inspect test-run residual processes.

Commands are specified in `docs/spec/fea-tool-main-merge-test-plan.md`.

Expected result: all verification commands exit `0`; process inspection shows no unexplained test leftovers.

### Task 5: Commit And Push Main

- [ ] Confirm staged diff matches the browser lifecycle merge, plan docs, and no unrelated cleanup.
- [ ] Commit the merge on `main`.
- [ ] Push `main` to `origin/main`.
- [ ] Confirm local `main` and `origin/main` point to the same commit.

Validation:

```bash
git status --short --branch
git rev-parse main origin/main
```

Expected result: clean worktree and matching commit hashes.

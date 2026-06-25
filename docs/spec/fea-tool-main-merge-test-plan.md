# fea-tool Main Merge Test Plan

Date: 2026-06-26

## Expected Product Result

After `fea-tool` is merged into `main`, browser pages opened through BuddySwitch are managed lifecycle resources: a new page is either registered with browser idle state and a keyed daemon expiry schedule, or it is closed and the caller receives a failure. The daemon remains generic, and active code exposes no old TTL or `touch_page_idle` path.

## Focused Verification

Run after merge conflict resolution:

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

Expected result:

- Exit code `0`.
- `OK` from unittest.
- Any `ResourceWarning` output is recorded but does not count as behavioral failure unless it leaves a residual process or file lock.

## No-Residual Checks

Run after focused verification:

```bash
find docs/spec -maxdepth 1 -type f -name 'browser-page-idle-lifecycle-*' -print
```

Expected result: no output.

```bash
rg -n 'register_browser_page_ttl|BROWSER_PAGE_TTL_SECONDS|ttl_seconds|ttl_registered|expiry_policy|Browser page TTL|touch_page_idle' scripts tools tests
```

Expected result: no output and exit code `1`.

```bash
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)' -- .
```

Expected result: no merge conflict markers.

## Broad Verification

Run after focused verification passes:

```bash
python -m unittest discover tests
```

Expected result: exit code `0` and `OK`.

```bash
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Expected result: exit code `0`.

## Acceptance Inspection

Run after broad verification:

```bash
ps -axo pid,ppid,pgid,command | rg 'buddyswitch|fake_codex|chrome-devtools|runtime_broker|app_server' || true
```

Expected result:

- No unexplained process from the test run remains.
- Existing user/runtime processes may appear, but must be identified as outside this merge verification before delivery.

## Push Verification

Run after pushing `main`:

```bash
git status --short --branch
git rev-parse main origin/main
```

Expected result:

- `git status` reports `## main...origin/main` with no changed files.
- `main` and `origin/main` resolve to the same commit.

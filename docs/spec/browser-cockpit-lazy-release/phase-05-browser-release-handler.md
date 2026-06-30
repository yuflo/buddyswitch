# Phase 05 Browser Release Handler

## Phase Objective

Implement the `browser.cockpit.release` handler and locked launcher release command. A stale release trigger must be harmless; an eligible release must stop the cockpit upstream process group, stop actor-owned Chrome, clear page-idle state, and clear `browser_port` without killing foreign endpoints.

This phase covers memo Task 6.

## Exact Source Files To Modify

- `tools/launcher/browser_release_handler.py`
- `tools/launcher/browser_cockpit.sh`
- `tools/launcher/env.sh`
- `buddyswitch-codex`
- `tests/test_browser_page_expired_handler.py`
- `tests/test_buddyswitch_launcher.py`

## Tests To Add Or Update

- Release handler unit tests:
  - parent activity running -> handled/no launcher call;
  - page-idle targets non-empty -> handled/no launcher call;
  - missing `browser_port` -> handled/no launcher call;
  - CDP reports real user page -> handled/no launcher call;
  - empty page-idle state and no real page -> calls `env browser release --instance <actor_id>`.
- Launcher tests:
  - owned release stops upstream PGID and Chrome PID, removes markers, removes page-idle state, and clears `browser_port`;
  - foreign endpoint release clears this actor's stale `browser_port` without killing the foreign listener or removing the foreign marker.

## Implementation Steps

1. Add failing release handler unit tests in `tests/test_browser_page_expired_handler.py`.
2. Add failing launcher release tests in `tests/test_buddyswitch_launcher.py`.
3. Implement release handler rechecks:
   - validate target actor;
   - read fresh `instance.json`;
   - noop when parent turn is running;
   - noop when page-idle `targets` is non-empty;
   - noop when `browser_port` is missing;
   - noop when CDP has a real non-internal user page;
   - call `buddyswitch-codex env browser release --instance <actor_id>` otherwise.
4. Add launcher shell cleanup helpers:
   - terminate upstream PGID marker, falling back to PID marker;
   - stop actor Chrome marker;
   - clear `runtime/browser/page_idle.json` and lock;
   - clear `browser_port`;
   - clear stale foreign/unknown recorded port without killing listeners.
5. Add `env browser release --instance <actor-id>` and locked `__locked-browser-release`.
6. Run focused tests, syntax checks, residue scan, and process cleanup check.

## Test Plan

Red checks before implementation:

```bash
python3 -m unittest tests.test_browser_page_expired_handler.BrowserReleaseHandlerTests
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_release_cleans_owned_runtime_state
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_release_clears_foreign_endpoint_port_without_killing_foreign
```

Expected before implementation: fail because the release handler still returns not implemented and `env browser release` does not exist.

Observed red results:

- `BrowserReleaseHandlerTests` failed because the handler returned `browser cockpit release handler is not implemented`;
- owned and foreign launcher release tests failed with `Unknown env browser command: release`.

Green checks after implementation:

```bash
python3 -m unittest tests.test_browser_page_expired_handler tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_release_cleans_owned_runtime_state tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_release_clears_foreign_endpoint_port_without_killing_foreign
bash -n buddyswitch-codex tools/launcher/browser_cockpit.sh tools/launcher/env.sh
python3 -m py_compile tools/launcher/browser_release_handler.py
git diff --check
```

Observed green results:

- `tests.test_browser_page_expired_handler` ran 22 tests and passed.
- The two focused launcher release tests passed.
- `tests.test_browser_cockpit_launcher` ran 13 tests and passed.
- `bash -n buddyswitch-codex tools/launcher/browser_cockpit.sh tools/launcher/env.sh` passed.
- `python3 -m py_compile tools/launcher/browser_release_handler.py tools/launcher/browser_page_expired_handler.py` passed.
- `git diff --check` produced no output.
- A full `tests.test_buddyswitch_launcher` run exposed two stale daemon handler registration expectations; both focused failures passed after updating the expected `browser_cockpit_release` registration.

Process cleanup check:

```bash
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|browser_release_handler.py|cockpit-upstream|sleep 60" || true
```

Observed result: only the process-check command and `rg` matched.

## Residue Search Terms

```bash
rg -n "not implemented|browser release|cockpit-upstream|env browser release|__locked-browser-release|browser_port.*None" \
  tools/launcher/browser_release_handler.py tools/launcher/browser_cockpit.sh tools/launcher/env.sh buddyswitch-codex tests/test_browser_page_expired_handler.py tests/test_buddyswitch_launcher.py
```

Accepted hits after this phase:

- release command help/dispatch;
- release handler and tests;
- upstream marker cleanup;
- assertions that `browser_port` is cleared.

Observed residue result: accepted hits only; no `not implemented` release handler residue remains.

## Phase Acceptance Checklist

- [x] Release handler noops when parent activity is running.
- [x] Release handler noops when tracked page-idle targets remain.
- [x] Release handler noops when no browser port is recorded.
- [x] Release handler noops when CDP has a real user page.
- [x] Release handler calls locked launcher release only after rechecks pass.
- [x] Launcher release stops upstream process group marker.
- [x] Launcher release stops actor-owned Chrome marker.
- [x] Launcher release removes page-idle state.
- [x] Launcher release clears `browser_port`.
- [x] Foreign endpoint is not killed.
- [x] Focused release tests pass.
- [x] Syntax, residue, and process cleanup checks pass.

## Plan Self-Review

- Memo coverage: maps to Task 6 release noops, release cleanup, fresh reads, and launcher release entrypoint.
- Boundary check: CDP/page-idle decisions stay in the browser release handler; process cleanup stays in browser launcher shell.
- TDD check: handler and launcher tests are added and observed red before production changes.
- Rebuild-forward check: no compatibility flag for old eager browser lifetime.

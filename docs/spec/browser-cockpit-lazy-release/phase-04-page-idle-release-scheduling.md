# Phase 04 Page Idle Release Scheduling

## Phase Objective

When browser page TTL expiry removes the final tracked page, schedule a keyed `browser.cockpit.release` trigger after 10 seconds. Also remove tracked page-idle residue when the Chrome endpoint is stale or unreachable, and make page expiry read the current `browser_port` from `instance.json` instead of the daemon's cached startup payload.

This phase covers memo Task 5 and the fresh-read part of memo finding 7. It does not stop Chrome or upstream MCP; that is Phase 5.

## Exact Source Files To Modify

- `scripts/env/cdp_browser_lifecycle.py`
- `tools/launcher/browser_page_expired_handler.py`
- Create `tools/launcher/browser_release_handler.py` as the browser-owned handler target for the new trigger.
- `tools/launcher/browser_inbound.py`
- `tests/test_cdp_browser_session.py`
- `tests/test_browser_page_expired_handler.py`
- `tests/test_daemon_trigger_router.py`
- `tests/test_instance_daemon_entrypoint.py`

## Tests To Add Or Update

- Add lifecycle helper test proving `schedule_browser_cockpit_release` emits:
  - `delay_seconds=10`
  - `trigger_type="browser.cockpit.release"`
  - `payload={"reason": "page_idle_empty"}`
  - `source_context={"owner": "browser"}`
  - `schedule_key="browser.cockpit.release"`
- Add page-expiry test proving closing the only tracked target schedules release after the target is forgotten.
- Add page-expiry test proving stale endpoint errors forget the target and schedule release when no tracked targets remain.
- Add page-expiry test proving the handler uses a fresh `instance.json` browser port when cached `context.instance_payload["browser_port"]` is missing.
- Update inbound/default handler tests to include `browser.cockpit.release`.

## Implementation Steps

1. Add failing lifecycle helper test in `tests/test_cdp_browser_session.py`.
2. Add failing page-expiry tests in `tests/test_browser_page_expired_handler.py`.
3. Add failing inbound/default handler expectations in `tests/test_browser_page_expired_handler.py` and `tests/test_instance_daemon_entrypoint.py`.
4. Implement lifecycle constants and `schedule_browser_cockpit_release`.
5. Refactor `BrowserPageExpiredHandler`:
   - read current `browser_port` from `context.instance_json`;
   - after `forget_page_idle_target`, schedule release if the remaining `targets` map is empty;
   - on stale browser endpoint errors, forget the target and schedule release if empty.
6. Add `browser_release_handler.py` with a minimal browser-owned unified handler for `browser.cockpit.release`. Full release behavior is Phase 5.
7. Register the release inbound event in `browser_inbound.py`.
8. Run focused tests, syntax checks, residue scan, and process cleanup check.

## Test Plan

Red checks before implementation:

```bash
python3 -m unittest tests.test_cdp_browser_session.CdpBrowserLifecycleTests.test_schedule_browser_cockpit_release_uses_keyed_browser_release_trigger
python3 -m unittest tests.test_browser_page_expired_handler.BrowserPageExpiredHandlerTests.test_final_tracked_page_schedules_release_after_close
python3 -m unittest tests.test_browser_page_expired_handler.BrowserPageExpiredHandlerTests.test_stale_endpoint_forgets_target_and_schedules_release
python3 -m unittest tests.test_browser_page_expired_handler.BrowserPageExpiredHandlerTests.test_expiry_reads_fresh_browser_port_from_instance_json
python3 -m unittest tests.test_instance_daemon_entrypoint.InstanceDaemonEntrypointTests.test_default_daemon_handlers_are_built_through_notification_center
```

Expected before implementation: fail because release scheduling helper, release handler registration, stale cleanup, and fresh instance reads do not exist.

Observed red results:

- lifecycle helper test errored with `AttributeError` because `schedule_browser_cockpit_release` did not exist;
- final-close release test failed because no release schedule call was made;
- stale endpoint test failed because `target-idle-1` remained in `page_idle.json`;
- fresh-port test failed because no close call happened when cached `browser_port` was `None`;
- inbound/default handler tests failed because `browser.cockpit.release` and `BrowserReleaseHandler` were not registered.

Green checks after implementation:

```bash
python3 -m unittest tests.test_cdp_browser_session tests.test_browser_page_expired_handler tests.test_daemon_trigger_router tests.test_instance_daemon_entrypoint
python3 -m py_compile scripts/env/cdp_browser_lifecycle.py tools/launcher/browser_page_expired_handler.py tools/launcher/browser_release_handler.py tools/launcher/browser_inbound.py
git diff --check
```

Observed green results: 51 focused tests passed; Python syntax checks passed; `git diff --check` produced no output.

Process cleanup check:

```bash
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|browser_page_expired_handler.py|browser_release_handler.py" || true
```

Observed result: only the process-check command and `rg` matched.

## Residue Search Terms

```bash
rg -n "browser\\.cockpit\\.release|instance_payload.*browser_port|page_idle_empty|forget_page_idle_target" \
  scripts/env/cdp_browser_lifecycle.py tools/launcher/browser_page_expired_handler.py tools/launcher/browser_inbound.py tools/launcher/browser_release_handler.py tests/test_cdp_browser_session.py tests/test_browser_page_expired_handler.py tests/test_instance_daemon_entrypoint.py
```

Accepted hits after this phase:

- release trigger constants, helper, tests, inbound registration, and handler stub;
- `forget_page_idle_target` in page-expiry cleanup and tests;
- no live `instance_payload["browser_port"]` use in `browser_page_expired_handler.py`.

Observed residue result: accepted hits only; the only `instance_payload` hits are test fixtures.

## Phase Acceptance Checklist

- [x] Release scheduling helper exists and uses the keyed 10-second browser release trigger.
- [x] Final tracked page close schedules browser release.
- [x] Final tracked target already gone schedules browser release.
- [x] Stale endpoint errors forget the target and schedule release when empty.
- [x] Page-expiry handler reads fresh `instance.json` for `browser_port`.
- [x] Browser inbound registers `browser.cockpit.release`.
- [x] Default daemon handler list includes the release handler.
- [x] Focused daemon lifecycle tests pass.
- [x] Syntax and diff checks pass.
- [x] Phase residue scan has only accepted hits.

## Plan Self-Review

- Memo coverage: maps to Task 5 and the daemon fresh-read requirement from finding 7.
- Boundary check: all behavior remains in browser-owned lifecycle, handler, and inbound files.
- TDD check: tests are added and run red before production changes.
- Rebuild-forward check: no compatibility branch for cached `browser_port`; the handler switches to fresh state reads.

# Phase 08 End-To-End Acceptance Smoke

## Phase Objective

Add a focused end-to-end smoke proving the user-visible lazy browser runtime loop:

```text
actor browser call -> lazy runtime starts -> page opens and registers TTL -> TTL closes final page -> release stops runtime -> next browser call starts runtime again
```

This phase covers memo Task 9.

## Exact Source Files Modified

- `tests/test_browser_lazy_release_integration.py`

## Test Shape

The smoke uses real BuddySwitch launcher/proxy/handler code with fake expensive runtime pieces:

- fake Chrome CDP server process started by the browser ensure script;
- fake upstream Chrome DevTools MCP process started by the cockpit proxy;
- real `chrome_devtools_cockpit_proxy.py` stdio process kept alive across release;
- real `search.open_browser` dispatch for page creation and page-idle state;
- real `BrowserPageExpiredHandler` for final target close and release scheduling;
- real `BrowserReleaseHandler` invoking `buddyswitch-codex env browser release`;
- real launcher release cleanup for upstream markers, Chrome marker, page idle files, and `browser_port`.

The daemon schedule client is stubbed only at the trigger enqueue boundary. The lifecycle state files are still written by the real lifecycle helper.

## Implementation Steps

1. Add executable fake runtime helpers inside the integration test:
   - fake CDP HTTP/WebSocket server;
   - fake ensure script that starts fake Chrome and writes `browser_port`;
   - fake upstream MCP server that stays alive until release kills its process group.
2. Start the real cockpit proxy and send a `tools/call`.
3. Assert first browser call:
   - invokes ensure;
   - starts fake Chrome;
   - starts upstream MCP;
   - writes upstream PID/PGID markers.
4. Dispatch `search.open_browser` against the same instance.
5. Assert page open and TTL registration:
   - `browser.page.expired` schedule is requested;
   - `runtime/browser/page_idle.json` tracks `target-1`.
6. Run page expiry handler and assert:
   - fake CDP target closes;
   - page idle state is empty;
   - `browser.cockpit.release` keyed schedule is requested.
7. Run release handler and assert:
   - launcher release returns handled;
   - `browser_port` is cleared;
   - upstream PID/PGID markers are removed;
   - page idle files are removed;
   - fake Chrome marker is removed;
   - fake CDP port closes.
8. Send a second proxy `tools/call` and assert:
   - fake Chrome restarts;
   - upstream MCP restarts;
   - tool response succeeds.
9. Run a final launcher release for test cleanup and assert the fake CDP port closes again.

## Test Plan

Focused smoke:

```bash
python3 -m unittest tests.test_browser_lazy_release_integration
```

Observed implementation-loop failures before green:

- first run failed at the Task Sys active-task gate, so the smoke now seeds a temp-runtime Task Sys task;
- second run failed because TTL registration attempted to contact a real daemon mailbox, so the smoke now stubs only `daemon_client.schedule_trigger` and keeps real lifecycle state writes.

Observed green result:

- `tests.test_browser_lazy_release_integration` ran 1 test and passed.

## Phase Acceptance Checklist

- [x] Smoke proves first actor browser call lazily starts fake Chrome.
- [x] Smoke proves first actor browser call starts upstream MCP without exiting the stable proxy.
- [x] Smoke proves `search.open_browser` opens a page and registers TTL state.
- [x] Smoke proves final page TTL expiry closes the page and schedules release.
- [x] Smoke proves release handler invokes real launcher release.
- [x] Smoke proves release clears `browser_port`, upstream markers, Chrome marker, and page idle files.
- [x] Smoke proves the fake CDP endpoint stops after release.
- [x] Smoke proves the next browser call restarts fake Chrome and upstream MCP.
- [x] Focused smoke verification passes.

## Plan Self-Review

- Memo coverage: maps to Task 9 full-loop smoke and residual process/marker checks.
- Boundary check: no generic resource manager or new runtime abstraction was added.
- Verification check: the smoke uses process markers and a real port, not only mocked function calls.

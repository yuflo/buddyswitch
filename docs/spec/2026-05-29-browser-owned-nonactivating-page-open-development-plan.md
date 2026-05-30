# BuddySwitch-Owned Non-Activating Page Open Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace BuddySwitch-owned direct CDP `/json/new` page-open paths with non-activating CDP `Target.createTarget` calls.

**Architecture:** Add one small Python helper under `tools/launcher` that talks to the browser websocket and creates a background target. Use that helper from the search tool and launcher ready-page repair path. Keep the existing `chrome-devtools-cockpit` proxy as the MCP protection layer.

**Tech Stack:** Python 3 stdlib HTTP, socket, websocket framing, subprocess; Bash launcher; `unittest` fake CDP servers and fake command capture.

---

## File Structure

- Create `tools/launcher/cdp_background_page.py`
  - Fetches `/json/version`.
  - Reads `webSocketDebuggerUrl`.
  - Opens a websocket.
  - Sends JSON-RPC `Target.createTarget` with `background: true`.
  - Exits non-zero with a concise error if the endpoint cannot create the target.

- Modify `scripts/env/tools/search/_impl.py`
  - Replace `_open_browser_page` direct HTTP `/json/new` call with the helper.
  - Preserve the public `search.open_browser` result and rejection contracts.

- Modify `tools/launcher/browser_cockpit.sh`
  - Add `BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL`.
  - Replace `buddyswitch_browser_create_blank_page` `/json/new?about:blank` curl with the helper command.
  - Leave existing usable-page checks in place so no page is created when `/json/list` already has a usable page.

- Modify tests:
  - `tests/test_search_env_tool.py`
  - `tests/test_browser_cockpit_launcher.py`
  - `tests/test_buddyswitch_launcher.py`

## Task 1: Search RED Tests

- [ ] **Step 1: Rewrite the search fake CDP server**

Add websocket support to `tests/test_search_env_tool.py` so it can return `/json/version` with a `webSocketDebuggerUrl`, receive one websocket JSON-RPC request, record it, and return either success or error.

- [ ] **Step 2: Change the main open-browser assertion**

Rename `test_search_open_browser_opens_cdp_page_with_encoded_target_url` to `test_search_open_browser_creates_background_cdp_target` and assert:

```python
self.assertFalse(any(request["path"] == "/json/new" for request in requests))
self.assertEqual(rpc["method"], "Target.createTarget")
self.assertEqual(rpc["params"]["url"], target_url)
self.assertIs(rpc["params"]["background"], True)
```

- [ ] **Step 3: Run the focused test and confirm RED**

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
```

Expected: fail because `_open_browser_page` still calls `/json/new`.

## Task 2: Non-Activating CDP Helper

- [ ] **Step 1: Create `tools/launcher/cdp_background_page.py`**

Implement a minimal stdlib websocket client:

```text
GET <browser-url>/json/version
require webSocketDebuggerUrl
websocket upgrade
send {"id":1,"method":"Target.createTarget","params":{"url":url,"background":true}}
require result.targetId
```

Use masked client frames, unmasked server frames, bounded timeouts, and no persistent background process.

- [ ] **Step 2: Use the helper in `scripts/env/tools/search/_impl.py`**

Build the helper path from `env_profiles.ROOT / "tools/launcher/cdp_background_page.py"` and run:

```bash
python3 <helper> --browser-url <endpoint> --url <target_url>
```

Return `(True, None)` on exit 0 and `(False, stderr-or-stdout)` on non-zero.

- [ ] **Step 3: Run search GREEN checks**

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
```

Expected: all pass.

## Task 3: Launcher RED Tests

- [ ] **Step 1: Add fake background opener command helpers**

In `tests/test_browser_cockpit_launcher.py` and `tests/test_buddyswitch_launcher.py`, add a fake executable that records:

```json
{"method":"CDP","path":"Target.createTarget","params":{"url":"about:blank","background":true}}
```

When allowed, it updates the fake CDP state so `/json/list` returns an `about:blank` page.

- [ ] **Step 2: Update launcher ready-page tests**

Rename expectations from PUT `/json/new?about:blank` to background target creation. Preserve the existing failure semantics when the endpoint remains unusable.

- [ ] **Step 3: Run focused launcher tests and confirm RED**

```bash
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_intro_only_with_background_target -v
```

Expected: fail because `browser_cockpit.sh` still uses `/json/new?about:blank`.

## Task 4: Launcher Implementation

- [ ] **Step 1: Add the helper default**

In `buddyswitch_browser_init_defaults`, export:

```bash
BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL="${BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL:-${BUDDYSWITCH_REPO_ROOT}/tools/launcher/cdp_background_page.py}"
```

- [ ] **Step 2: Replace ready-page creation**

Change `buddyswitch_browser_create_blank_page` to:

```bash
python3 "${BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL}" \
  --browser-url "$(buddyswitch_browser_url)" \
  --url about:blank >/dev/null
```

- [ ] **Step 3: Run launcher GREEN checks**

```bash
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_rejects_endpoint_only_when_background_ready_page_creation_fails -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_uses_bounded_timeouts_for_cdp_probes -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_intro_only_with_background_target -v
```

Expected: all pass.

## Task 5: Broader Launcher Alignment

- [ ] **Step 1: Update `tests/test_buddyswitch_launcher.py`**

Update the required-buddy intro-only repair and endpoint-only rejection tests to assert background target creation instead of `/json/new?about:blank`.

- [ ] **Step 2: Run targeted broader checks**

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
```

Expected: both pass.

## Task 6: Final Verification and Review

- [ ] **Step 1: Run focused suites**

```bash
python3 -m unittest tests.test_search_env_tool -v
python3 -m unittest tests.test_browser_cockpit_proxy -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

- [ ] **Step 2: Check residual processes**

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

- [ ] **Step 3: Run broader launcher suite**

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

- [ ] **Step 4: Source-shape review**

Run:

```bash
rg -n '/json/new|Target\.activateTarget|Page\.bringToFront' scripts/env/tools/search tools/launcher tests/test_search_env_tool.py tests/test_browser_cockpit_launcher.py tests/test_buddyswitch_launcher.py
```

Expected: no production `/json/new` in `scripts/env/tools/search/_impl.py` or `tools/launcher/browser_cockpit.sh`; focus-blocking methods appear only in the existing proxy and tests.

## Plan Review

This plan targets the two real漏点 from the memo and does not add a generic browser engine, permission system, or runtime-layer wrapper. The helper is concrete and local: one CDP browser target creation operation used by two BuddySwitch-owned call sites. The tests verify behavior from the functional requirement outward instead of matching a convenient implementation string.

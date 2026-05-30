# Search Open Browser Runtime Helper Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or the local TDD loop to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the CDP background target helper into the runtime sparse surface so `search.open-browser` works inside product runtime workspaces without depending on `tools/launcher`.

**Architecture:** Keep one concrete helper script at `scripts/env/cdp_background_page.py`. The runtime search tool invokes that helper relative to `env_profiles.ROOT`, while the launcher invokes the same helper through `${BUDDYSWITCH_REPO_ROOT}`. Delete the old `tools/launcher/cdp_background_page.py` path instead of maintaining dual helper locations.

**Tech Stack:** Python 3 stdlib HTTP/socket/websocket framing, Bash launcher defaults, `unittest` fake CDP servers and fake helper subprocesses.

---

## File Structure

- Create `scripts/env/cdp_background_page.py`
  - Owns the small CDP browser websocket operation.
  - Fetches `/json/version`.
  - Requires `webSocketDebuggerUrl`.
  - Sends `Target.createTarget` with `background: true`.
  - Exits non-zero with a concise stderr reason on failure.

- Modify `scripts/env/tools/search/_impl.py`
  - Change `_open_browser_page` helper path from `tools/launcher/cdp_background_page.py` to `scripts/env/cdp_background_page.py`.
  - Preserve the existing public search tool result and rejection contracts.

- Modify `tools/launcher/browser_cockpit.sh`
  - Change `BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL` default from `${BUDDYSWITCH_REPO_ROOT}/tools/launcher/cdp_background_page.py` to `${BUDDYSWITCH_REPO_ROOT}/scripts/env/cdp_background_page.py`.
  - Keep the environment override so tests and local debugging can still inject a fake helper.

- Delete `tools/launcher/cdp_background_page.py`
  - No wrapper.
  - No compatibility path.
  - No second implementation.

- Modify tests:
  - `tests/test_search_env_tool.py`
  - `tests/test_browser_cockpit_launcher.py`
  - `tests/test_buddyswitch_launcher.py`

## Task 1: Source Boundary RED Tests

- [ ] **Step 1: Strengthen search source-shape test**

In `tests/test_search_env_tool.py`, update `test_search_source_has_no_direct_json_new_page_open` so it asserts:

```python
text = (ROOT / "scripts" / "env" / "tools" / "search" / "_impl.py").read_text(encoding="utf-8")
self.assertNotIn("/json/new", text)
self.assertNotIn('"tools"', text)
self.assertNotIn('"launcher"', text)
self.assertNotIn("tools" + "/launcher", text)
self.assertIn('"scripts"', text)
self.assertIn('"env"', text)
self.assertIn("cdp_background_page.py", text)
self.assertTrue((ROOT / "scripts" / "env" / "cdp_background_page.py").exists())
self.assertFalse((ROOT / "tools" / "launcher" / "cdp_background_page.py").exists())
```

- [ ] **Step 2: Strengthen launcher source-shape test**

In `tests/test_browser_cockpit_launcher.py`, update `test_browser_launcher_source_is_instance_only` so it asserts:

```python
self.assertIn("scripts/env/cdp_background_page.py", text)
self.assertNotIn("tools" + "/launcher/cdp_background_page.py", text)
self.assertIn("chrome_devtools_cockpit_proxy.py", text)
self.assertNotIn("/json/new?about:blank", text)
```

- [ ] **Step 3: Add runtime sparse boundary regression test**

In `tests/test_buddyswitch_launcher.py`, add:

```python
def test_search_open_browser_helper_stays_inside_runtime_sparse_surface(self) -> None:
    workspace_text = (ROOT / "tools" / "launcher" / "workspace.sh").read_text(encoding="utf-8")
    search_text = (ROOT / "scripts" / "env" / "tools" / "search" / "_impl.py").read_text(encoding="utf-8")
    self.assertIn("scripts/env/", workspace_text)
    self.assertIn("tools", workspace_text)
    self.assertIn('"scripts"', search_text)
    self.assertIn('"env"', search_text)
    self.assertIn("cdp_background_page.py", search_text)
    self.assertNotIn("tools/launcher", search_text)
    self.assertTrue((ROOT / "scripts" / "env" / "cdp_background_page.py").exists())
    self.assertFalse((ROOT / "tools" / "launcher" / "cdp_background_page.py").exists())
```

- [ ] **Step 4: Verify RED**

Run:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_launcher_source_is_instance_only -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_search_open_browser_helper_stays_inside_runtime_sparse_surface -v
```

Expected: each fails because the helper currently lives under `tools/launcher`.

## Task 2: Move the Helper

- [ ] **Step 1: Create runtime helper file**

Copy the current helper implementation from `tools/launcher/cdp_background_page.py` to `scripts/env/cdp_background_page.py`. Keep its public CLI:

```bash
python3 scripts/env/cdp_background_page.py --browser-url http://127.0.0.1:9222 --url about:blank
```

- [ ] **Step 2: Update search helper path**

In `scripts/env/tools/search/_impl.py`, change:

```python
helper = env_profiles.ROOT / "tools" / "launcher" / "cdp_background_page.py"
```

to:

```python
helper = env_profiles.ROOT / "scripts" / "env" / "cdp_background_page.py"
```

- [ ] **Step 3: Update launcher helper path**

In `tools/launcher/browser_cockpit.sh`, change:

```bash
BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL="${BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL:-${BUDDYSWITCH_REPO_ROOT}/tools/launcher/cdp_background_page.py}"
```

to:

```bash
BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL="${BUDDYSWITCH_BROWSER_BACKGROUND_PAGE_TOOL:-${BUDDYSWITCH_REPO_ROOT}/scripts/env/cdp_background_page.py}"
```

- [ ] **Step 4: Remove old launcher helper**

Delete:

```text
tools/launcher/cdp_background_page.py
```

Do not leave a wrapper.

- [ ] **Step 5: Verify focused GREEN**

Run:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
python3 -m unittest tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_launcher_source_is_instance_only -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_search_open_browser_helper_stays_inside_runtime_sparse_surface -v
```

Expected: all pass.

## Task 3: Related Behavior Verification

- [ ] **Step 1: Run search suite**

```bash
python3 -m unittest tests.test_search_env_tool -v
```

- [ ] **Step 2: Run launcher source and ready-page suite**

```bash
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

- [ ] **Step 3: Run related runtime sparse and launcher required-buddy tests**

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_instance_start_execution_workspace_is_sparse_runtime_surface -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
```

Expected: all pass.

## Task 4: Resource and Source Review

- [ ] **Step 1: Run residual process check**

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

Expected: no leaked BuddySwitch-owned browser/proxy/broker/app-server processes. Ignore the `pgrep` command itself if the platform echoes it.

- [ ] **Step 2: Run source boundary review**

```bash
rg -n 'tools/launcher/cdp_background_page|/json/new|Target\.activateTarget|Page\.bringToFront' scripts/env tools/launcher
rg -n 'tools/launcher/cdp_background_page' tests/test_search_env_tool.py tests/test_browser_cockpit_launcher.py tests/test_buddyswitch_launcher.py || true
```

Expected:

- No production `tools/launcher/cdp_background_page` references.
- Test references to the retired helper path are split or absent so source review output stays easy to read.
- No production `/json/new` page-open path in `scripts/env/tools/search/_impl.py` or `tools/launcher/browser_cockpit.sh`.
- Focus-activating CDP methods appear only where unrelated existing proxy/test coverage requires them.

- [ ] **Step 3: Inspect git diff**

```bash
git diff -- docs/spec scripts/env tools/launcher tests
git status --short
```

Expected: only the intended docs, helper move, search path, launcher default, and tests changed.

## Plan Review

This plan fixes the actual runtime sparse workspace failure rather than adding `tools/launcher` to the sparse projection or preserving a compatibility wrapper. The helper is concrete, already behavior-tested, and belongs to `scripts/env` because `search.open-browser` executes from that runtime surface.

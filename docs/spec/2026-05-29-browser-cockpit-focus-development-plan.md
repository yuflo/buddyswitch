# Browser Cockpit Focus Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route `chrome-devtools-cockpit` through a BuddySwitch-owned proxy that preserves Chrome DevTools MCP capabilities while preventing default page-focus activation.

**Architecture:** Keep the public MCP server name unchanged. Replace launcher registration so Codex starts a BuddySwitch Python proxy; the proxy starts the pinned upstream `chrome-devtools-mcp` process, forwards JSON-RPC over stdio, and mutates only focus-sensitive tool calls.

**Tech Stack:** Bash launcher, Python 3 stdlib subprocess/threading/json, unittest fake subprocess tests.

---

## File Structure

- Create `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - Process-level MCP stdio proxy.
  - Starts upstream command `npx chrome-devtools-mcp@1.1.1` by default.
  - Forwards JSON-RPC messages between Codex and upstream.
  - Intercepts `tools/call` for `new_page` and `select_page`.
  - Patches `tools/list` response descriptions.

- Modify `tools/launcher/browser_cockpit.sh`
  - Add default upstream package version.
  - Register `chrome-devtools-cockpit` as `python3 <proxy> --browser-url=<url>`.
  - Detect stale raw MCP registration even when browser URL matches.

- Create `tests/test_browser_cockpit_proxy.py`
  - Unit-level tests for proxy JSON-RPC mutation and lifecycle.

- Modify `tests/test_browser_cockpit_launcher.py`
  - Assert launcher registers the proxy, not raw `chrome-devtools-mcp`.
  - Assert stale raw registration is repaired.

- Modify selected assertions in `tests/test_buddyswitch_launcher.py`
  - Keep broad launcher behavior expectations aligned with proxy registration.

## Task 1: Proxy RED Tests

**Files:**
- Create: `tests/test_browser_cockpit_proxy.py`

- [ ] **Step 1: Write failing proxy tests**

Create tests that start the proxy with a fake upstream script and verify the upstream receives rewritten `tools/call` arguments.

- [ ] **Step 2: Run focused proxy tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy -v
```

Expected: import or subprocess failure because `tools/launcher/chrome_devtools_cockpit_proxy.py` does not exist yet.

## Task 2: Proxy Implementation

**Files:**
- Create: `tools/launcher/chrome_devtools_cockpit_proxy.py`

- [ ] **Step 1: Implement the proxy command**

Implementation requirements:

- Accept `--browser-url` and pass it to upstream.
- Accept optional test-only `--upstream-command`.
- Default upstream command must be `npx chrome-devtools-mcp@1.1.1`.
- Read newline-delimited JSON-RPC from stdin.
- Launch upstream with stdin/stdout pipes and stderr inherited.
- Forward unknown messages unchanged.
- For `tools/call` with `name == "new_page"`:
  - If `arguments.isolatedContext` exists, return a tool error locally and do not forward.
  - Otherwise set `arguments.background = True`.
- For `tools/call` with `name == "select_page"`:
  - Set `arguments.bringToFront = False`.
- Track `tools/list` request ids and patch the returned tool descriptions.
- Close upstream stdin on client EOF.
- Terminate upstream if it does not exit after a short grace period.

- [ ] **Step 2: Run proxy tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy -v
```

Expected: all proxy tests pass.

Then run residual check:

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py' || true
```

Expected: no proxy or upstream test processes remain.

## Task 3: Launcher Registration RED Tests

**Files:**
- Modify: `tests/test_browser_cockpit_launcher.py`

- [ ] **Step 1: Update existing registration assertions**

Update tests to require proxy registration and reject raw `chrome-devtools-mcp@latest`.

- [ ] **Step 2: Add stale raw registration repair test**

Seed a config where `chrome-devtools-cockpit` uses raw `npx chrome-devtools-mcp@latest` with the already-correct browser URL. The test must fail until launcher detects raw registration as stale.

- [ ] **Step 3: Run focused launcher tests and confirm RED**

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

Expected: failures showing current launcher still registers or accepts raw MCP.

## Task 4: Launcher Implementation

**Files:**
- Modify: `tools/launcher/browser_cockpit.sh`

- [ ] **Step 1: Add proxy defaults**

Add:

- `BUDDYSWITCH_BROWSER_COCKPIT_PROXY`
- `BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE`

Defaults:

- proxy path: `${BUDDYSWITCH_REPO_ROOT}/tools/launcher/chrome_devtools_cockpit_proxy.py`
- upstream package: `chrome-devtools-mcp@1.1.1`

- [ ] **Step 2: Register the proxy**

Change `buddyswitch_browser_ensure_cockpit_mcp` so `mcp add chrome-devtools-cockpit -- ...` uses:

```bash
python3 "${BUDDYSWITCH_BROWSER_COCKPIT_PROXY}" \
  --upstream-command "npx ${BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE}" \
  --browser-url="${expected_browser_url}"
```

- [ ] **Step 3: Treat raw server config as stale**

Add a section parser helper that returns success only when the current MCP section contains `chrome_devtools_cockpit_proxy.py`. If browser URL matches but the proxy marker is missing, remove and re-add the server.

- [ ] **Step 4: Run focused launcher tests and confirm GREEN**

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

Expected: all browser cockpit launcher tests pass.

## Task 5: Broad Launcher Assertion Alignment

**Files:**
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Update captured MCP argv assertions**

For tests that inspect `mcp add chrome-devtools-cockpit`, assert the argv contains the proxy script and the correct `--browser-url`.

- [ ] **Step 2: Run targeted broad-launcher tests**

Run:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_buddy_wires_instance_env_and_lifecycle -v
```

Expected: both pass.

## Task 6: Final Verification and Review

**Files:**
- Read-only review over all changed files.

- [ ] **Step 1: Run focused verification**

Run:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
```

- [ ] **Step 2: Check residual processes**

Run:

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

Expected: no unexpected residual processes from the test run.

- [ ] **Step 3: Run broader relevant verification**

Run:

```bash
python3 -m unittest tests.test_buddyswitch_launcher -v
```

If clean and residual check remains clean, run:

```bash
python3 -m unittest discover tests -v
```

- [ ] **Step 4: Review against requirements**

Confirm:

- Raw `chrome-devtools-mcp` is no longer registered directly by launcher.
- Same public MCP name remains.
- `new_page`, `select_page`, and `isolatedContext` behavior is test-proven.
- No skill, daemon, runtime actor profile, or auth module changed.
- Resource lifecycle checks are clean.

## Phase 1 Review

The plan covers the current bottleneck without introducing a general plugin system or cross-layer architecture. The implementation is deliberately a small process proxy at the tool boundary because that is the layer where Codex currently receives direct browser tools. The only explicit compatibility cost is a focused wrapper around one MCP server; it is justified because the raw server is the bypass that causes the focus-control policy to be unenforceable.

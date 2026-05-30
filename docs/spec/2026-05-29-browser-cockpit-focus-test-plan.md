# Browser Cockpit Focus Control Test Plan

## Goal

BuddySwitch must expose `chrome-devtools-cockpit` through a BuddySwitch-owned proxy so Codex cannot directly call the raw `chrome-devtools-mcp` server. The proxy must preserve normal browser automation while preventing default foreground activation from the primary MCP page tools.

## Functional Requirements

1. `chrome-devtools-cockpit` remains the Codex-visible MCP server name.
2. Launcher registration must point to a BuddySwitch-owned proxy command, not directly to `chrome-devtools-mcp`.
3. The proxy must start the upstream Chrome DevTools MCP server itself and pass the existing browser URL through.
4. `new_page` calls must be forwarded with `background: true`, even when the caller omits `background` or sends `background: false`.
5. `select_page` calls must be forwarded with `bringToFront: false`, even when the caller sends `bringToFront: true`.
6. `new_page` calls with `isolatedContext` must not be silently forwarded because upstream currently ignores `background` for that path. The proxy must reject that call with an MCP tool error explaining the non-activating boundary.
7. `tools/list` should still expose the upstream tool list, with focus-sensitive descriptions patched so Codex sees the BuddySwitch behavior.
8. Existing browser cockpit lifecycle behavior must remain instance-scoped and must not create runtime workspaces.
9. Existing optional-browser behavior must still remove stale cockpit MCP registration when the browser is unavailable or MCP setup fails.
10. Tests must not launch real Chrome, real Codex, or long-lived services. Any subprocess started by a test must be owned by the test and terminated by normal process completion or teardown.

## Focused Tests

### Proxy Behavior

Create `tests/test_browser_cockpit_proxy.py`.

Test cases:

1. `test_new_page_defaults_to_background`
   - Start the proxy with a fake upstream MCP command.
   - Send one JSON-RPC `tools/call` request for `new_page` with only `url`.
   - Assert the fake upstream received `arguments.background == True`.
   - Assert the client receives the upstream response.

2. `test_new_page_forces_background_when_caller_requests_foreground`
   - Send `new_page` with `background: false`.
   - Assert the upstream receives `background == True`.

3. `test_select_page_forces_no_bring_to_front`
   - Send `select_page` with `bringToFront: true`.
   - Assert the upstream receives `bringToFront == False`.

4. `test_new_page_isolated_context_is_rejected_without_forwarding`
   - Send `new_page` with `isolatedContext`.
   - Assert the client receives a JSON-RPC result with `isError: true`.
   - Assert the fake upstream did not receive a `tools/call` request.

5. `test_tools_list_patches_focus_sensitive_descriptions`
   - Fake upstream returns `new_page` and `select_page` schemas.
   - Assert the proxy returns the tools and description text mentions BuddySwitch non-activating behavior.

Resource rule:

- Each proxy test starts one proxy subprocess and one fake upstream subprocess.
- Use `communicate(..., timeout=5)`.
- Kill the proxy if timeout is reached.
- Fake upstream exits when stdin closes.
- No test opens a browser socket or starts a daemon.

### Launcher Registration

Modify `tests/test_browser_cockpit_launcher.py`.

Test cases:

1. Update `test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps`
   - Assert `mcp add chrome-devtools-cockpit` still happens.
   - Assert command after `--` is `python3`.
   - Assert args include `tools/launcher/chrome_devtools_cockpit_proxy.py`.
   - Assert args include the expected `--browser-url`.
   - Assert args do not include `chrome-devtools-mcp@latest`.

2. Add `test_browser_ensure_repairs_raw_cockpit_mcp_with_matching_browser_url`
   - Seed instance Codex config with raw `chrome-devtools-mcp@latest` and the correct browser URL.
   - Run `buddyswitch-codex env browser ensure --instance <id>` against fake curl/chrome/codex.
   - Assert launcher removes and re-adds `chrome-devtools-cockpit`.
   - Assert re-add uses the proxy command.

3. Update source-shape test
   - Assert `browser_cockpit.sh` references `chrome_devtools_cockpit_proxy.py`.
   - Assert `browser_cockpit.sh` does not register `chrome-devtools-mcp@latest`.

### Broader Launcher Call Sites

Modify focused assertions in `tests/test_buddyswitch_launcher.py` where they inspect `mcp add chrome-devtools-cockpit`.

For each existing assertion that only checks `--browser-url`, add or update checks so the captured argv proves:

- proxy script is registered;
- raw `chrome-devtools-mcp@latest` is absent;
- browser URL is still passed.

Do not broaden these tests into real service runs beyond their current fake helpers.

## Verification Commands

Run in this order:

1. `python3 -m unittest tests.test_browser_cockpit_proxy -v`
2. `python3 -m unittest tests.test_browser_cockpit_launcher -v`
3. `python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url -v`
4. `python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_buddy_wires_instance_env_and_lifecycle -v`
5. `python3 -m unittest tests.test_buddyswitch_launcher -v`
6. `python3 -m unittest discover tests -v`

Resource lifecycle check after focused and broad runs:

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

This host may already have unrelated `chrome-devtools-mcp` servers owned by active Codex sessions. Record that baseline separately if needed, but do not kill those processes from this task. The completion check for this task is that the focused tests do not leave new proxy, fake upstream, fake Chrome, app-server, or broker processes behind.

The broad suite may only be run after the focused tests pass and the task-scoped residual process check is clean.

## Review Checklist

- Generated Codex registration no longer exposes raw `chrome-devtools-mcp`.
- Proxy behavior is proven by observing fake-upstream input, not by checking implementation strings.
- No tests depend on real Chrome, real network CDP, or real Codex.
- `isolatedContext` cannot bypass the no-focus boundary.
- Existing instance-scoped browser behavior remains covered.
- Resource lifecycle check is clean before declaring completion.

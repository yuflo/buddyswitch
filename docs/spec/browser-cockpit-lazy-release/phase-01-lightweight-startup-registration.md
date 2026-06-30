# Phase 01 Lightweight Startup Registration

## Phase Objective

Replace actor start/resume browser bootstrap with static browser preflight plus portless cockpit MCP registration, so start/resume exposes the browser tool surface without allocating `browser_port`, starting Chrome, or printing browser readiness.

This phase covers memo Task 1 and Task 2. It intentionally does not implement first-call lazy upstream startup; that is covered by the later cockpit proxy phase.

## Exact Source Files To Modify

- `buddyswitch-codex`
- `tools/launcher/browser_cockpit.sh`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py`

## Exact Tests To Add Or Update

- Update `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests._assert_cockpit_proxy_registration` so it verifies a portless cockpit proxy registration:
  - command prefix is `mcp add chrome-devtools-cockpit`;
  - command after `--` is `python3 tools/launcher/chrome_devtools_cockpit_proxy.py`;
  - args include `--upstream-command "npx chrome-devtools-mcp@1.1.1"`;
  - args include `--instance-root=<instance_root>`;
  - args do not include any `--browser-url` value.
- Update `tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests._assert_cockpit_proxy_registration` with the same portless assertions.
- Replace `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_ready_page_launches_codex` with `test_start_with_required_role_registers_browser_tool_without_starting_chrome`.
- Replace `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_role_allocates_next_browser_port_when_default_is_busy` with `test_start_with_role_does_not_allocate_browser_port_when_default_is_busy`.
- Update `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_blocks_codex_when_cockpit_mcp_setup_fails` to prove required-role start still fails when cockpit MCP registration fails.
- Update `tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps` to keep `env browser ensure` runtime startup coverage while expecting portless MCP config.
- Update `tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_raw_cockpit_mcp_with_matching_browser_url` so stale raw or fixed-browser-url config is removed and replaced with portless proxy config.
- Update `tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_repairs_stale_cockpit_mcp_browser_url` and `test_env_browser_ensure_repairs_cockpit_mcp_missing_or_wrong_instance_root` to expect portless repair.

## Current Behavior Evidence

- `buddyswitch-codex:start_locked_bootstrap` currently calls `buddyswitch_browser_allocate_instance_port`, then `buddyswitch_browser_bootstrap`, then records `browser_port`.
- `buddyswitch-codex:instance_resume_locked` currently restores or allocates a browser port, calls `buddyswitch_browser_bootstrap`, then records `browser_port`.
- `tools/launcher/browser_cockpit.sh:buddyswitch_browser_bootstrap` currently calls `buddyswitch_browser_ensure_cockpit_endpoint`, which probes or starts Chrome, then calls `buddyswitch_browser_ensure_cockpit_mcp`.
- `tools/launcher/browser_cockpit.sh:buddyswitch_browser_ensure_cockpit_mcp` currently compares and writes `--browser-url=http://127.0.0.1:<port>`.
- `tests/test_buddyswitch_launcher.py` currently asserts start creates `browser/chrome.pid`, records integer `browser_port`, and writes a fixed `--browser-url` in config.
- `tests/test_browser_cockpit_launcher.py` currently asserts `env browser ensure` adds a cockpit MCP with a fixed `--browser-url`.

## Target Behavior For This Phase

- Actor start/resume validates role, env profile, role AGENTS template, shared env, runtime broker, Codex config, env MCP, and browser static prerequisites.
- Browser static preflight checks the proxy script path, upstream command executable, Chrome binary availability, active role browser capability, and cockpit MCP registration.
- Actor start/resume does not call `buddyswitch_browser_allocate_instance_port`, does not call `buddyswitch_browser_ensure_cockpit_endpoint`, does not create `browser/chrome.pid`, does not create `browser/profile`, and does not record `browser_port`.
- Required-browser roles fail start/resume when static prerequisites or cockpit MCP registration fail.
- Browser-available roles can continue if static browser prerequisites fail, with stale cockpit MCP removed when possible.
- `env browser ensure` remains the runtime-starting path and still starts Chrome, creates the actor profile, records `browser_port`, and registers cockpit MCP.
- All cockpit MCP registrations are portless and include only proxy path, upstream command, and instance root.
- Existing cockpit MCP entries containing `--browser-url` are treated as stale live residue and replaced by portless config.

## Implementation Steps

1. Update both `_assert_cockpit_proxy_registration` helpers to remove the `browser_url` parameter and assert portless proxy args.
2. Update required-role start tests to assert:
   - `instance_payload["browser_port"] is None`;
   - `browser/chrome.pid` does not exist;
   - `browser/profile` does not exist;
   - `config_toml` contains `[mcp_servers.chrome-devtools-cockpit]`;
   - combined stdout/stderr does not contain `Browser cockpit ready:`;
   - cockpit MCP add command is portless.
3. Update the busy-default-port start test to assert actor start ignores the busy default port, records `browser_port` as `None`, and still registers portless cockpit MCP.
4. Update `env browser ensure` tests to keep Chrome-start assertions while expecting portless cockpit MCP config and stale fixed-url repair.
5. Add `buddyswitch_browser_preflight_static` in `tools/launcher/browser_cockpit.sh`:
   - check `BUDDYSWITCH_BROWSER_COCKPIT_PROXY` exists as a file;
   - check the executable token from `BUDDYSWITCH_BROWSER_COCKPIT_UPSTREAM_PACKAGE` command is resolvable;
   - check `buddyswitch_browser_find_chrome_bin` succeeds;
   - do not call CDP, create profile directories, create pages, or start Chrome.
6. Add `buddyswitch_browser_register_cockpit_mcp` in `tools/launcher/browser_cockpit.sh`:
   - initialize browser defaults needed for instance paths;
   - determine whether the active role requires browser cockpit;
   - run static preflight;
   - call `buddyswitch_browser_ensure_cockpit_mcp` on static preflight success;
   - for required roles, return failure if static preflight or MCP registration fails;
   - for available roles, remove stale cockpit MCP when preflight or registration fails and return success.
7. Change `buddyswitch_browser_ensure_cockpit_mcp` in `tools/launcher/browser_cockpit.sh`:
   - compare proxy path, upstream command, instance root, and absence of `--browser-url`;
   - remove and re-add stale entries containing `--browser-url`;
   - write args with `--upstream-command "npx chrome-devtools-mcp@1.1.1"` and `--instance-root=<instance_root>` only.
8. Change `buddyswitch-codex:start_locked_bootstrap` to call `buddyswitch_browser_register_cockpit_mcp` after `buddyswitch_env_mcp_ensure`, and remove startup browser port allocation, browser endpoint bootstrap, and `browser_port` recording.
9. Change `buddyswitch-codex:instance_resume_locked` to call `buddyswitch_browser_register_cockpit_mcp` after `buddyswitch_env_mcp_ensure`, and remove resume browser port allocation, browser endpoint bootstrap, and `browser_port` recording.
10. Run the focused tests and update this phase document with actual results.

## Test Plan

Run the new failing startup test before implementation:

```bash
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_registers_browser_tool_without_starting_chrome
```

Expected before implementation: fail because current start records `browser_port`, starts fake Chrome, creates `browser/chrome.pid`, and writes `--browser-url`.

Run the focused phase tests after implementation:

```bash
python3 -m unittest \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_registers_browser_tool_without_starting_chrome \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_role_does_not_allocate_browser_port_when_default_is_busy \
  tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_blocks_codex_when_cockpit_mcp_setup_fails \
  tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps \
  tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_raw_cockpit_mcp_with_matching_browser_url
```

Expected after implementation: pass.

Run the broader launcher groups relevant to changed behavior:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher
python3 -m unittest tests.test_buddyswitch_launcher
```

Expected after implementation: pass.

Run syntax and diff checks:

```bash
bash -n buddyswitch-codex
bash -n tools/launcher/browser_cockpit.sh
git diff --check
```

Expected after implementation: no output from syntax or diff checks.

## Cleanup Requirements For Service-Starting Tests

- The focused start tests use fake Chrome and fake Codex helpers; no real Chrome or upstream MCP should start.
- Any test that creates `browser/chrome.pid` must verify the pid file is absent or remove it through existing test cleanup.
- After focused service-starting tests, run:

```bash
ps -axo pid,ppid,rss,command | rg "chrome-devtools-mcp|chrome_devtools_cockpit_proxy|remote-debugging-port|Google Chrome" || true
```

Expected after implementation: no process attributable to the focused tests remains.

## Residue Search Terms For This Phase

```bash
rg -n "Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|allocates_next_browser_port_when_default_is_busy|ready_page_launches_codex" \
  buddyswitch-codex tools/launcher/browser_cockpit.sh tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
```

Accepted hits after this phase:

- `Browser cockpit ready:` may remain inside `tools/launcher/browser_cockpit.sh` runtime ensure/status functions and `env browser status/ensure` tests.
- `--browser-url=http://127.0.0.1` may remain only in stale-config fixture strings used to prove repair.
- The old test names must have no hits.

## Phase Acceptance Checklist

- [x] Start/resume no longer allocates or records a browser port.
- [x] Start/resume no longer starts Chrome or creates browser runtime files.
- [x] Start/resume still registers `chrome-devtools-cockpit` for required browser roles.
- [x] Required browser role still fails when cockpit MCP registration fails.
- [x] `env browser ensure` still starts Chrome and records the ensured port.
- [x] Cockpit MCP config written by both start and ensure is portless.
- [x] Stale fixed-browser-url cockpit MCP config is removed and re-added as portless.
- [x] Focused tests pass.
- [x] Relevant launcher test groups pass.
- [x] Bash syntax checks pass.
- [x] Phase residue scan has only accepted hits.

## Verification Evidence

Red check before implementation:

```text
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_registers_browser_tool_without_starting_chrome
FAILED (failures=1)
AssertionError: 9222 is not None
```

Focused phase tests after implementation:

```text
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_registers_browser_tool_without_starting_chrome tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_role_does_not_allocate_browser_port_when_default_is_busy tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_blocks_codex_when_cockpit_mcp_setup_fails tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_starts_chrome_with_shared_profile_and_bootstraps_mcps tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_ensure_repairs_raw_cockpit_mcp_with_matching_browser_url
Ran 5 tests in 8.725s
OK
```

Focused regression after broad-suite failure:

```text
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_bootstrap_retry_failure_cleans_state_and_records_failure
Ran 1 test in 2.146s
OK
```

Broader launcher verification:

```text
python3 -m unittest tests.test_browser_cockpit_launcher
Ran 13 tests in 6.392s
OK

python3 -m unittest tests.test_buddyswitch_launcher
Ran 202 tests in 322.058s
OK
```

Syntax and diff checks:

```text
bash -n buddyswitch-codex
no output

bash -n tools/launcher/browser_cockpit.sh
no output

git diff --check
no output
```

Residue scan:

```text
rg -n -- "Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|allocates_next_browser_port_when_default_is_busy|ready_page_launches_codex" buddyswitch-codex tools/launcher/browser_cockpit.sh tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
```

Accepted hits:

- `tools/launcher/browser_cockpit.sh` readiness strings remain in runtime `env browser status/ensure` code.
- `tests/test_browser_cockpit_launcher.py` and `tests/test_buddyswitch_launcher.py` readiness assertions remain for runtime status tests and startup negative assertions.
- `--browser-url=http://127.0.0.1` hits remain only in stale config fixtures used to prove fixed-url MCP repair.
- Old test names `allocates_next_browser_port_when_default_is_busy` and `ready_page_launches_codex` have no hits.

Process cleanup checks:

```text
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|fake-chrome|fake_upstream|BUDDYSWITCH_TEST|browser-ready\\.flag" || true
only the rg command itself matched

ps -axo pid,ppid,rss,command | rg "chrome_devtools_cockpit_proxy.py" || true
existing matches are from /Users/chen/Dev/buddyswitch/.worktrees/fea-webui

ps -axo pid,ppid,rss,command | rg "chrome-devtools-mcp@1\\.1\\.1|app-version=1\\.1\\.1" || true
existing matches are from /Users/chen/Dev/buddyswitch/.worktrees/fea-webui and /Users/chen/.codex-buddyswitch active instances
```

Remaining risk:

- Phase 1 registers portless cockpit MCP config, but the proxy still needs the later lazy facade phase before portless `tools/list` and first `tools/call` are fully side-effect free and functional.

## Plan Self-Review

- Memo coverage: this phase maps to Task 1 and Task 2, and leaves lazy `tools/call`, release, search ensure, residue cleanup, and final smoke to later phases.
- Test mapping: each source change above has focused launcher tests or shell syntax verification.
- Process cleanup: tests use fake processes and include a residual process check before marking the phase complete.
- Rebuild-forward check: old eager start behavior is removed from start/resume instead of guarded by a flag.
- Boundary check: changes stay inside launcher browser ownership and launcher tests.

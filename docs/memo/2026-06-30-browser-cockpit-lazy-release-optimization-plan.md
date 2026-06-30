# Browser Cockpit Lazy Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace eager per-actor browser stack startup with a stable actor-facing browser tool that lazily starts Chrome and upstream Chrome DevTools MCP on first real browser use, then releases those heavy resources after browser page TTL idle.

**Architecture:** `chrome-devtools-cockpit` stays visible to actors as one stable MCP server, but becomes a lightweight BuddySwitch-owned facade. Browser lifecycle ownership stays in the browser slice: launcher host ensure/release, cockpit proxy upstream supervision, search browser opening, and browser daemon TTL/release handlers. The old eager semantics are replaced rather than preserved beside the new path.

**Tech Stack:** Bash launcher functions, Python stdio MCP proxy, Python env.tool runtime, Chrome DevTools Protocol helpers, BuddySwitch daemon scheduled triggers, Codex MCP stdio integration, `unittest`/launcher integration tests.

---

## Task Goal And Standard

The current bottleneck is idle actor memory. A running actor can carry a browser stack even when it is not using browser tools:

```text
actor instance
  -> Chrome remote-debugging process tree
  -> chrome-devtools-mcp / npx / node upstream process tree
  -> cockpit proxy state
```

Measured browser stack cost is hundreds of MB to more than 1 GB per active actor. The target behavior is:

```text
actor start/resume
  -> browser/search tools are available
  -> no Chrome process
  -> no upstream chrome-devtools-mcp process

first browser/search tool call
  -> host ensures actor-owned Chrome endpoint
  -> proxy starts upstream chrome-devtools-mcp
  -> tool call succeeds through existing cockpit controls

browser idle TTL
  -> pages close
  -> final page removal schedules release
  -> release stops upstream and Chrome
  -> browser_port is cleared

next browser/search tool call
  -> cold-starts browser stack again
```

The user-visible contract is:

```text
actor browser/search call -> BuddySwitch stable tool surface -> actor-owned browser runtime starts if needed -> tool performs browser work -> idle runtime releases -> later call starts it again
```

Success means lower idle memory without lowering browser tool reliability. The expected cost is first-call latency around the previously measured 2.5s cold-start range, excluding page navigation.

## Bitter Principles Applied

This plan follows `docs/bitter` as hard constraints:

- **Tool/skill layering:** fix runtime tool semantics and responses, not AGENTS prompt wording.
- **Test resource lifecycle:** every test that starts Chrome, daemon, app-server, proxy, or fake upstream must register cleanup and check residuals before broad verification.
- **Parallel boundary:** keep browser changes inside browser-owned files instead of adding shared framework switches.
- **Residue cleanup:** old eager-start semantics must disappear from live tests, launcher paths, and actor-facing surfaces.
- **Wrong-boundary narrowness:** do not add one-off shared daemon or broker methods for browser release. Browser-owned events belong in `browser_inbound.py` and browser handlers.
- **Built-in product interface:** browser lifecycle is a built-in product capability; CLI, MCP, search, and daemon are projections of that capability.
- **End-to-end contract slice:** acceptance must prove the full user-visible loop, not only local units.

## Non-Goals

- Do not remove `chrome-devtools-cockpit` from Codex MCP config at runtime.
- Do not depend on `config/mcpServer/reload` for browser availability or release.
- Do not expose `browser_port`, `browser_endpoint`, or `browser_url` to ordinary actor-facing tool output.
- Do not share Chrome profiles across actors.
- Do not add a generic resource manager, event bus, plugin system, or compatibility mode.
- Do not keep eager and lazy browser startup as two selectable modes.
- Do not implement actor stop changes in this plan.

## Current Code Review Findings

### 1. Actor Start And Resume Are Eager

Current files:

- `buddyswitch-codex:275` allocates a browser port during `start_locked_bootstrap`.
- `buddyswitch-codex:290` calls `buddyswitch_browser_bootstrap` before app-server thread start.
- `buddyswitch-codex:1137-1149` resumes by restoring or allocating a port, bootstrapping browser, and recording `browser_port`.
- `tools/launcher/browser_cockpit.sh:709-749` makes `buddyswitch_browser_bootstrap` ensure a Chrome endpoint and cockpit MCP.

This makes browser readiness part of actor startup instead of browser use.

Replacement:

- Actor start/resume performs browser preflight and MCP registration only.
- Runtime Chrome endpoint is created only by `env browser ensure`, `search.open_browser`, or first cockpit `tools/call`.

### 2. Cockpit MCP Registration Is Bound To A Fixed Browser URL

Current files:

- `tools/launcher/browser_cockpit.sh:359-384` writes MCP args with `--browser-url=<current port>`.
- `tools/launcher/chrome_devtools_cockpit_proxy.py:46` requires `--browser-url`.
- `tools/launcher/chrome_devtools_cockpit_proxy.py:56-60` builds upstream argv with that fixed URL.

This breaks release/reallocate because the MCP server config becomes stale when `browser_port` is cleared and later reallocated.

Replacement:

- MCP config passes `--instance-root` and upstream command only.
- Runtime browser URL is resolved after host ensure, immediately before starting upstream or evaluating page gates.
- `--browser-url` is used only when the proxy starts upstream internally, not as Codex config.

### 3. Proxy Starts Upstream Eagerly And Exits With It

Current files:

- `tools/launcher/chrome_devtools_cockpit_proxy.py:603-677` starts upstream in `run_proxy` before reading client messages.
- The main loop writes all client messages to one upstream process.
- `finally` closes upstream and returns the upstream exit code.

This makes `tools/list` and status collection start heavy resources, and release would kill the MCP server that Codex expects to keep using.

Replacement:

- Proxy itself handles `initialize`, `notifications/initialized`, and `tools/list`.
- Proxy starts upstream only for tool calls that require Chrome DevTools MCP.
- Proxy remains alive when upstream exits or is externally released.
- Proxy supervises upstream as a restartable child process.

### 4. Codex Status Collection Can Start MCP Servers

Current external source review:

- `/Users/chen/Dev/codex/codex-rs/app-server/README.md:235-236` states `config/mcpServer/reload` applies on next active turn and `mcpServerStatus/list` enumerates configured MCP servers with tools.
- `/Users/chen/Dev/codex/codex-rs/app-server/src/request_processors/mcp_processor.rs:314-321` collects an MCP status snapshot.
- `/Users/chen/Dev/codex/codex-rs/codex-mcp/src/mcp/mod.rs:399-424` creates an `McpConnectionManager` for status snapshot collection.

Therefore `tools/list` on `chrome-devtools-cockpit` must be side-effect free. It cannot start Chrome or upstream.

### 5. `env browser ensure` Falls Back To Default Port When No Port Is Recorded

Current files:

- `buddyswitch-codex:1551-1567` reads `browser_port`; if missing, it only initializes defaults.
- `buddyswitch-codex:1804-1830` validates default port before locked ensure.
- `tools/launcher/browser_cockpit.sh:52` defaults `BUDDYSWITCH_BROWSER_PORT` to 9222.

After release clears `browser_port`, a later ensure can default to 9222 instead of allocating a free port. That can fail or attach to the wrong listener.

Replacement:

- Locked browser ensure must allocate a fresh port when the actor has no valid owned active endpoint.
- If recorded endpoint is active but foreign, do not kill it; clear this actor's stale port and allocate a new one.
- Explicit `--port` remains an override with existing validation.

### 6. Search Browser Opening Treats Missing Port As Browser Unavailable

Current files:

- `scripts/env/tools/search/_impl.py:68-76` builds endpoint only from `instance_payload["browser_port"]`.
- `scripts/env/tools/search/_impl.py:807-964` returns `E_SEARCH_BROWSER_UNAVAILABLE` when endpoint is missing.
- Current tests include `tests/test_search_env_tool.py:831-843`, which expects missing port to fail.

Replacement:

- `search.open_browser` must host-ensure the browser endpoint before computing the endpoint.
- It must reload `instance.json` inside the same call after ensure because the runtime broker loads `instance_payload` only once per request.
- It must keep current background CDP open behavior, page limit, and TTL registration.
- It must remove `browser_endpoint` from ordinary success and rejection payloads.

### 7. Daemon Browser Handlers Use Cached `instance_payload`

Current files:

- `tools/launcher/daemon_core.py:1243-1273` loads daemon context from `instance.json`.
- The daemon run path keeps this context for handlers.
- `tools/launcher/browser_page_expired_handler.py:58-65` reads `context.instance_payload["browser_port"]`.

With lazy start, the daemon can start while `browser_port` is `None`; later browser ensure writes a port, but the daemon handler may still see the cached `None`. This would make TTL expiry unable to close pages.

Replacement:

- Browser daemon handlers must read the current `browser_port` from `context.instance_json` at handling time.
- Release handler must also read fresh state from `instance.json`, not cached daemon context.

### 8. TTL Stale Endpoint Leaves Tracked Target Residue

Current files:

- `tools/launcher/browser_page_expired_handler.py:143-148` treats stale browser errors as handled.
- It does not call `forget_page_idle_target` on stale endpoint errors.

That can leave stale `page_idle.json` targets forever and block final release.

Replacement:

- On stale/unreachable endpoint, forget the tracked target.
- After any target is forgotten, if no tracked targets remain, schedule cockpit release.

### 9. Existing Stop Only Handles Chrome Marker PID

Current files:

- `tools/launcher/browser_cockpit.sh:751-774` kills only `browser/chrome.pid`.
- Upstream `chrome-devtools-mcp` is a child of proxy and has no current release marker.

Replacement:

- Proxy writes an upstream PID/PGID marker under the instance browser runtime directory.
- Browser release terminates the recorded upstream process group before stopping Chrome.
- Proxy treats external upstream termination as a releasable state and restarts upstream on the next browser tool call.

### 10. Recent Browser Behavior Must Not Regress

Recent commits show this area has been actively stabilized:

- `5689f9d Avoid browser focus stealing in cockpit`
- `ea7b638 Move browser background helper into runtime env surface`
- `eee86a8 feat: add browser page limit gate`
- `9a481c6 feat: implement browser page idle lifecycle`
- `6f6a2c1 feat: stabilize browser page lifecycle management`
- `45ae06c fix browser new page ttl registration`

The lazy release implementation must keep:

- background page creation;
- no focus stealing;
- page limit gate;
- `new_page` target reconciliation;
- TTL refresh for `new_page`, `select_page`, and page-scoped tools;
- cleanup when lifecycle registration fails.

## Replacement Architecture

### Browser Lifecycle Ownership

Use one browser-owned product slice:

```text
tools/launcher/browser_cockpit.sh
  host-level browser preflight, MCP registration, runtime ensure, runtime release

tools/launcher/chrome_devtools_cockpit_proxy.py
  stable MCP facade, static tools/list, lazy upstream supervisor, existing cockpit message mutation

scripts/env/cdp_browser_lifecycle.py
  page idle state, page TTL schedule, final release schedule helpers

tools/launcher/browser_page_expired_handler.py
  page expiry, stale target cleanup, release scheduling

tools/launcher/browser_release_handler.py
  final release trigger handling

tools/launcher/browser_inbound.py
  browser-owned trigger registrations only

scripts/env/tools/search/_impl.py
  search.open_browser projection that host-ensures browser before CDP open
```

Do not introduce a shared runtime resource manager. Browser owns browser lifecycle.

### Runtime State Files

Use existing instance-scoped browser runtime area:

```text
<instance_root>/browser/chrome.pid
<instance_root>/browser/profile/
<instance_root>/runtime/browser/page_idle.json
<instance_root>/runtime/browser/page_idle.lock
<instance_root>/runtime/browser/cockpit-upstream.pid
<instance_root>/runtime/browser/cockpit-upstream.pgid
```

`browser_port` remains in `instance.json`, but its meaning changes:

```text
None
  no active actor-owned browser endpoint is recorded

integer
  currently recorded actor browser endpoint; must still be verified for ownership before use or release
```

Do not preserve dormant port reservations after release. Release clears `browser_port`.

### MCP Facade Contract

The proxy must support:

```text
initialize
notifications/initialized
tools/list
tools/call
```

Facade behavior:

- `initialize`: respond locally with stable `serverInfo` and tool capability.
- `notifications/initialized`: record initialized state locally.
- `tools/list`: return local static schema patched with existing BuddySwitch restrictions.
- `tools/call`: ensure browser, start upstream if needed, initialize upstream internally, then forward through existing mutation/response patching.

Upstream supervision behavior:

- Start upstream only after browser ensure succeeds.
- Send upstream `initialize` with cached client capabilities or a minimal compatible local client payload.
- Send upstream initialized notification before forwarding the first tool call.
- If upstream exits outside an in-flight call, keep proxy alive.
- If upstream exits during a call, return an MCP tool error for that request and allow retry.
- Write upstream PID/PGID markers after successful spawn.
- Clear markers after upstream exit.

### Search Contract

`search.open_browser` becomes:

```text
validate payload
  -> validate profile allows browser_cockpit
  -> ensure actor-owned browser endpoint
  -> reload instance.json
  -> compute endpoint internally
  -> evaluate page limit/reuse
  -> open/reuse background page
  -> refresh TTL
  -> return target intent without endpoint leak
```

The actor sees browser intent and next actions, not port internals.

### TTL And Release Contract

Existing page TTL remains 300 seconds.

Release scheduling:

```text
page idle expires
  -> close or forget target
  -> if tracked targets are empty
  -> schedule browser.cockpit.release with key browser.cockpit.release
  -> delay 10s
```

Release handling:

```text
release trigger fires
  -> acquire launcher runtime lock
  -> reload instance.json
  -> reload page_idle.json
  -> if parent turn running: handled/noop
  -> if tracked targets exist: handled/noop
  -> if CDP has real non-internal user page: handled/noop
  -> if endpoint is foreign/unknown: clear only this actor stale browser_port when safe, do not kill listener
  -> stop upstream process group from marker
  -> stop owned Chrome from marker/ownership
  -> clear page_idle state
  -> clear browser_port
```

The release trigger is allowed to be stale. Rechecks make stale releases harmless.

## Implementation Tasks

### Task 1: Replace Actor Startup Browser Bootstrap With Lightweight Registration

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify tests: `tests/test_buddyswitch_launcher.py`, `tests/test_browser_cockpit_launcher.py`

- [x] Step 1: Add failing launcher tests proving actor start does not start Chrome for browser-required roles.

  Add or replace focused assertions around the existing required-browser startup tests:

  ```python
  self.assertFalse((instance_root / "browser" / "chrome.pid").exists())
  self.assertIsNone(instance_payload.get("browser_port"))
  self.assertIn("[mcp_servers.chrome-devtools-cockpit]", payload["config_toml"])
  self.assertNotIn("Browser cockpit ready:", completed.stdout + completed.stderr)
  ```

- [x] Step 2: Run the focused failing tests.

  ```bash
  python3 -m unittest \
    tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_role_registers_browser_tool_without_starting_chrome \
    tests.test_browser_cockpit_launcher.BrowserCockpitLauncherTests.test_browser_mcp_registration_is_lightweight
  ```

  Expected before implementation: fail because startup still bootstraps Chrome or records `browser_port`.

- [x] Step 3: Replace start/resume calls.

  Change `start_locked_bootstrap` and resume flow so they call a lightweight browser registration/preflight function instead of `buddyswitch_browser_allocate_instance_port` plus `buddyswitch_browser_bootstrap`.

  Required resulting behavior:

  ```text
  start/resume
    -> validate role
    -> ensure env MCP
    -> browser preflight for required role
    -> ensure cockpit MCP config
    -> no Chrome endpoint probe
    -> no browser_port write
  ```

- [x] Step 4: Keep required-role failure meaningful.

  Required browser roles must fail actor start when static prerequisites are missing:

  ```text
  proxy script missing
  upstream command executable cannot be resolved
  Chrome binary cannot be found
  cockpit MCP registration fails
  ```

  They must not fail because Chrome has not been launched.

- [x] Step 5: Run focused launcher tests.

  ```bash
  python3 -m unittest tests.test_buddyswitch_launcher tests.test_browser_cockpit_launcher
  ```

  Expected after implementation: browser startup expectations are replaced by lightweight registration expectations.

### Task 2: Make Cockpit MCP Config Portless

**Files:**

- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify tests: `tests/test_browser_cockpit_launcher.py`, `tests/test_buddyswitch_launcher.py`

- [x] Step 1: Add failing tests for portless MCP config.

  Expected MCP args:

  ```text
  python3 tools/launcher/chrome_devtools_cockpit_proxy.py
    --upstream-command "npx chrome-devtools-mcp@1.1.1"
    --instance-root <instance_root>
  ```

  Rejected in config:

  ```text
  --browser-url=http://127.0.0.1:<port>
  ```

- [x] Step 2: Update `buddyswitch_browser_ensure_cockpit_mcp`.

  It must compare only stable cockpit config:

  ```text
  proxy path
  upstream command
  instance root
  no browser URL
  ```

  If an existing MCP entry contains `--browser-url`, remove and re-add it as portless. This is cleanup of old live semantics, not a compatibility path.

- [x] Step 3: Update proxy args.

  `--browser-url` is removed from proxy CLI. Proxy computes browser URL from current instance state after host ensure.

- [x] Step 4: Run focused config tests.

  ```bash
  python3 -m unittest tests.test_browser_cockpit_launcher tests.test_buddyswitch_launcher
  ```

### Task 3: Fix Host Browser Ensure And Port Ownership

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify tests: `tests/test_buddyswitch_launcher.py`, `tests/test_browser_cockpit_launcher.py`

- [x] Step 1: Add failing test for no recorded port.

  Scenario:

  ```text
  instance.json browser_port = None
  port 9222 is occupied by another listener
  env browser ensure --instance <actor>
  ```

  Expected:

  ```text
  browser_port is next available free port
  no attach to 9222
  actor profile path is instance browser/profile
  ```

- [x] Step 2: Add failing test for foreign recorded endpoint.

  Scenario:

  ```text
  actor A records browser_port = 9333
  port 9333 is active with actor B profile
  env browser ensure --instance actor A
  ```

  Expected:

  ```text
  actor A does not kill actor B listener
  actor A allocates a new free port
  actor A instance.json records the new port
  ```

- [x] Step 3: Replace ensure logic.

  Locked ensure must use this state machine:

  ```text
  if explicit --port:
      validate and use explicit port
  elif recorded port has owned active endpoint:
      reuse recorded port
  elif recorded port is inactive:
      use recorded port only if socket is available, otherwise allocate
  elif recorded port is foreign or unknown:
      allocate fresh free port
  else:
      allocate fresh free port
  ```

- [x] Step 4: Run focused ensure tests.

  ```bash
  python3 -m unittest \
    tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_allocates_when_instance_port_missing \
    tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_env_browser_ensure_reallocates_foreign_recorded_port \
    tests.test_browser_cockpit_launcher
  ```

### Task 4: Refactor Cockpit Proxy Into A Stable Lazy Facade

**Files:**

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Create or modify: `tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json`
- Modify tests: `tests/test_browser_cockpit_proxy.py`

- [x] Step 1: Add failing test that `initialize` and `tools/list` do not start upstream.

  Test shape:

  ```python
  # Start proxy with fake upstream command that writes argv_path when spawned.
  # Send initialize.
  # Send notifications/initialized.
  # Send tools/list.
  self.assertFalse(argv_path.exists(), "tools/list must not spawn upstream")
  self.assertIn("new_page", listed_tool_names)
  ```

- [x] Step 2: Add failing test that first `tools/call` starts upstream and forwards through existing mutation.

  Expected for `new_page`:

  ```text
  upstream argv includes --browser-url=<ensured endpoint>
  forwarded arguments include background=true
  lifecycle target registration still happens
  ```

- [x] Step 3: Add failing test that upstream death does not kill proxy.

  Test shape:

  ```text
  first tools/call starts fake upstream
  fake upstream exits
  proxy stays running
  second tools/call starts new fake upstream
  second call receives response
  ```

- [x] Step 4: Implement a small `UpstreamManager`.

  Required responsibilities:

  ```text
  start(browser_url)
  ensure_initialized()
  send_request(message)
  stop()
  note_exited()
  write_pid_markers()
  clear_pid_markers()
  ```

  Keep this in `chrome_devtools_cockpit_proxy.py` unless the file becomes unreviewable during implementation.

- [x] Step 5: Preserve existing cockpit controls.

  Existing functions must remain in the call path:

  ```text
  mutate_client_message
  patch_tool_list_message
  patch_tool_response_page_use_metadata
  focus-blocking logic
  page limit gate
  TTL refresh hints
  new_page target reconciliation
  ```

- [x] Step 6: Run proxy tests.

  ```bash
  python3 -m unittest tests.test_browser_cockpit_proxy
  ```

### Task 5: Add Browser Release Scheduling To Page Lifecycle

**Files:**

- Modify: `scripts/env/cdp_browser_lifecycle.py`
- Modify: `tools/launcher/browser_page_expired_handler.py`
- Create: `tools/launcher/browser_release_handler.py`
- Modify: `tools/launcher/browser_inbound.py`
- Modify tests: `tests/test_cdp_browser_session.py`, `tests/test_browser_page_expired_handler.py`, `tests/test_daemon_trigger_router.py`, `tests/test_instance_daemon_entrypoint.py`

- [x] Step 1: Add failing test for final tracked page scheduling release.

  After `browser.page.expired` closes or forgets the only tracked target, expected scheduled trigger:

  ```json
  {
    "type": "browser.cockpit.release",
    "payload": {"reason": "page_idle_empty"},
    "source_context": {"owner": "browser"},
    "schedule_key": "browser.cockpit.release"
  }
  ```

  Delay must be 10 seconds.

- [x] Step 2: Add failing test for stale endpoint cleanup.

  Scenario:

  ```text
  page_idle.json contains target-idle-1
  close_page_target raises stale connection refused
  ```

  Expected:

  ```text
  target-idle-1 removed from page_idle.json
  release schedule created if no targets remain
  handler returns handled
  ```

- [x] Step 3: Add release scheduling helper.

  Add a browser lifecycle helper that schedules a keyed release trigger. It must not know how to stop processes.

- [x] Step 4: Register release inbound event.

  `browser_inbound.py` must register both:

  ```text
  browser.page.expired
  browser.cockpit.release
  ```

  This is still one browser-owned inbound source module.

- [x] Step 5: Run daemon lifecycle tests.

  ```bash
  python3 -m unittest \
    tests.test_cdp_browser_session \
    tests.test_browser_page_expired_handler \
    tests.test_daemon_trigger_router \
    tests.test_instance_daemon_entrypoint
  ```

### Task 6: Implement Browser Release Handler

**Files:**

- Create: `tools/launcher/browser_release_handler.py`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tools/launcher/env.sh`
- Modify tests: `tests/test_browser_page_expired_handler.py`, `tests/test_buddyswitch_launcher.py`

- [x] Step 1: Add failing unit tests for release noops.

  Noop cases:

  ```text
  parent activity is running
  page_idle targets are non-empty
  CDP reports a real user page
  endpoint ownership is foreign
  browser_port missing
  ```

- [x] Step 2: Add failing test for release cleanup.

  Scenario:

  ```text
  browser_port is recorded
  ownership is owned
  page_idle targets are empty
  upstream pid marker exists
  chrome pid marker exists
  parent activity is idle
  ```

  Expected:

  ```text
  upstream process group stopped
  Chrome stopped
  page_idle state cleared
  browser_port set to None
  foreign listeners untouched
  handler returns handled
  ```

- [x] Step 3: Implement fresh instance reads.

  Release handler must read `context.instance_json` at handling time. It must not trust cached `context.instance_payload`.

- [x] Step 4: Add launcher release function.

  Add a locked browser release entrypoint that:

  ```text
  validates actor id
  checks endpoint ownership
  terminates upstream marker process group
  stops owned Chrome
  clears browser_port
  clears browser runtime page idle file
  ```

- [x] Step 5: Run release tests.

  ```bash
  python3 -m unittest \
    tests.test_browser_page_expired_handler \
    tests.test_buddyswitch_launcher
  ```

### Task 7: Make `search.open_browser` Ensure Browser Runtime

**Files:**

- Modify: `scripts/env/tools/search/_impl.py`
- Modify tests: `tests/test_search_env_tool.py`, `tests/test_env_tool_response_contract.py`

- [x] Step 1: Replace missing-port failure test.

  Old expectation:

  ```text
  browser_port None -> E_SEARCH_BROWSER_UNAVAILABLE
  ```

  New expectation:

  ```text
  browser_port None -> host ensure called -> instance.json reloaded -> page opened
  ```

- [x] Step 2: Add test for ensure failure.

  If host ensure fails, `search.open_browser` returns a structured rejection:

  ```text
  code = E_SEARCH_BROWSER_ENSURE_FAILED
  state_changed = false
  page_opened = false
  no browser_endpoint in actor-facing payload
  retry option points to search.status
  ```

- [x] Step 3: Add endpoint leak tests.

  Success and rejection payloads must not include:

  ```text
  browser_endpoint
  browser_url
  ```

  Internal test helpers may inspect endpoint indirectly through the fake CDP server request log.

- [x] Step 4: Implement ensure-then-open.

  The call path must:

  ```text
  run launcher env browser ensure --instance <actor_id>
  reload instance.json from context["instance_json"]
  compute endpoint from fresh payload
  continue existing page gate/open/TTL code
  ```

- [x] Step 5: Run search tests.

  ```bash
  python3 -m unittest tests.test_search_env_tool tests.test_env_tool_response_contract
  ```

### Task 8: Remove Live Surface Residue

**Files:**

- Modify tests and docs that are live actor/runtime guidance only.
- Do not rewrite historical `docs/bitter` or old memo evidence.

- [x] Step 1: Define old and new live terms.

  Old live semantics:

  ```text
  actor start requires Chrome endpoint ready
  actor start records browser_port
  cockpit MCP config contains --browser-url
  search.open_browser reports missing browser_port as normal unavailable state
  ```

  New live semantics:

  ```text
  actor start registers browser capability without starting Chrome
  browser_port means active recorded endpoint only
  cockpit MCP config is portless
  browser/search calls ensure runtime on demand
  TTL final release clears browser runtime
  ```

- [x] Step 2: Add scoped residue scans.

  Use narrow scans over live surfaces:

  ```bash
  rg -n "start.*Chrome|Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|instance browser_port is missing" \
    buddyswitch-codex tools/launcher scripts/env/tools/search tests tools/launcher/assets/roles framework/contracts
  ```

  Remaining hits must be one of:

  ```text
  env browser ensure/status tests
  internal upstream argv construction
  historical docs outside live surfaces
  explicit negative test names proving old semantics are gone
  ```

- [x] Step 3: Update live guidance.

  Role AGENTS and contracts may continue to say use `search.open_browser` then `chrome-devtools-cockpit`. They must not teach ports, manual browser startup, or status-query startup.

- [x] Step 4: Run residue scan and record accepted hits in implementation notes.

### Task 9: End-To-End Acceptance Smoke

**Files:**

- Add or modify: `tests/test_browser_lazy_release_integration.py` if existing launcher tests become too broad.
- Prefer extending existing browser launcher/proxy tests when it stays readable.

- [x] Step 1: Add smoke test for full loop with fakes.

  Contract sentence:

  ```text
  actor browser call -> lazy runtime starts -> page opens and registers TTL -> TTL closes final page -> release stops runtime -> next browser call starts runtime again
  ```

  The smoke can use fake Chrome/CDP and fake upstream MCP; it must prove process markers and instance state transitions.

- [x] Step 2: Include residual process checks.

  After each service-starting smoke:

  ```text
  fake upstream stopped
  fake Chrome stopped
  pid markers removed
  sockets/temp runtime paths cleaned
  ```

- [x] Step 3: Run focused end-to-end smoke.

  ```bash
  python3 -m unittest tests.test_browser_lazy_release_integration
  ```

  If the test is folded into existing files, run the exact focused test names added there.

## Verification Plan

Run in this order during implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy
python3 -m unittest tests.test_cdp_browser_session tests.test_browser_page_expired_handler
python3 -m unittest tests.test_search_env_tool tests.test_env_tool_response_contract
python3 -m unittest tests.test_browser_cockpit_launcher
python3 -m unittest tests.test_buddyswitch_launcher
python3 -m unittest tests.test_daemon_trigger_router tests.test_instance_daemon_entrypoint
```

Then run residue and syntax checks:

```bash
python3 -m py_compile \
  tools/launcher/chrome_devtools_cockpit_proxy.py \
  tools/launcher/browser_page_expired_handler.py \
  tools/launcher/browser_release_handler.py \
  scripts/env/cdp_browser_lifecycle.py \
  scripts/env/tools/search/_impl.py

rg -n "start.*Chrome|Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|instance browser_port is missing" \
  buddyswitch-codex tools/launcher scripts/env/tools/search tests tools/launcher/assets/roles framework/contracts

git diff --check
```

Manual process verification after a real or fake-product smoke:

```bash
ps -axo pid,ppid,rss,command | rg "chrome-devtools-mcp|chrome_devtools_cockpit_proxy|remote-debugging-port|Google Chrome" || true
```

Acceptance requires:

- start/resume has no Chrome/upstream process;
- `mcpServerStatus/list` and `tools/list` do not start Chrome/upstream;
- first cockpit call starts runtime and succeeds;
- first `search.open_browser` starts runtime and succeeds;
- page TTL closes pages and schedules release;
- release stops upstream and Chrome and clears `browser_port`;
- next browser call starts runtime again;
- foreign endpoint is never killed;
- actor-facing payloads do not expose browser endpoint internals;
- live surfaces no longer teach eager browser startup semantics.

## Implementation Boundaries

Keep one intent:

```text
browser stack lazy start and idle release
```

Do not mix in:

- actor stop redesign;
- web-management UI redesign;
- unrelated daemon log/observability work;
- role prompt rewrite;
- search API provider changes;
- Chrome DevTools MCP package upgrade.

If the upstream tool schema snapshot needs regeneration because `chrome-devtools-mcp@1.1.1` changes, that is a separate explicit dependency update, not part of this behavior change.

## Rollout Shape

This is a replacement, not a compatibility rollout:

1. Add failing tests for new lazy/release contract.
2. Replace startup browser bootstrap with lightweight registration.
3. Replace fixed-port proxy with portless lazy facade.
4. Replace missing-port search behavior with host ensure.
5. Add release scheduling and release handler.
6. Remove live eager-start residue.
7. Run focused tests, end-to-end smoke, residue scan, syntax checks, and diff check.

Do not keep an environment flag for old eager browser startup.

## Completion Checklist

- [x] `docs/bitter` principles remain reflected in tests and live surfaces.
- [x] No actor start/resume path starts Chrome.
- [x] No `tools/list` path starts upstream Chrome DevTools MCP.
- [x] No ordinary actor-facing browser/search payload exposes endpoint internals.
- [x] Browser daemon handlers read fresh `instance.json`.
- [x] Release handles stale schedules safely.
- [x] Release never kills foreign endpoints.
- [x] Focus/background/page-limit/TTL registration behavior remains covered.
- [x] Service-starting tests clean up process groups, pid files, sockets, and temp runtime files.
- [x] Residue scan has no unexplained live hits.
- [x] End-to-end contract smoke proves lazy start, use, idle release, and restart.

# Phase 03 Stable Lazy Cockpit Proxy

## Phase Objective

Refactor `chrome_devtools_cockpit_proxy.py` from an eager upstream pipe into a stable portless MCP facade: `initialize`, `notifications/initialized`, and `tools/list` are handled locally without starting Chrome or upstream MCP; first real `tools/call` ensures the actor browser runtime, starts upstream with the fresh browser URL, forwards through existing BuddySwitch mutations, and keeps the proxy alive across upstream exits.

This phase covers memo Task 4 and the proxy-dependent part of memo Task 2.

## Exact Source Files To Modify

- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Create `tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json`
- `tests/test_browser_cockpit_proxy.py`

## Exact Tests To Add Or Update

- Add `tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_initialize_and_tools_list_do_not_start_upstream_without_browser_url`.
- Add `tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_first_tools_call_ensures_browser_and_starts_upstream`.
- Add `tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_upstream_exit_does_not_stop_proxy_and_next_call_restarts`.
- Update existing proxy tests so `_run_proxy` starts the proxy without `--browser-url`.
- Keep existing tests for:
  - `new_page` background forcing;
  - `isolatedContext` rejection before upstream;
  - focus-blocking;
  - page limit gate;
  - page reuse;
  - `select_page` and page-scoped TTL refresh;
  - `new_page` target reconciliation and lifecycle registration failure cleanup;
  - patched `tools/list` descriptions.

## Current Behavior Evidence

- `parse_args` currently requires `--browser-url`.
- `build_upstream_argv` currently appends `--browser-url=<args.browser_url>` before runtime state is consulted.
- `run_proxy` currently starts upstream before reading any client input.
- `tools/list` is currently forwarded to upstream, then patched on the response path.
- If upstream exits, the proxy closes upstream and returns the upstream exit code.
- Existing tests start fake upstream for all proxy runs, including `tools/list`.

## Target Behavior For This Phase

- Proxy CLI accepts `--upstream-command` and `--instance-root`; it no longer accepts or requires `--browser-url`.
- `initialize` request returns a local MCP initialize response with tool capability and stable server info.
- `notifications/initialized` is recorded or ignored locally and is not forwarded to upstream until upstream is started internally.
- `tools/list` returns a local static schema loaded from `tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json`, patched by `patch_tool_list_message`.
- No `initialize`, `notifications/initialized`, `tools/list`, invalid JSON pass-through, or local rejection starts upstream.
- First forwarded `tools/call`:
  - reads `actor_id` and current `browser_port` from `<instance_root>/instance.json`;
  - runs `buddyswitch-codex env browser ensure --instance <actor_id>`;
  - reloads `instance.json`;
  - computes `http://127.0.0.1:<browser_port>`;
  - starts upstream with `--browser-url=<fresh_url>`;
  - initializes upstream using the cached client initialize params or a minimal compatible params object;
  - sends `notifications/initialized`;
  - forwards the mutated tool call.
- If upstream exits outside an in-flight request, proxy stays alive and clears upstream state.
- If upstream exits during a request, proxy returns an MCP tool error for that request and allows a later call to start a new upstream.
- Existing functions remain in the call path:
  - `mutate_client_message`;
  - `patch_tool_list_message`;
  - `patch_tool_response_page_use_metadata`;
  - focus-blocking and local tool rejection logic;
  - page limit gate;
  - TTL refresh and `new_page` target reconciliation.

## Implementation Steps

1. Generate or create `tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json` with the Chrome DevTools MCP 1.1.1 `tools/list` result shape:
   - top-level object with `tools`;
   - include at least every tool name used by existing tests: `new_page`, `select_page`, `list_pages`, `close_page`, `take_snapshot`, `take_screenshot`, `click`, `type_text`, `evaluate_script`, `navigate_page`, `wait_for`, `fill`, `press_key`;
   - keep `new_page.background`, `new_page.isolatedContext`, and `select_page.bringToFront` schema properties so existing patch assertions remain meaningful.
2. Update `_run_proxy` test helper to omit `--browser-url` by default and create an `instance.json` under the provided `instance_root`.
3. Add test `test_initialize_and_tools_list_do_not_start_upstream_without_browser_url`:
   - fake upstream writes `argv_path` on spawn;
   - send `initialize`, `notifications/initialized`, and `tools/list`;
   - assert no upstream argv file exists;
   - assert `tools/list` includes `new_page`;
   - assert patched descriptions mention BuddySwitch non-activating behavior.
4. Add test `test_first_tools_call_ensures_browser_and_starts_upstream`:
   - instance starts with `browser_port=None`;
   - fake ensure script updates `instance.json` to a fake CDP server port and records the ensure call;
   - first `tools/call new_page` starts upstream with `--browser-url=<fake_cdp_url>`;
   - forwarded arguments include `background=True`;
   - lifecycle target registration still happens.
5. Add test `test_upstream_exit_does_not_stop_proxy_and_next_call_restarts`:
   - fake upstream handles one `tools/call`, exits, and records argv;
   - second `tools/call` in the same proxy process starts a new fake upstream;
   - both calls receive responses;
   - proxy process exits `0` after stdin closes.
6. Refactor `parse_args` and `build_upstream_argv`:
   - remove `--browser-url`;
   - make `build_upstream_argv(args, passthrough_args, browser_url)` append the runtime browser URL.
7. Add local MCP helpers:
   - `initialize_response(request)`;
   - `load_static_tools()`;
   - `tools_list_response(request)`;
   - `read_instance_payload(instance_root)`;
   - `ensure_browser_url(instance_root)`.
8. Add a small `UpstreamManager` inside `chrome_devtools_cockpit_proxy.py`:
   - owns `upstream`, relay thread, request id tracking, pending hints, output lock, and cached initialize params;
   - `ensure_started(browser_url)` starts upstream and initializes it when needed;
   - `send_request(message, response_hint)` writes one JSON-RPC message;
   - `stop()` terminates upstream on proxy shutdown;
   - relay clears state when upstream exits and patches responses through existing functions.
9. Update `run_proxy`:
   - loop over stdin without an upstream process initially;
   - handle `initialize`, `notifications/initialized`, and `tools/list` locally;
   - run existing local focus/tool rejections before starting upstream where possible;
   - for forwarded `tools/call`, ensure browser URL, start upstream, then send the mutated request;
   - keep proxy alive after upstream exits.
10. Run focused proxy tests and update this phase document with actual results.

## Implementation Results

- Created `tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json` as the local `tools/list` schema source.
- Removed `--browser-url` from the proxy CLI; the proxy now resolves the runtime browser URL after host ensure.
- Added local handling for `initialize`, `notifications/initialized`, `tools/list`, unsupported methods, focus-blocking, and invalid JSON before upstream startup.
- Added `UpstreamManager` to start/restart upstream, send the internal upstream initialize handshake, suppress the internal initialize response, forward tool calls, return a tool error for upstream exit during an in-flight call, and keep the proxy alive for later calls.
- Added upstream PID/PGID marker write and clear under `<instance_root>/runtime/browser/`.
- Preserved the existing mutation and response patch path for `new_page`, `select_page`, page-scoped tools, page limit checks, TTL refresh, lifecycle cleanup, and response hints.

## Verification Results

Red checks observed before implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_initialize_and_tools_list_do_not_start_upstream_without_browser_url
```

Failed because the proxy still required `--browser-url`.

```bash
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_first_tools_call_ensures_browser_and_starts_upstream
```

Failed before the ensure/reload path existed.

Green checks after implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_invalid_json_before_upstream_does_not_start_upstream
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_first_tools_call_ensures_browser_and_starts_upstream
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_upstream_exit_during_request_returns_error_and_next_call_restarts
python3 -m unittest tests.test_browser_cockpit_proxy
python3 -m py_compile tools/launcher/chrome_devtools_cockpit_proxy.py
git diff --check
```

Observed result: proxy suite ran 29 tests and passed; syntax check passed; `git diff --check` produced no output.

Residue scan:

```bash
rg -n -- "--browser-url|required=True|run_proxy\\(upstream_argv|tools/list.*forward|close_upstream\\(upstream\\)" \
  tools/launcher/chrome_devtools_cockpit_proxy.py tests/test_browser_cockpit_proxy.py tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json
```

Accepted hits only:

- upstream argv construction appends the fresh runtime `--browser-url`;
- tests assert the runtime `--browser-url` passed to upstream;
- `close_upstream(upstream)` remains inside `UpstreamManager.stop()`.

Process cleanup:

```bash
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|fake_upstream|chrome_devtools_cockpit_proxy.py" || true
```

Observed result: only the process-check command and `rg` matched.

## Test Plan

Run the first new lazy-list test before implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_initialize_and_tools_list_do_not_start_upstream_without_browser_url
```

Expected before implementation: fail because proxy requires `--browser-url` or starts upstream for `tools/list`.

Run the first-call lazy-start test before implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_first_tools_call_ensures_browser_and_starts_upstream
```

Expected before implementation: fail because the proxy has no ensure/reload path and still expects a fixed browser URL.

Run the focused proxy suite after implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy
```

Expected after implementation: pass.

Run syntax checks:

```bash
python3 -m py_compile tools/launcher/chrome_devtools_cockpit_proxy.py
git diff --check
```

Expected after implementation: no output from `git diff --check`.

## Cleanup Requirements For Service-Starting Tests

- Fake upstream subprocesses must be started with their own process group or be directly waited by the proxy test helper.
- `_run_proxy` must kill the proxy process group on timeout.
- Fake ensure helpers must only mutate temporary `instance.json` files.
- After focused tests, run:

```bash
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|fake_upstream|chrome_devtools_cockpit_proxy.py|chrome-devtools-mcp" || true
```

Expected after implementation: no process attributable to this phase remains; unrelated pre-existing browser/MCP processes must be explicitly classified if they appear.

## Residue Search Terms For This Phase

```bash
rg -n -- "--browser-url|required=True|run_proxy\\(upstream_argv|tools/list.*forward|close_upstream\\(upstream\\)" \
  tools/launcher/chrome_devtools_cockpit_proxy.py tests/test_browser_cockpit_proxy.py tools/launcher/assets/chrome-devtools-mcp-1.1.1-tools.json
```

Accepted hits after this phase:

- `--browser-url` may remain only in upstream argv construction and test assertions that prove first `tools/call` passes the fresh runtime URL to upstream.
- `tools/list` forwarding language may remain only in removed-history comments if none are live; no live code should forward `tools/list` to upstream.

## Phase Acceptance Checklist

- [x] Proxy CLI is portless.
- [x] `initialize` is local and does not start upstream.
- [x] `notifications/initialized` is local before upstream exists.
- [x] `tools/list` is local and does not start upstream.
- [x] First forwarded `tools/call` ensures browser runtime and starts upstream with fresh browser URL.
- [x] Existing cockpit mutation and response patching behavior remains covered.
- [x] Upstream external exit does not kill the proxy.
- [x] Later tool call restarts upstream.
- [x] Focused proxy tests pass.
- [x] Python syntax check passes.
- [x] Phase residue scan has only accepted hits.

## Plan Self-Review

- Memo coverage: this phase maps to Task 4 and completes the proxy side of Task 2.
- Test mapping: local initialize/tools-list, first-call ensure/start, restart after upstream exit, and existing cockpit behavior are covered by focused proxy tests.
- Process cleanup: fake upstream processes are owned by proxy test helpers and killed on timeout.
- Rebuild-forward check: the fixed-browser-url proxy mode is removed instead of preserved behind a flag.
- Boundary check: changes stay inside the browser cockpit proxy and its test file, with a static asset under launcher browser assets.

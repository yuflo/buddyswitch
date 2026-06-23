# Browser Tool Page Limit Development Plan

Date: 2026-06-23
Source memo: `docs/memo/2026-06-23-browser-tool-page-limit.md`

## Goal

Add one shared CDP page-count gate and apply it to both browser-opening paths:

- `search.open_browser` in `scripts/env/tools/search/_impl.py`;
- `chrome-devtools-cockpit` `new_page` in `tools/launcher/chrome_devtools_cockpit_proxy.py`.

The change is complete only when the tests in `docs/spec/2026-06-23-browser-tool-page-limit-test-plan.md` pass and final review confirms no prompt-only or compatibility-layer workaround was added.

## Architecture

Create `scripts/env/cdp_browser_session.py` as the single low-level browser-session helper. It should know only how to read CDP `/json/list`, count page targets, detect exact URL reuse, and evaluate page-open gating. It must not import env tool modules, launcher prompt modules, role instructions, task objects, or product object repositories.

Callers translate the structured gate result into their own response shape:

- `search.open_browser` returns env.tool success or rejection payloads.
- `chrome_devtools_cockpit_proxy.py` returns JSON-RPC tool responses and decides whether to forward to upstream.

## Constants And Shared Contract

In `scripts/env/cdp_browser_session.py` define:

```python
BROWSER_PAGE_LIMIT = 16
BROWSER_PAGE_HINT_THRESHOLD = 8
BROWSER_PAGE_HINT_TEMPLATE = "Browser pages: {count}/16. Reuse or close pages before opening many more."
BROWSER_PAGE_LIMIT_BLOCK_TEXT = "Blocked: browser page limit reached (16/16). Close or reuse existing pages, then retry opening this URL."
```

Use dataclasses or typed dictionaries for the helper result. Keep the result concrete:

```python
kind: "allow" | "reuse" | "block" | "verification_failed"
page_count: int | None
page_limit: int
projected_page_count: int | None
target_id: str | None
target_url: str
message: str | None
```

The helper API should be:

```python
def evaluate_page_open_gate(browser_url: str, target_url: str, timeout_seconds: float = 3.0) -> BrowserPageOpenGate:
    ...
```

Implementation requirements:

- read `GET {browser_url}/json/list` with proxy disabled;
- require the payload to be a JSON list;
- count rows whose `type` is exactly `"page"`;
- match duplicate rows whose `url` is exactly the requested target URL;
- if duplicate exists, return `reuse` regardless of count;
- if count is at least `16`, return `block`;
- otherwise return `allow` with `projected_page_count=count + 1`;
- expose `hint_text()` or equivalent only when projected count is at least `8`.

## TDD Tasks

### Task 1: Add `search.open_browser` page-gate tests

Modify `tests/test_search_env_tool.py`.

1. Extend the fake CDP handler to serve `/json/list`.
   - State key: `targets`.
   - Default target list: empty list.
   - If state key `list_fail` is true, return HTTP 500.
   - If state key `list_payload` exists, return that value.
   - Record every `/json/list` request in `state["requests"]`.

2. Add tests from the search section of the test plan:
   - below threshold no hint;
   - allowed open reaching `8/16` includes canonical hint;
   - `16/16` new target blocks with `E_SEARCH_BROWSER_PAGE_LIMIT_REACHED`;
   - `16/16` exact duplicate reuses without opening;
   - `/json/list` failure is explicit and does not open.

3. Run one focused red command:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
```

Expected before implementation: at least one new test fails because page-gate behavior does not exist.

### Task 2: Add proxy `new_page` page-gate tests

Modify `tests/test_browser_cockpit_proxy.py`.

1. Add a lightweight fake CDP list server helper in the test file.
   - Use `HTTPServer(("127.0.0.1", 0), handler)`.
   - Register `server.shutdown`, `thread.join`, and `server.server_close` cleanup.
   - Do not start Chrome or launcher services.

2. Allow `_run_proxy` to accept a `browser_url` argument so each test can point to its fake CDP server.

3. Add tests from the proxy section of the test plan:
   - below threshold forwards with `background=true` and no hint;
   - reaching `8/16` forwards and appends canonical hint;
   - `16/16` new URL blocks locally;
   - `16/16` exact duplicate reuses locally;
   - list failure blocks locally with explicit text;
   - existing focus-control behavior still passes.

4. Run one focused red command:

```bash
python3 -m pytest tests/test_browser_cockpit_proxy.py -q
```

Expected before implementation: at least one new test fails because proxy page-gate behavior does not exist.

### Task 3: Implement the shared helper

Create `scripts/env/cdp_browser_session.py`.

1. Implement the constants and result type.
2. Implement a proxy-disabled HTTP GET helper using `urllib.request.build_opener(ProxyHandler({}))`.
3. Implement `/json/list` parsing and validation.
4. Implement exact URL reuse and page-count gate evaluation.
5. Keep exceptions inside the helper and return `verification_failed` with a concise message.

Focused validation:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
python3 -m pytest tests/test_browser_cockpit_proxy.py -q
```

Expected after helper plus caller integration is incomplete: tests may still fail at caller response assertions, but helper import and list reads should work.

### Task 4: Integrate `search.open_browser`

Modify `scripts/env/tools/search/_impl.py`.

1. Import the shared helper constants and `evaluate_page_open_gate`.
2. After resolving `target_url` and `browser_endpoint`, call the page gate before `_open_browser_page`.
3. For `verification_failed`, return an env.tool rejection:
   - code `E_SEARCH_BROWSER_PAGE_COUNT_UNVERIFIED`;
   - `state_changed=false`;
   - `durability=none`;
   - `page_opened=false`;
   - include `browser_page_limit`, `target_url`, `browser_endpoint`, and the helper reason.
4. For `block`, return an env.tool rejection:
   - code `E_SEARCH_BROWSER_PAGE_LIMIT_REACHED`;
   - message exactly the canonical hard block text;
   - `state_changed=false`;
   - `durability=none`;
   - `page_opened=false`;
   - `browser_page_count=16`;
   - `browser_page_limit=16`;
   - `retry_guidance=Close or reuse existing browser pages, then retry opening this URL.`
5. For `reuse`, return an env.tool success:
   - `state_changed=false`;
   - `durability=none`;
   - `page_opened=false`;
   - `page_reused=true`;
   - `reused_target_id=<target id>`;
   - include `browser_page_count`, `browser_page_limit`, `target_url`, and `browser_endpoint`;
   - `mutates_product_state=false`.
6. For `allow`, call `_open_browser_page`.
   - Preserve the existing actual-open success metadata.
   - Add `browser_page_count=<projected count>` and `browser_page_limit=16`.
   - Add the canonical soft hint in `effect_summary` or `allowed_next_actions` when projected count is at least `8`.
   - Do not include the hint below threshold.
7. Keep invalid payload, invalid engine, missing browser endpoint, and CDP open failure behavior intact.

Focused validation:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
```

### Task 5: Integrate `chrome_devtools_cockpit_proxy.py`

Modify `tools/launcher/chrome_devtools_cockpit_proxy.py`.

1. Ensure `scripts/` is importable from the launcher script, then import the shared helper.
2. Thread `browser_url` into mutation logic:
   - change `mutate_tool_call(message)` to accept `browser_url`;
   - change `mutate_client_message(message)` to accept `browser_url`;
   - call from `run_proxy(upstream_argv, browser_url)`.
3. For `new_page`:
   - preserve the existing `isolatedContext` rejection before page-gate evaluation;
   - extract `url` from arguments as a non-empty string;
   - if no URL is provided, keep current forwarding behavior with forced `background=true`;
   - evaluate page gate for URL opens.
4. For `verification_failed`, return local `tool_error_response` and do not forward.
5. For `block`, return local `tool_error_response` with canonical hard block text and do not forward.
6. For `reuse`, return local success response with short text naming the reused target id and stating no new page was opened; do not forward.
7. For `allow`, forward to upstream with `background=true`.
8. Patch upstream response text for allowed opens when projected count is at least `8`.
   - Add a small pending-hints map keyed by request id.
   - When `upstream_to_client` sees that request id, append the hint to every text content item or append a new text item.
   - Do not mark the upstream response as an error.
9. Keep `select_page`, focus RPC blocking, and tool-list schema patching behavior intact.

Focused validation:

```bash
python3 -m pytest tests/test_browser_cockpit_proxy.py -q
```

### Task 6: Update contracts and semantics only where behavior changed

Modify `tests/test_env_tool_response_contract.py` and `scripts/env/tools/search/tool.py` if needed.

1. Update fake CDP handler in response-contract tests to serve `/json/list`.
2. Preserve actual-open response contract assertions.
3. Add or adjust a reuse success assertion so no-new-page success can truthfully use `state_changed=false` and `durability=none`.
4. Update `search.open_browser` semantic text to mention page-limit blocking and exact URL reuse without changing the action id or adding new action surfaces.
5. Do not weaken general contract rules for write actions beyond the specific search reuse/no-op case.

Focused validation:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

### Task 7: Final verification and review

Run the full required focused verification:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
python3 -m pytest tests/test_browser_cockpit_proxy.py -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
git diff --check
git status --short --branch
```

Review the final diff against these acceptance checks:

- no `innerTUI`, skill, role AGENTS, prompt-router, or generic resource framework was added;
- both browser-opening paths import or call the same shared helper;
- blocked opens never call `Target.createTarget` or forward upstream;
- duplicate exact URLs are reused and do not create a new page;
- soft hint starts at `8/16`;
- hard block starts at `16/16`;
- `/json/list` verification failure is visible;
- response text is concise and includes canonical wording;
- focused tests use fake servers and controlled subprocesses only.

## Phase 1 Self-Review

- Test coverage maps back to every explicit memo requirement.
- Development tasks are ordered red-green and can be executed without inventing architecture.
- The plan keeps one shared low-level helper instead of two diverging special cases.
- The verification loop avoids broad service-starting suites until focused tests pass.
- No transition, compatibility, prompt-only, or role-instruction workaround is planned.

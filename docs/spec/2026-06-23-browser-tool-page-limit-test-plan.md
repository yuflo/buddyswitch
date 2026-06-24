# Browser Tool Page Limit Test Plan

Date: 2026-06-23
Source memo: `docs/memo/2026-06-23-browser-tool-page-limit.md`

## Goal

Browser-opening tools must make browser page pressure visible and must stop opening new pages at the hard limit. The user-facing outcome is simple:

- existing URLs are reused instead of duplicated;
- opens below the soft threshold stay quiet;
- opens at or above the soft threshold include a short resource hint;
- opens at the hard limit are blocked before any page is created;
- both browser-opening paths use the same page-count rules.

The first constants are:

```text
page_limit = 10
hint_threshold = 5
```

Canonical soft hint:

```text
Browser pages: <count>/10. Reuse or close pages before opening many more.
```

Canonical hard block:

```text
Blocked: browser page limit reached (10/10). Close or reuse existing pages, then retry opening this URL.
```

## Risk And Resource Boundary

The focused tests should use in-process fake CDP HTTP servers and fake upstream MCP processes only. They must not start the BuddySwitch launcher, real Chrome, app-server, runtime broker service, daemon, or detached browser process.

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

- run focused tests first;
- every helper that opens a socket registers shutdown and close cleanup;
- every proxy subprocess test uses timeout handling and process-group kill on timeout;
- do not run broad service-starting suites unless focused cleanup is proven.

The required verification commands for this task are safe focused test files:

```bash
python3 -m pytest tests/test_search_env_tool.py -q
python3 -m pytest tests/test_browser_cockpit_proxy.py -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
git diff --check
git status --short --branch
```

## Functional Test Matrix

### Shared CDP Browser Session Helper

These tests should be added in the smallest existing focused file that can exercise the helper without a real browser, preferably through the caller tests rather than a separate broad suite.

1. Page snapshot counts only CDP targets with `type == "page"`.
2. Duplicate detection matches the exact requested target URL and returns the existing target id.
3. Gate result is `allow` when current page count is below the hard limit and the target URL is not already open.
4. Gate result is `reuse` when the target URL is already open, including at `10/10`.
5. Gate result is `block` when page count is `10/10` and the target URL is not already open.
6. Gate result records a verification failure when `/json/list` cannot be read or does not return a JSON list; callers must not silently claim page-count enforcement succeeded.

### `search.open_browser`

Add focused tests to `tests/test_search_env_tool.py`.

1. Below hint threshold, `search.open_browser` opens normally without the soft hint.
   - Fake `/json/list` returns three `type=page` targets with different URLs.
   - Call `search.open_browser` for a new query URL.
   - Assert `ok=true`, `page_opened=true`, `state_changed=true`, `browser_page_count=4`, `browser_page_limit=10`.
   - Assert response text does not contain `Browser pages:`.
   - Assert exactly one `Target.createTarget` RPC happened with `background=true`.

2. Allowed open that reaches `5/10` includes the canonical soft hint.
   - Fake `/json/list` returns four page targets.
   - Call `search.open_browser` for a new target.
   - Assert response contains `Browser pages: 5/10. Reuse or close pages before opening many more.`
   - Assert the page was opened once.

3. Hard limit blocks a new URL before `Target.createTarget`.
   - Fake `/json/list` returns ten page targets with different URLs.
   - Call `search.open_browser` for a new target.
   - Assert `ok=false`, `error.code=E_SEARCH_BROWSER_PAGE_LIMIT_REACHED`, `state_changed=false`, `durability=none`, `page_opened=false`, `browser_page_count=10`, `browser_page_limit=10`.
   - Assert `retry_guidance=Close or reuse existing browser pages, then retry opening this URL.`
   - Assert no websocket RPC request happened.

4. Hard limit reuses an exact existing URL instead of blocking or opening.
   - Fake `/json/list` returns ten page targets, including the exact target URL.
   - Call `search.open_browser` for that target.
   - Assert `ok=true`, `page_opened=false`, `page_reused=true`, `reused_target_id` matches the fake target.
   - Assert `state_changed=false`, `durability=none`.
   - Assert no websocket RPC request happened.

5. Page-list verification failure is explicit and does not pretend enforcement happened.
   - Fake `/json/list` returns HTTP 500 or non-list JSON.
   - Call `search.open_browser`.
   - Assert `ok=false`, `state_changed=false`, `page_opened=false`.
   - Assert the error explains browser page-count verification failure.
   - Assert no websocket RPC request happened.

6. Existing search behavior stays intact.
   - Query encoding for all supported engines still reaches `Target.createTarget`.
   - Missing browser endpoint and invalid port rejections still use the existing browser-unavailable path.
   - CDP create-target failure after an allowed gate still returns `E_SEARCH_BROWSER_OPEN_FAILED`.

### `chrome-devtools-cockpit` Proxy `new_page`

Add focused tests to `tests/test_browser_cockpit_proxy.py`.

1. Below hint threshold, `new_page` forwards with `background=true`.
   - Fake `/json/list` returns three existing page targets.
   - Call proxy tool `new_page` with a new URL.
   - Assert upstream receives one call and `arguments.background is True`.
   - Assert response does not include `Browser pages:`.

2. Allowed `new_page` that reaches `5/10` appends the canonical soft hint.
   - Fake `/json/list` returns four page targets.
   - Call proxy tool `new_page` with a new URL.
   - Assert upstream receives the call with `background=true`.
   - Assert the returned text contains `Browser pages: 5/10. Reuse or close pages before opening many more.`

3. Hard limit blocks locally and does not forward.
   - Fake `/json/list` returns ten page targets with different URLs.
   - Call proxy tool `new_page`.
   - Assert no upstream calls were written.
   - Assert local result has `isError=true`.
   - Assert text equals or contains the canonical hard block text.

4. Hard limit duplicate URL reuses locally and does not forward.
   - Fake `/json/list` returns ten page targets including the exact URL.
   - Call proxy tool `new_page` for that exact URL.
   - Assert no upstream calls were written.
   - Assert local result has `isError` absent or false.
   - Assert text mentions the existing page target id and says no new page was opened.

5. Verification failure blocks locally with explicit text.
   - Fake `/json/list` returns HTTP 500 or malformed JSON.
   - Call proxy tool `new_page`.
   - Assert no upstream calls were written.
   - Assert local result has `isError=true`.
   - Assert text mentions browser page-count verification failure.

6. Existing focus-control behavior still holds.
   - `select_page` still forces `bringToFront=false`.
   - focus RPC methods still return RPC errors.
   - `new_page` with `isolatedContext` is rejected before any page gate forwarding.
   - tool list descriptions are still patched.

### Env Tool Response And Semantic Contracts

Update `tests/test_env_tool_response_contract.py` only where the existing contract assumes every `search.open_browser` success mutates browser session state.

1. Existing actual-open success still matches the declared transient action semantics.
2. Reuse success is explicitly a no-new-page result:
   - `page_opened=false`;
   - `page_reused=true`;
   - `state_changed=false`;
   - `durability=none`;
   - `mutates_product_state=false`.
3. Hard-limit rejection follows the general rejection contract and reports no page opened.

Update semantic coverage only if the `search.open_browser` action description needs to mention reuse, page-limit blocking, and page-count hints. Do not weaken semantic tests to accommodate false response metadata.

## Review Checklist

- The tests are behavior-first and derived from the memo requirements, not from an implementation shortcut.
- Both browser-opening entry points are covered.
- Duplicate URL reuse and hard-limit blocking are tested separately.
- Verification failure is visible and does not silently open a page.
- Existing focus-control behavior remains covered.
- No planned test starts persistent launcher or browser services.

# Phase 06 Search Open Browser Ensure

## Phase Objective

Make `search.open_browser` lazily ensure the actor browser runtime before opening or reusing a page. The tool must reload `instance.json` after host ensure, compute the endpoint internally, preserve page gate/open/TTL behavior, and stop exposing `browser_endpoint` or `browser_url` in ordinary actor-facing payloads.

This phase covers memo Task 7.

## Exact Source Files To Modify

- `scripts/env/tools/search/_impl.py`
- `tests/test_search_env_tool.py`
- `tests/test_env_tool_response_contract.py`

## Tests To Add Or Update

- Replace the missing-port rejection test with a test where:
  - `browser_port` starts as `None`;
  - fake host ensure updates `instance.json` to the fake CDP port;
  - `search.open_browser` reloads the file and opens the page.
- Add ensure-failure test:
  - host ensure returns non-zero;
  - response code is `E_SEARCH_BROWSER_ENSURE_FAILED`;
  - `state_changed=false`, `page_opened=false`;
  - no `browser_endpoint` or `browser_url` appears anywhere in the response.
- Update endpoint leak tests:
  - open success has no endpoint keys;
  - reuse success has no endpoint keys;
  - open failure/page-count/page-limit/lifecycle rejections have no endpoint keys.

## Implementation Steps

1. Add failing ensure-on-demand and ensure-failure tests in `tests/test_search_env_tool.py`.
2. Update existing endpoint leak assertions in `tests/test_search_env_tool.py` and `tests/test_env_tool_response_contract.py`.
3. Add search helper functions:
   - host ensure command construction;
   - ensure execution with test override support;
   - fresh instance payload reload;
   - recursive endpoint leak assertion helper for tests.
4. Change `open_browser_for_active_instance`:
   - validate request and boundary first;
   - call host ensure before `_browser_endpoint`;
   - reload `instance.json`;
   - compute endpoint from fresh payload;
   - continue existing page gate, reuse, open, and TTL paths.
5. Remove `browser_endpoint` from ordinary actor-facing open-browser success and rejection extras.
6. Run focused search tests, response contract tests, syntax, residue, and diff checks.

## Test Plan

Red checks before implementation:

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_ensures_browser_when_port_missing
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_ensure_failure_without_endpoint_leak
```

Expected before implementation: fail because missing `browser_port` returns `E_SEARCH_BROWSER_UNAVAILABLE` and no host ensure path exists.

Observed red results:

- missing-port test failed with `E_SEARCH_BROWSER_UNAVAILABLE`;
- ensure-failure test failed because the code was still `E_SEARCH_BROWSER_UNAVAILABLE` instead of `E_SEARCH_BROWSER_ENSURE_FAILED`.

Green checks after implementation:

```bash
python3 -m unittest tests.test_search_env_tool tests.test_env_tool_response_contract
python3 -m py_compile scripts/env/tools/search/_impl.py
git diff --check
```

Observed green results:

- `tests.test_search_env_tool tests.test_env_tool_response_contract` ran 43 tests and passed.
- `python3 -m py_compile scripts/env/tools/search/_impl.py` passed.
- `git diff --check` produced no output.

Process cleanup check:

```bash
ps -axo pid,ppid,rss,command | rg "\\.worktrees/fea-tool|fake-search-browser-ensure|cdp_background_page.py" || true
```

Observed result: only the process-check command and `rg` matched.

## Residue Search Terms

```bash
rg -n "E_SEARCH_BROWSER_UNAVAILABLE|E_SEARCH_BROWSER_ENSURE_FAILED|browser_endpoint|browser_url|instance browser_port is missing|env browser ensure" \
  scripts/env/tools/search/_impl.py tests/test_search_env_tool.py tests/test_env_tool_response_contract.py
```

Accepted hits after this phase:

- `browser_endpoint` local variable names only inside implementation;
- `browser_url` only in low-level CDP helper argument names or status metadata if status intentionally remains diagnostic;
- tests asserting no endpoint leak;
- `E_SEARCH_BROWSER_UNAVAILABLE` for profile/invalid-port/status cases;
- `E_SEARCH_BROWSER_ENSURE_FAILED` for ensure failure.

Observed residue result: accepted hits only; endpoint terms remain as internal variable names and no-leak assertions.

## Phase Acceptance Checklist

- [x] Missing `browser_port` in `search.open_browser` calls host ensure.
- [x] `search.open_browser` reloads `instance.json` after ensure.
- [x] Host ensure failure returns `E_SEARCH_BROWSER_ENSURE_FAILED`.
- [x] Open success does not expose `browser_endpoint` or `browser_url`.
- [x] Reuse success does not expose endpoint internals.
- [x] Open/page-count/page-limit/lifecycle rejections do not expose endpoint internals.
- [x] Existing background open, page limit, reuse, and TTL refresh tests remain green.
- [x] Focused search and response-contract tests pass.
- [x] Syntax, residue, and diff checks pass.

## Plan Self-Review

- Memo coverage: maps to Task 7 ensure-then-open, ensure failure, fresh reload, and endpoint leak removal.
- Boundary check: implementation stays inside search env.tool projection and does not move browser lifecycle ownership out of launcher/browser slice.
- TDD check: missing-port and ensure-failure tests are observed red first.
- Rebuild-forward check: old missing-port-as-unavailable behavior is replaced, not preserved as an alternate open-browser path.

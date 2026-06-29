# Browser New Page TTL Registration Contract

Date: 2026-06-29

## Current Contract

`chrome-devtools-cockpit.new_page` must reconcile the browser target list after the upstream tool returns. If Chrome created exactly one new top-level page target, BuddySwitch registers that target with the existing browser page lifecycle even when the upstream response is an error.

For a created page:

- successful lifecycle registration appends the existing browser idle refresh hint to the upstream response;
- lifecycle registration failure closes the newly created target and returns a lifecycle error;
- ambiguous created targets return a lifecycle error instead of silently leaving unmanaged pages;
- no created target preserves the upstream response.

This keeps one path:

```text
new_page -> pre-call target snapshot -> upstream call -> post-call target reconciliation -> lifecycle registration or cleanup
```

## Boundary

- Lifecycle ownership stays in `tools/launcher/chrome_devtools_cockpit_proxy.py` and `scripts/env/cdp_browser_lifecycle.py`.
- The daemon does not scan browser targets.
- No Chrome target websocket listener or pending retry queue is introduced.
- `search.open_browser` is unchanged.
- Existing `select_page` and current-page scoped tools still refresh only after successful upstream responses.

## Verification Commands

```bash
python3 -m unittest tests.test_browser_cockpit_proxy
python3 -m unittest tests.test_cdp_browser_session tests.test_browser_page_expired_handler
git diff --check
```

## Acceptance Evidence

To accept the merge, the focused browser cockpit proxy test file must pass with:

- upstream `new_page` error plus one created target registering lifecycle state;
- ambiguous created targets returning lifecycle error;
- successful `new_page`, reuse, registration failure cleanup, and page-scoped refresh behavior still passing.

## Merge Verification 2026-06-29

```text
python3 -m unittest tests.test_browser_cockpit_proxy
Ran 24 tests in 14.724s
OK

python3 -m unittest tests.test_cdp_browser_session tests.test_browser_page_expired_handler
Ran 25 tests in 2.410s
OK

python3 -m unittest tests.test_search_env_tool
Ran 28 tests in 8.993s
OK

git diff --check
no output
```

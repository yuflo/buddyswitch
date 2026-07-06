# Browser TTL MCP Session Scope Rebuild Plan

Date: 2026-07-05

## 1. Task Goal

Rebuild the browser TTL page cleanup path so an expired actor browser page is closed through `chrome-devtools-mcp` using the page identity visible inside the same MCP session that performs the close.

The target outcome is:

```text
actor opens/uses page through chrome-devtools-cockpit
-> BuddySwitch records lifecycle projection
-> TTL expires
-> TTL handler resolves the real page inside one MCP session
-> TTL handler closes that resolved page through MCP
-> TTL handler verifies the page is gone
-> BuddySwitch clears projection
-> browser release can reclaim owned resources
```

## 2. Principle Alignment

This plan follows the repo `AGENTS.md` and the `docs/bitter` principles:

- `2026-05-26-test-resource-lifecycle-principles.md`: resource tests must prove host processes return to baseline, not only that assertions pass.
- `2026-06-25-end-to-end-contract-slice-principles.md`: the acceptance target is a real actor browser loop crossing cockpit, daemon TTL, MCP close, release, and process cleanup.
- `2026-06-02-residue-cleanup-principles.md`: no live surface should continue teaching stale cross-session pageId semantics.
- `2026-06-02-wrong-boundary-narrowness-principles.md`: the fix must be at the TTL/MCP session boundary, not a narrow symptom patch.
- `2026-06-25-built-in-product-interface-principles.md`: BuddySwitch owns lifecycle semantics; MCP is the browser operation interface.
- `2026-05-18-tool-skill-layering-principles.md`: runtime behavior and test proof must carry the contract, not prompts.

## 3. Confirmed Root Cause

Real CLI actor test proved the failure is pageId scope mismatch, not a broken MCP `close_page` primitive.

Observed actor cockpit session:

```text
1: about:blank
2: Google search page [selected]
BuddySwitch projection: current_page_id=2, selected_page_id=2
```

Observed TTL handler temporary MCP session against the same Chrome endpoint:

```text
1: Google search page [selected]
2: about:blank
```

Current TTL handler uses the stored `page_id=2` in a different MCP process. It sees `pageId=2` as `about:blank`, decides identity mismatch, does not call `close_page` for the Google page, but still clears `page_idle.json` and schedules release.

Result:

```text
page_idle.json cleared
real Google Chrome page remains
browser.cockpit.release skips with real_user_page_present
browser_port remains set
```

The actor's normal `chrome-devtools-cockpit.close_page(pageId=2)` succeeds in the same cockpit MCP session. Therefore `pageId` must be treated as a session-local MCP handle.

## 4. Architecture Target

Current architecture remains valid:

```text
browser use surface = chrome-devtools-cockpit
page operation truth = upstream chrome-devtools-mcp selected/pageId within one MCP session
BuddySwitch = lifecycle projection and resource ownership
Chrome process release = browser_runtime_manager / browser_cockpit_release
```

This rebuild does not change the select/current unification architecture. It fixes the asynchronous TTL close boundary.

New invariant:

```text
MCP pageId is session-local.
BuddySwitch may persist pageId as lifecycle projection, but TTL close must resolve a fresh close pageId inside the same MCP session that calls close_page.
```

## 5. Non-Goals

Do not do these:

- Do not reintroduce CDP `Target.closeTarget` or `target_id` as the browser page cleanup path.
- Do not restore old `search.open_browser`, `browser.open_url`, or broker browser-open data paths.
- Do not maintain dual cleanup branches such as "try MCP pageId, fallback to CDP target".
- Do not change cockpit `search_page`, `new_page`, `select_page`, or page-scoped operation semantics unless a failing test proves a direct regression.
- Do not clear `page_idle.json` merely because a stale stored pageId mismatches the temporary MCP session pageId.

## 6. Required Code Direction

### 6.1 Rebuild TTL Handler MCP Execution As One Session

Modify:

- `tools/launcher/browser_page_expired_handler.py`

Replace the current split calls:

```text
list_mcp_pages() -> starts MCP process A
close_mcp_page() -> starts MCP process B
```

with one session-scoped operation:

```text
with temporary MCP session:
  list_pages
  resolve page from recorded identity
  close_page(resolved_pageId)
  list_pages
  verify target page disappeared
```

The handler can keep using a short-lived MCP process, but list, close, and verify must happen before that process exits.

### 6.2 Resolve By Recorded Page Identity, Not Stored PageId First

Recorded identity lives in:

```text
runtime/browser/page_idle.json
pages[stored_page_id].url
pages[stored_page_id].title
```

TTL close resolution must:

1. Read the recorded page state for the expired stored page id.
2. Call MCP `list_pages` inside the close session.
3. Find candidates by recorded URL equality.
4. Use title only as a secondary guard when both recorded and observed titles are present.
5. If exactly one candidate matches, close that candidate's current-session `pageId`.
6. If no candidate matches, treat the page as already gone and then clear the projection.
7. If multiple candidates match, do not close anything; return a failed/retryable diagnostic.

The important change is:

```text
stored page_id is a projection key
resolved pageId is the temporary MCP session close handle
```

### 6.3 Verify Before Forgetting State

After `close_page(resolvedPageId)`, call `list_pages` again in the same MCP session.

Only clear BuddySwitch projection if:

```text
the recorded URL is no longer present in list_pages
```

If the page is still present:

```text
return failed/retryable
keep page_idle.json
do not schedule browser.cockpit.release
```

### 6.4 Replace Current Wrong Mismatch Behavior

Current wrong behavior:

```text
observed pageId exists but URL/title mismatch
-> forget tracked page
-> schedule release
```

Required behavior:

```text
stored pageId mismatch in temporary MCP session
-> resolve by recorded URL/title across all listed pages
-> close resolved current-session pageId
-> verify gone
-> then forget
```

If the URL/title cannot identify a unique page, keep the projection and fail visibly.

## 7. Test Plan Before Development

Add focused regression tests in:

- `tests/test_browser_page_expired_handler.py`

Required test cases:

1. `test_expiry_resolves_session_local_page_id_by_recorded_url`

   Setup:

   ```text
   page_idle stored page_id=2 url=https://example.com/search
   temporary MCP list_pages returns:
     pageId=1 url=https://example.com/search
     pageId=2 url=about:blank
   ```

   Expected:

   ```text
   close_page called with pageId=1
   page_idle state is cleared only after post-close list_pages no longer contains the URL
   release is scheduled
   ```

2. `test_expiry_does_not_forget_when_close_verification_still_sees_page`

   Setup:

   ```text
   pre-close list_pages resolves pageId=1 for recorded URL
   post-close list_pages still contains recorded URL
   ```

   Expected:

   ```text
   handler result = failed
   page_idle still contains original stored page_id
   release not scheduled
   ```

3. `test_expiry_does_not_close_or_forget_when_recorded_url_matches_multiple_pages`

   Setup:

   ```text
   pre-close list_pages returns two pages with same recorded URL
   ```

   Expected:

   ```text
   close_page not called
   page_idle remains
   release not scheduled
   handler result = failed
   ```

4. `test_expiry_forgets_when_recorded_page_already_absent`

   Setup:

   ```text
   page_idle stored page_id=2 url=https://example.com/search
   temporary MCP list_pages returns only about:blank
   ```

   Expected:

   ```text
   close_page not called
   page_idle cleared
   release scheduled
   ```

5. `test_expiry_uses_one_mcp_session_for_list_close_verify`

   Setup:

   ```text
   fake MCP session records operation order
   ```

   Expected:

   ```text
   operations == ["list_pages", "close_page", "list_pages"]
   all operations happen on one session object/process abstraction
   ```

Existing tests that assert mismatch clears state must be rewritten because that behavior is now the bug.

## 8. Implementation Phases

### Phase 1: Focused Regression Tests

Create failing tests for the session-local pageId bug before touching runtime logic.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_page_expired_handler.py
```

Expected before implementation:

```text
new regression tests fail
existing unrelated tests keep their previous pass/fail behavior
```

### Phase 2: Session-Scoped MCP Helper

In `tools/launcher/browser_page_expired_handler.py`, introduce a small local helper that owns one MCP process lifecycle for one TTL close attempt.

The helper must expose:

```text
list_pages()
close_page(page_id)
close()
```

It must preserve existing initialize/initialized/tool-call behavior and existing timeout/error handling.

### Phase 3: Resolve-Close-Verify TTL Flow

Update `_auto_close` to:

```text
read recorded page state
open one MCP session
list pages
resolve current-session pageId by recorded identity
close resolved pageId when unique
list pages again
verify recorded URL absent
forget projection only after success or already-absent
schedule release only after projection is empty
```

### Phase 4: Focused Tests Green

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_page_expired_handler.py
```

Expected:

```text
all browser_page_expired_handler tests pass
```

### Phase 5: Broader Browser Regression

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_cdp_browser_session.py tests/test_browser_page_expired_handler.py tests/test_browser_lazy_release_integration.py tests/test_repo_consistency.py
```

Expected:

```text
all focused browser/session/resource tests pass
```

### Phase 6: Real CLI Actor Acceptance

Run the real CLI path defined in:

```text
docs/memo/2026-07-05-browser-ttl-mcp-session-scope-acceptance-plan.md
```

Expected:

```text
actor cockpit opens page
TTL closes real page
page_idle clears
release clears browser_port
no actor-owned Chrome/MCP/watchdog process remains
```

## 9. Residue Checks

After implementation, run live-source scans:

```bash
rg -n 'Target\\.closeTarget|close_page_target|current_target_id|page_id_to_target_id|browser\\.open_url|search__open_browser|search\\.open_browser' scripts tools/launcher/assets framework/contracts buddyswitch/skills tools/launcher tests -S
```

Allowed hits:

- historical docs;
- explicit tests asserting legacy absence;
- release/browser status code that reads `/json/list` for process protection, not page close.

Disallowed hits:

- live browser page cleanup through CDP target close;
- old search/browser open route;
- page lifecycle truth based on `current_target_id`.

## 10. Definition Of Done

The task is done only when all are true:

1. TTL handler no longer uses a stored pageId as a cross-MCP-session close handle.
2. TTL close resolves, closes, and verifies inside one MCP session.
3. BuddySwitch does not clear `page_idle.json` unless the recorded page is gone or verified closed.
4. Resource release no longer skips due to a page that TTL should have closed.
5. Automated focused and broader browser tests pass.
6. Real CLI actor acceptance proves browser page and process resources return to baseline.
7. Test cleanup proves no actor-owned Chrome, MCP, telemetry watchdog, broker, app-server, or daemon process remains.

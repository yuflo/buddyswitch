# Browser Cockpit Open Current Projection Plan

Date: 2026-07-05
Status: planning memo; no implementation in this document.

## Goal

Make `chrome-devtools-cockpit.search_page` and `chrome-devtools-cockpit.new_page` establish BuddySwitch `current_page_id` / `selected_page_id` immediately after a successful upstream MCP page open.

The product contract is:

```text
actor calls search_page/new_page
  -> cockpit proxy forwards to upstream chrome-devtools-mcp new_page
  -> upstream returns the selected MCP pageId
  -> BuddySwitch records that same pageId as current/selected resource projection
  -> TTL tracks that same pageId
  -> list_pages shows the same selected/current page without requiring an extra select_page
```

This is a focused completion of the current cockpit page unification rebuild. It is not a new browser architecture.

## Scope Confirmation

The current optimization target is exactly this:

```text
open page = current page = selected page = actor-used page = TTL-tracked page
```

After `select_page`, this is already true. The remaining gap is:

```text
search_page/new_page opens a page and upstream marks it [selected],
but BuddySwitch projection remains empty until explicit select_page.
```

This task must close that gap.

## Non-Negotiable Requirements

- No `search.open_browser` revival.
- No `search__open_browser` revival.
- No `browser.open_url` revival.
- No local actor page opening through CDP `Target.createTarget`.
- No actor page cleanup through CDP `Target.closeTarget`.
- No `target_id` bridge, `current_target_id`, or `page_id_to_target_id` truth.
- No double-path compatibility where `search_page/new_page` can choose between upstream MCP and local CDP/browser-session opening.
- No prompt-only fix. Tool response semantics and persisted projection must prove the behavior.
- No broad service-starting test run without cleanup and residue checks.

## Bitter Principles Applied

From `docs/bitter`:

- `2026-06-25-end-to-end-contract-slice-principles.md`: component tests are not enough; acceptance must prove the user-visible browser loop.
- `2026-06-25-built-in-product-interface-principles.md`: page resource semantics belong to BuddySwitch product state, while cockpit/list/select are projections of that state and upstream MCP state.
- `2026-05-18-tool-skill-layering-principles.md`: the tool response must say the actual lifecycle effect; agents should not infer hidden behavior from `ok=true`.
- `2026-06-02-residue-cleanup-principles.md`: behavior proof and live-surface residue proof are both required.
- `2026-05-26-test-resource-lifecycle-principles.md`: real CLI/browser validation must stop/delete actor instances and verify host cleanup.
- `2026-06-02-wrong-boundary-narrowness-principles.md`: do not add another shared special-case browser path; keep the shared boundary stable and put the projection update in the cockpit/browser lifecycle owner.
- `2026-05-28-parallel-change-boundary-principles.md`: keep this change scoped to the cockpit page projection boundary; do not bundle unrelated launcher or search-tool cleanup.

## Current Evidence

Real CLI actor recheck:

- Actor: `act-market-838e05b491c1`
- Input allowed only `chrome-devtools-cockpit.search_page` and `chrome-devtools-cockpit.list_pages`.
- No `select_page`, `take_snapshot`, `search`, `search__request`, or `search__open_browser` was called.
- `search_page` succeeded and upstream returned:

```text
pageId 2: https://www.google.com.hk/search?q=BuddySwitch+pageId+current+projection+recheck... [selected]
```

- `list_pages` succeeded but BuddySwitch projection showed:

```text
current_page_id: <none>
selected_page_id: <none>
pages: <none>
```

Observed effect:

```text
upstream selected page exists
BuddySwitch current/selected projection is empty
TTL has no page to track
list_pages can schedule browser.cockpit.release with reason page_idle_empty
```

## Current Code Audit

### Opening path

`tools/launcher/chrome_devtools_cockpit_proxy.py`

- `search_page` builds a search URL and rewrites the call to upstream `new_page` with `background=true`.
- `new_page` rewrites to upstream `new_page` with `background=true`.
- Both return response metadata with `{"kind": "new_page"}`.

Relevant current lines:

```text
tools/launcher/chrome_devtools_cockpit_proxy.py:424-454
```

### Response handling gap

`patch_tool_response_page_use_metadata()` handles:

- `list_pages`: appends BuddySwitch resource projection and schedules release if no tracked pages.
- `select_page`: calls `_refresh_current_idle_hint(...)`.
- page-scoped tools: refresh the already-known selected page.

It does not handle:

```text
kind == "new_page"
```

Relevant current lines:

```text
tools/launcher/chrome_devtools_cockpit_proxy.py:584-650
```

### Lifecycle helper already exists

`scripts/env/cdp_browser_lifecycle.py` already provides the correct state transition:

- `refresh_current_page_idle(...)`
- schedules `browser.page.expired` with `payload: {"page_id": ...}`
- writes `pages[page_id]`
- writes `current_page_id`
- writes `selected_page_id`

Relevant current lines:

```text
scripts/env/cdp_browser_lifecycle.py:308-337
```

So this is not a missing lifecycle primitive. It is a missing call site after successful open.

### Test gap

Existing tests prove:

- `new_page` forwards upstream with `background=true`.
- `search_page` forwards upstream `new_page`.
- `select_page` marks the MCP pageId current.
- `list_pages` shows projection when projection already exists.
- `list_pages` with no tracked pages schedules `browser.cockpit.release`.

Missing tests:

- `new_page` success marks the returned upstream selected pageId current.
- `search_page` success marks the returned upstream selected pageId current.
- `search_page/new_page -> list_pages` does not report `<none>` projection and does not schedule `page_idle_empty`.
- `new_page` success without parseable selected pageId returns a lifecycle warning and does not invent a fake current page.

## Root Cause

The rebuild moved page opening to upstream MCP, but only `select_page` was wired to BuddySwitch current-page projection.

The missing link is:

```text
successful upstream new_page response
  -> parse returned selected MCP pageId
  -> refresh BuddySwitch current page idle
```

This is why explicit `select_page` fixes the state, while opening alone does not.

## Architecture Impact

The architecture is not invalidated.

The target architecture remains:

```text
page-use truth: upstream chrome-devtools-mcp pageId / selected page
BuddySwitch state: resource projection for TTL and cleanup
```

The fix should strengthen that architecture:

- source of page identity stays upstream MCP `pageId`;
- BuddySwitch records only projection and TTL metadata;
- no CDP target bridge is reintroduced;
- no browser-session current target path is reintroduced.

## Implementation Plan

### Phase 1: Lock the Failure With Focused Tests

Files:

- Modify: `tests/test_browser_cockpit_proxy.py`

Add focused failing tests before implementation:

1. `test_new_page_success_marks_opened_selected_page_current`
   - fake upstream returns:

     ```text
     ## Pages
     1: about:blank
     2: https://example.com/new [selected]
     ```

   - assert forwarded tool name is still upstream `new_page`;
   - assert forwarded arguments still include `background: True`;
   - assert daemon schedule key is `browser.page.idle:2`;
   - assert schedule payload is `{"page_id": "2"}`;
   - assert `page_idle.json.current_page_id == "2"`;
   - assert `page_idle.json.selected_page_id == "2"`;
   - assert `page_idle.json.pages["2"].url == "https://example.com/new"`;
   - assert no CDP RPC request was made.

2. `test_search_page_success_marks_opened_selected_page_current`
   - fake upstream receives rewritten `new_page`;
   - fake upstream returns selected page `2` with the generated Google search URL;
   - assert same projection and TTL schedule as above.

3. `test_opened_page_then_list_pages_does_not_schedule_empty_release`
   - call `search_page`, then `list_pages`;
   - assert `list_pages` response contains:

     ```text
     current_page_id: 2
     selected_page_id: 2
     page_id: 2
     current: true
     selected: true
     ```

   - assert no `browser.cockpit.release` schedule with `reason: page_idle_empty` is created.

4. `test_new_page_without_selected_page_id_reports_lifecycle_warning_without_state`
   - fake upstream returns successful text with no `[selected]` pageId;
   - assert response contains a clear `Browser lifecycle warning`;
   - assert no `page_idle.json` is created;
   - assert no `browser.page.expired` schedule is created.

Run expected failing command:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_new_page_success_marks_opened_selected_page_current \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_search_page_success_marks_opened_selected_page_current \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_opened_page_then_list_pages_does_not_schedule_empty_release \
  tests/test_browser_cockpit_proxy.py::BrowserCockpitProxyTests::test_new_page_without_selected_page_id_reports_lifecycle_warning_without_state
```

Expected before implementation: fail because `kind == "new_page"` does not refresh projection.

### Phase 2: Implement Open Response Projection

Files:

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`

Implementation shape:

1. Add a helper that extracts the selected page from upstream MCP text.

   Expected source format:

   ```text
   2: https://example.com/new [selected]
   ```

   The helper should return:

   ```python
   {"page_id": "2", "url": "https://example.com/new"}
   ```

   It must not synthesize a pageId when the selected marker is missing.

2. In `patch_tool_response_page_use_metadata()`, add a `kind == "new_page"` branch after root validation and success validation.

3. On successful parse, call:

   ```python
   _refresh_current_idle_hint(
       root=root,
       page_id=selected_page["page_id"],
       target_url=selected_page.get("url"),
   )
   ```

4. Append the same lifecycle hint style used by `select_page`, for example:

   ```text
   Browser page idle refreshed: 40s.
   ```

5. On successful upstream response without parseable selected pageId, append a warning:

   ```text
   Browser lifecycle warning: opened page id was not readable from upstream new_page response; browser idle was not refreshed.
   ```

6. Do not call CDP.

7. Do not call a second browser open path.

8. Do not silently call `select_page` as a compatibility fallback.

9. Do not schedule `browser.cockpit.release` from the `new_page` branch. Release scheduling remains owned by `list_pages` when there are no tracked pages.

### Phase 3: Update Live Tool Semantics

Files:

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Test: `tests/test_browser_cockpit_proxy.py`

Update live tool descriptions so host-visible semantics match behavior:

- `new_page`: forwards upstream `new_page(background=true)` and records the returned selected MCP pageId as BuddySwitch current/selected projection.
- `search_page`: builds the search URL, forwards upstream `new_page(background=true)`, and records the returned selected MCP pageId as BuddySwitch current/selected projection.
- `list_pages`: shows upstream pageId selected state plus BuddySwitch lifecycle projection.

Keep descriptions short. Do not move workflow instructions into AGENTS or skills.

Add/adjust tests that inspect `tools/list` descriptions to catch stale live-surface text.

### Phase 4: Focused Verification

Run only focused tests first:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_browser_cockpit_proxy.py
```

Then run the lifecycle-adjacent tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider \
  tests/test_cdp_browser_session.py \
  tests/test_browser_page_expired_handler.py \
  tests/test_browser_lazy_release_integration.py \
  tests/test_repo_consistency.py
```

If any service-starting test is added or changed, run a residual process check immediately after the focused test before expanding verification.

### Phase 5: Scoped Residue Checks

Run live-surface residue checks over current behavior surfaces, not historical notes.

Required no-hit scans:

```bash
rg -n 'search__open_browser|search\.open_browser|browser\.open_url|request_runtime_broker\("browser\.open_url"' \
  scripts tools/launcher/assets framework/contracts buddyswitch/skills
```

```bash
rg -n 'current_target_id|page_id_to_target_id|Target\.createTarget|Target\.closeTarget|browser_session\.open_or_reuse_page' \
  tools/launcher scripts/env tests
```

Allowed hits must be either:

- tests that assert old residue is absent; or
- historical `docs/` material outside live surfaces.

Any live-surface stale instruction is unfinished work.

## Acceptance Plan

### Contract Sentence

```text
An actor can call chrome-devtools-cockpit.search_page or new_page, then call list_pages without select_page, and BuddySwitch shows the opened upstream MCP pageId as current/selected with active TTL tracking.
```

### Real CLI Acceptance

Create a fresh actor through CLI in a temporary `BUDDYSWITCH_SHARED_ROOT`.

Actor input:

```text
Use only chrome-devtools-cockpit.
Do not call search, search__request, search__open_browser, search.open_browser, browser.open_url, select_page, or take_snapshot.

Perform exactly:
1. chrome-devtools-cockpit.search_page query "BuddySwitch pageId open current projection acceptance" engine "google".
2. chrome-devtools-cockpit.list_pages.

Reply with opened pageId, URL, and BuddySwitch projection state.
```

Acceptance evidence must show:

- `search_page` succeeded.
- `list_pages` succeeded.
- upstream selected pageId is visible.
- BuddySwitch projection shows:

  ```text
  current_page_id: <opened pageId>
  selected_page_id: <opened pageId>
  page_id: <opened pageId>
  current: true
  selected: true
  idle_tracked: true
  ```

- `runtime/browser/page_idle.json` contains the same pageId.
- daemon state contains `browser.page.expired` for that pageId.
- daemon state does not contain a pending or delivered `browser.cockpit.release` created from `page_idle_empty` before TTL expiry.
- session log contains no `select_page` call.
- session log contains no `search__open_browser`, `search.open_browser`, `browser.open_url`, or native search tool call.

After the run:

1. Stop the actor.
2. Delete the actor.
3. Verify no actor-owned browser runtime files remain.
4. Verify process scans do not show the actor id or temp root.

### TTL Acceptance

After the open-current acceptance path:

1. Wait for the configured TTL.
2. Confirm `browser.page.expired` delivered for the opened pageId.
3. Confirm cleanup uses upstream MCP `close_page(pageId)`.
4. Confirm BuddySwitch forgets that page projection.
5. Confirm `browser.cockpit.release` happens only after tracked pages are empty.
6. Confirm `browser_port` becomes `null`.
7. Confirm stop/delete still leaves no actor-owned browser files or processes.

### Failure Acceptance

For a successful upstream `new_page` response with no parseable selected pageId:

- response must contain a lifecycle warning;
- no fake current page is recorded;
- no TTL schedule is created for an unknown page;
- subsequent `list_pages` may schedule `page_idle_empty` because there are still no tracked pages.

This failure mode is intentional. It avoids inventing a second page truth.

## Definition of Done

The task is complete only when all are true:

- `search_page/new_page` opening success immediately records the returned upstream selected MCP pageId as BuddySwitch current/selected projection.
- `list_pages` immediately after open shows aligned upstream selected state and BuddySwitch projection without explicit `select_page`.
- TTL schedule is created for the opened pageId.
- Explicit `select_page` still refreshes the same projection and remains non-activating.
- Page-scoped actions still refresh the selected/current page.
- No CDP target open/close path is reintroduced.
- No old search/browser open route is reintroduced.
- Focused automated tests pass.
- Scoped residue scans pass.
- Real CLI acceptance passes and cleans up the actor/runtime resources.

## Implementation Boundary

This plan is intentionally small at the product boundary:

```text
cockpit upstream MCP selected pageId
  -> BuddySwitch current/selected resource projection
  -> TTL schedule
```

Do not expand the task into:

- browser process manager redesign;
- search tool redesign;
- role prompt rewrite;
- broader resource lifecycle rebuild;
- generic MCP page registry;
- compatibility shims for old `target_id` state.

The current bottleneck is open-time projection synchronization. Solve that and verify it.

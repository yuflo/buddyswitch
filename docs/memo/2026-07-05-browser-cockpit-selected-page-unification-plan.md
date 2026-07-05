# Browser Cockpit Selected Page Unification Plan

Date: 2026-07-05  
Status: optimization and acceptance plan; no runtime code changed by this memo

## 1. Goal

Unify `chrome-devtools-cockpit` page truth so `select_page`, BuddySwitch `current page`, actor page use, TTL protection, and page cleanup all refer to the same page.

The single fact source must be:

```text
upstream chrome-devtools-mcp pageId / selected page
```

BuddySwitch may keep resource lifecycle projection, but it must not independently define actor current page through CDP `target_id`.

## 2. Scope

This plan targets the remaining cockpit-internal dual path:

```text
search_page/new_page
  -> BuddySwitch cockpit proxy local CDP/browser-session open
  -> current_target_id/page_idle target tracking

select_page/take_snapshot/click/evaluate/navigate/close_page
  -> upstream chrome-devtools-mcp pageId / selected page
```

The old env search browser path is not the current problem:

- `search.open_browser` / `search__open_browser` is already removed or rejected.
- runtime broker `browser.open_url` is already removed.
- `search.request` and `search.status` remain non-opening metadata/planning actions.

## 3. Required Principles Reviewed

This plan applies the following `docs/bitter` rules:

- `2026-05-18-tool-skill-layering-principles.md`: fix the tool/runtime contract layer that owns the wrong semantics; do not hide contract weakness in prompts.
- `2026-05-26-test-resource-lifecycle-principles.md`: service-starting tests must prove process, socket, marker, browser, and runtime file cleanup.
- `2026-05-28-parallel-change-boundary-principles.md`: keep one intent in this change set; do not mix search cleanup, browser lifecycle, and unrelated refactors.
- `2026-06-02-residue-cleanup-principles.md`: semantic replacement needs behavior tests and live-surface residue scans.
- `2026-06-02-wrong-boundary-narrowness-principles.md`: small fixes at the wrong boundary are still wrong; do not keep adding local special cases to the proxy.
- `2026-06-25-built-in-product-interface-principles.md`: product semantics must live in one product model, with tools as projections.
- `2026-06-25-end-to-end-contract-slice-principles.md`: unit slices are not enough; a real actor loop must prove the final page path.

## 4. Current Findings

### 4.1 Search Entry Is Already Rebuilt

Current env search only exposes `status` and `request`:

- `scripts/env/tools/search/tool.py`
- `scripts/env/tools/search/_impl.py`

`search.open_browser` now rejects as unsupported in response contract tests:

- `tests/test_env_tool_response_contract.py`

runtime broker browser methods are only:

```text
browser.acquire
browser.status
browser.release
```

`browser.open_url` is no longer dispatched in `scripts/runtime_kernel/dispatcher.py`.

### 4.2 Cockpit Still Has Two Page Truths

`tools/launcher/chrome_devtools_cockpit_proxy.py` currently intercepts:

- `search_page`
- `new_page`

and calls:

```python
browser_session.open_or_reuse_page(...)
```

That path uses `scripts/env/cdp_browser_session.py`, which opens pages through:

```text
Target.createTarget
```

The tests intentionally protect this current behavior:

- `tests/test_browser_cockpit_proxy.py::test_new_page_opens_locally_through_browser_session_without_forwarding`
- `tests/test_browser_cockpit_proxy.py::test_search_page_opens_locally_without_forwarding`

Those tests assert:

- no upstream forwarding;
- no upstream argv;
- CDP `Target.createTarget` is called;
- schedule key is based on CDP `target_id`.

### 4.3 Page Use Still Runs Through Upstream MCP

The same proxy forwards these page-use tools to upstream `chrome-devtools-mcp`:

- `list_pages`
- `select_page`
- `take_snapshot`
- `take_screenshot`
- `click`
- `type_text`
- `evaluate_script`
- `navigate_page`
- `wait_for`
- `fill`
- `press_key`
- `close_page`

`select_page` is rewritten to force:

```text
bringToFront=false
```

but after success BuddySwitch tries to translate MCP `pageId` back into CDP `target_id`.

### 4.4 TTL Still Uses CDP Target State

Current page idle state contains:

```text
current_target_id
page_id_to_target_id
targets[target_id]
```

TTL schedule payload is:

```json
{"target_id": "..."}
```

The expiry handler closes pages through:

```text
close_page_target(browser_endpoint, target_id)
-> Target.closeTarget
```

This is physically precise for CDP target id, but it is not the same as actor/MCP selected-page precision.

## 5. Root Cause

The search rebuild removed the old env `search.open_browser` route, but it stopped at the cockpit proxy boundary.

That left cockpit with this split:

```text
page opening truth  = BuddySwitch local CDP target_id
page operation truth = upstream chrome-devtools-mcp selected pageId
```

The product target is not merely "search opens through cockpit". The real target is:

```text
actor selected page
BuddySwitch current page
MCP selected page
TTL-protected page
```

must all be the same page.

## 6. Target Architecture

### 6.1 Single Page Fact Source

Use upstream `chrome-devtools-mcp` page model as the page fact source:

```text
list_pages -> pageId/page URL/title/current selected marker
select_page(pageId, bringToFront=false)
new_page(url, background=true)
close_page(pageId)
```

BuddySwitch stores only a resource projection of this MCP state:

```text
page_id
url/title snapshot if available
last_used_at
idle_expires_at
selected/current projection
```

Do not store `current_target_id` as the page-use truth.

### 6.2 Browser Process Lifecycle Boundary

`browser.acquire/status/release` stays in BuddySwitch because it owns Chrome process lifecycle:

- lazy start;
- endpoint readiness;
- owned process discovery;
- release;
- stop cleanup;
- socket and pid marker cleanup.

This boundary may verify Chrome readiness, but it must not define actor page selection/current semantics.

### 6.3 Non-Focus Requirement

Non-focus behavior stays mandatory and must be expressed at the MCP/proxy boundary:

```text
new_page(..., background=true)
select_page(..., bringToFront=false)
block Page.bringToFront
block Target.activateTarget
```

No foreground activation fallback is allowed.

## 7. Required Rebuild

### Phase 0: Stage Plan And Red Tests

Before implementation, create `docs/spec` phase documents:

- development plan for each phase;
- test plan for each phase;
- expected failing tests before code changes;
- acceptance evidence required before moving to the next phase.

No runtime implementation should begin before these phase docs exist.

### Phase 1: Replace Cockpit Opening Path

Files:

- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `tests/test_browser_cockpit_proxy.py`

Change:

- `new_page` must forward to upstream `chrome-devtools-mcp.new_page`.
- `search_page` must remain a cockpit tool, but only build the search URL and then forward as upstream `new_page`.
- Both paths must set `background=true` unless upstream already receives an explicit safe value.
- Remove the local `browser_session.open_or_reuse_page()` opening path from `search_page/new_page`.
- Remove tests that require `forwarded == []` and CDP `Target.createTarget` for actor page opening.

Expected new tests:

- `test_new_page_forwards_upstream_with_background_true`
- `test_search_page_builds_url_and_forwards_upstream_new_page`
- `test_search_page_rejects_blank_query_before_forwarding`
- `test_search_page_rejects_unsupported_engine_before_forwarding`
- `test_new_page_does_not_call_target_create_target`
- `test_search_page_does_not_call_target_create_target`

### Phase 2: Rebuild Page Resource Projection Around MCP PageId

Files:

- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `scripts/env/cdp_browser_lifecycle.py` or a replacement browser page lifecycle module
- `tests/test_browser_cockpit_proxy.py`
- `tests/test_cdp_browser_session.py` if the old module remains temporarily under test

Change:

- Replace `current_target_id` projection with MCP `current_page_id` / `selected_page_id`.
- Replace `page_id_to_target_id` bridge with direct pageId resource records.
- On successful `select_page`, refresh the selected page resource projection using MCP pageId.
- On page-scoped tool success, refresh the MCP selected/current page projection, not a CDP target.
- `list_pages` output may append BuddySwitch resource state, but it must describe MCP pageId state, not CDP target state.

Expected new tests:

- `test_select_page_marks_mcp_page_id_current`
- `test_page_scoped_success_refreshes_selected_page_id_idle`
- `test_page_scoped_success_without_selected_page_reports_clear_lifecycle_warning`
- `test_list_pages_projects_page_id_resource_state`
- residue test rejects `current_target_id` and `page_id_to_target_id` in live page idle state fixtures.

### Phase 3: Rebuild TTL Close Around MCP close_page

Files:

- `tools/launcher/browser_page_expired_handler.py`
- `tools/launcher/browser_inbound.py`
- `scripts/env/cdp_browser_lifecycle.py` or replacement module
- `tests/test_browser_page_expired_handler.py`
- `tests/test_browser_lazy_release_integration.py`
- `tests/test_browser_runtime_manager.py`

Change:

- TTL trigger payload must use `page_id`, not `target_id`.
- TTL schedule key must use MCP page id, for example:

```text
browser.page.idle:<page_id>
```

- Expiry must use MCP page flow:

```text
list_pages
verify pageId still exists and matches recorded URL/title when available
close_page(pageId)
forget resource projection
schedule browser release if no tracked user pages remain
```

- Do not fallback to `Target.closeTarget`.
- If MCP cannot confirm the page, clear stale projection or retry according to a documented failure mode; do not blindly close an unknown page.

Expected new tests:

- `test_expiry_payload_requires_page_id`
- `test_expiry_closes_confirmed_mcp_page_id`
- `test_expiry_does_not_close_when_page_id_missing_from_list_pages`
- `test_expiry_does_not_close_when_page_identity_mismatch`
- `test_expiry_keeps_current_selected_page_when_parent_turn_running`
- `test_final_tracked_page_schedules_release_after_mcp_close`
- residue test rejects `Target.closeTarget` in page TTL close path.

### Phase 4: Delete Actor-Page CDP Dual Path

Files:

- `scripts/env/cdp_browser_session.py`
- `scripts/env/cdp_browser_lifecycle.py`
- `tools/launcher/chrome_devtools_cockpit_proxy.py`
- `tools/launcher/browser_runtime_manager.py`
- tests that currently protect CDP actor-page behavior

Change:

- Delete `cdp_browser_session.open_or_reuse_page` if no non-actor process-readiness owner remains.
- Delete or move CDP helpers that only served actor page open/close:
  - `create_background_page_target` as actor page open;
  - `close_page_target` as actor page TTL close;
  - `target_id_for_page_id`;
  - `current_target_id`.
- If `browser_runtime_manager` still needs a CDP readiness helper for about:blank, keep it private to browser process readiness and document that it is not page-use/current/TTL semantics.
- Remove live tool descriptions that say search/new page opens "locally" or "does not forward".

Expected new tests:

- source scan rejects actor-page calls to `browser_session.open_or_reuse_page`.
- source scan rejects `Target.createTarget` from `chrome_devtools_cockpit_proxy.py`.
- source scan rejects `Target.closeTarget` from `browser_page_expired_handler.py`.
- source scan permits CDP readiness only in the browser runtime manager boundary if still required.

### Phase 5: End-To-End CLI Acceptance

Use real actor CLI simulation without `buddyswitch-user-simulation-testing`.

Required actor flow:

```text
start market actor
call chrome-devtools-cockpit.search_page(query, engine)
call list_pages
call select_page(pageId)
call take_snapshot
wait TTL
verify non-current page cleanup
verify selected/current page protection
stop instance
verify browser schedules, files, sockets, upstream process, and Chrome process are clean
```

Evidence must be stored under `docs/spec`, including:

- raw actor input;
- session jsonl or tail;
- status before TTL;
- status after TTL;
- status after stop;
- process scans before and after cleanup;
- residue scan output.

## 8. Residue Rules

The old semantics for this task are:

```text
cockpit new_page opens locally
cockpit search_page opens locally
browser-session current_target_id is current page truth
page_id_to_target_id bridge is required
TTL closes by target_id
TTL uses Target.closeTarget
actor page opening uses Target.createTarget
```

The new semantics are:

```text
cockpit new_page forwards to upstream MCP
cockpit search_page builds URL then forwards to upstream MCP new_page
MCP pageId/selected page is current page truth
BuddySwitch stores only pageId resource projection
TTL closes by MCP close_page(pageId) after MCP list_pages verification
```

Scoped live-surface scans must cover:

- `tools/launcher/*.py`
- `scripts/env/cdp_browser*.py`
- `scripts/runtime_kernel/*.py`
- `tests/test_browser_*.py`
- `tests/test_cdp_browser_session.py`
- `tools/launcher/assets/roles/*/AGENTS.md`
- `framework/contracts/*.md`
- `buddyswitch/skills/**/*.md`

Historical memos are evidence, not cleanup targets, unless they are used as current execution guidance.

## 9. Acceptance Contract

The end-to-end contract sentence is:

```text
An actor opens or selects a browser page through chrome-devtools-cockpit, then every subsequent cockpit page operation, BuddySwitch current-page projection, TTL refresh, TTL close, and resource cleanup refers to that same upstream MCP pageId/selected page.
```

Acceptance requires all of the following:

1. `search.open_browser` remains removed/rejected and is not reintroduced.
2. `browser.open_url` remains removed/rejected and is not reintroduced.
3. `search_page` and `new_page` no longer open actor pages through local CDP `Target.createTarget`.
4. `search_page` and `new_page` forward to upstream MCP `new_page` with non-focus behavior.
5. `select_page` establishes the BuddySwitch current-page projection from MCP pageId.
6. Page-scoped actions refresh TTL for the MCP selected page, not a separate CDP target.
7. TTL expiry closes only confirmed MCP pages through `close_page(pageId)`.
8. TTL expiry never uses CDP `Target.closeTarget` for actor page cleanup.
9. Active selected/current page is protected during a running parent turn.
10. Stale page projection is cleaned without blindly closing an unconfirmed page.
11. Browser release still happens when no tracked user pages remain.
12. `instance stop` still clears browser schedules and runtime browser files.
13. Real actor CLI flow passes and leaves no residual Chrome/upstream/broker/browser schedule resources.

## 10. Verification Commands

Focused tests after implementation:

```bash
python3 -m pytest \
  tests/test_browser_cockpit_proxy.py \
  tests/test_browser_page_expired_handler.py \
  tests/test_browser_lazy_release_integration.py \
  tests/test_browser_runtime_manager.py \
  tests/test_cdp_browser_session.py \
  -q
```

Contract and residue tests:

```bash
python3 -m pytest \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_broker.py \
  tests/test_repo_consistency.py \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py \
  -q
```

Scoped source scans:

```bash
rg -n 'search__open_browser|search\.open_browser|browser\.open_url' \
  scripts tools/launcher/assets framework/contracts buddyswitch/skills tests

rg -n 'opens locally|without forwarding|current_target_id|page_id_to_target_id|Target\.createTarget|Target\.closeTarget|browser_session\.open_or_reuse_page' \
  tools/launcher scripts/env tests
```

Expected result:

- first scan has no live old search open/browser broker hits except tests that assert rejection;
- second scan has no actor page lifecycle hits except explicitly allowed browser process readiness code and historical tests removed from active expectations.

## 11. Risks And Required Decisions

### MCP page identity across time

`pageId` is an MCP page handle. The rebuild must not assume it is permanently stable across upstream restart.

Required behavior:

- before TTL close, call MCP `list_pages`;
- verify the recorded `pageId` exists;
- verify URL/title when recorded;
- close only after confirmation;
- otherwise clear stale projection or retry without blind close.

### Upstream restart

On upstream restart, BuddySwitch should not pretend selected page survived as hidden state.

Required behavior:

- rebuild operational view from MCP `list_pages`;
- require `select_page` before page-scoped actions when selected page cannot be confirmed;
- refresh projection from the new MCP selected page after successful selection/use.

### Page limit

Existing page limit behavior currently comes from CDP page target counting.

Required implementation planning:

- move page count/page limit to MCP `list_pages` results;
- do not keep CDP counting as a compatibility branch for actor pages.

## 12. Definition Of Done

The task is done only when:

- implementation follows the phase docs in `docs/spec`;
- old local CDP actor-page open/close path is removed from live behavior;
- MCP pageId/selected page is the only page-use/current/TTL fact source;
- behavior tests pass;
- residue scans pass;
- real CLI actor acceptance passes;
- resource cleanup leaves the host clean after TTL and instance stop;
- final report includes exact tests, scans, actor instance id, and remaining risks.

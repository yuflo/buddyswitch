# Browser New Page TTL Registration Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every top-level page actually created by `chrome-devtools-cockpit.new_page` enters the existing browser page lifecycle, even when upstream `new_page` returns timeout or error.

**Architecture:** Keep the lifecycle boundary in `chrome_devtools_cockpit_proxy.py` and the existing `cdp_browser_lifecycle.py` helper. Do not add daemon browser scanning, Chrome websocket listeners, background retry queues, compatibility branches, or dual lifecycle paths. Replace the broken success-only registration gate with one deterministic post-response reconciliation path for `new_page`.

**Tech Stack:** Python stdio JSON-RPC proxy, Chrome DevTools `/json/list`, existing BuddySwitch daemon schedule mailbox, `unittest`.

---

## Current Bottleneck

The unreliable part is this assumption:

`new_page` error means no page was created.

That assumption is false. Chrome can create a top-level page target, then upstream navigation can timeout and return `isError=true`. The current proxy exits early on error before it checks Chrome targets, so the created page is not registered in `runtime/browser/page_idle.json` and has no `browser.page.expired` schedule.

The fix must target that assumption directly. It must not introduce a daemon orphan sweep, a browser event listener service, async pending registration, or compatibility behavior that preserves the old error-skip path.

## Evidence From Current Code

- `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - `mutate_tool_call()` captures `before_targets` for `new_page` and stores metadata.
  - `patch_tool_response_page_use_metadata()` returns immediately when `_tool_response_succeeded(message)` is false.
  - The `new_page` reconciliation and `_refresh_current_idle_hint()` call only run after that success check.

- `scripts/env/cdp_browser_lifecycle.py`
  - `refresh_page_idle()` creates the daemon schedule through `daemon_client.schedule_trigger()`.
  - It then writes lifecycle metadata to `runtime/browser/page_idle.json`.
  - `refresh_current_page_idle()` marks the created target as current after scheduling.

- `tests/test_browser_cockpit_proxy.py`
  - Existing tests cover successful `new_page` registration.
  - Existing tests cover registration failure after successful `new_page`.
  - Missing test: upstream `new_page` returns `isError=true`, but `/json/list` shows exactly one new top-level page target.

## Non-Negotiable Design Rules

- No daemon browser business logic.
- No `/json/list` sweep outside the cockpit proxy flow.
- No Chrome websocket target listener.
- No async pending registration file.
- No warning-only lifecycle failure for a newly created page.
- No compatibility branch that keeps old behavior for `new_page` error responses.
- No broad lifecycle redesign.
- No changes to `search.open_browser`; this incident is in the cockpit proxy `new_page` path.

## Target Invariant

After a `new_page` call returns from upstream, if Chrome now has exactly one new top-level `page` target compared with the captured pre-call target list, then the proxy must run the existing lifecycle registration path for that target regardless of upstream success or error.

For a newly created page:

- Registration succeeds: append `Browser page idle refreshed: 300s.` to the original upstream response.
- Registration fails: close the newly created target through the existing `close_page_target()` path and return a lifecycle error response.
- No new target exists: preserve the original upstream response.
- New target cannot be resolved uniquely: return a lifecycle error instead of silently claiming lifecycle refresh.

This keeps one clean chain:

`new_page request -> before target list -> upstream new_page -> after target list -> lifecycle register or lifecycle failure cleanup`

## Files

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `tests/test_browser_cockpit_proxy.py`
- Do not modify: `tools/launcher/browser_page_expired_handler.py`
- Do not modify: `tools/launcher/daemon_core.py`
- Do not modify: `tools/launcher/daemon_mailbox.py`
- Do not modify: `scripts/env/cdp_browser_lifecycle.py`
- Do not modify: `scripts/env/tools/search/_impl.py`

## Implementation Plan

### Task 1: Add Regression Coverage For Error-Created Page

**Files:**

- Modify: `tests/test_browser_cockpit_proxy.py`

- [ ] Add a test named `test_new_page_error_response_still_registers_created_target`.

Test shape:

```python
def test_new_page_error_response_still_registers_created_target(self) -> None:
    before = _page_targets(1)
    after = before + [{"id": "target-new-page", "type": "page", "url": "https://example.com/new"}]
    browser_url = self._start_cdp_list_server({"requests": [], "list_payloads": [before, before, after]})

    with tempfile.TemporaryDirectory() as temp_root:
        instance_root = Path(temp_root) / "instances" / "act-dev-browser"
        daemon_core, server, thread = self._start_mailbox(instance_root)

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new", "forceError": True})],
            browser_url=browser_url,
            instance_root=instance_root,
        )
        server.close()
        thread.join(timeout=2)

        self.assertEqual(len(forwarded), 1)
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("failed new_page", json.dumps(response, ensure_ascii=True))
        self.assertIn("Browser page idle refreshed: 300s.", json.dumps(response, ensure_ascii=True))

        saved = json.loads(daemon_core.daemon_state_file(instance_root).read_text(encoding="utf-8"))
        schedule = saved["scheduled_triggers"]["schedule-1"]
        self.assertEqual(schedule["type"], "browser.page.expired")
        self.assertEqual(schedule["schedule_key"], "browser.page.idle:target-new-page")
        self.assertEqual(schedule["payload"], {"target_id": "target-new-page"})

        page_idle = json.loads((instance_root / "runtime" / "browser" / "page_idle.json").read_text(encoding="utf-8"))
        self.assertEqual(page_idle["current_target_id"], "target-new-page")
        self.assertFalse(thread.is_alive())
```

- [ ] Run the focused test and confirm it fails before implementation.

Command:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy.BrowserCockpitProxyTests.test_new_page_error_response_still_registers_created_target
```

Expected failure before implementation:

- No `Browser page idle refreshed: 300s.` in response, or
- daemon state file does not exist, because registration was skipped.

### Task 2: Replace Success-Only Gate With New Page Reconciliation

**Files:**

- Modify: `tools/launcher/chrome_devtools_cockpit_proxy.py`

- [ ] In `patch_tool_response_page_use_metadata()`, move the `_tool_response_succeeded(message)` early return so it does not apply to `kind == "new_page"`.

Required behavior:

- `select_page` and current-page scoped tools still only refresh idle on successful upstream responses.
- `new_page` always attempts post-response target reconciliation when it has `before_targets` and `target_url` metadata.

- [ ] Keep target reconciliation as the only `new_page` post-response path, but remove the quiet "not refreshed" fallback:

```python
after_targets = browser_lifecycle.read_page_targets(browser_url)
target_id = browser_lifecycle.new_page_target_id(before_targets, after_targets)
if target_id is None:
    return tool_error_response(
        message,
        _lifecycle_error_text(
            "new_page",
            browser_lifecycle.BrowserLifecycleError(
                "created browser target was not uniquely resolved after upstream response"
            ),
        ),
    )
hint = _refresh_current_idle_hint(
    root=root,
    target_id=target_id,
    target_url=target_url,
)
return patch_tool_response_hint(patched, hint)
```

- [ ] Implement the `target_id is None` lifecycle error without introducing a new compatibility branch. Use `browser_lifecycle.BrowserLifecycleError` or a local exception object that produces exactly the required text below.

Required response text:

```text
Browser page lifecycle registration failed during new_page: created browser target was not uniquely resolved after upstream response
```

- [ ] Preserve existing cleanup on registration exception:

```python
close_result = browser_lifecycle.close_page_target(browser_url, target_id)
return tool_error_response(message, _lifecycle_error_text("new_page", exc, close_result))
```

### Task 3: Update Existing New Page Lifecycle Tests

**Files:**

- Modify: `tests/test_browser_cockpit_proxy.py`

- [ ] Add a test for ambiguous new target resolution.

Test name:

`test_new_page_ambiguous_created_targets_returns_lifecycle_error`

Test shape:

```python
def test_new_page_ambiguous_created_targets_returns_lifecycle_error(self) -> None:
    before = _page_targets(1)
    after = before + [
        {"id": "target-new-a", "type": "page", "url": "https://example.com/new"},
        {"id": "target-new-b", "type": "page", "url": "https://example.com/new"},
    ]
    browser_url = self._start_cdp_list_server({"requests": [], "list_payloads": [before, before, after]})

    with tempfile.TemporaryDirectory() as temp_root:
        instance_root = Path(temp_root) / "instances" / "act-dev-browser"
        daemon_core, server, thread = self._start_mailbox(instance_root)

        responses, forwarded, _upstream_argv, _stderr = self._run_proxy(
            [self._single_call("new_page", {"url": "https://example.com/new"})],
            browser_url=browser_url,
            instance_root=instance_root,
        )
        server.close()
        thread.join(timeout=2)

        self.assertEqual(len(forwarded), 1)
        response = responses[0]
        self.assertTrue(response["result"].get("isError"), msg=response)
        self.assertIn("not uniquely resolved", response["result"]["content"][0]["text"])
        self.assertFalse(daemon_core.daemon_state_file(instance_root).exists())
```

- [ ] Keep `test_non_page_use_and_failed_page_response_do_not_refresh_idle` scoped to non-`new_page` page tools. Do not let that test assert old `new_page` error behavior.

### Task 4: Run Focused Verification

**Files:**

- Verify only; no source edits in this task.

- [ ] Run the changed proxy test file.

Command:

```bash
python3 -m unittest tests.test_browser_cockpit_proxy
```

Expected result:

- All tests in `tests.test_browser_cockpit_proxy` pass.

- [ ] Run the browser lifecycle tests.

Command:

```bash
python3 -m unittest tests.test_cdp_browser_session tests.test_browser_page_expired_handler
```

Expected result:

- All tests pass.

- [ ] Run search browser tests to ensure no accidental cross-path break.

Command:

```bash
python3 -m unittest tests.test_search_env_tool
```

Expected result:

- All tests pass.

## Rejected Approaches

- Daemon orphan sweep: rejected because it moves browser business logic into daemon infrastructure.
- Chrome target websocket listener: rejected because it adds a new long-lived lifecycle mechanism for a narrow `new_page` post-response bug.
- Async pending TTL registration: rejected because the observed failure is not transient registration failure; it is a skipped branch.
- Warning-only registration failure: rejected because it leaves unmanaged pages behind.
- Local-first lifecycle rewrite: rejected for this patch because it changes the scheduling contract and widens the task beyond the current bottleneck.
- Dual behavior preserving old error skip: rejected because it keeps the bug.

## Definition Of Done

- A `new_page` upstream error that still creates exactly one top-level page target results in lifecycle registration.
- Existing successful `new_page` registration still works.
- Existing reuse behavior still works.
- Existing registration failure cleanup still closes unmanaged newly created targets.
- No daemon browser sweep exists.
- No browser target listener exists.
- No pending TTL retry file exists.
- No compatibility branch preserves old error-skip behavior.
- Focused tests pass with the commands listed above.

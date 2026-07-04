# Browser Resource Lifecycle Rebuild Plan

Date: 2026-07-04

## Objective

Rebuild the browser resource lifecycle around one clear runtime owner, one release path, and verifiable cleanup.

This plan is scoped to architecture and implementation planning. Runtime code must not be changed until the implementation session has a written development plan and test plan under `docs/spec`.

## Confirmed Task Scope

The current target is not to patch symptoms. The target is to audit whether the browser resource lifecycle still matches the original architecture, then design a rebuild-forward plan that removes ambiguity and residue.

The required outcome is:

1. Confirm whether the current architecture conflicts with the original browser design.
2. Identify the exact resource lifecycle boundary that is currently unstable.
3. Design a rebuild plan with no long-lived dual path and no compatibility layer.
4. Preserve the already validated direction that browser-use capabilities converge on `chrome-devtools-cockpit`.
5. Produce a focused acceptance plan that proves cleanup by behavior, process state, socket state, and actor flow.

## Non-Negotiable Principles

This plan follows the `docs/bitter` and SHARP-forward rules:

1. Fix the product runtime contract, not prompts or surface wording.
2. Keep one main intent per change set.
3. Replace wrong boundaries instead of routing around them.
4. Treat old runtime paths as residue unless they are proven live requirements.
5. A resource lifecycle feature is only done when process, socket, marker, temp state, and observable product state all return to baseline.
6. Keep a real end-to-end consumer slice in verification.

## Architecture Audit Conclusion

The current macro architecture does not conflict with the original direction.

The intended shape is still valid:

1. Actor browser work enters through `chrome-devtools-cockpit`.
2. `chrome-devtools-cockpit` owns the browser-use tool surface, including specific actions such as search-page opening.
3. Browser page operations use `scripts/env/cdp_browser_session.py`.
4. Page TTL and page idle state use `scripts/env/cdp_browser_lifecycle.py`.
5. Browser process acquisition and release are owned by `tools/launcher/browser_runtime_manager.py`.
6. Runtime broker exposes only control-plane methods such as `browser.acquire`, `browser.status`, and `browser.release`.

The architecture problem is narrower and deeper:

`browser_runtime_manager.release()` can clear state without proving the actor-owned Chrome process is gone.

That violates the original lifecycle intent because the product state can say "inactive" while an actor-owned Chrome process still exists.

## Current Code Findings

### Already Aligned

`tools/launcher/chrome_devtools_cockpit_proxy.py` now has the right convergence point:

- `new_page` opens through `browser_session.open_or_reuse_page`.
- `search_page` builds a search URL, then opens through the same browser-session path.
- `tools/call` acquires the managed browser through `browser.acquire`.

`scripts/runtime_kernel/dispatcher.py` is also aligned:

- It supports `browser.acquire`, `browser.status`, and `browser.release`.
- It no longer keeps `browser.open_url` as the browser data-plane.

`scripts/env/cdp_browser_session.py` is aligned:

- It enforces page limits.
- It reuses exact URLs.
- It registers page idle state after creating a target.
- It closes the target if idle registration fails.

`scripts/env/cdp_browser_lifecycle.py` is aligned:

- It refreshes per-page idle expiry.
- It schedules `browser.page.expired`.
- It schedules cockpit release after all tracked pages are gone.

`tools/launcher/browser_page_expired_handler.py` is aligned at the page layer:

- It closes expired page targets.
- It removes stale page-idle entries.
- It schedules cockpit release when the tracked page set becomes empty.

### Not Aligned

`tools/launcher/browser_runtime_manager.py` mixes different resource meanings:

- `browser_port` is reachability state.
- `browser/chrome.pid` is a marker.
- `browser/profile` is the actor-owned Chrome identity.
- `runtime/browser/cockpit-upstream.pid` and `.pgid` are upstream MCP process markers.
- `runtime/browser/page_idle.json` is page lifecycle state.

The release path does not treat these as one transaction.

Current behavior:

1. `ownership_state()` can discover ownership by checking the recorded port and matching `--user-data-dir=<instance>/browser/profile`.
2. `release()` calls `stop()` only when ownership is `owned` or `inactive`.
3. `stop()` terminates only the marker PID from `browser/chrome.pid`.
4. `stop()` clears upstream markers, page idle state, and `browser_port`.
5. It does not verify that the profile-owned Chrome listener is gone before clearing state.
6. If `browser_port` is already missing, `release()` skips cleanup and cannot discover profile-owned orphaned Chrome.

This creates a bad state:

Chrome can remain alive while `instance.json.browser_port` is null and lifecycle files are cleared.

### Policy Boundary Drift

`tools/launcher/browser_release_handler.py` has release policy checks such as parent process, page-idle targets, and real-user-page protection.

`browser_runtime_manager.release(reason=...)` currently ignores `reason`.

That means automatic release policy and explicit release behavior are not represented in the single owner. The handler has part of the policy, while the manager has final cleanup authority. This split makes behavior hard to reason about and test.

## Root Cause

The root cause is not the recent `chrome-devtools-cockpit` convergence itself.

The root cause is an incomplete process-resource release contract:

1. Chrome ownership is not defined as a first-class resource identity.
2. Release does not discover all owned resources before acting.
3. Release clears state before verifying termination.
4. `browser_port` is treated as the cleanup anchor, but it is only recorded reachability state.
5. Marker PID absence is treated too much like "nothing to clean".

Recent updates made the issue easier to observe because cockpit convergence and lazy release made the browser lifecycle path more important. They did not invalidate the original design direction.

## Rebuild Target Architecture

### Single Runtime Owner

`tools/launcher/browser_runtime_manager.py` should become the only source of truth for Chrome runtime process ownership and final release semantics.

The manager must own:

1. Resource discovery.
2. Ownership classification.
3. Release policy interpretation.
4. Process termination.
5. Termination verification.
6. State cleanup.
7. Structured release/status result reporting.

Handlers and broker dispatchers should trigger the manager. They should not implement final cleanup semantics.

### Resource Model

The rebuild should define these resource layers explicitly:

| Layer | Owner | Identity | Cleanup Proof |
| --- | --- | --- | --- |
| Page target | `cdp_browser_session` and page expired handler | CDP `target_id` | target closed or removed from page idle state |
| Page idle state | `cdp_browser_lifecycle` | `runtime/browser/page_idle.json` | tracked target removed or file removed |
| Cockpit upstream MCP | `browser_runtime_manager` | upstream pid/pgid markers | process group gone and markers removed |
| Chrome runtime | `browser_runtime_manager` | `--user-data-dir=<instance>/browser/profile` | no profile-owned listener/process remains |
| Browser reachability | `browser_runtime_manager` | `instance.json.browser_port` | cleared only after owned runtime cleanup is verified |

Important rule:

`browser/profile` is the actor-owned Chrome identity. `browser_port` and `browser/chrome.pid` are hints, not ownership truth.

### Release Modes

`browser_runtime_manager.release(reason=...)` should stop ignoring `reason`.

It should map release reasons into explicit modes:

| Mode | Example reason | Behavior |
| --- | --- | --- |
| Automatic idle release | `page_idle_empty`, `browser.cockpit.release` | Release only when no protected real user page remains |
| Explicit actor cleanup | `instance_stop`, `manual_stop`, `test_cleanup` | Force cleanup of actor-owned Chrome and upstream resources |
| Status repair release | `orphan_repair` | Clean actor-owned orphaned Chrome discovered by profile identity |

The exact reason names can follow existing launcher vocabulary, but the manager must make the mode visible in its returned result.

### Discovery Before Action

Every release should begin by discovering:

1. Recorded `browser_port`.
2. Marker PID from `browser/chrome.pid`.
3. Marker process group if available.
4. Upstream PID and process group.
5. Listener PIDs for the recorded port.
6. Profile-owned Chrome processes for `browser/profile`, even when `browser_port` is null.
7. Current page-idle targets.
8. Current CDP pages when a reachable endpoint exists.

Discovery must not require `browser_port` to exist. A missing `browser_port` can no longer mean "skip cleanup" by itself.

### Ownership Classification

The manager should classify the runtime into one of these states:

| State | Meaning |
| --- | --- |
| `inactive` | no recorded endpoint and no profile-owned process |
| `owned` | recorded endpoint or process belongs to this instance profile |
| `orphaned_owned` | no valid recorded endpoint, but profile-owned Chrome exists |
| `foreign` | endpoint/process belongs to another profile |
| `unknown` | resource exists but ownership cannot be proven |
| `stale_state` | markers or `browser_port` exist but no live process exists |

Only `owned`, `orphaned_owned`, and `stale_state` should be eligible for automatic actor-owned cleanup.

`foreign` and `unknown` must not be killed by default.

### Transactional Release

Release should follow one path:

1. Discover resources.
2. Classify ownership.
3. Apply release mode policy.
4. Stop cockpit upstream process group.
5. Stop owned Chrome process group or owned profile processes.
6. Verify no owned profile process or listener remains.
7. Clear state files and `browser_port`.
8. Return structured result.

State cleanup must happen after verification, not before it.

If verification fails, release must return `ok: false` and keep enough state for diagnosis. It must not report handled success while owned Chrome remains alive.

### Stop Path

`stop()` should not be a separate implementation with different cleanup behavior.

It should delegate to the same release engine with an explicit force mode. That keeps instance stop, CLI release, broker release, and lazy release from diverging.

### Status Path

`status()` should expose orphaned ownership.

If `browser_port` is null but a Chrome process exists with this instance profile, status should not say simply "inactive". It should report a state equivalent to `orphaned_owned` with enough details to diagnose or trigger cleanup.

### Handler Boundary

`browser_release_handler.py` should become a trigger and guard layer:

1. Validate parent process state.
2. Avoid releasing when page-idle targets remain.
3. Ask the manager to perform automatic idle release.
4. Propagate manager failure as handler failure.
5. Log structured release result.

The handler should not be the only location where real-user-page protection lives. The final policy needs to be represented in the manager so all release callers use one semantic boundary.

## Implementation Phases

No runtime code should be changed until a detailed development plan and test plan are written under `docs/spec`.

### Phase 0 - Development Plan

Create a `docs/spec` implementation plan before code changes.

The plan must list:

1. Files to change.
2. New tests and the behavior each test proves.
3. Expected failing tests before implementation.
4. Manual actor verification commands.
5. Residue scans.
6. Roll-forward criteria for each phase.

### Phase 1 - Regression Tests First

Add failing tests that prove the current defect.

Required regression coverage:

1. Manager release cleans actor-owned Chrome when `browser/chrome.pid` is missing but the profile-owned listener exists.
2. Manager release cleans actor-owned Chrome when `browser_port` is null but a profile-owned Chrome process exists.
3. Manager release returns failure and preserves diagnostic state if owned Chrome cannot be terminated.
4. Manager status reports orphaned actor-owned Chrome instead of plain inactive.
5. Release handler propagates manager release failure instead of reporting handled success.
6. CLI or broker `browser.release` covers the same missing-marker owned-process case.

The tests should use real local fake Chrome processes where practical, because this bug is process-lifecycle behavior.

### Phase 2 - Resource Discovery Model

Refactor the manager around an internal discovered-resource snapshot.

The snapshot should include:

1. instance root
2. profile dir
3. recorded port
4. marker pid and process group
5. upstream pid and process group
6. port listener processes
7. profile-owned Chrome processes
8. ownership classification
9. page-idle target summary

Keep this internal to the manager unless a test needs to assert structured status output.

### Phase 3 - Transactional Release Engine

Replace the current `release()` and `stop()` split with one release engine.

Required behavior:

1. Stop upstream first.
2. Stop owned Chrome by marker process group when valid.
3. Fall back to profile-owned process discovery when marker is missing or stale.
4. Verify cleanup by checking profile-owned processes and listener state.
5. Clear runtime state only after verification.
6. Return `ok: false` on failed termination.

This is not a compatibility fallback. It is the rebuilt primary release algorithm.

### Phase 4 - Handler, Broker, CLI Projection

Update projection layers to call the rebuilt manager semantics.

Required behavior:

1. Automatic release uses idle release mode.
2. Explicit stop or instance cleanup uses force actor-owned mode.
3. Broker and CLI responses expose enough release detail to prove what happened.
4. Handler logs include release mode, ownership state, killed process count, and cleanup verification.

### Phase 5 - End-to-End Actor Verification

Validate the real actor path:

1. Start a market actor instance.
2. Use `chrome-devtools-cockpit` only.
3. Open a search page through the cockpit search/new-page path.
4. Confirm `list_pages`, `select_page`, and `take_snapshot` work.
5. Wait for page TTL and release delay.
6. Confirm page-idle state clears.
7. Confirm `browser_port` clears.
8. Confirm no actor-profile Chrome process remains.

## Explicit Non-Goals

This rebuild should not:

1. Reintroduce `search.open_browser`.
2. Reintroduce `browser.open_url`.
3. Add a second browser client path beside cockpit.
4. Preserve old search-browser compatibility behavior.
5. Move process lifecycle responsibility into prompts, skills, or role docs.
6. Add a generic resource framework.
7. Hide cleanup failures by clearing state first.

## Expected Final Architecture

After rebuild:

1. `chrome-devtools-cockpit` is the browser-use tool surface.
2. Search-specific browser use is implemented as cockpit behavior, not as the old env search tool.
3. Page lifecycle remains in `cdp_browser_session` and `cdp_browser_lifecycle`.
4. Chrome process lifecycle is owned by `browser_runtime_manager`.
5. Broker, CLI, and handlers are projections over the manager, not separate lifecycle owners.
6. Cleanup is proven by process and socket state before product state is cleared.

## Acceptance Gate

The rebuild is not acceptable unless all of these are true:

1. Regression tests fail on the old release behavior and pass after rebuild.
2. Actor-owned Chrome cannot remain alive while state reports inactive.
3. Foreign or unknown Chrome processes are not killed.
4. Automatic idle release does not close protected real user pages.
5. Explicit instance cleanup removes actor-owned upstream and Chrome resources.
6. `chrome-devtools-cockpit` search-page flow still works.
7. Residue scans show no live old `search.open_browser` or `browser.open_url` path.
8. Manual actor validation proves browser cleanup after TTL and release delay.

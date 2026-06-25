# Browser Page Idle Lifecycle Design Memo

Date: 2026-06-25

## Purpose

This task upgrades BuddySwitch's launcher-managed browser page resource management.

It is not a tool parameter upgrade. It should not expose a `ttl_seconds` or similar setting to Codex. The user-facing tool surface stays simple. Browser page lifetime should be managed internally by BuddySwitch.

The goal is:

- open browser pages with a short default idle timeout;
- keep pages alive when the actor is actually using them;
- automatically close pages that are no longer being used;
- avoid closing the current page while the actor is still working on it;
- keep daemon-service generic and free of browser-specific business logic.

## Scope

This applies to launcher-managed browser pages used through:

- `search.open_browser`
- `chrome-devtools-cockpit`
- browser lifecycle helpers under `scripts/env`
- browser-owned daemon inbound handler under `tools/launcher`

This is a browser page resource management upgrade, not a product-object persistence feature.

## Idle Model

Use a page idle timeout model.

- New page success: register a 300 second idle timeout.
- Page use: reset that page's idle timeout to 300 seconds.
- Expiry: close the page unless current-page protection applies.
- Current-page protection: if the expiring page is still the current page and the actor main turn is still running, do not close it; reset its idle timeout to 300 seconds.
- Actor idle, page no longer current, or page already gone: allow normal expiry handling.

Removed from the design:

- no tool-side TTL parameter;
- no `+180s` accumulated extension;
- no maximum remaining TTL such as 1200 seconds;
- no cross-page `-10%` idle reduction;
- no `expiry_policy`;
- no notify branch.

## Definition Of Page Use

A browser page is "used" when the actor makes it the concrete work target through a browser-capable tool.

Counts as page use:

- a new page is opened successfully;
- `search.open_browser` reuses an existing page;
- `chrome-devtools-cockpit.new_page` reuses an existing page for the requested URL;
- `chrome-devtools-cockpit.select_page` selects a page successfully;
- a page-scoped cockpit tool succeeds against the current page, such as:
  - `take_snapshot`
  - `take_screenshot`
  - `click`
  - `type_text`
  - `evaluate_script`
  - `navigate_page`
  - `wait_for`
  - `fill`
  - `press_key`

Does not count as page use:

- `list_pages`;
- `tools/list`;
- tool schema discovery;
- proxy-internal probing;
- `close_page`;
- failed page operations;
- BuddySwitch-blocked focus or bring-to-front requests.

## State Ownership

Browser lifecycle state is browser-owned runtime state.

Physical path:

```text
<instance_root>/runtime/browser/page_idle.json
```

This file may store only minimal browser lifecycle facts, such as:

- current CDP `target_id`;
- current page update timestamp;
- necessary `pageId` to `target_id` mapping cache;
- any minimal metadata needed to reconnect page use events to CDP targets.

It must not be stored in:

- `buddyswitch/objects/**`;
- `workspace/private`;
- daemon-service business state fields;
- tool input or output schemas.

Daemon service state remains:

```text
<instance_root>/runtime/daemon/state.json
```

That file may contain generic scheduled trigger rows, but it must not grow browser-specific fields such as `current_target_id` or `browser_page_idle`.

## Daemon-Service Boundary

Daemon-service provides generic scheduling capability. It does not implement browser page policy.

Daemon-service may support a generic keyed schedule upsert capability:

- `delay_seconds`
- `type`
- `payload`
- `source_context`
- `schedule_key`

`schedule_key` is opaque to daemon-service. For browser idle, browser lifecycle can use a key such as:

```text
browser.page.idle:<target_id>
```

Daemon-service behavior should be generic:

- if there is a pending schedule with the same key, update its due time and payload;
- otherwise create a new pending schedule;
- dispatch due schedules by type;
- leave all business interpretation to handlers.

This capability can support other domains later, such as message retry, delayed reminders, cleanup, debounce, and watchdog expiry. That reuse should not require daemon-service to understand those domains either.

## Module Responsibilities

`search.open_browser`

- Opens or reuses search pages.
- On new page or reuse, calls browser lifecycle to touch page idle state.
- Does not expose TTL/idle controls.

`chrome_devtools_cockpit_proxy.py`

- Detects browser page use through cockpit calls.
- Forces existing non-activating behavior.
- Tracks enough current-page identity to report page use to browser lifecycle.
- Must not treat upstream `pageId` as CDP `target_id`.

`cdp_browser_lifecycle.py`

- Owns browser idle semantics.
- Reads and writes `<instance_root>/runtime/browser/page_idle.json`.
- Converts use events into idle schedule upserts.
- Provides a small API such as:
  - touch page idle for a known `target_id`;
  - set current page;
  - resolve current page identity where possible.

Daemon-service

- Owns generic scheduled trigger persistence and delivery.
- Supports schedule creation and keyed schedule upsert.
- Does not understand browser page semantics.

`browser_page_expired_handler.py`

- Owns browser-specific expiry behavior.
- Reads browser-owned page idle state.
- Checks whether the expired page is the current page and whether the actor main turn is still running.
- Resets idle timeout when current-page protection applies.
- Closes the target otherwise.

## Important Implementation Notes

Do not append a new schedule on every page use. That would leave older schedules active and could close a page early. Page use must upsert the pending schedule for the same `target_id`.

Do not mix `pageId` and `target_id`.

- Chrome DevTools MCP `pageId` is an upstream MCP page identifier.
- CDP close operations require CDP `target_id`.
- Browser lifecycle must map or resolve identity before scheduling close.

Current-page protection must not make the page permanent.

- It applies only while the actor main turn is running.
- Once the actor is idle, the page can expire normally.

The design should remain internal.

- No new actor-facing TTL input.
- No user-facing policy switch.
- No speculative expiry modes.
- No browser-specific fields in daemon-service core state.

## Expected Result

After implementation, browser pages behave like managed idle resources:

- new pages get a short 300 second idle window;
- active browser work keeps the relevant page alive automatically;
- unused pages close without manual cleanup;
- the page currently under active actor analysis is not closed mid-turn;
- daemon-service remains a reusable scheduler rather than a browser lifecycle service.

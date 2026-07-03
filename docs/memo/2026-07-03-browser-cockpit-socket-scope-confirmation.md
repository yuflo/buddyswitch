# Browser Cockpit Socket Repair Scope Confirmation

Date: 2026-07-03  
Status: task scope confirmation; no implementation in this memo

## 1. Confirmed Task Target

The current task is a staged repair, not a full browser/search architecture rewrite.

The authorized first stage is:

1. Make the `chrome-devtools-cockpit` MCP process reliably receive the runtime broker socket in product mode.
2. Verify that `chrome-devtools-cockpit.new_page` can lazy-start Chrome and open a page in a real actor instance.
3. Stop after the first-stage verification and report evidence before touching `search.open_browser`.

The later search consolidation is a separate stage. It must not be implemented until the first-stage result is confirmed and a separate repair/test plan is reviewed.

## 2. Core Problem

The observed browser access failure is blocked before Chrome page work begins.

The runtime broker process is alive, but the browser-capability caller cannot reach it because the process path that needs browser acquisition does not have a stable `BUDDYSWITCH_RUNTIME_BROKER_SOCKET`.

Observed failure shape:

```text
browser acquire failed: BUDDYSWITCH_RUNTIME_BROKER_SOCKET is required in product mode
```

Important distinction:

- This is not a page navigation failure after Chrome opens.
- This is not evidence that the actor process is dead.
- This is not primarily a search query construction failure.
- This is a broker socket injection/boundary failure on the browser acquisition path.

## 3. Current First-Stage Scope

The first-stage repair may touch only the minimum code needed to make `chrome-devtools-cockpit` browser acquisition receive the runtime broker socket and prove `new_page` works.

Expected implementation area:

- launcher registration/configuration for `chrome-devtools-cockpit`
- `tools/launcher/chrome_devtools_cockpit_proxy.py` socket argument or environment handling, if required
- focused tests that prove the socket is passed into the cockpit MCP process
- focused launcher tests that prove generated actor MCP config contains the expected broker socket

Expected verification:

- run focused tests for cockpit proxy socket handling and launcher MCP config
- start a real `market` actor instance with `buddyswitch-codex instance start --role market`
- use the instance input interface, not a manual side-channel message, to ask the actor to use only `chrome-devtools-cockpit.new_page`
- confirm the first browser use changes instance `browser_port` from `null` to an active port
- confirm session logs show `chrome-devtools-cockpit.new_page` success
- optionally call/list pages through cockpit for evidence
- stop and delete the validation actor instance

## 4. Explicit Non-Scope For First Stage

The following must not be changed in the first stage unless the user explicitly approves expanding scope:

- do not remove or rewrite `search.open_browser`
- do not remove `search__open_browser`
- do not add a new cockpit search-specific action
- do not remove runtime broker `browser.open_url`
- do not change search tool public schemas
- do not rewrite market skills
- do not rewrite role `AGENTS.md` files
- do not rewrite framework contracts
- do not perform broad live-guidance cleanup
- do not delete old browser/search paths as part of the socket repair

The reason is procedural and architectural: the first-stage bottleneck is cockpit's broker socket acquisition. Search consolidation depends on this being fixed first, but it is not itself part of the first-stage implementation.

## 5. Required Stop Point

After completing the first-stage repair and verification, the work must stop.

The report at that stop point should include:

- files changed for the socket repair
- focused tests run and results
- real actor id used for validation
- exact cockpit tool call evidence
- instance `browser_port` before and after
- cleanup result for the validation actor
- any remaining risk or blocker

No `search.open_browser` implementation changes should be made before this report and user confirmation.

## 6. Later Stage To Discuss Separately

Only after the first-stage result is confirmed should the search consolidation be planned.

The later discussion must decide:

- whether `search.open_browser` should be fully removed or replaced
- whether the replacement should be a `chrome-devtools-cockpit` search-specific action
- whether runtime broker `browser.open_url` remains useful or should be removed
- where browser TTL/resource lifecycle ownership should remain
- how cockpit upstream lazy start relates to Chrome lazy start
- whether role `AGENTS.md`, market skills, and framework contracts must be updated
- which tests define the public contract for the new search path

That later stage requires a separate repair plan and test plan before implementation.

## 7. Key Boundary Statement

The immediate bottleneck is:

```text
chrome-devtools-cockpit MCP process
  -> browser acquisition
  -> runtime broker socket missing
  -> Chrome never starts
```

The first-stage target is only to make this path work:

```text
chrome-devtools-cockpit.new_page
  -> broker-backed browser acquire
  -> Chrome lazy start
  -> page opened
  -> observable actor/session evidence
```

The search path must remain untouched until the first-stage evidence is reviewed.

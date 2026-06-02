# Daemon Handler Action Surface Cleanup Task

Date: 2026-06-02
Status: confirmed cleanup task

## 1. Core Decision

After the trigger-handler-action dispatch rebuild, the daemon API surface needed by message async routing should be
narrowed to handler-facing runtime actions.

This memo does not define daemon ingress methods. Ingress is covered by:

```text
docs/memo/2026-06-02-daemon-trigger-handler-action-dispatch-rebuild.md
```

The goal is a clean ownership boundary:

```text
business handlers express judgment
daemon actions perform runtime control
daemon internals validate and record
```

## 2. Dependency On Unified Dispatch

This cleanup assumes the dispatch rebuild has already normalized inputs into daemon triggers:

```text
message.available
message.parent_required
```

The message handler should receive those through:

```text
handler.handles(trigger)
handler.handle(context, state, actions, trigger)
```

Transport details such as cross-actor delivery or local side trigger submission are not handler-facing runtime action
API. The only local-trigger requirement relevant here is that side ownership validation happens before the message
handler runs.

## 3. Handler-Facing Runtime Actions

These are the actions business handlers should be allowed to call.

### `actions.parent_activity()`

Purpose:

- inspect local parent thread state.

Return semantics:

```text
idle | running | unavailable
```

Optional data:

- active turn id when running;
- error text when unavailable.

Used by:

- `message.available` routing.

### `actions.submit_parent_prompt(text, handler_name, origin_id, interrupt_policy)`

Purpose:

- submit a prompt to the parent thread;
- optionally interrupt the active parent turn before submit.

Required `interrupt_policy` values:

```text
none
before_submit
```

Meaning:

- `none`: parent is idle or no interrupt is requested.
- `before_submit`: daemon interrupts the active parent turn first, then submits the prompt.

This replaces the exposed split between:

```text
submit_parent_prompt(...)
interrupt_and_submit_parent_prompt(...)
```

The handler expresses the required runtime policy; it does not manage the two-step operation itself.

### `actions.submit_side_triage_prompt(text, handler_name, origin_id)`

Purpose:

- submit a triage prompt to an existing open side thread when reusable;
- otherwise start a new side thread from the parent.

This replaces the business-facing name:

```text
start_or_reuse_side_triage(...)
```

The start/reuse decision is runtime control, not message business logic.

## 4. Daemon Internal Primitives

The following should remain daemon-internal and not be treated as message handler API.

### `interrupt_parent(...)`

Internal primitive used by:

```text
submit_parent_prompt(..., interrupt_policy="before_submit")
```

### `start_side_triage(...)`

Internal primitive for creating side triage.

### `send_side_triage(...)`

Internal primitive for sending follow-up input to an existing side thread.

### `require_side_thread(...)`

Internal side ownership validation.

It should be used inside local-trigger validation, not called directly by message business handlers.

### `close_side_triage(...)`

Internal for now.

It should not enter the message API unless a concrete message lifecycle later requires message-owned side closure.

### `record_daemon_action(...)` / `daemon_actions`

Internal status, provenance, and verification surface.

Handlers rely on actions to record facts; they do not directly manage provenance records.

## 5. Final API Surface

The cleaned handler-facing action surface relevant to message async routing should be:

```text
actions.parent_activity()
actions.submit_parent_prompt(..., interrupt_policy="none" | "before_submit")
actions.submit_side_triage_prompt(...)
```

Everything else is ingress infrastructure or daemon internal.

## 6. Message Routing Usage

### Case 1: parent idle

```text
message.available trigger
  -> handler calls parent_activity()
  -> status idle
  -> handler calls submit_parent_prompt(..., interrupt_policy="none")
```

### Case 2: parent running, side can handle

```text
message.available trigger
  -> handler calls parent_activity()
  -> status running
  -> handler calls submit_side_triage_prompt(...)
  -> side reads/replies with message tools
```

### Case 3: parent running, side needs parent

```text
message.parent_required local trigger
  -> daemon validates side ownership
  -> handler renders parent message prompt
  -> handler calls submit_parent_prompt(..., interrupt_policy="before_submit")
```

## 7. Current-State Gap

Current action-facing code still exposes or uses:

```text
actions.interrupt_and_submit_parent_prompt
actions.start_or_reuse_side_triage
actions.require_side_thread from message handler
```

Target cleanup:

```text
interrupt_and_submit_parent_prompt
  -> replace with submit_parent_prompt(..., interrupt_policy="before_submit")

start_or_reuse_side_triage
  -> replace with submit_side_triage_prompt

require_side_thread in MessageAvailableHandler
  -> move into unified dispatch local-trigger validation
```

Removal of the old business-specific mailbox method belongs to the dispatch rebuild memo because it is an ingress
method, not a handler-facing runtime action.

## 8. Success Criteria

The daemon API cleanup is complete when:

- message handlers no longer call low-level interrupt, side start/send, or side validation primitives;
- parent interrupt behavior is expressed by `interrupt_policy`;
- side start/reuse is expressed by `submit_side_triage_prompt`;
- side ownership validation is performed before handler business logic;
- tests cover all three message routing cases through the cleaned surface.

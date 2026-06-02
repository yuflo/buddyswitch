# Daemon Trigger-Handler-Action Dispatch Rebuild

Date: 2026-06-02
Status: confirmed architecture task

## 1. Core Decision

Daemon dispatch should be rebuilt around:

```text
trigger -> handler -> action
```

The daemon should not grow one mailbox method per business case.

The current `mailbox.parent_required` path is the wrong boundary: it is narrow, typed, and testable, but it places a message-specific business event directly on the shared daemon mailbox API. The clean shape is a stable ingress plus typed trigger payloads.

## 2. Daemon Positioning

The daemon owns local runtime coordination:

- receive runtime inputs from known ingress sources;
- normalize those inputs into daemon triggers;
- dispatch triggers to registered handlers;
- expose controlled runtime actions through `ActionGateway`;
- record handler/action provenance for debugging and verification.

The daemon does not own business judgment:

- it does not decide message urgency;
- it does not decide whether a side thread can reply;
- it does not decide task checkout semantics;
- it does not generate business TUI content except by submitting prompt text produced by handlers;
- it does not become an event bus, workflow engine, subscription platform, or plugin router.

## 3. Stable Ingress Sources

Ingress source means the physical or control path by which input reaches the daemon. It is not the business event type.

The intended stable sources are:

```text
app_server_notification
mailbox_cross_actor_signal
mailbox_local_trigger
```

### app_server_notification

Source for launcher/app-server notifications already consumed by the daemon loop.

Example:

```text
raw app-server notification method="turn/completed"
  -> normalized trigger type="app_server.turn_completed"
```

Task checkout belongs here.

### mailbox_cross_actor_signal

Source for cross-actor delivery through `mailbox.deliver`.

Example:

```text
mailbox.deliver signal type="message.available"
  -> normalized trigger type="message.available"
```

Message availability belongs here.

### mailbox_local_trigger

Source for local side-to-daemon typed triggers through a generic mailbox method.

Example:

```text
mailbox.local_trigger type="message.parent_required"
  -> normalized trigger type="message.parent_required"
```

Message parent escalation belongs here.

This replaces business-specific methods such as `mailbox.parent_required`.

## 4. DaemonTrigger Shape

All ingress adapters should normalize raw input into one daemon-internal shape:

```text
DaemonTrigger {
  source
  type
  target_actor_address
  origin_id
  correlation_id
  payload
  source_context
}
```

Field meaning:

- `source`: stable ingress source, such as `app_server_notification`.
- `type`: daemon-internal business/event semantic, such as `message.parent_required`.
- `target_actor_address`: actor this daemon instance is allowed to handle.
- `origin_id`: source-specific origin, such as message id or turn id.
- `correlation_id`: optional id for tracing related trigger/action chains.
- `payload`: business payload owned by the handler.
- `source_context`: ingress-specific validated context, such as parent thread id, side thread id, or raw turn id.

`type` is not the same as a raw external protocol field. For example, app-server `method="turn/completed"` can normalize to `type="app_server.turn_completed"`.

## 5. Ingress Adapter Responsibility

An ingress adapter is not a new platform. It is local protocol adaptation code.

It does:

- validate source protocol shape;
- validate target actor where applicable;
- extract source-specific context;
- normalize into `DaemonTrigger`.

It does not:

- make business decisions;
- call `ActionGateway`;
- render TUI prompts;
- implement subscription rules;
- know which action a handler will take.

## 6. Trigger Router Responsibility

`TriggerRouter` should own only handler dispatch:

```text
for handler in handlers:
  if handler.handles(trigger):
    result = handler.handle(context, state, actions, trigger)
```

It should preserve existing handler result recording semantics:

- matched count;
- handled count;
- ignored/failed handling status;
- handler errors;
- action provenance through `ActionGateway`.

It should not inspect business payload fields such as `message_id` beyond generic validation already done by ingress adapters.

## 7. Handler Interface

Handlers should converge to one trigger-facing interface:

```text
handler.handles(trigger) -> bool
handler.handle(context, state, actions, trigger) -> HandlerResult
```

This replaces split entry methods such as:

```text
handle_notification(...)
handle_signal(...)
handle_parent_required(...)
```

Handlers remain business-owned:

- `TaskCheckoutHandler` handles task checkout trigger semantics.
- `MessageAvailableHandler` handles `message.available` and `message.parent_required`.

## 8. Action Boundary

Handlers call daemon actions; they do not operate app-server or side registry primitives directly.

Runtime control stays in `ActionGateway`:

```text
parent activity inspection
parent prompt submission
side triage submission
parent interrupt before submit when requested
side ownership validation
action provenance
```

This keeps business judgment and runtime side effects separated.

## 9. Current-State Gap

Current implementation has three different dispatch shapes:

```text
app-server notification -> handle_notification(...)
mailbox.deliver        -> handle_signal(...)
mailbox.parent_required -> handle_parent_required(...)
```

The target shape is:

```text
app-server notification -> DaemonTrigger -> handler.handle(...)
mailbox.deliver        -> DaemonTrigger -> handler.handle(...)
mailbox.local_trigger  -> DaemonTrigger -> handler.handle(...)
```

After the rebuild, `mailbox.parent_required` should not remain as a daemon mailbox method.

## 10. Success Criteria

The dispatch rebuild is complete when:

- all daemon ingress paths normalize to `DaemonTrigger`;
- handler dispatch uses one trigger-facing interface;
- `mailbox.parent_required` is removed;
- `message.parent_required` is represented as `mailbox.local_trigger` with `type="message.parent_required"`;
- task checkout, message available, and message parent escalation all pass through the same trigger router;
- no business-specific method is added to the shared mailbox surface.

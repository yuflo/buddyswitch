# Current Runtime Business Support Adapter Migration Task

Date: 2026-06-02
Status: confirmed adapter migration task

## 1. Scope

This memo lists the current runtime business supports that must be adapted or explicitly preserved after the daemon
trigger-handler-action dispatch rebuild.

It excludes daemon API cleanup details already covered by:

```text
docs/memo/2026-06-02-daemon-api-surface-cleanup-task.md
```

The focus here is not the full message module implementation. It is the migration of existing runtime business support
surfaces:

```text
task input TUI
task checkout TUI
message TUI
```

For daemon-dispatched support, the target shape is:

```text
DaemonTrigger -> handler -> ActionGateway
```

## 2. Migration Guard

The migration must preserve existing behavior first, then change the entry shape.

Hard rules:

- task input TUI behavior and wrapper ownership stay unchanged;
- task checkout TUI content and checkout decision rules stay unchanged;
- parent message TUI content stays unchanged except where carrying `message_id` is required;
- side triage prompt changes are limited to binding the triggering `message_id` and using the unified local-trigger wording;
- message tool behavior, side direct-reply SOP, and message-reading APIs are deferred to Stage 3 message module work.

The dispatch rebuild must not become an excuse to redesign existing TUI behavior.

## 3. Task Input TUI Adapter

Current support:

```text
launcher input wrapper --wrapper task-tui
  -> tools/launcher/input_wrappers/task_tui.py
  -> task_tui.render_task_tui(...)
  -> parent input text
```

This is a currently running task business support, but it is not a daemon-dispatched event path.

Required migration:

- keep it outside daemon trigger routing;
- keep `task_tui.render_task_tui(...)` behavior unchanged;
- keep task input wrapper tests focused on wrapper composition;
- ensure the daemon dispatch rebuild does not pull task input TUI into daemon core.

## 4. Task Checkout TUI Adapter

Current shape:

```text
app-server notification
  -> TaskCheckoutHandler.handle_notification(...)
```

Target shape:

```text
app-server notification
  -> DaemonTrigger(type="app_server.turn_completed")
  -> TaskCheckoutHandler.handles(trigger)
  -> TaskCheckoutHandler.handle(context, state, actions, trigger)
```

Business logic remains the same:

- only react to completed turns;
- only react to this daemon's parent thread;
- ignore daemon-origin task checkout turns;
- render existing task checkout TUI through `task_tui.render_stop_task_tui(...)`;
- submit parent prompt through daemon action.

What changes:

- task checkout filtering reads normalized trigger fields instead of raw app-server notification;
- tests assert trigger-based handling, not `handle_notification`;
- task checkout no longer owns any app-server protocol parsing.

What does not change:

- task checkout TUI content;
- task checkout business decision rules;
- task domain ownership in `TaskCheckoutHandler`.

## 5. Message TUI Adapter: Message Available

Current shape:

```text
mailbox.deliver
  -> message.available signal
  -> MessageAvailableHandler.handle_signal(...)
```

Target shape:

```text
mailbox.deliver
  -> DaemonTrigger(type="message.available")
  -> MessageAvailableHandler.handles(trigger)
  -> MessageAvailableHandler.handle(context, state, actions, trigger)
```

Business logic:

- validate the message availability payload;
- require a concrete `message_id`;
- inspect parent activity through daemon action;
- parent idle: render existing parent message TUI and submit parent prompt;
- parent running: render existing side triage message TUI and submit side triage prompt;
- parent unavailable: fail handling with explicit error.

Important prompt adjustment:

- side triage should be bound to the specific `message_id`;
- the side should not infer the relevant message by scanning inbox order.

The prompt migration requirement stops at carrying the triggering `message_id`. Detailed message-reading behavior belongs
to Stage 3 message module implementation.

## 6. Message TUI Adapter: Parent Required

Current shape:

```text
mailbox.parent_required
  -> MessageAvailableHandler.handle_parent_required(...)
```

Target shape:

```text
mailbox.local_trigger(type="message.parent_required")
  -> DaemonTrigger(type="message.parent_required")
  -> MessageAvailableHandler.handles(trigger)
  -> MessageAvailableHandler.handle(context, state, actions, trigger)
```

Business logic:

- validate business payload, especially `message_id`;
- accept side-provided `reason` as context, not as daemon routing authority;
- render existing parent message TUI;
- ask daemon action to submit parent prompt with interrupt-before-submit policy.

The handler should not call side ownership validation directly. That belongs to local-trigger validation before dispatch.

## 7. Message Side Triage Prompt Adapter

The existing side triage prompt should be migrated so it is tied to the message that triggered it.

Required migration:

```text
message.available trigger payload includes message_id
  -> MessageAvailableHandler extracts message_id
  -> side triage prompt includes message_id
```

This avoids asking the side to infer the relevant message from inbox order.

The existing side escalation instruction should be migrated to the unified local-trigger wording:

```text
mailbox.local_trigger(type="message.parent_required", payload={message_id, reason})
```

Detailed message tool contracts, side reply behavior, and exact message reading are Stage 3 message module work, not
part of this migration memo.

## 8. Handler Registration Adjustment

Current registrations are split:

```text
notification_handlers: TaskCheckoutHandler
mailbox_handlers: MessageAvailableHandler
```

After trigger router adoption, registrations should be trigger-handler registrations.

Expected shape:

```text
daemon_handlers:
  - TaskCheckoutHandler
  - MessageAvailableHandler
```

Ingress adapters can still be source-specific, but handler dispatch should not be split by protocol family.

Task input TUI remains outside this handler registration because it is an input wrapper, not a daemon trigger handler.

## 9. Test Adjustment

Existing daemon business-handler tests should move from entry-method testing to trigger behavior testing.

Required coverage:

- task input TUI wrapper still composes task context outside daemon dispatch;
- task input TUI rendered content remains behavior-equivalent;
- task checkout handles `app_server.turn_completed`;
- task checkout TUI rendered content remains behavior-equivalent;
- message available with parent idle submits parent prompt;
- message available with parent running submits side triage prompt;
- message parent required submits parent prompt with interrupt-before-submit policy;
- parent message TUI rendered content remains behavior-equivalent except required `message_id` binding;
- wrong actor and wrong side are rejected before handler business logic;
- unknown trigger type is ignored;
- no business handler depends on raw mailbox method names.

## 10. Non-Goals

Do not adjust case 1/case 3 message TUI copy beyond what is required to carry `message_id`.

Do not redesign task input TUI or task checkout TUI copy.

Do not add delayed-message routing.

Do not add generic subscriptions.

Do not add a workflow DSL or routing config.

Do not preserve the old handler methods as compatibility paths once the rebuild lands.

Do not define message tool contracts, side direct-reply behavior, or exact message read APIs here.

## 11. Success Criteria

Adapter migration is complete when:

- task input TUI remains a launcher input wrapper and is not folded into daemon dispatch;
- task input TUI behavior is unchanged from the user's point of view;
- `TaskCheckoutHandler` and `MessageAvailableHandler` both handle `DaemonTrigger`;
- task checkout behavior is unchanged from the user's point of view;
- existing message TUI routing still supports parent idle, side triage, and side-to-parent escalation;
- side escalation uses `mailbox.local_trigger(type="message.parent_required")`;
- side triage prompt carries the triggering `message_id`;
- old business-specific dispatch methods are removed, not retained as fallback compatibility.

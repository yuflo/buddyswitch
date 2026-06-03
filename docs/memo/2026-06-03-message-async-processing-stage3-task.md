# Message Async Processing Stage 3 Task

Date: 2026-06-03
Status: confirmed implementation memo

## 1. Task

Rebuild the message module into disposition-driven parent/side async processing.

Target shape:

```text
message.available
  -> message handler checks parent activity
  -> parent idle: parent handles message prompt
  -> parent running: side triages message
  -> side either handles independently or marks parent required
```

This is a direct replacement task. Do not keep old paths, compatibility aliases, or dual behavior.

The daemon is already a generic trigger dispatcher plus runtime provider. The message module owns message state, business
judgment, message tools, and prompt content.

## 2. Current Tool Facts

Current message tools:

```text
message__contacts
message__send
message__list
message__conversation
```

Current `message__list` options:

```text
role?
q?
limit?
```

Keep these as general inbox-list filters. Do not make `message__list` the primary way to process a prompt that already
contains one exact `message_id`.

`message__conversation` currently supports:

```text
target_actor_address={role_id, actor_id}
role="..."
```

For this task, `role` support must be removed from `message__conversation`.

Reason:

- message processing for one inbound message already knows the sender actor address;
- `target_actor_address` is the correct selector;
- `actor_id` alone is not enough because actor identity is `role_id + actor_id`;
- `role` adds a useless model choice for the current path.

Final `message__conversation` selector:

```text
message__conversation(target_actor_address={ "role_id": "...", "actor_id": "..." }, q?, limit?)
```

## 3. Disposition Model

Use these durable dispositions:

```text
unseen
absorbed
replied
needs_parent
```

Do not add `seen`.

Meaning:

- `unseen`: message exists in the target inbox and has no completed disposition.
- `absorbed`: message was processed and no reply is needed.
- `replied`: message was processed by sending a reply.
- `needs_parent`: side thread determined parent must process it.

`needs_parent` is a handoff/lock state, not final completion.

Valid transitions:

```text
unseen -> absorbed
unseen -> replied
unseen -> needs_parent
needs_parent -> absorbed
needs_parent -> replied
```

Invalid transitions must be rejected by message business logic. This is the main duplicate-processing guard.

## 4. Tool Changes

### Keep

#### `message__contacts`

Keep for normal outbound contact discovery.

It is not part of normal prompt-driven reply handling because an inbound message already has a sender actor address.

#### `message__send`

Keep for normal outbound sending and direct replies.

For inbound processing:

```text
message__send(target_actor_address=<sender>, content="...", reply_to=<message_id>)
```

When `reply_to` is a valid processable inbound message, successful send must transition the original message:

```text
unseen -> replied
needs_parent -> replied
```

#### `message__list`

Keep for general inbox scanning and filters.

Current options stay:

```text
role?
q?
limit?
```

Do not use it as the main path for prompt-driven processing of a known `message_id`.

#### `message__conversation`

Keep only target actor-address conversation reads.

Remove `role` selector from:

```text
scripts/env/tools/message/tool.py
scripts/env/domain/messages.py
scripts/env/tools/message/_impl.py
tests/test_message_env_tool.py
tests/test_env_tool_schema_contract.py
```

### Add

#### `message__get(message_id)`

Purpose:

- read one exact message by id;
- validate that it is visible/processable by the active actor;
- return message content, sender actor address, target actor address, reply/disposition metadata.

Used by all three prompt paths.

#### `message__mark(...)`

Working name. Keep it if it remains clear during implementation.

Purpose:

- set non-reply dispositions;
- enforce valid transitions;
- prevent duplicate side/parent processing.

Supported calls:

```text
message__mark(message_id, disposition="absorbed")
message__mark(message_id, disposition="needs_parent", reason="...")
```

When `disposition="needs_parent"` succeeds, the message module must trigger parent handling internally. The model should
not call daemon mailbox, launcher APIs, or a parent-handoff tool.

Do not add low-reuse tools whose only purpose is to tell parent to handle one message.

## 5. Prompt Ownership

All message prompts are rendered by the message module:

```text
render_parent_message_prompt(...)
render_side_triage_prompt(...)
render_parent_required_prompt(...)
```

Daemon only submits prompt text through runtime methods:

```text
runtime.submit_parent_prompt(...)
runtime.submit_side_triage_prompt(...)
runtime.submit_parent_prompt(..., interrupt_policy="before_submit")
```

Daemon does not render message prompts, inspect message disposition, or understand message business rules.

## 6. Case Routing

### Case 1: Parent Idle

```text
message.available
  -> parent_activity() == idle
  -> render_parent_message_prompt(...)
  -> runtime.submit_parent_prompt(..., interrupt_policy="none")
```

Final disposition:

```text
unseen -> absorbed
unseen -> replied
```

### Case 2: Parent Running, Side Handles Independently

```text
message.available
  -> parent_activity() == running
  -> render_side_triage_prompt(...)
  -> runtime.submit_side_triage_prompt(...)
  -> side calls message__get(...)
  -> side calls message__send(..., reply_to=...) or message__mark(..., disposition="absorbed")
```

Final disposition:

```text
unseen -> absorbed
unseen -> replied
```

Parent is not interrupted.

### Case 3: Parent Running, Parent Required

```text
message.available
  -> parent_activity() == running
  -> render_side_triage_prompt(...)
  -> runtime.submit_side_triage_prompt(...)
  -> side calls message__get(...)
  -> side calls message__mark(..., disposition="needs_parent", reason=...)
  -> message module renders parent-required prompt
  -> runtime.submit_parent_prompt(..., interrupt_policy="before_submit")
```

Final disposition:

```text
unseen -> needs_parent -> absorbed
unseen -> needs_parent -> replied
```

Parent is interrupted before receiving the parent-required prompt.

Target daemon unavailable is not one of these cases. It remains a `message__send` reachability/delivery failure.

## 7. Prompt 1: Parent Message TUI

Renderer:

```text
render_parent_message_prompt(message_id, source_actor_address, target_actor_address)
```

Prompt:

```text
[MESSAGE AVAILABLE]

Message id: {message_id}
From: {source_actor_address}
To: {target_actor_address}

A direct message is available for this actor.

Process this exact message. Do not assume a reply is required.

Steps:
1. Call message__get with message_id="{message_id}".
2. Read the message content and sender.
3. If prior context is needed, call message__conversation with the sender actor address.
4. If a reply is needed, call message__send with:
   - target_actor_address = the sender actor address from the message
   - content = your reply
   - reply_to = "{message_id}"
5. If no reply is needed, call message__mark with:
   - message_id = "{message_id}"
   - disposition = "absorbed"

Finish after the message is marked "absorbed" or "replied".
```

## 8. Prompt 2: Side Triage Prompt

Renderer:

```text
render_side_triage_prompt(message_id, source_actor_address, target_actor_address)
```

Prompt:

```text
[MESSAGE TRIAGE]

Message id: {message_id}
From: {source_actor_address}
To: {target_actor_address}

A direct message arrived while the parent thread is running.

Your job is to process this exact message without interrupting the parent unless parent involvement is necessary.

Steps:
1. Call message__get with message_id="{message_id}".
2. Read the message content and sender.
3. If prior context is needed, call message__conversation with the sender actor address.
4. Decide one outcome:

Outcome A: You can handle it independently.
- If a reply is needed, call message__send with:
  - target_actor_address = the sender actor address from the message
  - content = your reply
  - reply_to = "{message_id}"
- If no reply is needed, call message__mark with:
  - message_id = "{message_id}"
  - disposition = "absorbed"

Outcome B: Parent must process it.
- Use this only when the message conflicts with, corrects, interrupts, or materially changes the parent thread's current work,
  or when answering safely requires parent context.
- Call message__mark with:
  - message_id = "{message_id}"
  - disposition = "needs_parent"
  - reason = a concise explanation of why parent involvement is required

Use only the message tools named in this prompt.
Finish after exactly one disposition path succeeds.
```

Do not include parent thread id in this prompt. Parent/thread linkage is internal runtime state.

## 9. Prompt 3: Parent Required Message TUI

Renderer:

```text
render_parent_required_prompt(message_id, source_actor_address, target_actor_address, reason)
```

Prompt:

```text
[MESSAGE NEEDS PARENT]

Message id: {message_id}
From: {source_actor_address}
To: {target_actor_address}
Reason from side triage:
{reason}

A side thread reviewed this message and determined that parent processing is required.

Process this exact message. Do not assume a reply is required.

Steps:
1. Call message__get with message_id="{message_id}".
2. Read the message content and sender.
3. If prior context is needed, call message__conversation with the sender actor address.
4. If a reply is needed, call message__send with:
   - target_actor_address = the sender actor address from the message
   - content = your reply
   - reply_to = "{message_id}"
5. If no reply is needed, call message__mark with:
   - message_id = "{message_id}"
   - disposition = "absorbed"

Finish after the message is marked "absorbed" or "replied".
```

## 10. Required Module Changes

### Message Tool Definition

File:

```text
scripts/env/tools/message/tool.py
```

Required changes:

- add `get`;
- add `mark`;
- remove `role` from `conversation` input schema;
- update `conversation` description, preconditions, and do-not-use text to target actor address only.

### Message Implementation

File:

```text
scripts/env/tools/message/_impl.py
```

Required changes:

- add `get_message(...)`;
- add `mark_message(...)`;
- remove conversation role branch and `selector={"role": ...}`;
- update `message__send(..., reply_to=...)` to transition the original inbound message to `replied`;
- when `message__mark(..., disposition="needs_parent")` succeeds, request parent handling internally.

### Message Domain Rules

File:

```text
scripts/env/domain/messages.py
```

Required changes:

- add disposition validation and transition rules;
- add processable-message validation for `get`, `mark`, and reply transitions;
- remove `role` selector support from `prepare_conversation_request(...)`;
- remove `target_role` support from `filter_conversation_messages(...)`.

### Message Repository / Stored Rows

Files depend on current repo structure.

Required durable fields:

```text
disposition
disposition_reason
disposition_updated_at
processed_by_actor_address
```

Keep the field set minimal. Add only what is needed to enforce transitions and render parent-required prompts.

### Message Daemon Handler

File:

```text
tools/launcher/message_available_handler.py
```

Required changes:

- move prompt strings to message-owned render functions;
- keep `message.available` as the only current daemon trigger handled here;
- parent idle submits `render_parent_message_prompt(...)`;
- parent running submits `render_side_triage_prompt(...)`;
- do not reintroduce `message.parent_required`;
- do not expose daemon mailbox details in prompts.

### Parent-Required Runtime Entry

Use message module internals after `message__mark(..., disposition="needs_parent")`.

Required behavior:

- validate the message is still in a state that can request parent;
- render `render_parent_required_prompt(...)`;
- call daemon runtime parent submit with `interrupt_policy="before_submit"`.

Do not expose this as a model-facing native tool.

## 11. Required Test Changes

### Tool Schema Tests

Update tests to prove:

- `message.get` exists;
- `message.mark` exists;
- `message.conversation` no longer accepts `role`;
- `message.conversation` requires `target_actor_address`;
- `message.conversation(role=...)` is rejected.

### Message Behavior Tests

Add tests for:

- `message.get` returns one exact visible message;
- `message.get` rejects invisible or unknown message ids;
- `message.mark(..., absorbed)` transitions `unseen -> absorbed`;
- `message.mark(..., needs_parent)` transitions `unseen -> needs_parent` and stores reason;
- invalid transitions are rejected;
- `message.send(..., reply_to=...)` transitions `unseen -> replied`;
- `message.send(..., reply_to=...)` transitions `needs_parent -> replied`;
- duplicate side/parent processing is rejected.

### Conversation Cleanup Tests

Remove or rewrite tests that currently expect:

```text
message__conversation(role=...)
selector={"role": ...}
exactly one of target_actor_address or role
```

### Prompt Tests

Add tests for:

- `render_parent_message_prompt(...)` exact key content;
- `render_side_triage_prompt(...)` exact key content;
- `render_parent_required_prompt(...)` exact key content;
- side prompt does not include parent thread id;
- prompts do not expose daemon, launcher, parent thread id, or `message.parent_required` details;
- prompts do not imply every message must be replied to.

### Handler Tests

Update tests to prove:

- parent idle path submits parent prompt;
- parent running path submits side triage prompt;
- handler does not handle `message.parent_required`;
- handler does not contain old local-trigger parent-required text.

## 12. Explicit Removals

Remove these paths completely:

```text
message.parent_required daemon trigger path
mailbox.local_trigger(type="message.parent_required")
message__conversation(role=...)
conversation role selector implementation
conversation role selector tests
```

Do not add:

```text
message__parent_required
message__handoff_to_parent
side__handoff_to_parent
```

Do not keep compatibility aliases for removed fields or tools.

## 13. Verification Commands

Focused:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_message_available_handler.py -q
python3 -m pytest tests/test_daemon_mailbox.py -q
python3 -m pytest tests/test_daemon_core_decoupling.py -q
```

Broader:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest --collect-only -q tests
git diff --check
```

Source audits:

```bash
rg -n 'message\.parent_required|mailbox\.local_trigger\(type="message\.parent_required"|handoff_to_parent|message__parent_required|message__handoff_to_parent' scripts tools tests
rg -n 'message__conversation\(role=|role selector|exactly one of target_actor_address or role|target_role|selector = \{"role"' scripts/env/tools/message scripts/env/domain/messages.py tests/test_message_env_tool.py tests/test_env_tool_schema_contract.py
rg -n 'Parent thread id|daemon mailbox|launcher APIs|message\.parent_required' tools/launcher/message_available_handler.py scripts/env/tools/message scripts/env/domain/messages.py
```

Expected source audit result:

- no old parent-required daemon path;
- no conversation role selector;
- no prompt exposing parent thread id or daemon control details.

## 14. Done Criteria

The task is done when:

- message dispositions are durable and transition-validated;
- `unseen`, `absorbed`, `replied`, and `needs_parent` are the only processing dispositions;
- no `seen` state exists;
- `message__get` exists and targets one exact message;
- `message__mark` exists for `absorbed` and `needs_parent`;
- `message__send(..., reply_to=...)` marks the original message as `replied`;
- `message__conversation` only supports `target_actor_address`;
- all three prompt renderers exist in the message module;
- parent idle, side independent, and parent-required flows are covered by tests;
- old parent-required daemon/local-trigger paths are removed;
- no compatibility or dual-track behavior remains;
- focused and broader verification pass.

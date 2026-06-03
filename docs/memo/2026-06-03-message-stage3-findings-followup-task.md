# Message Stage 3 Findings Follow-up Task

Date: 2026-06-03
Status: confirmed follow-up task

## 1. Task

Finish the Stage 3 message async-processing follow-up by fixing three review findings and bringing
the message tool catalog plus runtime feedback up to the `docs/bitter` standard.

This is a focused follow-up. Do not add new dispositions, workflow engines, outbox systems,
transaction frameworks, or compatibility aliases. Keep the message module as the owner of message
business semantics.

Relevant principle:

```text
docs/bitter/2026-05-18-tool-skill-layering-principles.md
```

The host must be able to choose and recover from message tools by reading the tool catalog and tool
responses. It must not need hidden implementation knowledge, AGENTS prose, or service-code reading
to understand what a message action did.

## 2. Current Code Facts

Primary files:

```text
scripts/env/domain/messages.py
scripts/env/tools/message/_impl.py
scripts/env/tools/message/tool.py
tests/test_message_env_tool.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_semantic_contract.py
tests/test_env_tool_response_contract.py
```

Current findings:

- `scripts/env/domain/messages.py` still has self checks that compare only `actor_id`.
- `message.send(reply_to=...)` delivers the reply, then saves the original message as `replied`
  once. There is no bounded retry around the final disposition save.
- `message.mark(disposition="needs_parent")` currently saves `needs_parent` before submitting the
  parent prompt. Its failure feedback says the message was already marked `needs_parent` but the
  parent prompt failed. That is the old order and must be replaced.
- `message.mark` schema already exposes only `absorbed` and `needs_parent`; keep that boundary.
- The tool descriptions and rejection feedback do not yet state the final host-visible contracts
  clearly enough.

## 3. Final Rules

### 3.1 Actor identity

Actor identity is full `ActorAddress`.

All self checks must use complete `ActorAddress` equality:

```text
role_id + actor_id
```

Apply this to:

- `message.send` self-send rejection;
- `message.conversation` self-conversation rejection;
- `message.contacts` sendable row calculation.

Do not add an actor-id-only semantic branch. The rule is only this: identical full `ActorAddress`
is self.

### 3.2 `message.send(reply_to=...)`

Keep the business order:

```text
create reply
deliver reply
save original as replied
```

Success means both effects are true:

- the reply message is durable and delivered;
- the original inbound message has disposition `replied`.

Saving the original as `replied` must use bounded retry:

```text
attempt 1: immediately
attempt 2: after about 100 ms
attempt 3: after about 250 ms
```

After the third failed save, return failure.

Actual state after that failure is not hidden:

- reply has already been delivered;
- original remains in its previous disposition;
- if original was `unseen`, it is still `unseen`;
- if original was `needs_parent`, it is still `needs_parent`.

Do not add `partial` or `indeterminate` as message dispositions. Do not add a product-level state
machine for this rare storage failure. The tool response must state the concrete effect and the
remaining original disposition.

### 3.3 `message.mark(disposition="needs_parent")`

Change the order:

```text
submit parent prompt
save original as needs_parent
```

The prompt submission must happen first because a message saved as `needs_parent` without a parent
prompt will not be handled.

`message.mark` public disposition targets remain:

```text
absorbed
needs_parent
```

It must not expose public marking to:

```text
replied
unseen
any other disposition
```

`replied` is owned by `message.send(reply_to=...)`. `unseen` is an initial or retained processing
state, not a public mark target.

For `needs_parent`, parent prompt submission uses the same bounded retry:

```text
attempt 1: immediately
attempt 2: after about 100 ms
attempt 3: after about 250 ms
```

If all three prompt-submit attempts fail:

- return failure;
- leave the original message in its previous disposition, normally `unseen`;
- report `state_changed=false`;
- do not save `needs_parent`.

After parent prompt submission succeeds, saving the original as `needs_parent` also uses the same
bounded retry.

If all three `needs_parent` saves fail:

- return failure;
- parent prompt has already been submitted;
- original remains in its previous disposition, normally `unseen`;
- the response must state that the prompt was submitted and the disposition save failed.

There must be no success response where:

```text
message disposition = needs_parent
parent prompt was not submitted
```

## 4. Implementation Changes

### 4.1 ActorAddress equality

Modify `scripts/env/domain/messages.py`:

- Replace self-send `actor_id` comparison with `target_actor == source_actor_address`.
- Replace self-conversation `actor_id` comparison with `target_actor == source_actor_address`.
- Replace contact self detection with `ActorAddress.from_payload(...) == active_actor_address`.
- Update error text to say full actor address, not actor id only.
- Keep `_same_actor_pair(...)` behavior aligned with full address pairs.

Tests:

- Add or update a test that identical full `ActorAddress` is rejected for self-send.
- Add or update a test that identical full `ActorAddress` is rejected for self-conversation.
- Add or update a test that contacts marks only the active full `ActorAddress` as not sendable.
- Do not add an actor-id-only semantic branch.

### 4.2 Shared bounded retry helper

Add the smallest local helper in `scripts/env/tools/message/_impl.py`.

Suggested shape:

```text
MESSAGE_MUTATION_RETRY_DELAYS_SECONDS = (0.0, 0.1, 0.25)
```

Use it for:

- saving original as `replied` after `message.send(reply_to=...)` delivery;
- submitting parent prompt in `message.mark(needs_parent)`;
- saving original as `needs_parent` after parent prompt submission.

The helper must be local and concrete. Do not add a generic retry framework. Make tests fast by
allowing the sleep function to be patched or skipped.

### 4.3 `message.send(reply_to=...)`

Modify `scripts/env/tools/message/_impl.py`:

- After reply delivery succeeds, transition the original to `replied`.
- Save that transition with the 3-attempt retry.
- On success, include the original message disposition change in response data.
- On final save failure, return a rejection that states:
  - reply message id;
  - delivery status `delivered`;
  - original message id;
  - original previous disposition;
  - original final disposition, which remains the previous disposition;
  - `state_changed=true`;
  - `durability=durable`;
  - retry guidance that says not to blindly send another reply.

Do not report this as a new message disposition. It is a failed tool call with a concrete durable
side effect.

### 4.4 `message.mark(absorbed)`

Keep this path simple:

```text
validate processable inbound message
save absorbed
return success
```

No parent prompt work applies.

### 4.5 `message.mark(needs_parent)`

Modify `scripts/env/tools/message/_impl.py`:

- Validate the request and current processable inbound message first.
- Render the parent-required prompt from the current message.
- Submit the parent prompt with the 3-attempt retry.
- If prompt submission fails after 3 attempts, return rejection with `state_changed=false` and keep
  the original disposition unchanged.
- If prompt submission succeeds, transition the current message to `needs_parent`.
- Save `needs_parent` with the 3-attempt retry.
- If save fails after 3 attempts, return rejection with `state_changed=true` because the parent
  prompt was submitted. The response must state that the original message disposition remains
  unchanged.
- If save succeeds, return success with `parent_request` and the updated message.

Remove the old failure wording that claims the message was already saved as `needs_parent` before
the parent prompt failed. That claim must not exist after the order changes.

## 5. Tool Catalog Requirements

Modify `scripts/env/tools/message/tool.py` so the catalog is host-decidable.

### 5.1 Tool-level description

State that message tools cover:

- online actor contact discovery;
- direct actor-address sends;
- exact processable inbound reads;
- non-reply disposition marking.

State that messages do not mutate tracks, tasks, artifacts, comments, requests, browser state, or
actor private files.

### 5.2 `message.send`

Description must cover both modes:

- direct outbound message;
- reply to one processable inbound message with `reply_to`.

`reply_to` field description must state:

- it must reference a processable inbound message addressed to the active actor;
- success marks that original message as `replied` after delivery.

`success_effect` must state:

- creates and delivers one durable message;
- when `reply_to` is provided, also transitions the original processable inbound message to
  `replied`.

`failure_state_guarantee` must state:

- reachability and payload rejections do not mutate state;
- delivery failures clean up the created message or report delivery cleanup uncertainty;
- reply disposition save failure can leave the delivered reply durable while the original remains in
  its previous disposition.

`do_not_use_when` must include:

- use `message.mark(absorbed)` when no reply is needed;
- use `message.mark(needs_parent)` when side triage needs parent handling.

### 5.3 `message.mark`

Description must state:

```text
Set only non-reply processing dispositions: absorbed or needs_parent.
```

`disposition` field description must state:

```text
Allowed values are absorbed and needs_parent. Use message.send(reply_to=...) for replied.
```

`reason` field description must state:

```text
Required and non-empty for needs_parent; ignored or omitted for absorbed.
```

`success_effect` must state:

- `absorbed` saves the message as processed without a reply;
- `needs_parent` submits the parent prompt first, then saves the message as `needs_parent`.

`failure_state_guarantee` must state:

- validation failures do not mutate state;
- `needs_parent` prompt-submit failure leaves the message in its previous disposition;
- `needs_parent` save failure after prompt submit leaves the message in its previous disposition but
  the parent prompt was already submitted.

`do_not_use_when` must state:

- use `message.send(reply_to=...)` when replying;
- do not use `message.mark` as a generic disposition editor.

### 5.4 `message.get`

Keep this clear:

- reads one exact processable inbound message;
- does not change disposition;
- processable means `unseen` or `needs_parent`.

### 5.5 `message.contacts`

Make sendability wording full-address based:

- only the active full `ActorAddress` row is not sendable as self;
- do not describe self as actor-id-only.

## 6. Tool Feedback Requirements

Modify `scripts/env/tools/message/_impl.py` so responses close the loop after every call.

Required success feedback:

- `message.send` success with no `reply_to`: state one new durable message id and delivery status.
- `message.send` success with `reply_to`: state new reply message id, delivery status, original
  message id, and original final disposition `replied`.
- `message.mark(absorbed)` success: state original message id and final disposition `absorbed`.
- `message.mark(needs_parent)` success: state parent prompt submitted, parent request details, and
  final disposition `needs_parent`.

Required rejection feedback:

- Payload and scope rejections: `state_changed=false`; identify correctable fields.
- Reachability rejection before message creation: `state_changed=false`; no readable message was
  created.
- Delivery failure with cleanup success: `state_changed=false`; created reply/message was cleaned.
- Delivery failure with cleanup failure: keep existing `E_MESSAGE_SEND_INDETERMINATE` style because
  this is an existing delivery-cleanup uncertainty path, not a message disposition.
- Reply disposition save final failure after delivery: `state_changed=true`; reply id is durable;
  original final disposition is the previous disposition; retry guidance says not to blindly send a
  second reply.
- `needs_parent` prompt-submit final failure: `state_changed=false`; original final disposition is
  the previous disposition; retryable after parent runtime availability is restored.
- `needs_parent` save final failure after prompt submit: `state_changed=true`; parent prompt was
  submitted; original final disposition is the previous disposition; retry guidance says to inspect
  message state before repeating the handoff.

Every non-trivial success or rejection should include object ids and actual final state in `extra`.
Do not rely on `ok=true` or a generic human summary.

## 7. Test Requirements

Focused tests should prove persisted state and host-visible response semantics.

### 7.1 ActorAddress tests

Update `tests/test_message_env_tool.py`:

- self-send rejects identical full `ActorAddress`;
- self-conversation rejects identical full `ActorAddress`;
- contacts sendability uses identical full `ActorAddress`, not actor id text.

### 7.2 `message.send(reply_to=...)` tests

Add tests for:

- success from `unseen` to `replied`;
- success from `needs_parent` to `replied`;
- save `replied` fails on attempt 1 and succeeds on attempt 2;
- save `replied` fails on all 3 attempts and returns failure with:
  - reply delivered;
  - original final disposition unchanged;
  - `state_changed=true`;
  - retry guidance does not tell the host to send another reply.

Keep the existing delivery-failure test that proves original does not transition when reply delivery
fails.

### 7.3 `message.mark` tests

Add or update tests for:

- `absorbed` transitions from `unseen`;
- `absorbed` transitions from `needs_parent`;
- `needs_parent` submits parent prompt before saving disposition;
- parent prompt attempt 1 fails and attempt 2 succeeds;
- parent prompt fails on all 3 attempts and leaves original disposition unchanged with
  `state_changed=false`;
- parent prompt succeeds, saving `needs_parent` fails on attempt 1 and succeeds on attempt 2;
- parent prompt succeeds, saving `needs_parent` fails on all 3 attempts and leaves original
  disposition unchanged with `state_changed=true`.

### 7.4 Tool catalog tests

Update `tests/test_env_tool_schema_contract.py` and `tests/test_env_tool_semantic_contract.py`:

- `message.mark` enum remains exactly `["absorbed", "needs_parent"]`;
- `message.mark` description or semantic fields include `absorbed`, `needs_parent`, and
  `message.send(reply_to=...)`;
- `message.send` description or semantic fields include `reply_to` and `replied`;
- catalog fields no longer imply that `message.mark` is a generic disposition editor.

### 7.5 Response contract tests

Update `tests/test_env_tool_response_contract.py` or focused message response tests:

- rejected `needs_parent` prompt-submit failure says state did not change;
- rejected `needs_parent` save failure after prompt submit says state changed because parent prompt
  was submitted;
- rejected reply-disposition save failure after delivery states reply id and unchanged original
  disposition.

## 8. Verification

Run focused tests first:

```text
pytest tests/test_message_env_tool.py -q
pytest tests/test_env_tool_schema_contract.py -q
pytest tests/test_env_tool_semantic_contract.py -q
pytest tests/test_env_tool_response_contract.py -q
```

Then run broader relevant checks:

```text
pytest --collect-only -q
pytest tests/test_buddyswitch_launcher.py -q
git diff --check
```

Definition of done:

- all three findings are fixed;
- message tool descriptions match final behavior;
- message tool feedback states actual effects and final state;
- tests prove persisted state, response feedback, and catalog semantics;
- no old `needs_parent` failure wording remains;
- no self check compares only `actor_id`.

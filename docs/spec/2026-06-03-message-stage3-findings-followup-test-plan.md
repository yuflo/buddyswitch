# Message Stage 3 Findings Follow-up Test Plan

Date: 2026-06-03
Source memo: `docs/memo/2026-06-03-message-stage3-findings-followup-task.md`

## Goal

Prove the message tool catalog, message domain checks, mutation ordering, bounded retry behavior,
and tool responses match the final Stage 3 follow-up contract.

This plan is requirement driven. Tests must prove host-visible behavior and persisted message state,
not merely fit the current implementation. Do not add compatibility dispositions, workflow engines,
outbox systems, transaction frameworks, or actor-id-only branches.

## Resource Safety

The required focused tests are in-process env-tool tests. Follow
`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`:

- Run focused message/schema/semantic/response tests before broad launcher verification.
- Patch retry sleep in focused tests so retry behavior is proven without slowing the suite.
- Do not run broad service-starting tests until focused tests pass.
- If a broad check starts persistent services, inspect residual processes before completion.

## Functional Coverage

### ActorAddress Identity

Files:

- `scripts/env/domain/messages.py`
- `tests/test_message_env_tool.py`

Required tests:

- `message.send` rejects only identical full `ActorAddress` self-send: same `role_id` and same
  `actor_id`.
- `message.conversation` rejects only identical full `ActorAddress` self-conversation.
- `message.contacts` marks only the active full `ActorAddress` row as not sendable.
- A contact row with the same `actor_id` text but a different `role_id` remains sendable when the
  actor address is valid and online.

Expected evidence:

- Error text and `why_blocked` refer to full actor address, not actor id alone.
- No self-check condition compares only `actor_id`.

### `message.send(reply_to=...)`

Files:

- `scripts/env/tools/message/_impl.py`
- `tests/test_message_env_tool.py`
- `tests/test_env_tool_response_contract.py`

Required tests:

- Reply success from `unseen` creates and delivers a durable reply and saves the original as
  `replied`.
- Reply success from `needs_parent` creates and delivers a durable reply and saves the original as
  `replied`.
- Saving the original as `replied` fails on attempt 1 and succeeds on attempt 2.
- Saving the original as `replied` fails on all 3 attempts and returns rejection with:
  - `state_changed=true`;
  - `durability=durable`;
  - reply message id and `delivery_status=delivered`;
  - original message id;
  - previous disposition;
  - final disposition unchanged from previous disposition;
  - retry guidance that tells the host not to blindly send another reply.
- Existing delivery failure behavior still leaves the original disposition unchanged.

Expected evidence:

- The retry helper attempts exactly 3 saves with delays `0.0`, about `0.1`, and about `0.25`.
- Tests patch the sleep function and assert retry delay calls without actually sleeping.

### `message.mark(absorbed)`

Files:

- `scripts/env/tools/message/_impl.py`
- `tests/test_message_env_tool.py`

Required tests:

- `absorbed` transitions from `unseen`.
- `absorbed` transitions from `needs_parent`.
- Success response includes original message id and final disposition `absorbed`.
- No parent prompt is submitted on the `absorbed` path.

### `message.mark(needs_parent)`

Files:

- `scripts/env/tools/message/_impl.py`
- `tests/test_message_env_tool.py`
- `tests/test_env_tool_response_contract.py`

Required tests:

- Parent prompt submission happens before saving `needs_parent`.
- Parent prompt attempt 1 fails and attempt 2 succeeds, then the message saves as `needs_parent`.
- Parent prompt fails on all 3 attempts and leaves the original disposition unchanged with
  `state_changed=false`.
- Parent prompt succeeds, saving `needs_parent` fails on attempt 1 and succeeds on attempt 2.
- Parent prompt succeeds, saving `needs_parent` fails on all 3 attempts and leaves the original
  disposition unchanged with `state_changed=true`.
- Failure after prompt submit states that the parent prompt was submitted and disposition save
  failed.
- There is no success response where disposition is `needs_parent` and parent prompt submission did
  not happen.

Expected evidence:

- Old wording such as "message was marked needs_parent, but parent prompt submission failed" is gone.
- Rejection `extra` carries object ids, prompt submission state, previous disposition, and final
  disposition.

### Tool Catalog Semantics

Files:

- `scripts/env/tools/message/tool.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`

Required tests:

- Tool-level message description covers contact discovery, direct actor-address sends, exact
  processable inbound reads, and non-reply disposition marking.
- Tool-level fields state messages do not mutate tracks, tasks, artifacts, comments, requests,
  browser state, or actor private files.
- `message.send` description covers direct outbound sends and `reply_to` replies.
- `message.send.reply_to` field states it must reference a processable inbound message addressed to
  the active actor and success marks the original as `replied` after delivery.
- `message.send.success_effect` and `failure_state_guarantee` describe durable delivery, reply
  disposition transition, delivery cleanup, cleanup uncertainty, and reply-disposition save failure.
- `message.mark` exposes exactly `["absorbed", "needs_parent"]`.
- `message.mark` description and semantic fields state it is not a generic disposition editor and
  that `replied` is owned by `message.send(reply_to=...)`.
- `message.get` states it reads one exact processable inbound message without changing disposition.
- `message.contacts` sendability wording is full-address based.

## Verification Commands

Focused verification:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
```

Source audits:

```bash
rg -n 'target_actor\.actor_id == source_actor_address\.actor_id|actor_address\["actor_id"\] == active_actor_address\.actor_id|message was marked needs_parent, but parent prompt submission failed' scripts/env/domain/messages.py scripts/env/tools/message/_impl.py
rg -n 'partial|indeterminate|outbox|workflow engine|transaction framework' scripts/env/domain/messages.py scripts/env/tools/message/_impl.py scripts/env/tools/message/tool.py
rg -n 'message\.mark|message\.send|reply_to|needs_parent|replied|ActorAddress' scripts/env/tools/message/tool.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py
```

The first audit must return no matches. The second audit may return the existing
`E_MESSAGE_SEND_INDETERMINATE` delivery-cleanup uncertainty path only; it must not introduce a
message disposition or framework.

Broader verification after focused tests pass:

```bash
python3 -m pytest --collect-only -q tests
git diff --check
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

If the launcher test starts persistent services, inspect residual app-server, broker, browser, and
daemon processes before claiming completion.

## Review Checklist

- Full `ActorAddress` equality is the only self identity rule.
- Reply delivery and original `replied` save follow create -> deliver -> save original.
- Reply disposition save failures report the durable delivered reply and unchanged original state.
- `needs_parent` follows prompt submit -> save disposition.
- `needs_parent` prompt-submit failures do not save `needs_parent`.
- `needs_parent` save failures after prompt submit report the submitted prompt and unchanged
  original state.
- Tool descriptions and response extras are sufficient for a host to choose and recover without
  reading implementation code.
- `message.mark` remains limited to `absorbed` and `needs_parent`.
- No new dispositions, aliases, outbox systems, workflow engines, or generic retry framework exist.

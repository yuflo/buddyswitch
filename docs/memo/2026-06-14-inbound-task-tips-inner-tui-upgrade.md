# Inbound Task Tips InnerTUI Upgrade

Date: 2026-06-14
Status: design memo for implementation

## Summary

This memo defines the second follow-up task after the `track.comment.added` daemon state-root bug
fix.

The goal is to improve inbound message and Track comment prompts so actors can recognize when an
inbound item is not only communication, but a concrete work demand that may need task capture,
selection, or minimal substantive execution before replying.

This is a prompt clarity task, not a task-tool semantics change.

## Relationship To Task 1

Task 1 is covered by:

```text
docs/memo/2026-06-12-track-comment-added-daemon-state-root-fix.md
```

That memo is the `track.comment.added` framework bug fix:

- bind target instance daemon object reads to `<shared-root>/state`;
- ensure `BUDDYSWITCH_STATE_ROOT=<shared-root>/state` is present in daemon start and run paths;
- make Track comment attention handlers reach parent or side prompts when the durable comment row
  exists in shared state.

Do not mix Task 1 with this memo. Task 1 should not change prompt text, task tips, message
dispositions, Track comment semantics, or runtime instance data.

## Current Bottleneck

The observed market actor failure was not caused by missing task tools. `task.capture` and
`task.select` were available, but the inbound direct-message prompt framed the turn narrowly:

```text
Process this exact message...
Finish after the message is marked "absorbed" or "replied".
```

Actors followed that narrow instruction, replied "received", and ended the turn without doing the
assigned research work or capturing it as active private actor work.

The prompt needs to make the runtime scene clearer:

- inbound communication can be FYI, status sync, clarification, or a work demand;
- a concrete assignment is not completed by acknowledgement alone;
- durable actor work may require `task.current`, `task.capture`, and `task.select`;
- small work can be completed immediately and replied with results;
- side triage should escalate parent-level work instead of pretending a lightweight reply is
  completion.

## Scope

Update inbound InnerTUI prompt text for:

- message parent prompt: `[MESSAGE AVAILABLE]`;
- message side prompt: `[MESSAGE TRIAGE]`;
- message parent-required prompt: `[MESSAGE NEEDS PARENT]`;
- Track comment parent prompt: `[TRACK COMMENT ATTENTION]`;
- Track comment side prompt: `[TRACK COMMENT TRIAGE]`.

Keep the implementation local to the source-owned prompt domains:

```text
scripts/env/domain/messages.py
scripts/env/domain/track_comments.py
```

## Out Of Scope

Do not introduce `additionalContext` for this task.

Do not send two prompts for one inbound event.

Do not add a generic prompt framework, rule engine, DSL, or cross-domain `PromptBuilder`.

Do not change task tool schemas, task action policy, resource locks, or `task.capture` semantics.

Do not add a Track comment `needs_parent` lifecycle in this task.

Do not change `message.send`, `message.mark`, `track.add_comment`, `track.list_comments`, or
`track.resolve_comment_thread` behavior.

## Implementation Shape

Do not keep growing one large string literal per prompt.

Use small domain-local section helpers so the current InnerTUI remains a single role-user input, but
the prompt can later be split or upgraded without rewriting the content.

Suggested message helpers:

```text
_message_header(...)
_message_runtime_context()
_message_parent_steps(...)
_message_side_triage_steps(...)
_message_parent_work_demand_tips()
_message_side_work_demand_tips()
_message_finish(...)
```

Suggested Track comment helpers:

```text
_track_comment_header(...)
_track_comment_runtime_context(...)
_track_comment_parent_steps(...)
_track_comment_side_steps(...)
_track_comment_parent_work_demand_tips()
_track_comment_side_work_demand_tips()
_track_comment_finish(...)
```

Keep these helpers concrete and private to their domain modules. If the same section pattern proves
useful across more inbound sources later, extract then.

## Prompt Content

The implementation should use the following content as the reviewed baseline. Minor line wrapping is
acceptable. Do not redesign these prompts during implementation without reopening the memo.

### Message Parent

```text
[MESSAGE AVAILABLE]

Message id: <message_id>
From: <source_actor_address>
To: <target_actor_address>

A direct message is available for this actor.

Required action:
Process this exact message. Do not assume a reply is required.

Runtime context:
A direct message may be simple communication, status sync, clarification, or a concrete work demand for this actor.
After reading the message, decide what kind of attention it needs.

Work-demand guidance:
If the message assigns concrete work to this actor, acknowledgement alone is usually not completion.
For durable actor work, consider task.current and task.capture/task.select before finishing.
If the requested work is small enough to complete now, do the smallest substantive work and send the result instead of only saying you will do it.
If the message is only FYI, status sync, or lightweight clarification, reply or mark absorbed normally.

Steps:
1. Call message__get with message_id="<message_id>".
2. Read the message content and sender.
3. If prior context is needed, call message__conversation with the sender actor address.
4. If the message contains concrete work that should be tracked, consider task.current and task.capture/task.select.
5. If a reply is needed, call message__send with:
   - target_actor_address = the sender actor address from the message
   - content = your reply
   - reply_to = "<message_id>"
6. If no reply is needed, call message__mark with:
   - message_id = "<message_id>"
   - disposition = "absorbed"

Finish:
Finish after the message is marked "absorbed" or "replied".
```

### Message Side Triage

```text
[MESSAGE TRIAGE]

Message id: <message_id>
From: <source_actor_address>
To: <target_actor_address>

A direct message arrived while the parent thread is running.

Required action:
Process this exact message without interrupting the parent unless parent involvement is necessary.

Runtime context:
A direct message may be simple communication, status sync, clarification, or a concrete work demand.
Side triage should not silently convert parent-level work into a lightweight acknowledgement.

Steps:
1. Call message__get with message_id="<message_id>".
2. Read the message content and sender.
3. If prior context is needed, call message__conversation with the sender actor address.
4. Decide one outcome.

Outcome A: You can handle it independently.
Use this for FYI, status checks, simple clarification, or messages that can be answered from visible runtime state.
- If a reply is needed, call message__send with:
  - target_actor_address = the sender actor address from the message
  - content = your reply
  - reply_to = "<message_id>"
- If no reply is needed, call message__mark with:
  - message_id = "<message_id>"
  - disposition = "absorbed"

Outcome B: Parent must process it.
Use needs_parent when the message requires parent-thread action on active work.
Mark needs_parent only if at least one condition is true:
1. The message changes active work: start, stop, pause, resume, reprioritize, redirect, narrow, expand, or replace current task/scope/next action.
2. The message blocks or unblocks active work: blocker, failure, missing dependency, deadline, external decision, or new constraint.
3. The message requires a parent decision or commitment.
4. The message is an instruction from a coordinating actor that should become active parent-thread input.
5. The message assigns concrete work to this actor that should not be completed as a side-triage acknowledgement.

If marking needs_parent, the reason must cite the specific condition.
Call message__mark with:
- message_id = "<message_id>"
- disposition = "needs_parent"
- reason = a concise explanation

Use only the message tools named in this prompt.

Finish:
Finish after exactly one disposition path succeeds.
```

### Message Needs Parent

```text
[MESSAGE NEEDS PARENT]

Message id: <message_id>
From: <source_actor_address>
To: <target_actor_address>

Reason from side triage:
<reason>

A side thread reviewed this message and determined that parent processing is required.

Required action:
Process this exact message. Do not assume a reply is required.

Runtime context:
This message already crossed the side-triage threshold.
It may require active-work adjustment, a decision, durable task capture, or substantive follow-through before reply.

Work-demand guidance:
If the message assigns concrete work to this actor, acknowledgement alone is usually not completion.
Consider task.current and task.capture/task.select when the work should become durable actor work.
If the requested work is small enough to complete now, do the smallest substantive work and send the result.
If only coordination is needed, reply normally.

Steps:
1. Call message__get with message_id="<message_id>".
2. Read the message content and sender.
3. If prior context is needed, call message__conversation with the sender actor address.
4. If the message contains concrete work that should be tracked, consider task.current and task.capture/task.select.
5. If a reply is needed, call message__send with:
   - target_actor_address = the sender actor address from the message
   - content = your reply
   - reply_to = "<message_id>"
6. If no reply is needed, call message__mark with:
   - message_id = "<message_id>"
   - disposition = "absorbed"

Finish:
Finish after the message is marked "absorbed" or "replied".
```

### Track Comment Parent

```text
[TRACK COMMENT ATTENTION]

Track id: <track_id>
Comment id: <comment_id>
Thread id: <thread_id>
From: <source_actor_address>
To: <target_actor_address>

One exact Track comment needs this actor's attention.

Required action:
Process this exact Track comment from Track source truth. Do not assume a reply or thread resolution is required.

Runtime context:
A Track comment may be discussion, FYI, review feedback, blocker information, or a concrete work demand.
Track tools remain the source of truth for reading and replying to the comment thread.
Task tools are only for this actor's private work tracking when the comment assigns durable work.

Work-demand guidance:
If the exact comment assigns concrete work to this actor, acknowledgement alone is usually not completion.
For durable actor work, consider task.current and task.capture/task.select.
If the requested work is small enough to complete now, do the smallest substantive work and reply with the result in the Track thread.
If the comment is only lightweight discussion, reply through Track tools when useful.

Steps:
1. Call track.open(track_id="<track_id>") to inspect the Track page.
2. Call track.list_comments(track_id="<track_id>", status="all") and find comment "<comment_id>" in thread "<thread_id>".
3. If the comment contains concrete work that should be tracked, consider task.current and task.capture/task.select.
4. If a reply is useful, call track.add_comment with:
   - track_id = "<track_id>"
   - content = your reply
   - reply_to = "<comment_id>"
5. Only if the active actor is the exact Track owner and durable closure is appropriate, call track.resolve_comment_thread with:
   - track_id = "<track_id>"
   - comment_id = "<comment_id>"
   - resolution_summary = the closure summary

Finish:
Finish after the Track comment has been handled through Track tools, and any needed actor task capture has been completed.
```

### Track Comment Side Triage

```text
[TRACK COMMENT TRIAGE]

Track id: <track_id>
Comment id: <comment_id>
Thread id: <thread_id>
From: <source_actor_address>
To: <target_actor_address>

A Track comment arrived while the main work is busy.

Required action:
Triage this exact comment from Track source truth.

Runtime context:
Side triage is for quick Track-thread handling only.
A Track comment may still contain a concrete work demand, but side triage should not treat a lightweight acknowledgement as completed work.

Work-demand guidance:
If the comment is lightweight, handle it through Track tools.
If the comment clearly assigns durable work that cannot be completed quickly in side triage, do not present it as done.
Leave substantive work for the parent/main path; use a concise Track reply only if it is useful for coordination.

Steps:
1. Call track.open(track_id="<track_id>") to inspect current Track state.
2. Call track.list_comments(track_id="<track_id>", status="all") and find comment "<comment_id>" in thread "<thread_id>".
3. If quick handling is enough, call track.add_comment with:
   - track_id = "<track_id>"
   - content = your reply
   - reply_to = "<comment_id>"
4. Only if the active actor is the exact Track owner and the thread is ready for durable closure, call track.resolve_comment_thread with:
   - track_id = "<track_id>"
   - comment_id = "<comment_id>"
   - resolution_summary = the closure summary

Use only Track tools for this comment.

Finish:
Finish after quick Track-thread triage is handled.
```

## Behavioral Notes

Message side triage can escalate because message has `needs_parent`.

Track comment side triage currently cannot escalate in the same way. There is no Track comment
`needs_parent` disposition or parent-required handoff. Therefore Track comment side prompt should
only prevent false completion language and keep quick handling inside Track tools.

If a later task adds Track comment parent handoff, revisit the Track comment side prompt and align it
with message side triage.

## Test Plan

Add focused prompt rendering assertions before implementation.

Suggested tests:

- message parent prompt includes `Runtime context`, `Work-demand guidance`, `task.current`, and
  `task.capture/task.select`;
- message side prompt includes the new concrete-work `needs_parent` condition;
- message parent-required prompt includes durable task capture guidance;
- Track comment parent prompt includes source-truth guidance, task tips, and Track reply guidance;
- Track comment side prompt includes lightweight side-triage guidance but does not mention
  `needs_parent`;
- handler tests still prove the correct prompt is submitted for idle and running parent state;
- existing forbidden-token checks remain intentional:
  - message prompts should not expose mailbox or daemon internals;
  - Track comment prompts should not import message disposition terms unless a future handoff
    feature is explicitly added.

Focused verification:

```bash
python -m pytest tests/test_message_available_handler.py tests/test_track_comment_added_handler.py -q
python -m pytest tests/test_message_env_tool.py -q
```

## Acceptance Criteria

The task is complete when:

- all five inbound prompt surfaces use reviewed sectioned content;
- prompt construction is split into small domain-local helpers instead of one growing string;
- direct-message work-demand prompts make `task.current` and `task.capture/task.select` visible;
- message side triage can route concrete work to parent via `needs_parent`;
- Track comment parent prompt can guide durable task capture when a comment assigns work;
- Track comment side prompt stays within current Track-tool-only semantics;
- focused prompt and handler tests pass.

## Risk Review

Primary risk:

```text
Over-guiding the actor so every inbound item becomes a task.
```

Mitigation:

- keep wording conditional: "if the message/comment assigns concrete work";
- explicitly allow FYI, status sync, clarification, and lightweight discussion to be handled normally;
- keep side prompts narrower than parent prompts.

Second risk:

```text
Mixing Track comment semantics with message disposition semantics.
```

Mitigation:

- do not add `absorbed`, `replied`, or `needs_parent` to Track comment prompts in this task;
- keep Track comment source truth through `track.open`, `track.list_comments`, and
  `track.add_comment`.

Review conclusion:

```text
Task 2 is a focused InnerTUI prompt upgrade. It should be implemented separately from the
track.comment.added daemon state-root fix and should preserve current runtime semantics.
```

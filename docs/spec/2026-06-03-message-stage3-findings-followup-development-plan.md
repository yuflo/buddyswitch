# Message Stage 3 Findings Follow-up Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Use `superpowers:test-driven-development` for behavior changes: write or update
> the focused regression test first, run it and confirm the expected failure, then implement the
> smallest direct change and rerun it green.

**Goal:** Fix the Stage 3 message follow-up findings so actor identity, reply mutation durability,
`needs_parent` ordering, tool catalog semantics, and tool response feedback match the memo.

**Architecture:** Keep message business semantics in `scripts/env/domain/messages.py` and
`scripts/env/tools/message/_impl.py`. Add one small local retry helper in the message tool
implementation. Do not introduce generic workflow, outbox, transaction, or compatibility layers.

**Tech Stack:** Python env-tool implementation, message domain helpers, runtime JSON message rows,
and pytest/unittest tests.

---

## Task 1: Save Follow-up Planning Artifacts

**Files:**

- Create: `docs/spec/2026-06-03-message-stage3-findings-followup-test-plan.md`
- Create: `docs/spec/2026-06-03-message-stage3-findings-followup-development-plan.md`
- Create: `docs/spec/2026-06-03-message-stage3-findings-followup-phase2-prompt.md`

Steps:

- [ ] Save the follow-up test plan mapped to every requirement in the memo.
- [ ] Save this development plan.
- [ ] Save the Phase 2 execution prompt.
- [ ] Review all three artifacts against
  `docs/memo/2026-06-03-message-stage3-findings-followup-task.md` and fix gaps before coding.

## Task 2: Add ActorAddress Regression Tests

**Files:**

- Modify: `tests/test_message_env_tool.py`

Steps:

- [ ] Add a self-send test proving identical full `ActorAddress` is rejected.
- [ ] Add a self-conversation test proving identical full `ActorAddress` is rejected.
- [ ] Add a contacts test proving the active full `ActorAddress` is not sendable while a row with
  the same `actor_id` and different `role_id` remains sendable.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q` and confirm the contacts same
  `actor_id` case fails under the old actor-id-only check.

## Task 3: Implement Full ActorAddress Identity

**Files:**

- Modify: `scripts/env/domain/messages.py`

Steps:

- [ ] Change self-send detection to `target_actor == source_actor_address`.
- [ ] Change self-conversation detection to `target_actor == source_actor_address`.
- [ ] Change contact self detection to compare `ActorAddress.from_payload(...)` with
  `active_actor_address`.
- [ ] Update self-send/self-conversation/contacts wording to say full actor address.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q` until the actor-address tests pass.

## Task 4: Add Reply Retry And Failure Tests

**Files:**

- Modify: `tests/test_message_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`

Steps:

- [ ] Add a reply test where saving original `replied` fails once, retry sleep is patched, and the
  second save succeeds.
- [ ] Add a reply test where saving original `replied` fails all 3 attempts and the response reports
  durable delivered reply plus unchanged original disposition.
- [ ] Add response-contract assertions for `state_changed=true`, `durability=durable`, object ids,
  previous/final original disposition, and retry guidance that does not tell the host to blindly
  send another reply.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py tests/test_env_tool_response_contract.py -q`
  and confirm failures are the missing retry/failure-response behavior.

## Task 5: Implement Local Retry Helper And Reply Save Handling

**Files:**

- Modify: `scripts/env/tools/message/_impl.py`

Steps:

- [ ] Add `MESSAGE_MUTATION_RETRY_DELAYS_SECONDS = (0.0, 0.1, 0.25)`.
- [ ] Add a local helper that retries a callable across those delays and accepts a patchable sleep
  function.
- [ ] Use the helper only for message mutation follow-up effects listed in this plan.
- [ ] Save the original `replied` transition after reply delivery through the helper.
- [ ] On final save failure, return rejection with durable reply id, delivery status, original id,
  previous disposition, unchanged final disposition, `state_changed=true`, and safe retry guidance.
- [ ] On reply success, include original id and final disposition `replied` in response data.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py tests/test_env_tool_response_contract.py -q`
  until the reply retry tests pass.

## Task 6: Add `needs_parent` Ordering And Retry Tests

**Files:**

- Modify: `tests/test_message_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`

Steps:

- [ ] Add a test proving `request_parent_message_handling` is called before saving
  `needs_parent`.
- [ ] Add a test where parent prompt attempt 1 fails and attempt 2 succeeds.
- [ ] Add a test where all parent prompt attempts fail and the original remains unchanged with
  `state_changed=false`.
- [ ] Add a test where prompt submit succeeds, save `needs_parent` fails once, and attempt 2
  succeeds.
- [ ] Add a test where prompt submit succeeds, all `needs_parent` saves fail, and the response says
  prompt submitted but disposition save failed with `state_changed=true`.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py tests/test_env_tool_response_contract.py -q`
  and confirm failures match the old save-before-submit order.

## Task 7: Implement `needs_parent` Prompt-first Order

**Files:**

- Modify: `scripts/env/tools/message/_impl.py`

Steps:

- [ ] Keep `absorbed` as validate -> save -> success.
- [ ] For `needs_parent`, validate current message and render parent-required prompt from current
  message before saving any disposition change.
- [ ] Submit parent prompt through the retry helper before saving `needs_parent`.
- [ ] If prompt submit fails after 3 attempts, return rejection with `state_changed=false` and
  unchanged original disposition.
- [ ] If prompt submit succeeds, save the `needs_parent` transition through the retry helper.
- [ ] If saving fails after 3 attempts, return rejection with `state_changed=true`, submitted parent
  request details, and unchanged original disposition.
- [ ] On success, return parent request details and final disposition `needs_parent`.
- [ ] Run `python3 -m pytest tests/test_message_env_tool.py tests/test_env_tool_response_contract.py -q`
  until the `needs_parent` tests pass.

## Task 8: Update Tool Catalog Contract Tests

**Files:**

- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`

Steps:

- [ ] Assert `message.mark` enum remains exactly `["absorbed", "needs_parent"]`.
- [ ] Assert `message.mark` fields mention `absorbed`, `needs_parent`,
  `message.send(reply_to=...)`, and not being a generic disposition editor.
- [ ] Assert `message.send` fields mention direct sends, replies with `reply_to`, `replied`,
  reply disposition save failure, and not blindly retrying duplicate replies.
- [ ] Assert `message.get` and `message.contacts` descriptions match exact-message and
  full-address sendability contracts.
- [ ] Run `python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q`
  and confirm failures are missing catalog wording only.

## Task 9: Implement Tool Catalog Wording

**Files:**

- Modify: `scripts/env/tools/message/tool.py`

Steps:

- [ ] Update tool-level description/object model/do-not-write wording to cover the memo's catalog
  requirements.
- [ ] Update `message.send` description, `reply_to` field, `success_effect`,
  `failure_state_guarantee`, `use_when`, and `do_not_use_when`.
- [ ] Update `message.mark` description, `disposition` field, `reason` field, `success_effect`,
  `failure_state_guarantee`, and `do_not_use_when`.
- [ ] Update `message.get` wording if it does not clearly state exact processable inbound read with
  no disposition mutation.
- [ ] Update `message.contacts` wording to use full `ActorAddress` sendability.
- [ ] Run `python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q`
  until green.

## Task 10: Focused Verification And Source Audits

**Files:**

- Verify: message env tool, schema, semantic, and response-contract tests.
- Verify: message domain/tool source.

Steps:

- [ ] Run `python3 -m pytest tests/test_message_env_tool.py -q`.
- [ ] Run `python3 -m pytest tests/test_env_tool_schema_contract.py -q`.
- [ ] Run `python3 -m pytest tests/test_env_tool_semantic_contract.py -q`.
- [ ] Run `python3 -m pytest tests/test_env_tool_response_contract.py -q`.
- [ ] Run the source audits from the follow-up test plan.
- [ ] Fix any actor-id-only self checks, old `needs_parent` failure wording, catalog gaps, or
  unexpected framework/disposition residue.

## Task 11: Broad Verification And Review

**Files:**

- Verify: pytest collection, whitespace diff, and launcher regression.

Steps:

- [ ] Run `python3 -m pytest --collect-only -q tests`.
- [ ] Run `git diff --check`.
- [ ] Run `python3 -m pytest tests/test_buddyswitch_launcher.py -q` only after focused tests pass.
- [ ] If launcher tests start persistent services, inspect residual service processes before final
  completion.
- [ ] Re-read the memo and this plan. Check each explicit requirement against code, tests, source
  audits, and command output.
- [ ] Confirm no new dispositions, compatibility aliases, outbox systems, workflow engines,
  transaction frameworks, or generic retry frameworks were added.

## Self-Review

- Spec coverage: every section of the follow-up memo maps to a test, implementation task, and
  verification command.
- Placeholder scan: no task depends on placeholder tokens or generic test instructions.
- Type consistency: final names are `ActorAddress`, `reply_to`, `replied`, `absorbed`,
  `needs_parent`, `MESSAGE_MUTATION_RETRY_DELAYS_SECONDS`, `state_changed`, `durability`, and
  `parent_request`.
- Scope guard: the plan keeps the message module as semantic owner and avoids transition layers,
  compatibility aliases, and speculative framework code.

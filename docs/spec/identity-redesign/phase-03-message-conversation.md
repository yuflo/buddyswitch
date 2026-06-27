# Phase 3: Message / Conversation

## Goal

Replace Central IM message and conversation semantics with identity ids: conversations are between identities, messages store from/to identity ids, states belong to owner identities, and events are visible to identity ids.

## Code Audit

- `scripts/env/repos/messages.py` persists Central IM conversations with `participants`, messages with `from`/`to`, message states with `participant`, and events with `participant`.
- `scripts/env/services/messages.py` accepts IM participants and wakes actor targets by reading `target["actor_address"]`.
- `scripts/env/tool_runtime/im_client.py` exposes actor-facing `target_actor_address` for send and conversation.
- `scripts/env/tools/message/tool.py` documents `target_actor_address` in action schemas and tool semantics.
- `buddyswitch/skills/shared/message-tool/SKILL.md` teaches copying `contact.actor_address` into `target_actor_address`.
- Existing tests lock the old participant model in `tests/test_im_product_core.py`, `tests/test_message_tool_im_client.py`, `tests/test_im_http_router.py`, `tests/test_env_tool_semantic_contract.py`, and `tests/test_env_tool_schema_contract.py`.

## Plan

1. Replace Central IM durable rows with identity fields on new writes.
2. Keep only explicit resolver/projection helpers for converting identity ids to display/routing data.
3. Replace actor-facing message tool input `target_actor_address` with `target_identity_id`.
4. Make `message.contacts` return identity ids plus hydrated display/routing metadata as projection.
5. Resolve daemon route only when waking an actor target.
6. Replace message-tool skill text and schema tests so live surfaces teach identity ids.
7. Run focused message and schema tests plus scoped residue searches.

## Test Plan

Use TDD across the smallest useful slices:

- Product core new write persists `conversation.identity_ids`, `message.from_identity_id`, `message.to_identity_id`, `message_state.owner_identity_id`, and `event.visible_to_identity_id`.
- External connection persists `identity_id`.
- Actor client sends with `target_identity_id`.
- Message tool schema exposes `target_identity_id` and does not expose `target_actor_address`.
- Conversation reads by current identity plus target identity.

Focused command:

```bash
python -m pytest tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_im_external_reply_loop.py tests/test_im_wake_handler.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py -q
```

## Implementation

- `scripts/env/repos/messages.py`
  - New Central IM writes persist `conversation.identity_ids`, `message.from_identity_id`, `message.to_identity_id`, `message_state.owner_identity_id`, and `event.visible_to_identity_id`.
  - Removed the legacy actor-address object-message repo API exports: `create_message`, `save_message`, `list_messages`, `get_message`, and `delete_message`.
  - Kept participant-shaped inputs only as local resolver/projection input for service boundaries and migration reads.
- `scripts/env/services/messages.py`
  - External connections now persist `identity_id`.
  - Send/reply/conversation lookup uses identity ids for durable membership and reply scope.
  - Actor wake still resolves to `target_actor_address` only at the daemon routing boundary.
- `scripts/env/tool_runtime/im_client.py`
  - Actor-facing sends and conversations now use `target_identity_id`.
  - `message.contacts` returns actor identity ids and no public `actor_address`.
- `scripts/env/tools/message/tool.py` and `buddyswitch/skills/shared/message-tool/SKILL.md`
  - Replaced `target_actor_address` contract text with `target_identity_id`.
- `scripts/env/tools/context/_impl.py`
  - `message_cues` now reads Central IM identity events and projects identity ids, not actor-address message rows.
- `scripts/env/tool_runtime/context.py`
  - Removed old `RuntimeObjectAccess.send_message/list_messages`.
  - Removed runtime exposure of the retired actor-address message domain.
- `scripts/env/domain/messages.py`
  - Deleted the dead actor-address message domain module.

## Verification

Focused red-green checks:

```bash
python -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_identity_inbox_message_cues -q
python -m pytest tests/test_runtime_actor_profile.py::ActorProfileTests::test_tool_context_can_be_constructed_from_actor_profile -q
python -m pytest tests/test_im_product_core.py::ImProductCoreTests::test_central_im_repo_does_not_export_legacy_actor_address_message_apis -q
python -m pytest tests/test_env_tool_payload_contract.py::EnvToolPayloadContractTests::test_services_do_not_define_duplicate_payload_field_sets_and_legacy_message_domain_is_retired -q
```

Representative red results before implementation:

```text
AssertionError: 'target identities' not found in 'Use message.contacts to discover online target actor addresses.'
AssertionError: True is not false
scripts/env/domain/messages.py: legacy actor-address message domain must stay retired
```

Green focused phase command:

```bash
python -m pytest tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_im_external_reply_loop.py tests/test_im_wake_handler.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_identity_inbox_message_cues tests/test_runtime_actor_profile.py tests/test_env_tool_payload_contract.py -q
```

Result:

```text
64 passed, 601 subtests passed in 0.46s
```

Residue checks:

```bash
rg -n "target_actor_address|actor_address|ActorAddress|actor address" scripts/env/tools/message buddyswitch/skills/shared/message-tool/SKILL.md -S
rg -n "env\\.domain\\.messages|from env\\.domain import messages|rules\\.message|_message_domain" scripts tests -S
rg -n "create_message\\(|list_messages\\(|get_message\\(|save_message\\(|delete_message\\(|from_actor_address|to_actor_address|processed_by_actor_address" scripts/env tests/test_context_binding_env_tool.py tests/test_im_product_core.py tests/test_message_tool_im_client.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_runtime_actor_profile.py tests/test_env_tool_payload_contract.py -S
```

Results:

- Public message tool/skill actor-address scan: no hits.
- Old message-domain import scan: only guard tests mention the retired module name.
- Old actor-address message object API scan: no live repo/context hits; remaining `get_message/list_messages` names are Central IM message tool action handlers, and remaining actor-address strings are negative assertions in tests.

## Gate

Complete.

- Phase test command passed.
- Phase goal is implemented.
- Replaced old actor-address message repo/runtime/domain write paths were deleted.
- `target_actor_address` remains only as daemon/track routing protocol data outside the actor-facing message contract.
- No new identity concept outside `IdentityRef { id, type }` was introduced.
- README updated to set `phase-04-web-external-identity` as current.

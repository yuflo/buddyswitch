# BuddySwitch IM Merge Readiness Test and Implementation Plan

**Goal:** make the `fea-daemon` IM update merge-ready by fixing the focused review blockers without expanding the Central IM scope.

**Expected Effects**

- Stable guidance under `docs/spec` no longer points readers at internal tool contract implementation surfaces.
- `message.list` public tool metadata matches the Central IM event-feed behavior implemented by `ActorImClient.list`.
- Invalid Central IM actor participant payloads return structured payload errors through HTTP and actor env-tool clients instead of leaking `ValueError`.
- Focused verification passes; full test execution is intentionally out of scope for this repair pass.

## Test Plan

1. Repository guidance check:
   - Run `python -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_stable_guidance_does_not_point_to_internal_tool_contract_surfaces -q`.
   - Expected result: pass.
   - Proves the stable docs no longer reference forbidden internal tool contract surfaces.

2. `message.list` schema and semantic contract:
   - Update `tests/test_env_tool_schema_contract.py` to assert `message.list` accepts only `cursor` and `limit`, returns `events` and `next_cursor`, and no longer advertises `role` or `q`.
   - Update `tests/test_env_tool_semantic_contract.py` to assert `message.list` authority and visibility describe Central IM participant events, not an active actor inbox.
   - Run `python -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q`.
   - Expected result before implementation: fail on current inbox metadata.
   - Expected result after implementation: pass.

3. Invalid actor address rejection:
   - Add `tests/test_im_http_router.py` coverage for `POST /api/im/messages` with a malformed actor address.
   - Add `tests/test_message_tool_im_client.py` coverage for `ActorImClient.send()` with a malformed `target_actor_address`.
   - Run `python -m pytest tests/test_im_http_router.py tests/test_message_tool_im_client.py -q`.
   - Expected result before implementation: fail because `ValueError` escapes.
   - Expected result after implementation: pass with `E_IM_PAYLOAD` and no state mutation claim.

4. Focused repair gate:
   - Run `python -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_stable_guidance_does_not_point_to_internal_tool_contract_surfaces tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_im_http_router.py tests/test_message_tool_im_client.py -q`.
   - Expected result: pass.

## Implementation Plan

1. Remove the stable-doc blocker:
   - Modify `docs/spec/buddyswitch-im-external-reply-loop-execution-prompt.md`.
   - Replace direct internal contract test file references in the execution command with stable focused test groups, or remove those direct references from the stable execution prompt.
   - Keep the ignored `tmp/im_reply_console.py` wording unchanged as a local smoke harness, not an official feature.

2. Align `message.list` contract with Central IM events:
   - Modify `scripts/env/tools/message/tool.py`.
   - Change `message.list` description, authority, visibility, read/return metadata, and success text from inbox rows to Central IM participant event feed.
   - Change schema properties to `cursor` and `limit`.
   - Keep `kind="read"`, `mutates="none"`, `required_permission="message.list"`, and `durability="none"`.

3. Convert invalid IM participant payloads at the service boundary:
   - Modify `scripts/env/services/messages.py`.
   - Add a small Central IM payload error helper returning `{"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": ...}}`.
   - Wrap sender and target participant normalization in `send_im_message`.
   - Preserve existing successful reply and send behavior.

4. Verify with focused tests only:
   - Run the focused commands listed in the test plan.
   - Do not run `python -m pytest tests -q` unless explicitly requested later.

## Scope Boundaries

- Do not restore the retired fake web-user actor path.
- Do not reintroduce `/api/messages/send`, `send_from_web_user`, `WebUserActorRuntime`, or `message.available` delivery semantics.
- Do not add compatibility layers for the old message repository path.
- Do not change main branch or perform a merge in this repair pass.

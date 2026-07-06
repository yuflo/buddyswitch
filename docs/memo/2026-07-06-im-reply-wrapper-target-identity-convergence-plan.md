# IM Reply Wrapper Target-Identity Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Central IM sending so `target_identity_id` is the only bottom send mode, while `reply_to` remains a wrapper that normalizes a reply intent into a target-identity send plus reply metadata.

**Architecture:** `reply_to` is resolved before the unified send chain. Core send receives a resolved target identity and optional persisted reply metadata; it never reads the original message, derives the target from `reply_to`, marks the original message replied, or bypasses the IM target resolver.

**Tech Stack:** Python service code under `scripts/env`, launcher HTTP/session adapters under `tools/launcher`, `unittest`/`pytest` tests under `tests`.

---

## Principles Read

This plan is based on the forward-development and bitter-lesson rules in:

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`

Applied rules:

- Rebuild forward; do not preserve the old bottom reply branch.
- No feature flag, compatibility alias, or dual-path adapter.
- Product semantics live in the Central IM product service, not in prompts.
- Tool catalog and skill surfaces must teach the new single-path contract.
- Verification must cover behavior and live-surface residue.

## Task Restatement

Current bottom shape:

```text
target_identity_id -> resolver -> send_im_message target path
reply_to           -> send_im_message internal reply branch -> derive target -> mark replied
```

Target bottom shape:

```text
target_identity_id -> resolver -> core_send
reply_to           -> reply wrapper -> target_identity_id -> resolver -> core_send
```

`reply_to` remains valid as product input and persisted message metadata. It stops being a bottom send mode.

## Current Code Findings

### Bottom reply branch exists

`scripts/env/services/messages.py` currently has:

- `_direct_conversation_identity_ids(...)`
- `_resolve_reply_conversation(...)`
- `send_im_message(..., to=None, reply_to=...)`
- an internal `if reply_to_id is not None` branch that reads the original message, derives target/conversation, writes the new message, then marks the original message replied.

This is the branch to delete, not wrap.

### Actor projection bypasses the target resolver for reply-only sends

`scripts/env/tool_runtime/im_client.py` currently does:

```python
elif reply_to is not None:
    target = None
```

That lets `send_im_message` derive the target and skips `resolve_im_send_target(...)` for pure replies.

### Tool catalog still describes reply as a peer/direct-conversation mode

`scripts/env/tools/message/tool.py` says `reply_to` derives the other direct identity. That language must be replaced with wrapper language:

```text
reply_to resolves the original message sender into target_identity_id, then uses the same target resolver.
```

### Tests prove reply works but not that it uses one bottom path

Existing tests in `tests/test_message_tool_im_client.py`, `tests/test_im_product_core.py`, `tests/test_external_im_session.py`, `tests/test_im_http_router.py`, `tests/test_web_management.py`, and `tests/test_im_external_reply_loop.py` assert reply behavior. They do not yet enforce that reply calls the target resolver, rejects offline actor targets before writes, or prevents `send_im_message(..., to=None, reply_to=...)`.

### Task Sys frame prompts are now a live message surface

Commit `9fe452d` completed the side/parent IM message permission update. `tools/launcher/task_sys_runtime.py` now exposes full message capabilities for IM source frames, including both:

- `message.send(reply_to=source_message_id, content=...)`
- `message.send(target_identity_id=..., content=...)`

This does not change the reply wrapper architecture. It does mean Task Sys frame prompt text and its tests are live surfaces that must be reviewed for stale dual-path wording. The wrapper task must not reopen or narrow the completed side/parent permission boundary.

## Target Architecture

```text
message.send(...)
        |
        v
Send intent layer

  target_identity_id input
    -> resolve_im_send_target(...)

  reply_to input
    -> send_im_reply(...)
       original_message = get(reply_to)
       guard original_message.target_identity.id == current sender identity id
       target_identity_id = original_message.sender_identity.id
       reply_metadata = {"reply_to": original_message.id}
       -> resolve_im_send_target(...)

        |
        v
Unified core send

  core_send(sender_identity, target_identity, content, reply_metadata)
    - find or create direct conversation
    - write Central IM message
    - write identity-visible events
    - write target unseen state
    - return message refs and final target identity

        |
        v
Post-send effects outside core send

  - actor delivery / wake
  - reply wrapper marks original inbound message replied after durable send success
```

Hard boundary:

```text
core send may persist reply_to metadata
core send must not read original_message
core send must not derive target from reply_to
core send must not mark original_message replied
core send must not bypass resolve_im_send_target
```

## Module Boundaries

### `scripts/env/services/messages.py`

Owns Central IM product semantics.

Keep here:

- identity normalization;
- target resolver;
- reply wrapper normalization;
- durable message write primitive;
- message state update for original replied disposition;
- event/read/disposition product functions.

Remove from core send:

- reply target derivation;
- reply conversation routing;
- original-message state mutation.

### `scripts/env/tool_runtime/im_client.py`

Owns actor env-tool projection.

Keep here:

- parsing `message.send` arguments;
- choosing send intent wrapper versus explicit target send;
- passing daemon reachability and wake handlers into product service;
- converting product service responses into actor-visible tool results.

Do not keep here:

- reply target derivation logic;
- conversation membership logic.

### `tools/launcher/external_im_session.py`

Owns external-session interface projection.

Keep here:

- external session authentication to sender identity;
- passing target resolver callbacks;
- routing explicit target sends and external reply wrapper sends into the product service.

Do not keep here:

- bottom send semantics;
- message object mutation rules.

### `scripts/env/tools/message/tool.py`

Owns live tool semantics.

It must teach:

- `target_identity_id` is the explicit send mode;
- `reply_to` is a wrapper that replies to the original sender through the same target resolver;
- `reply_to` is not a second bottom send path.

### Tests

Tests must prove:

- target-mode sends still write the same durable objects;
- reply wrapper calls the same target resolver;
- reply wrapper rejects invalid target resolver results before writes;
- reply wrapper marks the original message replied after accepted send;
- core send no longer accepts or implements reply routing;
- live surfaces do not teach the old dual-path model.

## Files To Modify

- `scripts/env/services/messages.py`
- `scripts/env/tool_runtime/im_client.py`
- `tools/launcher/external_im_session.py`
- `tools/launcher/im_http_router.py` only if method signatures need route-level shape alignment
- `scripts/env/tools/message/tool.py`
- `buddyswitch/skills/shared/task-management/SKILL.md`
- `tools/launcher/task_sys_runtime.py` only if its frame prompt text teaches stale reply semantics; do not change its message permission scope
- `tests/test_message_tool_im_client.py`
- `tests/test_im_product_core.py`
- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_im_external_reply_loop.py`
- `tests/test_web_management.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_task_sys_runtime_executor.py` only if Task Sys frame prompt wording changes
- `tests/test_repo_consistency.py`
- Any focused tests that call `message_service.send_im_message(..., reply_to=...)`

Do not edit runtime state under `buddyswitch/objects/**` or `buddyswitch/local/private/**`.

## End-To-End Contract Sentence

```text
An actor calls message.send(reply_to=<inbound message id>) -> the system resolves the original sender as target_identity_id, validates that target through the same IM target resolver, writes one Central IM message through the unified core send, marks the original inbound message replied, and the recipient observes the reply through the normal Central IM event/conversation paths.
```

Keep this contract alive through focused tests and the existing external reply loop acceptance.

## Task 1: Add Product-Service Tests For Reply Wrapper And Target-Only Core

**Files:**

- Modify: `tests/test_im_product_core.py`

- [ ] **Step 1: Add a test that target-mode core send does not need reply routing**

Add or update the current durable-object send test so it calls the new target-only service signature:

```python
response = message_service.send_im_message(
    sender_identity=sender,
    target_identity=target["identity"],
    content="  ping  ",
)
```

Expected assertions:

- response is `ok`;
- persisted message `reply_to` is `None`;
- one direct conversation exists;
- one target unseen state exists;
- two visible events exist;
- no actor handling fields appear in the product-core response.

- [ ] **Step 2: Add a reply wrapper success test**

Add this behavior to `ImProductCoreTests`:

```python
def test_send_im_reply_normalizes_original_sender_to_target_identity_and_marks_replied(self) -> None:
    _created, _external_session, external = self._external_session()
    actor = self._actor_identity(role="dev", label="act-dev-reply-wrapper")
    root = message_service.send_im_message(
        sender_identity=external,
        target_identity=actor["identity"],
        content="ping",
    )

    reply = message_service.send_im_reply(
        sender_identity=actor["identity"],
        reply_to=root["message"]["id"],
        content="pong",
        actor_reachability_checker=lambda *, target_identity_id: {
            "reachability_status": "online",
            "target_identity_id": target_identity_id,
            "record": {"identity_id": target_identity_id},
        },
    )

    self.assertTrue(reply.get("ok"), msg=reply)
    self.assertEqual(reply["target_identity"], external)
    self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
    self.assertEqual(reply["message"]["conversation_id"], root["message"]["conversation_id"])
    self.assertEqual(reply["original_message_id"], root["message"]["id"])
    self.assertEqual(reply["original_final_disposition"], "replied")
```

Then assert the original message state file for the actor has disposition `replied`.

- [ ] **Step 3: Add a reply wrapper guard test**

Add this behavior:

```python
def test_send_im_reply_rejects_message_not_addressed_to_sender(self) -> None:
    sender = self._actor_identity(role="pm", label="act-pm-reply-guard")
    intended = self._actor_identity(role="dev", label="act-dev-reply-guard")
    outsider = self._actor_identity(role="test", label="act-test-reply-guard")
    root = message_service.send_im_message(
        sender_identity=sender["identity"],
        target_identity=intended["identity"],
        content="private request",
    )

    reply = message_service.send_im_reply(
        sender_identity=outsider["identity"],
        reply_to=root["message"]["id"],
        content="bad reply",
        actor_reachability_checker=lambda *, target_identity_id: {
            "reachability_status": "online",
            "target_identity_id": target_identity_id,
            "record": {"identity_id": target_identity_id},
        },
    )

    self.assertFalse(reply.get("ok"), msg=reply)
    self.assertEqual(reply["error"]["code"], "E_IM_REPLY_TARGET")
```

Also assert no new message file was created beyond the root message.

- [ ] **Step 4: Add a target resolver negative test for reply**

Add this behavior:

```python
def test_send_im_reply_to_offline_actor_rejects_before_write(self) -> None:
    source = self._actor_identity(role="pm", label="act-pm-offline-reply")
    active = self._actor_identity(role="dev", label="act-dev-offline-reply")
    root = message_service.send_im_message(
        sender_identity=source["identity"],
        target_identity=active["identity"],
        content="need reply",
    )
    before_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))

    reply = message_service.send_im_reply(
        sender_identity=active["identity"],
        reply_to=root["message"]["id"],
        content="reply",
        actor_reachability_checker=lambda *, target_identity_id: {
            "reachability_status": "offline",
            "target_identity_id": target_identity_id,
            "record": {"identity_id": target_identity_id},
        },
    )

    self.assertFalse(reply.get("ok"), msg=reply)
    self.assertEqual(reply["error"]["code"], "E_IM_TARGET")
    after_messages = sorted((self.runtime_state_root / "im" / "messages").glob("*.json"))
    self.assertEqual(after_messages, before_messages)
```

- [ ] **Step 5: Run the new focused tests and verify they fail before implementation**

Run:

```bash
python3 -m pytest tests/test_im_product_core.py -q
```

Expected before implementation:

- tests referencing `target_identity=` or `send_im_reply(...)` fail because the service does not yet expose the new target-only/wrapper contract;
- existing reply tests may still pass through the old branch.

## Task 2: Rebuild `messages.py` Around Target-Only Core Send

**Files:**

- Modify: `scripts/env/services/messages.py`

- [ ] **Step 1: Replace reply-conversation resolver with reply-intent resolver**

Delete:

- `_direct_conversation_identity_ids(...)`
- `_resolve_reply_conversation(...)`

Add:

```python
def _resolve_reply_target_identity_id(
    *,
    message_repo: Any,
    sender: dict[str, str],
    reply_to_id: str,
) -> dict[str, Any]:
    original_message = message_repo.get_im_message(reply_to_id)
    if original_message is None:
        return _im_reply_target_error("reply_to message not found")
    try:
        original_sender = _identity_ref(original_message.get("sender_identity"), "reply_to.sender_identity")
        original_target = _identity_ref(original_message.get("target_identity"), "reply_to.target_identity")
    except ValueError as exc:
        return _im_reply_target_error(str(exc))
    if original_target["id"] != sender["id"]:
        return _im_reply_target_error("reply_to message is not addressed to the sender identity")
    return {
        "ok": True,
        "target_identity_id": original_sender["id"],
        "reply_to": str(original_message["id"]),
    }
```

This function resolves reply intent only. It does not decide the bottom send path.

- [ ] **Step 2: Replace `send_im_message` with target-only semantics**

Change the public service signature to target-only:

```python
def send_im_message(
    *,
    sender_identity: dict[str, Any],
    target_identity: dict[str, Any],
    content: str,
    reply_to: str | None = None,
) -> dict[str, Any]:
```

Implementation rules:

- normalize `sender_identity`;
- normalize `target_identity`;
- reject empty content;
- reject sender equal target;
- treat `reply_to` only as metadata to persist;
- find or create direct conversation by `[sender, target]`;
- write message, event, and target unseen state;
- return `target_identity`, message refs, event id, delivery status, and next cursor;
- include `original_message_id` only in `send_im_reply(...)`, not in raw target sends.

Do not read original messages inside this function.

- [ ] **Step 3: Add `send_im_reply` wrapper**

Add:

```python
def send_im_reply(
    *,
    sender_identity: dict[str, Any],
    reply_to: str,
    content: str,
    actor_reachability_checker: ActorReachabilityChecker | None = None,
) -> dict[str, Any]:
```

Required behavior:

1. Normalize sender.
2. Validate `reply_to` is a non-empty string.
3. Resolve `target_identity_id` through `_resolve_reply_target_identity_id(...)`.
4. Call `resolve_im_send_target(...)` with that target id and the provided actor reachability checker.
5. Call `send_im_message(...)` with the resolved `target_identity` and `reply_to` metadata.
6. If durable send succeeds, mark the original message replied for the sender identity.
7. Return the core send response plus `original_message_id` and `original_final_disposition`.

- [ ] **Step 4: Keep original replied marking outside core send**

Keep or rename `_mark_reply_source_replied(...)`. It must be called only by `send_im_reply(...)`.

- [ ] **Step 5: Update `send_external_session_message`**

Make it target-only:

```python
result = send_im_message(
    sender_identity=sender,
    target_identity=target,
    content=content,
)
```

Do not forward `reply_to` into core send from this function.

- [ ] **Step 6: Add explicit external-session reply service if the external adapter needs reply support**

If `ExternalImSession.send_message(reply_to=...)` remains supported, add:

```python
def send_external_session_reply(
    *,
    external_session: dict[str, Any],
    reply_to: str,
    content: str,
    actor_reachability_checker: ActorReachabilityChecker | None = None,
) -> dict[str, Any]:
```

It authenticates the external session identity, then calls `send_im_reply(...)`.

- [ ] **Step 7: Run product-service focused tests**

Run:

```bash
python3 -m pytest tests/test_im_product_core.py -q
```

Expected after this task:

- new product-service wrapper tests pass;
- tests still calling old `send_im_message(..., to=..., reply_to=...)` fail until call sites are updated.

## Task 3: Rebuild Actor And External Projections To Use The Wrapper

**Files:**

- Modify: `scripts/env/tool_runtime/im_client.py`
- Modify: `tools/launcher/external_im_session.py`
- Modify: `tools/launcher/im_http_router.py` only if needed for optional `target_identity_id` in reply mode
- Modify: `tests/test_message_tool_im_client.py`
- Modify: `tests/test_external_im_session.py`
- Modify: `tests/test_im_external_reply_loop.py`
- Modify: `tests/test_im_http_router.py`
- Modify: `tests/test_web_management.py`

- [ ] **Step 1: Update actor `message.send` projection**

In `ActorImClient.send(...)`, make the intent split explicit:

```python
has_target = isinstance(target_identity_id, str) and bool(target_identity_id.strip())
has_reply = isinstance(reply_to, str) and bool(reply_to.strip())
if has_target and has_reply:
    return {
        "ok": False,
        "error": {
            "code": "E_IM_PAYLOAD",
            "message": "message.send accepts either target_identity_id or reply_to, not both",
        },
    }
if has_reply:
    result = message_service.send_im_reply(
        sender_identity=self._identity,
        reply_to=reply_to.strip(),
        content=str(args.get("content") or ""),
        actor_reachability_checker=getattr(self._context.daemon, "check_reachability", None),
    )
else:
    target_response = self._send_target_identity(target_identity_id)
    if target_response.get("ok") is not True:
        return target_response
    result = message_service.send_im_message(
        sender_identity=self._identity,
        target_identity=target_response["target_identity"],
        content=str(args.get("content") or ""),
    )
```

Then call `attach_post_write_delivery_status(...)` once, using `result["target_identity"]` when present.

- [ ] **Step 2: Add actor projection tests**

Add or update tests in `tests/test_message_tool_im_client.py`:

```python
def test_actor_reply_to_actor_origin_uses_target_resolver_before_write(self) -> None:
    active_actor_id = self._runtime_actor_id(role="dev", label="act-dev-wrapper-resolver")
    source_actor_id = self._runtime_actor_id(role="pm", label="act-pm-wrapper-resolver")
    self._save_actor_profile(identity_id=active_actor_id, role_id="dev")
    self._save_actor_profile(identity_id=source_actor_id, role_id="pm")
    root = message_service.send_im_message(
        sender_identity={"id": source_actor_id, "type": "actor"},
        target_identity={"id": active_actor_id, "type": "actor"},
        content="Need a reply.",
    )
    reachability_calls: list[str] = []

    class _Daemon(_RecordingWakeDaemon):
        def check_reachability(self, *, target_identity_id: str) -> dict[str, Any]:
            reachability_calls.append(target_identity_id)
            return {
                "reachability_status": "online",
                "target_identity_id": target_identity_id,
                "record": {"identity_id": target_identity_id},
            }

    daemon = _Daemon()
    client = im_client_module.ActorImClient(
        _RealImContext(identity_id=active_actor_id, role_id="dev", daemon=daemon)
    )

    reply = client.send({"content": "Reply from dev.", "reply_to": root["message"]["id"]})

    self.assertTrue(reply.get("ok"), msg=reply)
    self.assertEqual(reachability_calls, [source_actor_id])
    self.assertEqual(reply["target_identity"], {"id": source_actor_id, "type": "actor"})
    self.assertEqual(reply["message"]["reply_to"], root["message"]["id"])
    self.assertEqual(reply["actor_handling_status"], "submitted")
```

Also add:

```python
def test_actor_reply_to_offline_actor_rejects_without_message_write(self) -> None:
```

Use the same root setup, return `{"reachability_status": "offline"}` from `check_reachability`, and assert:

- response is not `ok`;
- error code is `E_IM_TARGET`;
- no new message file was created;
- original message state for active actor remains `unseen`.

- [ ] **Step 3: Update external session projection**

In `ExternalImSession.send_message(...)`, support exactly one intent:

```python
has_target = isinstance(target_identity_id, str) and bool(target_identity_id.strip())
has_reply = isinstance(reply_to, str) and bool(reply_to.strip())
if has_target and has_reply:
    return {"ok": False, "error": {"code": "E_IM_PAYLOAD", "message": "provide either target_identity_id or reply_to, not both"}}
if has_reply:
    result = message_service.send_external_session_reply(
        external_session=external_session,
        reply_to=reply_to.strip(),
        content=content,
        actor_reachability_checker=self._actor_reachability_checker,
    )
else:
    target_response = self._send_target_identity(external_session, target_identity_id)
    ...
```

This keeps browser/external sends symmetrical with actor tool sends.

- [ ] **Step 4: Update route tests for external reply mode**

In `tests/test_external_im_session.py`, add:

```python
def test_session_reply_uses_reply_wrapper_without_explicit_target_identity(self) -> None:
```

Scenario:

1. Actor sends an explicit target message to external through product service.
2. External session calls `send_message(external_session=..., target_identity_id=None, content="pong", reply_to=<actor message id>)`.
3. Assert the reply targets the actor, preserves `reply_to`, and triggers actor handling through the same reachability and wake path.

- [ ] **Step 5: Replace direct actor reply simulation call sites**

Update tests that simulate actor replies using:

```python
message_service.send_im_message(..., to=..., reply_to=...)
```

Replace with either:

```python
message_service.send_im_reply(...)
```

for service-level tests, or:

```python
ActorImClient(...).send({"content": "...", "reply_to": message_id})
```

for end-to-end actor projection tests.

Known files from current search:

- `tests/test_im_product_core.py`
- `tests/test_message_tool_im_client.py`
- `tests/test_external_im_session.py`
- `tests/test_im_http_router.py`
- `tests/test_im_external_reply_loop.py`
- `tests/test_web_management.py`

- [ ] **Step 6: Run projection and loop tests**

Run:

```bash
python3 -m pytest tests/test_message_tool_im_client.py tests/test_external_im_session.py tests/test_im_http_router.py tests/test_im_external_reply_loop.py -q
```

Expected:

- actor reply and external reply both use wrapper semantics;
- explicit target sends still pass;
- reply to offline actor rejects before write;
- external reply loop still observes the reply through normal events.

## Task 4: Update Live Tool, Skill, And Schema Surfaces

**Files:**

- Modify: `scripts/env/tools/message/tool.py`
- Modify: `buddyswitch/skills/shared/task-management/SKILL.md`
- Review and modify only if stale: `tools/launcher/task_sys_runtime.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_task_management_skill_architecture.py` if skill wording assertions need alignment
- Modify: `tests/test_task_sys_runtime_executor.py` only if frame prompt wording changes

- [ ] **Step 1: Rewrite `message.send` catalog wording**

Replace dual-path wording with:

```text
Send one Central IM message. Use target_identity_id for an explicit target send. Use reply_to when replying to one processable inbound message; the reply wrapper resolves the original sender into target_identity_id, validates it through the same IM target resolver, writes through the unified send path, then marks the original message replied after durable send success.
```

Update field descriptions:

- `target_identity_id`: explicit target identity id for target sends; omit when using `reply_to`.
- `reply_to`: processable inbound message id; wrapper derives the reply target from the original message sender and uses the same resolver.

Update preconditions:

- content is non-empty;
- exactly one of `target_identity_id` or `reply_to` is provided;
- target resolver accepts the final target identity;
- reply source message is addressed to the active sender identity.

Update failure guarantee:

- resolver and reply wrapper rejections do not mutate state;
- durable send success followed by original-disposition save failure can leave a sent reply while the original remains unchanged.

- [ ] **Step 2: Keep skill wording product-level and compact**

In `buddyswitch/skills/shared/task-management/SKILL.md`, keep the actor guidance short:

```text
Use `message.send(reply_to=...)` when replying to a processable inbound IM message; the runtime resolves the original sender through the normal target-identity path.
```

Do not copy service internals into the skill.

- [ ] **Step 3: Review Task Sys frame prompt wording without changing permissions**

Inspect `tools/launcher/task_sys_runtime.py` after the side/parent permission update.

Keep product-level usage text such as:

```text
message.send(reply_to=source_message_id, content=...) to reply to the current source message
message.send(target_identity_id=..., content=...) to send required IM communication to an explicit actor or external identity
```

Change only if the text teaches old bottom semantics such as:

- `reply_to` as a separate core send path;
- deriving the other direct identity in core send;
- bypassing the target resolver;
- source-bound-only reply restrictions already removed by the side/parent permission task.

Do not remove `message.contacts`, `message.list`, `message.get`, `message.conversation`, `message.send`, or `message.mark` from IM source frames.

- [ ] **Step 4: Update schema and semantic tests**

Update `tests/test_env_tool_schema_contract.py` expected snippets:

- keep `reply_to`;
- keep `target_identity_id`;
- add `reply wrapper`;
- add `same IM target resolver` or equivalent exact wording;
- remove expectation that `target_identity_id is only required for a new target-identity message`.

Update `tests/test_env_tool_semantic_contract.py` expected snippets:

- keep identity, external, replied, absorbed, `message.send(reply_to=...)`;
- add wrapper/normalization language;
- forbid old phrases such as `derives the other direct identity`.

- [ ] **Step 5: Run live-surface tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py tests/test_task_management_skill_architecture.py tests/test_task_sys_runtime_executor.py -q
```

Expected:

- tool catalog and skill surfaces teach wrapper-to-target normalization;
- Task Sys frame prompts still expose the completed side/parent message capabilities;
- no live surface teaches reply as a second bottom send mode.

## Task 5: Add Residue Guards For The Old Reply Branch

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a scoped residue test**

Add a test named:

```python
def test_im_reply_wrapper_convergence_has_no_old_core_reply_branch_residue(self) -> None:
```

Use scoped targets:

```python
targets = [
    "scripts/env/services/messages.py",
    "scripts/env/tool_runtime/im_client.py",
    "tools/launcher/external_im_session.py",
    "tools/launcher/im_http_router.py",
    "tools/launcher/task_sys_runtime.py",
    "scripts/env/tools/message/tool.py",
    "buddyswitch/skills/shared/task-management/SKILL.md",
    "tests/test_im_product_core.py",
    "tests/test_message_tool_im_client.py",
    "tests/test_external_im_session.py",
    "tests/test_im_http_router.py",
    "tests/test_im_external_reply_loop.py",
    "tests/test_web_management.py",
    "tests/test_task_sys_runtime_executor.py",
    "tests/test_env_tool_schema_contract.py",
    "tests/test_env_tool_semantic_contract.py",
]
```

Forbid exact old implementation and semantic phrases:

```python
patterns = [
    r"\b_resolve_reply_conversation\b",
    r"\b_direct_conversation_identity_ids\b",
    r"reply target cannot be derived from the direct conversation",
    r"reply_to must stay in the same direct conversation",
    r"Central IM derives the other direct identity",
    r"reply_to only to reply inside the existing direct conversation",
]
```

Add a multiline scan for the old bottom call shape:

```python
multiline_patterns = [
    r"send_im_message\([\s\S]{0,500}\bto\s*=\s*None[\s\S]{0,500}\breply_to\s*=",
    r"send_im_message\([\s\S]{0,500}\breply_to\s*=[\s\S]{0,500}\bto\s*=\s*None",
]
```

Expected result after implementation:

```text
hits == []
```

- [ ] **Step 2: Run residue guard before cleanup**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_im_reply_wrapper_convergence_has_no_old_core_reply_branch_residue -q
```

Expected before cleanup:

- failure with hits in `scripts/env/services/messages.py` and tool catalog wording.

- [ ] **Step 3: Run residue guard after cleanup**

Expected after implementation:

- pass with no hits.

## Task 6: Full Focused Verification And Acceptance

**Files:**

- No new production files.
- Update tests only if focused verification exposes stale old-API call sites.

- [ ] **Step 1: Run focused behavior tests**

Run:

```bash
python3 -m pytest \
  tests/test_im_product_core.py \
  tests/test_message_tool_im_client.py \
  tests/test_external_im_session.py \
  tests/test_im_http_router.py \
  tests/test_im_external_reply_loop.py \
  tests/test_web_management.py \
  -q
```

Expected:

- all pass;
- no service-starting broad suite is invoked by this command.

- [ ] **Step 2: Run focused surface and residue tests**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_task_management_skill_architecture.py \
  tests/test_repo_consistency.py \
  -q
```

Expected:

- all pass;
- residue guard catches no old reply branch terms.

- [ ] **Step 3: Run exact manual scans**

Run:

```bash
rg -n "_resolve_reply_conversation|_direct_conversation_identity_ids|reply target cannot be derived|reply_to must stay in the same direct conversation|Central IM derives the other direct identity|reply_to only to reply inside the existing direct conversation" \
  scripts/env/services/messages.py \
  scripts/env/tool_runtime/im_client.py \
  tools/launcher/external_im_session.py \
  tools/launcher/task_sys_runtime.py \
  scripts/env/tools/message/tool.py \
  buddyswitch/skills/shared/task-management/SKILL.md \
  tests
```

Expected:

```text
no matches
```

Run:

```bash
rg -n "send_im_message\([\s\S]{0,500}to\s*=\s*None[\s\S]{0,500}reply_to\s*=" tests scripts/env tools/launcher
```

Expected:

```text
no matches
```

- [ ] **Step 4: Inspect final diff for boundary cleanliness**

Run:

```bash
git diff -- scripts/env/services/messages.py scripts/env/tool_runtime/im_client.py tools/launcher/external_im_session.py tools/launcher/task_sys_runtime.py scripts/env/tools/message/tool.py tests
```

Diff acceptance:

- `send_im_message` no longer has a reply routing branch;
- `send_im_reply` is the only product reply wrapper;
- actor and external projections route reply through wrapper;
- tool catalog explains wrapper-to-target normalization;
- Task Sys frame prompt changes, if any, are wording-only and preserve the completed side/parent message permission surface;
- tests assert resolver use and residue cleanup.

## Acceptance Criteria

The task is complete only when all criteria are true:

- `reply_to` sends pass through `resolve_im_send_target(...)`.
- Actor reply to offline actor target rejects before new message write.
- Actor reply to message not addressed to the actor rejects before new message write.
- Reply success persists `reply_to` metadata on the new message.
- Reply success marks the original inbound message `replied`.
- Core send does not read original messages.
- Core send does not derive target from `reply_to`.
- Core send does not mark original messages replied.
- Tool and skill surfaces describe `reply_to` as wrapper-to-target normalization.
- Task Sys frame prompts remain aligned with the completed side/parent message permission update and do not teach old bottom reply semantics.
- Scoped residue guard and exact manual scans have no old-branch hits.
- Focused behavior tests and surface tests pass.

## Out Of Scope

- Reworking Task Sys side/parent message permissions.
- Reworking Central daemon socket ownership.
- Rewriting IM storage layout.
- Replacing direct conversation persistence.
- Adding a generic workflow engine, permission framework, or compatibility bridge.
- Running broad service-starting suites without lifecycle-specific need.

## Final Handoff Summary Template

Use this format after implementation:

```text
Implemented Central IM reply wrapper convergence.

Changed:
- Product service: target-only core send plus send_im_reply wrapper.
- Actor/external projections: reply intent routes through wrapper and target resolver.
- Tool/skill surfaces: reply_to described as wrapper-to-target normalization.
- Tests: resolver-use behavior, negative no-write cases, residue guard.

Verified:
- <focused behavior command> PASS
- <surface/residue command> PASS
- <manual residue scans> no matches

Remaining risk:
- <state any remaining risk, or "none identified in focused verification">
```

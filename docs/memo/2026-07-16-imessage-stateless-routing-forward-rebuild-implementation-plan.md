# iMessage Two-Domain Parser Forward Rebuild Plan

> **For agentic workers:** Execute inline with `superpowers:executing-plans`, `superpowers:test-driven-development`, and the repository's sole `./buddyswitch-test focused` entry. Do not delegate this task.

**Goal:** Make iMessage interaction syntax one explicit parser with two mutually exclusive domains: `NativeReply` and `TopLevel`.

**Architecture:** The parser consumes the complete iMessage row and returns either `NativeReply(anchor_guid, body)` or `TopLevel(command)`. Only `TopLevel` parses `/actors`, `@actor-id content`, or invalid input; `NativeReply.body` is opaque actor payload. Central IM remains the sole owner of Send, Reply, target resolution, and the one-reply disposition rule.

**Tech Stack:** Python 3.13, `imsg` 0.11.1, macOS Messages `chat.db`, External IM HTTP API, Central IM, JSON channel state, `./buddyswitch-test focused`.

---

## 1. Acceptance sentence

For every non-empty inbound iMessage row, one pure parser produces exactly one `NativeReply` or `TopLevel` syntax tree; `/actors` and `@actor-id content` exist only inside `TopLevel`, Reply body is never recursively parsed as an interface command, `reply_to_guid` alone never creates `NativeReply`, and no flat-intent, priority, fallback, focus, selection, or TTL model remains live.

## 2. Confirmed facts

1. Live Messages DB evidence shows ordinary top-level messages in this direct chat carry `reply_to_guid`; explicit inline Reply additionally carries `thread_originator_guid`.
2. `thread_originator_guid` is therefore the current Native Reply form marker. `reply_to_guid` and `reply_to_text` are not interface-routing inputs.
3. The existing schema-6 `message_links` map is the single owner of exact `iMessage GUID -> Central IM message/event` correlation and survives service restart without TTL.
4. Live routing has already proved `/actors`, explicit `@actor`, exact GUID Reply, one-shot rejection, contact isolation, offline failure/recovery, and actor-visible `reply_to` references.
5. The current parser behavior is correct, but its flat result types and wording still represent competing alternatives rather than the accepted two-domain grammar. This architecture residue is the rebuild bottleneck.

## 3. Current-only grammar and ownership

```text
InboundMessage := NativeReply | TopLevel

NativeReply := thread_originator_guid body

TopLevel := ListActors
          | SendToActor(actor_id, content)
          | InvalidTopLevel
```

Rules:

- `NativeReply` and `TopLevel` are disjoint message forms, not competing commands.
- A non-empty `thread_originator_guid` constructs `NativeReply`; its body is opaque to the interface parser.
- Without `thread_originator_guid`, the same parser constructs `TopLevel` and parses its command production.
- `/actors` must match the complete trimmed top-level body.
- `@actor-id content` must have a non-empty identity token and non-empty content.
- `reply_to_guid`, `reply_to_text`, actor envelope text, prior actor, and cached actor lists are forbidden routing inputs.
- Parser code performs no state lookup, API call, send, persistence, or feedback.
- Execution consumes the parsed tree once and never reparses its body.

## 4. Files and direct replacement

**Modify:**

- `tools/launcher/imessage_channel.py`: own the two-domain AST, parser productions, and one parsed-tree dispatch.
- `tests/unit/im/test_imessage_inbound_parser.py`: prove the pure grammar and forbid replaced architecture names.
- `tests/integration/im/test_imessage_routing.py`: express user-visible behavior in domain language.
- this plan: record exact RED/GREEN, affected proof, residue, and live acceptance.

**Physically remove:**

- `_ActorsQueryIntent`, `_ActorSendIntent`, `_NativeReplyIntent`, `_InvalidInputIntent`, and `_InboundIntent`;
- `_parse_inbound_intent`;
- flat `intent` dispatch and the `_handle_actor_mention` method name;
- active test or plan wording that models Native Reply as winning a priority contest;
- every `reply_to_guid` fallback or alternate parser path.

No compatibility aliases, adapters, re-exports, deprecated names, dual parser, or migration reader are allowed.

## 5. TDD execution

### Task 1: RED — lock the two-domain syntax tree

**Files:**

- Modify: `tests/unit/im/test_imessage_inbound_parser.py`
- Modify: `tests/integration/im/test_imessage_routing.py`

- [x] Replace direct parser expectations with the exact new tree:

```python
parsed = imessage_channel._parse_inbound_message(
    {
        "text": "/actors",
        "thread_originator_guid": "ACTOR-BUBBLE-GUID",
        "reply_to_guid": "OTHER-CONTEXT-GUID",
    }
)
self.assertEqual(
    parsed,
    imessage_channel._NativeReply(
        anchor_guid="ACTOR-BUBBLE-GUID",
        body="/actors",
    ),
)
```

- [x] Prove `reply_to_guid` alone produces the nested top-level tree:

```python
self.assertEqual(
    imessage_channel._parse_inbound_message(
        {
            "text": "@act-dev-demo hello",
            "reply_to_guid": "PREVIOUS-DIRECT-MESSAGE-GUID",
        }
    ),
    imessage_channel._TopLevel(
        command=imessage_channel._SendToActor(
            target_identity_id="act-dev-demo",
            content="hello",
        )
    ),
)
```

- [x] Add direct `TopLevel(ListActors)` and `TopLevel(InvalidTopLevel)` proofs.
- [x] Add a structural assertion rejecting every physically replaced type/function name from production source.
- [x] Rename integration cases from ownership language to domain language without changing their product assertions.
- [x] Run:

```bash
./buddyswitch-test focused \
  tests/unit/im/test_imessage_inbound_parser.py \
  tests/integration/im/test_imessage_routing.py
```

Expected RED: new domain types/parser are absent and old flat parser names remain.

Observed RED: `00798731bd944e9c9db1f471e76fadab` — 13 architecture failures and 16 behavior passes. Failures were limited to the absent two-domain parser/types and presence of the retired flat names.

### Task 2: GREEN — replace the parser and dispatch

**Files:**

- Modify: `tools/launcher/imessage_channel.py`

- [x] Add only these current syntax-tree types:

```python
@dataclass(frozen=True)
class _ListActors:
    pass

@dataclass(frozen=True)
class _SendToActor:
    target_identity_id: str
    content: str

@dataclass(frozen=True)
class _InvalidTopLevel:
    pass

_TopLevelCommand = _ListActors | _SendToActor | _InvalidTopLevel

@dataclass(frozen=True)
class _NativeReply:
    anchor_guid: str
    body: str

@dataclass(frozen=True)
class _TopLevel:
    command: _TopLevelCommand

_ParsedInboundMessage = _NativeReply | _TopLevel
```

- [x] Implement the grammar as one parser with a top-level production:

```python
def _parse_inbound_message(row: dict[str, Any]) -> _ParsedInboundMessage:
    content = _content_from_row(row)
    raw_anchor = row.get("thread_originator_guid")
    anchor_guid = raw_anchor.strip() if isinstance(raw_anchor, str) else ""
    match anchor_guid:
        case "":
            return _TopLevel(command=_parse_top_level_command(content))
        case _:
            return _NativeReply(anchor_guid=anchor_guid, body=content)


def _parse_top_level_command(content: str) -> _TopLevelCommand:
    match content.split(maxsplit=1):
        case ["/actors"]:
            return _ListActors()
        case [head, body] if head.startswith("@") and len(head) > 1 and body.strip():
            return _SendToActor(target_identity_id=head[1:], content=body.strip())
        case _:
            return _InvalidTopLevel()
```

- [x] Parse once before state execution, dispatch `_NativeReply` or `_TopLevel(command)` once, and rename `_handle_actor_mention` to `_handle_actor_send`.
- [x] Delete the complete flat parser implementation and names; do not alias them.
- [x] Run the Task 1 command and require GREEN.

Observed GREEN: `60a6191c2e784f86a040896279956f9d` — 19 passed, 10 subtests passed.

### Task 3: affected proof and residue acceptance

- [x] Run once:

```bash
./buddyswitch-test focused \
  tests/unit/im/test_imessage_inbound_parser.py \
  tests/unit/im/test_imessage_command_client.py \
  tests/integration/im/test_imessage_state.py \
  tests/integration/im/test_imessage_routing.py \
  tests/integration/im/test_imessage_outbound.py \
  tests/integration/im/test_imessage_worker.py \
  tests/integration/im/test_http_router.py::ImHttpRouterTests::test_external_http_reply_uses_wrapper_without_target_identity \
  tests/integration/im/test_external_session.py::ExternalImSessionTests::test_session_reply_uses_reply_wrapper_without_explicit_target_identity \
  tests/integration/im/test_external_session.py::ExternalImSessionTests::test_session_list_and_send_reject_offline_actor_rows \
  tests/integration/im/test_product_core.py::ImProductCoreTests::test_send_im_reply_rejects_non_processable_source_message_without_write
```

- [x] Require zero matches in production/current tests for the removed flat parser names and priority wording; scoped structural negative assertions are allowed.
- [x] Require `reply_to_guid` only in negative parser/routing fixtures, never production.
- [x] Run `git diff --check`, inspect the full task diff, and verify runner roots/processes were removed.

Observed affected GREEN: `34c88276262748cb8152f2a1f96d3c15` — 45 passed, 19 subtests. `git diff --check` passed; all three run roots were removed; no runner or pytest process remained. Removed names exist only in the structural absence assertion, priority wording only describes forbidden residue in this plan, and `reply_to_guid` exists only in negative fixtures.

### Task 4: live product acceptance

- [x] Restart the `fea-im` service on `127.0.0.1:8765` without resetting schema-6 state.
- [x] Prove top-level `/actors` when `reply_to_guid` is present and `thread_originator_guid` absent.
- [x] Prove top-level `@actor` reaches only the explicit actor.
- [x] Prove Native Reply command-like body reaches the anchor actor as opaque body.
- [x] Prove ordinary top-level text returns interface usage and wakes no actor.
- [x] Prove repeated Native Reply follows Central IM one-shot rejection without target fallback.
- [x] Prove a new mapped bubble survives another service restart and still routes Native Reply.

Observed live acceptance:

- top-level `PARSER-PLAIN-13-R2` returned only the usage prompt and appeared in no BuddySwitch state or actor workspace;
- top-level `/actors` returned the three healthy actors even though the direct chat row carried `reply_to_guid`;
- top-level `@act-test-fcd458b81fcd ...REBUILD-ANCHOR-14` created `msg-a82a05c15925` for Test with `reply_to=null`, and Test returned mapped bubble `B0331FB4-...`;
- Native Reply `/actors` to that bubble created `msg-ea029e63468d` with exact `reply_to=msg-e8ce58cfe480`; Test, not the interface, interpreted the opaque body and generated a new actor-list reply;
- a second Native Reply to the same source had `thread_originator_guid=B0331FB4-...` while its unrelated `reply_to_guid` was `68BE7424-...`; the interface used the Native Reply anchor, returned `Reply failed...`, and Central IM created no message after sequence 16;
- after a complete service restart, all seven mappings remained. Native Reply through persisted GUID `68BE7424-...` created `msg-e27dba53fdc5` for Test with `reply_to=msg-be74a03d94f5`; Test returned `PERSIST-OK-17`, stored as the eighth mapped bubble.

## 6. Evidence retained from this worktree

- Original forward rebuild focused acceptance: `31cd1ea3be754d5b87ef7e2a89dc71ad` — 39 passed, 9 subtests.
- `reply_to_guid` defect/parser correction RED: `67cdd6057b254acf9cbf76f948482ead`.
- Flat parser exact GREEN: `dd228e1dbfde45bba99154c145616545` — 18 passed, 3 subtests.
- Flat parser affected GREEN: `e6b7ef30b5a84abd80cf29da75801037` — 44 passed, 12 subtests.
- Two-domain architecture RED: `00798731bd944e9c9db1f471e76fadab` — 13 architecture failures, 16 behavior passes.
- Two-domain exact GREEN: `60a6191c2e784f86a040896279956f9d` — 19 passed, 10 subtests.
- Two-domain affected GREEN: `34c88276262748cb8152f2a1f96d3c15` — 45 passed, 19 subtests.
- Final-source affected GREEN: `aebcd1788dfd46358e0ec05d02a84c56` — 45 passed, 19 subtests; runner root removed cleanly.
- Live current service evidence: top-level `/actors` and explicit `@dev`/`@pm` route correctly despite `reply_to_guid`; Native Reply `/actors` reached PM with exact `reply_to`, after which PM independently interpreted the opaque body and generated its own actor list.

These runs remain historical evidence for behavior they covered. They do not prove the pending two-domain architecture replacement.

## 7. Completion gate

Completion requires all four tasks checked, exact and affected proof green on the final source identity, zero unexplained parser residue, live acceptance complete, and runtime/test resources clean. Do not run repository-wide `full`; the user requested efficient affected-boundary proof.

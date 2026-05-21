# Tool Layer P0/P1 Test Plan

Date: 2026-05-21

Scope: `docs/spec/2026-05-21-tool-layer-p0-p1-forward-scope.md`

## Test Strategy

Tests must start from functional behavior, not from the easiest implementation path.

The suite must prove:

- humans and buddies see a compact working surface;
- private or historical data is not leaked into the wrong surface;
- direct-message semantics stay direct and inbox-scoped;
- buddybox policy is visible without changing privacy;
- registry and payload contracts are coherent;
- architecture decoupling remains intact.

Do not write tests that merely assert fields exist. Each behavior test should prove visibility, compactness, state unchanged, or a boundary.

## Requirement Matrix

### P0 Requirements

R1. `context.get.artifact_summaries` excludes superseded/history artifacts by default.

R2. `context.summarize.candidate_artifacts` excludes superseded/history artifacts by default.

R3. Context candidate artifacts include current shared material.

R4. Context candidate artifacts include current close proof.

R5. Context candidate artifacts include active-buddy-owned drafts only in unfiltered context.

R6. `context.summarize {"track_id": ...}` excludes active-buddy-owned drafts that are not tied to that track.

R7. Context candidate artifacts exclude archived-track artifacts.

R8. `artifact.list` can still show readable historical artifacts according to its discovery contract.

R9. `artifact.get` still returns `relation_summary` for a readable historical artifact.

R10. All expected registry tool sets include `request`.

R11. Dynamic probe tool discovery still works without central registry edits.

R12. Registry projection does not import private `_impl`, `env.repos`, or `env.domain` modules.

R13. Hyphenated action ids are normalized to underscore action ids where existing router tests require it.

R14. `request.create` rejects unsupported fields before missing required fields.

R15. `request.create` unknown-field rejection leaves runtime state unchanged.

R16. `artifact_relations.py` does not own publication writes or become a relation engine.

R17. Publication write boundary tests still reject publication logic outside the allowed publication/visibility/storage domains.

R18. Full pytest suite passes.

### P1 Requirements

R19. `context.summarize` includes compact active-buddy inbox message cues.

R20. Message cues include count, latest message ids, sender buddy, and reply linkage when present.

R21. Message cues do not include full message content by default.

R22. Message cues do not include sent messages that are not in the active buddy's inbox.

R23. `buddybox.desc` includes a `logical_name_policy` object.

R24. `logical_name_policy` describes relative path requirement, absolute-path rejection, traversal rejection, and buddy-prefix rejection.

R25. `logical_name_policy` includes generic valid examples only.

R26. `logical_name_policy` does not prescribe role/business directory SOP.

R27. Invalid buddybox logical names still return structured rejection feedback and mutate no files.

R28. `message.list` keeps existing active-buddy inbox visibility.

R29. `message.list {"q": ...}` filters only active-buddy inbox messages by keyword.

R30. `message.list {"limit": N}` returns at most N active-buddy inbox rows.

R31. `message.list` applies visibility before `q` and `limit`.

R32. `message.list` rejects unsupported product-binding fields such as `track_id`, `artifact_id`, `request_id`, and `refs`.

R33. Message storage remains direct-message shape only: no `track_id`, `artifact_id`, `request_id`, `refs`, `status`, or `read_at`.

R34. `message.send` remains unchanged for direct send and same-pair replies.

R35. No P1 change introduces sibling tool imports or central registry business special cases.

## Detailed Test Design

### T1: Context Candidate Artifacts Are Current Working Surface

File: `tests/test_context_binding_env_tool.py`

Seed:

- active track `track-context-active`;
- current material `art-task-dev-context-note-r2`;
- superseded material `art-task-dev-context-note-r1`;
- archived track artifact `art-task-dev-archived-r1`;
- active-buddy draft `art-dev-private-draft-r1`.

Assertions:

- `context.get {}` `artifact_summaries` contains `art-task-dev-context-note-r2`;
- it does not contain `art-task-dev-context-note-r1`;
- it does not contain `art-task-dev-archived-r1`;
- unfiltered context may contain `art-dev-private-draft-r1` when active buddy owns it;
- rows do not include full `body`.

### T2: Track-Filtered Context Does Not Pull Untied Drafts

File: `tests/test_context_binding_env_tool.py`

Seed:

- track A current artifact;
- track B current artifact;
- active-buddy own draft with no `published_to_track`.

Assertions:

- `context.summarize {"track_id": "track-a"}` contains only artifacts tied to track A;
- it excludes track B artifact;
- it excludes the untied own draft;
- `candidate_requests`, `open_comment_threads`, and `recent_updates` remain track-scoped.

### T3: Artifact History Remains Discoverable Outside Context

File: `tests/test_artifact_env_tool.py`

Seed:

- r1 published material;
- r2 supersedes r1 and becomes current material.

Assertions:

- `context.summarize` does not include r1 as candidate;
- `artifact.list {"track_id": ...}` can include r1 if readable as track history;
- `artifact.get {"artifact_id": "r1"}` returns `relation_summary.publication.currentness == "superseded"`.

### T4: Registry Tool Sets Include Request

Files:

- `tests/test_env_tool_router.py`
- `tests/test_env_tool_package_independence.py`
- existing semantic/schema tests

Assertions:

- expected tool sets include `request`;
- supported actions for `request` are `create`, `list`, `get`, `accept`, `block`, `complete`, `cancel`;
- `context.summarize.tool_affordances` includes `request`;
- dynamic probe discovery test still passes.

### T5: Router Normalization And Catalog Error Isolation

File: `tests/test_env_tool_router.py` or `tests/test_env_tool_semantic_contract.py`

Assertions:

- dispatching `{"tool": "context", "action": "list-sources"}` succeeds as `context.list_sources`;
- failed lookup for unsupported tool does not leave stale load errors that later break `semantic_contract_errors()`;
- dynamic probe discovery remains visible in `env_tools_description()`.

### T6: Request Unknown Field Rejection Order

File: `tests/test_env_tool_payload_contract.py` or `tests/test_request_env_tool.py`

Payload:

```json
{"__unexpected_payload_field__": true}
```

Assertions:

- `request.create` returns `ok=false`;
- response contains `__unexpected_payload_field__`;
- `state_changed=false`;
- no request file is created.

### T7: Artifact Relation Boundary

File: `tests/test_env_layer_boundaries.py`

Assertions:

- `artifact_relations.py` is either free of publication write terms or explicitly allowed only as read-only derived relation helper;
- no new relation object directory exists;
- no relation JSON files exist;
- publication state mutation still lives only in publication/repos/visibility allowlisted modules.

### T8: Context Message Cues Are Compact Inbox Cues

File: `tests/test_host_decision_surface_product_mode.py` or `tests/test_context_binding_env_tool.py`

Seed:

- message from `pm` to active buddy `dev`;
- message from `design` to active buddy `dev` with `reply_to`;
- message from `dev` to `pm`;
- message from `market` to `pm`.

Assertions:

- `context.summarize` includes `message_cues`;
- `message_cues.count >= 2` for active buddy inbox;
- latest rows include message ids and sender buddy;
- reply-linked row includes `reply_to`;
- sent-only `dev -> pm` message is not counted as active buddy inbox;
- no cue row includes `content`.

### T9: Buddybox Desc Logical Name Policy

File: `tests/test_buddybox_env_tool.py`

Assertions:

- `buddybox.desc` includes `buddybox_desc.logical_name_policy`;
- policy says logical names are relative;
- policy says absolute paths are rejected;
- policy says `..` traversal is rejected;
- policy says manifest buddy prefixes are rejected;
- policy includes generic examples such as `notes/todo.md`;
- policy does not include `coordination/`, `execution/`, role names as recommended business paths, or workflow SOP.

### T10: Buddybox Rejection Feedback Uses Policy

File: `tests/test_buddybox_env_tool.py`

Payloads:

- `{"logical_name": "/tmp/x", "content": "x"}`;
- `{"logical_name": "../x", "content": "x"}`;
- `{"logical_name": "dev/x", "content": "x"}` when active buddy is `dev`.

Assertions:

- each rejects with `ok=false`;
- `state_changed=false`;
- `permission_boundary` or rejection detail points to logical-name boundary;
- response contains a structured correctable field for `logical_name`;
- no private file is created.

### T11: Message List Keyword Filter

File: `tests/test_message_env_tool.py`

Seed:

- `pm -> dev`: `Need Wukong proof asset`;
- `design -> dev`: `Hero screenshot ready`;
- `market -> pm`: `Wukong unrelated to dev inbox`;
- `dev -> design`: `Wukong sent by dev`.

Assertions:

- as active buddy `dev`, `message.list {"q": "wukong"}` returns only `pm -> dev`;
- it excludes `market -> pm`;
- it excludes `dev -> design`;
- `state_changed=false`;
- rows do not include unsupported fields.

### T12: Message List Limit

File: `tests/test_message_env_tool.py`

Seed:

- three inbox messages to active buddy.

Assertions:

- `message.list {"limit": 2}` returns exactly two rows;
- rows are deterministic by newest-first if implementation chooses recency ordering;
- response includes `discovery_summary.count == 2` or equivalent returned count.

### T13: Message List Rejects Product Binding Fields

File: `tests/test_message_env_tool.py`

Payloads:

- `{"track_id": "track-x"}`;
- `{"artifact_id": "art-x"}`;
- `{"request_id": "req-x"}`;
- `{"refs": []}`;
- `{"status": "unread"}`.

Assertions:

- each rejects with `E_MESSAGE_PAYLOAD`;
- rejection includes unsupported field name;
- state unchanged.

### T14: Message Send Remains Direct

File: `tests/test_message_env_tool.py`

Assertions:

- existing send/reply tests still pass;
- saved message rows do not contain `track_id`, `artifact_id`, `request_id`, `refs`, `status`, or `read_at`;
- `message.send` rejects product-binding fields.

### T15: Architecture Guard Suite

Files:

- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_tool_package_independence.py`
- `tests/test_parallel_contracts.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`

Assertions:

- no sibling tool imports;
- public tool files do not import host repos/domains;
- registry projection stays definition-derived;
- shared skills do not copy payload/action/schema tables;
- no scheduler/daemon/workflow engine text or code is introduced for this work.

## Verification Commands

Run focused tests after each implementation block:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_package_independence.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_message_env_tool.py -q
python3 -m pytest tests/test_black_box_tool_runtime.py tests/test_parallel_contracts.py tests/test_repo_consistency.py tests/test_runtime_skills.py -q
```

Final verification:

```bash
python3 -m pytest -q
```

Passing focused tests without the final full suite is not enough.

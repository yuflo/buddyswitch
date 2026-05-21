# Request And PM Comment Resolution Test Plan

Date: 2026-05-21

Scope document: `docs/spec/2026-05-21-request-comment-closure-scope.md`

## Goal

Prove BuddySwitch supports a lean cross-buddy request loop and PM-reviewed comment closure through
runtime-owned env tools, without turning messages, private tasks, comments, or tracks into a hidden
workflow engine.

## Task Confirmation

The bottleneck is collaboration closure:

- `message` can ask informally, but cannot expose accepted/blocked/done state.
- `task` can track private work, but cannot represent a cross-buddy request.
- `comment` can discuss a track or artifact, but cannot close reviewed feedback through a tool.

The repair is:

```text
new request object/module + request env tool
existing comment object/module + PM-only comment.resolve operation
```

The repair must be forward-only. There must be no `handoff` compatibility path, no request/message
dual write, no comment reopen path, no approval/review object, and no workflow engine.

## Functional Requirements

R1. `request` is a shipped env tool discovered through the same black-box tool registry as all
existing tools.

R2. `request` exposes exactly these initial operations:

```text
create, list, get, accept, block, complete, cancel
```

R3. `request.create` creates one durable request with `track_id`, `from_buddy`, `to_buddy`,
`title`, `summary`, optional `target_refs`, `status=open`, no blocker, empty `result_refs`, and
timestamps.

R4. `request.create` rejects unknown buddies, self-requests, archived or missing tracks, blank
titles/summaries, malformed target refs, unsupported payload fields, and unsupported status inputs.

R5. Request refs use a concrete schema: each ref is an object with `type` and `id`; supported types
are `track`, `artifact`, and `comment`. `track` refs must match the bound `track_id`; artifact and
comment refs must be readable in the request track context.

R6. `request.list` returns requests visible to the active buddy. Visibility is: requester,
recipient, or PM on the same readable track. Filters support `box`, `status`, `track_id`, and
`buddy`.

R7. `request.get` returns one visible request and rejects invisible requests without leaking body
fields.

R8. `request.accept`, `request.block`, and `request.complete` are recipient-only state mutations.

R9. `request.cancel` is requester-only. It is not a PM override in this task.

R10. Valid request state transitions are only:

```text
open -> accepted
open -> canceled
accepted -> blocked
accepted -> done
accepted -> canceled
blocked -> accepted
blocked -> done
blocked -> canceled
```

R11. `request.block` requires a non-empty `blocker` and clears completion/cancel fields.

R12. `request.complete` requires a non-empty `result_refs` array and rejects completion from
`open`, `done`, or `canceled`.

R13. All request write successes return canonical tool result fields, including `state_changed`,
`durability`, `created_ids` or `updated_ids`, `state_changes`, and actionable next guidance.

R14. All request rejections return canonical rejection fields, `state_changed=false`, and
`durability=none`.

R15. `comment.resolve` is a new operation on the existing `comment` tool. There is no
`comment.reopen`.

R16. `comment.resolve` only succeeds for active buddy `pm`.

R17. `comment.resolve` requires `comment_id` and `resolution_summary`.

R18. `comment.resolve` resolves the whole thread containing `comment_id` by setting every comment in
that thread to `status=resolved`, `resolved_by=pm`, `resolved_at`, and the provided
`resolution_summary`.

R19. `comment.resolve` rejects non-PM callers, missing comments, unreadable targets, archived
targets, blank summaries, unsupported payload fields, and already fully resolved threads.

R20. `comment.list` status counts and thread status reflect PM resolution.

R21. Runtime discovery exposes complete request and comment.resolve schemas through
`context.get.tool_catalog`, `operation_semantics`, `turn_runtime.py status`, and CLI help.

R22. `context.summarize` remains compact but includes request affordance and request counts or
candidate request summaries.

R23. Workspace projection includes requests and request counts without embedding request state into
track, artifact, task, message, or comment objects.

R24. Manifest validation accepts `request.*` permissions and `comment.resolve`; every buddy gets the
request skill/tool permissions needed for participant workflows; only PM gets `comment.resolve`.

R25. `message` remains immutable direct inbox text. Tests must continue rejecting message status,
target refs, broadcast, and workflow fields.

R26. `task` remains active-buddy private. Tests must prove request objects do not mutate or expose
private task ownership.

R27. Architecture tests prove the new request package follows the black-box tool boundary: single
public `tool.py`, no legacy public modules, no direct runtime storage mutation, no sibling tool
imports, and no registry business special cases.

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| REQ1 | R1/R2/R21/R27 | `tests/test_black_box_tool_runtime.py` | request tool is shipped | expected tool/action sets include request; package has only `tool.py` public entrypoint |
| REQ2 | R3/R13 | `tests/test_request_env_tool.py` | PM creates request to Dev | durable request created, status open, correct sender/recipient/track/timestamps |
| REQ3 | R4/R5/R14 | `tests/test_request_env_tool.py` | invalid create payloads | unknown buddy, self-send, missing track, archived track, malformed refs reject with no state change |
| REQ4 | R6/R7 | `tests/test_request_env_tool.py` | visibility and filters | requester/recipient/PM can read; unrelated buddy cannot; filters return expected subsets |
| REQ5 | R8/R10 | `tests/test_request_env_tool.py` | accept lifecycle | recipient moves open to accepted; requester and third buddy are rejected |
| REQ6 | R8/R10/R11 | `tests/test_request_env_tool.py` | block lifecycle | recipient blocks accepted request with blocker; invalid states and blank blocker reject |
| REQ7 | R8/R10/R12 | `tests/test_request_env_tool.py` | complete lifecycle | recipient completes accepted/blocked request with result refs; open/done/canceled reject |
| REQ8 | R9/R10 | `tests/test_request_env_tool.py` | cancel lifecycle | requester cancels open/accepted/blocked request; recipient/third buddy rejected |
| REQ9 | R13/R14 | `tests/test_env_tool_response_contract.py` | response shape | request writes/rejections satisfy canonical success/rejection contracts |
| CMT1 | R15/R21 | `tests/test_env_tool_semantic_contract.py` | comment operations include resolve only | comment actions are add/list/resolve; reopen absent |
| CMT2 | R16/R17/R18 | `tests/test_comment_env_tool.py` | PM resolves thread | every row in thread becomes resolved with PM resolution metadata |
| CMT3 | R19 | `tests/test_comment_env_tool.py` | non-PM and bad resolve payloads | non-PM, missing id, blank summary, already resolved, archived target reject with no state change |
| CMT4 | R20 | `tests/test_comment_env_tool.py` | listing after resolve | status filters/counts and thread status reflect resolution |
| DISC1 | R21/R22 | `tests/test_host_decision_surface_product_mode.py` | discovery includes request and resolve | full catalog includes schemas; summary has compact affordance and no copied schema blobs |
| MAN1 | R24 | `tests/test_env_manifest_v2.py` | manifest accepts request/comment.resolve | validator accepts request permissions; all buddies have request tool; only PM has comment.resolve |
| PROF1 | R24 | `tests/test_buddy_env_profiles.py` | profiles stay aligned | state/tool capability includes request effects; PM-only resolve is represented without generic permission language |
| PROJ1 | R23 | `tests/test_parallel_contracts.py` | workspace projection includes requests | projection contract and payload contain top-level requests and request counts |
| E2E1 | R1-R24 | `tests/test_env_layer_end_to_end.py` | PM -> Dev -> Test loop | PM creates Dev request, Dev completes with artifact, PM resolves related comment, Test proof remains readable |
| REG1 | R25 | `tests/test_message_env_tool.py` | messages stay non-workflow | status, read, target refs, broadcast, and workflow fields remain rejected |
| REG2 | R26 | `tests/test_task_env_tool.py` | tasks stay private | request lifecycle does not expose or mutate another buddy's tasks |
| SCAN1 | R27 | `tests/test_repo_consistency.py` | no transition residue | no `handoff`, request/message bridge, compatibility adapter, or old public module residue |

## Detailed Test Designs

### REQ2: Create Request Main Path

Setup:

- create active track `track-req-main`;
- create published artifact `art-design-r1`;
- dispatch `request.create` as PM with `to_buddy=dev`.

Assertions:

- response has `ok=true`, `state_changed=true`, `durability=durable`;
- `created_ids == [request_id]`;
- persisted object is under `buddyswitch/objects/requests/<request_id>.json`;
- object has `from_buddy=pm`, `to_buddy=dev`, `status=open`, `blocker=null`,
  `target_refs=[{"type":"artifact","id":"art-design-r1"}]`, and empty `result_refs`;
- track, artifact, task, message, and comment files are unchanged except for seeded setup.

### REQ4: Visibility

Seed:

- request A: PM -> Dev on `track-visible`;
- request B: Design -> Test on `track-visible`;
- request C: PM -> Market on another track.

Assertions:

- Dev can get/list request A.
- PM can get/list request A and B because PM owns iteration visibility.
- Design can get/list request B.
- Market cannot get request A unless Market is requester or recipient.
- `request.list --box inbox` for Dev returns requests where `to_buddy=dev`.
- `request.list --box outbox` for PM returns requests where `from_buddy=pm`.
- `request.list --track_id track-visible` filters correctly.

### REQ5-REQ8: Lifecycle

Test every allowed transition and representative rejected transitions:

- `open -> accepted` by recipient succeeds.
- `accepted -> blocked` by recipient with blocker succeeds.
- `blocked -> accepted` by recipient clears blocker and succeeds.
- `accepted -> done` by recipient with non-empty result refs succeeds.
- `open -> done` rejects.
- `done -> blocked` rejects.
- `canceled -> accepted` rejects.
- requester can cancel open/accepted/blocked;
- recipient cannot cancel;
- third buddy cannot mutate.

Each rejection must assert no persisted request JSON changed.

### CMT2: PM Resolves Thread

Setup:

- create track;
- Dev adds root comment;
- Design adds reply to root;
- PM calls `comment.resolve` with the reply id and a resolution summary.

Assertions:

- both root and reply comments now have `status=resolved`;
- both have `resolved_by=pm`, non-empty `resolved_at`, and same `resolution_summary`;
- target track JSON is unchanged;
- `comment.list status=resolved` returns both comments;
- `comment.list status=open` returns none for that thread;
- workspace projection open/resolved counts update.

### CMT3: PM-Only Boundary

Setup:

- create readable track and comment thread.

Assertions:

- Dev calling `comment.resolve` rejects with `permission_boundary=comment.pm_review_authority`;
- PM calling with blank summary rejects with `permission_boundary=request-payload`;
- PM calling a missing `comment_id` rejects and does not create a comment file;
- PM resolving an already resolved thread rejects with `permission_boundary=comment.state`;
- resolving a comment on an archived target rejects through the existing target lifecycle boundary.

## Required Verification Commands

Focused tests:

```bash
python3 -m pytest \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Runtime integration:

```bash
python3 -m pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_parallel_contracts.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_repo_consistency.py \
  -q
```

Regression sweep:

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py \
  tests/test_message_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_runless_runtime_contract.py \
  tests/test_runtime_skills.py \
  -q
```

Architecture residue scan:

```bash
rg -n "handoff|request-message bridge|compatibility adapter|dual catalog|fallback registry|comment\\.reopen|review object|approval object" \
  scripts tests buddyswitch framework docs/spec docs/memo README.md
```

Allowed hits in the scan are only historical docs that explicitly mark rejected designs or this
planning scope. Active runtime code and tests must not contain compatibility implementation paths.

## Completion Standard

The test plan is complete only when:

- every functional requirement above has at least one test;
- focused tests prove request lifecycle and PM-only comment resolution;
- integration tests prove context/projection/manifest/skill surfaces are aligned;
- regression tests prove message and task semantics were not stretched;
- static tests prove no transition architecture was introduced.

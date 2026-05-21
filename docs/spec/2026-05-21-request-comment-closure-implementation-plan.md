# Request And PM Comment Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Runtime behavior changes must follow `superpowers:test-driven-development`: write the focused failing test, verify the failure, implement the smallest direct change, and rerun the focused test before moving on.

**Goal:** Add a runtime-owned `request` object/tool and PM-only `comment.resolve` so lean buddy collaboration has verifiable handoff and closure state.

**Architecture:** Follow the existing black-box env.tool runtime. `scripts/env/tools/request/tool.py::DEFINITION` owns the public request contract; `request/_impl.py` calls host-owned domain/repo access through `ToolContext`; shared registry code only discovers and projects definitions. `comment.resolve` is added to the existing comment package without adding `comment.reopen`, review objects, approval objects, or compatibility paths.

**Tech Stack:** Python runtime tools, JSON-backed repos, dataclass tool definitions, broker-routed `env.tool`, JSON-compatible schemas, `unittest`/`pytest`, BuddySwitch manifest/profile/skill/context/projection contracts.

---

## Source Inputs

Read before implementation:

- `docs/spec/2026-05-21-request-comment-closure-scope.md`
- `docs/spec/2026-05-21-request-comment-closure-test-plan.md`
- `docs/memo/2026-05-20-black-box-tool-runtime-memo.md`
- `docs/memo/2026-05-20-tool-layer-semantic-contract-memo.md`
- `scripts/env/tool_runtime/definition.py`
- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/tools/comment/tool.py`
- `scripts/env/tools/comment/_impl.py`
- `scripts/env/repos/comments.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/task/_impl.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/message/_impl.py`
- `scripts/env/repos/messages.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/runtime_store/projections.py`
- `framework/contracts/workspace-projection.json`
- `buddyswitch/manifest.toml`
- `framework/contracts/*.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`

## Forward Rules

- Do not create `handoff`.
- Do not use `message` as a request transport with status fields.
- Do not make `task` cross-buddy-readable.
- Do not add `comment.reopen`.
- Do not add a `review` or `approval` object.
- Do not add a workflow engine, assignment engine, WIP model, generic permission language, or event bus.
- Do not create compatibility adapters, old public tool modules, central schema catalogs, or registry per-tool business logic.
- Do not edit `main`; all work stays in `.worktrees/clean-runtime-env`.

## Target Files

Create:

```text
scripts/env/domain/requests.py
scripts/env/repos/requests.py
scripts/env/tools/request/__init__.py
scripts/env/tools/request/tool.py
scripts/env/tools/request/_impl.py
buddyswitch/skills/shared/request-tool/SKILL.md
tests/test_request_env_tool.py
```

Modify:

```text
scripts/env/repos/runtime_files.py
scripts/env/tool_runtime/context.py
scripts/env/tools/comment/tool.py
scripts/env/tools/comment/_impl.py
scripts/env/repos/comments.py
scripts/env/tools/context/_impl.py
scripts/runtime_store/projections.py
framework/contracts/workspace-projection.json
buddyswitch/manifest.toml
scripts/env_manifest.py
framework/contracts/buddy-env-profile.json
buddyswitch/env-profiles/*.json
framework/contracts/{pm,design,dev,market,test}.md
tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md
buddyswitch/skills/shared/comment-tool/SKILL.md
tests/test_black_box_tool_runtime.py
tests/test_env_tool_semantic_contract.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_response_contract.py
tests/test_comment_env_tool.py
tests/test_host_decision_surface_product_mode.py
tests/test_env_layer_end_to_end.py
tests/test_parallel_contracts.py
tests/test_env_manifest_v2.py
tests/test_buddy_env_profiles.py
tests/test_runtime_skills.py
tests/test_repo_consistency.py
```

## Data Contracts

### Request Object

```json
{
  "id": "req-example",
  "track_id": "track-example",
  "from_buddy": "pm",
  "to_buddy": "dev",
  "title": "Implement approved scope",
  "summary": "Build the scoped flow from the current design artifact.",
  "target_refs": [{"type": "artifact", "id": "art-design-r1"}],
  "status": "open",
  "blocker": null,
  "result_refs": [],
  "created_at": "2026-05-21T00:00:00+08:00",
  "updated_at": "2026-05-21T00:00:00+08:00",
  "accepted_at": null,
  "blocked_at": null,
  "completed_at": null,
  "canceled_at": null
}
```

Valid statuses:

```text
open, accepted, blocked, done, canceled
```

Request ref item schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "id"],
  "properties": {
    "type": {"type": "string", "enum": ["track", "artifact", "comment"]},
    "id": {"type": "string"}
  }
}
```

### Comment Resolution Fields

Add these optional fields to comment rows:

```json
{
  "resolved_by": "pm",
  "resolved_at": "2026-05-21T00:00:00+08:00",
  "resolution_summary": "Reviewed by PM; addressed in art-dev-r1."
}
```

For unresolved comments, these fields are `null`.

## Task 1: Write Failing Request And Resolve Tests

**Files:**

- Create: `tests/test_request_env_tool.py`
- Modify: `tests/test_comment_env_tool.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Add `tests/test_request_env_tool.py`**

Use `RuntimeWorkspaceTestMixin` and the broker dispatch helper pattern from `tests/test_message_env_tool.py` and `tests/test_comment_env_tool.py`.

Add tests covering:

- create main path;
- invalid create payloads;
- visibility for requester/recipient/PM/unrelated buddy;
- accept/block/complete/cancel lifecycle;
- invalid transition rejections;
- canonical response shape;
- no mutation outside request objects.

- [ ] **Step 2: Replace unsupported resolve test**

In `tests/test_comment_env_tool.py`, replace `test_resolve_and_reopen_actions_are_not_supported` with PM-only resolve tests:

- PM resolves a thread from any comment id in that thread;
- non-PM resolve rejects with `permission_boundary="comment.pm_review_authority"`;
- blank `resolution_summary` rejects with `permission_boundary="request-payload"`;
- already resolved thread rejects with `permission_boundary="comment.state"`;
- `comment.reopen` remains unsupported with `E_ENV_TOOL`.

- [ ] **Step 3: Update semantic/schema/response expectations**

Update:

- `tests/test_env_tool_semantic_contract.py`: expected tools include `request`; comment actions include `resolve`; request action boundaries mention create/list/get/accept/block/complete/cancel.
- `tests/test_env_tool_schema_contract.py`: request schemas have required fields, ref item shapes, status/box enums, and comment.resolve schema has required `comment_id` and `resolution_summary`.
- `tests/test_env_tool_response_contract.py`: `context.get` no longer excludes `comment.resolve`; request write and rejection paths satisfy canonical response fields.

- [ ] **Step 4: Verify focused failures**

Run:

```bash
python3 -m pytest \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected before implementation: failures for unsupported `request`, unsupported `comment.resolve`,
missing schemas, and missing request persistence.

## Task 2: Add Request Runtime Storage

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Create: `scripts/env/repos/requests.py`
- Modify: `scripts/env/tool_runtime/context.py`

- [ ] **Step 1: Add request object directory**

In `scripts/env/repos/runtime_files.py`:

- add `REQUESTS_DIR = OBJECTS_ROOT / "requests"` in `_recompute_runtime_roots`;
- create `REQUESTS_DIR` in `ensure_runtime_dirs`.

- [ ] **Step 2: Create request repo**

Create `scripts/env/repos/requests.py` with:

- `VALID_REQUEST_STATUS = ("open", "accepted", "blocked", "done", "canceled")`;
- `request_file(request_id)`;
- `list_requests()`;
- `get_request(request_id)`;
- `save_request(request)`;
- `create_request(...)`;
- `update_request(request_id, patch)`.

Validation must:

- require safe ids with `runtime_files.require_id`;
- require manifest-safe buddy ids as non-empty strings;
- require `track_id`, `title`, `summary`;
- require `target_refs` and `result_refs` to be lists of ref objects;
- reject unknown fields;
- normalize unresolved resolution-like fields to `None`;
- sort list output by `updated_at` descending, then id.

- [ ] **Step 3: Wire repo access**

In `scripts/env/tool_runtime/context.py`:

- import `env.repos.requests as _request_repo`;
- add `request` to `RepoAccess`;
- add request runtime source text to `RuntimeObjectAccess.runtime_sources()`.

- [ ] **Step 4: Run repo-focused tests**

Run:

```bash
python3 -m pytest tests/test_request_env_tool.py -q
```

Expected after this task: tests still fail at missing request tool/domain, but storage import errors are gone.

## Task 3: Add Request Domain Rules

**Files:**

- Create: `scripts/env/domain/requests.py`
- Modify: `scripts/env/tool_runtime/context.py`

- [ ] **Step 1: Create domain exceptions**

Create:

- `RequestPayloadError(message, correctable_fields=None, field_errors=None)`;
- `RequestScopeError(message, permission_boundary, human_summary, why_blocked, retryable=False, correctable_fields=None, code="E_REQUEST_SCOPE")`;
- `RequestStateError(message, correctable_fields=None)`.

- [ ] **Step 2: Add normalization helpers**

Implement helpers:

- `manifest_buddy_ids(manifest)`;
- `ensure_manifest_buddy(buddy_id, manifest_buddy_ids, field)`;
- `normalize_ref_items(value, field)`;
- `normalize_create_args(args, active_buddy, manifest, track, readable_ref_checker, allowed_fields)`;
- `normalize_list_args(args, manifest, allowed_fields)`;
- `require_request_id(args)`;
- `ensure_visible(request, active_buddy)`;
- `ensure_recipient(request, active_buddy)`;
- `ensure_requester(request, active_buddy)`.

Visibility rule:

```text
active_buddy == request.from_buddy
or active_buddy == request.to_buddy
or active_buddy == "pm"
```

- [ ] **Step 3: Add transition helpers**

Implement:

- `accept_patch(request, active_buddy, now)`;
- `block_patch(request, active_buddy, blocker, now)`;
- `complete_patch(request, active_buddy, result_refs, now)`;
- `cancel_patch(request, active_buddy, now)`.

Use exactly the transition table in the scope doc.

- [ ] **Step 4: Wire domain access**

In `ToolContext.DomainAccess`, add `request`.

- [ ] **Step 5: Run request tests**

Run:

```bash
python3 -m pytest tests/test_request_env_tool.py -q
```

Expected after this task: tests still fail until the tool package exists.

## Task 4: Add Request Tool Package

**Files:**

- Create: `scripts/env/tools/request/__init__.py`
- Create: `scripts/env/tools/request/tool.py`
- Create: `scripts/env/tools/request/_impl.py`

- [ ] **Step 1: Define `request` ToolDefinition**

`tool.py` must expose:

```text
DEFINITION = ToolDefinition(...)
invoke(action, args, context)
```

Actions:

```text
create
list
get
accept
block
complete
cancel
```

Every input schema must include:

- root `type: object`;
- `additionalProperties: false`;
- `required`;
- field descriptions;
- enums for `status`, `box`, `type`;
- nested `target_refs.items` and `result_refs.items` object schemas.

- [ ] **Step 2: Implement `_impl.py` handlers**

Implement handlers:

- `create_request`;
- `list_requests`;
- `get_request`;
- `accept_request`;
- `block_request`;
- `complete_request`;
- `cancel_request`.

All handlers must:

- derive allowed fields from `DEFINITION`;
- validate through `context.rules.request`;
- read/write through `context.repos.request`;
- use `tool_results.success` and `tool_results.rejection`;
- return `state_changed=false` and `durability=none` on rejection.

- [ ] **Step 3: Use exact action ids**

Broker action ids are underscore/lowercase values from `ActionDefinition.name`. CLI hyphen aliases
are created by `scripts/env/client.py`; broker calls must use canonical names.

- [ ] **Step 4: Run request focused tests**

Run:

```bash
python3 -m pytest tests/test_request_env_tool.py -q
```

Expected after this task: request main path and lifecycle tests pass.

## Task 5: Add PM-Only `comment.resolve`

**Files:**

- Modify: `scripts/env/repos/comments.py`
- Modify: `scripts/env/tools/comment/tool.py`
- Modify: `scripts/env/tools/comment/_impl.py`

- [ ] **Step 1: Extend comment row shape**

In `comments.py`, allow and normalize:

```text
resolved_by
resolved_at
resolution_summary
```

Unresolved comments return those fields as `None`.

- [ ] **Step 2: Add repository mutation**

Add:

```python
def resolve_thread(*, comment_id: str, resolved_by: str, resolution_summary: str) -> list[dict[str, Any]]:
```

Behavior:

- load the target comment;
- find all comments with the same `thread_id`;
- reject when the comment is missing;
- reject when every row in the thread is already resolved;
- set every row in the thread to `status="resolved"` with PM resolution metadata;
- update all rows atomically enough for current JSON-file repo pattern: validate all rows before writing any row.

- [ ] **Step 3: Add `comment.resolve` ToolDefinition action**

Schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["comment_id", "resolution_summary"],
  "properties": {
    "comment_id": {"type": "string", "description": "Comment id in the thread PM reviewed."},
    "resolution_summary": {"type": "string", "description": "PM review closure summary."}
  }
}
```

Use:

- `kind="write"`;
- `mutates="runtime_objects"`;
- `required_permission="comment.resolve"`;
- `authority="pm.review_closure"`.

- [ ] **Step 4: Implement handler**

In `_impl.py`, `resolve_comment` must:

- reject unsupported fields;
- require `active_buddy == "pm"`;
- require non-empty `comment_id` and `resolution_summary`;
- load the comment;
- use existing target readability checks for the comment target;
- call repo `resolve_thread`;
- return `updated_ids` for all resolved comment ids and `state_changes` with `change="resolved"`.

- [ ] **Step 5: Run comment focused tests**

Run:

```bash
python3 -m pytest tests/test_comment_env_tool.py -q
```

Expected after this task: comment add/list/resolve tests pass and `comment.reopen` remains unsupported.

## Task 6: Update Discovery, Context, And Projection

**Files:**

- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/runtime_store/projections.py`
- Modify: `framework/contracts/workspace-projection.json`
- Modify: `tests/test_host_decision_surface_product_mode.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Add request context sections**

In `context/_impl.py`:

- include visible request rows in `_current_context_sections`;
- count requests in `current_context_summary`;
- expose compact `candidate_requests` in `context.summarize`;
- add `requests` to `context_sources_desc`.

Visibility must match domain rule: requester, recipient, or PM.

- [ ] **Step 2: Add workspace projection request view**

In `runtime_store/projections.py`:

- import `request_repo`;
- build `requests = [build_request_view(row) ...]`;
- add request ids/counts by track;
- add `request_ids`, `open_request_count`, `blocked_request_count`, and `done_request_count` to track views if needed for scanning.

Keep request rows top-level. Do not embed full request bodies into track objects.

- [ ] **Step 3: Update projection contract**

In `framework/contracts/workspace-projection.json`:

- add `"requests"` to `top_level_key_order`;
- add `buddyswitch/objects/requests/*.json` to `data_sources`;
- add `request` view shape;
- add request summary fields to track view shape if implemented in Step 2.

- [ ] **Step 4: Run context/projection tests**

Run:

```bash
python3 -m pytest \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_parallel_contracts.py \
  -q
```

Expected after this task: context and projection tests pass.

## Task 7: Update Manifest, Profiles, Skills, And Role Guidance

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `buddyswitch/manifest.toml`
- Modify: `framework/contracts/buddy-env-profile.json`
- Modify: `buddyswitch/env-profiles/*.json`
- Create: `buddyswitch/skills/shared/request-tool/SKILL.md`
- Modify: `buddyswitch/skills/shared/comment-tool/SKILL.md`
- Modify: `framework/contracts/{pm,design,dev,market,test}.md`
- Modify: `tools/launcher/assets/buddies/{pm,design,dev,market,test}/AGENTS.md`

- [ ] **Step 1: Manifest validator**

Add `request` to supported permission objects in `_validate_permission`.

Keep `handoff` rejected.

- [ ] **Step 2: Manifest rows**

Add shared skill row:

```toml
[[skills]]
id = "request-tool"
path = "buddyswitch/skills/shared/request-tool"
```

Add `request-tool` to every buddy skills list.

Add permissions to every buddy:

```text
request.read
request.create
request.accept
request.block
request.complete
request.cancel
```

Add only to PM:

```text
comment.resolve
```

- [ ] **Step 3: Env profiles**

Add `request_effects` to profile contract/profile validation and each profile:

```json
["create", "accept", "block", "complete", "cancel"]
```

Add `comment_effects` or equivalent profile field only if tests need a formal PM-only resolve
surface. If added, PM must include `resolve`; other buddies must not.

- [ ] **Step 4: Shared skills**

Create `request-tool/SKILL.md`:

- purpose: cross-buddy request lifecycle;
- route: `python3 scripts/env/client.py request <action> --payload '<json-object>'`;
- rules: request is product-readable, task remains private, message remains informal;
- operation notes for create/list/get/accept/block/complete/cancel;
- verification through `request.get`, `request.list`, and track/context surfaces.

Update `comment-tool/SKILL.md`:

- comment has `add`, `list`, and PM-only `resolve`;
- remove "Do not use for resolution workflows";
- state that non-PM buddies add follow-up comments instead of resolving.

- [ ] **Step 5: Role guidance**

Update role contracts and buddy AGENTS to include `request` in env tool lists and explain:

- start with context;
- use `request.list` for incoming/outgoing structured work requests;
- use `request.complete` with artifact/comment result refs;
- PM uses `comment.resolve` after review.

- [ ] **Step 6: Run manifest/profile/skill tests**

Run:

```bash
python3 -m pytest \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Expected after this task: manifest/profile/skill/guidance tests pass.

## Task 8: End-To-End Runtime Flow

**Files:**

- Modify: `tests/test_env_layer_end_to_end.py`

- [ ] **Step 1: Add lean collaboration flow**

Extend or add an e2e test:

1. PM creates a track.
2. PM creates request to Dev referencing PM/design artifact.
3. Dev lists inbox request and accepts it.
4. Dev creates implementation artifact.
5. Dev completes request with `result_refs=[{"type":"artifact","id":"art-dev-r1"}]`.
6. Test or Design adds a comment on the artifact.
7. PM reviews and resolves that comment thread.
8. Test publishes proof through existing `track.add_proof`.
9. PM opens context and sees request done and no open comments for the resolved thread.

- [ ] **Step 2: Assert no unrelated object mutation**

The e2e test must assert:

- message objects are not created by request actions;
- private task ownership is unchanged;
- track material/proof publication still uses existing artifact/track path;
- request state is separate top-level state.

- [ ] **Step 3: Run e2e**

Run:

```bash
python3 -m pytest tests/test_env_layer_end_to_end.py -q
```

Expected after this task: e2e passes.

## Task 9: Broad Verification And Residue Scan

**Files:**

- Modify tests only if failures expose real contract gaps from this task.

- [ ] **Step 1: Focused verification**

Run:

```bash
python3 -m pytest \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  -q
```

- [ ] **Step 2: Integration verification**

Run:

```bash
python3 -m pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_parallel_contracts.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

- [ ] **Step 3: Regression verification**

Run:

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py \
  tests/test_message_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_runless_runtime_contract.py \
  tests/test_clean_runtime_environment.py \
  -q
```

- [ ] **Step 4: Residue scan**

Run:

```bash
rg -n "request-message bridge|compatibility adapter|dual catalog|fallback registry|comment\\.reopen|review object|approval object|handoff" \
  scripts tests buddyswitch framework docs/spec docs/memo README.md
```

Allowed hits:

- historical docs that clearly reject old `handoff`;
- this scope/test/implementation plan;
- tests that assert `handoff` remains absent.

Active runtime implementation must not contain compatibility implementation hits.

## Self-Review Checklist

- `request` is a real object/module and a real env tool, not a message variant.
- `comment.resolve` is PM-only and there is no `comment.reopen`.
- Request visibility, state transitions, and result refs are fully tested.
- Context and projection expose request state without embedding it into unrelated objects.
- Manifest, profiles, skills, and role guidance are aligned with runtime capabilities.
- Existing message and task boundaries remain unchanged.
- No registry per-tool business logic was added.
- No transition path or compatibility bridge was introduced.

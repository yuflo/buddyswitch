# Product Request Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or
> `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Remove the BuddySwitch product-layer collaboration `request` object/tool completely, while
preserving unrelated low-level "request" concepts such as runtime broker requests, HTTP requests,
`search.request`, and `task.switch_request`.

**Architecture:** `message` and `comment` remain the active inbound communication channels.
Track pages remain the shared collaboration state surface. Product-layer `request` is removed as an
object, env tool, skill, context section, permission capability, artifact relation source, and role
contract instruction.

**Tech Stack:** Python env tool runtime, JSON runtime objects, TOML manifest, role env profiles,
pytest/unittest contract tests.

---

Date: 2026-06-08
Status: implementation memo

## 1. Task

Remove the product-layer collaboration request design from BuddySwitch.

In scope:

- Delete the request domain/repo/tool package.
- Delete the shared `request-tool` skill and manifest wiring.
- Remove request object directories from runtime setup.
- Remove request from `ToolContext` rule/repo access.
- Remove request from `context.get` and `context.summarize` output.
- Remove request backlinks/counts from artifact relation summaries.
- Remove request permissions and env profile `request_effects`.
- Remove request guidance from role contracts.
- Update tests and contracts so request is no longer a shipped env tool.

Out of scope:

- Do not remove `search.request`; it is a search action, not a product collaboration request.
- Do not remove `task.switch_request`; it is a private task-switch operation, not a collaboration request object.
- Do not remove runtime broker request, JSON-RPC request, HTTP request, `request_id`, or
  `request-payload` error-boundary naming.
- Do not remove the dev skill `request-dev-code-review`; it means "ask for a code review", not the
  product request object/tool.
- Do not design the future track-level collaboration management model in this task.

## 2. Product Reason

Product-layer request currently carries too many meanings at once:

- inbound channel;
- structured demand object;
- lifecycle manager;
- requester/recipient coordination primitive;
- task-like state;
- track-scoped work cue.

This conflicts with the clearer boundary:

```text
message/comment = actor communication
track = shared collaboration state
task = actor-private execution state
```

Removing request reduces inbound-info ambiguity and prevents actors from needing to decide whether a
need belongs in message, comment, task, or request.

## 3. Scope Boundary

### Remove This Product Request Surface

Primary files:

```text
scripts/env/domain/requests.py
scripts/env/repos/requests.py
scripts/env/tools/request/__init__.py
scripts/env/tools/request/tool.py
scripts/env/tools/request/_impl.py
buddyswitch/skills/shared/request-tool/SKILL.md
tests/test_request_env_tool.py
```

Hard-wired runtime references:

```text
scripts/env/repos/runtime_files.py
scripts/env_legacy_store.py
scripts/env/tool_runtime/context.py
scripts/env/tools/context/_impl.py
scripts/env/tools/context/tool.py
scripts/env/domain/artifact_relations.py
scripts/env/domain/artifact_visibility.py
scripts/env/domain/tasks.py
scripts/env/tools/task/tool.py
scripts/env/tool_runtime/role_auth.py
scripts/env_profiles.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/*.json
framework/contracts/*.md
```

Tests and contract expectations:

```text
tests/test_artifact_env_tool.py
tests/test_black_box_tool_runtime.py
tests/test_buddy_env_profiles.py
tests/test_context_binding_env_tool.py
tests/test_env_layer_end_to_end.py
tests/test_env_manifest_v2.py
tests/test_env_tool_active_task_gate.py
tests/test_env_tool_package_independence.py
tests/test_env_tool_response_contract.py
tests/test_env_tool_router.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_semantic_contract.py
tests/test_host_decision_surface_product_mode.py
tests/test_repo_consistency.py
tests/test_role_action_auth.py
tests/test_runtime_skills.py
tests/test_task_management_skill_architecture.py
```

### Keep These Non-Product Request Surfaces

These are not part of the product collaboration request object:

```text
scripts/runtime_kernel/*
scripts/env/tools/search/*
tests/test_search_env_tool.py
tests/test_runtime_tool_feedback.py
tests/helpers/fake_codex.py
tests/test_app_server_client.py
tests/test_web_management.py
tests/test_task_checkout_handler.py
tests/test_daemon_core_decoupling.py
buddyswitch/skills/dev/request-dev-code-review/SKILL.md
```

Keep terms like:

```text
request_id
request-payload
search.request
task.switch_request
HTTP request
runtime broker request
JSON-RPC request
```

## 4. Expected Final Runtime Shape

`env.tool` shipped tools:

```text
task
track
artifact
context
evidence
search
message
comment
```

Not shipped:

```text
request
```

Runtime object directories created by `ensure_runtime_dirs()`:

```text
buddyswitch/objects/tracks
buddyswitch/objects/artifacts
buddyswitch/objects/artifact-attachments
buddyswitch/objects/messages
buddyswitch/objects/comments
```

Not created:

```text
buddyswitch/objects/requests
```

`context.summarize` should expose:

```text
candidate_tracks
candidate_tasks
candidate_artifacts
open_comment_threads
recent_updates
message_cues
```

It should not expose:

```text
requests
candidate_requests
has_requests
current_context_summary.requests
request_lifecycle_visibility
```

## 5. Implementation Plan

### Task 1: Update Tool Surface Contract Tests First

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_env_tool_package_independence.py`
- Modify: `tests/test_black_box_tool_runtime.py`
- Modify: `tests/test_env_tool_active_task_gate.py`

**Steps:**

- [ ] Remove `"request"` from expected shipped tool sets.
- [ ] Remove request action expectations:

```python
{"create", "list", "get", "accept", "block", "complete", "cancel"}
```

- [ ] Remove `request.list` and `request.get` from free action expectations.
- [ ] Remove `request.create`, `request.accept`, `request.block`, `request.complete`, and
  `request.cancel` from active-task-required expectations.
- [ ] Keep `search.request` in active-task-required expectations.
- [ ] Keep `task.switch_request` in task action expectations.
- [ ] Remove request schema assertions from high-risk schema tests.
- [ ] Remove request package path from package-independence and live-task-surface tests.

**Focused check:**

```bash
pytest \
  tests/test_repo_consistency.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_package_independence.py \
  tests/test_env_tool_active_task_gate.py \
  tests/test_black_box_tool_runtime.py -q
```

Expected at this stage: failures are acceptable if implementation has not yet removed request. They
should point at request still being present.

### Task 2: Delete Product Request Tool, Domain, Repo, Skill, and Dedicated Tests

**Files:**

- Delete: `scripts/env/domain/requests.py`
- Delete: `scripts/env/repos/requests.py`
- Delete: `scripts/env/tools/request/__init__.py`
- Delete: `scripts/env/tools/request/tool.py`
- Delete: `scripts/env/tools/request/_impl.py`
- Delete: `buddyswitch/skills/shared/request-tool/SKILL.md`
- Delete: `tests/test_request_env_tool.py`

**Steps:**

- [ ] Delete the product request files above.
- [ ] Run registry discovery to confirm the package is gone:

```bash
python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
from env.tool_runtime import registry

print(sorted(registry.supported_tools()))
PY
```

Expected: output does not include `request`.

### Task 3: Remove Request Runtime Object Root

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `scripts/env_legacy_store.py`

**Steps:**

- [ ] Remove `REQUESTS_DIR` global declaration and assignment from `runtime_files.py`.
- [ ] Remove `REQUESTS_DIR.mkdir(...)` from `ensure_runtime_dirs()`.
- [ ] Remove `REQUESTS_DIR` rebinding from `env_legacy_store.py`.
- [ ] Do not add a compatibility alias or empty request dir.

**Focused check:**

```bash
python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
from env.repos import runtime_files

print(hasattr(runtime_files, "REQUESTS_DIR"))
PY
```

Expected:

```text
False
```

### Task 4: Remove Request from ToolContext and Runtime Sources

**Files:**

- Modify: `scripts/env/tool_runtime/context.py`

**Steps:**

- [ ] Remove imports:

```python
from env.domain import requests as _request_domain
from env.repos import requests as _request_repo
```

- [ ] Remove `DomainAccess.request`.
- [ ] Remove `RepoAccess.request`.
- [ ] Remove `"requests": "request.list / request.get"` from `RuntimeObjectAccess.runtime_sources()`.
- [ ] Keep `BrowserAccess.request(...)` because it supports `search.request`.
- [ ] Keep `DaemonAccess.request_parent_message_handling(...)` because it is message parent handling.

**Focused check:**

```bash
python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
from env.tool_runtime.context import DomainAccess, RepoAccess, RuntimeObjectAccess

print(hasattr(DomainAccess(), "request"))
print(hasattr(RepoAccess(), "request"))
print(RuntimeObjectAccess().runtime_sources())
PY
```

Expected:

```text
False
False
```

and no `requests` key in the printed runtime sources.

### Task 5: Remove Request from Context Discovery

**Files:**

- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tools/context/tool.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`

**Steps:**

- [ ] Delete `_request_from_actor_role(...)`.
- [ ] Delete `_candidate_request_row(...)`.
- [ ] Delete `_visible_requests(...)`.
- [ ] Remove `visible_requests` calculation from `_current_context_sections(...)`.
- [ ] Remove response fields:

```text
requests
candidate_requests
decision_surface.context_readiness.has_requests
current_context_summary.requests
capability_snapshot.request_lifecycle_visibility
context_sources_desc()["requests"]
```

- [ ] Update `context.tool` descriptions and return lists so they mention tracks/tasks/artifacts,
  not tracks/requests/artifacts.
- [ ] Update context tests to assert request fields are absent, not empty.
- [ ] Keep `open_comment_threads`, `recent_updates`, and `message_cues`.

**Focused check:**

```bash
pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
```

Expected: PASS after tests and implementation agree on no request context section.

### Task 6: Remove Request Artifact Backlinks and Counts

**Files:**

- Modify: `scripts/env/domain/artifact_relations.py`
- Modify: `scripts/env/domain/artifact_visibility.py`
- Modify: `tests/test_artifact_env_tool.py`

**Steps:**

- [ ] Remove request imports from `artifact_relations.py`.
- [ ] Delete `_request_is_visible(...)`.
- [ ] Delete `_request_backlinks(...)`.
- [ ] Remove `target_ref_by_requests` and `result_ref_by_requests` from `incoming_refs`.
- [ ] Remove `target_request_count` and `result_request_count` from `relation_counts_for_artifact(...)`.
- [ ] Remove `target_request_count` and `result_request_count` from `artifact_visibility.artifact_list_row(...)`.
- [ ] Update artifact tests to cover remaining incoming refs:

```text
source_ref_by_artifacts
track_update_refs
comment_ids
```

- [ ] Do not keep zero-valued request count fields.

**Focused check:**

```bash
pytest tests/test_artifact_env_tool.py -q
```

Expected: PASS with no request backlink assertions.

### Task 7: Remove Request from Private Task Ref/Origin Types

**Files:**

- Modify: `scripts/env/domain/tasks.py`
- Modify: `scripts/env/tools/task/tool.py`
- Modify: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_task_env_tool.py` if assertions reference request refs.

**Steps:**

- [ ] Change allowed private task ref id types from:

```python
{"track", "artifact", "message", "comment", "request"}
```

to:

```python
{"track", "artifact", "message", "comment"}
```

- [ ] Remove `"request"` from `_TASK_REF_SCHEMA.properties.type.enum`.
- [ ] Remove `"request"` from `_TASK_ORIGIN_SCHEMA.properties.type.enum`.
- [ ] Remove `"request state"` from `_NO_SIBLING_WRITES`.
- [ ] Update task object model/do-not-use text so it refers to shared track/artifact/message/comment
  state only.
- [ ] Accept that pre-existing private tasks with request refs become invalid if mutated; this is an
  internal stale-state consequence of removing the product object.

**Focused check:**

```bash
pytest tests/test_env_tool_schema_contract.py tests/test_task_env_tool.py -q
```

Expected: PASS with task ref/origin enums excluding `request`.

### Task 8: Remove Request Permissions and Env Profile Capability

**Files:**

- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `scripts/env_profiles.py`
- Modify: `buddyswitch/env-profiles/design.json`
- Modify: `buddyswitch/env-profiles/dev.json`
- Modify: `buddyswitch/env-profiles/market.json`
- Modify: `buddyswitch/env-profiles/pm.json`
- Modify: `buddyswitch/env-profiles/test.json`
- Modify: `tests/test_role_action_auth.py`
- Modify: `tests/test_buddy_env_profiles.py`

**Steps:**

- [ ] Remove permissions:

```text
request.read
request.create
request.accept
request.block
request.complete
request.cancel
```

- [ ] Remove `state_capability.request_effects` validation from `scripts/env_profiles.py`.
- [ ] Remove `request_effects` arrays from all env profile JSON files.
- [ ] Keep JSON key order valid under `role-env-profile` top-level ordering.
- [ ] Update role-action tests so `request.accept` is no longer expected.

**Focused check:**

```bash
python3 scripts/env_profiles.py validate-all
pytest tests/test_role_action_auth.py tests/test_buddy_env_profiles.py -q
```

Expected: env profiles validate and no request permission appears in action summaries.

### Task 9: Remove Request Skill and Role Contract Wiring

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/test.md`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_runtime_skills.py`

**Steps:**

- [ ] Remove the `[[skills]]` block for `request-tool`.
- [ ] Remove `"request-tool"` from every role skill list.
- [ ] Keep `"request-dev-code-review"` in the dev role skill list.
- [ ] Remove request lifecycle instructions from role contracts.
- [ ] Replace role contract handoff language with existing surfaces only:

```text
Use message for direct actor communication.
Use comment for track/artifact discussion.
Use track.update_now / track.add_update / track.add_material / track.add_proof for shared collaboration state.
```

- [ ] Update manifest/runtime skill tests to require message/comment/task/track/artifact skills only.

**Focused check:**

```bash
pytest tests/test_env_manifest_v2.py tests/test_runtime_skills.py -q
```

Expected: PASS with no `request-tool` requirement.

### Task 10: Remove Request Lifecycle E2E and Response Contract Coverage

**Files:**

- Modify: `tests/test_env_layer_end_to_end.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`

**Steps:**

- [ ] Delete `test_request_lifecycle_and_pm_comment_resolution_flow` or split it so only the PM
  comment resolution behavior remains.
- [ ] Remove request write/rejection response contract checks.
- [ ] Remove host decision setup that creates request rows.
- [ ] Keep tests for:

```text
message cues
comment threads
recent track updates
task active gate
track/artifact operations
```

**Focused check:**

```bash
pytest \
  tests/test_env_layer_end_to_end.py \
  tests/test_env_tool_response_contract.py \
  tests/test_host_decision_surface_product_mode.py -q
```

Expected: PASS without product request setup.

### Task 11: Residue Scan

**Files:** all repo files.

**Steps:**

- [ ] Run targeted scan for removed product request surfaces:

```bash
rg -n \
  "request-tool|request\\.list|request\\.get|request\\.create|request\\.accept|request\\.block|request\\.complete|request\\.cancel|candidate_requests|request_effects|REQUESTS_DIR|target_ref_by_requests|result_ref_by_requests|target_request_count|result_request_count" \
  scripts buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles
```

Expected: no hits, except a hit may be acceptable only if it is in this memo.

- [ ] Run broader classification scan:

```bash
rg -n "\\brequest\\b|requests" scripts buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles
```

Expected remaining hits are classified as non-product request usage:

```text
runtime broker request
HTTP request
JSON-RPC request
request_id
request-payload
search.request
task.switch_request
request-dev-code-review
ordinary prose such as "user request"
```

## 6. Full Verification

Run focused verification first:

```bash
pytest \
  tests/test_repo_consistency.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_package_independence.py \
  tests/test_env_tool_active_task_gate.py \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_artifact_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_skills.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_role_action_auth.py \
  tests/test_task_env_tool.py \
  tests/test_task_management_skill_architecture.py -q
```

Run profile validation:

```bash
python3 scripts/env_profiles.py validate-all
```

Run broad verification:

```bash
pytest -q
```

## 7. Acceptance Criteria

- `request` is absent from `registry.supported_tools()`.
- `scripts/env/tools/request/` no longer exists.
- `scripts/env/domain/requests.py` and `scripts/env/repos/requests.py` no longer exist.
- `buddyswitch/skills/shared/request-tool/` no longer exists.
- `buddyswitch/manifest.toml` has no `request-tool` shared skill or role assignment.
- `context.get` and `context.summarize` have no request or candidate request sections.
- Artifact summaries have no request backlink fields or request count fields.
- Task ref/origin schemas no longer allow product request refs.
- Role auth has no `request.*` permissions.
- Env profiles have no `request_effects`.
- Role contracts no longer tell actors to use request lifecycle tools.
- Remaining `request` tokens are classified as non-product request usage.
- Focused verification and full `pytest -q` pass.

## 8. Risks and Decisions

### Stale Runtime Objects

Existing `buddyswitch/objects/requests/*.json` files in old runtime workspaces become stale. This
task should not migrate or reinterpret them. The new runtime should simply stop creating and reading
request objects.

### Stale Private Task Refs

Existing private taskbox tasks may contain refs with `"type": "request"`. After removing request
from task refs, mutating those tasks may reject the stale ref shape. This is acceptable for the
rebuild-forward scope unless a live runtime migration is explicitly requested later.

### Track-Level Collaboration Management

Do not add track-level collaboration management in this task. The request removal should leave a
cleaner surface for a later track-layer design instead of replacing request with a new hidden
workflow.

### Generic Request Wording

Do not run blind search-and-delete on the word `request`. The repo legitimately uses that word for
transport, search, task switching, user input, and dev code-review requests.


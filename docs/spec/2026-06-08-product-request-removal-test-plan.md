# Product Request Removal Test Plan

Date: 2026-06-08
Source:
- `docs/memo/2026-06-08-product-request-removal-task.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`

## Target

Prove that the product-layer collaboration `request` object and env tool are removed from BuddySwitch.
The shipped collaboration surface becomes:

```text
message/comment = actor communication
track = shared collaboration state
task = active actor private execution state
```

The word `request` remains valid for unrelated concepts: `search.request`, `task.switch_request`,
HTTP/JSON-RPC/runtime broker requests, `request_id`, `request-payload`, user request prose, and the
dev skill `request-dev-code-review`.

## Resource Lifecycle Guard

This plan uses env-tool contract tests, repository scans, schema checks, and isolated runtime-root
tests. These checks must not start daemon, app-server, browser, watcher, runtime broker daemon, or
detached worker processes.

Do not run broad launcher/browser/app-server/daemon suites unless their service-starting helpers have
explicit process registration, teardown on assertion failure, pid/process-group termination, cleanup of
pid files/sockets/temporary runtime files, and post-run residual checks as required by
`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

## Functional Requirements

- `request` is not a supported env tool.
- The product request tool package, request domain, request repo, request skill, and dedicated request
  tool tests are deleted.
- Runtime setup no longer creates `buddyswitch/objects/requests`.
- `ToolContext` exposes no request domain/repo access and runtime sources no longer mention
  `request.list` or `request.get`.
- `context.get`, `context.summarize`, and `context.list_sources` expose tracks, tasks, artifacts,
  comments, messages, and updates, with no request/candidate request sections.
- Artifact relation summaries expose no request backlinks or request count fields.
- Task ref and origin schemas no longer accept product request refs.
- Role auth and env profiles contain no `request.*` permissions or `request_effects`.
- Role contracts no longer instruct actors to use request lifecycle tools.
- Manifest/runtime skill wiring no longer ships `request-tool`; `request-dev-code-review` remains.
- Remaining `request` tokens are classified as non-product request usage.

## Expected Shipped Tool Set

```python
{"task", "track", "artifact", "context", "evidence", "search", "message", "comment"}
```

## Expected Action Exceptions

Keep these exact request-named non-product actions:

```text
search.request
task.switch_request
```

Remove these product request actions:

```text
request.create
request.list
request.get
request.accept
request.block
request.complete
request.cancel
```

## Test Files

Update existing tests:

- `tests/test_repo_consistency.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_package_independence.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_tool_active_task_gate.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_host_decision_surface_product_mode.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_skills.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_role_action_auth.py`
- `tests/test_task_env_tool.py`
- `tests/test_task_management_skill_architecture.py`

Delete obsolete dedicated tests:

- `tests/test_request_env_tool.py`

## Test Cases

### Tool Surface Contract

- Assert the supported tool set is exactly the expected shipped set.
- Assert package discovery finds no `scripts/env/tools/request`.
- Assert `tool_catalog.supported_actions("request")` is not used as a valid product surface.
- Assert active-task classification still includes `search.request` and excludes every
  `request.*` action.
- Assert router and black-box invalid-tool behavior treats `request` like any unsupported tool.

### Runtime Object Root

- In a temporary runtime root, call `ensure_runtime_dirs()`.
- Assert these object directories exist:

```text
buddyswitch/objects/tracks
buddyswitch/objects/artifacts
buddyswitch/objects/artifact-attachments
buddyswitch/objects/messages
buddyswitch/objects/comments
```

- Assert this object directory does not exist:

```text
buddyswitch/objects/requests
```

- Assert `env.repos.runtime_files` has no `REQUESTS_DIR` attribute.

### ToolContext Contract

- Instantiate `DomainAccess` and `RepoAccess`; assert neither has a `request` attribute.
- Assert `RuntimeObjectAccess().runtime_sources()` has no `requests` key.
- Assert `BrowserAccess.request(...)` and daemon parent-message request helpers remain available
  because they are unrelated to product request objects.

### Context Output

- Seed tracks, active private taskbox tasks, artifacts, comments, messages, and recent track updates.
- Call `context.summarize`; assert it exposes:

```text
candidate_tracks
candidate_tasks
candidate_artifacts
open_comment_threads
recent_updates
message_cues
```

- Assert it does not expose:

```text
requests
candidate_requests
decision_surface.context_readiness.has_requests
current_context_summary.requests
capability_snapshot.request_lifecycle_visibility
```

- Call `context.get`; assert full context omits `requests`.
- Call `context.list_sources`; assert no source key describes request lifecycle rows or
  `request.list` / `request.get`.

### Artifact Relations

- Seed artifacts that are referenced by artifacts, track updates, and comments.
- Call artifact list/get flows and assert remaining relation fields are present.
- Assert these removed fields are absent, not zero-valued:

```text
incoming_refs.target_ref_by_requests
incoming_refs.result_ref_by_requests
relation_counts.target_request_count
relation_counts.result_request_count
target_request_count
result_request_count
```

### Task Schemas

- Assert task ref type enum is:

```python
["track", "artifact", "message", "comment"]
```

- Assert task origin type enum is:

```python
["manual", "user_input", "track", "artifact", "message", "comment"]
```

- Assert task catalog text no longer says task refs can reference or mutate product request state.
- Keep `task.switch_request` action and its active-task semantics.

### Role Auth And Env Profiles

- Assert no role action summary includes:

```text
request.read
request.create
request.accept
request.block
request.complete
request.cancel
```

- Validate every env profile.
- Assert no profile has `state_capability.request_effects`.

### Manifest, Skills, And Role Contracts

- Assert `buddyswitch/manifest.toml` has no `request-tool` shared skill block or role skill assignment.
- Assert runtime skill installation requires track/artifact/task/message/comment skills and does not
  require `request-tool`.
- Assert the dev role may still ship `request-dev-code-review`.
- Assert role contracts do not mention `request.list`, `request.get`, `request.create`,
  `request.accept`, `request.block`, `request.complete`, or `request.cancel`.
- Assert replacement instructions use message, comment, and track update surfaces.

### E2E And Response Contracts

- Remove request lifecycle E2E coverage.
- Keep PM comment resolution, message cues, track/artifact, and active-task gate coverage.
- Remove response-contract assertions for request lifecycle write/rejection success shapes.
- Keep `request-payload` response-contract tests for unrelated payload validation boundaries.

### Residue Classification

Run a narrow removed-surface scan:

```bash
rg -n "request-tool|request\\.list|request\\.get|request\\.create|request\\.accept|request\\.block|request\\.complete|request\\.cancel|candidate_requests|request_effects|REQUESTS_DIR|target_ref_by_requests|result_ref_by_requests|target_request_count|result_request_count" scripts/env scripts/env_profiles.py buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles -g '!tests/helpers/fake_codex.py'
```

Expected: no hits.

Run a broader classification scan:

```bash
rg -n "\\brequest\\b|requests" scripts buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles
```

Expected remaining hits are one of:

```text
runtime broker request
HTTP request
JSON-RPC request
request_id
request-payload
search.request
task.switch_request
request-dev-code-review
ordinary prose such as user request
```

## Verification Commands

Focused contract and behavior loop:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
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
  tests/test_task_management_skill_architecture.py \
  -q
```

Profile validation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/env_profiles.py validate-all
```

Compile touched Python modules:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile \
  scripts/env_legacy_store.py \
  scripts/env/repos/runtime_files.py \
  scripts/env/tool_runtime/context.py \
  scripts/env/tool_runtime/role_auth.py \
  scripts/env/tools/context/tool.py \
  scripts/env/tools/context/_impl.py \
  scripts/env/domain/artifact_relations.py \
  scripts/env/domain/artifact_visibility.py \
  scripts/env/domain/tasks.py \
  scripts/env/tools/task/tool.py \
  scripts/env_profiles.py
```

Broad suite after focused checks are green:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

## Acceptance

The test plan passes only when request is absent from the shipped product env-tool/runtime/skill
surface, all removed-surface scans are clean, all remaining request-named usages are classified as
non-product request concepts, profile validation passes, and focused plus broad verification pass
without resource lifecycle residue.

## Plan Review

- Requirement coverage: every memo scope item maps to a test case above.
- Anti-cheat check: tests assert product-visible behavior, schemas, contracts, docs, and residue
  scans instead of only checking implementation details.
- Forward principle: no compatibility alias, empty request directory, request tombstone tool, or hidden
  fallback remains.
- Resource safety: default verification avoids daemon/app-server/browser process creation.

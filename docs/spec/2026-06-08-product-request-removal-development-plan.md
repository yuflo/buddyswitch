# Product Request Removal Development Plan

Date: 2026-06-08
Source:
- `docs/spec/2026-06-08-product-request-removal-test-plan.md`
- `docs/memo/2026-06-08-product-request-removal-task.md`

## Goal

Remove the product-layer collaboration request object/tool completely while preserving unrelated
request-named runtime, transport, search, task-switch, and code-review concepts.

## Non-Negotiables

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/fea-daemon`.
- Do not edit `buddyswitch/objects/**` or old private runtime state directly.
- Use tests first; update focused behavior/contract tests and verify they fail while request is still
  present before removing implementation.
- Do not keep compatibility wrappers, tombstone tools, request aliases, or an empty request object root.
- Do not remove `search.request`, `task.switch_request`, HTTP/JSON-RPC/runtime broker request naming,
  `request_id`, `request-payload`, or `request-dev-code-review`.
- Keep verification focused until the contract suite is green; avoid broad service-starting suites
  unless lifecycle cleanup is proven.

## File Responsibilities

- `scripts/env/tools/request/*`: obsolete product request env tool package; delete.
- `scripts/env/domain/requests.py`: obsolete request validation/lifecycle domain; delete.
- `scripts/env/repos/requests.py`: obsolete request object repo; delete.
- `buddyswitch/skills/shared/request-tool/SKILL.md`: obsolete actor skill; delete.
- `tests/test_request_env_tool.py`: obsolete dedicated request lifecycle tests; delete.
- `scripts/env/repos/runtime_files.py` and `scripts/env_legacy_store.py`: remove request object root.
- `scripts/env/tool_runtime/context.py`: remove request domain/repo/runtime source access.
- `scripts/env/tools/context/_impl.py` and `scripts/env/tools/context/tool.py`: remove request sections
  from context outputs and descriptions.
- `scripts/env/domain/artifact_relations.py` and `scripts/env/domain/artifact_visibility.py`: remove
  request backlinks/counts.
- `scripts/env/domain/tasks.py` and `scripts/env/tools/task/tool.py`: remove request ref/origin schemas
  and prose while keeping `task.switch_request`.
- `scripts/env/tool_runtime/role_auth.py`, `scripts/env_profiles.py`, and `buddyswitch/env-profiles/*.json`:
  remove request permissions and `request_effects`.
- `buddyswitch/manifest.toml` and `framework/contracts/*.md`: remove request skill and role instructions.
- Tests listed in the test plan: update expected shipped surface and removed fields.

## Implementation Sequence

### Task 1: Add Failing Tool Surface Tests

Modify:

- `tests/test_repo_consistency.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_env_tool_router.py`
- `tests/test_env_tool_package_independence.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_tool_active_task_gate.py`

Steps:

- Remove `"request"` from expected shipped tool sets.
- Remove request action expectations.
- Remove `request.list` and `request.get` from free action expectations.
- Remove `request.create`, `request.accept`, `request.block`, `request.complete`, and
  `request.cancel` from active-task-required expectations.
- Keep `search.request` in active-task-required expectations.
- Keep `task.switch_request` in task action expectations.
- Remove request schema assertions.
- Remove request package path assertions.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_package_independence.py \
  tests/test_env_tool_active_task_gate.py \
  tests/test_black_box_tool_runtime.py \
  -q
```

Expected before implementation: failures showing request is still present or expected implementation
has not yet been removed.

### Task 2: Delete Product Request Package, Domain, Repo, Skill, And Dedicated Tests

Delete:

- `scripts/env/domain/requests.py`
- `scripts/env/repos/requests.py`
- `scripts/env/tools/request/__init__.py`
- `scripts/env/tools/request/tool.py`
- `scripts/env/tools/request/_impl.py`
- `buddyswitch/skills/shared/request-tool/SKILL.md`
- `tests/test_request_env_tool.py`

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
from env.tool_runtime import registry

print(sorted(registry.supported_tools()))
PY
```

Expected: output does not include `request`.

### Task 3: Remove Runtime Object Root

Modify:

- `scripts/env/repos/runtime_files.py`
- `scripts/env_legacy_store.py`

Steps:

- Remove `REQUESTS_DIR` declaration, assignment, and `mkdir`.
- Remove legacy store rebinding for `REQUESTS_DIR`.
- Do not create a compatibility directory.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
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

### Task 4: Remove Request From ToolContext

Modify:

- `scripts/env/tool_runtime/context.py`

Steps:

- Remove request domain/repo imports.
- Remove `DomainAccess.request`.
- Remove `RepoAccess.request`.
- Remove `"requests": "request.list / request.get"` from runtime sources.
- Keep browser and daemon methods whose names use request for unrelated transport/search purposes.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
from env.tool_runtime.context import DomainAccess, RepoAccess, RuntimeObjectAccess

print(hasattr(DomainAccess(), "request"))
print(hasattr(RepoAccess(), "request"))
print("requests" in RuntimeObjectAccess().runtime_sources())
PY
```

Expected:

```text
False
False
False
```

### Task 5: Remove Request From Context Discovery

Modify:

- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/context/tool.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_host_decision_surface_product_mode.py`

Steps:

- Delete request row helpers and visible request discovery.
- Remove `requests`, `candidate_requests`, `has_requests`, current summary request counts,
  capability snapshot request lifecycle visibility, and request source descriptions.
- Update descriptions to mention tracks, active tasks, artifacts, comments, messages, and updates.
- Update tests to assert removed request fields are absent.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  -q
```

Expected after implementation: pass.

### Task 6: Remove Request Artifact Backlinks And Counts

Modify:

- `scripts/env/domain/artifact_relations.py`
- `scripts/env/domain/artifact_visibility.py`
- `tests/test_artifact_env_tool.py`

Steps:

- Remove request imports and request backlink helpers.
- Remove `target_ref_by_requests` and `result_ref_by_requests`.
- Remove `target_request_count` and `result_request_count`.
- Update tests to assert remaining artifact/track/comment refs and absence of request fields.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_artifact_env_tool.py -q
```

Expected after implementation: pass.

### Task 7: Remove Request Task Ref And Origin Types

Modify:

- `scripts/env/domain/tasks.py`
- `scripts/env/tools/task/tool.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_task_env_tool.py`

Steps:

- Change allowed private task ref id types to `{"track", "artifact", "message", "comment"}`.
- Remove request from task ref and origin schema enums.
- Remove request state from task no-sibling-writes text.
- Update task prose so private tasks do not publish or mutate track/artifact/message/comment state.
- Keep `task.switch_request`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_schema_contract.py \
  tests/test_task_env_tool.py \
  -q
```

Expected after implementation: pass.

### Task 8: Remove Request Permissions And Env Profile Capability

Modify:

- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env_profiles.py`
- `buddyswitch/env-profiles/design.json`
- `buddyswitch/env-profiles/dev.json`
- `buddyswitch/env-profiles/market.json`
- `buddyswitch/env-profiles/pm.json`
- `buddyswitch/env-profiles/test.json`
- `tests/test_role_action_auth.py`
- `tests/test_buddy_env_profiles.py`

Steps:

- Remove all `request.*` permissions.
- Remove validation for `state_capability.request_effects`.
- Remove `request_effects` arrays from profile JSON.
- Update role-action tests so no request action is expected.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/env_profiles.py validate-all
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_role_action_auth.py \
  tests/test_buddy_env_profiles.py \
  -q
```

Expected after implementation: pass.

### Task 9: Remove Request Skill And Role Contract Wiring

Modify:

- `buddyswitch/manifest.toml`
- `framework/contracts/design.md`
- `framework/contracts/dev.md`
- `framework/contracts/market.md`
- `framework/contracts/pm.md`
- `framework/contracts/test.md`
- `tests/test_env_manifest_v2.py`
- `tests/test_runtime_skills.py`

Steps:

- Remove the `request-tool` skill block.
- Remove `request-tool` from every role skill list.
- Keep `request-dev-code-review` in the dev role skill list.
- Remove request lifecycle guidance from role contracts.
- Replace handoff guidance with message, comment, and track update surfaces.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_manifest_v2.py \
  tests/test_runtime_skills.py \
  -q
```

Expected after implementation: pass.

### Task 10: Remove Request Lifecycle E2E And Response Contract Coverage

Modify:

- `tests/test_env_layer_end_to_end.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_host_decision_surface_product_mode.py`

Steps:

- Delete or split request lifecycle E2E tests so unrelated PM comment resolution remains covered.
- Remove request write/rejection response contract checks.
- Remove host decision setup that creates product request rows.
- Keep tests for messages, comments, recent updates, active-task gate, and track/artifact operations.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_layer_end_to_end.py \
  tests/test_env_tool_response_contract.py \
  tests/test_host_decision_surface_product_mode.py \
  -q
```

Expected after implementation: pass.

### Task 11: Residue Scan And Full Verification

Run removed-surface scan:

```bash
rg -n "request-tool|request\\.list|request\\.get|request\\.create|request\\.accept|request\\.block|request\\.complete|request\\.cancel|candidate_requests|request_effects|REQUESTS_DIR|target_ref_by_requests|result_ref_by_requests|target_request_count|result_request_count" scripts/env scripts/env_profiles.py buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles -g '!tests/helpers/fake_codex.py'
```

Expected: no hits.

Run classification scan:

```bash
rg -n "\\brequest\\b|requests" scripts buddyswitch framework tests README.md AGENTS.md tools/launcher/assets/roles
```

Expected: remaining hits are classified as non-product request usage.

Run full focused verification, profile validation, compile check, and broad pytest from the test plan.

## Acceptance

Implementation is complete only when every task above is implemented, removed-surface scans are clean,
remaining request tokens are classified as non-product request concepts, profile validation passes,
focused verification passes, broad pytest passes, and the final review checklist has no gaps.

## Plan Review

- Requirement coverage: all memo scope items and test-plan functional requirements are represented.
- Scope check: one direct removal path; no compatibility layer or replacement workflow is introduced.
- Ambiguity resolved: stale runtime request JSON and stale private task refs are accepted as internal
  obsolete state; no migration is added in this task.
- Type consistency: `search.request` and `task.switch_request` remain action names; product `request.*`
  disappears from the shipped tool catalog.

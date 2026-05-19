# Tool Independence Repair Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` when implementing runtime changes from this plan. Each behavior change starts with a failing test that is verified red before production code is edited.

**Goal:** Prove env.tool runtime independence by verifying Python 3.9-compatible imports, service-light routing, selected-tool-only loading, contract/service payload alignment, and preservation of existing tool behavior.

**Architecture:** Tests describe externally observable tool behavior and explicit architecture boundaries. Behavior tests use broker/router dispatch through temporary runtime workspaces. Boundary tests may inspect imports and registry projections because import isolation and single-source payload contracts are product architecture requirements.

**Tech Stack:** Python `unittest`/`pytest`, `RuntimeWorkspaceTestMixin`, broker-routed `runtime_broker.dispatch_runtime_request`, direct `env.tools.router.dispatch_env_tool_request` for focused routing tests, subprocess checks under default `python3`, AST/import-boundary checks, and existing env.tool suites.

---

## Test Rules

- Write each new failing test before changing production code.
- Verify every new test fails for the expected reason before implementation.
- Tests must be derived from the tool independence requirements in this document, not from private implementation details that would let broken behavior pass.
- It is valid to assert service-light imports because "one tool cannot break all tools at import time" is a required architecture boundary.
- It is valid to simulate an unrelated service import failure because that models the failure class observed in the memo.
- Do not monkeypatch the code under test to force a pass.
- Do not weaken existing tool behavior assertions to make dispatch changes easier.
- Do not use docs as functional assertions.
- Positive behavior tests must assert response shape and relevant persisted state.
- Negative behavior tests must assert rejection code or permission boundary, `state_changed=False`, and no unintended mutation.
- Run focused tests first, then broader suites.

## Requirements Model

R1. Default `python3` imports the public env.tool contract, router, and dispatch modules successfully.

R2. Public catalog/router import paths are service-light. Importing `env.tools.contracts`, `env.tools.router`, or `env.tools.dispatch` does not import `env.services.*`.

R3. Healthy selected tools do not depend on unrelated service imports. If `env.services.messages` cannot import, `task.list` still succeeds.

R4. Selected-tool service load failures are localized. If `message.list` is selected and `env.services.messages` cannot import, the response is structured env.tool feedback, not a process crash, and no state changes.

R5. Dispatch coverage, router actions, runtime status catalog, and CLI operations match `contracts.TOOL_REGISTRY`.

R6. For each tool/action, accepted request fields match the registry payload fields. Hidden service-only fields are not accepted.

R7. `task.create` rejects `buddy` and `active_buddy`; the only task owner source is runtime `active_buddy`.

R8. `track.update_now` and `track.add_update` reject `owner_buddy`; track owner remains immutable and cannot be patched through action payloads.

R9. `comment.add` registry fields include `target_type`, `target_id`, `content`, `reply_to`, `artifact_revision_id`, `anchor`, and `mentions` because these have active behavior. `comment.list` registry and CLI include `status`.

R10. Existing main-path behavior for task, track, artifact, buddybox, context, evidence, message, comment, and search remains green after the dispatch and contract cleanup.

R11. Runtime skill/catalog consistency checks remain green so skills continue to discover exact fields from runtime catalog instead of copied schema tables.

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| TI1 | R1 | `tests/test_env_tool_router.py` | Default `python3` imports env.tool modules | subprocess exits 0 for contracts/router/dispatch import |
| TI2 | R2 | `tests/test_env_tool_router.py` | Tool modules import without services | subprocess imports contracts/router/dispatch and reports no `env.services.*` modules |
| TI3 | R3 | `tests/test_env_tool_router.py` | Block message service import, dispatch `task.list` | response `ok=true`, `tool=task`, no message import required |
| TI4 | R4 | `tests/test_env_tool_router.py` | Block message service import, dispatch `message.list` | response `ok=false`, structured dispatch error, `state_changed=false` |
| TI5 | R5 | `tests/test_env_tool_router.py` | Registry/action coverage | dispatch/router/status/CLI actions equal registry |
| PC1 | R6 | `tests/test_env_tool_payload_contract.py` | Registry exposes payload fields for every action | `contracts.env_tools_description()` payload fields equal action specs |
| PC2 | R6 | `tests/test_env_tool_payload_contract.py` | Every action rejects an unregistered payload field | `ok=false`, field named in feedback, `state_changed=false` |
| PC3 | R6 | `tests/test_env_tool_payload_contract.py` | Services and message domain do not keep duplicate payload allowlists | no service-level `_FIELDS` payload constants remain; message domain send/list field sets are removed |
| PC4 | R6/R7 | `tests/test_task_env_tool.py` | `task.create` rejects `buddy` | no task file created, request-payload rejection |
| PC5 | R6/R7 | `tests/test_task_env_tool.py` | `task.create` rejects `active_buddy` | no task file created, request-payload rejection |
| PC6 | R6/R8 | `tests/test_track_env_tool.py` | `track.update_now` rejects `owner_buddy` | no now/state/update row mutation |
| PC7 | R6/R8 | `tests/test_track_env_tool.py` | `track.add_update` rejects `owner_buddy` | no update row appended |
| PC8 | R9 | `tests/test_env_tool_semantic_contract.py` | Comment registry fields match real capability | comment payload fields include anchor/revision/mentions/status |
| PC9 | R9 | `tests/test_comment_env_tool.py` | Comment advanced fields still work | artifact section anchor, revision chain, mentions, and status filter pass |
| CLI1 | R9 | `tests/test_env_tool_router.py` | Comment CLI exposes status list filter | `comment list --help` includes `--status`; CLI operation map remains aligned |
| REG1 | R10 | Existing focused suites | All active env.tool suites | behavior remains green under `python3` |
| REG2 | R11 | Consistency suites | Runtime catalog and skill boundary | skill/schema-copy and repo consistency tests pass |

## Detailed Test Design

### TI1: Default Python3 Imports Env.Tool Modules

**File:** `tests/test_env_tool_router.py`

**Setup:** No runtime state required. Run a subprocess so the import state is clean and uses default `python3`.

**Operation:**

```bash
python3 - <<'PY'
import sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / "scripts"))
import env.tools.contracts
import env.tools.router
import env.tools.dispatch
print("ok")
PY
```

**Assertions:**

- Return code is 0.
- stdout contains `ok`.
- stderr is empty.

**Focused command:**

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_python3_imports_env_tool_modules -q
```

Expected before implementation: fails with the current `GetMessage` Python 3.9 type-alias error.

### TI2: Tool Module Imports Are Service-Light

**File:** `tests/test_env_tool_router.py`

**Setup:** Clean subprocess under default `python3`.

**Operation:** Import `env.tools.contracts`, `env.tools.router`, and `env.tools.dispatch`; then print loaded service modules.

**Assertions:**

- Return code is 0.
- Loaded module list for `name.startswith("env.services.")` is `[]`.
- The assertion must not scan docs or source text. It checks actual import behavior.

**Focused command:**

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_env_tool_imports_do_not_load_services -q
```

Expected before implementation: fails because `dispatch.py` eagerly imports service modules.

### TI3: Unrelated Service Failure Does Not Block Healthy Tool

**File:** `tests/test_env_tool_router.py`

**Setup:**

- Use `RuntimeWorkspaceTestMixin`.
- Create an active `dev` instance JSON.
- Use a clean subprocess so a meta-path import guard can block only `env.services.messages`.

**Operation:** In the subprocess:

1. Insert `scripts` into `sys.path`.
2. Install a meta-path finder that raises `RuntimeError("blocked message service import")` for `env.services.messages`.
3. Import `env.tools.router`.
4. Dispatch payload `{"tool": "task", "action": "list", "args": {}}`.
5. Print JSON response.

**Assertions:**

- Return code is 0.
- Response has `ok=true`.
- Response has `tool="task"` and `action="task.list"`.
- Response has `state_changed=false`.
- stderr does not contain `blocked message service import`.

**Focused command:**

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_unrelated_service_import_failure_does_not_block_task_tool -q
```

Expected before implementation: fails because router/dispatch import path tries to import message service.

### TI4: Selected Service Failure Is Structured Feedback

**File:** `tests/test_env_tool_router.py`

**Setup:** Same blocked-message subprocess pattern as TI3.

**Operation:** Dispatch payload `{"tool": "message", "action": "list", "args": {}}`.

**Assertions:**

- Return code is 0.
- Response has `ok=false`.
- Response has `tool="message"` and `action="message.list"`.
- Error code is `E_ENV_TOOL_DISPATCH`.
- `permission_boundary` is `env.tool.dispatch`.
- `state_changed=false`.
- `retryable=false`.
- `why_blocked` includes `blocked message service import`.

**Focused command:**

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_selected_service_import_failure_returns_structured_feedback -q
```

Expected before implementation: fails by process error or import-time crash.

### PC1-PC2: Payload Contract Is Single-Source

**File:** `tests/test_env_tool_payload_contract.py`

**Setup:** Import `env.tools.contracts` under default `python3`.

**Operation:**

- Build expected action field maps from `contracts.TOOL_REGISTRY`.
- Compare `contracts.env_tools_description()[tool]["payload_fields"][action]` to registry fields.
- Compare `contracts.payload_fields_for_action(tool, action)` to registry fields.
- For every registered action, dispatch one request with `args={"__unexpected_payload_field__": true}`.
- Scan `scripts/env/services/*.py` for service-level duplicate payload field constants ending in `_FIELDS`; none may remain except explicitly non-payload constants listed in the test.
- Scan `scripts/env/domain/messages.py` for `_SEND_FIELDS` and `_LIST_FIELDS`; neither may remain.

**Assertions:**

- Every registered action has exactly one payload field list.
- No service keeps a second payload field source that can accept fields absent from registry.
- No registry action is missing from service validation.
- Field order in runtime catalog matches registry order.
- Each registered action rejects the unexpected payload field before mutating runtime state.

**Focused command:**

```bash
python3 -m pytest tests/test_env_tool_payload_contract.py -q
```

Expected before implementation: fails for task, track, and comment drift.

### PC3-PC4: Task Create Rejects Ignored Owner Fields

**File:** `tests/test_task_env_tool.py`

**Setup:** Create a `dev` instance JSON and snapshot `buddyswitch/objects/tasks`.

**Operations:**

- Dispatch `task.create` with `buddy="design"`.
- Dispatch `task.create` with `active_buddy="pm"`.

**Assertions for each case:**

- Response has `ok=false`.
- Error code is `E_TASK_PAYLOAD`.
- `permission_boundary="request-payload"`.
- `state_changed=false`.
- `correctable_fields` contains the rejected field.
- Task snapshot is unchanged.
- No task file with the requested id exists.

**Focused commands:**

```bash
python3 -m pytest tests/test_task_env_tool.py::TaskEnvToolTests::test_task_create_rejects_buddy_field_without_state_mutation -q
python3 -m pytest tests/test_task_env_tool.py::TaskEnvToolTests::test_task_create_rejects_active_buddy_field_without_state_mutation -q
```

Expected before implementation: fails because the request succeeds and stores the task under runtime active buddy.

### PC5-PC6: Track Owner Field Is Not Patchable Payload

**File:** `tests/test_track_env_tool.py`

**Setup:** Create a PM-owned active track, snapshot its JSON.

**Operations:**

- Dispatch `track.update_now` with `owner_buddy="design"` plus a valid `now`.
- Dispatch `track.add_update` with `owner_buddy="design"` plus a valid summary.

**Assertions for each case:**

- Response has `ok=false`.
- Error code is `E_TRACK_PAYLOAD`.
- `permission_boundary="request-payload"`.
- `state_changed=false`.
- `why_blocked` contains `unsupported payload fields: owner_buddy`.
- Track JSON is unchanged, including `owner_buddy`, `now`, and update rows.

**Focused commands:**

```bash
python3 -m pytest tests/test_track_env_tool.py::TrackEnvToolTests::test_update_now_rejects_owner_buddy_without_state_mutation -q
python3 -m pytest tests/test_track_env_tool.py::TrackEnvToolTests::test_add_update_rejects_owner_buddy_without_state_mutation -q
```

Expected before implementation: fails because the service currently accepts `owner_buddy` before returning a special immutable-field rejection.

### PC7-PC8: Comment Registry Matches Real Comment Capability

**Files:**

- `tests/test_env_tool_semantic_contract.py`
- `tests/test_comment_env_tool.py`
- `tests/test_env_tool_router.py`

**Setup:** Use existing comment fixtures for readable tracks and artifacts.

**Operations and assertions:**

- Registry payload fields for `comment.add` equal `["target_type", "target_id", "content", "reply_to", "artifact_revision_id", "anchor", "mentions"]`.
- Registry payload fields for `comment.list` equal `["target_type", "target_id", "status"]`.
- `context.get.tool_catalog["comment"].payload_fields` exposes the same lists.
- `comment list --help` includes optional `--status`.
- Existing comment behavior for artifact section anchors, revision-chain checks, mentions, and `status="all"` stays green.

**Focused commands:**

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_comment_payload_fields_match_active_comment_capability -q
python3 -m pytest tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_cli_operation_maps_align_with_registry_actions -q
```

Expected before implementation: registry assertions fail because active fields are hidden from the catalog.

## Regression Verification

Run these focused suites after all new tests pass:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
python3 -m pytest tests/test_task_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_evidence_env_tool.py tests/test_search_env_tool.py -q
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_runtime_broker.py -q
python3 -m pytest tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_runtime_skills.py -q
```

Run this broader verification before claiming completion:

```bash
python3 -m pytest -q
git diff --check
```

If the full suite is too slow or blocked by unrelated failures, record the blocker and run all listed focused suites plus the affected neighboring suites.

# All-Buddy Runtime Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the packet-era `resolve -> prepare-execution -> persist` runtime with the converged all-buddy `resolve_context -> host skill turn -> persist_skill_result -> refreshed_context` contract, including `design` and market browser-native guarantees.

**Architecture:** Land this as one branch-level cutover, not a long-lived compatibility bridge. Keep the runtime centered in `scripts/switch_runtime.py` and `scripts/runtime_kernel/*`, freeze the new public surfaces in contract tests, let `resolve` materialize the task context plus reserved run envelope, and let `persist-skill-result` be the only canonical write boundary. Keep `market` fail-closed through normalized `host_execution/tool_scope`, and make `design` a real skill package instead of a manifest exception.

**Tech Stack:** Python runtime (`scripts/switch_runtime.py`, `scripts/env_store.py`, `scripts/runtime_kernel/*`), TOML skill packages, JSON schemas/contracts, Markdown docs, `pytest` regression/contract tests, launcher runtime instructions.

## Execution Status

- Identity: BuddySwitch source-checkout Codex agent following repo-root `AGENTS.md`; this work is for source development, not the launcher-managed runtime worktree.
- Canonical execution branch/worktree: `pm-agentic-refactor` at `.worktrees/pm-agentic-refactor`.
- Current state as of 2026-04-22: the Task 1-8 cutover is implemented in this worktree, and the final code-quality review gate passed after trust-boundary and doc-consistency fixes.
- Verification evidence:
  - `python3 -m pytest tests/test_switch_runtime.py -q` -> `68 passed, 15 subtests passed`
  - `python3 -m pytest tests/test_repo_consistency.py -q` -> `55 passed, 123 subtests passed`
  - `python3 -m pytest tests/test_env_manifest_v2.py tests/test_env_store_v2.py tests/test_switch_runtime.py tests/test_switch_integration.py tests/test_parallel_contracts.py tests/test_repo_consistency.py -q` -> `159 passed, 138 subtests passed`
- Tracking note: the checkbox steps below remain the original execution outline and were not maintained live during implementation. Treat this status block plus branch history as the authoritative progress record. The per-task commit steps were superseded by the final branch-level migration/closeout in `pm-agentic-refactor`.

---

## Scope Guard

This refactor touches runtime code, schemas, skill packages, launcher instructions, and contract tests, but those are one coupled public ABI change. Do not split this into separate implementation plans. A half-cutover leaves the repo in a broken state where docs, runtime, and tests disagree about whether the host should use `selected_skill_packet` or `resolve_context`.

## File Structure

- Create `framework/contracts/resolve-context.json`
  - Freeze the machine-readable `resolve_context` response contract.
- Create `framework/contracts/persist-skill-result.json`
  - Freeze the machine-readable persist response contract (`receipt` + `refreshed_context`).
- Delete `framework/contracts/selected-skill-packet.json`
  - Remove the packet-era contract file once the new contract tests are green.
- Create `framework/schemas/design/shape-prototype.json`
  - Define the concrete `design` artifact schema.
- Create `buddyswitch/skills/design/shape-prototype/skill.toml`
  - Register the new design skill metadata.
- Create `buddyswitch/skills/design/shape-prototype/SKILL.md`
  - Define the host-executed design skill instructions.
- Create `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`
  - Give the design skill a repo-native template asset consistent with other artifact-producing skills.
- Modify `buddyswitch/manifest.toml`
  - Register `shape-prototype` and remove `design` as a zero-skill buddy.
- Modify `scripts/env_manifest.py`
  - Keep loading `host_execution` / `tool_scope` into the normalized runtime metadata surface and accept the new design package.
- Modify `scripts/env_store.py`
  - Allow resolve-time task materialization with no persisted runs yet, while preserving artifact/track invariants.
- Modify `scripts/switch_runtime.py`
  - Replace packet-era resolve/prepare/persist flow with `resolve_context` and `persist_skill_result`.
- Modify `scripts/runtime_kernel/__init__.py`
  - Export only the new resolve/persist entrypoints.
- Modify `scripts/runtime_kernel/resolve.py`
  - Delegate to the new resolve implementation.
- Modify `scripts/runtime_kernel/persist.py`
  - Delegate to the new `persist_skill_result` implementation.
- Delete `scripts/runtime_kernel/prepare_execution.py`
  - Remove the runtime-kernel wrapper for the deleted packet step.
- Modify `framework/schemas/pm/track-manager.json`
  - Narrow online actions to `create`, `update`, `advance`, `archive`.
- Modify `framework/docs/switch-spec.md`
  - Rewrite the public runtime model, host duties, and CLI examples around `resolve_context` and `persist-skill-result`.
- Modify `framework/docs/browser-cockpit.md`
  - Move the market browser-native contract from packet fields to `skills[*].host_execution` / `tool_scope`.
- Modify `framework/contracts/market.md`
  - Keep market browser-native guarantees without referencing packet-era fields.
- Modify `framework/docs/track-registry.md`
  - Document resolve-time task creation and the new run lifecycle constraints.
- Modify `tools/launcher/assets/runtime-AGENTS.md`
  - Update runtime instructions for launcher-managed sessions.
- Modify `README.md`
  - Rewrite the runtime flow and CLI examples.
- Modify `.codex/agents/router.toml`
  - Replace `prepare-execution` guidance with the new loop.
- Modify `tests/test_parallel_contracts.py`
  - Freeze `resolve_context` and `persist_skill_result` instead of `selected_skill_packet`.
- Modify `tests/test_switch_runtime.py`
  - Cover resolve response shape, deleted packet path, new persist API, trust boundary, market host contract, track-manager narrowing, and design buddy behavior.
- Modify `tests/test_switch_integration.py`
  - Cover end-to-end `resolve_context -> persist_skill_result -> refreshed_context`.
- Modify `tests/test_env_store_v2.py`
  - Cover task creation without persisted runs and preserved artifact lineage invariants.
- Modify `tests/test_env_manifest_v2.py`
  - Cover the new design skill package and current market metadata normalization.
- Modify `tests/test_repo_consistency.py`
  - Remove packet-era wording checks and add new active-doc/runtime-surface checks.
- Create `docs/dev0154/2026-04-22-all-buddy-runtime-cutover-manual-checklist.md`
  - Add a short manual verification checklist for the first real runtime pass after code lands.

## Task 1: Freeze The New Public Contract Surface

**Files:**
- Create: `framework/contracts/resolve-context.json`
- Create: `framework/contracts/persist-skill-result.json`
- Delete: `framework/contracts/selected-skill-packet.json`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Write failing contract tests for `resolve_context` and `persist_skill_result`**

```python
# tests/test_parallel_contracts.py
RESOLVE_CONTEXT_CONTRACT = CONTRACTS_DIR / "resolve-context.json"
PERSIST_SKILL_RESULT_CONTRACT = CONTRACTS_DIR / "persist-skill-result.json"

def test_contract_matches_real_resolve_context(self) -> None:
    contract = _load_json(RESOLVE_CONTEXT_CONTRACT)
    payload = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")

    self.assertTrue(payload["ok"])
    self.assertEqual(list(payload.keys()), contract["response_key_order"])
    self.assertEqual(payload["task_resolution"]["task_id"], payload["task_context"]["task"]["id"])
    self.assertEqual(payload["run_envelope"]["status"], "reserved")
    self.assertEqual(payload["run_envelope"]["previous_run_id"], None)
    self.assertNotIn("eligible_skills", payload)
    self.assertNotIn("implicit_skill_id", payload)
    self.assertNotIn("selected_skill_packet", json.dumps(payload, ensure_ascii=True))

def test_contract_matches_real_persist_skill_result_response(self) -> None:
    contract = _load_json(PERSIST_SKILL_RESULT_CONTRACT)
    context = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
    result = {
        "execution_summary": "Implemented the requested change and verified the core path.",
        "working_notes": ["Scoped the edits to onboarding CTA behavior."],
        "deliverables_or_changed_files": ["projects/app/src/example.ts"],
        "artifact_content": {
            "task_summary": "Implemented onboarding improvements.",
            "changed_files": ["projects/app/src/example.ts"],
            "implementation_notes": ["Updated CTA behavior.", "Kept state transitions unchanged."],
            "verification_runs": [{"command": "npm test", "result": "passed", "notes": "Targeted unit coverage."}],
            "known_limitations": ["No production build was executed in this contract test."],
        },
    }

    persisted = switch_runtime.persist_skill_result(context, skill_id="implement-task", result=result)
    self.assertTrue(persisted["ok"])
    self.assertEqual(list(persisted.keys()), contract["response_key_order"])
    self.assertEqual(persisted["receipt"]["run_id"], context["run_envelope"]["run_id"])
    self.assertEqual(
        persisted["refreshed_context"]["run_envelope"]["previous_run_id"],
        persisted["receipt"]["run_id"],
    )
    self.assertEqual(persisted["refreshed_context"]["run_envelope"]["status"], "reserved")
```

- [ ] **Step 2: Run the contract/runtime tests and confirm they fail on packet-era fields**

Run:

```bash
python3 -m pytest tests/test_parallel_contracts.py tests/test_switch_runtime.py -q
```

Expected: FAIL because the runtime still returns `eligible_skills` / `implicit_skill_id`, still exposes `prepare-execution`, and does not return a `receipt + refreshed_context` persist response.

- [ ] **Step 3: Add the two new contract files and remove the packet contract from the freeze**

```json
// framework/contracts/resolve-context.json
{
  "contract_id": "resolve-context",
  "contract_version": "2026-04-22",
  "response_key_order": [
    "ok",
    "context_revision",
    "switch",
    "buddy",
    "authority",
    "task_resolution",
    "run_envelope",
    "task_context",
    "track_context",
    "inputs",
    "skills",
    "warnings"
  ]
}
```

```json
// framework/contracts/persist-skill-result.json
{
  "contract_id": "persist-skill-result",
  "contract_version": "2026-04-22",
  "response_key_order": [
    "ok",
    "receipt",
    "refreshed_context"
  ]
}
```

- [ ] **Step 4: Re-run the freeze tests and confirm the new contract files are now the only runtime contract surface**

Run:

```bash
python3 -m pytest tests/test_parallel_contracts.py tests/test_switch_runtime.py -q
```

Expected: PASS for the new contract file loading checks, and FAIL only on unimplemented runtime behavior that will be fixed in the next tasks.

- [ ] **Step 5: Commit the contract freeze scaffolding**

```bash
git add \
  framework/contracts/resolve-context.json \
  framework/contracts/persist-skill-result.json \
  tests/test_parallel_contracts.py \
  tests/test_switch_runtime.py
git rm framework/contracts/selected-skill-packet.json
git commit -m "test: freeze resolve-context and persist-skill-result contracts"
```

## Task 2: Cut `resolve` Over To `resolve_context`

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/runtime_kernel/__init__.py`
- Modify: `scripts/runtime_kernel/resolve.py`
- Delete: `scripts/runtime_kernel/prepare_execution.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_switch_integration.py`

- [ ] **Step 1: Write failing resolve-path tests for the new shape and deleted packet step**

```python
# tests/test_switch_runtime.py
def test_single_skill_buddy_returns_resolve_context(self) -> None:
    payload = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")

    self.assertTrue(payload["ok"])
    self.assertEqual(payload["skills"][0]["id"], "implement-task")
    self.assertEqual(payload["task_resolution"]["mode"], "create")
    self.assertEqual(payload["task_resolution"]["task_id"], payload["task_context"]["task"]["id"])
    self.assertEqual(payload["run_envelope"]["status"], "reserved")
    self.assertEqual(payload["warnings"], [])
    self.assertNotIn("eligible_skills", payload)
    self.assertNotIn("run_instructions", payload)

def test_prepare_execution_command_is_removed(self) -> None:
    parser = switch_runtime.build_parser()
    with self.assertRaises(SystemExit):
        parser.parse_args(["prepare-execution", "--resolved", "resolved.json", "--skill-id", "implement-task"])
```

```python
# tests/test_switch_integration.py
def test_tolerant_switch_flow_resolves_without_prepare_execution(self) -> None:
    resolved = switch_runtime.resolve_switch("switch dev : Implement the approved onboarding improvements in projects/app")
    self.assertTrue(resolved["ok"])
    self.assertEqual(resolved["skills"][0]["id"], "implement-task")
    self.assertEqual(resolved["run_envelope"]["status"], "reserved")
```

- [ ] **Step 2: Run the resolve/integration tests and confirm they fail on the old response shape**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_switch_integration.py -k "resolve_context or prepare_execution_command_is_removed or resolves_without_prepare_execution" -q
```

Expected: FAIL because `resolve_switch` still returns `eligible_skills`, `implicit_skill_id`, `run_instructions`, and the CLI still exposes `prepare-execution`.

- [ ] **Step 3: Replace the old resolve builder with a real `resolve_context` response**

```python
# scripts/switch_runtime.py
def _derive_context_revision(task: dict[str, Any], sequence: int) -> str:
    return f"ctx-{task['id']}-turn-{sequence}"

def _build_resolve_context(
    *,
    parsed: dict[str, Any],
    buddy: dict[str, Any],
    task: dict[str, Any],
    task_resolution: dict[str, Any],
    run_envelope: dict[str, Any],
    track_context: dict[str, Any] | None,
    inputs: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "ok": True,
        "context_revision": _derive_context_revision(task, run_envelope["sequence"]),
        "switch": {
            "raw_text": parsed["raw_text"],
            "buddy_id": buddy["id"],
            "demand": parsed["demand"],
            "task_id": parsed.get("task_id"),
            "track_id": parsed.get("track_id"),
        },
        "buddy": {"id": buddy["id"], "label": buddy["label"], "scope": buddy["scope"]},
        "authority": {"buddy_id": buddy["id"], "permissions": list(buddy.get("permissions", []))},
        "task_resolution": task_resolution,
        "run_envelope": run_envelope,
        "task_context": _build_task_context(task),
        "track_context": track_context,
        "inputs": inputs,
        "skills": skills,
        "warnings": warnings,
    }
```

```python
# scripts/runtime_kernel/__init__.py
from .persist import persist_skill_result_request
from .resolve import resolve_switch_request

__all__ = ["resolve_switch_request", "persist_skill_result_request"]
```

- [ ] **Step 4: Re-run the resolve/integration tests and confirm the packet step is gone**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_switch_integration.py -k "resolve_context or prepare_execution_command_is_removed or resolves_without_prepare_execution" -q
```

Expected: PASS for the new resolve shape and removed `prepare-execution` CLI path.

- [ ] **Step 5: Commit the resolve cutover**

```bash
git add \
  scripts/switch_runtime.py \
  scripts/runtime_kernel/__init__.py \
  scripts/runtime_kernel/resolve.py \
  tests/test_switch_runtime.py \
  tests/test_switch_integration.py
git rm scripts/runtime_kernel/prepare_execution.py
git commit -m "feat: cut resolve over to resolve-context"
```

## Task 3: Allow Resolve-Time Task Materialization And Reserved Runs

**Files:**
- Modify: `scripts/env_store.py`
- Modify: `framework/docs/track-registry.md`
- Modify: `tests/test_env_store_v2.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Write failing storage/runtime tests for task creation without a persisted run**

```python
# tests/test_env_store_v2.py
def test_create_task_allows_resolve_time_materialization_without_run(self) -> None:
    task = create_task(
        "task-dev-resolve-only",
        "Resolve Only Task",
        buddy="dev",
        initial_run_id=None,
    )

    self.assertEqual(task["run_ids"], [])
    self.assertIsNone(task["latest_run_id"])

def test_validate_task_allows_empty_run_ids_when_latest_run_is_null(self) -> None:
    row = env_store.validate_task(
        {
            "id": "task-dev-resolve-only",
            "buddy": "dev",
            "title": "Resolve Only Task",
            "status": "active",
            "track_id": None,
            "artifact_ids": [],
            "artifact_slots": {},
            "run_ids": [],
            "latest_run_id": None,
            "summary": "",
            "created_at": "2026-04-22T01:00:00+08:00",
            "updated_at": "2026-04-22T01:00:00+08:00",
        }
    )
    self.assertEqual(row["run_ids"], [])
    self.assertIsNone(row["latest_run_id"])
```

```python
# tests/test_switch_runtime.py
def test_resolve_create_mode_materializes_task_before_persist(self) -> None:
    payload = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
    task_id = payload["task_resolution"]["task_id"]
    stored_task = get_task(task_id)

    self.assertIsNotNone(stored_task)
    self.assertEqual(stored_task["run_ids"], [])
    self.assertIsNone(stored_task["latest_run_id"])
```

- [ ] **Step 2: Run the storage/runtime tests and confirm they fail under the current `initial_run_id` requirement**

Run:

```bash
python3 -m pytest tests/test_env_store_v2.py tests/test_switch_runtime.py -k "resolve_time_materialization_without_run or empty_run_ids_when_latest_run_is_null or materializes_task_before_persist" -q
```

Expected: FAIL because `create_task` currently requires `initial_run_id`, and `validate_task` rejects empty `run_ids`.

- [ ] **Step 3: Update the task storage model to support resolve-created tasks**

```python
# scripts/env_store.py
def _legacy_create_task(
    task_id: str,
    title: str,
    *,
    buddy: str,
    track_id: str | None = None,
    status: str = "active",
    summary: str = "",
    initial_run_id: str | None = None,
) -> dict[str, Any]:
    if initial_run_id is not None:
        require_id(initial_run_id, "task.initial_run_id")
    task = {
        "id": task_id,
        "buddy": buddy,
        "title": title,
        "status": status,
        "track_id": track_id,
        "artifact_ids": [],
        "artifact_slots": {},
        "run_ids": [initial_run_id] if initial_run_id else [],
        "latest_run_id": initial_run_id,
        "summary": summary,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
```

```python
# scripts/env_store.py
if not run_ids:
    if latest_run_id is not None:
        raise ValueError("task.latest_run_id must be null when task.run_ids is empty")
else:
    if not isinstance(latest_run_id, str) or latest_run_id not in run_ids:
        raise ValueError("task.latest_run_id must be included in task.run_ids")
```

- [ ] **Step 4: Re-run the storage/runtime tests and confirm resolve-created tasks are now valid**

Run:

```bash
python3 -m pytest tests/test_env_store_v2.py tests/test_switch_runtime.py -k "resolve_time_materialization_without_run or empty_run_ids_when_latest_run_is_null or materializes_task_before_persist" -q
```

Expected: PASS for zero-run task creation and resolve-time task persistence.

- [ ] **Step 5: Commit the resolve-time task lifecycle change**

```bash
git add \
  scripts/env_store.py \
  framework/docs/track-registry.md \
  tests/test_env_store_v2.py \
  tests/test_switch_runtime.py
git commit -m "feat: allow resolve-time task materialization"
```

## Task 4: Replace `persist` With `persist-skill-result` And A Freshened Context Loop

**Files:**
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/runtime_kernel/persist.py`
- Modify: `scripts/runtime_kernel/__init__.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_switch_integration.py`

- [ ] **Step 1: Write failing persist-path tests for trust boundaries and refreshed context**

```python
# tests/test_switch_runtime.py
def test_persist_skill_result_re_resolves_skill_definition_from_manifest(self) -> None:
    context = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
    context["skills"][0]["output_schema"] = "framework/schemas/pm/write-prd.json"

    result = {
        "execution_summary": "Implemented the requested change and verified the core path.",
        "working_notes": [],
        "deliverables_or_changed_files": [],
        "artifact_content": {
            "task_summary": "Implemented onboarding improvements.",
            "changed_files": [],
            "implementation_notes": [],
            "verification_runs": [],
            "known_limitations": [],
        },
    }

    persisted = switch_runtime.persist_skill_result(context, skill_id="implement-task", result=result)
    self.assertEqual(persisted["receipt"]["skill_id"], "implement-task")

def test_persist_skill_result_rejects_stale_context_revision(self) -> None:
    context = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
    stale = dict(context)
    stale["context_revision"] = "ctx-stale"

    with self.assertRaisesRegex(ValueError, "context_revision"):
        switch_runtime.persist_skill_result(
            stale,
            skill_id="implement-task",
            result={
                "execution_summary": "Implemented the requested change and verified the core path.",
                "working_notes": [],
                "deliverables_or_changed_files": [],
                "artifact_content": {
                    "task_summary": "Implemented onboarding improvements.",
                    "changed_files": [],
                    "implementation_notes": [],
                    "verification_runs": [],
                    "known_limitations": [],
                },
            },
        )
```

```python
# tests/test_switch_integration.py
def test_resolve_then_persist_returns_refreshed_context(self) -> None:
    resolved = switch_runtime.resolve_switch("switch dev : Implement the approved onboarding improvements in projects/app")
    persisted = switch_runtime.persist_skill_result(
        resolved,
        skill_id="implement-task",
        result={
            "execution_summary": "Implemented the requested change and verified the core path.",
            "working_notes": [],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "task_summary": "Implemented onboarding improvements.",
                "changed_files": [],
                "implementation_notes": [],
                "verification_runs": [],
                "known_limitations": [],
            },
        },
    )

    self.assertTrue(persisted["ok"])
    self.assertEqual(persisted["receipt"]["run_id"], resolved["run_envelope"]["run_id"])
    self.assertEqual(persisted["refreshed_context"]["run_envelope"]["previous_run_id"], persisted["receipt"]["run_id"])
    self.assertEqual(persisted["refreshed_context"]["task_context"]["task"]["latest_run_id"], persisted["receipt"]["run_id"])
```

- [ ] **Step 2: Run the persist/integration tests and confirm they fail under the old `persist_switch` API**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_switch_integration.py -k "persist_skill_result or refreshed_context" -q
```

Expected: FAIL because `persist_switch` still expects the old resolved payload shape and does not return `receipt + refreshed_context`.

- [ ] **Step 3: Implement the new persist entrypoint and response**

```python
# scripts/switch_runtime.py
def _validate_context_revision(context: dict[str, Any]) -> None:
    expected = f"ctx-{context['task_context']['task']['id']}-turn-{context['run_envelope']['sequence']}"
    if context["context_revision"] != expected:
        raise ValueError(f"context_revision mismatch: expected {expected}, got {context['context_revision']}")

def _validate_result_against_skill(skill: dict[str, Any], result: dict[str, Any]) -> None:
    schema = load_output_schema(skill["runtime"]["output_schema"])
    errors = validate_output_payload(result, schema)
    if errors:
        raise ValueError("result payload failed schema validation: " + "; ".join(errors))

def persist_skill_result(
    context: dict[str, Any],
    *,
    skill_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    _validate_context_revision(context)
    skill = _resolve_execution_skill(
        buddy_id=context["buddy"]["id"],
        skill_id=skill_id,
        manifest_path=DEFAULT_MANIFEST,
    )
    _validate_result_against_skill(skill, result)
    task = get_task(context["task_context"]["task"]["id"])
    if task is None:
        raise ValueError(f"task not found: {context['task_context']['task']['id']}")
    if skill_id == "track-manager":
        receipt = _persist_track_manager(
            resolved=context,
            result=result,
            run_id=context["run_envelope"]["run_id"],
            task=task,
            effective_track_id=task.get("track_id"),
        )
    else:
        receipt = _persist_artifact_skill(
            resolved=context,
            skill=skill,
            result=result,
            run_id=context["run_envelope"]["run_id"],
            task=task,
            effective_track_id=task.get("track_id"),
        )
    stored_task = get_task(receipt["task_id"])
    refreshed_context = {
        **context,
        "context_revision": f"ctx-{receipt['task_id']}-turn-{context['run_envelope']['sequence'] + 1}",
        "run_envelope": {
            "run_id": f"run-{uuid.uuid4().hex[:10]}",
            "previous_run_id": receipt["run_id"],
            "sequence": context["run_envelope"]["sequence"] + 1,
            "status": "reserved",
        },
        "task_context": _build_task_context(stored_task),
        "track_context": _build_track_context(stored_task.get("track_id")) if stored_task else None,
        "warnings": [],
    }
    return {"ok": True, "receipt": receipt, "refreshed_context": refreshed_context}
```

```python
# scripts/runtime_kernel/persist.py
def persist_skill_result_request(
    context: dict[str, Any],
    *,
    skill_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    import switch_runtime
    return switch_runtime.persist_skill_result(context, skill_id=skill_id, result=result)
```

- [ ] **Step 4: Re-run the persist/integration tests and confirm the new loop is live**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_switch_integration.py -k "persist_skill_result or refreshed_context" -q
```

Expected: PASS for the new persist API, manifest-backed trust boundary, and refreshed-context return surface.

- [ ] **Step 5: Commit the new persist boundary**

```bash
git add \
  scripts/switch_runtime.py \
  scripts/runtime_kernel/persist.py \
  scripts/runtime_kernel/__init__.py \
  tests/test_switch_runtime.py \
  tests/test_switch_integration.py
git commit -m "feat: replace persist with persist-skill-result"
```

## Task 5: Narrow `track-manager` To Mutation-Only And Freeze Persist Invariants

**Files:**
- Modify: `framework/schemas/pm/track-manager.json`
- Modify: `scripts/switch_runtime.py`
- Modify: `framework/docs/track-registry.md`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_env_store_v2.py`

- [ ] **Step 1: Write failing tests for the narrowed `track-manager` contract and state invariants**

```python
# tests/test_switch_runtime.py
def test_track_manager_schema_rejects_read_and_list_actions(self) -> None:
    context = switch_runtime.resolve_switch("switch pm: manage the active track")
    with self.assertRaisesRegex(ValueError, "track_operation.action"):
        switch_runtime.persist_skill_result(
            context,
            skill_id="track-manager",
            result={
                "execution_summary": "Tried to list tracks.",
                "working_notes": [],
                "deliverables_or_changed_files": [],
                "track_operation": {"action": "list"},
            },
        )

def test_track_creation_binds_task_and_track_ids_together(self) -> None:
    context = switch_runtime.resolve_switch("switch pm: create a landing page track")
    persisted = switch_runtime.persist_skill_result(
        context,
        skill_id="track-manager",
        result={
            "execution_summary": "Created a landing-page track.",
            "working_notes": [],
            "deliverables_or_changed_files": [],
            "track_operation": {
                "action": "create",
                "track_id": "track-landing-page",
                "title": "Landing Page",
                "status": "active",
                "current_buddy": "pm",
                "next_buddy": "design",
                "summary": "Track for landing-page definition and prototype handoff."
            },
        },
    )
    task = get_task(persisted["receipt"]["task_id"])
    track = get_track("track-landing-page")
    self.assertEqual(task["track_id"], "track-landing-page")
    self.assertIn(task["id"], track["task_ids"])
```

- [ ] **Step 2: Run the track-manager and storage tests and confirm they fail on the old action set**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_env_store_v2.py -k "track_manager_schema_rejects_read_and_list_actions or binds_task_and_track_ids_together" -q
```

Expected: FAIL because the schema still allows `read` / `list`, and the runtime still carries the old action vocabulary.

- [ ] **Step 3: Narrow the schema and keep the persist routing explicit**

```json
// framework/schemas/pm/track-manager.json
"action": {
  "type": "string",
  "enum": ["create", "update", "advance", "archive"]
}
```

```python
# scripts/switch_runtime.py
TRACK_ACTIONS = {"create", "update", "advance", "archive"}

def _persist_track_manager(...):
    action = str(op.get("action") or "").lower()
    if action not in TRACK_ACTIONS:
        raise ValueError("track_operation.action must be one of create/update/advance/archive")
```

- [ ] **Step 4: Re-run the track-manager and storage tests and confirm the online loop is mutation-only**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_env_store_v2.py -k "track_manager_schema_rejects_read_and_list_actions or binds_task_and_track_ids_together" -q
```

Expected: PASS, with `track.read` / `track.list` now absent from the online-turn contract.

- [ ] **Step 5: Commit the narrowed track-manager surface**

```bash
git add \
  framework/schemas/pm/track-manager.json \
  scripts/switch_runtime.py \
  framework/docs/track-registry.md \
  tests/test_switch_runtime.py \
  tests/test_env_store_v2.py
git commit -m "feat: narrow track-manager to mutation-only actions"
```

## Task 6: Make `design` A Real Buddy With `shape-prototype`

**Files:**
- Create: `framework/schemas/design/shape-prototype.json`
- Create: `buddyswitch/skills/design/shape-prototype/skill.toml`
- Create: `buddyswitch/skills/design/shape-prototype/SKILL.md`
- Create: `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`
- Modify: `buddyswitch/manifest.toml`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write failing manifest/runtime/repo tests for the new design package**

```python
# tests/test_switch_runtime.py
def test_design_buddy_resolves_shape_prototype_skill(self) -> None:
    payload = switch_runtime.resolve_switch("switch design: Shape the landing-page prototype")

    self.assertTrue(payload["ok"])
    self.assertEqual([skill["id"] for skill in payload["skills"]], ["shape-prototype"])
    self.assertEqual(payload["skills"][0]["output_slot"], "design-handoff")

def test_design_persist_creates_design_handoff_artifact(self) -> None:
    context = switch_runtime.resolve_switch("switch design: Shape the landing-page prototype")
    persisted = switch_runtime.persist_skill_result(
        context,
        skill_id="shape-prototype",
        result={
            "execution_summary": "Shaped the landing-page prototype and packaged the handoff.",
            "working_notes": ["Focused the first pass on information architecture and CTA flow."],
            "deliverables_or_changed_files": [".sandbox/design/task-design-landing-page/index.html"],
            "artifact_content": {
                "prototype_kind": "page-map-plus-key-pages",
                "page_map": ["home", "pricing", "demo-request", "confirmation"],
                "primary_user_flow": ["home -> demo-request -> confirmation"],
                "preview": {
                    "sandbox_root": ".sandbox/design/task-design-landing-page",
                    "entry_file": "index.html"
                },
                "handoff": {
                    "pm": ["Keep the first CTA above the fold."],
                    "dev": ["Implement hero, proof strip, and CTA flow first."],
                    "test": ["Verify the primary CTA path and top-level navigation labels."]
                },
                "open_questions": ["Do enterprise visitors need a separate trust section?"]
            },
        },
    )

    self.assertEqual(persisted["receipt"]["skill_id"], "shape-prototype")
```

```python
# tests/test_repo_consistency.py
self.assertTrue((ROOT / "buddyswitch" / "skills" / "design" / "shape-prototype" / "skill.toml").exists())
self.assertTrue((ROOT / "framework" / "schemas" / "design" / "shape-prototype.json").exists())
```

- [ ] **Step 2: Run the design-focused tests and confirm they fail because the skill package does not exist**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py -k "design_buddy_resolves_shape_prototype_skill or design_persist_creates_design_handoff_artifact or shape-prototype" -q
```

Expected: FAIL because `design` still has no registered skills, no design schema exists, and the repo-consistency package lists do not include a design package.

- [ ] **Step 3: Add the concrete design skill package, schema, and manifest registration**

```toml
# buddyswitch/skills/design/shape-prototype/skill.toml
id = "shape-prototype"
buddy = "design"
description = "Use when the task is shaping a visible UI/UX prototype and packaging design handoff outcomes."
objects = ["task", "artifact"]
produces_artifact = true
output_slot = "design-handoff"
input_slots = ["market-scan", "prd", "requirements", "track", "prior-design-handoff"]
output_schema = "framework/schemas/design/shape-prototype.json"
produces = ["design-handoff"]
consumes = ["market-scan", "prd", "requirements", "track", "prior-design-handoff"]
side_effect_level = "medium"
required_tools = []
required_env = []
allowed_task_kinds = ["design"]
```

```toml
# buddyswitch/manifest.toml
[[skills]]
id = "shape-prototype"
path = "buddyswitch/skills/design/shape-prototype"

[[buddies]]
id = "design"
label = "Design"
scope = "Shape UI/UX prototype direction and design handoff outcomes."
skills = ["shape-prototype"]
permissions = ["track.read", "task.read", "task.create", "task.update", "task.archive", "artifact.read", "artifact.create", "artifact.update"]
```

- [ ] **Step 4: Re-run the design-focused tests and confirm `design` is now part of the live runtime**

Run:

```bash
python3 -m pytest tests/test_switch_runtime.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py -k "design_buddy_resolves_shape_prototype_skill or design_persist_creates_design_handoff_artifact or shape-prototype" -q
```

Expected: PASS for design resolve/persist behavior, schema existence, and package consistency.

- [ ] **Step 5: Commit the design-buddy closure**

```bash
git add \
  framework/schemas/design/shape-prototype.json \
  buddyswitch/skills/design/shape-prototype/skill.toml \
  buddyswitch/skills/design/shape-prototype/SKILL.md \
  buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md \
  buddyswitch/manifest.toml \
  tests/test_env_manifest_v2.py \
  tests/test_switch_runtime.py \
  tests/test_repo_consistency.py
git commit -m "feat: add concrete design shape-prototype skill"
```

## Task 7: Rewrite Host-Facing Docs And Remove Packet-Era Instructions

**Files:**
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `framework/contracts/market.md`
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `README.md`
- Modify: `.codex/agents/router.toml`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write failing doc-boundary tests for the new loop**

```python
# tests/test_repo_consistency.py
def test_switch_spec_documents_resolve_context_loop(self) -> None:
    text = (ROOT / "framework" / "docs" / "switch-spec.md").read_text(encoding="utf-8").lower()
    self.assertIn("resolve_context", text)
    self.assertIn("persist-skill-result", text)
    self.assertNotIn("prepare-execution", text)
    self.assertNotIn("selected_skill_packet", text)

def test_runtime_agents_doc_uses_context_then_persist_flow(self) -> None:
    text = (ROOT / "tools" / "launcher" / "assets" / "runtime-AGENTS.md").read_text(encoding="utf-8").lower()
    self.assertIn("resolve_context", text)
    self.assertIn("persist-skill-result", text)
    self.assertNotIn("selected_skill_packet", text)
```

- [ ] **Step 2: Run the repo-consistency tests and confirm they fail on the old docs**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: FAIL because the active docs still instruct the host to call `prepare-execution` and inject `selected_skill_packet`.

- [ ] **Step 3: Rewrite the active docs around the new host loop and market execution boundary**

```md
<!-- framework/docs/switch-spec.md -->
1. call `scripts/switch_runtime.py resolve "<switch text>"`
2. choose one `skill_id` from `resolve_context.skills`
3. execute that skill locally with the current `sub_task`
4. keep market browser-native execution inside `skills[*].host_execution` and `skills[*].tool_scope`
5. call `scripts/switch_runtime.py persist-skill-result --context <file> --skill-id <skill_id> --result <file>`
6. continue from `refreshed_context` until the user goal is satisfied
```

```md
<!-- framework/docs/browser-cockpit.md -->
- The host reads market browser rules from `resolve_context.skills[*].host_execution`.
- The host applies `resolve_context.skills[*].tool_scope` before browser-native research.
- BuddySwitch still does not execute browser tools itself; it only normalizes the market contract and persists validated results.
```

- [ ] **Step 4: Re-run the repo-consistency tests and confirm packet-era wording is gone**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected: PASS for the active-doc/runtime-loop wording checks.

- [ ] **Step 5: Commit the doc and launcher cutover**

```bash
git add \
  framework/docs/switch-spec.md \
  framework/docs/browser-cockpit.md \
  framework/contracts/market.md \
  tools/launcher/assets/runtime-AGENTS.md \
  README.md \
  .codex/agents/router.toml \
  tests/test_repo_consistency.py
git commit -m "docs: rewrite host flow around resolve-context"
```

## Task 8: Run The Full Verification Sweep And Write The Manual Checklist

**Files:**
- Create: `docs/dev0154/2026-04-22-all-buddy-runtime-cutover-manual-checklist.md`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_switch_integration.py`
- Modify: `tests/test_env_store_v2.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Write the manual checklist file before the final verification run**

```md
# All-Buddy Runtime Cutover Manual Checklist

1. Run `python3 scripts/switch_runtime.py resolve "switch market: validate an AI workflow"` and confirm the response contains `context_revision`, `run_envelope`, `skills`, and no packet-era fields.
2. Run a market skill through the host and confirm `host_execution` keeps `browser_executor = "chrome-devtools-cockpit"` and `discovery_mode = "browser-native"`.
3. Run `switch pm: create a landing page track`, persist a `track-manager` result, and confirm `task.track_id` and `track.task_ids` update together.
4. Run `switch design: shape the landing-page prototype`, persist a `shape-prototype` result, and confirm the durable artifact is `design-handoff` while sandbox files are only recorded in run audit.
5. Persist a second dev or pm turn and confirm the response returns a new reserved `run_id` in `refreshed_context.run_envelope`.
```

- [ ] **Step 2: Run the full targeted verification suite**

Run:

```bash
python3 -m pytest \
  tests/test_env_manifest_v2.py \
  tests/test_env_store_v2.py \
  tests/test_switch_runtime.py \
  tests/test_switch_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: PASS across the manifest, storage, runtime, integration, contract, and active-doc boundaries for the new all-buddy loop.

- [ ] **Step 3: Run one CLI smoke check for `dev` and one for `design`**

Run:

```bash
python3 scripts/switch_runtime.py resolve "switch dev: Implement the approved onboarding improvements in projects/app"
python3 scripts/switch_runtime.py resolve "switch design: Shape the landing-page prototype"
```

Expected: both commands print JSON payloads with `context_revision`, `run_envelope.status = "reserved"`, `skills`, and no `prepare-execution` or `selected_skill_packet` fields.

- [ ] **Step 4: Re-run the full suite after any final doc/test fixups**

Run:

```bash
python3 -m pytest \
  tests/test_env_manifest_v2.py \
  tests/test_env_store_v2.py \
  tests/test_switch_runtime.py \
  tests/test_switch_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: PASS again with no new regressions introduced during the last cleanup pass.

- [ ] **Step 5: Commit the final verification baseline**

```bash
git add \
  docs/dev0154/2026-04-22-all-buddy-runtime-cutover-manual-checklist.md \
  tests/test_env_manifest_v2.py \
  tests/test_env_store_v2.py \
  tests/test_switch_runtime.py \
  tests/test_switch_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py
git commit -m "test: verify all-buddy runtime cutover"
```

## Spec Coverage Check

- `online loop` clarity is covered by Task 1, Task 2, Task 4, and Task 7.
- host/runtime trust boundary and per-turn run refresh are covered by Task 2, Task 3, and Task 4.
- `track-manager` query removal and persist invariants are covered by Task 5.
- `market` browser-native contract preservation is covered by Task 2 and Task 7.
- `design` concrete skill/schema/manifest closure is covered by Task 6.
- all-buddy active-doc and launcher cutover is covered by Task 7.
- end-to-end proof and manual main-path verification are covered by Task 8.

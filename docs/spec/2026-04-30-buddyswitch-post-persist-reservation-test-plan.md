# BuddySwitch Post-Persist Reservation Test Plan

**Target plan:** `docs/spec/2026-04-30-buddyswitch-post-persist-reservation-plan.md`

**Goal:** Prove the post-persist reservation fix with behavior tests that exercise real runtime writes, not mocked success paths or string-only assertions.

**Core invariant:** `resolve` creates a reservation, `persist` consumes that reservation, and a later turn must call explicit `resolve` to create the next reservation. Successful `persist` must not silently reserve the next run.

---

## Sub-Agent Review Summary

Two read-only sub-agents reviewed the testing strategy:

- Runtime/product-mode reviewer: test the full `_cmd_resolve -> _cmd_persist -> _cmd_resolve` path without mocking `resolve_switch`, `persist_skill_result`, `_build_resolve_context`, or `_save_run_reservation`; assert actual `buddyswitch/content/runs/reserved/*.json` file state.
- Contract/docs reviewer: keep real contract tests that call `switch_runtime.resolve_switch()` and `switch_runtime.persist_skill_result()`; add a contract behavior test that fails if `refreshed_context.ok` changes but hidden reservations still remain.

Chosen testing posture: every material claim must be backed by runtime state, persisted file paths, or real contract surfaces. Return shape alone is not enough.

## Non-Cheating Test Rules

Valid tests must:

- Use real `switch_runtime.resolve_switch()` or product-mode `_cmd_resolve()` when proving reservation creation.
- Use real `switch_runtime.persist_skill_result()` or product-mode `_cmd_persist()` when proving reservation consumption.
- Inspect `switch_runtime._reserved_run_path(run_id)` and the `reserved` directory to prove no hidden post-persist reservation remains.
- Assert canonical writes exist through receipt paths: run content, task object, artifact object, and track object when applicable.
- Assert follow-up `resolve` creates a new reservation with a new `run_id`.
- Assert failed `ok:false` contexts cannot be persisted and do not consume an existing reservation.

Invalid or weak tests to avoid:

- Mocking `resolve_switch`, `persist_skill_result`, `_build_resolve_context`, `_save_run_reservation`, or `_clear_run_reservation` in tests that claim to prove reservation lifecycle.
- Handwriting a successful resolved payload to prove `persist` consumes a reservation.
- Only checking `refreshed_context.ok == false` without checking the `reserved` directory.
- Only checking error messages or `recommended_switch` text.
- Only checking consumed reservation deletion without checking that no replacement reservation was created.
- Changing an `ok:false` payload into `ok:true` to make `persist` accept it.
- Testing docs by searching only for `recommended_switch`, because that token already appears in command-display sections.

## Runtime Behavior Tests

### Test 1: Product-Mode Persist Leaves No Post-Persist Reservation

**File:** `tests/test_switch_runtime.py`

**Test name:** `ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_does_not_leave_post_persist_reservation`

**Purpose:** Prove the real product-mode flow commits a run and leaves no hidden active reservation after successful `persist`.

**Required path:** `_cmd_resolve()` -> `_cmd_persist()` -> `_cmd_resolve()` with `patch.dict(os.environ, product_env, clear=True)`.

**Do not mock:** `resolve_switch`, `persist_skill_result`, `_build_resolve_context`, `_save_run_reservation`, `_clear_run_reservation`.

**Core assertions:**

```python
resolve_exit_code, resolved_payload = self._run_cmd_resolve("Draft updated PRD")
self.assertEqual(resolve_exit_code, 0)
self.assertTrue(resolved_payload["ok"])

consumed_run_id = resolved_payload["run_envelope"]["run_id"]
consumed_path = switch_runtime._reserved_run_path(consumed_run_id)  # type: ignore[attr-defined]
self.assertTrue(consumed_path.exists())

persist_exit_code, persisted_payload = self._run_cmd_persist(
    resolved_payload,
    self._pm_prd_result(),
    skill_id="write-prd",
)
self.assertEqual(persist_exit_code, 0)
self.assertTrue(persisted_payload["ok"])
self.assertFalse(consumed_path.exists())

receipt = persisted_payload["receipt"]
refreshed_context = persisted_payload["refreshed_context"]
self.assertFalse(refreshed_context["ok"])
self.assertEqual(refreshed_context["error"]["code"], "E_RUNTIME_REFRESH_CONTEXT")
self.assertEqual(refreshed_context["error"]["recommended_switch"], receipt["recommended_switch"])
self.assertNotIn("run_envelope", refreshed_context)

reserved_dir = switch_runtime._reserved_run_path("placeholder").parent  # type: ignore[attr-defined]
remaining = sorted(reserved_dir.glob("*.json")) if reserved_dir.exists() else []
self.assertEqual(remaining, [])
```

**Canonical write assertions:**

```python
paths = receipt["paths"]
self.assertTrue((ROOT / paths["run"]).exists())
self.assertTrue((ROOT / paths["task"]).exists())
for artifact_path in paths["artifacts"]:
    self.assertTrue((ROOT / artifact_path).exists())
```

**Follow-up resolve assertions:**

Use the receipt-provided switch, not a fresh unrelated prompt:

```python
followup_switch = receipt["recommended_switch"].replace("<demand>", "Continue PRD")
followup_exit_code, followup_payload = self._run_cmd_resolve(followup_switch)
self.assertEqual(followup_exit_code, 0)
self.assertTrue(followup_payload["ok"])

followup_run_id = followup_payload["run_envelope"]["run_id"]
self.assertNotEqual(followup_run_id, consumed_run_id)
followup_path = switch_runtime._reserved_run_path(followup_run_id)  # type: ignore[attr-defined]
self.assertTrue(followup_path.exists())

followup_reservation = json.loads(followup_path.read_text(encoding="utf-8"))
self.assertEqual(followup_reservation["status"], "reserved")
self.assertEqual(followup_reservation["run_id"], followup_run_id)
self.assertEqual(followup_reservation["task_id"], receipt["task_id"])
self.assertEqual(followup_reservation["instance_id"], "inst-pm-no-post-persist-reserve")
self.assertEqual(followup_payload["run_envelope"]["previous_run_id"], receipt["run_id"])
```

**Expected RED before implementation:** the test fails because `persist` currently creates a new reserved `refreshed_context`.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_does_not_leave_post_persist_reservation -q
```

### Test 2: Pre-Persist Active Reservation Still Blocks

**File:** `tests/test_switch_runtime.py`

**Existing test to strengthen:** `ResolveProductModeInputAdapterTests::test_cmd_resolve_product_mode_records_instance_and_blocks_second_active_task_reservation`

**Purpose:** Ensure the fix does not weaken the concurrency guard for unresolved active work.

**Add assertions after first reservation read:**

```python
self.assertEqual(first_reservation["status"], "reserved")
self.assertEqual(first_reservation["run_id"], first_run_id)
self.assertEqual(first_reservation["task_id"], task_id)
self.assertEqual(first_reservation["instance_id"], "inst-pm-first")
```

**Add assertion after second resolve fails:**

```python
reserved_dir = switch_runtime._reserved_run_path("placeholder").parent  # type: ignore[attr-defined]
remaining = sorted(path.name for path in reserved_dir.glob("*.json"))
self.assertEqual(remaining, [f"{first_run_id}.json"])
```

**Keep existing failure assertions:**

```python
self.assertEqual(second_exit_code, 1)
self.assertFalse(second_payload["ok"])
self.assertEqual(second_payload["error"]["code"], "E_RUNTIME_RESOLVE")
self.assertIn("active run reservation", second_payload["error"]["message"])
self.assertIn("inst-pm-first", second_payload["error"]["message"])
```

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_resolve_product_mode_records_instance_and_blocks_second_active_task_reservation -q
```

### Test 3: Failed Resolve Payload Cannot Be Persisted

**File:** `tests/test_switch_runtime.py`

**Test name:** `ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_rejects_failed_resolve_payload_without_writes`

**Purpose:** Prevent the log-observed failure mode where an agent re-runs `resolve`, receives `ok:false`, then tries to persist that failed payload.

**Setup:** Create a real failed resolve payload by using two product-mode instances on the same task.

**Core flow:**

```python
shared_root = self.runtime_root / "shared-root"
first_instance_json = self._write_instance_json(instance_id="inst-pm-first-failed-persist")
first_env = self._product_env("pm", "inst-pm-first-failed-persist", first_instance_json)
first_env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

with patch.dict(os.environ, first_env, clear=True):
    first_exit_code, first_payload = self._run_cmd_resolve("Draft launch requirements")
self.assertEqual(first_exit_code, 0)
self.assertTrue(first_payload["ok"])

task_id = first_payload["switch"]["task_id"]
first_run_id = first_payload["run_envelope"]["run_id"]
first_reservation_path = switch_runtime._reserved_run_path(first_run_id)  # type: ignore[attr-defined]
self.assertTrue(first_reservation_path.exists())

second_instance_json = self._write_instance_json(
    instance_id="inst-pm-second-failed-persist",
    current_task_id=task_id,
)
second_env = self._product_env("pm", "inst-pm-second-failed-persist", second_instance_json)
second_env["BUDDYSWITCH_SHARED_ROOT"] = str(shared_root)

with patch.dict(os.environ, second_env, clear=True):
    failed_exit_code, failed_payload = self._run_cmd_resolve("Continue launch requirements")
    persist_exit_code, persist_payload = self._run_cmd_persist(
        failed_payload,
        self._pm_prd_result(),
        skill_id="write-prd",
    )
```

**Assertions:**

```python
self.assertEqual(failed_exit_code, 1)
self.assertFalse(failed_payload["ok"])
self.assertEqual(failed_payload["error"]["code"], "E_RUNTIME_RESOLVE")

self.assertEqual(persist_exit_code, 1)
self.assertFalse(persist_payload["ok"])
self.assertEqual(persist_payload["error"]["code"], "E_RUNTIME_PERSIST")
self.assertIn("context payload must be successful before persist_skill_result", persist_payload["error"]["message"])

self.assertTrue(first_reservation_path.exists())
self.assertFalse(list((ROOT / "buddyswitch" / "content" / "runs").glob("run-*.json")))
self.assertFalse(list((ROOT / "buddyswitch" / "objects" / "artifacts").glob("*.json")))
```

**Why this is valid:** the failed payload is produced by the real runtime guard, not hand-written.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_rejects_failed_resolve_payload_without_writes -q
```

### Test 4: Forged Error Context Is Rejected Before Reservation Consumption

**File:** `tests/test_switch_runtime.py`

**Test name:** `PersistRuntimeTests::test_persist_skill_result_rejects_ok_false_context_even_with_forged_envelope_without_writes`

**Purpose:** Guard against a hand-reconstructed payload that keeps a real `run_envelope` and `switch` but changes `ok` to false.

**Core flow:**

```python
resolved = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
run_id = resolved["run_envelope"]["run_id"]
reservation_path = switch_runtime._reserved_run_path(run_id)  # type: ignore[attr-defined]
self.assertTrue(reservation_path.exists())

forged = deepcopy(resolved)
forged["ok"] = False
forged["error"] = {"code": "E_RUNTIME_RESOLVE", "message": "active run reservation"}

with self.assertRaisesRegex(ValueError, "context payload must be successful before persist_skill_result"):
    switch_runtime.persist_skill_result(
        forged,
        skill_id="implement-task",
        result=self._artifact_result(),
    )

self.assertTrue(reservation_path.exists())
self.assertFalse((ROOT / "buddyswitch" / "content" / "runs" / f"{run_id}.json").exists())
self.assertFalse(list((ROOT / "buddyswitch" / "objects" / "artifacts").glob("*.json")))
```

**Why this is valid:** it proves the existing guard fires before reservation load/consume/write side effects.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::PersistRuntimeTests::test_persist_skill_result_rejects_ok_false_context_even_with_forged_envelope_without_writes -q
```

## Contract Behavior Tests

### Test 5: Persist Surface Is Present But Not Reserved

**Files:**

- `tests/test_switch_runtime.py`
- `tests/test_parallel_contracts.py`

**Tests to update:**

- `PersistRuntimeTests::test_persist_skill_result_surface_freezes_public_shape`
- `PersistRuntimeTests::test_cmd_persist_uses_persist_skill_result_surface`
- `ResolveAndPersistContractTests::test_contract_matches_real_persist_skill_result_surface`

**Required assertions:**

```python
self.assertTrue(payload["ok"])
self.assertEqual(list(payload.keys()), PERSIST_SKILL_RESULT_RESPONSE_KEY_ORDER)
self.assertEqual(payload["receipt"]["run_id"], resolved["run_envelope"]["run_id"])

self.assertFalse(payload["refreshed_context"]["ok"])
self.assertEqual(payload["refreshed_context"]["error"]["code"], "E_RUNTIME_REFRESH_CONTEXT")
self.assertEqual(
    payload["refreshed_context"]["error"]["recommended_switch"],
    payload["receipt"]["recommended_switch"],
)
self.assertNotIn("run_envelope", payload["refreshed_context"])
```

Continue to assert packet-era fields are absent from the top level:

```python
for field in PERSIST_SKILL_RESULT_PACKET_ERA_FIELDS:
    self.assertNotIn(field, payload)
```

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::PersistRuntimeTests::test_persist_skill_result_surface_freezes_public_shape \
  tests/test_switch_runtime.py::PersistRuntimeTests::test_cmd_persist_uses_persist_skill_result_surface \
  tests/test_parallel_contracts.py::ResolveAndPersistContractTests::test_contract_matches_real_persist_skill_result_surface -q
```

### Test 6: Contract Test Catches Hidden Follow-Up Reservations

**File:** `tests/test_parallel_contracts.py`

**Test name:** `ResolveAndPersistContractTests::test_persist_contract_does_not_leave_hidden_follow_up_reservation`

**Purpose:** Prevent a cheating implementation that returns `refreshed_context.ok == false` but still writes a hidden `reserved/*.json`.

**Core assertions:**

```python
context = switch_runtime.resolve_switch("switch dev: Implement the approved onboarding improvements in projects/app")
consumed_run_id = context["run_envelope"]["run_id"]
consumed_path = switch_runtime._reserved_run_path(consumed_run_id)  # type: ignore[attr-defined]
self.assertTrue(consumed_path.exists())

persisted = switch_runtime.persist_skill_result(
    context,
    skill_id="implement-task",
    result=self._artifact_result(),
)

self.assertTrue(persisted["ok"])
self.assertFalse(consumed_path.exists())
self.assertFalse(persisted["refreshed_context"]["ok"])
self.assertNotIn("run_envelope", persisted["refreshed_context"])

reserved_dir = switch_runtime._reserved_run_path("placeholder").parent  # type: ignore[attr-defined]
remaining = sorted(reserved_dir.glob("*.json")) if reserved_dir.exists() else []
self.assertEqual(remaining, [])
```

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_parallel_contracts.py::ResolveAndPersistContractTests::test_persist_contract_does_not_leave_hidden_follow_up_reservation -q
```

## Docs And Prompt Consistency Tests

### Test 7: Docs Define Persist As End-Of-Turn Boundary

**File:** `tests/test_repo_consistency.py`

**Test name:** `RepoConsistencyTests::test_docs_define_persist_as_end_of_turn_explicit_resolve_boundary`

**Purpose:** Prevent docs from teaching the old hidden follow-up handoff.

**Test discipline:** Do not only search full-file tokens. Scope assertions to the README persist section and switch spec persist/host sections where possible.

**README assertions:**

```python
self.assertIn("successful `persist` does not reserve a follow-up run", readme)
self.assertIn("receipt.recommended_switch", readme)
self.assertIn("run `resolve` with `receipt.recommended_switch`", readme)
self.assertIn("5. if another turn is needed, run `resolve` with `receipt.recommended_switch`", readme)
self.assertNotIn("5. continue from `refreshed_context`", readme)
self.assertNotIn("continue from `refreshed_context`", readme)
```

**Switch spec assertions:**

```python
self.assertIn("`persist` is the end-of-turn commit boundary", switch_spec)
self.assertIn("successful `persist` does not reserve a follow-up run", switch_spec)
self.assertIn("receipt.recommended_switch", switch_spec)
self.assertIn("run explicit `resolve` with `receipt.recommended_switch`", switch_spec)
self.assertNotIn("`refreshed_context` normally carries the next-turn resolve handoff", switch_spec)
self.assertNotIn("continue from `refreshed_context` when it is true", switch_spec)
```

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_docs_define_persist_as_end_of_turn_explicit_resolve_boundary -q
```

### Test 8: Active Host Prompts Require Explicit Resolve

**File:** `tests/test_repo_consistency.py`

**Test name:** `RepoConsistencyTests::test_active_host_prompts_require_explicit_resolve_after_persist`

**Targets:**

- `tools/launcher/assets/runtime-AGENTS.md`
- `.codex/agents/router.toml`

**Required assertions per target:**

```python
self.assertIn("check `refreshed_context.ok`", text)
self.assertIn("e_runtime_refresh_context", text)
self.assertIn("receipt.recommended_switch", text)
self.assertIn("next explicit `resolve`", text)
self.assertIn("if another turn is needed", text)
self.assertNotIn("continue from `refreshed_context`", text)
self.assertNotIn("`refreshed_context` is the canonical follow-up handoff after a successful persist", text)
```

**Why this is valid:** it binds the error condition, command source, and next-turn action together; it is stronger than searching for `recommended_switch` anywhere in the file.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_host_prompts_require_explicit_resolve_after_persist -q
```

## RED/GREEN Execution Order

Run tests in this order to keep failures local and meaningful:

1. Runtime lifecycle RED tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_does_not_leave_post_persist_reservation \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_rejects_failed_resolve_payload_without_writes \
  tests/test_switch_runtime.py::PersistRuntimeTests::test_persist_skill_result_rejects_ok_false_context_even_with_forged_envelope_without_writes -q
```

2. Contract surface RED tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::PersistRuntimeTests::test_persist_skill_result_surface_freezes_public_shape \
  tests/test_switch_runtime.py::PersistRuntimeTests::test_cmd_persist_uses_persist_skill_result_surface \
  tests/test_parallel_contracts.py::ResolveAndPersistContractTests::test_contract_matches_real_persist_skill_result_surface \
  tests/test_parallel_contracts.py::ResolveAndPersistContractTests::test_persist_contract_does_not_leave_hidden_follow_up_reservation -q
```

3. Docs/prompt RED tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_docs_define_persist_as_end_of_turn_explicit_resolve_boundary \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_host_prompts_require_explicit_resolve_after_persist -q
```

4. Focused GREEN suite after implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py tests/test_parallel_contracts.py tests/test_repo_consistency.py -q
```

5. Final regression:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
```

## Acceptance Criteria

- The post-persist lifecycle test fails before implementation because a hidden reservation remains.
- The lifecycle test passes after implementation and proves no `reserved/*.json` remains after successful `persist`.
- A later explicit `resolve` using `receipt.recommended_switch` succeeds and creates exactly one new reservation.
- A failed second `resolve` payload cannot be persisted and cannot consume the original reservation.
- Contract tests keep `{ok, receipt, refreshed_context}` but reject reserved default `refreshed_context`.
- Docs and prompts no longer instruct agents to continue from `refreshed_context` by default.
- Full focused suite passes without mocking reservation lifecycle functions.

# BuddySwitch Post-Persist Reservation Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make successful `persist` an end-of-turn boundary that commits canonical runtime state without silently reserving the next run and blocking later `resolve`.

**Architecture:** Keep the existing `resolve creates reservation, persist consumes reservation` contract. Change `persist_skill_result` so the top-level `refreshed_context` remains present for response-shape compatibility but is not a consumable reserved context by default; callers should use `receipt.recommended_switch` or `receipt.reference_switches` and run explicit `resolve` for the next turn.

**Tech Stack:** Python runtime state machine in `scripts/switch_runtime.py`, JSON contract fixtures under `framework/contracts`, pytest runtime and consistency suites.

---

## Scope

Only fix the `persist/refreshed_context` reservation lifecycle problem:

- Successful `persist` must clear the consumed reservation.
- Successful `persist` must not create a new blocking reservation unless a future explicit opt-in is added.
- A later same-task `resolve` must be able to create a fresh reservation normally.
- Pre-persist active reservations must still block competing product-mode resolves.
- `persist` must still reject failed or manually reconstructed error payloads; callers must persist with a successful `resolve` payload.

Out of scope:

- Browser cockpit blocked detection.
- Runtime lock permissions.
- A new `--reserve-next`, `--end`, or cleanup command.
- Silent acceptance of `ok:false` resolve payloads.

## Confirmed Facts

- `scripts/switch_runtime.py:_build_resolve_context()` always creates a reservation through `_save_run_reservation()`.
- `scripts/switch_runtime.py:_persist_skill_result()` clears the consumed run reservation, then calls `_build_resolve_context()` to return `refreshed_context`.
- That refresh call creates a new active reservation for the same task even when the caller is done.
- `scripts/switch_runtime.py:_save_run_reservation()` blocks product-mode `resolve` when any active reservation exists for the task.
- `scripts/switch_runtime.py:_persist_binding_from_payload()` already updates product-mode instance binding from `receipt.task_id` / `receipt.track_id` when `refreshed_context.error.code == "E_RUNTIME_REFRESH_CONTEXT"`, so product-mode binding does not require a reserved refreshed context.
- `receipt.reference_switches` and `receipt.recommended_switch` already provide the explicit command a caller can resolve for the next turn.

## Sub-Agent Review Summary

Two read-only sub-agents reviewed the issue:

- Agent A recommended allowing same-instance `resolve` to replace an existing active reservation. This preserves the old `refreshed_context` handoff but keeps hidden post-persist reservation state and only makes the symptom less visible for the same instance.
- Agent B recommended making `persist` stop creating post-persist reservations by default. This directly fixes the hidden begin-next-turn behavior and keeps the CLI rule simple.

Chosen plan: Agent B's model, with no fake nonblocking `refreshed_context`. A non-reserved context must not look persistable. The returned `refreshed_context` should be `ok:false` with `E_RUNTIME_REFRESH_CONTEXT` and guidance to rerun `resolve` using `receipt.recommended_switch`.

## File Map

- Modify: `scripts/switch_runtime.py`
  - Stop `_persist_skill_result()` from calling `_build_resolve_context()` after a successful commit.
  - Add a small helper that returns the non-reserved refresh handoff error.
- Modify: `tests/test_switch_runtime.py`
  - Add product-mode regression coverage for `resolve -> persist -> resolve` after successful persist.
  - Update public response-shape assertions for the new default `refreshed_context`.
- Modify: `tests/test_parallel_contracts.py`
  - Update contract behavior assertions so `refreshed_context` is present but not reserved by default.
- Modify: `README.md`
  - Replace "continue from `refreshed_context`" default guidance with explicit `resolve` using `recommended_switch`.
- Modify: `framework/docs/switch-spec.md`
  - Define `persist` as an end-of-turn commit boundary.
  - Keep `refreshed_context.ok` check guidance but state the default is `ok:false` until an explicit next-turn reservation feature exists.
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
  - Update host instructions to rerun `resolve` from `receipt.recommended_switch` after successful persist when another turn is needed.
- Modify: `.codex/agents/router.toml`
  - Mirror runtime host guidance for product-mode agents.
- Modify: `tests/test_repo_consistency.py`
  - Update doc/prompt assertions to enforce the new explicit-resolve continuation rule.

## Task 1: Add Product-Mode Failing Test

**Files:**
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add a reusable PM PRD result helper in `ResolveProductModeInputAdapterTests`**

Add this method near the existing `_resolve_ok()` helper:

```python
    @staticmethod
    def _pm_prd_result() -> dict[str, object]:
        return {
            "execution_summary": "Captured PRD draft updates.",
            "working_notes": ["Focused on scope and acceptance criteria."],
            "deliverables_or_changed_files": [],
            "artifact_content": {
                "problem": "Users need a clearer PRD path for runtime updates.",
                "goals": ["Capture clear scope", "Preserve product-mode safety"],
                "non_goals": ["Implement delivery code in this step"],
                "users_and_scenarios": ["PM updates task scope after runtime resolve."],
                "scope_p0_p1": {
                    "p0": ["Define minimum acceptance criteria"],
                    "p1": ["Add extended delivery notes"],
                },
                "acceptance_criteria": ["PRD payload validates and persists successfully."],
                "risks": ["Reservation cleanup may fail if runtime storage is unstable."],
                "open_questions": ["Should cleanup retries be added later?"],
            },
        }
```

- [ ] **Step 2: Add the failing post-persist reservation regression test**

Add this test in `ResolveProductModeInputAdapterTests` near the existing product-mode persist tests:

```python
    def test_cmd_persist_product_mode_does_not_leave_post_persist_reservation(self) -> None:
        instance_json = self._write_instance_json(instance_id="inst-pm-no-post-persist-reserve")
        env = self._product_env("pm", "inst-pm-no-post-persist-reserve", instance_json)

        with patch.dict(os.environ, env, clear=True):
            resolve_exit_code, resolved_payload = self._run_cmd_resolve("Draft updated PRD")
            self.assertEqual(resolve_exit_code, 0)
            self.assertTrue(resolved_payload["ok"])

            consumed_run_id = resolved_payload["run_envelope"]["run_id"]
            consumed_reservation_path = switch_runtime._reserved_run_path(consumed_run_id)  # type: ignore[attr-defined]
            self.assertTrue(consumed_reservation_path.exists())

            persist_exit_code, persisted_payload = self._run_cmd_persist(
                resolved_payload,
                self._pm_prd_result(),
                skill_id="write-prd",
            )

            self.assertEqual(persist_exit_code, 0)
            self.assertTrue(persisted_payload["ok"])
            self.assertFalse(consumed_reservation_path.exists())
            refreshed_context = persisted_payload["refreshed_context"]
            self.assertFalse(refreshed_context["ok"])
            self.assertEqual(refreshed_context["error"]["code"], "E_RUNTIME_REFRESH_CONTEXT")
            self.assertIn("recommended_switch", refreshed_context["error"])

            reserved_dir = switch_runtime._reserved_run_path("placeholder").parent  # type: ignore[attr-defined]
            remaining_reservations = sorted(reserved_dir.glob("*.json")) if reserved_dir.exists() else []
            self.assertEqual(remaining_reservations, [])

            followup_exit_code, followup_payload = self._run_cmd_resolve("Continue PRD")

        self.assertEqual(followup_exit_code, 0)
        self.assertTrue(followup_payload["ok"])
        followup_run_id = followup_payload["run_envelope"]["run_id"]
        self.assertTrue(switch_runtime._reserved_run_path(followup_run_id).exists())  # type: ignore[attr-defined]

        stored_instance = json.loads(instance_json.read_text(encoding="utf-8"))
        self.assertEqual(stored_instance["current_task_id"], persisted_payload["receipt"]["task_id"])
        self.assertEqual(stored_instance["current_track_id"], persisted_payload["receipt"]["track_id"])
```

- [ ] **Step 3: Verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_does_not_leave_post_persist_reservation -q
```

Expected before implementation: FAIL because `persist` currently returns a reserved `refreshed_context` and leaves a new reservation file.

## Task 2: Update Public Surface Tests For Non-Reserved Refresh

**Files:**
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Update `test_persist_skill_result_surface_freezes_public_shape`**

Replace the assertions that expect a reserved `refreshed_context.run_envelope` with:

```python
        self.assertFalse(payload["refreshed_context"]["ok"])
        self.assertEqual(payload["refreshed_context"]["error"]["code"], "E_RUNTIME_REFRESH_CONTEXT")
        self.assertIn("recommended_switch", payload["refreshed_context"]["error"])
        self.assertEqual(
            payload["refreshed_context"]["error"]["recommended_switch"],
            payload["receipt"]["recommended_switch"],
        )
```

Keep these assertions unchanged:

```python
        self.assertTrue(payload["ok"])
        self.assertEqual(list(payload.keys()), PERSIST_SKILL_RESULT_RESPONSE_KEY_ORDER)
        self.assertEqual(payload["receipt"]["run_id"], resolved["run_envelope"]["run_id"])
        for field in PERSIST_SKILL_RESULT_PACKET_ERA_FIELDS:
            self.assertNotIn(field, payload)
```

- [ ] **Step 2: Update `test_contract_matches_real_persist_skill_result_surface`**

Replace the reserved `refreshed_context.run_envelope` assertions with:

```python
        self.assertFalse(persisted["refreshed_context"]["ok"])
        self.assertEqual(persisted["refreshed_context"]["error"]["code"], "E_RUNTIME_REFRESH_CONTEXT")
        self.assertEqual(
            persisted["refreshed_context"]["error"]["recommended_switch"],
            persisted["receipt"]["recommended_switch"],
        )
```

Keep the response key order and removed-field assertions unchanged.

- [ ] **Step 3: Verify RED for public surface expectations**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::SwitchRuntimeTests::test_persist_skill_result_surface_freezes_public_shape \
  tests/test_parallel_contracts.py::ParallelContractsTests::test_contract_matches_real_persist_skill_result_surface -q
```

Expected before implementation: FAIL because current `persist` returns `refreshed_context.ok == true` with `run_envelope.status == "reserved"`.

## Task 3: Change Persist To End The Turn By Default

**Files:**
- Modify: `scripts/switch_runtime.py`

- [ ] **Step 1: Add helper for non-reserved refresh handoff**

Add this helper near `_refresh_context_error()` or near `_build_refresh_switch_text()`:

```python
def _post_persist_refreshed_context_unavailable(receipt: dict[str, Any]) -> dict[str, Any]:
    recommended_switch = receipt.get("recommended_switch")
    reference_switches = receipt.get("reference_switches")
    error: dict[str, Any] = {
        "code": "E_RUNTIME_REFRESH_CONTEXT",
        "message": (
            "persist completed without reserving a follow-up run; "
            "rerun resolve with receipt.recommended_switch to continue"
        ),
    }
    if isinstance(recommended_switch, str) and recommended_switch.strip():
        error["recommended_switch"] = recommended_switch
    if isinstance(reference_switches, dict):
        error["reference_switches"] = reference_switches
    return {"ok": False, "error": error}
```

- [ ] **Step 2: Replace post-persist `_build_resolve_context()` call**

In `_persist_skill_result()`, after clearing the consumed reservation, replace the current `try: refreshed_context = _build_resolve_context(...)` block with:

```python
    refreshed_context = _post_persist_refreshed_context_unavailable(receipt)

    return {
        "ok": True,
        "receipt": receipt,
        "refreshed_context": refreshed_context,
    }
```

Delete the now-unused local `refreshed_track_id` calculation if it only fed `_build_refresh_switch_text()`.

- [ ] **Step 3: Keep strict persist validation**

Do not change this guard:

```python
    if not context.get("ok"):
        raise ValueError("context payload must be successful before persist_skill_result")
```

This prevents an agent from persisting with a failed second `resolve` payload.

- [ ] **Step 4: Verify GREEN for focused runtime tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_persist_product_mode_does_not_leave_post_persist_reservation \
  tests/test_switch_runtime.py::SwitchRuntimeTests::test_persist_skill_result_surface_freezes_public_shape \
  tests/test_parallel_contracts.py::ParallelContractsTests::test_contract_matches_real_persist_skill_result_surface -q
```

Expected after implementation: PASS.

## Task 4: Preserve Active Reservation Safety

**Files:**
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Keep existing pre-persist cross-instance guard**

Do not weaken this existing test:

```python
tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_resolve_product_mode_records_instance_and_blocks_second_active_task_reservation
```

It must continue to prove an unresolved active run reservation blocks a second product-mode instance.

- [ ] **Step 2: Add a direct assertion to the existing guard**

In that test, after reading `first_reservation`, keep or add:

```python
        self.assertEqual(first_reservation["status"], "reserved")
        self.assertEqual(first_reservation["instance_id"], "inst-pm-first")
```

The expected behavior remains:

```python
        self.assertEqual(second_exit_code, 1)
        self.assertFalse(second_payload["ok"])
        self.assertEqual(second_payload["error"]["code"], "E_RUNTIME_RESOLVE")
        self.assertIn("active run reservation", second_payload["error"]["message"])
        self.assertIn("inst-pm-first", second_payload["error"]["message"])
```

- [ ] **Step 3: Run active reservation guard**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py::ResolveProductModeInputAdapterTests::test_cmd_resolve_product_mode_records_instance_and_blocks_second_active_task_reservation -q
```

Expected after implementation: PASS.

## Task 5: Update Runtime Docs And Host Prompts

**Files:**
- Modify: `README.md`
- Modify: `framework/docs/switch-spec.md`
- Modify: `tools/launcher/assets/runtime-AGENTS.md`
- Modify: `.codex/agents/router.toml`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update README flow**

Replace the default flow item:

```markdown
5. continue from `refreshed_context`
```

with:

```markdown
5. if another turn is needed, run `resolve` with `receipt.recommended_switch`
```

Update nearby prose to state:

```markdown
Check `refreshed_context.ok`. By default, successful `persist` does not reserve a follow-up run; when `refreshed_context.error.code = E_RUNTIME_REFRESH_CONTEXT`, continue by running `resolve` with `receipt.recommended_switch`.
```

- [ ] **Step 2: Update switch spec flow**

Replace the old normal-case wording:

```markdown
`refreshed_context` normally carries the next-turn resolve handoff.
```

with:

```markdown
`persist` is the end-of-turn commit boundary. By default, `refreshed_context` is `{ok: false, error.code: E_RUNTIME_REFRESH_CONTEXT}` and carries `recommended_switch` guidance; run explicit `resolve` with `receipt.recommended_switch` to reserve the next turn.
```

- [ ] **Step 3: Update runtime agent prompt**

Replace continuation guidance in `tools/launcher/assets/runtime-AGENTS.md` with:

```markdown
11. Check `refreshed_context.ok`; when it is false with `E_RUNTIME_REFRESH_CONTEXT`, use `receipt.recommended_switch` for the next explicit `resolve` if another turn is needed.
```

- [ ] **Step 4: Update router prompt**

Replace continuation guidance in `.codex/agents/router.toml` with:

```toml
- Check `refreshed_context.ok`; when it is false with `E_RUNTIME_REFRESH_CONTEXT`, use `receipt.recommended_switch` for the next explicit `resolve` if another turn is needed.
```

- [ ] **Step 5: Update repo consistency tests**

In `test_docs_place_persist_follow_up_fields_inside_receipt` and `test_active_host_prompts_require_refresh_context_check_and_retry`, enforce:

```python
self.assertIn("receipt.recommended_switch", readme)
self.assertIn("successful `persist` does not reserve a follow-up run", readme)
self.assertIn("receipt.recommended_switch", switch_spec)
self.assertIn("successful `persist` does not reserve a follow-up run", switch_spec)
```

Update legacy-forbidden strings to include:

```python
"continue from `refreshed_context` when it is true"
"`refreshed_context` normally carries the next-turn resolve handoff"
```

- [ ] **Step 6: Verify docs consistency**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected after docs update: PASS.

## Task 6: Final Verification

**Files:**
- No new source files beyond previous tasks.

- [ ] **Step 1: Python compile**

Run:

```bash
PYTHONPYCACHEPREFIX=/tmp/buddyswitch-pycache PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/switch_runtime.py
```

Expected: no output.

- [ ] **Step 2: Focused runtime and contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_switch_runtime.py tests/test_parallel_contracts.py tests/test_repo_consistency.py -q
```

Expected: all pass.

- [ ] **Step 3: Current main regression suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
```

Expected: all pass.

- [ ] **Step 4: Manual product-mode proof**

In a product-mode instance, run:

```bash
python3 scripts/switch_runtime.py resolve 'switch pm: Draft a small test PRD' > /tmp/resolve.json
python3 scripts/switch_runtime.py persist --resolved /tmp/resolve.json --result /tmp/result.json --skill-id write-prd > /tmp/persist.json
python3 - <<'PY'
import json
payload = json.load(open('/tmp/persist.json', encoding='utf-8'))
print(payload['ok'])
print(payload['refreshed_context']['ok'])
print(payload['refreshed_context']['error']['code'])
print(payload['receipt']['recommended_switch'])
PY
```

Expected:

```text
True
False
E_RUNTIME_REFRESH_CONTEXT
switch pm(...): <demand>
```

Then run explicit next-turn resolve with the printed `receipt.recommended_switch`; expected result is `ok: true` and one new reservation file for that next turn.

## Self-Review

- Root cause fixed: successful `persist` no longer calls the reservation-creating resolve path.
- Scope kept narrow: no browser cockpit changes, no runtime lock changes, no new workflow engine.
- Concurrency preserved: unresolved active reservations still block competing product-mode resolves.
- Public contract preserved at top level: response remains `{ok, receipt, refreshed_context}`.
- Contract semantics clarified: `refreshed_context` is not a default hidden next-turn reservation; explicit `resolve` owns next-turn reservation.
- Remaining risk: callers that directly consumed `refreshed_context` as a reserved next-turn context must switch to `receipt.recommended_switch` plus explicit `resolve`.

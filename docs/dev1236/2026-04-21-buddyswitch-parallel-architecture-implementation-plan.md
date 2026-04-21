# BuddySwitch Parallel Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the parallel-architecture recommendation without destabilizing the current product surface, so BuddySwitch can support sustained multi-line development in one repo.

**Architecture:** Freeze the external contracts first, then carve the current monolith into six hard boundaries: `contracts`, `runtime-kernel`, `state-store`, `launcher-runtime`, `console-readonly`, and `projects/app`. Keep all current entrypoints stable while replacing internals in layers, with launcher changes deliberately deferred until the kernel and data plane are stable.

**Tech Stack:** Python 3, Bash, JSON schema validation, pytest, git worktrees, existing BuddySwitch launcher/runtime scripts, Next.js app under `projects/app`, context panel server under `scripts/serve_context_panel.py`.

## Progress

- `2026-04-21`: Task 1 completed.
- Contract freeze landed in three commits:
  - `cbffbb5` `docs: freeze BuddySwitch parallel architecture contracts`
  - `ffcd9b9` `docs: harden parallel architecture contracts`
  - `66d23e6` `docs: constrain nested contract containers`
- Verification after Task 1:
  - `python3 -m pytest tests/test_parallel_contracts.py tests/test_repo_consistency.py tests/test_switch_runtime.py -q`
  - Result: `99 passed`
- Review status:
  - spec review: approved
  - code quality review: approved
- `2026-04-21`: Task 2 completed.
- Runtime-kernel carve-out landed in two commits:
  - `a8fd795` `refactor: carve runtime kernel from switch runtime`
  - `6427ebd` `refactor: stabilize runtime kernel entrypoints`
- Verification after Task 2:
  - `python3 -m pytest tests/test_switch_runtime.py -k runtime_kernel -q`
  - Result: `7 passed`
  - `python3 -m pytest tests/test_switch_runtime.py tests/test_switch_integration.py -q`
  - Result: `56 passed`
- Review status:
  - spec review: approved
  - code quality review: approved
- `2026-04-21`: Task 3 completed.
- Runtime-store carve-out landed in two commits:
  - `017fb92` `refactor: carve runtime store repositories from env_store`
  - `ed4322e` `refactor: stabilize runtime store package surface`
- Verification after Task 3:
  - `python3 -m pytest tests/test_env_store_v2.py -k runtime_store -q`
  - Result: `7 passed`
  - `python3 -m pytest tests/test_env_store_v2.py tests/test_switch_runtime.py -q`
  - Result: `69 passed`
- Review status:
  - spec review: approved
  - code quality review: approved
- `2026-04-21`: Task 4 completed.
- Read-projection boundary landed in one follow-up commit:
  - `eb887ae` `refactor: move workspace projection implementations into runtime store`
- Verification after Task 4:
  - `python3 -m pytest tests/test_switch_runtime.py -k workspace_data -q`
  - Result: `2 passed, 56 deselected`
  - `python3 -m pytest tests/test_switch_runtime.py -q`
  - Result: `58 passed`
  - `python3 -m pytest tests/test_switch_runtime.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q`
  - Result: `109 passed`
- Review status:
  - spec review: approved
  - code quality review: approved
- `2026-04-21`: Task 5 completed.
- UI-boundary lock and follow-up fixes landed in four commits:
  - `e5a4c9e` `docs: lock ui surface runtime boundary`
  - `4e27706` `fix: remove ui runtime path fallbacks`
  - `43e0d90` `fix: align console source details with projection contract`
  - `e9380ab` `fix: drop unsupported track path from console UI`
- Verification after Task 5:
  - `python3 -m pytest tests/test_repo_consistency.py -k ui_surface -q`
  - Result: `2 passed, 46 deselected`
  - `python3 -m pytest tests/test_repo_consistency.py -k "ui_surface or track_object_path" -q`
  - Result: `3 passed, 46 deselected`
  - `python3 -m pytest tests/test_repo_consistency.py -q`
  - Result: `49 passed`
- Review status:
  - spec review: approved
  - code quality review: approved
- `2026-04-21`: Task 6 completed.
- Launcher-runtime isolation and reserved-state guardrails landed in three commits:
  - `bad5b73` `fix: confine launcher workspace under shared root`
  - `f8085f3` `fix: harden launcher workspace confinement`
  - `ce7241b` `fix: reject launcher workspace collisions with reserved state`
- Verification after Task 6:
  - `python3 -m pytest tests/test_buddyswitch_launcher.py -k "workspace_dir_outside_shared_root or parent_traversal_outside_shared_root or equal_to_shared_root or reserved_launcher_state" -q`
  - Result: `4 passed, 7 deselected, 4 subtests passed`
  - `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py -q`
  - Result: `15 passed`
  - `python3 -m pytest tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py tests/test_switch_runtime.py tests/test_env_store_v2.py -q`
  - Result: `136 passed`
- Review status:
  - spec review: approved
  - code quality review: approved
- Current active phase: complete

---

## File Structure

**Create**
- `docs/dev1236/2026-04-21-buddyswitch-parallel-architecture-implementation-plan.md`
- `framework/contracts/switch-grammar.json`
- `framework/contracts/selected-skill-packet.json`
- `framework/contracts/workspace-projection.json`
- `scripts/runtime_kernel/__init__.py`
- `scripts/runtime_kernel/resolve.py`
- `scripts/runtime_kernel/prepare_execution.py`
- `scripts/runtime_kernel/persist.py`
- `scripts/runtime_store/__init__.py`
- `scripts/runtime_store/repositories.py`
- `scripts/runtime_store/projections.py`
- `tests/test_parallel_contracts.py`

**Modify**
- `docs/whiteboard/buddyswitch-parallel-architecture-recommendation-2026-04-21.md`
- `framework/docs/switch-spec.md`
- `framework/docs/interface-spec.md`
- `buddyswitch/manifest.toml`
- `scripts/env_manifest.py`
- `scripts/switch_runtime.py`
- `scripts/env_store.py`
- `scripts/workspace_data.py`
- `scripts/serve_context_panel.py`
- `tests/test_switch_runtime.py`
- `tests/test_switch_integration.py`
- `tests/test_env_store_v2.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py`

**Why these boundaries**
- `framework/contracts/**` becomes the canonical ABI layer instead of letting runtime code, docs, and tests each redefine the same contract.
- `scripts/runtime_kernel/**` absorbs orchestration logic without changing the public CLI surface.
- `scripts/runtime_store/**` becomes the only state API; `workspace_data.py` becomes a thin compatibility adapter until the transition is complete.
- Launcher and UI surfaces stay stable until kernel and data boundaries are proven.

---

### Task 1: Freeze the External Contracts Before Any Refactor

**Files:**
- Create: `framework/contracts/switch-grammar.json`
- Create: `framework/contracts/selected-skill-packet.json`
- Create: `framework/contracts/workspace-projection.json`
- Create: `tests/test_parallel_contracts.py`
- Modify: `framework/docs/switch-spec.md`
- Modify: `framework/docs/interface-spec.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing tests that lock the three contract surfaces**

```python
def test_switch_contract_files_exist() -> None:
    for rel in (
        "framework/contracts/switch-grammar.json",
        "framework/contracts/selected-skill-packet.json",
        "framework/contracts/workspace-projection.json",
    ):
        assert (ROOT / rel).exists()
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `python3 -m pytest tests/test_parallel_contracts.py -q`
Expected: FAIL because the new contract files do not exist yet.

- [ ] **Step 3: Write the initial machine-readable contracts from existing docs**

```json
{
  "id": "selected-skill-packet",
  "type": "object",
  "required": ["skill_id", "instruction_path", "output_schema", "run_instructions"]
}
```

- [ ] **Step 4: Point docs and repo-consistency checks at the new contract files**

```python
CONTRACT_FILES = (
    ROOT / "framework" / "contracts" / "switch-grammar.json",
    ROOT / "framework" / "contracts" / "selected-skill-packet.json",
    ROOT / "framework" / "contracts" / "workspace-projection.json",
)
```

- [ ] **Step 5: Run contract and consistency tests**

Run: `python3 -m pytest tests/test_parallel_contracts.py tests/test_repo_consistency.py -q`
Expected: PASS with the new contract files treated as canonical sources.

- [ ] **Step 6: Commit**

```bash
git add framework/contracts framework/docs/switch-spec.md framework/docs/interface-spec.md tests/test_parallel_contracts.py tests/test_repo_consistency.py
git commit -m "docs: freeze BuddySwitch parallel architecture contracts"
```

---

### Task 2: Extract `runtime-kernel` While Keeping the CLI Stable

**Files:**
- Create: `scripts/runtime_kernel/__init__.py`
- Create: `scripts/runtime_kernel/resolve.py`
- Create: `scripts/runtime_kernel/prepare_execution.py`
- Create: `scripts/runtime_kernel/persist.py`
- Modify: `scripts/switch_runtime.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_switch_integration.py`

- [ ] **Step 1: Add a failing import-level regression for the new kernel entrypoints**

```python
from runtime_kernel.resolve import resolve_switch_request
from runtime_kernel.prepare_execution import prepare_execution_request
from runtime_kernel.persist import persist_switch_request
```

- [ ] **Step 2: Run the focused runtime tests to verify failure**

Run: `python3 -m pytest tests/test_switch_runtime.py -k runtime_kernel -q`
Expected: FAIL because the new package does not exist yet.

- [ ] **Step 3: Create the kernel API and move orchestration logic behind wrappers**

```python
def resolve_switch_request(text: str, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return _legacy_resolve_switch(text, manifest_path=manifest_path)
```

- [ ] **Step 4: Reduce `scripts/switch_runtime.py` to a compatibility shell**

```python
from runtime_kernel.resolve import resolve_switch_request
from runtime_kernel.prepare_execution import prepare_execution_request
from runtime_kernel.persist import persist_switch_request
```

- [ ] **Step 5: Verify CLI and JSON outputs did not change**

Run: `python3 -m pytest tests/test_switch_runtime.py tests/test_switch_integration.py -q`
Expected: PASS with existing CLI-facing tests unchanged.

- [ ] **Step 6: Commit**

```bash
git add scripts/runtime_kernel scripts/switch_runtime.py tests/test_switch_runtime.py tests/test_switch_integration.py
git commit -m "refactor: carve runtime kernel from switch runtime"
```

---

### Task 3: Extract `state-store` Repositories Without Changing Canonical Objects

**Files:**
- Create: `scripts/runtime_store/__init__.py`
- Create: `scripts/runtime_store/repositories.py`
- Modify: `scripts/env_store.py`
- Modify: `tests/test_env_store_v2.py`
- Modify: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add a failing repository import regression**

```python
from runtime_store.repositories import create_task_record, create_track_record, create_artifact_record
```

- [ ] **Step 2: Run the store tests to verify failure**

Run: `python3 -m pytest tests/test_env_store_v2.py -q`
Expected: FAIL because the repository package does not exist yet.

- [ ] **Step 3: Move raw object read/write APIs into `runtime_store.repositories`**

```python
def create_task_record(...):
    return _legacy_create_task(...)
```

- [ ] **Step 4: Turn `env_store.py` into a compatibility adapter**

```python
from runtime_store.repositories import create_task_record as create_task
```

- [ ] **Step 5: Run the state and runtime regression suite**

Run: `python3 -m pytest tests/test_env_store_v2.py tests/test_switch_runtime.py -q`
Expected: PASS with canonical object formats unchanged.

- [ ] **Step 6: Commit**

```bash
git add scripts/runtime_store scripts/env_store.py tests/test_env_store_v2.py tests/test_switch_runtime.py
git commit -m "refactor: extract runtime state repositories"
```

---

### Task 4: Split Read Projections From Writable State

**Files:**
- Create: `scripts/runtime_store/projections.py`
- Modify: `scripts/workspace_data.py`
- Modify: `scripts/serve_context_panel.py`
- Modify: `tests/test_switch_runtime.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add a failing projection contract test**

```python
def test_workspace_projection_matches_contract() -> None:
    payload = workspace_data.build_workspace_data()
    assert "tracks" in payload and "tasks" in payload and "run_audits" in payload
```

- [ ] **Step 2: Run the projection tests to verify the new module is missing**

Run: `python3 -m pytest tests/test_switch_runtime.py -k workspace_data -q`
Expected: FAIL once the import target is switched to `runtime_store.projections`.

- [ ] **Step 3: Move projection builders into the new module**

```python
def build_workspace_projection() -> dict[str, Any]:
    return {
        "tracks": build_track_views(),
        "tasks": build_task_views(),
        "run_audits": scan_run_audits(),
    }
```

- [ ] **Step 4: Make `workspace_data.py` and the context panel consume only projections**

```python
from runtime_store.projections import build_workspace_projection
```

- [ ] **Step 5: Verify the panel API shape and regression suite**

Run: `python3 -m pytest tests/test_switch_runtime.py tests/test_repo_consistency.py -q`
Expected: PASS and `/api/workspace` contract unchanged.

- [ ] **Step 6: Commit**

```bash
git add scripts/runtime_store/projections.py scripts/workspace_data.py scripts/serve_context_panel.py tests/test_switch_runtime.py tests/test_repo_consistency.py
git commit -m "refactor: isolate workspace projections from writable state"
```

---

### Task 5: Decouple the Two UI Surfaces From Internal Runtime Modules

**Files:**
- Modify: `framework/console/app.js`
- Modify: `projects/app/main.js`
- Modify: `framework/docs/interface-spec.md`
- Test: manual smoke for `python3 scripts/serve_context_panel.py`
- Test: manual smoke for `projects/app`

- [ ] **Step 1: Document the read-only UI contract and add a repo-consistency guard**

```python
def test_ui_surfaces_do_not_import_runtime_store_repositories() -> None:
    forbidden = ("env_store", "runtime_store.repositories", "switch_runtime")
```

- [ ] **Step 2: Run the consistency test and verify it fails if a direct import exists**

Run: `python3 -m pytest tests/test_repo_consistency.py -k ui_surfaces -q`
Expected: FAIL until the new guard and UI adapters align.

- [ ] **Step 3: Route both UI surfaces through the projection/query API only**

```javascript
const workspace = await fetch("/api/workspace").then((r) => r.json())
```

- [ ] **Step 4: Verify both surfaces still load**

Run: `python3 scripts/serve_context_panel.py`
Expected: `/api/workspace` responds and the console renders without touching writable state internals.

- [ ] **Step 5: Commit**

```bash
git add framework/console/app.js projects/app/main.js framework/docs/interface-spec.md tests/test_repo_consistency.py
git commit -m "refactor: decouple UI surfaces from runtime internals"
```

---

### Task 6: Isolate `launcher-runtime` Last and Lock Parallel Guardrails

**Files:**
- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/workspace.sh`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `.codex/agents/router.toml`

- [ ] **Step 1: Add a failing launcher regression that asserts launcher calls runtime APIs instead of internal modules**

```python
def test_launcher_uses_runtime_entrypoints_only(self) -> None:
    assert "scripts/env_store.py" not in launcher_source
```

- [ ] **Step 2: Run launcher tests to confirm the new guard starts red**

Run: `python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py -q`
Expected: FAIL until launcher/runtime boundaries are explicit.

- [ ] **Step 3: Make launcher shell helpers call stable runtime entrypoints only**

```bash
python3 scripts/switch_runtime.py resolve "$directive"
python3 scripts/switch_runtime.py prepare-execution --resolved "$resolved"
```

- [ ] **Step 4: Add the permanent parallel-development guardrails**

```python
FORBIDDEN_CROSS_IMPORTS = {
    "projects/app": ("switch_runtime", "env_store", "runtime_store.repositories"),
    "framework/console": ("env_store", "runtime_store.repositories"),
}
```

- [ ] **Step 5: Run the full architecture safety suite**

Run: `python3 -m pytest tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py tests/test_switch_runtime.py tests/test_env_store_v2.py -q`
Expected: PASS with launcher stable and guardrails enforced.

- [ ] **Step 6: Commit**

```bash
git add buddyswitch-codex tools/launcher/env.sh tools/launcher/workspace.sh tools/launcher/browser_cockpit.sh .codex/agents/router.toml tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py
git commit -m "refactor: isolate launcher runtime and enforce parallel boundaries"
```

---

## Self-Review

- Spec coverage: this plan covers contract freezing, kernel extraction, store extraction, projection isolation, UI decoupling, launcher isolation, and permanent guardrails; no recommendation item is left without a task.
- Placeholder scan: no `TBD`, `TODO`, or “implement later” markers remain.
- Type consistency: the plan consistently uses `runtime-kernel`, `state-store`, `repositories`, `projections`, `selected_skill_packet`, and `workspace projection` as the canonical target names.

## Execution Handoff

Plan complete and saved to `docs/dev1236/2026-04-21-buddyswitch-parallel-architecture-implementation-plan.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

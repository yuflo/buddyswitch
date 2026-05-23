# Remove Legacy Dashboard And Skill Create Development Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the old Context Panel dashboard and the old skill-create/importer surface without touching browser cockpit or normal runtime skill installation.

**Architecture:** This is a forward deletion. Remove the obsolete files, remove manifest registrations and test expectations that anchored them, then add consistency gates that prevent reintroduction. Keep the app-server service mode, browser cockpit, env context tool, and runtime skill materialization paths intact.

**Tech Stack:** Bash launcher tests, Python unittest/pytest, TOML manifest, static repo scans with `rg`.

---

## Scope

This plan deletes two stale surfaces:

- Context Panel dashboard and its dashboard-only workspace projection path.
- `skill-creator-importer` script, skill package, fixture, manifest registration, and tests.

This plan does not delete:

- `tools/launcher/browser_cockpit.sh`
- `tests/test_browser_cockpit_launcher.py`
- `chrome-devtools-cockpit` MCP references
- `scripts/env/tools/search/**`
- `scripts/runtime_skills.py`
- normal registered skill packages
- `scripts/env/tools/context/**`
- `framework/contracts/prepare-turn-context.json`

## Files To Delete

Dashboard:

- `scripts/serve_context_panel.py`
- `framework/console/index.html`
- `framework/console/app.js`
- `framework/console/styles.css`
- `framework/contracts/workspace-projection.json`
- `scripts/workspace_data.py`
- `scripts/runtime_store/projections.py`
- `tests/test_console_app_contract.py`
- `tests/test_parallel_contracts.py`

Skill-create/importer:

- `scripts/skill_creator_importer.py`
- `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- `tests/test_skill_creator_importer.py`
- `tests/fixtures/community-skills/dev-summary/SKILL.md`

Delete empty directories after file deletion:

- `framework/console/`
- `buddyswitch/skills/dev/skill-creator-importer/assets/`
- `buddyswitch/skills/dev/skill-creator-importer/`
- `tests/fixtures/community-skills/dev-summary/`
- `tests/fixtures/community-skills/` if empty

## Files To Modify

- `AGENTS.md`
  - remove the Context panel command bullet.

- `README.md`
  - remove the Context Panel section.
  - remove the `framework/contracts/workspace-projection.json` runtime source bullet.
  - update instance command examples if they still mention removed `instance open`.

- `buddyswitch/manifest.toml`
  - delete the `[[skills]]` entry with `id = "skill-creator-importer"`.
  - remove `"skill-creator-importer"` from the Dev buddy `skills` list.

- `tests/test_repo_consistency.py`
  - remove `framework/console/app.js` from generic scan targets.
  - remove `test_workspace_projection_contract_uses_track_page_shape`.
  - add removed-surface path and token guards.

- `tests/test_memory_removal_contract.py`
  - remove `workspace_data` import.
  - replace projection-based memory/handoff assertion with cleanup-only assertion.

- `tests/test_runtime_skills.py`
  - change importer inclusion expectations to exclusion expectations.
  - remove importer from expected Dev runtime materialization set.

- `tests/test_buddyswitch_launcher.py`
  - change importer runtime materialization assertions to absence assertions.

## Implementation Tasks

### Task 1: Add Removal Gates First

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing path absence gate**

Add:

```python
def test_removed_dashboard_and_skill_create_surfaces_are_absent(self) -> None:
    removed_paths = [
        "scripts/serve_context_panel.py",
        "framework/console",
        "framework/contracts/workspace-projection.json",
        "scripts/workspace_data.py",
        "scripts/runtime_store/projections.py",
        "scripts/skill_creator_importer.py",
        "buddyswitch/skills/dev/skill-creator-importer",
        "tests/test_console_app_contract.py",
        "tests/test_parallel_contracts.py",
        "tests/test_skill_creator_importer.py",
        "tests/fixtures/community-skills/dev-summary",
    ]
    for relative in removed_paths:
        with self.subTest(path=relative):
            self.assertFalse((ROOT / relative).exists())
```

- [ ] **Step 2: Add failing token absence gate**

Add:

```python
def test_removed_dashboard_and_skill_create_names_are_not_referenced(self) -> None:
    forbidden = (
        "serve_context_panel",
        "Context Panel",
        "workspace-projection",
        "framework/console",
        "skill_creator_importer",
        "skill-creator-importer",
        "community-skills",
    )
    scan_targets = [
        "README.md",
        "AGENTS.md",
        "scripts",
        "buddyswitch",
        "tools",
        "framework",
        "tests",
    ]
    for token in forbidden:
        completed = subprocess.run(
            ["rg", "-n", "-i", token, *scan_targets, "-g", "!**/__pycache__/**", "-g", "!**/*.pyc"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "", msg=f"{token}\n{completed.stdout}")
```

- [ ] **Step 3: Run the new gates and confirm they fail**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_removed_dashboard_and_skill_create_surfaces_are_absent -q
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_removed_dashboard_and_skill_create_names_are_not_referenced -q
```

Expected:

- both fail because the stale files and references still exist.

### Task 2: Remove Dashboard Files And Dashboard-Only Tests

**Files:**

- Delete: `scripts/serve_context_panel.py`
- Delete: `framework/console/index.html`
- Delete: `framework/console/app.js`
- Delete: `framework/console/styles.css`
- Delete: `framework/contracts/workspace-projection.json`
- Delete: `scripts/workspace_data.py`
- Delete: `scripts/runtime_store/projections.py`
- Delete: `tests/test_console_app_contract.py`
- Delete: `tests/test_parallel_contracts.py`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Delete dashboard files**

Use `apply_patch` delete hunks for the files listed above.

- [ ] **Step 2: Remove Context Panel docs**

In `README.md`, delete the section:

````markdown
## Context Panel

```bash
python3 scripts/serve_context_panel.py
```

Open `http://127.0.0.1:8765/` and click `Refresh workspace`.
````

In `README.md`, delete this runtime source bullet:

```markdown
- `framework/contracts/workspace-projection.json` for context panel workspace projection shape.
```

In `AGENTS.md`, delete:

```markdown
- Context panel: `python3 scripts/serve_context_panel.py`
```

- [ ] **Step 3: Remove repo consistency dashboard assumptions**

In `tests/test_repo_consistency.py`, remove `framework/console/app.js` from the `_scan` targets list.

Delete the full method:

```python
def test_workspace_projection_contract_uses_track_page_shape(self) -> None:
    ...
```

- [ ] **Step 4: Run dashboard-focused tests**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected:

- repo consistency passes or only fails on skill-create/importer references that will be removed in Task 4.

### Task 3: Remove Dashboard Projection Dependency From Memory Removal Test

**Files:**

- Modify: `tests/test_memory_removal_contract.py`

- [ ] **Step 1: Remove dashboard projection import**

Delete:

```python
import workspace_data  # noqa: E402
```

- [ ] **Step 2: Replace projection-based assertion**

Replace:

```python
def test_workspace_projection_and_cleanup_ignore_old_memory_files(self) -> None:
    runtime_manifest = self._copy_manifest_into_runtime()
    self._write_old_memory_file(memory_id="mem-old-projection", buddy="pm")

    projection = workspace_data.build_workspace_data()
    self.assertNotIn("memories", projection)
    self.assertNotIn("handoffs", projection)

    cleanup_plan = env_cleanup.build_cleanup_plan(
        scope="all-data",
        buddy=None,
        repo_root=self.runtime_root,
        manifest_path=runtime_manifest,
    )
    self.assertNotIn("memory_object_ids", cleanup_plan)
    self.assertNotIn("handoff_object_ids", cleanup_plan)
```

with:

```python
def test_cleanup_ignores_old_memory_files(self) -> None:
    runtime_manifest = self._copy_manifest_into_runtime()
    self._write_old_memory_file(memory_id="mem-old-projection", buddy="pm")

    cleanup_plan = env_cleanup.build_cleanup_plan(
        scope="all-data",
        buddy=None,
        repo_root=self.runtime_root,
        manifest_path=runtime_manifest,
    )
    self.assertNotIn("memory_object_ids", cleanup_plan)
    self.assertNotIn("handoff_object_ids", cleanup_plan)
```

- [ ] **Step 3: Run focused memory removal tests**

Run:

```bash
python3 -m pytest tests/test_memory_removal_contract.py -q
```

Expected:

- pass.

### Task 4: Remove Skill Create / Importer Surface

**Files:**

- Delete: `scripts/skill_creator_importer.py`
- Delete: `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- Delete: `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- Delete: `tests/test_skill_creator_importer.py`
- Delete: `tests/fixtures/community-skills/dev-summary/SKILL.md`
- Modify: `buddyswitch/manifest.toml`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Delete importer files and tests**

Use `apply_patch` delete hunks for all listed importer files. Remove empty directories left by those deletes.

- [ ] **Step 2: Remove importer manifest registration**

In `buddyswitch/manifest.toml`, delete:

```toml
[[skills]]
id = "skill-creator-importer"
path = "buddyswitch/skills/dev/skill-creator-importer"
```

In the Dev buddy `skills = [` list, delete:

```toml
  "skill-creator-importer",
```

- [ ] **Step 3: Update runtime skill tests**

In `tests/test_runtime_skills.py`, change:

```python
self.assertIn("skill-creator-importer", dev_skills)
```

to:

```python
self.assertNotIn("skill-creator-importer", dev_skills)
```

Change:

```python
expected = set(self.DEV_PRODUCT_SKILLS) | self.SHARED_RUNTIME_TOOL_SKILLS | {"skill-creator-importer"}
```

to:

```python
expected = set(self.DEV_PRODUCT_SKILLS) | self.SHARED_RUNTIME_TOOL_SKILLS
```

- [ ] **Step 4: Update launcher materialization test**

In `tests/test_buddyswitch_launcher.py`, replace:

```python
self.assertTrue((runtime_skills / "skill-creator-importer" / "SKILL.md").exists())
self.assertTrue(
    (runtime_skills / "skill-creator-importer" / "assets" / "skill-import-report-template.md").exists()
)
```

with:

```python
self.assertFalse((runtime_skills / "skill-creator-importer").exists())
```

- [ ] **Step 5: Run focused skill tests**

Run:

```bash
python3 -m pytest \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_dev_product_engineering_skill_chain_is_registered \
  tests/test_runtime_skills.py::RuntimeSkillsTests::test_runtime_skill_installer_materializes_expanded_dev_skill_set \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy \
  -q
```

Expected:

- pass.

### Task 5: Validate Protected Browser Cockpit Boundary

**Files:**

- No planned source changes.

- [ ] **Step 1: Scan retained browser cockpit surface**

Run:

```bash
rg -n 'browser_cockpit|chrome-devtools-cockpit' tools tests scripts buddyswitch framework README.md AGENTS.md
```

Expected:

- hits remain in `tools/launcher/browser_cockpit.sh`
- hits remain in `tests/test_browser_cockpit_launcher.py`
- hits remain in launcher/config/search/market/design paths that use browser runtime capability

- [ ] **Step 2: Run browser cockpit tests**

Run:

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py -q
```

Expected:

- pass.

### Task 6: Full Verification

**Files:**

- No planned source changes unless verification exposes a real broken reference.

- [ ] **Step 1: Run focused removal and lifecycle tests**

Run:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py \
  tests/test_memory_removal_contract.py \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  -q
```

Expected:

- pass.

- [ ] **Step 2: Run app-server service-mode regression tests**

Run:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_cleanup_system.py tests/test_runtime_broker.py -q
```

Expected:

- pass.

- [ ] **Step 3: Run deleted-surface residual scans**

Run:

```bash
rg -n -i 'Context Panel|serve_context_panel|workspace-projection|framework/console|dashboard' AGENTS.md README.md scripts tests framework buddyswitch tools
rg -n 'skill-creator-importer|skill_creator_importer|community-skills|skill creator|skill create|Import a Codex-native skill' AGENTS.md README.md scripts tests buddyswitch tools framework
```

Expected:

- no output.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git diff --stat
git diff -- AGENTS.md README.md buddyswitch/manifest.toml tests/test_repo_consistency.py tests/test_memory_removal_contract.py tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py
```

Expected:

- diff deletes only the planned stale surfaces
- diff keeps browser cockpit, app-server, runtime skills installer, and env context tool intact

## Implementation Notes

- Use `apply_patch` for all manual edits and deletes.
- Do not edit `buddyswitch/objects/**`.
- Do not edit `buddyswitch/local/buddybox/**`.
- Do not touch `tools/launcher/browser_cockpit.sh` unless a test failure proves an unrelated existing issue.
- Do not replace the deleted dashboard with a new dashboard placeholder.
- Do not replace `skill-creator-importer` with a renamed compatibility skill.

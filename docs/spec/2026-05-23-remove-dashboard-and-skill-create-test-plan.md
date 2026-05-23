# Remove Legacy Dashboard And Skill Create Test Plan

Date: 2026-05-23

## Test Goal

Prove BuddySwitch no longer exposes or maintains the old Context Panel dashboard and skill-create/importer surfaces, while preserving the current app-server service mode, browser cockpit, runtime skill installation, and env context tool paths.

Tests must validate real removal behavior. Do not make tests pass by renaming deleted concepts into new compatibility wrappers.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Context Panel server script is deleted and no command/documentation points users to it. |
| FR2 | Context Panel static UI assets are deleted. |
| FR3 | Workspace projection contract and its dashboard-only projection facade are deleted. |
| FR4 | Tests that only validate the deleted dashboard are removed. |
| FR5 | Remaining runtime tests no longer import `workspace_data` or `runtime_store.projections`. |
| FR6 | Memory/handoff removal tests keep proving old memory/handoff runtime surfaces are gone without depending on dashboard projection. |
| FR7 | Repo consistency rejects reintroducing Context Panel/dashboard files or references. |
| FR8 | `browser_cockpit` and `chrome-devtools-cockpit` runtime behavior remains in place and tested. |
| FR9 | Skill-create/importer script and skill package are deleted. |
| FR10 | Dev buddy manifest no longer registers or materializes `skill-creator-importer`. |
| FR11 | Skill importer tests and community-skill fixture are deleted. |
| FR12 | Runtime skills still install for all buddies from manifest after importer removal. |
| FR13 | Launcher start still materializes Dev runtime skills except the deleted importer. |
| FR14 | Repo consistency rejects reintroducing skill-create/importer references. |
| FR15 | No changes write directly to `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**`. |

## Coverage Matrix

| Requirement | Primary Verification |
| --- | --- |
| FR1 | `rg` scans in repo consistency and manual final scan. |
| FR2 | Deleted file assertions in repo consistency and absence from `rg --files`. |
| FR3 | Deleted file assertions and import scan for `workspace_data` / `runtime_store.projections`. |
| FR4 | `rg --files tests` proves dashboard-only tests are gone. |
| FR5 | `python3 -m pytest tests/test_memory_removal_contract.py tests/test_repo_consistency.py -q`. |
| FR6 | Updated `tests/test_memory_removal_contract.py` keeps tool registry, dispatch, source_ref, and cleanup assertions. |
| FR7 | New repo consistency test for forbidden dashboard tokens and paths. |
| FR8 | Existing `tests/test_browser_cockpit_launcher.py` plus launcher tests. |
| FR9 | Deleted file assertions and forbidden token scan. |
| FR10 | `tests/test_runtime_skills.py` manifest and runtime installer assertions. |
| FR11 | `rg --files` absence checks. |
| FR12 | Full `tests/test_runtime_skills.py`. |
| FR13 | Focused `tests/test_buddyswitch_launcher.py` runtime skill materialization tests. |
| FR14 | New repo consistency test for forbidden importer tokens and paths. |
| FR15 | Existing repo consistency direct-runtime-write guard plus final scan. |

## Test Changes

### 1. Repo Consistency Removal Gates

Modify:

- `tests/test_repo_consistency.py`

Add a test that fails before deletion:

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

Add a scan-based guard:

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

Keep the existing browser cockpit references out of this forbidden list. `chrome-devtools-cockpit` is still valid.

Run before implementation:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_removed_dashboard_and_skill_create_surfaces_are_absent -q
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_removed_dashboard_and_skill_create_names_are_not_referenced -q
```

Expected before implementation: fail on existing files and references.

Expected after implementation: pass.

### 2. Memory Removal Contract Without Dashboard Projection

Modify:

- `tests/test_memory_removal_contract.py`

Remove:

```python
import workspace_data  # noqa: E402
```

Replace the dashboard projection part of `test_workspace_projection_and_cleanup_ignore_old_memory_files` with a cleanup-only test:

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

Keep these existing tests unchanged:

- `test_tool_registry_status_and_help_exclude_memory_and_handoff`
- `test_env_tool_memory_or_handoff_request_is_rejected`
- `test_source_refs_reject_memory_and_handoff_type`

Run:

```bash
python3 -m pytest tests/test_memory_removal_contract.py -q
```

Expected: pass after dashboard projection removal.

### 3. Runtime Skill Tests Without Importer

Modify:

- `tests/test_runtime_skills.py`

Update `test_dev_product_engineering_skill_chain_is_registered`:

```python
self.assertNotIn("skill-creator-importer", dev_skills)
```

Update `test_runtime_skill_installer_materializes_expanded_dev_skill_set`:

```python
expected = set(self.DEV_PRODUCT_SKILLS) | self.SHARED_RUNTIME_TOOL_SKILLS
```

Keep assertions that Dev startup skills and shared runtime tool skills are installed. Do not remove `scripts/runtime_skills.py` or normal skill package assertions.

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_dev_product_engineering_skill_chain_is_registered -q
python3 -m pytest tests/test_runtime_skills.py::RuntimeSkillsTests::test_runtime_skill_installer_materializes_expanded_dev_skill_set -q
```

Expected before implementation: fail because manifest still includes importer.

Expected after implementation: pass.

### 4. Launcher Runtime Skill Materialization

Modify:

- `tests/test_buddyswitch_launcher.py`

In `test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy`, replace importer presence assertions with absence assertions:

```python
self.assertFalse((runtime_skills / "skill-creator-importer").exists())
```

Keep all other service-mode start and materialization assertions.

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_instance_start_materializes_runtime_skills_from_manifest_for_each_buddy -q
```

Expected before implementation: fail because importer is still materialized.

Expected after implementation: pass.

### 5. Delete Obsolete Test Files

Delete these tests because they only validate removed surfaces:

- `tests/test_console_app_contract.py`
- `tests/test_parallel_contracts.py`
- `tests/test_skill_creator_importer.py`

After deletion, prove no test runner references remain:

```bash
rg -n 'test_console_app_contract|test_parallel_contracts|test_skill_creator_importer' tests README.md AGENTS.md
```

Expected:

- no output

### 6. Browser Cockpit Protection Tests

Do not modify browser cockpit tests except for unrelated baseline failures discovered during verification.

Run:

```bash
python3 -m pytest tests/test_browser_cockpit_launcher.py -q
```

Expected: pass.

Run launcher service-mode tests that cover browser cockpit lifecycle integration:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected: pass.

### 7. Final Residual Scans

Run:

```bash
rg -n -i 'Context Panel|serve_context_panel|workspace-projection|framework/console|dashboard' AGENTS.md README.md scripts tests framework buddyswitch tools
rg -n 'skill-creator-importer|skill_creator_importer|community-skills|skill creator|skill create|Import a Codex-native skill' AGENTS.md README.md scripts tests buddyswitch tools framework
```

Expected:

- no output
- archival references remain only in `docs/spec/2026-05-23-remove-dashboard-and-skill-create-*.md`

Run protected-retention scan:

```bash
rg -n 'browser_cockpit|chrome-devtools-cockpit' tools tests scripts buddyswitch framework README.md AGENTS.md
```

Expected:

- Valid hits remain in browser cockpit launcher/tests, search env tools, Codex config expectations, and market/design skill guidance.

## Final Verification Commands

Run focused removal tests:

```bash
python3 -m pytest \
  tests/test_repo_consistency.py \
  tests/test_memory_removal_contract.py \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  -q
```

Run app-server service-mode regression tests:

```bash
python3 -m pytest tests/test_app_server_client.py tests/test_cleanup_system.py tests/test_runtime_broker.py -q
```

Run repo-wide relevant scan:

```bash
rg -n -i 'Context Panel|serve_context_panel|workspace-projection|framework/console|dashboard' AGENTS.md README.md scripts tests framework buddyswitch tools
rg -n 'skill-creator-importer|skill_creator_importer|community-skills|skill creator|skill create|Import a Codex-native skill' AGENTS.md README.md scripts tests buddyswitch tools framework
```

Expected final state:

- all tests pass
- deleted-surface scans return no output outside archival spec docs
- browser cockpit scans still show the expected retained runtime surface

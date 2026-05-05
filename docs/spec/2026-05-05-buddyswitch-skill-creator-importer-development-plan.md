# BuddySwitch Skill Creator Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a forward-only importer that turns an external Codex-native skill package into a repo-registered BuddySwitch skill with BuddySwitch persist guidance.

**Architecture:** Add one deterministic Python importer script plus one native Dev buddy skill wrapper that invokes it. The importer copies a source Codex skill package into `buddyswitch/skills/<buddy>/<skill-id>/`, appends BuddySwitch persist closing rules to the generated `SKILL.md`, and updates `buddyswitch/manifest.toml`; runtime materialization, `prepare`, and `persist` remain unchanged.

**Tech Stack:** Python standard library, TOML manifest parsing through existing `scripts/env_manifest.py`, Markdown skill packages, JSON result templates, `unittest`/`pytest`.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout for this task.

## Preflight Gate

Target outcome and bottleneck:

- Outcome: a developer can import an external Codex-native skill into BuddySwitch with one deterministic command and make it available to the selected buddy after normal instance start/open/sync materialization.
- Current bottleneck: dev0210 has the runtime boundary needed for community packages, but no creator/importer implementation exists; the historical memo still contains stale package-compatibility language that can misdirect implementation.
- Verifiable improvement: an imported skill package appears under `buddyswitch/skills/<buddy>/<skill-id>/`, is registered in `buddyswitch/manifest.toml`, materializes into `.agents/skills/<skill-id>`, and can persist a minimally writable result under its native `skill_id`.

Confirmed facts from current dev0210:

- `buddyswitch/skills/**` first-party packages are Codex-native `SKILL.md` packages and no longer use `skill.toml`.
- `scripts/runtime_skills.py` treats source packages as opaque content and validates only copy boundaries.
- `scripts/env_manifest.py` validates BuddySwitch registration fields and buddy membership; it does not validate package contents or source readiness.
- `scripts/turn_runtime.py persist` validates selected skill membership, non-empty `output_slot`, minimum writable result shape, and PM track-effect safety; it does not require full schema completeness.
- `framework/docs/skill-runtime-shared-rules.md` states that Codex CLI owns package acceptance after `.agents/skills/<skill-id>` materialization.
- `docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md` still uses stale wording such as `BuddySwitch-compatible`, `transform`, and `package-format gatekeeping`.

Open assumptions and invalidators:

- Assumption: importer input is a Codex-native source package containing a `SKILL.md` with usable frontmatter; importing a package without `SKILL.md` is out of scope because the importer must generate a Codex-executable skill.
- Assumption: the generated manifest `output_schema` is selected by target buddy and the generated `output_slot` defaults to the generated `skill_id`.
- Assumption: the importer skill itself belongs to the `dev` buddy because it changes BuddySwitch source and manifest state.
- Assumption: a generated skill becomes available through existing instance start/open/sync materialization; active Codex sessions are not hot-reloaded.
- Invalidator: if product direction changes back to accepting arbitrary community output through a runtime adapter, stop because that reintroduces a historical compatibility layer.
- Invalidator: if the importer must synchronize already-running sessions live, stop and split that lifecycle feature into a separate task.
- Invalidator: if a marketplace/package-sync system is requested, stop and split it; this task imports one local source package at a time.

Permissions and boundaries:

- Use normal workspace writes inside `.worktrees/dev0210`.
- Do not run destructive git commands.
- Do not add a runtime bridge, compatibility adapter, fallback converter, transcript parser, dual manifest format, or `skill.toml` metadata reader.
- Do not change `scripts/runtime_skills.py`, `scripts/turn_runtime.py`, or runtime gate semantics unless a test proves the existing current boundary is insufficient.
- Do not introduce a plugin system, package registry, background sync daemon, or live reload mechanism.

Verification plan and stop condition:

- Stop when tests prove source import, generated package shape, manifest registration, materialization, persist integration, docs, and no-history-residue constraints.
- Completion requires fresh output from the final verification commands in Task 7.

## Target Behavior

Command shape:

```bash
python3 scripts/skill_creator_importer.py \
  --source /path/to/community-skill \
  --buddy dev \
  --skill-id dev-summary
```

Input contract:

- `--source` may point to a source skill package directory containing `SKILL.md` or directly to a `SKILL.md` file.
- `--buddy` must be exactly one of the current manifest buddy ids: `pm`, `dev`, `test`, `market`, `design`.
- `--skill-id` is optional only when the source `SKILL.md` frontmatter has a usable `name`; the generated id must match `^[a-z][a-z0-9-]*$`.
- Source `SKILL.md` must have a non-empty `description` frontmatter value so the generated package remains Codex-native.
- Non-retired source package contents are copied as package content; arbitrary files, `agents/openai.yaml`, `assets/`, `references/`, `scripts/`, and symlink objects are preserved.
- The importer must drop `skill.toml` from generated BuddySwitch source packages. Runtime materialization stays opaque, but the source generator must not carry retired metadata into first-party skill packages.
- The importer may read `SKILL.md` to derive `name`, confirm `description`, and append BuddySwitch closing rules. It must not inspect arbitrary package files to decide runtime acceptability.

Generated package:

```text
buddyswitch/skills/<buddy>/<skill-id>/
  SKILL.md
  ...copied non-retired source package content...
```

Generated `SKILL.md` must preserve source text and append this section, filled with the concrete buddy, skill id, output slot, and schema path:

```markdown
## BuddySwitch Runtime Closing Rules

- Emit BuddySwitch buddy-level result JSON directly.
- Persist with `scripts/turn_runtime.py persist --skill-id <skill-id>` using this same native skill id.
- Use top-level keys `execution_summary`, `working_notes`, `deliverables_or_changed_files`, and `artifact_content`.
- Keep `execution_summary` a non-empty string.
- Keep `artifact_content` an object.
- Keep `working_notes` and `deliverables_or_changed_files` as lists when present.
- Use buddy-level schema guidance from `<schema-path>`; runtime persist requires only the write-safety minimum unless a field is needed for safe writes.
- Do not call a result bridge, transcript parser, compatibility wrapper, or legacy markdown output path.
```

Manifest registration:

```toml
[[skills]]
id = "<skill-id>"
path = "buddyswitch/skills/<buddy>/<skill-id>"
produces_artifact = true
output_slot = "<skill-id>"
output_schema = "<buddy-result-schema>"
```

Buddy result schema map:

```python
{
    "pm": "framework/schemas/pm/pm-result.json",
    "dev": "framework/schemas/dev/dev-result.json",
    "test": "framework/schemas/test/test-result.json",
    "market": "framework/schemas/market/market-result.json",
    "design": "framework/schemas/design/design-result.json",
}
```

The importer skill itself is a Dev buddy skill:

```toml
[[skills]]
id = "skill-creator-importer"
path = "buddyswitch/skills/dev/skill-creator-importer"
produces_artifact = true
output_slot = "skill-import-report"
output_schema = "framework/schemas/dev/dev-result.json"
```

Add `skill-creator-importer` to the `dev` buddy skill list after `implement-task`.

## File Map

Create:

- `scripts/skill_creator_importer.py`
- `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- `tests/test_skill_creator_importer.py`

Modify:

- `buddyswitch/manifest.toml`
- `docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_turn_runtime.py`

Do not modify:

- `scripts/runtime_skills.py`
- `scripts/turn_runtime.py`
- `scripts/result_bridge.py` because it must remain absent
- `buddyswitch/skills/**/skill.toml` because it must remain absent from first-party packages

## Implementation Tasks

### Task 1: Update The Memo To Current Boundary

**Files:**

- Modify: `docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md`

- [ ] **Step 1: Replace stale package-compatibility language**

Replace phrases that imply runtime package-format compatibility work:

```text
Generate a BuddySwitch-compatible skill package under the repo.
```

with:

```text
Generate a repo-registered Codex-native skill package with BuddySwitch persist guidance.
```

Replace:

```text
transform an external skill into a repo-native BuddySwitch skill package
```

with:

```text
copy an external Codex-native skill package into the BuddySwitch repo and add BuddySwitch persist closing rules
```

- [ ] **Step 2: Update the non-goal list**

Remove the stale non-goal:

```text
solving all package-format gatekeeping concerns recorded in `2026-05-03-community-skill-package-validation-memo.md`
```

Add:

```text
- reopening runtime package-format gatekeeping, which is already closed by the 2026-05-05 runtime gate trimming boundary;
- adapting arbitrary community output through a runtime bridge, wrapper, transcript parser, or fallback converter.
```

- [ ] **Step 3: Update the instance synchronization boundary**

Change the instance note so it reflects current launcher behavior:

```text
An imported skill appears in runtime `.agents/skills` after an instance workspace is created or explicitly refreshed by the existing launcher open/sync/start materialization path. Already-running Codex sessions are not hot-reloaded by this task.
```

- [ ] **Step 4: Run the memo residue check**

Run:

```bash
rg -n "BuddySwitch-compatible|package-format gatekeeping|runtime interception|result_bridge|selected_skill_packet|skill.toml" docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md
```

Expected: no matches for `BuddySwitch-compatible`, `package-format gatekeeping`, `runtime interception`, `result_bridge`, or `selected_skill_packet`. A `skill.toml` match is allowed only if it is in a sentence saying the importer does not read or create `skill.toml`.

### Task 2: Lock Importer Behavior With Red Tests

**Files:**

- Create: `tests/test_skill_creator_importer.py`

- [ ] **Step 1: Add source package and manifest helpers**

Create `tests/test_skill_creator_importer.py` with helpers that write a minimal temp repo, manifest, and external package. The temp repo must contain:

```text
<temp-repo>/buddyswitch/manifest.toml
<temp-repo>/buddyswitch/skills/
<temp-repo>/framework/schemas/dev/dev-result.json
<temp-repo>/framework/schemas/pm/pm-result.json
<temp-repo>/framework/schemas/test/test-result.json
<temp-repo>/framework/schemas/market/market-result.json
<temp-repo>/framework/schemas/design/design-result.json
```

Use `unittest.TestCase` and import the future module with:

```python
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import skill_creator_importer  # noqa: E402
```

- [ ] **Step 2: Add the success test**

Add `test_imports_codex_skill_package_and_registers_target_buddy`:

- Source package contains `SKILL.md`, `assets/example.md`, `references/notes.md`, and `scripts/helper.sh`.
- Run `skill_creator_importer.import_skill(source=source_dir, buddy_id="dev", skill_id="dev-summary", repo_root=temp_repo)`.
- Assert `buddyswitch/skills/dev/dev-summary/SKILL.md` exists.
- Assert copied files exist under the generated package.
- Assert generated `SKILL.md` still contains the source workflow heading.
- Assert generated `SKILL.md` contains `BuddySwitch Runtime Closing Rules`.
- Assert generated `SKILL.md` contains `persist --skill-id dev-summary`.
- Assert manifest contains a `[[skills]]` entry with `id = "dev-summary"`, `path = "buddyswitch/skills/dev/dev-summary"`, `produces_artifact = true`, `output_slot = "dev-summary"`, and `output_schema = "framework/schemas/dev/dev-result.json"`.
- Assert the `dev` buddy skill list contains `dev-summary`.

- [ ] **Step 3: Add deterministic id tests**

Add:

- `test_import_derives_skill_id_from_frontmatter_name`
- `test_import_rejects_invalid_skill_id_without_writes`
- `test_import_rejects_duplicate_skill_id_without_writes`

Each negative test must snapshot the temp repo manifest bytes and target package existence before calling `import_skill(...)`, then assert both are unchanged after failure.

- [ ] **Step 4: Add source contract tests**

Add:

- `test_import_accepts_direct_skill_md_file`
- `test_import_rejects_missing_skill_md_without_writes`
- `test_import_rejects_missing_description_frontmatter_without_writes`
- `test_import_preserves_symlink_objects`
- `test_import_drops_skill_toml_from_generated_package`

The symlink test must assert that a copied symlink remains a symlink and has the same link target text.

The `skill.toml` test must assert that a source package containing `skill.toml` imports successfully, that generated `SKILL.md` is valid, and that `buddyswitch/skills/<buddy>/<skill-id>/skill.toml` does not exist.

- [ ] **Step 5: Add manifest validity tests**

Add:

- `test_imported_manifest_loads_with_env_manifest`
- `test_import_rejects_unknown_buddy_without_writes`

Use existing `env_manifest.load_manifest(imported_manifest_path)` to prove the generated manifest is valid after import.

- [ ] **Step 6: Run the red importer tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_skill_creator_importer.py -q
```

Expected before implementation: fail because `scripts/skill_creator_importer.py` does not exist.

### Task 3: Implement The Importer Script

**Files:**

- Create: `scripts/skill_creator_importer.py`

- [ ] **Step 1: Add constants and result types**

Create the module with:

```python
#!/usr/bin/env python3
"""Import a Codex-native skill package into BuddySwitch source."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from env_manifest import DEFAULT_MANIFEST, ManifestError, load_manifest, require_buddy


ROOT = Path(__file__).resolve().parents[1]
SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
BUDDY_OUTPUT_SCHEMAS = {
    "pm": "framework/schemas/pm/pm-result.json",
    "dev": "framework/schemas/dev/dev-result.json",
    "test": "framework/schemas/test/test-result.json",
    "market": "framework/schemas/market/market-result.json",
    "design": "framework/schemas/design/design-result.json",
}


class SkillImportError(ValueError):
    """Raised when a skill import request is invalid or cannot be applied safely."""


@dataclass(frozen=True)
class ImportResult:
    skill_id: str
    buddy_id: str
    package_path: str
    manifest_path: str
    output_slot: str
    output_schema: str
```

- [ ] **Step 2: Implement source normalization**

Add functions:

- `_normalize_source(source: Path) -> tuple[Path, bool]`, where the boolean is `True` when the input is a direct `SKILL.md` file.
- `_read_skill_md(source_root: Path, direct_skill_file: bool) -> str`.
- `_frontmatter_value(skill_text: str, key: str) -> str | None`.
- `_derive_skill_id(explicit: str | None, skill_text: str, source: Path) -> str`.
- `_validate_skill_id(skill_id: str) -> str`.

Rules:

- direct file input must have name `SKILL.md`;
- directory input must contain `SKILL.md`;
- explicit `--skill-id` wins over frontmatter;
- frontmatter `name` wins over source directory name;
- derived ids are lowercased, whitespace and underscores become hyphens, repeated hyphens collapse, and invalid characters are removed;
- final id must match `^[a-z][a-z0-9-]*$`.

- [ ] **Step 3: Implement package staging**

Add `_copy_source_package(source: Path, direct_skill_file: bool, staging_dir: Path) -> Path`.

Rules:

- direct file input creates `staging_dir / "SKILL.md"`;
- directory input copies all package content into `staging_dir`;
- use `shutil.copytree(..., symlinks=True)` for directory input;
- do not reject arbitrary package files;
- do not read, copy, or write `skill.toml`;
- fail if `staging_dir` already exists.

- [ ] **Step 4: Implement BuddySwitch closing rules**

Add `_append_buddyswitch_rules(skill_md: Path, *, skill_id: str, buddy_id: str, output_schema: str) -> None`.

Append exactly this section with concrete values:

```markdown

## BuddySwitch Runtime Closing Rules

- Target BuddySwitch buddy: `<buddy-id>`.
- Emit BuddySwitch buddy-level result JSON directly.
- Persist with `scripts/turn_runtime.py persist --skill-id <skill-id>` using this same native skill id.
- Use top-level keys `execution_summary`, `working_notes`, `deliverables_or_changed_files`, and `artifact_content`.
- Keep `execution_summary` a non-empty string.
- Keep `artifact_content` an object.
- Keep `working_notes` and `deliverables_or_changed_files` as lists when present.
- Use buddy-level schema guidance from `<schema-path>`; runtime persist requires only the write-safety minimum unless a field is needed for safe writes.
- Do not call a result bridge, transcript parser, compatibility wrapper, or legacy markdown output path.
```

- [ ] **Step 5: Implement manifest serialization**

Add:

- `_manifest_without_runtime_keys(manifest: dict[str, Any]) -> dict[str, Any]`
- `_skill_entry(...) -> dict[str, Any]`
- `_serialize_manifest(manifest: dict[str, Any]) -> str`
- `_register_skill(manifest: dict[str, Any], *, skill_id: str, buddy_id: str, output_schema: str) -> dict[str, Any]`

Serialization rules:

- keep `schema_version` and `[env]`;
- write all `[[skills]]` entries first, in current order plus the imported skill appended;
- ignore runtime-added `persistence` keys when serializing;
- write all `[[buddies]]` entries in current order;
- keep single-line `skills = [...]` for buddy lists with one or two skills;
- use multiline `skills = [` format for lists with more than two skills;
- write `permissions` as the current manifest does, using multiline only when more than three permissions exist.

Registration rules:

- fail if manifest already has `skill_id`;
- fail if target buddy is unknown;
- add generated skill to exactly the selected buddy;
- set `output_slot = skill_id`;
- set `produces_artifact = true`;
- set `output_schema` from `BUDDY_OUTPUT_SCHEMAS[buddy_id]`.

- [ ] **Step 6: Implement transaction-safe import**

Add:

```python
def import_skill(
    *,
    source: Path,
    buddy_id: str,
    skill_id: str | None = None,
    repo_root: Path = ROOT,
    manifest_path: Path | None = None,
) -> ImportResult:
```

Write order:

1. load manifest;
2. validate buddy and skill id;
3. compute target path;
4. fail if target path exists;
5. create staging directory under the target parent with `tempfile.mkdtemp(prefix=f".{skill_id}.import-", dir=target_parent)`;
6. copy source into staging directory;
7. append BuddySwitch rules to staging `SKILL.md`;
8. create updated manifest text and validate it with `load_manifest(temp_manifest_path)`;
9. rename staging directory to final target with `os.replace`;
10. replace manifest with updated text using `os.replace`;
11. on any exception after staging creation, remove staging and final target if they were created by this import, and restore original manifest bytes.

- [ ] **Step 7: Implement CLI**

CLI arguments:

```text
--source PATH      required
--buddy BUDDY      required
--skill-id ID      optional
--manifest PATH    optional, defaults to buddyswitch/manifest.toml
--repo-root PATH   optional, defaults to current source checkout root
```

Success output is JSON:

```json
{
  "ok": true,
  "skill_id": "dev-summary",
  "buddy_id": "dev",
  "package_path": "buddyswitch/skills/dev/dev-summary",
  "manifest_path": "buddyswitch/manifest.toml",
  "output_slot": "dev-summary",
  "output_schema": "framework/schemas/dev/dev-result.json"
}
```

Failure output goes to stderr as:

```text
ERROR: <message>
```

Return code is `0` on success and `1` on validation or write failure.

- [ ] **Step 8: Run importer tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_skill_creator_importer.py -q
```

Expected after implementation: pass.

### Task 4: Add The Dev Skill Wrapper And Register It

**Files:**

- Create: `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- Create: `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- Modify: `buddyswitch/manifest.toml`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Create the skill package**

Create `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`:

```markdown
---
name: skill-creator-importer
description: Use when importing an external Codex-native skill package into BuddySwitch source and registering it for a target buddy.
---

# skill-creator-importer

## Purpose
- Import one external Codex-native skill package into BuddySwitch source as a repo-registered skill.

## Use when
- The user provides or references an external Codex skill package or `SKILL.md`.
- The user wants the skill available to one BuddySwitch buddy: `pm`, `dev`, `test`, `market`, or `design`.
- The task is about registering the skill for future normal runtime materialization.

## Do Not Use When
- The request asks to hot-reload an already-running Codex session.
- The request asks to parse Codex transcripts or wrap arbitrary community output.
- The request asks to build a marketplace, sync daemon, package registry, or runtime adapter.

## Steps
1. Confirm the target buddy and source package path.
2. Run `python3 scripts/skill_creator_importer.py --source <source> --buddy <buddy>` from the BuddySwitch source checkout, adding `--skill-id <id>` when the intended id must be explicit.
3. Inspect the generated package and `buddyswitch/manifest.toml` diff.
4. Run importer, manifest, runtime materialization, and repo consistency tests.
5. Report the imported skill id, target buddy, package path, manifest registration, and verification output.

## Shared Runtime Rules
- See `framework/docs/skill-runtime-shared-rules.md`.
- Emit buddy-level Dev result JSON directly and persist with `persist --skill-id skill-creator-importer`.
- Do not call `result_bridge`, transcript parsing, compatibility wrappers, or legacy markdown output paths.

## Required Output Fields
Top-level envelope keys:
- `execution_summary`
- `working_notes`
- `deliverables_or_changed_files`
- `artifact_content`

Buddy-specific fields inside `artifact_content`:
- `task_summary`
- `changed_files`
- `implementation_notes`
- `verification`
- `risks`
- `follow_ups`
```

- [ ] **Step 2: Create the report template**

Create `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md` with valid Dev result JSON containing:

```json
{
  "execution_summary": "Imported a Codex-native skill package into BuddySwitch.",
  "working_notes": [],
  "deliverables_or_changed_files": [
    "buddyswitch/skills/<buddy>/<skill-id>/SKILL.md",
    "buddyswitch/manifest.toml"
  ],
  "artifact_content": {
    "task_summary": "Imported and registered one external Codex-native skill package.",
    "changed_files": [
      "buddyswitch/skills/<buddy>/<skill-id>/SKILL.md",
      "buddyswitch/manifest.toml"
    ],
    "implementation_notes": [
      "The generated package preserves the original workflow and adds BuddySwitch persist closing rules.",
      "The manifest registers the skill under the selected buddy with a buddy-level output schema."
    ],
    "verification": [
      "Importer tests passed.",
      "Runtime materialization tests passed.",
      "Repo consistency tests passed."
    ],
    "risks": [],
    "follow_ups": []
  }
}
```

- [ ] **Step 3: Register the wrapper skill**

Add the manifest entry shown in `Target Behavior` and change the Dev buddy list from:

```toml
skills = ["implement-task"]
```

to:

```toml
skills = ["implement-task", "skill-creator-importer"]
```

- [ ] **Step 4: Update repo consistency constants**

In `tests/test_repo_consistency.py`, add `skill-creator-importer` to:

- `ARTIFACT_SKILL_DOCS`
- `ARTIFACT_SKILL_TO_BUDDY_RESULT_SCHEMA`
- `ARTIFACT_SKILL_TO_OUTPUT_SLOT`
- `ARTIFACT_TEMPLATE_SCHEMAS`

Use:

```python
"skill-creator-importer": "framework/schemas/dev/dev-result.json"
"skill-creator-importer": "skill-import-report"
```

and template path:

```python
ROOT / "buddyswitch" / "skills" / "dev" / "skill-creator-importer" / "assets" / "skill-import-report-template.md"
```

- [ ] **Step 5: Update hardcoded materialization expectations**

Run:

```bash
rg -n "implement-task|skill-creator-importer|dev buddy|dev.*skills" tests/test_buddyswitch_launcher.py tests/test_runtime_skills.py tests/test_env_manifest_v2.py tests/test_repo_consistency.py
```

Update any hardcoded live Dev buddy expectations so the expected Dev skill set is `implement-task` and `skill-creator-importer`.

- [ ] **Step 6: Run manifest and repo consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_repo_consistency.py -q
```

Expected: pass.

### Task 5: Prove Runtime Materialization And Persist Integration

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add imported package materialization coverage**

In `tests/test_runtime_skills.py`, add `test_imported_skill_package_materializes_after_registration`.

Test flow:

1. Create an external package in a temp directory under `ROOT`.
2. Use `skill_creator_importer.import_skill(...)` with `repo_root=temp_repo`.
3. Patch `runtime_skills.ROOT` to the temp repo.
4. Run `runtime_skills.install_runtime_skills(manifest_path=temp_manifest, buddy_id="dev", workspace=workspace)`.
5. Assert `.agents/skills/dev-summary/SKILL.md` exists.
6. Assert installed `SKILL.md` contains `BuddySwitch Runtime Closing Rules`.
7. Assert copied assets are present.

- [ ] **Step 2: Add imported skill persist coverage**

In `tests/test_turn_runtime.py`, add `test_imported_skill_id_persists_minimum_result_for_target_buddy`.

Test flow:

1. Use a temp manifest with `dev-summary` registered to Dev, `output_slot = "dev-summary"`, and `output_schema = "framework/schemas/dev/dev-result.json"`.
2. Prepare a Dev product context with existing test helpers.
3. Persist:

```json
{
  "execution_summary": "Saved imported skill summary.",
  "working_notes": [],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Saved imported skill summary.",
    "freeform": {
      "imported_skill": "dev-summary"
    }
  }
}
```

4. Assert receipt `skill_id == "dev-summary"`.
5. Assert artifact object `skill_id == "dev-summary"`.
6. Assert run audit `skill_id == "dev-summary"`.

- [ ] **Step 3: Add cross-buddy rejection coverage**

In `tests/test_turn_runtime.py`, add `test_imported_skill_id_rejects_wrong_buddy_without_writes`.

Test flow:

1. Use the same temp manifest registering `dev-summary` only to Dev.
2. Prepare a PM product context.
3. Snapshot runtime state.
4. Persist with `skill_id="dev-summary"`.
5. Assert persist fails.
6. Assert runtime state snapshot is unchanged.

- [ ] **Step 4: Add launcher materialization coverage**

In `tests/test_buddyswitch_launcher.py`, update the existing live manifest materialization test so Dev instances assert both:

```text
.agents/skills/implement-task/SKILL.md
.agents/skills/skill-creator-importer/SKILL.md
```

Do not add a separate launcher path or sync mechanism.

- [ ] **Step 5: Run focused runtime integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_turn_runtime.py tests/test_buddyswitch_launcher.py -q
```

Expected: pass.

### Task 6: Add Forward-Only Residue Guards

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add no-history assertions for importer docs and code**

Add a test named `test_skill_creator_importer_does_not_reintroduce_retired_runtime_paths`.

Scan:

- `scripts/skill_creator_importer.py`
- `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- `docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md`

Assert none contain:

- `result_bridge`
- `selected_skill_packet`
- `prepare_context.skills`
- `runtime interception`
- `compatibility wrapper`
- `fallback converter`
- `skill.toml` as an active input, copied package file, or output

- [ ] **Step 2: Add source package residue assertion**

Add or extend the existing `skill.toml` consistency test so:

```python
self.assertEqual(list((ROOT / "buddyswitch" / "skills").rglob("skill.toml")), [])
```

Expected: no first-party source package contains `skill.toml`.

- [ ] **Step 3: Run repo consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected: pass.

### Task 7: Final Verification

**Files:**

- All changed files from Tasks 1-6

- [ ] **Step 1: Compile the new script**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/skill_creator_importer.py
```

Expected: exits 0.

- [ ] **Step 2: Run focused importer suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_skill_creator_importer.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run runtime and manifest regression suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_turn_runtime.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Run residue scan**

Run:

```bash
rg -n "result_bridge|scripts/result_bridge.py|selected_skill_packet|prepare_context\\.skills|runtime interception|compatibility wrapper|fallback converter" scripts buddyswitch/skills framework/docs tools/launcher/assets/buddies docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md
```

Expected: no active implementation or active prompt/doc matches. Matches inside tests as negative assertions are allowed only in `tests/`.

- [ ] **Step 5: Check whitespace and git status**

Run:

```bash
git diff --check
git status --short --branch
```

Expected: `git diff --check` exits 0. `git status` shows only intentional files for this task.

## Acceptance Criteria

- `scripts/skill_creator_importer.py` imports one external Codex-native package into `buddyswitch/skills/<buddy>/<skill-id>/`.
- Generated `SKILL.md` preserves the source workflow and adds BuddySwitch persist closing rules.
- Generated manifest registration uses the target buddy schema and `output_slot = skill_id`.
- The Dev buddy has a registered `skill-creator-importer` skill package and report template.
- Imported packages materialize through existing `.agents/skills` runtime install.
- Imported skill ids can persist minimally writable results under their native id for the target buddy.
- Cross-buddy imported skill persist attempts fail before writes.
- No runtime bridge, `skill.toml` metadata reader, copied `skill.toml` source package residue, transcript parser, compatibility wrapper, fallback converter, live reload, or dual path is introduced.
- Verification commands in Task 7 pass with fresh output.

## Reviewer Rubric

- Does the importer solve repo registration and persist guidance without changing runtime gates?
- Does any code path inspect arbitrary package contents to decide runtime acceptability?
- Does any code path reintroduce `skill.toml`, `result_bridge`, `selected_skill_packet`, or transcript parsing?
- Does manifest update remain deterministic and safe on failure?
- Does verification prove package generation, manifest registration, runtime materialization, and persist behavior?
- Did scope stay limited to one-package import and the Dev skill wrapper?

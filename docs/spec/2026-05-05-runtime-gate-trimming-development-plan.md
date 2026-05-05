# Runtime Gate Trimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trim BuddySwitch runtime validation so each gate only checks conditions that can make the current chain run wrong or write bad state.

**Architecture:** Keep three narrow runtime gates: materialization validates copy boundaries, `prepare` validates turn context and reservation safety, and `persist` validates write safety. Remove Codex skill package content validation and content-quality schema gates from runtime paths; Codex CLI owns skill package acceptance, while BuddySwitch owns paths, registrations, context identity, and state writes.

**Tech Stack:** Python runtime scripts, TOML manifest parsing, JSON runtime state, Markdown docs, `unittest`/`pytest`.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit `/Users/chen/Dev/buddyswitch` main checkout for this task.

## Preflight Gate

Target outcome and bottleneck:

- Outcome: BuddySwitch no longer rejects community Codex skills or current product turns for checks that do not affect actual installation, turn preparation, or durable state writes.
- Current bottleneck: `load_manifest()` and `runtime_skills.py` still perform package-format admission checks, and `prepare`/`persist` inherit those checks even when they do not affect the current operation.
- Verifiable improvement: a community skill package with non-BuddySwitch metadata or unusual contents can materialize; `prepare` succeeds when only package/readiness metadata is invalid; `persist` accepts minimally writable result output while still rejecting stale, cross-buddy, or unsafe state writes.

Confirmed facts from current code:

- `scripts/env_manifest.py` parses `SKILL.md` frontmatter, rejects `skill.toml`, requires frontmatter `name` to match manifest skill id, and requires `description`.
- `scripts/runtime_skills.py` requires `SKILL.md`, rejects `skill.toml`, requires YAML frontmatter delimiters, rejects package content symlinks, and uses `shutil.copytree()` without preserving symlink objects.
- `scripts/turn_runtime.py prepare` calls `load_manifest()` and therefore inherits package/schema readiness failures before it builds turn context.
- `scripts/turn_runtime.py persist` calls `load_manifest()`, checks active buddy skill membership, validates the full selected output schema, validates PM track effects, and writes artifact/task/track/run state.
- The current product direction after the last two dev0210 updates is direct buddy-level result emission; there is no runtime bridge or wrapper that should be reintroduced for this task.

Open assumptions and invalidators:

- Assumption: Codex CLI, not BuddySwitch, decides whether a materialized `.agents/skills/<skill-id>` package is a valid Codex skill.
- Assumption: `output_schema` may remain as a development/documentation aid, but it must not block `prepare` and should not be a strict runtime `persist` content-quality gate.
- Assumption: `output_slot` remains runtime-critical because artifact ids, artifact slots, and receipts need it.
- Invalidator: if the product requires BuddySwitch to reject invalid Codex skill packages before Codex CLI sees them, stop because that reverses the agreed boundary.
- Invalidator: if strict buddy-level schema validation is required as a product write gate, stop and define the retry UX that lets Codex correct the payload after a failed `persist`.

Permissions and boundaries:

- Use normal workspace writes inside `.worktrees/dev0210`.
- Do not run destructive git commands.
- Do not add compatibility wrappers, old package shims, or a second materialization path.
- Do not add a generic workflow engine or broad validation framework.
- Do not infer track mutations from request text; keep explicit `state_effects.track_operation`.

Verification plan and stop condition:

- Stop when tests prove materialization, prepare, and persist each reject only chain-impacting failures.
- Completion requires fresh output from the final verification commands in Task 7.

## Target Runtime Boundaries

### Gate 1: Instance Startup / Skill Materialization

This gate answers only: "Can this active buddy's registered skill directories be copied into this runtime workspace without escaping source or target boundaries?"

Keep:

- active buddy exists in manifest;
- active buddy's skill ids reference manifest skill entries;
- skill id can safely be used as `.agents/skills/<skill-id>`;
- source path is repo-relative, resolves inside the repo, exists, and is a directory;
- runtime workspace exists and is not the source checkout root or filesystem root;
- target `.agents` and `.agents/skills` are not symlink write targets;
- copied package preserves opaque content instead of dereferencing external symlink targets.

Remove:

- `SKILL.md` existence checks;
- YAML frontmatter checks;
- `name` / `description` checks;
- `skill.toml` rejection;
- package content symlink rejection;
- any package file-content inspection.

### Gate 2: Prepare

This gate answers only: "Can this request produce a correct turn context and reservation?"

Keep:

- request text is non-empty;
- product-mode instance identity is complete and matches the instance JSON;
- active buddy is known enough to create or reuse a task context;
- explicit task and track bindings do not conflict;
- run reservation can be created for the resolved task/context.

Remove:

- package/source readiness checks;
- `SKILL.md` or metadata checks;
- output schema file existence checks;
- active buddy "has registered skills" checks;
- selected skill readiness checks.

### Gate 3: Persist

This gate answers only: "Can this result be written without corrupting artifact/task/track/run state?"

Keep:

- context payload is successful;
- context revision and run reservation match the current task turn;
- selected skill id belongs to the active buddy;
- selected skill has the runtime fields needed to write an artifact, especially `output_slot`;
- result has the minimum writable shape: object payload, string `execution_summary`, object `artifact_content`, and list-shaped run note fields when present;
- `state_effects.track_operation` is PM-only and validates action, track id, status, buddy ids, and task binding before writes.

Remove or downgrade:

- strict full output schema validation as a runtime write gate;
- package/source checks;
- output schema file checks during `persist`;
- content-quality requirements that only make artifacts prettier or more complete.

## File Map

Modify:

- `docs/memo/2026-05-03-community-skill-package-validation-memo.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `framework/docs/turn-runtime-spec.md`
- `scripts/env_manifest.py`
- `scripts/runtime_skills.py`
- `scripts/turn_runtime.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_runtime_skills.py`
- `tests/test_turn_runtime.py`
- `tests/test_repo_consistency.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_buddyswitch_launcher.py`

Preserve:

- `buddyswitch/manifest.toml` current first-party skill registrations unless a test fixture needs a temporary manifest.
- Existing buddy ids and permissions.
- Existing artifact/task/track/run storage object shapes.
- Existing PM-only `state_effects.track_operation` behavior.

Do not create:

- compatibility package validator;
- community package wrapper;
- alternate manifest format;
- runtime bridge for native output.

## Implementation Tasks

### Task 1: Update Memo And Runtime Boundary Docs

**Files:**

- Modify: `docs/memo/2026-05-03-community-skill-package-validation-memo.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`
- Modify: `framework/docs/turn-runtime-spec.md`

- [ ] **Step 1: Rewrite the memo purpose**

Update the memo so it says this task is not only about package validation. It is about trimming three runtime gates:

```markdown
This memo now records the runtime validation boundary for community Codex-native skills across three BuddySwitch points:

1. instance startup skill materialization;
2. product request `prepare`;
3. result `persist`.

The rule is direct: keep only checks that prevent the current chain from running wrong or writing bad state. Remove checks that only prove package style, readiness, or content quality.
```

- [ ] **Step 2: Replace the target boundary section**

Use this target summary:

```markdown
BuddySwitch should not validate community skill package contents. Codex CLI owns package acceptance after the package is materialized into `.agents/skills`.

BuddySwitch should validate:

- materialization path and target boundaries during instance startup;
- turn context and reservation safety during `prepare`;
- write safety during `persist`.

BuddySwitch should not validate:

- `SKILL.md` frontmatter;
- `name` / `description` metadata;
- `skill.toml`;
- package file layout;
- package content symlinks;
- full artifact content quality during runtime persistence.
```

- [ ] **Step 3: Update direct result emission docs**

In `framework/docs/skill-runtime-shared-rules.md`, keep direct buddy-level result emission, but state that strict schema completeness is guidance for skill authors unless a field is needed for safe writes.

In `framework/docs/turn-runtime-spec.md`, document:

```text
prepare validates context safety, not skill package readiness.
persist validates write safety, not Codex skill package format.
```

- [ ] **Step 4: Verify docs have no compatibility language**

Run:

```bash
rg -n "compatibility wrapper|fallback|wrap native|skill package must|frontmatter.*required|skill\\.toml.*not allowed" docs/memo framework/docs
```

Expected: no active instruction tells BuddySwitch runtime to reject community package contents.

### Task 2: Make Manifest Loading Structural

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add red tests for package-opaque manifest loading**

In `tests/test_env_manifest_v2.py`, replace package-format rejection tests with positive tests:

```python
def test_load_manifest_does_not_validate_skill_package_contents(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        temp_root = Path(temp_dir)
        package_root = temp_root / "skills" / "community-skill"
        package_root.mkdir(parents=True)
        (package_root / "README.md").write_text("community package\n", encoding="utf-8")
        (package_root / "skill.toml").write_text('name = "legacy"\n', encoding="utf-8")
        (package_root / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
        manifest_path = self._write_manifest(
            temp_root,
            skills=[
                {
                    "id": "community-skill",
                    "path": package_root.relative_to(ROOT).as_posix(),
                    "produces_artifact": True,
                    "output_slot": "community-output",
                    "output_schema": "framework/schemas/dev/dev-result.json",
                }
            ],
            buddies={"dev": ["community-skill"]},
        )

        loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["id"], "community-skill")
        self.assertEqual(loaded["skills"][0]["path"], package_root.relative_to(ROOT).as_posix())
```

Add a second test proving a missing source directory does not block manifest loading:

```python
def test_load_manifest_does_not_require_skill_source_directory_for_non_materialization_paths(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        temp_root = Path(temp_dir)
        manifest_path = self._write_manifest(
            temp_root,
            skills=[
                {
                    "id": "missing-source-skill",
                    "path": "does/not/exist",
                    "produces_artifact": True,
                    "output_slot": "missing-source",
                    "output_schema": "framework/schemas/dev/dev-result.json",
                }
            ],
            buddies={"dev": ["missing-source-skill"]},
        )

        loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["path"], "does/not/exist")
```

- [ ] **Step 2: Add red tests for schema non-gating**

Add a test showing a missing `output_schema` file does not block manifest loading:

```python
def test_load_manifest_does_not_require_output_schema_file_for_prepare_paths(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        temp_root = Path(temp_dir)
        manifest_path = self._write_manifest(
            temp_root,
            skills=[
                {
                    "id": "schema-later",
                    "path": "buddyswitch/skills/dev/implement-task",
                    "produces_artifact": True,
                    "output_slot": "implementation-report",
                    "output_schema": "framework/schemas/dev/not-runtime-gated.json",
                }
            ],
            buddies={"dev": ["schema-later"]},
        )

        loaded = env_manifest.load_manifest(manifest_path)

        self.assertEqual(loaded["skills"][0]["output_schema"], "framework/schemas/dev/not-runtime-gated.json")
```

- [ ] **Step 3: Keep structural manifest tests**

Keep or add tests that still reject:

```text
duplicate skill id
unknown buddy skill reference
invalid buddy id
invalid permission object/action
missing skill id
missing skill path string
missing buddy id
```

These affect registration identity and runtime routing.

- [ ] **Step 4: Implement structural loading**

In `scripts/env_manifest.py`:

- remove `_parse_skill_frontmatter`;
- remove `_validate_skill_package`;
- stop calling `_validate_skill_package(...)` from `load_manifest()`;
- stop resolving or checking package directories inside `load_manifest()`;
- stop checking whether `output_schema` exists inside `load_manifest()`;
- preserve manifest identity checks, buddy references, permissions, and `persistence` normalization.

Keep `output_slot` in `skill["persistence"]` when configured. Keep `output_schema` as metadata if present, but do not load it or require the file to exist in `load_manifest()`.

- [ ] **Step 5: Remove repo consistency package-format gates**

In `tests/test_repo_consistency.py`, remove tests that assert runtime validity from:

```text
SKILL.md frontmatter
name/description metadata
absence of skill.toml
```

If a first-party docs style check remains, it must be clearly named as documentation style and must not be required by product runtime tests.

- [ ] **Step 6: Run focused manifest tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py -q
```

Expected: all manifest tests pass.

### Task 3: Trim Materialization To Copy Boundaries

**Files:**

- Modify: `scripts/runtime_skills.py`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add red tests for opaque package materialization**

In `tests/test_runtime_skills.py`, replace the current "source package is unsafe because frontmatter is missing" test with success cases:

```python
def test_install_materializes_opaque_community_package_contents(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        temp_root = Path(temp_dir)
        package_root = temp_root / "packages" / "community-skill"
        package_root.mkdir(parents=True)
        (package_root / "SKILL.md").write_text("# no BuddySwitch frontmatter\n", encoding="utf-8")
        (package_root / "skill.toml").write_text('legacy = true\n', encoding="utf-8")
        (package_root / "notes.txt").write_text("preserve me\n", encoding="utf-8")
        (package_root / "linked-notes.txt").symlink_to("notes.txt")
        manifest = self._write_manifest(
            temp_root,
            skills=[
                {
                    "id": "community-skill",
                    "path": package_root.relative_to(ROOT).as_posix(),
                    "produces_artifact": "true",
                    "output_slot": "community-output",
                    "output_schema": "framework/schemas/dev/dev-result.json",
                }
            ],
            buddies={"dev": ["community-skill"]},
        )
        workspace = temp_root / "workspace"
        workspace.mkdir()

        completed = self._run_install(manifest=manifest, buddy="dev", workspace=workspace)

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        installed = workspace / ".agents" / "skills" / "community-skill"
        self.assertTrue((installed / "SKILL.md").exists())
        self.assertTrue((installed / "skill.toml").exists())
        self.assertTrue((installed / "linked-notes.txt").is_symlink())
        self.assertEqual((installed / "linked-notes.txt").readlink(), Path("notes.txt"))
```

Add a separate success case for a package without `SKILL.md`:

```python
def test_install_does_not_require_skill_md_for_buddyswitch_materialization(self) -> None:
    with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
        temp_root = Path(temp_dir)
        package_root = temp_root / "packages" / "opaque-dir"
        package_root.mkdir(parents=True)
        (package_root / "README.md").write_text("Codex will decide if this is executable.\n", encoding="utf-8")
        manifest = self._write_manifest(
            temp_root,
            skills=[
                {
                    "id": "opaque-dir",
                    "path": package_root.relative_to(ROOT).as_posix(),
                    "produces_artifact": "true",
                    "output_slot": "opaque-output",
                    "output_schema": "framework/schemas/dev/dev-result.json",
                }
            ],
            buddies={"dev": ["opaque-dir"]},
        )
        workspace = temp_root / "workspace"
        workspace.mkdir()

        completed = self._run_install(manifest=manifest, buddy="dev", workspace=workspace)

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertTrue((workspace / ".agents" / "skills" / "opaque-dir" / "README.md").exists())
```

- [ ] **Step 2: Keep red tests for real copy-boundary failures**

Keep or add tests that still fail before mutating the runtime skill directory:

```text
invalid skill id with path separators
manifest source path is absolute
manifest source path contains ..
manifest source path resolves outside repo
manifest source path does not exist
manifest source path is not a directory
workspace does not exist
workspace is filesystem root
workspace is source checkout root
workspace/.agents is symlink
workspace/.agents/skills is symlink
```

Each negative test must snapshot `.agents/skills` before and after failure.

- [ ] **Step 3: Implement opaque copy**

In `scripts/runtime_skills.py`:

- delete `_validate_package_contents`;
- remove the call to `_validate_package_contents(source)`;
- simplify source path validation to repo-relative path, resolved-under-repo, exists directory;
- do not walk package contents;
- copy with symlink preservation:

```python
shutil.copytree(entry.source, target_dir, symlinks=True)
```

- [ ] **Step 4: Verify launcher-managed install path**

Keep launcher tests that prove PM workspaces still materialize active buddy skills. Add an assertion that a registered package asset still appears in `.agents/skills`.

- [ ] **Step 5: Run focused materialization tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py -q
```

Expected: runtime skill materialization and launcher tests pass.

### Task 4: Trim Prepare To Turn Context Safety

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Add red prepare tests for non-gating package readiness**

In `tests/test_turn_runtime.py`, add a product-mode prepare test using a temporary manifest where the active buddy's registered skill path points to missing or malformed package contents. Expected behavior:

```text
prepare succeeds
context_revision exists
run_envelope.status is reserved
current_task_id exists
no source package or output schema file was read
```

Use real `prepare_turn_context(...)` or the CLI prepare path under product-mode env, not private helper-only assertions.

- [ ] **Step 2: Add red prepare test for empty buddy skills**

Use a temporary manifest where active buddy exists but `skills = []`.

Expected:

```text
prepare succeeds
task context is produced
run reservation is produced
no "no registered skills" error is returned
```

This proves prepare is not a skill readiness gate.

- [ ] **Step 3: Keep prepare write-safety negatives**

Keep tests that reject:

```text
empty request text
missing product-mode env
partial product-mode env
instance id mismatch
task belongs to a different buddy
task is already bound to a different track
instance binding update failure after reservation
```

For each negative that can happen after a reservation, assert the reservation is cleaned or no invalid task/track state remains.

- [ ] **Step 4: Implement prepare trimming**

In `scripts/turn_runtime.py`:

- keep product session identity checks;
- keep known active buddy checks;
- keep task/track conflict checks;
- keep reservation creation and cleanup behavior;
- remove `buddy has no registered skills` failure;
- ensure `prepare` uses structural manifest loading and therefore does not fail on package/source/schema readiness.

- [ ] **Step 5: Run focused prepare tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py -q
```

Expected: prepare and persist runtime tests pass.

### Task 5: Trim Persist To Write Safety

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_output_schema_boundaries.py`

- [ ] **Step 1: Add red persist test for minimal writable result**

Add a real prepare/persist test where the selected skill result has only the fields required for safe writes:

```json
{
  "execution_summary": "Saved implementation note.",
  "working_notes": [],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "summary": "Saved implementation note.",
    "freeform": {
      "community_output": "This content is not shaped like the full buddy schema."
    }
  }
}
```

Expected:

```text
persist succeeds
artifact object is written
artifact.summary equals execution_summary
artifact.content equals artifact_content
run audit is written
receipt contains artifact_id and run_id
```

The test must use real `prepare` and real `persist`, not direct calls to private validators.

- [ ] **Step 2: Add red persist test for selected output schema non-gating**

Use a temporary manifest where the selected skill has a valid `output_slot` but an `output_schema` path that does not exist.

Expected:

```text
persist succeeds
artifact writes use output_slot
missing output_schema file does not block writes
```

- [ ] **Step 3: Keep persist write-safety negatives**

Keep or add tests that reject before writes:

```text
context payload not ok
stale context_revision
run reservation mismatch
duplicate run id
selected skill not available for active buddy
selected skill has no usable output_slot
missing artifact_content
artifact_content is not an object
execution_summary is missing or not a string
working_notes is present but not a list
deliverables_or_changed_files is present but not a list
top-level track_operation is present
non-PM buddy submits state_effects.track_operation
track operation action is invalid
track operation conflicts with current task/track binding
```

Every negative test must snapshot relevant task, track, artifact, run, and reservation state before and after rejection.

- [ ] **Step 4: Implement minimum result validation**

In `scripts/turn_runtime.py`, replace strict `_validate_result_against_skill(...)` with a minimum write-safety validator:

```python
def _validate_minimum_persist_result(result: dict[str, Any]) -> None:
    summary = result.get("execution_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("execution_summary must be a non-empty string")
    artifact_content = result.get("artifact_content")
    if not isinstance(artifact_content, dict):
        raise ValueError("artifact_content must be an object")
    for key in ("working_notes", "deliverables_or_changed_files"):
        value = result.get(key)
        if value is not None and not isinstance(value, list):
            raise ValueError(f"{key} must be a list when present")
```

Call it before any state effect application or artifact write.

- [ ] **Step 5: Keep selected skill runtime fields**

Ensure `_persist_artifact_skill(...)` still fails if the selected skill cannot provide a non-empty `output_slot`, because artifact slot and artifact id derivation require it.

- [ ] **Step 6: Remove runtime full-schema dependency**

Remove `load_output_schema(...)` and `validate_output_payload(...)` from runtime persist paths if they are no longer used. Keep `scripts/output_schema.py` and schema tests as development contract tooling unless later cleanup proves they are dead.

- [ ] **Step 7: Run focused persist tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_output_schema_boundaries.py -q
```

Expected: persist and schema-tooling tests pass.

### Task 6: Clean Test And Documentation Expectations

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `framework/docs/skill-runtime-shared-rules.md`

- [ ] **Step 1: Remove runtime-invalid package format assertions**

Delete tests that fail the product runtime because a skill package:

```text
lacks YAML frontmatter
has mismatched frontmatter name
lacks description metadata
contains skill.toml
contains symlinked package content
```

Do not replace them with equivalent indirect checks.

- [ ] **Step 2: Keep chain-impacting consistency checks**

Keep tests that prove:

```text
manifest buddy references point to declared skill ids
first-party active buddies exist
permissions use supported object/action shape
state_effects.track_operation remains PM-only
runtime source path tests live in runtime_skills materialization tests
```

- [ ] **Step 3: Update docs to match the final runtime gates**

Docs must say:

```text
materialization validates copy boundaries
prepare validates turn context
persist validates write safety
Codex CLI owns SKILL.md package acceptance
strict content schemas are authoring/development guidance unless a field is needed for safe writes
```

- [ ] **Step 4: Run consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
```

Expected: consistency and PM-only contract tests pass.

### Task 7: Final Verification

**Files:**

- No edits unless failures reveal a real task-scoped issue.

- [ ] **Step 1: Run Python compile check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env_manifest.py scripts/runtime_skills.py scripts/turn_runtime.py scripts/output_schema.py
```

Expected: exits 0.

- [ ] **Step 2: Run focused runtime gate suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_turn_runtime.py tests/test_output_schema_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py tests/test_buddyswitch_launcher.py -q
```

Expected: exits 0.

- [ ] **Step 3: Run full test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests -q
```

Expected: exits 0.

- [ ] **Step 4: Inspect diff for scope control**

Run:

```bash
git diff --stat
git diff -- docs/memo docs/spec framework/docs scripts tests
```

Expected:

- changes stay scoped to runtime gate trimming;
- no compatibility wrappers;
- no new package validator;
- no implementation changes outside `dev0210`.

## Self-Review Checklist

Before marking implementation complete, answer each item with code or test evidence:

- Does any runtime path still parse `SKILL.md` frontmatter?
- Does any runtime path still reject `skill.toml`?
- Does any runtime path still walk package contents before Codex CLI sees them?
- Does `prepare` still fail because of package source/schema readiness?
- Does `prepare` still fail only for context/reservation problems?
- Does `persist` still fail only for write-safety problems?
- Can a minimal community-style result persist into artifact/run state?
- Are stale context, wrong buddy, invalid track effects, and task/track conflicts still blocked before writes?
- Did the task avoid adding a wrapper, bridge, fallback, or compatibility layer?

# Codex Native Buddy Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every launcher-managed buddy instance expose BuddySwitch skills through Codex CLI native `.agents/skills` discovery, while removing BuddySwitch's custom skill selection and instruction-loading path.

**Architecture:** BuddySwitch skill packages become Codex-native source packages. The launcher materializes only the active buddy's skill packages into the instance workspace under `.agents/skills`, and Codex CLI owns skill discovery, selection, and loading. BuddySwitch keeps only environment setup, context preparation, persistence validation, and receipt/state projection.

**Tech Stack:** Bash launcher, Python manifest/runtime helpers, Codex-native `SKILL.md` packages, TOML manifest, pytest/unittest launcher and runtime tests.

---

## Target Outcome

Starting a buddy instance must create a complete Codex-native runtime environment:

```text
${BUDDYSWITCH_WORKSPACE_DIR}/AGENTS.md
${BUDDYSWITCH_WORKSPACE_DIR}/.agents/skills/<active-buddy-skill>/SKILL.md
${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/objects/**
${BUDDYSWITCH_WORKSPACE_DIR}/buddyswitch/content/runs/**
${BUDDYSWITCH_WORKSPACE_DIR}/projects/app
```

Codex CLI must discover and use the runtime skills through its native `.agents/skills` loader. BuddySwitch must not tell the host to select a skill from `prepare_context.skills`, read `instruction_path`, or execute a BuddySwitch-specific skill packet.

## Non-Negotiable Decisions

- No transitional compatibility layer from `skill.toml` to generated frontmatter.
- No dual truth for skill metadata. `SKILL.md` frontmatter is the skill metadata source for Codex.
- No tracked repo-root `.agents` directory.
- Runtime `.agents/skills` exists only inside launcher-managed instance workspaces.
- Codex must launch with the instance workspace as `cwd`, because Codex discovers repo `.agents/skills` by walking from `cwd` toward the project root. If a future launcher starts Codex from `projects/app`, the skill install root must move to the discovery root that Codex will scan.
- `buddyswitch/manifest.toml` keeps buddy membership and persistence contract fields only.
- `prepare` returns state/context for the host turn, not skill candidates or skill instructions.
- `persist` validates the reported `skill_id` against the active buddy's manifest membership and the persistence contract.
- Community Codex skills should be compatible when placed in `buddyswitch/skills/**` and referenced by the manifest, provided they include the small BuddySwitch persistence fields in the manifest.

## Confirmed Current Gaps

- `tools/launcher/workspace.sh` installs `AGENTS.md`, state projections, local excludes, and guardrail hooks, but does not install `.agents/skills`.
- `tools/launcher/env.sh` creates per-instance `CODEX_HOME` and auth/config, but does not prepare skills.
- Codex CLI scans repo/workspace `.agents/skills` and requires `SKILL.md` YAML frontmatter.
- `scripts/env_manifest.py` currently requires `skill.toml` and rejects `SKILL.md` frontmatter.
- `scripts/turn_runtime.py` currently builds `prepare_context.skills`, `run_instructions_by_skill`, and `instruction_path` guidance.
- Buddy prompt assets currently instruct the host to choose `skill_id` from `prepare_context.skills`.

## Files To Create, Modify, Or Delete

Create:

- `scripts/runtime_skills.py`
- `tests/test_runtime_skills.py`

Modify:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/**/SKILL.md`
- `scripts/env_manifest.py`
- `scripts/turn_runtime.py`
- `tools/launcher/workspace.sh`
- `buddyswitch-codex`
- `tools/launcher/assets/buddies/market/AGENTS.md`
- `tools/launcher/assets/buddies/pm/AGENTS.md`
- `tools/launcher/assets/buddies/design/AGENTS.md`
- `tools/launcher/assets/buddies/dev/AGENTS.md`
- `tools/launcher/assets/buddies/test/AGENTS.md`
- `framework/contracts/prepare-turn-context.json`
- `README.md`
- `AGENTS.md`
- `framework/docs/turn-runtime-spec.md`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/browser-cockpit.md`
- `tests/test_env_manifest_v2.py`
- `tests/test_turn_runtime.py`
- `tests/test_turn_integration.py`
- `tests/test_parallel_contracts.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddyswitch_launcher.py`

Delete:

- `buddyswitch/skills/**/skill.toml`
- Custom skill guidance parsing in `scripts/env_manifest.py`
- Custom skill card and run-instruction construction in `scripts/turn_runtime.py`
- Tests that assert `SKILL.md` must not contain frontmatter
- Tests/docs that describe `.agents/skills` as a legacy activation path

Keep:

- `scripts/turn_runtime.py prepare`
- `scripts/turn_runtime.py persist`
- Existing skill output schemas in `framework/schemas/**`
- Existing receipt/persistence behavior, except validation must no longer depend on `context.skills`

## Implementation Tasks

### Task 1: Convert Skill Source Packages To Codex Native Format

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Modify: `buddyswitch/skills/**/SKILL.md`
- Delete: `buddyswitch/skills/**/skill.toml`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Write failing tests for the new source format**

Add manifest/package tests that assert:

```python
def test_skill_packages_are_codex_native() -> None:
    for package_root in _manifest_skill_package_roots():
        skill_md = package_root / "SKILL.md"
        assert skill_md.exists()
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "\nname:" in text.split("---", 2)[1]
        assert "\ndescription:" in text.split("---", 2)[1]
        assert not (package_root / "skill.toml").exists()
```

Add a manifest test that fails if `scripts/env_manifest.py` still requires `skill.toml`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py::RepoConsistencyTests::test_skill_packages_are_codex_native tests/test_env_manifest_v2.py -q
```

Expected before implementation: failures because `skill.toml` exists and `SKILL.md` has no frontmatter.

- [ ] **Step 2: Move persistence fields from `skill.toml` into the manifest**

Each `[[skills]]` entry keeps the skill id/path plus BuddySwitch persistence fields:

```toml
[[skills]]
id = "write-prd"
path = "buddyswitch/skills/pm/write-prd"
produces_artifact = true
output_slot = "prd"
output_schema = "framework/schemas/pm/write-prd.json"
```

For `track-manager`, omit `output_slot` because it does not produce an artifact:

```toml
[[skills]]
id = "track-manager"
path = "buddyswitch/skills/pm/track-manager"
produces_artifact = false
output_schema = "framework/schemas/pm/track-manager.json"
```

Do not put `description`, `purpose`, `use_when`, or instruction-derived guidance in the manifest. Those belong to Codex-native `SKILL.md`.

- [ ] **Step 3: Add YAML frontmatter to every `SKILL.md`**

Use the old `skill.toml` description as the frontmatter description:

```markdown
---
name: write-prd
description: Use when the task is drafting a PRD, defining MVP scope, or turning validated requirements into product requirements.
---

# write-prd
```

Keep the existing markdown body and assets. Do not generate frontmatter at runtime.

- [ ] **Step 4: Delete every `skill.toml`**

Run:

```bash
find buddyswitch/skills -name skill.toml -print
```

Expected after implementation: no output.

- [ ] **Step 5: Verify source format**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py tests/test_env_manifest_v2.py -q
```

Expected after implementation: pass.

### Task 2: Simplify Manifest Loading Around Buddy Membership And Persistence

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Write failing tests for native metadata loading**

Test a temporary skill package with only `SKILL.md` frontmatter and no `skill.toml`:

```python
def test_load_manifest_accepts_codex_native_skill_package() -> None:
    package_root = make_skill_package(
        "demo-skill",
        skill_md="""\
---
name: demo-skill
description: Use when demo work needs a native Codex skill.
---

# demo-skill
"""
    )
    manifest = make_manifest_with_persistence_fields(package_root)
    loaded = env_manifest.load_manifest(manifest)
    assert loaded["skills"][0]["id"] == "demo-skill"
    assert "description" not in loaded["skills"][0]
    assert loaded["skills"][0]["persistence"]["output_schema"] == "framework/schemas/pm/write-prd.json"
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_load_manifest_accepts_codex_native_skill_package -q
```

Expected before implementation: fail because loader requires `skill.toml`.

- [ ] **Step 2: Replace `_load_skill_package`**

Make `_load_skill_package`:

- Read `SKILL.md`.
- Require leading YAML frontmatter.
- Do not add a new PyYAML dependency; this repo currently has no Python dependency manifest.
- Implement a small strict frontmatter field parser for the Codex-required top-level scalar fields `name` and `description`, including closing delimiter and parse-error handling.
- Support quoted and unquoted scalar values, including descriptions containing colons.
- Ignore unknown frontmatter keys instead of interpreting them as BuddySwitch metadata.
- Extract `name` and `description` for validation only.
- Reject missing or mismatched `name`.
- Reject missing or empty `description`.
- Reject local `skill.toml` to prevent dual metadata.
- Return only validation success. Do not expose `description` or parsed guidance through BuddySwitch runtime data.

Do not parse markdown headings into guidance sections.

- [ ] **Step 3: Add manifest-level persistence parsing**

Validate persistence fields from the `[[skills]]` entry:

- `produces_artifact` is required boolean.
- `output_schema` is required and must point to an existing schema file.
- `output_slot` is required only when `produces_artifact=true`.

Store them under `skill["persistence"]`.

Do not keep `allowed_task_kinds` in the new persistence contract. The current runtime has no stable task-kind field to enforce, and carrying the field would preserve custom skill-routing residue without a clear state-writing need.

- [ ] **Step 4: Update buddy authority wording**

Change `buddy_authority_profile` so it no longer says turn runtime uses buddy skills as selection authority. It should say buddy membership limits which runtime skills are materialized and which `skill_id` values `persist` accepts.

- [ ] **Step 5: Verify manifest behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py -q
./scripts/env_manifest.py show-buddy pm
```

Expected after implementation: tests pass; `show-buddy pm` reports buddy membership and persistence metadata, not descriptions, parsed instruction guidance, or host skill-selection hints.

### Task 3: Materialize Active Buddy Skills Into Instance `.agents/skills`

**Files:**

- Create: `scripts/runtime_skills.py`
- Modify: `tools/launcher/workspace.sh`
- Modify: `buddyswitch-codex`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Write failing runtime skill installer tests**

Create tests for:

- Installing PM skills creates `.agents/skills/write-prd/SKILL.md` and `.agents/skills/track-manager/SKILL.md`.
- Installing PM skills does not create `shape-prototype`, `implement-task`, or market skills.
- Reinstalling for another buddy clears stale skills first.
- Assets under a skill package are copied.
- Source packages with missing frontmatter fail before launching Codex.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py -q
```

Expected before implementation: fail because installer does not exist.

- [ ] **Step 2: Implement `scripts/runtime_skills.py`**

Implement a narrow CLI:

```bash
python3 scripts/runtime_skills.py install --buddy pm --workspace "$BUDDYSWITCH_WORKSPACE_DIR"
```

Behavior:

- Load `buddyswitch/manifest.toml`.
- Resolve the buddy's `skills` list.
- Remove `${workspace}/.agents/skills`.
- Recreate `${workspace}/.agents/skills`.
- Copy each source skill package directory to `${workspace}/.agents/skills/<skill-id>`.
- Fail if any source package has no frontmatter.
- Fail if any source package contains `skill.toml`.
- Print installed skill ids, one per line, for debugging.

Use `shutil.copytree` with no transformations.

- [ ] **Step 3: Wire workspace preparation**

Add `buddyswitch_workspace_install_runtime_skills` in `tools/launcher/workspace.sh`:

```bash
buddyswitch_workspace_install_runtime_skills() {
  local buddy_id="${BUDDYSWITCH_ACTIVE_BUDDY:-${BUDDYSWITCH_START_BUDDY:-}}"
  if [[ -z "${buddy_id}" ]]; then
    return 0
  fi
  python3 "${BUDDYSWITCH_REPO_ROOT}/scripts/runtime_skills.py" install \
    --buddy "${buddy_id}" \
    --workspace "${BUDDYSWITCH_WORKSPACE_DIR}"
}
```

Call it from:

- `buddyswitch_workspace_prepare_execution_worktree`
- `buddyswitch_workspace_sync_execution_worktree`
- `instance_open_locked_bootstrap` after state skeleton is ensured and before Codex launches

Add a launcher assertion that fake Codex captures `cwd == BUDDYSWITCH_WORKSPACE_DIR`. This proves Codex starts from the directory whose `.agents/skills` should be discovered. If this assertion fails, do not work around it with a second skill install path; fix the launch cwd or move the single runtime skill root to the actual Codex discovery root.

- [ ] **Step 4: Exclude runtime skills from worktree status**

Add `.agents/skills/**` to `buddyswitch_workspace_install_local_excludes`.

Do not add a tracked repo-root `.agents` directory.

- [ ] **Step 5: Add installer boundary checks**

Before deleting or copying anything, `scripts/runtime_skills.py` must:

- Resolve `--workspace` and reject empty, root, or non-directory values.
- Resolve the target as `<workspace>/.agents/skills` and verify it stays under the resolved workspace.
- Reject `.agents` or `.agents/skills` when either path is a symlink.
- Resolve each manifest skill path against the repo root.
- Reject absolute manifest skill paths.
- Reject manifest skill paths that escape the repo root with `..`.
- Reject skill package directories or package contents that are symlinks.
- Reject skill ids containing `/`, `\`, `..`, or path separators before building target paths.

Add tests for every rejection above. The installer must fail before deleting any existing valid runtime skill directory when the source manifest or workspace boundary is unsafe.

- [ ] **Step 6: Extend launcher integration tests**

In `tests/test_buddyswitch_launcher.py`, extend existing fake Codex capture tests to inspect the generated workspace:

```python
runtime_skills = workspace_dir / ".agents" / "skills"
self.assertTrue((runtime_skills / "write-prd" / "SKILL.md").exists())
self.assertTrue((runtime_skills / "track-manager" / "SKILL.md").exists())
self.assertFalse((runtime_skills / "shape-prototype").exists())
self.assertTrue((runtime_skills / "write-prd" / "assets" / "prd-template.md").exists())
```

Add an `instance open` test that plants a stale skill under `.agents/skills/stale-skill` and proves open bootstrap removes it.

Add a refresh test that corrupts an existing active runtime package file, runs `instance open`, and proves the runtime package file is byte-equal to the source package file afterward.

- [ ] **Step 7: Verify launcher materialization**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_buddyswitch_launcher.py -q
```

Expected after implementation: pass.

### Task 4: Remove BuddySwitch Custom Skill Selection From Prepare

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `framework/contracts/prepare-turn-context.json`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`
- Modify: `tests/test_parallel_contracts.py`

- [ ] **Step 1: Write failing tests for prepare context shape**

Assert `prepare` returns context and run envelope but no custom skill loading fields:

```python
context = prepare_turn("Draft onboarding PRD", active_buddy="pm")
assert context["ok"] is True
assert list(context) == [
    "ok",
    "context_revision",
    "instance_id",
    "active_buddy",
    "request_text",
    "current_task_id",
    "current_track_id",
    "task_context",
    "track_context",
    "track_artifact_index",
    "run_envelope",
    "warnings",
]
assert "skills" not in context
assert "inputs_by_skill" not in context
assert "run_instructions_by_skill" not in context
assert "selected_skill_packet" not in context
assert "instruction_path" not in json.dumps(context)
assert "skill_candidates" not in json.dumps(context)
assert "skill_instructions" not in json.dumps(context)
assert context["active_buddy"] == "pm"
assert context["run_envelope"]["run_id"].startswith("run-")
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py::TurnRuntimeTests::test_prepare_does_not_return_custom_skill_selection_fields -q
```

Expected before implementation: fail because `skills` and instruction fields exist.

- [ ] **Step 2: Remove custom skill card/run-instruction construction**

Delete or stop using:

- `_build_skill_card`
- `_build_run_instructions`
- `inputs_by_skill`
- `run_instructions_by_skill`
- instruction-path guidance in prepare response

Keep:

- task context
- track context
- track artifact index or equivalent artifact context
- run envelope/reservation
- warnings

- [ ] **Step 3: Update prepare contract**

Change `framework/contracts/prepare-turn-context.json` key order to the new context-only shape:

```json
[
  "ok",
  "context_revision",
  "instance_id",
  "active_buddy",
  "request_text",
  "current_task_id",
  "current_track_id",
  "task_context",
  "track_context",
  "track_artifact_index",
  "run_envelope",
  "warnings"
]
```

Do not add a replacement skill list field.

- [ ] **Step 4: Verify prepare behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_parallel_contracts.py -q
```

Expected after implementation: pass.

### Task 5: Make Persist Validate Skill Attribution Without `context.skills`

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `tests/test_turn_runtime.py`
- Modify: `tests/test_turn_integration.py`

- [ ] **Step 1: Write failing persist tests**

Add tests proving:

- `persist` accepts `skill_id="write-prd"` for a PM context even when `context` has no `skills`.
- `persist` rejects `skill_id="implement-task"` for a PM context.
- `persist` rejects unknown skill ids.
- `persist` rejects missing or empty `skill_id`.
- `persist` rejects a valid active-buddy `skill_id` when the result payload matches a different active-buddy skill schema.
- Artifact-producing and non-artifact `track-manager` runs still produce valid receipts.
- Rejection cases leave task, artifact, run, and reservation state unchanged.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py::TurnRuntimeTests::test_persist_validates_skill_id_from_active_buddy_manifest_membership -q
```

Expected before implementation: fail because persist requires `context.skills`.

- [ ] **Step 2: Replace `context.skills` validation**

In `_persist_skill_result`, remove:

```python
skills_payload = context.get("skills")
...
if selected_skill_id not in skill_ids:
    raise ValueError(...)
```

Replace it with manifest membership validation:

```python
manifest = load_manifest(manifest_path)
buddy = require_buddy(manifest, active_buddy)
allowed_skill_ids = set(buddy.get("skills", []))
if selected_skill_id not in allowed_skill_ids:
    raise ValueError(...)
```

- [ ] **Step 3: Resolve persistence contract from manifest**

Update `_resolve_execution_skill` and `_validate_result_against_skill` to read `skill["persistence"]`, not `skill["runtime"]`.

Preserve output schema validation and artifact persistence.

Do not enforce `allowed_task_kinds`; it is removed with `skill.toml` because there is no current stable task-kind field in the prepare/persist state contract.

- [ ] **Step 4: Verify persistence behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_parallel_contracts.py -q
```

Expected after implementation: pass.

### Task 6: Rewrite Runtime Buddy Prompts Around Codex Native Skills

**Files:**

- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Write failing prompt residue tests**

Assert every buddy prompt:

- Contains `.agents/skills`.
- Says Codex CLI owns native skill discovery/use.
- Does not contain `Choose exactly one skill_id from prepare_context.skills`.
- Does not contain `Read and execute the selected BuddySwitch SKILL.md`.
- Does not contain `instruction_path`.

- [ ] **Step 2: Update the Canonical Loop**

Use this prompt shape for every buddy:

```markdown
## Canonical Loop

1. Prepare context with `scripts/turn_runtime.py prepare "<ordinary request>"`.
2. Let Codex CLI use the native skills exposed in `.agents/skills`.
3. Execute the selected native skill in this host session.
4. Persist with `scripts/turn_runtime.py persist`, reporting the Codex skill name as `skill_id`.
5. If another turn is needed, derive a new `request_text` from `receipt.next_state`, then run `prepare` again.
```

Keep receipt/summary and buddy lock sections.

- [ ] **Step 3: Verify generated instance prompt and skills together**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_with_buddy_creates_shared_project_workspace -q
```

Expected after implementation: generated workspace has the updated `AGENTS.md` and runtime `.agents/skills`.

### Task 7: Clean Up Active Docs And Residue Tests

**Files:**

- Modify: `framework/docs/turn-runtime-spec.md`
- Modify: `framework/docs/skill-architecture-best-practices.md`
- Modify: `framework/docs/browser-cockpit.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Replace old skill architecture language**

Active docs must say:

- Source skill packages are Codex-native.
- Instance runtime skills are materialized under `.agents/skills`.
- BuddySwitch does not select or load skill instructions.
- `prepare` supplies context only.
- `persist` records the skill id used by Codex and validates it against buddy membership.

- [ ] **Step 2: Update `.agents/skills` repo consistency rule**

Keep the rule that repo root `.agents` must not exist. Remove the rule that forbids documenting runtime `.agents/skills`.

Add a replacement rule:

```python
def test_runtime_agents_skills_are_documented_as_instance_only(self) -> None:
    self.assertFalse((ROOT / ".agents").exists())
    for path in active_docs:
        if ".agents/skills" in path.read_text(encoding="utf-8"):
            self.assertIn("instance", path.read_text(encoding="utf-8").lower())
```

- [ ] **Step 3: Search for old custom skill handling language**

Run:

```bash
rg -n "prepare_context\\.skills|instruction_path|selected_skill_packet|run_instructions_by_skill|Choose exactly one skill_id|Read and execute the selected BuddySwitch" README.md AGENTS.md framework tools scripts buddyswitch
```

Expected after implementation: no active product-path references.

Run repo consistency tests for `skill.toml` and other retired strings. Those tests may contain forbidden strings only as explicit rejection or residue assertions; implementation and active docs must not use them as current behavior.

- [ ] **Step 4: Verify active docs and consistency tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_repo_consistency.py -q
```

Expected after implementation: pass.

### Task 8: End-To-End Verification And Manual Codex Smoke

**Files:**

- No new implementation files

- [ ] **Step 1: Run focused automated tests**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_env_manifest_v2.py \
  tests/test_turn_runtime.py \
  tests/test_turn_integration.py \
  tests/test_parallel_contracts.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run syntax verification**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env_manifest.py scripts/runtime_skills.py scripts/turn_runtime.py
```

Expected: no output.

- [ ] **Step 3: Run launcher smoke with fake Codex capture**

Use the existing launcher tests as the automated smoke. Confirm generated workspace contains:

```text
AGENTS.md
.agents/skills/<buddy-skill>/SKILL.md
.git/info/exclude with .agents/skills/**
projects/app
```

Also confirm fake Codex captures `cwd` as the instance workspace root, not `projects/app`.

- [ ] **Step 4: Run optional manual Codex-native smoke when local Codex is available**

Start a PM instance and ask for a PRD request:

```bash
./buddyswitch-codex instance start --buddy pm -- debug prompt-input "Draft the onboarding PRD"
```

This is a non-gating local canary if the developer has a current Codex CLI. Expected observable proof: prompt input or session behavior shows native PM skill names from `.agents/skills` and does not show BuddySwitch-injected `instruction_path`.

## Stop Condition

The task is complete only when:

- All skill source packages are Codex native.
- No `skill.toml` remains.
- Starting or opening a buddy instance materializes only that buddy's native skill packages under runtime `.agents/skills`.
- `prepare` no longer returns custom skill selection or instruction-loading fields.
- `persist` still writes valid task/artifact/track/run receipts and validates `skill_id` against active buddy membership.
- Active prompts and docs no longer teach BuddySwitch-specific skill handling.
- Focused tests pass.

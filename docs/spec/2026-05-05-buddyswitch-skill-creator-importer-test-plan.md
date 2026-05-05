# BuddySwitch Skill Creator Importer Test Plan

**Goal:** Verify that BuddySwitch can import an external Codex-native skill package into repo source, register it for one buddy, materialize it through the existing runtime path, and persist its output without adding historical compatibility burden.

**Testing Principle:** Tests start from user-facing functionality and product contracts: import a package, inspect generated repo state, materialize the selected buddy's runtime skills, and persist a result under the imported native `skill_id`. Do not construct tests around private helper names, historical branches, or error strings just to pass the implementation.

---

## Functional Requirements Under Test

FR1. The importer accepts one external Codex-native skill package directory containing `SKILL.md`.

FR2. The importer accepts a direct `SKILL.md` file and creates a package directory around it.

FR3. The target buddy is explicit and must be one of the current BuddySwitch buddies: `pm`, `dev`, `test`, `market`, `design`.

FR4. The imported skill id is deterministic, valid, and unique in the manifest.

FR5. The generated package path is `buddyswitch/skills/<buddy>/<skill-id>/`.

FR6. The generated `SKILL.md` preserves the original workflow text and appends BuddySwitch persist closing rules.

FR7. The importer preserves non-retired package files and symlink objects instead of normalizing package layout.

FR8. The importer updates `buddyswitch/manifest.toml` with a valid `[[skills]]` entry and adds the skill id to exactly the selected buddy.

FR9. The generated manifest registration uses `produces_artifact = true`, `output_slot = "<skill-id>"`, and the target buddy's buddy-level result schema.

FR10. Failed imports do not leave partial package directories or partial manifest edits.

FR11. The Dev buddy has a native `skill-creator-importer` package registered in the live manifest.

FR12. Existing launcher/runtime materialization installs imported and first-party skills through the same `.agents/skills` path.

FR13. An imported skill id can persist a minimally writable result for its target buddy.

FR14. An imported skill id cannot persist for a different active buddy.

FR15. The implementation does not reintroduce runtime bridges, transcript parsers, `skill.toml` metadata reading/copying, compatibility wrappers, fallback converters, or custom skill packets.

FR16. Active docs and memo describe importer behavior in current forward-only terms.

## Coverage Matrix

| Requirement | Test Type | Observable Proof |
| --- | --- | --- |
| FR1 | Import success | external package directory imports and generated package exists |
| FR2 | Import success | direct `SKILL.md` imports and generated package contains `SKILL.md` |
| FR3 | Import negative | unknown buddy fails and repo snapshot is unchanged |
| FR4 | Import contract | explicit and derived skill ids are valid; duplicate id fails without writes |
| FR5 | Repo state | generated package path is exactly under selected buddy directory |
| FR6 | Content contract | generated `SKILL.md` contains source workflow plus closing rules |
| FR7 | Package preservation | assets, references, scripts, arbitrary non-retired files, and symlink objects are preserved; `skill.toml` is dropped |
| FR8 | Manifest contract | `load_manifest()` accepts generated manifest and selected buddy includes skill id |
| FR9 | Manifest contract | persistence fields match target buddy schema and `output_slot = skill_id` |
| FR10 | Negative import | target package and manifest bytes are unchanged after failure |
| FR11 | Live manifest | `skill-creator-importer` is registered under Dev and materializes |
| FR12 | Runtime integration | `.agents/skills/<skill-id>` appears after existing install/start/open path |
| FR13 | Persist integration | receipt, artifact object, and run audit keep imported native `skill_id` |
| FR14 | Negative persist | cross-buddy persist fails with runtime state snapshot unchanged |
| FR15 | Residue guard | active code/docs/prompts contain no retired runtime path tokens |
| FR16 | Docs consistency | memo and skill docs describe repo registration plus persist guidance, not package-format compatibility |

## Test Data Rules

Use realistic source packages that look like community Codex skills, not BuddySwitch first-party fixtures disguised as community packages.

External package fixture:

```text
community-dev-summary/
  SKILL.md
  README.md
  assets/example-output.md
  references/style-guide.md
  scripts/helper.sh
  linked-readme.md -> README.md
```

Source `SKILL.md`:

```markdown
---
name: dev-summary
description: Use when summarizing code changes for handoff.
---

# dev-summary

Summarize code changes, verification evidence, and handoff risks.
```

Expected generated BuddySwitch closing rule tokens:

```text
BuddySwitch Runtime Closing Rules
persist --skill-id dev-summary
execution_summary
artifact_content
framework/schemas/dev/dev-result.json
Do not call a result bridge
```

Minimal writable imported result:

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

Invalid result:

```json
{
  "execution_summary": "",
  "working_notes": "not a list",
  "artifact_content": "not an object"
}
```

## Anti-Cheat Rules

- Do not test only private helper functions when product behavior can be tested through import, materialization, prepare, or persist.
- Do not make success tests pass by writing the generated package directly in the test instead of invoking the importer.
- Do not make negative tests pass by checking error text only; snapshot package paths and manifest bytes before and after failure.
- Do not use a community fixture that already contains BuddySwitch persist closing rules.
- Do not satisfy package preservation by copying only `SKILL.md`.
- Do not add a runtime adapter that lets imported skills avoid direct BuddySwitch result JSON.
- Do not restore `skill.toml` as metadata or copied first-party source residue, even if a source package contains it.
- Do not add live session reload behavior to make materialization tests pass.
- Do not accept cross-buddy persist by widening buddy membership.

## Test Groups

### TG-01: Import Input Contract

Requirement: importer accepts real Codex-native source inputs and rejects invalid requests before writes.

Cases:

1. Package directory imports.
   - Input: `community-dev-summary/` fixture with `SKILL.md`.
   - Command/API: `import_skill(source=source_dir, buddy_id="dev", skill_id="dev-summary", repo_root=temp_repo)`.
   - Expected: generated package exists at `buddyswitch/skills/dev/dev-summary`.
   - Expected: manifest contains `dev-summary`.

2. Direct `SKILL.md` imports.
   - Input: path to `community-dev-summary/SKILL.md`.
   - Expected: generated package exists with only generated `SKILL.md` content from that file plus closing rules.

3. Missing `SKILL.md` fails.
   - Input: package directory with `README.md` only.
   - Expected: import fails.
   - Expected: no target package directory exists.
   - Expected: manifest bytes are unchanged.

4. Missing description frontmatter fails.
   - Input: `SKILL.md` with `name` but no `description`.
   - Expected: import fails.
   - Expected: no target package directory exists.
   - Expected: manifest bytes are unchanged.

5. Unknown buddy fails.
   - Input: `buddy_id="ops"`.
   - Expected: import fails.
   - Expected: no target package directory exists.
   - Expected: manifest bytes are unchanged.

6. Invalid skill id fails.
   - Input: `skill_id="Bad/Skill"`.
   - Expected: import fails.
   - Expected: no target package directory exists.
   - Expected: manifest bytes are unchanged.

7. Duplicate skill id fails.
   - Input: `skill_id="implement-task"` in a manifest that already declares `implement-task`.
   - Expected: import fails.
   - Expected: original manifest bytes are unchanged.

### TG-02: Generated Package Contract

Requirement: generated package is a Codex-native package with original workflow preserved and BuddySwitch closing rules appended.

Cases:

1. Source workflow is preserved.
   - Input: source `SKILL.md` contains `# dev-summary` and workflow sentence.
   - Expected: generated `SKILL.md` contains both exact source lines.

2. BuddySwitch rules are appended.
   - Expected: generated `SKILL.md` contains `## BuddySwitch Runtime Closing Rules`.
   - Expected: generated `SKILL.md` contains the selected buddy id, generated skill id, persist command, minimum writable keys, and target schema path.

3. Historical runtime paths are absent.
   - Expected: generated `SKILL.md` does not contain `result_bridge`, `selected_skill_packet`, `prepare_context.skills`, `runtime interception`, `compatibility wrapper`, or `fallback converter`.

4. Package files are preserved.
   - Input: source package has `README.md`, `assets/example-output.md`, `references/style-guide.md`, and `scripts/helper.sh`.
   - Expected: each copied file exists under generated package with the same bytes.

5. Symlink objects are preserved.
   - Input: `linked-readme.md -> README.md`.
   - Expected: generated `linked-readme.md` is a symlink.
   - Expected: generated symlink target is `README.md`.

6. Source `skill.toml` is dropped as retired metadata.
   - Input: source package contains `skill.toml`.
   - Expected: generated package does not contain `skill.toml`.
   - Expected: generated manifest does not read values from `skill.toml`.
   - Expected: repo consistency still forbids `buddyswitch/skills/**/skill.toml` for first-party checked-in packages.

### TG-03: Manifest Registration Contract

Requirement: generated manifest is valid BuddySwitch registration state.

Cases:

1. Dev import registration.
   - Input: `buddy_id="dev"`, `skill_id="dev-summary"`.
   - Expected: `output_schema = "framework/schemas/dev/dev-result.json"`.
   - Expected: `output_slot = "dev-summary"`.
   - Expected: Dev buddy skill list includes `dev-summary`.
   - Expected: no other buddy skill list includes `dev-summary`.

2. PM import registration.
   - Input: `buddy_id="pm"`, `skill_id="pm-notes"`.
   - Expected: `output_schema = "framework/schemas/pm/pm-result.json"`.
   - Expected: `output_slot = "pm-notes"`.

3. Market import registration.
   - Input: `buddy_id="market"`, `skill_id="market-brief"`.
   - Expected: `output_schema = "framework/schemas/market/market-result.json"`.
   - Expected: Market buddy skill list includes `market-brief`.

4. Design import registration.
   - Input: `buddy_id="design"`, `skill_id="ux-notes"`.
   - Expected: `output_schema = "framework/schemas/design/design-result.json"`.

5. Test import registration.
   - Input: `buddy_id="test"`, `skill_id="regression-notes"`.
   - Expected: `output_schema = "framework/schemas/test/test-result.json"`.

6. Generated manifest loads.
   - Flow: call `env_manifest.load_manifest(generated_manifest_path)`.
   - Expected: load succeeds.
   - Expected: `skills_by_id(...)[skill_id]["persistence"]["output_slot"] == skill_id`.

### TG-04: Transaction Safety

Requirement: failed imports do not leave partial repo state.

Cases:

1. Target package already exists.
   - Setup: create `buddyswitch/skills/dev/dev-summary/SKILL.md`.
   - Expected: import fails.
   - Expected: existing package bytes are unchanged.
   - Expected: manifest bytes are unchanged.

2. Manifest duplicate exists.
   - Setup: manifest already has `[[skills]] id = "dev-summary"`.
   - Expected: import fails.
   - Expected: no package directory is created.

3. Invalid manifest after generated edit.
   - Setup: temp manifest missing a required buddy permission field.
   - Expected: import fails while validating generated manifest.
   - Expected: no target package directory remains.
   - Expected: original manifest bytes are restored.

4. Source read failure.
   - Setup: source path does not exist.
   - Expected: import fails.
   - Expected: no target package directory exists.
   - Expected: manifest bytes are unchanged.

### TG-05: Runtime Materialization

Requirement: imported skills use the existing runtime materialization path.

Cases:

1. Imported Dev skill materializes.
   - Flow: import `dev-summary` into a temp repo, patch runtime skill root to that temp repo, run `install_runtime_skills` for Dev.
   - Expected: `.agents/skills/dev-summary/SKILL.md` exists.
   - Expected: installed `SKILL.md` contains BuddySwitch closing rules.

2. Imported skill materializes only for selected buddy.
   - Flow: register `dev-summary` only for Dev and install PM skills.
   - Expected: `.agents/skills/dev-summary` does not exist in PM runtime workspace.

3. Live Dev wrapper skill materializes.
   - Flow: launcher or runtime materialization for live Dev buddy.
   - Expected: `.agents/skills/skill-creator-importer/SKILL.md` exists.
   - Expected: `.agents/skills/skill-creator-importer/assets/skill-import-report-template.md` exists.

4. Existing first-party skill materialization still works.
   - Flow: install live Dev skills.
   - Expected: `.agents/skills/implement-task/SKILL.md` still exists.

### TG-06: Persist Integration

Requirement: imported native skill ids persist through current BuddySwitch write-safety path.

Cases:

1. Imported Dev skill persists minimum result.
   - Setup: temp manifest registers `dev-summary` to Dev with `output_slot = "dev-summary"`.
   - Flow: prepare Dev context, persist minimal writable result with `skill_id="dev-summary"`.
   - Expected: persist returns `ok=true`.
   - Expected: receipt `skill_id == "dev-summary"`.
   - Expected: artifact object `skill_id == "dev-summary"`.
   - Expected: run audit `skill_id == "dev-summary"`.

2. Imported PM skill persists minimum result.
   - Setup: temp manifest registers `pm-notes` to PM with PM schema and `output_slot = "pm-notes"`.
   - Flow: prepare PM context, persist minimal writable result with `skill_id="pm-notes"`.
   - Expected: receipt and artifact keep `pm-notes`.

3. Cross-buddy persist fails before writes.
   - Setup: manifest registers `dev-summary` only to Dev.
   - Flow: prepare PM context, persist with `skill_id="dev-summary"`.
   - Expected: persist fails.
   - Expected: runtime state snapshot is unchanged.

4. Invalid minimum result fails before writes.
   - Setup: manifest registers imported skill for active buddy.
   - Flow: persist invalid result from Test Data Rules.
   - Expected: persist fails.
   - Expected: runtime state snapshot is unchanged.

5. Missing output schema file does not block write-safe imported result.
   - Setup: imported skill manifest uses a missing schema file path.
   - Flow: prepare target buddy context, persist minimal writable result.
   - Expected: persist succeeds because runtime write safety does not require schema file readiness.

### TG-07: Dev Skill Wrapper

Requirement: the importer is itself available as a current Dev buddy skill.

Cases:

1. Live manifest declares `skill-creator-importer`.
   - Expected: `id = "skill-creator-importer"`.
   - Expected: `path = "buddyswitch/skills/dev/skill-creator-importer"`.
   - Expected: `produces_artifact = true`.
   - Expected: `output_slot = "skill-import-report"`.
   - Expected: `output_schema = "framework/schemas/dev/dev-result.json"`.

2. Dev buddy includes importer skill.
   - Expected: Dev `skills` list is `["implement-task", "skill-creator-importer"]`.

3. Importer skill doc is Codex-native.
   - Expected: `SKILL.md` has frontmatter `name: skill-creator-importer`.
   - Expected: description is non-empty.

4. Importer report template is valid Dev result JSON.
   - Expected: template parses as JSON.
   - Expected: contains top-level `execution_summary`, `working_notes`, `deliverables_or_changed_files`, and `artifact_content`.
   - Expected: `artifact_content` contains Dev result fields `task_summary`, `changed_files`, `implementation_notes`, `verification`, `risks`, and `follow_ups`.

### TG-08: Docs And Forward-Only Residue

Requirement: docs and active code describe the current approach and keep retired paths retired.

Cases:

1. Importer memo uses current boundary terms.
   - Expected: memo says repo registration and persist guidance.
   - Expected: memo says runtime package-format gatekeeping remains closed.
   - Expected: memo says active Codex sessions are not hot-reloaded.

2. Importer memo does not use stale compatibility terms.
   - Expected: no `BuddySwitch-compatible`.
   - Expected: no `runtime interception`.
   - Expected: no `package-format gatekeeping` as a remaining importer task.

3. Active importer code and skill docs do not mention retired runtime paths.
   - Scan `scripts/skill_creator_importer.py`, `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`, and active framework docs.
   - Expected: no `result_bridge`, `selected_skill_packet`, `prepare_context.skills`, `compatibility wrapper`, or `fallback converter`.

4. First-party source packages still do not contain `skill.toml`.
   - Flow: `find buddyswitch/skills -type f -name skill.toml -print`.
   - Expected: no output.

5. Runtime scripts remain unchanged in boundary behavior.
   - Expected: runtime gate tests from the 2026-05-05 runtime gate trimming suite still pass.

## Required Verification Commands

Run from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/skill_creator_importer.py
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_skill_creator_importer.py -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_runtime_skills.py tests/test_turn_runtime.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py -q
```

```bash
rg -n "result_bridge|scripts/result_bridge.py|selected_skill_packet|prepare_context\\.skills|runtime interception|compatibility wrapper|fallback converter" scripts buddyswitch/skills framework/docs tools/launcher/assets/buddies docs/memo/2026-05-03-buddyswitch-skill-creator-importer-memo.md
```

```bash
find buddyswitch/skills -type f -name skill.toml -print
```

```bash
git diff --check
git status --short --branch
```

Expected final state:

- compile command exits 0;
- pytest commands pass;
- retired runtime path scan has no active implementation or active prompt/doc matches;
- `find buddyswitch/skills -type f -name skill.toml -print` prints nothing;
- `git diff --check` exits 0;
- `git status` shows only intentional task files.

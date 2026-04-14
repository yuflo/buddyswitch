# BuddySwitch Skill Architecture Current Status Review

## Metadata

- Document: BuddySwitch Skill Architecture Current Status Review
- Date: 2026-04-14
- Status: Updated after cleanup implementation
- Purpose:
  - independently restate the current skill-architecture status
  - reflect the implementation state in this worktree rather than the earlier review snapshot
  - separate resolved issues from true remaining risks

## Scope

This review covers the active skill contract and runtime path:

- `buddyswitch/manifest.toml`
- `buddyswitch/skills/**/skill.toml`
- `buddyswitch/skills/**/SKILL.md`
- `buddyswitch/skills/**/assets/**`
- `framework/docs/skill-architecture-best-practices.md`
- `framework/docs/skill-runtime-shared-rules.md`
- `scripts/env_manifest.py`
- `scripts/switch_runtime.py`
- `tests/test_env_manifest_v2.py`
- `tests/test_output_schema_boundaries.py`
- `tests/test_repo_consistency.py`
- `tests/test_switch_runtime.py`
- `tests/test_switch_integration.py`

## Verification Performed

The current status below is based on direct code inspection plus these checks:

```bash
python3 -m unittest tests.test_env_manifest_v2 tests.test_output_schema_boundaries tests.test_repo_consistency tests.test_switch_runtime tests.test_switch_integration -v
rg -n "_load_skill_runtime|default_artifact_kind|auto_summary|_split_front_matter" scripts tests framework/docs buddyswitch docs/whiteboard docs/reviews
```

Observed results:

- `Ran 46 tests`
- `OK`
- active runtime code no longer contains `_load_skill_runtime`, `_split_front_matter`, `default_artifact_kind`, or `auto_summary`
- grep hits for `default_artifact_kind` and `auto_summary` now remain only in tests that explicitly assert their retirement or construct legacy-shaped negative cases

## Current Verdict

The BuddySwitch skill architecture is now in a clean package-contract state.

The most accurate current summary is:

```text
BuddySwitch now uses skill packages as the only supported runtime contract.
Legacy single-file/frontmatter skill loading has been removed.
Runtime compatibility fields used during migration have been removed.
Skill descriptions and shared runtime rules have been tightened to fit the v2 package model.
```

This means the earlier whiteboard review should now be read as historical analysis, not as a description of the active implementation.

## Resolved Since The Earlier Review

### 1. Skill loading is package-only

The active loader path now requires:

- a skill package directory
- `skill.toml`
- `SKILL.md`

`load_manifest()` rejects non-directory skill paths, and package `SKILL.md` files reject frontmatter with an explicit move-to-`skill.toml` message.

There is no longer an active single-file/frontmatter production loader.

### 2. Package metadata is the active authority

`skill.toml` is now the active machine-readable skill contract for:

- `buddy`
- `description`
- `objects`
- `produces_artifact`
- `output_slot`
- `input_slots`
- `output_schema`
- `produces`
- `consumes`
- `allowed_task_kinds`

`manifest.toml` keeps skill entries at the minimal package index shape:

- `id`
- `path`

The manifest no longer duplicates skill description, objects, or buddy mapping fields under `[[skills]]`.

### 3. Compatibility runtime fields are gone

The migration-era fields:

- `default_artifact_kind`
- `auto_summary`

have been removed from the active package loader and from runtime skill-card emission.

Artifact persistence now requires `output_slot` directly.
There is no fallback to retired compatibility fields.

### 4. `track-manager` is represented cleanly

`track-manager` is now explicitly modeled as:

- `produces_artifact = false`
- no `output_slot`

Runtime tests now protect the expectation that its skill card omits artifact-slot output metadata while still remaining a valid resolved skill.

### 5. Shared runtime boilerplate has been extracted

Repeated artifact-skill runtime rules have been moved into:

- `framework/docs/skill-runtime-shared-rules.md`

The artifact-producing skill docs now point to that shared runtime rules document instead of repeating:

- execution summary persistence
- task/artifact boundary rules
- durable output path rules

Skill-local required output fields remain in each skill doc.

### 6. Skill descriptions are now activation-oriented

All six `skill.toml` files now use `Use when ...` descriptions.

The descriptions are no longer written in the earlier “this skill does X” style that mixed capability summary with trigger semantics.

Repo consistency tests now check:

- every skill description begins with `Use when `
- descriptions avoid a small set of obvious workflow-summary tokens

## Current Status By Category

### Package Structure

Current state:

- clear
- active
- consistent with the v2 package contract

Each skill package now has:

- `skill.toml`
- `SKILL.md`
- package-local assets where needed

### Runtime Authority

Current state:

- clean of historical skill-loader compatibility paths
- clean of migration-only runtime compatibility fields

The runtime now resolves package metadata, emits package-backed skill cards, and persists artifact-producing skills strictly through `output_slot`.

### Skill Documentation

Current state:

- materially cleaner than the earlier review snapshot
- still self-contained for skill-local behavior
- no longer bloated by repeated shared runtime boilerplate

The one important local refinement added after extraction was to restore PM-specific track/handoff guidance inside `write-prd`, rather than forcing that PM-specific rule into the shared runtime doc.

## Remaining Risk

No active historical compatibility residue remains in the skill runtime path reviewed here.

The main remaining limitation is not a compatibility issue but a testing limitation:

- static repo-consistency checks can enforce format and some obvious anti-patterns
- they cannot perfectly prove that a description is semantically trigger-oriented in every future edit

That remaining risk is best handled by:

- keeping the consistency checks in place
- continuing lightweight human review for future description edits

## Conclusion

The skill architecture cleanup is functionally complete for the reviewed scope.

The current implementation is no longer accurately described as:

- single-file skill contract
- frontmatter-driven loader
- compatibility-field-based runtime
- duplicated runtime boilerplate across artifact skills

The active BuddySwitch skill model is now:

- package-based
- package-authoritative
- package-only at load time
- slot-based for artifact persistence
- cleaner at the skill-doc boundary

# Codex Native Buddy Skills Test Plan

**Goal:** Verify that launcher-managed buddy instances provide a complete Codex-native skill environment and that BuddySwitch no longer performs custom skill selection, instruction loading, or dual metadata handling.

**Testing Principle:** Tests must start from functional requirements and observable contracts. They must not be written to satisfy a particular implementation shortcut, hidden fixture, or string-only pass condition.

---

## Functional Requirements Under Test

FR1. Starting a buddy instance creates a complete runtime environment for that buddy, including `AGENTS.md`, projected state, `projects/app`, and Codex-native runtime skills.

FR2. Runtime skills are exposed in the Codex CLI native repo/workspace location: `.agents/skills/<skill-id>/SKILL.md`.

FR3. Only the active buddy's skills are present in the instance runtime skill directory.

FR4. Opening or repairing an existing instance refreshes the runtime skill directory and removes stale skills.

FR5. Source skill packages are Codex-native packages with `SKILL.md` YAML frontmatter and no `skill.toml`.

FR6. Skill package assets and supporting files are copied into the runtime `.agents/skills` package unchanged.

FR7. BuddySwitch `prepare` provides context, state, and run envelope data, but does not provide skill candidates, skill instruction paths, or run instructions for a selected skill.

FR8. BuddySwitch `persist` accepts a `skill_id` used by Codex, validates it against the active buddy's manifest membership, validates the result against the persistence schema, and writes canonical state.

FR9. Buddy prompt assets tell the host that Codex CLI owns native skill discovery and use; they do not instruct the host to choose a skill from `prepare_context.skills`.

FR10. The repository has no active dual-format or compatibility residue: no `skill.toml`, no runtime generation of frontmatter from old metadata, no tracked repo-root `.agents`, and no active docs that describe BuddySwitch custom skill loading as current behavior.

FR11. Current community-style Codex skills can be used as BuddySwitch skills when their directory has valid `SKILL.md` frontmatter and the manifest provides the BuddySwitch persistence contract.

## Coverage Matrix

| Requirement | Test Type | Primary Proof |
|---|---|---|
| FR1 | Launcher integration | Fake Codex capture sees instance workspace with prompt, state projections, project projection, and runtime skills |
| FR2 | Launcher integration and repo consistency | `.agents/skills/<skill-id>/SKILL.md` exists in runtime workspace and root `.agents` does not exist |
| FR3 | Launcher integration | PM instance contains PM skills and excludes design/dev/test/market skills |
| FR4 | Launcher integration | Reopen removes a planted stale skill and restores current buddy skills |
| FR5 | Manifest and repo consistency | Every source skill has frontmatter and no `skill.toml`; manifest loads without custom skill metadata |
| FR6 | Runtime skill installer | Asset files copied unchanged into runtime packages |
| FR7 | Runtime contract | Prepare response lacks `skills`, `inputs_by_skill`, `run_instructions_by_skill`, `instruction_path`, and `selected_skill_packet` |
| FR8 | Runtime integration | Persist works for artifact and track-manager runs without `context.skills`; wrong-buddy skill ids are rejected |
| FR9 | Prompt contract | All buddy prompts contain native `.agents/skills` guidance and no custom skill-selection wording |
| FR10 | Residue guard | `rg` and repo tests find no active `skill.toml` or custom skill-loading guidance |
| FR11 | Manifest fixture | Temporary native skill package loads and can be materialized without BuddySwitch-specific package metadata |

## Test Groups

### TG-01: Buddy Instance Runtime Skill Environment

**Requirement:** A user starting a buddy instance receives a workspace where Codex can natively discover the active buddy's skills.

Cases:

1. Start `pm` with fake Codex capture.
   - Expected: command exits 0.
   - Expected: captured `cwd` is the instance workspace.
   - Expected: `AGENTS.md` exists and equals the PM prompt asset.
   - Expected: canonical runtime state paths exist or are projected: `buddyswitch/objects/tracks`, `buddyswitch/objects/tasks`, `buddyswitch/objects/artifacts`, `buddyswitch/content/runs`, and `runs/raw`.
   - Expected: `projects/app` exists and resolves to the shared project workspace.
   - Expected: `.agents/skills/write-prd/SKILL.md` exists.
   - Expected: `.agents/skills/track-manager/SKILL.md` exists.
   - Expected: `.agents/skills/shape-prototype` does not exist.
   - Expected: `.agents/skills/implement-task` does not exist.

2. Start `design` with fake Codex capture.
   - Expected: `.agents/skills/shape-prototype/SKILL.md` exists.
   - Expected: PM, dev, test, and market skill directories do not exist.

3. Start `market` with fake Codex capture.
   - Expected: all six market skill directories exist.
   - Expected: PM/design/dev/test skill directories do not exist.

4. Manifest-driven coverage for every buddy:
   - Read `buddyswitch/manifest.toml`.
   - For each buddy id, run `instance start --buddy <buddy>` with fake Codex capture in an isolated launcher root.
   - Expected: sorted directory names under `.agents/skills` equal exactly the sorted `buddies[*].skills` list from the manifest.

Anti-cheat rule:

- The test must inspect the generated workspace, not only stdout or source prompt files.
- Do not hard-code only PM/design/market. A manifest-driven test must cover every buddy.

### TG-02: Runtime Skill Isolation And Repair

**Requirement:** Runtime `.agents/skills` is deterministic for the active buddy and does not accumulate stale directories.

Cases:

1. Plant `.agents/skills/stale-skill/SKILL.md` in an inactive PM instance, then run `instance open <id>`.
   - Expected: `stale-skill` is removed.
   - Expected: PM skills are present after open bootstrap.

2. Run the runtime skill installer twice for different buddies against the same temporary workspace.
   - Expected: second install contains only the second buddy's skills.

3. Corrupt `.agents/skills/write-prd/SKILL.md` or an asset in an inactive PM instance, then run `instance open <id>`.
   - Expected: the corrupted file is replaced.
   - Expected: runtime package file bytes equal the source package file bytes.

4. Inspect `.git/info/exclude` in the instance workspace.
   - Expected: `.agents/skills/**` is excluded.
   - Expected: runtime state excludes still remain.

Anti-cheat rule:

- Do not satisfy repair by only adding missing skills. The stale directory must be removed.
- Do not satisfy refresh by only checking directories. At least one file must be proven byte-equal to source after repair.

### TG-03: Codex Native Source Package Compliance

**Requirement:** BuddySwitch source skill packages are directly compatible with Codex skill loading.

Cases:

1. For every manifest skill path:
   - Expected: `SKILL.md` exists.
   - Expected: first non-empty line is `---`.
   - Expected: frontmatter has a closing `---` delimiter.
   - Expected: the project frontmatter parser extracts a non-empty top-level scalar `name`.
   - Expected: the project frontmatter parser extracts a non-empty top-level scalar `description`.
   - Expected: quoted and unquoted scalar values work, including descriptions containing colons.
   - Expected: frontmatter `name` equals the manifest skill id.
   - Expected: `skill.toml` does not exist.

2. For each source package with assets:
   - Expected: assets remain under the skill package.
   - Expected: runtime install preserves asset relative paths and file bytes.

3. Temporary community-style skill fixture:
   - Source package contains only `SKILL.md` frontmatter and markdown body.
   - Manifest entry supplies BuddySwitch persistence fields.
   - Expected: manifest loads.
   - Expected: installer copies the package to `.agents/skills/<id>`.

Anti-cheat rule:

- Do not pass by accepting both `skill.toml` and frontmatter. Presence of `skill.toml` must fail repo consistency.

### TG-04: Codex Loader Compatibility Smoke

**Requirement:** The runtime package shape matches Codex CLI's native expectations, not merely BuddySwitch's tests.

Cases:

1. Automated structural smoke:
   - In a generated runtime workspace, every installed skill path matches `.agents/skills/<skill-id>/SKILL.md`.
   - Every installed `SKILL.md` has YAML frontmatter with `name` and `description`.
   - No installed package has `skill.toml`.
   - Fake Codex capture proves the process `cwd` is the instance workspace root that contains `.agents/skills`.

2. Optional manual/local Codex smoke when Codex CLI is available:
   - Start a PM instance.
   - Run `codex debug prompt-input` from the instance workspace.
   - Expected: prompt input/session context includes native PM skills without BuddySwitch injecting `instruction_path`.
   - This is a non-gating canary unless converted into a skip-if-unavailable automated test.

3. Explicit skill invocation smoke:
   - In the PM instance, ask for a request that should trigger `write-prd`.
   - Expected: Codex can use the native skill package.
   - Expected: BuddySwitch state writing happens only after `persist`.

Anti-cheat rule:

- Do not define compatibility as "file exists" alone. At least one smoke path must compare against Codex's documented/native directory and frontmatter contract.

### TG-05: Prepare Context No Longer Performs Skill Selection

**Requirement:** `prepare` is a context preparation step, not a skill router.

Cases:

1. Prepare in PM instance context with `Draft onboarding PRD`.
   - Expected: `ok=true`.
   - Expected: `active_buddy=pm`.
   - Expected: `current_task_id` and `run_envelope.run_id` exist.
   - Expected: top-level keys exactly match the allowlist in `framework/contracts/prepare-turn-context.json`.
   - Expected: no `skills` key.
   - Expected: no `inputs_by_skill` key.
   - Expected: no `run_instructions_by_skill` key.
   - Expected: no `selected_skill_packet` key.
   - Expected: serialized response contains no `instruction_path`.
   - Expected: recursive scan finds no `skill_candidates`, `skill_instructions`, `selected_skill`, or per-skill run instruction packet under any renamed field.

2. Prepare in dev instance context with implementation request.
   - Expected: same context-only shape.
   - Expected: no skill list despite dev having only one skill.

3. Prepare with malformed structural legacy input.
   - Input: `switch pm: Draft the PRD`.
   - Expected: rejection behavior remains unchanged.
   - Expected: `ok=false` or non-zero CLI exit according to the existing prepare error contract.
   - Expected: no writes appear under `buddyswitch/objects/tasks`, `buddyswitch/objects/artifacts`, `buddyswitch/content/runs`, or `runs/raw`.

Anti-cheat rule:

- Do not remove only the top-level `skills` key while leaving equivalent skill candidates under a renamed field.
- Do not rely only on known legacy names. Use an allowlisted top-level contract plus recursive forbidden-concept checks.

### TG-06: Persist Skill Attribution And State Writing

**Requirement:** `persist` records the skill Codex used while BuddySwitch validates state and schemas.

Artifact cases:

1. Prepare PM context and persist a valid `write-prd` result.
   - Expected: context has no `skills`.
   - Expected: persist succeeds with `skill_id=write-prd`.
   - Expected: receipt includes task id, artifact id, run id, and receipt paths.
   - Expected: artifact object has `skill_id=write-prd`.

2. Prepare dev context and persist a valid `implement-task` result.
   - Expected: persist succeeds with no context skill list.
   - Expected: receipt references the dev task and implementation artifact.

Track-manager cases:

1. Prepare PM context and persist a valid `track-manager` create result.
   - Expected: persist succeeds.
   - Expected: no artifact is written.
   - Expected: receipt includes track id and track action.

Rejection cases:

1. PM context with missing, empty, or whitespace-only `skill_id`.
   - Expected: persist rejects.
   - Expected: no artifact/run commit occurs.

2. PM context with `skill_id=implement-task`.
   - Expected: persist rejects wrong-buddy skill id.
   - Expected: no artifact/run commit occurs.

3. PM context with unknown `skill_id`.
   - Expected: persist rejects unknown skill id.
   - Expected: no artifact/run commit occurs.

4. Valid buddy skill id with invalid result payload.
   - Expected: schema validation rejects.
   - Expected: no partial artifact commit occurs.

5. Valid PM skill id paired with another PM skill's valid payload shape, for example `skill_id=write-prd` with a `track-manager` result payload.
   - Expected: schema validation rejects because the payload does not match the selected skill's persistence schema.
   - Expected: no partial artifact commit occurs.

Anti-cheat rule:

- At least one success case must call real `prepare` and real `persist`, then inspect persisted files. Do not use a fake context fixture only.
- Rejection cases must compare state snapshots before and after persist to prove no partial writes.

### TG-07: Runtime Prompt Contract

**Requirement:** Buddy prompts describe the native Codex skill path and do not preserve custom BuddySwitch skill-selection instructions.

Cases:

1. For every `tools/launcher/assets/buddies/<buddy>/AGENTS.md`:
   - Expected: contains `.agents/skills`.
   - Expected: says Codex CLI owns native skill discovery/use.
   - Expected: says `prepare` provides context.
   - Expected: says `persist` records the Codex skill name as `skill_id`.
   - Expected: retains receipt and summary contract.

2. Forbidden prompt text:
   - `Choose exactly one skill_id from prepare_context.skills`
   - `Read and execute the selected BuddySwitch SKILL.md`
   - `instruction_path`
   - `selected_skill_packet`
   - `run_instructions_by_skill`

3. Launcher-generated workspace prompt:
   - Start PM and design instances with fake Codex capture.
   - Expected: generated `AGENTS.md` matches source asset.
   - Expected: generated prompt has native skill guidance and no forbidden text.

Anti-cheat rule:

- Do not check only source prompt assets. At least one test must inspect generated instance `AGENTS.md`.

### TG-08: Residue And No-Dual-Track Guard

**Requirement:** The repository must not preserve active old custom skill handling as an alternate path.

Cases:

1. Search active source and documentation paths for custom skill-selection residue:

```bash
rg -n "prepare_context\\.skills|instruction_path|selected_skill_packet|run_instructions_by_skill|Choose exactly one skill_id|Read and execute the selected BuddySwitch" README.md AGENTS.md framework tools scripts buddyswitch
```

Expected: no active implementation, prompt, or docs references.

2. Repo root `.agents` remains absent.

3. Runtime `.agents/skills` documentation is allowed only when described as launcher-managed instance materialization.

4. No code path writes skills into user `$HOME/.agents/skills` or deprecated `$CODEX_HOME/skills`.

5. `skill.toml` appears only in explicit rejection/error/assertion code and this plan. No `buddyswitch/skills/**/skill.toml` file exists and no active loader reads it as metadata.

6. Tests may contain forbidden strings only as explicit residue assertions with allowlisted test file paths.

Anti-cheat rule:

- Do not silence this group by narrowing the search to skip active docs or prompt assets.
- Do not require zero `skill.toml` string matches in rejection tests or installer validation errors; require zero active metadata-loading use.

### TG-09: Failure Behavior

**Requirement:** Invalid skill environment setup fails before Codex starts and leaves clear diagnostics.

Cases:

1. Manifest references a missing skill path.
   - Expected: `instance start --buddy <buddy>` fails before fake Codex capture is written.
   - Expected: error names the missing package path.

2. Source package has `SKILL.md` without frontmatter.
   - Expected: installer fails before Codex starts.
   - Expected: error names the invalid `SKILL.md`.

3. Source package contains stale `skill.toml`.
   - Expected: manifest or installer fails.
   - Expected: error explains dual metadata is not allowed.

4. Workspace `.agents/skills` cannot be removed or created.
   - Expected: launcher exits non-zero.
   - Expected: Codex is not launched.

5. Manifest skill id contains `/`, `\`, `..`, or path separators.
   - Expected: manifest loading or runtime installer rejects before any workspace mutation.

6. Manifest skill path is absolute or escapes the repo root with `..`.
   - Expected: manifest loading or runtime installer rejects before any workspace mutation.

7. Source skill package path or runtime target path contains a symlink boundary.
   - Expected: runtime installer rejects before deleting the existing runtime skill directory.

8. `--workspace` is empty, `/`, a file, or resolves outside the intended temporary/instance workspace.
   - Expected: runtime installer rejects before deleting or copying files.

Anti-cheat rule:

- Do not allow fallback to old `skill.toml` parsing after native package validation fails.
- Do not mutate the runtime skill directory before all source and target path safety checks pass.

## Required Verification Commands

Focused suite:

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

Syntax check:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env_manifest.py scripts/runtime_skills.py scripts/turn_runtime.py
```

Residue check:

```bash
rg -n "prepare_context\\.skills|instruction_path|selected_skill_packet|run_instructions_by_skill|Choose exactly one skill_id|Read and execute the selected BuddySwitch" README.md AGENTS.md framework tools scripts buddyswitch
```

Expected: no output.

Run repo consistency tests for allowlisted `skill.toml` rejection/error mentions and forbidden-string assertion mentions.

Optional manual Codex smoke:

```bash
./buddyswitch-codex instance start --buddy pm -- debug prompt-input "Draft the onboarding PRD"
```

This smoke is non-gating unless implemented as a skip-if-unavailable automated test.

## Completion Criteria

- Functional tests prove the active buddy gets only its own Codex-native skills in runtime `.agents/skills`.
- Source package tests prove there is no `skill.toml` dual metadata.
- Prepare tests prove BuddySwitch no longer exposes custom skill selection/loading fields.
- Persist tests prove state writing still works and validates `skill_id` from manifest membership.
- Prompt tests prove actual generated instances tell Codex to use native skills.
- Residue checks prove active docs and code do not preserve the retired BuddySwitch custom skill path.

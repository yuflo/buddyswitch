# Dev Source Root And Skill Rebuild Test Plan

Date: 2026-05-21
Scope: `docs/spec/2026-05-21-dev-source-root-skill-rebuild-scope.md`

## Test Strategy

Test from the product/runtime requirements:

- Dev should know the source root through runtime-visible facts, not AGENTS prose.
- Dev should only be able to write product source in the intended source root.
- Non-Dev buddies should not be able to write product source.
- README-only source roots should be recognized as present but not scaffolded.
- Dev skills should teach a complete product-engineering workflow without copying runtime schemas or hardcoding directory authority.

Do not construct tests to match a helper's private implementation. Tests should inspect generated profiles, context tool responses, materialized skills, AGENTS templates, and visible filesystem behavior.

## Requirement Matrix

R1. Runtime buddy AGENTS templates do not mention the concrete source path or project access values.

R2. AGENTS templates still contain startup runtime discovery and broker-boundary guidance.

R3. Dev sandbox profile grants write access to the product source root only, not to the whole project workspace if that would include non-source paths.

R4. Env profile and contract use unambiguous source-root permission language; no field named as a project-workspace permission target may be the authority for source-root write access.

R5. Dev sandbox profile keeps runtime workspace, state root, shared root, repo root, and instance root non-writable.

R6. Non-Dev sandbox profiles keep product source read-only.

R7. Temp writable roots cannot be placed inside product source, state root, project root, instance root, or runtime workspace.

R8. Shared project worktree sparse checkout exposes only the product source subtree and rejects dirty non-source entries.

R9. Runtime workspace source projection points to the shared product source root and does not expose runtime object state as source.

R10. `context.summarize` includes compact source facts for active buddy, source path, access, write capability, source state, bounded top-level entries, provenance, and permission boundary.

R11. `context.get` includes the same source facts.

R12. `context.list_sources` describes `source_workspace` as read-only orientation data.

R13. Context tool definition metadata names `source_workspace` in returns/effect descriptions and states it does not configure or grant write access.

R14. Source state is `missing` when the source root does not exist.

R15. Source state is `empty` when the root exists but has no entries.

R16. Source state is `readme_only` when the root has README-only content.

R17. Source state is `has_source` when source/application files are present.

R18. Context source facts do not include source file bodies.

R19. Context source facts are derived from runtime profile/instance data, not from AGENTS text, cwd guessing, or literal path fallback.

R20. No new project/dev-env/source-write tool is registered.

R21. Registry guardrails forbid source-write/configure tools and actions without freezing the entire supported-tool set.

R22. Dev manifest routes include the new Dev skills.

R23. Dev manifest no longer routes the catch-all `implement-task` as the primary implementation skill.

R24. `skill-creator-importer` remains registered for Dev platform maintenance.

R25. New Dev skills have valid `SKILL.md` frontmatter and materialize for Dev.

R26. Dev skills reference runtime context/source facts without copying full tool schemas or payload tables.

R27. Dev skills do not treat the concrete source path text as the authority for the source root.

R28. Dev skills include README-only handling and distinguish it from missing source.

R29. Dev skills require changed files to remain under the locked runtime source root without banning legitimate source-root scaffolds, lockfiles, generated app files, or tests.

R30. Dev report skill writes product-readable reports through artifact/request/track routes, not source folders.

R31. Dev skill files contain complete operational sections and pass scenario-based content checks, not only loose keyword scans.

R32. Runtime skill guardrails continue to forbid old env client flags and handoff residue.

R33. Existing product-mode launcher tests still prove shared project workspace isolation.

R34. True Codex sandbox smoke checks prove Dev write and non-Dev non-write behavior when the local sandbox is available.

R35. Full relevant suite passes.

R36. Profile-resolution failure is explicit rejection or unavailable context, not `state = "missing"`.

## Detailed Test Design

### T1: AGENTS Does Not Carry Source Directory Facts

File: `tests/test_repo_consistency.py`

Seed: read all files under `tools/launcher/assets/buddies/*/AGENTS.md`.

Assertions:

- none of the AGENTS files contains the concrete project source path string;
- none contains `project.access=`;
- all still include `context summarize --payload '{}'`;
- all still include `context get --payload '{}'`;
- all still say AGENTS is guidance only and not the permission source;
- all still say runtime tool rejections must not be bypassed.

This proves source directory facts moved out of prompt prose while startup discovery remains intact.

### T2: Dev Write Scope Is Product Source Root, Not Whole Project Workspace

File: `tests/test_buddy_env_sandbox.py`

Seed:

- `shared_root = temp/shared`;
- `project_workspace_dir = shared_root/project/workspace`;
- product source root is the profile-declared source path under that workspace;
- buddy is `dev`.

Assertions:

- env profile contract exposes source-root access semantics directly, not an ambiguous project-workspace permission authority;
- generated config marks product source root as `write`;
- generated config does not mark project workspace root as `write` when project workspace and source root differ;
- generated config marks runtime workspace as `read`;
- generated config marks shared state root as `none`;
- generated config marks repository root as `none`;
- generated writable paths include only home, codex-home, xdg-config, safe temp roots, and product source root.

This test must fail against any implementation that grants Dev broad project workspace writes.

### T3: Non-Dev Source Root Is Read-Only

File: `tests/test_buddy_env_sandbox.py`

Seed: generate profile configs for `pm`, `design`, `market`, and `test`.

Assertions for each buddy:

- product source root is readable;
- product source root is not writable;
- project workspace root is not writable;
- runtime workspace is not writable;
- state root is `none`;
- safe home/codex/config/temp roots remain writable as expected.

### T4: Temp Roots Cannot Reopen Source Or Runtime Boundaries

File: `tests/test_buddy_env_sandbox.py`

Seed:

- pass `--temp-root` values under product source root, project workspace root, state root, instance root, and runtime workspace;
- run once for `dev`, once for `pm`.

Assertions:

- none of those temp roots appears as writable;
- normal `/tmp` safe root remains writable when allowed;
- generated config does not contain nested writes that bypass product source or runtime boundaries.

### T5: Product Worktree Sparse Boundary Still Holds

File: `tests/test_buddyswitch_launcher.py`

Seed: start a buddy instance in a temporary shared root using fake codex/git helpers already used in launcher tests.

Assertions:

- shared project worktree exists;
- sparse checkout list equals the single product source path;
- forbidden entries such as `buddyswitch`, `tools`, `scripts`, `tests`, `framework`, `docs`, root `AGENTS.md`, root `README.md`, and launcher binary are absent from the project worktree;
- runtime workspace source projection resolves to the shared product source root;
- runtime workspace does not expose `.runtime` under product source.

These launcher tests are topology/projection tests. If they use fake Codex helpers, they must not be described as permission enforcement tests; fake Codex writes from the test process and does not prove sandbox allow/deny behavior.

### T6: Context Source Facts For Dev

File: `tests/test_context_binding_env_tool.py`

Seed:

- instance payload for active buddy `dev`;
- source root exists with README-only content.

Assertions:

- `context.summarize` returns `source_workspace.active_buddy == "dev"`;
- `source_workspace.path` is the runtime-declared relative source path;
- `source_workspace.access == "write"`;
- `source_workspace.can_write_source is True`;
- `source_workspace.state == "readme_only"`;
- `source_workspace.top_level_entries` is a bounded list of entry names;
- `source_workspace.top_level_entries_truncated` indicates whether the list hit its bound;
- `source_workspace.source_of_truth` identifies env profile/workspace projection provenance;
- `source_workspace.permission_boundary` says context is read-only and does not configure or grant writes;
- no row contains README body content.

### T7: Context Source Facts For Non-Dev

File: `tests/test_context_binding_env_tool.py`

Seed: active buddy `pm` with same source root.

Assertions:

- `source_workspace.access == "read-only"`;
- `source_workspace.can_write_source is False`;
- `source_workspace.state` still reflects the real source root state;
- `source_workspace.permission_boundary` remains read-only context orientation;
- PM source facts do not grant or suggest write authority.

### T8: Source State Classification

File: `tests/test_context_binding_env_tool.py` or focused `tests/test_source_workspace_context.py`

Subcases:

- missing source root;
- existing empty directory;
- directory containing only `README.md`;
- directory containing `package.json`;
- directory containing app files under `src/` or equivalent source-like entries.

Assertions:

- missing -> `missing`;
- empty -> `empty`;
- README-only -> `readme_only`;
- package/source-like entries -> `has_source`;
- non-empty, non-README-only roots without known framework hints -> `has_source` means source-root content exists for inspection, not that a runnable app was verified;
- summary includes top-level hint names but no file bodies.

### T8A: Context Does Not Trust AGENTS Source Facts

File: `tests/test_context_binding_env_tool.py`

Seed:

- env profile declares source path/access;
- temporary AGENTS text contains a deliberately wrong concrete source path or wrong write-access statement.

Assertions:

- `context.summarize` and `context.get` return the env-profile/workspace-projected source facts;
- wrong AGENTS text does not affect `source_workspace.path`, `source_workspace.access`, or `source_workspace.can_write_source`;
- if the env profile cannot load or validate, the context response is an explicit rejection/unavailable result rather than `state = "missing"`.

This proves AGENTS is guidance, not source-root authority.

### T9: No New Project Or Source-Write Tool

File: `tests/test_repo_consistency.py`

Assertions:

- `env.tool_runtime.registry.supported_tools()` does not include `project`, `dev_env`, `source`, `filesystem`, or `workspace_write`;
- supported action names across all tools do not include `apply_patch`, `write_file`, `delete_file`, or `configure_project`;
- there is no `scripts/env/tools/project` package;
- there is no `scripts/env/tools/dev_env` package.

### T10: Dev Manifest Skill Routing

File: `tests/test_runtime_skills.py`

Assertions:

- manifest contains skill ids:
  - `enter-dev-workspace`;
  - `read-implementation-context`;
  - `handle-empty-source-root`;
  - `implement-scoped-change`;
  - `debug-regression`;
  - `select-local-verification`;
  - `write-implementation-report`;
  - `prepare-review-readiness`;
- Dev buddy skill list includes those ids;
- Dev buddy skill list includes `skill-creator-importer`;
- Dev buddy skill list does not include `implement-task`;
- every registered skill path has `SKILL.md`.

### T11: Dev Skills Do Not Copy Runtime Schemas

File: `tests/test_runtime_skills.py`

Assertions over new Dev skill files:

- no `payload_fields`;
- no `operation_semantics` table;
- no `**payload:**` block;
- no `**returns:**` block;
- no action catalog table;
- allowed references are `context.summarize`, `context.get`, `python3 scripts/turn_runtime.py status`, runtime response fields, and shared tool skills.

### T12: Dev Skills Do Not Use Concrete Source Path As Authority

File: `tests/test_runtime_skills.py`

Assertions over new Dev skill files:

- files may mention "runtime source root" and "locked source root";
- files do not use the concrete path string as the authority sentence;
- if the concrete path appears in an example, the same paragraph must say runtime context/profile is authoritative;
- `enter-dev-workspace` says to lock the source root from context source facts;
- implementation/report skills say changed source files must remain under the locked source root.

### T13: README-Only Handling Skill Coverage

File: `tests/test_runtime_skills.py`

Assertions:

- `handle-empty-source-root` contains the terms `missing`, `empty`, `readme_only`, and `has_source`;
- it states README-only is not source-link missing;
- it permits scaffolding only when the user directly asks for app/source creation, or a PM/PRD/approved artifact clearly asks for it;
- it routes unclear product-scope decisions back to PM/user rather than inventing scope.

### T14: Implementation Report Skill Coverage

File: `tests/test_runtime_skills.py`

Assertions:

- `write-implementation-report` requires changed files;
- it requires verification commands or blocked-verification reason;
- it requires risks/follow-ups;
- it says durable reports use artifact/request/track routes;
- it says source folders must not receive runtime report noise.

### T15: Runtime Skill Guardrails Still Pass

Files:

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

Assertions:

- old env client flag scan still passes;
- handoff residue scan still passes;
- publication path guardrails still pass;
- shared tool skills still route exact contracts to runtime discovery.

### T16: Env Profile Contract Uses Source-Root Permission Semantics

File: `tests/test_buddy_env_profiles.py`

Assertions:

- `framework/contracts/buddy-env-profile.json` names the filesystem permission target as source root, not project workspace;
- all profiles use the new source-root permission key;
- Dev profile source-root access is `write`;
- market/pm/design/test profile source-root access is `read-only`;
- validation rejects profiles that contain both old and new permission keys;
- `project.path` still defines the product source path inside the shared project worktree.

This test should not care about the internal helper names used to load profiles. It proves the runtime contract exposed to tools and launcher code is semantically clear.

### T17: Context Tool Metadata Describes Source Workspace Semantics

Files:

- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_schema_contract.py` if a schema-level test is already a better local fit.

Assertions:

- `context.get` action metadata includes `source_workspace` in returned sections;
- `context.summarize` action metadata includes `source_workspace` in returned sections;
- `context.list_sources` includes a `source_workspace` descriptor;
- descriptor text says source facts are read-only orientation data;
- descriptor text says context does not configure roots or grant write permission;
- no context action mutates product source or runtime state.

This catches the `docs/bitter` class of failure where the action works but the tool catalog leaves the host guessing.

### T18: True Sandbox Source-Root Smoke

File: `tests/test_buddy_env_sandbox.py`

Seed:

- generate profile configs for Dev and PM in temp roots;
- create a runtime workspace path and product source root path;
- run `codex sandbox macos --permissions-profile buddyswitch-runtime` when local platform and CLI support it.

Assertions:

- Dev can write a file under the product source root;
- Dev cannot write under project workspace outside the product source root;
- Dev cannot write under sibling paths such as `tools/` or `docs/` if those paths exist in the projected workspace;
- Dev cannot write under runtime workspace or raw state;
- PM can read the product source root when a file exists;
- PM cannot write under the product source root;
- test skips with a clear reason when the Codex sandbox command is unavailable.

This complements config inspection. Fake Codex launcher tests still prove startup wiring, but they do not prove the OS sandbox enforces writes.

### T19: Dev Skill Operational Section And Scenario Coverage

File: `tests/test_runtime_skills.py`

Assertions over each new Dev skill:

- has frontmatter `name` and trigger-only `description`;
- has `Use when`, `Do not use when`, `Inputs`, `Steps`, `Outputs`, `Guardrails`, and either `Verification` or `Stop conditions`;
- does not copy payload schemas, return schemas, or operation catalogs;
- references shared tool skills or runtime discovery surfaces for exact tool details;
- includes at least one concrete scenario sentence for its main failure mode.

Required scenario coverage:

- `enter-dev-workspace`: missing `source_workspace` and README-only source root;
- `read-implementation-context`: artifact id mentioned but artifact body unread;
- `handle-empty-source-root`: scaffold requested explicitly versus absent scope;
- `implement-scoped-change`: changed file outside locked root;
- `debug-regression`: patch attempted before reproduction/root cause;
- `select-local-verification`: no project test command found;
- `write-implementation-report`: verification blocked;
- `prepare-review-readiness`: residual risk for Test/review.

This avoids a shallow keyword-only pass while still leaving the skill writer free to choose concise wording.

## Verification Commands

Focused checks:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py -q
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Final check:

```bash
python3 -m pytest -q
```

## Pass Criteria

The task is not complete unless all requirement IDs R1-R36 are covered by at least one test and all focused verification commands pass. If full pytest is blocked by an unrelated pre-existing failure, record the exact failing test, failure output, and why it is unrelated before asking for user direction.

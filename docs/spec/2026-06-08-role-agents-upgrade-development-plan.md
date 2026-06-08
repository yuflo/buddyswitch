# Role AGENTS Bootstrap Upgrade Development Plan

> **For agentic workers:** Use TDD for behavior changes. Add the role bootstrap regression test first, verify it fails for the current generic role files, then update the role `AGENTS.md` assets and run focused verification. Keep the change content-only except for tests and specs.

**Goal:** Upgrade `tools/launcher/assets/roles/*/AGENTS.md` into short role bootstrap files with shared runtime rules, concise role entry rules, and role-specific output rules.

**Architecture:** This is a direct asset replacement guarded by repo consistency tests. Runtime permissions remain enforced by env profiles, contracts, broker policy, and env tools; no launcher behavior or runtime storage contract changes are needed.

**Tech Stack:** Markdown role assets, Python `unittest`/pytest consistency tests, existing launcher asset copy path.

---

## Task 1: Add Role Bootstrap Regression Test

**Files:**

- Modify: `tests/test_repo_consistency.py`

Steps:

- [ ] Add `test_runtime_role_agents_are_short_role_bootstraps`.
- [ ] In the test, iterate `("market", "pm", "design", "dev", "test")`.
- [ ] Assert each role asset starts with `# BuddySwitch Runtime Workspace`.
- [ ] Assert each role asset includes `## Bootstrap Rules`, `## Role Entry`, and `## Output Rule`.
- [ ] Assert each role asset says `AGENTS.md is bootstrap guidance only and not the permission source.`
- [ ] Assert shared runtime rules preserve active role lock, runtime context summary, env MCP durable state, `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, Buddybox/private boundary, artifact full-body rule, search/browser route, and broker rejection behavior.
- [ ] Assert role-specific fragments listed in the test plan for each role.
- [ ] Assert forbidden fragments are absent: old section name, payload schema wording, JSON examples, hardcoded source-root path, old env client examples, retired flags, permission sourced from `AGENTS.md`.
- [ ] Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_are_short_role_bootstraps -q
```

Expected: fail because current role assets still use generic `## Runtime Boundary` and lack complete `## Role Entry` sections.

## Task 2: Replace Role AGENTS Assets

**Files:**

- Modify: `tools/launcher/assets/roles/design/AGENTS.md`
- Modify: `tools/launcher/assets/roles/dev/AGENTS.md`
- Modify: `tools/launcher/assets/roles/market/AGENTS.md`
- Modify: `tools/launcher/assets/roles/pm/AGENTS.md`
- Modify: `tools/launcher/assets/roles/test/AGENTS.md`

Steps:

- [ ] Use the same top-level structure in all five files.
- [ ] Keep shared `Bootstrap Rules` short and consistent across roles.
- [ ] Add `Role Entry` bullets for each role from the memo and authoritative contracts.
- [ ] Keep output rules concrete but short.
- [ ] Do not add workflow manuals, tool schemas, payload examples, source-root paths, or permission-source claims.
- [ ] Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_are_short_role_bootstraps -q
```

Expected: pass.

## Task 3: Run Existing Guidance Regressions

**Files:**

- Verify: `tests/test_repo_consistency.py`
- Verify: `tests/test_runtime_skills.py`

Steps:

- [ ] Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_use_native_first_env_tool_guidance tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_contract_and_agents_align_with_generic_skill_surface -q
```

Expected: pass.

## Task 4: Verify Launcher Copy Path

**Files:**

- Verify: `tests/test_buddyswitch_launcher.py`
- Verify: `tools/launcher/workspace.sh`

Steps:

- [ ] Run the focused fake-executable launcher-copy test only:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q
```

Expected: pass. Do not run the full launcher suite unless this focused test fails for a launcher reason.

## Task 5: Audit And Final Review

**Files:**

- Verify: `tools/launcher/assets/roles`
- Verify: `docs/spec/2026-06-08-role-agents-upgrade-test-plan.md`
- Verify: `docs/spec/2026-06-08-role-agents-upgrade-development-plan.md`
- Verify: `docs/spec/2026-06-08-role-agents-upgrade-phase2-prompt.md`

Steps:

- [ ] Run:

```bash
rg -n "## Runtime Boundary|AGENTS.md is guidance only and not the permission source|projects/app|payload schema|payload_fields|tool catalog dump|JSON example|python3 scripts/env/client.py|search open-browser --payload|context summarize --payload" tools/launcher/assets/roles
```

Expected: exit 1 or no output.

- [ ] Run:

```bash
git diff --check
```

Expected: exit 0.

- [ ] Review the diff against the memo and test plan.
- [ ] Confirm no runtime code path, env profile, framework contract, manifest, or storage object was modified.

## Self-Review

- Spec coverage: the development tasks cover the memo's shared structure, role entries, negative constraints, test planning, execution prompt, implementation, verification, and review.
- Placeholder scan: no `TBD`, `TODO`, or vague "add tests" steps remain.
- Type/path consistency: all file paths match existing repo layout.
- Scope guard: no compatibility layer, runtime behavior change, plugin system, tool schema duplication, or source-root hardcoding is planned.

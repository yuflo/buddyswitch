# Role AGENTS Bootstrap Upgrade Phase 2 Prompt

Use this prompt from the repository root or an isolated worktree. Do not modify the main checkout unless explicitly instructed.

```text
Complete the Role AGENTS bootstrap upgrade from:

- docs/spec/2026-06-08-role-agents-upgrade-test-plan.md
- docs/spec/2026-06-08-role-agents-upgrade-development-plan.md
- source memo docs/memo/2026-06-08-role-agents-upgrade-direction.html

Rules:

1. Follow SHARP: shortest verified path, no transitional compatibility, no speculative abstraction.
2. Read the current role AGENTS assets, env profiles, contracts, manifest, and existing tests before editing.
3. Use TDD:
   - Add the focused role bootstrap regression test first.
   - Run it and confirm it fails for the current generic role AGENTS files.
   - Only then update role AGENTS assets.
4. Keep the implementation scope to:
   - tests/test_repo_consistency.py
   - tools/launcher/assets/roles/{pm,design,dev,market,test}/AGENTS.md
   - docs/spec/2026-06-08-role-agents-upgrade-*.md if the plan needs correction
5. Do not edit runtime storage objects or old private runtime paths directly.
6. Do not add tool schemas, JSON payload examples, workflow manuals, hardcoded source-root paths, or permission claims sourced from AGENTS.md.
7. Avoid broad service-starting tests. Respect docs/bitter/2026-05-26-test-resource-lifecycle-principles.md.

Required verification:

1. RED:
   python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_are_short_role_bootstraps -q

2. GREEN:
   python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_are_short_role_bootstraps -q

3. Existing guidance regressions:
   python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_runtime_role_agents_use_native_first_env_tool_guidance tests/test_runtime_skills.py::RuntimeSkillsTests::test_pm_contract_and_agents_align_with_generic_skill_surface -q

4. Launcher copy regression:
   python3 -m pytest tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_start_execution_worktree_uses_runtime_workspace_agents_header -q

5. Source audit:
   rg -n "## Runtime Boundary|AGENTS.md is guidance only and not the permission source|projects/app|payload schema|payload_fields|tool catalog dump|JSON example|python3 scripts/env/client.py|search open-browser --payload|context summarize --payload" tools/launcher/assets/roles
   Expected: no output.

6. Whitespace check:
   git diff --check

Final review:

- Re-read the memo, test plan, development plan, tests, and diff.
- Confirm every role has Bootstrap Rules, Role Entry, and Output Rule.
- Confirm every role entry is concise and traceable to env profiles/contracts/manifest.
- Confirm no launcher/runtime behavior was changed.
- Report changed files, verification commands with outcomes, and remaining risk.
```

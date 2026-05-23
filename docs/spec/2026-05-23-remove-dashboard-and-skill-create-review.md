# Remove Legacy Dashboard And Skill Create Plan Review

Date: 2026-05-23

## Review Goal

Check the objective, test plan, and development plan before implementation starts.

Reviewed files:

- `docs/spec/2026-05-23-remove-dashboard-and-skill-create-objective.md`
- `docs/spec/2026-05-23-remove-dashboard-and-skill-create-test-plan.md`
- `docs/spec/2026-05-23-remove-dashboard-and-skill-create-development-plan.md`

## Scope Audit

### Dashboard Delete Scope

Covered:

- `scripts/serve_context_panel.py`
- `framework/console/index.html`
- `framework/console/app.js`
- `framework/console/styles.css`
- `framework/contracts/workspace-projection.json`
- `scripts/workspace_data.py`
- `scripts/runtime_store/projections.py`
- `tests/test_console_app_contract.py`
- `tests/test_parallel_contracts.py`
- `README.md` Context Panel references
- `AGENTS.md` Context panel reference
- `tests/test_repo_consistency.py` dashboard assumptions
- `tests/test_memory_removal_contract.py` dashboard projection dependency

No missing dashboard file found in the scan:

```bash
rg -n -i 'Context Panel|serve_context_panel|workspace-projection|framework/console|dashboard' AGENTS.md README.md scripts tests framework buddyswitch tools
```

### Skill Create Delete Scope

Covered:

- `scripts/skill_creator_importer.py`
- `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- `tests/test_skill_creator_importer.py`
- `tests/fixtures/community-skills/dev-summary/SKILL.md`
- `buddyswitch/manifest.toml` skill registration
- `buddyswitch/manifest.toml` Dev buddy skill list
- `tests/test_runtime_skills.py`
- `tests/test_buddyswitch_launcher.py`

No missing skill-create/importer file found in the scan:

```bash
rg -n 'skill-creator-importer|skill_creator_importer|community-skills|skill creator|skill create|Import a Codex-native skill' AGENTS.md README.md scripts tests buddyswitch tools framework
```

## Protected Boundary Audit

The plans explicitly preserve:

- `tools/launcher/browser_cockpit.sh`
- `tests/test_browser_cockpit_launcher.py`
- `chrome-devtools-cockpit` MCP setup/config/tests
- `scripts/env/tools/search/**`
- market and design skill browser workflow guidance
- app-server lifecycle integration with browser cockpit
- `scripts/runtime_skills.py`
- normal `buddyswitch/skills/**` packages except the importer package
- `scripts/env/tools/context/**`
- `framework/contracts/prepare-turn-context.json`
- `tests/test_context_binding_env_tool.py`
- `tests/test_prepare_runtime_context.py`

This addresses the main risk from broad keyword scans: `browser_cockpit` is core runtime capability and is not part of the old dashboard removal.

## Test Coverage Audit

The test plan covers:

- failing tests before deletion through repo consistency path/token gates
- dashboard file deletion
- dashboard reference deletion
- dashboard-only test deletion
- memory/handoff regression preservation without dashboard projection
- importer file deletion
- importer manifest removal
- runtime skill materialization without importer
- launcher materialization without importer
- browser cockpit retention
- app-server service-mode regression
- final residual scans

The plan does not rely on shallow line-count coverage. Each required behavior maps to either a focused unit/integration test, a repository consistency gate, or a final residual scan.

## Development Plan Audit

The development plan is ordered correctly:

1. Add failing removal gates first.
2. Delete dashboard files and dashboard-only tests.
3. Remove dashboard projection dependency from remaining memory/handoff test.
4. Delete skill-create/importer surface and update manifest/materialization tests.
5. Validate browser cockpit is retained.
6. Run focused and regression verification.

The plan uses direct deletion, not compatibility wrappers or renamed legacy paths.

## Risks

1. `tests/test_repo_consistency.py` scan guards must avoid scanning the new archival spec files, or the spec references will make the guard fail. The plan's scan targets intentionally exclude `docs` for enforced deleted-name gates.
2. `README.md` currently still lists `instance open`; although not part of this deletion task, the development plan includes updating that stale command example while editing the same block.
3. If any hidden script imports `workspace_data` outside the scanned paths, final `rg` and test runs should catch it.

## Review Conclusion

The implementation plan is ready.

Proceed with deletion only when explicitly asked. The next execution should follow the test plan first: add removal gates, confirm they fail, then delete/update code and run focused tests after each block.

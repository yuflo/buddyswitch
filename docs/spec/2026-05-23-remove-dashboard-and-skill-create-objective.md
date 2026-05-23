# Remove Legacy Dashboard And Skill Create Objective

Date: 2026-05-23

## Goal

Remove two stale BuddySwitch surfaces completely:

1. The old visual dashboard surface currently named Context Panel.
2. The old Codex skill-create/import surface currently named `skill-creator-importer`.

This is a forward deletion task. Do not keep compatibility commands, placeholder docs, or orphan tests for these surfaces.

## Current Bottleneck

BuddySwitch has just moved the buddy control plane to Codex app-server service mode. The next cleanup bottleneck is stale product surface area that no longer belongs to the main path.

The Context Panel dashboard is a separate static browser UI and workspace projection path. It is not part of the app-server service control loop.

The skill-create/import flow lets Dev import external Codex-native skills into BuddySwitch source. That is no longer a desired BuddySwitch runtime or product workflow.

Both surfaces increase scan noise, test maintenance, and contributor ambiguity. Removing them makes the remaining runtime boundary clearer.

## Delete Scope

### Legacy Context Panel Dashboard

Delete these primary files:

- `scripts/serve_context_panel.py`
- `framework/console/index.html`
- `framework/console/app.js`
- `framework/console/styles.css`
- `framework/contracts/workspace-projection.json`
- `scripts/workspace_data.py`
- `scripts/runtime_store/projections.py`

Delete or update tests that only exist for the dashboard projection:

- delete `tests/test_console_app_contract.py`
- delete `tests/test_parallel_contracts.py`
- update `tests/test_repo_consistency.py`
- update `tests/test_memory_removal_contract.py`

Remove user-facing references:

- `README.md` Context Panel section
- `README.md` workspace-projection runtime source bullet
- `AGENTS.md` Context panel command bullet

### Skill Create / Importer

Delete these primary files:

- `scripts/skill_creator_importer.py`
- `buddyswitch/skills/dev/skill-creator-importer/SKILL.md`
- `buddyswitch/skills/dev/skill-creator-importer/assets/skill-import-report-template.md`
- `tests/test_skill_creator_importer.py`
- `tests/fixtures/community-skills/dev-summary/SKILL.md`

Update registration and tests:

- remove the `skill-creator-importer` `[[skills]]` entry from `buddyswitch/manifest.toml`
- remove `skill-creator-importer` from the Dev buddy skill list in `buddyswitch/manifest.toml`
- update `tests/test_runtime_skills.py`
- update `tests/test_buddyswitch_launcher.py`

## Explicit Non-goals

Do not remove or weaken any browser runtime capability:

- keep `tools/launcher/browser_cockpit.sh`
- keep `tests/test_browser_cockpit_launcher.py`
- keep `chrome-devtools-cockpit` MCP setup and config
- keep `scripts/env/tools/search/**` browser-native discovery behavior
- keep market and design skill references to `chrome-devtools-cockpit`
- keep app-server lifecycle ownership of browser cockpit start/stop

Do not remove the runtime skill installation system:

- keep `scripts/runtime_skills.py`
- keep normal `buddyswitch/skills/**` packages except `buddyswitch/skills/dev/skill-creator-importer/**`
- keep runtime materialization of registered skills into `.agents/skills`

Do not remove runtime context tooling:

- keep `scripts/env/tools/context/**`
- keep `framework/contracts/prepare-turn-context.json`
- keep `tests/test_context_binding_env_tool.py`
- keep `tests/test_prepare_runtime_context.py`

Do not directly edit runtime durable object state:

- do not edit `buddyswitch/objects/**`
- do not edit `buddyswitch/local/buddybox/**`

## Success Criteria

- No dashboard command, UI, static asset, projection contract, or server script remains.
- No skill-create/importer script, skill package, manifest registration, fixture, or test remains.
- Dev runtime skills still materialize correctly without `skill-creator-importer`.
- Buddy app-server service mode tests still pass.
- Browser cockpit tests still pass unchanged except for unrelated baseline updates.
- Repo consistency tests prove the deleted surfaces do not return.
- Scans for the deleted names return no live-code hits.

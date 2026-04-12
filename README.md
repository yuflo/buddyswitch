# BuddySwitch Workspace (Env-Centric)

BuddySwitch runs as an orchestration layer inside the host Codex CLI session.

## Quick Start

1. Read `AGENTS.md`.
2. Validate parser and router:
   - `python3 scripts/parse_switch.py "switch pm: create track"`
   - `python3 scripts/codex_router.py "switch pm: create track"`
3. Resolve a switch directive:
   - `python3 scripts/switch_runtime.py resolve "switch market: quick market research for AI scheduler landing page"`
4. Inside the current Codex session:
   - choose one `skill_id` from `eligible_skills`
   - read the selected `buddyswitch/skills/.../SKILL.md`
   - run the workflow and produce a structured result matching the reported schema
5. Persist the structured result:
   - `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id implement-task --result result.json`
6. Start Context Panel:
   - `python3 scripts/serve_context_panel.py`
7. Open:
   - `http://127.0.0.1:8765/`

## Canonical UI

```text
switch <buddy>(<task-id>) -> <track-id>: <demand>
```

The supported forms are:

- `switch <buddy>: <demand>`
- `switch <buddy> -> <track-id>: <demand>`
- `switch <buddy>(<task-id>): <demand>`
- `switch <buddy>(<task-id>) -> <track-id>: <demand>`

The text after `:` is a demand, not a task object. If no task id is supplied, `persist` creates a new task for the run. Minor CLI spacing variation around `:` and `->` can be normalized as long as `switch`, `buddy`, optional task id, optional track id, and demand remain clear.

Buddy list, scope, skills, and object authority metadata are loaded from `buddyswitch/manifest.toml`.
`buddy -> skills` is the main runtime routing authority. Buddy `permissions` remain object-authority metadata for manual/debug mutation APIs.
Users are not required to provide output paths in demand text; runtime defaults are applied automatically.

## Core Storage

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Task objects: `buddyswitch/objects/tasks/*.json`
- Artifact objects with canonical structured content: `buddyswitch/objects/artifacts/*.json`
- Run audit content: `buddyswitch/content/runs/*.json`
- Legacy/raw dumps: `runs/raw/`

## Env APIs

- Switch runtime: `scripts/switch_runtime.py` (`resolve|persist`)
- Output schema validator: `scripts/output_schema.py`
- Manifest inspection: `scripts/env_manifest.py`
- Track CRUD/advance (manual/debug): `scripts/env_tracks.py`
- Task read/update/archive (manual/debug): `scripts/env_tasks.py`
- Artifact CRUD/auto-register (manual/debug): `scripts/env_artifacts.py`
- Codex routing: `scripts/codex_router.py`

## Runtime Notes

- BuddySwitch skills are stored under `buddyswitch/skills/**/SKILL.md`.
- BuddySwitch does not use Codex native `.agents/skills` semantics for these skills.
- `required_tools` and `required_env` are advisory skill metadata for the host session. They stay visible in `skill_cards`, but they do not reject resolve candidates.
- `resolve` returns `eligible_skills`, compact `skill_cards`, task context, optional track context, output schema paths, invocation details, and explicit next actions. `resolve` itself does not write BuddySwitch state.
- Single-skill buddies may expose `implicit_skill_id`; multi-skill buddies never auto-select in runtime.
- The host Codex session chooses `skill_id`, executes the selected skill, and emits structured output.
- `persist` is a minimal technical gate: it validates selected-skill identity, schema shape, and safe state references, then writes task objects, artifact objects with canonical content, optional track references through tasks, and run audit JSON under `buddyswitch/content/runs/`.
- Explicit requests to write BuddySwitch outputs into `artifacts/*.md` or `runs/summaries/**` are rejected. Derived markdown outputs are retired.

## Framework Docs

- Switch spec: `framework/docs/switch-spec.md`
- Track registry: `framework/docs/track-registry.md`
- Skill architecture target: `framework/docs/skill-architecture-best-practices.md`

## Example Commands

- `python3 scripts/switch_runtime.py resolve "switch market: quick market research for AI scheduler landing page"`
- `python3 scripts/switch_runtime.py resolve "switch pm: create ai-scheduler-lp track"`
- `python3 scripts/parse_switch.py "switch dev(task-dev-onboarding) -> track-demo: continue the implementation"`
- `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id write-prd --result result.json`
- `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id track-manager --result result.json`

## Context Panel

The panel is read-only and serves live data from `/api/workspace`:

- tracks from `buddyswitch/objects/tracks/*.json`
- tasks from `buddyswitch/objects/tasks/*.json`
- artifacts from `buddyswitch/objects/artifacts/*.json`
- run audits from `buddyswitch/content/runs/*.json`

The panel reads canonical object state only. It does not depend on any derived markdown compatibility layer.

## Cleanup

Manual cleanup script:

- `scripts/cleanup_buddyswitch.sh`

Defaults to dry-run. Add `--execute` to apply deletion.

Cleanup is storage-aware:

- `--agent <buddy>` cleans that buddy's raw logs, task objects, artifact objects, and run content with `switch.buddy == <buddy>`
- `--all-agents` clears BuddySwitch env state for all buddies, including run audit content under `buddyswitch/content/runs/`
- `--project app` only clears `projects/app/.runtime/`
- `--all-storage` clears the full local storage surface, including run audit content under `buddyswitch/content/runs/*.json`

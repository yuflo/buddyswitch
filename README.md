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

`switch <buddy>: <task>`

This is the canonical form, not a brittle exact-match requirement. Minor CLI spacing variation around `:` can be normalized as long as `switch`, `buddy`, and `task` remain clear.

Buddy list, scope, skills, and object authority metadata are loaded from `buddyswitch/manifest.toml`.
`buddy -> skills` is the main runtime routing authority. Buddy `permissions` remain object-authority metadata for manual/debug mutation APIs.
Users are not required to provide output paths in task text; runtime defaults are applied automatically.

## Core Storage

- Env manifest: `buddyswitch/manifest.toml`
- Track objects: `buddyswitch/objects/tracks/*.json`
- Artifact objects: `buddyswitch/objects/artifacts/*.json`
- Canonical structured content: `buddyswitch/content/**`
- Artifact markdown files: `artifacts/*.md` (flat root)
- Run summaries: `runs/summaries/`
- Raw dumps: `runs/raw/`

## Env APIs

- Switch runtime: `scripts/switch_runtime.py` (`resolve|persist`)
- Output schema validator: `scripts/output_schema.py`
- Manifest inspection: `scripts/env_manifest.py`
- Track CRUD/advance (manual/debug): `scripts/env_tracks.py`
- Artifact CRUD/auto-register (manual/debug): `scripts/env_artifacts.py`
- Codex routing: `scripts/codex_router.py`

## Runtime Notes

- BuddySwitch skills are stored under `buddyswitch/skills/**/SKILL.md`.
- BuddySwitch does not use Codex native `.agents/skills` semantics for these skills.
- `required_tools` and `required_env` are advisory skill metadata for the host session. They stay visible in `skill_cards`, but they do not reject resolve candidates.
- `resolve` returns `eligible_skills`, compact `skill_cards`, per-skill track context, artifact defaults, summary defaults, output schema paths, invocation details, and explicit next actions. `resolve` itself does not write BuddySwitch state.
- Single-skill buddies may expose `implicit_skill_id`; multi-skill buddies never auto-select in runtime.
- The host Codex session chooses `skill_id`, executes the selected skill, and emits structured output.
- `persist` is a minimal technical gate: it validates selected-skill identity, schema shape, and safe state references, then writes canonical JSON under `buddyswitch/content/` and renders compatibility markdown to `artifacts/*.md` and `runs/summaries/**`.

## Framework Docs

- Switch spec: `framework/docs/switch-spec.md`
- Track registry: `framework/docs/track-registry.md`
- Skill architecture target: `framework/docs/skill-architecture-best-practices.md`

## Example Commands

- `python3 scripts/switch_runtime.py resolve "switch market: quick market research for AI scheduler landing page"`
- `python3 scripts/switch_runtime.py resolve "switch pm: continue track-demo track and define the MVP scope with acceptance criteria"`
- `python3 scripts/switch_runtime.py resolve "switch pm: create ai-scheduler-lp track"`
- `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id write-prd --result result.json`
- `python3 scripts/switch_runtime.py persist --resolved resolved.json --skill-id track-manager --result result.json`

## Context Panel

The panel is read-only and serves live data from `/api/workspace`:

- tracks from `buddyswitch/objects/tracks/*.json`
- artifacts from `buddyswitch/objects/artifacts/*.json`
- artifact inbox from untracked `artifacts/*.md`
- run summaries from `runs/summaries/`

Current panel behavior stays unchanged in this phase. Markdown artifacts and summaries remain the human-readable compatibility layer even though BuddySwitch now also stores canonical structured payloads under `buddyswitch/content/`.

## Cleanup

Manual cleanup script:

- `scripts/cleanup_buddyswitch.sh`

Defaults to dry-run. Add `--execute` to apply deletion.

Cleanup is storage-aware:

- `--agent <buddy>` cleans that buddy's raw/summaries, artifact objects/files, canonical artifact content, and run content with `switch.buddy == <buddy>`
- `--all-agents` clears BuddySwitch env state for all buddies, including canonical content under `buddyswitch/content/**`
- `--project app` only clears `projects/app/.runtime/`
- `--all-storage` clears the full local storage surface, including `buddyswitch/content/artifacts/*.json` and `buddyswitch/content/runs/*.json`

Orphan canonical artifact content is reported in dry-run output and removed automatically during execute when it falls inside the selected cleanup scope.

# BuddySwitch Artifacts, Runs, and Git Policy

## 1. Scope

This document defines where execution outputs go and what should be committed to Git.

Model constraints:
- one workspace repository
- no extra storage system
- no multi-repo split

## 2. Output Boundary

### `buddyswitch/objects/artifacts/` (canonical artifact outputs)

Artifact objects are the source of truth for reusable buddy outputs:
- research reports
- PRDs
- design specs
- implementation reports
- test reports

Object source of truth:
- tracks: `buddyswitch/objects/tracks/*.json`
- artifacts with structured content: `buddyswitch/objects/artifacts/*.json`
- run audit payloads: `buddyswitch/content/runs/*.json`

### `runs/raw/` (raw execution dumps)

Use `runs/raw/` for noisy intermediate output that helps a run but is not durable:
- scratch notes
- transient logs
- debugging traces
- copied snippets and temporary analysis dumps

### `projects/app/.runtime/` (project runtime-only temporary data)

Use `projects/app/.runtime/` for project-level runtime artifacts that are not durable:
- local run traces
- temporary debug output
- generated runtime logs for manual validation

Do not write these files into `projects/app/` source folders.

## 3. Git Rules

### Commit by default

- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/router.toml`
- `buddyswitch/skills/**/SKILL.md`
- `framework/**`
- `projects/app/**`
- `evals/**`

### Do not commit by default

- generated state under `buddyswitch/objects/**` (except `.gitkeep`)
- generated run audit content under `buddyswitch/content/runs/**` (except `.gitkeep`)
- `runs/raw/**`
- `projects/app/.runtime/**` (except `.gitkeep`)
- temporary logs and traces
- scratch dumps
- machine-local clutter
- secret environment files

## 4. Placement Decision Checklist

Ask this before writing output:
1. Will this be useful in future handoff or review?
2. Is this output final enough to cite later?
3. Is this mainly temporary working noise?

Decision:
- If 1 or 2 is yes, write to an artifact object under `buddyswitch/objects/artifacts/`.
- If 3 is yes, write to `runs/raw/`.
- If the run should become BuddySwitch state, also write a run audit under `buddyswitch/content/runs/`.

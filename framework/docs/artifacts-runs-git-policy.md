# BuddySwitch v1 Artifacts, Runs, and Git Policy

## 1. Scope

This document defines where execution outputs go in BuddySwitch v1 and what should be committed to Git.

Model constraints for v1:
- one workspace repository
- no extra storage system
- no multi-repo split

## 2. Output Boundary

### `artifacts/` (durable outputs)

Use `artifacts/` for outputs that are reusable and worth preserving as project memory:
- research reports
- PRDs
- design specs
- implementation reports
- test reports
- `workspace-registry.json`, the explicit Track Registry

### `runs/raw/` (raw execution dumps)

Use `runs/raw/` for noisy intermediate output that helps a run but is not durable:
- scratch notes
- transient logs
- debugging traces
- copied snippets and temporary analysis dumps

### `runs/summaries/` (compact summaries)

Use `runs/summaries/` for optional compressed run summaries when the run produced meaningful progress.

A summary should be:
- much shorter than raw dumps
- readable in under a minute
- enough to understand what changed, why, and what remains

### `projects/app/.runtime/` (project runtime-only temporary data)

Use `projects/app/.runtime/` for project-level runtime artifacts that are not durable:
- local run traces
- temporary debug snapshots
- generated runtime logs for manual validation

Do not write these files into `projects/app/` source folders.

## 3. Git Rules

### Commit by default

- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `.agents/skills/**/SKILL.md`
- `framework/**`
- `projects/app/**`
- `artifacts/**`
- `runs/summaries/**`
- `evals/**`

### Do not commit by default

- `runs/raw/**`
- `projects/app/.runtime/**` (except `.gitkeep`)
- temporary logs and traces
- scratch dumps
- machine-local clutter
- secret environment files

## 4. Summary Compression Rule

Create or update `runs/summaries/<slug>.md` when a run includes one of:
- a durable artifact creation or major update
- code changes with verification results
- resolved blockers or risk decisions

Keep summary content focused:
1. what was done
2. key decisions and risks
3. changed files or artifact paths
4. suggested next switch (optional)

## 5. Placement Decision Checklist

Ask this before writing output:
1. Will this be useful in future handoff or review?
2. Is this output final enough to cite later?
3. Is this mainly temporary working noise?

Decision:
- If 1 or 2 is yes, write to `artifacts/`.
- If 3 is yes, write to `runs/raw/`.
- If the run has meaningful progress, optionally add a compact entry in `runs/summaries/`.

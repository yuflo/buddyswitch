# BuddySwitch v1 — File and Git Conventions

## 1. Git boundary

For the MVP, use **one Git repository** at the workspace root.

Do not create a separate inner Git repo for `projects/app/`.

## 2. Why

A single repo keeps the following aligned:

- framework instructions
- code changes
- durable artifacts
- evaluation cases
- summary history

It also keeps the BuddySwitch framework visible from wherever the user launches Codex within the workspace.

## 3. Which files should be committed

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

### Ignore by default
- `runs/raw/**`
- heavy traces
- temporary logs
- copied scratch text
- temporary experiments
- secrets and environment files

## 4. `.gitignore` principle

Git should preserve:
- durable project memory
- framework rules
- implementation state

Git should avoid preserving:
- noisy execution exhaust
- high-volume temporary debugging residue
- machine-local clutter

## 5. Artifact writing rule

If an output would be useful later as:

- a handoff
- a product memory
- a reviewable milestone
- an input to another agent

it belongs in `artifacts/`.

If it only helped complete the current run and is unlikely to matter later,
it belongs in `runs/raw/`.

## 6. Summary writing rule

Whenever a run produces meaningful progress, write a compact summary to:

- `runs/summaries/`

This should be far shorter than the raw dump and easier for humans to inspect.

## 7. Naming conventions

Use short kebab-case file names.

Examples:
- `companion-demand.md`
- `live-space-mvp.md`
- `onboarding-smoke.md`

Avoid:
- timestamps in every file name unless necessary
- overly nested directories
- vague names like `notes-final-v2-last.md`

## 8. Commit style recommendation

For BuddySwitch MVP testing, keep commits small and readable.

Suggested commit categories:

- `framework: ...`
- `pm: ...`
- `design: ...`
- `dev: ...`
- `test: ...`
- `eval: ...`

Examples:
- `framework: add initial switch protocol and agent contracts`
- `pm: draft buddyswitch v1 mvp prd`
- `dev: scaffold workspace config and custom agents`

## 9. Branching recommendation

For the first local MVP, simple branching is enough:

- `main` for the latest working framework state
- short-lived branches for larger experiments if needed

Do not over-design branch strategy for v1.

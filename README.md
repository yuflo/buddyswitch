# BuddySwitch v1 Workspace

This repository is the BuddySwitch v1 reference workspace.

## Quick Start

1. Read `AGENTS.md` first.
2. Ask Codex: `Read AGENTS.md and explain how this repository's BuddySwitch framework works.`
3. Run one switch command, for example:
   - `switch design: Produce IA and core flows from artifacts/prd/onboarding-minimal.md and write to artifacts/design/onboarding-minimal-v2.md`
4. Inspect outputs:
   - Durable artifacts in `artifacts/`
   - Optional summaries in `runs/summaries/`
   - Raw dumps in `runs/raw/`
5. Run minimal evals from `evals/cases/` when framework instructions change.

## Core Idea

- One workspace repository
- One explicit switch protocol: `switch <agent>: <task>`
- Five specialist agents: `market`, `pm`, `design`, `dev`, `test`
- Durable artifacts in `artifacts/`
- Raw dumps in `runs/raw/`
- Compact run summaries in `runs/summaries/`

## Key Locations

- `AGENTS.md`: root usage contract
- `.codex/config.toml`: Codex project configuration
- `.codex/agents/`: BuddySwitch custom agent definitions
- `.agents/skills/`: repo-local skills
- `framework/agent-registry.md`: canonical v1 agent roster and boundaries
- `framework/contracts/`: role output contracts
- `framework/templates/`: reusable templates
- `framework/docs/switch-spec.md`: switch syntax and error handling rules
- `framework/docs/artifacts-runs-git-policy.md`: durable output and Git rules
- `framework/console/`: read-only context panel for tracks, research inbox items, artifacts, and copyable commands
- `projects/app/`: application code area
- `projects/app/.runtime/`: project runtime-only data (temporary, cleanup-safe)
- `evals/`: lightweight evaluation cases and rubrics

## Git Boundary (Single Repo)

- Keep one workspace repository for framework, app code, artifacts, and evals.
- Commit durable outputs in `artifacts/` and compact summaries in `runs/summaries/`.
- Do not commit raw dumps or scratch output in `runs/raw/`.

## Context Panel

BuddySwitch includes a local read-only context panel for browsing tracks, market-only research inbox items, artifacts, summaries, suggested switch commands, and cleanup commands.

- `Tracks` are cross-agent workstreams inferred from PRD, design, build, or test artifacts.
- `Research Inbox` items are market-only research artifacts that have not become product tracks yet.
- Both are filename-inferred hints, not an explicit topic registry or hidden agent state.

Refresh the snapshot:

- `python3 scripts/build_console_snapshot.py`

Open:

- `framework/console/index.html`

Interface boundary:

- It does not call agents.
- It does not call Codex, Claude Code, or Gemini CLI.
- It does not execute cleanup commands.
- It generates copyable commands for the user to run manually in the CLI.
- It reads generated static data from `framework/console/workspace-data.js`.

## Manual Cleanup

BuddySwitch provides a manual cleanup script for storage data outside the framework logic.
Use it to reset experiments or clean state before regression runs.

Script:

- `scripts/cleanup_buddyswitch.sh`

Safety model:

- default is dry-run (preview only)
- add `--execute` to actually delete
- interactive confirmation is required for execute mode
- use `--force` with `--execute` only when you intentionally want non-interactive execution

Examples:

- Clean one agent data (artifacts + runs):
  - `scripts/cleanup_buddyswitch.sh --agent market`
- Clean all agent data:
  - `scripts/cleanup_buddyswitch.sh --all-agents`
- Clean project runtime data:
  - `scripts/cleanup_buddyswitch.sh --project app`
- Clean all storage data (`artifacts`, `runs`, `projects/app/.runtime`):
  - `scripts/cleanup_buddyswitch.sh --all-storage`
- Execute mode:
  - `scripts/cleanup_buddyswitch.sh --all-agents --execute`
  - `scripts/cleanup_buddyswitch.sh --all-storage --execute --force`

Important notes:

- Run `git status` before cleanup if you may want to keep generated files.
- Agent-target cleanup relies on path conventions (`runs/raw/<agent>`, `runs/summaries/<agent>`), not regex guessing.
- Legacy files placed directly under `runs/summaries/` root are not covered by agent-target cleanup and are only removed by `--all-storage`.

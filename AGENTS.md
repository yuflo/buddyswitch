# BuddySwitch Framework

This repository uses BuddySwitch, a project-level specialist-agent framework for collaborative software and product development.

## How To Use

Use the switch directive:

switch <agent>: <task>

Examples:
- switch market: Research demand for AI companion live spaces and write the result to artifacts/research/live-space.md
- switch pm: Draft an MVP PRD from artifacts/research/live-space.md
- switch design: Produce IA and core flows from artifacts/prd/live-space-mvp.md
- switch dev: Implement the onboarding flow in projects/app based on artifacts/prd/live-space-mvp.md
- switch test: Run smoke tests for the latest onboarding changes and write a report to artifacts/test/

## Available Agents

- market
- pm
- design
- dev
- test

## Required Behavior

When the user writes `switch <agent>: <task>`, you must:

1. Route the task to that agent only.
2. Obey that agent's role boundary.
3. Read:
   - `framework/contracts/<agent>.md`
   - `framework/agent-registry.md`
   - `framework/docs/track-registry.md` when the task references Tracks or artifact registration
   - `scripts/registry.py` when the task needs to create or update Track Registry state
   - relevant files in `framework/templates/`
   - relevant referenced artifacts
   - `artifacts/workspace-registry.json` when the task references Tracks or artifact registration
   - relevant repo-local skills in `.agents/skills/`
4. Return:
   - execution summary
   - working notes
   - deliverables or changed files
   - suggested next switch (optional)

## Switch Rules

- Treat `switch <agent>:` as a framework directive.
- Do not silently guess unknown agent names.
- Do not silently reroute to a different agent.
- Do not use multiple agents unless the user explicitly asks.

## Context Panel Rules

- `framework/console/` is a read-only context panel for registry tracks, untracked artifacts, summaries, and copyable commands.
- The interface must not invoke agents, call an LLM, execute cleanup, or hold hidden agent state.
- Tracks are explicit product iteration records in `artifacts/workspace-registry.json`.
- Untracked artifacts are diagnostics only, not a product queue.
- Agents must follow `framework/docs/track-registry.md` when a task references Tracks or artifact registration.
- Agents must use `scripts/registry.py` for Track Registry changes rather than editing JSON directly.
- Agents may suggest registry metadata, but must not create or associate Tracks without explicit user intent.
- The interface may generate suggested `switch ...` and cleanup commands for the user to run manually in CLI.
- Refresh interface data by running `python3 scripts/serve_context_panel.py` and using the page's `Refresh workspace` button.

## File Placement

- Durable outputs go to `artifacts/`.
- The explicit Track Registry lives at `artifacts/workspace-registry.json`.
- The registry file is the v1 local dump backend; `scripts/registry.py` is the temporary operation adapter for registry writes.
- Noisy raw dumps go to `runs/raw/`.
- Compact useful summaries go to `runs/summaries/`.
- Project runtime-only temporary data goes to `projects/app/.runtime/`.
- Durable outputs and summaries are expected to be commit-friendly.
- Raw dumps, scratch traces, and temporary logs should stay out of Git.
- Agent-target cleanup depends on path conventions (`runs/raw/<agent>`, `runs/summaries/<agent>`), not heuristic guessing.
- Cleanup keeps registry state aligned by calling the registry adapter when agent data is removed, and `--all-storage` removes the local registry dump.

## Project Code Location

The main product code lives in `projects/app/`.

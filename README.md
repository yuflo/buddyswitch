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
- `projects/app/`: application code area
- `evals/`: lightweight evaluation cases and rubrics

## Git Boundary (Single Repo)

- Keep one workspace repository for framework, app code, artifacts, and evals.
- Commit durable outputs in `artifacts/` and compact summaries in `runs/summaries/`.
- Do not commit raw dumps or scratch output in `runs/raw/`.

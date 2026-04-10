# BuddySwitch Legacy v1 Docs Pack

This folder contains historical v1 planning docs.

Current source of truth is env-centric and lives in:

- `AGENTS.md`
- `README.md`
- `buddyswitch/manifest.toml`
- `framework/docs/`

BuddySwitch is a **project-level agent framework** designed primarily for **Codex CLI MVP validation**.
It lets a user enter a workspace, ask Codex to read the framework, and then use a simple switch directive
to route work to a specific specialist agent.

Core idea:

- one workspace repo
- one shared framework
- one explicit switch directive
- five specialist agents
- structured process output
- durable artifacts separated from noisy dumps

Recommended reading order:

1. `01-product-overview.md`
2. `02-mvp-prd.md`
3. `04-switch-protocol.md`
4. `05-agent-specs.md`
5. `08-evaluation-plan.md`
6. `09-open-questions-and-notes.md`
7. `12-track-registry-and-context-panel-plan.md`

Removed from the active legacy pack:

- exploratory `.agents/skills` architecture notes
- early Codex-first implementation notes
- obsolete starter `AGENTS.md` draft

## Intended use with local Codex CLI

At the repo root, ask Codex to:

1. read `AGENTS.md`
2. explain the framework briefly
3. follow `switch <agent>: <task>` exactly as defined by the framework

## Scope of this docs pack

This docs pack is intentionally biased toward:

- getting the first MVP running in Codex CLI fast
- keeping the framework simple enough to iterate
- avoiding extra orchestration roles or workflow engines
- using explicit user-directed agent switching

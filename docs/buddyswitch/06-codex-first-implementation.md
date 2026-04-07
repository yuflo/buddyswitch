# BuddySwitch v1 — Codex-First Implementation Notes

## 1. Goal of this document

This document translates the BuddySwitch product spec into a practical first implementation shape for **Codex CLI**.

## 2. Codex-specific design assumptions for MVP

BuddySwitch v1 assumes the following Codex capabilities are available and should be used:

- root-level `AGENTS.md` for repo instructions
- project-level `.codex/config.toml`
- project-scoped custom agents under `.codex/agents/`
- repo-local skills under `.agents/skills/`
- project root discovery based on the repository root
- optional future hooks, but not required for v1

These assumptions should be rechecked when upgrading Codex versions.

## 3. Recommended `.codex/config.toml`

```toml
model = "gpt-5.4"
model_provider = "openai"

approval_policy = "on-request"
sandbox_mode = "workspace-write"
project_root_markers = [".git"]

[agents]
max_depth = 1
max_threads = 4

[features]
multi_agent = true
codex_hooks = false
```

## 4. Recommended `AGENTS.md` responsibilities

The root `AGENTS.md` should do four things well:

1. explain what BuddySwitch is
2. teach the switch syntax
3. define the available agent names
4. define the required response shape and file conventions

It should stay concise.

## 5. Recommended custom agent setup

Create one TOML file per custom agent:

- `.codex/agents/market.toml`
- `.codex/agents/pm.toml`
- `.codex/agents/design.toml`
- `.codex/agents/dev.toml`
- `.codex/agents/test.toml`

Each should define at least:
- `name`
- `description`
- `developer_instructions`

## 6. Recommended skill layout

Use one starter skill per agent first.

Suggested starter skills:

- market / `research-scan`
- pm / `write-prd`
- design / `ia-spec`
- dev / `implement-task`
- test / `smoke-test`

## 7. How BuddySwitch should be introduced to Codex

Suggested first prompt in a new workspace session:

```text
Read AGENTS.md and explain how this repository's BuddySwitch framework works.
```

Suggested second prompt:

```text
switch pm: Draft an MVP PRD from artifacts/research/live-space.md
```

## 8. Why hooks are excluded from v1

Hooks can be powerful for deterministic validation, but they add another layer of complexity.
For the first BuddySwitch MVP, the framework should rely on:

- clear instructions
- contracts
- skills
- small evaluation cases

Hooks can be added after the basic switching behavior is validated.

## 9. Minimal implementation backlog

### Phase 1
- create workspace skeleton
- write `AGENTS.md`
- create `.codex/config.toml`
- create five custom agents
- create five contracts
- create five skill folders

### Phase 2
- run first switch prompts manually
- inspect outputs
- fix weak instructions
- adjust file paths and conventions

### Phase 3
- add eval cases
- add artifact templates
- improve wording and boundaries

## 10. Delivery philosophy

BuddySwitch should be developed by using BuddySwitch itself as early as possible.

That means once the framework skeleton exists, the user should immediately begin using:
- `switch pm`
- `switch design`
- `switch dev`
- `switch test`

to refine the framework through real tasks.

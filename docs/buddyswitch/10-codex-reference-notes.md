# BuddySwitch v1 — Codex Reference Notes

This document captures the current Codex assumptions that informed the BuddySwitch v1 design.
Re-check these notes when updating Codex or broadening BuddySwitch beyond the first MVP.

## Notes

1. `AGENTS.md`
- Codex reads `AGENTS.md` files before doing any work.
- It supports layered instructions from global scope and project scope.

2. Project root discovery
- Codex walks up from the working directory until it reaches a project root.
- By default, a directory containing `.git` is treated as the project root.

3. Project-level config
- Codex supports project-scoped `.codex/config.toml`.

4. Custom agents
- Project-scoped custom agents live under `.codex/agents/`.
- Each standalone custom agent file must define:
  - `name`
  - `description`
  - `developer_instructions`

5. Skills
- Repo-local skills can live under `.agents/skills/`.
- A skill is a directory with a `SKILL.md` file.
- `SKILL.md` must include `name` and `description`.

6. Subagents
- Codex supports subagent workflows.
- For BuddySwitch v1, the user should explicitly switch agents rather than rely on hidden parallel orchestration.

7. Hooks
- Codex hooks are available as an extensibility framework.
- Hooks are still experimental, so BuddySwitch v1 does not depend on them.

8. Evals
- Lightweight evals are strongly recommended for checking whether skills and framework behaviors remain correct over time.

## Practical BuddySwitch takeaway

BuddySwitch v1 should center on:
- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/*.toml`
- `.agents/skills/**/SKILL.md`
- small eval cases

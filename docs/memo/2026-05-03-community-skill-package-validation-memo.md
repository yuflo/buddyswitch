# Community Skill Package Validation Memo

Date: 2026-05-03
Worktree: `dev0210`

## Purpose

Record the compatibility boundary for importing community Codex-native skills into BuddySwitch.

This memo focuses only on whether a community `SKILL.md` package must be rewritten or shaped differently to work in BuddySwitch. It does not treat manifest registration, buddy membership, or launcher selection as community-skill compatibility problems.

## Confirmed Current Behavior

BuddySwitch currently materializes skills through this path:

1. The launcher reads the skill path from `buddyswitch/manifest.toml`.
2. BuddySwitch validates the skill package.
3. BuddySwitch copies the package into the runtime instance at `.agents/skills/<skill-id>`.
4. Codex CLI discovers and executes the skill from `.agents/skills`.

This means Codex CLI is responsible for native skill execution, but BuddySwitch still performs an admission check before Codex CLI can see the skill.

## Current Compatibility Risk

The current admission check mixes two different responsibilities:

- Safe materialization: BuddySwitch must ensure source and target paths do not escape the intended workspace boundaries.
- Skill semantic validation: BuddySwitch currently inspects `SKILL.md` content and metadata before handing it to Codex CLI.

Only the first responsibility belongs in BuddySwitch.

The second responsibility should belong to Codex CLI because the target state is native Codex skill execution. If BuddySwitch rejects a package because of its own simplified interpretation of `SKILL.md`, then community skill compatibility is constrained by BuddySwitch instead of Codex CLI.

Current BuddySwitch-specific checks that can become compatibility blockers:

- `SKILL.md` frontmatter is parsed by BuddySwitch's simplified parser.
- `name` must exactly match the manifest skill id.
- `description` must be present and non-empty.
- `skill.toml` is rejected.
- Symlink package contents are rejected.
- Skill paths must be repo-relative and stay under the repo root.

The path and workspace-boundary checks are materialization safety checks. The `SKILL.md` semantic checks are the part that should be removed or delegated to Codex CLI.

## Target Boundary

BuddySwitch should treat a community skill package as an opaque directory for execution purposes.

BuddySwitch should validate only:

- the configured source path is allowed;
- the source path can be copied safely;
- the runtime target is exactly the intended `.agents/skills` directory;
- materialization cannot read from or write to unexpected filesystem locations.

BuddySwitch should not validate:

- whether `SKILL.md` frontmatter is valid;
- which frontmatter fields are allowed;
- whether `name` matches the manifest id;
- whether a legacy or extra metadata file exists, unless copying it creates a concrete security or isolation risk.

Those checks should be left to Codex CLI's native skill loader.

## Separate Persist Compatibility Issue

The larger product compatibility issue is still persist output, not package format.

A community skill can be natively executed by Codex CLI but still fail to become a valid BuddySwitch product result if it does not produce the JSON result expected by BuddySwitch persistence.

That issue is separate from package materialization. It should be solved by making BuddySwitch persistence accept or wrap native skill output, not by requiring every community skill to be rewritten around BuddySwitch-specific schemas.

## Working Conclusion

`dev0210` has moved execution to Codex-native skills, but BuddySwitch still has unnecessary package-format gatekeeping before execution.

For the target community-skill experience, BuddySwitch should keep only filesystem safety checks during materialization and should stop applying its own `SKILL.md` compatibility rules.

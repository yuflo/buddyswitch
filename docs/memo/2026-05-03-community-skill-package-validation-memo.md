# Community Skill Runtime Validation Memo

Date: 2026-05-03
Worktree: `dev0210`

## Purpose

This memo records the runtime validation boundary for community Codex-native skills across three BuddySwitch points:

1. instance startup skill materialization;
2. product request `prepare`;
3. result `persist`.

The rule is direct: keep only checks that prevent the current chain from running wrong or writing bad state. Remove checks that only prove package style, readiness, or content quality.

## Runtime Gates

### Gate 1: Materialization (instance startup)

BuddySwitch validates only copy boundaries:

- active buddy and skill ids are declared in manifest;
- skill id/path/source/workspace/target boundaries are safe;
- runtime target is `workspace/.agents/skills` and not a symlink write target;
- package copy preserves opaque content for Codex to evaluate.

BuddySwitch does not validate package file format at this gate.

### Gate 2: Prepare

`prepare` validates only turn-context and reservation safety:

- product session identity is complete and consistent;
- active buddy exists;
- explicit task/track bindings do not conflict;
- run reservation is created safely.

`prepare` does not validate package/source readiness, `SKILL.md`, or output schema file readiness.

### Gate 3: Persist

`persist` validates only write safety:

- context and reservation identity are current;
- selected `skill_id` belongs to the active buddy;
- selected skill has required runtime persistence fields (notably non-empty `output_slot`);
- result payload has minimum writable shape;
- PM-only `state_effects.track_operation` safety checks pass.

`persist` does not treat full schema completeness as a runtime write gate.

## Boundary Summary

BuddySwitch should not validate community skill package contents. Codex CLI owns package acceptance after packages are materialized into `.agents/skills`.

BuddySwitch validates:

- materialization path and target boundaries during instance startup;
- turn context and reservation safety during `prepare`;
- write safety during `persist`.

BuddySwitch does not validate:

- `SKILL.md` frontmatter;
- `name` / `description` metadata;
- `skill.toml` presence;
- package file layout;
- package content symlinks;
- full artifact content quality during runtime persistence.

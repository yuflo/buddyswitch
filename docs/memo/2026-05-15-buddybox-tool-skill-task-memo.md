# Buddybox Tool Skill Task Memo

Date: 2026-05-15

Status: task memo only. Do not treat this document as implementation.

## User Goal

Add a dedicated `buddybox-tool` shared skill so Codex CLI hosts can understand and operate BuddySwitch buddybox through the native Codex skill layer, without hardcoded trigger rules and without replacing the existing BuddySwitch env tool execution path.

The goal is not "when user says prototype, always write HTML to buddybox." The goal is semantic affordance: the host should be able to infer when buddybox is the right private local file workspace, when artifact is required for product-readable content, and how to call the existing env tool correctly.

## Current Consensus

BuddySwitch skills are still Codex-native:

- Runtime skills are materialized into `.agents/skills/<skill-id>`.
- Codex CLI remains the native skill reader/executor.
- BuddySwitch does not implement a separate "read SKILL.md and execute it" engine.
- BuddySwitch only prepares a buddy-specific runtime environment and calls `codex`.

Buddybox is currently not covered by an equivalent shared skill:

- `task-tool`, `track-tool`, `artifact-tool`, and `handoff-tool` exist as shared skills.
- `buddybox-tool` does not exist in `buddyswitch/manifest.toml`.
- Buddybox is exposed directly as a BuddySwitch env tool through `python3 scripts/env/client.py buddybox <operation>`.
- The real execution path is `env.client -> runtime broker -> env.tool -> buddybox service`.

This is acceptable as an execution architecture, but incomplete as host-facing operational guidance.

## Why This Task Exists

The lower layers already know what buddybox is:

- `scripts/env/tools/contracts.py` exposes buddybox actions and command surface.
- `scripts/env/tools/semantics.py` contains capability and action semantics.
- `scripts/env/services/context.py` exposes `buddybox_desc`, `tool_catalog`, and `operation_semantics`.
- `scripts/env/services/buddybox.py` enforces active-buddy private local boundaries and returns structured feedback.

The missing layer is the Codex-native skill guidance that teaches repeated operational behavior:

- how to choose buddybox versus artifact,
- how to form valid paths,
- how to write text versus binary payloads,
- how to inspect or verify a write,
- how to recover from scope/payload rejections,
- how to promote content to artifact only when product-readable content is needed.

This belongs in a skill because it is repeated task knowledge. It should not be expanded into AGENTS.md.

## Design Principle

`buddybox-tool` must be a skill, not an executor.

It should teach the host to call the existing env tool:

```bash
python3 scripts/env/client.py buddybox <operation>
```

It must not introduce:

- a second buddybox write path,
- direct filesystem writes into `buddyswitch/local/buddybox/**`,
- a rule engine,
- phrase triggers such as "prototype means HTML",
- mandatory artifact promotion after every buddybox write,
- long-form duplicated schemas that belong in `context.get` or `turn_runtime.py status`.

The correct layering is:

1. AGENTS.md gives a short route marker.
2. Codex native skill gives repeated operational guidance.
3. `context.get` / `turn_runtime.py status` provide full tool catalog and semantics.
4. `scripts/env/client.py buddybox ...` performs the broker-routed operation.
5. Tool response feedback tells the host what changed and what can happen next.

## Task Scope

Implement a new shared skill package:

```text
buddyswitch/skills/shared/buddybox-tool/SKILL.md
```

Register it in:

```text
buddyswitch/manifest.toml
```

Add `buddybox-tool` to every buddy that has buddybox permissions:

- market
- pm
- design
- dev
- test

Update tests so runtime materialization expects the skill and old direct/retired patterns stay blocked.

## Skill Content Requirements

The skill should stay concise and operational.

Required frontmatter:

```yaml
---
name: buddybox-tool
description: Use when the active buddy needs private local workspace files such as drafts, prototypes, exports, logs, reports, or binary outputs, and needs to operate buddybox through BuddySwitch env tools.
---
```

Required sections:

- What buddybox is.
- When to use it.
- When not to use it.
- Command forms for `desc`, `list`, `read`, `write`, and `delete`.
- Path rules.
- Text versus base64 payload guidance.
- Response fields to inspect.
- Promotion rule from buddybox to artifact.
- Runtime closing rules.

The skill should explicitly state:

- Buddybox is active-buddy private local workspace.
- Other buddies cannot read these files.
- Buddybox paths are not cross-buddy payload authority.
- Product-readable or cross-buddy readable content must be carried by artifact or another explicit readable object.
- Do not edit `buddyswitch/local/buddybox/**` directly.
- Do not edit `buddyswitch/objects/**` directly.
- Follow structured tool feedback on rejection.

## Suggested Skill Shape

Keep examples short and generic.

Good examples:

```bash
python3 scripts/env/client.py buddybox desc
python3 scripts/env/client.py buddybox list --path pm/prototypes --recursive
python3 scripts/env/client.py buddybox read --path pm/prototypes/landing.html
python3 scripts/env/client.py buddybox write --payload /tmp/buddybox-write.json
python3 scripts/env/client.py buddybox delete --path pm/tmp/obsolete.txt
```

Good write payload example:

```json
{
  "path": "pm/prototypes/landing.html",
  "content": "<!doctype html>...",
  "content_type": "text/html"
}
```

Good binary payload example:

```json
{
  "path": "pm/assets/snapshot.png",
  "content_base64": "<base64>",
  "content_type": "image/png"
}
```

Do not include large templates, full HTML samples, or complete tool schemas in the skill.

## Non-Goals

Do not change buddybox storage semantics in this task.

Do not add a Codex-native function/tool named buddybox.

Do not bypass the runtime broker.

Do not change `scripts/env/services/buddybox.py` unless a test exposes a real feedback gap that is inseparable from making the skill usable.

Do not bloat runtime AGENTS.md.

Do not make PM-specific prototype behavior a global trigger rule.

## Acceptance Criteria

The task is done when:

- `buddyswitch/skills/shared/buddybox-tool/SKILL.md` exists with concise operational guidance.
- `buddyswitch/manifest.toml` registers `buddybox-tool`.
- All buddies with `buddybox.read/write/delete` permissions include `buddybox-tool` in their skills.
- Runtime skill materialization installs `.agents/skills/buddybox-tool`.
- Existing Codex-native skill behavior remains intact.
- AGENTS.md remains short and does not embed buddybox tool documentation.
- Tests verify the skill teaches env tool usage, not direct filesystem mutation.
- Tests verify the skill does not reintroduce prepare/persist/run-tool wording.
- Tests verify shared runtime tool skill expectations include `buddybox-tool`.

## Test Plan

Add or update focused tests first.

Likely files:

```text
tests/test_runtime_skills.py
tests/test_buddyswitch_launcher.py
tests/test_repo_consistency.py
tests/test_env_manifest_v2.py
tests/test_runless_runtime_contract.py
```

Focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_repo_consistency.py \
  tests/test_env_manifest_v2.py \
  tests/test_runless_runtime_contract.py -q
```

If the implementation touches semantic surfaces or buddybox responses, also run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddybox_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py -q
```

## Implementation Order

1. Add a failing test that every buddy with buddybox permissions includes `buddybox-tool`.
2. Add a failing test that runtime materialization installs `.agents/skills/buddybox-tool`.
3. Add a failing test that `buddybox-tool/SKILL.md` mentions `env.tool` / `scripts/env/client.py buddybox` and does not mention retired prepare/persist/run flows.
4. Add the skill package.
5. Register the skill in `buddyswitch/manifest.toml`.
6. Add the skill id to all relevant buddies.
7. Run focused verification.

## Risk Notes

Main risk is overfitting the skill into a decision tree. Avoid that.

The skill should create better host judgment, not remove judgment. It should describe durable boundaries and command mechanics, while leaving product intent decisions to the host.

The second risk is duplicating the full semantic catalog. Avoid that too.

The skill should point to:

- `context get` for full catalog,
- `turn_runtime.py status` for runtime tool inventory,
- tool response feedback for next actions.

## Final Decision

`buddybox-tool` is required as a shared Codex-native skill because buddybox is a repeated operational capability and should have the same top-layer guidance quality as `task-tool`, `track-tool`, `artifact-tool`, and `handoff-tool`.

The skill must remain a guide over the existing BuddySwitch env tool path. The runtime execution path should stay unchanged.

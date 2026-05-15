# Buddybox Tool Skill Task Memo

Date: 2026-05-15

Status: task memo only. Do not treat this document as implementation.

## User Goal

Add a dedicated `buddybox-tool` shared skill so Codex CLI hosts can understand and operate BuddySwitch buddybox through the native Codex skill layer, without hardcoded trigger rules and without replacing the existing BuddySwitch env tool execution path.

The goal is not "when user says prototype, always write HTML to buddybox." The goal is semantic affordance: the host should be able to infer when buddybox is the right private local file workspace, when artifact is required for product-readable content, and how to call the existing env tool correctly.

After follow-up discussion, sharpen this goal from the buddy's point of view:

- `buddybox-tool` should be the buddy-facing operating playbook for common buddybox work.
- The env tool layer should remain the capability layer that exposes concrete actions, payloads, return semantics, and long-tail operations to Codex CLI.
- The skill should teach judgment and workflow sequencing, not duplicate the full tool schema.
- When a repeated operation requires deterministic boundary enforcement, add or extend an env tool action instead of telling the buddy to bypass BuddySwitch with raw filesystem commands.

## Current Consensus

BuddySwitch skills are still Codex-native:

- Runtime skills are materialized into `.agents/skills/<skill-id>`.
- Codex CLI remains the native skill reader/executor.
- BuddySwitch does not implement a separate "read SKILL.md and execute it" engine.
- BuddySwitch only prepares a buddy-specific runtime environment and calls `codex`.

At task start, buddybox was not covered by an equivalent shared skill:

- `task-tool`, `track-tool`, `artifact-tool`, and `handoff-tool` exist as shared skills.
- `buddybox-tool` does not exist in `buddyswitch/manifest.toml`.
- Buddybox is exposed directly as a BuddySwitch env tool through `python3 scripts/env/client.py buddybox <operation>`.
- The real execution path is `env.client -> runtime broker -> env.tool -> buddybox service`.

This is acceptable as an execution architecture, but incomplete as host-facing operational guidance.

The implemented direction keeps that execution architecture and adds the missing guidance layer. `buddybox-tool` is now best understood as an operating workflow skill over the existing `buddybox` env tool, not as another execution engine.

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

The skill/tool split is:

- **Skill layer**: repeated buddy workflows, decision cues, recovery habits, verification loops, and when to promote private content to artifact.
- **Tool catalog / semantics layer**: action names, payload fields, return fields, side effects, permissions, error meanings, and long-tail capability discovery.
- **Service implementation layer**: path normalization, active-buddy privacy enforcement, read/write/search behavior, response construction, and tests.

This means `buddybox-tool` may carry multiple common workflows as long as they remain short and operational. It should not become a full buddybox manual.

Good `buddybox-tool` workflow topics:

- create or update a private draft/prototype/export/log/report;
- list or search private local files, then read exact files;
- clean up obsolete private local files;
- recover from rejected paths or payloads;
- promote readable content to `artifact.create_revision` when another buddy or product flow must read it.

Do not split into sub-skills merely because there are several workflows. Split only when a workflow becomes independently triggerable, has its own inputs/outputs and verification pattern, or makes the main `SKILL.md` too large. Until then, keep a concise `Common Flows` section in `buddybox-tool`; if details grow, move variant-specific material into one-hop `references/*.md` files.

## Search Capability Decision

`buddybox.read` is an exact-file read. It is not a search operation and should not be described as one.

Current roles should stay distinct:

- `buddybox.list`: enumerate active-buddy private file summaries only; no content bodies.
- `buddybox.search`: find candidate text matches across active-buddy private local files. This is the right future operation for keyword or regex search.
- `buddybox.read`: read one exact path returned by `list` or `search`.

The clean design is to add `buddybox.search` as a broker-routed env tool action, not to instruct the buddy to use shell search over `buddyswitch/local/buddybox/**`.

Why env tool search is cleaner:

- keeps active-buddy privacy, path normalization, and symlink safety in the service layer;
- returns stable structured JSON with `ok`, `state_changed=false`, `read_scope`, matches, skipped files, and `allowed_next_action_options`;
- preserves the "do not directly touch `buddyswitch/local/buddybox/**`" rule for normal buddy operation;
- lets tests cover cross-buddy rejection, binary skipping, regex errors, and result truncation;
- keeps shell commands as developer/debug fallback only, not buddy-facing workflow.

Recommended minimal `buddybox.search` semantics:

```json
{
  "query": "pricing",
  "path": "pm/prototypes",
  "mode": "literal",
  "case_sensitive": false,
  "limit": 50
}
```

Optional regex mode:

```json
{
  "query": "price\\w+",
  "path": "pm",
  "mode": "regex",
  "case_sensitive": false,
  "limit": 50
}
```

Expected result shape:

```json
{
  "matches": [
    {
      "path": "pm/prototypes/landing.html",
      "line": 12,
      "column": 8,
      "snippet": "pricing table...",
      "content_type": "text/html",
      "private_to_buddy": "pm"
    }
  ],
  "skipped_files": [
    {
      "path": "pm/assets/snapshot.png",
      "reason": "binary_or_non_utf8"
    }
  ]
}
```

Search should be read-only, active-buddy-private, bounded by `limit`, and should return snippets rather than full file bodies. If the buddy needs full content, it should call `buddybox.read` on the returned path.

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
- Common flows for write/read/list/search/delete/promotion/rejection recovery.

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

Suggested common-flow wording:

```text
To find information in buddybox:
1. Use buddybox.search for keyword or regex snippets when available.
2. Use buddybox.list when only filenames, timestamps, sizes, or content types are needed.
3. Use buddybox.read only after choosing an exact active-buddy path.
4. Do not shell-search buddybox roots as the normal buddy workflow.
5. Promote readable content through artifact when another buddy or product flow must read it.
```

## Non-Goals

Do not change buddybox storage semantics in this task.

Do not add a Codex-native function/tool named buddybox.

Do not bypass the runtime broker.

Do not make shell search the normal buddy-facing search path for buddybox content.

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
- If `buddybox.search` is added, tests verify it is active-buddy-private, read-only, bounded, text/snippet-oriented, and clearly separate from exact-file `buddybox.read`.

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

If the implementation adds `buddybox.search`, also cover:

- literal keyword search over UTF-8 text files;
- explicit regex mode and invalid-regex rejection;
- active-buddy path scope rejection for foreign prefixes;
- binary or non-UTF-8 files skipped with structured reasons;
- no full file body in search results;
- next action options pointing to `buddybox.read`, `buddybox.list`, and optional artifact promotion when content must become product-readable.

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

Additional risk from the search discussion: using shell search as the buddy-facing answer would be short-term convenient but would leak boundary responsibility back to the host. The clean product path is a narrow env tool action with structured output. Shell remains acceptable for developer diagnostics, not for normal buddybox operation.

## Final Decision

`buddybox-tool` is required as a shared Codex-native skill because buddybox is a repeated operational capability and should have the same top-layer guidance quality as `task-tool`, `track-tool`, `artifact-tool`, and `handoff-tool`.

The skill must remain a guide over the existing BuddySwitch env tool path. The runtime execution path should stay unchanged.

## Implementation Review Addendum

Reviewed against the current implementation on 2026-05-15.

The implementation follows the intended layering:

- `buddyswitch/skills/shared/buddybox-tool/SKILL.md` exists and stays short.
- `buddyswitch/manifest.toml` registers `buddybox-tool`.
- Every buddy with `buddybox.read`, `buddybox.write`, and `buddybox.delete` permissions includes `buddybox-tool`.
- `scripts/env/tools/semantics.py` carries the full buddybox action semantics, including when to use buddybox, when not to use it, payload meaning, side effects, success meaning, and common failures.
- `scripts/env/services/context.py` exposes compact `tool_affordances` through `context.summarize` and full `tool_catalog` / `operation_semantics` through `context.get`.
- `scripts/env/services/buddybox.py` enforces active-buddy private local paths and returns structured `allowed_next_action_options`.
- `tests/test_runtime_skills.py`, `tests/test_buddybox_env_tool.py`, and `tests/test_host_decision_surface_product_mode.py` verify the key host-facing behavior.

The important correction is that the skill should not be treated as the only place that must contain every detail listed above. The current code uses a better split:

1. `AGENTS.md` gives route markers only.
2. `buddybox-tool` gives concise operational memory.
3. `context.summarize.tool_affordances` gives compact tool-choice guidance.
4. `context.get.tool_catalog`, `context.get.operation_semantics`, and `turn_runtime.py status` give full payload and action semantics.
5. Tool responses give the concrete result, state impact, and safe next actions.

So the original "Skill Content Requirements" should be read as a coverage requirement across the host-facing surfaces, not as a demand to duplicate the full semantic catalog inside `SKILL.md`. If future work makes the skill stricter, keep additions small and limited to missing operational guardrails, such as:

- state that other buddies cannot read active buddy private local files;
- state that buddybox paths are not cross-buddy payload authority;
- state that `buddyswitch/objects/**` must not be edited directly;
- include one short `write --payload` example only if real host behavior shows payload-shape confusion.

Do not add large schemas, long examples, PM-specific trigger rules, or copied action semantics to the skill.

## Practice Check

The implementation direction matches current agent/tool guidance:

- OpenAI skills guidance defines skills as reusable workflows/playbooks for recurring tasks. This supports putting several short buddybox operating workflows inside one `buddybox-tool` skill.
- OpenAI skills guidance also says skills are useful for reusable processes, tool-based workflows, and conventions. This matches `buddybox-tool`: it teaches how to combine `desc/list/search/read/write/delete` and artifact promotion.
- OpenAI Codex harness guidance says to give Codex a map, not a giant manual. This supports short AGENTS files and concise skills pointing to deeper tool semantics.
- OpenAI function-calling guidance says tool definitions should describe purpose, parameter formats, output meaning, and should pass the "intern test". This belongs in `tool_catalog` / `operation_semantics`, not as copied schema in the skill.
- Anthropic tool-use guidance similarly emphasizes detailed tool descriptions, parameter meaning, limitations, and behavior. This supports keeping action-level details in the tool layer.
- MCP tool specs describe `description`, `inputSchema`, optional `outputSchema`, and behavior annotations as client guidance. This reinforces that concrete long-tail operations such as `buddybox.search` belong in the tool surface.

Relevant references:

- OpenAI, "Using skills": https://openai.com/academy/skills/
- OpenAI, "Function calling": https://developers.openai.com/api/docs/guides/function-calling
- OpenAI, "Harness engineering: leveraging Codex in an agent-first world": https://openai.com/index/harness-engineering/
- Anthropic, "Define tools": https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
- Model Context Protocol, "Tools": https://modelcontextprotocol.io/specification/2025-06-18/server/tools

Conclusion: the converged design is to keep `buddybox-tool` as a compact multi-flow operating playbook, keep env tools as the capability and schema layer, and add deterministic buddybox capabilities such as search to the env tool layer when repeated buddy workflows need them. Search again only if a concrete host failure appears, such as repeated wrong tool choice, malformed `buddybox.write` payloads, confusion between private buddybox files and artifact-readable deliverables, or search results that cause the buddy to read too much irrelevant content.

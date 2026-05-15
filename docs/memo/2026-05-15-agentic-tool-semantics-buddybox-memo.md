# Agentic Tool Semantics And Buddybox Memo

Date: 2026-05-15
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

## Target

Strengthen BuddySwitch's host-facing tool semantics so Codex can choose the right runtime capability from meaning, not from hardcoded trigger rules.

The immediate question came from this scenario:

> In a PM buddy session, if the user says "for this product, quickly build a simple page prototype first", should the buddy naturally use buddybox to create a local HTML prototype?

The product goal is not to encode a rule such as "prototype means write HTML to buddybox". The product goal is to expose enough semantic information that the host can infer:

- PM cannot mutate shared product source when `projects/app` is read-only.
- Buddybox is the active buddy's private local file workspace.
- Private drafts, lightweight prototypes, exports, reports, logs, and binary/generated files fit buddybox.
- Cross-buddy-readable deliverables must be promoted into artifact content.
- Handoffs should carry explicit readable product object references, not private buddybox path assumptions.

## Principle

Do not hardcode intent-to-tool routing when the decision can be made from tool semantics.

The host should see clear affordances:

- what the capability is
- when to use it
- when not to use it
- what inputs it accepts
- what each input means
- what it reads
- what it mutates
- what success means
- what output fields represent
- what rejection means
- what safe next actions are available

This keeps BuddySwitch agentic instead of turning it into a brittle phrase matcher.

## AGENTS.md Position

AGENTS.md should not become a tool encyclopedia.

The investigation found a consistent community and official direction:

- OpenAI Codex loads AGENTS.md as durable project instructions, so every extra line consumes default context.
- AgentPatterns frames AGENTS.md as project orientation and a table of contents, not full documentation.
- Community Codex guidance favors short, explicit, positive action statements.
- An arXiv evaluation found repository context files can increase inference cost and reduce task success when they carry unnecessary requirements.

Therefore, AGENTS.md should stay short and operational. It should point the host to the correct discovery surface rather than embedding the discovery surface.

Good AGENTS.md shape for this issue:

```md
- Start with `python3 scripts/env/client.py context summarize`.
- Use `context get` or `python3 scripts/turn_runtime.py status` when selecting env tools or checking payload semantics.
```

Bad AGENTS.md shape:

- listing every buddybox action
- embedding full payload schemas
- adding many example-specific trigger phrases
- turning PM/design/dev behavior into a long decision tree
- duplicating the canonical tool catalog

## Current Implementation State

### Strong Parts

The core runtime already has a real semantic registry.

Important files:

- `scripts/env/tools/semantics.py`
  - capability-level semantics
  - action-level semantics
  - `use_when`
  - `do_not_use_when`
  - input explanations
  - side effects
  - risk hints
  - success meaning
  - common failures
- `scripts/env/tools/contracts.py`
  - turns the registry into `env_tools_description()`
  - exposes command, operations, payload fields, and action semantics
- `scripts/turn_runtime.py`
  - `status` exposes the full env tool catalog
- `scripts/env/services/context.py`
  - `context.get` exposes `tool_catalog` and `operation_semantics`
  - `context.summarize` exposes compact orientation and `buddybox_desc`
- `scripts/env/services/buddybox.py`
  - enforces active-buddy-private local root
  - returns state impact and next-action text
- `scripts/env/tools/responses.py`
  - defines canonical response fields such as `effect_summary`, `state_changed`, `durability`, `allowed_next_actions`, and `allowed_next_action_options`

Existing tests already verify much of this:

- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_runtime_agents.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddybox_env_tool.py`

The latest focused check from this discussion passed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_agents.py \
  tests/test_repo_consistency.py -q
```

Observed result:

```text
37 passed, 191 subtests passed
```

### Weak Parts

The full semantics exist, but the default discovery path is not strong enough.

Current weak spots:

- Runtime AGENTS files tell the buddy to start with `context summarize`, but `context.summarize` does not include a compact tool-affordance summary.
- `context.get` has the complete `tool_catalog`, but AGENTS does not clearly say to use it when selecting tools.
- `turn_runtime.py status` has the full catalog, but it is not the obvious next stop for tool selection.
- There is no shared `buddybox-tool` skill, while task/track/artifact/handoff each have shared tool skills.
- PM contract says "supporting scratch files in buddybox when needed", but that phrase is weaker than the intended file-output affordance.
- Some router rejection guidance still points to retired `prepare.runtime_context.env_tools` wording.
- Buddybox responses mostly expose next actions as strings; structured `allowed_next_action_options` are available but underused.

## Additional Best-Practice Review For Buddybox

The follow-up review adds several buddybox-specific requirements without expanding this into a generic tool-platform redesign.

Relevant best-practice signals:

- OpenAI function-calling guidance says tool definitions should describe purpose, each parameter and format, and what the output represents. It also recommends the "intern test": a human should be able to use the function correctly from only what the model sees.
- Anthropic tool guidance says detailed tool descriptions are the strongest factor in tool performance: describe what the tool does, when to use it and not use it, each parameter, caveats, limitations, and returned data. It also recommends high-signal responses with stable semantic identifiers.
- Anthropic's tool-engineering guidance emphasizes testing tools with realistic tasks, reading transcripts where agents get confused, returning only high-signal context, avoiding bloated outputs, and improving descriptions based on observed failures.
- MCP client practice recommends layered discovery: catalog first, inspect details only when needed, then execute. This avoids loading huge schemas by default.
- MCP tools expose `description`, `inputSchema`, optional `outputSchema`, and annotations such as read-only, destructive, idempotent, and open-world hints. Those annotations are guidance, not authorization.

Implications for buddybox:

- The default summary must tell the host enough to know buddybox is a candidate for private local file outputs.
- Full buddybox semantics must explain input formats and output meanings, not just action names.
- Buddybox responses must be compact and high-signal: file summaries for list, full content only for read, state impact for write/delete.
- Rejections must steer the host back to active-buddy private-local paths instead of encouraging direct filesystem bypass.
- Tests should include realistic host decision scenarios, not only field-presence checks.

## Buddybox Decision Contract

The buddybox decision contract should let the host answer these questions without reading service code:

1. Is the requested result a private active-buddy local file or a product-readable deliverable?
2. Is the active buddy allowed to write the shared project source, or should file output stay in buddybox?
3. Does another buddy need to read this content now?
4. Is the content text, binary/base64, or only a file summary?
5. Did the operation create, overwrite, read, list, delete, or merely describe state?
6. If blocked, did any state change, and what safe retry path exists?

For the PM page prototype case, the intended reasoning is:

- PM cannot mutate `projects/app` when project access is read-only.
- A quick single-file page prototype is a private local generated file unless the user asks for a product-source implementation or cross-buddy readable deliverable.
- `buddybox.write` is the right private file-output affordance.
- If the prototype must be handed to Design or Dev as readable collaboration state, create an artifact whose content carries the readable prototype or enough product-readable detail. A private buddybox path alone is not cross-buddy read authority.

This reasoning must come from semantic surfaces, not a hardcoded phrase rule.

## Design Direction

Use layered progressive disclosure.

For buddybox, the intended discovery layers are:

1. **Route map:** runtime AGENTS points to context discovery and full tool catalog commands.
2. **Catalog:** `context.summarize.tool_affordances` gives one compact row per relevant capability.
3. **Inspect:** `context.get.tool_catalog` or `turn_runtime.py status.env_tools` exposes full action semantics, payload fields, side effects, and response meaning.
4. **Execute:** `buddybox.*` responses return compact state impact and structured next actions.

### 1. AGENTS.md: short route map only

Keep runtime AGENTS minimal.

It should include:

- active buddy identity
- first command for compact context
- command to inspect full tool catalog when selecting tools
- direct runtime boundaries
- safety constraints
- final output expectations

It should not include detailed tool semantics.

### 2. `context.summarize`: compact affordances

Add a small `tool_affordances` block to `context.summarize`.

This is the default orientation surface, so it should tell the host enough to choose whether deeper discovery is needed.

Example shape:

```json
{
  "tool_affordances": {
    "buddybox": {
      "use_for": "active buddy private local files: drafts, prototypes, exports, logs, reports, binary outputs",
      "not_for": "cross-buddy readable deliverables or product objects",
      "promote_with": "artifact.create_revision when content must become product-readable"
    },
    "artifact": {
      "use_for": "task-scoped product-readable deliverables and revisions",
      "not_for": "private local files or generated binary outputs"
    }
  }
}
```

This must stay compact. The full catalog remains in `context.get` and `turn_runtime.py status`.

### 3. `semantics.py`: canonical full meaning

Strengthen buddybox semantics in `scripts/env/tools/semantics.py`.

Desired language should cover:

- active buddy private local workspace
- private drafts
- lightweight prototypes
- exports
- reports
- logs
- generated files
- binary outputs
- not collaborative
- not product object
- not visible to other buddies
- artifact promotion when content must become product-readable

This is not a trigger rule. It is a generalized capability description.

Buddybox action semantics should also explain output meanings:

- `buddybox.desc`
  - returns semantic description and compact state summary only
  - does not return file content or full file list
- `buddybox.list`
  - returns file summary rows only
  - each row should make `path`, `size_bytes`, `updated_at`, `content_type`, and `private_to_buddy` meaningful to the host
  - does not return `content` or `content_base64`
- `buddybox.read`
  - returns exactly one active-buddy private local file
  - returns UTF-8 `content` when possible, otherwise `content_base64`
  - `encoding` explains how the host should interpret the returned body
- `buddybox.write`
  - creates or overwrites exactly one active-buddy private local file
  - explains whether it created or overwrote
  - explains that no artifact, handoff, task, track, context, or evidence object was created
- `buddybox.delete`
  - deletes one active-buddy private local file if present
  - reports repeat delete as already absent without implying product-state change

Buddybox input semantics should be explicit enough for the host to avoid invalid calls:

- `path` must be under the active buddy prefix, such as `pm/prototypes/landing.html`.
- `content` and `content_base64` are mutually exclusive.
- `content` is UTF-8 text.
- `content_base64` is for binary or non-UTF-8 payloads.
- `content_type` is a MIME hint, not a product contract.
- `encoding` on read is output preference: `auto`, `utf-8`, or `base64`.

### 4. `buddybox-tool` skill: task knowledge, not project orientation

Add `buddyswitch/skills/shared/buddybox-tool/SKILL.md`.

Purpose:

- teach how to call `python3 scripts/env/client.py buddybox <operation>`
- explain path convention under `<active_buddy>/...`
- explain text vs base64 payloads
- explain list/read/write/delete behavior
- explain when to promote to artifact
- explain verification through response fields

This mirrors the existing shared tool skills:

- `task-tool`
- `track-tool`
- `artifact-tool`
- `handoff-tool`

The manifest should include `buddybox-tool` for buddies that have buddybox permissions.

### 5. Runtime responses: structured next actions

Keep natural-language `allowed_next_actions`, but also use `allowed_next_action_options` for machine-readable choices.

Buddybox examples:

- after `buddybox.write`
  - `buddybox.read` to confirm the private local file
  - `buddybox.list` to inspect local file summaries
  - `artifact.create_revision` when the host decides the content must become product-readable
- after `buddybox.read`
  - `buddybox.write` to replace the file
  - `artifact.create_revision` for promotion
- after rejection
  - `buddybox.desc` to review the private-local boundary
  - retry with a path under the active buddy root

These options should include tool, action, mutability, reason, and source refs through the existing response helper pattern.

Responses should stay high-signal:

- Do not include file content in `desc` or `list`.
- Do not include full tool documentation in each response.
- Do include state impact, durability, created/updated path ids, and privacy boundary.
- Do include artifact promotion as an option only when host decides product-readable content is needed.
- Do not phrase artifact creation as mandatory after every buddybox write.

Structured next-action options should distinguish private iteration from promotion:

```json
[
  {
    "tool": "buddybox",
    "action": "read",
    "reason": "Confirm the private local file just written."
  },
  {
    "tool": "artifact",
    "action": "create_revision",
    "reason": "Promote readable content when another buddy or product workflow must consume it."
  }
]
```

### 6. Role contracts: short boundary sentence

Role contracts should not duplicate tool docs.

For PM, a useful line is:

```md
- Use buddybox for PM-owned private local drafts, lightweight prototypes, exports, or supporting files; use artifact when the content must become product-readable.
```

For Design, Dev, Test, and Market, wording should stay role-specific and short.

### 7. Router feedback: remove retired references

Replace `prepare.runtime_context.env_tools` wording in runtime feedback with current surfaces:

- `context.get.tool_catalog`
- `python3 scripts/turn_runtime.py status`
- `context.summarize.tool_affordances` if added

This keeps rejection guidance aligned with the runless runtime model.

## Proposed Implementation Order

Shortest validated loop:

1. Add failing tests for compact `tool_affordances` in `context.summarize`.
2. Add failing tests that buddybox semantics mention generalized file-output affordances without hardcoded trigger rules.
3. Add failing tests that AGENTS remains short and points to full discovery instead of embedding tool schemas.
4. Add failing tests for structured buddybox `allowed_next_action_options`.
5. Implement `context.summarize.tool_affordances`.
6. Strengthen `scripts/env/tools/semantics.py`.
7. Add `buddyswitch/skills/shared/buddybox-tool/SKILL.md` and manifest registrations.
8. Add structured response options in `scripts/env/services/buddybox.py`.
9. Update PM/design/dev/test/market contracts only with short role-level boundary wording where useful.
10. Replace stale router guidance that references retired prepare runtime context.
11. Add a small host-decision scenario test for the PM prototype case. The assertion should check semantic surfaces and expected reasoning signals, not hardcode a phrase-trigger rule.
12. Run focused tests first, then broader runtime contract tests.

## Verification Targets

Focused:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py -q
```

Broader relevant:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_memory_removal_contract.py \
  tests/test_env_tool_router.py \
  tests/test_runless_runtime_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_agents.py \
  tests/test_runtime_skills.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_buddybox_env_tool.py \
  tests/test_repo_consistency.py -q
```

Buddybox-specific verification should prove:

- `context.summarize` exposes a compact buddybox affordance without dumping the full catalog.
- `context.get` and `turn_runtime.py status` expose full buddybox action semantics.
- Buddybox action semantics explain input formats and output meanings.
- `buddybox.desc/list/read/write/delete` responses state actual effect, state change, durability, privacy boundary, and next actions.
- `buddybox.list` and `buddybox.desc` never return file bodies.
- Foreign buddy paths, traversal, bad encoding, and bad base64 remain rejected with no state change.
- PM prototype scenario surfaces enough signals to choose buddybox for private local file output while preserving artifact promotion for cross-buddy readability.

## Decision Summary

Do:

- keep AGENTS.md short
- make `context.summarize` a better compact affordance surface
- keep full semantics in `context.get` and `turn_runtime.py status`
- add a buddybox shared skill for task-specific operation knowledge
- make responses guide the host with structured next actions
- explain buddybox input formats and output field meanings
- evaluate a realistic PM prototype decision path without adding phrase triggers
- test the semantic surfaces directly

Do not:

- hardcode phrase-to-tool routing
- stuff full tool docs into AGENTS.md
- make buddybox a cross-buddy transport
- rely on private buddybox paths as readable handoff content
- replace semantic discovery with examples-only prompting
- make artifact promotion mandatory after every buddybox write
- build a generic tool-search or MCP subsystem for this narrow buddybox pass

## Source Notes

External references used during investigation:

- OpenAI Codex AGENTS.md guide: `https://developers.openai.com/codex/guides/agents-md`
- OpenAI function calling guide: `https://developers.openai.com/api/docs/guides/function-calling`
- AgentPatterns AGENTS.md standard: `https://agentpatterns.ai/standards/agents-md/`
- Anthropic tool definition docs: `https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools`
- Anthropic tool engineering notes: `https://www.anthropic.com/engineering/writing-tools-for-agents`
- MCP client best practices: `https://modelcontextprotocol.io/docs/develop/clients/client-best-practices`
- MCP tools specification: `https://modelcontextprotocol.io/specification/2025-06-18/server/tools`
- MCP tool annotations schema: `https://modelcontextprotocol.io/specification/2025-06-18/schema`
- AGENTS.md evaluation paper: `https://arxiv.org/abs/2602.11988`

Internal reference points:

- `tools/launcher/assets/buddies/*/AGENTS.md`
- `framework/contracts/*.md`
- `scripts/env/tools/semantics.py`
- `scripts/env/tools/contracts.py`
- `scripts/env/tools/responses.py`
- `scripts/env/services/context.py`
- `scripts/env/services/buddybox.py`
- `scripts/turn_runtime.py`
- `buddyswitch/skills/shared/*-tool/SKILL.md`

# Env Tool Semantic Clarity Boundary Memo

Date: 2026-05-16
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: task memo only. Do not treat this document as implementation or a new schema spec.

Execution summary:

- Target: make runtime-visible env tool semantics and responses clear enough for a normal host to
  choose, call, and recover from atomic tools without reading service code.
- Boundary: tool catalog explains capability meaning; tool response explains actual effect and
  recovery; skills explain repeated workflows; AGENTS only points to the route map.
- Non-goal: no new schema, workflow engine, phrase router, tool-search subsystem, or business
  process encoding in tools.

## Background

This memo records the current convergence after reviewing BuddySwitch env tools, related skills,
and the recent buddybox discussion.

The problem is not that BuddySwitch lacks tools. The runtime already exposes env tools, operation
semantics, context discovery, shared skills, and structured responses. The problem is that a normal
host can still struggle to understand a capability from the exposed surfaces alone.

The target is not a case-by-case workflow cookbook. The target is clearer capability semantics and
clearer feedback, so Codex CLI can decide and act inside the environment.

KEY POINT: BuddySwitch should make the host capable of judgment, not hide judgment inside phrase
rules, workflow routers, or prompt-heavy instructions.

KEY POINT: Tool semantics must describe atomic capabilities. Business workflows belong in skills.

## Current Surfaces

The current method already has the right broad shape:

- `tools/launcher/assets/buddies/*/AGENTS.md` gives the short runtime route map.
- `context.summarize` gives compact orientation and `tool_affordances`.
- `context.get` gives full `tool_catalog` and `operation_semantics`.
- `scripts/turn_runtime.py status` exposes the same full env tool catalog outside a broker call.
- `scripts/env/tools/contracts.py` owns registered tools, actions, payload fields, permissions,
  mutability, authority, and returns.
- `scripts/env/tools/semantics.py` owns capability and action descriptions.
- `scripts/env/tools/responses.py` owns success/rejection feedback fields.
- `buddyswitch/skills/shared/*-tool/SKILL.md` gives repeated operational guidance.

The improvement should strengthen these existing surfaces. Do not add a new discovery subsystem,
semantic version layer, workflow engine, rule engine, or MCP server for this task.

## Task Goal

Make env tool capability descriptions and feedback clear enough that a normal host can answer:

- What capability does this tool provide?
- What does this action read, validate, create, update, delete, issue, or open?
- What input ids or payloads does it need, and what kind of runtime surface usually provides them?
- What does the response return: summary, full body, private file content, metadata, token,
  browser intent, or durable object?
- What state changed, if any?
- How durable is the result?
- Why was a rejected call blocked?
- Did the rejection change state?
- What can be corrected, or what alternative atomic capability might be relevant?

The host should not need to read `scripts/env/services/*.py` to answer these questions.

## Core Boundary

### Tool Layer

Tool layer describes atomic capability semantics.

It should explain:

- capability purpose;
- input meaning;
- return meaning;
- permission and ownership boundary;
- visibility boundary;
- side effects;
- durability;
- success meaning;
- failure meaning;
- safe correction or alternative capability signals.

It should not explain business process.

Examples of tool-layer content that is acceptable:

- `artifact.get` reads one readable artifact record with body content by explicit artifact id.
- `artifact.list` returns artifact summaries, not full bodies.
- `buddybox.write` writes one active-buddy private file and does not mutate product objects.
- `search.open_browser` opens a browser session target and does not issue evidence.
- A rejection did not mutate state and the payload field `task_id` can be corrected.

Examples of tool-layer content to avoid:

- After writing a PRD, hand off to Design.
- Market research should search, then issue evidence, then create artifact.
- Dev should read source artifacts, implement, then hand off to Test.
- If the user says a phrase, call a specific tool.

### Skill Layer

Skills own repeated business workflows.

Skills can describe how to combine atomic capabilities for a recurring task, such as source intake,
artifact production, market evidence, design handoff, implementation, or testing.

Skills must still defer to runtime feedback. A skill may describe the normal workflow, but it should
not override `permission_boundary`, `why_blocked`, `state_changed`, `durability`, or structured
tool feedback.

### AGENTS Layer

AGENTS stays short.

It should say where to begin, where the full catalog is, and which runtime boundaries must not be
bypassed. It should not become the full tool manual.

## Key Findings

Current strengths:

- The tool registry and broker-routed env tool model are already in place.
- `context.get.tool_catalog` and `operation_semantics` are runtime-visible.
- `responses.py` already has useful canonical fields such as `effect_summary`, `state_changed`,
  `durability`, `read_scope`, `correctable_fields`, `alternative_capabilities`, and
  `allowed_next_action_options`.
- `buddybox` and `search` are the clearest current examples of capability boundary thinking.
- Existing tests already prevent some regressions, including old run/binding surfaces, phrase
  routing, and missing semantic fields.

Current gaps:

- Some action descriptions remain template-like, such as "You need tool.action behavior" or
  "returned structured state".
- Compact affordances are uneven; some capabilities are clearer at `context.summarize` time than
  others.
- Service responses do not use feedback fields consistently across tools.
- Rejections often say why a call failed, but do not always explain correction or alternative
  capability in host-readable terms.
- Tests mostly prove field presence and a few scenarios, not whether the exposed descriptions are
  understandable.

## Non-Goals

Do not do these as part of this task:

- Do not add many new structured fields.
- Do not create semantic v2.
- Do not build a workflow engine, phrase router, rule engine, or generic tool-search subsystem.
- Do not encode business process into tool descriptions.
- Do not turn shared skills into long catalogs that mirror runtime behavior.
- Do not make `allowed_next_action_options` a mandatory step list.
- Do not optimize individual scenarios one by one as the primary strategy.

## Recommended Work Shape

Use the current fields and make them clearer.

Recommended implementation order:

1. `semantics.py`: clarify the source descriptions for each tool and action.
2. `responses.py`: clarify actual success and rejection feedback from runtime calls.
3. `context.summarize`: tighten compact first-pass tool affordances after the full semantics are
   clearer.
4. Shared skills: remove or shorten guidance that only exists to compensate for unclear tool
   semantics.

This order keeps runtime-visible tool meaning as the source of truth, then updates feedback,
compact discovery, and workflow guidance around it.

For `semantics.py`:

- Replace template descriptions with plain capability/action meaning.
- Keep `plain_description`, `use_when`, `do_not_use_when`, `inputs_explained`,
  `side_effects`, `success_means`, and `common_failures`.
- Use these fields to clarify atomic capability boundaries, not workflows.
- Pay special attention to content level: summary vs body vs file vs token vs browser intent.
- Pay special attention to state effect: read-only vs validation-only vs durable object mutation
  vs private file mutation vs transient browser/token effect.

For service responses:

- Use existing success fields to state actual effect, durability, read/write scope, and changed ids.
- Use existing rejection fields to state why blocked, impact, retryability, correctable fields, and
  alternative atomic capabilities.
- Add `allowed_next_action_options` only when there is a genuinely useful conditional affordance.
- Keep affordance wording conditional. It should not say "must", "always", or "only" unless the
  runtime boundary truly requires it.

For compact discovery:

- Keep `context.summarize.tool_affordances` compact.
- Add only the missing high-value capability distinctions needed for first-pass tool choice.
- Do not copy the full action catalog into summarize.

For shared skills:

- Keep them short.
- Let them describe repeated business workflows.
- Point back to `context.get.tool_catalog` and runtime response feedback for action details.
- Remove or avoid text that tries to patch unclear tool behavior with memorized rules.

## Review Checklist

Before implementing changes, review each tool/action with these questions:

- Can a normal host tell what this action does without reading service code?
- Can it tell what the response returns at the content level?
- Can it tell whether state changes?
- Can it tell the durability of the result?
- Can it tell the authority boundary in normal language?
- Can it tell what a common rejection means?
- Is the text describing an atomic capability rather than a business workflow?
- Is any guidance better placed in a skill?
- Is any new structure actually necessary, or can the existing field carry the meaning?

## Verification Direction

Verification should prove clarity without creating a giant schema.

Useful checks:

- Reject obvious template phrases in runtime-visible semantics.
- Ensure read actions clearly distinguish summary, body, file content, metadata, token, and browser
  intent where relevant.
- Ensure mutating actions clearly state what they mutate and what they do not mutate.
- Ensure representative rejections expose `why_blocked`, `impact`, `state_changed`,
  `retry_guidance`, and either correctable fields or alternative capability signals.
- Ensure `allowed_next_action_options` remains conditional affordance language, not workflow
  prescription.
- Keep a small number of realistic host scenarios as smoke tests for clarity, but do not make
  scenarios the design center.

## Final Task Definition

The task is to improve the current env tool semantic surface so the host can understand and use
atomic capabilities from runtime-visible descriptions and feedback.

The task is not to design a new schema or encode business workflows in tools.

The correct layering is:

```text
tool catalog: atomic capability meaning
tool response: actual effect and recovery feedback
skill: repeated business workflow
AGENTS: short runtime route map
host: final decision based on user goal, skill, tool semantics, and runtime feedback
```

This is the core reminder for the next implementation pass.

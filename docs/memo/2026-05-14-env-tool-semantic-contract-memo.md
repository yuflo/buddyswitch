# Env Tool Semantic Contract Memo

Date: 2026-05-14
Worktree: `dev2258`
Status: consensus memo and implementation handoff only. No source implementation in this phase.

## Consensus

BuddySwitch needs a first-class semantic contract for env tools.

The problem is not that the current env tool layer lacks registered operations. It already has a registry, CLI commands, operation names, payload fields, permissions, and structured feedback fields. The problem is that the host (`codex-cli`) often still needs to infer product meaning from implementation code.

The agreed target is direct:

```text
Systematically add information, explanations, and descriptions so the host can:

1. decide which capability to use in a given situation;
2. understand what result that capability produced;
3. analyze feedback to determine the actual impact of the attempted call.

The host must be able to do this without reading scripts/env/services/*.py.
```

This memo records the agreed direction: add enough semantic description and feedback meaning to satisfy that target, while keeping the implementation as simple as possible. This is not a "lite because easy" plan. It is the smallest sufficient plan that closes the host decision loop.

KEY POINT: The target is host judgment, not tool visibility. A tool being listed, callable, and routed through `env.tool` is not enough.

KEY POINT: The semantic layer must answer "which capability, what result, what impact" directly. Any design that still expects `codex-cli` to infer those answers from code or scattered docs has missed the consensus.

## Core Principles

These principles are the guardrails for implementation. They should keep the work aimed at the consensus target without turning it into a larger protocol project.

1. Optimize for host judgment quality, not schema elegance.
2. Put decision-critical semantics in runtime-visible env tool contracts, not only in docs, skills, or service code.
3. For each capability, explain when to use it, when not to use it, and what authority boundary it operates under.
4. For each action, explain inputs, side effects, success meaning, common failures, and risk hints.
5. For each response, explain actual impact: what changed, whether state changed, durability, and the next meaningful actions.
6. Treat permission and risk metadata as host guidance only; runtime enforcement remains in broker and service code.
7. Add the smallest complete registry-backed semantic layer first; defer full MCP exposure, generic schema frameworks, or tool-search subsystems until they become measured bottlenecks.
8. Verify semantic quality with tests and realistic host scenarios, not just field presence.

## Current State

Current authoritative surfaces in `dev2258`:

- Tool/action registry: `scripts/env/tools/contracts.py`
- Runtime projection: `prepare.runtime_context.env_tools` built from `scripts/turn_runtime.py`
- Runtime semantics map: `prepare.runtime_context.operation_semantics`
- Feedback helpers: `scripts/env/tools/responses.py`
- Router validation feedback: `scripts/env/tools/router.py`
- Service-level feedback: `scripts/env/services/*.py`
- Buddy visible guidance: `tools/launcher/assets/buddies/*/AGENTS.md`
- Shared skill guidance: `buddyswitch/skills/shared/*/SKILL.md`
- Runtime spec: `framework/docs/turn-runtime-spec.md`

The current tool registry exposes useful machine contract fields:

- `tool`
- `command`
- `scope`
- `operations`
- `payload_fields`
- `kind`
- `mutates`
- `required_permission`
- `authority`
- `requires`
- `returns`

The current feedback contract exposes useful machine/action fields:

- `ok`
- `tool`
- `action`
- `active_buddy`
- `error.code`
- `error.message`
- `permission_boundary`
- `allowed_next_actions`
- `allowed_next_action_options`
- `command_hint`
- optional service-specific fields such as `next_actions`, `missing_preconditions`, `relation`, and `why`

These are necessary, but not sufficient.

## Gap

The missing layer is semantic meaning.

Today, a host can often tell:

- what action name exists;
- which fields the action accepts;
- whether a rejection happened;
- which boundary rejected it;
- one or more next commands.

But the host cannot reliably tell, without reading implementation:

- when two actions look similar, which one is appropriate;
- whether an action only reads, validates, binds instance state, writes runtime objects, commits a run, opens a browser page, or issues a broker token;
- what a successful result means in product terms;
- whether a successful result produced durable state, transient browser state, or no state change;
- whether retrying with the same arguments is safe or meaningful;
- what practical impact a rejection has;
- whether a rejection changed any state before failing;
- how to rank multiple recovery options;
- what "permission_boundary=track.lifecycle_authority" or similar internal boundary names mean in normal language.

KEY POINT: The current system is structured, but not semantically self-explanatory.

KEY POINT: If `codex-cli` must read `scripts/env/services/*.py` to decide what a tool does or what feedback means, the env tool contract is incomplete.

## Recent Commit Read

Recent work moved in the right general direction, but did not make the host judgment goal explicit enough.

Relevant commits inspected:

- `cc2394c Remove env tool manager residue`
- `74874e0 feat: implement tool-visible search env layer`
- `f937d2d feat: upgrade track task artifact tooling`

### `cc2394c`: remove manager residue

This commit improved the visible surface by removing internal `*_manager` naming from active env tool descriptions and shared skill names. It made the exposed names closer to the actual capabilities: `task`, `track`, `artifact`, `run`, and so on.

What it solved:

- reduced internal implementation naming leakage;
- made `runtime_context.env_tools` keys look like normal tool ids;
- added consistency tests so old manager names do not come back.

What it did not solve:

- it did not explain when to choose one capability over another;
- it did not explain what success means for each action;
- it did not standardize feedback impact, retryability, or state-change meaning.

### `74874e0`: tool-visible search

This commit made search visible as an env tool with explicit backend boundaries and browser-native recovery commands.

What it solved:

- made native Codex web search unavailability explicit in product sessions;
- exposed `search.status`, `search.request`, and `search.open_browser`;
- returned useful boundaries such as browser availability, search API availability, and command hints.

What it did not solve:

- it still largely describes capability availability, not result impact;
- it does not fully explain the trust/risk implications of open-world browser/search output in the same semantic language as other tools;
- it does not give a uniform host-readable success/feedback contract shared with task, track, artifact, run, handoff, evidence, context, and binding.

### `f937d2d`: track/task/artifact tooling upgrade

This commit materially improved the normal path for product work:

- direct `track.get`;
- direct `artifact.get`;
- `track.join`;
- better artifact no-leak recovery fields;
- handoff list/validate/create;
- tests that next actions reference registered tools and command hints use env client commands.

What it solved:

- corrected the earlier drift toward context-driven artifact reads;
- made direct ids more usable;
- made blocked artifact reads explain safe recovery paths;
- improved machine-readable response structure.

What it did not solve:

- tests still mostly prove structural fields exist, not that a normal host can understand semantic meaning;
- registry fields still expose operation mechanics rather than decision-quality descriptions;
- success responses still do not consistently say what actually changed;
- rejection responses still rely on internal boundary names unless individual services added custom prose;
- the work improved tool visibility, but did not define "host can judge which capability/result/impact" as the central acceptance criterion.

KEY POINT: These commits were useful, but their center of gravity was "make env tools visible and routable." The next iteration must shift the center of gravity to "make env tools semantically decidable by the host."

KEY POINT: Do not repeat the same pattern by adding more tools, more command hints, or more field names without a semantic acceptance test.

## MCP Practice Signals

BuddySwitch does not need to become an MCP server for this work. The useful takeaway is the semantic shape MCP uses around tools.

Relevant MCP references:

- Tools specification: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- Schema reference: https://modelcontextprotocol.io/specification/2025-11-25/schema
- Client best practices: https://modelcontextprotocol.io/docs/develop/clients/client-best-practices
- Tool annotations risk vocabulary: https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/

MCP tool definitions carry model-facing and human-facing metadata:

- `title`: human-readable display name.
- `description`: human-readable functionality description that helps the LLM understand available tools.
- `inputSchema`: expected parameters with field descriptions.
- `outputSchema`: optional structured result shape.
- `annotations`: behavioral hints such as read-only, destructive, idempotent, and open-world behavior.

MCP also separates protocol errors from tool execution errors. Tool execution errors are visible to the model so the model can self-correct instead of treating every failure as an opaque transport failure.

MCP client practice also recommends progressive discovery when tool surfaces grow: catalog first, inspect details only when needed, then execute. The useful principle is not the exact mechanism. The useful principle is that the host needs enough semantic description at the discovery point to choose the right capability, and enough detail before execution to understand inputs and outputs.

KEY POINT: MCP annotations are hints, not authorization. BuddySwitch must keep runtime enforcement in broker/services. Semantic metadata improves host judgment; it must not become the security boundary.

KEY POINT: BuddySwitch should borrow MCP's semantic vocabulary, not import a full MCP architecture.

## Additional CLI And Agent Tool Research

This follow-up research checked whether broader CLI and agent-tool practice actually supports putting meaningful semantic information at the tool/env layer.

The answer is yes, with one important qualification:

```text
Agent-facing tools do carry substantial semantic metadata, but mature systems keep it targeted, structured, and sometimes progressively loaded.
```

### Anthropic Tool Guidance

Anthropic's tool definition guidance says client tools include `name`, `description`, `input_schema`, and optional `input_examples`. It specifically says `description` should explain what the tool does, when it should be used, and how it behaves. Its best-practice section recommends extremely detailed descriptions that cover:

- what the tool does;
- when it should and should not be used;
- what each parameter means and how it affects behavior;
- important caveats and limitations;
- what data the tool returns.

It also recommends high-signal tool responses, semantic stable identifiers, and helpful validation/error responses that steer the agent toward better tool use.

Reference:

- https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use
- https://www.anthropic.com/engineering/writing-tools-for-agents

Implication for BuddySwitch:

- `plain_description`, `use_when`, `do_not_use_when`, `inputs_explained`, `success_means`, `common_failures`, and high-signal result semantics are not over-designed. They map directly to established agent-tool guidance.

### OpenAI Function Calling Guidance

OpenAI's function-calling guide recommends clear and detailed function names, parameter descriptions, and instructions. It explicitly says to describe the function purpose, every parameter and format, and what the output represents. It also recommends telling the model when and when not to use each function, including edge cases and examples for recurring failures.

OpenAI also frames this as an "intern test": can a human correctly use the function given only what the model was given? If not, add the missing answers to the prompt/tool description.

OpenAI separately recommends tool search/deferred tools when there are many functions or large schemas, so detail is available without loading everything upfront.

Reference:

- https://platform.openai.com/docs/guides/function-calling

Implication for BuddySwitch:

- The host should not have to infer output meaning from code. "What the output represents" belongs in the tool/action contract.
- We should keep the semantic contract direct and testable, but can later use progressive discovery if context size becomes the bottleneck.

### Microsoft Semantic Kernel

Semantic Kernel's plugin documentation is unusually direct: just providing functions is not enough. It says plugins need details that semantically describe behavior, and that inputs, outputs, and side effects need to be described in a way AI can understand. It also recommends detailed descriptions, few-shot examples when needed, when-to-use/when-not-to-use guidance, and guidance on where required parameters come from.

Reference:

- https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/

Implication for BuddySwitch:

- Our "side_effects" and "result semantics" fields are not optional polish. They are exactly the missing category: behavior, output, and side-effect semantics.

### Pydantic AI

Pydantic AI extracts function docstrings and parameter descriptions into the tool schema sent to the model. It can enforce parameter descriptions with `require_parameter_descriptions=True`, raising an error if a parameter lacks a description.

Reference:

- https://pydantic.dev/docs/ai/tools-toolsets/tools/

Implication for BuddySwitch:

- Tests should fail when a payload field lacks explanation. Requiring `inputs_explained` for every payload field is aligned with this practice.

### LangChain, LlamaIndex, AutoGen, Vercel AI SDK

These frameworks all encode tool semantics at the tool layer:

- LangChain uses function docstrings as tool descriptions and type hints as input schema. It also distinguishes string returns, structured object returns, and state-updating command returns.
- LlamaIndex says tool selection and arguments rely strongly on the tool name and description, and that tuning these can significantly change how tools are called.
- AutoGen auto-generates schemas from signatures and type hints, and explicitly says clear descriptions matter because the LLM uses them to understand tool usage.
- Vercel AI SDK tools include `description`, `inputSchema`, field-level descriptions, and an `execute` result object.

References:

- https://docs.langchain.com/oss/python/langchain/tools
- https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/tools/
- https://autogenhub.github.io/autogen/docs/tutorial/tool-use/
- https://vercel.com/docs/ai-sdk

Implication for BuddySwitch:

- The ecosystem norm is not "code implementation is enough." It is "tool metadata is the model/host-facing contract."
- Structured return objects are normal; result shape matters to downstream reasoning.

### CLI-Specific Practice

Traditional CLI guidance still matters because BuddySwitch env tools are CLI-facing.

The Command Line Interface Guidelines recommend:

- concise and extensive help;
- JSON output for machine-readable cases;
- stdout/stderr separation;
- explaining state changes when commands mutate system state;
- suggesting follow-up commands;
- rewriting expected errors into useful, actionable messages;
- making current state easy to inspect.

The newer CLI Spec is explicitly agent-oriented. It says AI agents are now a primary CLI consumer and need structured output, predictable behavior, and machine-readable introspection. It recommends a `schema` command or equivalent runtime introspection that exposes:

- commands with descriptions;
- argument types/defaults/requiredness;
- output fields with types;
- finite error kinds;
- mutation markers for read-only vs state-changing commands.

References:

- https://clig.dev/
- https://clispec.dev/

Implication for BuddySwitch:

- Runtime introspection through `prepare.runtime_context.env_tools` is directionally correct.
- The current registry fields are a partial schema, but they lack output-field semantics, error-kind semantics, and mutation/impact descriptions rich enough for agent judgment.

### Claude Code MCP Tool Search

Claude Code's MCP docs show the practical context-management side: with many MCP tools, tool definitions can be deferred and loaded only when needed. Server instructions become important because they tell Claude what task categories the tools handle, when to search for them, and key capabilities. The docs also note description/instruction truncation and recommend putting critical details near the start.

Reference:

- https://code.claude.com/docs/en/mcp

Implication for BuddySwitch:

- We should not fear adding semantics, but we should structure it in layers:
  - short critical catalog fields first;
  - detailed action semantics available in runtime context while the surface is small;
  - later progressive discovery if env tools grow.

## Updated Research Conclusion

The stronger conclusion after this additional research:

```text
Yes, serious agent/tool ecosystems do put significant semantics at the tool layer.
They do not rely on implementation code as the host-facing contract.
```

But the best practice is not "dump huge prose everywhere." The best practice is:

1. Put decision-critical semantics in the tool/action definition.
2. Explain parameters, output meaning, side effects, and limitations.
3. Return structured, high-signal results.
4. Return actionable, structured errors/rejections.
5. Mark risk and mutation behavior.
6. Keep details concise and high priority.
7. Use progressive discovery/tool search only when the tool surface becomes too large.
8. Evaluate the tool surface with realistic tasks and transcripts.

KEY POINT: The community evidence strengthens, not weakens, the BuddySwitch direction. The next improvement should not be more docs around the tool layer; it should be a runtime-visible semantic contract that host decisions can rely on.

KEY POINT: The likely over-design boundary is not "semantic metadata exists." The over-design boundary is "building a full external tool protocol or generic schema framework before BuddySwitch needs it."

## Design Goal

Add a BuddySwitch env semantic contract that lets the host answer five questions without reading implementation:

1. What capability should I use now?
2. What inputs does it need and what do those inputs mean?
3. What will this call read or mutate?
4. What does success mean, including actual state impact?
5. What does rejection mean, including recovery and whether anything changed?

This must apply to all current env tools:

- `task`
- `track`
- `artifact`
- `context`
- `binding`
- `handoff`
- `run`
- `evidence`
- `search`

And to all current env actions.

## Host Judgment Acceptance Test

The concrete acceptance test for the next implementation should be:

```text
Given only prepare.runtime_context.env_tools plus tool responses from prior calls,
codex-cli can choose the next env capability, explain what the last call changed,
and decide whether the next recovery step is safe, useful, and allowed.
```

This must be true for:

- direct source intake: track id -> artifact ids -> full artifact read;
- joining work: missing relation -> track.join -> new or reused active-buddy task binding;
- artifact writes: validate/create revision -> produced artifact id -> run association;
- run validation/commit: validation-only result vs durable run commit;
- search/browser work: open-world browser/session effects and evidence requirements;
- blocked operations: no state changed, why blocked, what to do next;
- PM-only lifecycle changes vs non-PM task/artifact work.

KEY POINT: A passing implementation should let a reviewer inspect runtime context and sample responses, not service code, and still explain the intended next step and actual state impact.

## Option Evaluation

| Option | Description | Effect | Complexity | Decision |
| --- | --- | --- | --- | --- |
| A | Add more prose to docs and skill files only | Low to medium. Helps humans who read docs, but host still sees weak runtime semantics and still infers result meaning | Low | Reject as insufficient |
| B | Add registry-backed semantic fields, project them in `runtime_context.env_tools`, and standardize result/feedback semantics | High. Gives host a runtime-readable contract and actionable feedback without changing the broker model | Medium | Recommended |
| C | Build a full MCP-style catalog/detail/output-schema/annotation subsystem or expose a true MCP server | Very high, but more than the current bottleneck requires | High | Defer until external MCP host integration is a real need |

KEY POINT: The recommended option is B because it satisfies the host judgment requirement. Option A is cheaper but does not solve the core problem. Option C is more standard but too heavy for the current bottleneck.

## Recommended Contract Shape

### Capability Semantics

Each tool should expose a compact capability-level semantic block:

```json
{
  "title": "Track coordination",
  "plain_description": "Find tracks, inspect track context, join a track for the active buddy, and let PM mutate track lifecycle state.",
  "use_when": [
    "You need to find or inspect product work grouped by track.",
    "You have a track_id and need tasks, artifacts, relation, or handoff context.",
    "You need to join the active buddy to an existing track."
  ],
  "do_not_use_when": [
    "You already have an artifact_id and only need the full artifact body; use artifact.get.",
    "You need to commit the current run; use run.commit."
  ],
  "capability_boundary": {
    "identity_source": "active launcher instance",
    "authority_source": "manifest permissions plus runtime state checks",
    "raw_state_access": "not allowed; broker-owned only"
  }
}
```

This is not a replacement for `operation_semantics`. It is the plain-language decision surface that points to the correct operation.

### Action Semantics

Each action should expose semantic fields:

```json
{
  "title": "Join track",
  "plain_description": "Create or reuse an active-buddy task on the track and bind the current instance to that task.",
  "use_when": [
    "The active buddy needs to participate in an existing track.",
    "artifact.get or track.get says relation is missing and joining is the normal recovery."
  ],
  "do_not_use_when": [
    "You only need to read public track summaries; use track.get first.",
    "You are trying to change track lifecycle ownership; PM lifecycle actions handle that."
  ],
  "inputs_explained": {
    "track_id": "Existing track to join.",
    "task_id": "Optional existing active-buddy task on that track when multiple candidates exist."
  },
  "side_effects": {
    "mutates": "runtime_objects+instance_binding",
    "writes": ["task", "instance_binding"],
    "does_not_write": ["track_lifecycle", "artifact_content", "run_commit"],
    "durability": "runtime object state",
    "idempotency": "reuses a single active-buddy task when unambiguous; may reject when multiple candidates exist"
  },
  "success_means": "The active buddy has a task relation to the track and the current instance is bound to that task.",
  "common_failures": [
    "track_id does not exist",
    "track is archived",
    "multiple active-buddy tasks exist and task_id was omitted"
  ]
}
```

KEY POINT: `success_means` and `side_effects` are as important as `use_when`. Host confusion often happens after a successful call, not only after a rejection.

### Risk Hints

Use MCP-inspired risk hints, but keep them BuddySwitch-specific enough to be direct:

```json
{
  "risk_hints": {
    "read_only": false,
    "destructive": false,
    "idempotent": "conditional",
    "open_world": false,
    "requires_human_approval": false,
    "external_effect": false
  }
}
```

Mapping examples:

- `task.list`, `track.get`, `artifact.get`, `context.summarize`: read-only.
- `binding.set_task`, `task.set_current`: instance binding mutation.
- `task.create`, `artifact.create_revision`, `handoff.create`: runtime object writes.
- `run.commit`: durable run commit.
- `evidence.issue_browser`: broker token issuance.
- `search.open_browser`: browser session mutation and open-world interaction.
- `search.request` with `search_api`: open-world and provider-dependent.

KEY POINT: Treat `search` and browser-backed market research as open-world. Tool outputs from open web pages can carry untrusted content back into the host decision loop.

### Result Semantics

Every response should give the host enough meaning to interpret impact.

For success:

```json
{
  "effect_summary": "Joined track track-landing and bound current instance to task-dev-landing.",
  "state_changed": true,
  "state_changes": [
    {
      "object_type": "task",
      "object_id": "task-dev-landing",
      "change": "created_or_reused"
    },
    {
      "object_type": "instance_binding",
      "object_id": "inst-dev-...",
      "change": "current_task_id/current_track_id updated"
    }
  ],
  "durability": "runtime_object",
  "created_ids": [],
  "updated_ids": ["task-dev-landing"],
  "binding_changed": true,
  "read_scope": "track summary and active-buddy relation",
  "follow_up_affordances": [
    {
      "tool": "artifact",
      "action": "get",
      "reason": "Read a now-related artifact by id."
    }
  ]
}
```

For validation-only success:

```json
{
  "effect_summary": "Validated run result payload; no state was changed.",
  "state_changed": false,
  "durability": "none",
  "validation_only": true,
  "follow_up_affordances": [
    {
      "tool": "run",
      "action": "commit",
      "reason": "Commit the same validated context/result when ready."
    }
  ]
}
```

KEY POINT: `ok=true` is not enough. The host needs to know whether success changed state, what changed, and which follow-up ids or actions are now meaningful.

### Feedback Semantics

Every rejection should keep existing machine fields and add plain semantic fields:

```json
{
  "ok": false,
  "tool": "track",
  "action": "track.update",
  "error": {
    "code": "E_TRACK_LIFECYCLE_AUTHORITY",
    "message": "active buddy 'dev' cannot mutate track lifecycle state"
  },
  "permission_boundary": "track.lifecycle_authority",
  "human_summary": "Dev cannot change track lifecycle fields.",
  "why_blocked": "Only PM has authority to create, update, advance, or archive track lifecycle state.",
  "impact": "No track, task, artifact, binding, run, browser, or evidence state was changed.",
  "state_changed": false,
  "retryable": false,
  "retry_guidance": "Do not retry as Dev. Ask PM to perform the lifecycle change or use track.get/task/artifact tools for Dev-owned work.",
  "allowed_next_actions": [
    "Use PM for track lifecycle mutations.",
    "Non-PM buddies may read track context or attach their own task work to an existing track."
  ],
  "next_action_options": [
    {
      "tool": "track",
      "action": "get",
      "reason": "Inspect current track context without mutating lifecycle state."
    },
    {
      "tool": "handoff",
      "action": "create",
      "reason": "Ask another buddy to continue when ownership needs to move."
    }
  ]
}
```

KEY POINT: `permission_boundary` should remain stable for tests and machines, but it must be accompanied by normal-language explanation and impact.

KEY POINT: Rejections must say whether any state changed. Most rejections should be `state_changed=false`; if an operation can partially apply before failure, that must be explicit.

## Projection Strategy

The host should receive semantic information in `prepare.runtime_context.env_tools`.

Because BuddySwitch currently has 9 tools and 42 actions, it is acceptable to project a compact semantic block for all actions now. If the action count grows enough to burden context, move to a progressive shape:

1. Catalog: tool/action names, titles, one-line descriptions, risk hints.
2. Inspect: full semantic detail for selected tool/action.
3. Execute: `env.tool`.

Do not start with a heavy catalog/inspect subsystem unless context size becomes a measured problem.

KEY POINT: The current bottleneck is missing semantic meaning, not too many tools. Add the semantic contract first; add progressive discovery only when the tool surface is large enough to justify it.

## Implementation Shape

Preferred minimal implementation:

1. Extend the env tool contract source with semantic fields.
   - Keep one source of truth near `TOOL_REGISTRY`, or use a small adjacent module if the file becomes hard to read.
   - Avoid a generic DSL or workflow engine.
2. Add semantic projection to `env_tools_description()`.
   - Keep existing fields.
   - Add capability/action semantic fields.
3. Add response helpers for result and feedback semantics.
   - Keep `ok`, `tool`, `action`, `permission_boundary`, `allowed_next_actions`, and `command_hint`.
   - Add `effect_summary`, `state_changed`, `state_changes`, `durability`, `human_summary`, `why_blocked`, `impact`, `retryable`, and `retry_guidance`.
4. Upgrade high-impact service responses first.
   - `track`
   - `artifact`
   - `task`
   - `run`
   - `handoff`
   - `search`
   - `evidence`
   - `context`
   - `binding`
5. Add tests that enforce semantic coverage and feedback quality.

This should remain concrete. Do not introduce:

- a plugin system;
- a workflow engine;
- a generic permission language;
- a full MCP server;
- a generalized schema-generation framework;
- a long-lived parallel compatibility path.

KEY POINT: The semantic contract should make existing direct env tools understandable. It should not create a second tool system.

## Verification Requirements

The work is not done when fields exist. It is done when tests prove host-readable semantics exist for the full surface.

Required test coverage:

1. Every registered tool has:
   - `title`
   - `plain_description`
   - `use_when`
   - `do_not_use_when`
   - capability boundary text
2. Every registered action has:
   - `title`
   - `plain_description`
   - `inputs_explained`
   - `side_effects`
   - `risk_hints`
   - `success_means`
   - `common_failures`
3. Every action with `payload_fields` explains every payload field.
4. Every action with non-`none` mutation explains what it may write.
5. Every success response includes:
   - `effect_summary`
   - `state_changed`
   - `durability`
   - enough fields to interpret created/updated/bound/read result impact
6. Every rejection response includes:
   - `human_summary`
   - `why_blocked`
   - `impact`
   - `state_changed`
   - `retryable`
   - `retry_guidance`
7. Key recovery paths preserve command hints and structured next actions.
8. Tests explicitly reject docs-only coverage as sufficient.

Suggested focused test areas:

- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_repo_consistency.py`
- tool-specific tests such as `tests/test_track_env_tool.py`, `tests/test_artifact_env_tool.py`, `tests/test_search_env_tool.py`, and `tests/test_run_env_tool.py`

KEY POINT: Tests should enforce semantic coverage, not just JSON field existence. A field like `plain_description=""` or `"Use this tool"` should fail.

## Scope Boundaries

In scope:

- Env tool semantic metadata.
- Projection into runtime context.
- Response and feedback semantic fields.
- Tests that enforce semantic coverage.
- Updating docs/specs that define the new contract.

Out of scope for this iteration:

- Full MCP server exposure.
- External MCP registry integration.
- New host-side tool search implementation.
- Browser UI work.
- Rebuilding task/track/artifact product behavior.
- Changing core permission enforcement.

## Definition Of Done

This initiative is done when:

1. `prepare.runtime_context.env_tools` contains enough semantic information for host-side tool choice without service-code reading.
2. Every env action describes when to use it, what it changes, what success means, and common failures.
3. Successful tool responses describe actual effect and state impact.
4. Rejected tool responses explain the boundary, impact, retryability, and next step in normal language.
5. Runtime enforcement remains in broker/service code.
6. Tests fail if a new tool/action is added without semantic coverage.
7. The implementation does not introduce a heavy new abstraction layer beyond what the above requirements need.

## Final Recommendation

Implement Option B: a registry-backed BuddySwitch env semantic contract plus unified result/feedback semantics.

Do not settle for docs-only description. Do not jump to a full MCP architecture. Add the smallest complete semantic layer that lets `codex-cli` reason from runtime contracts and tool responses instead of reading implementation code.

KEY POINT: The success criterion is host judgment quality, not schema elegance.

# Buddybox Tool Layer Realignment Memo

Date: 2026-05-16
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: discussion convergence memo only. Do not treat this document as implementation.

## Background

This memo captures the product and architecture decision reached after reviewing the current
BuddySwitch `buddybox` implementation and discussing how the host should discover and use
runtime capabilities.

The immediate trigger was an observed runtime workspace layout:

```text
buddyswitch/local/buddybox/pm
-> /Users/chen/.codex-buddyswitch/state/buddyswitch/local/buddybox/pm
```

That layout showed that the active buddybox directory is currently projected into the instance
workspace as a symlink to launcher shared state. This contradicts the direction that `buddybox`
should be the active buddy's private local file capability, not product-readable shared runtime
state and not a host-visible filesystem contract.

The deeper issue is not only where bytes are stored. The deeper issue is the layer boundary:

- `buddybox` should be a tool-layer capability.
- The host should not reason from physical paths.
- The host should receive enough tool semantics and feedback to decide whether and how to use the
  capability.
- Prompt, AGENTS, and skill text should not become the primary enforcement layer for this behavior.

## Current Code Reality

The current implementation still exposes and depends on filesystem-oriented semantics.

Observed implementation points:

- `scripts/runtime_kernel/dispatcher.py` sets `BUDDYSWITCH_STATE_ROOT` to
  `<shared_root>/state`.
- `scripts/env_store.py` derives `BUDDYBOX_LOCAL_DIR` from
  `STATE_ROOT / "buddyswitch/local/buddybox"`.
- `tools/launcher/workspace.sh` creates the active buddy state directory under
  `${BUDDYSWITCH_SHARED_ROOT}/state/buddyswitch/local/buddybox/<buddy>` and symlinks
  `workspace/buddyswitch/local/buddybox/<buddy>` to it.
- `tests/test_buddyswitch_launcher.py` currently asserts that the workspace buddybox projection is
  a live symlink to shared state.
- `scripts/env/services/buddybox.py` currently requires paths shaped like `<active_buddy>/...`,
  which means the host must understand and supply active-buddy path prefixes.
- `scripts/env/services/context.py` currently exposes the buddybox source as
  `buddyswitch/local/buddybox/<active_buddy>/**`.
- `scripts/env/tools/semantics.py` currently describes writes as affecting
  `buddyswitch/local/buddybox/<active_buddy>/**`.

Current strengths:

- Buddybox already has a real service layer with active-buddy scope checks.
- Rejections already return structured fields such as `why_blocked`, `impact`, `retryable`, and
  `retry_guidance`.
- Tool semantics already include `use_when`, `do_not_use_when`, input explanations, side effects,
  success meanings, and common failures.
- `context.get` already exposes `tool_catalog` and `operation_semantics`.
- `context.summarize` already exposes compact tool affordance rows.

Current weaknesses:

- The storage projection still treats buddybox as shared runtime state.
- Host-facing semantics still expose filesystem paths.
- Inputs still require the host to supply active-buddy path prefixes.
- `allowed_next_actions` still contains command-like prose that can be mistaken for SOP.
- Response fields do not yet cleanly distinguish private file state, product-readable state,
  cross-buddy readability, instance lifetime, and product-state mutation.

## Corrected Principle

When a capability is missing, insufficient, or incorrectly bounded, improve the corresponding tool
implementation.

When the host is unsure how to use a tool, improve the tool's description, operation semantics,
response fields, rejection fields, and decision signals.

Do not respond to tool-layer weakness by adding more prompt rules for the host to remember.

Applied to buddybox:

- Do not teach Codex CLI to remember a physical directory.
- Do not ask the host to understand shared root, workspace root, symlink targets, or state storage.
- Do not turn common scenarios into mandatory SOPs.
- Do make `buddybox` expose enough capability, side-effect, visibility, lifetime, and recovery
  information for the host to choose its own strategy.

## Corrected Mental Model

`buddybox` is not a path.

`buddybox` is a tool-backed private file capability for the active buddy.

The host should understand `buddybox` through capabilities and structured signals:

- it can hold private files for the active buddy;
- it can write text or binary content;
- it can list summaries;
- it can read exact private files;
- it can delete exact private files;
- it does not create product-readable deliverables;
- it does not grant cross-buddy read authority;
- it does not mutate task, track, artifact, handoff, context, or evidence objects;
- if readable collaboration state is needed, another explicit tool such as `artifact` must carry
  the readable content.

The host should not need to know:

- where the file is physically stored;
- whether the runtime uses a real directory or symlink internally;
- where shared state is mounted;
- what active buddy prefix belongs in a filesystem path.

## Task Goal

Rebuild `buddybox` around the tool-layer capability boundary.

The target outcome is:

- Buddybox storage is active-instance local, not shared product/runtime state.
- The workspace buddybox directory is a real local directory, not a symlink to shared state.
- The tool owns path resolution and active-buddy namespace handling.
- The host-facing contract uses logical names and semantic fields, not physical paths.
- Context and tool semantics provide rich decision signals without prescribing fixed workflows.
- Rejections provide structured correction information so the host can recover without guessing.

## Non-Goals

Do not implement or preserve:

- shared buddybox storage under `~/.codex-buddyswitch/state`;
- a symlink from workspace buddybox to shared state;
- cross-instance buddybox synchronization;
- cross-buddy buddybox reads;
- buddybox paths as handoff payloads;
- buddybox paths as artifact-readable content;
- a generic permission framework;
- a rule engine or phrase-to-tool router;
- a prompt-heavy AGENTS expansion;
- large prose mirrors of runtime behavior;
- compatibility wrappers that keep old shared-state buddybox behavior alive.

If older runtime state exists under shared-state buddybox paths, it should be treated as legacy
unmanaged state unless a separate user request explicitly asks for migration or cleanup.

## Recommended Storage Direction

Implementation detail:

```text
<instance workspace>/buddyswitch/local/buddybox/<active_buddy>/
```

should be a real directory, not:

```text
<instance workspace>/buddyswitch/local/buddybox/<active_buddy>
-> <shared_root>/state/buddyswitch/local/buddybox/<active_buddy>
```

This keeps the active buddybox lifecycle bound to the active instance workspace and removes it from
shared product/runtime state.

Important boundary:

This directory location is an implementation detail. It should not become a host-facing contract.
Tool responses and context should not expose the absolute path, shared root, symlink target, or
workspace root.

## Tool Input Direction

Current input shape:

```json
{
  "path": "pm/prototypes/hero.html"
}
```

Target input shape:

```json
{
  "logical_name": "prototypes/hero.html"
}
```

Rationale:

- The active buddy is already known by the runtime context.
- The host should not need to repeat `pm/`, `dev/`, `design/`, `market/`, or `test/`.
- Tool-owned namespace resolution prevents the host from reasoning about physical paths.
- This reduces invalid calls caused by foreign buddy prefixes.

Path safety still belongs inside the tool:

- reject absolute paths;
- reject traversal;
- reject empty names;
- reject names resolving outside the active buddy private directory;
- reject symlink escapes if symlinks can appear under the private directory;
- keep all active-buddy ownership checks in service code and tests.

## Tool Discovery Direction

`context.summarize`, `context.get`, and tool catalog output should describe `buddybox` as a
capability, not as a path.

Good capability-level fields:

```json
{
  "capability": "private_file_workspace",
  "owner_scope": "active_buddy",
  "lifetime_scope": "active_instance_workspace",
  "visibility": "active_buddy_private",
  "product_readable": false,
  "cross_buddy_readable": false,
  "mutates_product_state": false,
  "supports": [
    "describe_capability",
    "list_private_file_summaries",
    "read_private_file",
    "write_private_text",
    "write_private_binary",
    "delete_private_file"
  ]
}
```

Avoid host-facing fields like:

```json
{
  "source_of_truth": "buddyswitch/local/buddybox/<active_buddy>/**",
  "logical_root": "buddyswitch/local/buddybox/pm",
  "writes": ["buddyswitch/local/buddybox/<active_buddy>/**"]
}
```

The service may still use internal paths, but context should expose capability semantics.

## Response Signal Direction

Buddybox tool responses should return high-signal structured context.

Recommended success fields:

```json
{
  "ok": true,
  "tool": "buddybox",
  "action": "write",
  "active_buddy": "pm",
  "state_changed": true,
  "object_kind": "private_file",
  "logical_name": "prototypes/hero.html",
  "visibility": "active_buddy_private",
  "owner_scope": "active_buddy",
  "lifetime_scope": "active_instance_workspace",
  "durability": "active_instance_local",
  "product_readable": false,
  "cross_buddy_readable": false,
  "mutates_product_state": false,
  "mutated_product_objects": [],
  "content_type": "text/html",
  "size_bytes": 1234,
  "created": true,
  "overwrote": false,
  "available_affordances": [
    {
      "tool": "buddybox",
      "action": "read",
      "effect": "read one active buddy private file",
      "condition": "host wants to inspect the private file content"
    },
    {
      "tool": "artifact",
      "action": "create_revision",
      "effect": "create product-readable content",
      "condition": "host decides another buddy or product workflow must read this content",
      "risk": "creates or updates product deliverable state"
    }
  ]
}
```

The important shift is from command-like prose to structured affordances.

Affordances should not force a path. They should say what is possible, under what condition, and
what effect the option has.

## Rejection Signal Direction

Rejections should be machine-readable and self-correcting.

Recommended rejection fields:

```json
{
  "ok": false,
  "tool": "buddybox",
  "action": "write",
  "error": {
    "code": "E_BUDDYBOX_LOGICAL_NAME",
    "class": "invalid_input"
  },
  "boundary": "active_buddy_private_file_capability",
  "state_changed": false,
  "mutates_product_state": false,
  "retryable": true,
  "correctable_fields": ["logical_name"],
  "why_blocked": "logical_name must be relative and stay inside the active buddy private file workspace",
  "alternative_capabilities": [
    {
      "tool": "artifact",
      "condition": "use when content must be product-readable"
    }
  ]
}
```

Avoid rejection guidance that says:

- retry with a path under `<active_buddy>/...`;
- edit `buddyswitch/local/buddybox/**` directly;
- inspect shared runtime state manually;
- use buddybox path as a cross-buddy reference.

## Prompt And Documentation Role

Prompt and docs remain useful, but only as a route map.

AGENTS and skills may say:

- use BuddySwitch env tools for runtime state;
- use context discovery to inspect available tools;
- use `buddybox` tool for active buddy private files;
- do not edit raw runtime state directly.

AGENTS and skills should not:

- encode filesystem roots;
- duplicate full schemas;
- list every scenario as a required procedure;
- prescribe "if user says X, call buddybox";
- make artifact promotion mandatory after every buddybox write.

If host behavior is weak, first improve the tool description, semantics, response structure, and
tests before adding prompt rules.

## Scenario Framing Correction

Earlier examples such as "PM writes a PRD draft" or "Design writes a prototype" are not intended
as SOP.

They are only examples of possible host decisions.

The product goal is not:

```text
when PM writes a draft, always use buddybox first
```

The product goal is:

```text
when the host is deciding how to handle a task, it can see that buddybox is a private file
capability, artifact is product-readable deliverable state, handoff is cross-buddy coordination
state, and project source writes are separate.
```

The host should then decide from task context.

This distinction matters. In an agentic system, over-prescribed workflows reduce the model's
ability to solve novel tasks. Rich capability descriptions and structured feedback expand what the
host can do safely.

## External Best-Practice Inputs

The discussion reviewed current community and official guidance.

Relevant takeaways:

- OpenAI function calling guidance emphasizes clear function definitions, schemas, and structured
  outputs. Tool callers should not be forced to provide values the application already knows.
  Reference: `https://developers.openai.com/api/docs/guides/function-calling`
- Anthropic tool guidance says tool descriptions should explain what the tool does, when to use it,
  when not to use it, parameter meanings, behavior, caveats, and returned data.
  Reference: `https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools`
- Anthropic's tool engineering guidance says tools for agents are not ordinary API wrappers.
  Effective tools return meaningful context, avoid low-level implementation identifiers, and should
  be improved through realistic evaluations and transcript review.
  Reference: `https://www.anthropic.com/engineering/writing-tools-for-agents`
- LangChain tool guidance distinguishes string returns from structured object returns and notes
  that structured outputs help downstream reasoning.
  Reference: `https://docs.langchain.com/oss/python/langchain/tools`
- MCP tool annotations provide a risk vocabulary such as read-only, destructive, idempotent, and
  open-world. These are hints, not authorization, but they show the value of structured behavioral
  metadata.
  Reference: `https://modelcontextprotocol.io/specification/2025-11-25/schema`
- The MCP tool annotation blog emphasizes that annotations are useful only when clients can take
  concrete action from them.
  Reference: `https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/`
- Recent MCP tool-description research identifies description quality dimensions: accuracy,
  functionality, information completeness, and conciseness. Missing parameter and return semantics
  materially hurt tool selection.
  Reference: `https://arxiv.org/abs/2602.18914`
- Recent MCP production-pattern research highlights structured error semantics as a missing
  primitive for deterministic agent self-correction.
  Reference: `https://arxiv.org/abs/2603.13417`

## Recommended Implementation Shape

This memo is not an implementation plan, but the likely implementation should stay focused:

1. Replace shared-state buddybox projection with an active-instance workspace local real directory.
2. Update `env_store` or service-level resolution so buddybox no longer derives active storage from
   `BUDDYSWITCH_STATE_ROOT`.
3. Update launcher workspace setup so it creates real buddybox directories instead of symlinks to
   shared state.
4. Replace host-facing `path` input with `logical_name` in buddybox operations, or clearly stage
   that replacement if tests need a narrow transition.
5. Remove active-buddy prefix requirements from host-facing payload semantics.
6. Update `context.list_sources`, `context.get`, `context.summarize`, and `operation_semantics` to
   expose capability metadata rather than path roots.
7. Replace command-like `allowed_next_actions` strings with structured affordance objects where
   possible.
8. Add response fields for visibility, lifetime, product readability, cross-buddy readability, and
   product-state mutation.
9. Update rejection responses to identify correctable fields and alternative capabilities.
10. Keep AGENTS and shared skills short; only adjust them enough to point hosts to tool discovery.

## Verification Targets

Focused tests should prove behavior, not just field presence.

Required launcher/storage tests:

- starting an instance creates a real directory at the active workspace buddybox location;
- the active workspace buddybox location is not a symlink;
- active buddybox files are not created under shared state;
- only the active buddy's private capability is exposed in that instance;
- workspace rebuild preserves or intentionally scopes private files according to the chosen
  instance-local lifecycle.

Required service tests:

- write text with `logical_name`;
- write binary with `logical_name`;
- list summaries without content bodies;
- read exact private file content;
- delete exact private file;
- reject absolute names;
- reject traversal;
- reject empty names;
- reject symlink escape if applicable;
- do not require or accept foreign buddy prefixes as host-facing input;
- do not mutate product objects for buddybox operations.

Required context/semantics tests:

- `context.get` exposes capability metadata, not filesystem roots;
- `context.list_sources` does not expose physical or logical filesystem source paths for buddybox;
- `operation_semantics` explains inputs and outputs without requiring `<active_buddy>/...`;
- side-effect metadata distinguishes private file mutation from product object mutation;
- response semantics include visibility, lifetime, readability, and product-state mutation fields.

Required rejection tests:

- invalid logical names return structured correction information;
- cross-boundary attempts return non-leaking rejection payloads;
- rejection payloads include `state_changed=false`;
- rejection payloads do not advise direct filesystem edits;
- rejection payloads point to alternative capabilities only as conditional affordances.

Required host-decision tests:

- tool semantics are sufficient for a host to distinguish private files from product-readable
  artifacts;
- buddybox is not advertised as a handoff-readable payload mechanism;
- artifact remains the explicit content carrier when product-readable state is required;
- no test encodes a mandatory phrase-to-tool SOP such as "prototype means buddybox".

## Definition Of Done For This Task

This task is done only when:

- buddybox no longer stores active files in shared state;
- buddybox no longer exposes physical path contracts to the host;
- host-facing inputs use tool-owned logical names;
- tool descriptions and operation semantics expose enough decision information without SOP;
- responses and rejections provide structured signals for host reasoning and recovery;
- AGENTS and skills stay route-map level;
- tests verify storage boundary, semantic boundary, tool behavior, and rejection behavior;
- remaining legacy shared-state buddybox data is either ignored as unmanaged legacy state or
  explicitly queued for a separate cleanup task.

## Open Decision To Confirm Before Implementation

The main design decision to confirm is whether to make the `path` to `logical_name` replacement as
a direct breaking change.

Recommended answer: yes.

Reason:

- This branch is following SHARP forward rules.
- The old host-facing path contract is the current bottleneck.
- Keeping both `path` and `logical_name` would preserve the confusion that this task is meant to
  remove.
- There is no stated external API commitment requiring compatibility.

If a short transition is required for tests or internal callers, it should be explicitly bounded and
removed in the same change set.


# Track/Task/Artifact Tooling Upgrade Multi-Agent Brief

Date: 2026-05-14
Worktree: `dev2258`
Status: task brief for a future `/clear` restart
Primary seed memo: `docs/memo/2026-05-13-cross-buddy-artifact-access-memo.md`

## Purpose

Use this document after `/clear` to restart Codex with a clear, bounded task:

> Start multiple read-only sub-agents in `.worktrees/dev2258` to research and discuss a major BuddySwitch upgrade plan for track, task, artifact, context, handoff, run, and related env tool capabilities. The plan must use the cross-buddy artifact access issue as the concrete trigger, but it should produce a broader system-level upgrade proposal for env buddy output management and collaboration.

Do not implement code during this task. The output should be a written upgrade proposal and implementation-planning handoff, saved under `docs/memo/`.

## Non-Negotiable Direction

The design direction is not to minimize tools. The design direction is to build a rich, explicit, recoverable environment where the Codex CLI host can make good autonomous decisions.

The target system should provide:

- enough env tools;
- enough tool descriptions and operation semantics;
- enough structured success, rejection, permission, and recovery feedback;
- enough prepared runtime context and discoverable state;
- enough skills and AGENTS guidance to frame higher-level work without replacing executable tool capability.

Do not frame `AGENTS.md`, skills, and env tools as conflicting layers.

Use this layering model:

- `AGENTS.md`: high-level runtime boundary, product philosophy, major constraints, and collaboration principles.
- Skills: richer problem-solving workflows, tool-composition guidance, domain method, and output standards.
- Env tools: executable runtime capability, state reads/writes, permission boundaries, and structured feedback.
- Runtime context/tool descriptions: current environment facts, available operations, payload hints, mutability, authorities, and response contracts.
- Tool feedback: closed-loop recovery after success or rejection, including allowed next actions.

The goal is not hidden orchestration. The goal is a tool-rich, context-rich environment where host + skills can reason forward.

## Current Trigger

The seed memo reports a real product failure mode:

- Dev saw track-level summaries for PM PRD and Design handoff artifacts.
- Dev could not read the full artifact bodies.
- The receipt showed `task: none`, `track: none`, `artifact ids: []`, `handoff: none`.
- Dev stopped rather than pretending it had read executable source artifacts.

This is correct agent caution and a product signal.

The core gap:

```text
cross-buddy artifact handoff content exists,
but the visible tool layer does not expose a short, obvious, validated read path.
```

The broader opportunity:

```text
rebuild track/task/artifact collaboration tooling so each buddy can discover, inspect, prepare, read, write, validate, and hand off work through explicit env tools, rich descriptions, and structured feedback.
```

## Hard Constraints

- Work only in `.worktrees/dev2258`.
- Do not touch main.
- Do not implement source changes during the research/discussion phase.
- Sub-agents should be read-only unless the coordinator later explicitly requests a document-writing worker.
- Do not edit raw runtime state under `buddyswitch/objects/**` or `buddyswitch/content/runs/**`.
- Do not broaden `artifact.get` into a global cross-buddy full-content reader as the default design.
- Do not put foreign full artifact bodies into `track.get`.
- Do not let non-PM buddies mutate track lifecycle or bind arbitrary tracks directly without a justified explicit tool design.
- Do not add hidden workflow routers, automatic binding, handoff inboxes, ACL engines, event buses, DSLs, or compatibility alias layers as the default answer.
- Do not reduce the plan to prompt wording. Tool capability, tool metadata, runtime context, skills, and feedback all matter.

## Required Coordinator Behavior

The coordinator Codex session should:

1. Read this brief.
2. Read `AGENTS.md`.
3. Read `docs/memo/2026-05-13-cross-buddy-artifact-access-memo.md`.
4. Inspect the current tool registry and services before forming conclusions.
5. Spawn multiple sub-agents with disjoint read-only research scopes.
6. Let sub-agents independently recommend target tool surfaces and tests.
7. Synthesize the results into one coherent upgrade proposal.
8. Save the proposal under `docs/memo/`.
9. Stop before implementation unless the user explicitly approves moving into an implementation plan.

Recommended final proposal filename:

```text
docs/memo/2026-05-14-track-task-artifact-tooling-upgrade-proposal.md
```

If date context has changed, use the current date.

## Recommended Sub-Agent Set

Start at least six sub-agents if tool limits allow. If the environment limits concurrent agents, start as many as possible, close completed agents, then continue until all six scopes have been covered.

### Agent 1: Current Env Tool Surface Inventory

Scope:

- `scripts/env/tools/contracts.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/client.py`
- `scripts/env/tools/responses.py`
- tests for env tool router and response contracts

Questions:

- What tools/actions exist today?
- Which are read-only, mutating, binding, validating, or committing?
- How rich are payload hints, authority descriptions, preconditions, returns, and operation semantics?
- Where are tool descriptions too thin for host autonomy?
- Which feedback responses already provide actionable recovery, and which are vague?

Deliverable:

- Current tool catalog.
- Weak action descriptions.
- Missing tool actions.
- Feedback improvements.
- Tests that should lock the tool contract.

### Agent 2: Track/Task/Artifact Data And Lifecycle Model

Scope:

- `scripts/env_store.py`
- `scripts/env/services/tasks.py`
- `scripts/env/services/tracks.py`
- `scripts/env/services/artifacts.py`
- tests for task, track, artifact env tools

Questions:

- What are the authoritative object shapes for tracks, tasks, artifacts, slots, revisions, runs, and bindings?
- What lifecycle operations are explicit tool actions today?
- What ownership and currentness boundaries already exist?
- Where does the data model already support richer collaboration?
- Where does it block or hide legitimate host decisions?

Deliverable:

- Object model summary.
- Lifecycle and ownership summary.
- Candidate additions such as `track.join`, `task.create_for_track`, artifact current output inspection, revision/history tooling, or validation tooling.
- Data constraints that must be preserved.

### Agent 3: Context, Cross-Buddy Reads, And Relation Model

Scope:

- `scripts/env/services/context.py`
- `scripts/env/services/bindings.py`
- `scripts/turn_runtime.py`
- `scripts/env/services/handoffs.py`
- tests for context/binding/handoff/prepared runtime

Questions:

- How does full cross-buddy artifact content currently become available?
- What relation should authorize a buddy to read full current track artifacts?
- Should there be `context.get_track_artifacts`, `context.explain_track_access`, `context.inspect_track_outputs`, or similar actions?
- What should unbound sessions see?
- How should rejections explain missing binding, missing relation, stale context, or wrong tool choice?

Deliverable:

- Proposed relation model.
- Proposed context read/explain actions.
- Response shape for full upstream artifact reads.
- No-leak rejection contract.
- Tests for participant/current/next/handoff/unrelated cases.

### Agent 4: Buddy Workflow And Skills Layer

Scope:

- `tools/launcher/assets/buddies/*/AGENTS.md`
- `buddyswitch/skills/shared/task-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- buddy-specific skills under `buddyswitch/skills/**`
- `buddyswitch/manifest.toml`

Questions:

- How should AGENTS, shared skills, and buddy-specific skills cooperate with env tools?
- What richer skill workflows should exist for cross-buddy collaboration?
- What should `task-tool`, `track-tool`, and `artifact-tool` teach beyond command lists?
- How should skills use tool feedback without becoming brittle flow scripts?
- What should each buddy naturally do with the upgraded tool layer?

Deliverable:

- Skill and AGENTS improvement proposal.
- Per-buddy collaboration workflows.
- Skill/tool division of responsibility.
- Avoided anti-patterns.

### Agent 5: Feedback, Permissions, And Recovery Contract

Scope:

- all env service rejection paths for task/track/artifact/context/binding/handoff/run/search
- `scripts/env/tools/responses.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`

Questions:

- What should every rejection payload include?
- How should permission feedback distinguish manifest permission, buddy scope, task scope, track relation, source run, stale binding, and payload errors?
- What should `allowed_next_action_options` contain?
- Should command hints be standardized?
- What feedback fields should become contractually required for collaboration-critical tools?

Deliverable:

- Canonical feedback schema proposal.
- Field-by-field examples for common failures.
- Upgrade checklist for service responses.
- Contract tests.

### Agent 6: End-To-End Collaboration And Verification Strategy

Scope:

- `tests/test_env_layer_end_to_end.py`
- `tests/test_turn_integration.py`
- `tests/test_prepare_runtime_context.py`
- `tests/test_context_binding_env_tool.py`
- relevant docs/spec and memo files

Questions:

- What end-to-end scenarios prove the upgrade?
- What is the shortest meaningful test loop?
- How do we verify PM -> Market -> Design -> Dev -> Test collaboration with explicit tools?
- How do we prove dev can read full PRD/design source artifacts before implementation?
- How do we verify no hidden lifecycle mutation returns through prepare/persist?

Deliverable:

- Acceptance scenarios.
- Focused test plan.
- Broader regression plan.
- Manual product-mode checks, if needed.

## Optional Agent 7: Proposal Synthesizer

Use this only if tool limits allow or after other agents complete.

Scope:

- Read all sub-agent results.
- Produce an integrated proposal outline.
- Identify conflicts and decide according to SHARP and the user's tool-rich environment principle.

Deliverable:

- Draft proposal structure.
- Phased roadmap.
- Non-goals and risks.

## Prompt Template For Each Sub-Agent

Use this shape when spawning:

```text
You are Sub-agent N: <role>.
Work only in /Users/chen/Dev/buddyswitch/.worktrees/dev2258.
Read-only: do not edit, create, delete, format, commit, or run commands that write repo files.

Task context:
- Read docs/memo/2026-05-14-track-task-artifact-tooling-upgrade-subagent-brief.md.
- Use docs/memo/2026-05-13-cross-buddy-artifact-access-memo.md as the concrete trigger.
- The design principle is a tool-rich, context-rich BuddySwitch env where Codex CLI host can autonomously decide using env tools, runtime context, skills, AGENTS guidance, and structured feedback.
- Do not frame tools and skills as competing layers.

Your scope:
<scope>

Your questions:
<questions>

Return:
- Findings with file references.
- Recommended tool/skill/context/feedback upgrades.
- Risks and non-goals.
- Tests that should prove your recommendations.
```

## Proposal Requirements

The final proposal should be more ambitious than adding a single action, while still avoiding speculative platform architecture.

It should cover these capability groups:

### Discovery

Hosts should be able to discover:

- candidate tracks relevant to active buddy;
- current and historical tasks on a track;
- current artifacts by buddy/kind/source;
- recent handoffs;
- output readiness and blockers;
- which artifacts are summaries only versus full-content readable.

Possible tools/actions to evaluate:

- `track.inspect`
- `track.outputs`
- `context.discover`
- `handoff.discover`
- `artifact.list_track_current`

### Explanation

Hosts should be able to ask why they can or cannot access something.

Possible tools/actions to evaluate:

- `context.explain_track_access`
- `artifact.explain_access`
- `binding.explain`
- `track.explain_relation`

Feedback should include relation, permission boundary, missing preconditions, and next actions.

### Preparation

Hosts should be able to prepare legitimate active-buddy work context without guessing a multi-step sequence.

Possible tools/actions to evaluate:

- `track.join`
- `task.create_for_track`
- `binding.prepare_for_track`

These should remain explicit mutating actions, not automatic binding.

### Reading

Hosts should be able to read legitimate upstream source artifacts through relation-aware context.

Possible tools/actions to evaluate:

- `context.get_track_artifacts`
- `context.get_upstream_artifacts`
- `track.read_current_outputs`

These actions must preserve:

- direct `artifact.get` buddy scope;
- summary-safe `track.get`;
- no content leak on rejection.

### Writing

Hosts should have clear writing tools for active-buddy outputs.

Evaluate whether existing actions are enough:

- `artifact.validate_payload`
- `artifact.create_revision`
- `artifact.update_metadata`
- `task.update`
- `track.attach_task`

Consider whether richer artifact draft/check actions are needed before creation.

### Validation

Hosts should be able to validate result coherence before commit.

Possible enhancements:

- stronger `run.validate_result`;
- `artifact.validate_association`;
- `track.validate_ready_for_handoff`;
- `context.validate_sources_read` if there is a concrete state proof.

Avoid fake proof fields that claim a host read something. Prefer verifying available context and declared associations.

### Feedback

Every collaboration-critical tool response should make the next valid action obvious.

Evaluate a standard feedback schema with:

- `permission_boundary`;
- `relation`;
- `missing_preconditions`;
- `available_read_surfaces`;
- `blocked_surfaces`;
- `allowed_next_actions`;
- `allowed_next_action_options`;
- `command_hint`;
- `stop_condition`;
- `no_content_leak: true` for rejection cases involving artifact bodies.

### Skills And Guidance

The proposal must include skill and AGENTS updates as first-class work.

Expected direction:

- AGENTS keeps high-level frame and runtime boundaries.
- Shared skills explain richer workflows and tool composition.
- Env tools provide executable state and feedback.
- Tool descriptions expose operation semantics.

Avoid:

- making skills brittle hardcoded scripts;
- making AGENTS a giant procedure manual;
- making env tools too thin and relying on prose to compensate.

## Suggested Final Proposal Structure

The final proposal document should use this outline:

```markdown
# Track/Task/Artifact Collaboration Tooling Upgrade Proposal

Date:
Worktree: `dev2258`
Seed memo:

## Executive Summary

## Product Principle

## Current State

## Core Bottleneck

## Target Architecture

## Tool Capability Roadmap

### Discovery Tools
### Explanation Tools
### Preparation Tools
### Reading Tools
### Writing Tools
### Validation Tools
### Feedback Contract
### Skills And AGENTS Guidance

## Recommended Phases

### Phase 0: Feedback And Descriptions
### Phase 1: Relation-Aware Reading
### Phase 2: Preparation And Join Tools
### Phase 3: Output Management And Validation
### Phase 4: Skill/Docs/Runtime Context Integration

## Test Strategy

## Acceptance Scenarios

## Non-Goals

## Risks

## Open Questions

## Implementation Planning Handoff
```

## Acceptance Criteria For The Proposal

The generated proposal is acceptable only if it:

- honors the user's tool-rich environment principle;
- treats skills and tools as complementary layers;
- covers the cross-buddy artifact access issue directly;
- proposes enough tool capability to materially improve buddy output management and collaboration;
- includes response/permission feedback design, not only action names;
- includes runtime context and tool description improvements;
- includes skill and AGENTS improvements;
- preserves important boundaries around direct artifact reads and track summary surfaces;
- avoids hidden workflow routing and speculative platform engines;
- includes focused tests and end-to-end collaboration scenarios;
- is specific enough to become an implementation plan after user approval.

## First Coordinator Commands After `/clear`

Use these as the initial local context commands:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev2258
git status --short --branch
sed -n '1,260p' docs/memo/2026-05-14-track-task-artifact-tooling-upgrade-subagent-brief.md
sed -n '1,260p' docs/memo/2026-05-13-cross-buddy-artifact-access-memo.md
rg -n "TOOL_REGISTRY|HANDLERS_BY_TOOL|def .*artifact|def .*track|def .*task|def .*context|allowed_next_action|permission_boundary" scripts/env scripts/turn_runtime.py tests
```

Then spawn the sub-agents described above.

## Completion Statement Template

When the coordinator finishes the proposal-generation task, answer the user with:

```text
已在 dev2258 完成多 sub-agent 调研和方案合成，未实施代码改动。

输出文档:
- docs/memo/<proposal-file>.md

覆盖:
- tool capability roadmap
- tool descriptions/runtime context
- permission and feedback contract
- skills and AGENTS guidance
- tests and acceptance scenarios
- non-goals and risks

当前未做:
- source implementation
- main worktree changes
```

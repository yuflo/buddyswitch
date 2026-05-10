# Buddy Env Layer And Task Manager Action Plan Memo

Date: 2026-05-10
Scope: BuddySwitch buddy env layer, shared task-manager skill, and unified lower-level tool abstraction.

## Core Goal

Build BuddySwitch's buddy env layer step by step so buddies can operate task, track, artifact, context, and binding state with stronger autonomy.

The immediate feature is not just a task API. It is the first forward step toward a unified environment layer where:

- all buddy-facing capabilities enter through a consistent skill layer;
- all real state operations execute through a consistent lower-level tool layer;
- permissions, current context, state mutation, and feedback signals are enforced by runtime/tool code;
- prompts and skill instructions describe capability and workflow, but do not act as the permission source.

## Discussion Summary

### Runtime Context And Feedback

The current direction is "more context, less prompt":

- `prepare.runtime_context` is the buddy-facing source for allowed actions, payload shape, tool requirements, and current context.
- Runtime/tool rejection should return structured feedback fields such as `permission_boundary`, `allowed_next_actions`, `stop_condition`, `command_hint`, and payload hints.
- `AGENTS.md` and `SKILL.md` should stay concise. They point to runtime context and tool feedback instead of duplicating long permission or payload recipes.

This direction is already present in current docs and tests:

- `framework/docs/turn-runtime-spec.md`
- `framework/contracts/buddy-env-profile.json`
- `tools/launcher/assets/buddies/*/AGENTS.md`
- `docs/memo/2026-05-08-buddy-host-desc-feedback-consensus-memo.md`
- `tests/test_prepare_runtime_context.py`
- `tests/test_runtime_tool_feedback.py`

### Switch-Era Task Binding

Historical switch input binding was deterministic syntax and runtime state, not LLM semantic understanding:

- parser extracted `buddy`, optional `task_id`, optional `track_id`, and `demand`;
- no `task_id` meant create mode;
- persist materialized the new task and returned the generated task id for future reference.

That product UX has been removed. Current product runtime uses launcher-managed buddy instances:

- active buddy comes from instance/session metadata;
- current task comes from instance binding;
- user text is ordinary request text and does not route or switch buddy/task by itself.

Therefore the new task-manager direction should not resurrect switch syntax. It should provide explicit env operations through the standard skill/tool model.

### Current Gap

Current task-related scripts are not sufficient as product env tools:

- `scripts/env_tasks.py` is manual/debug oriented.
- It checks manifest permissions such as `task.read` or `task.update`, but it is not the product-grade active-buddy scoped tool layer.
- Listing, showing, and updating tasks need deterministic ownership checks such as `task.buddy == active_buddy` in the tool/service layer.
- Current product runtime entrypoints are partially unified under `scripts/runtime_kernel/`, but lower-level skill-facing env tools are still scattered across root scripts.

The forward path is to rebuild the tool abstraction for the product buddy env layer, starting with task manager.

## Key Consensus Points

1. There is one product goal: build a stronger buddy env layer.
2. `task-manager` must be a normal skill, same architectural level as other skills.
3. `task-manager` must not be a special broker command from the user's perspective.
4. All skills should gradually converge on a unified lower-level env tool layer.
5. Permission rules must be enforced by runtime/tool/service code, not prompt text.
6. Active buddy and instance identity must be injected by runtime/session context, not authored by the LLM.
7. Cross-buddy task management is forbidden at the tool/service layer.
8. Tool success and failure responses must carry enough structured feedback for Codex CLI to decide the next action.
9. Human manual task/track/artifact operations are not a product goal; old manual/debug scripts should not define the long-term architecture.
10. Rebuild forward instead of wrapping incompatible old paths.

## Unified Architecture Target

The target model has two consistent public layers and two internal layers:

```text
Buddy / Codex CLI
  -> unified SKILL layer
       task-manager
       track-manager
       write-prd
       implement-task
       research-scan
       ...
  -> unified env tool layer
       env.tools.task
       env.tools.track
       env.tools.artifact
       env.tools.browser_evidence
       ...
  -> env service layer
       tasks
       tracks
       artifacts
       bindings
  -> env store layer
       objects
       projections
       paths
```

Responsibilities:

- Skill layer: capability description, use cases, workflow shape, and how to interpret tool feedback.
- Tool layer: stable buddy-callable operation surface, structured success/failure payloads, runtime context injection.
- Service layer: domain rules, permission checks, active-buddy scoping, binding rules, and state transitions.
- Store layer: low-level object read/write and projections, without product semantics exposed to the LLM.

Possible repo direction:

```text
buddyswitch/skills/shared/task-manager/SKILL.md

scripts/env/
  broker.py
  client.py
  context.py
  persist.py
  tools/
    task_manager.py
    track_manager.py
    artifact_manager.py
    browser_evidence.py
  services/
    tasks.py
    tracks.py
    artifacts.py
    bindings.py
  store/
    objects.py
    projections.py
    paths.py
```

This exact tree can be adjusted during implementation, but the separation should hold.

## Task Manager Initial Capability Set

`task-manager` should be available to every buddy and scoped to the active buddy only.

Initial operations:

- `task.create`: create a task for the active buddy.
- `task.list`: list only tasks owned by the active buddy.
- `task.get`: read details only for an active-buddy-owned task.
- `task.get_current`: return current instance task binding and task summary.
- `task.set_current`: set current instance task to an active-buddy-owned task and synchronize `current_track_id`.
- `task.update`: update minimal task fields such as `title`, `summary`, and `status`.
- `task.archive`: archive a task, or implement as `task.update(status="archived")` if the tool response remains clear.

Non-goals for the first version:

- deleting tasks;
- cross-buddy task reads or mutations;
- artifact/run management inside task-manager;
- track lifecycle creation or routing inside task-manager;
- manual human task administration UI or CLI as a product path.

## Tool Feedback Requirements

Every task tool response should be machine-readable and decision-friendly.

Successful responses should include:

- `ok: true`;
- `action`;
- `active_buddy`;
- affected `task_id`;
- current binding state when relevant;
- `next_actions` or `allowed_next_actions` when useful.

Rejected responses should include:

- `ok: false`;
- `error.code`;
- `error.message`;
- `permission_boundary`;
- `active_buddy`;
- attempted `task_id` when provided;
- `allowed_next_actions`;
- optional `context_hint` or `task_filter_hint`.

Example rejection shape:

```json
{
  "ok": false,
  "error": {
    "code": "E_TASK_BUDDY_SCOPE",
    "message": "task belongs to buddy 'pm', not active buddy 'dev'"
  },
  "permission_boundary": "task.buddy_scope",
  "active_buddy": "dev",
  "task_id": "task-pm-example",
  "allowed_next_actions": [
    "Choose a task owned by the active buddy.",
    "List active-buddy tasks before setting current task.",
    "Use handoff or track context instead of cross-buddy task mutation."
  ]
}
```

## Action Plan

### Phase 1: Lock The Env Layer Shape

Outcome: one clear target structure for shared skills and lower-level env tools.

Work:

- Define where shared skills live, starting with `task-manager`.
- Define where env tools, services, and store helpers live.
- Decide how broker/client exposes tool calls without making task-manager a special-case runtime command.
- Update docs/contracts only as needed to describe the unified skill/tool layering.

Verification:

- Repo consistency tests assert that task-manager is a normal skill package.
- Runtime docs state that permissions live in env tools/services, not SKILL prompts.

### Phase 2: Build Task Manager As The First Env Tool Skill

Outcome: all buddies can use a standard `task-manager` skill that calls deterministic task env tools.

Work:

- Add shared `task-manager` skill package.
- Add task env tool operations for create/list/get/get-current/set-current/update/archive.
- Add task service functions that enforce active-buddy scope.
- Ensure current task binding writes update instance `current_task_id` and synchronize `current_track_id`.
- Return structured feedback for success and rejection cases.

Verification:

- Tests prove active buddy can create/list/get/set/update/archive its own tasks.
- Tests prove cross-buddy task reads and mutations are rejected with structured feedback.
- Tests prove setting current task updates instance binding consistently.
- Tests prove SKILL text does not contain permission recipes as the enforcement source.

### Phase 3: Reclassify Existing Debug/Manual Paths

Outcome: old scattered task scripts no longer define product behavior.

Work:

- Mark `scripts/env_tasks.py` as debug/manual wrapper or migrate it onto the new service layer.
- Keep direct store functions internal and not buddy-facing.
- Avoid preserving compatibility paths that confuse product env ownership.

Verification:

- Product tests call the env tool path, not `env_tasks.py` directly.
- Debug wrappers, if retained, are thin and clearly not the permission source.

### Phase 4: Extend The Pattern To Track, Artifact, And Evidence Tools

Outcome: task-manager becomes the model for the rest of the buddy env layer.

Work:

- Apply the same skill/tool/service/store split to track manager.
- Move artifact operations behind the same env tool/service model.
- Align browser evidence with the same tool directory/feedback conventions.
- Keep migration incremental and driven by active product paths.

Verification:

- Each tool has structured feedback tests.
- Each tool gets active-buddy or role-specific permission tests.
- Runtime context points to tool capabilities without large prompt recipes.

## Decisions To Preserve

- One goal, one action plan, phased rollout.
- Start with task-manager because current task binding is the immediate product bottleneck.
- Rebuild forward; do not make old debug/manual scripts the center of the new product architecture.
- Keep task-manager architecturally identical to other skills.
- Keep lower-level tools unified and deterministic.
- Move permission and feedback into code-level env tools/services.

## Open Design Questions For The Next Step

1. Should shared skills live under `buddyswitch/skills/shared/` or be materialized into every buddy from a separate shared registry field?
2. Should env tools be called through an existing broker method namespace, or should the broker expose a generic `tool.call` envelope?
3. Should `task.archive` be its own operation or a named wrapper over `task.update(status="archived")`?
4. How much of `scripts/turn_runtime.py` should move into `scripts/env/context.py` and `scripts/env/persist.py` during the first pass?
5. Should old `env_tasks.py/env_tracks.py/env_artifacts.py` be immediately moved, or first converted into thin wrappers over new services?

## Stop Condition For First Implementation Slice

The first slice is complete when:

- `task-manager` exists as a normal shared skill;
- task env tool operations exist behind the unified lower-level tool layer;
- cross-buddy task operations are rejected by code, not prompt;
- current task binding can be changed safely by tool call;
- structured feedback gives Codex CLI clear next actions;
- tests cover own-buddy success paths, cross-buddy rejection paths, and binding updates.

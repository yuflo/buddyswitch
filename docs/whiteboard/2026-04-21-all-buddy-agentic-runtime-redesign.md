# All-Buddy Agentic Runtime Redesign

## Status

- Date: 2026-04-22
- Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/pm-agentic-refactor`
- Scope of this pass: close the 2026-04-22 review findings and freeze one runnable all-buddy contract
- Canonical note: this is the only retained whiteboard for the 2026-04-21/22 runtime redesign pass

## 1. Core Decision

BuddySwitch should expose one repeatable skill-turn loop:

`resolve_context -> choose {skill_id, sub_task} -> execute_skill locally -> persist_skill_result -> refreshed_context`

Three rules are non-negotiable:

1. `SKILL` is the minimum public execution unit.
2. Runtime never executes skills. The host is the only skill/tool executor.
3. The host never writes canonical BuddySwitch state. Runtime is the only writer of task, track, artifact, and run state.

This replaces the old packet flow:

`resolve -> selected_skill_packet -> host run -> persist`

The redesign is only converged if the new loop is sufficient for `market`, `pm`, `design`, `dev`, and `test` without hidden exceptions.

## 2. Source Of Truth

### 2.1 Runtime is authoritative for

- `context_revision`
- resolved `task_id`
- reserved per-turn `run_id`
- materialized `skills[*]` catalog
- materialized `skill_definition`
- result validation
- canonical task/track/artifact/run writes
- refreshed context after each turn

### 2.2 Host is authoritative for

- which `skill_id` to run next
- the current `sub_task`
- local execution of the selected skill
- the raw structured `result` produced by that skill

### 2.3 Trust boundary

- The host may cache or echo context locally, but runtime does not trust host-mutated copies of `context` or `skill_definition`.
- Runtime trusts only:
  - `context_revision`
  - `run_id`
  - `task_id`
  - `buddy_id`
  - `skill_id`
  - the validated structured `result`
- One persisted skill turn produces one durable run record.
- After every successful persist, runtime returns a new `context_revision` and a new reserved `run_id` for the next turn.

## 3. Contracts That Must Be Explicit

Five contracts must be frozen:

1. `resolve_context`
2. host-local `execute_skill_request`
3. `skill_result`
4. host-to-runtime `persist_skill_result`
5. persist routing and state invariants

Without all five, the redesign still depends on hidden packet behavior.

## 4. `resolve_context`

### 4.1 Required shape

```json
{
  "context_revision": "ctx-task-pm-write-the-prd-001-turn-1",
  "switch": {
    "raw_text": "switch pm -> track-landing-page: write the PRD",
    "buddy_id": "pm",
    "demand": "write the PRD",
    "task_id": null,
    "track_id": "track-landing-page"
  },
  "buddy": {
    "id": "pm",
    "label": "PM",
    "scope": "Own product iteration and track progression."
  },
  "authority": {
    "buddy_id": "pm",
    "permissions": [
      "track.read",
      "track.create",
      "track.update",
      "track.advance",
      "task.read",
      "task.create",
      "task.update",
      "artifact.read",
      "artifact.create"
    ]
  },
  "task_resolution": {
    "mode": "create",
    "task_id": "task-pm-write-the-prd-001",
    "created_during_resolve": true
  },
  "run_envelope": {
    "run_id": "run-task-pm-write-the-prd-001-001",
    "previous_run_id": null,
    "sequence": 1,
    "status": "reserved"
  },
  "task_context": {
    "task": {
      "id": "task-pm-write-the-prd-001",
      "title": "PM write the PRD",
      "buddy": "pm",
      "track_id": "track-landing-page",
      "status": "active",
      "summary": "",
      "artifact_slots": {},
      "artifact_ids": [],
      "run_ids": [],
      "latest_run_id": null
    },
    "artifacts": [],
    "recent_runs": []
  },
  "track_context": {
    "track": {
      "id": "track-landing-page",
      "title": "Landing Page",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": null,
      "summary": "Landing page planning track."
    },
    "tasks": []
  },
  "inputs": [
    {
      "slot": "market-scan",
      "artifact_id": "art-task-market-001-market-scan",
      "summary": "Competitive evidence for landing-page positioning."
    }
  ],
  "skills": [
    {
      "id": "write-prd",
      "description": "Draft PRD and MVP scope from validated requirements.",
      "allowed_task_kinds": ["definition"],
      "produces_artifact": true,
      "output_slot": "prd",
      "input_slots": [
        "market-scan",
        "pmf-report",
        "customer-discovery",
        "positioning-brief",
        "channel-plan",
        "launch-prep",
        "requirements",
        "track"
      ],
      "output_schema": "framework/schemas/pm/write-prd.json",
      "host_execution": {},
      "tool_scope": {}
    },
    {
      "id": "track-manager",
      "description": "Manage track lifecycle mutations.",
      "allowed_task_kinds": ["track-management"],
      "produces_artifact": false,
      "input_slots": [],
      "output_schema": "framework/schemas/pm/track-manager.json",
      "host_execution": {},
      "tool_scope": {}
    }
  ],
  "warnings": []
}
```

### 4.2 Required rules

- `task_resolution.task_id` is always concrete after `resolve_context`.
- `task_resolution.mode` explains whether runtime reused an existing task or created one during resolve.
- `run_envelope.run_id` is the reserved id for the next skill turn.
- The reserved `run_id` becomes durable only when `persist_skill_result` succeeds.
- `track_context` is always present:
  - object when a track exists
  - `null` when the task is untracked
- `warnings` is always present, including inside refreshed context.
- `skills[*]` is the host-facing skill catalog for the next choice. No extra `selected_skill_packet` is required.

### 4.3 What refreshes after every successful turn

Runtime returns the same top-level shape after each successful persist, with these fields refreshed:

- `context_revision`
- `run_envelope`
  - new reserved `run_id`
  - previous `run_id` moved into `previous_run_id`
  - incremented `sequence`
- `task_context.task.summary`
- `task_context.task.artifact_ids`
- `task_context.task.artifact_slots`
- `task_context.task.run_ids`
- `task_context.task.latest_run_id`
- `task_context.task.track_id`
- `task_context.artifacts`
- `task_context.recent_runs`
- `track_context`
- `inputs`
- `skills`
- `warnings`

The host should make the next decision only from this refreshed context.

## 5. Skill-Turn Transaction

### 5.1 Host-local `execute_skill_request`

This request is for the host's local skill executor. It is not a second source of truth.

```json
{
  "context_revision": "ctx-task-pm-write-the-prd-001-turn-1",
  "run_id": "run-task-pm-write-the-prd-001-001",
  "task_id": "task-pm-write-the-prd-001",
  "buddy_id": "pm",
  "skill_id": "write-prd",
  "sub_task": {
    "goal": "Draft the landing-page PRD under the active track.",
    "kind": "definition",
    "reason": "The user explicitly asked for a PRD after market evidence already exists."
  },
  "context_snapshot": {
    "context_revision": "ctx-task-pm-write-the-prd-001-turn-1"
  },
  "skill_definition": {
    "instruction_path": "buddyswitch/skills/pm/write-prd/SKILL.md",
    "description": "Use when the task is drafting a PRD, defining MVP scope, or turning validated requirements into product requirements.",
    "objects": ["task", "artifact"],
    "produces_artifact": true,
    "output_slot": "prd",
    "input_slots": [
      "market-scan",
      "pmf-report",
      "customer-discovery",
      "positioning-brief",
      "channel-plan",
      "launch-prep",
      "requirements",
      "track"
    ],
    "output_schema": "framework/schemas/pm/write-prd.json",
    "side_effect_level": "medium",
    "allowed_task_kinds": ["definition"],
    "host_execution": {},
    "tool_scope": {}
  }
}
```

Rules:

- `skill_id` is the only public execution selector.
- `sub_task` is required and stays small:
  - `goal`
  - `kind`
  - `reason`
- `sub_task.kind` must be compatible with `skill_definition.allowed_task_kinds`.
- `skill_definition` is materialized by runtime from manifest, `skill.toml`, and runtime normalization.
- `host_execution` and `tool_scope` are first-class contract fields. They replace packet-era `execution_constraints`, `tool_scope`, and `execution_steps`.

### 5.2 Host-to-runtime `persist_skill_result`

This is the only post-execution handoff back into runtime.

```json
{
  "context_revision": "ctx-task-pm-write-the-prd-001-turn-1",
  "run_id": "run-task-pm-write-the-prd-001-001",
  "task_id": "task-pm-write-the-prd-001",
  "buddy_id": "pm",
  "skill_id": "write-prd",
  "result": {
    "execution_summary": "Drafted the landing-page PRD from the active market evidence.",
    "working_notes": [
      "Used market-scan as the primary source.",
      "Kept scope at MVP landing-page definition."
    ],
    "deliverables_or_changed_files": [],
    "artifact_content": {
      "problem": "Teams struggle to trust generic AI support tools because setup and proof of value are unclear.",
      "goals": ["Explain value fast", "Drive qualified CTA conversion"],
      "non_goals": ["Full pricing system redesign"],
      "users_and_scenarios": ["Ops lead evaluating support automation for SMB SaaS"],
      "scope_p0_p1": {
        "p0": ["Hero value proposition", "Social proof", "Primary CTA"],
        "p1": ["Expanded comparison section"]
      },
      "acceptance_criteria": ["Page communicates target user and core value in the first fold"],
      "risks": ["Evidence is still thin for enterprise buyers"],
      "open_questions": ["Do we need region-specific trust proof?"]
    }
  }
}
```

Rules:

- Runtime validates `context_revision`, `run_id`, `task_id`, `buddy_id`, `skill_id`, and the skill schema before any business write.
- Runtime does not trust host-echoed `context_snapshot` or `skill_definition` for persistence.
- On success:
  - the reserved `run_id` becomes the durable run for that turn
  - runtime applies canonical business writes
  - runtime returns refreshed context with a new `context_revision` and new reserved `run_id`
- On validation failure:
  - runtime does not mutate task, track, or artifact state
  - runtime may write failure audit metadata for the attempted run
  - the host must continue from a freshly returned or freshly resolved context

## 6. Structured Result Contract

### 6.1 Shared envelope

Every skill result carries:

- `execution_summary`
- `working_notes`
- `deliverables_or_changed_files`

Default persistence rule:

- `execution_summary` may affect canonical state.
- `working_notes` and `deliverables_or_changed_files` are audit-only by default.
- If a skill wants durable content beyond `execution_summary`, that content must live under the skill-specific payload such as `artifact_content` or `track_operation`.

### 6.2 Artifact-producing skills

Artifact-producing skills use the existing result shape:

```json
{
  "execution_summary": "Drafted the landing-page PRD from the active market evidence.",
  "working_notes": [
    "Used market-scan as the primary source.",
    "Kept scope at MVP landing-page definition."
  ],
  "deliverables_or_changed_files": [],
  "artifact_content": {
    "problem": "Teams struggle to trust generic AI support tools because setup and proof of value are unclear.",
    "goals": ["Explain value fast", "Drive qualified CTA conversion"],
    "non_goals": ["Full pricing system redesign"],
    "users_and_scenarios": ["Ops lead evaluating support automation for SMB SaaS"],
    "scope_p0_p1": {
      "p0": ["Hero value proposition", "Social proof", "Primary CTA"],
      "p1": ["Expanded comparison section"]
    },
    "acceptance_criteria": ["Page communicates target user and core value in the first fold"],
    "risks": ["Evidence is still thin for enterprise buyers"],
    "open_questions": ["Do we need region-specific trust proof?"]
  }
}
```

### 6.3 `track-manager`

`track-manager` is mutation-only inside the online loop.

```json
{
  "execution_summary": "Created a track for the landing-page PRD work.",
  "working_notes": ["Set PM as current owner and kept status active."],
  "deliverables_or_changed_files": [],
  "track_operation": {
    "action": "create",
    "track_id": "track-landing-page",
    "title": "Landing Page",
    "status": "active",
    "current_buddy": "pm",
    "next_buddy": null,
    "summary": "Track for landing-page definition and downstream handoff."
  }
}
```

Rules:

- Allowed online actions are:
  - `create`
  - `update`
  - `advance`
  - `archive`
- `track.read` and `track.list` are not part of the online skill-turn loop.
- Query-style track inspection belongs in `resolve_context`, debug/manual APIs, or a fresh resolve pass.

### 6.4 `design` v1 concrete skill

`design` cannot remain an abstract promise. The minimum concrete v1 skill is:

- `skill_id`: `shape-prototype`
- `output_slot`: `design-handoff`
- `output_schema`: `framework/schemas/design/shape-prototype.json`
- `allowed_task_kinds`: `["design"]`
- `input_slots`:
  - `market-scan`
  - `prd`
  - `requirements`
  - `track`
  - `prior-design-handoff`

Minimum result shape:

```json
{
  "execution_summary": "Shaped the landing-page prototype and packaged the handoff.",
  "working_notes": [
    "Kept the prototype at page-map plus key pages.",
    "Focused the first pass on information architecture and CTA flow."
  ],
  "deliverables_or_changed_files": [
    ".sandbox/design/task-design-landing-page/index.html",
    ".sandbox/design/task-design-landing-page/routes.json"
  ],
  "artifact_content": {
    "prototype_kind": "page-map-plus-key-pages",
    "page_map": ["home", "pricing", "demo-request", "confirmation"],
    "primary_user_flow": ["home -> demo-request -> confirmation"],
    "preview": {
      "sandbox_root": ".sandbox/design/task-design-landing-page",
      "entry_file": "index.html"
    },
    "handoff": {
      "pm": ["Keep the first CTA above the fold."],
      "dev": ["Implement hero, proof strip, and CTA flow first."],
      "test": ["Verify the primary CTA path and top-level navigation labels."]
    },
    "open_questions": ["Do enterprise visitors need a separate trust section?"]
  }
}
```

Rules:

- The sandbox preview is execution-time filesystem state, not canonical BuddySwitch state.
- Only preview references and handoff conclusions belong in `artifact_content`.
- `deliverables_or_changed_files` records sandbox outputs for audit and operator visibility; it does not replace the durable artifact.

## 7. Persist Routing And State Invariants

### 7.1 Artifact-producing turn

Routing:

`artifact result + runtime envelope + skill metadata -> task.update + artifact.create + task.add_run + run.audit_write`

Required mapping:

- `result.execution_summary`
  - drives `artifact.summary`
  - drives `task.summary`
  - is copied into run audit
- `result.artifact_content`
  - drives `artifact.content`
- `skill_id`
  - drives `artifact.skill_id`
- `skill_definition.output_slot`
  - drives `artifact.slot`
  - drives `task.artifact_slots[slot]`
- `run_id`
  - drives `artifact.source_run_id`

### 7.2 Track-management turn

Routing:

`track-manager result + runtime envelope -> track mutation + optional task.bind_track + task.add_run + run.audit_write`

Required mapping:

- `track_operation.action`
  - selects `track.create`, `track.update`, `track.advance`, or `track.archive`
- `execution_summary`
  - drives `task.summary`
  - is copied into run audit
- Track creation with an active task binds that task to the created track inside the same persisted turn.

### 7.3 Audit-only fields

By default:

- `working_notes` -> `run.audit_write` only
- `deliverables_or_changed_files` -> `run.audit_write` only

These fields do not silently mutate task, track, or artifact state.

### 7.4 Canonical runtime operations

The runtime only needs this small business write set:

- `task.ensure_for_run`
- `task.update`
- `task.bind_track`
- `task.add_run`
- `artifact.create`
- `track.create`
- `track.update`
- `track.advance`
- `track.archive`
- `run.audit_write`

`track.read` and `track.list` are read concerns, not online-loop persist operations.

### 7.5 Hard invariants

These invariants must be explicit in the runtime contract and tests:

1. `task.track_id` and `track.task_ids` change together.
2. Artifact lineage is mandatory:
   - `artifact.slot`
   - `artifact.revision`
   - `artifact.supersedes_artifact_id`
   - `artifact.is_current`
   - `artifact.source_run_id`
3. Only one current artifact may exist per `task_id + slot`.
4. `task.artifact_slots[slot].current_artifact_id` must point at the current artifact for that slot.
5. `task.artifact_slots[slot].revision_count` must match the highest revision seen for that slot.
6. `task.run_ids` and `task.latest_run_id` must update on every successful persisted turn.
7. `track_context`, `inputs`, and `recent_runs` are always re-derived from canonical state after persist, never from host echo.

## 8. All-Buddy Coverage

### 8.1 Market

The browser-native contract must survive the packet deletion.

For every market skill, runtime must materialize `host_execution` from existing `skill.toml` fields:

```json
{
  "execution_mode": "browser-cockpit-native",
  "browser_mode": "headed-only",
  "browser_profile": "shared-browser",
  "browser_executor": "chrome-devtools-cockpit",
  "discovery_mode": "browser-native",
  "login_policy": "mandatory-takeover",
  "fallback_policy": "no-silent-degrade",
  "session_continuity": "shared-cockpit",
  "required_tools": ["chrome-devtools-cockpit"]
}
```

And runtime must normalize `tool_scope` from `tool_scope_profile = "market-browser-native"`.

Cutover rule:

- Do not delete `selected_skill_packet` until these same constraints are exposed under:
  - `resolve_context.skills[*].host_execution`
  - `resolve_context.skills[*].tool_scope`
  - `execute_skill_request.skill_definition.host_execution`
  - `execute_skill_request.skill_definition.tool_scope`

### 8.2 PM

`pm` remains the clearest proof that skill is the right execution unit:

- `track-manager` owns track mutations
- `write-prd` owns PRD artifact generation

### 8.3 Design

`design` stays inside the all-buddy cutover.

That means the same branch must do all of the following:

1. add the concrete `shape-prototype` skill contract
2. add `framework/schemas/design/shape-prototype.json`
3. register the skill in `buddyswitch/manifest.toml`
4. remove the zero-skill rejection in runtime and tests

`design` is not allowed to remain a hidden exception to the skill-only runtime.

### 8.4 Dev

`dev` already fits:

- `implement-task` is the public execution unit
- output is an implementation artifact plus run audit

### 8.5 Test

`test` already fits:

- `smoke-test` is the public execution unit
- output is a durable test artifact plus run audit

## 9. What Must Be Deleted

Delete the old public packet ABI instead of wrapping it:

- `prepare-execution`
- `selected_skill_packet`
- `implicit_skill_id`
- packet-era public docs that tell the host to follow injected ordered execution steps
- packet-era tests that freeze the packet flow
- `track-manager` query actions as part of the online skill-turn contract

## 10. Implementation Order

The safe implementation order is:

1. expose normalized `host_execution` and `tool_scope` from existing skill metadata, especially for `market`
2. add `context_revision`, concrete `task_resolution.task_id`, reserved per-turn `run_envelope`, and stable `track_context`/`warnings`
3. introduce `persist_skill_result` as the only post-execution runtime handoff
4. make runtime persistence trust only `context_revision + run_id + task_id + buddy_id + skill_id + result`
5. narrow `track-manager` to mutation-only online actions and move `read/list` out of the skill-turn loop
6. freeze task/track/artifact invariants in runtime tests
7. land the concrete `design` skill, schema, manifest registration, and zero-skill rejection removal in the same branch
8. only then delete packet-era docs, tests, and runtime affordances

Two cutover guards matter:

- do not remove market browser-native packet behavior before the equivalent `host_execution`/`tool_scope` contract is live
- do not declare all-buddy cutover before `design` has a concrete skill contract

## 11. Convergence Test

This whiteboard is only converged if all five checks are true:

1. The host can run one skill turn from `resolve_context` without hidden packet fields.
2. Runtime can persist a result without trusting host-echoed context or skill metadata.
3. Every buddy has either a live concrete skill contract or an explicit same-branch closure, with `design` included.
4. Task, track, artifact, and run invariants are explicit enough to encode in tests.
5. Refreshed context returns a new `context_revision` and new reserved `run_id` for the next turn.

## 12. One-Sentence End State

BuddySwitch should let the host choose one skill from explicit context, execute that skill locally under an explicit host contract, hand back one validated structured result, let runtime apply the only canonical writes, and then continue from refreshed context across `market`, `pm`, `design`, `dev`, and `test` without hidden exceptions.

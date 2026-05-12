> Superseded on 2026-05-12 by the env tool layer rebuild residue removal work. This file is historical context, not active implementation guidance.

# Host Decision Surface Env Upgrade Plan

> **For agentic workers:** This is a product and architecture upgrade plan, not an implementation diff. Before implementing any phase, use `superpowers:subagent-driven-development` or `superpowers:executing-plans`; use `superpowers:test-driven-development` for behavior changes; use `superpowers:verification-before-completion` before claiming a phase is done.

**Goal:** Upgrade BuddySwitch's env layer so a competent Codex CLI host can infer relevant context, safe operations, and next product actions from runtime state and env feedback, without handoff inboxes, automatic routing, fixed workflow rules, or prompt-level process recipes.

**Architecture:** Keep BuddySwitch as an environment and coordination layer. Add explicit host-facing decision semantics to existing runtime context, env tool contracts, track/context/handoff discovery responses, and verification tests while preserving host autonomy and runtime-enforced boundaries.

**Tech Stack:** Python stdlib, existing `scripts/turn_runtime.py`, broker-routed `env.tool`, services under `scripts/env/services/`, runtime object store via `scripts/env_store.py`, launcher instance JSON, pytest/unittest, product-mode CLI smoke checks.

---

## Working Directory

Run all work from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev2258
```

Do not edit the main checkout at:

```bash
/Users/chen/Dev/buddyswitch
```

Current branch and baseline when this plan was created:

- Main checkout: `main`, clean, at `d238d92 Merge dev0210 work`.
- Plan worktree: `dev2258`, clean before this document was written.
- Focused baseline command already passed before planning:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Observed baseline:

```text
29 passed, 83 subtests passed
```

## Source Inputs

Primary memo:

- `docs/memo/2026-05-11-host-autonomy-context-handoff-memo.md`

Relevant prior env plans:

- `docs/spec/2026-05-10-buddy-env-layer-task-manager-development-plan.md`
- `docs/spec/2026-05-10-buddy-env-layer-task-manager-test-plan.md`
- `docs/spec/2026-05-10-buddy-env-layer-phase-1-n-development-plan.md`
- `docs/spec/2026-05-10-buddy-env-layer-phase-1-n-test-plan.md`

Four read-only architecture reviews were incorporated:

- Runtime context and prepare decision surface.
- Env tool contract duplication and registry design.
- Product object model and handoff discovery semantics.
- Semantic verification strategy.

## Core Product Thesis

The current env layer has the right foundation: broker-routed tools, runtime-owned state, structured responses, active-buddy boundaries, track/task/artifact objects, run audits, handoff validation, evidence gates, and prepare context.

The current bottleneck is different:

**BuddySwitch exposes many fields, but not enough decision semantics.**

A host can often see that tools and context exist, but it must guess:

- whether it is bound to a task or track;
- whether a track is addressed to the active buddy;
- whether a handoff is discoverable through track context;
- whether `handoff.validate` is outgoing validation or incoming discovery;
- whether an operation is read-only, validation-only, binding mutation, durable state mutation, evidence issuance, or run commit;
- whether missing context means "inspect readable tracks", "create own task", "ask PM", "issue browser evidence", or "rerun prepare";
- whether a response's `allowed_next_actions` are just prose or a structured recovery surface.

The upgrade should make these meanings explicit in the environment.

## Non-Goals

Do not add these as the first-class solution:

- handoff inbox;
- automatic handoff routing;
- natural-language-to-track auto-binding;
- Market-specific handoff router;
- rule that always calls `track.list` before Market work;
- hardcoded onboarding rewrite logic;
- hardcoded next-buddy matching policy;
- workflow engine;
- event bus;
- generic process DSL;
- large new permission framework;
- long AGENTS or skill prompt recipes that teach hosts internal procedures.

These would move BuddySwitch toward orchestration. The current goal is stronger environmental semantics so the host can choose.

## Forward-Only Cleanup Rule

This plan follows SHARP forward development. Do not keep old code paths, compatibility branches, duplicated contract maps, or test-only mirrors after a replacement lands.

Each implementation phase must include cleanup work in the same change set:

- Replace hand-maintained contract maps instead of stacking generated data beside them.
- Delete duplicated router and manager action allowlists once the registry owns those names.
- Delete duplicated unknown-action validation once one layer owns that boundary.
- Replace string-only context source descriptors; do not keep a parallel legacy descriptor API.
- Replace shallow field-existence tests with semantic tests instead of keeping both.
- Remove response-field mirrors that exist only for older tests; update the tests to the new canonical response shape.
- Remove old naming and docs that imply compatibility, migration comfort, or alternate active paths.
- Add residue checks for retired active surfaces when deletion is part of the phase.

Allowed temporary state:

- A single commit may contain failing tests plus production changes while the developer is iterating locally.
- A phase may expose an old field name only when it remains the canonical active product contract, generated from the new source of truth, and no duplicate handwritten source remains.

Disallowed temporary state:

- long-lived dual paths;
- compatibility wrappers;
- old and new response contracts both treated as active;
- tests that pass by accepting either old or new behavior;
- docs that tell hosts to rely on old tool lists, old payload hints, or raw-state paths.

## Target Acceptance Scenario

Product prompt stays goal-oriented:

```text
Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design. Follow runtime feedback when browser evidence is needed.
```

Expected host behavior after the upgrade:

1. Read the prepared runtime context first.
2. If current track context includes a PM handoff to Market, use it.
3. If no current track is bound, infer from runtime context and env tool descriptions that readable tracks are candidate collaboration context.
4. Inspect candidate tracks using `track.list`, `track.get`, or `context.summarize` without direct raw-state reads.
5. Recognize `track.next_buddy == market` and recent run-audit handoff to Market as relevance signals.
6. Create or bind Market-owned task work only after identifying the collaboration context.
7. Issue browser evidence when Market artifact-producing work requires it.
8. Produce a Market-owned `market-scan` artifact.
9. Validate and persist a handoff to Design.

This is not a scripted flow. It is the expected result of a sufficiently expressive environment.

## Current Architecture Findings

### Runtime Context

Relevant code:

- `scripts/turn_runtime.py:_build_env_tools_desc`
- `scripts/turn_runtime.py:_build_runtime_context`
- `scripts/turn_runtime.py:_build_prepare_turn_context`
- `scripts/env/services/context.py:context_sources_desc`
- `scripts/env/services/context.py:summarize_current_context`

Current strengths:

- `runtime_context.env_tools` lists active env tools, commands, operations, payload fields, envelope shape, and feedback source.
- `runtime_context.capability_boundary` exposes artifact kinds, state effects, handoff targets, project access, scratch root, and raw-state broker boundary.
- `runtime_context.context_sources_desc` lists the major context sections.
- `runtime_context.current_context_summary` gives compact task, track, artifact, and recent handoff summaries.

Current gaps:

- `env_tools` is operation-shaped, not decision-shaped.
- `context_sources_desc` is a string dictionary, not a structured source descriptor.
- `current_context_summary` does not state binding status, active-buddy relation to task/track, missing context reasons, or handoff relevance.
- Fresh/unbound Market gets a new Market task, but existing PM handoff context is invisible unless track context is already bound or discoverable through another tool call.
- `allowed_next_actions` are human-readable strings and are only shallowly tested.

### Env Tool Contracts

Relevant code:

- `scripts/turn_runtime.py:_build_env_tools_desc`
- `scripts/env/tools/router.py`
- `scripts/env/client.py`
- `scripts/env/tools/*_manager.py`
- `scripts/env/services/*.py`

Current duplication:

- Prepare env tool descriptions hand-maintain tools, operations, payload fields, and manager names.
- Router repeats supported tools and actions.
- CLI repeats resources, operations, payload loading rules, and hyphen-to-underscore mapping.
- Manager modules repeat `_ACTION_MAP`, supported-action text, payload rejection shape, and action normalization.
- Services own the real semantic contract: allowed fields, required fields, boundaries, response shape, and state-dependent feedback.

Current gap:

The contract is not single-source enough to prevent drift, and it still does not expose operation semantics such as mutability, authority source, preconditions, and return fields.

### Object Model And Discovery

Runtime state is projected under the launcher/runtime state root, not necessarily the source checkout:

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/content/runs/*.json`

Core relationships:

- Tracks are global coordination objects with `current_buddy`, `next_buddy`, `task_ids`, and summary.
- Tasks are buddy-owned work units and may link to one track.
- Artifacts are task-owned revisions and do not point directly to tracks.
- Run audits are durable execution records.
- Handoffs are not standalone objects; they live inside run audits.
- Recent handoffs are discovered by scanning committed run audits for the current track.
- Bindings are active launcher instance cursors: `current_task_id` and `current_track_id`.

Current gaps:

- `track.list` returns shallow track fields but not why a track is relevant to the active buddy.
- `track.get` returns track summary but not the rich track context already buildable by `context.build_track_context`.
- `context.summarize` only summarizes current binding; unbound hosts get no candidate collaboration context.
- `handoff.validate` validates outgoing handoff payloads but does not explain discoverability after commit or alignment with track transition in structured fields.
- Non-PM buddies cannot `binding.set_track`, so fresh Market needs discovery semantics that do not suggest forbidden arbitrary track binding.

### Verification

Relevant tests:

- `tests/test_prepare_runtime_context.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_track_manager_env_tool.py`
- `tests/test_artifact_manager_env_tool.py`
- `tests/test_market_browser_evidence.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_runtime_tool_feedback.py`

Current strengths:

- Good coverage for shape, permissions, identity, state safety, stale context, browser evidence, run commit, and end-to-end product loops.

Current gap:

Many assertions prove fields exist and are non-empty. They do not prove the host receives enough decision semantics to infer what to inspect or mutate next.

## Target Model

The upgraded host-facing decision surface should have four layers.

### Layer 1: Structured Context Source Descriptors

Replace `context_sources_desc` from string-only descriptions with structured descriptors.

Keep a readable `description` field inside each descriptor because it is part of the new canonical contract, not a backward-compatibility branch.

Target shape:

```json
{
  "task_context.task": {
    "description": "Current task metadata and summary.",
    "content": "summary",
    "scope": "active_instance_current_task",
    "nullable": true,
    "source_of_truth": "buddyswitch/objects/tasks/<task_id>.json via broker",
    "decision_use": ["current_work_identity", "active_buddy_task_ownership"]
  },
  "task_context.artifacts": {
    "description": "Full prior artifact content for the current task when available.",
    "content": "full",
    "scope": "current_task",
    "max_items": 5,
    "sorted_by": "updated_at desc, id desc",
    "summary_projection": "runtime_context.current_context_summary.artifacts",
    "decision_use": ["read_prior_outputs", "avoid_recreating_known_context"]
  },
  "track_context.track": {
    "description": "Current track title, status, buddy progression, and summary when bound.",
    "content": "summary",
    "scope": "current_track",
    "nullable": true,
    "decision_use": ["collaboration_thread", "current_buddy", "next_buddy"]
  },
  "track_context.recent_handoffs": {
    "description": "Recent committed handoffs discovered from run audits on the current track.",
    "content": "summary",
    "scope": "current_track_run_audits",
    "nullable": false,
    "max_items": 5,
    "decision_use": ["handoff_continuation", "handoff_target", "handoff_context"]
  },
  "current_context_summary": {
    "description": "Compact scan-friendly summary of current task, track, artifacts, and handoffs.",
    "content": "summary",
    "scope": "prepared_turn",
    "decision_use": ["first_pass_orientation"]
  }
}
```

Important distinction:

- Full artifact content remains in `task_context.artifacts`.
- Compact artifact summaries remain in `current_context_summary.artifacts`.
- Track-level discovery may include artifact summaries, not full foreign artifact content.

### Layer 2: Runtime Decision Surface

Add `runtime_context.decision_surface`, built from current binding, task context, track context, active buddy, capabilities, and tool requirements.

It should be descriptive and source-referenced. It must not select a workflow or route automatically.

Target shape:

```json
{
  "binding_state": {
    "state": "bound_task_and_track",
    "current_task_id": "task-market-example",
    "current_track_id": "track-onboarding-rewrite",
    "source": "active_instance_binding"
  },
  "active_buddy_relation": {
    "task_role": "owner",
    "track_role": "next_buddy",
    "latest_handoff_to_active_buddy": true,
    "source_refs": [
      "track_context.track.next_buddy",
      "track_context.recent_handoffs[0]"
    ]
  },
  "context_readiness": {
    "has_current_task": true,
    "has_current_track": true,
    "has_track_handoffs": true,
    "has_full_current_task_artifacts": true,
    "primary_artifact_kinds_present": ["prd"],
    "recent_handoff_count": 1
  },
  "evidence_readiness": {
    "browser_cockpit": "required",
    "market_research_evidence": "required",
    "issued_for_current_run": false,
    "source_refs": [
      "runtime_context.tool_requirements",
      "runtime_context.persist_payload_hint.tool_evidence"
    ]
  },
  "safe_read_affordances": [
    {
      "id": "read_current_context_summary",
      "tool": "context",
      "action": "summarize",
      "mutates": "none",
      "preconditions": [],
      "source_refs": ["runtime_context.env_tools.context_manager"]
    },
    {
      "id": "inspect_readable_tracks",
      "tool": "track",
      "action": "list",
      "mutates": "none",
      "preconditions": ["track.read"],
      "source_refs": ["runtime_context.env_tools.track_manager"]
    }
  ]
}
```

Allowed values should be stable and tested:

- `binding_state.state`: `unbound`, `bound_task_only`, `bound_track_only`, `bound_task_and_track`, `stale_binding`.
- `task_role`: `owner`, `foreign`, `none`, `missing`.
- `track_role`: `current_buddy`, `next_buddy`, `participant`, `observer`, `none`, `missing`.
- `mutates`: `none`, `instance_binding`, `runtime_objects`, `run_commit`, `broker_token`.

Fresh/unbound Market target example:

```json
{
  "binding_state": {
    "state": "bound_task_only",
    "current_task_id": "task-market-generated",
    "current_track_id": null,
    "source": "active_instance_binding"
  },
  "active_buddy_relation": {
    "task_role": "owner",
    "track_role": "none",
    "latest_handoff_to_active_buddy": false,
    "source_refs": []
  },
  "context_readiness": {
    "has_current_task": true,
    "has_current_track": false,
    "has_track_handoffs": false,
    "recent_handoff_count": 0
  },
  "safe_read_affordances": [
    {
      "id": "inspect_candidate_tracks",
      "tool": "track",
      "action": "list",
      "mutates": "none",
      "preconditions": ["track.read"]
    }
  ]
}
```

This tells the host what is missing and where a read-only discovery path exists. It does not force the host to call `track.list`.

### Layer 3: Env Tool Operation Semantics

Upgrade `runtime_context.env_tools` so every action has static semantics in addition to the existing command and payload hints.

Target extension:

```json
{
  "track_manager": {
    "tool": "track",
    "operations": ["list", "get", "get_current", "..."],
    "payload_fields": {
      "list": [],
      "get": ["track_id"]
    },
    "operation_semantics": {
      "list": {
        "kind": "read",
        "mutates": "none",
        "required_permission": "track.read",
        "authority": "active_buddy_manifest_permission",
        "requires": [],
        "returns": ["tracks", "discovery_summary", "allowed_next_actions"]
      },
      "attach_task": {
        "kind": "mutate_durable_state",
        "mutates": "runtime_objects",
        "required_permission": "track.update",
        "authority": "active_buddy_owned_task_linkage",
        "requires": ["track_id", "task_id", "active_buddy_owns_task"],
        "returns": ["track", "task", "current_binding", "allowed_next_actions"]
      }
    }
  }
}
```

Action kinds:

- `read`
- `validate`
- `mutate_binding`
- `mutate_durable_state`
- `commit`
- `issue_evidence`

Authority values:

- `active_buddy_manifest_permission`
- `active_buddy_owned_task`
- `active_buddy_current_task`
- `pm_track_lifecycle`
- `broker_issued_context`
- `broker_issued_evidence`
- `runtime_active_instance`

This is a static contract. It must not encode dynamic workflow policy.

### Layer 4: Discovery Responses

Upgrade read and validation tool responses that are directly relevant to host decisions.

#### `track.list`

Target additions:

```json
{
  "tracks": [
    {
      "id": "track-onboarding",
      "title": "Onboarding Rewrite",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "market",
      "task_ids": ["task-pm-onboarding"],
      "summary": "Rewrite onboarding for activation.",
      "updated_at": "2026-05-11T10:00:00+08:00",
      "discovery": {
        "active_buddy_role": "next_buddy",
        "relevance_reasons": [
          "track.next_buddy == active_buddy",
          "recent_handoff.next_buddy == active_buddy"
        ],
        "task_count": 1,
        "buddies_with_tasks": ["pm"],
        "current_artifact_kinds": ["prd"],
        "latest_handoff_to_active_buddy": {
          "run_id": "run-pm-onboarding-r1",
          "from_buddy": "pm",
          "task_id": "task-pm-onboarding",
          "reason": "Market should validate onboarding positioning.",
          "context": "Use PRD and compare onboarding examples.",
          "timestamp": "2026-05-11T10:02:00+08:00"
        },
        "latest_run_at": "2026-05-11T10:02:00+08:00",
        "has_context_available": true
      }
    }
  ],
  "discovery_summary": {
    "active_buddy": "market",
    "candidate_track_count": 1,
    "candidate_track_ids": ["track-onboarding"],
    "basis": [
      "track.next_buddy",
      "recent_handoff.next_buddy",
      "active_buddy_task_participation"
    ]
  }
}
```

Sorting:

1. tracks with recent handoff to active buddy;
2. tracks where `next_buddy == active_buddy`;
3. tracks where active buddy has a task on the track;
4. latest handoff timestamp;
5. track `updated_at`;
6. track id.

Caps:

- Default `track.list` can keep all existing tracks if the count is small.
- Add a tested cap only if runtime context becomes too large; when capped, include `truncated_count`.

#### `track.get`

Target additions:

```json
{
  "track_context_summary": {
    "track": {
      "id": "track-onboarding",
      "title": "Onboarding Rewrite",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "market",
      "summary": "Rewrite onboarding for activation."
    },
    "active_buddy_relevance": {
      "role": "next_buddy",
      "relevance_reasons": ["track.next_buddy == active_buddy"]
    },
    "tasks": [
      {
        "task_id": "task-pm-onboarding",
        "buddy": "pm",
        "status": "done",
        "summary": "PM wrote PRD.",
        "current_artifacts": [
          {
            "id": "art-task-pm-onboarding-prd",
            "kind": "prd",
            "title": "Onboarding Rewrite PRD",
            "summary": "Activation-focused onboarding rewrite."
          }
        ]
      }
    ],
    "recent_handoffs": [
      {
        "run_id": "run-pm-onboarding-r1",
        "buddy_id": "pm",
        "next_buddy": "market",
        "reason": "Market should validate positioning.",
        "context": "Use PM PRD and compare onboarding examples."
      }
    ]
  }
}
```

Do not include full artifact content in this summary. Full content remains available through prepared current task context or explicit allowed artifact/context reads.

#### `context.summarize`

When bound:

- Continue returning `current_binding` and `current_context_summary`.
- Add `decision_surface`.
- Add `candidate_tracks` only when useful, such as no bound track or no recent handoff to active buddy.

When unbound or task-only bound:

```json
{
  "current_context_summary": {
    "task": null,
    "track": null,
    "artifacts": [],
    "recent_handoffs": []
  },
  "candidate_tracks": [
    {
      "id": "track-onboarding",
      "title": "Onboarding Rewrite",
      "discovery": {
        "active_buddy_role": "next_buddy",
        "latest_handoff_to_active_buddy": {
          "run_id": "run-pm-onboarding-r1",
          "reason": "Market should validate positioning.",
          "context": "Use PM PRD and compare onboarding examples."
        }
      }
    }
  ],
  "allowed_next_actions": [
    "Use track.get with a candidate track_id to inspect compact track context.",
    "Create or bind an active-buddy task only after choosing the relevant collaboration context."
  ]
}
```

This does not mutate binding and does not auto-select a track.

#### `handoff.validate`

Success target additions:

```json
{
  "track_alignment": {
    "track_id_source": "args",
    "track_current_buddy": "pm",
    "track_next_buddy": "market",
    "target_matches_track_next_buddy": true
  },
  "discoverability": {
    "will_be_discoverable_by_next_buddy": true,
    "discovery_basis": "persisted_run_audit_handoff",
    "available_after": "run.commit",
    "discovery_surfaces": ["track.list", "track.get", "context.summarize"]
  }
}
```

Conflict target additions:

```json
{
  "permission_boundary": "handoff.track_transition",
  "track_alignment": {
    "track_id_source": "args",
    "track_current_buddy": "pm",
    "track_next_buddy": "market",
    "requested_next_buddy": "design",
    "target_matches_track_next_buddy": false,
    "suggested_next_buddy": "market"
  }
}
```

This makes outgoing validation semantics explicit and helps prevent hosts from misusing it as incoming discovery.

## Contract Registry Plan

Create a small static contract registry:

```text
scripts/env/tools/contracts.py
```

It should own names, action metadata, schemas, manager names, CLI operation mapping, and static operation semantics.

It must not own dynamic workflow decisions or state-dependent feedback.

Suggested structures:

```python
@dataclass(frozen=True)
class PayloadSchema:
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    internal_accepted: tuple[str, ...] = ()
    field_types: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionSpec:
    action: str
    cli_operation: str
    payload: PayloadSchema
    kind: str
    mutates: str
    required_permission: str | None
    authority: str
    requires: tuple[str, ...]
    returns: tuple[str, ...]


@dataclass(frozen=True)
class ToolSpec:
    tool: str
    manager_name: str
    cli_resource: str
    command: str
    scope: str
    dispatcher: Callable[..., dict[str, Any]]
    actions: tuple[ActionSpec, ...]
```

Registry-derived surfaces:

- `turn_runtime._build_env_tools_desc()`
- `scripts/env/tools/router.py` supported tool/action maps
- manager handler maps or manager action validation
- CLI operation/action consistency tests
- env tool contract tests
- generated payload schema views for the active host contract
- richer `operation_semantics`

Keep service-owned surfaces:

- state-dependent validation;
- ownership checks;
- mutation behavior;
- current `allowed_next_actions`;
- rejection-specific boundaries;
- evidence token validation;
- run commit atomicity.

## Shared Response Helpers

Add lightweight helpers only after tests characterize current response shape:

```text
scripts/env/tools/responses.py
```

Purpose:

- standard success envelope;
- standard rejection envelope;
- standard runtime feedback projection;
- standard `permission_boundary`, `allowed_next_actions`, `command_hint`, and `stop_condition` placement.

Do not create a compatibility wrapper. Replace repeated boilerplate directly as domains migrate.

Policy:

- `permission_boundary`, `allowed_next_actions`, `command_hint`, and `stop_condition` remain authoritative top-level fields.
- `error.code` and `error.message` remain inside `error`.
- Do not keep mirrored response fields only to satisfy existing tests. Update tests to the canonical response shape and delete obsolete mirrors in the same phase.

## Implementation Phases

### Phase 0: Semantic Audit And Characterization Tests

Goal:

Lock current behavior and define failing tests for decision semantics before changing production code.

Files:

- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_track_manager_env_tool.py`
- Modify `tests/test_artifact_manager_env_tool.py`
- Modify `tests/test_market_browser_evidence.py`

Tests to add:

- Fresh Market prepare exposes binding state and no-track context absence.
- Bound Market prepare exposes PM PRD summary, PM handoff, track next buddy, and Market evidence requirement.
- `context.summarize` for unbound Market returns candidate track discovery information.
- `track.list` for unbound Market marks PM track as relevant when `next_buddy == market` or recent handoff targets Market.
- `handoff.validate` returns track alignment and discoverability semantics.
- Rejections include actionable recovery semantics, not just non-empty `allowed_next_actions`.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_track_manager_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_market_browser_evidence.py \
  -q
```

Expected before implementation:

- New semantic tests fail.
- Existing safety tests remain green when run without the new expectations.

### Phase 1: Structured Context Source Descriptors

Goal:

Make context sources machine-readable enough for a host to know what is full content, what is summary, what is nullable, and what decision each source supports.

Files:

- Modify `scripts/env/services/context.py`
- Modify `scripts/turn_runtime.py` only if call sites need adaptation
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`

Implementation:

- Change `context_sources_desc()` to return structured descriptors.
- Preserve a readable `description` field for every source.
- Update prepare and `context.list_sources` tests.
- Ensure compact summaries still do not leak full artifact content.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py::PrepareRuntimeContextTests::test_prepare_exposes_context_sources_for_product_work \
  tests/test_context_binding_env_tool.py \
  -q
```

Acceptance:

- Source descriptors include `content`, `scope`, `nullable`, and `decision_use`.
- Tests assert semantic fields, not only string non-emptiness.

### Phase 2: Runtime Decision Surface Builder

Goal:

Add `runtime_context.decision_surface` and expose the same surface through `context.summarize` / `context.get`.

Files:

- Modify `scripts/env/services/context.py`
- Modify `scripts/turn_runtime.py`
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_context_binding_env_tool.py`

Implementation:

- Add `build_decision_surface(...)`.
- Reuse it in `_build_runtime_context` and `current_context_sections`.
- Include binding state, active-buddy relation, context readiness, evidence readiness, and safe read affordances.
- Use source refs instead of hidden routing rules.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  -q
```

Acceptance:

- Fresh Market exposes missing track/handoff context and safe read affordances.
- Bound Market exposes handoff relevance to active buddy.
- No field names imply automatic route, queue, or selected next action.

### Phase 3: Track Discovery Semantics

Goal:

Make readable tracks usable as candidate collaboration context without adding an inbox.

Files:

- Modify `scripts/env/services/tracks.py`
- Modify `scripts/env/services/context.py`
- Modify `tests/test_track_manager_env_tool.py`
- Modify `tests/test_context_binding_env_tool.py`

Implementation:

- Add compact track discovery builder.
- Add `discovery` to `track.list` rows.
- Add `discovery_summary` to `track.list`.
- Add `track_context_summary` to `track.get`.
- Include latest handoff to active buddy from run audits.
- Include artifact kind summaries but not full foreign artifact content.
- Sort and cap deterministically.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_artifact_manager_env_tool.py \
  -q
```

Acceptance:

- Unbound Market can inspect tracks and see why a PM track is relevant.
- Market still cannot read PM task detail or PM artifact content through task/artifact tools.
- No instance binding changes occur during track discovery.

### Phase 4: Handoff Validation Semantics

Goal:

Clarify that handoff validation is outgoing validation, while discoverability comes from committed run audits and track/context read surfaces.

Files:

- Modify `scripts/env/services/handoffs.py`
- Modify `tests/test_context_binding_env_tool.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_runtime_tool_feedback.py`

Implementation:

- Add `track_alignment` to success and conflict responses.
- Add `discoverability` to success responses.
- Include `suggested_next_buddy` on transition conflicts.
- Preserve no-mutation behavior.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

Acceptance:

- Host can tell when target matches track transition.
- Host can tell handoff becomes discoverable only after `run.commit`.
- Conflict response points to PM track advance or matching next buddy, not raw state mutation.

### Phase 5: Env Tool Static Contract Registry

Goal:

Stop contract drift and expose operation semantics from a single static source.

Files:

- Create `scripts/env/tools/contracts.py`
- Modify `scripts/turn_runtime.py`
- Modify `scripts/env/tools/router.py`
- Modify `scripts/env/tools/*_manager.py`
- Modify `scripts/env/client.py` only after registry stabilizes or add consistency tests first
- Modify `tests/test_prepare_runtime_context.py`
- Modify `tests/test_env_tool_router.py`
- Modify `tests/test_env_tool_response_contract.py`
- Modify `tests/test_repo_consistency.py`

Implementation sequence:

1. Add registry with current active tools/actions and generated payload schema views.
2. Replace the hand-authored `_build_env_tools_desc()` map with registry-derived output.
3. Add `operation_semantics` generated from registry.
4. Make router derive supported tools/actions/hints from registry.
5. Make manager action maps derive from registry or remove duplicate manager unknown-action checks once router tests prove ownership.
6. Add CLI consistency tests before generating argparse from registry.
7. Generate CLI from registry only if duplication remains painful after tests.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_env_tool_router.py \
  tests/test_env_tool_response_contract.py \
  tests/test_repo_consistency.py \
  -q
```

Acceptance:

- Every registry action appears in prepare env tools.
- Router supported actions match registry.
- Manager handler actions match registry.
- CLI action normalization matches registry.
- payload schema views are generated, not hand-maintained.
- `operation_semantics` exists for every action.
- Old handwritten tool/action maps are deleted or reduced to registry imports.

### Phase 6: Structured Next Action Options

Goal:

Make recovery guidance machine-readable while retaining human-readable `allowed_next_actions`.

Files:

- Create or modify `scripts/env/tools/responses.py`
- Modify service response builders one domain at a time
- Modify `tests/test_env_tool_response_contract.py`
- Modify service-specific tests for task, track, artifact, context, binding, handoff, run, and evidence

Target field:

```json
{
  "allowed_next_action_options": [
    {
      "id": "inspect_candidate_tracks",
      "tool": "track",
      "action": "list",
      "mutates": "none",
      "preconditions": ["track.read"],
      "reason": "No current track is bound and track context is the handoff discovery surface.",
      "source_refs": ["runtime_context.env_tools.track_manager"]
    }
  ]
}
```

Rules:

- Keep dynamic state-specific feedback in services.
- Use registry operation semantics for `tool`, `action`, and `mutates` validation.
- Do not require every response to include this field in phase one; require it for decision-critical responses first.

Decision-critical responses:

- fresh/unbound `context.summarize`;
- `track.get_current` with no track;
- `track.list`;
- `track.get`;
- `handoff.validate`;
- Market missing evidence rejection;
- stale context rejection;
- non-PM track lifecycle rejection;
- foreign task/artifact rejection.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_track_manager_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_market_browser_evidence.py \
  -q
```

Acceptance:

- Structured next action options never point to raw-state writes.
- Options do not force a workflow.
- Options match actual registry tool/action names.

### Phase 7: Market Evidence And Artifact Decision Surface

Goal:

Align Market browser evidence, artifact production, and handoff continuation with the same decision surface.

Files:

- Modify `scripts/env/services/evidence.py`
- Modify `scripts/env/services/artifacts.py`
- Modify `scripts/env/services/runs.py`
- Modify `scripts/turn_runtime.py` if runtime context evidence readiness needs current token state
- Modify `tests/test_market_browser_evidence.py`
- Modify `tests/test_artifact_manager_env_tool.py`
- Modify `tests/test_env_layer_end_to_end.py`

Implementation:

- Add evidence readiness to decision surface.
- Ensure evidence response names exact persist field and run scope.
- Ensure Market missing-evidence rejection returns structured next action option for `evidence.issue_browser` or approved downgrade where valid.
- Add artifact list/get current revision metadata needed for decisions: kind, title, summary, source buddy, source run, revision, currentness.
- Do not expose foreign full content through artifact manager.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_market_browser_evidence.py \
  tests/test_artifact_manager_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

Acceptance:

- Market can infer evidence requirement before artifact-producing commit.
- Evidence token response gives exact persist field.
- Bound Market run audit preserves track/handoff continuity and evidence record.

### Phase 8: Product-Mode Scenario Evals

Goal:

Prove the whole decision surface supports realistic host reasoning.

Files:

- Modify `tests/test_env_layer_end_to_end.py`
- Add focused eval-style tests under existing test structure, not a new eval framework unless repeated need appears
- Optionally add a manual runbook under `docs/spec` after the automated checks stabilize

Scenarios:

- Fresh Market with no binding and one PM handoff track available.
- Bound Market with current track and newly created Market task.
- Bound Market with PM PRD, PM handoff, browser evidence requirement, Market artifact, handoff to Design.
- Multiple candidate tracks with deterministic ranking.
- Conflicting track next buddy and recent handoff target.

Verification:

```bash
python3 -m pytest -p no:cacheprovider \
  tests/test_env_layer_end_to_end.py \
  tests/test_prepare_runtime_context.py \
  tests/test_context_binding_env_tool.py \
  tests/test_track_manager_env_tool.py \
  tests/test_market_browser_evidence.py \
  -q
```

Manual smoke after automated tests pass:

```bash
./buddyswitch-codex instance start --buddy pm
./buddyswitch-codex instance start --buddy market
python3 scripts/turn_runtime.py prepare "Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design."
python3 scripts/env/client.py context summarize
python3 scripts/env/client.py track list
```

Manual check:

- JSON shows binding state.
- Candidate track discovery appears when unbound.
- PM handoff context appears when bound or after track inspection.
- Browser evidence requirement appears for Market.
- No automatic inbox, route, or binding mutation appears.

## Test Strategy

### Semantic Assertions

Prefer assertions like:

- `decision_surface.binding_state.state == "bound_task_and_track"`.
- `decision_surface.active_buddy_relation.track_role == "next_buddy"`.
- `decision_surface.active_buddy_relation.latest_handoff_to_active_buddy is True`.
- `track.discovery.relevance_reasons` contains `recent_handoff.next_buddy == active_buddy`.
- `context_sources_desc["task_context.artifacts"]["content"] == "full"`.
- `context_sources_desc["current_context_summary"]["content"] == "summary"`.
- `operation_semantics["track"]["list"]["mutates"] == "none"`.
- `handoff.track_alignment.target_matches_track_next_buddy is True`.
- `allowed_next_action_options[*].tool` and `.action` exist in the registry.

Avoid shallow assertions like:

- field exists;
- string is non-empty;
- long prose equals exact text;
- result count is non-zero without semantic meaning.

### Regression Safety

Keep these guarantees:

- Cross-buddy task mutation remains forbidden.
- Cross-buddy artifact reads through artifact manager remain forbidden.
- Track lifecycle mutation remains PM-owned.
- Non-PM arbitrary `binding.set_track` remains rejected.
- Run commit remains atomic.
- Market evidence remains run-scoped and broker-issued.
- Raw state remains broker-only.
- Compact summaries do not leak full artifact content.

### Full Gate

After all phases:

```bash
python3 -m pytest -p no:cacheprovider -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile $(find scripts tests -name '*.py' -print)
```

If the full suite is too slow during iteration, use the focused phase gates and run the full gate before final branch completion.

## Data And Privacy Boundaries

Discovery fields may expose:

- track title, status, summary;
- current and next buddy ids;
- task ids on a track;
- buddy ids with tasks on a track;
- artifact kind, title, summary, source run id, revision/currentness;
- handoff reason/context from committed run audits.

Discovery fields must not expose:

- full foreign artifact content;
- raw object file paths as instructions for host writes;
- mutable raw state locations;
- private task details outside existing allowed surfaces;
- browser evidence tokens outside the active run/buddy context.

## Naming Rules

Avoid policy-sounding names:

- `recommended_route`
- `selected_track`
- `handoff_inbox`
- `next_workflow_step`
- `auto_bind`
- `must_call_next`

Prefer descriptive names:

- `decision_surface`
- `binding_state`
- `active_buddy_relation`
- `context_readiness`
- `candidate_tracks`
- `discovery`
- `relevance_reasons`
- `source_refs`
- `operation_semantics`
- `allowed_next_action_options`

## Risks And Controls

Risk: Decision semantics become workflow policy.

Control: Use descriptive relation fields, source refs, and affordances. Do not auto-select or mutate.

Risk: Registry becomes a generic workflow engine.

Control: Keep registry static: tools, actions, schemas, CLI mapping, operation semantics. Keep state-dependent behavior in services.

Risk: Prepare payload grows too large.

Control: Keep full content in existing source sections. Add compact summaries and source refs. Cap track discovery summaries when needed.

Risk: Discovery leaks foreign artifact content.

Control: Track discovery includes artifact metadata only. Full content remains in current task context or explicitly allowed artifact reads.

Risk: Structured next-action options drift from actual tools.

Control: Validate tool/action names against registry in contract tests.

Risk: Tests become prompt-like.

Control: Assert semantic fields and object relationships, not LLM output text or prescribed call order.

Risk: Fresh Market still makes the wrong decision.

Control: Add product-mode scenario evals that assert the environment presents enough information. If failures persist after semantic surface improvements, only then revisit whether a new product concept is justified.

## Definition Of Done

This upgrade is done when:

1. `prepare.runtime_context` exposes structured source descriptors, decision surface, and operation semantics.
2. `context.summarize`, `track.list`, `track.get`, and `handoff.validate` expose discovery and alignment semantics without mutation.
3. Fresh Market can discover candidate PM handoff context through environment state without a handoff inbox or prompt recipe.
4. Bound Market can see PM PRD summary, PM handoff context, track relation, evidence requirement, and artifact/handoff constraints.
5. Env tool contracts are generated from one static registry or protected by strong consistency tests.
6. Decision-critical responses include structured next action options where appropriate.
7. Tests assert semantic decision information, not only shape.
8. Existing ownership, permission, evidence, and run commit boundaries remain green.
9. Manual product-mode smoke shows the same decision information through real CLI/broker surfaces.
10. No new hidden routing, inbox, workflow engine, or automatic binding behavior is introduced.

## Recommended First Implementation Slice

Start with the narrowest vertical slice:

**Bound and fresh Market handoff discovery.**

Concrete work:

1. Add failing semantic tests for fresh Market and bound Market.
2. Add structured context source descriptors.
3. Add `decision_surface` for binding/relation/readiness.
4. Add `track.list.discovery` and `track.get.track_context_summary`.
5. Add `context.summarize.candidate_tracks` for unbound or task-only-bound hosts.
6. Add `handoff.validate.track_alignment` and `discoverability`.
7. Run focused tests.

Do the contract registry after the vertical slice proves the semantic shape. The registry is justified by current duplication, but the first product bottleneck is host decision information, not code deduplication.

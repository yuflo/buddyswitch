# Buddy Host DESC/Feedback Runtime Surface Development Plan

> **For agentic workers:** implement this plan from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`. Use `superpowers:test-driven-development` before code changes and `superpowers:verification-before-completion` before claiming completion. Track progress with the checklist below.

**Goal:** Make ordinary launcher-managed buddy work executable from `prepare` output and structured runtime feedback, without requiring the host to read runtime source, schemas, manifests, or broker internals for basic boundary decisions.

**Current bottleneck:** `prepare.runtime_context` and runtime rejection feedback already exist, but they are still too skeletal for normal PM/Market/Design/Dev/Test work. The host still needs to infer payload fields, track lifecycle rules, artifact-kind usage, context file handling, and some recovery actions from source or contracts.

**Architecture:** Keep the existing `prepare -> skill work -> persist -> receipt` loop. Add compact executable DESC surfaces to prepare output, persist context to the buddy scratch path, and broaden structured rejection feedback for common persist validation failures. Keep AGENTS short and framework-level; do not move payload recipes back into prompt text.

---

## Working Directory

Run every command from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`.

Existing unrelated worktree state must be preserved:

- `.codex/config.toml` is already modified.
- `docs/memo/2026-05-08-buddy-host-desc-feedback-consensus-memo.md` is untracked.

## Source Memo

Implement the accepted direction from:

```text
docs/memo/2026-05-08-buddy-host-desc-feedback-consensus-memo.md
```

The memo defines DESC as runtime-returned descriptive contract surfaces, especially `prepare.runtime_context`, not longer prompt prose.

## Preflight Facts

- `scripts/turn_runtime.py::_build_runtime_context()` currently returns active buddy, skills, runtime commands, capability boundary, tool requirements, persist payload hint, and current context summary.
- `scripts/turn_runtime.py::_build_prepare_turn_context()` creates or resolves task/track context, reserves the run, and returns prepare payload.
- `RuntimeFeedbackError` already carries structured fields for some rejections.
- `scripts/runtime_kernel/client.py::broker_unavailable_feedback()` owns the product-mode broker hard stop.
- `buddyswitch/manifest.toml` owns buddy skills, scopes, artifact kinds, and permissions.
- `buddyswitch/env-profiles/*.json` owns project access, scratch root, tool capability, and PM-only track effects.
- `tools/launcher/assets/buddies/*/AGENTS.md` already points to `prepare.runtime_context` and structured tool feedback.
- Existing tests cover the current runtime context skeleton, canonical runtime commands, AGENTS validation, broker-unavailable hard stop, and several permission boundaries.

## Target Contract

### Prepare Output

Update `framework/contracts/prepare-turn-context.json` so successful prepare payloads expose:

```json
{
  "ok": true,
  "context_revision": "ctx-task-pm-ai-schedule-landing-page-turn-1",
  "instance_id": "inst-pm-example",
  "active_buddy": "pm",
  "runtime_context": {},
  "context_save_path": "runs/raw/pm/prepare-context-run-abc123.json",
  "persist_command_hint": "python3 scripts/turn_runtime.py persist --context runs/raw/pm/prepare-context-run-abc123.json --result runs/raw/pm/persist-result.json",
  "request_text": "Draft onboarding PRD",
  "current_task_id": "task-pm-ai-schedule-landing-page",
  "current_track_id": null,
  "task_context": {},
  "track_context": null,
  "track_artifact_index": {},
  "run_envelope": {},
  "warnings": []
}
```

Use repo-relative paths in public payload fields. Write the canonical prepare JSON to `context_save_path` after the payload is assembled, and ensure the saved file includes the same `context_revision`, `run_envelope.run_id`, `active_buddy`, `request_text`, and `persist_command_hint` returned to the host.

### Runtime Context Required Sections

Extend `runtime_context_required_sections` to include:

```json
[
  "active_buddy",
  "active_skill_ids",
  "runtime_commands",
  "capability_boundary",
  "tool_requirements",
  "persist_payload_hint",
  "desc",
  "track_lifecycle_desc",
  "artifact_kind_desc",
  "context_sources_desc",
  "current_context_summary"
]
```

### Runtime DESC Shape

Add `runtime_context.desc` with concise user-facing descriptions for persist fields:

```json
{
  "execution_summary": {
    "required": true,
    "purpose": "Short durable summary of what this buddy completed in this turn."
  },
  "artifacts": {
    "required": false,
    "purpose": "Durable work products owned by the active buddy.",
    "item_fields": ["kind", "title", "summary", "content"],
    "kind_source": "runtime_context.artifact_kind_desc"
  },
  "state_effects.task": {
    "required": false,
    "purpose": "Update status or summary for the current prepared task only.",
    "allowed_fields": ["status", "summary"]
  },
  "state_effects.track": {
    "required": false,
    "purpose": "PM-owned track lifecycle mutations.",
    "rule_source": "runtime_context.track_lifecycle_desc"
  },
  "handoff": {
    "required": false,
    "purpose": "Ask another manifest buddy to continue with explicit reason and context.",
    "does_not_mutate_track": true
  },
  "contributors": {
    "required": false,
    "purpose": "Record skill ids or agent labels that contributed to the run."
  },
  "tool_evidence": {
    "required": "Market artifact-producing commits require broker-issued evidence.",
    "purpose": "Attach broker-issued evidence tokens; do not hand-write tokens."
  }
}
```

Tests should verify semantic keys and required behaviors, not exact long prose.

### Track Lifecycle DESC

Add `runtime_context.track_lifecycle_desc`.

For PM:

```json
{
  "owner": "pm",
  "allowed_actions": ["create", "update", "advance", "archive"],
  "create": "Creates a track and binds the current prepared task.",
  "non_create_requires_existing_track": true,
  "handoff_does_not_mutate_track": true,
  "current_track_source": "current_track_id"
}
```

For non-PM buddies:

```json
{
  "owner": "pm",
  "allowed_actions": [],
  "handoff_does_not_mutate_track": true,
  "allowed_next_action": "Persist an artifact/task update or hand off track lifecycle changes to PM."
}
```

### Artifact Kind DESC

Add `runtime_context.artifact_kind_desc` as a map for the active buddy only:

```json
{
  "prd": {
    "label": "PRD",
    "use_when": "PM defines product requirements, scope, decisions, and acceptance criteria."
  }
}
```

Every active buddy artifact kind from `manifest.toml` must have exactly one description with a non-empty `use_when`. Do not expose artifact kinds owned only by other buddies.

### Context Sources DESC

Add `runtime_context.context_sources_desc` to tell product-facing buddies where usable context lives:

```json
{
  "request_text": "Original user request for this turn.",
  "task_context.task": "Current task metadata and summary.",
  "task_context.artifacts": "Full prior artifact content for the current task when available.",
  "track_context.track": "Current track title, status, buddies, and summary when bound.",
  "track_context.recent_handoffs": "Recent handoff reason and context.",
  "current_context_summary": "Compact scan-friendly summary; use full task_context artifacts when content detail is needed."
}
```

This is the product-facing substitute for reading runtime implementation files to discover where context is stored.

## File Map

Primary implementation files:

- `scripts/turn_runtime.py`
  - Add DESC helpers for persist fields, artifact kinds, track lifecycle, and context sources.
  - Add prepare context save path and persist command hint.
  - Write canonical prepare JSON to `runs/raw/<buddy>/prepare-context-<run_id>.json`.
  - Convert common persist validation failures to `RuntimeFeedbackError`.
- `framework/contracts/prepare-turn-context.json`
  - Add `context_save_path`, `persist_command_hint`, and new required runtime context sections.
- `framework/docs/turn-runtime-spec.md`
  - Document the DESC surfaces, context-save behavior, and structured feedback expectations.
- `tests/test_prepare_runtime_context.py`
  - Add functional tests for new prepare DESC fields and saved context.
- `tests/test_runtime_tool_feedback.py`
  - Add behavior tests for structured rejection recovery.
- `tests/test_turn_runtime.py`
  - Add focused CLI/public output assertions if lower-level command behavior changes.
- `tests/test_parallel_contracts.py`
  - Update frozen prepare contract and response shape expectations.
- `tests/test_repo_consistency.py`
  - Add drift guards for artifact-kind DESC coverage and active specs avoiding source-inference flows.
- `tests/test_runtime_agents.py`
  - Only adjust if AGENTS wording needs a new pointer. Do not expand AGENTS into payload recipes.

Secondary files only if needed:

- `tools/launcher/assets/buddies/*/AGENTS.md`
  - Keep concise. Add only a pointer such as "Use prepare DESC fields for payload and recovery details" if tests show current wording is insufficient.
- `scripts/runtime_agents.py`
  - Update validation only if AGENTS wording changes.

## Non-Goals

- Do not add a plugin system, workflow engine, event bus, or generic DESC registry.
- Do not make AGENTS prompt-heavy.
- Do not add request-specific examples such as landing pages, calendar apps, or competitor scans.
- Do not change buddy routing, switch-prefixed text handling, or the `prepare -> skill work -> persist` lifecycle.
- Do not widen project write access. Dev remains writable for `projects/app`; PM/Market/Design/Test remain read-only.
- Do not permit raw writes to `buddyswitch/objects/**` or `buddyswitch/content/runs/**`.
- Do not add compatibility wrappers or dual persist contracts.

## Implementation Tasks

### Task 1: Lock The Contract With Failing Tests

**Files:**

- Modify: `framework/contracts/prepare-turn-context.json`
- Modify: `tests/test_parallel_contracts.py`
- Modify: `tests/test_prepare_runtime_context.py`
- Modify: `tests/test_runtime_tool_feedback.py`

Steps:

- [ ] Add `context_save_path` and `persist_command_hint` to the expected prepare response key order.
- [ ] Add `desc`, `track_lifecycle_desc`, `artifact_kind_desc`, and `context_sources_desc` to expected runtime context sections.
- [ ] Add `test_prepare_runtime_context_exposes_desc_for_commit_fields`.
- [ ] Add `test_prepare_writes_context_file_and_exposes_persist_hint`.
- [ ] Add `test_prepare_exposes_track_lifecycle_desc_for_pm_and_non_pm`.
- [ ] Add `test_prepare_exposes_artifact_kind_desc_for_active_buddy`.
- [ ] Add `test_prepare_exposes_context_sources_for_product_work`.
- [ ] Add structured feedback tests for common persist rejections.

Suggested test skeleton:

```python
def test_prepare_runtime_context_exposes_desc_for_commit_fields(self) -> None:
    payload = self._prepare(buddy="pm", request_text=PM_REQUEST)
    desc = payload["runtime_context"]["desc"]

    for key in (
        "execution_summary",
        "artifacts",
        "state_effects.task",
        "state_effects.track",
        "handoff",
        "contributors",
        "tool_evidence",
    ):
        self.assertIn(key, desc)
        self.assertTrue(str(desc[key]["purpose"]).strip())

    self.assertTrue(desc["execution_summary"]["required"])
    self.assertIn("kind_source", desc["artifacts"])
    self.assertTrue(desc["handoff"]["does_not_mutate_track"])
```

Expected first run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_parallel_contracts.py \
  -q
```

Expected result before implementation: tests fail because the new public fields are absent or plain `ValueError` paths lack structured feedback.

### Task 2: Add Prepare Context Save Path And Persist Hint

**Files:**

- Modify: `scripts/turn_runtime.py`

Steps:

- [ ] Add a helper that builds repo-relative context paths:

```python
def _context_save_path(active_buddy: str, run_id: str) -> str:
    return f"runs/raw/{active_buddy}/prepare-context-{run_id}.json"
```

- [ ] Add a helper that builds the public persist command hint:

```python
def _persist_command_hint_for_context(context_save_path: str, active_buddy: str) -> str:
    return (
        "python3 scripts/turn_runtime.py persist "
        f"--context {context_save_path} "
        f"--result runs/raw/{active_buddy}/persist-result.json"
    )
```

- [ ] In `_build_prepare_turn_context()`, after `run_id` and `runtime_context` are available, add top-level `context_save_path` and `persist_command_hint` to the payload.
- [ ] Write the final successful payload to `ROOT / context_save_path`.
- [ ] Create parent directories with `mkdir(parents=True, exist_ok=True)`.
- [ ] Write JSON with `ensure_ascii=True`, `indent=2`, and a trailing newline.
- [ ] If writing the context file fails, clear the reservation and return/raise a prepare failure instead of returning a path that cannot be used.

Stop condition: if the correct writable root is not `ROOT / runs/raw/<buddy>`, pause and inspect `RuntimeWorkspaceTestMixin`, `env_store.ROOT`, and launcher projection before editing further.

### Task 3: Add Runtime DESC Sections

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `framework/docs/turn-runtime-spec.md`

Steps:

- [ ] Add `_build_persist_field_desc(active_buddy, tool_capability)` returning `runtime_context.desc`.
- [ ] Add `_build_track_lifecycle_desc(active_buddy, allowed_track_effects)` returning PM and non-PM variants.
- [ ] Add `_build_context_sources_desc()` returning stable context-source descriptions.
- [ ] Add a concrete artifact-kind description map covering all current manifest kinds:

```python
_ARTIFACT_KIND_DESC = {
    "market-scan": {
        "label": "Market scan",
        "use_when": "Market summarizes demand, competition, audience, and positioning evidence for downstream product decisions.",
    },
    "pmf-report": {
        "label": "PMF report",
        "use_when": "Market evaluates product-market-fit signals, ICP hypotheses, confidence, and interview angles.",
    },
    "customer-discovery": {
        "label": "Customer discovery",
        "use_when": "Market prepares or summarizes customer interview hypotheses, guides, and learning points.",
    },
    "positioning-brief": {
        "label": "Positioning brief",
        "use_when": "Market defines message house, homepage angles, competitive contrast, and copy direction.",
    },
    "channel-plan": {
        "label": "Channel plan",
        "use_when": "Market proposes acquisition channels, experiment plans, and channel scoring.",
    },
    "launch-prep": {
        "label": "Launch prep",
        "use_when": "Market prepares launch assets, instrumentation, feedback collection, and release readiness notes.",
    },
    "prd": {
        "label": "PRD",
        "use_when": "PM defines product requirements, scope, decisions, acceptance criteria, and implementation-ready constraints.",
    },
    "pm-decision": {
        "label": "PM decision",
        "use_when": "PM records a product decision, tradeoff, or scope clarification that downstream buddies should follow.",
    },
    "track-note": {
        "label": "Track note",
        "use_when": "PM records cross-buddy track status, next buddy direction, blockers, or lifecycle rationale.",
    },
    "design-handoff": {
        "label": "Design handoff",
        "use_when": "Design provides interaction decisions, visual direction, handoff notes, and implementation constraints.",
    },
    "prototype-brief": {
        "label": "Prototype brief",
        "use_when": "Design captures prototype goals, flows, interaction states, preview references, and open UX questions.",
    },
    "implementation-report": {
        "label": "Implementation report",
        "use_when": "Dev reports changed files, implementation notes, verification evidence, risks, and follow-up work.",
    },
    "skill-import-report": {
        "label": "Skill import report",
        "use_when": "Dev reports skill import or conversion work, changed skill files, validation, and remaining risks.",
    },
    "smoke-test": {
        "label": "Smoke test",
        "use_when": "Test records focused smoke checks, pass/fail/blocked results, reproduction notes, and readiness.",
    },
    "test-report": {
        "label": "Test report",
        "use_when": "Test records broader regression scope, commands, evidence, failures, and release readiness judgment.",
    },
}
```

- [ ] Add `_build_artifact_kind_desc(buddy)` that includes only `buddy["artifact_kinds"]`.
- [ ] Make missing descriptions fail loudly with `ValueError`, so a new manifest kind cannot silently produce weak DESC.
- [ ] Insert the four new sections into `_build_runtime_context()`.

Implementation guard: keep descriptions compact. They are executable hints, not product examples.

### Task 4: Broaden Structured Persist Feedback

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `tests/test_runtime_tool_feedback.py`

Steps:

- [ ] Convert common persist result shape failures to `RuntimeFeedbackError` with `permission_boundary`, `allowed_next_actions`, and `persist_payload_hint`.
- [ ] Cover these boundaries:

| Failure | Suggested `permission_boundary` | Required feedback |
|---|---|---|
| missing/empty `execution_summary` | `persist.execution_summary` | explain required summary |
| no artifact/state/handoff durable signal | `persist.durable_signal` | allowed durable signal options |
| duplicate artifact kind | `persist.artifacts.kind` | use one artifact per kind per commit |
| artifact missing title/content/kind | `persist.artifacts` | required artifact item fields |
| invalid track action | `env-profile.state_capability.track_effects` | allowed actions for active buddy |
| `create` when prepared task already has track | `state_effects.track.create` | use update/advance/archive or omit track effect |
| non-create track action without current/explicit track | `state_effects.track.track_id` | provide existing track id or create via PM |
| non-create references missing track | `state_effects.track.track_id` | rerun prepare with valid track or create first |
| update/advance has no mutable fields | `state_effects.track` | include title/status/current_buddy/next_buddy/summary |
| missing handoff reason/context | `persist.handoff` | required handoff fields |
| handoff target conflicts with track next buddy | `persist.handoff` | make targets match or remove one |

- [ ] Keep environment/profile corruption errors as ordinary internal failures where they are not user-recoverable.
- [ ] Do not catch broad `ValueError` at the top and guess feedback there; convert at the validation point that knows the boundary.
- [ ] Preserve atomicity: every rejection test must prove no task, track, artifact, run, or reservation state was committed incorrectly.

### Task 5: Add Drift Guards

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_runtime_agents.py` only if AGENTS wording changes.

Steps:

- [ ] Add a repo consistency test that every manifest artifact kind has an entry in `_ARTIFACT_KIND_DESC`.
- [ ] Add a test that active AGENTS still point to `prepare.runtime_context` and structured feedback, but do not include detailed payload recipes.
- [ ] Add an active-surface check that current docs/spec do not instruct hosts to read `scripts/turn_runtime.py`, `framework/contracts/*.json`, or `buddyswitch/manifest.toml` for ordinary boundary decisions.
- [ ] Keep historical memos out of active-surface checks unless they are used as current instructions.

### Task 6: Update Runtime Documentation

**Files:**

- Modify: `framework/docs/turn-runtime-spec.md`

Steps:

- [ ] Document `context_save_path` and `persist_command_hint`.
- [ ] Document `runtime_context.desc`.
- [ ] Document `runtime_context.track_lifecycle_desc`.
- [ ] Document `runtime_context.artifact_kind_desc`.
- [ ] Document `runtime_context.context_sources_desc`.
- [ ] State that AGENTS should point to these runtime surfaces and structured feedback, not duplicate recipes.
- [ ] Keep examples generic and non-product-specific.

### Task 7: Verify Main Runtime Path

Run focused checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_turn_runtime.py \
  tests/test_parallel_contracts.py \
  -q
```

Run contract and drift checks:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_agents.py \
  tests/test_repo_consistency.py \
  tests/test_output_schema_boundaries.py \
  tests/test_buddy_env_profiles.py \
  tests/test_buddy_env_sandbox.py \
  -q
```

Run launcher checks if AGENTS, materialization, or projected paths changed:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  -q
```

Run command-level proof:

```bash
python3 scripts/turn_runtime.py --help
python3 scripts/runtime_agents.py validate-all
python3 scripts/env_profiles.py validate-all
```

## Acceptance Criteria

- `prepare` returns `context_save_path` and `persist_command_hint`.
- The file at `context_save_path` exists and contains the same prepare identity as the returned payload.
- `prepare.runtime_context` includes `desc`, `track_lifecycle_desc`, `artifact_kind_desc`, and `context_sources_desc`.
- Every active buddy artifact kind has a non-empty usage description.
- PM track lifecycle rules are explicit; non-PM buddies are clearly told that track lifecycle is PM-owned.
- Structured feedback covers common persist validation failures with recoverable next actions and payload hints.
- Broker-unavailable product mode still returns hard stop feedback and does not suggest bypassing the broker.
- AGENTS remain concise and framework-level.
- Existing buddy boundaries remain unchanged.
- Tests prove behavior through public prepare/persist output and state snapshots, not private helper branches.

## Residual Risks

- Host source-reading behavior cannot be fully proven by unit tests. The proxy is that runtime output now exposes all basic boundary and recovery decisions.
- Writing prepare context files adds a prepare side effect. Keep it inside `runs/raw/<buddy>/` and test reservation cleanup on failure.
- Artifact descriptions are a new durable contract. Add drift tests so future manifest changes cannot skip descriptions.

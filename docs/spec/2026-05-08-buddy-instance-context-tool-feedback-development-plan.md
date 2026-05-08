# Buddy Instance Context Tool Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing buddy instance main path expose enough executable context and structured tool feedback that PM, Market, Design, Dev, and Test buddies can follow `prepare -> skill work -> persist -> receipt/handoff` without reading runtime source, schemas, profiles, or manifest files to infer what is allowed.

**Architecture:** Keep the already-built env profile, runtime broker, Market evidence, active skill projection, and launcher-managed instance path. Add one compact `prepare.runtime_context` block derived from manifest + env profile + current task/track state, then make broker/runtime/evidence failures return structured buddy-facing feedback fields. Only after those signals are tested, shrink prompt-like AGENTS/runtime wording that duplicates the new executable signals.

**Tech Stack:** Python runtime scripts, JSON contracts, TOML manifest data, Bash launcher-managed product mode, `unittest`/`pytest`, Markdown runtime docs and buddy AGENTS templates.

---

## Working Directory

Run all implementation and verification from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Do not edit the main checkout at `/Users/chen/Dev/buddyswitch`. This plan intentionally targets the `dev0210` worktree.

## Concise Understanding

The observed PM buddy behavior is not an AI calendar landing-page special case. It shows that the runtime currently makes the model infer too much from source, schemas, profiles, and docs.

The next bottleneck is main-path productization: `prepare` must show the active buddy's executable capability boundary, and runtime tools must explain rejections and safe next actions. The accepted path is not bigger prompts, not case-specific examples, and not a new continuation UX.

## Current Bottleneck

The first environment layer already strengthened executed boundaries. The remaining blocker is that the host still lacks compact, canonical, runtime-returned context and structured feedback:

- `prepare` returns task/track/run context but not an explicit capability block for allowed artifacts, state effects, handoff targets, active skills, project/scratch boundaries, Market evidence policy, or persist shape.
- Broker, persist, and evidence failures usually expose `code` + `message` only, so buddies may still inspect implementation files to recover.
- `AGENTS.md` and runtime docs still carry some compensating guidance that should move into durable runtime output once the output exists.

## Confirmed Facts

- `scripts/turn_runtime.py` owns public `prepare` and `persist` CLI names and builds the prepared context in `_build_prepare_turn_context`.
- `framework/contracts/prepare-turn-context.json` currently lists `ok`, `context_revision`, `instance_id`, `active_buddy`, `request_text`, task/track context, `track_artifact_index`, `run_envelope`, and `warnings`.
- `buddyswitch/env-profiles/*.json` already define per-buddy project access, scratch root, filesystem capability, state capability, tool capability, and context projection.
- `buddyswitch/manifest.toml` already maps buddies to active skill ids and allowed artifact kinds.
- `scripts/runtime_kernel/broker.py` dispatches product-mode `prepare`, `persist`, and `issue_browser_evidence` through the launcher-managed broker.
- `scripts/runtime_kernel/client.py` already fails product-mode broker transport with `E_RUNTIME_BROKER_UNAVAILABLE`.
- `scripts/browser_evidence.py` already calls the broker for Market evidence issuance.
- `tools/launcher/assets/buddies/*/AGENTS.md` currently provide framework-level runtime guidance and some boundary wording.
- Existing tests cover env profiles, broker identity, Market browser evidence, runtime AGENTS validation, and Buddy run persist behavior, but not the new executable context and structured feedback shape.

## Open Assumptions And Invalidators

- Assumption: Adding `runtime_context` to `prepare` is acceptable as a forward-compatible contract addition. Invalidator: any consumer requires exact response-key equality instead of contract-driven parsing; if found, update that consumer in the same task.
- Assumption: Buddy-facing errors can be added without replacing existing error `code` and `message`. Invalidator: tests or CLI consumers depend on exact error object equality; if found, preserve existing keys and add fields only.
- Assumption: `prepare.runtime_context` should summarize existing task/track/artifact/handoff context instead of duplicating full artifacts. Invalidator: product testing shows summaries are insufficient for action choice; if found, add only the missing summary fields, not full raw state dumps.
- Assumption: AGENTS slimming should happen only after structured runtime signals are proven. Invalidator: if runtime context tests fail or leave gaps, do not shrink AGENTS yet.

## Verification Stop Condition

Stop only when these are proven:

- PM, Market, Design, Dev, and Test `prepare` responses include `runtime_context`.
- `runtime_context` exposes active buddy, active skill ids, allowed artifact kinds, allowed `state_effects`, handoff targets, project/scratch/raw-state boundaries, tool/evidence requirements, persist payload hints, current task summary, current track summary, artifact summaries, and recent handoff summaries.
- Product-mode broker unavailable errors include a stop condition that says not to bypass the broker.
- Persist and broker rejections include structured fields such as `permission_boundary`, `allowed_next_actions`, `command_hint`, or `persist_payload_hint` where relevant.
- Market evidence issuance returns token mode, browser URL when relevant, persist field name, token scope, and next action.
- `AGENTS.md` remains framework-level and does not grow into task-specific or payload-specific prompt guidance.
- Focused tests and full relevant test suite pass.

## File Map

Modify:

- `scripts/turn_runtime.py`: build `runtime_context`; add structured error helpers and persist rejection metadata.
- `scripts/runtime_kernel/broker.py`: preserve structured error payloads from prepare/persist/evidence dispatch; add broker permission and stop feedback.
- `scripts/runtime_kernel/client.py`: attach structured broker-unavailable stop feedback to `RuntimeBrokerError`.
- `scripts/browser_evidence.py`: pass through structured evidence feedback and broker-unavailable stop feedback.
- `framework/contracts/prepare-turn-context.json`: add `runtime_context` to response order and document required subkeys.
- `framework/contracts/persist-buddy-run.json`: document structured error payload fields if contract scope is expanded there; otherwise keep response shape and document errors in runtime spec.
- `framework/docs/turn-runtime-spec.md`: document executable prepare context and structured tool feedback.
- `tools/launcher/assets/buddies/market/AGENTS.md`: shrink or redirect Market-specific details after runtime signals exist.
- `tools/launcher/assets/buddies/pm/AGENTS.md`: shrink or redirect PM track/persist details after runtime signals exist.
- `tools/launcher/assets/buddies/design/AGENTS.md`: keep framework-level runtime guidance only.
- `tools/launcher/assets/buddies/dev/AGENTS.md`: keep framework-level runtime guidance only.
- `tools/launcher/assets/buddies/test/AGENTS.md`: keep framework-level runtime guidance only.
- `scripts/runtime_agents.py`: validate shorter framework-level AGENTS plus reference to `prepare.runtime_context`, not duplicated payload recipes.
- `tests/test_turn_runtime.py`: focused prepare context and CLI broker-unavailable feedback tests.
- `tests/test_runtime_broker.py`: broker structured rejection tests.
- `tests/test_market_browser_evidence.py`: evidence feedback and Market rejection metadata tests.
- `tests/test_runtime_agents.py`: shorter AGENTS validator tests.
- `tests/test_repo_consistency.py`: guard against prompt bloat and source/schema-inference guidance.

Create if useful:

- `tests/test_prepare_runtime_context.py`: dedicated functional tests for `prepare.runtime_context` across buddies.
- `tests/test_runtime_tool_feedback.py`: dedicated functional tests for structured runtime feedback across prepare, persist, broker, and evidence tools.

Do not touch:

- Context panel server.
- Cleanup tools.
- Debug object APIs.
- Skill importer.
- New continuation commands such as `instance continue` or `open-handoff`.

## Target Runtime Context Shape

Add `runtime_context` as a compact object in `prepare` output:

```json
{
  "runtime_context": {
    "active_buddy": {
      "id": "pm",
      "label": "PM",
      "scope": "Own product iteration and track progression."
    },
    "active_skill_ids": ["write-prd", "track-manager"],
    "capability_boundary": {
      "allowed_artifact_kinds": ["prd", "pm-decision", "track-note"],
      "allowed_state_effects": {
        "task": ["status", "summary"],
        "track": ["create", "update", "advance", "archive"]
      },
      "handoff_targets": ["market", "pm", "design", "dev", "test"],
      "project": {
        "path": "projects/app",
        "access": "read-only",
        "write_rule": "handoff-to-dev"
      },
      "scratch": {
        "root": "runs/raw/pm",
        "access": "write"
      },
      "raw_state": {
        "access": "broker-only",
        "paths": [
          "buddyswitch/objects/tracks/*.json",
          "buddyswitch/objects/tasks/*.json",
          "buddyswitch/objects/artifacts/*.json",
          "buddyswitch/content/runs/*.json"
        ]
      }
    },
    "tool_requirements": {
      "browser_cockpit": "available",
      "market_research_evidence": "not-required",
      "ordinary_web_fallback": "available"
    },
    "persist_payload_hint": {
      "required": ["execution_summary"],
      "optional": ["working_notes", "artifacts", "state_effects", "handoff", "contributors", "tool_evidence"],
      "durable_signal_rule": "include at least one of artifacts/state_effects/handoff",
      "artifact_kind_source": "runtime_context.capability_boundary.allowed_artifact_kinds",
      "state_effect_source": "runtime_context.capability_boundary.allowed_state_effects",
      "handoff_target_source": "runtime_context.capability_boundary.handoff_targets"
    },
    "current_context_summary": {
      "task": {
        "id": "task-pm-example",
        "status": "active",
        "summary": ""
      },
      "track": null,
      "artifacts": [],
      "recent_handoffs": []
    }
  }
}
```

Market must include browser evidence-specific hints:

```json
{
  "tool_requirements": {
    "browser_cockpit": "required",
    "market_research_evidence": "required",
    "ordinary_web_fallback": "user-approved-only",
    "evidence_next_action": "use scripts/browser_evidence.py issue --context <prepare-context.json> --mode browser-cockpit-preflight before artifact-producing persist"
  },
  "persist_payload_hint": {
    "tool_evidence": {
      "required_when": "Market artifact-producing commit",
      "accepted_fields": ["browser_cockpit_token", "approved_downgrade_token"],
      "source": "broker-issued evidence response for current run"
    }
  }
}
```

## Target Structured Error Shape

Keep `ok=false`, `error.code`, and `error.message`. Add fields only when they help the buddy choose the next safe action:

```json
{
  "ok": false,
  "error": {
    "code": "E_RUNTIME_BROKER_UNAVAILABLE",
    "message": "runtime broker unavailable at /path/to/runtime-broker.sock: ...",
    "permission_boundary": "product-mode-runtime-broker",
    "stop_condition": "stop_and_report_do_not_bypass_broker",
    "allowed_next_actions": [
      "Report that the launcher-managed runtime broker is unavailable.",
      "Do not write raw BuddySwitch state directly.",
      "Do not call direct debug APIs to bypass product mode."
    ],
    "command_hint": "./buddyswitch-codex instance open <instance-id>"
  }
}
```

Persist rejection example:

```json
{
  "ok": false,
  "error": {
    "code": "E_RUNTIME_PERSIST",
    "message": "buddy 'market' is not allowed to perform track action 'create'",
    "permission_boundary": "env-profile.state_capability.track_effects",
    "allowed_next_actions": [
      "Remove state_effects.track from the Market commit.",
      "Persist a Market artifact or handoff instead.",
      "Hand off track lifecycle changes to PM."
    ],
    "persist_payload_hint": {
      "allowed_state_effects": {
        "task": ["status", "summary"],
        "track": []
      }
    }
  }
}
```

## Implementation Tasks

### Task 1: Add Prepare Runtime Context Contract

**Files:**

- Modify: `framework/contracts/prepare-turn-context.json`
- Modify: `framework/docs/turn-runtime-spec.md`
- Test: `tests/test_prepare_runtime_context.py`

- [ ] **Step 1: Write failing contract test for `runtime_context` presence and key order**

Add a test that invokes product-shaped prepare for each buddy and asserts the public response includes `runtime_context` with required top-level sections:

```python
required_sections = {
    "active_buddy",
    "active_skill_ids",
    "capability_boundary",
    "tool_requirements",
    "persist_payload_hint",
    "current_context_summary",
}
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py -q
```

Expected before implementation: fails because `runtime_context` is missing.

- [ ] **Step 2: Update `prepare-turn-context` contract**

Add `runtime_context` to `response_key_order` immediately after `active_buddy` or immediately before `task_context`. Use the same order in implementation and tests.

- [ ] **Step 3: Document the contract**

In `framework/docs/turn-runtime-spec.md`, add a short `Prepare Runtime Context` section listing the six required sections and stating that this is the buddy-facing source for allowed actions, forbidden actions, and compact persist shape.

- [ ] **Step 4: Run contract test and confirm it still fails only on implementation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_prepare_runtime_context.py -q
```

Expected: failure is now implementation-only, not missing test imports or invalid test setup.

### Task 2: Build `runtime_context` From Manifest, Env Profile, And Current State

**Files:**

- Modify: `scripts/turn_runtime.py`
- Test: `tests/test_prepare_runtime_context.py`
- Test: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add helper that derives active buddy and skill capability**

Implement a local helper near prepare builders:

```python
def _build_runtime_context(
    *,
    buddy: dict[str, Any],
    manifest: dict[str, Any],
    env_profile: dict[str, Any],
    task_context: dict[str, Any],
    track_context: dict[str, Any] | None,
    track_artifact_index: dict[str, Any],
) -> dict[str, Any]:
    ...
```

Keep it concrete. Do not introduce a generic permission DSL.

- [ ] **Step 2: Populate capability boundary**

Use existing data sources:

- `buddy["id"]`, `buddy["label"]`, `buddy["scope"]`
- `buddy["skills"]`
- `buddy["artifact_kinds"]`
- `env_profile["state_capability"]["task_effects"]`
- `env_profile["state_capability"]["track_effects"]`
- manifest buddy ids for handoff targets
- `env_profile["project"]`
- `env_profile["scratch"]`
- `env_profile["filesystem_capability"]`

For non-dev buddies, set project write rule to `handoff-to-dev`. For Dev, set it to `direct-project-write-allowed`.

- [ ] **Step 3: Populate tool requirements**

Use `env_profile["tool_capability"]`.

For Market, include a command hint for browser evidence issuance:

```text
python3 scripts/browser_evidence.py issue --context <prepare-context.json> --mode browser-cockpit-preflight
```

For non-Market buddies, state that `tool_evidence` is not required by their profile.

- [ ] **Step 4: Populate persist payload hint**

Use `framework/contracts/persist-buddy-run.json` as the source for required/optional keys, plus a fixed durable signal rule:

```text
include at least one of artifacts/state_effects/handoff
```

Reference runtime context sections as the source of allowed artifact kinds, state effects, and handoff targets.

- [ ] **Step 5: Populate compact current summaries**

Summarize from existing prepare structures:

- task id, buddy, status, summary, latest run id;
- track id, status, current buddy, next buddy, summary;
- artifact id, kind, title, buddy, task id, summary;
- recent handoff run id, buddy id, next buddy, reason, context.

Keep summaries compact and do not duplicate full artifact content.

- [ ] **Step 6: Insert `runtime_context` into prepare output**

In `_build_prepare_turn_context`, load the active env profile once and include the returned object in the prepare payload.

- [ ] **Step 7: Verify focused prepare behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  -q
```

Expected: all selected tests pass.

### Task 3: Add Structured Broker-Unavailable Feedback

**Files:**

- Modify: `scripts/runtime_kernel/client.py`
- Modify: `scripts/turn_runtime.py`
- Modify: `scripts/browser_evidence.py`
- Test: `tests/test_runtime_tool_feedback.py`
- Test: `tests/test_turn_runtime.py`

- [ ] **Step 1: Write failing public CLI tests**

Test product-mode `prepare`, product-mode `persist`, and `scripts/browser_evidence.py issue` with missing or unreachable broker socket.

Assert:

- exit code is non-zero;
- `error.code` is `E_RUNTIME_BROKER_UNAVAILABLE`;
- `error.permission_boundary` is `product-mode-runtime-broker`;
- `error.stop_condition` is `stop_and_report_do_not_bypass_broker`;
- `allowed_next_actions` includes no raw state write or direct debug bypass.

- [ ] **Step 2: Extend `RuntimeBrokerError` to carry structured details**

Add an optional `details: dict[str, Any]` or reuse `response` if already sufficient. Do not remove existing `code`, `message`, or `response`.

- [ ] **Step 3: Add broker-unavailable detail builder**

Add one concrete helper in `scripts/runtime_kernel/client.py`:

```python
def broker_unavailable_feedback(*, socket_path: Path | None = None) -> dict[str, Any]:
    return {
        "permission_boundary": "product-mode-runtime-broker",
        "stop_condition": "stop_and_report_do_not_bypass_broker",
        "allowed_next_actions": [
            "Report that the launcher-managed runtime broker is unavailable.",
            "Do not write raw BuddySwitch state directly.",
            "Do not call direct debug APIs to bypass product mode."
        ],
        "command_hint": "./buddyswitch-codex instance open <instance-id>"
    }
```

Include `socket_path` when known.

- [ ] **Step 4: Preserve details in CLI runtime errors**

Update `turn_runtime.runtime_error` call sites that catch `RuntimeBrokerError` to include `exc.details`. Do the same in `scripts/browser_evidence.py`.

- [ ] **Step 5: Verify focused feedback tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_tool_feedback.py \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_product_mode_prepare_without_broker_returns_unavailable \
  -q
```

Expected: all selected tests pass.

### Task 4: Add Structured Persist And Permission Rejection Feedback

**Files:**

- Modify: `scripts/turn_runtime.py`
- Modify: `scripts/runtime_kernel/broker.py`
- Test: `tests/test_runtime_tool_feedback.py`
- Test: `tests/test_runtime_broker.py`
- Test: `tests/test_market_browser_evidence.py`

- [ ] **Step 1: Write failing product-shaped rejection tests**

Cover these rejected commits through broker dispatch, not private validators:

- Market tries `state_effects.track.create`.
- Dev tries artifact kind `prd`.
- PM handoff target is unknown.
- PM task effect includes unsupported field.
- Market artifact-producing commit omits `tool_evidence`.
- Persist context active buddy mismatches active instance buddy.

For each, assert no state writes and structured fields identify the boundary and allowed next action.

- [ ] **Step 2: Add a lightweight runtime feedback exception**

In `scripts/turn_runtime.py`, add a small exception class or return helper that keeps structured metadata with existing `ValueError` behavior:

```python
class RuntimeFeedbackError(ValueError):
    def __init__(self, code: str, message: str, **feedback: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.feedback = feedback
```

Use it only for product-relevant boundaries. Do not convert every validation string into a taxonomy in this iteration.

- [ ] **Step 3: Convert high-value validation failures**

Add structured metadata for:

- env-profile state capability rejection;
- artifact kind rejection;
- task effect unsupported key;
- handoff target rejection;
- Market evidence missing or invalid;
- context/instance/buddy mismatch.

Keep messages short and specific.

- [ ] **Step 4: Preserve structured payload through broker dispatch**

Update `scripts/runtime_kernel/broker.py` so caught `RuntimeFeedbackError` returns:

```json
{
  "ok": false,
  "error": {
    "code": "...",
    "message": "...",
    "...feedback": "..."
  }
}
```

Do not collapse structured errors back into `E_RUNTIME_BROKER` unless the failure is truly broker transport or dispatch infrastructure.

- [ ] **Step 5: Verify rejection tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_tool_feedback.py \
  tests/test_runtime_broker.py \
  tests/test_market_browser_evidence.py \
  -q
```

Expected: all selected tests pass and negative cases prove state snapshots are unchanged.

### Task 5: Add Browser Evidence Success Feedback

**Files:**

- Modify: `scripts/runtime_kernel/broker.py`
- Modify: `scripts/browser_evidence.py`
- Test: `tests/test_market_browser_evidence.py`
- Test: `tests/test_runtime_tool_feedback.py`

- [ ] **Step 1: Write failing evidence issuance tests**

For `browser-cockpit-preflight`, assert the response includes:

- `tool_evidence.browser_cockpit_token`;
- `feedback.mode`;
- `feedback.browser_url`;
- `feedback.persist_field=tool_evidence.browser_cockpit_token`;
- `feedback.token_scope` with instance id, buddy id, task id, track id, context revision, and run id;
- `feedback.next_action` telling the buddy to include the token in the next artifact-producing persist.

For `approved-downgrade`, assert equivalent fields with `approved_downgrade_token` and reason.

- [ ] **Step 2: Extend evidence token response**

In `_write_evidence_token`, keep existing `tool_evidence` shape and add a sibling `feedback` object. This preserves existing consumers.

- [ ] **Step 3: Verify evidence tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_market_browser_evidence.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

Expected: all selected tests pass.

### Task 6: Slim Runtime AGENTS After Signals Are Proven

**Files:**

- Modify: `tools/launcher/assets/buddies/market/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/pm/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/design/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/dev/AGENTS.md`
- Modify: `tools/launcher/assets/buddies/test/AGENTS.md`
- Modify: `scripts/runtime_agents.py`
- Test: `tests/test_runtime_agents.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add guard against AGENTS payload bloat**

Add repo consistency checks that runtime AGENTS templates do not include long persist recipe examples, literal artifact-kind matrices, or task-specific examples like AI calendar landing pages.

- [ ] **Step 2: Update runtime AGENTS validator**

Require only framework-level facts:

- active buddy id;
- `AGENTS.md` is context projection only and not permission source;
- use `scripts/turn_runtime.py prepare` first;
- read `prepare.runtime_context` for allowed actions and persist shape;
- use `scripts/turn_runtime.py persist --context --result`;
- do not route around rejected runtime tools;
- final response uses receipt then summary.

Keep Dev source-write and non-Dev source-read-only wording only if it remains absent from `prepare.runtime_context` in terminal-visible form; otherwise prefer `prepare.runtime_context`.

- [ ] **Step 3: Shrink each AGENTS template**

Remove duplicated payload/evidence/track recipes that now live in `prepare.runtime_context` or structured tool feedback. Keep Market-specific browser rule only as a short pointer to `prepare.runtime_context.tool_requirements`.

- [ ] **Step 4: Verify AGENTS and repo guards**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_agents.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: all selected tests pass and AGENTS files are shorter or no longer more verbose than before this task.

### Task 7: End-To-End Main-Path Verification

**Files:**

- Test only unless failures reveal implementation gaps.

- [ ] **Step 1: Run focused product runtime suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_prepare_runtime_context.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_turn_runtime.py \
  tests/test_runtime_broker.py \
  tests/test_market_browser_evidence.py \
  tests/test_runtime_agents.py \
  tests/test_buddy_env_profiles.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run launcher smoke for product path**

Run the lowest-risk launcher checks already present in the repository test suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Inspect structured output manually**

Run a PM prepare in a launcher-managed test instance or existing test harness and confirm the JSON itself makes this path obvious:

```text
PM product definition + PRD artifact + state_effects.track create + handoff to Market
```

Expected: the correct path is visible in `runtime_context` without opening `manifest.toml`, `framework/contracts/*.json`, `scripts/turn_runtime.py`, or env profile files.

## Self-Review Checklist

- The plan targets the current bottleneck: executable context and tool feedback.
- The plan does not add a new continuation UX.
- The plan does not optimize for one AI calendar landing page prompt.
- The plan keeps env profiles, broker, prepare, persist, receipt, and handoff as the main path.
- Tests are written before implementation for each behavior block.
- Negative tests assert no state writes before accepting structured error payloads.
- AGENTS slimming happens only after runtime signals are proven.

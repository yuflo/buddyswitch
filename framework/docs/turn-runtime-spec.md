# BuddySwitch Turn Runtime Spec

## Purpose

Define the active runtime contract for launcher-managed buddy instances.

## Product Input Contract

- Users submit ordinary request text.
- Active buddy comes from launcher metadata (`BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_INSTANCE_JSON`).
- Command-shaped routing input is rejected before any task, artifact, run, or reservation writes.

## Runtime Entry

- `scripts/turn_runtime.py`
- Public API:
  - `prepare_turn_context(text, manifest_path=DEFAULT_MANIFEST)`
  - `persist_buddy_run(context, *, result, manifest_path=DEFAULT_MANIFEST)`
- Product CLI surface (unchanged names):
  - `python3 scripts/turn_runtime.py prepare "<request>"`
  - `python3 scripts/turn_runtime.py persist --context <context> --result <result>`

## Three Runtime Gates

1. Materialization validates copy boundaries only.
2. `prepare` validates turn context and reservation safety only.
3. `persist` validates write safety only.

Codex CLI owns skill package acceptance after runtime materialization into `.agents/skills/<skill-id>`.

Persist commits one active buddy run result. Native skills may contribute to that result, but native skill ids do not own the persist boundary, artifact identity, receipt identity, or write permissions.

## Native Output Flow

1. Codex runs needed native skills from runtime `.agents/skills/<skill-id>`.
2. The locked buddy session integrates outputs into one buddy run commit.
3. Persist with `scripts/turn_runtime.py persist --context <context> --result <result>`.

## CLI Contract

Prepare:

```bash
python3 scripts/turn_runtime.py prepare "Draft onboarding PRD"
```

Persist:

```bash
python3 scripts/turn_runtime.py persist \
  --context /tmp/prepare-context.json \
  --result /tmp/result.json
```

## Product-Mode Routing

- In product mode, host CLI calls route through the launcher-managed runtime broker (`BUDDYSWITCH_RUNTIME_BROKER_SOCKET`).
- Broker unavailability returns `ok=false` with `error.code=E_RUNTIME_BROKER_UNAVAILABLE`.
- Product mode has no direct host state-write fallback.
- Direct function calls (`prepare_turn_context`, `persist_buddy_run`) remain test/debug internals and broker server dispatch internals.

## Prepare Contract

`prepare` returns `ok=false` on validation errors, otherwise returns contract shape from `framework/contracts/prepare-turn-context.json`:

- `ok`
- `context_revision`
- `instance_id`
- `active_buddy`
- `request_text`
- `current_task_id`
- `current_track_id`
- `task_context`
- `track_context`
- `track_artifact_index`
- `run_envelope`
- `warnings`

Behavior:

- Uses locked buddy from instance metadata.
- Resolves or reuses active task and optional track binding.
- Reserves one run envelope for the turn.
- Validates context safety, not skill package readiness.
- Does not gate on `SKILL.md`, package source readiness, or output schema file existence.

## Persist Contract

Top-level response shape is frozen by `framework/contracts/persist-buddy-run.json`:

- `ok`
- `receipt`
- `refreshed_context`

`persist` write-safety checks include:

- context and reservation identity integrity;
- reserved run id exists and has not already been committed;
- commit includes non-empty `execution_summary`;
- `artifacts`, when present, are validated objects with non-empty `kind`/`title` and object `content`;
- artifact kinds are unique within one commit and authorized by active buddy `artifact_kinds`;
- `state_effects.track`, when present, uses `create|update|advance|archive` and is permission-gated;
- `state_effects.task`, when present, updates only current prepared task;
- `handoff`, when present, includes `next_buddy`, `reason`, `context`, and known buddy reference;
- profile state capability is enforced (`artifact_kinds`, `task_effects`, `track_effects`, `handoff_targets`);
- `tool_evidence` is optional generally and required for Market artifact-producing commits in broker-backed product mode;
- if both handoff next buddy and track next buddy are present, they must match;
- at least one durable collaboration signal exists: `artifacts`, `state_effects`, or `handoff`.

State writes in product mode are broker-owned.

## Receipt Contract

`receipt` is the canonical runtime metadata source for terminal rendering and follow-up turn composition.

Required `receipt` keys:

- `ok`
- `buddy_id`
- `task_id`
- `task_title`
- `artifact_ids`
- `run_id`
- `next_state`
- `receipt_paths`
- `related_run_ids`

Optional `receipt` keys:

- `track_id`
- `track_title`
- `track_action`
- `handoff`
- `warnings`

Terminal output must render user-facing IDs and titles from `receipt`, not debug path strings.

## Follow-up Turn Rule

After successful persist:

1. Read `receipt.next_state` and optional `receipt.handoff`.
2. Draft next ordinary `request_text`.
3. Run `prepare` again.

Do not continue a turn through hidden reservation state.

## Canonical State Paths

- `buddyswitch/objects/tracks/*.json`
- `buddyswitch/objects/tasks/*.json`
- `buddyswitch/objects/artifacts/*.json`
- `buddyswitch/content/runs/*.json`
- `runs/raw/` (instance-local scratch)

## Contracts

- `framework/contracts/prepare-turn-context.json`
- `framework/contracts/persist-buddy-run.json`
- `framework/contracts/buddy-env-profile.json`
- `framework/contracts/workspace-projection.json`

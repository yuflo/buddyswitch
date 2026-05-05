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
  - `persist_skill_result(context, *, skill_id, result, manifest_path=DEFAULT_MANIFEST)`

## Three Runtime Gates

1. Materialization validates copy boundaries only.
2. `prepare` validates turn context and reservation safety only.
3. `persist` validates write safety only.

Codex CLI owns skill package acceptance after runtime materialization into `.agents/skills/<skill-id>`.

## Native Output Flow

1. Codex runs a native skill from runtime `.agents/skills/<skill-id>`.
2. The selected native skill emits buddy-level result JSON directly.
3. Persist with `scripts/turn_runtime.py persist --skill-id <native-skill-id>`.

Buddy-level schemas remain development contracts under `framework/schemas/**`; runtime `persist` does not require full schema completeness unless a field is needed for safe writes.

PM payloads may include `state_effects.track_operation` for explicit lifecycle operations.
Retired top-level `track_operation` payloads are rejected before durable writes.

## CLI Contract

Prepare:

```bash
python3 scripts/turn_runtime.py prepare "Draft onboarding PRD"
```

Persist:

```bash
python3 scripts/turn_runtime.py persist \
  --context /tmp/prepare-context.json \
  --skill-id write-prd \
  --result /tmp/result.json
```

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

`persist` validates and commits exactly one selected skill output.
Top-level response shape is frozen by `framework/contracts/persist-skill-result.json`:

- `ok`
- `receipt`
- `refreshed_context`

`persist` write-safety checks include:

- context and reservation identity integrity;
- selected `skill_id` membership in active buddy manifest skills;
- selected skill non-empty `output_slot` for artifact slot/id derivation;
- minimum payload shape (`execution_summary` non-empty string, `artifact_content` object, list-shaped optional note fields);
- PM-only `state_effects.track_operation` validation.
- does not auto-reserve a follow-up run.

## Receipt Contract

`receipt` is the canonical runtime metadata source for terminal rendering and follow-up turn composition.

Required `receipt` keys:

- `ok`
- `skill_id`
- `task_id`
- `task_title`
- `artifact_ids`
- `run_id`
- `next_state`
- `receipt_paths`
- `related_run_ids`

Optional `receipt` keys:

- `artifact_id`
- `track_id`
- `track_title`
- `track_action`
- `warnings`

Terminal output must render user-facing IDs and titles from `receipt`, not debug path strings.

## Follow-up Turn Rule

After successful persist:

1. Read `receipt.next_state`.
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
- `framework/contracts/persist-skill-result.json`
- `framework/contracts/workspace-projection.json`

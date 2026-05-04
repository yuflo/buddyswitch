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

## Native Output Flow

Canonical artifact flow:

1. Codex runs native skill from runtime `.agents/skills/<skill-id>`.
2. The selected native skill emits buddy-level result JSON directly.
3. Persist with `scripts/turn_runtime.py persist --skill-id <native-skill-id>`.

Artifact-producing buddies validate against buddy-level schemas:

- `framework/schemas/pm/pm-result.json`
- `framework/schemas/dev/dev-result.json`
- `framework/schemas/test/test-result.json`
- `framework/schemas/market/market-result.json`
- `framework/schemas/design/design-result.json`

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
- Resolves/reuses active task and optional track binding.
- Reserves one run envelope for the turn.
- Does not return custom skill selection or instruction-loading fields.

## Persist Contract

`persist` validates and commits exactly one selected skill output.
Top-level response shape is frozen by `framework/contracts/persist-skill-result.json`:

- `ok`
- `receipt`
- `refreshed_context`

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

Terminal output must render user-facing IDs and titles from `receipt`, not from debug path strings.
Legacy command-style follow-up keys must not be present in `receipt`.

Behavior:

- Rejects missing/empty/non-string skill ids.
- Rejects skill ids outside active buddy membership in manifest.
- Rejects tampered context identity (buddy/task/run/request mismatch).
- Enforces context and reservation identity integrity before any state write.
- Validates skill output payload against schema from manifest persistence contract.
- Writes canonical task/artifact/track/run state.
- Clears consumed reservation.
- Does not auto-reserve a follow-up run.

## Follow-up Turn Rule

After successful persist:

1. Read `receipt.next_state`.
2. Draft next ordinary `request_text`.
3. Run `prepare` again.

Do not continue a turn through hidden reservation state.

## Codex Native Skills

- Source packages are Codex-native under `buddyswitch/skills/**`.
- Runtime packages are materialized under instance `.agents/skills/**`.
- Codex owns native skill discovery and instruction loading from runtime `.agents/skills`.

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

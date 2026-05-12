# BuddySwitch Turn Runtime Spec

## Purpose

Define the active runtime contract for launcher-managed buddy instances.

## Product Input Contract

- Users submit ordinary request text.
- Active buddy comes from launcher metadata (`BUDDYSWITCH_ACTIVE_BUDDY`, `BUDDYSWITCH_INSTANCE_ID`, `BUDDYSWITCH_INSTANCE_JSON`).
- User text never routes or changes the active buddy. Text that resembles retired switch-prefixed buddy syntax is preserved as ordinary `request_text`.
- Retired top-level launcher commands still fail closed at the launcher boundary; that is separate from runtime request text handling.

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

`prepare` is runtime preflight and does not execute user task work. Task execution stays with the host/skill step between `prepare` and `persist`.

Codex CLI owns skill package acceptance after runtime materialization into `.agents/skills/<skill-id>`.

Persist commits one active buddy run result. Native skills may contribute to that result, but native skill ids do not own the persist boundary, artifact identity, receipt identity, or write permissions.

## Native Output Flow

1. Codex runs needed native skills from runtime `.agents/skills/<skill-id>`.
2. The locked buddy session integrates outputs into one buddy run commit.
3. Persist with `python3 scripts/turn_runtime.py persist --context <context> --result <result>`.

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
- `runtime_context`
- `context_save_path`
- `persist_command_hint`
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
- Returns `context_save_path` and `persist_command_hint` for immediate host use.
- Writes the canonical successful prepare payload to `context_save_path` under `runs/raw/<buddy>/`.
- Validates context safety, not skill package readiness.
- Does not gate on `SKILL.md`, package source readiness, or output schema file existence.

## Prepare Runtime Context

`prepare.runtime_context` is the buddy-facing source of truth for allowed actions, forbidden actions, and compact persist payload shape.

Required top-level sections:

- `active_buddy`
- `active_skill_ids`
- `runtime_commands`
- `capability_boundary`
- `env_tools`
- `operation_semantics`
- `tool_requirements`
- `persist_payload_hint`
- `desc`
- `track_lifecycle_desc`
- `artifact_kind_desc`
- `context_sources_desc`
- `current_context_summary`
- `decision_surface`

`runtime_context.desc` provides compact persist field guidance for `execution_summary`, optional `task_id`, optional `track_id`, optional `artifact_ids`, `handoff`, `contributors`, and `tool_evidence`.

`runtime_context.track_lifecycle_desc` is the source of truth for PM-owned lifecycle rules:

- PM: `create`, `update`, `advance`, `archive`; create binds current prepared task; non-create requires existing track.
- Non-PM buddies: lifecycle actions are empty and PM handoff guidance is explicit.

`runtime_context.artifact_kind_desc` describes only the active buddy's allowed artifact kinds, each with compact `label` and `use_when`.

`runtime_context.context_sources_desc` is a structured descriptor map keyed by source id (`request_text`, `task_context.task`, `task_context.artifacts`, `track_context.track`, `track_context.recent_handoffs`, `current_context_summary`). Each descriptor includes `description`, `content`, `scope`, `nullable`, and `decision_use`, with optional `source_of_truth`, `summary_projection`, `max_items`, and `sorted_by`.

`runtime_context.decision_surface` is the host-facing decision summary for the active binding. It includes:

- `binding_state` (`unbound`, `bound_task_only`, `bound_track_only`, `bound_task_and_track`, `stale`)
- `active_buddy_relation` (`task_role`, `track_role`, `latest_handoff_to_active_buddy`)
- `context_readiness`
- `evidence_readiness`
- `safe_read_affordances` (read-only next options with `mutates=none`)

Runtime AGENTS guidance should point to these runtime context surfaces instead of duplicating payload recipes or capability matrices.

`runtime_context.env_tools` is the compact source for broker-routed env tool operations. Shared env slices are executed through `python3 scripts/env/client.py <resource> <operation>` and routed through broker method `env.tool` with envelope `{tool, action, args}`. Active slices include `task-tool`, `track-tool`, `artifact-tool`, `context`, `binding`, `handoff`, `run`, and `evidence`.

`runtime_context.operation_semantics` is a registry-derived map keyed by `"<tool>.<action>"` (for example `track.list`, `run.commit`). Each row includes `kind`, `mutates`, `required_permission`, `authority`, `requires`, and `returns`.

Permission enforcement, active-buddy ownership checks, PM-only track lifecycle authority, artifact-kind scope, artifact source-run validation, instance binding writes, context validation, handoff target validation, run reservation validation, run commit persistence, Market evidence issuance, browser ready-page enforcement, and evidence token scope are implemented in runtime tool/service code, not in prompt wording.

## Discovery Surfaces

Discovery is descriptive and read-only. It does not mutate active instance binding.

- `track.list` returns per-row `discovery` semantics and `discovery_summary.candidate_track_ids`.
- `track.get` returns `track_context_summary` with compact task/current-artifact metadata.
- Track-context artifact summaries expose decision metadata (`id`, `kind`, `title`, `summary`, `source_buddy`, `source_run`, `revision`, `is_current`, `currentness`) and must not include foreign full artifact `content`.

## Persist Contract

Top-level response shape is frozen by `framework/contracts/persist-buddy-run.json`:

- `ok`
- `receipt`
- `refreshed_context`

`persist` write-safety checks include:

- context and reservation identity integrity;
- reserved run id exists and has not already been committed;
- commit includes non-empty `execution_summary`;
- `artifact_ids`, when present, reference existing artifact revisions written through artifact-tool;
- optional `task_id` and `track_id` are validated as associations only (no lifecycle writes);
- lifecycle writes for task/track/artifact are rejected from persist payload and must route through env tools;
- `handoff`, when present, includes `next_buddy`, `reason`, `context`, and known buddy reference;
- profile state capability is enforced (`artifact_kinds`, `task_effects`, `track_effects`, `handoff_targets`);
- `tool_evidence` is optional generally and required for Market artifact-producing commits in broker-backed product mode;
- if both handoff next buddy and track next buddy are present, they must match;
- audit-only persist is valid; durable associations are optional metadata.

State writes in product mode are broker-owned. Run reservation and commit writes are owned by `scripts/env/services/runs.py`; the host `persist` command and broker `persist` method call the same service path as `env.tool` `run.commit`. Browser evidence tokens are issued by `scripts/env/services/evidence.py` through `env.tool` `evidence.issue_browser` and `evidence.approve_downgrade`; the host browser evidence CLI remains a wrapper over the same env tool path.

## Structured Tool Feedback

When `prepare`, `persist`, or broker-routed evidence tools reject a request, responses keep `ok=false`, `error.code`, and `error.message` and may add structured feedback fields:

- `permission_boundary`
- `stop_condition`
- `allowed_next_actions`
- `allowed_next_action_options`
- `command_hint`
- `persist_payload_hint`

Common persist validation failures should return structured `E_RUNTIME_PERSIST` feedback with actionable `permission_boundary` and `allowed_next_actions` (for example `persist.execution_summary`, `persist.state_effects`, `persist.artifacts`, `persist.task_id`, `persist.handoff`).

Buddy runtime guidance should follow these fields and must not bypass broker-owned runtime boundaries.

`allowed_next_action_options[*].source_refs` should reference operation semantics rows via resolvable keys such as `runtime_context.operation_semantics['track.list']`.

## Receipt Contract

`receipt` is the canonical runtime metadata source for terminal rendering and follow-up turn composition.

Required `receipt` keys:

- `ok`
- `buddy_id`
- `artifact_ids`
- `run_id`
- `next_state`
- `receipt_paths`
- `related_run_ids`

Optional `receipt` keys:

- `track_id`
- `track_title`
- `task_id`
- `task_title`
- `handoff`
- `warnings`

Terminal output must render user-facing IDs and titles from `receipt`, not debug path strings.

## Follow-up Turn Rule

After successful persist:

1. Read `receipt.next_state` and optional `receipt.handoff`.
2. Draft next ordinary `request_text`.
3. Run `prepare` again.

Do not continue a turn through hidden reservation state.

## Manual Product-Mode Smoke

Run in a launcher-managed instance context and verify the same decision surfaces exposed by tests:

```bash
./buddyswitch-codex instance start --buddy pm -- --help
./buddyswitch-codex instance start --buddy market -- --help
python3 scripts/turn_runtime.py prepare "Receive PM's onboarding rewrite handoff, do a quick market scan, produce a market-scan artifact, and hand the next step to Design."
python3 scripts/env/client.py context summarize
python3 scripts/env/client.py track list
```

Expected signals:

- `runtime_context.decision_surface` is present.
- Market `evidence_readiness.market_research_evidence` is explicit.
- `track.list.discovery_summary.candidate_track_ids` is present when candidate tracks exist.
- Top discovery rows include `discovery.active_buddy_role` and `discovery.relevance_reasons`.

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

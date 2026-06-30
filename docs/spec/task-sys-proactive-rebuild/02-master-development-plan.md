# Task Sys Proactive Rebuild Master Development Plan

Source memo: `docs/memo/2026-06-29-task-sys-proactive-rebuild.md`

## Goal

Rebuild actor-driving inbound flow so every actor-driving inbound envelope becomes a task sys task first, and actor runtime only receives task-framed input, side frames, parent frames, or checkpoint UI from task sys.

## Architecture

The implementation keeps four boundaries:

- `daemon-service`: generic ingress and physical actuator.
- `task sys`: product model, task state, side/parent/checkpoint coordination, runtime instructions.
- `product domains`: source data and source refs only.
- `actor runtime`: task-framed input consumer and task sys tool/UI consumer.

No phase may introduce a compatibility track where raw inbound and task sys both drive actors.

## Phase Order

1. Phase 0: Boundary and residue map.
2. Phase 1: Minimal task sys substrate.
3. Phase 2: Actor-driving inbound ingress rebuild.
4. Phase 3: Side fast-processing rebuild.
5. Phase 4: Parent handoff and interrupt rebuild.
6. Phase 5: Task checkpoint and chained innerTUI rebuild.
7. Phase 6: Actor-facing task skill/tool relocation.
8. Phase 7: Residue cleanup, test rewrite, and final verification.

## Phase 0: Boundary And Residue Map

Old paths to replace or classify:

- CLI/Web raw user input.
- IM message wake handler.
- Track comment wake handler.
- Turn-complete task checkout prompt.
- Direct side triage prompt helper.
- Direct parent prompt and interrupt helper.
- Taskbox and active-task gate.
- Scheduled/browser/local trigger paths that may or may not drive actors.

New path introduced:

- No product code yet. This phase freezes code-derived targets and classifies pure runtime maintenance.

Residue to remove:

- None yet; deletion starts with the phase that replaces each old path.

Test coverage target:

- No new product tests yet. Existing old-behavior tests are mapped to future rewrite phases.

Acceptance gate:

- `00-orientation.md`, `01-codebase-survey.md`, and this master plan exist.
- Every old actor-driving path has a phase owner.
- Pure runtime maintenance paths are explicitly classified.

## Phase 1: Minimal Task Sys Substrate

Old paths to replace:

- No old ingress deletion yet; this phase creates the new substrate needed before replacement.

New path introduced:

- Add a focused task sys module, likely under `scripts/env/domain/task_sys.py` or a small `scripts/env/domain/task_sys/` package.
- Define a minimal `InboundEnvelope` normalization boundary using concrete dict payloads, not a generic workflow framework.
- Define `TaskRecord` fields: task id, source type/ref, actor target, inbound context, status, active processor, parent handoff params, checkpoint metadata.
- Define statuses: `new`, `side_processing`, `closed`, `needs_parent`, `parent_processing`, `checkpoint`.
- Define runtime instruction records: `start_side`, `submit_parent`, `interrupt_submit_parent`, `no_actor_action`.
- Implement `ingest(envelope)` to persist a task record and return the first runtime instruction without calling daemon internals.

Residue to remove:

- None in this phase unless a small local helper is superseded by the new task sys core.

Test coverage target:

- Unit tests for task sys ingest, task id creation, task record persistence, status initialization, source refs, actor target validation, runtime instruction shape, and no daemon imports/calls.
- Boundary tests that task sys stores source/ref/context without copying IM/Track product state.

Acceptance gate:

- Focused task sys tests pass.
- Search proves task sys does not import `tools.launcher.daemon_core`, `app_server`, or `daemon_client`.
- Old taskbox is not used as task sys truth.

## Phase 2: Actor-Driving Inbound Ingress Rebuild

Old paths to replace:

- `buddyswitch-codex instance input` direct raw `submit_turn`.
- Web `/api/instances/<actor>/input` direct raw CLI input path.
- IM `send_im_message` wake payload to `im_wake_handler` prompt submission.
- Track comment added delivery to `track_comment_added_handler` prompt submission.
- Turn-complete trigger to direct `[TASK CHECKPOINT]` prompt submission.
- Any local/cross-actor/scheduled trigger that wakes actors directly.

New path introduced:

- Add generic ingress helpers that build task sys inbound envelopes and call `task_sys.ingest`.
- Daemon-service executes only the runtime instruction returned by task sys.
- CLI/Web user text becomes a source envelope, not raw actor input.
- IM and Track product domains provide source refs and context; they no longer own actor wake execution.
- Turn-complete is ingested as checkpoint source input, not submitted as a prompt.

Residue to remove:

- Direct actor-driving calls from ingress handlers.
- IM and Track handler prompt builders or handler-owned prompt render calls for actor wake.
- Tests asserting raw user text reaches `turn/start` or `turn/steer`.

Test coverage target:

- CLI and Web user input create a task before any actor instruction.
- IM message created and Track comment added create tasks before actor action.
- Turn complete creates checkpoint task sys state/instruction instead of `[TASK CHECKPOINT]` prompt.
- Negative tests prove raw user input, IM, Track, and checkpoint paths cannot call `submit_turn` or handler direct submit.

Acceptance gate:

- Focused ingress tests pass.
- Residue searches for raw actor-driving ingress direct calls have no live hits except physical actuator internals documented for later phases.

Status:

- Accepted. See `phase-02-inbound-ingress.md` for actual modifications, deleted paths, verification, and residue findings.

## Phase 3: Side Fast-Processing Rebuild

Old paths to replace:

- `runtime.submit_side_triage_prompt`.
- Handler-rendered IM and Track side triage prompts.
- Side IM `message.mark(needs_parent)` direct parent prompt submit as an escalation path.

New path introduced:

- Task sys generates side task frames from task records.
- Daemon-service exposes physical `start_side` / `send_side` actuator execution for task sys instructions.
- Side result tool accepts only `close` or `need_parent(params)`.
- `need_parent(params)` may include parent context, relation to parent task, `interrupt`, and simple ordering/priority metadata.

Residue to remove:

- `submit_side_triage_prompt` from handler-facing semantic paths.
- Side prompt renderers with business-specific triage instructions.
- Tests that expect side prompt text to contain IM/Track instructions.

Test coverage target:

- Side frame generation includes task id and source refs.
- Side result schema rejects any outcome except `close` and `need_parent`.
- Side cannot directly submit parent or interrupt.
- IM/Track running-parent paths schedule side via task sys instruction.

Acceptance gate:

- Focused side tests pass.
- Residue search proves no business handler calls `submit_side_triage_prompt`.

Status:

- Accepted. See `phase-03-side-fast-processing.md` for actual modifications, deleted paths, verification, and residue findings.

## Phase 4: Parent Handoff And Interrupt Rebuild

Old paths to replace:

- Handler calls to `runtime.submit_parent_prompt`.
- `message.mark(needs_parent)` direct parent prompt submission.
- Handler/side control of daemon interrupt policy.

New path introduced:

- Task sys accepts `need_parent(params)`, records state, generates parent task frame, and returns `submit_parent` or `interrupt_submit_parent` runtime instruction.
- Daemon-service physically executes submit/interrupt instructions without reading IM/Track/user/checkpoint business fields.
- Parent frame contains task id and enough source context for actor work.

Residue to remove:

- Business handlers directly calling parent submit.
- Business handlers or side tools choosing `interrupt_policy`.
- Parent prompt text without task id.

Test coverage target:

- Parent submit instructions are task-id traceable.
- Interrupt happens only through task sys runtime instruction.
- Daemon actuator tests remain low-level but no handler-facing API exposes semantic prompt submit.
- IM/Track/user/checkpoint paths cannot call parent submit directly.

Acceptance gate:

- Focused parent/interrupt tests pass.
- Residue search proves no business handler calls `submit_parent_prompt` and no side result acts as interrupt.

## Phase 5: Task Checkpoint And Chained InnerTUI Rebuild

Old paths to replace:

- `task_checkout_handler` direct `[TASK CHECKPOINT]` prompt submission.
- `scripts/env/domain/task_tui.py` as old checkpoint prompt renderer.

New path introduced:

- Turn complete enters task sys checkpoint.
- Task sys creates a checkpoint frame with current task context, pending task context, legal operations, required params, and constraints.
- Actor can call one minimal task sys tool to update task state.
- Tool response returns the next task sys UI frame.

Residue to remove:

- `[TASK CHECKPOINT]` prompt path and old turn-complete prompt tests.
- Checkpoint UI text that recommends tasks or makes decisions for Codex.

Test coverage target:

- Turn complete creates checkpoint state and frame.
- Checkpoint UI has legal operations and required params.
- Tool call updates task state and returns next frame.
- UI does not recommend next task or contain daemon-service business UI.

Acceptance gate:

- Focused checkpoint tests pass.
- Residue search proves no live direct `[TASK CHECKPOINT]` actor prompt remains.

## Phase 6: Actor-Facing Task Skill/Tool Relocation

Old paths to replace:

- Taskbox as actor-facing task source of truth.
- `task-management` skill teaching taskbox.
- `task` tool implementation and schema as private taskbox operations.
- Active-task gate using `TaskViewModel.current_anchor`.

New path introduced:

- Actor-facing task tool reads and mutates task sys task state.
- Task skill describes task sys operations and defers schemas/effects to runtime tool catalog.
- Active-task validation becomes task-bound operation validation, not a prompt/gate forcing actors to maintain a parallel taskbox.

Residue to remove:

- Live surfaces teaching taskbox as product model.
- `E_ACTIVE_TASK_REQUIRED` gate semantics tied to taskbox.
- Tests asserting taskbox-only mutation contracts as final architecture.

Test coverage target:

- Task tool operates on task sys records.
- Actor-visible task context comes from task sys.
- Active-task validation checks task sys task binding.
- Task skill does not duplicate task sys schema or teach private taskbox paths.

Acceptance gate:

- Focused task tool/skill/gate tests pass.
- Residue search proves taskbox is not a parallel live task truth.

## Phase 7: Residue Cleanup And Final Verification

Old paths to remove:

- Any remaining direct raw inbound actor submission.
- Handler business prompt rendering.
- Handler direct side/parent submit calls.
- Side direct parent submit or interrupt.
- Direct checkpoint prompt.
- Taskbox/active-task parallel truth.
- Old tests locking raw inbound behavior.

New path proved:

- All actor-driving inbound goes through task sys ingest.
- Side returns only `close` or `need_parent(params)`.
- Parent input and interrupt are task sys runtime instructions.
- Checkpoint and innerTUI are task sys outputs.
- Daemon-service remains generic transport and physical actuator.

Test coverage target:

- Cross-layer acceptance tests for user input, Web input, IM, Track, turn complete, side escalation, parent handoff, interrupt, and checkpoint.
- Scoped no-residue tests for live surfaces.
- Broader Python verification after focused tests and lifecycle checks.

Acceptance gate:

- Focused and broader tests pass.
- Residue searches have no unexpected live hits.
- `99-final-acceptance.md` records phase completion, old path deletion, test matrix, search results, final commands, and remaining risk.

## Cross-Phase Verification Discipline

- Run focused tests after each meaningful change block.
- Do not run broad service-starting suites until helper cleanup and residual process behavior are known.
- Each phase document must record the exact commands run and result text.
- Any remaining residue hit must be classified as current semantics, physical actuator internals, historical docs outside live surface, or unfinished work.

# Task Sys Proactive Rebuild Orientation

Source memo: `docs/memo/2026-06-29-task-sys-proactive-rebuild.md`

## Required Sources Read

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- Current `docs/spec/*` planning examples, especially `docs/spec/identity-redesign/*`

## Execution Principles

- Treat this work as a rebuild-forward task, not a compatibility migration.
- Move one phase at a time; do not start implementation for a phase before its phase plan and test plan exist.
- Use tests to hold behavior boundaries before replacing old paths.
- Delete replaced raw-inbound actor-driving paths in the same phase that replaces them.
- Do not keep new and old task systems running as parallel sources of truth.
- Do not add workflow engines, event buses, rule engines, plugin schedulers, wrappers, or adapters to preserve old handlers.
- Record actual verification and residue searches in each phase document before advancing.

## Architecture Boundary Confirmation

- `daemon-service` owns generic ingress, routing, mailbox/local/scheduled physical delivery, and runtime actuation only.
- `task sys` owns the task model, task state, side/parent/checkpoint coordination, task frames, task innerTUI, and runtime instruction production.
- `product domains` own IM, Track, browser, and related product state. They may supply source refs and context, but they do not wake actors directly.
- `actor runtime` consumes task-framed input and task sys UI/tool projections. It does not receive raw inbound information as actor-driving input.

## No-Residue Constraints

- No raw actor-driving inbound may call actor runtime directly after its phase replacement.
- No handler may render IM, Track, user-input, or checkpoint business prompts for actor submission.
- No handler may directly call parent submit or side triage submit once replaced.
- No side path may directly interrupt or submit the parent.
- `interrupt` may only be an input parameter to a task sys parent handoff, with daemon-service only executing the resulting runtime instruction.
- Old taskbox and active-task gate behavior must not remain as a parallel task truth after task sys owns actor-facing task state.

## Old Path Categories To Search

- Direct user/web/CLI actor submission: `submit_turn`, `SubmitTurn`, `turn_text`, `user input`.
- Business prompt rendering in inbound handlers: IM, Track comment, browser/local/scheduled trigger, checkpoint prompt assembly.
- Direct parent handoff: `submit_parent_prompt`, parent prompt helpers, parent-thread write calls outside task sys.
- Direct side triage: `submit_side_triage_prompt`, side prompt helpers, side-thread start/send calls outside task sys scheduling.
- Interrupt decisions outside task sys: `interrupt`, `interrupt_parent`, interrupt plus submit helpers.
- Checkpoint prompt residue: `[TASK CHECKPOINT]`, turn-complete handlers, checkpoint prompt builders.
- Parallel task truth: `taskbox`, `task-management`, `active-task`, private workspace task files, task gate/auth prompts.
- Tests that expect raw inbound to wake actors directly or expect old prompt text.

## Phase Index

- Phase 0: boundary and residue map.
- Phase 1: minimal task sys substrate.
- Phase 2: inbound ingress rebuild.
- Phase 3: side fast-processing rebuild.
- Phase 4: parent handoff and interrupt rebuild.
- Phase 5: task checkpoint and chained innerTUI rebuild.
- Phase 6: actor-facing task skill/tool relocation.
- Phase 7: residue cleanup, test rewrite, and final verification.

Phase details stay authoritative in `docs/memo/2026-06-29-task-sys-proactive-rebuild.md`; this directory records code-derived implementation plans, test plans, acceptance evidence, and necessary appendices only.

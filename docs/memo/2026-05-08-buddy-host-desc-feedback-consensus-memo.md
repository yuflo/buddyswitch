# Buddy Host DESC/Feedback Consensus Memo

Date: 2026-05-08
Scope: Buddy host behavior in launcher-managed product runtime (`prepare -> skill work -> persist`) when Codex appears to perform blackbox source exploration.

## Problem and Background

The observed issue was not that Codex lacked reasoning ability; it was that the host lacked a compact, executable runtime surface for "what is allowed now" and "what to do next when rejected". When those DESC/feedback surfaces are weak, the model compensates by reading runtime source, contracts, and manifests to infer rules.

In this memo, **DESC** means runtime-returned descriptive contract surfaces (especially `prepare.runtime_context`), not longer prompt prose.

## User Feedback Trigger

User testing on the PM request below showed high source/schema exploration before execution:

`给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track`

The feedback was: buddy behavior looked like blackbox "摸索". The core ask was to converge behavior through runtime context and tool feedback, not by patching one prompt case.

## Investigation and Consensus Process

Consensus came from three evidence layers:

1. Prior diagnosis memo and plan artifacts identified missing runtime context/feedback as the bottleneck, not a single prompt failure.
   - `docs/memo/2026-05-07-buddy-instance-context-tool-feedback-direction-memo.md`
   - `docs/spec/2026-05-08-buddy-instance-context-tool-feedback-development-plan.md`
2. Runtime contract and implementation review confirmed the intended product
   path is `prepare.runtime_context` plus structured tool feedback, but the
   current fields are still too skeletal for ordinary buddy work.
   - `framework/contracts/prepare-turn-context.json`
   - `framework/docs/turn-runtime-spec.md`
   - `scripts/turn_runtime.py` (`_build_runtime_context`, `RuntimeFeedbackError`)
   - `scripts/runtime_kernel/client.py` (`broker_unavailable_feedback`)
   - `scripts/runtime_kernel/broker.py` (structured broker/evidence feedback)
3. Test evidence confirms some runtime context and feedback surfaces are now
   enforced and regression-guarded, while the PM log still shows missing DESC
   and recovery hints.
   - `tests/test_prepare_runtime_context.py`
   - `tests/test_runtime_tool_feedback.py`
   - `tests/test_runtime_agents.py`

## Final Consensus

1. **Blackbox source exploration is primarily a product-surface symptom.** If runtime DESC/feedback is incomplete, host exploration increases even when the model is otherwise capable.
2. **Optimization target is executable environment output, not prompt growth.** Keep AGENTS framework-level and move actionable detail into runtime-returned context and structured errors.
3. **Main-path success criterion:** a buddy should complete normal work from `prepare` output + tool feedback, without needing runtime source/schema inference for basic boundary decisions.
4. **Do not overfit one request.** The fix must generalize across PM/Market/Design/Dev/Test workflows.

## Avoidable vs Normal Host Reads

Avoidable reads (should be unnecessary for ordinary turn execution once `prepare` is available):

- Reading `scripts/turn_runtime.py` to discover allowed artifact kinds/state effects/handoff targets.
- Reading `buddyswitch/manifest.toml` to infer active skill set or buddy boundary.
- Reading `framework/contracts/*.json` to discover persist payload basics.
- Reading runtime broker source to interpret common rejection recovery steps.

Normal reads (still expected and healthy):

- Reading user-relevant product text context or artifacts needed to perform the
  assigned task.
- Reading skill content required by the selected workflow.
- Reading project code for implementation/debug work (especially Dev/Test scope).
- Reading receipts/artifacts/track context as part of current task execution.

Decision rule: **reduce contract-discovery reads, not task-execution reads**.
When product state is needed, prefer a prepared text DESC/artifact over forcing
the host to inspect implementation files.

## Target Product Contract (DESC + Feedback)

The agreed runtime contract for host behavior is:

1. `prepare` returns `runtime_context` with executable boundaries and payload
   hints (active buddy/skills, capability boundary, tool requirements, persist
   hint, current summary).
2. Runtime/tool rejections return structured feedback fields (for example `permission_boundary`, `stop_condition`, `allowed_next_actions`, `command_hint`, `persist_payload_hint`) rather than generic failures.
3. Broker-unavailable in product mode returns a hard stop contract (`E_RUNTIME_BROKER_UNAVAILABLE`, stop/report/do-not-bypass) instead of encouraging workaround behavior.
4. Runtime `AGENTS.md` remains concise and points to `prepare.runtime_context` and structured tool feedback instead of duplicating long recipes.
5. `prepare` exposes DESC fields that explain allowed payload fields and state
   transitions in user-facing language, so the host does not read schemas or
   Python source to infer behavior.
6. `prepare` exposes command/path hints such as `context_save_path` and
   `persist_command_hint`, so the host does not guess whether
   `context_revision` is a file path.

## Solution Direction

Short-term direction:

1. Add a richer `runtime_context.desc` or equivalent field descriptions for
   `execution_summary`, `artifacts`, `state_effects.task`,
   `state_effects.track`, `handoff`, `contributors`, and `tool_evidence`.
2. Add `context_save_path` and `persist_command_hint` to the prepared turn
   output, preferably with prepare writing the canonical context JSON into the
   run scratch directory.
3. Add `track_lifecycle_desc`: PM can create/update/advance/archive; create
   binds the prepared task; non-create actions need an existing/current track;
   handoff does not implicitly mutate track.
4. Add artifact-kind descriptions for the active buddy, including when each
   artifact kind should be used.
5. Add product/context DESC surfaces for product-facing tasks so PM/Market/Design
   can consume text context instead of implementation source when possible.
6. Broaden structured feedback so common validation failures return
   `permission_boundary`, `allowed_next_actions`, and `command_hint` instead of
   plain `ValueError`.
7. Keep tests contract-first (functional behavior over private-branch
   assertions) for runtime context and rejection recovery.
8. Continue slimming prompt-like AGENTS wording whenever equivalent runtime
   surfaces exist.

Guardrail:

- Do not reintroduce prompt-heavy or source-inference-dependent flows for basic boundary decisions.
- If host reads drift back toward contract discovery, treat it as a missing/weak DESC or feedback field and fix the runtime surface first.

## Decision Status

Accepted. This is the durable consensus baseline for buddy-host behavior tuning: improve runtime DESC/feedback surfaces so Codex can execute safely on the main path without unnecessary blackbox source exploration.

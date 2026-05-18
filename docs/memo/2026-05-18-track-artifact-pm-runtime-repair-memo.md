# Track/Artifact PM Runtime Repair Memo

Date: 2026-05-18
Worktree: `/Users/chen/Dev/buddyswitch`
Branch: `main`
Status: repair memo only. No runtime implementation in this memo.

## Summary

The PM buddy regression after the track/artifact merge should not be handled by adding a large PM
prompt.

The fix is to correct a runtime contract mismatch introduced by the merge:

- `track` is the shared collaboration page.
- `artifact` is the readable Markdown content page.
- shared publication must have one closed runtime path.
- tool semantics and response feedback must describe that path accurately.

Current main has a broken split contract where `artifact.create_revision` can claim an artifact is
published to a track without making it visible in `track.open.shared_materials`. A later
`track.add_material` call can then reject the artifact because it is already bound to that track but
not current material. That is a dead path created by inconsistent runtime state and feedback.

## Background

Previous BuddySwitch memos already established the intended layering:

- `AGENTS.md`: short runtime route map and hard boundaries.
- Skills: repeated business workflows and output standards.
- Env tool catalog / semantics: atomic capability meaning, inputs, side effects, return meaning,
  authority, visibility, durability, success, and failure.
- Tool responses: actual effect, state change, durability, recovery, and next valid actions.

The earlier direction was not "write more prompt." It was to make the runtime-visible tool layer and
feedback sufficient for the host to choose and recover correctly.

Relevant prior direction:

- `docs/memo/2026-05-14-env-tool-semantic-contract-memo.md`: decision-critical semantics belong in
  runtime-visible env tool contracts, not only docs, skills, or service code.
- `docs/memo/2026-05-16-env-tool-semantic-clarity-boundary-memo.md`: tool layer explains atomic
  capability semantics; AGENTS stays short; skills own repeated workflows.
- `docs/memo/2026-05-17-track-task-role-rebuild-memo.md`: the shared collaboration path is
  `track.open -> shared_materials -> artifact.get`, with direct material publication to track.
- `docs/memo/2026-05-18-artifact-mini-object-design-memo.md`: artifact is a track-published
  Markdown content page, not a buddy homework record or task-derived object.

## Observed Regression

In a PM buddy session for a landing page request, PM behaved like a generic implementation agent:

- started with context discovery;
- searched source files and repo structure;
- did not use PM-facing product definition skill behavior;
- did not create or publish PM product direction output;
- did not use the expected track/artifact product collaboration path.

This appeared after the track/artifact merge.

The issue is not only skill triggering. The runtime tool path itself now contains contradictory
publication semantics.

## Confirmed Runtime Break

Temporary runtime check on main:

1. Create a track.
2. Call `artifact.create_revision` with:
   - `status="published"`
   - `published_to_track=<track-id>`
3. Open the track.

Observed result:

```json
{
  "artifact_create_ok": true,
  "artifact_published_to_track": "track-direct-envtool",
  "track_open_ok": true,
  "track_shared_materials": []
}
```

Then follow the response guidance and call `track.add_material` for that same artifact.

Observed result:

```json
{
  "followup_ok": false,
  "message": "artifact 'art-followup-r1' is already bound to track 'track-followup' but not as current material; create a new revision instead",
  "track_shared_materials": []
}
```

This proves the current contract can produce an orphan published artifact: artifact state says it is
published to the track, while track state does not expose it as shared material.

## Root Contract Conflict

Current main says multiple incompatible things:

- `framework/contracts/pm.md` says PM publishes collaboration outputs through
  `track.add_material` / `track.add_proof`.
- The same PM contract also says formal PM deliverables use `artifact.create_revision` with
  `published_to_track` when shared.
- `buddyswitch/skills/shared/artifact-tool/SKILL.md` says `artifact.create_revision` creates a
  private draft and shared publication happens via `track.add-material` or `track.add-proof`.
- `buddyswitch/skills/pm/write-prd/SKILL.md` tells PM to use `artifact.create_revision`, then
  verify shared visibility with `track.open` and `artifact.get`.
- `scripts/env/tools/contracts.py` exposes `track.add_material` with legacy `kind/content`, while
  `artifact.create_revision` uses V1 `template/body/published_to_track`.
- `scripts/env/tools/semantics.py` has action-level placeholders for these critical actions:
  empty `use_when`, empty `inputs_explained`, empty `common_failures`, and generic
  `success_means`.

This is not a prompt wording defect. It is a runtime contract and feedback defect.

## Repair Principle

Choose one active publication contract and make every layer match it.

Recommended contract:

```text
artifact.create_revision = create an active-buddy-owned draft/revision content page
track.add_material       = publish that artifact as current shared track material
track.add_proof          = publish that artifact as close proof
track.open               = read the current shared material/proof refs
artifact.get             = read the full body of a readable artifact id
```

Under this contract, `published_to_track` is a persisted artifact field set by track publication.
It must not be a standalone direct-publish input path that bypasses `track.shared_materials`.

## Complete One-Shot Repair List

Handle the following as one coherent repair. Do not split into long-lived dual paths.

1. Unify the only active publication path.
   - Make `track.add_material` / `track.add_proof` the single shared publication entry point.
   - Ensure these actions update both artifact state and track state.
   - Ensure `track.open.shared_materials` and `track.open.close_proof` are the source for shared
     track visibility.

2. Remove the orphan direct-publish path.
   - `artifact.create_revision(published_to_track=...)` must not create a published artifact that is
     absent from the track page.
   - Prefer rejecting `published_to_track` on `artifact.create_revision` unless the implementation
     intentionally makes it call the same track publication logic.
   - Do not keep both direct publish and track publish as active user-facing paths.

3. Fix revision/currentness semantics.
   - Creating a draft revision must not make the current shared track artifact non-current.
   - Replacing current shared material should happen only when `track.add_material` succeeds.
   - Replacing close proof should happen only when `track.add_proof` succeeds.
   - Superseded artifacts must remain traceable, but should not disappear from track history in a way
     that breaks reads or audits.

4. Normalize active payload language.
   - Use Artifact V1 terms: `template` and markdown `body`.
   - Keep `label`, `summary`, and `source_refs` for track display and provenance.
   - Remove active guidance around `kind=prd`, `content.prd`, and legacy `content` payloads.
   - Keep legacy normalization only as compatibility behavior and explicitly test it as legacy.

5. Update tool registry and CLI contract.
   - Align `scripts/env/tools/contracts.py` with the chosen active payloads.
   - Align `scripts/env/client.py` help text and payload expectations.
   - Ensure registry `payload_fields`, preconditions, returns, and permissions match service reality.

6. Rewrite critical runtime semantics.
   - Update `scripts/env/tools/semantics.py` for at least:
     - `track.create`
     - `track.open`
     - `track.add_material`
     - `track.add_proof`
     - `artifact.create_revision`
     - `artifact.get`
   - Fill `use_when`, `do_not_use_when`, `inputs_explained`, `side_effects`, `success_means`, and
     `common_failures` with real atomic semantics.
   - Keep semantics about capabilities and effects, not phrase-triggered workflows.

7. Fix success and rejection feedback.
   - `artifact.create_revision` must not return a next action that leads to rejection.
   - `artifact.create_revision` success must say whether the artifact is draft/private or otherwise
     clearly not shared track material.
   - `track.add_material` success must state both object mutations: artifact publication state and
     track shared material row.
   - `track.add_proof` success must state artifact publication state, track proof row, and proof
     update when applicable.
   - Rejections must preserve no-state-change and name the real correction.

8. Fix PM role contract.
   - Update `framework/contracts/pm.md` so PM has one publication route.
   - PM should own track lifecycle with `track.create`, `track.open`, `track.update_now`, and
     `track.archive`.
   - PM should publish product direction as shared track material/proof through `track.add_material`
     or `track.add_proof`.
   - `artifact.create_revision` should be described only as private draft/revision creation if kept
     as a separate action.
   - Durable output targets should include track objects because PM track state is part of PM output.

9. Fix PM skill behavior without bloating AGENTS.
   - Update `buddyswitch/skills/pm/write-prd/SKILL.md` to cover PM product brief / product direction
     / scope / acceptance output, not only narrow PRD/MVP wording.
   - A landing page request should naturally fit PM product definition behavior.
   - The skill should produce a PM brief or decision artifact through the unified publication path.
   - Do not encode a phrase rule such as "landing page means call X" in AGENTS.

10. Fix shared tool skills.
    - `track-tool` must say that shared publication is a track action.
    - `artifact-tool` must say whether it creates private drafts only or whether it has no direct
      publish responsibility.
    - Both skills must defer action details to `context.get.tool_catalog` and actual response
      feedback.
    - Remove contradictory "publish through artifact" wording from active guidance.

11. Keep `AGENTS.md` short.
    - Do not turn PM AGENTS into a full PM procedure manual.
    - It can continue to say where to begin, where to inspect tool semantics, and which raw-state
      boundaries cannot be bypassed.
    - If needed, add only a short pointer that active buddy skills are available under
      `.agents/skills`.

12. Add regression tests that inspect persisted JSON and env.tool responses.
    - Test that `artifact.create_revision` cannot create an orphan published artifact.
    - Test that `track.add_material` creates or publishes a brief, updates artifact state, writes
      `track.shared_materials`, and makes the body readable by Design/Dev.
    - Test that `track.add_proof` updates close proof and proof update rows.
    - Test that draft revisions do not replace current shared track material until publication.
    - Test that archived tracks reject publication and reads without state mutation.
    - Test that duplicate or already-bound material rejects with actionable feedback and no state
      mutation.
    - Test that PM contract, `write-prd`, `track-tool`, and `artifact-tool` all describe the same
      publication path.
    - Test that semantic rows for critical track/artifact actions are not placeholders.

13. Update end-to-end coverage.
    - PM creates a track.
    - PM publishes a `brief` through the unified publication path.
    - Design opens the track and reads the PM artifact body.
    - Design publishes design material.
    - Dev opens the track and reads PM plus Design material bodies.
    - Test publishes proof.
    - PM updates or closes the track based on shared materials/proof.
    - No step requires task relation, track join, attach/detach, or raw state edits.

14. Clean stale active vocabulary.
    - Remove active guidance for:
      - `kind=prd`
      - `content.prd`
      - direct shared publication via `artifact.create_revision(published_to_track=...)`
      - task-derived artifact visibility
      - `track.join`
      - `track.attach_task`
      - `track.detach_task`
    - Allow old vocabulary only in explicit legacy normalization tests or residue negative tests.

15. Verify PM runtime behavior manually after tests.
    - Start a PM runtime instance.
    - Ask for a product/landing-page PM output.
    - Confirm PM does not treat read-only `projects/app` as the implementation target.
    - Confirm PM writes the expected durable track/artifact state through env tools.
    - Confirm `track.open` exposes the material.
    - Confirm Design/Dev can `artifact.get` the full body.

## Required Test Targets

Add or update tests in the smallest relevant files:

- `tests/test_track_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_env_layer_end_to_end.py`
- `tests/test_turn_integration.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `tests/test_buddy_env_profiles.py`

The tests must inspect actual persisted JSON and env.tool responses. A shallow `ok=true` assertion is
not sufficient.

## Acceptance Criteria

The repair is acceptable only when all of the following are true:

- There is one active shared publication path.
- No env.tool call can create an artifact whose own state says it is published to a track while the
  track page does not expose it as material/proof.
- `artifact.create_revision` feedback cannot point the host into a guaranteed rejection.
- `track.add_material` and `track.add_proof` feedback precisely describe artifact and track
  mutations.
- PM contract, PM skill, track-tool, artifact-tool, registry, service behavior, and tests agree.
- AGENTS remains short and does not become a PM workflow manual.
- PM -> Design -> Dev -> Test main path works without task relation machinery.
- Residue checks do not show forbidden active-runtime vocabulary outside explicit legacy/negative
  tests.

## Non-Goals

- Do not add a prompt-heavy PM procedure manual.
- Do not add phrase routing such as "landing page means use write-prd."
- Do not introduce a second env tool system, workflow engine, semantic v2 layer, or tool router.
- Do not keep both direct artifact publish and track publish as equal active paths.
- Do not weaken tests to accept `ok=true` without inspecting durable state.
- Do not bypass runtime broker boundaries or edit `buddyswitch/objects/**` directly.

## Short Diagnosis

The merge moved the product model toward track-published artifact pages, but the implementation left
publication authority split between artifact and track. The correct repair is to make the runtime
state transition, tool semantics, response feedback, skills, and tests all describe the same single
path.

This is a contract correction, not prompt expansion.

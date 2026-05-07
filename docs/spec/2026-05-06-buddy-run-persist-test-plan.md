# Buddy Run Persist Rebuild Test Plan

**Goal:** Verify that BuddySwitch persistence becomes buddy-level run process management for cross-buddy collaboration, while codex-cli native SKILL execution remains intact.

**Testing Principle:** Tests must start from functional requirements and observable product behavior. Do not construct tests around private helper names, historic implementation branches, or legacy `skill_id` behavior just to make code pass.

---

## Functional Requirements Under Test

FR1. A buddy instance can still expose its active native skills to codex-cli through `.agents/skills/<skill-id>`.

FR2. `prepare` creates one active buddy run context and reserves one run id for an ordinary request.

FR3. `persist` commits one buddy run result without requiring or accepting a selected `skill_id`.

FR4. A buddy run commit can record multiple native skill contributors as audit metadata without making them state owners.

FR5. A buddy run commit can create one or more artifacts using buddy-level `artifact.kind`.

FR6. Artifact kind is validated against the active buddy's collaboration contract, not against native skill metadata.

FR7. Artifact objects, run audits, and receipts expose buddy/run/artifact semantics and do not require canonical `skill_id`.

FR8. A buddy run commit can explicitly mutate track state when the active buddy has the required permission.

FR9. A buddy run commit can update the current task status and summary.

FR10. A buddy run commit can record handoff to another buddy with reason and context.

FR11. Cross-buddy collaboration is readable from track context, track artifact index, related runs, artifacts, and handoff.

FR12. PM can create a track and PRD in one buddy run; Market can later add landing page market research to the same track in another buddy run.

FR13. Invalid buddy run commits fail before writing partial state.

FR14. Legacy skill-level persist entry points, CLI flags, contracts, docs, and tests are removed rather than kept as compatibility.

FR15. Community/imported native skills remain executable contributors inside a buddy, but do not gain persistence ownership.

FR16. A reserved buddy run id is single-use: successful persist commits it exactly once, clears the reservation, and replaying the same context fails without writes.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1 | TG-01 | active buddy native skills are materialized and visible through the public runtime/codex skill loading path, while inactive buddy skills are absent |
| FR2 | TG-02 | prepare returns `ok=true`, active buddy, task id, optional track id, and reserved run envelope |
| FR3 | TG-03 | CLI/function persist succeeds without `skill_id`; providing `--skill-id` is rejected by argument parser |
| FR4 | TG-03 | run audit stores `contributors.skills`; receipt/artifact ownership remains buddy-run |
| FR5 | TG-04 | one commit writes expected artifact ids for each artifact kind |
| FR6 | TG-04 | invalid kind for active buddy fails without writes |
| FR7 | TG-05 | artifact/run/receipt contain `buddy_id`/`kind`/`run_id` and no canonical `skill_id` |
| FR8 | TG-06 | authorized track create/update/advance/archive applies; unauthorized action fails |
| FR9 | TG-06 | task status/summary updates apply only to prepared task |
| FR10 | TG-07 | handoff appears in receipt, run audit, and next state |
| FR11 | TG-08 | downstream buddy context can see previous artifacts and related runs without skill ids |
| FR12 | TG-08 | PM-to-Market landing page flow works on one track |
| FR13 | TG-09 | malformed commits and stale contexts leave state snapshots unchanged |
| FR14 | TG-10 | repo consistency searches fail on old runtime contract strings |
| FR15 | TG-11 | imported skill materializes and can appear as contributor only |
| FR16 | TG-09 | successful persist writes one run audit; replay with same context fails and state is unchanged |

## Test Data Rules

Use product-shaped data:

- PM request: `给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track`
- Market request: `对于 track-id 这样一款产品的landing page，我们想了解这类产品在营销上应该怎么表达和展现，以及目前相关竞品的情况和它们的landing page`
- Track title: `AI Schedule Tool Landing Page`
- PRD artifact kind: `prd`
- Market artifact kind: `market-landing-page-brief`

Do not use fake values whose only purpose is to trigger a private branch. If a negative test needs invalid data, make the invalidity product-meaningful: wrong buddy, unauthorized track action, stale context, invalid artifact kind, malformed handoff, or malformed commit.

## Canonical Commit Fixtures

### PM Buddy Run Commit

```json
{
  "execution_summary": "PM wrote the AI schedule tool landing page PRD and created the delivery track.",
  "working_notes": [
    "The user requested PRD creation and track binding in one PM run."
  ],
  "artifacts": [
    {
      "kind": "prd",
      "title": "AI Schedule Tool Landing Page PRD",
      "summary": "Defines landing page scope, sections, MVP requirements, and acceptance criteria.",
      "content": {
        "problem": "Busy professionals need an AI-assisted way to reduce scheduling overhead.",
        "target_users": ["calendar-heavy professionals", "small team operators"],
        "landing_page_sections": ["hero", "pain points", "AI scheduling value", "use cases", "CTA"],
        "requirements": ["Explain the core promise in the hero", "Show concrete scheduling workflows"],
        "acceptance_criteria": ["A downstream design buddy can derive a page flow from this PRD"]
      }
    }
  ],
  "state_effects": {
    "track": {
      "action": "create",
      "track_id": "track-ai-schedule-landing-page",
      "title": "AI Schedule Tool Landing Page",
      "status": "active",
      "current_buddy": "pm",
      "next_buddy": "market",
      "summary": "Cross-buddy landing page iteration for an AI schedule tool."
    },
    "task": {
      "status": "done",
      "summary": "PM PRD is ready for market positioning research."
    }
  },
  "handoff": {
    "next_buddy": "market",
    "reason": "Market should validate competitor landing page positioning before design.",
    "context": "Use the PRD artifact and track summary as source context."
  },
  "contributors": {
    "skills": ["write-prd", "track-manager"],
    "agents": []
  }
}
```

### Market Buddy Run Commit

```json
{
  "execution_summary": "Market analyzed AI scheduling landing page competitors and recommended positioning angles.",
  "working_notes": [
    "The request referenced the existing PM-created track."
  ],
  "artifacts": [
    {
      "kind": "market-landing-page-brief",
      "title": "AI Schedule Tool Landing Page Market Brief",
      "summary": "Summarizes competitor messaging patterns and recommended landing page expression.",
      "content": {
        "research_question": "How should an AI schedule tool express and present itself on a landing page?",
        "competitor_patterns": ["automation promise", "calendar cleanup", "team coordination"],
        "recommended_angles": ["recover focus time", "reduce back-and-forth scheduling", "trustworthy calendar control"],
        "design_handoff_notes": ["Avoid generic AI productivity language", "Show concrete before/after scheduling moments"]
      }
    }
  ],
  "handoff": {
    "next_buddy": "design",
    "reason": "Design can now combine PRD scope with market positioning.",
    "context": "Use the PRD artifact and market landing page brief on this track."
  },
  "contributors": {
    "skills": ["research-scan", "positioning-copy"],
    "agents": []
  }
}
```

### Single-Fault Invalid Commit Fixtures

Each negative test starts from an otherwise valid PM commit and changes exactly one field:

- Empty summary: set `execution_summary` to `""`.
- Bad working notes: set `working_notes` to `"not a list"`.
- Invalid artifact kind: set first artifact `kind` to `"market-landing-page-brief"` while active buddy is PM.
- Empty artifact title: set first artifact `title` to `""`.
- Bad artifact content: set first artifact `content` to `"not an object"`.
- Bad contributors: set `contributors.skills` to `"write-prd"`.
- Bad handoff buddy: set `handoff.next_buddy` to `"unknown"`.
- Bad handoff reason: set `handoff.reason` to `""`.
- Conflicting next buddy: set `handoff.next_buddy` to `"market"` and `state_effects.track.next_buddy` to `"design"`.

Every single-fault case must assert no artifacts, run audits, task mutations, track mutations, or product session binding updates were written.

## Anti-Cheat Rules

- Do not call private persist helpers directly for product behavior tests; use public `prepare` and `persist` entry points where the product contract is under test.
- Do not keep `skill_id` in artifacts, receipts, or run audits and hide it from assertions.
- Do not make tests pass by accepting both old and new commit shapes.
- Do not create a shim that maps `skill_id` to `artifact.kind`.
- Do not skip native skill materialization tests because persistence no longer uses skill ids.
- Do not construct tests from current helper names; tests should describe buddy collaboration behavior.
- Do not let a failure write an artifact before failing on track or handoff validation.
- Do not infer track mutation from request text; state changes must come from explicit `state_effects`.
- Do not use a market/design/dev buddy to mutate tracks unless its manifest permissions allow the specific action.

## Test Groups

### TG-01: Native Skill Exposure Is Preserved

Requirement: codex-cli native SKILL execution must not be affected by buddy-run persist.

Cases:

1. PM instance materializes only PM skills.
   - Flow: run runtime skill install for buddy `pm`.
   - Expected: `.agents/skills/write-prd` and `.agents/skills/track-manager` exist.
   - Expected: `.agents/skills/research-scan` does not exist.

2. Market instance materializes all market skills.
   - Expected: `research-scan`, `positioning-copy`, `pmf-recon`, `customer-discovery`, `channel-discovery`, and `launch-prep` exist.

3. Active buddy native skills are visible through a public native-loader smoke path.
   - Flow: after materializing PM skills into a runtime workspace, run the available codex-cli/debug prompt or launcher smoke path used by the repo to inspect loaded native skills.
   - Expected: active PM skills are discoverable by the public native skill loading path.
   - Expected: inactive Market skills are not discoverable in the PM runtime workspace.

4. Native skill package instructions no longer tell skills to persist themselves.
   - Expected: search finds no `persist --skill-id` in active `SKILL.md` files.

### TG-02: Prepare Creates Buddy Run Context

Requirement: prepare reserves one active buddy run independent of selected native skill.

Cases:

1. PM ordinary request prepares successfully.
   - Input: PM landing page PRD request.
   - Expected: context contains `active_buddy="pm"`, `current_task_id`, `run_envelope.run_id`, `run_envelope.status="reserved"`.
   - Expected: context has no selected skill packet and no required selected skill id.

2. Market request with existing track prepares successfully.
   - Setup: existing track id in product session binding.
   - Expected: context contains `active_buddy="market"` and `current_track_id` equal to the PM-created track.

3. Switch-prefixed request text prepares as ordinary text.
   - Input: `switch market: do competitor scan` in a PM-locked instance.
   - Expected: context contains `active_buddy="pm"`, exact `request_text`, `current_task_id`, and `run_envelope.status="reserved"`.
   - Expected: context has no selected skill packet, no switch router, no switch recommendation, and no reference switch field.

4. Task/track binding conflict remains rejected.
   - Expected: prepare fails without creating an inconsistent task binding.

### TG-03: Persist API Is Buddy-Level

Requirement: persist accepts buddy run commit and rejects old skill-level API.

Cases:

1. CLI help does not expose `--skill-id`.
   - Flow: run `scripts/turn_runtime.py persist --help`.
   - Expected: help contains `--context` and `--result`.
   - Expected: help does not contain `--skill-id`.

2. Public runtime function persists without skill id.
   - Flow: call `persist_buddy_run(context, result=PM_COMMIT)`.
   - Expected: returns `ok=true`.

3. Old function name is gone.
   - Expected: importing `persist_skill_result` from `turn_runtime` fails or the symbol is absent.

4. Extra `skill_id` top-level commit field is rejected.
   - Input: valid PM commit plus `"skill_id": "write-prd"`.
   - Expected: persist fails before writes.
   - Scope note: this is an explicit negative legacy rejection test; it is the only acceptable use of the literal top-level `skill_id` payload outside contributor audit checks.

5. Contributor skills are accepted only under `contributors.skills`.
   - Input: valid PM commit with `contributors.skills`.
   - Expected: persist succeeds and contributors appear in run audit.

### TG-04: Artifact Kind Persistence

Requirement: artifacts are buddy deliverables keyed by kind.

Cases:

1. PM commit writes a `prd` artifact.
   - Expected: artifact object has `kind="prd"`, `buddy="pm"`, `source_run_id=<run_id>`.
   - Expected: artifact object has no `skill_id` and no `slot`.

2. Market commit writes `market-landing-page-brief`.
   - Expected: artifact kind is accepted for market.

3. PM cannot write market artifact kind.
   - Input: PM commit with `kind="market-landing-page-brief"`.
   - Expected: persist fails before writes.

4. Multiple artifacts in one buddy run are persisted atomically.
   - Input: PM commit with `prd` and `pm-decision`.
   - Expected: both artifacts write with same source run id.
   - Negative variant: second artifact has invalid kind; expected no artifacts are written.

5. Artifact revisions remain kind-scoped.
   - Flow: persist two PM commits with `kind="prd"` for same task.
   - Expected: latest artifact is current; previous artifact is superseded.

### TG-05: Receipt And Run Audit Are Buddy-Centered

Requirement: downstream users read buddy process state, not skill ownership.

Cases:

1. Receipt contains buddy identity.
   - Expected: receipt has `buddy_id="pm"`, `run_id`, `artifact_ids`, `task_id`, and `handoff`.
   - For track-bound runs, `track_id` is required in receipt, run audit, every artifact's task binding, and the track artifact index.

2. Receipt has no skill identity.
   - Expected: receipt lacks `skill_id`.

3. Run audit contains process fields.
   - Expected: run audit contains `buddy_id`, `execution_summary`, `working_notes`, `artifact_ids`, `state_effects`, `handoff`, `contributors`, and `writes`.

4. Run audit has no canonical `skill_id`.
   - Expected: `skill_id` is absent.

5. Related runs remain available.
   - Expected: second run on same task reports previous run id in `related_run_ids`.

### TG-06: State Effects

Requirement: buddy run commit manages project iteration state explicitly.

Cases:

1. PM creates a track.
   - Input: PM commit with `state_effects.track.action="create"`.
   - Expected: track exists, task is bound to track, receipt has track id/title/action.

2. PM updates a track.
   - Input: PM commit with `state_effects.track.action="update"` and summary patch.
   - Expected: existing track summary changes.

3. PM advances a track to another buddy.
   - Input: PM commit with `state_effects.track.action="advance"` and `next_buddy="market"`.
   - Expected: next state/handoff reflects market.

4. PM archives a track.
   - Input: PM commit with `state_effects.track.action="archive"`.
   - Expected: existing track status becomes `archived`.

5. Unauthorized track action fails.
   - Setup: buddy without `track.create` attempts track create.
   - Expected: persist fails before writes.

6. Invalid next buddy fails.
   - Input: `next_buddy="unknown"`.
   - Expected: persist fails before writes.

7. Task status update applies to current task only.
   - Input: `state_effects.task.status="done"`.
   - Expected: prepared task status changes.
   - Negative: commit attempts to reference another task; expected failure because task effects have no external task id.

### TG-07: Handoff

Requirement: persist provides explicit collaboration handoff.

Cases:

1. PM handoff to market is saved.
   - Expected: receipt includes `handoff.next_buddy="market"`.
   - Expected: run audit includes handoff reason/context.

2. Market handoff to design is saved.
   - Expected: receipt includes `handoff.next_buddy="design"`.

3. Handoff to unknown buddy fails before writes.

4. Empty handoff reason fails before writes.

5. Handoff without artifacts is allowed only if it is the explicit durable collaboration signal.
   - Expected: commit with summary + handoff succeeds.
   - Expected: commit with summary only fails.

### TG-08: PM To Market Collaboration On One Track

Requirement: different buddies can iterate on the same project track using buddy-level run commits.

Cases:

1. PM run creates PRD and track.
   - Use PM fixture.
   - Expected: one track, one PM task, one `prd` artifact, one PM run audit.

2. Market run uses the PM-created track.
   - Use Market fixture with current track binding from PM receipt.
   - Expected: no new track is created.
   - Expected: one Market task is bound to the existing track.
   - Expected: one `market-landing-page-brief` artifact.

3. Track context exposes both buddy contributions.
   - Expected: track task list contains PM and Market task ids.
   - Expected: track artifact index contains `prd` and `market-landing-page-brief`.
   - Expected: Market run related context can reference PM artifact without skill id.
   - Expected: track context exposes source buddy ids and source run ids for both artifacts.

4. Design can prepare on the same track after market handoff.
   - Flow: start/prepare design instance with current track id.
   - Expected: design context includes the same `track_id`.
   - Expected: design context includes PM PRD summary/content and Market brief summary/content.
   - Expected: design context includes source buddy/run ids for both artifacts.
   - Expected: design context or related run context exposes Market handoff `next_buddy="design"`, reason, and context.
   - Expected: design does not need any skill id to understand the handoff.

### TG-09: Failure Atomicity

Requirement: invalid persist attempts cannot leave partial collaboration state.

Cases:

1. Invalid artifact kind fails with no artifact, run audit, task mutation, or track mutation.

2. Valid artifact plus invalid track effect fails with no artifact.

3. Valid artifact plus invalid handoff fails with no artifact.

4. Stale context fails with no writes.

5. Reserved run id already used fails with no writes.
   - Flow: persist a valid commit once, then call persist again with the same prepared context.
   - Expected: second persist fails because the run id is already committed.
   - Expected: artifact list, run list, task object, track object, and product session binding are unchanged after the failed replay.

6. Product-mode context buddy mismatch fails with no writes.

For every case:

- snapshot task, track, artifact list, and run list before persist;
- run persist;
- assert snapshot is unchanged.

### TG-10: Historical Residue Removal

Requirement: old skill-level persist is gone, not hidden.

Search checks:

```bash
rg -n "persist-skill-result|persist --skill-id|same native skill_id|selected skill_id|skill_id is required" buddyswitch scripts tools framework tests
```

Expected: no active code, docs, or accepted fixtures contain old persist semantics. Matches are allowed only inside explicit negative rejection tests that prove legacy `skill_id` payloads are rejected.

```bash
rg -n "persist_skill_result|_persist_skill_result|_persist_artifact_skill|persist_skill_result_request" scripts tests
```

Expected: no matches.

```bash
rg -n "\"skill_id\"|artifact\\.skill_id|receipt\\[\"skill_id\"\\]" scripts tests framework tools buddyswitch
```

Expected: no canonical artifact, receipt, or run audit skill ownership. Matches are allowed only for `contributors.skills` assertions and explicit negative legacy rejection tests.

### TG-11: Imported Skill Contributor Behavior

Requirement: imported native skills remain useful but do not own persistence.

Cases:

1. Imported dev skill materializes.
   - Expected: `.agents/skills/dev-summary` exists for dev.

2. Imported dev skill can be listed in contributors.
   - Input: dev buddy run commit with `contributors.skills=["dev-summary"]`.
   - Expected: persist succeeds if artifact kind belongs to dev.

3. Imported dev skill cannot bypass buddy artifact kinds.
   - Input: dev commit with artifact kind equal to imported skill id when not registered as a dev artifact kind.
   - Expected: persist fails before writes.

4. Importer can optionally register a buddy artifact kind distinct from the skill id.
   - Flow: import skill `dev-summary` with `artifact_kind="community-dev-report"`.
   - Expected: manifest buddy artifact kinds include `community-dev-report`.
   - Expected: persist can write `kind="community-dev-report"` as dev buddy output.
   - Expected: artifact/run/receipt ownership remains buddy/run based; `dev-summary` appears only under `contributors.skills`.

## Verification Commands

Run from:

```bash
cd /Users/chen/Dev/buddyswitch/.worktrees/dev0210
```

Focused runtime suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_manifest_v2.py tests/test_env_store_v2.py tests/test_turn_runtime.py tests/test_turn_integration.py tests/test_runtime_skills.py -q
```

Launcher and repo consistency:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_repo_consistency.py tests/test_skill_creator_importer.py -q
```

Debug and cleanup regressions:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_debug_apis.py tests/test_cleanup_system.py -q
```

Compile changed runtime scripts:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env_manifest.py scripts/env_store.py scripts/runtime_kernel/persist.py scripts/runtime_store/projections.py scripts/skill_creator_importer.py scripts/turn_runtime.py scripts/runtime_skills.py
```

Residue search:

```bash
rg -n "persist-skill-result|persist --skill-id|same native skill_id|selected skill_id|skill_id is required|persist_skill_result|_persist_skill_result|_persist_artifact_skill|persist_skill_result_request" buddyswitch scripts tools framework tests
```

Expected: no active legacy persist semantics.

## Definition Of Tested

- A buddy run persists without skill id.
- Multi-skill contributors are audit-only.
- Artifacts are keyed by buddy-level kind.
- PM-to-Market collaboration works on one track.
- Handoff is explicit and readable by the next buddy.
- Invalid commits do not leave partial writes.
- Codex native skill materialization remains intact.
- Legacy skill-level persist is removed, not compatibility-wrapped.

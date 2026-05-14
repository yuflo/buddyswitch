# Normal Tool Layer Upgrade Proposal

Date: 2026-05-14
Worktree: `dev2258`
Seed memo: `docs/memo/2026-05-13-cross-buddy-artifact-access-memo.md`
Brief: `docs/memo/2026-05-14-track-task-artifact-tooling-upgrade-subagent-brief.md`
Status: proposal and implementation-planning handoff only. No source implementation in this phase.

## Principle

The tool layer must be understandable and usable by a normal person and by an LLM host without learning runtime internals first.

The core rule is direct-id access:

```text
See a track_id, use track.get.
See a task_id, use task.get.
See an artifact_id, use artifact.get.
If access fails, that same tool explains why and what to do next.
```

Everything else is subordinate to that rule.

Core target commands:

- `track.list`
- `track.get --track-id <track-id>`
- `artifact.list --track-id <track-id>`
- `artifact.get --artifact-id <artifact-id>`
- `track.join --track-id <track-id>`
- `task.list`
- `task.get --task-id <task-id>`
- `handoff.list`
- `handoff.validate`
- `handoff.create`
- `run.validate_result`
- `run.commit`

The environment can still have rich state, runtime snapshots, skills, and structured feedback. Those layers must not hide the simple path. They should make the obvious path safer, not force users through internal state concepts before reading an artifact id they can already see.

## What Was Wrong With The Previous Proposal

The previous proposal diagnosed the right product failure but routed the fix through the wrong concept.

The failure was:

```text
Dev could see PM PRD and Design handoff artifact summaries,
but could not naturally read the full source artifacts.
```

The previous solution made `context` the main artifact reading surface. That is backwards. A user who has an `artifact_id` should not need to know about runtime snapshots, relation explain actions, task selection internals, or source availability validators before trying to read it.

Rejected from the target design:

- `context.get_track_artifacts`
- `context.inspect_track_outputs`
- `context.explain_track_access`
- `context.validate_sources_available` as part of the artifact reading path
- `task.create_for_track` as the user-facing join concept
- separate `explain_*` tools as the normal recovery path

The previous proposal also put too much burden on skills and AGENTS guidance. Skills can teach workflows. AGENTS can state boundaries. Neither should compensate for a tool layer that cannot answer a direct read request.

## Target User Experience

The target surface should feel like this:

```bash
python3 scripts/env/client.py track list
python3 scripts/env/client.py track get --track-id track-landing
python3 scripts/env/client.py artifact list --track-id track-landing
python3 scripts/env/client.py artifact get --artifact-id art-pm-prd-r1
python3 scripts/env/client.py track join --track-id track-landing
python3 scripts/env/client.py task get --task-id task-dev-landing
python3 scripts/env/client.py handoff list --track-id track-landing
python3 scripts/env/client.py run validate-result --track-id track-landing
python3 scripts/env/client.py run commit --run-id run-dev-r1
```

Normal path for a receiving buddy:

1. `track.list` finds relevant tracks.
2. `track.get --track-id <track-id>` shows tasks and current artifact summaries, including artifact ids.
3. `artifact.get --artifact-id <artifact-id>` reads a legal artifact directly.
4. If the buddy has no valid relation yet, `artifact.get` rejects without content and points to `track.join` or handoff recovery.
5. `track.join --track-id <track-id>` joins the active buddy to the track and selects the active buddy's track task as current work.
6. The same `artifact.get --artifact-id <artifact-id>` now reads the related current source artifact.

The host should not need any `context.*` read action to move from `track.get` to full artifact content.

## Tool Surface

### track

Target actions:

- `track.list`
- `track.get --track-id <track-id>`
- `track.join --track-id <track-id>`

`track.list` should return candidate tracks ordered by relevance to the active buddy. It should include each track id, title, lifecycle status, current buddy, next buddy, latest handoff summary, active-buddy relation, and a short next command.

`track.get` is the main orientation surface. It returns:

- track metadata;
- lifecycle fields;
- active-buddy relation to the track;
- tasks on the track;
- recent handoffs;
- current artifact summaries;
- `artifact_id`;
- `kind`;
- `title`;
- `summary`;
- `source_buddy`;
- `source_task_id`;
- `source_run_id`;
- `currentness`;
- `readable_by_current_buddy`;
- shortest next step when an artifact is not currently readable.

`track.get` must not return foreign full artifact content. It must still return artifact ids because `artifact.get` is the natural next command.

Example artifact row:

```json
{
  "artifact_id": "art-pm-prd-r1",
  "kind": "prd",
  "title": "Landing Page PRD",
  "summary": "Approved scope for the landing page build.",
  "source_buddy": "pm",
  "source_task_id": "task-pm-prd",
  "source_run_id": "run-pm-prd-r1",
  "currentness": "current",
  "readable_by_current_buddy": true,
  "next_action": {
    "tool": "artifact",
    "action": "get",
    "args": {"artifact_id": "art-pm-prd-r1"}
  }
}
```

If an artifact is not readable:

```json
{
  "artifact_id": "art-design-handoff-r1",
  "kind": "design-handoff",
  "summary": "Design guidance exists, but the active buddy is not related yet.",
  "source_buddy": "design",
  "source_task_id": "task-design-landing",
  "source_run_id": "run-design-r1",
  "currentness": "current",
  "readable_by_current_buddy": false,
  "next_action": {
    "tool": "track",
    "action": "join",
    "args": {"track_id": "track-landing"},
    "why": "Join the track to create an active-buddy task relation."
  }
}
```

`track.join` replaces internal-flavored preparation names. Normal people join a track. Implementation may create, attach, and select a task, but that is an internal detail.

`track.join` behavior:

- requires `track_id`;
- creates an active-buddy-owned task on that track when one does not already exist;
- if exactly one active-buddy task already exists on the track, reuses it;
- selects the created or reused task as the active buddy's current task for the track;
- returns `task_id`, current task state, active-buddy relation, readable artifact count, and next command hints;
- does not mutate PM lifecycle fields such as status, current buddy, next buddy, or track ownership;
- if multiple active-buddy tasks exist on the track, rejects and asks for an explicit `--task-id`.

Selecting current work is part of joining. After `track.join`, the user should be able to keep using direct ids without learning a separate internal state concept. Do not add an inspect-only join flag unless a real repeated workflow proves that need.

### artifact

Target actions:

- `artifact.list --track-id <track-id>`
- `artifact.get --artifact-id <artifact-id>`

`artifact.list --track-id` is the normal way to inspect a track's artifact outputs by id.

It returns summaries only:

- `track_id`;
- active-buddy relation to the track;
- artifact ids;
- kind;
- title;
- summary;
- source buddy;
- source task id;
- source run id;
- revision;
- currentness;
- `readable_by_current_buddy`;
- next action for each row.

It does not return full content.

`artifact.get` is the direct full-content read entry point. If the active buddy is allowed to read the artifact, this tool returns the body. If not, this tool returns the reason, boundary, missing preconditions, and next action without leaking content.

Allowed full reads:

- artifact belongs to a task owned by the active buddy;
- artifact is a current artifact on a track where the active buddy has a reasonable relation.

Reasonable track relations:

- `pm_lifecycle_owner`: active buddy is PM;
- `participant`: active buddy already has a task on the track;
- `current_buddy`: `track.current_buddy == active_buddy`;
- `next_buddy`: `track.next_buddy == active_buddy`;
- `handoff_recipient`: latest relevant handoff recipient is the active buddy.

Blocked reads:

- unrelated buddy;
- stale or non-current foreign artifact;
- artifact exists but cannot be associated to an active-buddy task or related track;
- archived or invalid track relation;
- malformed or unknown artifact id.

Every blocked body read must include `no_content_leak: true`.

### task

Target actions:

- `task.list`
- `task.get --task-id <task-id>`

`task.list` should show active-buddy tasks and relevant track-linked tasks the active buddy can orient around. It should return task ids, track ids, owner buddy, status, current artifact ids, and current-work status.

`task.get` should make a visible task id useful:

- task metadata;
- owner buddy;
- track associations;
- active-buddy relation;
- current artifacts as summaries with artifact ids;
- whether each artifact is readable by the current buddy;
- next command hints.

`task.get` should not become the full artifact body reader. It points to `artifact.get`.

### handoff

Target actions:

- `handoff.list`
- `handoff.validate`
- `handoff.create`

`handoff.list` should support `--track-id` and return recent handoffs, source buddy, target buddy, source task, source run, referenced artifact ids, status, and whether any handoff makes the active buddy a read-authorized recipient.

`handoff.validate` checks whether a proposed handoff is coherent before creation or commit:

- source task belongs to active buddy;
- source artifacts belong to active buddy;
- target buddy is valid;
- track exists;
- handoff does not imply hidden lifecycle mutation;
- referenced source artifacts are current or explicitly marked as historical.

`handoff.create` creates an explicit handoff record. It should not be a workflow router and should not silently advance track lifecycle. PM lifecycle routing remains explicit through PM-owned track tools.

### run

Target actions:

- `run.validate_result`
- `run.commit`

`run.validate_result` should validate result coherence before commit:

- declared task id resolves;
- declared track id resolves;
- declared artifact ids exist;
- declared artifact ids are writable or readable under the right rule;
- handoff payloads reference valid task, track, buddy, run, and artifact ids;
- payload does not try retired or hidden lifecycle mutation fields;
- no raw runtime state edits are implied.

`run.commit` remains the audit commit path. It commits declared results. It must not become a hidden place for lifecycle routing, current-task repair, or permission repair.

### context

`context` remains useful, but not as the primary artifact read API.

Allowed role:

- prepare/runtime snapshot;
- bulk context projection for a turn;
- environment summary;
- available tool descriptions;
- active task facts;
- candidate track/task/artifact summaries.

Not allowed as the target artifact read chain:

- no `context.get_track_artifacts`;
- no `context.inspect_track_outputs`;
- no `context.explain_track_access`;
- no `context.validate_sources_available` as a gate before reading artifact content.

Prepared context may project summaries or already-authorized runtime snapshots for convenience. That projection is not the direct user/LLM read API and must not be required before reading a visible artifact id. The direct API remains `artifact.get --artifact-id <artifact-id>`.

## Read Rules

### Summary Reads

Summary reads are allowed through `track.get`, `artifact.list --track-id`, `task.get`, and `handoff.list` when the tool can safely orient the active buddy without exposing full foreign bodies.

Summary rows may include:

- ids;
- titles;
- kinds;
- brief summaries;
- source buddy;
- source task id;
- source run id;
- currentness;
- readable flag;
- next action.

Summary rows must not include foreign full `content`.

### Full Artifact Reads

`artifact.get --artifact-id <artifact-id>` decides full content access.

Decision order:

1. Resolve the artifact id.
2. If the artifact belongs to an active-buddy-owned task, allow full content.
3. Else find current track associations for the artifact.
4. If the artifact is a current artifact on a track where the active buddy has a reasonable relation, allow full content.
5. Otherwise reject with no content leak and actionable recovery.

The allowed relation set is intentionally small:

- PM lifecycle owner;
- active-buddy task on the track;
- active buddy is current buddy;
- active buddy is next buddy;
- latest handoff recipient is active buddy.

Relation-wide historical artifact browsing is out of scope. Foreign full reads should default to current track artifacts because the core product need is reading current source material before doing work.

### Rejections

Artifact body rejections must not leak content through error messages, summaries, previews, stack traces, source paths, or partial payloads.

A rejection should be useful anyway. It must say:

- why the read failed;
- which permission boundary blocked it;
- what relation was detected;
- what preconditions are missing;
- whether content was withheld;
- what commands can move the user forward.

## Write Rules

Write tools should remain direct and explicit.

`track.join`:

- may create an active-buddy task;
- may attach it to the target track;
- selects it as current work for the active buddy;
- must not mutate PM lifecycle fields.

Artifact writes:

- active buddy writes only to active-buddy-owned tasks;
- payload validation happens before revision creation;
- artifact metadata updates remain scoped to owned artifacts;
- foreign artifacts are read sources, not write targets.

Handoff writes:

- `handoff.create` records an explicit handoff;
- `handoff.validate` should be cheap and read-only;
- handoff creation must not silently rewrite track lifecycle fields.

Run writes:

- `run.validate_result` is the preflight;
- `run.commit` records the result;
- commit should not repair missing task/track/artifact relations.

No tool should recommend editing `buddyswitch/objects/**`, `buddyswitch/content/runs/**`, or `runs/raw/**` as a recovery path.

## Feedback Contract

Do not create normal-path `explain_*` tools. Put explanation inside the tool that failed.

This applies to reads as well as writes. If `track.get`, `task.get`, `artifact.list`, or `artifact.get` cannot return the requested result, that same response should explain the blocker and the shortest safe next command.

Every collaboration-critical failure should include:

- `ok`;
- `tool`;
- `action`;
- active buddy;
- target id;
- `why`;
- `permission_boundary`;
- `relation`;
- `missing_preconditions`;
- `next_actions`;
- `command_hint`;
- `no_content_leak: true` when artifact body content was requested and withheld.

Example `artifact.get` rejection:

```json
{
  "ok": false,
  "tool": "artifact",
  "action": "artifact.get",
  "active_buddy": "dev",
  "artifact_id": "art-design-handoff-r1",
  "why": "This artifact belongs to a track you have not joined and that has not been handed off to you.",
  "permission_boundary": "artifact.track_relation",
  "relation": "none",
  "missing_preconditions": [
    "active buddy must have a task on the track, be current or next buddy, be PM, or be the latest handoff recipient"
  ],
  "no_content_leak": true,
  "next_actions": [
    {
      "tool": "track",
      "action": "join",
      "args": {"track_id": "track-landing"}
    },
    {
      "tool": "handoff",
      "action": "list",
      "args": {"track_id": "track-landing"}
    }
  ],
  "command_hint": "python3 scripts/env/client.py track join --track-id track-landing"
}
```

Example `track.join` success:

```json
{
  "ok": true,
  "tool": "track",
  "action": "track.join",
  "active_buddy": "dev",
  "track_id": "track-landing",
  "task_id": "task-dev-landing",
  "created_task": true,
  "current_task_selected": true,
  "relation": "participant",
  "readable_artifact_count": 2,
  "next_actions": [
    {
      "tool": "artifact",
      "action": "get",
      "args": {"artifact_id": "art-pm-prd-r1"}
    }
  ],
  "command_hint": "python3 scripts/env/client.py artifact get --artifact-id art-pm-prd-r1"
}
```

Feedback quality is part of the product. A rejection that only says "permission denied" is not acceptable for this layer.

## Skills And AGENTS

AGENTS guidance should stay short:

```text
Use the env tool layer to read and write runtime state. Do not read or edit raw runtime state files.
If you see a track_id, task_id, or artifact_id, use track.get, task.get, or artifact.get.
Do not claim artifact content was read unless artifact.get returned the full body for that artifact id.
```

Skills should teach workflow, not compensate for bad tools.

Shared skill direction:

- `track-tool`: teach track discovery, `track.get`, `artifact.list --track-id`, and `track.join`;
- `artifact-tool`: teach `artifact.get` as the full-content entry point and how to interpret no-leak rejection feedback;
- `task-tool`: teach task identity, active work, and `task.get`, not internal state setup as a prerequisite concept;
- handoff/run guidance: teach validation and commit checks.

Do not make skills explain a complex internal route for normal artifact reads. If a skill is required to understand how to read an artifact id, the tool layer has failed.

## Implementation Slices

### Slice 0: Lock The Normal Contract

Goal: establish tests and response contracts before broad implementation.

Scope:

- define canonical response fields for `track.get`, `artifact.list`, `artifact.get`, `task.get`, `track.join`, `handoff.*`, and `run.*`;
- add no-leak response assertions for blocked artifact body reads;
- ensure command hints never point to raw runtime state.

Proof:

- contract tests fail on missing ids, missing readable flags, missing no-leak flags, or invalid next actions.

### Slice 1: Track And Artifact Summary Surfaces

Goal: make discovery naturally lead to artifact ids.

Scope:

- strengthen `track.get` artifact rows;
- add `artifact.list --track-id`;
- ensure both surfaces return readable flags and next actions;
- keep full foreign content out of both surfaces.

Proof:

- `track.get` returns current artifact ids for PM PRD and Design handoff;
- `artifact.list --track-id` returns the same ids and readable flags;
- neither response contains foreign full content.

### Slice 2: Direct Relation-Aware artifact.get

Goal: make `artifact.get` the full-content read entry point.

Scope:

- resolve artifact ownership;
- resolve current track associations;
- compute the reasonable relation set;
- allow full content for owned artifacts and related current track artifacts;
- reject unrelated reads with no content leak and recovery feedback.

Proof:

- active-buddy-owned artifact reads succeed;
- PM lifecycle owner reads current track artifacts;
- participant/current/next/latest-handoff recipient reads succeed;
- unrelated buddy reads reject without content.

### Slice 3: track.join

Goal: replace multi-step internal setup knowledge with a normal join action.

Scope:

- add `track.join --track-id`;
- create or reuse an active-buddy task;
- attach the task to the track;
- select that task as current work;
- preserve PM lifecycle fields.

Proof:

- after `track.join`, `artifact.get` can read current track artifacts;
- lifecycle fields are unchanged;
- repeated join is idempotent when exactly one active-buddy task exists;
- ambiguous existing tasks reject with a clear `--task-id` recovery.

### Slice 4: Handoff And Run Coherence

Goal: keep collaboration writes explicit and auditable.

Scope:

- add or strengthen `handoff.list`, `handoff.validate`, and `handoff.create`;
- strengthen `run.validate_result`;
- keep `run.commit` audit-focused;
- ensure validation errors include concrete next actions.

Proof:

- invalid handoff associations reject before commit;
- valid handoff recipient relation allows `artifact.get`;
- run validation catches unknown ids and retired mutation fields.

### Slice 5: Context, Skills, And AGENTS Cleanup

Goal: remove context-centric artifact reading from the proposal and guidance.

Scope:

- keep context as prepare/runtime snapshot and bulk projection only;
- update shared skills to point to direct-id tools;
- keep AGENTS short;
- remove guidance that teaches context read actions as the artifact body path.

Proof:

- docs and skill checks do not present context read actions as the target artifact read flow;
- Dev workflow is documented as `track.get -> artifact.get`, optionally `track.join -> artifact.get`.

## Tests

The tests should prove normal usage, not internal theory.

Focused regression:

1. Seed a track with current PM PRD and Design handoff artifacts.
2. Start Dev with no ownership of those artifacts.
3. `track.get --track-id <track-id>` returns both `artifact_id` values, source metadata, currentness, and readable flags.
4. `artifact.list --track-id <track-id>` returns the same ids and readable flags without full content.
5. `artifact.get --artifact-id <pm-prd-artifact-id>` succeeds when Dev has a valid relation.
6. `artifact.get --artifact-id <foreign-unrelated-artifact-id>` rejects with `no_content_leak: true`, `permission_boundary`, `relation`, `missing_preconditions`, `next_actions`, and `command_hint`.
7. `track.join --track-id <track-id>` creates or reuses a Dev task and selects it as current work.
8. After `track.join`, Dev can use `artifact.get --artifact-id <pm-prd-artifact-id>` and `artifact.get --artifact-id <design-handoff-artifact-id>` to read full content.
9. Dev can complete source intake from `track.get -> artifact.get` without any context read action.
10. Prepared context may still project runtime snapshots, but tests must not count that as the direct artifact read API.

Contract tests:

- every artifact body rejection has `no_content_leak: true`;
- no rejection includes foreign `content`, preview, or partial body;
- every `next_actions[*].tool/action` exists in the registry;
- every `command_hint` uses `scripts/env/client.py`, not raw state files;
- `track.get`, `artifact.list`, and `task.get` include ids needed for natural next commands;
- `track.join` does not mutate PM lifecycle fields;
- `run.validate_result` rejects invalid task, track, artifact, handoff, and retired mutation payloads.

End-to-end acceptance:

- PM creates PRD artifact on a track.
- Design reads PRD through `artifact.get`, writes design handoff, creates handoff to Dev.
- Dev uses `track.get`, sees PRD and design artifact ids, reads both through `artifact.get`, implements, writes own artifact, and hands off to Test.
- Test reads Dev output and upstream sources through direct artifact ids.
- No step requires a context-specific artifact read action.

Suggested verification commands for implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_context_binding_env_tool.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_layer_end_to_end.py tests/test_run_env_tool.py tests/test_env_tool_response_contract.py -q
```

## Non-Goals

- Do not add `context.get_track_artifacts`.
- Do not add `context.inspect_track_outputs`.
- Do not add `context.explain_track_access`.
- Do not make `context.validate_sources_available` part of artifact reading.
- Do not create separate explain tools as the normal path.
- Do not require users or LLMs to understand task-selection internals before reading a visible artifact id.
- Do not put full foreign artifact content in `track.get`.
- Do not open unrelated global `artifact.get` reads.
- Do not add a generic ACL engine.
- Do not add workflow routers, hidden orchestration, event buses, DSLs, plugin systems, or compatibility alias layers.
- Do not make AGENTS a procedure manual.
- Do not make skills explain around broken tools.
- Do not recommend raw runtime state reads or edits.

## Migration From Current Proposal

Replace the previous target surface directly:

| Previous proposal target | New target |
| --- | --- |
| `context.get_track_artifacts` | `artifact.get --artifact-id <artifact-id>` |
| `context.inspect_track_outputs` | `artifact.list --track-id <track-id>` |
| `context.explain_track_access` | failure feedback inside `artifact.get`, `track.get`, and `track.join` |
| `context.validate_sources_available` | `run.validate_result` over declared ids and normal tool responses |
| `task.create_for_track` | `track.join --track-id <track-id>` |
| source-intake skill route through context | `track.get -> artifact.get`, with `track.join` only when relation is missing |

Do not preserve the old context actions as compatibility aliases in the target design. This is a rebuild-forward change. The shorter path is the product improvement.

Implementation planning should start from tests that encode the normal user flow:

```text
track.get returns artifact_id
artifact.get reads legal artifact
artifact.get blocks illegal artifact without leak
artifact.list --track-id shows ids and readable flags
track.join makes artifact.get work for the track
```

That is the bottleneck. Solve that first.

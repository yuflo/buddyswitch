# Artifact Context Relation Human-Use Test Plan

Date: 2026-05-21

Scope document: `docs/spec/2026-05-21-artifact-context-relation-human-use-scope.md`

## Goal

Prove BuddySwitch supports human and buddy orientation around artifacts without introducing complex
filtering, new material objects, or a relation engine.

The tests must start from user-facing requirements:

- a human can find readable materials without knowing ids;
- a human can enter a track and see the compact working surface;
- a human can open an artifact and trace why it matters;
- unreadable private or archived state does not leak;
- list/context/relation surfaces stay compact.

## Task Confirmation

The bottleneck is not storage. Artifacts already exist. The bottleneck is human use:

- `artifact.get` requires a known id;
- `context.summarize` does not yet expose all first-pass working signals;
- artifact reads do not expose incoming refs or lineage.

The repair is:

```text
artifact.list
context.summarize candidate_artifacts/open_comment_threads/recent_updates
artifact.get relation_summary
```

The repair must be forward-only:

- no `artifact.index` or search alias;
- no transitional compatibility paths;
- no `relation` object/tool;
- no `insight`, `experiment`, `roadmap`, `review`, or `approval` env tool objects;
- no complex filter DSL;
- no body full-text search.

## Functional Requirements

### Artifact Discovery

R1. `artifact` exposes exactly one new read action: `list`.

R2. `artifact.list` is discoverable through the black-box runtime registry, `context.get`, operation
semantics, and CLI/status surfaces.

R3. `artifact.list` accepts only these filters: `track_id`, `created_by`, `template`, `status`, `q`,
and `limit`.

R4. Unsupported fields reject with canonical tool rejection fields and no state change.

R5. Invalid filter values reject:

- blank `track_id`;
- unknown `created_by`;
- unknown `template`;
- unknown `status`;
- non-string `q`;
- non-positive or non-integer `limit`.

R6. `artifact.list` applies read visibility before filters. Foreign private drafts and artifacts
behind archived track boundaries must not leak.

R7. Active buddy can list own private drafts.

R8. Active buddy can list readable published current material, close proof, and readable historical
published material/proof on non-archived tracks.

R9. `track_id` filters to artifacts connected to that track and rejects missing or archived tracks
through the existing track lifecycle boundary.

R10. `q` searches only `title` and `summary`, case-insensitively. It must not match artifact `body`.

R11. `limit` bounds returned rows deterministically. Default limit is 20.

R12. Rows are summary-only and never include `body`.

R13. Rows include material orientation fields: `artifact_id`, `title`, `summary`, `template`,
`status`, `currentness`, `relation`, `created_by`, `authors`, `published_to_track`, `revision`,
`supersedes_artifact_id`, `source_refs_summary`, comment counts, and `updated_at`.

R14. `artifact.list` is read-only: no artifact, track, request, comment, task, message, or buddybox
state changes.

### Context Summarize

R15. `context.summarize` remains compact and read-only.

R16. `context.summarize` never includes full `tool_catalog`, full `operation_semantics`, JSON Schema
payloads, artifact `body`, full comment thread bodies, or full timeline history.

R17. `context.summarize` includes `candidate_artifacts` using the same summary-only shape and
visibility rules as `artifact.list`.

R18. `context.summarize` includes `candidate_requests` for visible requests. Existing request
behavior must remain intact.

R19. `context.summarize` includes `open_comment_threads` as unresolved thread summaries for visible
track/artifact targets.

R20. `context.summarize` includes `recent_updates` as compact latest update rows for visible tracks.

R21. `track_id` filter narrows candidate tracks, candidate artifacts, candidate requests, open
comment threads, and recent updates to the selected readable track.

R22. Empty workspace or no matching filter returns deterministic empty arrays and counts, not
exceptions.

R23. `current_context_summary` includes counts/readiness signals for tracks, artifacts, requests,
open comment threads, and recent updates.

R24. `tool_affordances` remains compact and points to follow-up tools such as `artifact.get`,
`artifact.list`, `request.get`, `comment.list`, and `track.open`.

### Relation Summary / Backlinks

R25. `artifact.get` includes `relation_summary` for readable artifacts.

R26. `relation_summary.publication` reports the artifact read relation and currentness:

```text
owner, track_material, track_proof, track_history
draft, current, proof, superseded
```

R27. `relation_summary.lineage` reports the artifact's `supersedes_artifact_id` and visible
`superseded_by_artifact_ids`.

R28. `relation_summary.incoming_refs.source_ref_by_artifacts` lists visible artifacts whose
`source_refs` reference the current artifact.

R29. `relation_summary.incoming_refs.target_ref_by_requests` lists visible requests whose
`target_refs` reference the current artifact.

R30. `relation_summary.incoming_refs.result_ref_by_requests` lists visible requests whose
`result_refs` reference the current artifact.

R31. `relation_summary.incoming_refs.track_update_refs` lists visible track updates whose `refs`
reference the current artifact.

R32. `relation_summary.incoming_refs.comment_ids` lists visible comments on the artifact, including
`artifact_section` comments normalized to the artifact target.

R33. All incoming relation rows are lightweight. They must not include full artifact bodies, full
request summaries when not needed, full comment content, or private buddybox content.

R34. Unreadable incoming refs are omitted without leaking their ids, titles, or counts.

R35. `artifact.list` may include lightweight relation counts, but must not include full
`relation_summary` rows.

R36. No persisted relation files or new relation runtime object directories are created.

### Regression And Boundary

R37. Existing `request` and PM-only `comment.resolve` focused tests remain green.

R38. Existing `artifact.create_revision`, `artifact.update_metadata`, publication, track update,
comment, and projection tests remain green.

R39. Static/contract tests prove no new tools named `insight`, `experiment`, `roadmap`, `review`,
`approval`, `relation`, `artifact_index`, or `artifact_search` are shipped.

R40. Runtime root protected paths remain respected; tests must not write directly to
`buddyswitch/objects/**` except through existing test fixtures/helpers already used by the suite.

## Test Matrix

| ID | Requirements | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| ART-LIST-1 | R1/R2 | `tests/test_env_tool_semantic_contract.py` | shipped action discovery | artifact actions include `list`; no forbidden tools/actions appear |
| ART-LIST-2 | R2/R3/R5 | `tests/test_env_tool_schema_contract.py` | list schema | only six filter properties; enum and minimum constraints match contract |
| ART-LIST-3 | R7/R12/R13/R14 | `tests/test_artifact_env_tool.py` | owner lists private drafts | owner sees draft summary, no `body`, no state mutation |
| ART-LIST-4 | R6/R7 | `tests/test_artifact_env_tool.py` | foreign private drafts hidden | non-owner list omits draft and does not leak ids |
| ART-LIST-5 | R8/R9 | `tests/test_artifact_env_tool.py` | published track materials/proofs/history | readable published rows include relation/currentness fields |
| ART-LIST-6 | R3/R10/R11 | `tests/test_artifact_env_tool.py` | simple filters | `track_id`, `created_by`, `template`, `status`, `q`, `limit` narrow rows |
| ART-LIST-7 | R4/R5 | `tests/test_artifact_env_tool.py` | invalid filters | unsupported/bad filters reject with canonical rejection and no mutation |
| ART-LIST-8 | R6/R9 | `tests/test_artifact_env_tool.py` | archived boundary | archived track artifact does not appear; archived track filter rejects |
| CTX-1 | R15/R16 | `tests/test_env_tool_response_contract.py` | summary compactness | no full catalog, schemas, operation semantics, bodies, full threads |
| CTX-2 | R17/R18/R23/R24 | `tests/test_host_decision_surface_product_mode.py` | entry surface with active work | summary includes candidate tracks/requests/artifacts/counts/affordances |
| CTX-3 | R19/R20/R21 | `tests/test_host_decision_surface_product_mode.py` | comments and recent updates | unresolved threads and latest updates appear for selected track |
| CTX-4 | R21/R22 | `tests/test_host_decision_surface_product_mode.py` | filtered and empty states | `track_id` narrows all candidate arrays; no matches returns empty arrays |
| REL-1 | R25/R26 | `tests/test_artifact_env_tool.py` | get includes publication summary | draft/current/proof/history artifacts report expected publication/currentness |
| REL-2 | R27 | `tests/test_artifact_env_tool.py` | lineage | supersedes and visible superseded-by ids appear correctly |
| REL-3 | R28/R34 | `tests/test_artifact_env_tool.py` | source-ref backlinks | visible source refs appear; unreadable private referencing artifacts omitted |
| REL-4 | R29/R30/R34 | `tests/test_artifact_env_tool.py` | request target/result backlinks | visible requests appear in correct target/result bucket |
| REL-5 | R31 | `tests/test_artifact_env_tool.py` | track update backlinks | update refs appear with track/update metadata only |
| REL-6 | R32/R33 | `tests/test_artifact_env_tool.py` | comment backlinks | artifact and section comment ids appear without comment bodies |
| REL-7 | R35/R36 | `tests/test_artifact_env_tool.py` and `tests/test_repo_consistency.py` | no relation engine | list has counts only; no relation files/tools/dirs are created |
| PROJ-1 | R35/R36/R38 | `tests/test_parallel_contracts.py` | projection stays lightweight | artifact projection has comment counts and optional relation counts, no full relation object |
| REG-1 | R37/R38 | existing suites | baseline regression | request/comment/artifact/track tests remain green |
| SCAN-1 | R39 | `tests/test_repo_consistency.py` | forbidden surfaces absent | no forbidden tool packages, docs plans only as spec references |

## Detailed Test Designs

### ART-LIST-3: Owner Lists Private Drafts

Setup:

- active buddy `pm`;
- create two PM drafts with different templates and summaries;
- create one Dev private draft.

Action:

```text
artifact.list {}
```

Assertions:

- PM sees the two PM drafts;
- PM does not see Dev draft;
- each row has `status=draft`, `currentness=draft`, `relation=owner`;
- no row contains `body`;
- `source_refs_summary` is present and contains only lightweight source ref data;
- file snapshots for tracks/tasks/comments/messages/requests/buddybox are unchanged.

### ART-LIST-5: Published Materials, Proofs, And History

Setup:

- create track `track-art-list`;
- create and publish `art-brief-r1` as material;
- create `art-proof-r1` and publish it as close proof;
- create `art-brief-r2` superseding `art-brief-r1` and publish it as current material.

Actions:

```text
artifact.list {"track_id": "track-art-list"}
artifact.list {"template": "proof"}
artifact.list {"status": "published"}
```

Assertions:

- current material row reports `relation=track_material`, `currentness=current`;
- proof row reports `relation=track_proof`, `currentness=proof`;
- superseded historical row is readable if existing track history already permits it and reports
  `relation=track_history`, `currentness=superseded`;
- rows are sorted deterministically by updated time then id;
- no `body` appears.

### ART-LIST-6: Simple Filters

Seed rows:

- `art-alpha-brief` title "Alpha Brief", summary "Signup flow";
- `art-alpha-design` title "Alpha Design", summary "Visual state";
- `art-beta-proof` title "Beta Proof", body contains "Signup" but title/summary do not.

Assertions:

- `q=signup` matches title/summary rows only, not the body-only match;
- `created_by=design` returns only design-created rows;
- `template=brief` returns only brief rows;
- `status=published` excludes drafts;
- `limit=1` returns exactly one row;
- `limit=0`, `limit=-1`, and `limit="1"` reject.

### CTX-2: Entry Surface With Active Work

Setup:

- create one active track with `now`, health, and owner;
- publish one current artifact and one proof artifact;
- create one visible request involving the active buddy;
- add one unresolved artifact comment;
- add one track update referencing an artifact.

Action:

```text
context.summarize {}
```

Assertions:

- response has `candidate_tracks`;
- response has `candidate_requests`;
- response has `candidate_artifacts` with no `body`;
- response has `open_comment_threads` with thread ids/counts but no full comment content;
- response has `recent_updates` with update id/kind/summary/ref_count;
- `current_context_summary` counts match visible rows;
- `tool_affordances` includes artifact/context/request/comment/track paths and no forbidden tools.

### CTX-3: Track Filter Narrows Everything

Setup:

- two active tracks, each with artifacts, requests, comments, and updates.

Action:

```text
context.summarize {"track_id": "track-a"}
```

Assertions:

- every `candidate_artifacts` row has `published_to_track=track-a` or is a readable artifact tied to track-a;
- every `candidate_request` row has `track_id=track-a`;
- every `open_comment_threads` row targets track-a or an artifact on track-a;
- every `recent_updates` row has `track_id=track-a`;
- track-b ids do not appear in any compact arrays.

### REL-2: Lineage

Setup:

- create `art-lineage-r1`;
- create `art-lineage-r2` with `supersedes_artifact_id=art-lineage-r1`;
- publish both through normal track paths so the active buddy can read allowed history.

Action:

```text
artifact.get {"artifact_id": "art-lineage-r1"}
```

Assertions:

- `relation_summary.lineage.supersedes_artifact_id` is null for r1;
- `relation_summary.lineage.superseded_by_artifact_ids` includes r2 if r2 is readable;
- no unreadable private draft from another buddy appears as superseded-by.

### REL-3: Source-Ref Backlinks

Setup:

- target artifact `art-source-target`;
- visible artifact `art-source-visible` has `source_refs=[{"type":"artifact","id":"art-source-target"}]`;
- private Dev draft `art-source-private` has the same source ref.

Actions:

```text
artifact.get {"artifact_id": "art-source-target"} as pm
artifact.get {"artifact_id": "art-source-target"} as dev
```

Assertions:

- PM sees `art-source-visible` if readable;
- PM does not see Dev private draft id or count;
- Dev sees its own private draft backlink when the target is readable to Dev;
- source refs remain described as provenance, not required reading path.

### REL-4: Request Target/Result Backlinks

Setup:

- target artifact is published on a track;
- request A has `target_refs` pointing to the artifact;
- request B completes with `result_refs` pointing to the artifact;
- request C exists on another track not visible to active buddy.

Action:

```text
artifact.get {"artifact_id": "art-request-target"}
```

Assertions:

- request A appears only in `target_ref_by_requests`;
- request B appears only in `result_ref_by_requests`;
- invisible request C is omitted without leaking id/title/count;
- rows include request id, track id, requester, recipient, status, and title only.

### REL-5: Track Update Backlinks

Setup:

- track update `upd-one` has `refs=[{"type":"artifact","id":"art-update-target"}]`;
- another update has no ref;
- another track is archived.

Action:

```text
artifact.get {"artifact_id": "art-update-target"}
```

Assertions:

- `upd-one` appears under `track_update_refs`;
- unrelated update does not appear;
- archived track update does not appear;
- row includes `track_id`, `update_id`, `kind`, `summary`, `by_buddy`, `created_at`.

### REL-6: Comment Backlinks

Setup:

- root comment on artifact;
- section comment with `target_type=artifact_section`;
- resolved comment on artifact;
- comment on another artifact.

Action:

```text
artifact.get {"artifact_id": "art-comment-target"}
```

Assertions:

- artifact and section comment ids appear in `comment_ids`;
- comments on other artifacts do not appear;
- both open and resolved comments may be listed as ids;
- no `content` field appears inside `relation_summary`.

## Required Verification Commands

Focused artifact/context/relation loop:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_repo_consistency.py \
  -q
```

Request/comment baseline:

```bash
python3 -m pytest \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

Projection and contract loop:

```bash
python3 -m pytest \
  tests/test_parallel_contracts.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_runtime_skills.py \
  -q
```

Broader relevant verification before claiming completion:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_parallel_contracts.py \
  tests/test_black_box_tool_runtime.py \
  tests/test_repo_consistency.py \
  -q
```

## Pass Criteria

- Every functional requirement R1-R40 maps to at least one test row above.
- Focused tests fail before implementation for the missing behavior.
- Focused tests pass after implementation.
- Existing request/comment and publication behavior remains green.
- No test asserts implementation internals as a substitute for product behavior.


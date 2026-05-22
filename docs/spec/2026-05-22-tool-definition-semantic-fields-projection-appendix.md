# ToolDefinition Semantic Fields Projection Appendix

Date: 2026-05-22
Status: Task 1 semantic reference for `clean-runtime-env`.

## Purpose

This appendix gives the semantic content that Task 1 should put into `ToolDefinition` and
`ActionDefinition`. It is intentionally about atomic tool meaning only. It does not define PM
workflow sequencing, phrase routing, or one-track-per-feature behavior.

## Tool Object Models

Use these as `ToolDefinition.object_model` values, with minor wording changes allowed only when the
meaning stays intact.

| Tool | Object model |
| --- | --- |
| `track` | Track pages are shared product outcome threads. A track can cover a feature iteration, decision thread, delivery slice, or other coherent shared outcome; not every feature mention requires a new track. PM owns create/archive lifecycle; shared mutation publishes material, proof, timeline, or now-state on the track. |
| `task` | Tasks are active-buddy private work items. A task may link to a track for context, but task state does not define shared product state, publish artifacts, mutate track state, or change artifact readability. |
| `artifact` | Artifacts are buddy-authored product content records. Draft revisions are owner-scoped until `track.add_material` or `track.add_proof` publishes them to shared track state; `artifact.get` returns full body content only for readable artifact ids. |
| `buddybox` | Buddybox files are active-buddy private instance-local files addressed by `logical_name`. They are not product-readable and do not mutate tracks, tasks, artifacts, requests, comments, or messages. |
| `comment` | Comments are target-scoped discussion rows on readable track, artifact, or artifact_section targets. Comments support discussion and PM thread resolution, but they do not become canonical track timeline progress or direct inbox messages. |
| `message` | Messages are direct buddy-to-buddy inbox rows. They are informal direct communication and do not mutate tracks, artifacts, tasks, comments, or request lifecycle state. |
| `request` | Requests are durable cross-buddy collaboration lifecycle rows bound to readable tracks. They model requester/recipient accepted-blocked-done-canceled state and are separate from private tasks and informal messages. |
| `context` | Context is read-only progressive runtime discovery. It exposes current orientation, candidate ids, source workspace facts, generated tool affordances, full catalog, and operation semantics without granting authority or mutating state. |
| `search` | Search is a runtime-visible search/browser boundary. It exposes backend status, URL planning, and launcher-managed browser opening; it does not fetch, summarize, or persist search result content as product state. |
| `evidence` | Evidence actions issue transient target-scoped token metadata for artifact quality gates. Evidence tokens do not persist product objects and do not replace durable artifact, track, request, or comment state. |

## Common Failure Guarantees

Use these exact guarantees unless an action needs a narrower one:

| Category | `failure_state_guarantee` |
| --- | --- |
| Read actions | `Rejected reads do not mutate runtime state and return no full object body beyond rejection metadata.` |
| Runtime object writes | `Rejected writes do not mutate runtime objects; response explains the permission, payload, lifecycle, or visibility boundary.` |
| Runtime file writes | `Rejected file writes do not create, replace, or delete private files; response explains the private file boundary.` |
| Browser/session actions | `Rejected browser actions do not open a page and do not mutate product state.` |
| Token issuance actions | `Rejected token issuance does not create token metadata and does not mutate product state.` |

## Action Semantic Reference

The `reads`, `writes`, and `does_not_write` entries are suggested tuple values. Keep them concrete
and host-visible. Do not replace them with generic values such as `state`.

### Track

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `track.create` | `manifest buddy permissions`, `existing track ids` | `shared track page` | `artifact body`, `task state`, `request lifecycle`, `buddybox files` | `shared to buddies with track read access` | `durable` | `track page` | Creates one PM-owned shared product outcome thread with initial outcome, appetite, now focus, state, and health. |
| `track.list` | `non-archived track summaries` | none | `track state`, `artifact state`, `task state`, `request lifecycle`, `buddybox files` | `active-buddy readable track summaries` | `none` | `summary rows` | Returns non-archived track summaries for choosing whether to reuse, split, or open a track. |
| `track.open` | `one non-archived track page` | none | `track state`, `artifact body`, `task state`, `request lifecycle`, `buddybox files` | `active-buddy readable track page` | `none` | `track page with refs and summaries` | Opens one shared track page with now-state, timeline, material refs, and proof refs; use `artifact.get` for full artifact bodies. |
| `track.update_now` | `one non-archived track page` | `track now/state/health`, `track timeline update row` | `artifact body`, `artifact publication slot`, `task state`, `request lifecycle`, `buddybox files` | `shared to buddies with track read access` | `durable` | `track page` | Updates shared track now/state/health and records the change on the track timeline. |
| `track.add_material` | `one non-archived track page`, `one publishable artifact` | `track shared_materials`, `artifact publication metadata` | `task state`, `request lifecycle`, `buddybox files`, `comment threads` | `shared to buddies with track read access` | `durable` | `track page plus artifact id` | Publishes one draft artifact as current shared material on the track. |
| `track.add_update` | `one non-archived track page`, `optional readable artifact refs` | `track timeline update row` | `artifact body`, `artifact publication slot`, `task state`, `request lifecycle`, `buddybox files` | `shared to buddies with track read access` | `durable` | `timeline update row and track page` | Appends one narrative progress, decision, blocker, or proof-note update to the track timeline. |
| `track.add_proof` | `one non-archived track page`, `one publishable artifact` | `track close_proof`, `track timeline update row`, `artifact publication metadata` | `task state`, `request lifecycle`, `buddybox files`, `comment threads` | `shared to buddies with track read access` | `durable` | `track page plus artifact id and update id` | Publishes one draft artifact as current close proof and records the proof event on the track timeline. |
| `track.archive` | `one track page` | `track archived_at` | `artifact body`, `artifact publication metadata`, `task state`, `request lifecycle`, `buddybox files` | `shared to buddies with track read access until archived filters hide it` | `durable` | `track page` | Archives one PM-owned track so it leaves active collaboration flows and rejects routine shared mutations. |

### Task

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `task.create` | `active-buddy task namespace`, `optional track existence` | `active-buddy private task` | `track state`, `artifact state`, `artifact visibility`, `request lifecycle`, `comments`, `messages`, `buddybox files` | `active-buddy private` | `durable` | `task row` | Creates one private work item for the active buddy; `track_id` is a context link only. |
| `task.list` | `active-buddy private task summaries` | none | `task state`, `track state`, `artifact visibility`, `request lifecycle`, `buddybox files` | `active-buddy private` | `none` | `summary rows` | Returns active-buddy private task rows for triage or filtering. |
| `task.get` | `one active-buddy private task` | none | `task state`, `track state`, `artifact visibility`, `request lifecycle`, `buddybox files` | `active-buddy private` | `none` | `task row` | Returns one active-buddy private task row by id. |
| `task.update` | `one active-buddy private task`, `optional track existence` | `active-buddy private task` | `track state`, `artifact state`, `artifact visibility`, `request lifecycle`, `comments`, `messages`, `buddybox files` | `active-buddy private` | `durable` | `task row` | Updates private task fields or lifecycle status; `track_id` remains context only. |
| `task.archive` | `one active-buddy private task` | `active-buddy private task archived_at` | `track state`, `artifact visibility`, `request lifecycle`, `comments`, `messages`, `buddybox files` | `active-buddy private` | `durable` | `task row` | Archives one active-buddy private task without changing shared product state. |

### Artifact

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `artifact.list` | `readable artifact summaries` | none | `artifact body`, `artifact state`, `track state`, `task state`, `request lifecycle`, `buddybox files` | `active-buddy readable artifact summaries` | `none` | `summary rows only` | Returns readable artifact summaries and filters without loading full markdown bodies. |
| `artifact.get` | `one readable artifact body` | none | `artifact state`, `track state`, `task state`, `request lifecycle`, `buddybox files` | `active-buddy readable artifact body` | `none` | `full markdown body` | Returns one readable artifact including full markdown body. |
| `artifact.create_revision` | `optional superseded artifact`, `source refs metadata` | `active-buddy private draft artifact revision` | `track state`, `track material slot`, `track proof slot`, `task state`, `request lifecycle`, `buddybox files` | `owner-scoped draft until track publication` | `durable` | `artifact row with draft body` | Creates one active-buddy private draft artifact revision; publication starts only with `track.add_material` or `track.add_proof`. |
| `artifact.update_metadata` | `one active-buddy-owned artifact` | `active-buddy-owned artifact metadata/body` | `track state`, `track material slot`, `track proof slot`, `task state`, `request lifecycle`, `buddybox files` | `owner-scoped unless already published through track state` | `durable` | `artifact row` | Patches metadata or body on one active-buddy-owned artifact without changing track publication slots. |

### Buddybox

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `buddybox.desc` | `active-buddy private file capability descriptor` | none | `private files`, `product objects`, `browser session`, `tokens` | `active-buddy private` | `none` | `capability descriptor` | Describes private buddybox file boundaries and logical-name addressing. |
| `buddybox.list` | `active-buddy private file summaries` | none | `private files`, `product objects`, `browser session`, `tokens` | `active-buddy private` | `none` | `private file summary rows` | Lists active-buddy private file summaries without reading product state. |
| `buddybox.read` | `one active-buddy private file body` | none | `private files`, `product objects`, `browser session`, `tokens` | `active-buddy private` | `none` | `private file body` | Reads one active-buddy private file by logical name. |
| `buddybox.write` | `active-buddy private file namespace` | `active-buddy private file` | `tracks`, `tasks`, `artifacts`, `requests`, `comments`, `messages`, `browser session`, `tokens` | `active-buddy private` | `durable` | `private file row` | Creates or replaces one active-buddy private file; content is not product-readable. |
| `buddybox.delete` | `one active-buddy private file` | `active-buddy private file deletion` | `tracks`, `tasks`, `artifacts`, `requests`, `comments`, `messages`, `browser session`, `tokens` | `active-buddy private` | `durable` | `delete result` | Deletes one active-buddy private file without retracting published product content. |

### Comment

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `comment.add` | `readable target thread`, `optional parent comment`, `manifest buddy ids` | `comment row` | `track timeline`, `track now-state`, `artifact body`, `task state`, `request lifecycle`, `message inbox` | `readable to buddies with target access` | `durable` | `comment row and id` | Adds one target-scoped discussion row to a track, artifact, or artifact_section thread. |
| `comment.list` | `readable target thread comments` | none | `comment state`, `track timeline`, `artifact body`, `task state`, `request lifecycle`, `message inbox` | `readable to buddies with target access` | `none` | `comment rows` | Lists comment rows for one readable target thread, optionally by status. |
| `comment.resolve` | `one readable comment thread` | `comment thread status` | `track timeline`, `track now-state`, `artifact body`, `task state`, `request lifecycle`, `message inbox` | `readable to buddies with target access` | `durable` | `resolved comment rows` | PM marks all open rows in one reviewed comment thread as resolved with a closure summary. |

### Message

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `message.send` | `manifest buddy ids` | `direct buddy inbox message` | `tracks`, `tasks`, `artifacts`, `comments`, `requests`, `buddybox files`, `browser session` | `sender and recipient direct message visibility` | `durable` | `message row and id` | Sends one direct inbox message to another manifest buddy. |
| `message.list` | `active-buddy inbox messages` | none | `messages`, `tracks`, `tasks`, `artifacts`, `comments`, `requests`, `buddybox files` | `active-buddy inbox` | `none` | `message rows` | Lists active-buddy inbox messages with optional filters. |

### Request

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `request.create` | `readable non-archived track`, `manifest buddy ids`, `target refs` | `request row` | `task state`, `track timeline`, `artifact body`, `comment status`, `message inbox`, `buddybox files` | `requester, recipient, and PM` | `durable` | `request row and id` | Creates one durable track-scoped cross-buddy request for a recipient buddy. |
| `request.list` | `visible request rows` | none | `request lifecycle`, `task state`, `track state`, `artifact body`, `message inbox`, `buddybox files` | `requester, recipient, and PM filtered visibility` | `none` | `request summary rows` | Lists requests visible to the active buddy for inbox/outbox/status scanning. |
| `request.get` | `one visible request row` | none | `request lifecycle`, `task state`, `track state`, `artifact body`, `message inbox`, `buddybox files` | `requester, recipient, and PM filtered visibility` | `none` | `request row` | Reads one durable request row by id. |
| `request.accept` | `one visible request row` | `request status` | `task state`, `track timeline`, `artifact body`, `comment status`, `message inbox`, `buddybox files` | `requester, recipient, and PM` | `durable` | `request row` | Recipient moves one open or blocked request to accepted. |
| `request.block` | `one visible request row` | `request status and blocker` | `task state`, `track timeline`, `artifact body`, `comment status`, `message inbox`, `buddybox files` | `requester, recipient, and PM` | `durable` | `request row` | Recipient marks an accepted request blocked with blocker text. |
| `request.complete` | `one visible request row`, `result refs` | `request status and result refs` | `task state`, `track timeline`, `artifact body`, `comment status`, `message inbox`, `buddybox files` | `requester, recipient, and PM` | `durable` | `request row` | Recipient marks an accepted or blocked request done with result refs. |
| `request.cancel` | `one visible request row` | `request status` | `task state`, `track timeline`, `artifact body`, `comment status`, `message inbox`, `buddybox files` | `requester, recipient, and PM` | `durable` | `request row` | Requester cancels one request that is no longer needed. |

### Context

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `context.get` | `runtime context sections`, `source workspace facts`, `tool registry`, `operation semantics` | none | `runtime objects`, `runtime files`, `browser session`, `tokens`, `source root config` | `active-buddy runtime orientation` | `none` | `full context and full catalog` | Returns full read-only context, full generated tool catalog, operation semantics, and source workspace facts. |
| `context.summarize` | `runtime context summary`, `candidate ids`, `registry compact affordances`, `source workspace facts` | none | `runtime objects`, `runtime files`, `browser session`, `tokens`, `source root config`, `full schemas` | `active-buddy runtime orientation` | `none` | `compact summary` | Returns compact first-pass orientation with candidate ids and generated compact affordances. |
| `context.list_sources` | `context source descriptors` | none | `runtime objects`, `runtime files`, `browser session`, `tokens`, `source root config` | `active-buddy runtime orientation` | `none` | `source descriptors` | Returns read-only source descriptors and boundaries. |

### Search

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `search.status` | `search profile`, `browser readiness` | none | `product objects`, `runtime files`, `browser page`, `tokens` | `active-buddy runtime orientation` | `none` | `backend status` | Returns configured search/backend/browser readiness metadata. |
| `search.request` | `search profile`, `query payload` | none | `product objects`, `runtime files`, `browser page`, `tokens`, `fetched results` | `active-buddy runtime orientation` | `none` | `target URL plan` | Resolves a target URL plan for a query; it does not fetch results and does not open a browser page. |
| `search.open_browser` | `search profile`, `query payload`, `launcher browser endpoint` | `browser session page open` | `product objects`, `runtime files`, `tokens`, `fetched result summaries` | `launcher-managed browser session` | `transient` | `browser open intent and target URL` | Opens the planned search URL in the launcher-managed browser for browser-native discovery. |

### Evidence

| Action | Reads | Writes | Does not write | Visibility | Durability | Result content | Success effect |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `evidence.issue_browser` | `target artifact metadata`, `browser evidence payload` | `transient evidence token metadata` | `artifact body`, `artifact state`, `track state`, `request lifecycle`, `buddybox files` | `active-buddy token response only` | `transient` | `token metadata` | Issues one transient browser evidence token metadata row for an artifact target. |
| `evidence.approve_downgrade` | `target artifact metadata`, `reason payload` | `transient downgrade approval token metadata` | `artifact body`, `artifact state`, `track state`, `request lifecycle`, `buddybox files` | `active-buddy token response only` | `transient` | `token metadata` | Issues one transient downgrade approval token metadata row with a non-empty reason. |

## Result Content Level Vocabulary

Use short stable strings:

```text
summary rows
full markdown body
draft artifact row
metadata/body patch result
private file descriptor
private file body
comment rows
message rows
request row
request summary rows
track page
timeline update row
compact context
full context and catalog
source descriptors
backend status
target URL plan
browser open intent
token metadata
delete result
```

## Durability Mapping

Use this mapping:

| Mutation kind | Durability |
| --- | --- |
| `mutates="none"` | `none` |
| `mutates="runtime_objects"` | `durable` |
| `mutates="runtime_files"` | `durable` |
| `mutates="broker_token"` | `transient` |
| `mutates="browser_session"` | `transient` |

If a future action breaks this mapping, add a focused test explaining why.

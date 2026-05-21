# Tool Layer Action Semantics Plan

Goal: make action-level tool selection semantics runtime-visible for every current `tool.action`, with no prompt compensation, no compatibility track, and no partial coverage.

Current bottleneck: `scripts/env/tool_runtime/registry.py::_action_semantic_row()` still emits placeholder selection text:

- `Use when <tool.action> is the intended action.`
- `Do not use <tool.action> when another action is a closer semantic match.`

This leaves the host unable to choose between adjacent actions such as `track.add_material`, `track.add_update`, and `track.add_proof` from the runtime catalog alone.

System scan sources:

- `tmp/buddyswitch-real-startup-skill-inventory.html`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/memo/buddyswitch-parallel-modular-architecture.md`
- `scripts/env/tool_runtime/definition.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/client.py`
- `scripts/env/tools/*/tool.py`
- `scripts/env/tools/*/_impl.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_schema_contract.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `buddyswitch/skills/**/*.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`

## Current Fact Table

| Action | Current description | Payload fields | State effect | Current returns |
| --- | --- | --- | --- | --- |
| `artifact.get` | Get one readable artifact including full markdown body. | `artifact_id` | read-only, `mutates=none` | `artifact` |
| `artifact.create_revision` | Create one active-buddy private draft artifact revision. | `artifact_id`, `title`, `summary`, `template`, `body`, `supersedes_artifact_id`, `source_refs`, `read_claim` | durable runtime object write | `artifact` |
| `artifact.update_metadata` | Update metadata on one active-buddy-owned artifact. | `artifact_id`, `title`, `summary`, `template`, `body`, `source_refs`, `read_claim` | durable runtime object write | `artifact` |
| `buddybox.desc` | Describe active-buddy private file capability. | none | read-only private capability description | `buddybox_desc` |
| `buddybox.list` | List active-buddy private file summaries. | `logical_name`, `recursive`, `limit` | read-only private file summaries | `files` |
| `buddybox.read` | Read one active-buddy private file. | `logical_name`, `encoding` | read-only private file body | `private_file` |
| `buddybox.write` | Write one active-buddy private file. | `logical_name`, `content`, `content_base64`, `content_type` | active-instance-local private file write | `private_file` |
| `buddybox.delete` | Delete one active-buddy private file. | `logical_name` | active-instance-local private file deletion when file exists | `deleted`, `logical_name` |
| `comment.add` | Add one comment row to a readable target thread. | `target_type`, `target_id`, `content`, `reply_to`, `artifact_revision_id`, `anchor`, `mentions` | durable runtime comment write | `comment_id`, `comment` |
| `comment.list` | List comment rows for a readable target thread. | `target_type`, `target_id`, `status` | read-only comment thread view | `comments` |
| `context.get` | Return full runtime context sections with full tool catalog and operation semantics. | `track_id`, `task_id`, `limit` | read-only runtime discovery | `sections`, `tool_catalog`, `decision_surface` |
| `context.summarize` | Return compact runtime context orientation and first-pass affordances. | `track_id`, `task_id`, `limit` | read-only compact orientation | `summary`, `candidate_tracks`, `buddybox_desc` |
| `context.list_sources` | Return context source descriptors only. | none | read-only descriptor metadata | `sources` |
| `evidence.issue_browser` | Issue one browser evidence token metadata row. | `target_type`, `target_id`, `mode` | transient broker-token metadata | `tool_evidence` |
| `evidence.approve_downgrade` | Issue one downgrade approval token metadata row. | `target_type`, `target_id`, `reason` | transient broker-token metadata | `tool_evidence` |
| `message.send` | Send one direct message to another manifest buddy. | `to_buddy`, `content`, `reply_to` | durable runtime message write | `message_id`, `message` |
| `message.list` | List active-buddy inbox messages. | `buddy` | read-only active-buddy inbox | `messages` |
| `search.status` | Read search capability and backend/browser readiness metadata. | none | read-only search/browser readiness metadata | `backend_status` |
| `search.request` | Resolve one explicit search target URL intent. | `query`, `backend`, `engine` | read-only URL planning, no browser open | `target_url`, `backend`, `engine` |
| `search.open_browser` | Open one search URL through launcher-managed browser endpoint. | `query`, `engine` | browser-session mutation, no product object write | `target_url`, `backend`, `engine` |
| `task.create` | Create one active-buddy private task. | `task_id`, `title`, `summary`, `status`, `track_id` | durable private task write | `task_id`, `task` |
| `task.list` | List active-buddy private tasks. | `status`, `track_id`, `limit` | read-only private task summaries | `tasks` |
| `task.get` | Get one active-buddy private task. | `task_id` | read-only private task record | `task` |
| `task.update` | Update one active-buddy private task. | `task_id`, `title`, `summary`, `status`, `track_id` | durable private task patch | `task` |
| `task.archive` | Archive one active-buddy private task. | `task_id` | durable private task archival when not already archived | `task` |
| `track.create` | Create one PM-owned shared track page. | `track_id`, `title`, `outcome`, `appetite`, `now`, `state`, `health` | durable PM-owned shared track write | `track` |
| `track.list` | List non-archived track page summaries. | `state`, `limit` | read-only shared track summaries | `tracks` |
| `track.open` | Open one non-archived shared track page. | `track_id` | read-only shared track page | `track` |
| `track.update_now` | Update now/state/health on a shared track page. | `track_id`, `now`, `state`, `health` | durable shared track state write | `track` |
| `track.add_material` | Publish one draft artifact as current shared material. | `track_id`, `artifact_id`, `label`, `summary` | durable track/artifact publication write | `artifact_id`, `track`, `state_changes` |
| `track.add_update` | Append one track timeline update row. | `track_id`, `summary`, `kind`, `refs` | durable shared track timeline write | `track`, `update` |
| `track.add_proof` | Publish one draft artifact as current close proof. | `track_id`, `artifact_id`, `label`, `summary` | durable track/artifact proof publication write | `artifact_id`, `track`, `state_changes` |
| `track.archive` | Archive one PM-owned shared track page. | `track_id` | durable PM-owned shared track archival | `track` |

Runtime source of truth target:

- Add action-owned `use_when` and `do_not_use_when` semantics to `ActionDefinition` in `scripts/env/tool_runtime/definition.py`.
- Project those fields in `scripts/env/tool_runtime/registry.py`.
- Populate every action in `scripts/env/tools/*/tool.py`.
- Prove through tests that no action semantics are generated from the old registry template.

Serial contract seed before parallel implementation:

- Modify `scripts/env/tool_runtime/definition.py` to add `ActionDefinition.use_when: tuple[str, ...]` and `ActionDefinition.do_not_use_when: tuple[str, ...]`.
- Validate both fields as non-empty text tuples for every action.
- Modify `scripts/env/tool_runtime/registry.py` so `_action_semantic_row()` reads action-owned semantics instead of generating placeholders.
- Modify `scripts/env/tool_runtime/registry.py` so broker payload `action` is strict: remove `raw_action.strip().replace("-", "_")` normalization and require the canonical underscore registry action id in `env.tool` payloads.
- This seed is a shared write set and must be completed once by the integrator before I1/I2/I3 populate per-tool definitions.

Parallel implementation ownership after the serial seed:

- I1 modifies only `scripts/env/tools/artifact/tool.py`, `scripts/env/tools/task/tool.py`, `scripts/env/tools/track/tool.py`, and `scripts/env/tools/comment/tool.py`.
- I2 modifies only `scripts/env/tools/context/tool.py`, `scripts/env/tools/buddybox/tool.py`, and `scripts/env/tools/message/tool.py`.
- I3 modifies only `scripts/env/tools/search/tool.py` and `scripts/env/tools/evidence/tool.py`.
- I4 modifies only `buddyswitch/skills/**/*.md` and `tools/launcher/assets/buddies/*/AGENTS.md`.
- I5 modifies only `tests/test_env_tool_semantic_contract.py`, `tests/test_env_tool_schema_contract.py`, `tests/test_runtime_skills.py`, `tests/test_repo_consistency.py`, and, if needed, one new focused test file.
- R2 reviews only. R2 must not edit files.

Implementation Agent I1:

- Write set:
  - `scripts/env/tools/artifact/tool.py`
  - `scripts/env/tools/task/tool.py`
  - `scripts/env/tools/track/tool.py`
  - `scripts/env/tools/comment/tool.py`
- Task: populate work-object action semantics and fix scoped runtime definition text drift.
- Forbidden write set: all other files.

Implementation Agent I2:

- Write set:
  - `scripts/env/tools/context/tool.py`
  - `scripts/env/tools/buddybox/tool.py`
  - `scripts/env/tools/message/tool.py`
- Task: populate runtime context, private workspace, and message action semantics.
- Forbidden write set: all other files.

Implementation Agent I3:

- Write set:
  - `scripts/env/tools/search/tool.py`
  - `scripts/env/tools/evidence/tool.py`
- Task: populate browser/search/evidence action semantics.
- Forbidden write set: all other files.

Implementation Agent I4:

- Write set:
  - `buddyswitch/skills/**/*.md`
  - `tools/launcher/assets/buddies/*/AGENTS.md`
- Task: delete stale CLI flag guidance and replace active examples with payload-form guidance without copying runtime schemas.
- Forbidden write set: Python runtime and tests.

Implementation Agent I5:

- Write set:
  - `tests/test_env_tool_semantic_contract.py`
  - `tests/test_env_tool_schema_contract.py`
  - `tests/test_runtime_skills.py`
  - `tests/test_repo_consistency.py`
  - one new focused test file only if needed for broker action alias rejection
- Task: add semantic, schema, guidance, CLI, and rg guardrails.
- Forbidden write set: runtime implementation and active guidance.

Review Agent R2:

- Write set: none.
- Checks:
  - no old flags;
  - no template action semantics;
  - no compatibility residue or aliases;
  - no docs/bitter violation;
  - every current registry action has target semantics;
  - implementation write scopes stayed disjoint.

Non-goals:

- No old CLI flags, aliases, deprecated examples, or dual-path guidance.
- No workflow engine, plugin system, rule system, migration layer, or generic DSL.
- No full runtime schema copy in skills or AGENTS.
- No "later semantics" gap; every current registry action is covered here.

## Action Semantics

### artifact.get

Current issue:
- The catalog says this is a readable artifact fetch, but placeholder `use_when` does not explain that this is the full-body read path rather than creation, metadata patching, or track publication.

Target use_when:
- Use when the active buddy needs the full body and metadata for one readable artifact id.

Target do_not_use_when:
- Do not use to create, revise, publish, or discover artifacts; use `artifact.create_revision`, `artifact.update_metadata`, `track.open`, or track publication actions instead.

Distinguish from:
- `artifact.create_revision`: creates a new private draft instead of reading.
- `artifact.update_metadata`: patches an owned artifact instead of reading.
- `track.open`: reads shared track refs and timeline, not full artifact body.

Expected runtime catalog effect:
- The host chooses `artifact.get` after it already has an artifact id and needs body content.

Implementation target:
- Modify `scripts/env/tools/artifact/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that `artifact.get` semantics mention full body/readable artifact and reject create/publish intent.

### artifact.create_revision

Current issue:
- The catalog exposes fields and preconditions, but action selection does not say this creates a private draft and does not publish.

Target use_when:
- Use when the active buddy has new markdown artifact content to save as a private draft revision.
- Use this before publishing material or proof to a track.

Target do_not_use_when:
- Do not use to publish, set status, bind to a track, or patch an existing artifact in place.

Distinguish from:
- `artifact.get`: reads existing full artifact body.
- `artifact.update_metadata`: patches an existing owned artifact.
- `track.add_material` / `track.add_proof`: publish an existing draft to shared track state.

Expected runtime catalog effect:
- The host understands the draft-then-publish path: `artifact.create_revision` creates content; track actions publish it.

Implementation target:
- Modify `scripts/env/tools/artifact/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that the semantics mention private draft and publication exclusion.
- Keep `tests/test_env_tool_schema_contract.py` coverage proving `status` and `published_to_track` are not accepted create inputs.

### artifact.update_metadata

Current issue:
- The catalog does not explain that this is an in-place owned-artifact patch, not a new revision or publication action.

Target use_when:
- Use when the active buddy owns an artifact and needs to patch title, summary, template, body, source refs, or read claim in place.

Target do_not_use_when:
- Do not use to create a separate revision or to publish or change shared track material/proof bindings.

Distinguish from:
- `artifact.create_revision`: creates a new private draft artifact revision.
- `track.add_material` / `track.add_proof`: change shared publication refs.
- `artifact.get`: read-only full-body retrieval.

Expected runtime catalog effect:
- The host chooses this only for owned artifact patching and does not treat it as publication.

Implementation target:
- Modify `scripts/env/tools/artifact/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics separate patching from create and publish.

### buddybox.desc

Current issue:
- The action is read-only capability description, but placeholder text does not distinguish capability boundaries from listing or reading private files.

Target use_when:
- Use when the active buddy needs to understand private file capability boundaries and current private workspace summary without listing file rows.

Target do_not_use_when:
- Do not use when the next step requires file inventory, exact file contents, or product-readable shared output.

Distinguish from:
- `buddybox.list`: returns private file summary rows.
- `buddybox.read`: returns one private file body.
- `artifact.create_revision`: creates product-readable artifact content after private work is ready.

Expected runtime catalog effect:
- The host uses `buddybox.desc` for private workspace orientation and stops treating it as a file read.

Implementation target:
- Modify `scripts/env/tools/buddybox/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention private capability boundaries and exclude file content/product output.

### buddybox.list

Current issue:
- Placeholder text does not distinguish private file inventory from exact content reads or shared artifact publication.

Target use_when:
- Use when the active buddy needs private file summary rows by logical name, optionally limited to a prefix or recursive listing.

Target do_not_use_when:
- Do not use when exact file content is needed, or when the content must be shared through product-readable artifact state.

Distinguish from:
- `buddybox.read`: reads one private file body.
- `buddybox.desc`: describes capability, not file rows.
- `artifact.create_revision`: creates product-readable draft artifact content.

Expected runtime catalog effect:
- The host lists private files only to discover logical names or inspect inventory.

Implementation target:
- Modify `scripts/env/tools/buddybox/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention summaries and exclude exact content.

### buddybox.read

Current issue:
- The catalog does not explain that this reads one active-buddy private file body by `logical_name`; it also hides the current schema/implementation mismatch around `encoding=auto`.

Target use_when:
- Use when the active buddy needs the exact body of one private file addressed by `logical_name`.

Target do_not_use_when:
- Do not use when the logical name is unknown, when only inventory is needed, or when another buddy or product workflow must read the content directly.

Distinguish from:
- `buddybox.list`: finds private file logical names without body content.
- `buddybox.write`: creates or replaces private file content.
- `artifact.create_revision`: promotes content into product-readable artifact state.

Expected runtime catalog effect:
- The host reads only known private logical names and does not treat buddybox content as shared output.

Implementation target:
- Modify `scripts/env/tools/buddybox/tool.py`.
- I5 must add or update tests to reconcile `buddybox.read.encoding`: either schema and behavior both accept `auto`, or implementation rejects `auto`.

### buddybox.write

Current issue:
- Placeholder text does not clarify that this replaces one private file and is not append, merge, shared publication, or product object mutation.

Target use_when:
- Use when the active buddy needs to create or replace one private workspace file with text or base64 content.

Target do_not_use_when:
- Do not use for product-readable deliverables, append or merge semantics, shared collaboration state, or any write where replacing the whole private file is not intended.

Distinguish from:
- `buddybox.read`: reads private content.
- `buddybox.delete`: removes private content.
- `artifact.create_revision`: creates durable product artifact content.

Expected runtime catalog effect:
- The host chooses `buddybox.write` only for active-buddy private workspace files.

Implementation target:
- Modify `scripts/env/tools/buddybox/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention create/replace and private workspace boundary.

### buddybox.delete

Current issue:
- Placeholder text does not surface destructive private-file semantics or distinguish file deletion from object archival.

Target use_when:
- Use when the active buddy intentionally wants to remove one private file by `logical_name`.

Target do_not_use_when:
- Do not use for directories, shared/product objects, or cleanup where the target file has not been confirmed enough for destructive private mutation.

Distinguish from:
- `buddybox.write`: creates or replaces one private file.
- `task.archive` / `track.archive`: archive runtime objects, not private files.

Expected runtime catalog effect:
- The host treats `buddybox.delete` as a private destructive mutation and does not apply it to product state.

Implementation target:
- Modify `scripts/env/tools/buddybox/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention private file deletion and exclude runtime objects.

### comment.add

Current issue:
- The action description says target-scoped comments, but placeholder selection text does not distinguish comments from track timeline updates, messages, or state mutations.

Target use_when:
- Use when the active buddy needs a target-scoped discussion comment, reply, mention, or artifact-section note on a readable target.

Target do_not_use_when:
- Do not use for shared progress timeline, state changes, material publication, proof publication, or direct buddy messages.

Distinguish from:
- `comment.list`: reads comment threads.
- `track.add_update`: writes shared track timeline history, not threaded discussion.
- `message.send`: sends direct inbox messages.

Expected runtime catalog effect:
- The host chooses `comment.add` for discussion attached to track/artifact targets and not for track progress facts.

Implementation target:
- Modify `scripts/env/tools/comment/tool.py`.
- I1 should align preconditions with schema/implementation support for `artifact_section`.
- I1 should correct any response guidance that says `track.get`; current active track read action is `track.open`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics separate comments from timeline updates and messages.

### comment.list

Current issue:
- Placeholder text does not distinguish comments from track timeline updates or artifact body reads.

Target use_when:
- Use when the active buddy needs comments and thread grouping for one readable target.

Target do_not_use_when:
- Do not use to read track timeline updates, task updates, direct messages, or artifact bodies.

Distinguish from:
- `track.open`: reads track timeline and shared refs.
- `artifact.get`: reads artifact body.
- `message.list`: reads active-buddy inbox messages.

Expected runtime catalog effect:
- The host chooses `comment.list` only for target-scoped discussion threads.

Implementation target:
- Modify `scripts/env/tools/comment/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that comments and track timeline are distinct.

### context.get

Current issue:
- The action is the full runtime discovery surface, but placeholder text does not distinguish it from compact context or mutation actions.

Target use_when:
- Use when the host needs full read-only runtime orientation, including complete tool catalog, operation semantics, visible work state, and candidate ids.

Target do_not_use_when:
- Do not use when compact orientation is enough, or when the intent is to mutate private files, messages, tasks, tracks, or artifacts.

Distinguish from:
- `context.summarize`: compact first-pass orientation.
- `context.list_sources`: context source descriptors only.
- Every write action: context is read-only discovery.

Expected runtime catalog effect:
- The host escalates from summary to full catalog only when exact schemas, action semantics, or visible state are needed.

Implementation target:
- Modify `scripts/env/tools/context/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention full catalog/operation semantics and read-only use.

### context.summarize

Current issue:
- Placeholder text does not explain that this is the first-pass compact orientation, not the full catalog.

Target use_when:
- Use when the host needs a compact first-pass orientation with candidate ids, buddybox capability summary, and high-level tool affordances.

Target do_not_use_when:
- Do not use when exact input schemas, full operation semantics, or full visible context sections are required.

Distinguish from:
- `context.get`: full tool catalog and detailed runtime context.
- `context.list_sources`: source descriptor metadata only.

Expected runtime catalog effect:
- The host starts with `context.summarize` for quick orientation, then uses `context.get` only when more detail is needed.

Implementation target:
- Modify `scripts/env/tools/context/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention compact orientation and exclude full catalog needs.

### context.list_sources

Current issue:
- Placeholder text does not explain that this is a descriptor-only source map, not a data fetch.

Target use_when:
- Use when the host needs to know which runtime context sources exist and what each source represents.

Target do_not_use_when:
- Do not use to fetch actual tracks, tasks, artifacts, messages, comments, private file inventory, or private file contents.

Distinguish from:
- `context.get`: returns full context sections and catalog.
- `context.summarize`: returns compact current orientation.
- Tool-specific reads such as `track.open`, `artifact.get`, `message.list`, and `buddybox.list`.

Expected runtime catalog effect:
- The host uses this for orientation about source classes, not object data.

Implementation target:
- Modify `scripts/env/tools/context/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention descriptors only.

### evidence.issue_browser

Current issue:
- The action issues a transient browser evidence token, but placeholder selection text does not distinguish it from search/open-browser or downgrade approval.

Target use_when:
- Use when browser-native work has produced evidence for an active-buddy-authored artifact target and the host needs broker-issued evidence token metadata for later artifact references.

Target do_not_use_when:
- Do not use for non-artifact targets, readable-but-not-authored artifacts, durable evidence storage, or user-approved downgrade cases.
- Do not invent token strings.

Distinguish from:
- `search.open_browser`: opens browser pages but does not issue evidence tokens.
- `evidence.approve_downgrade`: records explicit downgrade approval instead of browser evidence.
- `artifact.update_metadata`: may later persist references but does not issue transient token metadata.

Expected runtime catalog effect:
- The host separates browser traversal from token issuance and does not treat evidence tokens as durable product objects.

Implementation target:
- Modify `scripts/env/tools/evidence/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention browser evidence, artifact-only scope, and transient token metadata.

### evidence.approve_downgrade

Current issue:
- Placeholder text does not surface that this is only for explicit one-off downgrade approval with a reason.

Target use_when:
- Use only when an explicit one-off evidence downgrade has been approved and the reason must be attached to an active-buddy-authored artifact target.

Target do_not_use_when:
- Do not use as a silent substitute for browser-native research, ordinary browser evidence, search backend permission, or missing evidence.
- Do not use without a concrete non-empty downgrade reason.

Distinguish from:
- `evidence.issue_browser`: issues browser evidence token metadata.
- `search.request` / `search.open_browser`: plan or open search pages, not approval tokens.

Expected runtime catalog effect:
- The host treats downgrade approval as an explicit exception and does not use it as fallback.

Implementation target:
- Modify `scripts/env/tools/evidence/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` and existing evidence tests that reason and transient token semantics remain distinct.

### message.send

Current issue:
- Placeholder text does not distinguish direct durable inbox messages from comments, track updates, or artifact publication.

Target use_when:
- Use when the active buddy needs to send one durable direct inbox message to one other manifest-declared buddy, including same-pair replies.

Target do_not_use_when:
- Do not use for self-messages, broadcasts, object-level discussion, artifact publication, or comments tied to tracks/artifacts.

Distinguish from:
- `message.list`: reads active-buddy inbox.
- `comment.add`: attaches discussion to a readable object target.
- `track.add_update`: writes shared track timeline history.

Expected runtime catalog effect:
- The host uses messages only for buddy-to-buddy inbox communication.

Implementation target:
- Modify `scripts/env/tools/message/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention manifest buddy and exclude comments/broadcasts.

### message.list

Current issue:
- Placeholder text does not clarify inbox-only reads or distinguish messages from object threads.

Target use_when:
- Use when the active buddy needs to read its inbox, optionally filtered to messages from one manifest buddy.

Target do_not_use_when:
- Do not use to inspect another buddy's inbox, list sent-only messages, or read object-level comment threads.

Distinguish from:
- `message.send`: creates a direct durable message.
- `comment.list`: reads object-level discussion threads.
- `context.get`: may summarize visible state but is not the inbox reader.

Expected runtime catalog effect:
- The host reads only active-buddy inbox messages with this action.

Implementation target:
- Modify `scripts/env/tools/message/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention inbox-only scope.

### search.status

Current issue:
- Placeholder text does not distinguish readiness metadata from URL planning or opening a browser page.

Target use_when:
- Use when the host needs current search capability metadata, backend availability, or browser cockpit readiness before choosing a search action.

Target do_not_use_when:
- Do not use when a query should be resolved to a target URL or opened in the browser session.
- Do not use for durable product state or evidence token changes.

Distinguish from:
- `search.request`: validates a query/backend and returns `target_url` without opening a page.
- `search.open_browser`: mutates the browser session by opening a search page.
- `evidence.issue_browser`: issues evidence token metadata after browser work.

Expected runtime catalog effect:
- The host checks capability readiness without assuming a search page has opened.

Implementation target:
- Modify `scripts/env/tools/search/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention capability metadata and no browser open.

### search.request

Current issue:
- The runtime response already says `page_opened=false`, but action selection semantics do not explain this is planning only.

Target use_when:
- Use when the host needs to validate a query/backend choice and receive the planned `target_url` without opening a browser page.

Target do_not_use_when:
- Do not use when browser-native discovery must actually begin; use `search.open_browser` for that.
- Do not use implicit backend selection or `search_api` as a silent fallback.

Distinguish from:
- `search.status`: search readiness metadata only.
- `search.open_browser`: opens a launcher-managed browser page.
- `evidence.issue_browser`: token metadata, not URL planning.

Expected runtime catalog effect:
- The host uses `search.request` for planning/validation and then calls `search.open_browser` only when it wants browser-session mutation.

Implementation target:
- Modify `scripts/env/tools/search/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` and search tests that semantics align with `page_opened=false`.

### search.open_browser

Current issue:
- Browser workflow itself is correct, but placeholder action semantics and stale skills/AGENTS examples do not clearly state that this action opens a launcher-managed browser session and must be called with `--payload`.

Target use_when:
- Use when browser-native discovery should start by opening a search results page in the launcher-managed browser session.
- Continue page inspection and evidence capture through `chrome-devtools-cockpit`.

Target do_not_use_when:
- Do not use for metadata-only checks or URL planning without session mutation.
- Do not pass old CLI flags such as `--query`, `--engine`, or `--backend`; payload JSON is the runtime contract.

Distinguish from:
- `search.request`: returns target URL intent and `page_opened=false`.
- `search.status`: returns capability readiness.
- `evidence.issue_browser`: issues token metadata after evidence work.

Expected runtime catalog effect:
- The host can choose the browser-open path and then use `chrome-devtools-cockpit` without relying on stale market skill syntax.

Implementation target:
- Modify `scripts/env/tools/search/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` and `tests/test_search_env_tool.py` that response still includes `page_opened`, `target_url`, browser session durability, and cockpit next action.

### task.create

Current issue:
- Placeholder text does not clarify that tasks are active-buddy private work aids, not shared deliverables.

Target use_when:
- Use when the active buddy needs a private work item to track optional work, optionally linked to a track.

Target do_not_use_when:
- Do not use for shared deliverables, track progress, artifact publication, or cross-buddy coordination.

Distinguish from:
- `task.list`: discover owned task ids.
- `track.add_update`: shared track progress.
- `message.send`: cross-buddy communication.

Expected runtime catalog effect:
- The host creates private tasks only for local work management.

Implementation target:
- Modify `scripts/env/tools/task/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention private work item and exclude shared state.

### task.list

Current issue:
- Placeholder text does not distinguish id discovery/filtering from reading one task or mutating tasks.

Target use_when:
- Use when the active buddy needs task ids or a filtered summary list of owned private tasks.

Target do_not_use_when:
- Do not use when one task's full record is already known; use `task.get`.
- Do not use to mutate task state.

Distinguish from:
- `task.get`: reads one owned task record.
- `task.update`: patches one task.
- `task.archive`: retires one task from active flow.

Expected runtime catalog effect:
- The host uses list for discovery and filtering before selecting a specific task action.

Implementation target:
- Modify `scripts/env/tools/task/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention summaries/id discovery.

### task.get

Current issue:
- Placeholder text does not distinguish one-record read from list, update, or archive.

Target use_when:
- Use when the active buddy needs the current details of one owned task id.

Target do_not_use_when:
- Do not use to search/filter tasks or change task fields.

Distinguish from:
- `task.list`: summary discovery/filtering.
- `task.update`: patches fields.
- `task.archive`: archives the task.

Expected runtime catalog effect:
- The host selects `task.get` only after it has a task id and needs current details.

Implementation target:
- Modify `scripts/env/tools/task/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention one owned task record and read-only behavior.

### task.update

Current issue:
- Placeholder text does not distinguish ordinary field patching from task archival.

Target use_when:
- Use when the active buddy needs to patch an owned task's title, summary, status, or linked track id.

Target do_not_use_when:
- Do not use when the intent is specifically to retire the task from active use; use `task.archive`.

Distinguish from:
- `task.get`: read-only.
- `task.archive`: semantic retirement from active task flow.
- `task.create`: creates a new private task.

Expected runtime catalog effect:
- The host chooses `task.update` for ordinary task edits and `task.archive` for retirement.

Implementation target:
- Modify `scripts/env/tools/task/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that update/archive boundaries are explicit.

### task.archive

Current issue:
- Placeholder text does not explain this is the semantic retirement action, even though status is also patchable.

Target use_when:
- Use when the active buddy intends to remove an owned task from the active task flow by archiving it.

Target do_not_use_when:
- Do not use for ordinary status, title, summary, or track-link edits.

Distinguish from:
- `task.update`: ordinary field patching.
- `track.archive`: PM-only shared track archival.
- `buddybox.delete`: private file deletion.

Expected runtime catalog effect:
- The host uses `task.archive` for task retirement and not as a generic update shortcut.

Implementation target:
- Modify `scripts/env/tools/task/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that archive semantics mention active-flow retirement.

### track.create

Current issue:
- Placeholder text does not surface PM-only shared track lifecycle semantics.

Target use_when:
- Use when PM needs to create a new shared track page with outcome, appetite, and current next step.

Target do_not_use_when:
- Do not use as a non-PM buddy or for private task/artifact creation.

Distinguish from:
- `task.create`: creates private active-buddy work item.
- `artifact.create_revision`: creates private draft content.
- `track.update_now`: changes an existing track.

Expected runtime catalog effect:
- The host understands track creation is a PM-owned shared page lifecycle action.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention PM-owned shared track creation.

### track.list

Current issue:
- Placeholder text does not distinguish summary/id discovery from full track page reads.

Target use_when:
- Use when the active buddy needs non-archived track ids or summaries, optionally filtered by state.

Target do_not_use_when:
- Do not use when a full track page, material refs, proof refs, or timeline is needed; use `track.open`.

Distinguish from:
- `track.open`: full shared track page.
- `context.summarize`: compact runtime orientation across sources.
- `track.create`: creates a new track.

Expected runtime catalog effect:
- The host lists tracks to discover candidate ids, then opens one for details.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that list/open distinction is explicit.

### track.open

Current issue:
- Placeholder text does not explain that this reads one shared track page including refs/timeline, not artifact body content.

Target use_when:
- Use when the active buddy needs the current shared page for one non-archived track, including material/proof refs and timeline updates.

Target do_not_use_when:
- Do not use for full artifact body content; use `artifact.get` with the referenced artifact id.

Distinguish from:
- `track.list`: summary/id discovery.
- `artifact.get`: full body read for referenced artifact.
- `track.update_now`: mutates track state.

Expected runtime catalog effect:
- The host reads track context first and follows artifact refs with `artifact.get` only when full bodies are needed.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics mention refs/timeline and not artifact body.

### track.update_now

Current issue:
- Placeholder text does not distinguish now/state/health mutation from timeline update or artifact publication.

Target use_when:
- Use when the shared track's now, state, or health needs to reflect current progress, blockage, review state, or completion state.

Target do_not_use_when:
- Do not use to publish artifacts or append a standalone decision/progress note without changing now/state/health.

Distinguish from:
- `track.add_update`: appends timeline row without changing current now/state/health intent.
- `track.add_material` / `track.add_proof`: publish artifacts.
- `track.archive`: PM-only track closure.

Expected runtime catalog effect:
- The host updates current track state only when the current status/next step changes.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that update_now is separated from timeline and publication actions.

### track.add_material

Current issue:
- The action publishes a draft artifact as shared material, but placeholder text and one current field description can blur this with timeline updates.

Target use_when:
- Use when an active-buddy-owned draft artifact should become current shared material on a non-archived track.

Target do_not_use_when:
- Do not use for close proof, ordinary timeline updates, comments, or artifact body edits.

Distinguish from:
- `track.add_update`: adds timeline row only and does not publish or change current material refs.
- `track.add_proof`: publishes close proof, not shared material.
- `artifact.create_revision`: creates draft content before publication.

Expected runtime catalog effect:
- The host chooses `track.add_material` only for the material publication transition.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- I1 should align `summary` field description so it does not imply `track.add_material` appends a timeline update row.
- Test in `tests/test_env_tool_semantic_contract.py` that semantics distinguish material publication from update/proof.

### track.add_update

Current issue:
- Placeholder text does not explain that this is timeline-only and does not publish artifacts, even when `kind` is `proof`.

Target use_when:
- Use when the track needs a durable timeline row for progress, decision, blocker, or proof-related note, optionally referencing readable artifacts.

Target do_not_use_when:
- Do not use to publish an artifact, change current material/proof bindings, or hold threaded discussion.

Distinguish from:
- `track.add_material`: publishes draft artifact to current shared material.
- `track.add_proof`: publishes draft artifact to close proof and records proof update.
- `comment.add`: threaded target discussion, not track history.

Expected runtime catalog effect:
- The host treats `track.add_update(kind="proof")` as a timeline note, not proof publication.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that update/proof/material distinctions are asserted.

### track.add_proof

Current issue:
- Placeholder text does not distinguish proof publication from proof-labeled timeline notes or general material publication.

Target use_when:
- Use when an active-buddy-owned draft artifact should become current close proof on a non-archived track and record a proof update.

Target do_not_use_when:
- Do not use for general shared material or for a proof-labeled timeline note that does not publish proof.

Distinguish from:
- `track.add_material`: publishes current shared material.
- `track.add_update`: timeline row only.
- `artifact.update_metadata`: patch artifact body/metadata without publication.

Expected runtime catalog effect:
- The host chooses `track.add_proof` only for the close-proof publication transition.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that close proof publication semantics are explicit.

### track.archive

Current issue:
- Placeholder text does not surface PM-only closure and can be confused with temporary `done`, `review`, or `blocked` state.

Target use_when:
- Use when PM intends to close a shared track page from further normal collaboration.

Target do_not_use_when:
- Do not use as a non-PM buddy or to mark temporary blocked, done, review, or health state; use `track.update_now`.

Distinguish from:
- `track.update_now`: changes current state/health without archiving.
- `task.archive`: private task retirement.
- `track.list`: lists non-archived tracks after archival.

Expected runtime catalog effect:
- The host treats track archival as lifecycle closure, not ordinary status update.

Implementation target:
- Modify `scripts/env/tools/track/tool.py`.
- Test in `tests/test_env_tool_semantic_contract.py` that track archive semantics mention PM and closure.

## Completion Tests

Focused tests:

- `python3 -m unittest tests.test_env_tool_semantic_contract.EnvToolSemanticContractTests.test_registry_semantics_cover_every_registered_tool_and_action`
- `python3 -m unittest tests.test_env_tool_semantic_contract.EnvToolSemanticContractTests.test_operation_semantics_machine_contract_is_preserved`
- Add `test_every_action_has_action_owned_selection_semantics`.
- Add `test_action_semantics_do_not_use_registry_placeholders`.
- Add `test_adjacent_action_boundaries_are_explained`.

Expected output:

- All semantic contract tests pass.
- No action emits `Use when <tool.action> is the intended action`.
- No action emits `Do not use <tool.action> when another action is a closer semantic match`.

Runtime catalog introspection check:

```bash
PYTHONPATH=scripts python3 - <<'PY'
from env.tool_runtime import registry
desc = registry.env_tools_description()
bad = []
for tool, tool_row in desc.items():
    for action, semantic in tool_row["action_semantics"].items():
        text = "\n".join(semantic.get("use_when", []) + semantic.get("do_not_use_when", []))
        if "is the intended action" in text or "closer semantic match" in text:
            bad.append(f"{tool}.{action}")
print("placeholder_semantics=", bad)
raise SystemExit(1 if bad else 0)
PY
```

Expected output:

```text
placeholder_semantics= []
```

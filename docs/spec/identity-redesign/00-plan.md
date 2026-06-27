# Identity Redesign Audit And Plan

## Goal

Rebuild BuddySwitch identity around one public identity shape:

```ts
IdentityRef = {
  id: string,
  type: "actor" | "external"
}
```

The redesign replaces public and persisted "who" fields with identity ids. Auth, routing, display, and session data become projections resolved from identity. The work is rebuild-forward: no long-lived compatibility path, no dual public locator, and no new identity concept outside the memo.

## Required Documents Read

- `AGENTS.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/memo/2026-06-27-identity-system-redesign.md`

## Code Audit

### Runtime Identity And Auth

- Current runtime identity core is `scripts/env/tool_runtime/actor_profile.py`.
- It defines `Actor`, `Role`, `ActorAddress`, `AuthSubject`, `RuntimeActorRecord`, and `ActorProfile`.
- `ActorAddress` is currently `{ actor_id, role_id }`, and it is used both as actor identity and daemon route projection.
- `scripts/env/tool_runtime/context.py` exposes `active_actor`, `active_role`, `actor_id`, `role_id`, `actor_address`, and `auth_subject`; it does not expose `current_identity`.
- `scripts/env/tool_runtime/role_auth.py` correctly authorizes by trusted runtime `role_id`; this should remain a permission projection, not become identity.

### Daemon And Routing

- Daemon routing is actor-address based in `scripts/env/tool_runtime/daemon_client.py`, `tools/launcher/central_daemon_core.py`, `tools/launcher/daemon_mailbox.py`, `tools/launcher/daemon_triggers.py`, `tools/launcher/im_wake_handler.py`, and `tools/launcher/track_comment_added_handler.py`.
- This routing layer can keep `actor_address` internally, but actor-facing and web-facing contracts must stop accepting or returning it as the business locator.
- Delivery code should resolve actor identity to routing projection immediately before daemon calls.

### Message / Conversation

- `scripts/env/repos/messages.py` has two live storage shapes:
  - legacy runtime-workspace rows with `from_actor_address`, `to_actor_address`, and `processed_by_actor_address`;
  - Central IM rows with `participant`, `conversation.participants`, message `from`/`to`, state `participant`, and event `participant`.
- Central IM participants currently use `{ kind: "actor", actor_address }` and `{ kind: "external", external_id }`.
- `scripts/env/services/messages.py` persists `external_id`, authenticates by `connection_key`, creates direct conversations from participant keys, and wakes actor targets via `target_actor_address`.
- `scripts/env/tool_runtime/im_client.py` and `scripts/env/tools/message/tool.py` expose `target_actor_address` in actor-facing `message.send` and `message.conversation`.
- `buddyswitch/skills/shared/message-tool/SKILL.md` still teaches actors to copy `contact.actor_address` into `target_actor_address`.

### Web / External

- `tools/launcher/im_http_router.py` exposes `/api/im/actors`, `POST /api/im/messages` with `to: { kind, actor_address }`, and `/api/im/conversations/direct?kind=actor&role_id=...&actor_id=...`.
- `tools/launcher/web_management.py` exposes web routes that still key events and direct conversations by `role_id + actor_id`.
- `tools/launcher/assets/web-management/app.js` builds URLs and payloads with `role_id`, `actor_id`, and `actor_address`.
- `tools/launcher/web_im_identity.py` persists a server-owned web IM session with `participant` and `connection_key`; it does not yet expose `identity`.

### Product Ownership

- Tracks persist `owner_actor`, update `by_actor`, and relation `from_actor` in `scripts/env/repos/tracks.py`.
- Tasks persist `owner_actor` in `scripts/env/repos/tasks.py`.
- Artifacts persist `created_by_actor`, `author_actors`, and attachment `created_by_actor` in `scripts/env/repos/artifacts.py`.
- Track comments persist `by_actor`, `mentioned_actors`, and `resolved_by_actor` in `scripts/env/repos/track_comments.py`.
- Track tool contracts describe `owner_actor` and `mentioned_actors` in `scripts/env/tools/track/tool.py`.

### Tests And Live Surface Residue

- Existing tests intentionally lock old semantics in files including `tests/test_runtime_actor_profile.py`, `tests/test_message_tool_im_client.py`, `tests/test_im_http_router.py`, `tests/test_im_product_core.py`, `tests/test_track_owner_actor_model.py`, `tests/test_track_comments_repo.py`, `tests/test_artifact_env_tool.py`, and `tests/test_env_tool_semantic_contract.py`.
- `tests/test_env_tool_semantic_contract.py::test_message_catalog_uses_actor_address_identity_language` must be replaced, not preserved.
- Scoped residue counts show old terms across runtime, daemon, web, skill, and tests. Historical docs are not cleanup targets; live surfaces are.

## Field Migration Map

| Current field | Target field | Notes |
| --- | --- | --- |
| `ActorAddress { actor_id, role_id }` as business locator | `IdentityRef { id: actor_id, type: "actor" }` | Keep actor address only as daemon routing projection. |
| `participant: { kind: "actor", actor_address }` | `identity_id` plus hydrated projection when needed | Conversation/message/event/state storage should not persist role as locator. |
| `participant: { kind: "external", external_id }` | `identity_id: external_id` | External identity type resolves from identity registry/projection. |
| `connection.participant` | `connection.identity_id` | `connection_key` remains auth credential only. |
| `conversation.participants` | `conversation.identity_ids` | Direct conversation lookup by current identity and target identity. |
| `message.from` / `message.to` | `from_identity_id` / `to_identity_id` | Direct message remains one recipient for this redesign. |
| `message_state.participant` | `owner_identity_id` | Disposition belongs to identity. |
| `event.participant` | `visible_to_identity_id` | Event visibility belongs to identity. |
| `target_actor_address` tool/API input | `target_identity_id` | Actor/web contract must not expose routing address. |
| `role_id + actor_id` web query | `identity_id` | Role remains display/auth projection only. |
| `track.owner_actor` | `track.owner_identity_id` | Actor-only ownership rules check identity type. |
| `track.updates[].by_actor` | `track.updates[].by_identity_id` | Hydrate display separately. |
| `track.artifact_relations[].from_actor` | `from_identity_id` | This is authorship/provenance, not route. |
| `task.owner_actor` | `task.owner_identity_id` | Taskbox storage remains active actor scoped unless later product need proves otherwise. |
| `artifact.created_by_actor` | `artifact.created_by_identity_id` | Author list becomes `author_identity_ids`. |
| `artifact.author_actors` | `artifact.author_identity_ids` | No display snapshots unless product asks. |
| `comment.by_actor` | `comment.by_identity_id` | Mention/resolution follow identity ids. |
| `comment.mentioned_actors` | `comment.mentioned_identity_ids` | Mention delivery resolves actor identity to route. |
| `comment.resolved_by_actor` | `comment.resolved_by_identity_id` | Owner authority compares identity id. |

## Phase Plan

### Phase 1: Identity Core

Goal: define the shared identity core and projections without changing public contracts yet.

Code targets:

- `scripts/env/tool_runtime/actor_profile.py`
- `scripts/env/tool_runtime/context.py`
- new or renamed focused identity module under `scripts/env/domain/` or `scripts/env/tool_runtime/`
- `tests/test_runtime_actor_profile.py`
- `tests/test_env_tool_identity.py`

Required behavior:

- `IdentityRef(id, type)` validates `type in {"actor", "external"}` and non-empty id.
- Current runtime actor resolves to `IdentityRef(actor_id, "actor")`.
- External connection participant resolves to `IdentityRef(external_id, "external")`.
- Actor identity resolves to daemon `ActorAddress` projection only when routing needs it.
- Auth continues to use `AuthSubject(role_id)`.
- `ToolContext` exposes `current_identity` while preserving internal runtime auth/routing projections only as implementation details for later phases.

### Phase 2: Runtime / Auth / Routing

Goal: keep runtime/auth/routing layered after identity exists.

Code targets:

- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `tools/launcher/central_daemon_core.py`
- `tools/launcher/daemon_mailbox.py`
- `tools/launcher/daemon_triggers.py`
- daemon handler tests

Required behavior:

- Runtime provides trusted `current_identity`.
- Auth still trusts runtime `role_id`, not payload role hints.
- Actor-facing contracts do not expose `actor_address`.
- Daemon internals keep route projection and never treat it as business identity.

### Phase 3: Message / Conversation

Goal: replace message storage and actor-facing message contract with identity ids.

Code targets:

- `scripts/env/repos/messages.py`
- `scripts/env/services/messages.py`
- `scripts/env/tool_runtime/im_client.py`
- `scripts/env/tools/message/tool.py`
- `scripts/env/domain/messages.py`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- message, IM, and semantic contract tests

Required behavior:

- New writes persist `conversation.identity_ids`, `message.from_identity_id`, `message.to_identity_id`, `message_state.owner_identity_id`, `event.visible_to_identity_id`, and `connection.identity_id`.
- Actor tools accept `target_identity_id`, not `target_actor_address`.
- `message.get(message_id)` reads one concrete message only; conversation history is only by current identity plus target identity.
- Reply target derives from the existing direct conversation.
- Actor delivery resolves target actor identity to daemon route.

### Phase 4: Web / External Identity

Goal: make external web session and HTTP contract consume identity ids.

Code targets:

- `tools/launcher/im_http_router.py`
- `tools/launcher/web_management.py`
- `tools/launcher/web_im_identity.py`
- `tools/launcher/assets/web-management/app.js`
- `tests/test_im_http_router.py`
- `tests/test_web_management.py`
- web UI tests

Required behavior:

- Session response returns identity projection.
- `POST /api/web/im/messages` accepts `target_identity_id`.
- `GET /api/web/im/conversations/direct?identity_id=...` reads a direct conversation.
- `connection_key` remains authentication only.
- External identity has no actor runtime or daemon route.

### Phase 5: Product Ownership

Goal: replace track/task/artifact/comment ownership and authorship with identity ids.

Code targets:

- `scripts/env/repos/tracks.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/repos/artifacts.py`
- `scripts/env/repos/track_comments.py`
- `scripts/env/domain/track_read.py`
- `scripts/env/domain/track_comments.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/tools/track/tool.py`
- `scripts/env/tools/task/_impl.py`
- `scripts/env/tools/artifact/_impl.py`
- ownership tests

Required behavior:

- Track/task/artifact/comment new writes use identity fields only.
- Owner checks compare identity ids.
- Actor-only ownership restrictions check `IdentityRef.type == "actor"`.
- Mention/comment delivery resolves identity to daemon route at the delivery boundary.

### Phase 6: Contract Replacement And Verification

Goal: remove old public locator residue and prove end-to-end identity behavior.

Code targets:

- live tool schema and context output
- HTTP API routes and JS client
- shared skills
- tests and focused residue checks

Required behavior:

- No actor-facing or web-facing contract exposes `actor_address`.
- No public locator combines `role_id + actor_id`.
- Old fields only appear in migration readers or daemon-internal routing code.
- End-to-end tests cover actor-to-actor message, external-to-actor message, actor conversation by identity, external conversation by identity, message state by owner identity, daemon delivery through resolver, role auth from runtime role, and product ownership by identity.

## Test Strategy

### Phase 1 Commands

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_env_tool_identity.py -q
```

### Phase 2 Commands

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_role_action_auth.py tests/test_daemon_communication_boundary.py tests/test_daemon_mailbox.py tests/test_daemon_trigger_router.py -q
```

### Phase 3 Commands

```bash
python -m pytest tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_im_external_reply_loop.py tests/test_im_wake_handler.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py -q
```

### Phase 4 Commands

```bash
python -m pytest tests/test_im_http_router.py tests/test_web_management.py tests/test_im_web_management_projection.py -q
npm test -- --runTestsByPath tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

If this repo has no npm test harness available in the current checkout, record the blocker in the phase doc and run the existing JS test command found in `package.json` or the project-local equivalent.

### Phase 5 Commands

```bash
python -m pytest tests/test_track_owner_actor_model.py tests/test_track_comments_repo.py tests/test_track_comment_env_tool.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_env_store_v2.py -q
```

### Phase 6 Commands

```bash
python -m pytest tests/test_runtime_actor_profile.py tests/test_env_tool_identity.py tests/test_message_tool_im_client.py tests/test_im_product_core.py tests/test_im_http_router.py tests/test_web_management.py tests/test_track_owner_actor_model.py tests/test_track_comments_repo.py tests/test_task_env_tool.py tests/test_artifact_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py -q
```

Run broader verification only after focused service-starting tests have lifecycle proof, following `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

## Residue Search Strategy

Search live surfaces only, not old memos or history.

### Actor/Web Public Contract Residue

```bash
rg -n "target_actor_address|actor_address|role_id.*actor_id|actor_id.*role_id" scripts/env/tools scripts/env/tool_runtime/im_client.py tools/launcher/im_http_router.py tools/launcher/web_management.py tools/launcher/assets/web-management buddyswitch/skills/shared tests/test_env_tool_semantic_contract.py tests/test_env_tool_schema_contract.py
```

Expected final result: no actor-facing or web-facing public contract hits. Daemon-internal routing hits are allowed only outside this scope.

### Product Ownership Residue

```bash
rg -n "owner_actor|created_by_actor|author_actors|by_actor|mentioned_actors|resolved_by_actor" scripts/env/repos scripts/env/domain scripts/env/tools tests
```

Expected final result: no new-write path hits except explicitly documented one-time migration inputs, if any.

### Message Storage Residue

```bash
rg -n "conversation\\.participants|message_state.*participant|event.*participant|from_actor_address|to_actor_address|processed_by_actor_address|external_id" scripts/env/repos/messages.py scripts/env/services/messages.py tests/test_im_product_core.py tests/test_message_tool_im_client.py
```

Expected final result: no new-write path hits; `external_id` may remain only inside identity creation/resolution.

## First Phase Entry

Start Phase 1 with `docs/spec/identity-redesign/phase-01-identity-core.md`.

First failing test:

- Add identity core assertions to `tests/test_runtime_actor_profile.py`.
- Verify the test fails because `IdentityRef` and `current_identity` do not exist yet.

First implementation target:

- Introduce the smallest shared identity core used by runtime actor profile and external IM auth.
- Add `current_identity` to `ActorProfile` and `ToolContext`.
- Add resolver helpers for actor identity to daemon route projection and external participant to identity.

Do not change message, web, or ownership public contracts in Phase 1. Those are gated by later phase docs and tests.

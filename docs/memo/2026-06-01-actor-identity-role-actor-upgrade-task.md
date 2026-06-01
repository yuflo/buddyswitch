# Actor Identity -> Role / Actor Upgrade Task

Date: 2026-06-01
Status: rebuild memo

## 1. One-Line Goal

Rebuild BuddySwitch identity into one module:

```text
Actor Identity
├── Role
└── Actor
```

After this upgrade, live runtime code, schemas, tools, launcher UI, skills, and tests should use only `Role`
and `Actor` for business identity. The old `buddy` identity wording should not remain as aliases,
compatibility fields, or parallel paths.

## 2. Trigger

The concrete failure came from PM-to-PM messaging.

The runtime could discover several online PM participants, but `message.contacts` marked every PM target
as not sendable:

```text
sendable=false
why_not_sendable="message.send rejects targets with the same buddy_id as the active actor"
```

This is not only a `message` bug. It exposed the deeper identity confusion:

- `buddy_id` is actually a role such as `pm`, `market`, `design`, `dev`, or `test`.
- `instance_id` is the only thing distinguishing concrete running participants, but it is named like a runtime detail.
- Message delivery incorrectly treats same role as same participant.
- Auth already behaves like role-based auth, but its source data still comes through buddy-shaped names.
- Launcher, daemon, object repos, tool responses, skills, and contracts reinforce the same ambiguity.

The product capability we need is simple:

```text
Two PM actors are both Role=pm, but they are different Actors and can message each other.
```

## 3. Final Concepts

There are only three concepts to keep in the mental model.

### 3.1 Actor Identity

`Actor Identity` is the module / boundary that owns runtime participant identity.

It owns:

- Role definitions.
- Actor definitions.
- Actor address parsing and serialization.
- Runtime actor profile construction.
- The bridge from actor identity into role auth.

It does not own:

- business object visibility rules;
- message-specific sendability;
- request lifecycle policy;
- runtime process management beyond identity fields.

### 3.2 Role

`Role` is a capability and responsibility class.

Examples:

```text
pm
market
design
dev
test
```

Role is used for:

- auth policy;
- tool/action permission;
- role-specific skills;
- role contracts and AGENTS guidance;
- artifact template allowlists;
- role-scoped request queues;
- browser/tool capability profiles.

Role is not used for:

- direct message recipient identity;
- object author identity;
- exact task owner identity;
- online presence identity;
- daemon mailbox routing;
- self-send checks.

### 3.3 Actor

`Actor` is a concrete participant in the system.

Minimum shape:

```json
{
  "actor_id": "act-pm-218214e45145",
  "role_id": "pm"
}
```

Actor is used for:

- direct message sender and recipient;
- online contact identity;
- daemon registration and reachability;
- comments, artifact authorship, and action authorship;
- task ownership;
- request requester and lifecycle operators;
- current tool runtime context;
- actor-private workspace ownership.

An `ActorAddress` is the routeable identity payload:

```json
{
  "actor_id": "act-pm-218214e45145",
  "role_id": "pm"
}
```

Rules:

- `actor_id` is the concrete identity key.
- `role_id` is the capability class.
- Same `role_id` does not mean same actor.
- Same `actor_id` means same actor.
- Direct messaging rejects only same `actor_id`.

## 4. What Happens To Instance

`instance` should stop being a business identity concept.

If the launcher still needs a runtime/process record, keep it internal and name it plainly as runtime state:

```text
actor_run_id
runtime_process_id
actor_runtime_record
```

Do not expose `instance_id` as message identity, object author, task owner, or tool response identity.

Public product language should become:

```text
role list
role show
actor start --role pm
actor status <actor-id>
actor input <actor-id>
actor stop <actor-id>
```

Final shipped public surfaces should use `actor`, not `instance`, for the concrete participant.

## 5. Auth Model

Auth answers only this question:

```text
Does this Actor's Role allow this action?
```

Input:

```text
actor.role_id
action permission
role policy
```

Output:

```text
allowed / denied
reason
allowed_roles
required_permission
```

Auth should not answer:

- whether an actor can message itself;
- whether a request lifecycle transition is valid;
- whether an artifact draft is editable by this actor;
- whether a track object is visible;
- whether a target actor is online.

Those are domain rules and must compare concrete actor fields or object fields.

`AuthSubject(role_id)` can remain as an internal auth input if useful, but it is not a third business
identity concept.

## 6. Locked Rebuild Rules

This task is a rebuild, not a compatibility migration.

Rules:

- No live `buddy_id` alias.
- No live `active_buddy` alias.
- No public `--buddy` flag.
- No message/object schema accepting both old and new fields.
- No silent normalization from old buddy fields into new actor fields.
- No adapter layer that preserves the old model.
- No generic identity provider or broad permission framework.
- Historical docs may mention old terms as history, but live code, schemas, tests, skills, contracts,
  and AGENTS templates should not.

The development environment can be rebuilt forward. Unless production data migration is explicitly
required later, old runtime objects do not need compatibility handling.

## 7. Field Conversion

| Old field / concept | New field / concept | Rule |
| --- | --- | --- |
| `buddy_id` | `role_id` | Old value represented role class. |
| `active_buddy` | `active_role` plus `active_actor` | Context must expose both role and actor. |
| `instance_id` | `actor_id` for business identity | Runtime process ids, if needed, stay internal. |
| `RuntimeActorAddress` | `ActorAddress` | Payload is `{actor_id, role_id}`. |
| `RuntimeActorProfile` | `ActorProfile` | Profile contains Actor, Role, address, auth subject. |
| `manifest.buddies` | `manifest.roles` | Manifest rows are role definitions. |
| `from_buddy` | `from_actor` or `from_role` | Choose by domain meaning; message uses actor. |
| `to_buddy` | `to_actor` or `to_role` | Direct message uses actor; request queue uses role. |
| `by_buddy` | `by_actor` | Actions are performed by concrete actors. |
| `owner_buddy` | `owner_actor` or `owner_role` | Task uses actor; track usually uses role. |
| `created_by` | `created_by_actor` | Authorship is actor identity. |
| `authors` | `author_actors` | Actor list, not role list. |
| `mentions` | `mentioned_actors` | Role-wide work should use requests, not mentions. |
| `buddybox` | actor private workspace | Recommended path: `workspace/private`. |

## 8. Module Responsibilities And Required Changes

### 8.1 Actor Identity Core

Files:

- `scripts/env/tool_runtime/actor_profile.py`
- `tests/test_runtime_actor_profile.py`
- `tests/test_env_tool_identity.py`

Required changes:

- Define `Role`, `Actor`, `ActorAddress`, `ActorProfile`, and `RuntimeActorRecord`.
- Use `ROLE_ID_PATTERN` for roles.
- Use `ACTOR_ID_PATTERN` for actor ids.
- `ActorAddress.to_payload()` returns only `{"actor_id": "...", "role_id": "..."}`.
- `ActorAddress.from_payload()` rejects old fields and presence/runtime fields.
- Remove old runtime address/profile classes from live imports.

### 8.2 Role Auth

Files:

- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tool_runtime/auth_feedback.py`
- `tests/test_role_action_auth.py`

Required changes:

- Read declared roles from `manifest.roles`.
- Authorize by `actor.role_id`.
- Rejection payloads expose `active_role`, not `active_buddy`.
- Permission boundary remains simple role-action auth.

### 8.3 Tool Runtime Context And Results

Files:

- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `tools/launcher/env_tool_mcp_server.py`
- response/payload/schema contract tests

Required changes:

- Dispatch uses trusted `actor_id` and `role_id`.
- `ToolContext` exposes:

```text
active_actor
active_role
actor_id
role_id
actor_address
actor_private_dir
```

- Success and rejection responses include `active_actor` and `active_role`.
- Responses must not include `active_buddy` or `buddy_id`.
- Payload spoofing cannot override trusted runtime actor identity.

### 8.4 Manifest, Role Profiles, Skills, And Contracts

Files:

- `buddyswitch/manifest.toml`
- `scripts/env_manifest.py`
- `scripts/env_profiles.py`
- `buddyswitch/env-profiles/*.json`
- `framework/contracts/*.md`
- `framework/contracts/role-env-profile.json`
- `buddyswitch/skills/**/SKILL.md`
- `tools/launcher/assets/roles/*/AGENTS.md`
- repo consistency tests

Required changes:

- `[[buddies]]` becomes `[[roles]]`.
- `list-buddies` / `show-buddy` become `list-roles` / `show-role`.
- Env profiles use `role_id`.
- Role contracts teach Role and Actor.
- Active skills explain new tool fields.
- AGENTS templates live under `assets/roles/<role_id>`.
- Active guidance must not tell agents to use old buddy fields or `--buddy`.

### 8.5 Launcher, CLI, And Web Management

Files:

- `buddyswitch-codex`
- `tools/launcher/instance.sh`
- `tools/launcher/env.sh`
- `tools/launcher/web_management.py`
- `tools/launcher/assets/web-management/app.js`
- `tools/launcher/codex_config.py`
- launcher and web tests

Required public surface:

```text
buddyswitch-codex role list [--json]
buddyswitch-codex role show <role-id> [--json]
buddyswitch-codex actor start --role <role-id> [--json]
buddyswitch-codex actor list [--role <role-id>] [--json]
buddyswitch-codex actor status <actor-id> [--json]
buddyswitch-codex actor input <actor-id> --text <text>
buddyswitch-codex actor stop <actor-id> [--json]
```

Required runtime record shape:

```json
{
  "actor_id": "act-pm-218214e45145",
  "role_id": "pm",
  "status": "active",
  "actor_root": "...",
  "workspace_dir": "...",
  "updated_at": "..."
}
```

Required changes:

- Public CLI uses actor and role words.
- Web API exposes `/api/roles` and actor resources.
- Web UI labels use Role / Actor.
- `BUDDYSWITCH_INSTANCE_ID` becomes `BUDDYSWITCH_ACTOR_ID` on public/runtime tool surfaces.
- `BUDDYSWITCH_ACTIVE_BUDDY` is removed.

### 8.6 Central Daemon, Mailbox, And Signals

Files:

- `tools/launcher/central_daemon_core.py`
- `scripts/env/tool_runtime/daemon_client.py`
- `tools/launcher/daemon_core.py`
- `tools/launcher/daemon_mailbox.py`
- `tools/launcher/message_available_handler.py`
- daemon and mailbox tests

Required changes:

- Registry key is `actor_id`.
- Contact rows contain `actor_address`, `actor_id`, `role_id`, `contact_status`, and reachability metadata.
- Contact filtering uses `role_id`.
- Signal envelopes use `source_actor_address` and `target_actor_address`.
- Mailbox target matching uses ActorAddress / actor id equality.

### 8.7 Message Tool

Files:

- `scripts/env/domain/messages.py`
- `scripts/env/repos/messages.py`
- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/message/_impl.py`
- `tests/test_message_env_tool.py`

Required changes:

- Message is Actor-to-Actor.
- Send input uses `target_actor_address={actor_id, role_id}`.
- Stored rows use `from_actor_address` and `to_actor_address`.
- `contacts` filter is role-based, named `role` or `role_id`.
- `list` and `conversation` filter by actor address or role according to explicit parameter names.
- Same actor self-send is rejected.
- Same role different actor send is allowed.

Required product proof:

```text
Actor A: {actor_id: act-pm-1, role_id: pm}
Actor B: {actor_id: act-pm-2, role_id: pm}
message.send A -> B succeeds
message.send A -> A fails
```

### 8.8 Request Tool

Files:

- `scripts/env/domain/requests.py`
- `scripts/env/repos/requests.py`
- `scripts/env/tools/request/tool.py`
- `scripts/env/tools/request/_impl.py`
- request tests

Required model:

```text
from_actor
to_role
status
accepted_by_actor
blocked_by_actor
completed_by_actor
canceled_by_actor
```

Required changes:

- Main path is role queue request, not direct buddy request.
- Requester visibility uses `from_actor`.
- Work queue visibility uses `to_role`.
- Lifecycle operators are concrete actors.
- PM override, if kept, is explicit role policy.

### 8.9 Task And Taskbox

Files:

- `scripts/env/domain/tasks.py`
- `scripts/env/domain/task_management.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/task/_impl.py`
- `tools/launcher/task_checkout_handler.py`
- `tools/launcher/input_wrappers/task_tui.py`
- task tests

Required changes:

- Task owner is `owner_actor`.
- Current task snapshot is keyed by `actor_id`.
- Taskbox/private state is actor-scoped.
- Checkout context uses active actor, not role as identity.

### 8.10 Track

Files:

- `scripts/env/repos/tracks.py`
- `scripts/env/domain/publication.py`
- `scripts/env/tools/track/tool.py`
- `scripts/env/tools/track/_impl.py`
- track tests

Recommended model:

```text
owner_role
created_by_actor
updates[].by_actor
shared_materials[].from_actor
close_proof[].from_actor
```

Reason:

- Track is a product work surface, often owned by a role such as PM.
- Actions on the track are performed by concrete actors.

### 8.11 Artifact

Files:

- `scripts/env/repos/artifacts.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/domain/artifact_relations.py`
- `scripts/env/domain/source_refs.py`
- `scripts/env/tools/artifact/tool.py`
- `scripts/env/tools/artifact/_impl.py`
- `scripts/artifact_selection.py`
- artifact tests

Required model:

```text
created_by_actor
author_actors
attachments[].created_by_actor
```

Required changes:

- Template permission uses active role.
- Draft edit ownership uses active actor.
- Shared material visibility uses track publication, not buddy identity.
- Private source refs use actor private workspace naming.

### 8.12 Comment

Files:

- `scripts/env/repos/comments.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/tools/comment/tool.py`
- `scripts/env/tools/comment/_impl.py`
- comment tests

Required model:

```text
by_actor
mentioned_actors
resolved_by_actor
```

Role-wide work should go through requests, not comment mentions.

### 8.13 Context Projection

Files:

- `scripts/env/tools/context/tool.py`
- `scripts/env/tools/context/_impl.py`
- `framework/contracts/prepare-turn-context.json`
- context binding tests

Required changes:

- Top-level context exposes `active_actor`, `active_role`, and `actor_address`.
- Candidate object summaries use actor/role field names.
- Writable private surfaces use actor private workspace wording.
- Context does not expose old buddy identity keys.

### 8.14 Actor Private Workspace

Files:

- `scripts/env/repos/buddybox_files.py`
- `scripts/env/domain/buddybox_workspace.py`
- `scripts/env_cleanup.py`
- `tools/launcher/workspace.sh`
- `tools/launcher/codex_config.py`
- `tools/launcher/app_server.sh`
- cleanup / attachment / env-layer tests

Required target:

```text
<actor-root>/workspace/private
BUDDYSWITCH_ACTOR_PRIVATE_DIR
```

Required changes:

- Rename live concept from buddybox to actor private workspace.
- Rename source ref type from old private buddy wording to `actor_private` or `private_file`.
- Cleanup category should describe actor private files.

### 8.15 Search, Browser, And Evidence

Files:

- `scripts/env/tools/search/_impl.py`
- `scripts/env/tools/evidence/tool.py`
- `scripts/env/tools/evidence/_impl.py`
- `tools/launcher/browser_cockpit.sh`
- search/evidence/browser tests

Required changes:

- Browser capability derives from active role.
- Evidence authors and approvers, if stored, are actors.
- Market-specific behavior remains role policy.
- No browser path should infer identity from active buddy.

### 8.16 Runtime Store And Cleanup

Files:

- `scripts/env_store.py`
- `scripts/env_legacy_store.py`
- `scripts/env_cleanup.py`
- runtime store and cleanup tests

Required changes:

- Live runtime store exports actor/role fields only.
- Legacy store code must not be in the main runtime path.
- Cleanup understands actor roots and actor private workspace.
- Do not normalize old object fields in the live repos.

## 9. Rebuild Sequence

### Phase 1: Lock Target Tests

Add or update tests that prove:

- ActorAddress uses only `{actor_id, role_id}`.
- Role auth reads `manifest.roles`.
- Same-role different-actor messages are allowed.
- Same actor messages are rejected.
- Tool responses expose `active_actor` and `active_role`.
- Old identity keys are rejected or absent.

### Phase 2: Replace Identity Core

Implement:

- `Role`
- `Actor`
- `ActorAddress`
- `ActorProfile`
- runtime actor record construction
- result and rejection payload changes

Remove old runtime identity classes from live imports.

### Phase 3: Replace Manifest, Profiles, Launcher Surface

Implement:

- `manifest.roles`
- role profile contract
- role skill/contract paths
- actor start/list/status CLI
- actor runtime record
- web roles/actors surface

No `--buddy` public compatibility path.

### Phase 4: Replace Daemon And Message

Implement:

- daemon registry keyed by actor id;
- contact filter by role id;
- ActorAddress in signal/mailbox payloads;
- message send/list/conversation actor semantics.

This phase proves the original PM-to-PM failure is fixed.

### Phase 5: Replace Collaboration Object Fields

Implement object field replacements for:

- artifact;
- track;
- request;
- comment;
- task.

Do not keep old and new fields side by side.

### Phase 6: Replace Actor Private Workspace Naming

Implement:

- actor private directory;
- env var rename;
- source ref rename;
- cleanup and writable-root changes.

### Phase 7: Replace Active Guidance

Implement:

- skills;
- role contracts;
- AGENTS templates;
- repo consistency checks.

Agents should learn the new model from guidance, not rediscover it from code.

### Phase 8: Verify Full Path

Required verification groups:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_role_action_auth.py -q
python3 -m pytest tests/test_central_daemon_service.py tests/test_message_env_tool.py -q
python3 -m pytest tests/test_request_env_tool.py tests/test_artifact_env_tool.py tests/test_track_env_tool.py -q
python3 -m pytest tests/test_comment_env_tool.py tests/test_task_env_tool.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_buddyswitch_launcher.py tests/test_web_management.py -q
python3 -m pytest tests/test_repo_consistency.py -q
```

Then run one product smoke:

```text
start PM actor A
start PM actor B
A lists contacts filtered by role pm
A sends message to B
B receives message available signal
B reads inbox
```

## 10. Residual Checks

Live code, schemas, tests, skills, contracts, and launcher assets should pass zero-residual checks for
retired business identity fields:

```bash
rg -n "buddy_id|active_buddy|from_buddy|to_buddy|by_buddy|owner_buddy|private_to_buddy" \
  scripts tools framework buddyswitch tests

rg -n "\\bbuddies\\b|\\b--buddy\\b|BUDDYSWITCH_ACTIVE_BUDDY|BUDDYSWITCH_BUDDYBOX_DIR" \
  scripts tools framework buddyswitch tests
```

`buddybox` should also be removed from live concepts after the actor private workspace phase. If old
historical docs mention the retired words, they should be excluded from live consistency checks explicitly.

## 11. Done Criteria

The upgrade is done only when:

1. `Actor Identity -> Role / Actor` is the only live identity model.
2. Same-role different-actor direct messages work.
3. Same-actor self messages are rejected.
4. Auth uses role policy derived from the current actor.
5. Collaboration objects record actor authorship/action and role routing only where role routing is intended.
6. Launcher and Web UI expose roles and actors, not buddies.
7. Private workspace naming is actor-scoped.
8. Active skills, contracts, and AGENTS templates teach the new model.
9. No live compatibility aliases or dual paths remain.
10. Focused tests and relevant broad tests pass.

## 12. Non-Goals

Do not add:

- generic identity provider;
- multi-tenant auth framework;
- actor groups beyond Role;
- workflow engine;
- broad permission DSL;
- migration adapter for old runtime objects;
- long-lived fallback parsing for old object fields;
- separate Session concept before repeated real usage proves Actor needs it.

## 13. Decisions Already Locked

Locked:

- `buddy_id` is replaced by `role_id`.
- concrete participant identity is `actor_id`.
- `Role` and `Actor` live under Actor Identity.
- direct message identity is Actor-to-Actor.
- request main path is `from_actor -> to_role`, with lifecycle actors.
- track ownership is role-level by default; actions are actor-level.
- no compatibility residue or transition layer.

Still implementation-local:

- exact internal name for a hidden runtime process id, if one remains: prefer `actor_run_id` or
  `runtime_process_id`;
- exact actor private source-ref type name, either `actor_private` or `private_file`;
- exact mechanical patch order.

Because the user explicitly disallowed residual transition, the final shipped state uses one public naming path:
Role for capability class, Actor for concrete participant.

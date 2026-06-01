# Actor Identity Final Rebuild Task

Date: 2026-06-01
Status: confirmed execution memo
Supersedes for execution: `docs/memo/2026-06-01-actor-identity-role-actor-upgrade-task.md`

## 1. Goal

Unify BuddySwitch runtime identity to:

```text
Actor Identity
├── Role
└── Actor
```

The final live system has one identity model:

- `Role`: capability and responsibility class, for example `pm`, `dev`, `market`, `design`, `test`.
- `Actor`: concrete runtime participant, identified by `actor_id`, always carrying its `role_id`.

`instance` remains only a launcher/runtime/process/path concept. It is not an auth subject, message subject,
object owner, private-workspace owner, or product identity concept.

This is a rebuild-forward task. Do not preserve old `buddy` / `buddybox` aliases, compatibility fields, or
parallel old/new paths.

## 2. Locked Concept Rules

### Role

Use `Role` for:

- tool/action permissions;
- role-specific skills and guidance;
- artifact template allowlists;
- request work queues such as `to_role`;
- track role ownership where the product surface is role-owned;
- browser/search capability profiles.

Do not use `Role` for:

- direct message identity;
- private draft ownership;
- task owner identity;
- actor private workspace ownership;
- self-send checks;
- authorship or executor provenance.

### Actor

Use `Actor` for:

- direct message sender and recipient;
- online contact address;
- message inbox ownership;
- private workspace ownership;
- task ownership;
- draft artifact ownership;
- artifact author identity;
- comment author and resolver identity;
- request requester and lifecycle operator identity;
- tool execution provenance;
- evidence token issuer provenance.

Canonical actor payload:

```json
{
  "actor_id": "act-pm-1b66ce8773ca",
  "role_id": "pm"
}
```

Same `role_id` does not mean same participant. Same `actor_id` means same participant.

### Instance

Keep `instance` only for runtime storage/process/path implementation where needed:

- actor runtime root;
- workspace path;
- process metadata;
- browser process/port;
- launcher lifecycle.

Do not expose instance as ownership, auth, private scope, or message identity.

## 3. Current Confirmed Findings

### Message

Runtime behavior is already actor-correct:

- same `actor_id` send is rejected;
- same `role_id` but different `actor_id` send is allowed;
- contacts mark only the active actor itself as not sendable.

Remaining message work is contract and wording cleanup only.

### Artifact Draft

Runtime behavior is not actor-correct yet.

Private draft visibility still has role-scoped checks through `artifact_read_decision(artifact, active_role)`.
That means same-role different actors can incorrectly be treated as draft owners.

This is a real behavior bug, not only documentation drift.

### Tool Result

`ToolResult` is not strict enough.

When a tool omits `active_actor`, the response helper can fall back to a role-only payload. The broker normally
overwrites this with full actor data, but the helper still encodes a compatibility path. Final state must require
complete `active_actor={actor_id, role_id}` in every success and rejection response.

### Evidence

Evidence target authorization already checks actor authorship, but issued token metadata still records only
`active_role`. Final state must record the issuing actor.

### Context

`context` still has an old artifact candidate check using `created_by` against `active_role`. Final state must
delete that path and use `created_by_actor` / `active_actor`.

### Buddybox

`buddybox` is not a real shared role box. The actual active private directory is per actor runtime workspace:

```text
<actor runtime workspace>/private
```

The live formal concept must be `Actor private workspace`.

## 4. Required Behavior Changes

### 4.1 Artifact Draft Actor Isolation

Private draft artifacts must be readable only by the creating actor.

Required rule:

```text
artifact.status == "draft"
read allowed only when artifact.created_by_actor.actor_id == active_actor.actor_id
```

Same-role different actors must not be able to:

- `artifact.get` the draft;
- see it in `artifact.list`;
- see it in `context.summarize` / `context.get` candidate artifacts;
- comment on it;
- list or get its attachments;
- use it in source refs with `read_claim="summarized-full-content"`;
- supersede it;
- reference it through track update refs unless it is published to a readable track.

Files to update:

- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/domain/source_refs.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/domain/artifact_relations.py`
- `scripts/env/tools/artifact/_impl.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/track/_impl.py`
- affected artifact/comment/context/track tests

Implementation notes:

- Change `artifact_read_decision` to receive active actor identity, not only active role.
- Keep published artifact readability tied to track publication/readability.
- Keep template permission role-based.
- Keep draft edit/delete ownership actor-based.
- Remove any fallback to retired artifact fields such as `created_by`.

### 4.2 Context Artifact Candidate Cleanup

Remove stale candidate logic:

```text
artifact.get("created_by") == active_role
```

Final candidate rules:

- published material/proof candidates are visible through readable tracks;
- private draft candidates are visible only to `created_by_actor.actor_id == active_actor.actor_id`;
- context output never leaks same-role other-actor drafts.

Primary file:

- `scripts/env/tools/context/_impl.py`

### 4.3 ToolResult Active Actor Hardening

Every env tool response must include:

```json
{
  "active_actor": {
    "actor_id": "...",
    "role_id": "..."
  },
  "active_role": "..."
}
```

Required changes:

- remove role-only fallback from `scripts/env/tool_runtime/results.py`;
- make `active_actor` required for `tool_results.success`;
- make `active_actor` required for `tool_results.rejection`;
- update all tool handlers that currently rely on broker overwrite or role-only fallback;
- keep broker overwrite as a final normalization guard, not as the only source of correctness.

Likely handler groups to update:

- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/request/_impl.py`
- `scripts/env/tools/search/_impl.py`
- `scripts/env/tools/evidence/_impl.py`
- `scripts/env/tools/task/_impl.py`
- any local rejection helper that accepts only `active_role`

### 4.4 Evidence Issuer Provenance

Evidence token metadata must record the concrete actor that issued it.

Required final token fields:

```json
{
  "token_id": "...",
  "target_type": "artifact",
  "target_id": "...",
  "issued_by_actor": {
    "actor_id": "...",
    "role_id": "..."
  },
  "mode": "...",
  "evidence_kind": "...",
  "issued_at": "..."
}
```

Do not keep `active_role` as the primary issuer field. If role is useful, derive it from `issued_by_actor.role_id`.

Files:

- `scripts/env/tools/evidence/_impl.py`
- evidence tests / response contract tests

## 5. Required Naming And Contract Cleanup

### 5.1 Message Contract Wording

Do not change message behavior unless tests prove otherwise. Clean the live contract wording.

Replace:

- `Role Messages`
- `message.direct_role_channel`
- `target_actor_address is online and not the active role`
- `Active role cannot send to another actor with the same role id`
- `active-role inbox`

With:

- direct actor-address messages;
- direct actor-address channel;
- target actor is online and not the active actor;
- active actor cannot send to itself;
- active actor inbox.

Files:

- `scripts/env/tools/message/tool.py`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- message semantic/contract tests

### 5.2 Buddybox To Actor Private Workspace

Remove `buddybox` as a live formal concept.

Replace:

- `Buddybox`
- `buddybox`
- `$BUDDYSWITCH_BUDDYBOX_DIR`
- role-private file wording

With:

- `Actor private workspace`
- `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`
- active actor private file/workspace wording

Final path:

```text
<actor runtime workspace>/private
```

No alias, no fallback env var, no old path compatibility.

Files and surfaces:

- `tools/launcher/assets/roles/*/AGENTS.md`
- `buddyswitch/skills/**/SKILL.md`
- `scripts/env/tools/*/tool.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/repos/actor_private_files.py`
- launcher env / app server / codex config files that describe private writable roots
- repo consistency tests

Important implementation detail:

- `tools/launcher/assets/roles/*/AGENTS.md` may currently be ignored by git because of a broad `AGENTS.md`
  ignore rule. Ensure the corrected templates are actually tracked or the ignore rule is adjusted for this
  repository path.

Started instances are explicitly out of scope. Do not edit:

```text
/Users/chen/.codex-buddyswitch/instances/*/workspace/AGENTS.md
```

### 5.3 Actor Private File Summary

Remove role-owned summary fields.

Replace:

```text
private_to_role
```

With an actor-scoped field such as:

```text
owner_actor
```

or:

```text
private_to_actor
```

Prefer `owner_actor` if the row describes ownership, because it matches task/artifact provenance vocabulary.

Files:

- `scripts/env/repos/actor_private_files.py`
- `scripts/env/domain/actor_private_workspace.py`
- `scripts/env/tool_runtime/context.py`
- context/private workspace tests

### 5.4 Task And Context Wording

Task behavior is already instance-root actor scoped and records `owner_actor`, but public wording still implies
role-private state.

Replace:

- `active-role private`
- `active role's taskbox`
- `private work item for the active role`
- `instance-local active-role taskbox`

With:

- `active actor private task state`
- `active actor taskbox`
- `private work item for the active actor`
- `instance-local active-actor taskbox`

Files:

- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/task/_impl.py`
- `scripts/env/tools/context/_impl.py`
- task/context semantic tests
- runtime skills that mention active-role-private tasks

Do not turn `taskbox/<role>` into a public role-private concept. If the underlying path remains for now, it must
remain an implementation detail inside the actor runtime root.

### 5.5 Old Private Root Removal

Delete old root compatibility and old path references from live code.

Remove/replace live references such as:

- `runtime_files.ACTOR_PRIVATE_DIR = LOCAL_ROOT / "actor-private"`
- `env_store.ACTOR_PRIVATE_DIR`
- `env_legacy_store.ACTOR_PRIVATE_DIR`
- launcher skeleton paths under `buddyswitch/local/actor-private`
- scans/tests that assume the old private root is valid

Keep the only live root:

```text
runtime_files.actor_private_dir(...) -> runtime_workspace_root(...) / "private"
```

## 6. Confirmed Non-Behavior Changes

### Request

Keep request routing as:

```text
from_actor -> to_role
```

This is a role work queue, not a missed actor migration.

Actor-scoped parts that must remain:

- requester visibility uses `from_actor`;
- `request.cancel` is requester actor scoped;
- `accepted_by_actor`, `blocked_by_actor`, `completed_by_actor`, `canceled_by_actor` record concrete actors.

Only update wording if it implies buddy identity or role-private ownership.

### Track

Track is shared product state.

Keep:

- `owner_role` where the track is role-owned product work;
- PM role policy for create/archive if still intended;
- `created_by_actor`, `updates[].by_actor`, `shared_materials[].from_actor`, `close_proof[].from_actor`.

Do not force track ownership to Actor unless a separate product decision asks for actor-owned tracks.

### Search

Search is not an ownership surface.

Keep:

- role-derived capability profile;
- instance/browser execution path.

Only update `ToolResult active_actor` plumbing and wording that says active-role runtime orientation where it
misleads about ownership.

### Auth

Keep role-action auth.

Final auth rule:

```text
Role authorizes. Actor executes.
```

Auth answers whether the current actor's role can use an action. It does not answer object ownership,
message reachability, private draft visibility, request lifecycle validity, or target online status.

Do not build a generic identity provider or broad permission framework.

## 7. File Groups To Touch

### Core runtime identity/result layer

- `scripts/env/tool_runtime/actor_profile.py`
- `scripts/env/tool_runtime/context.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/tool_runtime/role_auth.py`
- `scripts/env/tool_runtime/auth_feedback.py`

### Artifact and visibility layer

- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/domain/artifact_relations.py`
- `scripts/env/domain/source_refs.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/tools/artifact/_impl.py`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/track/_impl.py`

### Tool contract and implementation layer

- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/context/tool.py`
- `scripts/env/tools/task/tool.py`
- `scripts/env/tools/request/tool.py`
- `scripts/env/tools/comment/tool.py`
- `scripts/env/tools/evidence/tool.py`
- `scripts/env/tools/evidence/_impl.py`
- `scripts/env/tools/search/_impl.py`
- `scripts/env/tools/request/_impl.py`
- `scripts/env/tools/task/_impl.py`

### Actor private workspace layer

- `scripts/env/repos/actor_private_files.py`
- `scripts/env/domain/actor_private_workspace.py`
- `scripts/env/repos/runtime_files.py`
- `scripts/env_store.py`
- `scripts/env_legacy_store.py`
- `scripts/env_cleanup.py`
- `tools/launcher/env.sh`
- `tools/launcher/app_server.sh`
- `tools/launcher/codex_config.py`
- `tools/launcher/assets/roles/*/AGENTS.md`

### Skills and live guidance

- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/**/SKILL.md` where they mention active-role-private or buddybox
- role AGENTS templates under `tools/launcher/assets/roles`

## 8. Test Requirements

Add or update tests for these behaviors.

### Message

- same role different actor can send;
- same actor self-send is rejected;
- contacts mark only same actor as not sendable;
- live message guidance does not say same-role actors cannot send.

### Artifact draft isolation

- same role different actor cannot `artifact.get` another actor's draft;
- same role different actor cannot see another actor's draft in `artifact.list`;
- same role different actor cannot list/get another actor draft attachments;
- same role different actor cannot comment on another actor's draft;
- same role different actor cannot use another actor's draft for source-ref full-read claim;
- same role different actor cannot supersede another actor's draft;
- own actor can still read, list, update, attach, and supersede its own draft.

### Context

- `context.summarize` and `context.get` do not leak same-role other-actor draft candidates;
- context candidate artifact logic does not depend on retired `created_by`;
- writable surfaces say actor private workspace.

### ToolResult

- every success response includes full `active_actor`;
- every rejection response includes full `active_actor`;
- direct calls to response helpers without `active_actor` fail fast or are impossible by signature;
- no response helper returns `{"role_id": "..."}` as a complete actor.

### Evidence

- evidence issue token includes `issued_by_actor`;
- evidence downgrade token includes `issued_by_actor`;
- token issuer role, if needed, is derived from `issued_by_actor.role_id`;
- evidence target authorization remains actor-authored.

### Actor private workspace

- private file summary no longer contains `private_to_role`;
- private workspace descriptor uses owner actor semantics;
- launcher exports `$BUDDYSWITCH_ACTOR_PRIVATE_DIR`;
- no live code exports or requires `$BUDDYSWITCH_BUDDYBOX_DIR`;
- new role AGENTS templates contain actor private workspace wording.

### Auth/request/track/search guardrails

- auth denial includes full `active_actor` and role-policy details;
- request still routes to `to_role` and records lifecycle actor fields;
- track create/update/publication records actor provenance;
- search responses include full `active_actor` but keep role capability profile.

## 9. Suggested Verification Commands

Run focused tests first:

```bash
python3 -m pytest tests/test_message_env_tool.py -q
python3 -m pytest tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_runtime_actor_profile.py -q
python3 -m pytest tests/test_env_tool_identity.py -q
python3 -m pytest tests/test_runtime_broker.py -q
```

Run contract and guidance tests:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_runtime_skills.py -q
python3 -m pytest tests/test_repo_consistency.py -q
```

Run launcher/private workspace tests:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_clean_runtime_environment.py -q
python3 -m pytest tests/test_env_layer_end_to_end.py -q
```

Run scans against live surfaces. Historical docs may be excluded if they are not live guidance.

```bash
rg -n "BUDDYSWITCH_BUDDYBOX_DIR|\\bbuddybox\\b|\\bBuddybox\\b" \
  scripts tools buddyswitch tests framework

rg -n "same role cannot|same-role.*cannot|not the active role|direct_role_channel|Role Messages" \
  scripts tools buddyswitch tests framework

rg -n "active-role private|active role's taskbox|private_to_role|\\bcreated_by\\b" \
  scripts/env/tools scripts/env/domain scripts/env/repos buddyswitch/skills tools/launcher/assets/roles tests
```

Expected final scan result:

- no live `BUDDYSWITCH_BUDDYBOX_DIR`;
- no live formal `buddybox` concept;
- no same-role message block wording;
- no `private_to_role`;
- no artifact/context ownership checks using retired `created_by`.

## 10. Explicit Non-Goals

Do not:

- modify already-started instance copies under `/Users/chen/.codex-buddyswitch/instances/*/workspace`;
- keep `$BUDDYSWITCH_BUDDYBOX_DIR` as an alias;
- keep old private roots as fallbacks;
- add adapter layers for old buddy fields;
- normalize old buddy fields in live object repos;
- make `instance` an identity concept;
- change request from `to_role` to `to_actor` without a separate product decision;
- change track ownership from role to actor without a separate product decision;
- rewrite role-action auth into actor-specific permissions;
- build a generic identity provider, group system, workflow engine, or permission framework;
- rewrite historical memos/specs only because they mention retired terms as historical context.

## 11. Done Criteria

This task is done only when:

1. live identity language is `Actor Identity -> Role / Actor`;
2. direct message behavior is actor-to-actor, with same-role different-actor allowed;
3. private draft artifact visibility is actor-isolated across every tool path;
4. `context` does not leak same-role other-actor drafts;
5. every tool response carries full `active_actor`;
6. evidence tokens record `issued_by_actor`;
7. actor private workspace is the only live private file concept;
8. `buddybox` and `$BUDDYSWITCH_BUDDYBOX_DIR` are gone from live guidance and contracts;
9. `private_to_role` and retired artifact `created_by` ownership checks are gone;
10. role-action auth remains simple and explicit: Role authorizes, Actor executes;
11. focused behavior tests and live-surface scans pass.


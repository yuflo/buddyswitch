# Actor Identity Role / Actor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild BuddySwitch identity around `Actor Identity -> Role / Actor`, removing legacy buddy identity from live runtime, launcher, tool, object, schema, skill, and test surfaces.

**Architecture:** Use one concrete identity module. `Role` owns capability classification and auth input. `Actor` owns routeable participant identity and object authorship/ownership where a person-like runtime participant is required. No compatibility alias or dual path is retained.

**Tech Stack:** Python runtime tools and repos, Bash launcher scripts, JSON/TOML contracts, Node web UI tests, pytest/unittest.

---

## Current Bottleneck

The current system can discover multiple online PM runtime participants but blocks PM-to-PM messages because message logic rejects targets with the same `buddy_id`. The root problem is not a message-only bug: live code uses legacy buddy naming for role, actor, launcher, auth, object authorship, and private workspace semantics.

## File Responsibility Map

- `scripts/env/tool_runtime/actor_profile.py`: canonical Actor Identity dataclasses and normalization.
- `scripts/env/tool_runtime/role_auth.py`: role-action authorization using role ids.
- `scripts/env/tool_runtime/context.py`: ToolContext, daemon access, private workspace access, context mapping.
- `scripts/env/tool_runtime/results.py`: canonical tool response shape.
- `scripts/env/tool_runtime/registry.py`: dispatch, auth gate, ToolContext construction.
- `scripts/runtime_kernel/dispatcher.py`: broker runtime identity validation and environment binding.
- `scripts/env_manifest.py`: manifest loading and role helper CLI.
- `scripts/env_profiles.py`: role profile loading and validation.
- `scripts/env/domain/messages.py`: message payload and scope rules.
- `scripts/env/repos/messages.py`: message storage contract.
- `tools/launcher/central_daemon_core.py`: online actor registry and reachability.
- `scripts/env/tool_runtime/daemon_client.py`: central daemon client payload contract.
- `tools/launcher/daemon_core.py`, `tools/launcher/daemon_mailbox.py`, `tools/launcher/message_available_handler.py`: actor signals and daemon context.
- `scripts/env/repos/{artifacts,tracks,comments,requests,tasks}.py`: runtime object field contracts.
- `scripts/env/tools/*/{tool.py,_impl.py}`: public env tool schemas, payload validation, response fields.
- `tools/launcher/{env.sh,instance.sh,codex_config.py,web_management.py}`: CLI, env vars, MCP server registration, web API.
- `buddyswitch/manifest.toml`, `buddyswitch/env-profiles/*.json`, `framework/contracts/*.md`, `buddyswitch/skills/**/SKILL.md`, `tools/launcher/assets/roles/*/AGENTS.md`: role-facing configuration and agent guidance.
- `tests/**`: behavior gates.

## Execution Rules

- Work only in `fea-daemon`.
- Start each behavior change with a failing focused test.
- Do not keep `buddy_id`, `active_buddy`, `--buddy`, or old buddy object fields as aliases.
- Follow `docs/memo/2026-06-01-actor-identity-final-rebuild-task.md` as the authoritative scope.
- Do not make a compatibility adapter.
- Do not edit runtime state under `buddyswitch/objects/**` directly.
- Avoid broad launcher/service tests until focused cleanup tests pass.

## Task 1: Establish Actor Identity Core

**Files:**

- Modify: `scripts/env/tool_runtime/actor_profile.py`
- Modify: `tests/test_runtime_actor_profile.py`

- [ ] Step 1: Replace the first actor-address tests with target Actor/Role behavior.

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py::RuntimeActorProfileTests::test_runtime_actor_address_serializes_stable_payload -q
```

Expected before implementation: fail because only `RuntimeActorAddress(buddy_id, instance_id)` exists.

- [ ] Step 2: Implement concrete dataclasses in `actor_profile.py`.

Required classes and functions:

```python
ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ACTOR_ID_PATTERN = re.compile(r"^act-[A-Za-z0-9._-]+$")

@dataclass(frozen=True)
class Role:
    role_id: str

@dataclass(frozen=True)
class Actor:
    actor_id: str
    role_id: str

@dataclass(frozen=True)
class AuthSubject:
    role_id: str

@dataclass(frozen=True)
class ActorAddress:
    actor_id: str
    role_id: str

@dataclass(frozen=True)
class RuntimeActorRecord:
    actor_id: str
    role_id: str
    instance_json: Path
    payload: dict[str, Any]

@dataclass(frozen=True)
class ActorProfile:
    actor_id: str
    role_id: str
    active_actor: Actor
    active_role: Role
    actor_address: ActorAddress
    auth_subject: AuthSubject
    actor_record: RuntimeActorRecord
```

`ActorAddress.to_payload()` must return `{"actor_id": actor_id, "role_id": role_id}`.

- [ ] Step 3: Delete `RuntimeActorAddress`, `RuntimeInstanceRecord`, and `RuntimeActorProfile` imports and usages from the focused test.

- [ ] Step 4: Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

Expected after implementation: actor identity focused tests pass.

## Task 2: Move Manifest From Buddies to Roles

**Files:**

- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env_manifest.py`
- Modify: `tests/test_env_manifest_v2.py`
- Modify: `tests/test_role_action_auth.py`

- [ ] Step 1: Update tests to require `manifest.roles`, `list-roles`, and `show-role`.

Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py tests/test_role_action_auth.py -q
```

Expected before implementation: fail on missing roles helpers and manifest shape.

- [ ] Step 2: Rename manifest tables from `[[buddies]]` to `[[roles]]`.

- [ ] Step 3: Replace manifest helper functions:

```text
buddies_by_id -> roles_by_id
get_buddy -> get_role
require_buddy -> require_role
buddy_authority_profile -> role_authority_profile
buddy_skill_docs -> role_skill_docs
list-buddies -> list-roles
show-buddy -> show-role
```

- [ ] Step 4: Update `role_auth.manifest_role_ids()` to read `manifest["roles"]`.

- [ ] Step 5: Run:

```bash
python3 -m pytest tests/test_env_manifest_v2.py tests/test_role_action_auth.py -q
```

Expected after implementation: manifest/auth tests pass.

## Task 3: Rebind Runtime Dispatch and Tool Context

**Files:**

- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tool_runtime/results.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `tools/launcher/env_tool_mcp_server.py`
- Modify: `tests/test_env_tool_identity.py`
- Modify: `tests/test_env_tool_response_contract.py`
- Modify: `tests/test_env_tool_payload_contract.py`

- [ ] Step 1: Update tests to use `actor_id`, `role`, `active_actor`, and `active_role`.

Run:

```bash
python3 -m pytest tests/test_env_tool_identity.py tests/test_env_tool_response_contract.py tests/test_env_tool_payload_contract.py -q
```

Expected before implementation: fail on old dispatch payload and response keys.

- [ ] Step 2: Change dispatch parameters from `active_buddy` and `instance_id` to trusted `actor_id` and `role_id`.

- [ ] Step 3: Change `ToolContext` fields to:

```python
active_actor: Actor
active_role: Role
actor_id: str
role_id: str
actor_address: ActorAddress
auth_subject: AuthSubject
```

- [ ] Step 4: Change result helpers to require and emit `active_actor` and `active_role`.

- [ ] Step 5: Change broker env binding:

```text
BUDDYSWITCH_ACTOR_ID
BUDDYSWITCH_ROLE_ID
BUDDYSWITCH_ACTOR_PRIVATE_DIR
```

Do not emit `BUDDYSWITCH_ACTIVE_BUDDY`.

- [ ] Step 6: Run focused tests until green.

## Task 4: Rebuild Central Daemon Actor Registry

**Files:**

- Modify: `tools/launcher/central_daemon_core.py`
- Modify: `scripts/env/tool_runtime/daemon_client.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tools/launcher/daemon_mailbox.py`
- Modify: `tools/launcher/message_available_handler.py`
- Modify: `tests/test_central_daemon_service.py`
- Modify: `tests/test_daemon_mailbox.py`
- Modify: `tests/test_message_available_handler.py`

- [ ] Step 1: Update tests to register `{"actor_id": "...", "role_id": "..."}`.

Run:

```bash
python3 -m pytest tests/test_central_daemon_service.py tests/test_daemon_mailbox.py tests/test_message_available_handler.py -q
```

Expected before implementation: fail on invalid actor address shape.

- [ ] Step 2: Key registry upsert and lookup by `actor_id`.

- [ ] Step 3: Change contact filter from `buddy_id` to `role_id`.

- [ ] Step 4: Ensure signals use `source_actor_address` and `target_actor_address` with ActorAddress payload.

- [ ] Step 5: Run focused daemon tests until green.

## Task 5: Rebuild Message Tool

**Files:**

- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/repos/messages.py`
- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tools/message/_impl.py`
- Modify: `tests/test_message_env_tool.py`
- Modify: `tests/test_env_tool_schema_contract.py`

- [ ] Step 1: Add red tests for same-role different-actor message send.

Required test assertion:

```python
self.assertIs(row["sendable"], True)
self.assertEqual(row["actor_address"]["role_id"], "pm")
self.assertNotEqual(row["actor_address"]["actor_id"], active["actor_id"])
```

Run:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_contacts_marks_only_same_actor_not_sendable -q
```

Expected before implementation: fail because same role is marked not sendable.

- [ ] Step 2: Replace all message schemas with `{actor_id, role_id}`.

- [ ] Step 3: Rename filter field `buddy` to `role`.

- [ ] Step 4: Change self-send/self-conversation checks to compare `actor_id`.

- [ ] Step 5: Change conversation role selector to compare `other_actor.role_id`.

- [ ] Step 6: Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_env_tool_schema_contract.py -q
```

Expected after implementation: message behavior and schema tests pass.

## Task 6: Rebuild Runtime Objects

**Files:**

- Modify: `scripts/env/repos/artifacts.py`
- Modify: `scripts/env/repos/tracks.py`
- Modify: `scripts/env/repos/comments.py`
- Modify: `scripts/env/repos/requests.py`
- Modify: `scripts/env/repos/tasks.py`
- Modify: `scripts/env/domain/*.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `scripts/env/tools/comment/_impl.py`
- Modify: `scripts/env/tools/request/_impl.py`
- Modify: `scripts/env/tools/task/_impl.py`
- Modify: related `tool.py` schema files
- Modify: object tool tests listed in the test plan

- [ ] Step 1: Update object tests to reject old buddy fields and require Actor/Role fields.

Run:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_task_env_tool.py \
  -q
```

Expected before implementation: fail on old field names.

- [ ] Step 2: Replace field contracts:

```text
artifact.created_by -> artifact.created_by_actor
artifact.authors -> artifact.author_actors
track.owner_buddy -> track.owner_role
track.shared_materials[].from_buddy -> track.shared_materials[].from_actor
track.updates[].by_buddy -> track.updates[].by_actor
request.from_buddy -> request.from_actor
request.to_buddy -> request.to_role
comment.by_buddy -> comment.by_actor
comment.mentions -> comment.mentioned_actors
comment.resolved_by -> comment.resolved_by_actor
task.owner_buddy -> task.owner_actor
```

- [ ] Step 3: Make request lifecycle actor fields explicit:

```text
accepted_by_actor
blocked_by_actor
completed_by_actor
canceled_by_actor
```

- [ ] Step 4: Scope taskbox by actor id, not role.

- [ ] Step 5: Run object tool tests until green.

## Task 7: Rebuild Private Workspace, Evidence, Search

**Files:**

- Modify: `scripts/env/domain/buddybox_workspace.py`
- Modify: `scripts/env/repos/buddybox_files.py`
- Modify: `scripts/env/tools/evidence/_impl.py`
- Modify: `scripts/env/tools/search/_impl.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: related tests

- [ ] Step 1: Update tests to use active Actor private workspace.

- [ ] Step 2: Rename live `buddybox` concepts to `private_workspace`.

- [ ] Step 3: Keep filesystem directory name simple and actor-scoped. Use `workspace/private` for launcher workspaces.

- [ ] Step 4: Run:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_env_layer_boundaries.py \
  tests/test_search_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_market_browser_evidence.py \
  tests/test_artifact_env_tool.py \
  -q
```

## Task 7A: Final Rebuild Behavior Hardening

**Files:**

- Modify: `scripts/env/domain/artifact_visibility.py`
- Modify: `scripts/env/domain/source_refs.py`
- Modify: `scripts/env/domain/comment_targets.py`
- Modify: `scripts/env/domain/artifact_relations.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `scripts/env/tools/comment/_impl.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `scripts/env/tool_runtime/results.py`
- Modify: `scripts/env/tools/evidence/_impl.py`
- Modify: `scripts/env/repos/actor_private_files.py`
- Modify: `scripts/env/domain/actor_private_workspace.py`
- Modify: focused tests listed below

- [ ] Step 1: Add draft isolation red tests.

Required test behaviors:

```text
Same-role different Actor cannot artifact.get/list another Actor draft.
Same-role different Actor cannot list/get another Actor draft attachments.
Same-role different Actor cannot comment on another Actor draft.
Same-role different Actor cannot use another Actor draft in summarized-full-content source_refs.
Same-role different Actor cannot supersede another Actor draft.
Creating Actor can still read/list/update/attach/list attachments/get attachment/supersede own draft.
```

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_comment_env_tool.py -q
```

Expected before implementation: fail because artifact visibility uses `created_by_actor.role_id == active_role`.

- [ ] Step 2: Replace draft readability with exact Actor ownership.

Implementation requirements:

```text
artifact_read_decision(artifact, active_actor)
draft allowed only when artifact.created_by_actor.actor_id == active_actor.actor_id
published artifact readability remains tied to readable track publication
template permission remains role-based
draft edit/delete remains actor-owned
```

Update every caller that currently passes `active_role` only:

```text
source_refs.normalize_source_refs
comment_targets.assert_target_readable
artifact_relations relation/backlink helpers
artifact tool list/get/list_attachments/get_attachment/create_revision/update_metadata/attach_file
track artifact ref checks
context candidate artifact rows
```

- [ ] Step 3: Add context candidate red tests.

Required test behaviors:

```text
context.summarize shows the active Actor's own private draft as a candidate when no track filter is used.
context.summarize does not show a same-role different Actor draft.
context.get has the same candidate boundary.
```

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py -q
```

Expected before implementation: fail because own drafts without retired `created_by` are not candidate rows.

- [ ] Step 4: Delete retired context candidate logic.

Replace:

```text
artifact.get("created_by") == active_role
```

With:

```text
decision.relation == "owner" for active Actor draft candidates
```

- [ ] Step 5: Add ToolResult active actor red tests.

Required test behaviors:

```text
tool_results.success(...) raises ValueError when active_actor is missing.
tool_results.rejection(...) raises ValueError when active_actor is missing.
Both helpers raise when active_actor lacks actor_id or role_id.
Both helpers return full active_actor and active_role when supplied.
No helper returns {"role_id": "..."} as a complete active_actor.
```

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py -q
```

Expected before implementation: fail because helpers synthesize a role-only active actor.

- [ ] Step 6: Require full active Actor in result helpers and update callers.

Implementation requirements:

```text
Remove _active_actor_payload fallback.
Make active_actor required in success and rejection signatures.
Pass context["active_actor"] through context, evidence, request, search, task, and local rejection helpers.
Keep broker normalization only as a guard, not as the source of correctness.
```

- [ ] Step 7: Add evidence issuer red tests.

Required test behaviors:

```text
evidence.issue_browser token has issued_by_actor equal to active_actor.
evidence.approve_downgrade token has issued_by_actor equal to active_actor.
tool_evidence does not contain active_role as issuer metadata.
target authorization still requires active Actor authorship.
```

Run:

```bash
python3 -m pytest tests/test_evidence_env_tool.py -q
```

Expected before implementation: fail because tokens contain `active_role` and omit `issued_by_actor`.

- [ ] Step 8: Add actor private summary red tests.

Required test behaviors:

```text
Actor private file summary rows contain owner_actor={actor_id, role_id}.
Actor private file summary rows do not contain private_to_role.
Actor private workspace descriptors use active Actor ownership wording.
```

Run:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py tests/test_context_binding_env_tool.py -q
```

Expected before implementation: fail because summaries contain `private_to_role`.

- [ ] Step 9: Run final hardening focused group.

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py \
  tests/test_evidence_env_tool.py \
  tests/test_runtime_actor_profile.py \
  -q
```

## Task 8: Rebuild Launcher, MCP, and Web Management

**Files:**

- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/codex_config.py`
- Modify: `tools/launcher/web_management.py`
- Modify: `tools/launcher/assets/web-management/app.js`
- Modify: `tools/launcher/assets/web-management/index.html`
- Modify: `tools/launcher/assets/web-management/styles.css`
- Modify: `buddyswitch-codex`
- Modify: launcher and web tests

- [ ] Step 1: Update tests for:

```text
instance roles
instance start --role <role>
instance list --role <role>
MCP args --actor-id and --role
/api/roles
create instance body {"role": "..."}
```

- [ ] Step 2: Change generated runtime records to:

```json
{
  "actor_id": "act-pm-...",
  "role": "pm",
  "status": "active"
}
```

- [ ] Step 3: Change launcher environment variables to Actor/Role naming.

- [ ] Step 4: Run resource-safe launcher tests:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "process_registry or cleanup or mcp or config or list or start" -q
python3 -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

- [ ] Step 5: Run residual process inspection.

## Task 9: Rename Role Profiles, Skills, Contracts, and Live Docs

**Files:**

- Modify: `buddyswitch/env-profiles/*.json`
- Modify: `framework/contracts/*.md`
- Modify: `framework/contracts/buddy-env-profile.json`
- Modify: `tools/launcher/assets/roles/*/AGENTS.md`
- Modify: `buddyswitch/skills/**/SKILL.md`
- Modify: `README.md`
- Modify: repo consistency tests

- [ ] Step 1: Rename live guidance terms from buddy identity to role/actor identity.

- [ ] Step 2: Keep `BuddySwitch` as the product name.

- [ ] Step 3: Exclude historical docs from residual checks.

- [ ] Step 4: Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_buddy_env_profiles.py -q
```

## Task 10: Residual Scan and Final Review

**Files:**

- Modify any live file found by the residual scan.

- [ ] Step 1: Run live residual scan:

```bash
rg -n 'buddy_id|active_buddy|--buddy|\\bbuddy\\b|instance_id|BUDDYSWITCH_BUDDYBOX_DIR|\\bbuddybox\\b|\\bBuddybox\\b|private_to_role' \
  scripts tools framework buddyswitch tests README.md AGENTS.md \
  -g '!docs/**' \
  -g '!**/__pycache__/**'
```

- [ ] Step 2: Classify every hit.

Allowed:

- `BuddySwitch` product name.
- `runtime_instance_id` only when internal process bookkeeping and not part of public identity.
- Historical docs outside live runtime checks.

Not allowed:

- `buddy_id`
- `active_buddy`
- `--buddy`
- public `instance_id` identity payloads
- object fields using buddy as owner/author/recipient
- `private_to_role` in actor private file summaries
- `buddybox` or `$BUDDYSWITCH_BUDDYBOX_DIR` in live code, tests, role templates, or skills

- [ ] Step 3: Run final focused verification from the test plan.

- [ ] Step 4: Run service-sensitive checks and residual process inspection.

- [ ] Step 5: Review diff for accidental compatibility adapters, old aliases, and broad unrelated refactors.

## Definition of Done

The task is done only when:

1. The original PM-to-PM same-role message path is allowed for different Actors.
2. Same-Actor self-send remains rejected.
3. Actor Identity core is the only live runtime identity model.
4. Auth consumes Role only.
5. Manifest, launcher, MCP, web UI, tool schemas, object repos, skills, and tests use Role/Actor naming.
6. Focused tests pass.
7. Resource-sensitive tests pass without residual process leaks.
8. Residual scan has no disallowed live hits.
9. Review finds no compatibility alias or transition layer.

## Self Review

Spec coverage:

- The plan maps every source memo module group to concrete files and verification.
- The original blocker has a dedicated message red test.
- Test resource lifecycle is built into launcher verification.
- No compatibility phase is specified.

Placeholder scan:

- Placeholder scan passes for banned marker words and deferred-work phrases.
- Each task has exact files, commands, and expected outcomes.

Type consistency:

- Public identity is `actor_id` plus `role_id`.
- Runtime role field in launcher records is `role`.
- Auth subject remains `AuthSubject(role_id)`.

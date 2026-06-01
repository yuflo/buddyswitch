# Actor Identity Role / Actor Test Plan

Date: 2026-06-01
Worktree: `fea-daemon`
Source memo: `docs/memo/2026-06-01-actor-identity-role-actor-upgrade-task.md`

## Goal

Prove the rebuild from legacy buddy identity to:

```text
Actor Identity
├── Role
└── Actor
```

The tests must prove behavior from product requirements, not mirror the current implementation.

## Hard Requirements

1. `Role` is the capability and responsibility class: `pm`, `market`, `design`, `dev`, `test`.
2. `Actor` is the concrete participant and routeable identity.
3. Direct messaging is Actor-to-Actor.
4. Same-role, different-Actor messaging is allowed.
5. Same-Actor messaging is rejected.
6. Auth consumes `actor.role_id` and answers only role-action permission.
7. Public/runtime payloads do not expose `buddy_id`, `active_buddy`, or `instance_id` as identity.
8. Manifest role definitions are `[[roles]]`, not `[[buddies]]`.
9. Launcher starts with `--role`, not `--buddy`.
10. Object authors, owners, mentions, request lifecycle actors, messages, taskboxes, and private workspace ownership use Actor/Role fields according to their semantics.
11. No compatibility alias, adapter, or dual path remains in live runtime code.

## Resource-Safe Test Rule

Follow `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

Before broad verification:

1. Prefer pure unit tests and `RuntimeWorkspaceTestMixin` tests.
2. Do not run broad launcher tests until process registry cleanup coverage is confirmed.
3. For any test that can start daemon/app-server/browser/broker processes, run one focused test first.
4. After service-starting tests, inspect residual processes before claiming completion.

## Test Groups

### 1. Actor Identity Core

Files:

- `tests/test_runtime_actor_profile.py`
- new or renamed tests may use `tests/test_actor_identity.py`

Required behaviors:

- `ActorAddress(actor_id="act-pm-aaa", role_id="pm")` serializes to `{"actor_id": "...", "role_id": "pm"}`.
- `ActorAddress.from_payload` rejects `buddy_id`, `instance_id`, endpoint, status, heartbeat, and other non-identity fields.
- `actor_id` accepts current launcher-safe ids such as `act-pm-1de000000002`.
- `role_id` validates against the role id pattern.
- Actor id does not need to start with the role prefix for correctness unless the launcher generator chooses that shape.
- `ActorProfile` exposes `actor_id`, `role_id`, `active_actor`, `active_role`, `actor_address`, and `auth_subject`.
- `ActorProfile` does not expose presence, endpoint, heartbeat, mailbox, or status.
- Tool context mapping exposes `active_actor`, `active_role`, `actor_id`, and `role_id`; it does not expose `active_buddy` or `instance_id`.

Focused command:

```bash
python3 -m pytest tests/test_runtime_actor_profile.py -q
```

### 2. Role Auth

Files:

- `tests/test_role_action_auth.py`

Required behaviors:

- Role ids come from `manifest.roles`.
- Unknown roles are denied.
- Unknown permissions are denied.
- PM-only permissions are still PM-only.
- Common permissions still allow every declared role.
- Auth rejection payload reports `active_role`, `allowed_roles`, `required_permission`, and `permission_boundary="tool.role_authority"`.
- Auth rejection payload does not report `active_buddy`.

Focused command:

```bash
python3 -m pytest tests/test_role_action_auth.py -q
```

### 3. Message Actor-to-Actor

Files:

- `tests/test_message_env_tool.py`
- `tests/test_central_daemon_service.py`
- `tests/test_env_tool_schema_contract.py`

Required behaviors:

- `message.contacts` returns contact rows with `role_id`, `actor_address`, `contact_status`, `sendable`, and `last_seen_at`.
- Same `actor_id` contact is not sendable.
- Same `role_id` with different `actor_id` is sendable.
- `message.send` accepts `target_actor_address={actor_id, role_id}`.
- `message.send` rejects self-send by same `actor_id`.
- `message.send` allows same-role different-actor messages and writes a durable message row.
- Message rows contain `from_actor_address` and `to_actor_address` with `{actor_id, role_id}`.
- Message rows do not contain `from_buddy`, `to_buddy`, `buddy_id`, or `instance_id`.
- `message.list` filters inbox by exact `to_actor_address`.
- Sender filter is named `role`, not `buddy`.
- `message.conversation` can select by exact `target_actor_address` or by `role`.
- Reply scope is checked by exact Actor pair, not role pair.
- Central daemon contacts filter is `role_id`.
- Central daemon registry upsert key is `actor_id`.

Focused command:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_central_daemon_service.py -q
```

### 4. Runtime Broker and Tool Result Shape

Files:

- `tests/test_env_tool_identity.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_env_tool_payload_contract.py`
- `tests/test_env_native_mcp_projection.py`
- `tests/test_env_native_mcp_server.py`
- `tests/test_runless_runtime_contract.py`

Required behaviors:

- Broker validates active `actor_id` and `role_id`.
- Env tool dispatch constructs Actor Identity from trusted runtime record.
- Payload identity spoofing with `actor`, `role`, `active_actor`, or `active_role` cannot override trusted runtime identity.
- Success and rejection helpers emit `active_actor` and `active_role`.
- Success and rejection helpers do not emit `active_buddy`.
- Native MCP schemas use Actor/Role fields.
- `env_tool_mcp_server.py` uses `--actor-id` and `--role`.

Focused command:

```bash
python3 -m pytest \
  tests/test_env_tool_identity.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_native_mcp_projection.py \
  tests/test_env_native_mcp_server.py \
  tests/test_runless_runtime_contract.py \
  -q
```

### 5. Manifest, Role Profiles, Skills, and Contracts

Files:

- `tests/test_env_manifest_v2.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`
- `buddyswitch/manifest.toml`
- `buddyswitch/env-profiles/*.json`
- `framework/contracts/*.md`
- `tools/launcher/assets/buddies/*/AGENTS.md`
- `buddyswitch/skills/**/SKILL.md`

Required behaviors:

- Manifest uses `[[roles]]`.
- Manifest helper commands are role commands: `list-roles`, `show-role`.
- Env profile JSON uses `role_id`, not `buddy_id`.
- Profile helper functions use role naming.
- Role contracts teach `Role` and `Actor`, not buddy-level identity.
- Live skills do not instruct users or agents to use `buddy_id`, `active_buddy`, or `--buddy`.
- Historical docs can contain old terms only if excluded from live-contract consistency checks.

Focused command:

```bash
python3 -m pytest tests/test_env_manifest_v2.py tests/test_buddy_env_profiles.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

### 6. Object Repositories and Tool Domains

Files:

- `tests/test_artifact_env_tool.py`
- `tests/test_track_env_tool.py`
- `tests/test_request_env_tool.py`
- `tests/test_comment_env_tool.py`
- `tests/test_task_env_tool.py`
- `tests/test_task_checkout_handler.py`
- `tests/test_task_input_context.py`

Required behaviors:

- Artifact fields are `created_by_actor` and `author_actors`.
- Artifact template authorization uses current role.
- Track field is `owner_role`; track material/proof fields use `from_actor`; updates use `by_actor`.
- Request role-queue fields are `from_actor`, `to_role`, `accepted_by_actor`, `blocked_by_actor`, `completed_by_actor`, and `canceled_by_actor`.
- Comment fields are `by_actor`, `mentioned_actors`, and `resolved_by_actor`.
- Task fields are `owner_actor`; taskbox path is actor-scoped.
- None of these objects accept old buddy owner/author fields.

Focused command:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_task_checkout_handler.py \
  tests/test_task_input_context.py \
  -q
```

### 7. Private Workspace and Evidence/Search

Files:

- `tests/test_clean_runtime_environment.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_search_env_tool.py`
- `tests/test_evidence_env_tool.py`
- `tests/test_market_browser_evidence.py`
- `tests/test_artifact_env_tool.py`

Required behaviors:

- Private workspace is actor-owned and surfaced as `private_workspace`.
- `buddybox` is not a live tool or public runtime concept.
- Attachments can only be adopted from the active Actor private workspace.
- Evidence and search responses use `active_actor` and `active_role`.

Focused command:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_env_layer_boundaries.py \
  tests/test_search_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_market_browser_evidence.py \
  -q
```

### 8. Launcher and Web Management

Files:

- `tests/test_buddyswitch_launcher.py`
- `tests/test_web_management.py`
- `tests/web_management_ui_contract.test.js`
- `tests/web_management_ui_state.test.js`

Required behaviors:

- Start command is `buddyswitch-codex instance start --role <role>`.
- Role listing command replaces buddy listing.
- Instance list filter is `--role`.
- Instance records store `actor_id` and `role`, not `instance_id` and `buddy`.
- MCP registration uses `--actor-id` and `--role`.
- Web management `/api/roles` replaces `/api/buddies`.
- Web management create payload uses `role`.

Resource-safe command sequence:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "manifest or mcp or config or list or start" -q
python3 -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Do not run broader launcher service tests until cleanup registration is confirmed in the focused output.

## Red-Green Requirements

Before production edits for each behavior group:

1. Add or update the focused test to encode the target behavior.
2. Run the focused test and confirm it fails for the expected legacy reason.
3. Implement the smallest direct replacement.
4. Run the focused test until green.
5. Only then move to the next group.

## Final Verification

Run focused groups first. Then run the broad pure suite:

```bash
python3 -m pytest \
  tests/test_runtime_actor_profile.py \
  tests/test_role_action_auth.py \
  tests/test_message_env_tool.py \
  tests/test_central_daemon_service.py \
  tests/test_env_tool_identity.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_native_mcp_projection.py \
  tests/test_env_native_mcp_server.py \
  tests/test_runless_runtime_contract.py \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_profiles.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_artifact_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_request_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_task_checkout_handler.py \
  tests/test_task_input_context.py \
  tests/test_clean_runtime_environment.py \
  tests/test_env_layer_boundaries.py \
  tests/test_search_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_market_browser_evidence.py \
  -q
```

Run service-sensitive checks separately:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "process_registry or cleanup or mcp or config or list or start" -q
python3 -m pytest tests/test_web_management.py -q
node --test tests/web_management_ui_contract.test.js tests/web_management_ui_state.test.js
```

Run residual resource inspection after any service-sensitive group:

```bash
ps -axo pid,ppid,command | rg 'buddyswitch|runtime_broker|app_server|central_daemon|chrome|fake_codex' || true
```

Run codebase residual scans for live paths:

```bash
rg -n 'buddy_id|active_buddy|--buddy|\\bbuddy\\b|instance_id' \
  scripts tools framework buddyswitch tests \
  -g '!docs/**' \
  -g '!**/__pycache__/**'
```

Expected residuals:

- `BuddySwitch` product name may remain.
- Historical docs under `docs/memo` and `docs/bitter` may retain old terms.
- `runtime_instance_id` may remain only if it is internal process bookkeeping and never appears in message/object/tool identity payloads.

## Self Review

Coverage check:

- Actor Identity core is covered.
- Auth is covered.
- Message PM-to-PM original blocker is covered.
- Daemon routing is covered.
- Manifest/profile/skills/contracts are covered.
- Object ownership and authorship are covered.
- Launcher/Web entrypoints are covered.
- Test resource lifecycle is explicitly guarded.

No placeholder terms are used as implementation instructions. Any discovered gap during execution should become a concrete failing test before production code changes.

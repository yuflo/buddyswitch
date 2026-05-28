# Runtime Actor Profile Phase 1 Task

Date: 2026-05-28

## Task In One Sentence

Split the current env.tool actor identity and role-auth path into small runtime-kernel modules so actor identity, auth decision, auth-denied feedback, and tool-facing context can evolve independently without forcing tool packages to depend on actor profile internals.

## Core Goal

Make the runtime auth path match the parallel change boundary principle:

- identity changes should stay in actor identity code;
- auth policy changes should stay in role auth code;
- auth-denied response changes should stay in feedback code;
- tool behavior changes should stay in the owning tool package.

This phase must not change product behavior.

## Target Runtime Flow

```text
Buddy runtime instance
  -> RuntimeInstanceRecord
  -> RuntimeActorProfile
  -> registry loads ActionDefinition.required_permission
  -> role_auth checks required_permission + AuthSubject
  -> denied: auth_feedback returns E_TOOL_ROLE_AUTH
  -> allowed: ToolContext calls tool service
  -> tool/domain handles business rules
```

## Module Boundary

### 1. `actor_profile`

Owns runtime actor identity resolution.

Expected responsibilities:

- define `RuntimeInstanceRecord`;
- define `RuntimeActorProfile`;
- define `AuthSubject`;
- resolve the trusted local instance record into the normalized actor profile.

This module answers:

```text
Who is acting in this local runtime instance?
```

It must not own tool behavior, message routing, track ownership, artifact visibility, request lifecycle, repos, or domain rules.

### 2. `role_auth`

Owns role-action authorization decisions.

Expected responsibilities:

- accept `required_permission` and `AuthSubject`;
- query the role-action policy table;
- return `AuthDecision`.

This module answers:

```text
Is this auth subject allowed to run an action requiring this permission?
```

It must not build tool responses, import tool implementations, or enforce business scope rules.

### 3. `auth_feedback`

Owns standard auth-denied runtime feedback.

Expected responsibilities:

- convert `AuthDecision` into the standard `E_TOOL_ROLE_AUTH` response;
- maintain auth-denied feedback fields such as `category`, `auth_source`, `auth_stage`, `executed`, `state_changed`, and `durability`.

This module answers:

```text
How does runtime report pre-dispatch auth denial?
```

It must not decide authorization and must not be duplicated inside tool packages.

### 4. `context`

Owns the tool-facing execution contract.

Expected responsibilities:

- build `ToolContext` from the runtime actor profile and runtime services;
- expose stable tool-facing identity facts, repos, domain rules, and runtime helpers.

This module answers:

```text
What stable execution view does a tool receive?
```

Tool packages should not depend on `RuntimeActorProfile` internals. They should consume `ToolContext`.

## Registry Role

`registry` remains the orchestrator, not the owner of these responsibilities.

Expected responsibilities:

- load the selected tool and action definition;
- read `ActionDefinition.required_permission`;
- call `role_auth`;
- route denied decisions through `auth_feedback`;
- create `ToolContext` on allowed calls;
- invoke the selected tool service.

## Tool Boundary

Tool packages remain product slices.

They own:

- action definitions;
- payload schemas;
- business behavior;
- domain-level rejections such as message self-send, reply scope, artifact visibility, and request lifecycle.

They do not own:

- runtime actor identity resolution;
- role auth decisions;
- standard role-auth denied feedback.

The only intentional auth boundary between tool and auth is:

```text
ActionDefinition.required_permission
```

Adding a new action with an existing permission should not require auth module changes.
Adding a new permission type is a shared contract change and should update `role_auth` and tests.

## What To Change

### 1. Add Actor Profile Core

Create the actor identity module under env tool runtime.

Expected owner file:

- `scripts/env/tool_runtime/actor_profile.py`

It should normalize the trusted local instance record into a runtime actor profile. The request payload must not be treated as the identity source.

### 2. Update Role Auth Input

Change role auth to consume `AuthSubject` instead of a raw active role string.

Expected owner file:

- `scripts/env/tool_runtime/role_auth.py`

Behavior remains the same: current auth subject is role-based, and current role ids are the manifest buddy ids.

### 3. Extract Auth Feedback

Move pre-dispatch role-auth rejection response construction out of registry into a dedicated feedback module.

Expected owner files:

- `scripts/env/tool_runtime/auth_feedback.py`
- `scripts/env/tool_runtime/registry.py`

`registry` should call the feedback helper, not build the full `E_TOOL_ROLE_AUTH` body inline.

### 4. Keep ToolContext As The Tool-Facing Contract

Update context construction only as needed so runtime identity comes from the actor profile while tool packages keep consuming the stable `ToolContext` contract.

Expected owner file:

- `scripts/env/tool_runtime/context.py`

Do not force all tool packages to import or inspect `RuntimeActorProfile`.

## Explicit Non-Goals

- Do not change message addressing from role inbox to instance inbox.
- Do not add per-instance auth.
- Do not merge env capability profiles into actor profile in this phase.
- Do not introduce delegation, elevation, permission DSL, workflow engine, or plugin system.
- Do not duplicate role auth inside tool packages.
- Do not move tool/domain business rules into runtime auth.
- Do not rewrite all tools to depend on `RuntimeActorProfile`.

## Why This Meets Parallel Change Boundary Principles

This phase turns a shared runtime hotspot into small owned contracts:

- `actor_profile` owns identity normalization;
- `role_auth` owns policy decisions;
- `auth_feedback` owns denial response shape;
- `context` owns the tool-facing execution contract;
- tool packages remain independently changeable product slices.

Future changes should land in the owning module:

- actor identity change -> `actor_profile`;
- permission policy change -> `role_auth`;
- auth-denied response change -> `auth_feedback`;
- tool behavior change -> the owning tool package;
- tool-facing projection change -> `context`.

The tool/auth intersection remains small and explicit:

```text
ActionDefinition.required_permission
```

## Definition Of Done

- Runtime actor identity is resolved through `actor_profile`.
- `role_auth` consumes `AuthSubject`, not a raw active role string.
- `E_TOOL_ROLE_AUTH` response construction is owned by `auth_feedback`, not duplicated in tools.
- `registry` is reduced to orchestration for identity, auth, context creation, and dispatch.
- Tool packages do not import or depend on `RuntimeActorProfile`.
- Product behavior is unchanged.
- Focused role auth, router, context, semantic contract, and message tests pass.
- Search confirms no old direct auth entrypoint remains outside the intended boundary.

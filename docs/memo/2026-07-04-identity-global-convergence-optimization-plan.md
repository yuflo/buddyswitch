# Identity Global Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `env.domain.identity` the only owner of actor/external static identity schema and remove every live second-owner surface.

**Architecture:** Identity becomes a product slice, not a helper: `IdentityRef`, `ActorIdentityProfile`, and `ExternalIdentityProfile` live in `scripts/env/domain/identity.py`, with JSON-backed profile persistence in an identity repo. Runtime, daemon, web, Track, Artifact, Comment, IM, and result helpers can store their own runtime or product facts, but they must reference identity and must not define actor/external static identity shapes.

**Tech Stack:** Python runtime code under `scripts/env/`, launcher code under `tools/launcher/`, JSON runtime state under `scripts/env/repos/runtime_files.py`, existing `unittest`/`pytest` suites, and scoped `rg` residue scans over live surfaces.

---

## 0. Task Target Restatement

Task A is the global identity convergence task.

It is not an IM task. It is not the actor-to-external messaging task. It is not a compatibility migration.

The target invariant is:

```text
actor/external static identity schema has exactly one owner:
  env.domain.identity

all other modules may only store:
  runtime facts about an identity
  product facts about an identity
  delivery facts about an identity
```

Task A completes when these are true:

1. `ActorIdentityProfile` owns actor static identity fields, including `identity`, `role_id`, and optional display fields.
2. `ExternalIdentityProfile` owns external static identity fields, including `identity` and optional display fields.
3. `scripts/env/tool_runtime/actor_profile.py` is deleted.
4. `ActorAddress`, `Actor`, `ActorProfile`, and `identity_from_im_participant` are deleted from live code.
5. Runtime/web/Track/Artifact/Comment/result-helper surfaces do not maintain actor static identity structures such as `active_actor = {"actor_id": ..., "role_id": ...}`.
6. Remaining runtime facts such as endpoint, heartbeat, thread id, workspace path, browser port, message state, and ownership relations reference identity.

## 1. `docs/bitter` Principles Applied

- Residue cleanup: Task A needs behavior tests for identity profile semantics and scoped no-hit scans for old static identity owners.
- Wrong-boundary narrowness: deleting `ActorAddress` without introducing an identity owner would only move the duplicate schema elsewhere.
- Built-in product interface: identity owns model, validation, persistence, and contract; runtime/web/tools are projections.
- Parallel boundary: this plan deliberately creates one small identity owner contract so downstream consumers do not keep editing shared runtime wrappers.
- Tool and prompt layering: fix runtime contracts and responses, not prompt text or role instructions.
- End-to-end contract slice: at least one tool-runtime dispatch path must prove identity profile is used across context, auth, and result output.
- Test resource lifecycle: Task A should use unit and file-backed tests only; no long-lived daemon/browser process tests are required.

## 2. Current Code Audit

Evidence from current live code:

- `scripts/env/domain/identity.py`
  - owns `IdentityRef`, `actor_identity()`, `external_identity()`.
  - still contains `identity_from_im_participant()`, which makes identity depend on IM legacy participant shape.
- `scripts/env/tool_runtime/actor_profile.py`
  - defines `Role`, `Actor`, `AuthSubject`, `ActorAddress`, `RuntimeActorRecord`, `ActorProfile`.
  - is a second owner for actor static identity.
- `scripts/env/tool_runtime/context.py`
  - stores `active_actor`, `active_role`, `actor_id`, `role_id`, and `actor_address`.
  - builds `DaemonAccess` by converting identity back to `ActorAddress`.
- `scripts/env/tool_runtime/registry.py`
  - constructs `runtime_actor = actor_profile.resolve_actor_profile(...)`.
  - passes `active_actor` payloads into tools and result helpers.
- `scripts/env/tool_runtime/results.py`
  - validates `active_actor.actor_id` and `active_actor.role_id`.
- `scripts/env/repos/tracks.py`, `scripts/env/repos/artifacts.py`, `scripts/env/repos/track_comments.py`
  - import `ActorAddress` for old actor payload normalization.
- `tools/launcher/web_management.py`
  - builds `active_actor = {"actor_id": actor_id, "role_id": role}` for product projections.

Conclusion:

```text
IdentityRef exists, but identity is not yet the static identity owner.
actor_profile.py and several product projections still teach the old actor static schema.
```

## 3. Target Architecture

### 3.1 Identity Domain Contract

`scripts/env/domain/identity.py` owns the stable schema:

```python
@dataclass(frozen=True)
class IdentityRef:
    id: str
    type: Literal["actor", "external"]

@dataclass(frozen=True)
class ActorIdentityProfile:
    identity: IdentityRef
    role_id: str
    label: str | None = None
    created_at: str | None = None

@dataclass(frozen=True)
class ExternalIdentityProfile:
    identity: IdentityRef
    display_name: str | None = None
    created_at: str | None = None
```

Rules:

- actor identity ids must start with `act-`.
- external identity ids must start with `ext-`.
- `ActorIdentityProfile.identity.type` must be `actor`.
- `ExternalIdentityProfile.identity.type` must be `external`.
- `role_id` is an actor static identity field but the role definition remains in `buddyswitch/manifest.toml`.
- identity domain must not import IM, daemon, runtime context, tools, web, or launcher modules.

### 3.2 Identity Repo Contract

Create `scripts/env/repos/identities.py`:

```text
state/identities/actors/<actor_identity_id>.json
state/identities/externals/<external_identity_id>.json
```

Responsibilities:

- persist normalized actor and external identity profiles;
- read actor/external profiles by identity id;
- list actor profiles for projections that need role/display information;
- reject legacy `actor_address`, `active_actor`, `participant`, `external_id` top-level identity shapes.

### 3.3 Runtime Context Contract

`ToolContext` should expose:

```python
current_identity: IdentityRef
current_actor_profile: ActorIdentityProfile
role_id: str
```

It should not expose:

```python
active_actor
actor_address
Actor
ActorAddress
ActorProfile
```

Dictionary projection compatibility is not preserved. Tool implementations and tests must be updated in the same task.

### 3.4 Product Surface Contract

Product surfaces may store identity references:

```python
owner_identity_id = "act-..."
author_identity_ids = ["act-..."]
mentioned_identity_ids = ["act-..."]
current_identity = {"id": "act-...", "type": "actor"}
```

Product surfaces must not store actor static identity payloads:

```python
active_actor = {"actor_id": "...", "role_id": "..."}
created_by_actor = {"actor_id": "...", "role_id": "..."}
by_actor = {"actor_id": "...", "role_id": "..."}
```

## 4. Non-Goals

Do not implement these in Task A:

- actor -> external active send.
- IM participant identity API cutover.
- daemon registry identity delivery cutover.
- iMessage outbound external routing.
- compatibility wrappers for `actor_profile.py`, `ActorAddress`, or `active_actor`.
- broad formatting or unrelated cleanup.

Those items either belong to Task B or a separate external delivery task.

## 5. Implementation Tasks

### Task A1: Add Red Tests For Identity Profile Ownership

**Files:**

- Create: `tests/test_identity_global_convergence.py`
- Modify: none
- Test: `tests/test_identity_global_convergence.py`

- [ ] **Step 1: Write identity profile schema tests**

Create `tests/test_identity_global_convergence.py` with:

```python
from __future__ import annotations

import unittest

from env.domain.identity import (
    ActorIdentityProfile,
    ExternalIdentityProfile,
    IdentityRef,
    actor_identity,
    external_identity,
)


class IdentityGlobalConvergenceTests(unittest.TestCase):
    def test_actor_identity_profile_is_the_actor_static_identity_owner(self) -> None:
        profile = ActorIdentityProfile.from_payload(
            {
                "identity": {"id": "act-pm-global", "type": "actor"},
                "role_id": "pm",
                "label": "PM",
                "created_at": "2026-07-04T00:00:00Z",
            }
        )

        self.assertEqual(profile.identity, IdentityRef(id="act-pm-global", type="actor"))
        self.assertEqual(profile.role_id, "pm")
        self.assertEqual(profile.to_payload()["identity"], {"id": "act-pm-global", "type": "actor"})
        self.assertNotIn("actor_id", profile.to_payload())
        self.assertNotIn("actor_address", profile.to_payload())

    def test_external_identity_profile_is_the_external_static_identity_owner(self) -> None:
        profile = ExternalIdentityProfile.from_payload(
            {
                "identity": {"id": "ext-web-global", "type": "external"},
                "display_name": "Web",
                "created_at": "2026-07-04T00:00:00Z",
            }
        )

        self.assertEqual(profile.identity, IdentityRef(id="ext-web-global", type="external"))
        self.assertEqual(profile.display_name, "Web")
        self.assertEqual(profile.to_payload()["identity"], {"id": "ext-web-global", "type": "external"})
        self.assertNotIn("external_id", profile.to_payload())

    def test_identity_helpers_reject_cross_type_ids(self) -> None:
        with self.assertRaises(ValueError):
            actor_identity("ext-not-actor")
        with self.assertRaises(ValueError):
            external_identity("act-not-external")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_identity_global_convergence.py -q
```

Expected result:

```text
FAILED tests/test_identity_global_convergence.py
AttributeError or ImportError for ActorIdentityProfile / ExternalIdentityProfile
```

### Task A2: Implement Identity Profiles In The Identity Domain

**Files:**

- Modify: `scripts/env/domain/identity.py`
- Test: `tests/test_identity_global_convergence.py`

- [ ] **Step 1: Replace the IM legacy adapter with profile schema**

In `scripts/env/domain/identity.py`, remove `identity_from_im_participant()` and add:

```python
ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ACTOR_ID_PATTERN = re.compile(r"^act-[A-Za-z0-9._-]+$")
EXTERNAL_ID_PATTERN = re.compile(r"^ext-[A-Za-z0-9._-]+$")
```

Update `actor_identity()` and `external_identity()` so they validate the correct prefix pattern.

- [ ] **Step 2: Add profile dataclasses**

Add `ActorIdentityProfile` and `ExternalIdentityProfile` with `from_payload()` and `to_payload()` methods matching the tests from Task A1.

- [ ] **Step 3: Run focused test**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_identity_global_convergence.py -q
```

Expected result:

```text
3 passed
```

### Task A3: Add Identity Profile Repository

**Files:**

- Create: `scripts/env/repos/identities.py`
- Modify: `tests/test_identity_global_convergence.py`
- Test: `tests/test_identity_global_convergence.py`

- [ ] **Step 1: Add repository tests**

Append to `IdentityGlobalConvergenceTests`:

```python
    def test_identity_repo_persists_actor_and_external_profiles(self) -> None:
        from env.repos import identities as identity_repo

        actor = identity_repo.save_actor_profile(
            {
                "identity": {"id": "act-dev-repo", "type": "actor"},
                "role_id": "dev",
                "label": "Dev",
            }
        )
        external = identity_repo.save_external_profile(
            {
                "identity": {"id": "ext-web-repo", "type": "external"},
                "display_name": "Web",
            }
        )

        self.assertEqual(actor["identity"], {"id": "act-dev-repo", "type": "actor"})
        self.assertEqual(identity_repo.get_actor_profile("act-dev-repo")["role_id"], "dev")
        self.assertEqual(external["identity"], {"id": "ext-web-repo", "type": "external"})
        self.assertEqual(identity_repo.get_external_profile("ext-web-repo")["display_name"], "Web")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_identity_global_convergence.py::IdentityGlobalConvergenceTests::test_identity_repo_persists_actor_and_external_profiles -q
```

Expected result:

```text
FAILED with ImportError for env.repos.identities
```

- [ ] **Step 3: Implement `scripts/env/repos/identities.py`**

Create functions:

```python
def identity_root() -> Path
def save_actor_profile(payload: dict[str, Any]) -> dict[str, Any]
def get_actor_profile(identity_id: str) -> dict[str, Any] | None
def list_actor_profiles() -> list[dict[str, Any]]
def save_external_profile(payload: dict[str, Any]) -> dict[str, Any]
def get_external_profile(identity_id: str) -> dict[str, Any] | None
```

Use `runtime_files.write_json_object()` and `runtime_files.require_id()`. Persist actors under `state/identities/actors/` and externals under `state/identities/externals/`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_identity_global_convergence.py -q
```

Expected result:

```text
4 passed
```

### Task A4: Replace Runtime Actor Profile With Identity Profile

**Files:**

- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: `scripts/env/tool_runtime/context.py`
- Modify: `scripts/env/tool_runtime/role_auth.py`
- Modify: `scripts/env/tool_runtime/results.py`
- Delete: `scripts/env/tool_runtime/actor_profile.py`
- Test: `tests/test_runtime_actor_profile.py`
- Test: `tests/test_role_action_auth.py`
- Test: `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Rewrite runtime tests to assert identity profile context**

Replace actor-profile-oriented tests in `tests/test_runtime_actor_profile.py` with identity-context tests:

```python
def test_tool_context_uses_identity_profile_without_actor_address(self) -> None:
    profile = ActorIdentityProfile.from_payload(
        {"identity": {"id": "act-dev-context", "type": "actor"}, "role_id": "dev"}
    )
    context = ToolContext.from_identity_profile(
        actor_profile=profile,
        instance_json=Path("/tmp/instance.json"),
        instance_payload={"identity_id": "act-dev-context"},
        manifest={"roles": [{"id": "dev"}]},
    )

    self.assertEqual(context.current_identity.to_payload(), {"id": "act-dev-context", "type": "actor"})
    self.assertEqual(context.role_id, "dev")
    self.assertEqual(context["current_identity"], {"id": "act-dev-context", "type": "actor"})
    with self.assertRaises(KeyError):
        _ = context["active_actor"]
    self.assertFalse(hasattr(context, "actor_address"))
```

- [ ] **Step 2: Run focused runtime tests to verify failure**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_runtime_actor_profile.py tests/test_role_action_auth.py -q
```

Expected result:

```text
FAILED because ToolContext.from_identity_profile does not exist and actor_profile imports still exist
```

- [ ] **Step 3: Update `role_auth.py` to use role_id strings**

Remove `AuthSubject` import. Change signatures:

```python
def authorize(required_permission: str, role_id: str, manifest: dict[str, Any]) -> AuthDecision
def role_action_summary(role_id: str, manifest: dict[str, Any], operation_semantics: dict[str, dict[str, Any]]) -> dict[str, Any]
```

- [ ] **Step 4: Update `context.py`**

Replace actor-profile fields with:

```python
current_identity: IdentityRef
current_actor_profile: ActorIdentityProfile
role_id: str
```

Add:

```python
@classmethod
def from_identity_profile(
    cls,
    *,
    actor_profile: ActorIdentityProfile,
    instance_json: Path,
    instance_payload: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path | None = None,
) -> "ToolContext":
    ...
```

Remove `actor_address`, `active_actor`, `active_role`, and `auth_subject` from the context surface.

- [ ] **Step 5: Update `registry.py` dispatch construction**

When dispatch receives `actor_id` and `active_role` from launcher, upsert/read the actor identity profile through `env.repos.identities`, then construct `ToolContext.from_identity_profile(...)`.

- [ ] **Step 6: Update `results.py`**

Replace `active_actor` fields with:

```python
"current_identity": {"id": "...", "type": "actor"},
"active_role": "pm"
```

Reject only when `current_identity.type != "actor"` or `active_role` is missing.

- [ ] **Step 7: Delete `scripts/env/tool_runtime/actor_profile.py`**

Delete the file after all imports are removed.

- [ ] **Step 8: Run focused runtime tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_runtime_actor_profile.py tests/test_role_action_auth.py tests/test_env_tool_response_contract.py -q
```

Expected result:

```text
PASS
```

### Task A5: Replace Product Static Actor Payloads With Identity References

**Files:**

- Modify: `scripts/env/repos/tracks.py`
- Modify: `scripts/env/repos/artifacts.py`
- Modify: `scripts/env/repos/track_comments.py`
- Modify: `scripts/env/domain/artifact_visibility.py`
- Modify: `scripts/env/domain/track_comments.py`
- Modify: `scripts/env/domain/track_read.py`
- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tools/launcher/web_management.py`
- Test: `tests/test_track_env_tool.py`
- Test: `tests/test_artifact_env_tool.py`
- Test: `tests/test_track_comment_env_tool.py`
- Test: `tests/test_context_binding_env_tool.py`
- Test: `tests/test_web_management.py`

- [ ] **Step 1: Write failing product surface tests**

Add assertions to existing tests so returned rows contain `current_identity`, `owner_identity_id`, `by_identity_id`, or `author_identity_ids`, and do not contain `active_actor`, `created_by_actor`, `by_actor`, or `actor_address`.

Example assertion:

```python
self.assertEqual(response["current_identity"], {"id": actor_id, "type": "actor"})
self.assertNotIn("active_actor", response)
self.assertNotIn("actor_address", json.dumps(response))
```

- [ ] **Step 2: Run focused product tests to verify failure**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comment_env_tool.py tests/test_context_binding_env_tool.py -q
```

Expected result:

```text
FAILED with old active_actor / actor_address expectations
```

- [ ] **Step 3: Replace repo/domain normalization**

Replace `ActorAddress.from_payload(...)` and `_actor_identity_id(...)` helpers with direct identity-id validation:

```python
def _identity_id(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return runtime_files.require_id(value.strip(), field)
    if isinstance(value, dict) and isinstance(value.get("identity"), dict):
        return IdentityRef.from_payload(value["identity"]).id
    raise ValueError(f"{field} must be an identity id or identity payload")
```

- [ ] **Step 4: Replace tool and web projections**

Use `context.current_identity.to_payload()` and `context.role_id` instead of `context["active_actor"]` or `context.actor_address`.

- [ ] **Step 5: Run focused product tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_track_env_tool.py tests/test_artifact_env_tool.py tests/test_track_comment_env_tool.py tests/test_context_binding_env_tool.py tests/test_web_management.py -q
```

Expected result:

```text
PASS
```

### Task A6: Add Scoped Residue Guard For Task A

**Files:**

- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add residue test**

Add a test that scans live Python and contract surfaces:

```python
def test_identity_global_convergence_has_no_second_actor_identity_owner(self) -> None:
    root = Path(__file__).resolve().parents[1]
    live_roots = [root / "scripts", root / "tools", root / "tests"]
    forbidden = (
        "env.tool_runtime.actor_profile",
        "class ActorAddress",
        "ActorProfile",
        "ActorAddress",
        "identity_from_im_participant",
        "participant.actor_address",
        "participant.external_id",
    )
    allowed_files = {Path("tests/test_repo_consistency.py")}
    hits: list[str] = []
    for live_root in live_roots:
        for path in live_root.rglob("*.py"):
            rel = path.relative_to(root)
            if rel in allowed_files:
                continue
            text = path.read_text(encoding="utf-8")
            for term in forbidden:
                if term in text:
                    hits.append(f"{rel}: {term}")
    self.assertEqual(hits, [])
```

- [ ] **Step 2: Run residue test**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_identity_global_convergence_has_no_second_actor_identity_owner -q
```

Expected result:

```text
PASS
```

### Task A7: Final Verification For Task A

**Files:**

- No new files.

- [ ] **Step 1: Run exact focused tests**

Run:

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/test_identity_global_convergence.py \
  tests/test_runtime_actor_profile.py \
  tests/test_role_action_auth.py \
  tests/test_env_tool_response_contract.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_track_comment_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_web_management.py \
  tests/test_repo_consistency.py -q
```

Expected result:

```text
PASS
```

- [ ] **Step 2: Run exact residue scans**

Run:

```bash
test ! -f scripts/env/tool_runtime/actor_profile.py
rg -n "env\\.tool_runtime\\.actor_profile|class ActorAddress|ActorProfile|ActorAddress|identity_from_im_participant|participant\\.actor_address|participant\\.external_id" scripts tools tests
```

Expected result:

```text
test command exits 0
rg exits 1 with no live hits except the residue test forbidden-term list
```

## 6. Completion Audit

Task A is complete only when:

- `env.domain.identity` owns actor/external static identity profiles.
- `scripts/env/tool_runtime/actor_profile.py` is gone.
- runtime context no longer exposes actor static identity as `active_actor` or `actor_address`.
- product surfaces use identity references instead of actor payloads.
- behavior tests and residue scans both pass.
- Task B can consume identity profiles without defining its own identity schema.

# Env Legacy Store Cleanup Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` when implementing runtime changes from this plan. Tests must express runtime behavior and architectural boundaries, not the current helper implementation.

**Goal:** Prove active runtime behavior no longer depends on `env_legacy_store` for source refs, artifact readability, context discovery, or evidence target scope, while preserving the accepted parallel modular architecture.

**Architecture:** Use focused broker-routed env.tool tests for behavior, persisted runtime-state assertions for mutation boundaries, and static import guards for active runtime coupling. Runtime tests may use `env_legacy_store` as fixture setup until fixture cleanup is planned separately; active runtime code may not import it.

**Tech Stack:** Python `unittest`/`pytest`, `RuntimeWorkspaceTestMixin`, broker-routed `runtime_broker.dispatch_runtime_request`, concrete runtime object repos under `scripts/env/repos/**`, domain readability logic under `scripts/env/domain/artifact_visibility.py`, AST static checks, and `rg` verification.

---

## Test Rules

- Do not use `docs/**` as a functional assertion target.
- Do not add or modify docs while executing runtime cleanup.
- Do not write tests that pass only by monkeypatching `env_legacy_store` to fail. Behavior tests should describe tool-visible requirements.
- Static import guards may assert active runtime import boundaries because that is an architectural requirement.
- Tests may continue using `env_legacy_store` to seed tracks, tasks, and artifacts in temporary runtime workspaces.
- Positive behavior tests must assert response shape and relevant persisted state.
- Negative behavior tests must assert rejection code, permission boundary, absence of created token/object data, and no unintended state mutation.
- Full-suite verification is required after focused tests pass.

## Requirements Model

R1. `source_refs` accepts structured provenance refs for `artifact`, `track`, `task`, `buddybox`, `external`, and `note`, validates ids with the same runtime id rules, and never treats provenance as a required read path.

R2. A full-content `read_claim` for an artifact source ref is accepted only when the active buddy can read the referenced artifact through runtime artifact visibility rules.

R3. Artifact readability preserves these rules:

- active buddy can read its own private draft;
- non-owner cannot read another buddy's private draft;
- published current track material is readable from a non-archived track;
- published close proof is readable from a non-archived track;
- historical published material/proof remains readable as history;
- archived tracks block track opening and published artifact reads.

R4. `context.get` and `context.summarize` discover active runtime state through the same product behavior as before: non-archived tracks, active-buddy tasks connected to visible tracks, current shared material summaries, compact tool affordances, and buddybox capability metadata.

R5. `context` does not expose archived tracks, tasks attached to archived tracks, superseded current-material entries, or retired buddy-routing fields.

R6. `evidence.issue_browser` and `evidence.approve_downgrade` issue transient token metadata only for `target_type="artifact"` and only when the active buddy is an author of the target artifact.

R7. Evidence rejects missing targets, unsupported target types, and readable-but-not-authored artifacts without issuing token metadata or mutating product state.

R8. Active runtime modules under `scripts/env/services`, `scripts/env/domain`, `scripts/env/repos`, and `scripts/env/tools` do not import `env_legacy_store`.

R9. Existing parallel architecture boundaries remain true: object repos do not import sibling repos, track/artifact publication goes through the publication domain, message/comment/buddybox focused tests stay independent, and runtime skill/contract discovery remains aligned.

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| SR1 | R1 | `tests/test_artifact_env_tool.py` | Invalid artifact source ref id | `E_SOURCE_REFS`, `source_refs.required_fields`, no artifact file |
| SR2 | R2/R3 | `tests/test_artifact_env_tool.py` | Full read claim against readable published artifact | success, source ref persisted, no legacy run lineage |
| SR3 | R2/R3 | `tests/test_artifact_env_tool.py` | Full read claim against another buddy's private draft | `E_SOURCE_REFS_READ_SCOPE`, `source_refs.read_scope`, no artifact file |
| AV1 | R3 | `tests/test_artifact_env_tool.py` | Draft owner and non-owner reads | owner success, non-owner `E_ARTIFACT_READ_SCOPE` |
| AV2 | R3/R9 | `tests/test_artifact_env_tool.py` | Publish and read current material from another buddy | `artifact.get` success, `currentness="current"` |
| AV3 | R3/R9 | `tests/test_artifact_env_tool.py` | Superseded published artifact remains readable as history | old body readable, `currentness="superseded"` |
| AV4 | R3/R9 | `tests/test_artifact_env_tool.py` | Archived track blocks published artifact reads | `track.lifecycle_status` and artifact read rejection |
| CT1 | R4/R5 | `tests/test_context_binding_env_tool.py` | Context summary exposes compact tool affordances | all expected tools, no handoff action |
| CT2 | R4/R5 | `tests/test_context_binding_env_tool.py` | Context get with active and archived tracks | active track present, archived track absent |
| CT3 | R4/R5 | `tests/test_context_binding_env_tool.py` | Context tasks use active buddy plus visible track scope | active visible task present, archived-track task absent |
| CT4 | R4/R5 | `tests/test_context_binding_env_tool.py` | Context artifact summaries are current only | current material present, superseded and archived absent |
| EV1 | R6/R7 | `tests/test_evidence_env_tool.py` | Issue token for active-buddy-authored artifact | success, transient token, no `run_id` |
| EV2 | R6/R7 | `tests/test_evidence_env_tool.py` | Missing artifact target | `E_EVIDENCE_PAYLOAD`, no `tool_evidence` |
| EV3 | R6/R7 | `tests/test_evidence_env_tool.py` | Unsupported target type | `E_EVIDENCE_TARGET_TYPE`, no `tool_evidence` |
| EV4 | R6/R7 | `tests/test_evidence_env_tool.py` | Readable published artifact not authored by active buddy | `E_EVIDENCE_TARGET_SCOPE`, `artifact.authors`, no `tool_evidence` |
| EV5 | R6/R7 | `tests/test_market_browser_evidence.py` | Market browser evidence and downgrade flows | artifact-only target, no run files, downgrade reason retained |
| BG1 | R8 | `tests/test_env_layer_boundaries.py` | Active runtime import guard | no AST import of `env_legacy_store` in services/domain/repos/tools |
| PA1 | R9 | `tests/test_env_layer_boundaries.py` | Repo/domain boundary checks | no sibling repo imports, publication writes allowlisted |
| PA2 | R9 | `tests/test_repo_consistency.py` | Runtime discovery and residue checks | active tool surface and guidance remain aligned |
| PA3 | R9 | `tests/test_parallel_contracts.py` | Parallel architecture contracts | projection and publication contracts still hold |
| PA4 | R9 | `tests/test_message_env_tool.py`, `tests/test_comment_env_tool.py`, `tests/test_buddybox_env_tool.py` | Independent object modules | focused suites pass without cross-object coupling regressions |

## Detailed Test Design

### SR1: Invalid Source Ref Id Rejects Before Artifact Creation

**File:** `tests/test_artifact_env_tool.py`

**Setup:** Create an active buddy instance for `pm`.

**Operation:** Dispatch `artifact.create_revision` with a valid artifact payload and `source_refs=[{"type": "artifact", "id": "Bad.ID"}]`.

**Assertions:**

- Response has `ok=false`.
- Error code is `E_SOURCE_REFS`.
- `permission_boundary` is `source_refs.required_fields`.
- Requested artifact id does not exist in `buddyswitch/objects/artifacts`.
- No track state is created or changed.

**Focused command:**

```bash
python3 -m pytest tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_source_ref_invalid_artifact_id_rejects_without_artifact -q
```

### SR2: Full Read Claim Allows Readable Published Artifact

**File:** `tests/test_artifact_env_tool.py`

**Setup:**

- Create a PM-owned active track.
- Create a PM artifact revision.
- Publish it through `track.add_material`.
- Create a `dev` instance.

**Operation:** Dispatch `artifact.create_revision` as `dev` with an artifact source ref to the published PM artifact and `read_claim="summarized-full-content"`.

**Assertions:**

- Response has `ok=true`.
- Created artifact has `status="draft"`.
- Created artifact `source_refs` contains `{"type": "artifact", "id": "<published-id>"}`.
- Created artifact does not contain legacy run lineage fields.
- The source artifact is readable through `artifact.get` as `dev`.

**Focused command:**

```bash
python3 -m pytest tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_source_ref_full_read_claim_accepts_readable_published_artifact -q
```

### SR3: Full Read Claim Rejects Unreadable Private Draft

**File:** `tests/test_artifact_env_tool.py`

**Setup:**

- Create a PM private draft artifact.
- Create a `dev` instance.

**Operation:** Dispatch `artifact.create_revision` as `dev` with a source ref to the PM private draft and `read_claim="summarized-full-content"`.

**Assertions:**

- Response has `ok=false`.
- Error code is `E_SOURCE_REFS_READ_SCOPE`.
- `permission_boundary` is `source_refs.read_scope`.
- Rejection mentions provenance-only source refs through `why_blocked`.
- Requested dev artifact id does not exist.
- PM draft remains unchanged.

**Focused command:**

```bash
python3 -m pytest tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_source_ref_full_read_claim_rejects_unreadable_private_draft -q
```

### AV1-AV4: Artifact Readability Regression Set

**File:** `tests/test_artifact_env_tool.py`

**Existing coverage to keep green:**

- Draft owner can read, non-owner cannot.
- Published current material is readable by other buddies.
- Superseded published revision remains readable as history.
- Archived track blocks `track.open` and published artifact reads.

**Assertions to preserve:**

- `artifact.get` for non-owner private draft returns `E_ARTIFACT_READ_SCOPE` with `permission_boundary="artifact.status"`.
- Published artifact response includes body and `currentness`.
- Superseded artifact response includes old body and `currentness="superseded"`.
- Archived read path returns `track.lifecycle_status`.

**Focused command:**

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

### CT1-CT4: Context Discovery Regression Set

**File:** `tests/test_context_binding_env_tool.py`

**Setup:** Use the existing seeded context state pattern with:

- one active track;
- one task for the active buddy on the active track;
- two artifact revisions where the second is current shared material;
- one archived track;
- one task attached to the archived track;
- one artifact published on the archived track.

**Operations:**

- Dispatch `context.summarize` with `{}`.
- Dispatch `context.get` with `{}`.
- Dispatch `context.get` with `{"track_id": "track-context-active", "task_id": "task-dev-context", "limit": 5}`.
- Dispatch `context.list_sources` with `{}`.

**Assertions:**

- `tool_affordances` contains the expected active tools and excludes `handoff`.
- `candidate_tracks` and `tracks` include `track-context-active`.
- `candidate_tracks` and `tracks` exclude `track-context-archived`.
- `tasks` include `task-dev-context`.
- `tasks` exclude `task-dev-archived`.
- `artifact_summaries` include only the current active-track material.
- `artifact_summaries` exclude superseded material and archived-track material.
- Rows do not expose retired fields such as `current_buddy`, `next_buddy`, or `readable_by_current_buddy`.
- `context.list_sources` includes runtime sources such as `tracks`, `artifacts`, and `buddybox`, and excludes retired handoff sources.

**Focused command:**

```bash
python3 -m pytest tests/test_context_binding_env_tool.py -q
```

### EV1-EV4: Evidence Target Scope Regression Set

**File:** `tests/test_evidence_env_tool.py`

**Setup:** Use runtime workspace fixtures to create market-authored artifacts. Publish one artifact when testing readable-but-not-authored scope.

**Operations:**

- Issue browser evidence for a market-authored artifact as `market`.
- Approve downgrade for a market-authored artifact as `market`.
- Issue browser evidence for a missing artifact id.
- Issue browser evidence for `target_type="memory"`.
- Issue browser evidence as `design` for a readable market-authored published artifact.

**Assertions:**

- Successful evidence response has `state_changed=true`, `durability="transient token"`, `mutates_product_state=False`, `target_type="artifact"`, `active_buddy`, and no `run_id`.
- Missing target returns `E_EVIDENCE_PAYLOAD` and no `tool_evidence`.
- Unsupported target type returns `E_EVIDENCE_TARGET_TYPE`, `permission_boundary="evidence.target_type"`, and no `tool_evidence`.
- Readable but not authored target returns `E_EVIDENCE_TARGET_SCOPE`, `permission_boundary="artifact.authors"`, and no `tool_evidence`.

**Focused command:**

```bash
python3 -m pytest tests/test_evidence_env_tool.py -q
```

### EV5: Browser Evidence Integration Regression

**File:** `tests/test_market_browser_evidence.py`

**Existing coverage to keep green:**

- Browser evidence CLI accepts artifact target type and rejects old target types.
- Market can issue artifact-scoped evidence.
- Market artifact write with evidence source refs remains runless.
- Downgrade approval records the reason in transient token metadata.

**Assertions to preserve:**

- No `buddyswitch/content/runs` or `runs/raw` paths are created by evidence flow.
- Evidence token metadata has no `run_id`.
- Artifact writes can persist evidence token references as source-ref metadata without requiring browser/run durable state.

**Focused command:**

```bash
python3 -m pytest tests/test_market_browser_evidence.py -q
```

### BG1: Active Runtime Import Guard

**File:** `tests/test_env_layer_boundaries.py`

**Scan roots:**

- `scripts/env/services`
- `scripts/env/domain`
- `scripts/env/repos`
- `scripts/env/tools`

**Operation:** Parse every `*.py` file under those roots with `ast.parse`, excluding `__init__.py` only if it contains no imports. Inspect `ast.Import` and `ast.ImportFrom`.

**Assertions:**

- No `ast.Import` alias has name `env_legacy_store`.
- No `ast.ImportFrom` has module `env_legacy_store`.
- Failure output lists `relative/path.py:line` for each violation.
- `tests/**` is not scanned by this guard.

**Focused command:**

```bash
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_active_runtime_modules_do_not_import_env_legacy_store -q
```

**Manual verification mirror:**

```bash
rg -n "import env_legacy_store|from env_legacy_store import" scripts/env/services scripts/env/domain scripts/env/repos scripts/env/tools
```

Expected result after cleanup: no matches.

### PA1-PA4: Parallel Architecture Regression Set

**Files:**

- `tests/test_runtime_skills.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_repo_consistency.py`
- `tests/test_parallel_contracts.py`
- `tests/test_message_env_tool.py`
- `tests/test_comment_env_tool.py`
- `tests/test_buddybox_env_tool.py`

**Assertions to preserve:**

- Shared skills and role contracts rely on runtime discovery instead of copied payload schemas.
- Object repos do not import sibling repos.
- Cross-object imports remain allowlisted only in domain modules.
- Track/artifact publication writes remain in the publication domain and concrete repos.
- Message tests pass without track/artifact/task setup.
- Comment tests mutate comment objects and do not mutate target objects.
- Buddybox tests keep private files under active-buddy local workspace and out of product objects.

**Focused command:**

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
```

## Verification Sequence

Run focused checks in this order while implementing:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_runtime_tool_feedback.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_track_env_tool.py tests/test_comment_env_tool.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py tests/test_turn_integration.py -q
python3 -m pytest tests/test_evidence_env_tool.py tests/test_market_browser_evidence.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_env_layer_boundaries.py tests/test_repo_consistency.py tests/test_parallel_contracts.py -q
python3 -m pytest tests/test_message_env_tool.py tests/test_comment_env_tool.py tests/test_buddybox_env_tool.py -q
```

Then run the import scan:

```bash
rg -n "import env_legacy_store|from env_legacy_store import" scripts/env/services scripts/env/domain scripts/env/repos scripts/env/tools
```

Expected result: no matches.

Then run the full suite:

```bash
python3 -m pytest -q
```

## Test Completion Criteria

Testing is complete when all of these are true:

- Source-ref tests cover id validation, readable full-content claims, and unreadable full-content claims.
- Artifact readability tests cover draft privacy, published readability, superseded history readability, and archived-track blocking.
- Context tests cover compact discovery, full discovery, filters, active-buddy task scope, archived-track exclusion, and current-only artifact summaries.
- Evidence tests cover authored target success, missing target rejection, unsupported target type rejection, readable-but-not-authored rejection, downgrade reason, transient token shape, and no run lineage.
- Active runtime import guard fails on any direct `env_legacy_store` import under services/domain/repos/tools.
- Existing parallel architecture regression tests pass.
- Focused commands and `python3 -m pytest -q` pass.

# Env Tool Semantic Clarity Test Plan

## 1. Test Objective

Prove that a host can understand, choose, call, and recover from BuddySwitch env tools using runtime-visible descriptions and runtime feedback, without reading `scripts/env/services/*.py`.

The tests start from host needs and memo boundaries. They are not allowed to pass merely because a current helper returns a field count, a full snapshot matches, or a private function has a particular shape.

## 2. Functional Requirements From The Memo

| ID | Requirement |
| --- | --- |
| `FR-001` | Host can identify what capability each env tool provides. |
| `FR-002` | Host can identify what each action reads, validates, creates, updates, deletes, issues, or opens. |
| `FR-003` | Host can identify required ids and payloads, plus the runtime surface where ids normally appear. |
| `FR-004` | Host can distinguish response content levels: summary, body, private file content, metadata, token, browser intent, browser session effect, and durable object. |
| `FR-005` | Host can identify whether state changed. |
| `FR-006` | Host can identify durability: none, durable product object, active-instance-local private file, transient token, or browser session. |
| `FR-007` | Host can understand why a rejected call was blocked. |
| `FR-008` | Host can tell whether a rejection changed state. |
| `FR-009` | Host can find correctable fields or alternative atomic capabilities after rejection. |
| `FR-010` | Host can distinguish tool atomic capabilities from business workflows. |
| `FR-011` | `allowed_next_action_options` is a conditional affordance, not a prescribed workflow. |
| `FR-012` | `context.summarize.tool_affordances` is compact but sufficient for first-pass tool choice. |
| `FR-013` | `context.get.tool_catalog`, `context.get.operation_semantics`, and `scripts/turn_runtime.py status` expose the full catalog. |
| `FR-014` | Shared skills describe repeated workflows and defer action details, effects, and recovery to runtime catalog and feedback. |

## 3. Quality Requirements

| ID | Requirement |
| --- | --- |
| `QR-001` | Tests must prove host-understandable meaning, not only field presence. |
| `QR-002` | Tests may reject obvious template phrases, but must not assert entire prose snapshots. |
| `QR-003` | Tests must not inspect private implementation structure when runtime-visible behavior is available. |
| `QR-004` | Tests must keep the current schema shape; they must not require semantic v2 or a new catalog. |
| `QR-005` | Tests must reject workflow prescriptions and phrase routing in tool semantics, response affordances, AGENTS, and shared skills. |
| `QR-006` | Tests must be deterministic and runnable with local pytest/unittest. |

## 4. Test Layers

### Focused Unit Tests

Purpose: prove semantic text and response helper output carry the minimum host-meaningful information before integration paths are checked.

Primary files:

- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_skills.py`

### Runtime-Visible Catalog Tests

Purpose: prove full catalog and compact discovery are visible through the same surfaces a host sees.

Primary files:

- `tests/test_context_binding_env_tool.py`
- `tests/test_turn_runtime.py`
- `tests/test_repo_consistency.py`
- `tests/test_host_decision_surface_product_mode.py`

### Representative Runtime Response Tests

Purpose: prove success and rejection feedback explain actual effect and recovery across read, write, validation, token, and browser actions.

Primary files:

- `tests/test_env_tool_response_contract.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_env_layer_end_to_end.py`
- tool-specific tests under `tests/test_*_env_tool.py`

### Regression And Boundary Tests

Purpose: prevent old patterns from returning: template text, phrase routers, workflow prescriptions, semantic v2, copied runtime catalogs in skills, and guidance that tells the host to inspect service code.

Primary files:

- `tests/test_repo_consistency.py`
- `tests/test_runtime_skills.py`
- `tests/test_env_tool_semantic_contract.py`

## 5. Focused Unit Test Cases

### `SEM-U-001`: Semantic Text Rejects Template Action Language

**Purpose:** Prove runtime-visible action text explains meaning rather than restating the action name.

**Fixture:** Call `contracts.env_tools_description()` directly.

**Execution:** Iterate every capability and `action_semantics` row.

**Assertions:**

- `plain_description`, `use_when`, and `success_means` do not match template fragments such as "You need `<tool>.<action>` behavior", "Execute `<tool>.<action>`", "returned structured state", or "structured capability feedback".
- Each action has at least one meaning-bearing token from its category:
  - read/list/get category includes summary, record, body, metadata, private file, token, browser intent, or catalog as applicable.
  - mutating category includes creates, updates, archives, deletes, opens, issues, or writes as applicable.

**Why this proves the requirement:** It checks host-visible semantics for explanatory value while avoiding exact sentence matching.

### `SEM-U-002`: Action Semantics Explain Return Level, State Effect, And Durability

**Purpose:** Prove each action tells a host what is returned and whether state changes.

**Fixture:** `contracts.env_tools_description()` and `contracts.TOOL_REGISTRY`.

**Execution:** Iterate all registered actions and group them by kind and tool.

**Assertions:**

- List actions describe summaries or records and avoid claiming full body content unless the action truly returns it.
- Get/read actions describe one explicit id or logical name and the content level returned.
- Validate actions describe validation-only behavior, no mutation, and normalized output when applicable.
- Mutating actions describe the state plane they write: product object, private file, token, or browser session.
- `side_effects.mutates` matches registry `mutates`.
- `side_effects.durability` is one of the existing durability meanings used by the runtime.

**Why this proves the requirement:** The host can infer action suitability from runtime-visible action semantics, not from service internals.

### `SEM-U-003`: Input Explanations Identify Runtime Id Sources

**Purpose:** Prove hosts can understand where ids and payload fields come from.

**Fixture:** Full tool catalog from `contracts.env_tools_description()`.

**Execution:** Check representative fields across tools.

**Assertions:**

- `task_id` explanations mention owned task rows or creation/list/get surfaces.
- `track_id` explanations mention candidate tracks, `track.list`, or `track.get`.
- `artifact_id` explanations mention `artifact.list`, artifact creation, track artifact summaries, or context artifact summaries.
- `logical_name` explanations mention active-buddy private buddybox capability and do not mention filesystem roots.
- `target_id` for evidence mentions artifact target ids.
- `query`, `backend`, and `engine` for search explain search request boundaries.

**Why this proves the requirement:** The assertions target host decision inputs and source surfaces, not a helper's internal code.

### `RESP-U-001`: Response Helpers Require Host-Visible Effect And Recovery Fields

**Purpose:** Keep canonical success and rejection helpers from accepting low-information payloads.

**Fixture:** Direct calls to `tool_responses.success()` and `tool_responses.rejection()`.

**Execution:** Exercise valid and invalid payloads.

**Assertions:**

- Success requires non-empty `effect_summary`, boolean `state_changed`, and non-empty `durability`.
- Rejection requires non-empty `why_blocked`, `impact`, and `retry_guidance`, plus boolean `state_changed` and `retryable`.
- Valid helper output preserves `tool`, `action`, `active_buddy`, and provided correction fields.

**Why this proves the requirement:** The helper is the shared gateway for runtime feedback, so it prevents semantic-free responses.

### `RESP-U-002`: Next Action Options Are Conditional Affordances

**Purpose:** Prevent `allowed_next_action_options` from becoming workflow prescription.

**Fixture:** Direct calls to `tool_responses.next_action_option()` and representative service responses.

**Execution:** Build option rows with valid conditional reasons and invalid workflow-prescriptive reasons.

**Assertions:**

- Valid option rows contain `tool`, `action`, `mutates`, `preconditions`, `reason`, and `source_refs`.
- Reasons with obvious prescriptions such as "must create artifact", "always create artifact", or "only next action" are rejected by helper tests or rejected in service-output regression scans.
- Option rows refer to runtime catalog or operation semantics through `source_refs`.

**Why this proves the requirement:** It validates optional atomic affordances without tying tests to one business scenario.

## 6. Runtime-Visible Catalog Test Cases

### `CAT-I-001`: `context.get` Exposes Full Catalog And Operation Semantics

**Purpose:** Prove the full semantic catalog is available through runtime context discovery.

**Fixture:** RuntimeWorkspaceTestMixin instance with active buddy `pm`.

**Execution:** Broker-route `context.get` with empty args.

**Assertions:**

- Response is `ok=true`, `state_changed=false`, `durability="none"`.
- Response contains `tool_catalog` and `operation_semantics`.
- Each registered tool has `plain_description`, `use_when`, `do_not_use_when`, and `action_semantics`.
- `operation_semantics` has every registered `tool.action`.
- `context.get` response does not require or mention reading `scripts/env/services/*.py`.

**Why this proves the requirement:** The host sees the same full catalog at runtime without source-code inspection.

### `CAT-I-002`: `turn_runtime.py status` Exposes The Same Full Catalog Outside Broker Calls

**Purpose:** Prove the full catalog is available before a broker call.

**Fixture:** Local checkout.

**Execution:** Run `python3 scripts/turn_runtime.py status` and parse JSON.

**Assertions:**

- `ok=true`.
- `env_tools` tool set equals `contracts.TOOL_REGISTRY`.
- Every tool row contains `action_semantics`.
- No `run`, `binding`, or `memory` tool appears.

**Why this proves the requirement:** It validates the outside-runtime route map named by the memo.

### `CAT-I-003`: Runtime Catalog Explains Representative Content Levels

**Purpose:** Prove catalog semantics distinguish summary, full body, private file content, token, and browser intent.

**Fixture:** `context.get.tool_catalog`.

**Execution:** Inspect representative action semantic rows.

**Assertions:**

- `artifact.list` says summaries and not full content.
- `artifact.get` says full artifact body/content.
- `buddybox.list` says private file summaries and no file body.
- `buddybox.read` says one private file body with `content` or `content_base64`.
- `evidence.issue_browser` says transient target-scoped token.
- `search.request` says target URL/browser intent and no page open.
- `search.open_browser` says browser session effect.

**Why this proves the requirement:** It verifies the distinctions that drive host tool selection, not exact implementation wording.

### `CAT-I-004`: Operation Semantics Machine Contract Remains Stable

**Purpose:** Prove semantic clarity did not become a new schema or break existing machine-readable action metadata.

**Fixture:** `contracts.operation_semantics()`.

**Execution:** Iterate all registry actions.

**Assertions:**

- Each action has `kind`, `mutates`, `required_permission`, `authority`, `requires`, `returns`, and `risk_hints`.
- No `semantic_v2`, `workflow_engine`, or parallel catalog key is introduced.

**Why this proves the requirement:** It protects the memo's "use current fields" boundary.

## 7. Representative Success Response Test Cases

### `RESP-I-001`: Read/List/Get Responses Identify Content Level

**Purpose:** Prove actual runtime responses carry the same content-level clarity as the catalog.

**Fixture:** Seed a track, task, artifact with body content, a buddybox file, and a handoff where needed.

**Execution:** Broker-route:

- `task.list`
- `task.get`
- `track.get`
- `artifact.list`
- `artifact.get`
- `buddybox.list`
- `buddybox.read`
- `handoff.list`
- `context.get`
- `context.summarize`
- `search.status`
- `search.request`

**Assertions:**

- Every response has `ok=true`, `effect_summary`, `state_changed=false`, `durability="none"` except browser/session paths.
- `read_scope` identifies the returned level.
- Summary/list responses do not contain full artifact body or buddybox file content.
- `artifact.get` contains artifact body content.
- `buddybox.read` contains exactly one of `content` or `content_base64`.
- `search.request` returns `target_url` and `page_opened=false`.

**Why this proves the requirement:** It verifies runtime behavior visible to the host, not just catalog metadata.

### `RESP-I-002`: Mutating Responses Identify State Plane And Durability

**Purpose:** Prove actual mutating responses tell the host what changed.

**Fixture:** Runtime workspace with seed ids as needed.

**Execution:** Broker-route:

- `task.create`
- `task.update`
- `track.join`
- `track.create` as PM
- `artifact.create_revision`
- `artifact.update_metadata`
- `handoff.create`
- `buddybox.write`
- `buddybox.delete`
- `evidence.issue_browser`
- `search.open_browser` with fake CDP server

**Assertions:**

- Durable product object writes have `state_changed=true`, `durability="durable"`, and created/updated ids or state change rows.
- Buddybox file writes/deletes use `durability="active_instance_local"` when a file changes and `mutates_product_state=false`.
- Evidence token issue uses `durability="transient token"` and does not claim product object mutation.
- Search browser open uses browser session durability and does not claim product object mutation.
- Already-archived task and repeated buddybox delete paths return `state_changed=false`.

**Why this proves the requirement:** It distinguishes product object mutation, private file mutation, token issue, and browser session effects.

### `RESP-I-003`: Validation Successes Are Explicitly Read-Only

**Purpose:** Prove validation actions do not look like writes.

**Fixture:** Valid artifact and handoff candidate payloads.

**Execution:** Broker-route `artifact.validate_payload` and `handoff.validate`.

**Assertions:**

- Responses have `state_changed=false`, `durability="none"`, `validation_only=true`.
- Responses return normalized candidate data.
- Any `allowed_next_action_options` is conditional and references the matching create action.

**Why this proves the requirement:** It confirms hosts can safely validate before deciding whether to write.

## 8. Representative Rejection Test Cases

### `REJ-I-001`: Payload Rejections Explain Correctable Fields

**Purpose:** Prove malformed payloads tell the host what to fix.

**Fixture:** Runtime instance for active buddy `pm`.

**Execution:** Send malformed payloads:

- `task.create` without `title`
- `artifact.create_revision` without `task_id`
- `handoff.validate` without `target_buddy`
- `context.get` with unsupported filter key
- `search.request` without `backend`
- `buddybox.write` with both `content` and `content_base64`

**Assertions:**

- Each response has `ok=false`, `why_blocked`, `impact`, `state_changed=false`, `retryable=true`, and `retry_guidance`.
- `correctable_fields` names the bad or missing fields.
- At least one recovery surface is visible through `allowed_next_actions`, `allowed_next_action_options`, or `alternative_capabilities`.

**Why this proves the requirement:** It tests host recovery from realistic malformed calls, not helper internals.

### `REJ-I-002`: Scope And Authority Rejections Explain Boundary And Alternatives

**Purpose:** Prove non-payload denials are understandable and do not look like silent failures.

**Fixture:** Seed PM-owned task/artifact and use non-PM or foreign-buddy calls.

**Execution:** Broker-route:

- `track.create` as `design`
- `task.get` for a foreign task
- `artifact.update_metadata` for a foreign artifact
- `handoff.validate` with foreign artifact id
- `evidence.issue_browser` for unsupported `target_type`

**Assertions:**

- Each response has a specific `permission_boundary`.
- `why_blocked` states the ownership, authority, target, or scope reason.
- `impact` says no product state changed.
- `correctable_fields` or `alternative_capabilities` helps the host recover.
- `retryable` value reflects whether changing payload alone can fix the issue.

**Why this proves the requirement:** It validates host-readable boundaries for permission and ownership failures.

### `REJ-I-003`: Buddybox Rejections Are Self-Correcting Without Path Guidance

**Purpose:** Preserve the strongest current example and prevent regression.

**Fixture:** Runtime instance for `pm`.

**Execution:** Call buddybox with:

- legacy `path`
- buddy-prefixed `logical_name`
- traversal
- unsupported encoding
- missing file

**Assertions:**

- Rejections expose `error.code`, `error.class`, `boundary`, `correctable_fields`, `alternative_capabilities`, `state_changed=false`, `mutates_product_state=false`.
- Response text does not expose absolute roots or tell the host to edit `buddyswitch/local/buddybox/**` directly.

**Why this proves the requirement:** It checks actual correction and privacy behavior visible to the host.

### `REJ-I-004`: Browser And Search Dependency Rejections Explain Impact

**Purpose:** Prove open-world search failures identify browser/search boundaries.

**Fixture:** Runtime instances with missing, invalid, and failing browser endpoints.

**Execution:** Broker-route `search.request` and `search.open_browser` through missing backend, invalid engine, browser unavailable, and CDP failure cases.

**Assertions:**

- Rejections include `why_blocked`, `impact`, `state_changed=false`, and `retry_guidance`.
- `correctable_fields` includes `query`, `backend`, `engine`, or browser readiness as applicable.
- Alternative capability includes `search.status` or a browser-open route where relevant.
- No rejection claims a product object changed.

**Why this proves the requirement:** It validates recovery from external dependency problems without hiding them behind generic retry text.

### `REJ-I-005`: Handoff Rejects Private Buddybox As Target-Readable Payload

**Purpose:** Prove tool semantics and runtime feedback keep private files distinct from cross-buddy handoff payloads.

**Fixture:** Design-owned track/task/artifact and a private buddybox logical name.

**Execution:** Call `handoff.validate` with `source_refs=[{"type":"buddybox","logical_name":"handoff/private.md"}]`.

**Assertions:**

- Response rejects with source-ref scope error.
- `why_blocked` explains buddybox logical names are private provenance, not target-readable handoff payloads.
- `state_changed=false`.
- Alternatives point toward artifact/product object references.

**Why this proves the requirement:** It verifies the core boundary between tool atomic capability and collaboration-readable object workflow.

## 9. Compact Discovery Test Cases

### `CTX-I-001`: Compact Affordances Support First-Pass Tool Choice

**Purpose:** Prove `context.summarize` is enough for a first tool-choice decision without full catalog duplication.

**Fixture:** Runtime instance with readable track/task/artifact plus empty or existing buddybox state.

**Execution:** Broker-route `context.summarize`.

**Assertions:**

- `tool_affordances` contains compact rows for `task`, `track`, `artifact`, `handoff`, `buddybox`, `context`, `evidence`, `search`, and `project_source`.
- Each row has host-choice fields: `capability`, `choose_when`, `id_inputs_from`, `returns`, `state_effect`, `durability`, and `supports`.
- Rows are compact and do not include `payload_fields`, `action_semantics`, `content`, `content_base64`, or full catalog structures.

**Why this proves the requirement:** It verifies first-pass choice support while enforcing the compact boundary.

### `CTX-I-002`: `context.summarize` Does Not Copy The Full Catalog

**Purpose:** Prevent compact discovery from turning into another catalog.

**Fixture:** Runtime instance.

**Execution:** Broker-route `context.summarize`.

**Assertions:**

- Response omits `tool_catalog` and `operation_semantics`.
- Response still includes `decision_surface`, `candidate_tracks`, `buddybox_desc`, and `tool_affordances`.
- `effect_summary` and `read_scope` describe compact orientation, not full catalog.

**Why this proves the requirement:** It protects the memo's context-discovery layering.

### `CTX-I-003`: Host Scenario Chooses Full Catalog Only When Needed

**Purpose:** Prove compact discovery and full catalog work together.

**Fixture:** Runtime instance.

**Execution:** First call `context.summarize`, then call `context.get`.

**Assertions:**

- `context.summarize.tool_affordances.artifact` lets a host infer artifact is product-readable and mutates product state.
- `context.summarize.tool_affordances.buddybox` lets a host infer buddybox is private and active-instance-local.
- `context.get.tool_catalog.artifact.action_semantics.get` supplies full action detail for artifact body reads.
- `context.get.tool_catalog.buddybox.action_semantics.read` supplies full action detail for private file reads.

**Why this proves the requirement:** It validates the intended discovery route rather than a single implementation function.

## 10. Shared Skill And AGENTS Boundary Test Cases

### `SKILL-I-001`: Shared Skills Defer Action Details To Runtime Catalog

**Purpose:** Prove shared skills do not replace runtime semantics.

**Fixture:** Read all files under `buddyswitch/skills/shared/*-tool/SKILL.md`.

**Execution:** Scan text with semantic boundary assertions.

**Assertions:**

- Each skill mentions `env.tool`.
- Each skill points to `context.get.tool_catalog`, `context.summarize.tool_affordances`, `scripts/turn_runtime.py status`, or runtime feedback for action details.
- Skills do not contain `payload_fields`, `action_semantics`, full response schemas, or copied action semantics.
- Skills do not tell hosts to ignore `permission_boundary`, `why_blocked`, `state_changed`, `durability`, `correctable_fields`, or `alternative_capabilities`.

**Why this proves the requirement:** It keeps repeated workflows in skills while runtime behavior remains authoritative.

### `SKILL-I-002`: Buddybox Skill Stays Workflow-Level

**Purpose:** Trim the longest shared skill without losing useful workflow guidance.

**Fixture:** `buddyswitch/skills/shared/buddybox-tool/SKILL.md`.

**Execution:** Scan text and section names.

**Assertions:**

- Skill still explains active-buddy private file capability and logical names.
- Skill still mentions representative use cases such as drafts, prototypes, exports, logs, reports, generated files, and binary outputs.
- Skill says runtime feedback wins for effects and recovery.
- Skill does not include a long common-flow catalog, `--path`, private roots, shell-search instructions, or mandatory artifact promotion language.

**Why this proves the requirement:** It preserves workflow utility while preventing skill text from becoming a second runtime catalog.

### `AGENTS-I-001`: AGENTS Files Stay Route Maps

**Purpose:** Prove AGENTS remains the short discovery route map layer.

**Fixture:** Root `AGENTS.md` and `tools/launcher/assets/buddies/*/AGENTS.md`.

**Execution:** Scan active AGENTS files.

**Assertions:**

- Buddy AGENTS mention `context summarize`.
- Buddy AGENTS mention `context get` or `turn_runtime.py status`.
- Buddy AGENTS list env tool names as a short route map.
- Buddy AGENTS do not contain `payload_fields`, `action_semantics`, `content_base64`, business workflow steps, phrase routing, or service-code inspection instructions.
- Root AGENTS keeps the direct runtime-state edit prohibition.

**Why this proves the requirement:** It validates the route-map layer without using AGENTS as a full manual.

## 11. Forbidden Pattern Regression Tests

### `REG-I-001`: Active Surfaces Reject Template Phrases

**Purpose:** Prevent low-signal semantic text from returning.

**Fixture:** Runtime-visible catalog and active guidance files.

**Execution:** Scan `contracts.env_tools_description()`, `context.summarize.tool_affordances`, shared skills, AGENTS, README, and role contracts.

**Assertions:**

- No runtime-visible semantics contain template fragments rejected by `SEM-U-001`.
- Documentation and skills do not contain phrase routing fragments such as "prototype means", "if the user says", or "route prototype to buddybox".

**Why this proves the requirement:** It protects host-understandable text quality across active surfaces.

### `REG-I-002`: Non-Goals Stay Absent

**Purpose:** Ensure the implementation does not create forbidden architecture.

**Fixture:** Repo scan over `scripts`, `buddyswitch`, `tools`, `framework`, `README.md`, and `AGENTS.md`, excluding memo/spec docs.

**Execution:** Use `rg` through `tests/test_repo_consistency.py`.

**Assertions:**

- No new active code or guidance mentions `semantic_v2`, `workflow_engine`, `phrase_router`, `rule_engine`, `generic tool-search subsystem`, or a new MCP env tool server.
- Existing runtime tools remain the registered env tools.

**Why this proves the requirement:** It directly maps to memo non-goals.

### `REG-I-003`: Tool Descriptions Do Not Encode Business Workflows

**Purpose:** Keep atomic tool semantics separate from business process.

**Fixture:** Runtime catalog and response affordance rows.

**Execution:** Scan capability semantics, action semantics, `allowed_next_action_options`, and `available_affordances`.

**Assertions:**

- No tool description says "after writing a PRD", "market research should", "Dev should", "handoff to Design", or similar business sequence.
- `allowed_next_action_options` reasons are conditional and action-level.

**Why this proves the requirement:** It verifies the core layer boundary between tools and skills.

### `REG-I-004`: Host-Facing Guidance Does Not Require Service Code

**Purpose:** Prove the active guidance route never sends the host to implementation internals for normal tool understanding.

**Fixture:** README, AGENTS, shared skills, role contracts, runtime context source descriptors, and full catalog text.

**Execution:** Scan active host-facing surfaces.

**Assertions:**

- No host-facing guidance tells the host to inspect `scripts/env/services/*.py` for tool meaning.
- Canonical code references can still name `scripts/env/tools/contracts.py` and `scripts/env/tools/semantics.py` as development sources, but runtime usage guidance points to `context.get`, `context.summarize`, `turn_runtime.py status`, and response fields.

**Why this proves the requirement:** It tests the memo's primary outcome from the host's point of view.

## 12. Smoke Host Scenarios

### `HOST-I-001`: Choose Artifact Body Read After Summary Discovery

**Purpose:** Prove host can infer that summaries are insufficient when full artifact body is needed.

**Fixture:** Track with at least one readable artifact containing body content.

**Execution:** Call `context.summarize`, `artifact.list`, then `context.get`.

**Assertions:**

- Compact affordance identifies artifact as product-readable deliverable.
- `artifact.list` response and catalog say summary rows only.
- Full catalog says `artifact.get` returns full body.
- Scenario test does not read `scripts/env/services/artifacts.py`.

**Why this proves the requirement:** It models a realistic host decision without hardcoding an exact sentence.

### `HOST-I-002`: Choose Buddybox Read After Private File Summary

**Purpose:** Prove host can choose exact private file read after list.

**Fixture:** Active buddy private file exists.

**Execution:** Call `context.summarize`, `buddybox.list`, then inspect `allowed_next_action_options`.

**Assertions:**

- Compact affordance identifies buddybox as active-buddy private and not product-readable.
- `buddybox.list` returns summaries only.
- Option row for `buddybox.read` is conditional and references runtime semantics.
- `buddybox.read` returns one file body and no product mutation.

**Why this proves the requirement:** It exercises summary/body/private-file distinctions through runtime surfaces.

### `HOST-I-003`: Recover From Invalid Artifact Create Payload

**Purpose:** Prove host can correct an invalid write call.

**Fixture:** Runtime instance with one owned task available through `task.list`.

**Execution:** Call `artifact.create_revision` without `task_id`, then call `task.list`, then call valid `artifact.create_revision`.

**Assertions:**

- Rejection says `task_id` is correctable and no state changed.
- Alternative capability or guidance points to task/context discovery.
- Valid retry creates durable artifact and returns created id.

**Why this proves the requirement:** It demonstrates correction from runtime feedback rather than hidden service knowledge.

### `HOST-I-004`: Use Search Request As Browser Intent, Not Evidence Or Product State

**Purpose:** Prove host can distinguish search planning from browser session mutation and evidence token issue.

**Fixture:** Runtime instance with browser endpoint.

**Execution:** Call `search.status`, `search.request`, and `search.open_browser` with fake CDP.

**Assertions:**

- `search.status` returns capability metadata.
- `search.request` returns target URL and `page_opened=false`.
- `search.open_browser` reports browser session mutation.
- No search response claims durable product object mutation or issues evidence token.

**Why this proves the requirement:** It validates metadata, browser intent, and browser session effect levels.

## 13. Verification Commands

Focused semantic and response tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runtime_tool_feedback.py \
  -q
```

Runtime catalog and compact discovery tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_turn_runtime.py \
  -q
```

Representative tool behavior tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_search_env_tool.py \
  tests/test_env_layer_end_to_end.py \
  -q
```

Guidance and non-goal regression tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Full targeted regression:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_context_binding_env_tool.py \
  tests/test_host_decision_surface_product_mode.py \
  tests/test_runtime_tool_feedback.py \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_handoff_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_search_env_tool.py \
  tests/test_env_tool_router.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_turn_runtime.py \
  tests/test_run_env_tool.py \
  tests/test_prepare_runtime_context.py \
  tests/test_runless_runtime_contract.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Manual catalog inspection:

```bash
python3 scripts/turn_runtime.py status
```

Manual inspection pass criteria:

- Full catalog includes every registered env tool.
- Full catalog contains clear action semantics and no template action language.
- `context.summarize` remains compact.
- Shared skills defer action details and recovery to runtime surfaces.

## 14. Coverage Matrix

| Memo section | Test categories | Specific cases |
| --- | --- | --- |
| Task Goal: host knows capability | Focused semantics, catalog visibility, compact discovery | `SEM-U-001`, `CAT-I-001`, `CTX-I-001` |
| Task Goal: host knows action effect | Focused semantics, success responses | `SEM-U-002`, `RESP-I-001`, `RESP-I-002`, `RESP-I-003` |
| Task Goal: host knows input ids and payload sources | Focused semantics, rejection recovery, host scenarios | `SEM-U-003`, `REJ-I-001`, `HOST-I-003` |
| Task Goal: host knows response content level | Catalog tests, success response tests, host scenarios | `CAT-I-003`, `RESP-I-001`, `HOST-I-001`, `HOST-I-002`, `HOST-I-004` |
| Task Goal: host knows state changed | Success and rejection response tests | `RESP-I-001`, `RESP-I-002`, `REJ-I-001`, `REJ-I-002`, `REJ-I-003`, `REJ-I-004` |
| Task Goal: host knows durability | Focused semantics and mutating success tests | `SEM-U-002`, `RESP-I-002`, `HOST-I-004` |
| Task Goal: host understands rejection reason | Rejection tests | `REJ-I-001`, `REJ-I-002`, `REJ-I-003`, `REJ-I-004`, `REJ-I-005` |
| Task Goal: host knows correction or alternative capability | Rejection tests and host correction scenario | `REJ-I-001`, `REJ-I-002`, `REJ-I-003`, `HOST-I-003` |
| Core Boundary: tool catalog explains atomic capability | Semantic and catalog tests | `SEM-U-001`, `SEM-U-002`, `CAT-I-001`, `CAT-I-003` |
| Core Boundary: tool response explains actual effect and recovery | Response success and rejection tests | `RESP-I-001`, `RESP-I-002`, `RESP-I-003`, `REJ-I-001` through `REJ-I-005` |
| Core Boundary: skills own repeated workflows | Shared skill tests | `SKILL-I-001`, `SKILL-I-002` |
| Core Boundary: AGENTS only route map | AGENTS boundary test | `AGENTS-I-001` |
| Non-Goal: no semantic v2 | Operation semantics and repo consistency | `CAT-I-004`, `REG-I-002` |
| Non-Goal: no workflow engine or phrase router | Forbidden pattern tests | `REG-I-002`, `REG-I-003` |
| Non-Goal: no business process in tool descriptions | Semantic and affordance regression | `REG-I-001`, `REG-I-003`, `RESP-U-002` |
| Non-Goal: shared skills are not runtime catalogs | Skill boundary tests | `SKILL-I-001`, `SKILL-I-002` |
| Verification Direction: reject template phrases | Semantic regression | `SEM-U-001`, `REG-I-001` |
| Verification Direction: distinguish summaries, bodies, files, metadata, tokens, browser intent | Content-level tests | `CAT-I-003`, `RESP-I-001`, `HOST-I-001`, `HOST-I-002`, `HOST-I-004` |
| Verification Direction: mutating actions state mutation and non-mutation | Mutating response tests | `RESP-I-002` |
| Verification Direction: representative rejections expose impact and recovery | Rejection tests | `REJ-I-001` through `REJ-I-005` |
| Verification Direction: `allowed_next_action_options` remains conditional | Response helper and host tests | `RESP-U-002`, `RESP-I-003`, `HOST-I-002`, `REG-I-003` |
| Verification Direction: compact scenarios smoke clarity without becoming design center | Compact and host tests | `CTX-I-001`, `CTX-I-002`, `CTX-I-003`, `HOST-I-001` through `HOST-I-004` |

## 15. Self-Check

- The test plan covers the full memo task: semantics, runtime feedback, compact discovery, shared skills, AGENTS route maps, non-goals, and regression gates.
- The test plan contains no placeholder cases.
- No test requires semantic v2, a workflow engine, phrase routing, a generic tool-search subsystem, or business workflow encoding in tool descriptions.
- Tests are organized from host functional requirements, then mapped to files and commands.
- The coverage matrix maps memo goals, boundaries, non-goals, and verification direction to concrete test cases.

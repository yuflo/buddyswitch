# Tool Layer Semantic Contract Test Plan

Date: 2026-05-20

Source memo: `docs/memo/2026-05-20-tool-layer-semantic-contract-memo.md`

## Goal

Prove the env.tool layer exposes a complete, truthful, runtime-owned semantic contract: agents can
discover exact action payload shapes from `context.get.tool_catalog`, call tools without reading
source code, and recover from payload rejections through standard field-level feedback.

## Task Confirmation

The current bottleneck is not dispatch, package independence, or runtime state isolation. Those were
addressed by the clean-runtime and black-box runtime work. The current bottleneck is the contract
visible to agents:

- `ToolDefinition.input_schema` is too shallow for several actions;
- some schema types do not match implementation behavior;
- registry projection still emits placeholder input explanations;
- full discovery does not expose the complete input schema;
- rejection feedback names correctable fields but does not consistently show expected field shape.

The repair must be forward-only. The finished branch must have one contract path:

```text
scripts/env/tools/<tool>/tool.py::DEFINITION
  -> env.tool_runtime.registry projection
  -> context.get / turn_runtime status / client help discovery
  -> ToolResult rejection feedback
```

No compatibility catalog, prompt-side schema mirror, second semantic card layer, or old/new dual
reader is allowed in the final state.

## Test Design Rules

- Tests are derived from functional requirements: discoverability, callability, recovery, and
  forward-only architecture.
- Tests must exercise public runtime surfaces wherever behavior matters: registry projection,
  `context.get`, `context.summarize`, generic env.tool dispatch, and CLI/status projection.
- Schema tests may inspect `ToolDefinition` because `DEFINITION` is the explicit public contract
  source for each tool.
- Tests must not assert a shape merely because current code happens to produce it. The expected
  shapes below come from repository domain contracts and user-visible tool semantics.
- Tests must fail when a tool action omits required fields, field descriptions, enum values, nested
  object properties, array item shapes, or complex examples needed for host construction.
- Tests must fail when registry code contains per-tool business knowledge such as `track.now`,
  `artifact.source_refs`, or `comment.mentions`.
- Tests must fail when compact discovery starts copying schema fragments or payload examples.
- Tests must fail when rejection responses mutate state on payload errors or hide exact field
  recovery information for targeted high-friction actions.

## Functional Requirements

R1. `scripts/env/tools/<tool>/tool.py::DEFINITION` remains the single source of truth for each
tool's public action contract.

R2. Every shipped action input schema is a truthful JSON Schema object with
`additionalProperties: false`, `properties`, `required`, and descriptions for public fields.

R3. Nested object and array fields expose host-constructible shapes through `properties`, `items`,
`required`, `enum`, `additionalProperties: false`, and examples where payload construction is not
obvious from primitive types.

R4. Enum-like implementation checks have matching schema `enum` values.

R5. Full discovery surfaces expose the complete action input schemas projected from
`ToolDefinition`.

R6. `payload_fields` remains derived convenience data only. It is not a contract source.

R7. `inputs_explained` is derived from schema descriptions and never falls back to placeholder text
such as `<field> payload field`.

R8. `context.summarize` remains compact and does not expose `tool_catalog`, `input_schemas`,
`properties`, `required`, `examples`, or payload examples.

R9. Rejection responses accept one canonical optional `field_errors` list and reject attempts to
override it through `extra`.

R10. Payload rejections keep `ok=false`, `state_changed=false`, and `durability="none"`.

R11. Targeted high-friction write paths return useful `field_errors`:

- `track.create` and `track.update_now` for `now`;
- `track.add_update` for `refs`;
- `artifact.create_revision` and `artifact.update_metadata` for `template` and `source_refs`;
- `buddybox.write` for `logical_name`, `content`, and `content_base64`;
- `comment.add` for `mentions` and section `anchor`.

R12. Shipped schemas match the domain contracts below.

R13. Skills and AGENTS continue to point agents to runtime discovery for exact payload knowledge and
do not copy schema tables.

R14. No compatibility modules, compatibility adapters, dual catalogs, schema mirrors, old tool
public modules, or registry per-tool special cases remain.

R15. Existing black-box runtime and clean-runtime behavior remains green.

## Required Schema Contract Coverage

| Area | Required contract |
| --- | --- |
| All action schemas | root `type: object`, `additionalProperties: false`, `properties`, `required`, and root or field descriptions sufficient for host use |
| Empty-payload actions | `properties: {}`, `required: []`, and no examples that imply a payload is needed |
| `track.create.now` / `track.update_now.now` | object with `required: ["next"]`, `next` string, `blocker` string-or-null, `additionalProperties: false`, and an example |
| `track.state` | enum `["active", "blocked", "review", "done"]` |
| `track.health` | enum `["ok", "risk", "blocked", "stale"]` |
| `track.add_update.kind` | enum `["progress", "decision", "blocker", "proof"]` |
| `track.add_update.refs` | array of objects with `type` enum `["artifact"]` and required `id` |
| `artifact.template` | enum `["brief", "proposal", "design", "decision", "proof", "note"]` |
| `artifact.source_refs` | array whose items support `artifact`, `track`, `task`, `buddybox`, `external`, and `note` refs with required fields for each ref kind |
| `artifact.read_claim` | optional string; description documents `summarized-full-content` as the value that triggers read-scope enforcement |
| `buddybox.list.recursive` | boolean, default `false` |
| `buddybox.list.limit` | integer with minimum `1`, default `200` |
| `buddybox.read.encoding` | enum for accepted encodings, including `utf-8` and `base64` when supported by implementation |
| `buddybox.write` | required `logical_name`; schema documents exactly one of `content` or `content_base64` must be provided |
| `comment.target_type` | enum `["track", "artifact", "artifact_section"]` |
| `comment.list.status` | enum `["open", "resolved"]` |
| `comment.add.mentions` | array of non-empty manifest buddy id strings |
| `task.status` | enum `["active", "blocked", "done", "archived"]` |
| `task.list.limit` | integer with minimum `1` |
| `context.get.limit` / `context.summarize.limit` | integer with minimum `1` |
| `evidence.target_type` | enum `["artifact"]` |
| `search.backend` | enum `["browser", "search_api"]` |
| `search.engine` | enum `["google", "web", "reddit", "x"]` |
| `message.to_buddy` | string description states it must be a manifest buddy id different from active buddy |

## Test Matrix

| ID | Requirement | File | Scenario | Main assertions |
| --- | --- | --- | --- | --- |
| SC1 | R1-R4 | `tests/test_env_tool_schema_contract.py` | Every shipped definition has complete schema metadata | every action has `required`; every field has `description`; object/array fields have nested shape; enum-like fields match domain values |
| SC2 | R3/R12 | `tests/test_env_tool_schema_contract.py` | High-risk nested payload shapes are host-constructible | exact checks for `track.now`, `track.refs`, `artifact.source_refs`, `comment.mentions`, and list limits |
| SC3 | R2/R3 | `tests/test_black_box_tool_runtime.py` | `validate_definition` rejects incomplete schemas | probe definitions missing descriptions, required lists, nested items, or enum values fail validation |
| SC4 | R5/R6 | `tests/test_env_tool_semantic_contract.py` | Full catalog exposes schemas from definitions | `env_tools_description()[tool]["input_schemas"][action] == action_def.input_schema`; `payload_fields` still matches property order |
| SC5 | R7 | `tests/test_env_tool_semantic_contract.py` | Input explanations are derived and non-placeholder | each `inputs_explained[field]` includes schema description; no value contains `payload field` |
| SC6 | R8 | `tests/test_env_tool_response_contract.py` | Compact context stays schema-free | `context.summarize` omits full catalog, input schemas, JSON Schema keys, and payload examples |
| SC7 | R9 | `tests/test_env_tool_response_contract.py` | `field_errors` is canonical rejection feedback | a complete `tool_results.rejection()` call with `field_errors` emits the list; the same complete call with `extra={"field_errors": []}` raises |
| SC8 | R10/R11 | `tests/test_env_tool_response_contract.py` | High-friction payload failures return field errors | invalid `track.now`, `track.refs`, `artifact.source_refs`, `buddybox.write`, and `comment.mentions` return field errors and no state change |
| SC9 | R5 | `tests/test_runless_runtime_contract.py` | `context.get` exposes full schemas | `context.get.tool_catalog["track"]["input_schemas"]["create"]` contains nested `now` shape |
| SC10 | R8 | `tests/test_runless_runtime_contract.py` | `context.summarize` stays compact | summary has affordances only; no copied schemas or examples |
| SC11 | R5 | `tests/test_turn_runtime.py` | `turn_runtime.py status` uses full registry projection | status output equals registry catalog and includes input schemas |
| SC12 | R14 | `tests/test_repo_consistency.py` | Forward-only architecture has no residue | scans reject schema cards, compatibility adapters, dual catalogs, and registry per-tool business branches |
| REG1 | R15 | Existing `tests/test_*_env_tool.py` suites | Shipped behavior remains intact | main path behavior for each tool still passes |
| SKILL1 | R13 | `tests/test_runtime_skills.py` | Skills defer to runtime discovery | skill text references `context.get.tool_catalog` and does not embed payload/schema tables |

## Detailed Test Designs

### SC1: Complete Shipped Schema Metadata

Create `tests/test_env_tool_schema_contract.py`.

Assertions:

- for every supported tool/action, `input_schema["required"]` exists and is a list;
- every value in `required` exists under `properties`;
- every top-level property has a non-empty `description`;
- every object property has `properties` and `additionalProperties: false`;
- every array property has an `items` schema;
- every nested object property has descriptions for public nested fields;
- complex fields named `now`, `refs`, `source_refs`, and `mentions` expose examples or item
  examples sufficient to construct a valid payload.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_every_shipped_action_schema_is_complete -q
```

Expected baseline before implementation: fail because existing schemas omit `required`, field
descriptions, and several nested shapes.

### SC2: High-Risk Schema Shapes Match Functional Contracts

In `tests/test_env_tool_schema_contract.py`, add explicit checks for the table in
"Required Schema Contract Coverage".

Key assertions:

- `track.create.now` and `track.update_now.now` require `next`, allow nullable `blocker`, and reject
  extra object fields through schema shape;
- `track.add_update.refs.items.properties.type.enum == ["artifact"]`;
- `artifact.create_revision.source_refs.items` accepts all supported source ref kinds with required
  fields for each kind;
- `buddybox.list.recursive.type == "boolean"` and `buddybox.list.limit.type == "integer"`;
- `comment.add.mentions.type == "array"` and `comment.add.mentions.items.type == "string"`;
- enums match the exact repository domain value sets.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py::EnvToolSchemaContractTests::test_high_risk_schema_shapes_match_domain_contracts -q
```

Expected baseline before implementation: fail on `now`, `source_refs`, `recursive`, `limit`,
`mentions`, and missing enums.

### SC3: Definition Validation Rejects Incomplete Contracts

Extend `tests/test_black_box_tool_runtime.py`.

Probe cases:

- property without `description`;
- schema without `required`;
- `required` field not present under `properties`;
- object property without nested `properties`;
- array property without `items`;
- property named `status`, `state`, `health`, `kind`, `template`, `target_type`, `backend`, or
  `engine` without `enum`.

Focused command:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_definition_validation_rejects_incomplete_input_contracts -q
```

Expected baseline before implementation: fail because `validate_definition` currently accepts
shallow schemas.

### SC4-SC5: Full Catalog Projection Is Derived From Definition

Extend `tests/test_env_tool_semantic_contract.py`.

Assertions:

- `env_tools_description()[tool]["input_schemas"][action]` deep-equals
  `get_action_definition(tool, action).input_schema`;
- `payload_fields` still equals top-level property order;
- `inputs_explained` contains every top-level property;
- `inputs_explained[field]` equals or includes the field `description`;
- no explanation contains `payload field`.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected baseline before implementation: fail because full input schemas are absent and
`inputs_explained` uses placeholder text.

### SC6, SC9, SC10, SC11: Runtime Discovery Surfaces

Extend `tests/test_env_tool_response_contract.py`, `tests/test_runless_runtime_contract.py`, and
`tests/test_turn_runtime.py`.

Assertions:

- full `context.get` includes `tool_catalog[tool]["input_schemas"]`;
- `context.get.tool_catalog` equals `env.tool_runtime.registry.env_tools_description()`;
- `context.summarize` excludes `tool_catalog`, `input_schemas`, `required`, `properties`,
  `examples`, and example payload values such as `Set up PM coordination`;
- `turn_runtime.py status` returns the same full tool catalog projection as the registry.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_runless_runtime_contract.py tests/test_turn_runtime.py -q
```

Expected baseline before implementation: fail on missing full schemas.

### SC7: Canonical `field_errors`

Extend `tests/test_env_tool_response_contract.py`.

Assertions:

- a complete `tool_results.rejection()` call with a `field_errors` row for `path="now"` emits
  `field_errors`;
- `field_errors` must be a list of objects;
- each field error has non-empty `path`, `message`, and at least one of `expected`,
  `allowed_values`, or `example`;
- `extra={"field_errors": []}` raises `ValueError` because canonical fields cannot be overridden.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_rejection_supports_canonical_field_errors -q
```

Expected baseline before implementation: fail because `rejection()` has no `field_errors` argument.

### SC8: High-Friction Payload Recovery

Extend `tests/test_env_tool_response_contract.py`.

Dispatch invalid public calls through `dispatch_env_tool_request`, not private helpers:

- PM calls `track.create` with `now: "next step"`;
- PM calls `track.update_now` with `now: {"blocker": null}`;
- PM calls `track.add_update` with `refs: {"id": "art-x"}`;
- dev calls `artifact.create_revision` with invalid `source_refs`;
- dev calls `buddybox.write` without both `content` and `content_base64`;
- dev calls `comment.add` with `mentions: "pm"`.

Assertions for every case:

- `ok is False`;
- `state_changed is False`;
- `durability == "none"`;
- `field_errors` exists and includes the failing field path;
- the field error contains actionable expected shape or allowed values;
- `correctable_fields` may remain for compatibility of response meaning, but it is not the only
  recovery signal.

Focused command:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_high_friction_payload_rejections_include_field_errors -q
```

Expected baseline before implementation: fail because payload rejections do not emit field errors.

### SC12: No Transition Residue

Extend `tests/test_repo_consistency.py`.

Scans:

```bash
rg -n 'schema card|semantic card|compatibility adapter|dual catalog|fallback registry|minimal_payload' scripts tests buddyswitch tools README.md

rg -n 'track\.now|artifact\.source_refs|comment\.mentions|buddybox\.list' scripts/env/tool_runtime
```

Assertions:

- first scan has no active transition/residue terms;
- second scan has no output, proving registry/runtime does not contain per-tool business logic.

Focused command:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_tool_semantic_contract_has_no_transition_residue -q
```

Expected baseline before implementation: both scans pass today and must stay green.

## Focused Baseline Command

Run after tests are added and before implementation:

```bash
python3 -m pytest \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runless_runtime_contract.py \
  tests/test_turn_runtime.py \
  tests/test_repo_consistency.py \
  -q
```

Expected baseline: fail only on semantic-contract gaps listed in this plan.

## Broader Verification

Run after focused tests pass:

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_schema_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runless_runtime_contract.py \
  tests/test_turn_runtime.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Run shipped behavior coverage:

```bash
python3 -m pytest \
  tests/test_artifact_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_search_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  -q
```

Run clean-runtime and broker regression coverage:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_broker.py \
  -q
```

Run syntax and residue checks:

```bash
python3 -m compileall scripts/env/tool_runtime scripts/env/tools tests -q

rg -n 'env\.tools\.(catalog|cli_helpers|discovery|dispatch|model|responses|router)|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|scripts/env/tools/.*/(contract|semantics|handlers|cli|service)\.py' \
  scripts tests buddyswitch tools README.md

rg -n 'schema card|semantic card|compatibility adapter|dual catalog|fallback registry|minimal_payload' \
  scripts tests buddyswitch tools README.md

rg -n 'track\.now|artifact\.source_refs|comment\.mentions|buddybox\.list' scripts/env/tool_runtime
```

The first `rg` command must return no old-runtime active code references. The second and third `rg`
commands must return no active implementation hits.

## Acceptance Standard

This task is complete only when:

1. focused semantic-contract tests pass;
2. shipped behavior tests pass;
3. clean-runtime and broker regression tests pass;
4. schema and field-error recovery are visible through public runtime surfaces;
5. compact discovery stays compact;
6. no transition compatibility residue remains;
7. final review confirms the implementation follows the forward-only architecture in the memo.

# Tool Layer Semantic Contract Memo

Date: 2026-05-20
Status: architecture memo; no runtime code changes implemented here.

## Background Problem

The black-box tool runtime migration removed the old central tool runtime surfaces and made each
tool expose a single public entrypoint:

```text
scripts/env/tools/<tool>/tool.py
scripts/env/tools/<tool>/_impl.py
scripts/env/tool_runtime/{definition,context,registry,results}.py
```

That is the right runtime shape, but the host-visible tool contract is still too weak for reliable
agent use.

The concrete symptom came from PM buddy trying to create a track. The buddy could discover
`track.create`, but the exposed catalog only said that the payload had fields such as `track_id`,
`title`, `outcome`, `appetite`, and `now`. It did not expose that `now` must be an object with
`next` and `blocker`. After a failed call, the rejection said `now is required`, which did not give
the exact object shape. The buddy then read help output, full context, and finally source code.

That behavior is a runtime contract failure, not a role-prompt problem.

Current code review found the broader pattern:

- action schemas often contain only top-level field names and primitive types;
- schemas commonly omit `required`, field `description`, nested object/array shapes, enums,
  defaults, and examples;
- registry projection flattens input details into `payload_fields` and generic text such as
  `now payload field`;
- some schemas do not match implementation behavior, such as list limits typed as strings while the
  implementation accepts integers, or list fields typed as strings;
- rejection responses expose `correctable_fields`, but not a standard field-level expected shape or
  valid example.

The bottleneck is therefore not tool dispatch. The bottleneck is that the runtime-visible contract
does not yet carry the full atomic capability semantics that the tool layer owns.

## Review Confirmation

The architecture should remain simple and forward-moving.

Use the existing black-box runtime. Do not add a second semantic layer, a compatibility bridge, or a
prompt-side schema mirror.

The final implementation must be one direct replacement of the weak contract surfaces:

```text
ToolDefinition.input_schema      -> complete, truthful JSON Schema contract
registry projection              -> deterministic projection of ToolDefinition
ToolResult rejection feedback    -> standard recovery signal for failed calls
```

There should be no interim supported state where old and new semantics coexist. During local
development, temporary helpers are acceptable only if removed before completion. The finished branch
must not leave future developers with another cleanup phase.

## Architecture Decision

The single source of truth is:

```text
scripts/env/tools/<tool>/tool.py::DEFINITION
```

`DEFINITION` owns the externally discoverable contract for that tool. It must describe the action
surface with enough precision that a host can call the tool without reading `_impl.py`.

The runtime has only three responsibilities around this contract:

1. validate that each definition is well formed;
2. project the definition into discovery surfaces;
3. route calls and format canonical tool responses.

The registry must not interpret tool business semantics. It may recursively project schemas and
metadata, but it must not contain per-tool special cases such as `track.now` or
`artifact.source_refs`.

The tool implementation remains independent:

```text
tool.py        owns public contract and invoke entrypoint
_impl.py       owns private implementation
ToolContext    provides host-owned capabilities
ToolResult     provides canonical success/rejection response shape
registry.py    discovers and projects tool.py definitions
```

## Contract Shape

Use JSON Schema as the input contract. Do not invent a schema-comment DSL.

Each action input schema should use normal JSON Schema features where they affect host behavior:

- `required` for mandatory inputs;
- `description` for each public field and important nested field;
- `enum` for fixed values;
- nested `properties` for object fields;
- `items` for array fields;
- `additionalProperties: false` at object boundaries that reject unknown fields;
- `default` when omission has a real semantic default;
- `examples` for complex or format-sensitive payloads.

Examples belong in the schema because they are validated against the same contract. They should stay
minimal and action-specific.

Do not put workflow sequencing into schemas. For example, `track.add_material` can say it publishes
one active-buddy-owned draft artifact as current shared material. It must not say that a PM landing
page workflow should next hand off to Design.

## Discovery Projection

`context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, and related full discovery
surfaces should expose the complete action input schema from `ToolDefinition`.

`inputs_explained` should be derived from schema descriptions, not manually written as a parallel
table. If a field has no description, the definition is incomplete.

`payload_fields` may remain as a convenience projection for quick field lists and legacy tests, but
it must be treated as derived data. It is not a contract source.

`context.summarize` should stay compact. It should not contain minimal payload examples or copied
schema fragments. Its job is first-pass affordance discovery:

```text
what capability exists
when to use it
when not to use it
where to inspect the exact contract
```

This keeps progressive discovery intact and avoids creating a second place where payload knowledge
can drift.

## Tool Response Recovery

Tool responses close the loop after a call. Rejection feedback should remain canonical and small.

Add one optional standard field to rejection responses:

```text
field_errors: [
  {
    path: "now",
    message: "now must be an object with required field next and optional blocker",
    expected: {"next": "non-empty string", "blocker": "string|null"},
    allowed_values: null,
    example: {"next": "Set up PM coordination.", "blocker": null}
  }
]
```

`field_errors` is a recovery signal. It does not replace JSON Schema and does not become a validator.
Each tool may fill it when a rejected payload has a precise field-level correction. Generic failures
can continue using `why_blocked`, `retry_guidance`, and `correctable_fields`.

The response layer must not infer tool-specific field errors from implementation internals. Tool
implementations own their rejection details.

## Independence Impact

This design preserves independent tool development.

Adding or changing a tool action should touch only:

```text
scripts/env/tools/<tool>/tool.py
scripts/env/tools/<tool>/_impl.py
tests focused on that tool and shared contract projection
```

It should not require:

- editing registry business logic;
- editing shared skills;
- editing AGENTS guidance;
- editing another tool package;
- adding compatibility adapters;
- updating a separate schema catalog.

The added burden on tool authors is deliberate: the tool owner must keep `input_schema` truthful.
That is not extra architecture; it is the public contract the tool already claims to expose.

## Rejected Designs

### Pure prose descriptions

Rejected because prose cannot be validated, cannot reliably express nested payload shapes, and tends
to drift into skills or AGENTS.

### Schema comments without real schema correction

Rejected because several current schemas are incomplete or mismatched with implementation behavior.
Adding comments to an inaccurate schema would preserve the root problem.

### Separate semantic cards

Rejected because hand-written cards would become a second source of truth. Compact affordances must
be derived from `ToolDefinition` and must not include payload examples.

### Compatibility transition

Rejected under the forward development rule. Do not support old and new semantic ownership at the
same time. The implementation may stage local edits, but the completed state must expose one
contract path only.

### Restoring old per-tool public modules

Rejected. Do not reintroduce `contract.py`, `semantics.py`, `handlers.py`, `cli.py`, `service.py`,
`TOOL_SPEC`, `ACTION_SEMANTICS`, or `HANDLER_SPECS`.

## One-Time Implementation Scope

The implementation should land as one coherent contract repair, not a partial patch that leaves a
future migration.

Required work:

1. Strengthen `ToolDefinition` validation so action schemas can express and require truthful
   metadata.
2. Fix all shipped tool input schemas to match implementation behavior.
3. Expose full action input schemas through full runtime discovery.
4. Derive `inputs_explained` from schema descriptions.
5. Keep compact discovery lightweight and schema-free.
6. Add canonical `field_errors` support to rejection responses.
7. Use `field_errors` for high-friction write actions first, including track creation/update,
   artifact revision creation, buddybox writes, and comments.
8. Delete or avoid any temporary compatibility code before declaring completion.

High-risk schema fixes to include in the same pass:

- `track.create.now` and `track.update_now.now` must expose the `next` / `blocker` object shape.
- `track.add_update.refs` must expose array item shape.
- `artifact.create_revision.template` and `artifact.update_metadata.template` must expose valid
  artifact templates.
- `artifact.source_refs` must expose supported ref shapes enough for host construction.
- `buddybox.list.recursive` and `buddybox.list.limit` must match implementation behavior.
- `comment.add.mentions` must be an array of buddy ids, not a string.
- fixed status/kind/mode fields must use enums where implementation rejects other values.

## Completion Standard

The work is complete only when the following are all true:

1. Every shipped action input schema includes required fields, field descriptions, and accurate
   nested object/array shapes where applicable.
2. Every enum-like implementation check has a matching schema enum.
3. `context.get.tool_catalog` exposes the full action input schemas as projections of
   `ToolDefinition`.
4. `context.summarize` remains compact and does not include schema or payload examples.
5. Rejection responses still guarantee `state_changed=False` for payload failures.
6. Rejection responses for targeted high-friction actions include useful `field_errors`.
7. Skills and AGENTS still point to runtime discovery instead of copying schemas.
8. No old public tool modules, old contract constants, dual registries, or compatibility readers are
   present.
9. No registry code contains per-tool business special cases.
10. Focused and broad env/tool/runtime tests pass.

Suggested verification:

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_tool_semantic_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_runless_runtime_contract.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q

rg -n 'env\.tools\.(catalog|cli_helpers|discovery|dispatch|model|responses|router)|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|scripts/env/tools/.*/(contract|semantics|handlers|cli|service)\.py' \
  scripts tests buddyswitch tools docs/memo docs/spec README.md

rg -n 'minimal_payload|schema card|compatibility adapter|dual catalog|fallback registry' \
  scripts tests buddyswitch tools docs/memo docs/spec README.md
```

The first command proves behavior and discovery contracts. The scans protect the forward-only
architecture from old runtime surfaces and new transitional abstractions.

## Final Position

The clean architecture is not a new layer. It is the existing black-box runtime made truthful:

```text
tool.py DEFINITION is the source
registry projects it
ToolResult reports what happened
skills and AGENTS defer to runtime discovery
```

This keeps tool development independent, removes the need for prompt-side repair text, and prevents
future cleanup burden from a half-migrated semantic surface.

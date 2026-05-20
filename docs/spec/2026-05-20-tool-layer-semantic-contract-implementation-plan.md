# Tool Layer Semantic Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Runtime behavior changes must follow `superpowers:test-driven-development`: write the focused failing test, verify the failure, implement the smallest direct change, and rerun the focused test before moving on.

**Goal:** Repair the env.tool semantic contract so each shipped tool exposes complete input schemas, full discovery projects those schemas from `ToolDefinition`, payload rejections provide standard field-level recovery, and no compatibility or schema-mirror layer remains.

**Architecture:** Keep the existing black-box runtime. `scripts/env/tools/<tool>/tool.py::DEFINITION` is the only source of public action semantics; `env.tool_runtime.registry` validates and projects definitions without per-tool business logic; `env.tool_runtime.results` formats canonical responses. This is a direct replacement of weak contract surfaces, not a transition to a second semantic layer.

**Tech Stack:** Python 3.9-compatible runtime code, dataclass definitions, JSON-compatible schemas, public env.tool dispatch, `unittest`/`pytest`, AST/text architecture checks, existing BuddySwitch runtime test helpers.

---

## Source Inputs

Read before editing:

- `docs/memo/2026-05-20-tool-layer-semantic-contract-memo.md`
- `docs/spec/2026-05-20-tool-layer-semantic-contract-test-plan.md`
- `scripts/env/tool_runtime/definition.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/tools/*/tool.py`
- `scripts/env/tools/*/_impl.py`
- `scripts/env/repos/tracks.py`
- `scripts/env/repos/artifacts.py`
- `scripts/env/repos/tasks.py`
- `scripts/env/repos/comments.py`
- `scripts/env/domain/source_refs.py`
- `scripts/env/domain/comment_targets.py`
- `scripts/env/domain/tasks.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_tool_payload_contract.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_runless_runtime_contract.py`
- `tests/test_turn_runtime.py`
- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

## Objective And Key Problems

The full task is one coherent semantic-contract repair:

1. Make shipped action schemas complete enough for an agent to construct valid payloads from
   discovery alone.
2. Make registry projection expose complete schemas and derive human input explanations from those
   schemas.
3. Add canonical rejection `field_errors` so invalid calls return actionable field-level recovery.
4. Keep compact discovery compact.
5. Remove or avoid all transition compatibility and per-tool business logic in shared runtime code.

The root problem is not missing PM instructions. The PM buddy had to inspect help, full context, and
source because runtime discovery did not expose that `track.create.now` must be an object with
`next` and `blocker`. The implementation must repair the runtime contract, not compensate with role
prompt text.

## Forward Rules

- Do not create `semantics.py`, `contract.py`, `schema_card.py`, a central schema catalog, a prompt
  mirror, or a compatibility reader.
- Do not restore `TOOL_SPEC`, `ACTION_SEMANTICS`, `HANDLER_SPECS`, or old `env.tools.*` runtime
  modules.
- Do not put `track.now`, `artifact.source_refs`, `comment.mentions`, or other tool-specific field
  logic in `env.tool_runtime.registry`.
- Do not add a JSON Schema validator dependency for runtime payload validation. The schema is the
  public contract; existing tool implementations remain the payload validators.
- Do not add workflow sequencing to schemas or field errors.
- Do not modify runtime state files directly.
- Do not edit main. All work happens in `.worktrees/clean-runtime-env`.

## Target File Structure

Create:

```text
tests/test_env_tool_schema_contract.py
```

Modify:

```text
scripts/env/tool_runtime/definition.py
scripts/env/tool_runtime/registry.py
scripts/env/tool_runtime/results.py
scripts/env/tools/artifact/tool.py
scripts/env/tools/artifact/_impl.py
scripts/env/tools/buddybox/tool.py
scripts/env/tools/buddybox/_impl.py
scripts/env/tools/comment/tool.py
scripts/env/tools/comment/_impl.py
scripts/env/tools/context/tool.py
scripts/env/tools/evidence/tool.py
scripts/env/tools/message/tool.py
scripts/env/tools/search/tool.py
scripts/env/tools/task/tool.py
scripts/env/tools/track/tool.py
scripts/env/tools/track/_impl.py
tests/test_black_box_tool_runtime.py
tests/test_env_tool_semantic_contract.py
tests/test_env_tool_response_contract.py
tests/test_runless_runtime_contract.py
tests/test_turn_runtime.py
tests/test_repo_consistency.py
```

Do not create or modify any compatibility layer.

## Final Discovery Shape

`registry.env_tools_description()` must project each tool like this:

```python
{
    "track": {
        "title": "Track Pages",
        "plain_description": "Operate shared progress pages and shared material/proof publication.",
        "use_when": ["You need to operate shared collaboration on a non-archived track."],
        "do_not_use_when": ["You need full artifact body content by id; use artifact.get."],
        "capability_boundary": "Only PM can create/archive tracks; shared mutation requires readable track scope.",
        "command": "python3 scripts/env/client.py track <action> --payload '<json-object>'",
        "scope": "shared track progress pages and publication timeline",
        "broker_method": "env.tool",
        "envelope": {"tool": "track", "action": "<action>", "args": "<object>"},
        "cli_resource": "track",
        "operations": ["create", "list", "open", "update_now", "add_material", "add_update", "add_proof", "archive"],
        "payload_fields": {"create": ["track_id", "title", "outcome", "appetite", "now", "state", "health"]},
        "input_schemas": {
            "create": {
                "type": "object",
                "additionalProperties": False,
                "required": ["track_id", "title", "outcome", "appetite", "now"],
                "properties": {
                    "track_id": {"type": "string", "description": "Stable id for the new track."},
                    "title": {"type": "string", "description": "Human-readable track title."},
                    "outcome": {"type": "string", "description": "Desired track outcome."},
                    "appetite": {"type": "string", "description": "Time or scope appetite for the track."},
                    "now": {
                        "type": "object",
                        "description": "Current next step and optional blocker for the track.",
                        "additionalProperties": False,
                        "required": ["next"],
                        "properties": {
                            "next": {"type": "string", "description": "Non-empty next action or current focus."},
                            "blocker": {"type": ["string", "null"], "description": "Current blocker text, or null."},
                        },
                    },
                    "state": {"type": "string", "description": "Track state.", "enum": ["active", "blocked", "review", "done"]},
                    "health": {"type": "string", "description": "Track health.", "enum": ["ok", "risk", "blocked", "stale"]},
                },
            }
        },
        "action_semantics": {
            "create": {
                "title": "track.create",
                "plain_description": "Create one PM-owned shared track page.",
                "inputs_explained": {"now": "Current next/blocker object for the track."},
                "side_effects": {"mutates": "runtime_objects", "durability": "durable"},
                "common_failures": ["active buddy is pm"],
            }
        },
        "feedback_source": "runtime/tool response fields",
        "authoritative_fields": [
            "permission_boundary",
            "allowed_next_actions",
            "allowed_next_action_options",
            "state_changed",
            "durability",
        ],
    }
}
```

`payload_fields`, `input_schemas`, and `inputs_explained` are all derived from
`ToolDefinition.input_schema`. `input_schemas` is the full contract projection. `payload_fields` is
only a derived convenience list. `inputs_explained` is only a concise human explanation derived from
schema descriptions.

`context.summarize` continues to use `registry.compact_tool_affordances()` and must not include
`input_schemas`, schema fragments, required fields, properties, examples, or payload examples.

## Field Error Shape

Add one canonical optional rejection field:

```python
field_errors=[
    {
        "path": "now",
        "message": "now must be an object with required field next and optional blocker",
        "expected": {"next": "non-empty string", "blocker": "string|null"},
        "allowed_values": None,
        "example": {"next": "Set up PM coordination.", "blocker": None},
    }
]
```

Rules:

- `field_errors` must be a list of objects.
- Each object must have non-empty `path` and `message`.
- Each object must include at least one of `expected`, `allowed_values`, or `example`.
- `extra` cannot override `field_errors`.
- Tool implementations decide which field errors to return.
- Shared response code validates shape only; it does not infer tool-specific field meaning.

## Schema Update Reference

Apply these schema updates in `scripts/env/tools/*/tool.py`:

| Tool | Required schema updates |
| --- | --- |
| `track` | add `required`, descriptions, `now` object shape, state/health/kind enums, `refs.items` object shape |
| `artifact` | add `required`, descriptions, template enum, `source_refs.items` union shape, `read_claim` description |
| `buddybox` | add `required`, descriptions, boolean `recursive`, integer `limit`, encoding enum, write content rules |
| `comment` | add `required`, descriptions, target type/status enums, `mentions` array |
| `context` | add `required`, descriptions, integer `limit` |
| `evidence` | add `required`, descriptions, target type enum |
| `message` | add `required`, descriptions, manifest buddy id description |
| `search` | add `required`, descriptions, backend/engine enums |
| `task` | add `required`, descriptions, status enum, integer `limit` |

Use domain values from repository code:

```text
track state: active, blocked, review, done
track health: ok, risk, blocked, stale
track update kind: progress, decision, blocker, proof
artifact template: brief, proposal, design, decision, proof, note
task status: active, blocked, done, archived
comment target_type: track, artifact, artifact_section
comment status: open, resolved
search backend: browser, search_api
search engine: google, web, reddit, x
source_ref type: artifact, track, task, buddybox, external, note
```

## Task 1: Add Schema Contract Tests

**Files:**

- Create: `tests/test_env_tool_schema_contract.py`
- Modify: `tests/test_black_box_tool_runtime.py`

- [ ] **Step 1: Create shipped schema completeness tests**

Create `tests/test_env_tool_schema_contract.py` with tests named:

```python
class EnvToolSchemaContractTests(unittest.TestCase):
    def test_every_shipped_action_schema_is_complete(self) -> None:
        self.assertTrue(catalog.supported_tools())

    def test_high_risk_schema_shapes_match_domain_contracts(self) -> None:
        self.assertIn("track", catalog.supported_tools())
```

The first test iterates `catalog.supported_tools()` and `catalog.supported_actions(tool)` and checks:

```python
schema = catalog.get_action_definition(tool, action).input_schema
self.assertEqual(schema.get("type"), "object")
self.assertIs(schema.get("additionalProperties"), False)
self.assertIsInstance(schema.get("properties"), dict)
self.assertIsInstance(schema.get("required"), list)
self.assertTrue(set(schema.get("required", [])).issubset(set(schema.get("properties", {}))))
for field, field_schema in schema["properties"].items():
    self.assertIsInstance(field_schema.get("description"), str, msg=f"{tool}.{action}.{field}")
    self.assertTrue(field_schema["description"].strip(), msg=f"{tool}.{action}.{field}")
```

Add recursive checks for object and array fields:

```python
if field_schema.get("type") == "object":
    self.assertIs(field_schema.get("additionalProperties"), False)
    self.assertIsInstance(field_schema.get("properties"), dict)
if field_schema.get("type") == "array":
    self.assertIsInstance(field_schema.get("items"), dict)
```

The high-risk test asserts the exact schema requirements listed in the test plan.

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py -q
```

Expected: fail on missing `required`, descriptions, nested shapes, and mismatched primitive types.

- [ ] **Step 3: Add definition validation negative tests**

In `tests/test_black_box_tool_runtime.py`, add
`test_definition_validation_rejects_incomplete_input_contracts`.

Use small probe `ToolDefinition` instances to assert `validate_definition()` raises `ValueError`
when:

- schema has no `required`;
- a property has no description;
- an object property has no nested `properties`;
- an array property has no `items`;
- an enum-like field name has no `enum`.

- [ ] **Step 4: Run focused validation test and verify it fails**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_definition_validation_rejects_incomplete_input_contracts -q
```

Expected: fail because current validation accepts incomplete schemas.

## Task 2: Add Discovery Projection Tests

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_runless_runtime_contract.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Test full catalog input schema projection**

In `tests/test_env_tool_semantic_contract.py`, add:

```python
def test_full_catalog_exposes_input_schemas_from_definitions(self) -> None:
    desc = catalog.env_tools_description()
    for tool in sorted(catalog.supported_tools()):
        for action in sorted(catalog.supported_actions(tool)):
            action_def = catalog.get_action_definition(tool, action)
            self.assertEqual(desc[tool]["input_schemas"][action], action_def.input_schema)
```

- [ ] **Step 2: Test derived non-placeholder input explanations**

In the same file, add:

```python
def test_inputs_explained_are_derived_from_schema_descriptions(self) -> None:
    desc = catalog.env_tools_description()
    for tool in sorted(catalog.supported_tools()):
        for action in sorted(catalog.supported_actions(tool)):
            schema = catalog.get_action_definition(tool, action).input_schema
            properties = schema.get("properties") or {}
            explanations = desc[tool]["action_semantics"][action]["inputs_explained"]
            self.assertEqual(set(explanations), set(properties))
            for field, field_schema in properties.items():
                self.assertIn(field_schema["description"], explanations[field])
                self.assertNotIn("payload field", explanations[field])
```

- [ ] **Step 3: Test runtime discovery surfaces**

Update existing context/status tests so:

- `context.get.tool_catalog` equals `registry.env_tools_description()`;
- `context.get.tool_catalog["track"]["input_schemas"]["create"]` contains the nested `now` schema;
- `turn_runtime.py status` includes the same `input_schemas` projection.

- [ ] **Step 4: Run discovery tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_runless_runtime_contract.py tests/test_turn_runtime.py -q
```

Expected: fail because `input_schemas` is absent and input explanations are placeholders.

## Task 3: Add Response Recovery Tests

**Files:**

- Modify: `tests/test_env_tool_response_contract.py`

- [ ] **Step 1: Test canonical `field_errors` support**

Add `test_rejection_supports_canonical_field_errors`:

```python
payload = tool_results.rejection(
    tool="track",
    action="track.create",
    active_buddy="pm",
    code="E_TRACK_PAYLOAD",
    message="now must be an object",
    permission_boundary="request-payload",
    human_summary="Track request payload is invalid.",
    why_blocked="now must be an object",
    impact="No track state changed.",
    state_changed=False,
    retryable=True,
    retry_guidance="Fix now and retry.",
    field_errors=[{
        "path": "now",
        "message": "now must be an object with required next and optional blocker",
        "expected": {"next": "non-empty string", "blocker": "string|null"},
        "example": {"next": "Set up PM coordination.", "blocker": None},
    }],
)
self.assertEqual(payload["field_errors"][0]["path"], "now")
with self.assertRaises(ValueError):
    tool_results.rejection(
        tool="track",
        action="track.create",
        active_buddy="pm",
        code="E_TRACK_PAYLOAD",
        message="now must be an object",
        permission_boundary="request-payload",
        human_summary="Track request payload is invalid.",
        why_blocked="now must be an object",
        impact="No track state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Fix now and retry.",
        extra={"field_errors": []},
    )
```

Use complete rejection arguments in committed test code.

- [ ] **Step 2: Test high-friction payload rejections**

Add `test_high_friction_payload_rejections_include_field_errors`. Dispatch public env.tool requests
for:

- `track.create` with string `now`;
- `track.update_now` with `now` missing `next`;
- `track.add_update` with non-list `refs`;
- `artifact.create_revision` with invalid `source_refs`;
- `buddybox.write` without `content` and without `content_base64`;
- `comment.add` with string `mentions`.

Assert every response has:

```python
self.assertFalse(response.get("ok"), msg=response)
self.assertIs(response.get("state_changed"), False, msg=response)
self.assertEqual(response.get("durability"), "none", msg=response)
self.assertIsInstance(response.get("field_errors"), list, msg=response)
self.assertTrue(response["field_errors"], msg=response)
```

- [ ] **Step 3: Run response tests and verify they fail**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py -q
```

Expected: fail because `field_errors` is not canonical and tool rejections do not emit it.

## Task 4: Strengthen `ToolDefinition` Validation

**Files:**

- Modify: `scripts/env/tool_runtime/definition.py`

- [ ] **Step 1: Add recursive input schema validation**

Extend `_validate_schema_object()` with helpers that validate:

- root schema has `required` list;
- `required` entries are strings and are present in `properties`;
- every property schema has non-empty `description`;
- object property schemas have `properties` and `additionalProperties: false`;
- object property schemas have `required` list;
- array property schemas have an object `items`;
- enum-like fields named `status`, `state`, `health`, `kind`, `template`, `target_type`, `backend`,
  and `engine` have a non-empty `enum` list.

Keep this as structural validation only. Do not validate runtime payloads against JSON Schema.

- [ ] **Step 2: Run validation tests**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_definition_validation_rejects_incomplete_input_contracts -q
```

Expected: pass for the new negative validation cases after Task 5 fixes shipped schemas. During the
Task 4 to Task 5 boundary, the worktree can be temporarily red because shipped schemas have not yet
been upgraded to the stricter validator.

## Task 5: Fix Shipped Tool Input Schemas

**Files:**

- Modify every `scripts/env/tools/<tool>/tool.py`

- [ ] **Step 1: Add small schema constants inside each `tool.py` where they reduce duplication**

Allowed constants are local to a tool file, such as:

```python
_NOW_SCHEMA = {
    "type": "object",
    "description": "Current next step and optional blocker for a track.",
    "additionalProperties": False,
    "required": ["next"],
    "properties": {
        "next": {"type": "string", "description": "Non-empty next action or current focus."},
        "blocker": {"type": ["string", "null"], "description": "Current blocker text, or null when unblocked."},
    },
    "examples": [{"next": "Set up PM coordination.", "blocker": None}],
}
```

Do not move these constants into registry or a central schema module.

- [ ] **Step 2: Update `track/tool.py`**

Add `required`, descriptions, enums, nested `now`, and nested `refs.items`.

Required fields:

```text
create: track_id, title, outcome, appetite, now
list: []
open: track_id
update_now: track_id
add_material: track_id, artifact_id, label, summary
add_update: track_id, summary
add_proof: track_id, artifact_id, label, summary
archive: track_id
```

Use repository enums:

```text
state: active, blocked, review, done
health: ok, risk, blocked, stale
kind: progress, decision, blocker, proof
```

- [ ] **Step 3: Update `artifact/tool.py`**

Required fields:

```text
get: artifact_id
create_revision: title, template, body
update_metadata: artifact_id
```

Add template enum and `source_refs` array items. The source ref item schema must support:

```text
artifact/track/task: required type, id
buddybox: required type, logical_name
external: required type, label; optional url
note: required type, label
```

Keep `read_claim` as an optional string with a description for `summarized-full-content`; do not
make it an enum because implementation accepts other strings.

- [ ] **Step 4: Update `buddybox/tool.py`**

Required fields:

```text
desc: []
list: []
read: logical_name
write: logical_name
delete: logical_name
```

Set:

```text
list.recursive type boolean default false
list.limit type integer minimum 1 default 200
read.encoding enum utf-8, base64
write.content/content_base64 descriptions documenting exactly-one requirement
```

- [ ] **Step 5: Update `comment/tool.py`**

Required fields:

```text
add: target_type, target_id, content
list: target_type, target_id
```

Set `target_type` enum, `status` enum, and `mentions` array of strings.

- [ ] **Step 6: Update remaining tool schemas**

Apply accurate `required`, descriptions, enums, and integer limits:

```text
context.get/context.summarize: limit integer minimum 1, required []
evidence.issue_browser: target_type, target_id
evidence.approve_downgrade: target_type, target_id, reason
message.send: to_buddy, content
message.list: []
search.status: []
search.request: query, backend
search.open_browser: query
task.create: title, summary
task.list: []
task.get: task_id
task.update: task_id
task.archive: task_id
```

Use enums from the schema update reference.

- [ ] **Step 7: Run schema tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py tests/test_black_box_tool_runtime.py::BlackBoxToolRuntimeTests::test_definition_validation_rejects_incomplete_input_contracts -q
```

Expected: pass.

## Task 6: Project Full Schemas And Derived Input Explanations

**Files:**

- Modify: `scripts/env/tool_runtime/registry.py`

- [ ] **Step 1: Add schema projection helpers**

Add a helper that returns JSON-compatible copies of action schemas:

```python
def _schema_copy(schema: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(schema))
```

Import `copy`. Do not mutate `ToolDefinition.input_schema`.

- [ ] **Step 2: Add `input_schemas` to full catalog**

In `env_tools_description()`, populate:

```python
input_schemas[action.name] = _schema_copy(action.input_schema)
```

and include `"input_schemas": input_schemas` in each tool row.

- [ ] **Step 3: Derive `inputs_explained` from schema descriptions**

Replace placeholder text in `_action_semantic_row()`:

```python
description = prop_schema.get("description")
if isinstance(description, str) and description.strip():
    inputs[key] = description.strip()
```

For object/array fields, append a concise type hint derived from nested schema, such as
`" Shape: object."` or `" Shape: array."`. Do not add tool-specific branches.

- [ ] **Step 4: Run discovery tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_runless_runtime_contract.py tests/test_turn_runtime.py -q
```

Expected: pass after compact-context assertions are updated.

## Task 7: Add Canonical `field_errors`

**Files:**

- Modify: `scripts/env/tool_runtime/results.py`

- [ ] **Step 1: Add `field_errors` to rejection canonical fields**

Add `"field_errors"` to `_REJECTION_CANONICAL_FIELDS`.

- [ ] **Step 2: Validate field error shape**

Add:

```python
def _validate_field_errors(value: Any) -> list[dict[str, Any]]:
    rows = _require_list(value, "field_errors")
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"field_errors[{index}] must be an object")
        path = _require_non_empty_text(row.get("path"), f"field_errors[{index}].path")
        message = _require_non_empty_text(row.get("message"), f"field_errors[{index}].message")
        if not any(key in row for key in ("expected", "allowed_values", "example")):
            raise ValueError(
                f"field_errors[{index}] must include expected, allowed_values, or example"
            )
        normalized.append(dict(row, path=path, message=message))
    return normalized
```

- [ ] **Step 3: Add `field_errors` argument to `rejection()`**

Add `field_errors: list[dict[str, Any]] | None = None` before `extra`.

If provided:

```python
payload["field_errors"] = _validate_field_errors(field_errors)
```

- [ ] **Step 4: Run response contract test**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_rejection_supports_canonical_field_errors -q
```

Expected: pass.

## Task 8: Add Field Errors To Targeted Tool Rejections

**Files:**

- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `scripts/env/tools/buddybox/_impl.py`
- Modify: `scripts/env/tools/comment/_impl.py`

- [ ] **Step 1: Extend local reject helpers**

Add optional `field_errors: list[dict[str, Any]] | None = None` to each targeted tool's
`_reject_payload()` helper and pass it to `tool_results.rejection()`.

- [ ] **Step 2: Add track field errors**

Return field errors for:

```text
track.create now missing/not object
track.update_now now missing next or not object
track.add_update refs not list or malformed ref entries
```

Use examples:

```python
{"next": "Set up PM coordination.", "blocker": None}
[{"type": "artifact", "id": "art-example-r1"}]
```

- [ ] **Step 3: Add artifact field errors**

Return field errors for:

```text
artifact.create_revision template invalid
artifact.update_metadata template invalid
artifact.create_revision source_refs invalid
artifact.update_metadata source_refs invalid
```

Use allowed template values from `context.repos.artifact.VALID_ARTIFACT_TEMPLATES` and examples:

```python
[{"type": "note", "label": "Source note"}]
[{"type": "external", "label": "Product page", "url": "https://example.com"}]
```

- [ ] **Step 4: Add buddybox field errors**

Return field errors for:

```text
missing logical_name
both content and content_base64 missing
both content and content_base64 provided
invalid encoding
```

Use expected text that makes the exactly-one content rule clear.

- [ ] **Step 5: Add comment field errors**

Return field errors for:

```text
mentions not list
mentions entry not string
unknown mention buddy
artifact_section missing anchor
```

For unknown buddies, include `allowed_values` from the manifest buddy ids.

- [ ] **Step 6: Run high-friction response tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_high_friction_payload_rejections_include_field_errors -q
```

Expected: pass.

## Task 9: Keep Compact Discovery Compact

**Files:**

- Modify: `scripts/env/tool_runtime/registry.py`
- Inspect: `scripts/env/tools/context/_impl.py`
- Modify: relevant context tests from Task 2

- [ ] **Step 1: Verify compact affordances remain schema-free**

Confirm `compact_tool_affordances()` returns only:

```text
capability
when_to_use
when_not_to_use
state_effect
returns
```

- [ ] **Step 2: Run compact discovery tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_runless_runtime_contract.py::RunlessRuntimeContractTests::test_context_summarize_omits_full_tool_catalog -q
```

Expected: pass. Run the full `tests/test_runless_runtime_contract.py -q` file as the required
check for this step.

## Task 10: Remove Transition Residue And Per-Tool Registry Knowledge

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Inspect: `scripts/env/tool_runtime/*`
- Inspect: `scripts/env/tools/*`
- Inspect: `buddyswitch/skills/*/SKILL.md`
- Inspect: `tools/launcher/assets/buddies/*/AGENTS.md`

- [ ] **Step 1: Add residue tests**

Add `test_tool_semantic_contract_has_no_transition_residue`.

It must reject active implementation hits for:

```text
schema card
semantic card
compatibility adapter
dual catalog
fallback registry
minimal_payload
```

It must reject per-tool field names inside `scripts/env/tool_runtime`:

```text
track.now
artifact.source_refs
comment.mentions
buddybox.list
```

- [ ] **Step 2: Run residue tests**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_tool_semantic_contract_has_no_transition_residue -q
```

Expected: pass.

## Task 11: Focused Verification Loop

Run focused tests after each implementation block:

```bash
python3 -m pytest tests/test_env_tool_schema_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_runless_runtime_contract.py tests/test_turn_runtime.py -q
python3 -m pytest tests/test_repo_consistency.py -q
```

Stop on the first failure. Fix the direct root cause before continuing.

## Task 12: Broader Verification And Review

**Files:**

- No planned production edits in this task after broader verification starts.

- [ ] **Step 1: Run contract and runtime discovery verification**

Run:

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

Expected: pass.

- [ ] **Step 2: Run shipped tool behavior verification**

Run:

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

Expected: pass.

- [ ] **Step 3: Run clean-runtime and broker verification**

Run:

```bash
python3 -m pytest \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_broker.py \
  -q
```

Expected: pass.

- [ ] **Step 4: Run syntax and residue checks**

Run:

```bash
python3 -m compileall scripts/env/tool_runtime scripts/env/tools tests -q
```

Expected: pass.

Run:

```bash
rg -n 'env\.tools\.(catalog|cli_helpers|discovery|dispatch|model|responses|router)|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|scripts/env/tools/.*/(contract|semantics|handlers|cli|service)\.py' \
  scripts tests buddyswitch tools README.md
```

Expected: no active-code hits.

Run:

```bash
rg -n 'schema card|semantic card|compatibility adapter|dual catalog|fallback registry|minimal_payload' \
  scripts tests buddyswitch tools README.md
```

Expected: no active implementation hits.

Run:

```bash
rg -n 'track\.now|artifact\.source_refs|comment\.mentions|buddybox\.list' scripts/env/tool_runtime
```

Expected: no output.

- [ ] **Step 5: Final review acceptance**

Review against:

- `docs/memo/2026-05-20-tool-layer-semantic-contract-memo.md`;
- this implementation plan;
- `docs/spec/2026-05-20-tool-layer-semantic-contract-test-plan.md`;
- test output from Steps 1-4.

The review must confirm:

- `ToolDefinition.input_schema` is the single public contract source;
- registry has no per-tool business branches;
- no compatibility or schema mirror was introduced;
- full discovery exposes complete schemas;
- compact discovery remains compact;
- `field_errors` is canonical and useful for targeted failures;
- all required verification commands passed.

## Completion Standard

Do not declare completion until all are true:

1. implementation tasks above are complete;
2. focused tests pass;
3. broader verification passes;
4. residue scans pass;
5. final review passes;
6. final summary lists changed files, verification commands, results, and remaining risk.

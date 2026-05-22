# ToolDefinition Semantic Fields Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ToolDefinition` the single source for static tool semantics and generate all runtime catalog projections from it.

**Architecture:** Keep the black-box env.tool runtime. Add concrete semantic fields to `ToolDefinition` and `ActionDefinition`, populate them in each `scripts/env/tools/<tool>/tool.py`, and update `scripts/env/tool_runtime/registry.py` so catalog, operation semantics, compact affordances, and status projections are derived from those fields. Do not create a new semantic overlay or workflow routing layer.

**Tech Stack:** Python 3.9-compatible dataclasses, JSON-compatible runtime projections, existing env.tool registry, `unittest`/`pytest`, BuddySwitch runtime tests.

---

## Required Reading

- `docs/spec/2026-05-22-tool-layer-semantic-source-of-truth-task-split.md`
- `docs/spec/2026-05-22-tool-definition-semantic-fields-projection-appendix.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `scripts/env/tool_runtime/definition.py`
- `scripts/env/tool_runtime/registry.py`
- `scripts/env/tool_runtime/results.py`
- `scripts/env/tools/*/tool.py`
- `scripts/env/tools/*/_impl.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_env_tool_response_contract.py`
- `tests/test_turn_runtime.py`

## Forward Rules

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`.
- Do not edit `main`.
- Do not restore old `contract.py`, `semantics.py`, `TOOL_SPEC`, or `ACTION_SEMANTICS` surfaces.
- Do not add a generic workflow/routing engine.
- Do not add phrase-to-track routing.
- Do not put PM workflow sequencing into ToolDefinition.
- Do not copy full payload schemas into AGENTS or shared skills.
- Do not modify `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Target Files

Modify:

```text
scripts/env/tool_runtime/definition.py
scripts/env/tool_runtime/registry.py
scripts/env/tools/artifact/tool.py
scripts/env/tools/buddybox/tool.py
scripts/env/tools/comment/tool.py
scripts/env/tools/context/tool.py
scripts/env/tools/evidence/tool.py
scripts/env/tools/message/tool.py
scripts/env/tools/request/tool.py
scripts/env/tools/search/tool.py
scripts/env/tools/task/tool.py
scripts/env/tools/track/tool.py
tests/test_env_tool_semantic_contract.py
tests/test_context_binding_env_tool.py
tests/test_turn_runtime.py
```

Do not modify shared skills or AGENTS in this task. That cleanup is Task 4 in the task split.

## Target Contract Fields

Add these fields:

```python
@dataclass(frozen=True)
class ActionDefinition:
    name: str
    title: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    kind: str
    mutates: str
    required_permission: str
    authority: str
    visibility: str
    durability: str
    result_content_level: str
    success_effect: str
    failure_state_guarantee: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    does_not_write: tuple[str, ...]
    preconditions: tuple[str, ...] = ()
    returns: tuple[str, ...] = ()
    use_when: tuple[str, ...] = ()
    do_not_use_when: tuple[str, ...] = ()
    risk_hints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    title: str
    description: str
    cli_resource: str
    command: str
    scope: str
    capability_boundary: str
    object_model: str
    use_when: tuple[str, ...]
    do_not_use_when: tuple[str, ...]
    actions: tuple[ActionDefinition, ...]
    backend_model: Mapping[str, Any] = field(default_factory=dict)
```

Allowed `ActionDefinition.durability` values:

```python
_ALLOWED_DURABILITY_VALUES = {"none", "transient", "durable"}
```

Meaning:

- `object_model`: stable tool-level meaning of the object/capability.
- `reads`: exact runtime object or boundary classes read by the action.
- `writes`: exact runtime object, runtime file, token, or browser-session classes written by the action.
- `does_not_write`: explicit guarantees that reduce host ambiguity.
- `visibility`: who can see the returned or mutated state.
- `durability`: declared effect durability for successful calls.
- `result_content_level`: whether result returns summary, full body, token metadata, browser intent, file body, or lifecycle row.
- `success_effect`: plain-language meaning of success.
- `failure_state_guarantee`: state-change guarantee on normal rejection/failure.

## Task 0: Baseline Confirmation

**Files:** none

- [ ] **Step 1: Confirm worktree**

Run:

```bash
pwd
git status --short --branch
```

Expected:

- `pwd` prints `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`;
- branch is `clean-runtime-env`;
- there is no switch to `main`.

- [ ] **Step 2: Run current semantic projection tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected before implementation:

- existing tests pass or fail only on unrelated local edits;
- they do not yet require `object_model`, `reads`, `writes`, `does_not_write`, `visibility`,
  `durability`, `result_content_level`, `success_effect`, or `failure_state_guarantee`.

## Task 1: Add Failing Tests For The New Semantic Fields

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add field completeness tests**

Add this test to `EnvToolSemanticContractTests`:

```python
    def test_every_tool_and_action_exposes_source_of_truth_semantic_fields(self) -> None:
        desc = self._desc()
        for tool in sorted(catalog.supported_tools()):
            with self.subTest(tool=tool):
                tool_desc = desc[tool]
                self.assertIsInstance(tool_desc.get("object_model"), str, msg=tool_desc)
                self.assertTrue(str(tool_desc.get("object_model", "")).strip(), msg=tool_desc)
            for action in sorted(catalog.supported_actions(tool)):
                with self.subTest(action=f"{tool}.{action}"):
                    semantic = desc[tool]["action_semantics"][action]
                    self.assertIsInstance(semantic.get("visibility"), str, msg=semantic)
                    self.assertTrue(str(semantic.get("visibility", "")).strip(), msg=semantic)
                    self.assertIn(semantic.get("durability"), {"none", "transient", "durable"}, msg=semantic)
                    self.assertIsInstance(semantic.get("result_content_level"), str, msg=semantic)
                    self.assertTrue(str(semantic.get("result_content_level", "")).strip(), msg=semantic)
                    self.assertIsInstance(semantic.get("success_means"), str, msg=semantic)
                    self.assertNotIn("completed under declared capability boundary", semantic["success_means"])
                    self.assertIsInstance(semantic.get("failure_state_guarantee"), str, msg=semantic)
                    self.assertTrue(str(semantic.get("failure_state_guarantee", "")).strip(), msg=semantic)
                    side_effects = semantic.get("side_effects")
                    self.assertIsInstance(side_effects, dict, msg=semantic)
                    assert isinstance(side_effects, dict)
                    for key in ("reads", "writes", "does_not_write"):
                        self.assertIsInstance(side_effects.get(key), list, msg=semantic)
                    self.assertTrue(
                        side_effects.get("reads") or side_effects.get("writes") or side_effects.get("does_not_write"),
                        msg=semantic,
                    )
```

- [ ] **Step 2: Add operation semantics projection tests**

Add this test to `EnvToolSemanticContractTests`:

```python
    def test_operation_semantics_include_generated_effect_fields(self) -> None:
        op = catalog.operation_semantics()
        for key, row in op.items():
            with self.subTest(action=key):
                self.assertIn("reads", row)
                self.assertIn("writes", row)
                self.assertIn("does_not_write", row)
                self.assertIn("visibility", row)
                self.assertIn("durability", row)
                self.assertIn("result_content_level", row)
                self.assertIn("success_effect", row)
                self.assertIn("failure_state_guarantee", row)
                self.assertIsInstance(row["reads"], list)
                self.assertIsInstance(row["writes"], list)
                self.assertIsInstance(row["does_not_write"], list)
                self.assertIn(row["durability"], {"none", "transient", "durable"})
```

- [ ] **Step 3: Add exact high-risk wording tests**

Add this test to `EnvToolSemanticContractTests`:

```python
    def test_high_risk_object_boundaries_are_explicit(self) -> None:
        desc = self._desc()
        track_model = str(desc["track"].get("object_model", "")).lower()
        task_model = str(desc["task"].get("object_model", "")).lower()
        artifact_model = str(desc["artifact"].get("object_model", "")).lower()
        buddybox_model = str(desc["buddybox"].get("object_model", "")).lower()

        self.assertIn("shared product outcome thread", track_model)
        self.assertIn("feature iteration", track_model)
        self.assertIn("not every feature", track_model)
        self.assertIn("private work item", task_model)
        self.assertIn("context link", task_model)
        self.assertIn("draft", artifact_model)
        self.assertIn("track.add_material", artifact_model)
        self.assertIn("private file", buddybox_model)
        self.assertIn("not product-readable", buddybox_model)

        task_create = desc["task"]["action_semantics"]["create"]
        task_side_effects = task_create["side_effects"]
        self.assertIn("track state", " ".join(task_side_effects["does_not_write"]).lower())
        self.assertIn("artifact visibility", " ".join(task_side_effects["does_not_write"]).lower())

        artifact_create = desc["artifact"]["action_semantics"]["create_revision"]
        self.assertIn("draft", artifact_create["success_means"].lower())
        self.assertIn("track.add_material", " ".join(artifact_create["side_effects"]["does_not_write"]))

        search_request = desc["search"]["action_semantics"]["request"]
        self.assertIn("does not fetch", search_request["success_means"].lower())
        self.assertEqual(search_request["durability"], "none")
```

- [ ] **Step 4: Add context and status projection tests**

In `tests/test_context_binding_env_tool.py`, extend
`test_context_get_metadata_and_source_workspace_semantics` with:

```python
        track_catalog = context_catalog.get("tool_catalog", {}).get("track", {})
        self.assertIn("shared product outcome thread", str(track_catalog.get("object_model", "")).lower())
        track_create = track_catalog.get("action_semantics", {}).get("create", {})
        self.assertIn("visibility", track_create)
        self.assertIn("failure_state_guarantee", track_create)
```

In `tests/test_turn_runtime.py`, add or extend a status test with:

```python
        desc = turn_runtime._build_env_tools_desc()
        self.assertIn("object_model", desc["track"])
        self.assertIn("reads", desc["track"]["action_semantics"]["open"]["side_effects"])
        self.assertNotIn(
            "completed under declared capability boundary",
            desc["track"]["action_semantics"]["open"]["success_means"],
        )
```

- [ ] **Step 5: Run failing tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_metadata_and_source_workspace_semantics tests/test_turn_runtime.py -q
```

Expected before implementation:

- tests fail because `object_model`, semantic side-effect fields, and concrete `success_means` are
  not projected yet.

## Task 2: Extend Runtime Definition Validation

**Files:**

- Modify: `scripts/env/tool_runtime/definition.py`

- [ ] **Step 1: Add durability values and dataclass fields**

Add the allowed durability set near `_ALLOWED_MUTATION_VALUES`:

```python
_ALLOWED_DURABILITY_VALUES = {"none", "transient", "durable"}
```

Update dataclasses to match the target contract fields in this plan.

- [ ] **Step 2: Validate new tool-level field**

In `validate_definition`, after `capability_boundary`, add:

```python
    _require_text(definition.object_model, field=f"{tool_id}.object_model")
```

- [ ] **Step 3: Validate new action-level fields**

In the action loop, after `authority`, add:

```python
        _require_text(action.visibility, field=f"{tool_id}.{name}.visibility")
        _require_text(action.result_content_level, field=f"{tool_id}.{name}.result_content_level")
        _require_text(action.success_effect, field=f"{tool_id}.{name}.success_effect")
        _require_text(action.failure_state_guarantee, field=f"{tool_id}.{name}.failure_state_guarantee")
        if action.durability not in _ALLOWED_DURABILITY_VALUES:
            raise ValueError(f"{tool_id}.{name}.durability must be one of {_ALLOWED_DURABILITY_VALUES}")
        _validate_text_tuple(action.reads, field=f"{tool_id}.{name}.reads")
        _validate_text_tuple(action.writes, field=f"{tool_id}.{name}.writes")
        _validate_text_tuple(action.does_not_write, field=f"{tool_id}.{name}.does_not_write", require_non_empty=True)
        if not (action.reads or action.writes or action.does_not_write):
            raise ValueError(f"{tool_id}.{name} must declare reads, writes, or does_not_write")
```

- [ ] **Step 4: Run definition-dependent tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_registry_semantics_cover_every_registered_tool_and_action -q
```

Expected after this step and before tool rows are populated:

- loading fails for tools whose `ToolDefinition` / `ActionDefinition` constructors do not yet
  provide the new required fields.

## Task 3: Update Registry Projections

**Files:**

- Modify: `scripts/env/tool_runtime/registry.py`

- [ ] **Step 1: Project tool-level object model**

In `env_tools_description()`, add `object_model` to each tool row:

```python
            "object_model": definition.object_model,
```

- [ ] **Step 2: Replace generic action semantic projection**

In `_action_semantic_row`, replace the generic side effects and success fields with:

```python
        "visibility": row.visibility,
        "durability": row.durability,
        "result_content_level": row.result_content_level,
        "side_effects": {
            "mutates": row.mutates,
            "reads": list(row.reads),
            "writes": list(row.writes),
            "does_not_write": list(row.does_not_write),
            "durability": row.durability,
            "idempotency": "idempotent read" if row.mutates == "none" else "state mutation",
        },
        "risk_hints": dict(row.risk_hints),
        "success_means": row.success_effect,
        "failure_state_guarantee": row.failure_state_guarantee,
        "common_failures": list(row.preconditions),
```

Keep the existing `inputs_explained` derivation from input schema descriptions.

- [ ] **Step 3: Extend operation semantics**

In `operation_semantics()`, add:

```python
                "reads": list(action.reads),
                "writes": list(action.writes),
                "does_not_write": list(action.does_not_write),
                "visibility": action.visibility,
                "durability": action.durability,
                "result_content_level": action.result_content_level,
                "success_effect": action.success_effect,
                "failure_state_guarantee": action.failure_state_guarantee,
```

- [ ] **Step 4: Extend compact affordances without schema bulk**

In `compact_tool_affordances()`, add:

```python
            "object_model": definition.object_model,
```

Keep `compact_tool_affordances()` free of `input_schemas`, `payload_fields`, `required`,
`properties`, and examples.

- [ ] **Step 5: Run projection tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_operation_semantics_machine_contract_is_preserved tests/test_env_tool_semantic_contract.py::EnvToolSemanticContractTests::test_operation_semantics_include_generated_effect_fields -q
```

Expected before tool rows are populated:

- imports fail or validation errors identify missing semantic fields.

## Task 4: Populate Every ToolDefinition Row

**Files:**

- Modify: `scripts/env/tools/artifact/tool.py`
- Modify: `scripts/env/tools/buddybox/tool.py`
- Modify: `scripts/env/tools/comment/tool.py`
- Modify: `scripts/env/tools/context/tool.py`
- Modify: `scripts/env/tools/evidence/tool.py`
- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/tools/request/tool.py`
- Modify: `scripts/env/tools/search/tool.py`
- Modify: `scripts/env/tools/task/tool.py`
- Modify: `scripts/env/tools/track/tool.py`

- [ ] **Step 1: Add tool-level `object_model` values**

Use the exact tool-level values from
`docs/spec/2026-05-22-tool-definition-semantic-fields-projection-appendix.md`.

- [ ] **Step 2: Add action-level fields**

For every `ActionDefinition`, add:

```python
visibility='<appendix value>',
durability='<appendix value>',
result_content_level='<appendix value>',
success_effect='<appendix value>',
failure_state_guarantee='<appendix value>',
reads=(<appendix tuple values>),
writes=(<appendix tuple values>),
does_not_write=(<appendix tuple values>),
```

The appendix covers all currently supported actions:

```text
artifact.list
artifact.get
artifact.create_revision
artifact.update_metadata
buddybox.desc
buddybox.list
buddybox.read
buddybox.write
buddybox.delete
comment.add
comment.list
comment.resolve
context.get
context.summarize
context.list_sources
evidence.issue_browser
evidence.approve_downgrade
message.send
message.list
request.create
request.list
request.get
request.accept
request.block
request.complete
request.cancel
search.status
search.request
search.open_browser
task.create
task.list
task.get
task.update
task.archive
track.create
track.list
track.open
track.update_now
track.add_material
track.add_update
track.add_proof
track.archive
```

- [ ] **Step 3: Keep PM workflow out of ToolDefinition**

When editing `track` and `task`, include the object distinction:

```text
track = shared product outcome thread; feature iteration is common but not mandatory.
task = active-buddy private work item; track_id is context only.
```

Do not add deterministic routing such as "create one track per feature".

- [ ] **Step 4: Run import and semantic coverage tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Expected after implementation:

- all registered tools load;
- every action has generated semantic effect fields;
- generic `success_means` text is absent;
- high-risk object boundary wording is present.

## Task 5: Verify Context And Status Projections

**Files:**

- Modify only tests if failures show missing assertions from Task 1.

- [ ] **Step 1: Run context projection test**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_metadata_and_source_workspace_semantics -q
```

Expected:

- `context.get.tool_catalog` includes `object_model`;
- `operation_semantics` includes action `reads`, `writes`, `does_not_write`, `visibility`,
  `durability`, `result_content_level`, `success_effect`, and `failure_state_guarantee`;
- `context.summarize` remains compact and does not include full schemas.

- [ ] **Step 2: Run status projection tests**

Run:

```bash
python3 -m pytest tests/test_turn_runtime.py -q
```

Expected:

- status projection still matches registry output;
- generated tool descriptions include the new semantic fields.

## Task 6: Final Verification

**Files:** none

- [ ] **Step 1: Run focused semantic suite**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_semantic_contract.py \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_metadata_and_source_workspace_semantics \
  tests/test_env_tool_response_contract.py::EnvToolResponseContractTests::test_context_get_and_summarize_catalog_scope \
  tests/test_turn_runtime.py \
  -q
```

Expected:

- all selected tests pass.

- [ ] **Step 2: Run drift scan**

Run:

```bash
rg -n "completed under declared capability boundary|scripts/env/tools/.*/(contract|semantics)\\.py|TOOL_SPEC|ACTION_SEMANTICS|track.get|comment.reopen" scripts tests buddyswitch/skills tools/launcher/assets docs/spec docs/bitter
```

Expected:

- no live runtime/skill/AGENTS references reintroduce old semantic surfaces or nonexistent actions;
- historical docs may appear only when clearly describing removed history.

- [ ] **Step 3: Inspect diff**

Run:

```bash
git diff --stat
git diff -- scripts/env/tool_runtime/definition.py scripts/env/tool_runtime/registry.py tests/test_env_tool_semantic_contract.py
```

Expected:

- changes are limited to semantic contract fields, generated projections, tool definitions, and
  focused tests;
- no AGENTS or shared skill cleanup appears in this Task 1 diff.

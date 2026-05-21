# Tool Layer P0/P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close P0 runtime/test red points and implement P1 human-use inbox/buddybox/context discovery improvements without weakening tool-layer boundaries.

**Architecture:** Keep tools black-boxed behind `tool.py` and `ToolContext`. P0 tightens existing runtime contracts; P1 adds compact read-only discovery surfaces and simple message inbox filters. Business SOP remains in skills or explicit prompts.

**Tech Stack:** Python env.tool runtime, JSON-backed repos, `ToolDefinition`/`ActionDefinition`, `ToolContext`, canonical `ToolResult`, `unittest`/`pytest`.

---

## Required Reading

- `docs/memo/2026-05-21-tool-layer-p0-p1-architecture-review.md`
- `docs/spec/2026-05-21-tool-layer-p0-p1-forward-scope.md`
- `docs/spec/2026-05-21-tool-layer-p0-p1-test-plan.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/memo/2026-05-20-black-box-tool-runtime-memo.md`
- `scripts/env/tools/context/_impl.py`
- `scripts/env/tools/message/tool.py`
- `scripts/env/tools/message/_impl.py`
- `scripts/env/domain/messages.py`
- `scripts/env/repos/messages.py`
- `scripts/env/domain/buddybox_workspace.py`
- `scripts/env/repos/buddybox_files.py`
- `scripts/env/tools/buddybox/_impl.py`
- `scripts/env/tools/request/_impl.py`
- `scripts/env/domain/artifact_relations.py`
- `scripts/env/domain/artifact_visibility.py`
- `scripts/env/tool_runtime/registry.py`

## Forward Rules

- Work only in `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`.
- Do not edit `main`.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
- Do not create transition adapters.
- Do not add old per-tool public surfaces.
- Do not create message bindings to track/artifact/request.
- Do not create scheduler/daemon/workflow engine.
- Do not add relation object files or relation tool.
- Do not weaken black-box tool runtime tests.

## Target Files

Expected modifications:

```text
scripts/env/domain/artifact_relations.py
scripts/env/domain/artifact_visibility.py
scripts/env/domain/buddybox_workspace.py
scripts/env/domain/messages.py
scripts/env/tool_runtime/registry.py
scripts/env/tools/context/_impl.py
scripts/env/tools/context/tool.py
scripts/env/tools/message/tool.py
scripts/env/tools/message/_impl.py
scripts/env/tools/request/_impl.py
tests/test_artifact_env_tool.py
tests/test_black_box_tool_runtime.py
tests/test_buddybox_env_tool.py
tests/test_context_binding_env_tool.py
tests/test_env_layer_boundaries.py
tests/test_env_tool_package_independence.py
tests/test_env_tool_payload_contract.py
tests/test_env_tool_router.py
tests/test_env_tool_schema_contract.py
tests/test_env_tool_semantic_contract.py
tests/test_host_decision_surface_product_mode.py
tests/test_message_env_tool.py
tests/test_parallel_contracts.py
tests/test_repo_consistency.py
```

Do not modify shared skills unless a test proves they are stale. If skills are modified, they must continue to point to runtime discovery and not copy payload/action tables.

## Task 0: Baseline And Red Point Confirmation

**Files:** none

- [ ] **Step 1: Confirm worktree**

Run:

```bash
pwd
git status --short
```

Expected:

- `pwd` is `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`;
- dirty files may exist;
- no switch to `main`.

- [ ] **Step 2: Run current focused red groups**

Run:

```bash
python3 -m pytest \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_artifact_summaries_are_current_only \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_get_applies_filters \
  tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_exposes_compact_tool_affordances \
  tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_track_artifact_publication_writes_only_live_in_publication_domain \
  tests/test_env_tool_payload_contract.py::EnvToolPayloadContractTests::test_every_action_rejects_unregistered_payload_field_without_state_change \
  -q
```

Expected before implementation:

- context tests may fail on historical artifact rows or old request expected sets;
- layer-boundary test may fail on `artifact_relations.py`;
- payload contract may fail on `request.create`.

- [ ] **Step 3: Run registry-focused red groups**

Run:

```bash
python3 -m pytest \
  tests/test_env_tool_router.py \
  tests/test_env_tool_package_independence.py \
  tests/test_env_tool_semantic_contract.py \
  -q
```

Expected before implementation:

- failures may include old expected tool sets, dash action normalization, dynamic probe projection, or stale catalog errors.

## Task 1: P0 Context Candidate Artifact Surface

**Files:**

- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_host_decision_surface_product_mode.py`
- Modify: `scripts/env/tools/context/_impl.py`

- [ ] **Step 1: Add or tighten failing tests for current-only context artifacts**

In `tests/test_context_binding_env_tool.py`, ensure tests cover:

```python
def test_context_artifact_summaries_are_current_only(self) -> None:
    self._seed_context_state()
    instance_json = self._instance_json()
    payload = self._dispatch(instance_json=instance_json, tool="context", action="get", args={})
    self.assertTrue(payload.get("ok"), msg=payload)

    rows = payload.get("artifact_summaries")
    self.assertIsInstance(rows, list, msg=payload)
    ids = [row.get("artifact_id") for row in rows if isinstance(row, dict)]
    self.assertIn("art-task-dev-context-note-r2", ids)
    self.assertNotIn("art-task-dev-context-note-r1", ids)
    self.assertNotIn("art-task-dev-archived-r1", ids)
    for row in rows:
        if isinstance(row, dict):
            self.assertNotIn("body", row, msg=row)
```

Add a separate test for track-filtered own draft exclusion:

```python
def test_context_summarize_track_filter_excludes_unpublished_owner_drafts(self) -> None:
    self._seed_context_state()
    draft = env_store.create_artifact_revision(
        artifact_id="art-context-owner-draft-untracked",
        title="Owner Draft",
        summary="private draft",
        body="private",
        template="note",
        supersedes_artifact_id=None,
        created_by="dev",
        authors=["dev"],
        source_refs=[{"type": "note", "label": "private"}],
    )
    self.assertEqual(draft.get("status"), "draft")

    instance_json = self._instance_json()
    payload = self._dispatch(
        instance_json=instance_json,
        tool="context",
        action="summarize",
        args={"track_id": "track-context-active"},
    )
    self.assertTrue(payload.get("ok"), msg=payload)
    ids = [row.get("artifact_id") for row in payload.get("candidate_artifacts", []) if isinstance(row, dict)]
    self.assertIn("art-task-dev-context-note-r2", ids)
    self.assertNotIn("art-task-dev-context-note-r1", ids)
    self.assertNotIn("art-context-owner-draft-untracked", ids)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_artifact_summaries_are_current_only tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_track_filter_excludes_unpublished_owner_drafts -q
```

Expected before implementation:

- at least one test fails because historical rows are included or the new test is not implemented yet.

- [ ] **Step 3: Implement context row filtering**

In `scripts/env/tools/context/_impl.py`, update `_candidate_artifact_rows` so it:

- computes artifact read decision;
- skips unreadable artifacts;
- when `track_filter` is set, includes only artifacts whose decision track id equals the filter and whose currentness is `current` or `proof`;
- when no `track_filter` is set, includes current/proof rows and active-buddy-owned drafts;
- skips `track_history`/superseded rows in context surfaces.

Use existing `artifact_list_row`; do not add new object types.

Implementation shape:

```python
def _context_artifact_row_allowed(
    *,
    artifact: dict[str, Any],
    decision: dict[str, Any],
    active_buddy: str,
    track_filter: str | None,
) -> bool:
    relation = decision.get("relation")
    if isinstance(track_filter, str) and track_filter.strip():
        return decision.get("track_id") == track_filter.strip() and relation in {"track_material", "track_proof"}
    if relation in {"track_material", "track_proof"}:
        return True
    return artifact.get("status") == "draft" and artifact.get("created_by") == active_buddy
```

Call this helper before building rows.

- [ ] **Step 4: Run focused context tests**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
```

Expected:

- all context/decision-surface tests pass;
- rows remain summary-only.

## Task 2: P0 Registry Contract And Router Red Points

**Files:**

- Modify: `tests/test_env_tool_router.py`
- Modify: `tests/test_env_tool_package_independence.py`
- Modify: `scripts/env/tool_runtime/registry.py`
- Modify: other registry tests only if they still contain stale expected tool sets.

- [ ] **Step 1: Update stale expected tool sets**

In `tests/test_env_tool_router.py`, add `request`:

```python
EXPECTED_TOOLS = {"task", "track", "artifact", "buddybox", "context", "evidence", "search", "message", "comment", "request"}
```

In `tests/test_env_tool_package_independence.py`, add `request`:

```python
SHIPPED_TOOLS = {
    "task",
    "track",
    "artifact",
    "buddybox",
    "context",
    "evidence",
    "message",
    "comment",
    "search",
    "request",
}
```

- [ ] **Step 2: Run expected-tool tests**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py::EnvToolRouterTests::test_registry_surface_matches_expected_tools tests/test_env_tool_package_independence.py::EnvToolPackageIndependenceTests::test_registry_projection_does_not_load_private_impl_repos_or_domains -q
```

Expected:

- pass after expected sets are updated;
- if failures remain, they must be real registry behavior failures, not stale constants.

- [ ] **Step 3: Fix dash action normalization**

In `scripts/env/tool_runtime/registry.py`, normalize action hyphens to underscores before supported-action lookup:

```python
action = raw_action.strip().replace("-", "_")
```

Keep rejection feedback using the normalized semantic action.

- [ ] **Step 4: Fix dynamic probe projection if needed**

If `test_local_probe_tool_package_is_discovered_without_central_edits` still fails, inspect cache behavior in `env_tools_description()`.

The desired behavior:

- after `env.tools.__path__.append(...)`, `importlib.invalidate_caches()`, and `registry.clear_cache()`, `supported_tools()` includes `probe`;
- `env_tools_description()` includes `probe`;
- load errors from previous unsupported lookups do not hide valid dynamic tools.

If `_LOAD_ERRORS` contains stale rows for tools no longer returned by `discover_tool_ids()`, filter them in `tool_catalog_errors()`:

```python
def tool_catalog_errors() -> list[dict[str, str]]:
    discovered = set(discover_tool_ids())
    for tool in sorted(discovered):
        try:
            load_definition(tool)
        except Exception:
            continue
    for tool in sorted(set(_LOAD_ERRORS) - discovered):
        _LOAD_ERRORS.pop(tool, None)
    return [_LOAD_ERRORS[name] for name in sorted(_LOAD_ERRORS)]
```

- [ ] **Step 5: Run registry suite**

Run:

```bash
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_package_independence.py tests/test_env_tool_semantic_contract.py -q
```

Expected:

- registry/router/package-independence suite passes;
- no private `_impl`, repo, or domain modules are loaded during projection tests.

## Task 3: P0 Request Unknown Field Rejection

**Files:**

- Modify: `tests/test_request_env_tool.py`
- Modify: `scripts/env/tools/request/_impl.py`

- [ ] **Step 1: Add focused request.create test**

In `tests/test_request_env_tool.py`, add:

```python
def test_create_rejects_unknown_field_before_required_fields(self) -> None:
    instance_json = self._instance_json(instance_id="inst-request-unknown", buddy="dev")
    before = self._objects_state()
    response = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-request-unknown",
        buddy="dev",
        tool="request",
        action="create",
        args={"__unexpected_payload_field__": True},
    )
    after = self._objects_state()
    self.assertFalse(response.get("ok"), msg=response)
    self.assertEqual((response.get("error") or {}).get("code"), "E_REQUEST_PAYLOAD")
    self.assertIn("__unexpected_payload_field__", json.dumps(response, ensure_ascii=True))
    self.assertIs(response.get("state_changed"), False)
    self.assertEqual(before, after)
```

If `tests/test_request_env_tool.py` does not have `_objects_state`, use the existing runtime-state snapshot helper from neighboring tests or add a request-file snapshot helper local to the test class.

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python3 -m pytest tests/test_request_env_tool.py::RequestEnvToolTests::test_create_rejects_unknown_field_before_required_fields -q
```

Expected before implementation:

- failure because response reports `track_id is required`.

- [ ] **Step 3: Implement unknown-field check first**

In `scripts/env/tools/request/_impl.py`, at the top of `create_request`, before reading `track_id`, add:

```python
unknown = sorted(key for key in args if key not in _allowed(action))
if unknown:
    return _reject_payload(
        action=action,
        active_buddy=active_buddy,
        message=f"unsupported payload fields: {', '.join(unknown)}",
        correctable_fields=unknown,
    )
```

Do not add a central validator.

- [ ] **Step 4: Run payload contract tests**

Run:

```bash
python3 -m pytest tests/test_request_env_tool.py tests/test_env_tool_payload_contract.py -q
```

Expected:

- all pass;
- unknown fields are reported for every action before required-field errors.

## Task 4: P0 Artifact Relation Boundary

**Files:**

- Modify: `scripts/env/domain/artifact_relations.py`
- Modify: `tests/test_env_layer_boundaries.py` only if needed after code cleanup.

- [ ] **Step 1: Run current boundary test**

Run:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py::EnvLayerBoundaryTests::test_track_artifact_publication_writes_only_live_in_publication_domain -q
```

Expected before implementation:

- may fail with `scripts/env/domain/artifact_relations.py`.

- [ ] **Step 2: Remove duplicated publication vocabulary where practical**

In `scripts/env/domain/artifact_relations.py`:

- keep `_relation_and_currentness` delegating to `artifact_visibility_domain.artifact_read_decision`;
- avoid string literals that are publication write terms if the same value can be obtained through visibility decisions;
- do not inspect or mutate track `shared_materials` or `close_proof`;
- do not add writes.

For fallback invalid artifact payloads, use neutral values through existing helper constants or leave them out if no valid artifact id exists.

- [ ] **Step 3: If whitelist remains necessary, make it narrow**

Only if code cleanup cannot avoid the boundary term scan, update `tests/test_env_layer_boundaries.py` allowed paths with a comment or assertion proving the file is read-only:

```python
allowed_paths = {
    "scripts/env/domain/publication.py",
    "scripts/env/repos/artifacts.py",
    "scripts/env/repos/tracks.py",
    "scripts/env/domain/artifact_visibility.py",
    "scripts/env/domain/artifact_relations.py",
    "scripts/env/domain/tasks.py",
}
```

Also add a guard:

```python
self.assertNotIn("save_", source)
self.assertNotIn("update_", source)
self.assertNotIn("publish_", source)
```

Prefer Step 2 over whitelisting.

- [ ] **Step 4: Run relation and boundary suites**

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_env_layer_boundaries.py -q
```

Expected:

- relation summary behavior remains green;
- publication boundary tests pass.

## Task 5: P1 Message List `q` And `limit`

**Files:**

- Modify: `tests/test_message_env_tool.py`
- Modify: `scripts/env/tools/message/tool.py`
- Modify: `scripts/env/domain/messages.py`
- Modify: `scripts/env/tools/message/_impl.py`

- [ ] **Step 1: Add message.list q test**

In `tests/test_message_env_tool.py`, add:

```python
def test_message_list_q_filters_active_buddy_inbox_only(self) -> None:
    env_store.create_message(from_buddy="pm", to_buddy="dev", content="Need Wukong proof asset")
    env_store.create_message(from_buddy="design", to_buddy="dev", content="Hero screenshot ready")
    env_store.create_message(from_buddy="market", to_buddy="pm", content="Wukong not in dev inbox")
    env_store.create_message(from_buddy="dev", to_buddy="design", content="Wukong sent by dev")

    instance_json = self._instance_json(instance_id="inst-dev-message-q", buddy="dev")
    response = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-dev-message-q",
        buddy="dev",
        tool="message",
        action="list",
        args={"q": "wukong"},
    )
    self.assertTrue(response.get("ok"), msg=response)
    messages = response.get("messages", [])
    self.assertEqual(len(messages), 1, msg=response)
    self.assertEqual(messages[0]["from_buddy"], "pm")
    self.assertEqual(messages[0]["to_buddy"], "dev")
    self.assertIn("Wukong", messages[0]["content"])
```

- [ ] **Step 2: Add message.list limit test**

In `tests/test_message_env_tool.py`, add:

```python
def test_message_list_limit_bounds_active_buddy_inbox(self) -> None:
    env_store.create_message(from_buddy="pm", to_buddy="dev", content="one")
    env_store.create_message(from_buddy="design", to_buddy="dev", content="two")
    env_store.create_message(from_buddy="market", to_buddy="dev", content="three")

    instance_json = self._instance_json(instance_id="inst-dev-message-limit", buddy="dev")
    response = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-dev-message-limit",
        buddy="dev",
        tool="message",
        action="list",
        args={"limit": 2},
    )
    self.assertTrue(response.get("ok"), msg=response)
    messages = response.get("messages", [])
    self.assertEqual(len(messages), 2, msg=response)
    self.assertEqual(response.get("discovery_summary", {}).get("count"), 2)
```

- [ ] **Step 3: Add rejection tests for product-binding fields**

In `tests/test_message_env_tool.py`, add:

```python
def test_message_list_rejects_product_binding_fields(self) -> None:
    instance_json = self._instance_json(instance_id="inst-dev-message-bindings", buddy="dev")
    for field, value in (
        ("track_id", "track-x"),
        ("artifact_id", "art-x"),
        ("request_id", "req-x"),
        ("refs", []),
    ):
        with self.subTest(field=field):
            response = self._dispatch(
                instance_json=instance_json,
                instance_id="inst-dev-message-bindings",
                buddy="dev",
                tool="message",
                action="list",
                args={field: value},
            )
            self.assertFalse(response.get("ok"), msg=response)
            self.assertEqual((response.get("error") or {}).get("code"), "E_MESSAGE_PAYLOAD")
            self.assertIn(field, json.dumps(response, ensure_ascii=True))
```

- [ ] **Step 4: Run tests and verify failure**

Run:

```bash
python3 -m pytest tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_q_filters_active_buddy_inbox_only tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_limit_bounds_active_buddy_inbox tests/test_message_env_tool.py::MessageEnvToolTests::test_message_list_rejects_product_binding_fields -q
```

Expected before implementation:

- q and limit tests fail because fields are unsupported;
- product-binding rejections may already pass for some fields but must include field names.

- [ ] **Step 5: Update message tool definition**

In `scripts/env/tools/message/tool.py`, add `q` and `limit` to `message.list` input schema:

```python
"q": {
    "type": "string",
    "description": "Optional case-insensitive keyword filter over active-buddy inbox message content.",
},
"limit": {
    "type": "integer",
    "description": "Optional maximum number of inbox messages to return.",
    "minimum": 1,
},
```

Do not add `track_id`, `artifact_id`, `request_id`, or `refs`.

- [ ] **Step 6: Update message domain list normalization**

In `scripts/env/domain/messages.py`:

- extend `ListRequest` with `q: str | None` and `limit: int`;
- normalize `q` to lowercase stripped string or `None`;
- normalize `limit` to positive integer default 20;
- reject non-string `q`;
- reject non-positive or non-integer `limit`.

Implementation shape:

```python
class ListRequest(TypedDict):
    buddy: str | None
    q: str | None
    limit: int
```

```python
q_raw = args.get("q")
q = None
if q_raw is not None:
    if not isinstance(q_raw, str):
        raise MessagePayloadError("q must be a string", correctable_fields=["q"])
    q = q_raw.strip().lower() or None

limit_raw = args.get("limit", 20)
if not isinstance(limit_raw, int) or limit_raw <= 0:
    raise MessagePayloadError("limit must be a positive integer", correctable_fields=["limit"])
```

Return `{"buddy": normalized_buddy, "q": q, "limit": limit_raw}`.

- [ ] **Step 7: Apply q and limit after inbox visibility**

In `scripts/env/domain/messages.py`, update `filter_inbox_messages` signature:

```python
def filter_inbox_messages(
    *,
    messages: list[dict[str, Any]],
    active_buddy: str,
    sender_buddy: str | None = None,
    q: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
```

Implementation:

```python
inbox = [message for message in messages if message.get("to_buddy") == active_buddy]
if sender_buddy is not None:
    inbox = [message for message in inbox if message.get("from_buddy") == sender_buddy]
if q:
    inbox = [message for message in inbox if q in str(message.get("content") or "").lower()]
inbox.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or "")), reverse=True)
return inbox[:limit]
```

- [ ] **Step 8: Wire _impl**

In `scripts/env/tools/message/_impl.py`, pass normalized q/limit:

```python
inbox = context.rules.message.filter_inbox_messages(
    messages=all_messages,
    active_buddy=active_buddy,
    sender_buddy=request["buddy"],
    q=request["q"],
    limit=request["limit"],
)
```

Return filters in `discovery_summary`:

```python
"discovery_summary": {
    "count": len(inbox),
    "filters": {"buddy": request["buddy"], "q": request["q"], "limit": request["limit"]},
}
```

- [ ] **Step 9: Run message tests**

Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_env_tool_schema_contract.py tests/test_env_tool_semantic_contract.py -q
```

Expected:

- message tests pass;
- schema/semantic tests recognize new fields.

## Task 6: P1 Buddybox Logical Name Policy

**Files:**

- Modify: `tests/test_buddybox_env_tool.py`
- Modify: `scripts/env/domain/buddybox_workspace.py`

- [ ] **Step 1: Add buddybox desc policy test**

In `tests/test_buddybox_env_tool.py`, add:

```python
def test_desc_exposes_logical_name_policy_without_business_sop(self) -> None:
    instance_json = self._instance_json(instance_id="inst-dev-buddybox-policy", buddy="dev")
    response = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-dev-buddybox-policy",
        buddy="dev",
        tool="buddybox",
        action="desc",
        args={},
    )
    self.assertTrue(response.get("ok"), msg=response)
    desc = response.get("buddybox_desc")
    self.assertIsInstance(desc, dict, msg=response)
    policy = desc.get("logical_name_policy") if isinstance(desc, dict) else None
    self.assertIsInstance(policy, dict, msg=desc)
    text = json.dumps(policy, ensure_ascii=True).lower()
    for snippet in ("relative", "absolute", "..", "buddy prefix"):
        self.assertIn(snippet, text)
    self.assertIn("notes/todo.md", text)
    self.assertNotIn("coordination/", text)
    self.assertNotIn("execution/", text)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_desc_exposes_logical_name_policy_without_business_sop -q
```

Expected before implementation:

- fails because `logical_name_policy` is absent.

- [ ] **Step 3: Add policy to buddybox descriptor**

In `scripts/env/domain/buddybox_workspace.py`, add:

```python
def _logical_name_policy() -> dict[str, Any]:
    return {
        "scope": "active_buddy_private_relative_path",
        "valid_shape": "non-empty relative logical_name without absolute prefix, buddy prefix, or '..' traversal",
        "invalid_patterns": [
            {"pattern": "absolute path", "reason": "logical_name must be relative"},
            {"pattern": ".. traversal", "reason": "logical_name must stay inside active buddy private root"},
            {"pattern": "manifest buddy prefix", "reason": "logical_name is already relative to the active buddy private capability"},
        ],
        "examples": ["notes/todo.md", "scratch/analysis.md"],
    }
```

Include it in `build_buddybox_desc`:

```python
"logical_name_policy": _logical_name_policy(),
```

Do not include role/business directories.

- [ ] **Step 4: Run buddybox tests**

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py -q
```

Expected:

- all buddybox tests pass;
- rejection behavior remains unchanged and structured.

## Task 7: P1 Context Message Cues

**Files:**

- Modify: `tests/test_context_binding_env_tool.py` or `tests/test_host_decision_surface_product_mode.py`
- Modify: `scripts/env/tools/context/tool.py`
- Modify: `scripts/env/tools/context/_impl.py`
- Possibly modify: `scripts/env/tool_runtime/context.py` if a repo access helper is missing.

- [ ] **Step 1: Add context message cue test**

In `tests/test_context_binding_env_tool.py`, add:

```python
def test_context_summarize_includes_compact_active_inbox_message_cues(self) -> None:
    root = env_store.create_message(from_buddy="pm", to_buddy="dev", content="Need proof asset")
    reply = env_store.create_message(from_buddy="design", to_buddy="dev", content="Screenshot ready", reply_to=root["id"])
    env_store.create_message(from_buddy="dev", to_buddy="pm", content="Sent by dev only")
    env_store.create_message(from_buddy="market", to_buddy="pm", content="Not dev inbox")

    instance_json = self._instance_json()
    payload = self._dispatch(instance_json=instance_json, tool="context", action="summarize", args={})
    self.assertTrue(payload.get("ok"), msg=payload)
    cues = payload.get("message_cues")
    self.assertIsInstance(cues, dict, msg=payload)
    rows = cues.get("latest")
    self.assertIsInstance(rows, list, msg=cues)
    ids = [row.get("message_id") for row in rows if isinstance(row, dict)]
    self.assertIn(root["id"], ids)
    self.assertIn(reply["id"], ids)
    for row in rows:
        if isinstance(row, dict):
            self.assertEqual(row.get("to_buddy"), "dev")
            self.assertNotIn("content", row)
    self.assertGreaterEqual(cues.get("count", 0), 2)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py::ContextBindingEnvToolTests::test_context_summarize_includes_compact_active_inbox_message_cues -q
```

Expected before implementation:

- fails because `message_cues` is absent.

- [ ] **Step 3: Add message cue row builder**

In `scripts/env/tools/context/_impl.py`, add:

```python
def _message_cues(*, active_buddy: str, limit_value: int, context: ContextServiceContext) -> dict[str, Any]:
    inbox = context.rules.message.filter_inbox_messages(
        messages=context.repos.message.list_messages(),
        active_buddy=active_buddy,
        sender_buddy=None,
        q=None,
        limit=limit_value,
    )
    latest = [
        {
            "message_id": row.get("id"),
            "from_buddy": row.get("from_buddy"),
            "to_buddy": row.get("to_buddy"),
            "reply_to": row.get("reply_to"),
            "created_at": row.get("created_at"),
        }
        for row in inbox
    ]
    return {"count": len(inbox), "latest": latest}
```

Do not include `content`.

- [ ] **Step 4: Wire summary and tool definition**

In `_current_context_sections`, compute:

```python
message_cues = _message_cues(active_buddy=active_buddy, limit_value=limit_value, context=context)
```

Return it in sections and summary:

```python
"message_cues": message_cues,
```

In `scripts/env/tools/context/tool.py`, add `message_cues` to `context.summarize` returns.

- [ ] **Step 5: Run context response contract tests**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_tool_response_contract.py tests/test_host_decision_surface_product_mode.py -q
```

Expected:

- all pass;
- compact summary does not include full message content.

## Task 8: Contract And Documentation Guardrails

**Files:**

- Modify tests only if needed:
  - `tests/test_repo_consistency.py`
  - `tests/test_runtime_skills.py`
  - `tests/test_parallel_contracts.py`

- [ ] **Step 1: Add or verify no prohibited message fields**

Ensure repo consistency or message tests prove `scripts/env/repos/messages.py` still forbids:

```python
forbidden = {"track_id", "task_id", "artifact_id", "request_id", "refs", "status", "read_at", "recipients", "broadcast"}
```

If `request_id` and `refs` are not currently in `_FORBIDDEN_MESSAGE_FIELDS`, add them to prevent future drift.

- [ ] **Step 2: Verify no workflow engine or scheduler was introduced**

Run:

```bash
rg -n "workflow engine|scheduler|daemon|relation object|message/request/comment bridge" scripts docs tests
```

Expected:

- matches only in docs/spec/memo non-goal text or existing architecture guidance;
- no runtime implementation introduces these constructs.

- [ ] **Step 3: Run architecture guard suites**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py tests/test_parallel_contracts.py tests/test_repo_consistency.py tests/test_runtime_skills.py -q
```

Expected:

- all pass;
- no new sibling tool imports;
- no skill schema mirrors.

## Task 9: Final Verification And Review

**Files:** none

- [ ] **Step 1: Run focused P0/P1 verification**

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_host_decision_surface_product_mode.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_env_tool_router.py tests/test_env_tool_package_independence.py tests/test_env_tool_semantic_contract.py tests/test_env_tool_payload_contract.py -q
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_message_env_tool.py -q
python3 -m pytest tests/test_black_box_tool_runtime.py tests/test_parallel_contracts.py tests/test_repo_consistency.py tests/test_runtime_skills.py -q
```

Expected:

- all commands exit 0.

- [ ] **Step 2: Run full suite**

Run:

```bash
python3 -m pytest -q
```

Expected:

- full suite passes.

- [ ] **Step 3: Manual architecture review**

Review diff:

```bash
git diff -- scripts/env tests docs/spec docs/memo
```

Check:

- no message binding to product objects;
- no scheduler/daemon/workflow engine;
- no relation object;
- public `tool.py` files remain black-box;
- context summary remains compact;
- buddybox remains active-buddy private;
- skills do not copy schema tables.

- [ ] **Step 4: Final status**

Final response must include:

- changed files;
- verification commands and pass/fail output;
- architecture review result;
- remaining risks, if any.

# Artifact Attachments and Design Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add generic private-file import, artifact-owned attachments, buddy-declared artifact template permission enforcement, and Design handoff guidance that uses generic attachment refs without adding a Design-specific tool.

**Architecture:** Keep `artifact` as a buddy-neutral runtime tool. Use `buddybox.import_file` as the generic ingress from local files produced by tools such as Chrome DevTools MCP into the active buddy's private logical-name workspace. Attachments are artifact-owned references to pinned private files: the producer names one active-buddy buddybox `logical_name`, the artifact repository adopts or pins that existing file behind an `attachment_id`, and other buddies read it only through artifact visibility checks. Design business workflow stays in Design skills and handoff templates; runtime code only enforces generic payload, permission, visibility, and durability boundaries.

**Tech Stack:** Python env.tool runtime, artifact repository helpers, runtime broker tests, manifest-derived buddy permissions/templates, Markdown skills/templates, pytest/unittest.

---

## Current Objective And Forward Decision

This is one complete task, implemented in stages but not partially scoped. The final state must cover:

1. Template permissions: artifact writes must enforce each active buddy's `artifact_templates` from `buddyswitch/manifest.toml`.
2. Private file ingress: add `buddybox.import_file` so local files produced by external tools can enter buddybox without base64 reconstruction through the agent context.
3. Attachment actions: add `artifact.attach_file`, `artifact.list_attachments`, and `artifact.get_attachment`.
4. Attachment visibility: attachment read/list follows artifact readability; attachment write is limited to active-buddy-owned drafts.
5. Artifact architecture: no Design-specific artifact schema, no generic asset platform, no capture env tool.
6. Design handoff: update Design skill/template guidance to refer to generic attachment ids and Chrome DevTools MCP screenshots.
7. Attachment references: cross-buddy readers receive stable attachment ids and metadata, never runtime filesystem paths. Any pinned storage path is repository-internal.
8. Ergonomic success path: producers import a local tool output into buddybox once, promote the active-buddy private buddybox `logical_name` into an artifact attachment, and consumers can discover attachments from `track.open` before fetching content.

No transition plan is allowed. Do not keep old invalid template behavior behind compatibility flags. Do not add wrappers or aliases for old behavior.

## Explicit Non-Goals

- Do not implement `capture` as an env tool.
- Do not implement `asset` as an env tool.
- Do not implement Figma, `design_source`, `a11y_scan`, `component_inventory`, `ux_signal`, or visual regression.
- Do not add `design_*`, `ux_*`, `screen_*`, or `screenshot_*` fields to artifact tool payloads.
- Do not make attachment actions available only to Design.
- Do not edit `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.

## Existing Files And Responsibilities

- `buddyswitch/manifest.toml`: buddy skill, permission, and `artifact_templates` declarations.
- `scripts/env_manifest.py`: manifest validation vocabulary.
- `scripts/env/repos/artifacts.py`: artifact persistence, validation, revision updates, and new attachment repository helpers.
- `scripts/env/repos/runtime_files.py`: runtime root constants and safe file write helpers.
- `scripts/env/repos/buddybox_files.py`: active-buddy private file validation, local file import, and private file persistence.
- `scripts/env/domain/artifact_visibility.py`: read visibility decisions used by artifact reads.
- `scripts/env/tools/buddybox/tool.py`: buddybox action definitions and generic private-file import semantics.
- `scripts/env/tools/buddybox/_impl.py`: buddybox request validation and ToolResult responses.
- `scripts/env/tools/artifact/tool.py`: artifact tool action definitions and runtime discovery semantics.
- `scripts/env/tools/artifact/_impl.py`: artifact tool request validation and ToolResult responses.
- `scripts/env/tools/track/_impl.py`: track page output; should expose attachment summaries on readable material/proof refs.
- `scripts/env/tool_runtime/context.py`: host-owned context passed to tool implementations.
- `tests/test_artifact_env_tool.py`: main artifact integration behavior tests.
- `tests/test_env_tool_semantic_contract.py`: runtime action vocabulary and semantics tests.
- `tests/test_black_box_tool_runtime.py`: black-box env.tool architecture tests.
- `tests/test_env_client_payload_cli.py`: generated CLI command behavior.
- `tests/test_env_tool_response_contract.py`: ToolResult success/rejection shape.
- `tests/test_runtime_skills.py`: skill materialization and runtime guidance expectations.
- `tests/test_repo_consistency.py`: repository-wide guardrails.
- `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`: current Design handoff body template until the larger Design skill split replaces it.

## Stage 1: Template Permission Hardening

### Task 1: Add Failing Tests For Buddy Template Permissions

**Files:**

- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_env_tool_response_contract.py`

- [x] Add create-revision tests proving active buddy template permissions are enforced from manifest:
  - PM accepts `brief`, `decision`, `note`.
  - PM rejects `design`, `proof`.
  - Design accepts `design`, `brief`.
  - Design rejects `decision`, `note`, `proof`.
  - Dev accepts `brief`, `note`.
  - Test accepts `proof` and rejects `brief`.
  - Market accepts `brief` and rejects `design`.

- [x] Add update-metadata test proving an owned artifact cannot be changed to a template not declared for the active buddy.

- [x] Rejections must assert:
  - `ok=false`
  - error code `E_ARTIFACT_TEMPLATE_PERMISSION`
  - `permission_boundary="artifact.template_permission"`
  - `state_changed=false`
  - `durability="none"`
  - `correctable_fields=["template"]`
  - no artifact create/update mutation happened.

- [x] Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected before implementation: new template permission tests fail because global template-valid values are currently accepted regardless of active buddy.

### Task 2: Implement Manifest-Derived Template Permission Helper

**Files:**

- Modify: `scripts/env/tools/artifact/_impl.py`

- [x] Add a helper that reads active buddy `artifact_templates` from `context["manifest"]`.

Required behavior:

```python
def _allowed_templates_for_active_buddy(context: ArtifactServiceContext) -> tuple[str, ...]:
    active_buddy = context["active_buddy"]
    buddies = context.get("manifest", {}).get("buddies", [])
    if not isinstance(buddies, list):
        return ()
    for buddy in buddies:
        if not isinstance(buddy, dict) or buddy.get("id") != active_buddy:
            continue
        templates = buddy.get("artifact_templates")
        if not isinstance(templates, list):
            return ()
        return tuple(row for row in templates if isinstance(row, str) and row.strip())
    return ()
```

- [x] Add a rejection helper:

```python
def _reject_template_permission(
    *,
    action: str,
    active_buddy: str,
    template: str,
    allowed_templates: tuple[str, ...],
) -> dict[str, Any]:
    allowed = ", ".join(allowed_templates) if allowed_templates else "none"
    return tool_results.rejection(
        tool="artifact",
        action=action,
        active_buddy=active_buddy,
        code="E_ARTIFACT_TEMPLATE_PERMISSION",
        message=f"template '{template}' is not declared for active buddy '{active_buddy}'",
        permission_boundary="artifact.template_permission",
        human_summary="Artifact template is not allowed for the active buddy.",
        why_blocked=f"Active buddy '{active_buddy}' may create or update only these artifact templates: {allowed}.",
        impact="No artifact state changed.",
        state_changed=False,
        retryable=True,
        retry_guidance="Use one template declared for the active buddy in manifest artifact_templates.",
        allowed_next_actions=[
            "Use context.get to inspect active buddy capabilities.",
            "Retry artifact.create_revision or artifact.update_metadata with an allowed template.",
        ],
        correctable_fields=["template"],
        field_errors=[
            {
                "path": "template",
                "message": "template must be declared for the active buddy",
                "allowed_values": list(allowed_templates),
                "example": allowed_templates[0] if allowed_templates else "brief",
            }
        ],
    )
```

- [x] Call the helper after global vocabulary validation and before artifact creation/update.

- [x] Keep the helper generic. It must not branch on `"design"` or any other specific buddy id.

- [x] Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected after implementation: template permission tests pass and pre-existing artifact tests still pass.

## Stage 2: Generic Buddybox File Import Ingress

### Task 3: Add Failing Buddybox Import Tests

**Files:**

- Modify: `tests/test_buddybox_env_tool.py`
- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_black_box_tool_runtime.py`
- Modify: `tests/test_env_client_payload_cli.py`

- [x] Add `import_file` to expected buddybox action sets.
- [x] Add operation semantics coverage for `buddybox.import_file`.
- [x] Add CLI coverage for:

```bash
python3 scripts/env/client.py buddybox import-file --payload '<json-object>'
```

- [x] Add behavior tests proving:
  - importing a regular local file writes one active-buddy private file at `logical_name`
  - response returns the private file summary only
  - response does not include `source_path`, buddybox root, or any filesystem path
  - imported file can be read back through `buddybox.read`
  - source file is not mutated or deleted
  - missing, directory, symlink-escaping, runtime-object, and runtime-local source paths are rejected without writing a buddybox file

Representative test:

```python
def test_import_file_writes_private_file_without_exposing_paths(self) -> None:
    instance_json = self._instance_json(instance_id="inst-buddybox-import", buddy="design")
    source = self._runtime_path("tmp/chrome-devtools/desktop.png")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"\x89PNG\r\n")

    imported = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-buddybox-import",
        buddy="design",
        tool="buddybox",
        action="import_file",
        args={
            "logical_name": "screenshots/desktop.png",
            "source_path": str(source),
            "content_type": "image/png",
        },
    )

    self.assertTrue(imported.get("ok"), msg=imported)
    self.assertEqual(imported.get("logical_name"), "screenshots/desktop.png")
    self.assertEqual(imported.get("content_type"), "image/png")
    self.assertNotIn("source_path", imported)
    self.assertNotIn("path", imported)

    read_back = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-buddybox-import",
        buddy="design",
        tool="buddybox",
        action="read",
        args={"logical_name": "screenshots/desktop.png", "encoding": "base64"},
    )
    self.assertTrue(read_back.get("ok"), msg=read_back)
    self.assertEqual(read_back.get("content_base64"), "iVBORw0K")
    self.assertTrue(source.exists())
```

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_env_client_payload_cli.py -q
```

Expected before implementation: missing `buddybox.import_file` action and behavior failures.

### Task 4: Implement Buddybox Import File

**Files:**

- Modify: `scripts/env/repos/buddybox_files.py`
- Modify: `scripts/env/tools/buddybox/tool.py`
- Modify: `scripts/env/tools/buddybox/_impl.py`

- [x] Add repository helper `import_private_file(...)` that copies bytes from one allowed local source file into an active-buddy private logical name using the existing atomic private-file write path.

Required helper shape:

```python
def import_private_file(
    *,
    root: Path,
    logical_name: str,
    source_path: Path,
    allowed_roots: tuple[Path, ...],
    blocked_roots: tuple[Path, ...],
) -> tuple[bool, str, int]:
    ...
```

- [x] Source path validation:
  - required non-empty string accepted by the tool handler
  - resolves to an existing regular file
  - resolved source stays inside one allowed root
  - resolved source does not stay inside any blocked root such as `runtime_files.OBJECTS_ROOT` or `runtime_files.LOCAL_ROOT`
  - symlinks that resolve outside allowed roots are rejected
  - directories are rejected

- [x] Allowed roots are intentionally narrow and generic:
  - `runtime_files.runtime_workspace_root(context["instance_payload"])`
  - `Path(tempfile.gettempdir())`

- [x] Add `ActionDefinition` for `buddybox.import_file`.

Input schema:

```python
{
    "type": "object",
    "additionalProperties": False,
    "required": ["logical_name", "source_path"],
    "properties": {
        "logical_name": {"type": "string", "description": "Private logical_name to write inside the active buddy buddybox."},
        "source_path": {"type": "string", "description": "Local file path produced by another tool; not stored or returned."},
        "content_type": {"type": "string", "description": "Optional MIME content type metadata."},
    },
}
```

Semantics:

- kind: `write`
- mutates: `runtime_files`
- required_permission: `buddybox.write`
- authority: `buddybox.private_local_scope`
- visibility: `active-buddy private`
- durability: `durable`
- reads: one allowed local source file
- writes: one active-buddy private buddybox file
- does_not_write: tracks, tasks, artifacts, requests, comments, messages, browser session
- returns: private file summary only, never source path or buddybox filesystem path

- [x] Implement handler `import_buddybox_file_for_active_buddy`.
- [x] Add the handler to `_ACTION_HANDLERS`.
- [x] Keep `buddybox.write` unchanged; do not add a third payload mode to it.
- [x] Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_env_client_payload_cli.py -q
```

Expected after implementation: buddybox import tests pass and existing buddybox read/write/delete behavior remains unchanged.

## Stage 3: Artifact Attachment Repository Model

### Task 5: Add Failing Attachment Repository Tests

**Files:**

- Modify: `tests/test_artifact_env_tool.py`

- [x] Add tests proving artifacts without `attachments` validate as `attachments=[]`.
- [x] Add tests proving `artifact.get` returns attachment summary metadata but not blob content.
- [x] Add tests proving `track.open` material/proof rows expose `attachment_count` and attachment summary ids for readable artifacts.
- [x] Add tests proving unsafe attachment metadata is rejected by repository validation.

Expected before implementation: validation tests fail because `validate_artifact` does not preserve or validate an `attachments` field.

### Task 6: Implement Attachment Metadata And Pinned File Helpers

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `scripts/env/repos/artifacts.py`

- [x] In `runtime_files.py`, add an internal pinned attachment root constant:

```python
ARTIFACT_ATTACHMENTS_DIR = OBJECTS_ROOT / "artifact-attachments"
```

Update `_recompute_runtime_roots()` so the constant follows runtime root overrides.

- [x] In `runtime_files.ensure_runtime_dirs()`, create `ARTIFACT_ATTACHMENTS_DIR`.

- [x] In `artifacts.py`, add attachment metadata validation:

Required row shape:

```python
{
    "attachment_id": "att-...",
    "filename": "desktop.png",
    "content_type": "image/png",
    "size_bytes": 12345,
    "sha256": "<64 lowercase hex chars>",
    "created_by": "design",
    "created_at": "...",
}
```

- [x] Add filename normalization:
  - required non-empty string
  - no `/`
  - no `\`
  - no `..`
  - not `"."`
  - not `".."`.

- [x] Add internal pinned-file path helper:

```python
def attachment_file(artifact_id: str, attachment_id: str) -> Path:
    return runtime_files.ARTIFACT_ATTACHMENTS_DIR / runtime_files.require_id(artifact_id, "artifact id") / f"{runtime_files.require_id(attachment_id, 'attachment id')}.bin"
```

- [x] Add repository helpers:
  - `attachment_summaries(artifact_id: str) -> list[dict[str, Any]]`
  - `adopt_buddybox_attachment(artifact_id: str, filename: str, created_by: str, source_logical_name: str, content_type: str | None, context: ToolContext) -> tuple[dict[str, Any], dict[str, Any]]`
  - `get_attachment_content(artifact_id: str, attachment_id: str) -> tuple[dict[str, Any], bytes]`

- [x] `adopt_buddybox_attachment` must not expose the buddybox path. It should validate the active-buddy private file through buddybox repository helpers, compute `size_bytes` and `sha256`, then pin the existing file under artifact-owned storage. Prefer hardlink/reflink/rename-style adoption where safe; copying is allowed only as an internal durability fallback and must not appear in the tool contract.

- [x] Store attachment summaries on the artifact object in an `attachments` list.

- [x] Do not store file content in artifact JSON.

- [x] Do not expose blob filesystem paths in artifact JSON, `artifact.get`, `artifact.list_attachments`, or `artifact.get_attachment` responses.

- [x] Use `runtime_files.write_json_object` and safe runtime write checks for metadata. Use a helper in `artifacts.py` for file adoption/pinning so `scripts/env/tools/artifact/_impl.py` does not write direct paths or reconstruct file bytes.

- [x] Update `validate_artifact()` return payload to include:

```python
"attachments": attachments,
```

- [x] Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected after implementation: repository-level attachment tests pass.

## Stage 4: Artifact Tool Actions

### Task 7: Add Failing Tool Contract Tests For Attachment Actions

**Files:**

- Modify: `tests/test_env_tool_semantic_contract.py`
- Modify: `tests/test_black_box_tool_runtime.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_env_client_payload_cli.py`

- [x] Add `attach_file`, `list_attachments`, and `get_attachment` to expected artifact action sets.
- [x] Add adjacent-boundary semantic assertions for each new action.
- [x] Add CLI tests for generated commands:
  - `artifact attach-file`
  - `artifact list-attachments`
  - `artifact get-attachment`
- [x] Add tests proving direct env.tool dispatch requires underscore action ids and rejects hyphenated action ids.

Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_env_client_payload_cli.py tests/test_repo_consistency.py -q
```

Expected before implementation: missing-action failures.

### Task 8: Define Generic Attachment Actions

**Files:**

- Modify: `scripts/env/tools/artifact/tool.py`

- [x] Add `ActionDefinition` for `attach_file`.

Input schema:

```python
{
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_id", "filename", "source_buddybox_logical_name"],
    "properties": {
        "artifact_id": {"type": "string", "description": "Active-buddy-owned draft artifact id to attach a file to."},
        "filename": {"type": "string", "description": "Display filename without path separators."},
        "source_buddybox_logical_name": {"type": "string", "description": "Active-buddy private buddybox logical_name to promote into this artifact attachment."},
        "content_type": {"type": "string", "description": "Optional MIME content type metadata."}
    }
}
```

Semantics:

- kind: `write`
- mutates: `runtime_objects`
- required_permission: `artifact.update`
- visibility: owner-scoped draft attachment metadata until artifact is readable through later publication
- durability: `durable`
- writes: artifact attachment metadata and an internal pinned attachment file reference
- does_not_write: track state, task state, requests, comments, messages, buddybox files, browser session. Promoting from buddybox reads the private file and does not mutate it. The attachment response exposes only an attachment id and metadata, not the buddybox path.

- [x] Add `ActionDefinition` for `list_attachments`.

Input schema:

```python
{
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_id"],
    "properties": {
        "artifact_id": {"type": "string", "description": "Readable artifact id whose attachment summaries should be listed."}
    }
}
```

Semantics:

- kind: `read`
- mutates: `none`
- required_permission: `artifact.read`
- result content: attachment summary rows only

- [x] Add `ActionDefinition` for `get_attachment`.

Input schema:

```python
{
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_id", "attachment_id"],
    "properties": {
        "artifact_id": {"type": "string", "description": "Readable artifact id that owns the attachment."},
        "attachment_id": {"type": "string", "description": "Exact attachment id to read."}
    }
}
```

Semantics:

- kind: `read`
- mutates: `none`
- required_permission: `artifact.read`
- result content: one attachment metadata row plus `content_base64`

- [x] Keep action names generic. Do not mention Design or screenshots in action definitions.

- [x] Run:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py -q
```

Expected after implementation: action discovery and semantic contract tests pass.

### Task 9: Implement Attachment Tool Handlers

**Files:**

- Modify: `scripts/env/tools/artifact/_impl.py`

- [x] Add payload rejection helpers for attachment fields:
  - unsafe filename
  - missing `source_buddybox_logical_name`
  - unsupported inline `content` or `content_base64`
  - empty source file bytes
  - invalid buddybox logical name
  - unknown attachment id

- [x] Add `attach_file` handler:
  - validate allowed fields
  - require active-buddy-owned draft artifact
  - reject foreign artifacts with `artifact.buddy_scope`
  - reject already published artifacts with `artifact.lifecycle_status`
  - validate `source_buddybox_logical_name` through active-buddy buddybox access
  - call repository `adopt_buddybox_attachment`
  - return summary only, not blob bytes
  - return `attachment_id`, not a local filesystem path
  - include next actions for `artifact.list_attachments`, `artifact.get_attachment`, and `artifact.get`

- [x] Add `list_attachments` handler:
  - validate readable artifact via `context.rules.artifact_visibility.artifact_read_decision`
  - return summaries only
  - reject unreadable artifacts using artifact read-scope feedback

- [x] Add `get_attachment` handler:
  - validate readable artifact via existing artifact visibility decision
  - fetch exact pinned attachment content through repository helper
  - return `content_base64` only, so binary and text attachments share one output shape

- [x] Add handlers to `_ACTION_HANDLERS`.

- [x] Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_env_tool_response_contract.py -q
```

Expected after implementation: attachment behavior and ToolResult shape tests pass.

## Stage 5: Runtime Discovery, Context, And Guardrails

### Task 10: Make Cross-Buddy Attachment Discovery Obvious

**Files:**

- Modify: `scripts/env/tools/track/_impl.py`
- Modify: `scripts/env/domain/artifact_visibility.py` if shared summary helpers are cleaner there.
- Modify: `tests/test_track_env_tool.py`
- Modify: `tests/test_env_layer_end_to_end.py`

- [x] Add attachment summary metadata to readable material/proof refs returned by `track.open`.

Required shape on each readable artifact ref:

```python
{
    "attachment_count": 1,
    "attachments": [
        {
            "attachment_id": "att-...",
            "filename": "desktop.png",
            "content_type": "image/png",
            "size_bytes": 12345,
            "sha256": "<64 lowercase hex chars>",
        }
    ]
}
```

- [x] For unreadable refs, expose `attachment_count=0` and `attachments=[]` or omit both; do not leak private draft attachment metadata.
- [x] Do not include blob bytes.
- [x] Do not include filesystem paths.
- [x] Keep `artifact.get` as the full artifact body read and `artifact.get_attachment` as the content fetch.

Expected user path after this task:

1. Producer creates draft, attaches files, publishes artifact.
2. Consumer calls `track.open`.
3. Consumer sees attachment ids on material/proof rows.
4. Consumer calls `artifact.get_attachment` only for the files they need.

Run:

```bash
python3 -m pytest tests/test_track_env_tool.py tests/test_env_layer_end_to_end.py -q
```

Expected after implementation: cross-buddy track page tests pass.

### Task 11: Update Context/Discovery Expectations

**Files:**

- Modify only tests if registry projections already derive from definitions.
- Modify `scripts/env/tools/context/_impl.py` only if capability snapshot hardcodes old artifact action assumptions.

- [x] Verify `context.get.tool_catalog["artifact"].operations` includes the new actions.
- [x] Verify `context.get.operation_semantics` includes the new actions.
- [x] Verify no extra prose mirror or duplicate schema table is introduced.

Run:

```bash
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_env_layer_end_to_end.py -q
```

Expected: context projections expose new actions from runtime definitions.

### Task 12: Preserve Tool Independence

**Files:**

- Modify tests only unless failures expose real architecture violations.

- [x] Run:

```bash
python3 -m pytest tests/test_env_tool_package_independence.py tests/test_black_box_tool_runtime.py -q
```

- [x] Fix any violation by moving path, pinned-file, or validation logic into `scripts/env/repos/artifacts.py` or `scripts/env/repos/runtime_files.py`.

Expected: artifact tool package remains a black-box tool with one public `tool.py` and implementation using local modules/context-owned repo helpers.

## Stage 6: Design Skill And Handoff Guidance

### Task 13: Update Design Handoff Template Without Tool Leakage

**Files:**

- Modify: `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`
- Modify: `buddyswitch/skills/design/shape-prototype/SKILL.md`
- Later Design skill split may move this content to `prepare-dev-handoff/assets/design-handoff-template.md`; if that split lands first, update the new file instead and remove stale references from `shape-prototype`.

- [x] Add a stable handoff section for attachment references.

Required section content concept:

```markdown
## Assets and Attachments

- Artifact attachments:
  - `<attachment_id>`: `<filename>` — `<purpose/provenance>`
- Screenshot provenance:
  - Captured with chrome-devtools-cockpit when visual evidence is needed.
  - Attached through generic artifact attachment actions.
```

- [x] Do not inline binary content.
- [x] Do not instruct Design to use a `capture` env tool.
- [x] Do not say attachments are Design-only.
- [x] Keep Design business judgment in skill text: when screenshots help handoff, when no screenshot exists, and how to cite attachment ids.

### Task 14: Add Skill Boundary Tests

**Files:**

- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

- [x] Assert Design handoff template mentions artifact attachments.
- [x] Assert active guidance mentions `chrome-devtools-cockpit` for screenshot capture where visual evidence is needed.
- [x] Assert no active skill or contract references `capture` as an env tool.
- [x] Assert no artifact tool file includes Design-specific terms such as `design_handoff`, `ux_flow`, `screen_state`, or `screenshot_ref` as payload fields.

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected after implementation: skill/tool boundary tests pass.

## Stage 7: End-To-End Verification

### Task 15: Run Focused Verification

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py -q
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: all focused tests pass.

### Task 16: Run Broader Regression Verification

Run:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_track_env_tool.py tests/test_env_layer_end_to_end.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_env_tool_schema_contract.py tests/test_env_tool_package_independence.py -q
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_env_tool_response_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: all relevant runtime, artifact, discovery, CLI, and skill-boundary tests pass.

### Task 17: Manual Runtime Smoke

Use a launcher runtime workspace, not source checkout direct state edits.

- [x] Start or use a runtime instance:

```bash
./buddyswitch-codex instance start --buddy design
```

- [x] Inside the runtime workspace, run:

```bash
python3 scripts/env/client.py context summarize --payload '{}'
python3 scripts/env/client.py artifact create-revision --payload '{"title":"Design attachment smoke","summary":"smoke","template":"design","body":"# Smoke"}'
```

- [x] Capture the returned `artifact_id`.

- [x] Create a local tool-output source file under `tmp/`:

```bash
mkdir -p tmp/artifact-attachment-smoke
printf 'hello' > tmp/artifact-attachment-smoke/smoke.txt
```

- [x] Import the local source file into the active buddy private buddybox:

```bash
python3 scripts/env/client.py buddybox import-file --payload '{"logical_name":"screenshots/smoke.txt","source_path":"tmp/artifact-attachment-smoke/smoke.txt","content_type":"text/plain"}'
```

- [x] Attach the buddybox file:

```bash
python3 scripts/env/client.py artifact attach-file --payload '{"artifact_id":"<artifact_id>","filename":"smoke.txt","source_buddybox_logical_name":"screenshots/smoke.txt","content_type":"text/plain"}'
```

- [x] Capture the returned `attachment_id`.

- [x] List attachments:

```bash
python3 scripts/env/client.py artifact list-attachments --payload '{"artifact_id":"<artifact_id>"}'
```

- [x] Read the attachment:

```bash
python3 scripts/env/client.py artifact get-attachment --payload '{"artifact_id":"<artifact_id>","attachment_id":"<attachment_id>"}'
```

Expected: create, import, attach, list, and get all return `ok=true`; read returns `content_base64="aGVsbG8="`; no source checkout runtime object files are edited directly.

## Final Acceptance Criteria

- [x] `artifact.create_revision` enforces active buddy template permission.
- [x] `artifact.update_metadata` enforces active buddy template permission when template is patched.
- [x] `buddybox.import_file` imports a local tool-output file into one active-buddy private logical name without exposing filesystem paths in the response.
- [x] `artifact.attach_file` adopts/pins one active-buddy buddybox file as an artifact-owned attachment through repository helpers.
- [x] `artifact.attach_file` promotes active-buddy private buddybox logical names without exposing a path and rejects inline blob payloads.
- [x] `artifact.list_attachments` returns summaries for readable artifacts.
- [x] `artifact.get_attachment` returns exact attachment content as `content_base64` only for readable artifacts.
- [x] `artifact.get` includes attachment summaries and never includes blob bytes.
- [x] New actions appear in runtime discovery, operation semantics, CLI, and response contract tests.
- [x] Attachment read/write permissions are generic and buddy-neutral.
- [x] Attachment writes are draft-only; published artifact attachment changes require a new revision.
- [x] Attachment responses expose stable ids and metadata, not runtime filesystem paths.
- [x] `track.open` exposes attachment summaries for readable material/proof refs so cross-buddy consumers can discover files without guessing.
- [x] Design handoff guidance cites generic attachment actions and Chrome DevTools MCP screenshots.
- [x] No `capture`, `asset`, Figma, a11y, component inventory, or UX signal tool is added.
- [x] No Design-specific logic or schema is added to artifact tool code.
- [x] Focused and broader verification commands pass.

## Execution Notes

- Implement tests first for each stage and confirm they fail for the expected reason before changing implementation.
- Keep commits stage-sized:
  - template permission tests and implementation
  - attachment repository model
  - attachment tool contract/actions
  - attachment behavior handlers
  - skill/guidance updates
  - final verification cleanup
- Do not modify `buddyswitch/objects/**` or `buddyswitch/local/buddybox/**` directly.
- Keep generated runtime files and temporary screenshots out of source-controlled paths.
